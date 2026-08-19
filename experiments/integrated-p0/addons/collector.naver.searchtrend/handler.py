"""NAVER DataLab Search Trend: one window, one request, one item per point.

`[확인 사실]` `POST /search-trend/v1/search`, documented at
https://api.ncloud-docs.com/docs/naver-api-hub-search-trend (fetched 2026-08-19). The body
carries a date window, an interval, and up to five keyword groups of up to twenty keywords;
the response nests periods inside series:

    {"startDate", "endDate", "timeUnit",
     "results": [{"title", "keywords": [], "data": [{"period", "ratio"}]}]}

Four decisions are worth reading before the code.

**The body is composed here, and nothing else about the request is.** DP-020 D2 makes a
request body the add-on's for the same reason a query string always was: it says *what is
being asked for*, not *where the request goes*. This module names no host, no path, no
header, and no credential — `fetch` takes the endpoint name `trend` and the platform does
the rest.

**One item per `(series, period)`, not one per response.** DP-021 D4. The response nests,
`raw_item` is flat, and `source_item_key` is the lineage key a normalized record points back
to — so the nesting is unrolled here and the whole response is still preserved verbatim in
the Raw envelope, which the platform records before this add-on sees a byte.

**The window travels with every point.** `[확인 사실]` The vendor documents `ratio` as
*"구간별 검색량의 상대적 비율"* with the window's maximum set to 100. `[추론]` So a point
without its window is a number on an unknown scale, and two runs over different windows are
not comparable. Every item carries `startDate`, `endDate`, and `timeUnit` for that reason,
and this add-on does no arithmetic on `ratio` at all.

**The cursor is the last window's `endDate`.** A resumed run starts the day after it, so a
second run collects new intervals rather than the same ones. When the cursor has already
reached the configured end there is nothing to ask for, and the run makes **no request** —
a call that can only return an empty window still spends the 50,000-a-month Data Lab quota.

`[가설]` Everything here is written against the documented shape; no capture of this
endpoint existed when it was written. Falsified by a real response whose `results[].data[]`
is absent, whose `ratio` is not a number, or whose `title` is not the group name that was
asked for.
"""

from __future__ import annotations

import json
from typing import Any

from addon_api.context import CollectContext, FetchResponse
from addon_api.errors import AddonConfigInvalid, AddonPermanent, AddonTransient
from addon_api.results import CollectOutcome, RawItem

#: The name this add-on asks for in `[declares].endpoints`. The platform maps it to a path.
ENDPOINT = "trend"

#: What DP-021 D2 calls this dimension. A reader of one row has to know whether the ratio
#: counts searches, category clicks, or keyword clicks within a category.
DIMENSION = "search_keyword"

TIME_UNITS = ("date", "week", "month")

#: `[확인 사실]` Both documented, and checked here rather than remotely: an `SE01` says only
#: "incorrect query request", which is not something an operator can act on.
MAX_GROUPS = 5
MAX_KEYWORDS = 20

DEVICES = ("pc", "mo")
GENDERS = ("m", "f")

#: `[확인 사실]` Search Trend numbers its age bands 1-11. Shopping Insight uses 10/20/30/…
#: for the same idea, which is why neither add-on shares this constant with the other.
AGE_BANDS = tuple(str(n) for n in range(1, 12))


