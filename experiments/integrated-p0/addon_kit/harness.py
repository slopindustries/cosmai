"""Run one add-on against captured fixtures, with no database, worker, or network.

**What this is for.** An add-on author needs a feedback loop before the platform's
capability layer exists (B0.3), and will still want one afterwards, because a loop
that needs PostgreSQL and a claimed job to tell you a JSON path was wrong is a slow
way to find out a JSON path was wrong.

**What it is not.** Passing here is **not** evidence that an add-on integrates with
the platform. It exercises the add-on's *logic* against the contract's shapes. Four
things the platform does are absent by construction, and each is a real failure mode
this cannot show you:

* **The outbound guard.** `fetch` here reads a file. The real one composes a URL from
  a registered source's approved profile, revalidates redirects, checks resolved
  address ranges, enforces timeouts and size limits, resolves a credential, and
  strips protected headers. An add-on that only ever met this `fetch` has never met a
  refusal.
* **Atomicity.** `emit_raw` and `advance_cursor` here append to a list. In the
  platform they are statements in one transaction with the fenced completion, and an
  interruption between them is the failure `domain.store` exists to prevent.
* **Retry, lease, and attempt budget.** Raising `AddonTransient` here reports a
  transient failure and stops. In the platform it is rescheduled with backoff until a
  budget the add-on cannot see runs out.
* **Persistence.** Nothing is written anywhere. A second run starts from whatever
  cursor you passed, not from what the last run advanced to.

That list is why this module lives in `addon_kit` — the authoring tool — and not in
`addon_host`. Integration evidence comes from the conformance suite and, for real,
from B0.3.

**Fixtures.** A collector's fixture is a directory of captured responses, one file
per endpoint call, named `<endpoint_ref>.<n>.<ext>` — `items.1.json`, `items.2.json`.
Calls to one endpoint are served in that order, so a paginating collector sees page 1
then page 2. Asking for a call with no fixture is an error naming what was missing,
because silently returning an empty page would let a paginating add-on look finished
when it is untested.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from addon_api import (
    AddonError,
    AddonManifest,
    CollectContext,
    CollectOutcome,
    FetchResponse,
    ImportContext,
    Limits,
    NormalizeContext,
    NormalizedResult,
    NormalizeOutcome,
    RawItem,
    SnapshotItem,
)

__all__ = [
    "HarnessError",
    "HarnessResult",
    "Interaction",
    "default_limits",
    "load_fixtures",
    "run_addon",
]

#: `items.1.json` -> endpoint `items`, call 1. The extension is not interpreted;
#: `content_type` comes from the manifest-independent guess below.
_FIXTURE_NAME = re.compile(
    r"^(?P<endpoint>[A-Za-z0-9._-]+)\.(?P<index>\d+)\.(?P<ext>[A-Za-z0-9]+)$"
)

_CONTENT_TYPES: Mapping[str, str] = {
    "json": "application/json",
    "csv": "text/csv",
    "xml": "application/xml",
    "txt": "text/plain",
}


class HarnessError(Exception):
    """The harness itself could not run: a missing fixture, an unusable directory.

    Kept apart from `addon_api.errors` deliberately. An `AddonError` means the add-on
    reported a failure, which is a result worth seeing; a `HarnessError` means the
    question was never put to the add-on.
    """


@dataclass(frozen=True)
class Interaction:
    """One thing the add-on did, in the order it did it.

    The transcript is the output. An author wants to see *what was requested, what
    was emitted, where the cursor went* — not just a pass or a fail.
    """

    kind: str
    detail: Mapping[str, Any]


@dataclass
class HarnessResult:
    """What one run produced. Mutable while running, read afterwards."""

    interactions: list[Interaction] = field(default_factory=list)
    raw_items: list[RawItem] = field(default_factory=list)
    results: list[NormalizedResult] = field(default_factory=list)
    cursors: dict[str, Any] = field(default_factory=dict)
    logs: list[tuple[str, Mapping[str, Any]]] = field(default_factory=list)
    outcome: CollectOutcome | NormalizeOutcome | None = None
    failure: AddonError | None = None

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def emitted_count_disagrees(self) -> bool:
        """Whether the add-on's own count disagrees with what it actually emitted.

        The platform cross-checks these and fails the attempt on a mismatch, so the
        harness surfaces it too: an add-on that miscounts its own work is the cheapest
        signal that it is doing something other than what it thinks.
        """
        if isinstance(self.outcome, CollectOutcome):
            return self.outcome.items_emitted != len(self.raw_items)
        if isinstance(self.outcome, NormalizeOutcome):
            return self.outcome.results_emitted != len(self.results)
        return False


def default_limits() -> Limits:
    """Limits an add-on can read. The harness does not enforce them; the platform does.

    Present so that an add-on which cooperates with `context.limits` can be exercised.
    Deliberately not enforced here: pretending to enforce would teach an author that
    their own bounds checking is what keeps a request bounded, and it is not.
    """
    return Limits(
        connect_timeout_s=5.0,
        read_timeout_s=30.0,
        max_response_bytes=8 * 1024 * 1024,
        max_redirects=3,
        max_pages=20,
        max_records=5000,
    )


def load_fixtures(directory: Path) -> dict[str, list[Path]]:
    """Group `<endpoint>.<n>.<ext>` files by endpoint, in call order."""
    if not directory.is_dir():
        raise HarnessError(f"fixture directory {directory} does not exist")
    grouped: dict[str, list[tuple[int, Path]]] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        match = _FIXTURE_NAME.fullmatch(path.name)
        if match is None:
            continue
        grouped.setdefault(match.group("endpoint"), []).append((int(match.group("index")), path))
    return {
        endpoint: [path for _, path in sorted(entries)]
        for endpoint, entries in grouped.items()
    }


def _content_type_of(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lstrip(".").lower(), "application/octet-stream")


class _Recorder:
    """The capabilities, closed over one `HarnessResult`."""

    def __init__(
        self,
        result: HarnessResult,
        fixtures: Mapping[str, Sequence[Path]],
        status: int = 200,
    ) -> None:
        self._result = result
        self._fixtures = fixtures
        self._served: dict[str, int] = {}
        self._status = status

    def fetch(self, endpoint_ref: str, params: Mapping[str, str]) -> FetchResponse:
        available = self._fixtures.get(endpoint_ref)
        served = self._served.get(endpoint_ref, 0)
        if not available or served >= len(available):
            known = ", ".join(sorted(self._fixtures)) or "none"
            raise HarnessError(
                f"the add-on asked for call {served + 1} of endpoint {endpoint_ref!r} and no "
                f"fixture supplies it; endpoints with fixtures: {known}. Add "
                f"{endpoint_ref}.{served + 1}.json, or stop the add-on earlier."
            )
        path = available[served]
        self._served[endpoint_ref] = served + 1
        body = path.read_bytes()
        self._result.interactions.append(
            Interaction("fetch", {"endpoint_ref": endpoint_ref, "params": dict(params),
                                  "fixture": path.name, "bytes": len(body)})
        )
        return FetchResponse(
            endpoint_ref=endpoint_ref,
            status=self._status,
            headers={"content-type": _content_type_of(path)},
            body=body,
            # A fixed, obviously-fake reference. The platform assigns a real one when
            # it records the envelope; a plausible-looking id here would invite an
            # add-on to store or parse it.
            envelope_ref=f"harness:{path.name}",
            retrieved_at="1970-01-01T00:00:00Z",
        )

    def open_input(self, input_ref: str) -> Iterator[bytes]:
        available = self._fixtures.get(input_ref)
        if not available:
            known = ", ".join(sorted(self._fixtures)) or "none"
            raise HarnessError(
                f"the add-on asked to open input {input_ref!r} and no fixture supplies it; "
                f"inputs with fixtures: {known}"
            )
        path = available[0]
        self._result.interactions.append(
            Interaction("open_input", {"input_ref": input_ref, "fixture": path.name})
        )
        return iter([path.read_bytes()])

    def emit_raw(self, items: Sequence[RawItem]) -> None:
        self._result.raw_items.extend(items)
        self._result.interactions.append(
            Interaction("emit_raw", {"count": len(items),
                                     "item_keys": [item.item_key for item in items]})
        )

    def emit_result(self, results: Sequence[NormalizedResult]) -> None:
        self._result.results.extend(results)
        self._result.interactions.append(
            Interaction("emit_result", {"count": len(results)})
        )

    def advance_cursor(self, stream: str, cursor: Any) -> None:
        self._result.cursors[stream] = cursor
        self._result.interactions.append(
            Interaction("advance_cursor", {"stream": stream, "cursor": cursor})
        )

    def log(self, message: str, fields: Mapping[str, Any]) -> None:
        self._result.logs.append((message, dict(fields)))
        self._result.interactions.append(
            Interaction("log", {"message": message, "fields": dict(fields)})
        )


def run_addon(
    directory: Path,
    fixtures: Mapping[str, Sequence[Path]] | None = None,
    config: Mapping[str, Any] | None = None,
    cursor: Any = None,
    snapshot: Sequence[SnapshotItem] | None = None,
    status: int = 200,
) -> HarnessResult:
    """Load the add-on at `directory` and run it once against `fixtures`.

    Loading is deliberately **not** `addon_host`'s: `addon_kit` may import `addon_api`
    and nothing else local (DP-008 D1, enforced by the direction guard). The two
    loaders are therefore near-duplicates, which is a real cost and is accepted for a
    stated reason — the harness must not be able to reach the platform, because an
    author running it must not be able to depend on the platform by accident. The
    version gate, the `sys.modules` bookkeeping, and the error translation that make
    `addon_host` load-bearing are all absent here on purpose.
    """
    manifest = AddonManifest.load(directory / "addon.toml")
    entry = _load_entry(directory, manifest)
    result = HarnessResult()
    recorder = _Recorder(result, fixtures or {}, status)
    context = _context_for(manifest, recorder, config or {}, cursor, snapshot or [])

    try:
        outcome = entry(context)
    except AddonError as error:
        result.failure = error
        return result
    result.outcome = outcome
    return result


def _load_entry(directory: Path, manifest: AddonManifest) -> Any:
    import importlib.util

    path = directory / f"{manifest.entry_module}.py"
    if not path.is_file():
        raise HarnessError(f"{manifest.entry!r} names {path.name}, which is not a file")
    spec = importlib.util.spec_from_file_location(f"addon_kit_harness_{manifest.addon_id}", path)
    if spec is None or spec.loader is None:
        raise HarnessError(f"{path} cannot be loaded as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = getattr(module, manifest.entry_attribute, None)
    if not callable(entry):
        raise HarnessError(f"{manifest.entry!r} names something that is not callable")
    return entry


def _context_for(
    manifest: AddonManifest,
    recorder: _Recorder,
    config: Mapping[str, Any],
    cursor: Any,
    snapshot: Sequence[SnapshotItem],
) -> CollectContext | ImportContext | NormalizeContext:
    """Build the real contract context for this kind.

    The contexts are `addon_api`'s own dataclasses, not harness look-alikes. That is
    the one thing this module must get right: an author who codes against what the
    harness passes must be coding against the contract, or the loop teaches a
    fiction.
    """
    if manifest.kind == "collector":
        return CollectContext(
            source_id="harness",
            config=config,
            cursor=cursor,
            limits=default_limits(),
            fetch=recorder.fetch,
            emit_raw=recorder.emit_raw,
            advance_cursor=recorder.advance_cursor,
            log=recorder.log,
        )
    if manifest.kind == "importer":
        return ImportContext(
            source_id="harness",
            config=config,
            cursor=cursor,
            limits=default_limits(),
            open_input=recorder.open_input,
            emit_raw=recorder.emit_raw,
            advance_cursor=recorder.advance_cursor,
            log=recorder.log,
        )
    return NormalizeContext(
        run_id="harness-run",
        snapshot_id="harness-snapshot",
        config=config,
        read_snapshot=lambda: iter(snapshot),
        emit_result=recorder.emit_result,
        log=recorder.log,
    )


def format_report(result: HarnessResult, manifest: AddonManifest) -> str:
    """A transcript an author reads, not a machine-readable result."""
    lines = [f"{manifest.addon_id}@{manifest.addon_version} ({manifest.kind})", ""]
    for step, interaction in enumerate(result.interactions, start=1):
        detail = json.dumps(interaction.detail, sort_keys=True, default=str)
        lines.append(f"  {step:>3}. {interaction.kind:<15} {detail}")
    lines.append("")

    if result.failure is not None:
        failure = result.failure
        lines.append(f"  FAILED  {type(failure).__name__}: {failure.summary}")
        if failure.detail:
            lines.append(f"          detail: {json.dumps(dict(failure.detail), default=str)}")
        lines.append("")
        lines.append("  In the platform this class decides whether the attempt is retried.")
        return "\n".join(lines)

    lines.append(f"  emitted   {len(result.raw_items)} raw item(s), "
                 f"{len(result.results)} result(s)")
    lines.append(f"  cursors   {json.dumps(result.cursors, sort_keys=True, default=str)}")
    lines.append(f"  outcome   {result.outcome}")
    if result.emitted_count_disagrees():
        lines.append("")
        lines.append("  WARNING   the outcome's own count disagrees with what was emitted.")
        lines.append("            The platform cross-checks these and fails the attempt.")
    return "\n".join(lines)
