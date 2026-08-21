"""Data access for the domain tables. Nothing here commits.

Copy-adapted from ``experiments/integrated-p0/domain/store.py``. Every table
reference is schema-qualified (``cosmai.<table>``) rather than left to
``search_path``, the same adaptation ``platform_core.jobs.store`` makes and for
the same reason (DP-032 D1/D3). CTE shapes, column lists, and every statement's
actual logic are otherwise unchanged from P0 **except** the three deviations
this module's docstring and the affected functions name explicitly — DP-029
D2/D3 (snapshot member selection and manifest ordering) and DP-030 D2 (per-record
fault tolerance in ``canonical_body``/``record_results``).

The convention is ``platform_core.jobs.store.JobStore``'s, deliberately and for a
load-bearing reason rather than for symmetry. That module says:

    The connection is the caller's. Nothing here commits, opens a transaction, or
    closes anything, because the transaction boundary is one of the things this
    experiment is meant to observe rather than hide. Every method is one statement,
    so an autocommit connection gives one transaction per operation.

That last sentence is exactly what P0-A could get away with and P0-B cannot. A
collection is **three or more statements** — the Raw envelope, its items, and the
cursor — and then a fourth that closes the attempt. On an autocommit connection
those are four transactions, and an interruption between any two leaves Raw without
a cursor (the same records collected again) or a cursor without Raw (records lost
silently, forever, with nothing to notice it by).

So a collection is wrapped, by its caller, in one explicit transaction:

    with connection.transaction():
        store.record_envelope(...)
        store.record_items(...)
        store.advance_cursor(...)
        completion = job_store.complete_success(job_id, attempt_id, worker_id)
        if not completion:
            raise LeaseNoLongerHeld(...)      # rolls the whole thing back

Two properties make that correct, and neither is obvious:

* **The fenced completion goes last.** ``JobStore``'s completion statement checks
  that this worker still owns the lease and that its attempt row is still open. Put
  first, it would pass and then the Raw writes could still fail; put last, its
  refusal discards the Raw writes with it, because they are in the same transaction.
  A worker that lost its lease must not persist Raw or advance a cursor — some other
  worker has already been given the same work.
* **Nothing here commits.** If any method opened its own transaction, the statements
  would leave the caller's boundary one at a time and the paragraph above would be
  decoration. That is why this module has no ``commit`` and no ``transaction()``.

**Three deviations from P0, all decided by DP-029/DP-030 rather than found here.**

1. **Snapshot member selection (DP-029 D2).** P0's ``SELECT_SNAPSHOT_MEMBERS``
   broke a same-``item_key`` tie with ``emitted_at desc, id desc`` —
   ``emitted_at`` is a **transaction** timestamp, not a per-row order, and the
   ``uuid4`` fallback it drops to on a tie selected the *older* payload in 2 of
   3 keys across 12 forced re-seals (DP-029's own evidence). This module orders
   by ``raw_item.seq`` (a ``generated always as identity`` column,
   ``apps/platform_core/db/migrations/0002_domain.sql``) instead — the highest
   ``seq`` for one key wins, independent of which transaction wrote which row.
2. **Manifest member ordering (DP-029 D3).** P0's snapshot-selection query's
   outer ``order by item_key`` used whatever collation the connected database
   and column carried, and a collation-only column alteration (no value
   changed) reordered every member a read-time selection returned on a
   development cluster (DP-029's evidence). This module orders by
   ``convert_to(item_key, 'UTF8')`` — PostgreSQL's ``bytea`` comparison is
   always unsigned-byte order, so this is a fixed UTF-8 bytewise comparison
   regardless of the connection's or the column's collation. Chosen over an
   app-side ``sorted(members, key=lambda m: m.item_key.encode("utf-8"))``
   because the ordinal (which fixes ``snapshot_item.ordinal`` and therefore the
   manifest digest) has to be assigned before the rows are materialized either
   way, and doing it in the same statement that already selects the rows is
   one round trip instead of two.
3. **Per-record fault tolerance in ``canonical_body``/``record_results``
   (DP-030 D2; repairs ``P1-INHERITED-DEFECTS.md`` §1).** P0's
   ``canonical_body`` called ``json.dumps`` with the default ``allow_nan=True``
   and no guard at all against a lone UTF-16 surrogate reaching
   ``.encode("utf-8")`` — either one raised out of ``record_results`` and ended
   the whole normalize run for one bad record. ``canonical_body`` here passes
   ``allow_nan=False`` (closing the ``NaN`` gap P0 left unbounded), and
   ``record_results`` catches both failure modes per record via
   ``_safe_canonical_body``: the offending top-level field is replaced with
   ``None`` in a copy of the body, a ``notes.normalize_error {field, reason}``
   entry is written, and the run continues. See ``_safe_canonical_body`` and
   ``record_results`` for the mechanism and its documented limits.

This is the first real exercise of the limitation the P0-A Completion Gate recorded
first: every duplicate-suppression result there rests on **one row with a
primary-key conflict**, and a durable effect spanning several statements was
untested. Cursor advancement together with Raw persistence is that effect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

__all__ = [
    "CURSOR_STREAM_DEFAULT",
    "DomainStore",
    "NormalizedResultRow",
    "RawItemRow",
    "RecordResultsSummary",
    "SnapshotMember",
    "SourceRow",
    "canonical_body",
    "digest_of",
]

#: The stream name an add-on gets when it advances a cursor without naming one. A
#: single-stream source is the ordinary case and should not have to invent a word for
#: it; a multi-stream source names its own, and `[declares].streams` is what an
#: operator sees.
CURSOR_STREAM_DEFAULT: Final = "default"


def digest_of(payload: bytes) -> str:
    """The lowercase hex SHA-256 the schema's CHECK constraints expect."""
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class SourceRow:
    """A registered source as the database holds it.

    ``config`` carries no secret: ``addon_api.validate_config`` refuses a field the
    manifest marked ``secret``, and ``credential_ref`` is a key **name** whose shape
    the schema checks. Both halves of DP-008 D6 are therefore enforced somewhere
    other than in the code that happens to write this row.
    """

    source_id: str
    addon_id: str
    addon_version: str
    kind: str
    config: Mapping[str, Any] = field(default_factory=dict)
    config_schema_version: str = "1"
    credential_ref: str | None = None
    outbound_profile: Mapping[str, Any] | None = None
    #: DP-024. What an importer is allowed to read, as the operator approved it. The
    #: schema refuses this on any other kind, mirroring `outbound_profile`'s refusal on a
    #: normalizer.
    input_profile: Mapping[str, Any] | None = None
    data_class: str = "local"
    enabled: bool = True


