"""DataLab points into `Normalized Schema 0.2` trend records (DP-021 D2), with DP-030 D2's
record-level fault tolerance.

The input is what `collector.naver.datalab` emits in any of its three modes: one Raw item
per `(series, period)`, already unrolled from the response's nesting, of the shape

    {"dimension", "title", "terms", "period", "ratio",
     "startDate", "endDate", "timeUnit", "device"?, "gender"?, "ages"?}

**It computes nothing, and that is the decision worth reading.** `[확인 사실]` The vendor
documents `ratio` as *"구간별 검색량의 상대적 비율"*, with the maximum in the window set to
100. `[추론]` So a ratio is only meaningful **inside its window**: two runs over different
windows produce numbers on different scales, and averaging, ranking, or differencing across
them is arithmetic in mixed units. This module therefore carries the number through
unchanged and puts the window in `notes`, so a later reader can see the scale rather than
having to assume one. DP-021 D3.

**Where the skip/fallback line is drawn — DP-030 D2, an implementer decision.**
[DP-030](../../../docs/decisions/DP-030-p1-normalization-scope.md) D2 makes record-level
fault tolerance a P1 requirement: on a record's normalization failure, substitute missing
values, write a `notes.normalize_error {field, reason}`, and continue — never drop a record
silently. `P1-INHERITED-DEFECTS.md` §1's repaired finding was specifically about an
*encoding* crash (a lone UTF-16 surrogate) aborting the whole run; that crash-level guard is
now `domain.store._safe_canonical_body` (M2, platform-level, defends every normalizer's
output regardless of what any one of them does). What is left for **this** add-on, named
explicitly in DP-030's "Required changes" ("each normalizer's fallback is M4 work"), is the
same philosophy applied one level up, inside the add-on's own field-by-field reading of a
point:

- **An item that does not even claim to be a DataLab point is still skipped, not
  fallback-substituted.** A snapshot of blog Raw (or anything else without a `dimension`
  key at all) handed to this normalizer produces nothing for that item — the honest answer
  to "you pointed the wrong normalizer at this snapshot", same as P0. Emitting a
  near-empty record built from fields that were never there would not be a "record failure
  with a missing value"; it would be inventing a record.
- **An item whose payload is not even JSON, or not an object, is skipped for the same
  reason** — there is no field to attribute a `normalize_error` to.
- **An item that does carry a `dimension` string is a DataLab-record candidate, and every
  other malformed or missing field on it now goes through the fallback, including
  `dimension` itself when its value is not one of the three DP-021 D2 names.** DP-021 D2's
  own concern — that an unrecognised dimension must stay *observable* rather than silently
  widening the enumeration — still holds under this design: the record's `dimension` field
  is written `null`, never the unrecognised value, and the offending field is named in
  `notes.normalize_error`. A reader who cares about schema growth greps
  `notes.normalize_error.field == "dimension"` instead of a bare `skipped` count — which is
  *more* specific than what P0 offered, not less. Only the **first** offending field is
  named (mirroring `domain.store._safe_canonical_body`'s own narrowing), but every invalid
  field is still substituted with `null` so the emitted record never carries an unchecked
  value forward.
- **A document item is skipped rather than mangled** stays true in the narrower sense above:
  it is the "no `dimension` key at all" case, not a change in behaviour from P0.

`results_emitted` counts every record emitted, including one whose `notes` carries
`normalize_error` — DP-030 D2 says a bad record is emitted with a note, not withheld. The
run's own aggregate of *how many* of those were flagged is `error_records` in
`NormalizeOutcome.notes`, alongside `skipped` for the (now narrower) truly-foreign-item
count. `addon_api`'s `NormalizeOutcome` has no dedicated error-record field, so this is
carried the same way `skipped` and `schema_version` already are: in `notes`.

**D1's normalization-time metadata needs nothing added here.** `[확인 사실]`
`cosmai.normalized_result` already carries `snapshot_id`, `addon_id`, `addon_version`, and
`created_at` as columns the host attaches when it writes the row — `NormalizeContext` does
not even expose this add-on's own id or version to it. D1's metadata-preservation
requirement is therefore already satisfied at the row the host writes, not something this
add-on can or should duplicate into every record's `notes`.
"""

from __future__ import annotations

import json
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome

SCHEMA_VERSION = "0.2"
RECORD_TYPE = "trend_point"
DEFAULT_LANGUAGE = "ko"

