"""The seam `registration.Invoke` describes: a `JobContext` becomes the kind's context.

`registration.capabilities_not_bound` is what this replaces, and its docstring says why it
existed — every capability DP-008 D4 grants reads or writes something `domain` owns, so
until `domain` existed the honest thing was a stated refusal. This module binds them.

Four obligations meet here and none of them belongs to the add-on.

**The outbound obligations stay on the platform — four of the six.** `fetch` takes an
endpoint *name*. `domain.outbound.resolve` turns it into a URL from the source's approved
profile or refuses it by rule; `domain.transport` resolves the host once, checks every
address, and connects to one it checked; each redirect goes back through `check_redirect`
under the same policy. The add-on composes no URL, holds no credential, and opens no socket.

`[측정]` **Corrected 2026-08-18.** This paragraph claimed *every* obligation.
`ADVERSARIAL-REVIEW-2026-08-18.md` F1 measured that `max_pages` and `max_records` are enforced
by nothing here — the one committed collector honours `max_pages` voluntarily, which is why
the integration test passed while proving only that the add-on cooperates. F5 measures that
`read_timeout_s` bounds each socket read rather than the whole response. Those are work
items, not properties, until the counters and the deadline exist.

**A refusal cannot be swallowed.** `fetch` raises a `PlatformError` on refusal, and add-on
code could catch it — nothing stops `except Exception`. So the refusal is also *recorded*,
and a run that returns normally after one is failed anyway, with the refusal's own reason.
Without this, `try: fetch() except Exception: pass` would turn a security control into a
suggestion, and the resulting job would report success. Transport *failures* are not treated
this way: a timeout an add-on chooses to absorb is a collection decision, but a rule that
refused a request is not the add-on's to overrule.

**Writes are enlisted, not performed.** `emit_raw` and `advance_cursor` buffer. The whole
collection — every envelope, every item, the cursor — is handed to
`JobContext.enlist_durable_work`, so it runs inside the transaction that completes the
attempt, with the fenced completion last (DP-010). A worker that lost its lease persists
neither Raw nor cursor, which is what `domain.store`'s docstring specifies and what
`TestCollectionIsAtomic` proved at the store level. Buffering rather than opening a
transaction in `fetch` is also what keeps a transaction from being held across the network.

`envelope_ref` is therefore a **run-scoped handle, not a row id**. The row does not exist
while the add-on holds it; it comes into being when the attempt completes. That keeps the
"no database handle" rule literal — an add-on never learns a primary key — and it is the
one place where the wording in `addon_api.context.FetchResponse` had to be corrected rather
than implemented.

**What the add-on claims is checked against what it did.** `CollectOutcome.items_emitted` is
compared with the items actually buffered. An add-on that miscounts is reporting provenance
it did not produce, and `AddonOutputInvalid` exists for exactly that.

Only `collector` is bound. The other two kinds are refused by name and for a stated reason,
not left to fail obscurely: `normalizer` has nowhere to put results, because `0002_domain.sql`
creates no normalized-result table and OQ-004 has not settled what one would hold; `importer`
needs a registry of approved local inputs that no document defines yet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final
from uuid import uuid4

from addon_api import (
    AddonOutputInvalid,
    CollectContext,
    CollectOutcome,
    ConfigValidationError,
    FetchResponse,
    Limits,
    RawItem,
    validate_config,
)
from domain.outbound import (
    DEFAULT_LIMITS,
    OutboundProfile,
    PreparedRequest,
    Refusal,
    check_redirect,
    resolve,
)
from domain.store import CURSOR_STREAM_DEFAULT, DomainStore, RawItemRow
from domain.transport import Transport, TransportLimits, TransportUnavailable
from platform_core.errors import (
    ConfigurationInvalidError,
    PlatformPermanentError,
    PlatformTransientError,
)
from platform_core.jobs.registry import JobContext
from platform_core.obs.logging import StructuredLogger

from addon_host.loading import LoadedAddon
from addon_host.registration import Invoke

__all__ = ["SOURCE_ID_FIELD", "bind_capabilities"]

#: The one payload key a collect job carries. `p0-security.md` requires that operator input
#: select a **registered** `source_id` rather than an arbitrary URL; this is that selection,
#: and everything else about the request is read from the row it names.
SOURCE_ID_FIELD: Final = "source_id"

_UNBOUND_KINDS: Final[Mapping[str, str]] = {
    "normalizer": (
        "0002_domain.sql creates no normalized-result table, so emit_result has nowhere to "
        "write; what such a table holds is part of OQ-004"
    ),
    "importer": (
        "open_input needs a registry of approved local inputs, and no document defines one yet"
    ),
}


def bind_capabilities(
    domain: DomainStore,
    transport: Transport,
    logger: StructuredLogger | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Invoke:
    """Return the `Invoke` a host registers add-ons with.

    Everything per-process is closed over here and everything per-job is built inside, so a
    worker binds once at start and a job carries no configuration of its own beyond the
    `source_id` it names.
    """
    ticker = clock if clock is not None else _utc_now

    def invoke(addon: LoadedAddon, context: JobContext) -> None:
        kind = addon.manifest.kind
        reason = _UNBOUND_KINDS.get(kind)
        if reason is not None:
            raise PlatformPermanentError(
                f"add-on {addon.identity} is a {kind}, and this host binds no {kind} "
                f"capabilities: {reason}",
                {"addon_id": addon.manifest.addon_id, "kind": kind, "job_id": str(context.job_id)},
            )
        _CollectRun(addon, context, domain, transport, logger, ticker).execute()

    return invoke


# --------------------------------------------------------------------------- #
# What one collect job accumulates
# --------------------------------------------------------------------------- #


@dataclass
class _Envelope:
    """One response, held until the completion transaction writes it."""

    token: str
    endpoint_ref: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    request_summary: Mapping[str, Any]
    content_type: str | None


@dataclass
class _Buffer:
    """Everything the run wants persisted, in the order it was produced.

    Items are keyed by the envelope token they name rather than appended to a single list,
    because `record_items` writes per envelope and an item's envelope is its provenance.
    """

    envelopes: list[_Envelope] = field(default_factory=list)
    items: dict[str, list[RawItemRow]] = field(default_factory=dict)
    cursor: tuple[str, Any] | None = None

    @property
    def item_count(self) -> int:
        return sum(len(rows) for rows in self.items.values())


class _CollectRun:
    """One attempt at one collect job. Not reused; every field is per-attempt state."""

    def __init__(
        self,
        addon: LoadedAddon,
        context: JobContext,
        domain: DomainStore,
        transport: Transport,
        logger: StructuredLogger | None,
        clock: Callable[[], datetime],
    ) -> None:
        self._addon = addon
        self._context = context
        self._domain = domain
        self._transport = transport
        self._logger = logger
        self._clock = clock
        self._buffer = _Buffer()
        #: The first refusal this run met, whether or not the add-on let it out.
        self._refusal: Refusal | None = None

    # ------------------------------------------------------------------ run

    def execute(self) -> None:
        source = self._require_source()
        profile = self._require_profile(source)
        stream = self._require_single_stream()
        config = self._require_config(source)
        cursor = self._domain.read_cursor(source["source_id"], stream)

        collect = CollectContext(
            source_id=source["source_id"],
            config=config,
            cursor=cursor,
            limits=_limits_of(profile),
            fetch=lambda endpoint_ref, params: self._fetch(profile, endpoint_ref, params),
            emit_raw=self._emit_raw,
            advance_cursor=lambda name, value: self._advance_cursor(stream, name, value),
            log=self._log,
        )
        outcome = self._addon.entry(collect)
        self._check_outcome(outcome)
        self._check_no_refusal_was_swallowed()
        self._context.enlist_durable_work(self._flush(source["source_id"]))

    # --------------------------------------------------------------- source

    def _require_source(self) -> Mapping[str, Any]:
        """The registered row this job names, or a permanent failure saying which check failed.

        Every one of these is a job that must not be retried: retrying cannot register a
        source, enable it, or change which add-on a row names.
        """
        source_id = self._context.payload_field(SOURCE_ID_FIELD)
        if not isinstance(source_id, str) or not source_id:
            raise self._permanent(
                f"a collect job must name a registered source in its {SOURCE_ID_FIELD!r} payload "
                "field"
            )
        row = self._domain.read_source(source_id)
        if row is None:
            # SEC-002's first half. The name is echoed because an operator typed it and it
            # is not input to a request — `resolve` never sees it.
            raise self._permanent(f"no source named {source_id!r} is registered", source_id)
        if not row["enabled"]:
            raise self._permanent(f"source {source_id!r} is disabled", source_id)
        if row["kind"] != self._addon.manifest.kind:
            raise self._permanent(
                f"source {source_id!r} is a {row['kind']} but {self._addon.identity} is a "
                f"{self._addon.manifest.kind}",
                source_id,
            )
        if row["addon_id"] != self._addon.manifest.addon_id:
            raise self._permanent(
                f"source {source_id!r} names add-on {row['addon_id']!r}, not "
                f"{self._addon.manifest.addon_id!r}",
                source_id,
            )
        return row

    def _require_config(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        """Check the stored row against the add-on's declared schema, and classify a failure.

        `ConfigValidationError` is a plain `Exception` rather than an `AddonError`, so
        `translated_failures` would classify it as "the add-on raised an unexpected
        ConfigValidationError" — a permanent failure that reads as an add-on defect. It is
        the opposite: the operator's row does not satisfy a schema the operator can fix.
        `[측정]` Found on 2026-08-18 by the first integration run, whose source row typed
        `display` as a string.

        The offending field names are carried through because the contract went out of its
        way to provide them, so an operator surface can mark the fields rather than reject
        the whole form.
        """
        try:
            return validate_config(self._addon.manifest.config_schema, source["config"])
        except ConfigValidationError as invalid:
            raise ConfigurationInvalidError(
                f"source {source['source_id']!r} does not satisfy {self._addon.identity}'s "
                f"configuration schema: {invalid.summary}",
                {
                    "source_id": source["source_id"],
                    "addon_id": self._addon.manifest.addon_id,
                    "fields": list(invalid.fields),
                },
            ) from invalid

    def _require_profile(self, source: Mapping[str, Any]) -> OutboundProfile:
        profile = OutboundProfile.from_row(source["outbound_profile"])
        if profile is None:
            # A collector with no approved profile cannot fetch anything, and every call it
            # makes would be refused one at a time. Saying so once, before the add-on runs,
            # is the same rule stated earlier.
            raise self._permanent(
                f"source {source['source_id']!r} has no approved outbound profile, so a "
                "collector cannot run against it",
                source["source_id"],
            )
        return profile

    def _require_single_stream(self) -> str:
        """The cursor stream this run reads and is allowed to write.

        `CollectContext.cursor` is one value while `advance_cursor` names a stream, and the
        contract does not say how the two line up for an add-on with more than one stream.
        That gap is OQ-010's; until it is settled, a single-stream add-on is bound to its
        declared name and a multi-stream one is refused rather than silently given the
        default stream's cursor — which would read a stream it never writes and restart from
        the beginning on every attempt, losing nothing and re-collecting everything, with
        no failure to notice it by.
        """
        streams = self._addon.manifest.declares.streams
        if not streams:
            return CURSOR_STREAM_DEFAULT
        if len(streams) > 1:
            raise self._permanent(
                f"{self._addon.identity} declares {len(streams)} cursor streams "
                f"({', '.join(streams)}), and this host binds only one: CollectContext.cursor "
                "is a single value with no contract for which stream it holds (OQ-010)"
            )
        return streams[0]

    # ------------------------------------------------------------ fetching

    def _fetch(
        self, profile: OutboundProfile, endpoint_ref: str, params: Mapping[str, str]
    ) -> FetchResponse:
        prepared = resolve(endpoint_ref, profile, params)
        if isinstance(prepared, Refusal):
            raise self._refused(prepared)

        bounds = TransportLimits.from_profile(profile)
        hops = 0
        while True:
            try:
                sent = self._transport.send(prepared, profile, limits=bounds)
            except TransportUnavailable as failure:
                # Transient, and stated here rather than left to `translated_failures`, which
                # classifies anything it does not recognise as permanent. A name that did not
                # resolve and a far end that timed out are the retryable failures this whole
                # attempt budget exists for; letting them reach the generic path would burn a
                # job on a blip.
                raise PlatformTransientError(
                    failure.summary,
                    {
                        "addon_id": self._addon.manifest.addon_id,
                        "job_id": str(self._context.job_id),
                        **dict(failure.detail),
                    },
                ) from failure
            if isinstance(sent, Refusal):
                raise self._refused(sent)
            if sent.status not in _REDIRECT_STATUSES or sent.location is None:
                break
            hops += 1
            next_hop = check_redirect(sent.location, profile, hops)
            if isinstance(next_hop, Refusal):
                raise self._refused(next_hop)
            prepared = next_hop

        return self._record_response(prepared, endpoint_ref, sent.status, sent.headers, sent.body)

    def _record_response(
        self,
        prepared: PreparedRequest,
        endpoint_ref: str,
        status: int,
        headers: Mapping[str, str],
        body: bytes,
    ) -> FetchResponse:
        """Buffer the envelope and hand the add-on a handle to it.

        The envelope is buffered whether or not the add-on emits anything from it, which is
        what keeps losslessness independent of add-on quality: an add-on that carves a
        response badly has produced bad items over a preserved original.
        """
        token = uuid4().hex
        retrieved_at = self._clock().isoformat()
        self._buffer.envelopes.append(
            _Envelope(
                token=token,
                endpoint_ref=endpoint_ref,
                status=status,
                headers=headers,
                body=body,
                # The URL only. No parameter values: a query string is the part an add-on
                # controls, and `Refusal` gives the same reason for never quoting one.
                request_summary={"url": prepared.url.split("?", 1)[0], "host": prepared.host},
                content_type=headers.get("Content-Type") or headers.get("content-type"),
            )
        )
        return FetchResponse(
            endpoint_ref=endpoint_ref,
            status=status,
            headers=headers,
            body=body,
            envelope_ref=token,
            retrieved_at=retrieved_at,
        )

    # -------------------------------------------------------------- writing

    def _emit_raw(self, items: Sequence[RawItem]) -> None:
        known = {envelope.token for envelope in self._buffer.envelopes}
        for item in items:
            if item.envelope_ref is None or item.envelope_ref not in known:
                # `raw_item.envelope_id` is not null because an item without its original is
                # an extraction nobody can check. An add-on that emits one has lost the link
                # between what it produced and what it read.
                raise AddonOutputInvalid(
                    f"item {item.item_key!r} names no envelope this run fetched",
                    {"item_key": item.item_key, "envelope_ref": item.envelope_ref},
                )
            self._buffer.items.setdefault(item.envelope_ref, []).append(
                RawItemRow(
                    item_key=item.item_key,
                    payload=item.payload,
                    content_type=item.content_type,
                    notes=item.notes,
                )
            )

    def _advance_cursor(self, bound: str, name: str, value: Any) -> None:
        if name != bound:
            raise AddonOutputInvalid(
                f"this run reads and writes the {bound!r} cursor stream; {name!r} was not "
                "declared (OQ-010)",
                {"stream": name, "bound": bound},
            )
        if value is None:
            # `read_cursor` returns None for "no cursor yet", so a stored null would be
            # indistinguishable from never having run — its own docstring says so.
            raise AddonOutputInvalid(
                "a cursor value of None cannot be stored: it is how 'never ran' is read back",
                {"stream": name},
            )
        self._buffer.cursor = (name, value)

    def _log(self, event: str, fields: Mapping[str, Any]) -> None:
        if self._logger is None:
            return
        # Nested under one key for the reason `errors._detail` gives: an add-on must not be
        # able to overwrite the identity fields the platform recorded, and here it also must
        # not be able to collide with a reserved structural field and raise.
        self._logger.log(
            "INFO",
            f"addon.{event}",
            addon_id=self._addon.manifest.addon_id,
            addon_version=self._addon.manifest.addon_version,
            job_id=str(self._context.job_id),
            fields=dict(fields),
        )

    def _flush(self, source_id: str) -> Callable[[], None]:
        """The durable work, closed over what the run produced. Runs in the completion
        transaction and nowhere else.
        """
        buffer = self._buffer
        attempt_id = self._context.attempt_id
        job_id = self._context.job_id
        manifest = self._addon.manifest

        def write() -> None:
            for envelope in buffer.envelopes:
                envelope_id = self._domain.record_envelope(
                    source_id,
                    job_id,
                    attempt_id,
                    manifest.addon_id,
                    manifest.addon_version,
                    body=envelope.body,
                    content_type=envelope.content_type,
                    endpoint_ref=envelope.endpoint_ref,
                    request_summary=envelope.request_summary,
                    status=envelope.status,
                    response_headers=envelope.headers,
                )
                rows = buffer.items.get(envelope.token)
                if rows:
                    self._domain.record_items(envelope_id, source_id, rows)
            if buffer.cursor is not None:
                stream, value = buffer.cursor
                self._domain.advance_cursor(source_id, value, attempt_id, stream)

        return write

    # ------------------------------------------------------------- checking

    def _check_outcome(self, outcome: object) -> None:
        if not isinstance(outcome, CollectOutcome):
            raise AddonOutputInvalid(
                f"a collector must return a CollectOutcome, not {type(outcome).__name__}",
                {"returned": type(outcome).__name__},
            )
        if outcome.items_emitted != self._buffer.item_count:
            raise AddonOutputInvalid(
                f"the collector reported {outcome.items_emitted} items and emitted "
                f"{self._buffer.item_count}",
                {"reported": outcome.items_emitted, "emitted": self._buffer.item_count},
            )

    def _check_no_refusal_was_swallowed(self) -> None:
        if self._refusal is None:
            return
        raise PlatformPermanentError(
            f"{self._addon.identity} continued past an outbound refusal and returned "
            f"normally: {self._refusal.summary}",
            {
                "reason": str(self._refusal.reason),
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                **dict(self._refusal.detail),
            },
        )

    # -------------------------------------------------------------- failing

    def _refused(self, refusal: Refusal) -> PlatformPermanentError:
        """Record the refusal, then return the error to raise for it.

        Recording first is what makes the control unswallowable: by the time add-on code
        could catch this, the run already knows a rule refused it.
        """
        if self._refusal is None:
            self._refusal = refusal
        return PlatformPermanentError(
            refusal.summary,
            {
                "reason": str(refusal.reason),
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                **dict(refusal.detail),
            },
        )

    def _permanent(self, summary: str, source_id: str | None = None) -> PlatformPermanentError:
        detail: dict[str, Any] = {
            "addon_id": self._addon.manifest.addon_id,
            "job_id": str(self._context.job_id),
        }
        if source_id is not None:
            detail["source_id"] = source_id
        return PlatformPermanentError(summary, detail)


#: Statuses whose `Location` this host follows. A `304` carries no body to follow and a
#: `305` is obsolete; neither is a redirect this guard should be inventing behaviour for.
_REDIRECT_STATUSES: Final[frozenset[int]] = frozenset({301, 302, 303, 307, 308})


def _limits_of(profile: OutboundProfile) -> Limits:
    """Tell the add-on this source's bounds. Two of them are advisory — see `Limits`.

    `max_pages` and `max_records` are passed through and counted nowhere: `_fetch` has no
    call counter and `_emit_raw` has no item counter. `ADVERSARIAL-REVIEW-2026-08-18.md` F1
    measured that. This function's previous docstring said "what the platform will enforce
    anyway", which was true of four of these six.
    """
    limits = {**DEFAULT_LIMITS, **profile.limits}
    return Limits(
        connect_timeout_s=float(limits["connect_timeout_s"]),
        read_timeout_s=float(limits["read_timeout_s"]),
        max_response_bytes=int(limits["max_response_bytes"]),
        max_redirects=int(limits["max_redirects"]),
        max_pages=int(limits["max_pages"]),
        max_records=int(limits["max_records"]),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