@dataclass(frozen=True)
class RawItemRow:
    """One item an add-on extracted, on its way to ``raw_item``."""

    item_key: str
    payload: bytes
    content_type: str
    notes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedResultRow:
    """One normalized record on its way to ``normalized_result``.

    ``source_item_key`` is the lineage link the P0 Charter's exit criteria ask for by name.
    ``body`` is Schema 0.1+ (DP-019 D1, DP-030 D4) and is checked against the add-on's
    declared output contract by the host, not here.
    """

    source_item_key: str
    body: Mapping[str, Any]
    notes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordResultsSummary:
    """What one ``record_results`` call did — DP-030 D2's run-summary aggregate.

    Not itself a "run" object (that is M3's ``addon_host`` concern); this is the
    per-call count a run summary is built from. ``written`` counts every result
    persisted, ``error_records`` counts how many of those carried a
    ``notes.normalize_error`` entry because their canonical serialization failed
    and was substituted (DP-030 D2) rather than aborting the call.
    """

    written: int
    error_records: int


def canonical_body(body: Mapping[str, Any]) -> bytes:
    """The one serialization a result's digest is taken over (DP-019 D4).

    Determinism is required of a normalizer — ``NormalizeContext``'s own docstring says the
    same snapshot must produce byte-identical results — and "byte-identical" is only a
    testable claim once the bytes are fixed by something other than each writer's habits.
    So: sorted keys, no whitespace, and ``ensure_ascii=False``.

    The last one is not cosmetic. This source's documents are Korean; escaping them to
    ``제`` would make every digest depend on a serializer setting nobody stated, and a
    later change of that setting would look like a normalizer that stopped being
    deterministic.

    **DP-030 D2, closing a gap P0 left unbounded.** P0 called ``json.dumps`` with the
    default ``allow_nan=True``, so a non-finite float in any add-on's body reached the
    store as a bare ``NaN``/``Infinity`` literal — not valid JSON, and nothing downstream
    was contracted to expect it. ``allow_nan=False`` here means such a value raises
    ``ValueError`` in this function instead, the same way a lone UTF-16 surrogate already
    raised ``UnicodeEncodeError`` from the ``.encode("utf-8")`` below (``json.dumps`` itself
    does not reject a lone surrogate; only encoding the resulting ``str`` to bytes does).
    Both failure modes now route through ``_safe_canonical_body``'s per-record fallback in
    ``record_results`` rather than escaping uncaught — this function itself still raises on
    either, so a caller that wants the *record*, not the run, to survive must go through
    that fallback rather than call this function directly on untrusted input.
    """
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _safe_canonical_body(
    body: Mapping[str, Any],
) -> tuple[bytes, Mapping[str, Any], dict[str, str] | None]:
    """Canonicalize ``body``, substituting a per-record fallback instead of raising.

    DP-030 D2; repairs ``P1-INHERITED-DEFECTS.md`` §1's finding that one malformed row
    (P0's example: ``{"code": "a\\ud800"}``, a lone surrogate) raised out of
    ``domain.store.canonical_body`` and ended the whole normalize run.

    Tries the whole body first — the common, fast path, and the one every existing
    test exercises. On the two failure modes ``canonical_body`` can raise (a
    ``ValueError`` from a non-finite float now that ``allow_nan=False``, or a
    ``UnicodeEncodeError`` from a lone surrogate surviving ``json.dumps`` and failing
    only at ``.encode("utf-8")``), narrows the search to **one top-level field**: each
    field of ``body`` is serialized and encoded on its own, in insertion order, and
    the first one that fails the same way is replaced with ``None`` in a copy of
    ``body``. Every field that fails this per-field check is nulled — not only the
    first — so the record the store ends up writing never carries an unencodable
    value forward, even though only the first offending field is *named*.

    **Why only the first field is named.** DP-030 D2's own text describes one
    ``notes.normalize_error {field, reason}`` entry per record, a single object
    rather than a list. A record with two simultaneously-bad top-level fields is
    possible but was not the case DP-030 D2's evidence (`P1-INHERITED-DEFECTS.md`
    §1's single-surrogate example) or this module's regression test exercise — this
    is a documented narrowing, not a silent one, and a future packet that needs every
    offending field named is free to widen the shape.

    **What this cannot localize.** A value that fails only when nested two or more
    levels deep inside a field that is itself well-formed at the top level — the
    scan checks each top-level field's *entire* value, so it does find a surrogate or
    a NaN anywhere inside that field's structure; what it cannot do is name a field
    *within* a nested object as the culprit, only the top-level field containing it.
    If no top-level field reproduces the failure the whole body raised with (which
    ``TestCanonicalBodyRejectsWhatItClaimsTo`` in ``tests/test_domain_store.py``
    checks does not happen for the documented cases), the whole body is replaced
    with an empty one and the reason is recorded as an opaque failure — a
    last-resort fallback that keeps the guarantee ("a bad record never aborts the
    run") rather than the guarantee resting on this scan finding a name for every
    case.
    """
    try:
        return canonical_body(body), body, None
    except (ValueError, UnicodeEncodeError):
        pass

    safe_body: dict[str, Any] = dict(body)
    error: dict[str, str] | None = None
    for name, value in body.items():
        try:
            canonical_body({name: value})
        except (ValueError, UnicodeEncodeError) as exc:
            safe_body[name] = None
            if error is None:
                error = {"field": name, "reason": str(exc)}

    if error is None:
        # The failure did not reproduce at any single top-level field (nested more
        # deeply than one field can localize, or an interaction between fields).
        # The guarantee this function exists to keep — a bad record never aborts
        # the caller's run — still has to hold, so the body is replaced wholesale
        # rather than raising here.
        return (
            canonical_body({}),
            {},
            {"field": "<body>", "reason": "canonical serialization failed"},
        )

    return canonical_body(safe_body), safe_body, error


