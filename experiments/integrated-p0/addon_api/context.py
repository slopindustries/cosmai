"""What an add-on is handed when it runs, and what it is deliberately not handed.

Each ``kind`` gets its own context because the three components are asymmetric in
kind, not in degree (DP-008, and the table in the P0-B review). A collector needs
the outside world, a credential, and somewhere to keep its position; a normalizer
needs a sealed input and nothing else. Giving all three the same context would
mean handing a normalizer a ``fetch`` it must be trusted not to call, and a
capability withheld is stronger than a capability documented as unused.

What no context contains, in any kind:

- a credential — the platform resolves it inside ``fetch`` and the add-on never
  sees the value;
- a URL — ``fetch`` takes an endpoint name and the platform composes the request
  from the registered source's approved profile, so ``p0-security.md``'s
  "no general URL fetcher" holds by construction rather than by review;
- a database handle, a connection, or anything reaching the job tables — the same
  reason ``platform_core.jobs.registry`` gives for keeping ``JobContext`` thin:
  a component that can write its own state makes the state machine untestable.

The capabilities are callables. Under subprocess isolation they become the
request/response surface, which is why every value they carry is a type from
:mod:`addon_api.results` with an explicit JSON form.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self

from addon_api.results import (
    CollectOutcome,
    NormalizedResult,
    NormalizeOutcome,
    RawItem,
    SnapshotItem,
)

__all__ = [
    "CollectContext",
    "CollectEntry",
    "FetchResponse",
    "ImportContext",
    "ImportEntry",
    "InputStream",
    "Limits",
    "NormalizeContext",
    "NormalizeEntry",
]


@dataclass(frozen=True)
class Limits:
    """The bounds on this source, told to the add-on. Not all of them are enforced.

    Readable and not settable. An add-on that knows the page limit can stop at it
    cleanly instead of being cut off mid-request.

    **Corrected 2026-08-18.** This docstring said "an add-on that ignores these is
    still bounded — the platform enforces them whatever the add-on believes", and
    that was false for two of the six. The adversarial review of `27f712b`
    (`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md`, F1) measured an add-on
    fetching 12 times and emitting 600 items against ``max_pages=2, max_records=3``,
    and it succeeded.

    As of that review:

    - ``connect_timeout_s``, ``read_timeout_s``, ``max_response_bytes`` and
      ``max_redirects`` are enforced by the platform. ``read_timeout_s`` bounds each
      socket read rather than the whole response, which F5 measures.
    - ``max_pages`` and ``max_records`` are **advisory**. Nothing counts them. An
      add-on that ignores them is not bounded by them.

    `[결정]` The wording is corrected before the counters are written rather than
    after, because this is contract text an add-on author reads to decide what they
    must defend against, and a control promised in the present tense is one nobody
    writes twice.
    """

    connect_timeout_s: float
    read_timeout_s: float
    max_response_bytes: int
    max_redirects: int
    max_pages: int
    max_records: int

    def to_json(self) -> dict[str, Any]:
        return {
            "connect_timeout_s": self.connect_timeout_s,
            "read_timeout_s": self.read_timeout_s,
            "max_response_bytes": self.max_response_bytes,
            "max_redirects": self.max_redirects,
            "max_pages": self.max_pages,
            "max_records": self.max_records,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            connect_timeout_s=float(data["connect_timeout_s"]),
            read_timeout_s=float(data["read_timeout_s"]),
            max_response_bytes=int(data["max_response_bytes"]),
            max_redirects=int(data["max_redirects"]),
            max_pages=int(data["max_pages"]),
            max_records=int(data["max_records"]),
        )


@dataclass(frozen=True)
class FetchResponse:
    """One response, already bounded, already stripped, already taken into Raw.

    By the time an add-on holds this the platform has applied the source's
    allowlist, revalidated any redirect, checked the resolved address range,
    enforced the timeouts and the size limit, removed ``Authorization``,
    ``Cookie``, and provider-protected headers, and taken the response bytes into
    the Raw envelope this run will persist under ``envelope_ref``.

    That last point is why losslessness does not depend on the add-on. The
    envelope is recorded whether or not the add-on emits anything from it, so an
    add-on that carves the response badly has produced bad items over a preserved
    original rather than lost the original.

    ``envelope_ref`` is a **run-scoped handle, not a row id**, and this paragraph is
    a correction rather than a description: until 2026-08-18 the sentence above read
    "persisted the response bytes", which was true of the design DP-008 assumed and
    false of the one DP-010 settled. Raw and the fenced completion go into one
    transaction with the completion last, so a worker that lost its lease persists
    neither. The envelope becomes a row when the attempt completes, and never if it
    does not. No add-on can observe the difference — none holds a database handle —
    but a contract stating the wrong moment is the kind of claim this project treats
    as a defect rather than as wording.
    """

    endpoint_ref: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    envelope_ref: str
    retrieved_at: str

    def to_json(self) -> dict[str, Any]:
        return {
            "endpoint_ref": self.endpoint_ref,
            "status": self.status,
            "headers": dict(self.headers),
            "body": base64.b64encode(self.body).decode("ascii"),
            "envelope_ref": self.envelope_ref,
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            endpoint_ref=str(data["endpoint_ref"]),
            status=int(data["status"]),
            headers={str(k): str(v) for k, v in dict(data["headers"]).items()},
            body=base64.b64decode(str(data["body"]), validate=True),
            envelope_ref=str(data["envelope_ref"]),
            retrieved_at=str(data["retrieved_at"]),
        )


#: What ``open_input`` yields: the registered file, in chunks, already class-checked.
InputStream = Iterator[bytes]


@dataclass(frozen=True)
class CollectContext:
    """A collector's world. Network in, Raw and a cursor out."""

    source_id: str
    config: Mapping[str, Any]
    cursor: Any | None
    limits: Limits
    fetch: Callable[[str, Mapping[str, str]], FetchResponse]
    emit_raw: Callable[[Sequence[RawItem]], None]
    advance_cursor: Callable[[str, Any], None]
    log: Callable[[str, Mapping[str, Any]], None]

    def config_field(self, name: str, fallback: Any = None) -> Any:
        """Read one configuration key.

        Present so that reading configuration reads the same way in every add-on,
        and so the template has something to demonstrate. A missing key is an
        ordinary answer here; a *required* missing key was already rejected when
        the host validated the stored configuration against the declared schema,
        so an add-on reaching this point does not need to re-check it.
        """
        return self.config.get(name, fallback)


