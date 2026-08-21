"""One JSON object per line, from a file the operator approved, into Raw.

Copy-adapted verbatim from ``experiments/integrated-p0/addons/importer.local.jsonl/``
(M4). Nothing here changed: ``addon_api``'s ``ImportContext``/``RawItem``/``CollectOutcome``
shapes and DP-024's ``open_input`` grant are unchanged in this tree's rebuild, so this
add-on's logic and names are the P0 original, per the controller's Ruling 3.

**Why this add-on exists.** P0-B work package B1 asks for one REST source *and one dataset*,
and B4 asks for "malformed and partially invalid dataset rows" as a failure scenario. Those
rows have no other way into the system: `ImportContext` is the only context without `fetch`,
and until DP-024 nothing bound it.

**What it deliberately does not do.** It does not decide whether a row is *good*, only
whether it is a JSON object with the configured key. Judging content is normalization's,
and an importer that dropped rows for being uninteresting would be losing Raw the platform
promised to preserve.

`[가설]` One line is one record. False for a JSONL file with embedded newlines inside a
string — which is legal JSON but not legal JSONL — and the failure is visible: such a line
is counted as malformed rather than silently joined to its neighbour.
"""

from __future__ import annotations

import json
from typing import Any

from addon_api import AddonConfigInvalid, CollectOutcome, ImportContext, RawItem

#: The name this add-on opens. Declared in `addon.toml`; the operator's profile says which
#: file it is. There is no configuration field for a path, and that is the point.
INPUT = "rows"

#: Why a line was not emitted, as counts an operator can read back from the outcome.
_MALFORMED = "malformed_json"
_NOT_AN_OBJECT = "not_an_object"
_NO_KEY = "missing_key_field"


def run(context: ImportContext) -> CollectOutcome:
    key_field = _require_key_field(context)
    ceiling = _require_max_rows(context)

    opened = context.open_input(INPUT)

    items: list[RawItem] = []
    skipped = {_MALFORMED: 0, _NOT_AN_OBJECT: 0, _NO_KEY: 0}
    line_number = 0

    for line_number, raw_line in enumerate(opened.body.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if ceiling is not None and len(items) >= ceiling:
            break
        entry = _parse(line, skipped)
        if entry is None:
            continue
        key = entry.get(key_field)
        if key is None or key == "":
            skipped[_NO_KEY] += 1
            continue
        items.append(
            RawItem(
                item_key=str(key),
                # The line as it was read, not a re-serialization. A round trip through
                # `json.dumps` would reorder keys and normalize numbers, and Raw that
                # differs from the source bytes is not the losslessness this promised.
                payload=line,
                content_type="application/json",
                envelope_ref=opened.envelope_ref,
                notes={"line": line_number},
            )
        )

    context.emit_raw(items)
    if items:
        context.advance_cursor(INPUT, {"lines_read": line_number})

    context.log(
        "import.finished",
        {"emitted": len(items), "lines": line_number, **skipped},
    )
    return CollectOutcome(
        items_emitted=len(items),
        more_available=ceiling is not None and len(items) >= ceiling,
        notes={"lines_read": line_number, **skipped},
    )


def _parse(line: bytes, skipped: dict[str, int]) -> dict[str, Any] | None:
    try:
        entry = json.loads(line)
    except (ValueError, RecursionError):
        # ValueError covers json.JSONDecodeError and UnicodeDecodeError (both are
        # ValueError subclasses) as well as CPython's integer-string-conversion limit
        # (`ValueError: Exceeds the limit ... for integer string conversion`, not a
        # JSONDecodeError). RecursionError covers pathologically deep nesting. Both must
        # abstain rather than abort per DP-030 D2 — see B1 in REVIEW-M2-M7.md.
        skipped[_MALFORMED] += 1
        return None
    if not isinstance(entry, dict):
        # A JSON array or scalar per line is valid JSON and not a record. Counted rather
        # than raised: one bad line in a dataset is a partial-validity case, and refusing
        # the whole file would discard every good row with it.
        skipped[_NOT_AN_OBJECT] += 1
        return None
    return entry


def _require_key_field(context: ImportContext) -> str:
    value = context.config_field("key_field")
    if not isinstance(value, str) or not value:
        raise AddonConfigInvalid("key_field must be a non-empty string", {"key_field": value})
    return value


def _require_max_rows(context: ImportContext) -> int | None:
    value = context.config_field("max_rows")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AddonConfigInvalid("max_rows must be a positive integer", {"max_rows": value})
    return value