@dataclass(frozen=True)
class SnapshotMember:
    """One sealed snapshot member, in the order the snapshot fixes."""

    ordinal: int
    item_key: str
    payload: bytes
    content_type: str


INSERT_SOURCE = """
insert into cosmai.source (
    source_id, addon_id, addon_version, kind, config, config_schema_version,
    credential_ref, outbound_profile, input_profile, data_class, enabled
) values (
    %(source_id)s, %(addon_id)s, %(addon_version)s, %(kind)s, %(config)s,
    %(config_schema_version)s, %(credential_ref)s, %(outbound_profile)s,
    %(input_profile)s, %(data_class)s, %(enabled)s
)
"""

READ_SOURCE = """
select source_id, addon_id, addon_version, kind, config, config_schema_version,
       credential_ref, outbound_profile, input_profile, data_class, enabled, created_at, updated_at
from cosmai.source
where source_id = %(source_id)s
"""

LIST_SOURCES = """
select source_id, addon_id, addon_version, kind, config, config_schema_version,
       credential_ref, outbound_profile, input_profile, data_class, enabled, created_at, updated_at
from cosmai.source
order by source_id
"""

READ_CURSOR = """
select cursor, stream, updated_by_attempt, updated_at
from cosmai.source_cursor
where source_id = %(source_id)s and stream = %(stream)s
"""

