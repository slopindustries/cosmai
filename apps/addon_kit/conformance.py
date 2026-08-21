"""The suite an add-on author runs against any add-on, before a host ever sees it.

**Why this module exists rather than being a copy-adapt.** M3's task packet asked for
P0's conformance suite, copy-adapted. `[확인 사실]` P0 never built one.
`experiments/integrated-p0/EXP-002-addon-layer.md` names it explicitly as work
"deliberately deferred: without the capability layer it could [not be built]" and
`EXP-003-capability-layer.md` still lists "the conformance suite" among what remains
after the capability layer landed. `docs/decisions/DP-008-addon-architecture.md`
counts it among the architecture's costs; nothing in the P0 tree implements it as a
runnable tool. What P0 built instead — and what
`contracts/experimental/CONTRACT-ADDON-1.3.md`'s own "Acceptance criteria" section
names as the add-on layer's actual evidence — is a pytest suite exercising the
contract, the host, and the capability layer together
(`tests/test_addon_*.py`, `test_capabilities.py`, `test_normalizer_capability.py`,
`test_importer_local_jsonl.py`). That suite needs a database, a worker, and — for
three of those four files — a real add-on; it is not something an author runs against
a work-in-progress add-on before either exists.

So this module is new, not copy-adapted, built from what the contract and the harness
already promise rather than invented from nothing:

* **Manifest validity and contract-range conformance** restate
  `addon_host.loading`'s own version gate (`_require_supported_contract`) — the same
  check, run without a host, database, or installed set, so an author sees the
  refusal `addon_host` would give before ever reaching a real one.
* **Kind-capability conformance** is `addon_kit.harness.run_addon` itself: the
  harness already builds the contract's own context type for the add-on's kind,
  validates configuration exactly as the host does, and cross-checks what the
  add-on claims against what it emitted. Running once *is* the check; this module's
  contribution is turning the result into a pass/fail line rather than a transcript
  an author reads by eye.
* **The cursor resume scenario** (collector, importer): a second harness run, seeded
  with the cursor the first run's own `advance_cursor` call wrote, using the same
  fixtures. An add-on that cannot accept a cursor value it wrote itself has broken
  the read/write pair OQ-010 is about — checkable with the harness alone, without a
  second, differently-paged fixture set an author would have to construct by hand.
* **Determinism** is deliberately **not** checked here, and that omission is itself a
  decision this module names rather than a gap it hides:
  `docs/decisions/DP-030-p1-normalization-scope.md` D1 excludes byte-identical
  normalization from the P1 contract requirement ("Deterministic normalization is
  excluded from the P1 contract requirement. Normalization-time metadata... is
  preserved... to support a reader instead"). P0's own conformance evidence for its
  one normalizer test double asserted exactly this — two runs over one snapshot
  produce byte-identical output — and DP-030 D1 is the P1 decision that carries the
  *structural* guarantee forward (`NormalizeContext` still offers no clock and no
  random source; nothing about that changed in contract 1.3) while dropping the
  *behavioral obligation* every add-on would otherwise have to pass. A generic
  conformance suite that failed a normalizer for non-deterministic output would be
  re-imposing the obligation DP-030 D1 struck down; one that always passed the check
  vacuously (nothing about the contract's own types could ever fail it) would be
  theater. Neither is built. What a normalizer conformance run does check —
  `kind_capability_conformance` — still catches the failures that matter: a bad
  return type, a miscounted result, an unhandled parse error.

Deliberately built on `addon_kit.harness` alone, never `addon_host`: `addon_kit` may
import `addon_api` and nothing else local
(`tests/environment/test_addon_layer_direction.py`, and this tree's own
`tests/environment/test_p1_isolation.py` extension), and an author runs this before a
host — sometimes before a database exists at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from addon_api import CONTRACT_VERSION, AddonManifest, ManifestError, SnapshotItem
from addon_kit.harness import HarnessError, load_fixtures, run_addon

__all__ = ["CheckResult", "ConformanceReport", "format_conformance_report", "run_conformance"]


@dataclass(frozen=True)
class CheckResult:
    """One named check, and what it found. `detail` is for a human, not a machine."""

    name: str
    passed: bool
    detail: str


@dataclass
class ConformanceReport:
    """Every check this run made, in the order they ran.

    Stops at the first check whose failure makes every later one meaningless — an
    invalid manifest has no `addon_id` to run the harness against — rather than
    reporting a cascade of failures that are all really the first one.
    """

    addon_id: str | None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether every check that ran, passed. A report with zero checks is
        vacuously true and never returned — `run_conformance` always appends at
        least `manifest_is_valid`."""
        return all(check.passed for check in self.checks)


