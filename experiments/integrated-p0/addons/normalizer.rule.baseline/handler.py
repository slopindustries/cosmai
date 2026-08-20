"""`normalizer.rule.baseline` — deterministic rules over a sealed snapshot that judge.

TASK-004 exists because `project-state.md` §5's hypothesis 6 — *"a rule baseline can
expose schema and quality problems before ML or LLM providers are introduced"* — had no
add-on to test it: `normalizer.naver.blog` and `normalizer.naver.trend` **reshape**
(markup removal, date parsing, unit copying) and abstain silently on anything they cannot
place in Schema 0.1 or 0.2. Neither *reports* a violation; both simply produce nothing for
a bad item and move on. This add-on's whole job is the thing they do not do: for an item
that is structurally intact but wrong, say so, name the rule, name the field, say what was
expected and what was there.

**No product semantics.** DP-026 moved evidence cards, product/ingredient/topic identity,
and trend classification to P1. Every rule below is decidable from the record's own fields
(or one other field in the same record) without knowing what a sunscreen or a toner is —
the same discipline `normalizer.naver.blog`/`normalizer.naver.trend` already apply to
*reshaping*, applied here to *judging*.

**What "snapshot item" means here — the biggest open question this add-on found.**
TASK-004's own text says Schema 0.1 (blog documents) and Schema 0.2 (trend points) "are
the snapshot item shapes your rules operate over," which read literally means
`NormalizeContext.read_snapshot()` yields DP-019/DP-021's *output* envelope — a payload
already carrying `schema_version`, `record_type`, `external_id`, and so on.

`[가설]` This module assumes the opposite: that a snapshot for this add-on holds the same
**raw, vendor-shaped** JSON that `normalizer.naver.blog` and `normalizer.naver.trend`
already consume (blog: `title`/`link`/`description`/`bloggername`/`bloggerlink`/`postdate`;
trend: `dimension`/`title`/`terms`/`period`/`ratio`/`timeUnit`/`startDate`/`endDate`), not
their canonical output. Three things point that way and none of them is proof:

1. `POC-CONTRACT-0.1` §4 says a snapshot "materializes its members" from Raw, and DP-019 D5
   fixes that selection as "every `raw_item` of one source" — the input to normalization,
   never its output. §5 states Schema 0.2 is normalization's **product**. Nothing describes
   a mechanism for a snapshot to be sealed over `normalized_result` rows, and no such
   mechanism is exercised by any test this repository has.
2. `test_normalizer_naver_blog.py::an_item` and `test_normalizer_naver_trend.py::a_point`
   both build their `SnapshotItem` fixtures from vendor-shaped dicts, not from Schema
   0.1/0.2 bodies. If the packet's literal reading were what the host actually does, those
   two normalizers' own tests would be exercising the wrong input shape.
3. The strongest reason is structural rather than textual: `normalizer.naver.blog` already
   erases most of the defects this add-on exists to report. A raw `postdate` of `"20261301"`
   becomes `published_at: null` — the malformed *value* is gone, replaced by an honest
   absence, before anything downstream could see it. A missing `link` is skipped outright
   and never reaches a result at all. If rule-baseline read *that* normalizer's output, "an
   out-of-range value" and "a missing required field" would already have been silently
   converted into "an absent, in-range field" by the time this add-on saw the record —
   which would make TASK-004's Acceptance Criterion 1 unsatisfiable by construction. Reading
   the same raw shape `normalizer.naver.blog`/`normalizer.naver.trend` read is the only
   reading under which a rule can still catch what those two normalizers hide.

**Falsification.** A real platform run, or a later capture, in which
`NormalizeContext.read_snapshot()` for a source this add-on is pointed at yields a payload
that itself parses with `schema_version` and `record_type` keys (DP-019/DP-021's own field
names) rather than the vendor field names above, falsifies this assumption. If that is what
the host actually does, every rule in this file needs to be rewritten against the Schema
0.1/0.2 field names instead, and the classification step below (`_classify`) becomes
unnecessary — `record_type` would already say which kind a record is.
`tests/test_normalizer_rule_baseline.py::TestTheSnapshotShapeAssumption` encodes this: it
feeds a genuinely Schema-0.1-shaped payload through and asserts today's code treats it as
unclassifiable (skipped), naming exactly this assumption in the skip reason. If a real
capture shows the packet's literal reading was right, that test's *expectation* is what
should flip, and its own docstring says so.

**Two smaller `[가설]`s, both about a single vendor fact this add-on had no capture to
check:**

- `blog.invalid_postdate` treats a **missing** `postdate` key the same as a malformed one.
  `[가설]` This assumes the vendor's documented blog-search response always carries the key
  (as `normalizer.naver.blog`'s own docstring already assumes for the same field).
  Falsification: a real capture of a legitimate result that omits `postdate` entirely would
  show "missing" and "malformed" need different rules, since DP-019 D1 treats "the source
  gave no parseable date" (which reads as *malformed*, not *absent*) as the only reason
  `published_at` is null.
- `trend.ratio_out_of_range` treats `ratio < 0` as a violation. `[가설]` DP-021 D3 quotes the
  vendor only on the *maximum* ("구간별 검색량의 상대적 비율", window's maximum set to 100);
  it says nothing about a minimum. Falsification: a real DataLab capture or vendor
  documentation showing a negative `ratio` would falsify treating negative as wrong, and the
  lower bound should be dropped from this rule.

**A boundary judgment, not a documentation gap.** `record_kind` below (`"document"` or
`"trend_point"`) is this add-on's own structural classification of *which field population a
record matches* — it is not DP-019/DP-021's `record_type`, and deciding it requires no
knowledge of what a document or a trend point *means*, only which of two disjoint key sets
is present. I judged this is not the product semantics DP-026 excluded (evidence cards,
ingredient/topic identity, trend classification of *what is popular*) because it never reads
past field names. A second author reading only DP-026 might reasonably read the exclusion
more broadly; flagged here rather than argued away.

**Another documentation gap, unrelated to input shape.** `[addon].output_contract_version`
here is `"0.1"`, which is also DP-019's name for the blog document schema. Nothing in
`CONTRACT-ADDON@1.3` or `addon-authoring.md` says an output contract version must be unique
across add-ons — `normalized_result`'s natural key is `(snapshot_id, addon_id, addon_version,
output_contract_version, source_item_key)`, and `addon_id` alone already disambiguates two
"0.1"s belonging to different add-ons. But a reader of the table filtering only on
`output_contract_version = '0.1'` without also filtering on `addon_id` would silently mix two
unrelated shapes together, and no contract text warns about that. Recorded as a question
rather than resolved, since resolving it (bumping to some other string, or requiring
per-add-on namespacing) is a documentation or contract decision, not an implementation one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome

#: This add-on's own report schema version. Independent of DP-019's `0.1` and DP-021's
#: `0.2` — see the module docstring's note on the spelling collision with
#: `output_contract_version`.
RULE_REPORT_VERSION = "0.1"

RULE_BLOG_MISSING_LINK = "blog.missing_link"
RULE_BLOG_MISSING_CONTENT = "blog.missing_content"
RULE_BLOG_INVALID_POSTDATE = "blog.invalid_postdate"
RULE_BLOG_LINK_EQUALS_BLOGGERLINK = "blog.link_equals_bloggerlink"

RULE_TREND_MISSING_FIELD = "trend.missing_field"
RULE_TREND_UNKNOWN_DIMENSION = "trend.unknown_dimension"
RULE_TREND_UNKNOWN_TIME_UNIT = "trend.unknown_time_unit"
RULE_TREND_RATIO_INVALID = "trend.ratio_invalid"
RULE_TREND_RATIO_OUT_OF_RANGE = "trend.ratio_out_of_range"
RULE_TREND_PERIOD_OUTSIDE_WINDOW = "trend.period_outside_window"

#: DP-021 D2's three names. A fourth is that decision's own falsification condition, so an
#: unrecognised `dimension` is a finding here rather than silently accepted.
TREND_DIMENSIONS = ("search_keyword", "shopping_category", "shopping_keyword")

#: DP-021 D2's three names for `timeUnit`.
TREND_TIME_UNITS = ("date", "week", "month")

#: Keys that appear only in a DataLab point, never in a blog search result (per the vendor
#: shapes `normalizer.naver.trend` and `normalizer.naver.blog` already consume). `title` is
#: deliberately excluded from both marker sets below — a blog post and a DataLab series both
#: carry a field named `title`, so it cannot tell the two apart.
TREND_MARKER_KEYS = frozenset(
    {"dimension", "terms", "period", "ratio", "timeUnit", "startDate", "endDate"}
)

#: Keys that appear only in a blog search result, never in a DataLab point.
BLOG_MARKER_KEYS = frozenset({"link", "description", "bloggername", "bloggerlink", "postdate"})

_POSTDATE = re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})$")
_ISO_DATE = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})$")


def run(context: NormalizeContext) -> NormalizeOutcome:
    """One sealed snapshot in, one finding report per classifiable item out.

    Every classifiable item produces exactly one result, whether or not any rule fired —
    "checked and clean" and "checked and wrong" are both judgments; only "could not be
    checked at all" is an abstention. That third case is `skipped`, named in `notes`, and
    never silently dropped (Acceptance Criterion 4).
    """
    results: list[NormalizedResult] = []
    skipped = 0
    skip_reasons: dict[str, int] = {
        "payload_not_a_json_object": 0,
        "unclassifiable_record_kind": 0,
    }
    kind_counts = {"document": 0, "trend_point": 0}
    clean_count = 0
    dirty_count = 0

    for item in context.read_snapshot():
        record = _parse(item.payload)
        if record is None:
            skipped += 1
            skip_reasons["payload_not_a_json_object"] += 1
            continue

        kind = _classify(record)
        if kind is None:
            skipped += 1
            skip_reasons["unclassifiable_record_kind"] += 1
            continue

        findings = _check_blog(record) if kind == "document" else _check_trend(record)
        clean = not findings
        if clean:
            clean_count += 1
        else:
            dirty_count += 1
        kind_counts[kind] += 1

        results.append(
            NormalizedResult(
                source_item_key=item.item_key,
                body={
                    "rule_report_version": RULE_REPORT_VERSION,
                    "record_kind": kind,
                    "clean": clean,
                    "findings": findings,
                },
                notes={"rules_fired": [finding["rule"] for finding in findings]},
            )
        )

    context.emit_result(results)
    notes = {
        "rule_report_version": RULE_REPORT_VERSION,
        "documents_checked": kind_counts["document"],
        "trend_points_checked": kind_counts["trend_point"],
        "clean": clean_count,
        "with_findings": dirty_count,
        "skip_reasons": skip_reasons,
    }
    context.log(
        "normalize.complete",
        {"results_emitted": len(results), "skipped": skipped, **notes},
    )
    return NormalizeOutcome(results_emitted=len(results), skipped=skipped, notes=notes)


def _parse(payload: bytes) -> dict[str, Any] | None:
    try:
        record = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return record if isinstance(record, dict) else None


def _classify(record: Mapping[str, Any]) -> str | None:
    """Which rule set applies, decided from key names alone — never from a value's meaning.

    Ambiguous (both marker sets present) and unclassifiable (neither) are the same
    abstention: this rule cannot decide, so the item is `skipped` rather than guessed at
    under either rule set.
    """
    has_trend = not TREND_MARKER_KEYS.isdisjoint(record)
    has_blog = not BLOG_MARKER_KEYS.isdisjoint(record)
    if has_trend and not has_blog:
        return "trend_point"
    if has_blog and not has_trend:
        return "document"
    return None


def _finding(rule: str, field: str, expected: str, found: Any) -> dict[str, Any]:
    return {"rule": rule, "field": field, "expected": expected, "found": found}


def _check_blog(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Four rules, each decidable from this one record.

    - **missing_link** — a required field absent (Acceptance Criterion 1's first
      category). `link` is the identity and the lineage key `normalizer.naver.blog` itself
      relies on; a record without one is unusable by any downstream reader, not merely
      imperfect.
    - **missing_content** — a compound missing-field check. DP-019 D1 tolerates *one* of
      `title`/`description` being empty ("empty string if the source gave none"); both empty
      at once means the record carries no readable text at all, which is a different claim
      a single-field check cannot make.
    - **invalid_postdate** — an out-of-range/malformed value. `date(year, month, day)`
      raising `ValueError` catches a calendar-invalid date (`20260230`) that a naive
      1–31/1–12 range check would accept; `normalizer.naver.blog`'s own parser is the naive
      version, so this rule is strictly more discriminating than the normalizer whose input
      it shares.
    - **link_equals_bloggerlink** — a cross-field inconsistency. A specific post's URL
      cannot legitimately equal the blog's home page URL; if the source ever reported that,
      one of the two fields is wrong, and no single-field check would notice.
    """
    findings: list[dict[str, Any]] = []

    link = record.get("link")
    link_ok = isinstance(link, str) and bool(link.strip())
    if not link_ok:
        findings.append(
            _finding(
                RULE_BLOG_MISSING_LINK,
                "link",
                "a non-empty string identifying the post",
                link,
            )
        )

    title = record.get("title")
    description = record.get("description")
    title_blank = not isinstance(title, str) or not title.strip()
    description_blank = not isinstance(description, str) or not description.strip()
    if title_blank and description_blank:
        findings.append(
            _finding(
                RULE_BLOG_MISSING_CONTENT,
                "content",
                "at least one of title or description non-empty",
                {"title": title, "description": description},
            )
        )

    postdate = record.get("postdate")
    if not _is_valid_yyyymmdd(postdate):
        findings.append(
            _finding(
                RULE_BLOG_INVALID_POSTDATE,
                "postdate",
                "an 8-digit yyyymmdd date that exists on the calendar",
                postdate,
            )
        )

    bloggerlink = record.get("bloggerlink")
    bloggerlink_ok = isinstance(bloggerlink, str) and bool(bloggerlink.strip())
    if link_ok and bloggerlink_ok and link.strip() == bloggerlink.strip():  # type: ignore[union-attr]
        findings.append(
            _finding(
                RULE_BLOG_LINK_EQUALS_BLOGGERLINK,
                "bloggerlink",
                "different from `link` (a post is not the blog's home page)",
                {"link": link, "bloggerlink": bloggerlink},
            )
        )

    return findings


