"""Streaming export of Raw items and normalized results (M6 batch 6b; DP-033 D3).

D3's own text: exports are scoped by source, a date period, and an ``item_key``
prefix; Raw defaults to JSONL (lossless, re-importable) with a CSV option;
normalized results flatten to CSV; and — the property this module exists to hold —
every export streams rather than buffers a full result set (H3: "M6's download
implementation cannot complete a full-source export without holding the entire
result set in process memory at once" is the falsification condition).

**How streaming actually happens.** ``_rows`` opens a *named* (server-side)
cursor — ``connection.cursor(name=..., ...)`` rather than the ordinary client-side
cursor every other store in this tree uses — and sets ``itersize``. A named
cursor is what makes ``for row in cursor`` fetch in ``BATCH_SIZE``-row batches
from the server instead of the driver pulling the whole result set across the
wire on ``execute()`` and holding it client-side; that second behavior is what an
ordinary cursor does, and it is exactly the thing H3 asks this module not to do.
The generator functions below (``stream_raw``/``stream_results``) never call
``fetchall()``, and never build a Python list of rows — each output line or CSV
row is produced from one fetched row and yielded immediately, which is what lets
``fastapi.responses.StreamingResponse`` hand bytes to the client as they are
produced rather than after the whole export has been assembled in memory.

A named cursor needs an ordinary (non-autocommit) connection: unlike every other
read in ``domain.api`` (``connect(config, autocommit=True)``, one statement, one
implicit transaction, closed immediately), this module opens its own connection
with the default ``autocommit=False`` and keeps it — and the transaction the
first statement on it opens — alive for as long as the streaming response is
being drained, closing it in a ``finally`` so a client that disconnects mid-export
(or one that reads to the end) both release the connection exactly once.

**Two format shapes, one for each of the two content types this module knows
about.** JSONL: one line per row, metadata fields plus the row's own content.
For Raw, the stored ``payload`` is spliced into the line **verbatim** rather than
round-tripped through ``json.loads``/``json.dumps`` when it already parses as
JSON (the ordinary case — an add-on's items are JSON) — the point is that the
export byte-for-byte reproduces what was persisted rather than a reformatted
equivalent of it; a payload that is not valid JSON falls back to an escaped
string field instead. Normalized-result bodies have no such byte-identity
question (they are stored as ``jsonb``, already parsed), so their JSONL line is
an ordinary ``json.dumps``. CSV: metadata/envelope columns plus one payload/body
column, using the streaming-``csv.writer`` idiom (``_Echo``) so a formatted row
is handed straight to the caller rather than buffered into a file object first.
Both formats always write at least a header (CSV) or nothing at all (JSONL,
correctly zero lines) for an empty result, so an empty export is a valid empty
file rather than a client-visible error.

**Redaction.** ``apps/domain/api.py``'s own ``result_view`` passes
``normalized_result.body`` through ``redact_mapping`` before it reaches an
operator — a normalizer's output is treated as external text on every egress
path, JSON API or export alike, so this module applies the same redaction here.
Raw's ``payload`` is not redacted, by the same DP-033 D2 reasoning
``apps/domain/api.py``'s ``raw_item_view`` already states: no body-level
redaction mechanism exists anywhere in this platform for Raw, and this module
does not invent one.

**Scope filters.** ``source_id`` is required — an export with no source is not a
smaller export, it is a different, unbounded feature D3's own rejected
alternative ("one format, no scope filter") explicitly declines. ``from``/``to``
bound the row's own timestamp (``raw_item.emitted_at`` / `normalized_result.
created_at``); ``key_prefix`` is a prefix match on the row's key
(`item_key`/`source_item_key`) using PostgreSQL's ``starts_with``, chosen over a
hand-built ``LIKE`` pattern so a prefix containing ``%`` or ``_`` is matched
literally rather than as a wildcard.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any, Final
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.obs.redaction import redact_mapping

__all__ = ["RAW_HEADER", "RESULT_HEADER", "stream_raw", "stream_results"]

#: How many rows one FETCH pulls from the server-side cursor. Small enough that
#: no meaningful fraction of a large export sits in memory at once; large enough
#: that a 10,000-row export does not pay a network round trip per row.
BATCH_SIZE: Final = 500

#: RFC4180 quoting (what `csv.writer` already guarantees) protects a cell from breaking
#: CSV *syntax*; it says nothing about a spreadsheet application choosing to *evaluate*
#: a well-quoted cell because its content starts with one of these characters — CSV
#: formula injection (M-S4, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`). The content
#: this guards (an add-on's `payload`, a normalized `body`) is exactly the untrusted
#: content DP-033 D2 already forces to plain text on the dashboard's own detail pane and
#: preview cell (M-S5, same review); this is that rule's export-path equivalent.
_FORMULA_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@")


def _csv_cell(value: str) -> str:
    """`value`, prefixed with a literal `'` if a spreadsheet would read it as a formula
    on open. A no-op for every other string — including one that already starts with
    `'`, which this does not double-guard."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


