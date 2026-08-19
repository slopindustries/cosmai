"""Naver blog search results into `Normalized Schema 0.1` (DP-019 D1).

**Structural, and deliberately dull.** One snapshot item becomes at most one document
record. There is no sentiment, no topic, no ingredient extraction, and no scoring, because
DP-019 D1 forbids them and gives the reason: a schema carrying an inference answers the
product question `OQ-002` has not been asked while claiming to answer a plumbing one. What
this add-on is *for* is testing that the pipeline carries meaning end to end, and an
inference in the middle would make a wrong result impossible to attribute.

Two rules are applied, and both are reversible against the preserved Raw:

**Markup removal.** The API wraps matched terms in `<b>...</b>` and HTML-escapes the rest.
`[확인 사실]` Documented at https://api.ncloud-docs.com/docs/naver-api-hub-search-blog
(fetched 2026-08-18) as the response shape; the `<b>` wrapping is visible in every sample
the documentation shows. Left in, every downstream reader has to strip it and the ones that
forget will compare `"<b>수분크림</b>"` with `"수분크림"` and find them different.

**Date parsing.** `postdate` is `yyyymmdd`. Anything that does not parse becomes `null`
rather than a guess — `published_at` is nullable in Schema 0.1 for exactly this case, and a
guessed date is a fact nobody can trace back to the bytes it came from.

**What is skipped rather than failed.** An item whose payload is not JSON, or that carries
no `link`, produces no record and increments `skipped`. `NormalizeOutcome` separates
`skipped` from `results_emitted` because "this item produced nothing" and "this item was
never looked at" are different claims. Raising instead would lose every good item in the
snapshot to one bad one, and the bad one is still in Raw to be looked at.

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
from addon_api.results import NormalizedResult, NormalizeOutcome

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
    """One sealed snapshot in, one Schema 0.1 record per usable item out."""
    language = _require_language(context)
    results: list[NormalizedResult] = []
    skipped = 0

    for item in context.read_snapshot():
        entry = _parse(item.payload)
        if entry is None:
            skipped += 1
            continue
        link = entry.get("link")
        if not isinstance(link, str) or not link:
            # `link` is both the identity and the lineage key. Inventing one would break
            # the link from a result back to the bytes it came from, which the P0 Charter's
            # exit criteria ask for by name.
            skipped += 1
            continue
        results.append(
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
            )
        )

    # One call with the whole run's results rather than one per item: the host buffers them
    # and writes inside the completion transaction (DP-010), so batching changes nothing
    # about atomicity and keeps the interaction log readable.
    context.emit_result(results)
    context.log(
        "normalize.complete", {"results_emitted": len(results), "skipped": skipped}
    )
    return NormalizeOutcome(
        results_emitted=len(results),
        skipped=skipped,
        notes={"schema_version": SCHEMA_VERSION, "language": language},
    )


def _require_language(context: NormalizeContext) -> str:
    stated = context.config_field("language", DEFAULT_LANGUAGE)
    if not isinstance(stated, str) or not stated.strip():
        return DEFAULT_LANGUAGE
    return stated.strip()


def _parse(payload: bytes) -> dict[str, Any] | None:
    try:
        entry = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return entry if isinstance(entry, dict) else None


def _plain(value: object) -> str:
    """Markup out, entities decoded, and never `None`.

    `title` and `excerpt` are not nullable in Schema 0.1 — an empty string says the source
    gave nothing, which is a claim; `null` in a non-nullable field would be a defect.
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
