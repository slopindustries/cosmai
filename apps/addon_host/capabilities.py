"""The seam `registration.Invoke` describes: a `JobContext` becomes the kind's context.

Copy-adapted from `experiments/integrated-p0/addon_host/capabilities.py` (M3
batch 3b). The one substantive change is credential resolution: P0 imported
`domain.secrets.CredentialNotResolved`; M2 batch 2c centralized
`resolve_credential`/`CredentialNotResolved` in `platform_core.secrets` instead
(DP-032 D4's `COSMA_SRC_*`/`COSMA_DB_*` ref families share one resolver), and
`domain.outbound.credential_headers` already reuses it — this module now
imports the same `CredentialNotResolved` `domain.outbound` raises, rather than
a second copy that would never actually be the type `except` catches. Every
other name below (`DomainStore`, `domain.inputs`, `domain.outbound`,
`domain.transport`, `platform_core.errors`, `platform_core.jobs.registry`)
matches P0's shape exactly, so nothing else changes.

`registration.capabilities_not_bound` is what this replaces, and its docstring says why it
existed — every capability DP-008 D4 grants reads or writes something `domain` owns, so
until `domain` existed the honest thing was a stated refusal. This module binds them.

Four obligations meet here and none of them belongs to the add-on.

**The outbound obligations stay on the platform — all six.** `fetch` takes an
endpoint *name*. `domain.outbound.resolve` turns it into a URL from the source's approved
profile or refuses it by rule; `domain.transport` resolves the host once, checks every
address, and connects to one it checked; each redirect goes back through `check_redirect`
under the same policy. The add-on composes no URL, holds no credential, and opens no socket.

`[측정]` **Corrected twice, and the history is the point.** At `27f712b` this paragraph
claimed *every* obligation while `max_pages` and `max_records` were counted by nothing and
`read_timeout_s` bounded each socket read rather than the whole response —
`ADVERSARIAL-REVIEW-2026-08-18.md` F1 and F5. Both are now enforced: `_CollectRun._pages`,
the item test in `_emit_raw`, and `TransportLimits.deadline`. The claim is true again, and
it was false for long enough to be worth saying so here rather than only in a review file.

DP-018 added credential attachment and DP-020 added the request method and body. The add-on
still composes no URL, holds no credential, and opens no socket; what DP-020 gave it is the
*question* — a body, exactly as `params` always was — never the destination.

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

`collector` and `normalizer` are bound; `importer` is refused by name and for a stated
reason rather than left to fail obscurely — `open_input` needs a registry of approved local
inputs that no document defines.

`[측정]` **`normalizer` was refused here until 2026-08-18**, and the reason given was
accurate at the time: `0002_domain.sql` created no normalized-result table, so `emit_result`
had nowhere to write. `0003_normalized_result.sql` created one and DP-019 decided what it
holds, so the refusal expired and `_NormalizeRun` replaced it. The two runs are siblings
rather than a hierarchy, and that module-level note explains why.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID, uuid4

from psycopg.pq import TransactionStatus

from addon_api import (
    AddonOutputInvalid,
    CollectContext,
    CollectOutcome,
    ConfigValidationError,
    FetchResponse,
    ImportContext,
    Limits,
    NormalizeContext,
    NormalizedResult,
    NormalizeOutcome,
    OpenedInput,
    RawItem,
    SnapshotItem,
    validate_config,
)
from addon_host.loading import LoadedAddon
from addon_host.registration import Invoke
from domain.inputs import (
    InputProfile,
    InputRefusal,
    InputRefusalReason,
    InputRefused,
    open_stream,
    read_input_profile,
    resolve_input,
)
from domain.outbound import (
    DEFAULT_LIMITS,
    OutboundProfile,
    PreparedRequest,
    Refusal,
    RefusalReason,
    check_redirect,
    credential_headers,
    resolve,
)
from domain.store import (
    CURSOR_STREAM_DEFAULT,
    DomainStore,
    NormalizedResultRow,
    RawItemRow,
)
from domain.transport import Transport, TransportLimits, TransportUnavailable
from platform_core.errors import (
    ConfigurationInvalidError,
    PlatformPermanentError,
    PlatformTransientError,
)
from platform_core.jobs.registry import JobContext
from platform_core.obs.logging import StructuredLogger
from platform_core.secrets import CredentialNotResolved

__all__ = ["SNAPSHOT_ID_FIELD", "SOURCE_ID_FIELD", "bind_capabilities"]

#: The one payload key a collect job carries. `p0-security.md` requires that operator input
#: select a **registered** `source_id` rather than an arbitrary URL; this is that selection,
#: and everything else about the request is read from the row it names.
SOURCE_ID_FIELD: Final = "source_id"

#: `[측정]` `normalizer` left this table on 2026-08-18. Its stated reason — "0002_domain.sql
#: creates no normalized-result table, so emit_result has nowhere to write" — expired when
#: `0003_normalized_result.sql` created one and DP-019 decided what it holds. `importer`
#: stays, and its reason is unchanged: nothing defines a registry of approved local inputs.
#: `[확인 사실]` Empty since 2026-08-19. `normalizer` left when DP-019 gave it a result
#: table; `importer` left when DP-024 defined the registry of approved local inputs its
#: `open_input` needed. The mapping stays because the refusal it drives is the honest
#: answer for any kind a future contract adds before this host can serve it — a capability
#: silently missing is worse than one refused by name.
_UNBOUND_KINDS: Final[Mapping[str, str]] = {}

#: The one payload key a normalize job carries beyond its source. DP-019 D6: normalization
#: is started by an operator naming a sealed snapshot, never by collection finishing.
SNAPSHOT_ID_FIELD: Final = "snapshot_id"


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
        if kind == "normalizer":
            _NormalizeRun(addon, context, domain, transport, logger, ticker).execute()
        elif kind == "importer":
            _ImportRun(addon, context, domain, logger, ticker).execute()
        else:
            _CollectRun(addon, context, domain, transport, logger, ticker).execute()

    return invoke


# --------------------------------------------------------------------------- #
# What one collect job accumulates
# --------------------------------------------------------------------------- #


@dataclass
class _Envelope:
    """One original, held until the completion transaction writes it.

    A collector fills `endpoint_ref`, `status` and `headers`; an importer fills
    `input_ref` and leaves those absent, because a file has no status. DP-024.
    """

    token: str
    endpoint_ref: str | None
    status: int | None
    headers: Mapping[str, str]
    body: bytes
    request_summary: Mapping[str, Any]
    content_type: str | None
    input_ref: str | None = None


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


# --------------------------------------------------------------------------- #
# The clauses every kind checks, in one copy
# --------------------------------------------------------------------------- #
#
# `[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5 measured what two copies of these
# clauses cost: `enabled`, `kind`, `addon_id`, and the configuration schema were each GREEN
# on at least one side, because a duplicated guard is only as strong as its least-tested
# copy. DP-024 adds a third run kind, so the choice was one copy or three.
#
# What is *not* shared is the prose. Each run class keeps its own docstring, because why a
# normalizer has a source row of its own and why a collect job must name one are genuinely
# different explanations of the same check.


def _resolved_source_row(
    context: JobContext,
    domain: DomainStore,
    addon: LoadedAddon,
    job_noun: str,
    permanent: Callable[..., PlatformPermanentError],
) -> Mapping[str, Any]:
    """The registered row this job names, or a permanent failure saying which check failed.

    Every one of these is a job that must not be retried: retrying cannot register a
    source, enable it, or change which add-on a row names.
    """
    source_id = context.payload_field(SOURCE_ID_FIELD)
    if not isinstance(source_id, str) or not source_id:
        raise permanent(
            f"a {job_noun} job must name a registered source in its "
            f"{SOURCE_ID_FIELD!r} payload field"
        )
    row = domain.read_source(source_id)
    if row is None:
        # SEC-002's first half. The name is echoed because an operator typed it and it
        # is not input to a request — `resolve` never sees it.
        raise permanent(f"no source named {source_id!r} is registered", source_id)
    if not row["enabled"]:
        raise permanent(f"source {source_id!r} is disabled", source_id)
    if row["kind"] != addon.manifest.kind:
        raise permanent(
            f"source {source_id!r} is a {row['kind']} but {addon.identity} is a "
            f"{addon.manifest.kind}",
            source_id,
        )
    if row["addon_id"] != addon.manifest.addon_id:
        raise permanent(
            f"source {source_id!r} names add-on {row['addon_id']!r}, not "
            f"{addon.manifest.addon_id!r}",
            source_id,
        )
    if row["config_schema_version"] != addon.manifest.config_schema_version:
        # M-P1 (REVIEW-M2-M7.md): `config_schema_version` was parsed, stored, and
        # echoed back on every source read, but nothing ever compared it — the
        # README's/template's own "a source configured under an older schema ...
        # refuses to run" sentence named a rule this function did not enforce. A
        # `ConfigurationInvalidError` rather than a permanent failure for the same
        # reason `_validated_config` below raises one: this is the operator's stored
        # row failing to satisfy a schema the operator can fix by reconfiguring the
        # source, not an add-on defect.
        raise ConfigurationInvalidError(
            f"source {source_id!r} was configured under schema "
            f"{row['config_schema_version']!r}, but {addon.identity} now requires "
            f"{addon.manifest.config_schema_version!r}; reconfigure the source",
            {
                "source_id": source_id,
                "addon_id": addon.manifest.addon_id,
                "stored_config_schema_version": row["config_schema_version"],
                "required_config_schema_version": addon.manifest.config_schema_version,
            },
        )
    return row


def _validated_config(addon: LoadedAddon, source: Mapping[str, Any]) -> Mapping[str, Any]:
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
        return validate_config(addon.manifest.config_schema, source["config"])
    except ConfigValidationError as invalid:
        raise ConfigurationInvalidError(
            f"source {source['source_id']!r} does not satisfy {addon.identity}'s "
            f"configuration schema: {invalid.summary}",
            {
                "source_id": source["source_id"],
                "addon_id": addon.manifest.addon_id,
                "fields": list(invalid.fields),
            },
        ) from invalid


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
        #: A credential that could not be resolved, held for the same reason. It is not a
        #: `Refusal` — nothing was refused, the request was never authenticated — and it
        #: keeps `CONFIGURATION_INVALID` rather than becoming a permanent failure, because
        #: DP-018 D5 wants an operator to see a missing key as a missing key.
        self._credential_failure: CredentialNotResolved | None = None
        #: Envelope tokens whose response was not 2xx and which the add-on has not decided
        #: about. Emptied by `accept_status`; anything left when the run returns normally
        #: fails it. `ADVERSARIAL-REVIEW-2026-08-19.md` F2.
        self._undecided: dict[str, int] = {}
        #: Pages this run has been *granted*, counted by the platform rather than by the
        #: add-on. One per `fetch` call; a redirect is the same page reached differently and
        #: is bounded by `max_redirects` instead. `ADVERSARIAL-REVIEW-2026-08-18.md` F1.
        self._pages = 0

    # ------------------------------------------------------------------ run

    def execute(self) -> None:
        source = self._require_source()
        profile = self._require_profile(source)
        self._require_declared_credential_is_granted(profile, source)
        stream = self._require_single_stream()
        config = self._require_config(source)
        cursor = self._domain.read_cursor(source["source_id"], stream)
        limits = _limits_of(profile)

        collect = CollectContext(
            source_id=source["source_id"],
            config=config,
            cursor=cursor,
            limits=limits,
            fetch=lambda endpoint_ref, params=None, body=None: self._fetch(
                profile, limits, endpoint_ref, params, body
            ),
            accept_status=self._accept_status,
            emit_raw=lambda items: self._emit_raw(limits, items),
            advance_cursor=lambda name, value: self._advance_cursor(stream, name, value),
            log=self._log,
        )
        outcome = self._addon.entry(collect)
        self._check_outcome(outcome)
        self._check_no_refusal_was_swallowed()
        self._check_every_status_was_decided()
        self._context.enlist_durable_work(self._flush(source["source_id"]))

    # --------------------------------------------------------------- source

    def _require_source(self) -> Mapping[str, Any]:
        """The registered row this job names, or a permanent failure saying which check failed.

        Every one of these is a job that must not be retried: retrying cannot register a
        source, enable it, or change which add-on a row names.
        """
        return _resolved_source_row(
            self._context, self._domain, self._addon, "collect", self._permanent
        )

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
        return _validated_config(self._addon, source)

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
        self,
        profile: OutboundProfile,
        limits: Limits,
        endpoint_ref: str,
        params: Mapping[str, str] | None,
        body: bytes | None,
    ) -> FetchResponse:
        self._pages += 1
        if self._pages > limits.max_pages:
            # Counted before anything is resolved or sent, so the refused page costs no
            # request. `[측정]` The reviewer's runaway add-on made 12 requests against a
            # limit of 2 and succeeded; this is the counter that was missing.
            raise self._refused(
                Refusal(
                    RefusalReason.PAGE_LIMIT_EXCEEDED,
                    f"this source grants {limits.max_pages} pages per run and the collector "
                    f"asked for {self._pages}",
                    {
                        "endpoint_ref": endpoint_ref,
                        "limit": limits.max_pages,
                        "requested": self._pages,
                    },
                )
            )
        # Resolved before the URL is built, so a source whose credential is missing never
        # reaches a socket. `secret-setup.md` invariant 4 and DP-018 D5: the failure this
        # ordering prevents is an unauthenticated request answered with `200` and an error
        # body, stored as Raw and read later as data.
        if body is not None and len(body) > limits.max_request_bytes:
            # Counted here as well as in `resolve`, and deliberately: `resolve` refuses by
            # the *profile's* limit and this refuses by the one the add-on was told.
            #
            # `[측정]` **It is not defence in depth.** `ADVERSARIAL-REVIEW-2026-08-19.md` F1
            # deleted this check entirely and the suite stayed green, because it is the same
            # `len(body) > limit` as `resolve`'s and carries the same flaw: `len` counts
            # elements, not bytes, for anything that is not exactly `bytes`.
            raise self._refused(
                Refusal(
                    RefusalReason.REQUEST_TOO_LARGE,
                    f"the request body for {endpoint_ref!r} is {len(body)} bytes and this "
                    f"source grants {limits.max_request_bytes}",
                    {
                        "endpoint_ref": endpoint_ref,
                        "limit": limits.max_request_bytes,
                        "size": len(body),
                    },
                )
            )
        credentials = self._require_credentials(profile)
        prepared = resolve(endpoint_ref, profile, params, body)
        if isinstance(prepared, Refusal):
            raise self._refused(prepared)

        # Pinned once, here, and handed to every hop below. `TransportLimits.starting_now`
        # is idempotent, so the transport will not restart the budget per request — which
        # is the redirect multiplier `ADVERSARIAL-REVIEW-2026-08-18.md` F5 names. One
        # `fetch` is one budget, however many hops it takes.
        bounds = TransportLimits.from_profile(profile).starting_now()
        hops = 0
        while True:
            try:
                sent = self._transport.send(
                    prepared, profile, headers=credentials, limits=bounds
                )
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

        response = self._record_response(
            prepared, endpoint_ref, sent.status, sent.headers, sent.body
        )
        if not 200 <= sent.status < 300:
            # Recorded before the add-on can catch anything, exactly as `_refused` does. By
            # the time add-on code could swallow this, the run already knows a non-success
            # status was handed over and undecided.
            self._undecided[response.envelope_ref] = sent.status
        return response

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

    def _emit_raw(self, limits: Limits, items: Sequence[RawItem]) -> None:
        proposed = self._buffer.item_count + len(items)
        if proposed > limits.max_records:
            # Across the run rather than per call: an add-on emitting one item at a time
            # would otherwise never meet a per-call bound. Checked before anything is
            # buffered, so a refused call leaves the buffer as it was — the refusal fails
            # the whole run anyway, and a half-applied batch would be a second state to
            # reason about for no gain.
            raise self._refused(
                Refusal(
                    RefusalReason.RECORD_LIMIT_EXCEEDED,
                    f"this source grants {limits.max_records} records per run and the "
                    f"collector emitted {proposed}",
                    {"limit": limits.max_records, "emitted": proposed},
                )
            )
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
            self._require_completion_transaction()
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

    def _require_completion_transaction(self) -> None:
        """Refuse to write unless these statements are inside the completion transaction.

        `ADVERSARIAL-REVIEW-2026-08-18.md` F3. H2a — *"a worker that lost its lease persists
        neither Raw nor cursor"* — is true only while `DomainStore` and `JobStore` share one
        connection, and that requirement was carried by a test fixture's docstring. On its
        own autocommit connection the `DomainStore` still never commits, and the reviewer
        measured Raw, items, and cursor all surviving a refused completion anyway: *"never
        commits" and "is inside the fence's transaction" are different properties.*

        Asked of the connection rather than of the wiring, and asked here rather than at
        bind time, because this is the moment at which the answer is a fact instead of a
        guess. `JobStore.durable_scope` has opened its transaction by now; if this store is
        on that connection its status is `INTRANS`, and if it is anywhere else — a second
        connection, an autocommit connection, no transaction at all — it is `IDLE`.

        `ConfigurationInvalidError` rather than a permanent failure because that is what it
        is: the host was assembled wrongly, no retry can change it, and SEC-003's rule is
        that such a process refuses rather than runs degraded. Nothing has been written when
        this raises — the buffer is still a buffer — so the refusal costs the collection and
        no partial state.
        """
        status = self._domain.connection.info.transaction_status
        if status in _INSIDE_A_TRANSACTION:
            return
        raise ConfigurationInvalidError(
            f"{self._addon.identity} cannot persist: this host's domain store is not inside "
            "the transaction that completes the attempt, so Raw and the cursor would survive "
            "a completion the fence refused",
            {
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                "transaction_status": status.name,
            },
        )

    def _require_declared_credential_is_granted(
        self, profile: OutboundProfile, source: Mapping[str, Any]
    ) -> None:
        """Refuse before any request if the add-on needs a credential the profile withholds.

        `[측정]` `ADVERSARIAL-REVIEW-2026-08-19.md` F2(a): the real `collector.naver.blog`,
        which declares `needs_credential = true`, ran against a profile granting none and
        **sent an anonymous request** — the gateway saw no credential headers at all. The
        manifest's declaration is the add-on's *request* and the profile is the *grant*, and
        nothing compared them.

        `CONFIGURATION_INVALID` rather than a permanent failure: an operator registered a
        source without the grant its add-on asked for, and no retry changes that. Checked
        here rather than at registration because a profile can be edited after a source is
        registered, and the run is where the two are both in hand.
        """
        if not self._addon.manifest.declares.needs_credential:
            return
        if profile.credentials:
            return
        raise ConfigurationInvalidError(
            f"{self._addon.identity} declares that it needs a credential and source "
            f"{source['source_id']!r} grants none; add a `credentials` entry to its "
            "outbound profile naming the header and the secret-store key",
            {
                "addon_id": self._addon.manifest.addon_id,
                "source_id": source["source_id"],
                "job_id": str(self._context.job_id),
            },
        )

    def _accept_status(self, response: FetchResponse, reason: str) -> None:
        """The add-on's statement that this non-success status is data for this source.

        Deliberately not silent and not implicit. `reason` is required and is logged, so a
        run that took a `404` as data leaves a record of who decided that and why — which is
        what an operator reading the Raw six weeks later needs.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise AddonOutputInvalid(
                "accept_status needs a reason: a status accepted without one is a decision "
                "nobody can review",
                {"status": response.status},
            )
        self._undecided.pop(response.envelope_ref, None)
        self._log(
            "status_accepted",
            {"status": response.status, "endpoint_ref": response.endpoint_ref,
             "reason": reason.strip()},
        )

    def _check_every_status_was_decided(self) -> None:
        """A non-success status the add-on neither raised on nor accepted fails the run.

        The same shape as `_check_no_refusal_was_swallowed`, and for the same reason: an
        add-on that returns normally after being handed a `401` has decided nothing, and
        `ADVERSARIAL-REVIEW-2026-08-19.md` F2 measured what that produces — a `SUCCEEDED` job
        with an error body stored as a Raw item.

        `[결정]` The platform does not decide what a status *means*. A `404` is "no results"
        to one source and "wrong endpoint" to another, and putting that knowledge here would
        be source semantics in the platform. What it enforces is that a decision happened.

        **The limit, stated because the whole point of this session was claims that overrun
        their code.** This is weaker than `_check_no_refusal_was_swallowed` beside it, and
        the difference is the direction of the failure:

        | | swallowed | result |
        |---|---|---|
        | a refusal | caught anyway | the run **fails** |
        | a status | accepted reflexively | the run **succeeds** |

        An add-on that calls `accept_status` on every response passes this check and behaves
        exactly as it did before the check existed. Nothing here can stop that, because
        stopping it means judging whether the acceptance was right, which means knowing the
        source. What this changes is the *default* — silence used to succeed — and it makes
        the alternative cost a call and a written reason, both logged and countable.

        `[추론]` Which is to say the useful successor to this check is not a stronger check.
        It is a **signal**: a run that accepted many statuses, or a normalization whose
        `skipped` equals its item count, is visible without any source knowledge at all.
        """
        if not self._undecided:
            return
        statuses = sorted(set(self._undecided.values()))
        raise PlatformPermanentError(
            f"{self._addon.identity} returned normally after a response with status "
            f"{', '.join(str(status) for status in statuses)} without raising or calling "
            "accept_status; a status nobody decided about is not a status anyone checked",
            {
                "statuses": statuses,
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
            },
        )

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

    def _require_credentials(self, profile: OutboundProfile) -> Mapping[str, str]:
        """This source's credential headers, or a failure the add-on cannot absorb.

        Recorded before it is raised, exactly as `_refused` does and for the same reason:
        by the time add-on code could catch this, the run already knows the request was
        never authenticated. Without that, `try: fetch() except Exception: pass` around a
        missing credential is a job that reports success having collected nothing — and
        goes on reporting it, because a retry resolves the same absent key.
        """
        try:
            return credential_headers(profile)
        except CredentialNotResolved as unresolved:
            if self._credential_failure is None:
                self._credential_failure = unresolved
            raise

    def _check_no_refusal_was_swallowed(self) -> None:
        if self._credential_failure is not None:
            raise self._credential_failure
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