def run(context: CollectContext) -> CollectOutcome:
    """Collect one window of search-trend points."""
    window = _require_window(context)
    if window is None:
        context.log("collect.window_already_collected", {"reason": "cursor reached end_date"})
        return CollectOutcome(items_emitted=0, notes={"stopped_reason": "nothing_to_collect"})

    start, end, unit = window
    body: dict[str, Any] = {
        "startDate": start,
        "endDate": end,
        "timeUnit": unit,
        "keywordGroups": _require_groups(context),
    }
    body.update(_segment(context))

    response = context.fetch(
        ENDPOINT, {}, body=json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    parsed = _parse(response)

    items = [
        _to_raw_item(series, point, parsed, response)
        for series in parsed["results"]
        for point in series["data"]
    ]
    context.emit_raw(items)
    # Advanced even when the window was empty. Not advancing would make the next run ask
    # the same question and get the same nothing, forever.
    context.advance_cursor("window", {"last_end_date": end})
    context.log(
        "collect.window_complete",
        {"start_date": start, "end_date": end, "time_unit": unit, "points": len(items)},
    )
    return CollectOutcome(
        items_emitted=len(items),
        notes={"start_date": start, "end_date": end, "time_unit": unit,
               "series": len(parsed["results"])},
    )


# ------------------------------------------------------------------ configuration


def _require_window(context: CollectContext) -> tuple[str, str, str] | None:
    """The window to ask for, or `None` when the cursor has already covered it."""
    end = _require_date(context.config_field("end_date"), "end_date")
    unit = context.config_field("time_unit")
    if not isinstance(unit, str) or unit not in TIME_UNITS:
        raise AddonConfigInvalid(
            f"time_unit must be one of {', '.join(TIME_UNITS)}", {"time_unit": unit}
        )
    start = _resume_from(context) or _require_date(context.config_field("start_date"), "start_date")
    if start > end:
        if _resume_from(context) is not None:
            # A resumed run that has caught up. Ordinary, and not a configuration error.
            return None
        raise AddonConfigInvalid(
            "start_date is after end_date", {"start_date": start, "end_date": end}
        )
    return start, end, unit


def _resume_from(context: CollectContext) -> str | None:
    """The day after the last window's end, or `None` on a first run."""
    cursor = context.cursor
    if cursor is None:
        return None
    if not isinstance(cursor, dict) or not isinstance(cursor.get("last_end_date"), str):
        raise AddonPermanent(
            "the stored cursor is not a window this add-on wrote",
            {"cursor_type": type(cursor).__name__},
        )
    return _day_after(_require_date(cursor["last_end_date"], "cursor.last_end_date"))


def _require_groups(context: CollectContext) -> list[dict[str, Any]]:
    groups = _require_json_array(context.config_field("keyword_groups"), "keyword_groups")
    if not groups:
        raise AddonConfigInvalid("keyword_groups names no group", {"groups": 0})
    if len(groups) > MAX_GROUPS:
        raise AddonConfigInvalid(
            f"this API accepts at most {MAX_GROUPS} keyword groups and {len(groups)} were "
            "configured",
            {"groups": len(groups)},
        )
    read: list[dict[str, Any]] = []
    for group in groups:
        name = group.get("groupName")
        keywords = group.get("keywords")
        if not isinstance(name, str) or not name:
            raise AddonConfigInvalid("a keyword group has no groupName", {})
        if not isinstance(keywords, list) or not keywords:
            raise AddonConfigInvalid(f"group {name!r} lists no keywords", {"group": name})
        if len(keywords) > MAX_KEYWORDS:
            raise AddonConfigInvalid(
                f"group {name!r} lists {len(keywords)} keywords and this API accepts "
                f"{MAX_KEYWORDS}",
                {"group": name, "keywords": len(keywords)},
            )
        read.append({"groupName": name, "keywords": [str(word) for word in keywords]})
    return read


def _segment(context: CollectContext) -> dict[str, Any]:
    """The optional device/gender/ages filters, absent unless configured.

    Absent and empty are different requests: the API defaults each of these to "all", and
    sending an empty value asks something else.
    """
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
                f"ages must be bands {AGE_BANDS[0]}-{AGE_BANDS[-1]}; got {', '.join(unknown)}",
                {"unknown": unknown},
            )
        segment["ages"] = bands
    return segment


# ------------------------------------------------------------------- response


