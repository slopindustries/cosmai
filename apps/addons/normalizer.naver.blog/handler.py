"""Naver blog search results into `Normalized Schema 0.1` (DP-019 D1).

Copy-adapted from ``experiments/integrated-p0/addons/normalizer.naver.blog/handler.py``
(M4 naver-blog worktree). Structurally the two rules P0 wrote are unchanged. What
changed is what happens to a record this add-on cannot fully normalize: P0 skipped it
(no result emitted, ``NormalizeOutcome.skipped`` incremented); this add-on emits a
result with the fields it could not derive set to ``null`` and a
``notes.normalize_error {field, reason}`` entry, and counts it instead of dropping it.

That is `docs/decisions/DP-030-p1-normalization-scope.md` D2, a P1 contract
requirement, not a local style choice: "On a record's normalization failure, the run
substitutes missing values for that record's fields, writes `normalize_error {field,
reason}` to the record's `notes`, and continues; the run summary aggregates the
error-record count." D2 rejected P0's skip-and-count behavior by name (per-record
candidate 1) because ``P1-INHERITED-DEFECTS.md`` §1 measured that a failure *below*
the normalizer still aborted the whole run — the fix has to hold at the record level,
inside the add-on, not only in `domain.store`'s own `_safe_canonical_body` fallback
(which only ever catches a body that fails to *serialize*, not one this add-on
declined to extract from a malformed or incomplete Raw item).

**Why every item now produces exactly one result.** A `SnapshotItem.item_key` is
assigned by `collector.naver.blog` at collection time and is always present in the
sealed snapshot, independent of whether this add-on can parse the item's `payload`.
So `source_item_key` never has to be invented, even for a record this add-on cannot
read at all — which is what makes "substitute nulls and continue" possible instead of
"skip because there is nothing to name the result by".

**Two distinct failure shapes, not one.** A payload that is not valid JSON (or not a
JSON object) carries no usable data at all, so every derived field is nulled. A
payload that parses but carries no usable `link` still has a title, a description, a
`postdate`, and a blogger name worth keeping — only `external_id`/`url` (both derived
from `link`) are nulled, and `notes.normalize_error` names `link` as the field that
failed. Both shapes are one record, one `normalize_error` entry (DP-030 D2's own text:
a single object per record, matching `domain.store._safe_canonical_body`'s "name the
first offending field" convention), and the run's own summary aggregates how many of
the emitted results carried one, in `NormalizeOutcome.notes["error_records"]`.

Two rules are applied to a record that *does* have a `link`, and both are reversible
against the preserved Raw:

**Markup removal.** The API wraps matched terms in `<b>...</b>` and HTML-escapes the rest.
`[확인 사실]` Documented at https://api.ncloud-docs.com/docs/naver-api-hub-search-blog
(fetched 2026-08-18) as the response shape; the `<b>` wrapping is visible in every sample
the documentation shows. Left in, every downstream reader has to strip it and the ones that
forget will compare `"<b>수분크림</b>"` with `"수분크림"` and find them different.

**Date parsing.** `postdate` is `yyyymmdd`. Anything that does not parse becomes `null`
rather than a guess — `published_at` is nullable in Schema 0.1 for exactly this case, and a
guessed date is a fact nobody can trace back to the bytes it came from.

`[가설]` Everything here is written against the *documented* response shape. No capture of
the real source existed when it was written. The falsification condition is a real capture
whose `title`, `description`, `link`, `bloggername`, or `postdate` behaves differently —
which is what the real-data scenario exists to find out.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome, SnapshotItem

SCHEMA_VERSION = "0.1"
RECORD_TYPE = "document"
DEFAULT_LANGUAGE = "ko"

#: The API's own emphasis markup. Only `<b>` is documented; the pattern is written for any
#: tag rather than for that one, because a normalizer that removed `<b>` and left `<strong>`
#: would produce records that differ by which tag the provider happened to choose.
_TAG = re.compile(r"<[^>]+>")

#: `yyyymmdd`, and nothing else. A looser parser would accept `2026-08-01` and `01/08/2026`
#: and silently disagree with itself about which is the month.
_POSTDATE = re.compile(r"^(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})$")


def run(context: NormalizeContext) -> NormalizeOutcome:
    """One sealed snapshot in, exactly one Schema 0.1 record per item out (DP-030 D2)."""
    language = _require_language(context)
    results: list[NormalizedResult] = []
    error_records = 0

    for item in context.read_snapshot():
        result, failed = _normalize_item(item, language)
        results.append(result)
        if failed:
            error_records += 1

    # One call with the whole run's results rather than one per item: the host buffers them
    # and writes inside the completion transaction (DP-010), so batching changes nothing
    # about atomicity and keeps the interaction log readable.
    context.emit_result(results)
    context.log(
        "normalize.complete",
        {"results_emitted": len(results), "error_records": error_records},
    )
    return NormalizeOutcome(
        results_emitted=len(results),
        skipped=0,
        notes={
            "schema_version": SCHEMA_VERSION,
            "language": language,
            "error_records": error_records,
        },
    )


def _require_language(context: NormalizeContext) -> str:
    stated = context.config_field("language", DEFAULT_LANGUAGE)
    if not isinstance(stated, str) or not stated.strip():
        return DEFAULT_LANGUAGE
    return stated.strip()


def _normalize_item(item: SnapshotItem, language: str) -> tuple[NormalizedResult, bool]:
    """One item's result, and whether it carries a `normalize_error` (DP-030 D2)."""
    entry, parse_failure = _parse(item.payload)
    if entry is None:
        assert parse_failure is not None
        return (
            _error_result(item.item_key, language, field="payload", reason=parse_failure),
            True,
        )

    link = entry.get("link")
    if not isinstance(link, str) or not link:
        # `link` is both the identity and the lineage key when it is present. It is not
        # `source_item_key` here — that always comes from the snapshot, never from the
        # payload — but the derived fields (`external_id`, `url`) have nothing to be
        # derived from, so they null while every other field this entry does carry is
        # kept, per D2's "substitute what could not be derived" rather than "null the
        # whole record".
        return (
            _partial_result(
                item.item_key, language, entry, field="link",
                reason="missing or invalid `link` field",
            ),
            True,
        )

    return (
        NormalizedResult(
            source_item_key=item.item_key,
            body={
                "schema_version": SCHEMA_VERSION,
                "record_type": RECORD_TYPE,
                "external_id": link,
                "url": link,
                "title": _plain(entry.get("title")),
                "excerpt": _plain(entry.get("description")),
                "published_at": _iso_date(entry.get("postdate")),
                "author": _optional_text(entry.get("bloggername")),
                "language": language,
            },
            notes={"blogger_link": _optional_text(entry.get("bloggerlink"))},
        ),
        False,
    )