@dataclass(frozen=True)
class ImportContext:
    """An importer's world. A registered local input in, Raw and a cursor out.

    Deliberately no ``fetch``. A dataset importer that wants the network is a
    collector that has not admitted it, and the two are separated so that the
    outbound surface is exactly the set of sources an operator approved.
    """

    source_id: str
    config: Mapping[str, Any]
    cursor: Any | None
    limits: Limits
    open_input: Callable[[str], InputStream]
    emit_raw: Callable[[Sequence[RawItem]], None]
    advance_cursor: Callable[[str, Any], None]
    log: Callable[[str, Mapping[str, Any]], None]

    def config_field(self, name: str, fallback: Any = None) -> Any:
        return self.config.get(name, fallback)


@dataclass(frozen=True)
class NormalizeContext:
    """A normalizer's world. A sealed snapshot in, versioned results out.

    No ``fetch``, no credential, and no cursor — not as an oversight but because
    the input is fixed before the run starts. That is also why a normalizer's
    failure cannot be partial in the way a collector's can, and why DP-008 expects
    the two to need different retry treatment.

    Determinism is required of what comes out of here: the same snapshot must
    produce byte-identical results after canonical serialization (OQ-003). An
    add-on that reads a clock, a random source, or anything outside ``config`` and
    the snapshot breaks that, and nothing in this context offers those.
    """

    run_id: str
    snapshot_id: str
    config: Mapping[str, Any]
    read_snapshot: Callable[[], Iterator[SnapshotItem]]
    emit_result: Callable[[Sequence[NormalizedResult]], None]
    log: Callable[[str, Mapping[str, Any]], None]

    def config_field(self, name: str, fallback: Any = None) -> Any:
        return self.config.get(name, fallback)


#: The signature every add-on's entry point has, by kind. Stated as a type so the
#: host can check it at load time and the template can be written against it.
CollectEntry = Callable[[CollectContext], CollectOutcome]
ImportEntry = Callable[[ImportContext], CollectOutcome]
NormalizeEntry = Callable[[NormalizeContext], NormalizeOutcome]