#: The three DP-021 D2 names. A fourth is that decision's falsification condition, and it is
#: still refused as a record *value* here (never written into `body["dimension"]`) — but,
#: per DP-030 D2, the record itself is now emitted with `dimension: null` and a
#: `normalize_error` note instead of being dropped. See this module's docstring.
DIMENSIONS = ("search_keyword", "shopping_category", "shopping_keyword")

TIME_UNITS = ("date", "week", "month")


def run(context: NormalizeContext) -> NormalizeOutcome:
    """One sealed snapshot of DataLab points in, one Schema 0.2 record per DataLab-shaped
    item — degraded with a fallback rather than dropped when a field cannot be trusted."""
    language = _require_language(context)
    results: list[NormalizedResult] = []
    skipped = 0
    error_records = 0

    for item in context.read_snapshot():
        point = _parse(item.payload)
        if point is None:
            skipped += 1
            continue
        record = _to_record(point, language)
        if record is None:
            skipped += 1
            continue
        body, notes = record
        if "normalize_error" in notes:
            error_records += 1
        results.append(NormalizedResult(source_item_key=item.item_key, body=body, notes=notes))

    context.emit_result(results)
    context.log(
        "normalize.complete",
        {"results_emitted": len(results), "skipped": skipped, "error_records": error_records},
    )
    return NormalizeOutcome(
        results_emitted=len(results),
        skipped=skipped,
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


def _parse(payload: bytes) -> dict[str, Any] | None:
    try:
        point = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return point if isinstance(point, dict) else None


def _to_record(
    point: dict[str, Any], language: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The Schema 0.2 body and its notes, or `None` when this item is not a DataLab point
    at all.

    `None` (skip) is reserved for an item that carries no `dimension` key at all — this
    normalizer's data selection, not a normalization failure (see the module docstring).
    Everything else that is wrong with a candidate item goes through the DP-030 D2 fallback:
    the first invalid field is named in `notes.normalize_error`, every invalid field is
    substituted with `None`, and a record is still returned.
    """
    raw_dimension = point.get("dimension")
    if not isinstance(raw_dimension, str) or not raw_dimension:
        return None

    error: tuple[str, str] | None = None

    def checked(field: str, value: object, ok: bool, reason: str) -> Any:
        nonlocal error
        if ok:
            return value
        if error is None:
            error = (field, reason)
        return None

    dimension = checked(
        "dimension",
        raw_dimension,
        raw_dimension in DIMENSIONS,
        f"{raw_dimension!r} is not one of {DIMENSIONS}",
    )
    series_raw = point.get("title")
    series = checked(
        "series",
        series_raw,
        isinstance(series_raw, str) and bool(series_raw),
        "missing or not a string",
    )
    period_raw = point.get("period")
    period = checked(
        "period",
        period_raw,
        isinstance(period_raw, str) and bool(period_raw),
        "missing or not a string",
    )
    ratio_raw = point.get("ratio")
    ratio_ok = isinstance(ratio_raw, int | float) and not isinstance(ratio_raw, bool)
    ratio = checked("ratio", ratio_raw, ratio_ok, "missing or not numeric")
    unit_raw = point.get("timeUnit")
    unit = checked(
        "time_unit", unit_raw, unit_raw in TIME_UNITS, f"{unit_raw!r} is not one of {TIME_UNITS}"
    )

    terms_raw = point.get("terms")
    terms = [str(term) for term in terms_raw] if isinstance(terms_raw, list) else []

    body = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        # The same pair the collector used as `item_key`, with a missing half rendered as
        # empty rather than as the literal text "None" — a substitution, not a display bug.
        "external_id": f"{series if series is not None else ''}|"
        f"{period if period is not None else ''}",
        "language": language,
        "series": series,
        "dimension": dimension,
        "terms": terms,
        "period": period,
        "time_unit": unit,
        # Carried, never computed. See this module's docstring.
        "ratio": ratio,
        # Always present, each part null when the request asked for no filter: a missing
        # key and "all devices" are different claims.
        "segment": {
            "device": _optional(point.get("device")),
            "gender": _optional(point.get("gender")),
            "ages": _optional_list(point.get("ages")),
        },
    }
    notes: dict[str, Any] = {
        # The window the ratio is relative to. Without it the number has no scale.
        "start_date": point.get("startDate"),
        "end_date": point.get("endDate"),
    }
    if error is not None:
        field, reason = error
        notes["normalize_error"] = {"field": field, "reason": reason}
    return body, notes


def _optional(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _optional_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    return [str(item) for item in value]