def _error_result(item_key: str, language: str, *, field: str, reason: str) -> NormalizedResult:
    """A record whose payload carried no usable data at all — every derived field nulls."""
    return NormalizedResult(
        source_item_key=item_key,
        body={
            "schema_version": SCHEMA_VERSION,
            "record_type": RECORD_TYPE,
            "external_id": None,
            "url": None,
            "title": None,
            "excerpt": None,
            "published_at": None,
            "author": None,
            "language": language,
        },
        notes={"normalize_error": {"field": field, "reason": reason}},
    )


def _partial_result(
    item_key: str, language: str, entry: dict[str, Any], *, field: str, reason: str
) -> NormalizedResult:
    """A record whose payload parsed but was missing its identity — keep what parsed."""
    return NormalizedResult(
        source_item_key=item_key,
        body={
            "schema_version": SCHEMA_VERSION,
            "record_type": RECORD_TYPE,
            "external_id": None,
            "url": None,
            "title": _plain(entry.get("title")),
            "excerpt": _plain(entry.get("description")),
            "published_at": _iso_date(entry.get("postdate")),
            "author": _optional_text(entry.get("bloggername")),
            "language": language,
        },
        notes={
            "blogger_link": _optional_text(entry.get("bloggerlink")),
            "normalize_error": {"field": field, "reason": reason},
        },
    )


def _parse(payload: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """The parsed payload, or `(None, reason)` naming why it could not be used."""
    try:
        entry = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, "payload is not valid JSON"
    if not isinstance(entry, dict):
        return None, "payload is not a JSON object"
    return entry, None


def _plain(value: object) -> str:
    """Markup out, entities decoded, and never `None` when the source gave a string.

    `title` and `excerpt` are not nullable in Schema 0.1 for an ordinary result — an empty
    string says the source gave nothing, which is a claim; `null` would be a defect. A
    record whose entry never reached this function at all (the whole-payload failure case
    in `_error_result`) is a different claim — DP-030 D2's — and is nulled there instead.
    Unescaping happens **after** tag removal, so an escaped `&lt;b&gt;` in the original text
    survives as text rather than being turned into a tag and then stripped.
    """
    if not isinstance(value, str):
        return ""
    return html.unescape(_TAG.sub("", value)).strip()


def _optional_text(value: object) -> str | None:
    """A nullable field. `""` and `null` are different claims and are kept different."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _iso_date(value: object) -> str | None:
    """`yyyymmdd` to `yyyy-mm-dd`, or `None`.

    The month and day ranges are checked here rather than left to a consumer: `20261301`
    parses under a pattern that only counts digits, and a record carrying it would be a
    date nothing downstream can compare.
    """
    if not isinstance(value, str):
        return None
    matched = _POSTDATE.match(value.strip())
    if matched is None:
        return None
    year, month, day = (int(matched.group(name)) for name in ("year", "month", "day"))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"
