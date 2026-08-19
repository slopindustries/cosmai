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
from typing import Any, Protocol, Self

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
    "Fetch",
    "FetchResponse",
    "ImportContext",
    "ImportEntry",
    "OpenedInput",
    "Limits",
    "NormalizeContext",
    "NormalizeEntry",
]


@dataclass(frozen=True)
class Limits:
    """The bounds on this source. An add-on that ignores these is still bounded —
    the platform enforces every one of them whatever the add-on believes.

    `[측정]` **That sentence was false twice, and both corrections are kept.** At
    `27f712b` ``max_pages`` and ``max_records`` were counted by nothing
    (`ADVERSARIAL-REVIEW-2026-08-18.md` F1). Between DP-020 and 2026-08-19
    ``max_request_bytes`` counted `len(body)`, which is a byte count only for
    `bytes` — the independent review of that date measured a one-element
    `list[bytes]` of 1 MiB passing a 64 KiB grant, because `http.client` streams a
    sequence of chunks. Both are now counted, and the history stays because this is
    contract text an add-on author reads to decide what they must defend against.

    Readable and not settable. Knowing the page limit lets an add-on stop at it
    cleanly, with a cursor it can resume from, instead of being refused at it — but
    stopping cleanly is the add-on's convenience, not the bound.

    **What is enforced, and where.** ``connect_timeout_s``, ``read_timeout_s`` and
    ``max_response_bytes`` bound one hop in ``domain.transport``; ``max_redirects``
    bounds the hops in ``domain.outbound.check_redirect``; ``max_pages`` and
    ``max_records`` bound the run in the host's capability layer. Running past any of
    them is an outbound *refusal* — the same class of failure as an unapproved host —
    and it is not swallowable: catching it and reporting success still fails the job.

    **This paragraph was false once, and the history is kept.** Between `27f712b` and
    2026-08-18 it promised all six while ``max_pages`` and ``max_records`` were counted
    by nothing; the adversarial review of that commit
    (`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md`, F1) measured an add-on
    fetching 12 times and emitting 600 items against ``max_pages=2, max_records=3``,
    and it succeeded. `[결정]` The note stays because this is contract text an add-on
    author reads to decide what they must defend against, and "it says so" was not
    evidence the last time either.
    """

    connect_timeout_s: float
    read_timeout_s: float
    max_response_bytes: int
    max_redirects: int
    max_pages: int
    max_records: int
    max_request_bytes: int = 64 * 1024
    #: DP-024. Bounds one input stream an importer opens. Separate from
    #: ``max_response_bytes`` because a dataset is legitimately larger than an HTTP
    #: response, and enforced in ``domain.inputs.open_stream`` before the first chunk.
    max_input_bytes: int = 64 * 1024 * 1024

    def to_json(self) -> dict[str, Any]:
        return {
            "connect_timeout_s": self.connect_timeout_s,
            "read_timeout_s": self.read_timeout_s,
            "max_response_bytes": self.max_response_bytes,
            "max_redirects": self.max_redirects,
            "max_pages": self.max_pages,
            "max_records": self.max_records,
            "max_request_bytes": self.max_request_bytes,
            "max_input_bytes": self.max_input_bytes,
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
            max_request_bytes=int(data.get("max_request_bytes", 64 * 1024)),
            max_input_bytes=int(data.get("max_input_bytes", 64 * 1024 * 1024)),
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


@dataclass(frozen=True)
class OpenedInput:
    """One approved local input, already bounded, already taken into Raw.

    `FetchResponse`'s counterpart, and it exists for the same reason: an add-on that emits
    a `RawItem` must be able to say **which original it came from**, and `envelope_ref` is
    that link. DP-024 discovered this while binding `open_input` — the contract's first
    shape returned a bare `Iterator[bytes]`, which left an importer unable to emit anything
    at all, because `RawItem.envelope_ref` has no other source.

    `[측정]` **`body` is bytes rather than a stream, and a guard is why.** The second shape
    of this class carried an `Iterator[bytes]`, and
    `tests/environment/test_addon_contract_is_serializable.py` refused it: DP-008 H4 keeps
    every boundary type serializable so that subprocess isolation stays a host change
    rather than a contract rewrite, and a live iterator cannot cross a process. The input is
    read whole in any case — `Limits.max_input_bytes` bounds it, and the envelope must
    exist before `emit_raw` can name it — so the streaming shape bought nothing and cost
    the property DP-008 was protecting.

    `input_ref` is the name the add-on asked for, never the path it resolved to. The path
    is the operator's, and an add-on that could read it back would hold a destination it
    was never given.
    """

    input_ref: str
    envelope_ref: str
    body: bytes

    def to_json(self) -> dict[str, Any]:
        return {
            "input_ref": self.input_ref,
            "envelope_ref": self.envelope_ref,
            "body": base64.b64encode(self.body).decode("ascii"),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            input_ref=str(data["input_ref"]),
            envelope_ref=str(data["envelope_ref"]),
            body=base64.b64decode(str(data["body"]), validate=True),
        )



class Fetch(Protocol):
    """One request the platform composes, sends, and records.

    A `Protocol` rather than a `Callable` alias because DP-020 gave it an optional third
    argument and a `Callable[...]` cannot express one. The shape is also the whole of
    DP-008 D4 restated: the add-on names an **endpoint**, supplies the **question** as
    parameters or a body, and is handed a response. Nothing here names a host, a path, a
    method, or a credential — those are the profile's, and an add-on cannot reach them.

    `body` is the add-on's, exactly as `params` always has been: it says *what is being
    asked for*, not *where the request goes*. It is only accepted for an endpoint the
    source's profile granted `POST`, and it is bounded by `Limits.max_request_bytes`.
    """

    def __call__(
        self,
        endpoint_ref: str,
        params: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> FetchResponse: ...


@dataclass(frozen=True)
class CollectContext:
    """A collector's world. Network in, Raw and a cursor out."""

    source_id: str
    config: Mapping[str, Any]
    cursor: Any | None
    limits: Limits
    fetch: Fetch
    #: Say what a non-success status means for this source, and mean it (contract 1.2).
    #:
    #: The platform records every response whose status is not 2xx and **fails the run if
    #: the add-on returns normally without having decided**. Deciding is either raising —
    #: which is what a collector does when the status is a failure — or calling this, which
    #: is what it does when the status is *data*. A `404` is "no results" to one API and
    #: "wrong endpoint" to another, and only the add-on knows which.
    #:
    #: `reason` is required and is written to the log. An operator reading a run that took a
    #: `404` as data needs to see why someone decided that, not merely that they did.
    #:
    #: `[측정]` This exists because `ADVERSARIAL-REVIEW-2026-08-19.md` F2 measured a
    #: collector emitting from a `401` body: the job reported `SUCCEEDED` and
    #: `{"errorCode": "SE01"}` landed in `raw_item` as data.
    #:
    #: **What this is not.** It is not unswallowable in the sense a refusal is. Swallowing a
    #: refusal *fails*; calling this on every response *succeeds*, and an add-on that does so
    #: has restored the behaviour the check was added to remove. The platform cannot tell a
    #: considered acceptance from a reflexive one, because judging whether a `404` was really
    #: data means knowing the source — which is the knowledge the add-on boundary exists to
    #: keep out of the platform.
    #:
    #: So what changed is the **default**: silence used to succeed and now fails, and buying
    #: the old behaviour back costs a call and a written reason per response, both of which
    #: are in the log and countable. A run that accepted twenty statuses is a different thing
    #: from one that accepted one, and that is an operator signal rather than a control.
    #:
    #: **And it sees nothing of a source that answers `200` with an error body.** The
    #: platform reads a status, not a meaning. That case is the add-on's alone and is why
    #: `collector.naver.blog`'s first `[가설]` is about exactly it.
    accept_status: Callable[[FetchResponse, str], None]
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
    open_input: Callable[[str], OpenedInput]
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
