"""NAVER DataLab: Search Trend + Shopping Insight, one window, one request per run.

`[확인 사실]` Three `POST` endpoints, documented at
https://api.ncloud-docs.com/docs/naver-api-hub-search-trend,
.../naver-api-hub-shopping-insight-categories, and
.../naver-api-hub-shopping-insight-keywords (fetched 2026-08-19, re-checked 2026-08-21). All
three answer the same nested shape:

    {"startDate", "endDate", "timeUnit",
     "results": [{"title", "keywords"|"category"|"keyword", "data": [{"period", "ratio"}]}]}

**Implementer choice: one add-on, three modes, not three add-ons.** Spec §5.3 leaves this
open ("datalab 계열 둘은 하나의 수집기로 합칠지 재구축 시 판단"). P0 already answered half of
it — `collector.naver.shoppinginsight` merged the categories and keywords endpoints behind a
`mode` field, on the grounds that they "answer the same question at two depths" and every
other field is shared. Search Trend answers a third, adjacent question (which *keywords* are
being searched, not which *shopping* categories or in-category keywords are being clicked)
with the exact same window/cursor/segment/unrolling machinery and only the body's shape and
the age-band vocabulary differing. `[추론]` Extending P0's own merge to the third endpoint
removes the second copy of that machinery rather than the first: the two P0 collectors were
already 90% identical (window resolution, cursor resume, device/gender/ages segmentation,
date arithmetic, response parsing, point unrolling), and the only per-mode facts are the
request body's shape, the endpoint name, the dimension name, and the age-band vocabulary —
all four of which are already table-driven data (`_MODES`), not duplicated logic. `[결정]`
Rejected: three separate add-ons (P0's shape, minus the merge P0 itself already made) — this
would restore the duplication P0's own shoppinginsight docstring already argued against, for
no benefit the merge does not already deliver. See this add-on's `README.md` for the fuller
account and `docs/superpowers/sdd/2026-08-21-m2-m7-batch/m4-naver-datalab-report.md` for the
decision record.

Four decisions carried forward from P0's two collectors, unchanged:

**The body is composed here, and nothing else about the request is.** DP-020 D2 makes a
request body the add-on's for the same reason a query string always was: it says *what is
being asked for*, not *where the request goes*. This module names no host, no path, no
header, and no credential — `fetch` takes an endpoint name and the platform does the rest.

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
a call that can only return an empty window still spends the 50,000-a-month Data Lab quota,
shared across all three modes.

`[가설]` Everything here is written against the documented shape; no capture of any of the
three endpoints existed when it was written. Falsified by a real response whose
`results[].data[]` is absent, whose `ratio` is not a number, or whose `title` is not the
group/category/keyword name that was asked for.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple

from addon_api.context import CollectContext, FetchResponse
from addon_api.errors import AddonConfigInvalid, AddonPermanent, AddonTransient
from addon_api.results import CollectOutcome, RawItem

TIME_UNITS = ("date", "week", "month")

DEVICES = ("pc", "mo")
GENDERS = ("m", "f")

#: `[확인 사실]` Search Trend numbers its age bands 1-11. The two Shopping Insight endpoints
#: use 10/20/30/40/50/60 for the same idea — a different vocabulary, not a subset, which is
#: why the two constants below are not one.
SEARCH_AGE_BANDS = tuple(str(n) for n in range(1, 12))
SHOPPING_AGE_BANDS = ("10", "20", "30", "40", "50", "60")

#: `[확인 사실]` Both documented maxima, checked locally so an operator sees which limit was
#: exceeded rather than a remote "incorrect query request" (`SE01`).
MAX_GROUPS = 5
MAX_GROUP_KEYWORDS = 20
MAX_CATEGORIES = 3
MAX_MODE_KEYWORDS = 5


class _Mode(NamedTuple):
    """What one `mode` value asks for: which endpoint, which dimension, which age vocabulary.

    A plain `NamedTuple` rather than `@dataclass` on purpose: `dataclasses._process_class`
    (checking every field for `dataclasses.KW_ONLY`) resolves a bare string annotation —
    which `from __future__ import annotations` makes every annotation here — through
    `sys.modules[cls.__module__]`. That lookup only succeeds for a module the loader
    registered in `sys.modules` before executing it. `addon_host`'s own loader does exactly
    that (`addon_host.loading._import_by_path`), but `addon_kit.harness._load_entry` — the
    conformance suite and `addon_kit run` — does not, and a bare `@dataclass` here raised
    `AttributeError: 'NoneType' object has no attribute '__dict__'` under that loader.
    `[측정]` found running this add-on through `addon_kit.conformance.run_conformance`.
    `NamedTuple` does not evaluate its field annotations at class-creation time, so it never
    reaches that code path."""

    endpoint: str
    dimension: str
    age_bands: tuple[str, ...]


#: `mode` to the endpoint name it asks for (`[declares].endpoints`), the dimension DP-021 D2
#: records for it, and its age-band vocabulary. The three names are this add-on's contract
#: with its own configuration, not anything the API names — `_selection` below is what maps
#: a mode to the request body its endpoint actually documents.
_MODES: dict[str, _Mode] = {
    "search_trend": _Mode("trend", "search_keyword", SEARCH_AGE_BANDS),
    "shopping_categories": _Mode("categories", "shopping_category", SHOPPING_AGE_BANDS),
    "shopping_keywords": _Mode("category_keywords", "shopping_keyword", SHOPPING_AGE_BANDS),
}


def run(context: CollectContext) -> CollectOutcome:
    """Collect one window of DataLab points, for whichever mode this source configures."""
    mode_name, mode = _require_mode(context)
    window = _require_window(context)
    if window is None:
        context.log(
            "collect.window_already_collected",
            {"reason": "cursor reached end_date", "mode": mode_name},
        )
        return CollectOutcome(
            items_emitted=0, notes={"stopped_reason": "nothing_to_collect", "mode": mode_name}
        )

    start, end, unit = window
    body: dict[str, Any] = {"startDate": start, "endDate": end, "timeUnit": unit}
    body.update(_selection(context, mode_name))
    body.update(_segment(context, mode.age_bands))

    response = context.fetch(
        mode.endpoint, {}, body=json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    parsed = _parse(response, mode_name)

    items = [
        _to_raw_item(series, point, parsed, response, mode.dimension)
        for series in parsed["results"]
        for point in series["data"]
    ]
    context.emit_raw(items)
    # Advanced even when the window was empty. Not advancing would make the next run ask
    # the same question and get the same nothing, forever.
    context.advance_cursor("window", {"last_end_date": end})
    context.log(
        "collect.window_complete",
        {
            "mode": mode_name,
            "start_date": start,
            "end_date": end,
            "time_unit": unit,
            "points": len(items),
        },
    )
    return CollectOutcome(
        items_emitted=len(items),
        notes={
            "mode": mode_name,
            "start_date": start,
            "end_date": end,
            "time_unit": unit,
            "series": len(parsed["results"]),
        },
    )


# ------------------------------------------------------------------ configuration


def _require_mode(context: CollectContext) -> tuple[str, _Mode]:
    mode_name = context.config_field("mode")
    if not isinstance(mode_name, str) or mode_name not in _MODES:
        raise AddonConfigInvalid(
            f"mode must be one of {', '.join(sorted(_MODES))}; this add-on implements no "
            "other DataLab breakdown",
            {"mode": mode_name},
        )
    return mode_name, _MODES[mode_name]


def _require_window(context: CollectContext) -> tuple[str, str, str] | None:
    """The window to ask for, or `None` when the cursor has already covered it."""
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


def _selection(context: CollectContext, mode_name: str) -> dict[str, Any]:
    """What this mode measures, in the shape its endpoint documents.

    The three bodies differ in exactly this: Search Trend takes an array of keyword groups;
    the categories endpoint takes an **array** of category pairs; the keywords endpoint
    takes one category **string** plus an array of keyword pairs. Getting these crossed
    produces an `SE01` and nothing more useful, so each is assembled by name here.
    """
    if mode_name == "search_trend":
        return {"keywordGroups": _require_groups(context)}

    if mode_name == "shopping_categories":
        categories = _require_pairs(
            context.config_field("categories"), "categories", MAX_CATEGORIES
        )
        return {"category": categories}

    # shopping_keywords
    category = context.config_field("category")
    if not isinstance(category, str) or not category.strip():
        raise AddonConfigInvalid(
            "shopping_keywords measures keywords within one category, and no category is "
            "configured",
            {"mode": "shopping_keywords"},
        )
    keywords = _require_pairs(context.config_field("keywords"), "keywords", MAX_MODE_KEYWORDS)
    for pair in keywords:
        if len(pair["param"]) != 1:
            raise AddonConfigInvalid(
                f"keyword {pair['name']!r} must carry exactly one term; this API accepts "
                "one per pair",
                {"keyword": pair["name"], "terms": len(pair["param"])},
            )
    return {"category": category.strip(), "keyword": keywords}


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
        if len(keywords) > MAX_GROUP_KEYWORDS:
            raise AddonConfigInvalid(
                f"group {name!r} lists {len(keywords)} keywords and this API accepts "
                f"{MAX_GROUP_KEYWORDS}",
                {"group": name, "keywords": len(keywords)},
            )
        read.append({"groupName": name, "keywords": [str(word) for word in keywords]})
    return read


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


def _segment(context: CollectContext, age_bands: tuple[str, ...]) -> dict[str, Any]:
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
        unknown = [band for band in bands if band not in age_bands]
        if unknown:
            raise AddonConfigInvalid(
                f"ages must be bands {', '.join(age_bands)} for this mode; got "
                f"{', '.join(unknown)}",
                {"unknown": unknown},
            )
        segment["ages"] = bands
    return segment


# ------------------------------------------------------------------- response


def _parse(response: FetchResponse, mode_name: str) -> dict[str, Any]:
    """Classify by status, then check the shape the documentation promises.

    Status only, as `collector.naver.blog` does and for the same reason: the error body's
    shape is not documented reliably enough to branch on.
    """
    if response.status == 429:
        raise AddonTransient(
            "Data Lab rate limit exceeded (429)", {"status": 429, "mode": mode_name}
        )
    if response.status >= 500:
        raise AddonTransient(
            f"DataLab ({mode_name}) returned {response.status}",
            {"status": response.status, "mode": mode_name},
        )
    if response.status in (401, 403):
        raise AddonConfigInvalid(
            f"DataLab ({mode_name}) rejected the configured credential ({response.status})",
            {"status": response.status, "mode": mode_name},
        )
    if response.status != 200:
        raise AddonPermanent(
            f"DataLab ({mode_name}) rejected the request ({response.status})",
            {"status": response.status, "mode": mode_name},
        )
    try:
        body = json.loads(response.body)
    except json.JSONDecodeError as error:
        raise AddonPermanent(
            f"DataLab ({mode_name}) returned 200 with a body that is not JSON"
        ) from error
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise AddonPermanent(
            f"DataLab ({mode_name}) returned 200 without the documented `results` array — "
            "this falsifies the response-shape assumption in this module's docstring",
            {"body_keys": sorted(body) if isinstance(body, dict) else None, "mode": mode_name},
        )
    for series in body["results"]:
        if not isinstance(series, dict) or not isinstance(series.get("data"), list):
            raise AddonPermanent(f"a DataLab ({mode_name}) series carries no `data` array")
    return body


def _to_raw_item(
    series: dict[str, Any],
    point: object,
    parsed: dict[str, Any],
    response: FetchResponse,
    dimension: str,
) -> RawItem:
    if not isinstance(point, dict) or not isinstance(point.get("period"), str):
        raise AddonPermanent("a DataLab point carries no `period`")
    ratio = point.get("ratio")
    if isinstance(ratio, bool) or not isinstance(ratio, int | float):
        raise AddonPermanent("a DataLab point carries no numeric `ratio`")
    title = series.get("title")
    if not isinstance(title, str) or not title:
        raise AddonPermanent("a DataLab series carries no `title`")
    # The response names its terms `keywords` (Search Trend), `category` (Shopping
    # Insight/categories), or `keyword` (Shopping Insight/keywords). All three mean "what
    # this series was built from", so all become `terms`, and which endpoint they came from
    # is already recorded as `dimension`.
    terms = series.get("keywords") or series.get("category") or series.get("keyword") or []
    payload = {
        "dimension": dimension,
        "title": title,
        "terms": [str(term) for term in terms],
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
    That is a contract gap worth naming rather than working around silently: several fields
    across this add-on's three modes now carry JSON in a string, and each one re-implements
    this check.
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