# One statement, so a first advance and a later one are the same call. The cursor is
# replaced rather than merged: it is opaque to the platform, so merging would require
# interpreting it.
ADVANCE_CURSOR = """
insert into cosmai.source_cursor (source_id, stream, cursor, updated_by_attempt)
values (%(source_id)s, %(stream)s, %(cursor)s, %(attempt_id)s)
on conflict (source_id, stream) do update
set cursor = excluded.cursor,
    updated_by_attempt = excluded.updated_by_attempt,
    updated_at = now()
"""

INSERT_ENVELOPE = """
insert into cosmai.raw_envelope (
    id, source_id, job_id, attempt_id, addon_id, addon_version,
    endpoint_ref, input_ref, request_summary, status, response_headers,
    body, body_sha256, content_type
) values (
    %(id)s, %(source_id)s, %(job_id)s, %(attempt_id)s, %(addon_id)s, %(addon_version)s,
    %(endpoint_ref)s, %(input_ref)s, %(request_summary)s, %(status)s, %(response_headers)s,
    %(body)s, %(body_sha256)s, %(content_type)s
)
"""

INSERT_ITEM = """
insert into cosmai.raw_item (id, envelope_id, source_id, item_key, payload, content_type, notes)
values (%(id)s, %(envelope_id)s, %(source_id)s, %(item_key)s, %(payload)s,
        %(content_type)s, %(notes)s)
"""

COUNT_ITEMS_OF_SOURCE = (
    "select count(*) as total from cosmai.raw_item where source_id = %(source_id)s"
)

INSERT_SNAPSHOT = """
insert into cosmai.snapshot (id, source_id, item_count, manifest_sha256, selection, sealed_at)
values (%(id)s, %(source_id)s, %(item_count)s, %(manifest_sha256)s, %(selection)s, now())
"""

INSERT_SNAPSHOT_ITEM = """
insert into cosmai.snapshot_item (
    snapshot_id, ordinal, item_key, payload, content_type, payload_sha256
)
values (%(snapshot_id)s, %(ordinal)s, %(item_key)s, %(payload)s, %(content_type)s, %(digest)s)
"""

# The selection, as one statement. DP-029 D2/D3, both deviations from P0 named in this
# module's docstring:
#
#   * The inner `distinct on (item_key) ... order by item_key, seq desc` collapses a
#     duplicate key to the row with the **highest `seq`** — an explicit, monotonically
#     increasing per-row identity column, independent of which transaction wrote which
#     row. P0 used `emitted_at desc, id desc`; `emitted_at` is a transaction timestamp,
#     and the `uuid4` id it fell back to on a genuine tie selected the *older* payload
#     in 2 of 3 keys across 12 forced re-seals (DP-029's evidence).
#   * The outer `order by convert_to(item_key, 'UTF8')` fixes manifest member order to
#     UTF-8 bytewise comparison, independent of the connection's or the column's
#     collation — `convert_to` returns `bytea`, and PostgreSQL's `bytea` ordering is
#     always unsigned-byte order. P0's outer `order by item_key` used whatever
#     collation was in effect, and DP-029's evidence found a collation-only column
#     change (no value altered) reordered every member a read-time selection returned.
SELECT_SNAPSHOT_MEMBERS = """
select item_key, payload, content_type
from (
    select distinct on (item_key) item_key, payload, content_type, seq
    from cosmai.raw_item
    where source_id = %(source_id)s
    order by item_key, seq desc
) latest
order by convert_to(item_key, 'UTF8')
"""