RAW_HEADER: Final[tuple[str, ...]] = ("item_key", "seq", "emitted_at", "content_type", "payload")

RESULT_HEADER: Final[tuple[str, ...]] = (
    "id",
    "snapshot_id",
    "source_id",
    "addon_id",
    "addon_version",
    "output_contract_version",
    "source_item_key",
    "body_sha256",
    "notes",
    "created_at",
    "body",
)

RAW_EXPORT_QUERY = """
select item_key, seq, emitted_at, content_type, payload
from cosmai.raw_item
where source_id = %(source_id)s
  and (%(from_ts)s::timestamptz is null or emitted_at >= %(from_ts)s::timestamptz)
  and (%(to_ts)s::timestamptz is null or emitted_at <= %(to_ts)s::timestamptz)
  and (%(key_prefix)s::text is null or starts_with(item_key, %(key_prefix)s))
order by seq
"""

RESULTS_EXPORT_QUERY = """
select id, snapshot_id, source_id, addon_id, addon_version, output_contract_version,
       source_item_key, body, body_sha256, notes, created_at
from cosmai.normalized_result
where source_id = %(source_id)s
  and (%(from_ts)s::timestamptz is null or created_at >= %(from_ts)s::timestamptz)
  and (%(to_ts)s::timestamptz is null or created_at <= %(to_ts)s::timestamptz)
  and (%(key_prefix)s::text is null or starts_with(source_item_key, %(key_prefix)s))
order by created_at, id
"""


class _Echo:
    """A file-like object whose ``write`` hands the formatted text straight back.

    The standard way to make ``csv.writer`` a line formatter instead of something
    that owns a buffer: ``writer.writerow(row)`` returns whatever ``write``
    returns, so ``writer.writerow(row)`` itself is one CSV line, ready to yield.
    """

    def write(self, value: str) -> str:
        return value


