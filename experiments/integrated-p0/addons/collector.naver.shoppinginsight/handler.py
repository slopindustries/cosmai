"""NAVER DataLab Shopping Insight: category or keyword click trend, one window at a time.

`[확인 사실]` Two `POST` endpoints, documented at
https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-categories and
.../naver-api-hub-shopping-insight-keywords (fetched 2026-08-19):

    categories         /shopping/v1/categories         "category": [{name, param[]}]  max 3
    category_keywords  /shopping/v1/category/keywords   "category": "<cat_id>"
                                                        "keyword":  [{name, param[1]}] max 5

Both answer with the same nested shape Search Trend uses — `results[].data[]` of
`{period, ratio}` — which is why the two add-ons look alike and why one normalizer reads
both.

**One add-on, two endpoints, chosen by `mode`.** They answer the same question at two
depths: which categories are being clicked, and which keywords within one category. Two
add-ons would duplicate every field and every check for one difference in the body. The
operator's profile still has to grant whichever endpoint the mode names, so a source
configured for a mode it was not granted is refused by the outbound guard rather than here.

**The age bands are not Search Trend's.** `[확인 사실]` This API documents `10, 20, 30, 40,
50, 60` while Search Trend documents `1`–`11` for the same idea. The two constants are not
shared between the add-ons for that reason: one vocabulary borrowed into the other would be
a request the API rejects with a message nobody can act on.

Everything else — the window, the cursor, the unrolling, and the refusal to interpret
`ratio` — is `collector.naver.searchtrend`'s, and its module docstring gives the reasoning
for each. `[결정]` The two are **not** factored into a shared module: an add-on may import
`addon_api` and nothing else in this project, which is DP-008 D1 and what
`tests/environment/test_addon_layer_direction.py` enforces. `[추론]` The duplication is
about eighty lines and is the price of that rule; if a third DataLab add-on appears, the
right response is a generator or a documented template, not an import.

`[가설]` Written against the documented shape; no capture existed. Falsified by a real
response whose `results[].data[]` is absent or whose `title` is not the configured name.
"""

from __future__ import annotations

import json
from typing import Any

from addon_api.context import CollectContext, FetchResponse
from addon_api.errors import AddonConfigInvalid, AddonPermanent, AddonTransient
from addon_api.results import CollectOutcome, RawItem

#: `mode` to the endpoint name it asks for, and the dimension DP-021 D2 records for it.
MODES: dict[str, tuple[str, str]] = {
    "categories": ("categories", "shopping_category"),
    "keywords": ("category_keywords", "shopping_keyword"),
}

TIME_UNITS = ("date", "week", "month")

#: `[확인 사실]` Both documented maxima, checked locally so an operator sees which limit was
#: exceeded rather than a remote "incorrect query request".
MAX_CATEGORIES = 3
MAX_KEYWORDS = 5

DEVICES = ("pc", "mo")
GENDERS = ("m", "f")

#: `[확인 사실]` This API's bands. Search Trend's are 1-11; see the module docstring.
AGE_BANDS = ("10", "20", "30", "40", "50", "60")