def _check_trend(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Six rules, each decidable from this one record.

    - **missing_field** — `dimension`, `title` (the series name), `period`, and `timeUnit`
      are never absent per DP-021 D2; `terms` is excluded because DP-021 D2 states it "may
      be empty" and `device`/`gender`/`ages` are excluded because DP-021 D2 makes them
      optional by design (null when the request asked for no filter).
    - **unknown_dimension** / **unknown_time_unit** — an enum violation: the value is
      present but is not one of DP-021 D2's fixed names. Fires only when the field is
      present at all, so it never doubles up with `missing_field` on the same defect.
    - **ratio_invalid** — present but not a number (or is a `bool`, which Python's `int`
      would otherwise accept).
    - **ratio_out_of_range** — numeric but outside `[0, 100]`. DP-021 D3 quotes the vendor's
      own documentation that the window's maximum is fixed at 100; see this module's
      `[가설]` on the lower bound.
    - **period_outside_window** — a cross-field consistency check across three fields:
      `period` must fall within `[startDate, endDate]`, the window `notes.start_date`/
      `notes.end_date` in `normalizer.naver.trend` already carries. It fires only when all
      three parse as valid calendar dates, so it never contradicts `missing_field` (which
      already covers an absent `period`) — a malformed or absent `startDate`/`endDate` alone
      is not itself a violation this rule set names, since neither field is in DP-021 D2's
      required set.
    """
    findings: list[dict[str, Any]] = []

    for field_name in ("dimension", "title", "period", "timeUnit"):
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                _finding(RULE_TREND_MISSING_FIELD, field_name, "a non-empty string", value)
            )

    dimension = record.get("dimension")
    if isinstance(dimension, str) and dimension.strip() and dimension not in TREND_DIMENSIONS:
        findings.append(
            _finding(
                RULE_TREND_UNKNOWN_DIMENSION,
                "dimension",
                f"one of {', '.join(TREND_DIMENSIONS)}",
                dimension,
            )
        )

    time_unit = record.get("timeUnit")
    if isinstance(time_unit, str) and time_unit.strip() and time_unit not in TREND_TIME_UNITS:
        findings.append(
            _finding(
                RULE_TREND_UNKNOWN_TIME_UNIT,
                "timeUnit",
                f"one of {', '.join(TREND_TIME_UNITS)}",
                time_unit,
            )
        )

    ratio = record.get("ratio")
    if isinstance(ratio, bool) or not isinstance(ratio, int | float):
        findings.append(_finding(RULE_TREND_RATIO_INVALID, "ratio", "a number", ratio))
    elif not (0 <= ratio <= 100):
        findings.append(
            _finding(
                RULE_TREND_RATIO_OUT_OF_RANGE,
                "ratio",
                "between 0 and 100 inclusive (DP-021 D3: the window's maximum is fixed at 100)",
                ratio,
            )
        )

    period = _parse_iso_date(record.get("period"))
    start = _parse_iso_date(record.get("startDate"))
    end = _parse_iso_date(record.get("endDate"))
    all_parsed = period is not None and start is not None and end is not None
    if all_parsed and not (start <= period <= end):  # type: ignore[operator]
        findings.append(
            _finding(
                RULE_TREND_PERIOD_OUTSIDE_WINDOW,
                "period",
                "within [startDate, endDate]",
                {
                    "period": record.get("period"),
                    "startDate": record.get("startDate"),
                    "endDate": record.get("endDate"),
                },
            )
        )

    return findings


def _is_valid_yyyymmdd(value: object) -> bool:
    if not isinstance(value, str):
        return False
    matched = _POSTDATE.match(value.strip())
    if matched is None:
        return False
    try:
        date(int(matched["y"]), int(matched["m"]), int(matched["d"]))
    except ValueError:
        return False
    return True


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    matched = _ISO_DATE.match(value.strip())
    if matched is None:
        return None
    try:
        return date(int(matched["y"]), int(matched["m"]), int(matched["d"]))
    except ValueError:
        return None