def _parse(response: FetchResponse) -> dict[str, Any]:
    """Classify by status, then check the shape the documentation promises.

    Status only, as `collector.naver.blog` does and for the same reason: the error body's
    shape is not documented reliably enough to branch on.
    """
    if response.status == 429:
        raise AddonTransient("Data Lab rate limit exceeded (429)", {"status": 429})
    if response.status >= 500:
        raise AddonTransient(
            f"search trend returned {response.status}", {"status": response.status}
        )
    if response.status in (401, 403):
        raise AddonConfigInvalid(
            f"search trend rejected the configured credential ({response.status})",
            {"status": response.status},
        )
    if response.status != 200:
        raise AddonPermanent(
            f"search trend rejected the request ({response.status})", {"status": response.status}
        )
    try:
        body = json.loads(response.body)
    except json.JSONDecodeError as error:
        raise AddonPermanent("search trend returned 200 with a body that is not JSON") from error
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise AddonPermanent(
            "search trend returned 200 without the documented `results` array — this "
            "falsifies the response-shape assumption in this module's docstring",
            {"body_keys": sorted(body) if isinstance(body, dict) else None},
        )
    for series in body["results"]:
        if not isinstance(series, dict) or not isinstance(series.get("data"), list):
            raise AddonPermanent("a search trend series carries no `data` array")
    return body


def _to_raw_item(
    series: dict[str, Any], point: object, parsed: dict[str, Any], response: FetchResponse
) -> RawItem:
    if not isinstance(point, dict) or not isinstance(point.get("period"), str):
        raise AddonPermanent("a search trend point carries no `period`")
    ratio = point.get("ratio")
    if isinstance(ratio, bool) or not isinstance(ratio, int | float):
        raise AddonPermanent("a search trend point carries no numeric `ratio`")
    title = series.get("title")
    if not isinstance(title, str) or not title:
        raise AddonPermanent("a search trend series carries no `title`")
    payload = {
        "dimension": DIMENSION,
        "title": title,
        "terms": [str(word) for word in series.get("keywords", [])],
        "period": point["period"],
        "ratio": ratio,
        # The window, on every point. See this module's docstring: `ratio` is relative to
        # it, so a point without it is a number on an unknown scale.
        "startDate": parsed.get("startDate"),
        "endDate": parsed.get("endDate"),
        "timeUnit": parsed.get("timeUnit"),
    }
    return RawItem(
        # DP-021 D4: one row per (series, period), and the key is that pair.
        item_key=f"{title}|{point['period']}",
        payload=json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        envelope_ref=response.envelope_ref,
    )


# ----------------------------------------------------------------------- dates


def _require_date(value: object, where: str) -> str:
    """`yyyy-mm-dd`, checked without importing anything.

    An add-on may import only `addon_api`, so the parsing is by hand. That is a real cost
    and it is small: the format is fixed and the failure it prevents — a window the API
    rejects with `SE01` — is one an operator cannot diagnose from the remote message.
    """
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise AddonConfigInvalid(f"{where} must be yyyy-mm-dd", {where: value})
    year, month, day = value[:4], value[5:7], value[8:]
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise AddonConfigInvalid(f"{where} must be yyyy-mm-dd", {where: value})
    if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        raise AddonConfigInvalid(f"{where} is not a date", {where: value})
    return value


#: Days per month, index 1-12. February is 29 on purpose: this arithmetic only has to
#: produce a start date the API accepts, and asking for 2026-02-29 costs one empty day
#: rather than a wrong window. Getting leap years right here would be a second calendar
#: implementation in an add-on that has no business owning one.
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
    """A JSON array of objects, out of a string field.

    `[config.field]` has no array type, so a structured value arrives as text. `[추론]`
    That is a contract gap worth naming rather than working around silently: three fields
    across two add-ons now carry JSON in a string, and each one re-implements this check.
    """
    if not isinstance(value, str) or not value.strip():
        raise AddonConfigInvalid(f"{where} is not configured", {where: value})
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise AddonConfigInvalid(f"{where} is not valid JSON", {where: "<unparseable>"}) from error
    if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
        raise AddonConfigInvalid(f"{where} must be a JSON array of objects", {})
    return parsed