class _ImportRun:
    """One attempt at one import job. DP-024.

    The collector's shape with the network taken out. What replaces `fetch` is
    `open_input`, and the two are the same idea: the add-on names something, the operator's
    approved profile says what that name is, and the add-on never composes a destination.

    Every guard clause a collect run applies to its source row applies here too, through
    the same `_resolved_source_row` and `_validated_config` those runs call. That is
    deliberate — `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5 measured what a second
    hand-written copy of those clauses costs, and this is the third kind.
    """

    def __init__(
        self,
        addon: LoadedAddon,
        context: JobContext,
        domain: DomainStore,
        logger: StructuredLogger | None,
        clock: Callable[[], datetime],
    ) -> None:
        self._addon = addon
        self._context = context
        self._domain = domain
        self._logger = logger
        self._clock = clock
        self._buffer = _Buffer()
        #: The first refusal this run met, whether or not the add-on let it out. Same
        #: reason as the collector's: a refused read that the add-on caught must still
        #: fail the job, or the rule is a suggestion.
        self._refusal: InputRefusal | None = None

    # ------------------------------------------------------------------ run

    def execute(self) -> None:
        source = self._require_source()
        profile = read_input_profile(source["input_profile"])
        stream = self._require_single_stream()
        config = self._require_config(source)
        cursor = self._domain.read_cursor(source["source_id"], stream)
        limits = _limits_for_input(source)

        importing = ImportContext(
            source_id=source["source_id"],
            config=config,
            cursor=cursor,
            limits=limits,
            open_input=lambda input_ref: self._open_input(profile, limits, input_ref),
            emit_raw=lambda items: self._emit_raw(limits, items),
            advance_cursor=lambda name, value: self._advance_cursor(stream, name, value),
            log=self._log,
        )
        outcome = self._addon.entry(importing)
        self._check_outcome(outcome)
        self._check_no_refusal_was_swallowed()
        self._context.enlist_durable_work(self._flush(source["source_id"]))

    # --------------------------------------------------------------- source

    def _require_source(self) -> Mapping[str, Any]:
        """The importer's own registered row, and the profile that says what it may read.

        The row carries the `input_profile`; the add-on carries only the names. An
        importer's row can hold no outbound profile — the `source` table refuses one — so
        nothing here can turn into a request.
        """
        return _resolved_source_row(
            self._context, self._domain, self._addon, "import", self._permanent
        )

    def _require_config(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        return _validated_config(self._addon, source)

    def _require_single_stream(self) -> str:
        declared = self._addon.manifest.declares.streams
        if len(declared) > 1:
            raise AddonOutputInvalid(
                "this host binds one cursor stream per source and this add-on declares "
                f"{len(declared)} (OQ-010)",
                {"streams": list(declared)},
            )
        return declared[0] if declared else CURSOR_STREAM_DEFAULT

    # --------------------------------------------------------------- reading

    def _open_input(
        self, profile: InputProfile | None, limits: Limits, input_ref: str
    ) -> OpenedInput:
        """Resolve a declared input name, take its bytes into Raw, and hand them over.

        The bytes are read **whole** rather than streamed past the add-on. Two reasons, and
        the second is the load-bearing one:

        * `max_input_bytes` already bounds what may be read, so holding it is bounded too.
        * The envelope has to exist before `emit_raw` can name it, and losslessness is the
          property that an item's original is preserved *whether or not* the add-on emits
          anything. A stream the platform never saw the end of could not promise that.
        """
        prepared = resolve_input(input_ref, profile)
        if isinstance(prepared, InputRefusal):
            raise self._refused(prepared)
        try:
            body = b"".join(open_stream(prepared, limits.max_input_bytes))
        except InputRefused as refused:
            raise self._refused(refused.refusal) from refused

        token = uuid4().hex
        self._buffer.envelopes.append(
            _Envelope(
                token=token,
                endpoint_ref=None,
                input_ref=input_ref,
                status=None,
                headers={},
                body=body,
                # The declared name only. Not the path: the path is the operator's and an
                # add-on that could read it back would learn a destination it never held.
                request_summary={"input_ref": input_ref, "bytes": len(body)},
                content_type=None,
            )
        )
        return OpenedInput(input_ref=input_ref, envelope_ref=token, body=body)

    # -------------------------------------------------------------- writing

    def _emit_raw(self, limits: Limits, items: Sequence[RawItem]) -> None:
        proposed = self._buffer.item_count + len(items)
        if proposed > limits.max_records:
            raise self._refused(
                InputRefusal(
                    InputRefusalReason.INPUT_TOO_LARGE,
                    f"this source grants {limits.max_records} records per run and the "
                    f"importer emitted {proposed}",
                    {"limit": limits.max_records, "emitted": proposed},
                )
            )
        known = {envelope.token for envelope in self._buffer.envelopes}
        for item in items:
            if item.envelope_ref is None or item.envelope_ref not in known:
                raise AddonOutputInvalid(
                    f"item {item.item_key!r} names no envelope this run opened",
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
            raise AddonOutputInvalid(
                "a cursor value of None cannot be stored: it is how 'never ran' is read back",
                {"stream": name},
            )
        self._buffer.cursor = (name, value)

    def _log(self, event: str, fields: Mapping[str, Any]) -> None:
        if self._logger is None:
            return
        self._logger.log(
            "INFO",
            f"addon.{event}",
            addon_id=self._addon.manifest.addon_id,
            addon_version=self._addon.manifest.addon_version,
            job_id=str(self._context.job_id),
            fields=dict(fields),
        )

    def _flush(self, source_id: str) -> Callable[[], None]:
        buffer = self._buffer
        attempt_id = self._context.attempt_id
        job_id = self._context.job_id
        manifest = self._addon.manifest

        def write() -> None:
            self._require_completion_transaction()
            for envelope in buffer.envelopes:
                envelope_id = self._domain.record_envelope(
                    source_id,
                    job_id,
                    attempt_id,
                    manifest.addon_id,
                    manifest.addon_version,
                    body=envelope.body,
                    content_type=envelope.content_type,
                    input_ref=envelope.input_ref,
                    request_summary=envelope.request_summary,
                )
                rows = buffer.items.get(envelope.token)
                if rows:
                    self._domain.record_items(envelope_id, source_id, rows)
            if buffer.cursor is not None:
                stream, value = buffer.cursor
                self._domain.advance_cursor(source_id, value, attempt_id, stream)

        return write

    # ------------------------------------------------------------- checking

    def _require_completion_transaction(self) -> None:
        """The collector's guard, asked the same way and for the same reason.

        `ADVERSARIAL-REVIEW-2026-08-18.md` F3: "never commits" and "is inside the fence's
        transaction" are different properties, and only the second one makes a lost lease
        persist nothing. An importer writes exactly what a collector writes, so it is
        exactly as exposed.
        """
        status = self._domain.connection.info.transaction_status
        if status in _INSIDE_A_TRANSACTION:
            return
        raise ConfigurationInvalidError(
            f"{self._addon.identity} cannot persist: this host's domain store is not inside "
            "the transaction that completes the attempt, so Raw and the cursor would survive "
            "a completion the fence refused",
            {
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                "transaction_status": status.name,
            },
        )

    def _check_outcome(self, outcome: object) -> None:
        if not isinstance(outcome, CollectOutcome):
            raise AddonOutputInvalid(
                f"an importer must return a CollectOutcome, not {type(outcome).__name__}",
                {"returned": type(outcome).__name__},
            )
        if outcome.items_emitted != self._buffer.item_count:
            raise AddonOutputInvalid(
                f"the importer reported {outcome.items_emitted} items and emitted "
                f"{self._buffer.item_count}",
                {"reported": outcome.items_emitted, "emitted": self._buffer.item_count},
            )

    def _check_no_refusal_was_swallowed(self) -> None:
        """A refused read that the add-on caught still fails the run.

        The collector's rule, applied unchanged: `try: open_input() except Exception: pass`
        would otherwise turn an approval boundary into a suggestion, and the job would
        report success having read nothing it was allowed to read.
        """
        if self._refusal is None:
            return
        raise PlatformPermanentError(
            f"an input was refused and the importer did not stop: {self._refusal.summary}",
            {
                "reason": self._refusal.reason.value,
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                **dict(self._refusal.detail),
            },
        )

    def _refused(self, refusal: InputRefusal) -> PlatformPermanentError:
        if self._refusal is None:
            self._refusal = refusal
        return PlatformPermanentError(
            refusal.summary,
            {
                "reason": refusal.reason.value,
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


class _NormalizeRun:
    """One attempt at one normalize job: a sealed snapshot in, versioned results out.

    Structurally a sibling of `_CollectRun` and deliberately not a subclass of it. The two
    share four checks — the source row, the config schema, the completion transaction, the
    outcome cross-check — and differ in everything the contract says they differ in: this
    one has no `fetch`, no credential, no cursor, no page counter, and no refusal to be
    swallowed, because its input is fixed before it starts. A base class holding the union
    of both would be a place for a collector's machinery to reach a normalizer by accident,
    which is the coupling `NormalizeContext` exists to prevent.
    """

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
        self._logger = logger
        self._clock = clock
        #: What the add-on emitted, held until the completion transaction writes it. Same
        #: reason as `_CollectRun`'s buffer: DP-010 puts the writes and the fenced
        #: completion in one transaction, so a run that lost its lease persists nothing.
        self._results: list[NormalizedResultRow] = []

    # ------------------------------------------------------------------ run

    def execute(self) -> None:
        source = self._require_source()
        config = self._require_config(source)
        snapshot = self._require_verified_snapshot()
        members = self._domain.read_snapshot_items(snapshot["id"])
        keys = {str(row["item_key"]) for row in members}

        normalize = NormalizeContext(
            run_id=str(self._context.attempt_id),
            snapshot_id=str(snapshot["id"]),
            config=config,
            read_snapshot=lambda: iter(
                [
                    SnapshotItem(
                        item_key=str(row["item_key"]),
                        payload=bytes(row["payload"]),
                        content_type=str(row["content_type"]),
                    )
                    for row in members
                ]
            ),
            emit_result=self._emit_result,
            log=self._log,
        )
        outcome = self._addon.entry(normalize)
        self._check_outcome(outcome)
        self._check_lineage(keys)
        self._context.enlist_durable_work(self._flush(snapshot["id"], str(snapshot["source_id"])))

    # --------------------------------------------------------------- inputs

    def _require_source(self) -> Mapping[str, Any]:
        """The normalizer's own registered row. Its config is the run's configuration.

        A normalizer has a source row of its own — DP-008 D5 derives the handler from
        `addon_id`, so it must — and the `source` table refuses to give that row an
        outbound profile or a credential. The snapshot names a *different* source: the one
        whose Raw was sealed. Keeping them apart is what lets one normalizer read several
        collectors' snapshots without inheriting any collector's grants.
        """
        return _resolved_source_row(
            self._context, self._domain, self._addon, "normalize", self._permanent
        )

    def _require_config(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        return _validated_config(self._addon, source)

    def _require_verified_snapshot(self) -> Mapping[str, Any]:
        """The sealed input, hash-checked before the add-on sees a byte.

        `NormalizeContext`'s docstring promises exactly this, and it is the reason a
        snapshot is materialized rather than queried: an input that could change under a
        run makes determinism unclaimable. Tampering is a *permanent* failure — recomputing
        the digest again will not change the answer — and it names which member failed,
        because "this snapshot is broken" and "member 3 was edited" need different actions.
        """
        stated = self._context.payload_field(SNAPSHOT_ID_FIELD)
        if not isinstance(stated, str) or not stated:
            raise self._permanent(
                f"a normalize job must name a sealed snapshot in its {SNAPSHOT_ID_FIELD!r} "
                "payload field (DP-019 D6)"
            )
        try:
            snapshot_id = UUID(stated)
        except ValueError:
            raise self._permanent(
                f"{SNAPSHOT_ID_FIELD!r} is not a snapshot identifier"
            ) from None
        snapshot = self._domain.read_snapshot(snapshot_id)
        if snapshot is None:
            raise self._permanent(f"no snapshot {stated} exists")
        if snapshot["sealed_at"] is None:
            raise self._permanent(f"snapshot {stated} is not sealed and cannot be consumed")
        problems = self._domain.snapshot_tampering(snapshot_id)
        if problems:
            raise PlatformPermanentError(
                f"snapshot {stated} no longer matches what was sealed: {'; '.join(problems)}",
                {
                    "snapshot_id": stated,
                    "addon_id": self._addon.manifest.addon_id,
                    "job_id": str(self._context.job_id),
                },
            )
        return snapshot

    # -------------------------------------------------------------- writing

    def _emit_result(self, results: Sequence[NormalizedResult]) -> None:
        for result in results:
            self._results.append(
                NormalizedResultRow(
                    source_item_key=result.source_item_key,
                    body=dict(result.body),
                    notes=dict(result.notes),
                )
            )

    def _log(self, event: str, fields: Mapping[str, Any]) -> None:
        if self._logger is None:
            return
        self._logger.log(
            "INFO",
            f"addon.{event}",
            addon_id=self._addon.manifest.addon_id,
            addon_version=self._addon.manifest.addon_version,
            job_id=str(self._context.job_id),
            fields=dict(fields),
        )

    def _flush(self, snapshot_id: UUID, source_id: str) -> Callable[[], None]:
        """The durable work. Runs in the completion transaction and nowhere else."""
        results = self._results
        manifest = self._addon.manifest
        output_contract = manifest.output_contract_version or "0"

        def write() -> None:
            self._require_completion_transaction()
            self._domain.record_results(
                snapshot_id, source_id, manifest.addon_id, manifest.addon_version,
                output_contract, results,
            )

        return write

    # ------------------------------------------------------------- checking

    def _require_completion_transaction(self) -> None:
        """The same precondition `_CollectRun` checks, for the same reason and against the
        same finding. `ADVERSARIAL-REVIEW-2026-08-18.md` F3."""
        status = self._domain.connection.info.transaction_status
        if status in _INSIDE_A_TRANSACTION:
            return
        raise ConfigurationInvalidError(
            f"{self._addon.identity} cannot persist: this host's domain store is not inside "
            "the transaction that completes the attempt, so results would survive a "
            "completion the fence refused",
            {
                "addon_id": self._addon.manifest.addon_id,
                "job_id": str(self._context.job_id),
                "transaction_status": status.name,
            },
        )

    def _check_outcome(self, outcome: object) -> None:
        if not isinstance(outcome, NormalizeOutcome):
            raise AddonOutputInvalid(
                f"a normalizer must return a NormalizeOutcome, not {type(outcome).__name__}",
                {"returned": type(outcome).__name__},
            )
        if outcome.results_emitted != len(self._results):
            raise AddonOutputInvalid(
                f"the normalizer reported {outcome.results_emitted} results and emitted "
                f"{len(self._results)}",
                {"reported": outcome.results_emitted, "emitted": len(self._results)},
            )

    def _check_lineage(self, keys: set[str]) -> None:
        """Every result must name an item the snapshot actually held.

        The normalizer's version of `raw_item.envelope_id` being not null: a result whose
        `source_item_key` is in no snapshot is an interpretation nobody can check against
        the bytes it claims to come from, and the P0 Charter asks for that link by name.
        """
        for result in self._results:
            if result.source_item_key not in keys:
                raise AddonOutputInvalid(
                    f"result {result.source_item_key!r} names an item this snapshot does "
                    "not hold",
                    {"source_item_key": result.source_item_key},
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

#: What a connection inside an open transaction reports. `IDLE` is the mis-wiring F3
#: measured; `UNKNOWN` means the connection is broken and cannot be trusted to say.
_INSIDE_A_TRANSACTION: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.INTRANS, TransactionStatus.ACTIVE, TransactionStatus.INERROR}
)


def _limits_of(profile: OutboundProfile) -> Limits:
    """Tell the add-on this source's bounds — all six of which the platform enforces.

    `[측정]` Between `27f712b` and the F1 repair, two of the six were passed through and
    counted nowhere: `_fetch` had no call counter and `_emit_raw` had no item counter, so
    a collector fetching 12 times and emitting 600 items against `{max_pages: 2,
    max_records: 3}` succeeded. `_CollectRun._pages` and the `_Buffer.item_count` test in
    `_emit_raw` are those counters, and `TestThePageLimitIsEnforced` and
    `TestTheRecordLimitIsEnforced` are written against add-ons that ignore what is told
    to them here — which is the only way to tell enforcement from cooperation.
    """
    limits = {**DEFAULT_LIMITS, **profile.limits}
    return Limits(
        connect_timeout_s=float(limits["connect_timeout_s"]),
        read_timeout_s=float(limits["read_timeout_s"]),
        max_response_bytes=int(limits["max_response_bytes"]),
        max_redirects=int(limits["max_redirects"]),
        max_pages=int(limits["max_pages"]),
        max_records=int(limits["max_records"]),
        max_request_bytes=int(limits["max_request_bytes"]),
        max_input_bytes=int(limits["max_input_bytes"]),
    )


def _limits_for_input(source: Mapping[str, Any]) -> Limits:
    """An importer's bounds. Every network member is the default and unused.

    An importer holds no outbound profile — the `source` table refuses it one — so there is
    no per-source place to state a timeout it will never spend. `max_records` and
    `max_input_bytes` are the two that mean anything here, and both come from
    `DEFAULT_LIMITS` unless the operator's row overrides them.
    """
    stored = source.get("input_profile") or {}
    overrides = stored.get("limits", {}) if isinstance(stored, Mapping) else {}
    limits = {**DEFAULT_LIMITS, **overrides}
    return Limits(
        connect_timeout_s=float(limits["connect_timeout_s"]),
        read_timeout_s=float(limits["read_timeout_s"]),
        max_response_bytes=int(limits["max_response_bytes"]),
        max_redirects=int(limits["max_redirects"]),
        max_pages=int(limits["max_pages"]),
        max_records=int(limits["max_records"]),
        max_request_bytes=int(limits["max_request_bytes"]),
        max_input_bytes=int(limits["max_input_bytes"]),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
