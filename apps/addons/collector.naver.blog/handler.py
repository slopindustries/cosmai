"""Collector for Naver API Hub's blog search — the first real (non-synthetic) collector.

Copy-adapted from ``experiments/integrated-p0/addons/collector.naver.blog/handler.py``
(M4 naver-blog worktree). Logic is unchanged; P0's own name and behavior is the
spec (the M2-M7 plan's controller ruling 3), and nothing in this add-on's contract
surface changed between ``addon_api`` 1.0 and the ``1.3`` this tree's ``addon_api``
implements — ``CollectContext.accept_status`` (1.2) is not needed here because every
non-200 status this handler sees already ends in a raise, never a return, so there is
no response left for which the platform's "decided or not" check would find nothing.

Endpoint shape from the vendor docs, fetched 2026-08-18:
  https://api.ncloud-docs.com/docs/naver-api-hub-search-blog (params, response, SE0x errors)
  https://guide.ncloud-docs.com/docs/apihub-overview (RPS limiting, quotas)
`[확인 사실]` Both pages document the request/response shape and the SE01-SE06/SE99/429 status
table used below. Neither page shows an actual captured response or error body — there is no
capture of this source yet, only its documentation — so three behaviors this add-on depends on
are undocumented and are marked `[가설]` at the point they matter, with the falsification
condition a real capture would need to check:

1. **What `start` past the end of the result pool returns.** `[가설]` Assumed: HTTP 200 with
   `items: []` (and `total`/`display`/`start` still present), not a missing `items` key and not
   an SE03/other error. Falsified by: a captured response at `start` beyond the pool that is not
   `200` with an `items` array. `_parse_page` below treats a 200 body without an `items` list as
   a **different** failure (malformed body, `AddonPermanent`) from the empty-page case, on
   purpose — so a real capture proves or disproves this specific claim rather than merging it
   with generic malformed-response handling.
2. **Whether `total` holds still across calls of the same query.** `[가설]` Assumed: no —
   `total` is a live count of a search index and can drift between two requests for the same
   `query`. Falsified by: two captures of the same `query`, same `sort`, taken a few seconds
   apart, returning different `total`. Because this is assumed rather than known, `total` is
   never used for loop control below; it is logged only. See `_ceiling_and_progress` cost this
   forces: an extra page is always fetched to confirm exhaustion.
3. **The shape of a 429 body, and whether `Retry-After` is present.** `[가설]` Assumed: neither
   is reliable. `_error_detail` reads `Retry-After` case-insensitively and best-effort parses an
   `errorCode`/`errorMessage` pair matching the SE0x shape shown for 4xx/5xx, but a 429 with
   neither is treated identically to one with both — the classification is `AddonTransient`
   purely from the status code. Falsified by: a captured 429 whose body or headers carry
   information this add-on should be using (e.g. a documented `Retry-After` this add-on should
   surface for the platform's backoff, instead of leaving backoff entirely to the platform).

`[확인 사실]` `start` is documented as capped at 1000 while `total` can run far higher. That is
a capability limit of this source, not a bug: this add-on cannot exhaustively collect a query
whose result count exceeds `1000 - display + 1` reachable rows, and it stops cleanly at the
ceiling (`_STOPPED_START_CEILING`) rather than looping or raising.

`needs_credential = true` plus two `secret = true` config fields (`client_id`, `client_secret`)
is a guess about how a two-part credential (`X-NCP-APIGW-API-KEY-ID` and `X-NCP-APIGW-API-KEY`)
is supposed to be declared. `addon_api.manifest.Declarations.needs_credential` is a single
boolean; nothing in `addon_api` says how — or whether — a declared secret config field is wired
to a specific outbound header name, or what happens when a source needs two. This add-on cannot
resolve that; DP-018 puts the two header/ref pairs on the source's outbound profile instead,
which is what a real registration (`experiments/integrated-p0/tests/test_naver_real_data.py`'s
own `registered` fixture) does.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from addon_api.context import CollectContext, FetchResponse
from addon_api.errors import AddonConfigInvalid, AddonPermanent, AddonTransient
from addon_api.results import CollectOutcome, RawItem

#: The name this add-on requests in [declares].endpoints; the platform maps it to the real path.
ENDPOINT = "blog"

DISPLAY_MIN, DISPLAY_MAX = 1, 100
DISPLAY_DEFAULT = 10
#: `[확인 사실]` documented hard ceiling on `start`, independent of `total`.
START_MAX = 1000
VALID_SORTS = frozenset({"sim", "date"})

_STOPPED_EMPTY_PAGE = "empty_page"
_STOPPED_START_CEILING = "start_ceiling"
_STOPPED_MAX_PAGES = "max_pages"


def run(context: CollectContext) -> CollectOutcome:
    """Page through blog search results for one configured query.

    Termination is driven only by an empty `items` array or the `start` ceiling — never by
    `total` (assumption 2 above). That means a query whose results fit on one page still costs
    two requests: one that returns the page, one that confirms the next page is empty. There is
    no cheaper way to be sure under assumption 2, and getting this wrong in the other direction
    is silent data loss, not a wasted call.
    """
    query = _require_query(context)
    display = _require_display(context)
    sort = _require_sort(context)
    start = _require_start(context.cursor)

    raw_items: list[RawItem] = []
    pages_fetched = 0
    last_total: int | None = None
    stopped_reason = _STOPPED_EMPTY_PAGE

    while True:
        if start > START_MAX:
            stopped_reason = _STOPPED_START_CEILING
            context.log(
                "collect.start_ceiling_reached",
                {"start": start, "last_observed_total": last_total},
            )
            break
        if pages_fetched >= context.limits.max_pages:
            stopped_reason = _STOPPED_MAX_PAGES
            break

        params: dict[str, str] = {"query": query, "display": str(display), "start": str(start)}
        if sort is not None:
            params["sort"] = sort

        response = context.fetch(ENDPOINT, params)
        pages_fetched += 1
        body = _parse_page(response)
        items = body["items"]
        last_total = _as_optional_int(body.get("total"))

        if not items:
            stopped_reason = _STOPPED_EMPTY_PAGE
            break

        page_items = [_to_raw_item(entry, response) for entry in items]
        raw_items.extend(page_items)
        context.emit_raw(page_items)

        start = start + display
        context.advance_cursor("items", start)
        context.log(
            "collect.page_fetched",
            {"start": start - display, "display": display, "returned": len(items),
             "total": last_total},
        )

    more_available = stopped_reason == _STOPPED_MAX_PAGES
    context.log(
        "collect.run_complete",
        {"items_emitted": len(raw_items), "pages_fetched": pages_fetched,
         "stopped_reason": stopped_reason},
    )
    return CollectOutcome(
        items_emitted=len(raw_items),
        more_available=more_available,
        notes={
            "stopped_reason": stopped_reason,
            "pages_fetched": pages_fetched,
            "last_observed_total": last_total,
            "next_start": start,
        },
    )


def _require_query(context: CollectContext) -> str:
    query = context.config_field("query")
    if not isinstance(query, str) or not query.strip():
        # The host validates `required = true` before this runs, but only for presence and
        # type, not for "non-empty" — an empty string is a valid `str`. Re-checked here for the
        # same reason the generated collector skeleton re-checks `base_path`.
        raise AddonConfigInvalid("query is not configured", {"source_id": context.source_id})
    return query


def _require_display(context: CollectContext) -> int:
    display = context.config_field("display", DISPLAY_DEFAULT)
    if isinstance(display, bool) or not isinstance(display, int) or not (
        DISPLAY_MIN <= display <= DISPLAY_MAX
    ):
        raise AddonConfigInvalid(
            f"display must be an integer between {DISPLAY_MIN} and {DISPLAY_MAX}",
            {"display": display},
        )
    return display


def _require_sort(context: CollectContext) -> str | None:
    sort = context.config_field("sort", None)
    if sort is None:
        return None
    if not isinstance(sort, str) or sort not in VALID_SORTS:
        raise AddonConfigInvalid(
            f"sort must be one of {sorted(VALID_SORTS)}", {"sort": sort}
        )
    return sort


def _require_start(cursor: Any) -> int:
    """The next `start` to request. Our own cursor shape: a bare int, nothing more."""
    if cursor is None:
        return 1
    if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 1:
        raise AddonPermanent(f"resume cursor is not a valid start position: {cursor!r}")
    return cursor


def _parse_page(response: FetchResponse) -> dict[str, Any]:
    """Classify `response` and return its parsed body, or raise the matching `AddonError`.

    Status-code classification only — no `errorCode` parsing decides the class, per assumption 3
    (the error body shape is not documented reliably enough to branch on).
    """
    status = response.status
    if status == 200:
        return _parse_ok_body(response)
    if status == 429:
        raise AddonTransient("blog search rate limit exceeded (429)", _error_detail(response))
    if status >= 500:
        raise AddonTransient(f"blog search returned {status}", _error_detail(response))
    if status in (401, 403):
        # Not documented for this endpoint specifically, but is the project's general mapping
        # for an auth rejection (see addon_api.errors.AddonConfigInvalid and the normalizer
        # README's identical note) — kept in case the gateway rejects the credential before the
        # blog-search error codes ever apply.
        raise AddonConfigInvalid(
            f"blog search rejected the configured credential ({status})", _error_detail(response)
        )
    # SE01 (bad request), SE02 (display out of range), SE03 (start out of range), SE04 (bad
    # sort), SE05 (404, bad endpoint), SE06 (bad encoding): all mapped to AddonPermanent. SE02
    # and SE04 are pre-validated locally (_require_display, _require_sort) and should not reach
    # here in practice; if they do, that is this add-on's own bug, and AddonConfigInvalid would
    # overstate what the operator can fix, since reconfiguring won't help a validation gap here.
    raise AddonPermanent(f"blog search rejected the request ({status})", _error_detail(response))


def _parse_ok_body(response: FetchResponse) -> dict[str, Any]:
    try:
        body = json.loads(response.body)
    except json.JSONDecodeError as error:
        raise AddonPermanent(
            "blog search returned 200 with a body that is not valid JSON",
            {"status": 200},
        ) from error
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise AddonPermanent(
            "blog search returned 200 without the documented `items` array — this falsifies "
            "assumption 1 in handler.py's module docstring (empty-but-present `items` past the "
            "end of the result pool)",
            {"status": 200, "body_keys": sorted(body) if isinstance(body, dict) else None},
        )
    return body


def _to_raw_item(entry: object, response: FetchResponse) -> RawItem:
    if not isinstance(entry, dict) or not isinstance(entry.get("link"), str) or not entry["link"]:
        raise AddonPermanent(
            "a blog search result is missing its documented `link` field",
            {"entry_keys": sorted(entry) if isinstance(entry, dict) else None},
        )
    return RawItem(
        # `link` is the natural identity for a blog post within this source: the API assigns no
        # other id, and a post's URL is stable across pages and re-runs.
        item_key=entry["link"],
        payload=json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        envelope_ref=response.envelope_ref,
    )


def _error_detail(response: FetchResponse) -> dict[str, Any]:
    detail: dict[str, Any] = {"status": response.status}
    retry_after = _header(response.headers, "retry-after")
    if retry_after is not None:
        detail["retry_after"] = retry_after
    try:
        parsed = json.loads(response.body)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        for key in ("errorCode", "errorMessage"):
            if key in parsed:
                detail[key] = parsed[key]
    return detail


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _as_optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
