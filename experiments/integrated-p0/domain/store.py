"""Data access for the domain tables. Nothing here commits.

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
    "RawItemRow",
    "SnapshotMember",
    "SourceRow",
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
class SnapshotMember:
    """One sealed snapshot member, in the order the snapshot fixes."""

    ordinal: int
    item_key: str
    payload: bytes
    content_type: str


INSERT_SOURCE = """
insert into source (
    source_id, addon_id, addon_version, kind, config, config_schema_version,
    credential_ref, outbound_profile, data_class, enabled
) values (
    %(source_id)s, %(addon_id)s, %(addon_version)s, %(kind)s, %(config)s,
    %(config_schema_version)s, %(credential_ref)s, %(outbound_profile)s,
    %(data_class)s, %(enabled)s
)
"""

READ_SOURCE = """
select source_id, addon_id, addon_version, kind, config, config_schema_version,
       credential_ref, outbound_profile, data_class, enabled, created_at, updated_at
from source
where source_id = %(source_id)s
"""

LIST_SOURCES = """
select source_id, addon_id, addon_version, kind, config, config_schema_version,
       credential_ref, outbound_profile, data_class, enabled, created_at, updated_at
from source
order by source_id
"""

READ_CURSOR = """
select cursor, stream, updated_by_attempt, updated_at
from source_cursor
where source_id = %(source_id)s and stream = %(stream)s
"""

# One statement, so a first advance and a later one are the same call. The cursor is
# replaced rather than merged: it is opaque to the platform, so merging would require
# interpreting it.
ADVANCE_CURSOR = """
insert into source_cursor (source_id, stream, cursor, updated_by_attempt)
values (%(source_id)s, %(stream)s, %(cursor)s, %(attempt_id)s)
on conflict (source_id, stream) do update
set cursor = excluded.cursor,
    updated_by_attempt = excluded.updated_by_attempt,
    updated_at = now()
"""

INSERT_ENVELOPE = """
insert into raw_envelope (
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
insert into raw_item (id, envelope_id, source_id, item_key, payload, content_type, notes)
values (%(id)s, %(envelope_id)s, %(source_id)s, %(item_key)s, %(payload)s,
        %(content_type)s, %(notes)s)
"""

COUNT_ITEMS_OF_SOURCE = "select count(*) as total from raw_item where source_id = %(source_id)s"

INSERT_SNAPSHOT = """
insert into snapshot (id, source_id, item_count, manifest_sha256, selection, sealed_at)
values (%(id)s, %(source_id)s, %(item_count)s, %(manifest_sha256)s, %(selection)s, now())
"""

INSERT_SNAPSHOT_ITEM = """
insert into snapshot_item (snapshot_id, ordinal, item_key, payload, content_type, payload_sha256)
values (%(snapshot_id)s, %(ordinal)s, %(item_key)s, %(payload)s, %(content_type)s, %(digest)s)
"""

READ_SNAPSHOT = """
select id, source_id, item_count, manifest_sha256, selection, sealed_at, created_at
from snapshot
where id = %(snapshot_id)s
"""

READ_SNAPSHOT_ITEMS = """
select ordinal, item_key, payload, content_type, payload_sha256
from snapshot_item
where snapshot_id = %(snapshot_id)s
order by ordinal
"""


class DomainStore:
    """Data access for the domain tables. One instance per connection, no commits."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

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
        answer it silently.
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
        and one OQ-004 still owns along with backend-independent snapshot identity.
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