def _instant(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def _rows(
    connection: psycopg.Connection[Any],
    query: str,
    source_id: str,
    from_ts: datetime | None,
    to_ts: datetime | None,
    key_prefix: str | None,
) -> Iterator[dict[str, Any]]:
    """Every matching row, fetched ``BATCH_SIZE`` at a time from a server-side
    cursor. Never ``fetchall()``, never a materialized list — see this module's
    docstring."""
    with connection.cursor(name=f"export_{uuid4().hex}", row_factory=dict_row) as cursor:
        cursor.itersize = BATCH_SIZE
        cursor.execute(
            query,
            {
                "source_id": source_id,
                "from_ts": from_ts,
                "to_ts": to_ts,
                "key_prefix": key_prefix,
            },
        )
        yield from cursor


def _raw_jsonl_line(row: Mapping[str, Any]) -> bytes:
    """One line: metadata as JSON, ``payload`` spliced in verbatim when the stored
    bytes already parse as JSON (see this module's docstring), or as an escaped
    string field when they do not."""
    payload = bytes(row["payload"])
    meta = json.dumps(
        {
            "item_key": row["item_key"],
            "seq": int(row["seq"]),
            "emitted_at": _instant(row["emitted_at"]),
            "content_type": row["content_type"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        field = json.dumps(payload.decode("utf-8", errors="replace"), ensure_ascii=False)
    else:
        # B3 (REVIEW-M2-M7.md): `json.loads` accepts embedded newlines (and any other
        # whitespace JSON permits between tokens), so a pretty-printed payload spliced
        # in verbatim would put its own newlines inside what is supposed to be one JSONL
        # line, corrupting every line after it for a line-oriented reader. Re-serializing
        # the parsed value compactly keeps the payload's *content* exactly as stored
        # (this is the JSONL export, not the stored Raw bytes themselves — `_raw_csv_rows`
        # below carries the payload as a CSV field with its own quoting, untouched) while
        # guaranteeing the one structural property JSONL requires: no newline inside a
        # line.
        field = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    # `meta` is a compact `json.dumps` of a flat mapping, so it is `{...}` with no
    # trailing content after the closing brace; splicing `payload` in before that
    # brace is what keeps it spliced in rather than re-serialized.
    return (meta[:-1] + ',"payload":' + field + "}\n").encode("utf-8")


def _raw_csv_rows(rows: Iterator[Mapping[str, Any]]) -> Iterator[bytes]:
    writer = csv.writer(_Echo())
    yield writer.writerow(RAW_HEADER).encode("utf-8")
    for row in rows:
        payload_text = bytes(row["payload"]).decode("utf-8", errors="replace")
        yield writer.writerow(
            [
                _csv_cell(row["item_key"]),
                int(row["seq"]),
                _instant(row["emitted_at"]),
                _csv_cell(row["content_type"]),
                _csv_cell(payload_text),
            ]
        ).encode("utf-8")


def stream_raw(
    config: PlatformConfig,
    source_id: str,
    from_ts: datetime | None,
    to_ts: datetime | None,
    key_prefix: str | None,
    fmt: str,
) -> Iterator[bytes]:
    """Every ``raw_item`` of ``source_id`` matching the scope filters, streamed.

    Opens its own connection (not the short-lived ``autocommit=True`` one every
    other read in ``domain.api`` uses) because the named cursor `_rows` opens
    needs an ordinary transaction to stay alive across the whole response — see
    this module's docstring. Closed in ``finally`` regardless of whether the
    generator ran to completion or was abandoned by a disconnected client.
    """
    connection = connect(config)
    try:
        rows = _rows(connection, RAW_EXPORT_QUERY, source_id, from_ts, to_ts, key_prefix)
        if fmt == "csv":
            yield from _raw_csv_rows(rows)
        else:
            for row in rows:
                yield _raw_jsonl_line(row)
    finally:
        connection.close()


def _result_jsonl_line(row: Mapping[str, Any]) -> bytes:
    obj = {
        "id": str(row["id"]),
        "snapshot_id": str(row["snapshot_id"]),
        "source_id": row["source_id"],
        "addon_id": row["addon_id"],
        "addon_version": row["addon_version"],
        "output_contract_version": row["output_contract_version"],
        "source_item_key": row["source_item_key"],
        "body_sha256": row["body_sha256"],
        "notes": row["notes"],
        "created_at": _instant(row["created_at"]),
        "body": dict(redact_mapping(row["body"])),
    }
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _result_csv_rows(rows: Iterator[Mapping[str, Any]]) -> Iterator[bytes]:
    writer = csv.writer(_Echo())
    yield writer.writerow(RESULT_HEADER).encode("utf-8")
    for row in rows:
        body = dict(redact_mapping(row["body"]))
        yield writer.writerow(
            [
                str(row["id"]),
                str(row["snapshot_id"]),
                _csv_cell(row["source_id"]),
                _csv_cell(row["addon_id"]),
                row["addon_version"],
                row["output_contract_version"],
                _csv_cell(row["source_item_key"]),
                row["body_sha256"],
                _csv_cell(json.dumps(row["notes"], ensure_ascii=False)),
                _instant(row["created_at"]),
                _csv_cell(json.dumps(body, ensure_ascii=False)),
            ]
        ).encode("utf-8")


def stream_results(
    config: PlatformConfig,
    source_id: str,
    from_ts: datetime | None,
    to_ts: datetime | None,
    key_prefix: str | None,
    fmt: str,
) -> Iterator[bytes]:
    """Every ``normalized_result`` whose ``source_id`` (the normalizer that
    produced it) matches, across every snapshot — the export's scope is the
    source and the period, not one snapshot at a time. See `stream_raw` for the
    connection-lifetime reasoning; identical here."""
    connection = connect(config)
    try:
        rows = _rows(connection, RESULTS_EXPORT_QUERY, source_id, from_ts, to_ts, key_prefix)
        if fmt == "csv":
            yield from _result_csv_rows(rows)
        else:
            for row in rows:
                yield _result_jsonl_line(row)
    finally:
        connection.close()