INSERT_RESULT = """
insert into cosmai.normalized_result (
    id, snapshot_id, source_id, addon_id, addon_version, output_contract_version,
    source_item_key, body, body_sha256, notes
) values (
    %(id)s, %(snapshot_id)s, %(source_id)s, %(addon_id)s, %(addon_version)s,
    %(output_contract_version)s, %(source_item_key)s, %(body)s, %(body_sha256)s, %(notes)s
)
"""

READ_RESULTS = """
select id, snapshot_id, source_id, addon_id, addon_version, output_contract_version,
       source_item_key, body, body_sha256, notes, created_at
from cosmai.normalized_result
where snapshot_id = %(snapshot_id)s
  and (%(addon_version)s::text is null or addon_version = %(addon_version)s::text)
order by source_item_key, addon_version, output_contract_version
"""

RAW_SUMMARY = """
select (select count(*) from cosmai.raw_envelope where source_id = %(source_id)s) as envelope_count,
       (select count(*) from cosmai.raw_item where source_id = %(source_id)s) as item_count,
       (select max(retrieved_at) from cosmai.raw_envelope where source_id = %(source_id)s)
           as last_retrieved_at
"""

# Newest first, because the snapshot an operator wants is almost always the one just
# sealed. `id` breaks ties so paging is stable when two are sealed in one instant.
LIST_SNAPSHOTS = """
select id, source_id, item_count, manifest_sha256, selection, sealed_at, created_at
from cosmai.snapshot
where %(source_id)s::text is null or source_id = %(source_id)s::text
order by created_at desc, id desc
"""

READ_SNAPSHOT = """
select id, source_id, item_count, manifest_sha256, selection, sealed_at, created_at
from cosmai.snapshot
where id = %(snapshot_id)s
"""

READ_SNAPSHOT_ITEMS = """
select ordinal, item_key, payload, content_type, payload_sha256
from cosmai.snapshot_item
where snapshot_id = %(snapshot_id)s
order by ordinal
"""


