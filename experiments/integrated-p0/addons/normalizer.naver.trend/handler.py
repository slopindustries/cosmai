"""DataLab points into `Normalized Schema 0.2` trend records (DP-021 D2).

The input is what `collector.naver.searchtrend` and `collector.naver.shoppinginsight` both
emit: one Raw item per `(series, period)`, already unrolled from the response's nesting, of
the shape

    {"dimension", "title", "terms", "period", "ratio",
     "startDate", "endDate", "timeUnit", "device"?, "gender"?, "ages"?}

**It computes nothing, and that is the decision worth reading.** `[확인 사실]` The vendor
documents `ratio` as *"구간별 검색량의 상대적 비율"*, with the maximum in the window set to
100. `[추론]` So a ratio is only meaningful **inside its window**: two runs over different
windows produce numbers on different scales, and averaging, ranking, or differencing across
them is arithmetic in mixed units. This module therefore carries the number through
unchanged and puts the window in `notes`, so a later reader can see the scale rather than
having to assume one. DP-021 D3.

**An unknown dimension is skipped, not passed through.** DP-021 D2 enumerates three, and
its own falsification condition is a fourth arriving. Passing an unrecognised one into the
record would widen the enumeration silently and make that condition unobservable; skipping
it makes a run report `skipped > 0` and leaves the item in Raw to be looked at.

**A document item produces nothing.** A snapshot of blog Raw handed to this normalizer is
skipped item by item rather than mangled into records built from fields that were not
there. The operator sees a run with zero results, which is the honest answer to "you pointed
the wrong normalizer at this snapshot".
"""

from __future__ import annotations

import json
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome

SCHEMA_VERSION = "0.2"
RECORD_TYPE = "trend_point"
DEFAULT_LANGUAGE = "ko"

#: The three DP-021 D2 names. A fourth is that decision's falsification condition, so it is
#: refused here rather than absorbed.
DIMENSIONS = ("search_keyword", "shopping_category", "shopping_keyword")

TIME_UNITS = ("date", "week", "month")


def run(context: NormalizeContext) -> NormalizeOutcome:
    """One sealed snapshot of DataLab points in, one Schema 0.2 record per usable point."""
    language = _require_language(context)
    results: list[NormalizedResult] = []
    skipped = 0

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
        results.append(
            NormalizedResult(source_item_key=item.item_key, body=body, notes=notes)
        )

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
        point = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return point if isinstance(point, dict) else None


def _to_record(
    point: dict[str, Any], language: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The Schema 0.2 body and its notes, or `None` if this item is not a trend point.

    Every check here is a reason to skip rather than to fail: one unusable item must not
    lose the rest of the snapshot, and `NormalizeOutcome.skipped` exists to say how many
    there were.
    """
    dimension = point.get("dimension")
    if dimension not in DIMENSIONS:
        return None
    series = point.get("title")
    if not isinstance(series, str) or not series:
        return None
    period = point.get("period")
    if not isinstance(period, str) or not period:
        return None
    ratio = point.get("ratio")
    if isinstance(ratio, bool) or not isinstance(ratio, int | float):
        return None
    unit = point.get("timeUnit")
    if unit not in TIME_UNITS:
        return None

    body = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        # The same pair the collector used as `item_key`, so the record and its lineage
        # key say the same thing rather than two things that have to be kept in step.
        "external_id": f"{series}|{period}",
        "language": language,
        "series": series,
        "dimension": dimension,
        "terms": [str(term) for term in point.get("terms", [])],
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
    notes = {
        # The window the ratio is relative to. Without it the number has no scale.
        "start_date": point.get("startDate"),
        "end_date": point.get("endDate"),
    }
    return body, notes


def _optional(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _optional_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    return [str(item) for item in value]