def run_conformance(
    directory: Path,
    fixtures: Mapping[str, Sequence[Path]] | None = None,
    config: Mapping[str, Any] | None = None,
    snapshot: Sequence[SnapshotItem] | None = None,
    contract: str = CONTRACT_VERSION,
) -> ConformanceReport:
    """Run every check this module offers against one add-on directory.

    `fixtures`/`config`/`snapshot` are the author's, exactly as `addon_kit run`
    already asks for them — this module adds no second fixture format. A collector
    or importer with a declared stream that advances its cursor also gets the
    resume check; a normalizer, or a stream-less add-on, does not, because there is
    nothing to resume from.
    """
    checks: list[CheckResult] = []

    try:
        manifest = AddonManifest.load(directory / "addon.toml")
    except ManifestError as error:
        checks.append(CheckResult("manifest_is_valid", False, str(error)))
        return ConformanceReport(addon_id=None, checks=checks)
    identity = f"{manifest.addon_id}@{manifest.addon_version} ({manifest.kind})"
    checks.append(CheckResult("manifest_is_valid", True, identity))

    if manifest.supports(contract):
        checks.append(
            CheckResult(
                "contract_range_is_satisfiable",
                True,
                f"requires {manifest.requires_contract.text!r}, this contract is {contract}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "contract_range_is_satisfiable",
                False,
                f"requires {manifest.requires_contract.text!r}, this contract is {contract} — a "
                "real host would refuse this at load time, before importing the module (D3)",
            )
        )
        return ConformanceReport(manifest.addon_id, checks)

    try:
        result = run_addon(directory, fixtures=fixtures, config=config, snapshot=snapshot)
    except HarnessError as error:
        checks.append(CheckResult("entry_is_resolvable", False, str(error)))
        return ConformanceReport(manifest.addon_id, checks)
    checks.append(CheckResult("entry_is_resolvable", True, "the entry point loaded and was called"))

    if result.failed:
        assert result.failure is not None
        checks.append(
            CheckResult(
                "kind_capability_conformance",
                False,
                f"{type(result.failure).__name__}: {result.failure.summary}",
            )
        )
        return ConformanceReport(manifest.addon_id, checks)
    if result.emitted_count_disagrees():
        checks.append(
            CheckResult(
                "kind_capability_conformance",
                False,
                "the outcome's own count disagrees with what was actually emitted — the "
                "platform cross-checks this and fails the attempt",
            )
        )
        return ConformanceReport(manifest.addon_id, checks)
    checks.append(
        CheckResult("kind_capability_conformance", True, f"outcome: {result.outcome}")
    )

    if manifest.kind in ("collector", "importer") and manifest.declares.streams:
        stream = manifest.declares.streams[0]
        advanced = result.cursors.get(stream)
        if advanced is None:
            checks.append(
                CheckResult(
                    "cursor_resume_scenario",
                    True,
                    f"the {stream!r} stream was declared but not advanced in this run; "
                    "nothing to resume from (not a failure)",
                )
            )
        else:
            try:
                second = run_addon(
                    directory, fixtures=fixtures, config=config, cursor=advanced
                )
            except HarnessError as error:
                checks.append(
                    CheckResult(
                        "cursor_resume_scenario",
                        False,
                        f"a second run seeded with the first run's own {stream!r} cursor "
                        f"could not even start: {error}",
                    )
                )
            else:
                if second.failed:
                    assert second.failure is not None
                    checks.append(
                        CheckResult(
                            "cursor_resume_scenario",
                            False,
                            f"a second run seeded with the first run's own {stream!r} cursor "
                            f"({advanced!r}) failed: {type(second.failure).__name__}: "
                            f"{second.failure.summary}",
                        )
                    )
                else:
                    checks.append(
                        CheckResult(
                            "cursor_resume_scenario",
                            True,
                            f"a second run accepted the {stream!r} cursor the first run wrote "
                            f"({advanced!r}) and returned normally",
                        )
                    )

    return ConformanceReport(manifest.addon_id, checks)


def format_conformance_report(report: ConformanceReport) -> str:
    """A transcript an author reads, not a machine-readable result."""
    lines = [report.addon_id or "(manifest did not parse)", ""]
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(f"  [{mark}] {check.name}: {check.detail}")
    lines.append("")
    lines.append("CONFORMANT" if report.passed else "NOT CONFORMANT")
    return "\n".join(lines)


def load_conformance_fixtures(directory: Path | None) -> Mapping[str, Sequence[Path]]:
    """`addon_kit.harness.load_fixtures`, or an empty mapping when none were given.

    Named separately from `harness.load_fixtures` only so `__main__` has one place to
    call for both `run` and `run --conformance` without repeating the `None` check.
    """
    return {} if directory is None else load_fixtures(directory)