def run(context: CollectContext) -> CollectOutcome:
    """Collect one window of shopping-insight points."""
    endpoint, dimension = _require_mode(context)
    window = _require_window(context)
    if window is None:
        context.log("collect.window_already_collected", {"reason": "cursor reached end_date"})
        return CollectOutcome(items_emitted=0, notes={"stopped_reason": "nothing_to_collect"})

    start, end, unit = window
    body: dict[str, Any] = {"startDate": start, "endDate": end, "timeUnit": unit}
    body.update(_selection(context, endpoint))
    body.update(_segment(context))

    response = context.fetch(
        endpoint, {}, body=json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    parsed = _parse(response)

    items = [
        _to_raw_item(series, point, parsed, response, dimension)
        for series in parsed["results"]
        for point in series["data"]
    ]
    context.emit_raw(items)
    context.advance_cursor("window", {"last_end_date": end})
    context.log(
        "collect.window_complete",
        {"start_date": start, "end_date": end, "time_unit": unit,
         "dimension": dimension, "points": len(items)},
    )
    return CollectOutcome(
        items_emitted=len(items),
        notes={"start_date": start, "end_date": end, "time_unit": unit,
               "dimension": dimension, "series": len(parsed["results"])},
    )


# ------------------------------------------------------------------ configuration


def _require_mode(context: CollectContext) -> tuple[str, str]:
    mode = context.config_field("mode")
    if not isinstance(mode, str) or mode not in MODES:
        raise AddonConfigInvalid(
            f"mode must be one of {', '.join(sorted(MODES))}; this add-on implements no "
            "other Shopping Insight breakdown",
            {"mode": mode},
        )
    return MODES[mode]


def _selection(context: CollectContext, endpoint: str) -> dict[str, Any]:
    """What this mode measures, in the shape its endpoint documents.

    The two bodies differ in exactly this: the categories endpoint takes an **array** of
    category pairs, and the keywords endpoint takes one category **string** plus an array
    of keyword pairs. Getting the two crossed produces an `SE01` and nothing more useful,
    so each is assembled by name here.
    """
    if endpoint == "categories":
        categories = _require_pairs(
            context.config_field("categories"), "categories", MAX_CATEGORIES
        )
        return {"category": categories}

    category = context.config_field("category")
    if not isinstance(category, str) or not category.strip():
        raise AddonConfigInvalid(
            "keywords mode measures keywords within one category, and no category is "
            "configured",
            {"mode": "keywords"},
        )
    keywords = _require_pairs(context.config_field("keywords"), "keywords", MAX_KEYWORDS)
    for pair in keywords:
        if len(pair["param"]) != 1:
            raise AddonConfigInvalid(
                f"keyword {pair['name']!r} must carry exactly one term; this API accepts "
                "one per pair",
                {"keyword": pair["name"], "terms": len(pair["param"])},
            )
    return {"category": category.strip(), "keyword": keywords}


def _require_pairs(value: object, where: str, limit: int) -> list[dict[str, Any]]:
    parsed = _require_json_array(value, where)
    if not parsed:
        raise AddonConfigInvalid(f"{where} names nothing", {where: 0})
    if len(parsed) > limit:
        raise AddonConfigInvalid(
            f"this API accepts at most {limit} {where} and {len(parsed)} were configured",
            {where: len(parsed)},
        )
    pairs: list[dict[str, Any]] = []
    for entry in parsed:
        name = entry.get("name")
        param = entry.get("param")
        if not isinstance(name, str) or not name:
            raise AddonConfigInvalid(f"an entry in {where} has no name", {})
        if not isinstance(param, list) or not param:
            raise AddonConfigInvalid(f"{name!r} in {where} lists no param", {"name": name})
        pairs.append({"name": name, "param": [str(item) for item in param]})
    return pairs


def _require_window(context: CollectContext) -> tuple[str, str, str] | None:
    end = _require_date(context.config_field("end_date"), "end_date")
    unit = context.config_field("time_unit")
    if not isinstance(unit, str) or unit not in TIME_UNITS:
        raise AddonConfigInvalid(
            f"time_unit must be one of {', '.join(TIME_UNITS)}", {"time_unit": unit}
        )
    resumed = _resume_from(context)
    start = resumed or _require_date(context.config_field("start_date"), "start_date")
    if start > end:
        if resumed is not None:
            return None
        raise AddonConfigInvalid(
            "start_date is after end_date", {"start_date": start, "end_date": end}
        )
    return start, end, unit


def _resume_from(context: CollectContext) -> str | None:
    cursor = context.cursor
    if cursor is None:
        return None
    if not isinstance(cursor, dict) or not isinstance(cursor.get("last_end_date"), str):
        raise AddonPermanent(
            "the stored cursor is not a window this add-on wrote",
            {"cursor_type": type(cursor).__name__},
        )
    return _day_after(_require_date(cursor["last_end_date"], "cursor.last_end_date"))


def _segment(context: CollectContext) -> dict[str, Any]:
    segment: dict[str, Any] = {}
    device = context.config_field("device")
    if isinstance(device, str) and device:
        if device not in DEVICES:
            raise AddonConfigInvalid(
                f"device must be one of {', '.join(DEVICES)}", {"device": device}
            )
        segment["device"] = device
    gender = context.config_field("gender")
    if isinstance(gender, str) and gender:
        if gender not in GENDERS:
            raise AddonConfigInvalid(
                f"gender must be one of {', '.join(GENDERS)}", {"gender": gender}
            )
        segment["gender"] = gender
    ages = context.config_field("ages")
    if isinstance(ages, str) and ages.strip():
        bands = [band.strip() for band in ages.split(",") if band.strip()]
        unknown = [band for band in bands if band not in AGE_BANDS]
        if unknown:
            raise AddonConfigInvalid(
                f"ages must be bands {', '.join(AGE_BANDS)} for this API; got "
                f"{', '.join(unknown)}",
                {"unknown": unknown},
            )
        segment["ages"] = bands
    return segment


# ------------------------------------------------------------------- response


def _parse(response: FetchResponse) -> dict[str, Any]:
    if response.status == 429:
        raise AddonTransient("Data Lab rate limit exceeded (429)", {"status": 429})
    if response.status >= 500:
        raise AddonTransient(
            f"shopping insight returned {response.status}", {"status": response.status}
        )
    if response.status in (401, 403):
        raise AddonConfigInvalid(
            f"shopping insight rejected the configured credential ({response.status})",
            {"status": response.status},
        )
    if response.status != 200:
        raise AddonPermanent(
            f"shopping insight rejected the request ({response.status})",
            {"status": response.status},
        )
    try:
        body = json.loads(response.body)
    except json.JSONDecodeError as error:
        raise AddonPermanent(
            "shopping insight returned 200 with a body that is not JSON"
        ) from error
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise AddonPermanent(
            "shopping insight returned 200 without the documented `results` array — this "
            "falsifies the response-shape assumption in this module's docstring",
            {"body_keys": sorted(body) if isinstance(body, dict) else None},
        )
    for series in body["results"]:
        if not isinstance(series, dict) or not isinstance(series.get("data"), list):
            raise AddonPermanent("a shopping insight series carries no `data` array")
    return body


def _to_raw_item(
    series: dict[str, Any],
    point: object,
    parsed: dict[str, Any],
    response: FetchResponse,
    dimension: str,
) -> RawItem:
    if not isinstance(point, dict) or not isinstance(point.get("period"), str):
        raise AddonPermanent("a shopping insight point carries no `period`")
    ratio = point.get("ratio")
    if isinstance(ratio, bool) or not isinstance(ratio, int | float):
        raise AddonPermanent("a shopping insight point carries no numeric `ratio`")
    title = series.get("title")
    if not isinstance(title, str) or not title:
        raise AddonPermanent("a shopping insight series carries no `title`")
    # The response names its terms `category` in one endpoint and `keyword` in the other.
    # Both mean "what this series was built from", so both become `terms` and the endpoint
    # they came from is already recorded as `dimension`.
    terms = series.get("category") or series.get("keyword") or []
    payload = {
        "dimension": dimension,
        "title": title,
        "terms": [str(term) for term in terms],
        "period": point["period"],
        "ratio": ratio,
        "startDate": parsed.get("startDate"),
        "endDate": parsed.get("endDate"),
        "timeUnit": parsed.get("timeUnit"),
    }
    return RawItem(
        item_key=f"{title}|{point['period']}",
        payload=json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        envelope_ref=response.envelope_ref,
    )


# ----------------------------------------------------------------------- dates


def _require_date(value: object, where: str) -> str:
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise AddonConfigInvalid(f"{where} must be yyyy-mm-dd", {where: value})
    year, month, day = value[:4], value[5:7], value[8:]
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise AddonConfigInvalid(f"{where} must be yyyy-mm-dd", {where: value})
    if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        raise AddonConfigInvalid(f"{where} is not a date", {where: value})
    return value


#: See `collector.naver.searchtrend`: February is 29 on purpose, because this arithmetic
#: only has to produce a start date the API accepts.
_MONTH_LENGTH = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _day_after(date: str) -> str:
    year, month, day = int(date[:4]), int(date[5:7]), int(date[8:])
    day += 1
    if day > _MONTH_LENGTH[month]:
        day, month = 1, month + 1
    if month > 12:
        month, year = 1, year + 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _require_json_array(value: object, where: str) -> list[dict[str, Any]]:
    if not isinstance(value, str) or not value.strip():
        raise AddonConfigInvalid(f"{where} is not configured", {where: value})
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise AddonConfigInvalid(f"{where} is not valid JSON", {where: "<unparseable>"}) from error
    if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
        raise AddonConfigInvalid(f"{where} must be a JSON array of objects", {})
    return parsed
