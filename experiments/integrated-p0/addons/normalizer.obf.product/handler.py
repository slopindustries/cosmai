"""Open Beauty Facts product rows into `Normalized Schema 0.3` `product` records (DP-028).

**Structural, and deliberately narrow.** One snapshot item becomes at most one `product`
record. DP-028 D3 fixes the five fields this add-on may carry — `external_id`, `display_name`,
`brands`, `observed_at`, `has_ingredients` — and D5 forbids the rest by name: no category, no
ingredient parsing, no brand resolution, no canonical product. `brands` is the source's own
tag list carried forward, not a resolved brand identity.

**Absence is the ordinary case, not the edge.** `[측정]` SRC-003 measured `product_name`
present in 19 of 36 sampled rows and `ingredients_text` in 12 of 36. A body shape that made
either field required would force this add-on to invent a value, which is the failure mode
DP-028's evidence section names by name. So every field but `code` abstains to `None` (or, for
`brands`, to an empty list) rather than guessing.

**What is skipped rather than emitted.** A row whose payload is not a JSON object, or whose
`code` is absent, non-string, or blank after trimming, produces no record and increments
`skipped`. `code` is the row's only stated identity (DP-028 D3: "never — a row without it is
`skipped` and counted") and there is nothing else this add-on could use as `external_id`.
`NormalizeOutcome` separates `skipped` from `results_emitted` because "this item produced
nothing" and "this item was never looked at" are different claims, and each skip is also named
in `NormalizeOutcome.notes["skipped_item_keys"]` and in a `normalize.skipped` log line.

`[가설]` Three readings this add-on had to choose without DP-028 saying so directly, each
falsifiable by a real capture or an owner ruling:

- **"Verbatim" for `display_name` means the stored string is exactly what the source sent** —
  no trimming, no markup handling — and trimming is used only to decide whether the field
  counts as *present*. Falsified by a real `product_name` whose leading or trailing
  whitespace the project decides must not survive into the record.
- **A blank-after-trim `code` is treated the same as an absent one**, mirroring the rule
  DP-028 states for `display_name` even though D3's `code` row only says "never" for the
  null case and does not mention blank strings. Falsified by an owner ruling that a
  whitespace-only `code` should be carried through as `external_id` rather than skipped.
- **"Non-numeric" for `observed_at` means anything other than a JSON `int` or `float`** — a
  numeric string does not convert. SRC-003 measured `last_modified_t` as a JSON number in
  every sampled row and never as a string. Falsified by a real capture carrying it as a
  string that the project decides should still convert.

See this add-on's test file for exhaustive per-field cases and where each `[가설]` above is
pinned as an assertion.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome

SCHEMA_VERSION = "0.3"
RECORD_TYPE = "product"
DEFAULT_LANGUAGE = "en"


def run(context: NormalizeContext) -> NormalizeOutcome:
    """One sealed snapshot of Open Beauty Facts rows in, one Schema 0.3 record per row
    that carries a usable `code`."""
    language = _require_language(context)
    results: list[NormalizedResult] = []
    skipped = 0
    skipped_item_keys: list[str] = []

    for item in context.read_snapshot():
        row = _parse(item.payload)
        if row is None:
            skipped += 1
            skipped_item_keys.append(item.item_key)
            context.log(
                "normalize.skipped",
                {"item_key": item.item_key, "reason": "payload is not a JSON object"},
            )
            continue

        external_id = _external_id(row.get("code"))
        if external_id is None:
            skipped += 1
            skipped_item_keys.append(item.item_key)
            context.log(
                "normalize.skipped",
                {"item_key": item.item_key, "reason": "no usable code"},
            )
            continue

        results.append(
            NormalizedResult(
                source_item_key=item.item_key,
                body={
                    "schema_version": SCHEMA_VERSION,
                    "record_type": RECORD_TYPE,
                    "external_id": external_id,
                    "language": language,
                    "display_name": _display_name(row.get("product_name")),
                    "brands": _brands(row.get("brands_tags")),
                    "observed_at": _observed_at(row.get("last_modified_t")),
                    "has_ingredients": _has_ingredients(row.get("ingredients_text")),
                },
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
        notes={
            "schema_version": SCHEMA_VERSION,
            "language": language,
            "skipped_item_keys": tuple(skipped_item_keys),
        },
    )


def _require_language(context: NormalizeContext) -> str:
    stated = context.config_field("language", DEFAULT_LANGUAGE)
    if not isinstance(stated, str) or not stated.strip():
        return DEFAULT_LANGUAGE
    return stated.strip()


def _parse(payload: bytes) -> dict[str, Any] | None:
    try:
        row = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return row if isinstance(row, dict) else None


def _external_id(value: object) -> str | None:
    """`code` is the row's only stated identity. Absent, non-string, or blank is unusable.

    Stored verbatim (not trimmed) once it passes the presence check, for the same reason
    `_display_name` stores its value verbatim: trimming decides presence, not content.
    """
    if not isinstance(value, str):
        return None
    return value if value.strip() else None


def _display_name(value: object) -> str | None:
    """`product_name`, verbatim, or `None` when the source omits it or it is blank.

    See this module's docstring for the `[가설]` this reading of "verbatim" rests on.
    """
    if not isinstance(value, str):
        return None
    return value if value.strip() else None


def _brands(value: object) -> list[str]:
    """`brands_tags`, the source's own order, never `None` — `[]` when the source has none.

    Every entry is coerced to `str` defensively; DP-028 D5 forbids resolving a brand, and
    coercing a stray non-string entry is not resolution, it is carrying the list through in
    a shape every reader can rely on.
    """
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in value]


def _observed_at(value: object) -> str | None:
    """`last_modified_t`, Unix seconds to ISO-8601 UTC; `None` when omitted or non-numeric.

    `bool` is excluded even though it is an `int` subtype in Python — a timestamp of `True`
    would be a defect wearing the type checker's blind spot, not a real observation.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        moment = datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_ingredients(value: object) -> bool:
    """Presence, not quality (DP-028 D4): `True` only when `ingredients_text` is a
    non-blank string. Never `None` — the field always states one of two facts."""
    return isinstance(value, str) and bool(value.strip())