class DomainStore:
    """Data access for the domain tables. One instance per connection, no commits."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    @property
    def connection(self) -> psycopg.Connection[Any]:
        """The connection these writes go out on. Readable so the requirement above
        can be *checked* rather than described.

        `ADVERSARIAL-REVIEW-2026-08-18.md` F3 is why this exists. This module's docstring
        says a collection must be wrapped by its caller in one transaction with the fenced
        completion, and until 2026-08-18 that requirement was carried by a fixture
        docstring: put on its own autocommit connection, this store still never committed —
        and Raw, items, and the cursor all survived a refused completion anyway, because
        *"never commits" and "is inside the fence's transaction" are different properties*.
        A caller cannot check the second one without being able to ask which connection
        this is, so it asks.
        """
        return self._connection

    # -------------------------------------------------------------- sources

    def register_source(self, source: SourceRow) -> None:
        """Insert a registered source. The caller validated ``config`` already.

        Validation is ``addon_api.validate_config``'s and is not repeated here: it
        needs the add-on's declared schema, which is a manifest and not a row. What
        this layer still guarantees is the part a caller cannot get wrong — the
        schema's own constraints on ``credential_ref``'s shape and on what a
        normalizer source may be granted.
        """
        with self._cursor() as cursor:
            cursor.execute(
                INSERT_SOURCE,
                {
                    "source_id": source.source_id,
                    "addon_id": source.addon_id,
                    "addon_version": source.addon_version,
                    "kind": source.kind,
                    "config": Jsonb(dict(source.config)),
                    "config_schema_version": source.config_schema_version,
                    "credential_ref": source.credential_ref,
                    "outbound_profile": (
                        None
                        if source.outbound_profile is None
                        else Jsonb(dict(source.outbound_profile))
                    ),
                    "input_profile": (
                        None
                        if source.input_profile is None
                        else Jsonb(dict(source.input_profile))
                    ),
                    "data_class": source.data_class,
                    "enabled": source.enabled,
                },
            )

    def read_source(self, source_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            cursor.execute(READ_SOURCE, {"source_id": source_id})
            return cursor.fetchone()

    def list_sources(self) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            cursor.execute(LIST_SOURCES)
            return list(cursor.fetchall())

    # -------------------------------------------------------------- cursors

    def read_cursor(self, source_id: str, stream: str = CURSOR_STREAM_DEFAULT) -> Any | None:
        """The opaque value this source last wrote for ``stream``, or ``None``.

        ``None`` means "no cursor yet", which an add-on reads as "start at the
        beginning". A stored JSON ``null`` would be indistinguishable from that, so
        an add-on that wants to record "finished" has to write something other than
        null — noted here because the alternative is a cursor that silently resets.
        """
        with self._cursor() as cursor:
            cursor.execute(READ_CURSOR, {"source_id": source_id, "stream": stream})
            row = cursor.fetchone()
        return None if row is None else row["cursor"]

    def advance_cursor(
        self,
        source_id: str,
        cursor_value: Any,
        attempt_id: UUID,
        stream: str = CURSOR_STREAM_DEFAULT,
    ) -> None:
        """Record where this source has now reached, as of ``attempt_id``.

        Must run inside the same transaction as the Raw writes it accompanies and the
        completion that closes the attempt. See this module's docstring: on its own
        this is one more autocommit statement, and a cursor that moved without its
        Raw is how records are lost with nothing to notice it by.
        """
        with self._cursor() as cursor:
            cursor.execute(
                ADVANCE_CURSOR,
                {
                    "source_id": source_id,
                    "stream": stream,
                    "cursor": Jsonb(cursor_value),
                    "attempt_id": attempt_id,
                },
            )

    # ------------------------------------------------------------------ raw

    def record_envelope(
        self,
        source_id: str,
        job_id: UUID,
        attempt_id: UUID,
        addon_id: str,
        addon_version: str,
        body: bytes,
        content_type: str | None = None,
        endpoint_ref: str | None = None,
        input_ref: str | None = None,
        request_summary: Mapping[str, Any] | None = None,
        status: int | None = None,
        response_headers: Mapping[str, str] | None = None,
    ) -> UUID:
        """Persist the lossless original and return its id.

        Written by the platform before an add-on sees the bytes, which is what makes
        losslessness independent of add-on quality: an add-on that carves a response
        badly has produced bad items over a preserved original rather than lost the
        original.

        ``request_summary`` and ``response_headers`` must already have had
        Authorization, Cookie, and provider-protected headers removed. Stripping is
        the caller's — the platform's outbound guard — because a header that reached
        this method has already been in memory next to a credential.
        """
        envelope_id = uuid4()
        with self._cursor() as cursor:
            cursor.execute(
                INSERT_ENVELOPE,
                {
                    "id": envelope_id,
                    "source_id": source_id,
                    "job_id": job_id,
                    "attempt_id": attempt_id,
                    "addon_id": addon_id,
                    "addon_version": addon_version,
                    "endpoint_ref": endpoint_ref,
                    "input_ref": input_ref,
                    "request_summary": (
                        None if request_summary is None else Jsonb(dict(request_summary))
                    ),
                    "status": status,
                    "response_headers": (
                        None if response_headers is None else Jsonb(dict(response_headers))
                    ),
                    "body": body,
                    "body_sha256": digest_of(body),
                    "content_type": content_type,
                },
            )
        return envelope_id

    def record_items(
        self, envelope_id: UUID, source_id: str, items: Sequence[RawItemRow]
    ) -> tuple[UUID, ...]:
        """Persist what an add-on extracted from one envelope.

        ``item_key`` is not made unique. What duplicate and changed-content policy it
        feeds is an open P0-B contract question, and enforcing uniqueness here would
        answer it silently. ``raw_item.seq`` (DP-029 D2) is assigned by the database
        (``generated always as identity``) and is never supplied here.
        """
        identifiers: list[UUID] = []
        with self._cursor() as cursor:
            for item in items:
                item_id = uuid4()
                cursor.execute(
                    INSERT_ITEM,
                    {
                        "id": item_id,
                        "envelope_id": envelope_id,
                        "source_id": source_id,
                        "item_key": item.item_key,
                        "payload": item.payload,
                        "content_type": item.content_type,
                        "notes": Jsonb(dict(item.notes)),
                    },
                )
                identifiers.append(item_id)
        return tuple(identifiers)

    def count_items(self, source_id: str) -> int:
        with self._cursor() as cursor:
            cursor.execute(COUNT_ITEMS_OF_SOURCE, {"source_id": source_id})
            row = cursor.fetchone()
        return 0 if row is None else int(row["total"])

    # ------------------------------------------------------------- snapshots

    def seal_snapshot(
        self,
        source_id: str,
        members: Sequence[SnapshotMember],
        selection: Mapping[str, Any] | None = None,
    ) -> UUID:
        """Materialize a snapshot and seal it in one call, returning its id.

        Created and sealed together on purpose: an unsealed snapshot is a state
        nothing in P0 can consume, so leaving one reachable would add a state whose
        only use is to be wrong. Growing a snapshot incrementally is a change to make
        when something needs it.

        The manifest digest is over ``ordinal``, ``item_key``, and each member's own
        digest — not over the payloads themselves. That is what lets tamper detection
        recompute one digest instead of re-reading every payload, and it is why
        altering a payload is still detectable: the member digest changes, so the
        manifest digest computed from it does too.

        DP-029 D1: materialized. Member bytes are copied into ``snapshot_item`` here,
        at seal time — the caller's ``members`` (typically ``seal_snapshot_from_raw``'s
        already-selected rows) are not referenced from ``raw_item`` again afterward.
        """
        snapshot_id = uuid4()
        manifest = [
            {"ordinal": member.ordinal, "item_key": member.item_key,
             "sha256": digest_of(member.payload)}
            for member in members
        ]
        manifest_digest = digest_of(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        with self._cursor() as cursor:
            cursor.execute(
                INSERT_SNAPSHOT,
                {
                    "id": snapshot_id,
                    "source_id": source_id,
                    "item_count": len(members),
                    "manifest_sha256": manifest_digest,
                    "selection": Jsonb(dict(selection or {})),
                },
            )
            for member in members:
                cursor.execute(
                    INSERT_SNAPSHOT_ITEM,
                    {
                        "snapshot_id": snapshot_id,
                        "ordinal": member.ordinal,
                        "item_key": member.item_key,
                        "payload": member.payload,
                        "content_type": member.content_type,
                        "digest": digest_of(member.payload),
                    },
                )
        return snapshot_id

    def record_results(
        self,
        snapshot_id: UUID,
        source_id: str,
        addon_id: str,
        addon_version: str,
        output_contract_version: str,
        results: Sequence[NormalizedResultRow],
    ) -> RecordResultsSummary:
        """Persist one run's results. Raises on a rerun of the same version over the same
        snapshot, which the unique index makes a duplicate rather than a version.

        DP-030 D2: a record whose canonical serialization fails (a lone surrogate, a
        non-finite float — see ``_safe_canonical_body``) does not raise out of this
        call and does not abort the rest of ``results``. It is written with the
        offending field replaced by ``null`` and a ``notes.normalize_error`` entry,
        and counted in the returned ``RecordResultsSummary`` rather than only logged —
        repairing ``P1-INHERITED-DEFECTS.md`` §1, where the same failure ended the
        whole run.
        """
        written = 0
        error_records = 0
        with self._cursor() as cursor:
            for result in results:
                serialized, safe_body, error = _safe_canonical_body(result.body)
                notes = dict(result.notes)
                if error is not None:
                    notes["normalize_error"] = error
                    error_records += 1
                cursor.execute(
                    INSERT_RESULT,
                    {
                        "id": uuid4(),
                        "snapshot_id": snapshot_id,
                        "source_id": source_id,
                        "addon_id": addon_id,
                        "addon_version": addon_version,
                        "output_contract_version": output_contract_version,
                        "source_item_key": result.source_item_key,
                        "body": Jsonb(dict(safe_body)),
                        "body_sha256": digest_of(serialized),
                        "notes": Jsonb(notes),
                    },
                )
                written += 1
        return RecordResultsSummary(written=written, error_records=error_records)

    def read_results(
        self, snapshot_id: UUID, addon_version: str | None = None
    ) -> list[dict[str, Any]]:
        """Every result over one snapshot, or one add-on version's.

        Unfiltered by default because coexistence is the point: a reader comparing two
        normalizer versions asks for both and narrows afterwards.
        """
        with self._cursor() as cursor:
            cursor.execute(
                READ_RESULTS, {"snapshot_id": snapshot_id, "addon_version": addon_version}
            )
            return list(cursor.fetchall())

    def seal_snapshot_from_raw(self, source_id: str) -> UUID:
        """Materialize and seal every ``raw_item`` of one source, ordered by ``item_key``.

        DP-019 D5 for the rule ("every raw_item of one source, ordered by item_key"),
        DP-029 D2/D3 for how the two open halves of that rule are now decided — see
        ``SELECT_SNAPSHOT_MEMBERS``'s own comment and this module's docstring.

        **A duplicate key collapses to the highest ``seq``.** ``raw_item`` deliberately
        carries no uniqueness constraint on ``item_key`` — duplicate policy is still an
        open question — while ``snapshot_item`` requires one row per key, so something
        has to choose. DP-029 D2 chose the row with the highest ``seq``.
        """
        with self._cursor() as cursor:
            cursor.execute(SELECT_SNAPSHOT_MEMBERS, {"source_id": source_id})
            rows = cursor.fetchall()
        members = [
            SnapshotMember(
                ordinal=ordinal,
                item_key=row["item_key"],
                payload=bytes(row["payload"]),
                content_type=row["content_type"],
            )
            for ordinal, row in enumerate(rows)
        ]
        return self.seal_snapshot(
            source_id,
            members,
            selection={
                "source_id": source_id,
                "rule": "every raw_item of one source, ordered by item_key",
                "manifest_order": "UTF-8 bytewise (DP-029 D3)",
                "duplicate_key": "highest seq wins (DP-029 D2)",
                "decided_by": "DP-019 D5; DP-029 D2/D3",
            },
        )

    def raw_summary(self, source_id: str) -> dict[str, Any]:
        """How much this source has collected. Counts, never payloads.

        A page of Raw bodies on an operator screen is a page of unreviewed external text,
        and nothing in P0-B needs one to answer "did the collection do anything". The last
        instant is included because a count alone cannot distinguish a source that
        collected once a month ago from one that is collecting now.
        """
        with self._cursor() as cursor:
            cursor.execute(RAW_SUMMARY, {"source_id": source_id})
            row = cursor.fetchone()
        assert row is not None
        return {
            "source_id": source_id,
            "envelope_count": int(row["envelope_count"]),
            "item_count": int(row["item_count"]),
            "last_retrieved_at": (
                None if row["last_retrieved_at"] is None else row["last_retrieved_at"].isoformat()
            ),
        }

    def list_snapshots(self, source_id: str | None = None) -> list[dict[str, Any]]:
        """Sealed snapshots, newest first, optionally for one source."""
        with self._cursor() as cursor:
            cursor.execute(LIST_SNAPSHOTS, {"source_id": source_id})
            return list(cursor.fetchall())

    def read_snapshot(self, snapshot_id: UUID) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            cursor.execute(READ_SNAPSHOT, {"snapshot_id": snapshot_id})
            return cursor.fetchone()

    def read_snapshot_items(self, snapshot_id: UUID) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            cursor.execute(READ_SNAPSHOT_ITEMS, {"snapshot_id": snapshot_id})
            return list(cursor.fetchall())

    def snapshot_tampering(self, snapshot_id: UUID) -> tuple[str, ...]:
        """Every way this snapshot no longer matches what was sealed.

        Returns reasons rather than a boolean, and an empty tuple when the snapshot
        verifies. A boolean would be the wrong shape: "the manifest digest differs"
        and "member 3's payload was altered" need different operator actions, and a
        normalizer run refused for tampering has to say which.

        Recomputed from the stored rows, so it detects a payload edited in place. It
        does **not** detect a snapshot deleted whole, which is a different question
        and one OQ-004/`SR-003` still own along with backend-independent snapshot
        identity and the erasure obligation (DP-029 D4).
        """
        snapshot = self.read_snapshot(snapshot_id)
        if snapshot is None:
            return (f"snapshot {snapshot_id} does not exist",)
        items = self.read_snapshot_items(snapshot_id)
        problems: list[str] = []
        if len(items) != int(snapshot["item_count"]):
            problems.append(
                f"sealed with {snapshot['item_count']} members but {len(items)} are present"
            )
        manifest: list[dict[str, Any]] = []
        for item in items:
            recomputed = digest_of(bytes(item["payload"]))
            if recomputed != item["payload_sha256"]:
                problems.append(
                    f"member {item['ordinal']} ({item['item_key']!r}) no longer matches its digest"
                )
            manifest.append(
                {"ordinal": item["ordinal"], "item_key": item["item_key"], "sha256": recomputed}
            )
        recomputed_manifest = digest_of(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        if recomputed_manifest != snapshot["manifest_sha256"]:
            problems.append("the recomputed manifest digest differs from the sealed one")
        return tuple(problems)

    # ---------------------------------------------------------------- internal

    def _cursor(self) -> psycopg.Cursor[dict[str, Any]]:
        return self._connection.cursor(row_factory=dict_row)
