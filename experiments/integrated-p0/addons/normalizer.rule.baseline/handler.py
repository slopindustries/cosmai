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

**Why `clean` is narrower than "no rule fired" (TASK-006, F2).** A rule whose input it
cannot read reaches no verdict, and the first version of this module reported such a record
as `clean: true` with an empty `findings` list — a claim about *coverage* that nothing had
established. `clean` now means **every rule applicable to this record kind ran, and none
fired**. A record with no findings but an unread rule is not clean; it is not judged wrong
either, and the two are distinguished by `findings` being empty while `rules_not_evaluated`
is not.

**What `_coverage` actually checks, and the gap it does not close (TASK-009, correcting
TASK-006's F2 text).** `[확인 사실]` `rules_evaluated` is computed by *subtraction* —
`RULES_BY_KIND[record_kind]` minus the rules named in `rules_not_evaluated` — not by
observing that a rule ran. `_coverage` raises `AddonOutputInvalid` when a rule name outside
this kind's set fired or abstained (a rule was added and the set was not updated), or when
one rule both fired and abstained (a checker gave the same rule a verdict and an abstention
at once). It does **not** raise, and cannot by construction, when a rule declared in
`RULES_BY_KIND` reaches no verdict and appends nothing to either list: subtracting an empty
`not_evaluated` entry for it leaves it in `rules_evaluated`, and the record can be emitted
`clean: true` without that rule having run. `[추론]` Today's ten rules are each *decided* on
every input this module classifies — not measured against every input, but structural:
`_check_blog` and `_check_trend` are straight-line functions with no early return, so every
checker's **condition is evaluated** on every record they see. A rule whose condition does
not hold is decided as passing, and a decision of "passing" is what records nothing in
either list — not an unevaluated rule skipping the append, but an evaluated one with nothing
to report. A rule whose condition does hold either appends a finding or an abstention. So a
name sitting in `rules_evaluated` because it passed and a name sitting there because it
never ran are byte-identical in the emitted body; that is a property of the ten checkers as
written, not something `_coverage` enforces. The only thing standing between a future rule
missing its abstention
branch and a wrong `clean: true` is review — the same distinction `AGENTS.md` draws between
a convention and a control.

`[결정]` The report shape changed while `rule_report_version` and
`[addon].output_contract_version` both stayed `"0.1"`. No run has ever written a
`normalized_result` row for this add-on, so nothing exists to be misread; and whether a
report-shape change owes a version bump is exactly the question TASK-004's review left open
about `output_contract_version` having no defining artefact and no validator. Bumping the
string here would answer that question by implementation, which is not this task's to do.

**Five of these ten rules cannot fire on anything either NAVER collector produces, and that
is the first line working rather than a defect (TASK-006, F4).** `[확인 사실]`
`collector.naver.blog` raises `AddonPermanent` on an absent or empty `link`; both trend
collectors set `dimension` from a module constant or a validated mode, and refuse a
non-numeric `ratio` and an empty `title`. So `blog.missing_link`,
`trend.missing_field` (for `dimension` and `title`), `trend.unknown_dimension`, and
`trend.ratio_invalid` are unreachable from those collectors *by construction*.
`[추론]` That is what a second line looks like: each of those five names a condition the
collector currently refuses to pass on, so their silence on real data is evidence the
collector's own guard held — and if a collector were relaxed, retired, or replaced by an
importer feeding the same source (`importer.local.jsonl` already can), these rules are what
would notice. `[결정]` The owner decided on 2026-08-20 that hypothesis 6 closes on fixture
evidence with this reason recorded, and that no rule is added so that something fires on
real data: a rule chosen for its firing rate optimises for the appearance of evidence.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from addon_api.context import NormalizeContext
from addon_api.errors import AddonOutputInvalid
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

#: Every rule that applies to a record of each kind — the set `clean: true` claims ran.
#: `_coverage` refuses to emit a body whose fired-or-abstained rules name something outside
#: this set, or name one rule in both lists. `[측정]` It does not refuse a body where a rule
#: in this set reaches neither list — that rule is subtracted into `rules_evaluated` as if
#: it had run. See the module docstring's "What `_coverage` actually checks" for what is and
#: is not caught (TASK-009).
BLOG_RULES = (
    RULE_BLOG_MISSING_LINK,
    RULE_BLOG_MISSING_CONTENT,
    RULE_BLOG_INVALID_POSTDATE,
    RULE_BLOG_LINK_EQUALS_BLOGGERLINK,
)
TREND_RULES = (
    RULE_TREND_MISSING_FIELD,
    RULE_TREND_UNKNOWN_DIMENSION,
    RULE_TREND_UNKNOWN_TIME_UNIT,
    RULE_TREND_RATIO_INVALID,
    RULE_TREND_RATIO_OUT_OF_RANGE,
    RULE_TREND_PERIOD_OUTSIDE_WINDOW,
)
RULES_BY_KIND = {"document": BLOG_RULES, "trend_point": TREND_RULES}

#: Why a rule reached no verdict. Fixed prose, never the offending value: an abstention is
#: a statement about this rule's own reach, and the value is already the finding's job.
ABSTAIN_LINK_PAIR_INCOMPLETE = (
    "one of link or bloggerlink is absent, blank, or not a string, so the two cannot be "
    "compared"
)
ABSTAIN_NO_NAME_TO_ADMIT = (
    "the field is absent, blank, or not a string, so there is no value to check against the "
    "admitted names"
)
ABSTAIN_RATIO_NOT_A_NUMBER = "ratio is not a number, so it cannot be placed in a range"
ABSTAIN_WINDOW_UNPARSEABLE = (
    "period, startDate, or endDate is not a parseable calendar date, so the window cannot "
    "be applied — neither startDate nor endDate is required by DP-021 D2, so their absence "
    "is not itself a violation this rule set names"
)

#: How much of an offending value a finding may echo. A finding exists to name what was
#: there, not to copy it: `found` is persisted into `normalized_result.body`, and the value
#: it echoes is untrusted Raw that nothing upstream bounded — a 200 KB field otherwise
#: becomes a 200 KB row (TASK-006, F11).
FOUND_MAX_TEXT = 200
FOUND_MAX_ITEMS = 8
FOUND_MAX_DEPTH = 2
FOUND_MAX_BYTES = 4096

#: The one key under which a bounded stand-in appears. It replaces the whole value rather
#: than being added beside it, so it shadows an untrusted key spelled the same way rather
#: than sitting beside it. `[측정]` It does not distinguish the two: a source value that is
#: itself `{BOUNDED: "..."}` with the exact marker text produces a `found` byte-identical to
#: a genuine bound (TASK-009, F2). This field is a diagnostic for a human reader, not a
#: parseable channel a caller should trust to mean "the rule baseline truncated this."
BOUNDED = "<bounded by the rule baseline>"

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

    Abstention has two granularities and both are named. An **item** nothing can classify
    is `skipped`. A **rule** whose input it cannot read is listed in the body's
    `rules_not_evaluated` with the reason, and the record is not reported `clean` — see the
    module docstring's note on F2 for why an unread rule is not a passed rule.
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
    incomplete_count = 0

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

        checker = _check_blog if kind == "document" else _check_trend
        findings, not_evaluated = checker(record)
        evaluated = _coverage(kind, findings, not_evaluated)
        clean = not findings and not not_evaluated
        if findings:
            dirty_count += 1
        elif not_evaluated:
            incomplete_count += 1
        else:
            clean_count += 1
        kind_counts[kind] += 1

        results.append(
            NormalizedResult(
                source_item_key=item.item_key,
                body={
                    "rule_report_version": RULE_REPORT_VERSION,
                    "record_kind": kind,
                    "clean": clean,
                    "findings": findings,
                    "rules_evaluated": evaluated,
                    "rules_not_evaluated": not_evaluated,
                },
                notes={
                    "rules_fired": [finding["rule"] for finding in findings],
                    "rules_not_evaluated": [entry["rule"] for entry in not_evaluated],
                },
            )
        )

    context.emit_result(results)
    notes = {
        "rule_report_version": RULE_REPORT_VERSION,
        "documents_checked": kind_counts["document"],
        "trend_points_checked": kind_counts["trend_point"],
        "clean": clean_count,
        "with_findings": dirty_count,
        "not_fully_checked": incomplete_count,
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
    """One judgment: which rule, which field, what was expected, what was there.

    `found` passes through `_bound_found` because it is the only place in this module where
    untrusted Raw flows into a stored body.
    """
    return {"rule": rule, "field": field, "expected": expected, "found": _bound_found(found)}


def _abstention(rule: str, field: str, reason: str) -> dict[str, Any]:
    """One rule that reached no verdict, and why. Not a finding, and not a pass."""
    return {"rule": rule, "field": field, "reason": reason}


def _coverage(
    kind: str, findings: list[dict[str, Any]], not_evaluated: list[dict[str, Any]]
) -> list[str]:
    """The kind's declared rules minus the ones this record's checkers abstained on.

    `[확인 사실]` This refuses two of the ways the bookkeeping can lie, not every way — see the
    module docstring's "What `_coverage` actually checks" for the third. The two refused
    here: a rule name outside this kind's set (a rule was added and its set was not), and a
    rule that both fired and abstained (a rule was given a verdict and an abstention at
    once). Neither is reachable from today's ten rules, which is why
    `tests/test_normalizer_rule_baseline.py` drives this branch through `RULES_BY_KIND`
    rather than leaving a guard nothing can fail. What this function does **not** refuse: a
    rule declared in `RULES_BY_KIND[kind]` that reaches no verdict at all — it is computed by
    subtraction, so such a rule is simply left in the returned list, indistinguishable from
    one that actually ran.
    """
    applicable = RULES_BY_KIND[kind]
    unevaluated = {entry["rule"] for entry in not_evaluated}
    fired = {finding["rule"] for finding in findings}
    stray = sorted((fired | unevaluated) - set(applicable))
    contradictory = sorted(fired & unevaluated)
    if stray or contradictory:
        raise AddonOutputInvalid(
            "a record's rule coverage does not match its kind's rule set, so `clean` would "
            "not mean that every applicable rule ran",
            {
                "record_kind": kind,
                "outside_the_rule_set": stray,
                "both_fired_and_abstained": contradictory,
            },
        )
    return [rule for rule in applicable if rule not in unevaluated]


def _bound_found(value: Any) -> Any:
    """A stand-in for `value` that is small, strict JSON, and the same every run.

    Two separate defects sit behind this (TASK-006, F11). Size: `found` echoed the offending
    value verbatim, so a 200 KB field produced a 200 KB `normalized_result` row. Strictness:
    `json.loads` accepts the bare `NaN` and `Infinity` literals that both NAVER collectors'
    `json.dumps` defaults write, and `domain.store.canonical_body` writes them straight back
    out — PostgreSQL's `jsonb` rejects them, which would fail the transaction that stores
    *every* result in the run, not just this one.

    The serialization round-trip is the actual guarantee: whatever comes back from here is
    something `json.dumps(..., allow_nan=False)` has already accepted at a bounded size.
    """
    bounded = _bounded(value)
    try:
        encoded = json.dumps(bounded, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return {BOUNDED: f"a {type(value).__name__} this report cannot serialize"}
    if len(encoded.encode("utf-8")) <= FOUND_MAX_BYTES:
        return bounded
    return {BOUNDED: f"a {type(value).__name__} too large to echo, bounded away in full"}


def _bounded(value: Any, depth: int = 0) -> Any:
    """Recursively shrink one parsed-JSON value. Deterministic: keys are visited sorted."""
    if isinstance(value, str):
        return _bounded_text(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else f"<not a finite number: {value!r}>"
    if isinstance(value, int):
        return value if len(str(value)) <= FOUND_MAX_TEXT else _bounded_text(str(value))
    if depth >= FOUND_MAX_DEPTH:
        return f"<{type(value).__name__} omitted below depth {FOUND_MAX_DEPTH}>"
    if isinstance(value, Mapping):
        keys = sorted(value, key=str)
        kept = {str(key): _bounded(value[key], depth + 1) for key in keys[:FOUND_MAX_ITEMS]}
        if len(keys) <= FOUND_MAX_ITEMS:
            return kept
        return {BOUNDED: {"kept": kept, "keys_omitted": len(keys) - FOUND_MAX_ITEMS}}
    if isinstance(value, list | tuple):
        items = [_bounded(item, depth + 1) for item in value[:FOUND_MAX_ITEMS]]
        if len(value) <= FOUND_MAX_ITEMS:
            return items
        return {BOUNDED: {"kept": items, "items_omitted": len(value) - FOUND_MAX_ITEMS}}
    return _bounded_text(str(value))


def _bounded_text(text: str) -> str:
    if len(text) <= FOUND_MAX_TEXT:
        return text
    return f"{text[:FOUND_MAX_TEXT]}… ({len(text) - FOUND_MAX_TEXT} more characters omitted)"


def _check_blog(
    record: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Four rules, each decidable from this one record. Returns findings and abstentions.

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
      one of the two fields is wrong, and no single-field check would notice. This is the
      one blog rule that can abstain: with either side missing there is nothing to compare,
      and `collector.naver.blog` requires only `link`, so a vendor omission of
      `bloggerlink` is a live input rather than a hypothetical one.
    """
    findings: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    link = record.get("link")
    link_text = link.strip() if isinstance(link, str) else ""
    if not link_text:
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
    bloggerlink_text = bloggerlink.strip() if isinstance(bloggerlink, str) else ""
    if not link_text or not bloggerlink_text:
        not_evaluated.append(
            _abstention(
                RULE_BLOG_LINK_EQUALS_BLOGGERLINK, "bloggerlink", ABSTAIN_LINK_PAIR_INCOMPLETE
            )
        )
    elif link_text == bloggerlink_text:
        findings.append(
            _finding(
                RULE_BLOG_LINK_EQUALS_BLOGGERLINK,
                "bloggerlink",
                "different from `link` (a post is not the blog's home page)",
                {"link": link, "bloggerlink": bloggerlink},
            )
        )

    return findings, not_evaluated


def _check_trend(
    record: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Six rules, each decidable from this one record. Returns findings and abstentions.

    - **missing_field** — `dimension`, `title` (the series name), `period`, and `timeUnit`
      are never absent per DP-021 D2; `terms` is excluded because DP-021 D2 states it "may
      be empty" and `device`/`gender`/`ages` are excluded because DP-021 D2 makes them
      optional by design (null when the request asked for no filter).
    - **unknown_dimension** / **unknown_time_unit** — an enum violation: the value is
      present but is not one of DP-021 D2's fixed names. Fires only when the field is
      present at all, so it never doubles up with `missing_field` on the same defect —
      and *abstains* when it is not, because "no name to admit" is not "an admitted name".
    - **ratio_invalid** — present but not a number (or is a `bool`, which Python's `int`
      would otherwise accept).
    - **ratio_out_of_range** — numeric but outside `[0, 100]`. DP-021 D3 quotes the vendor's
      own documentation that the window's maximum is fixed at 100; see this module's
      `[가설]` on the lower bound. Abstains exactly when `ratio_invalid` fires.
    - **period_outside_window** — a cross-field consistency check across three fields:
      `period` must fall within `[startDate, endDate]`, the window `notes.start_date`/
      `notes.end_date` in `normalizer.naver.trend` already carries. It fires only when all
      three parse as valid calendar dates, so it never contradicts `missing_field` (which
      already covers an absent `period`) — a malformed or absent `startDate`/`endDate` alone
      is not itself a violation this rule set names, since neither field is in DP-021 D2's
      required set. It is the rule TASK-006's F2 was reported against: it abstains far more
      often than it fires, and until F2 that abstention was invisible.
    """
    findings: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    for field_name in ("dimension", "title", "period", "timeUnit"):
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                _finding(RULE_TREND_MISSING_FIELD, field_name, "a non-empty string", value)
            )

    dimension = record.get("dimension")
    if not isinstance(dimension, str) or not dimension.strip():
        not_evaluated.append(
            _abstention(RULE_TREND_UNKNOWN_DIMENSION, "dimension", ABSTAIN_NO_NAME_TO_ADMIT)
        )
    elif dimension not in TREND_DIMENSIONS:
        findings.append(
            _finding(
                RULE_TREND_UNKNOWN_DIMENSION,
                "dimension",
                f"one of {', '.join(TREND_DIMENSIONS)}",
                dimension,
            )
        )

    time_unit = record.get("timeUnit")
    if not isinstance(time_unit, str) or not time_unit.strip():
        not_evaluated.append(
            _abstention(RULE_TREND_UNKNOWN_TIME_UNIT, "timeUnit", ABSTAIN_NO_NAME_TO_ADMIT)
        )
    elif time_unit not in TREND_TIME_UNITS:
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
        not_evaluated.append(
            _abstention(RULE_TREND_RATIO_OUT_OF_RANGE, "ratio", ABSTAIN_RATIO_NOT_A_NUMBER)
        )
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
    if period is None or start is None or end is None:
        not_evaluated.append(
            _abstention(RULE_TREND_PERIOD_OUTSIDE_WINDOW, "period", ABSTAIN_WINDOW_UNPARSEABLE)
        )
    elif not (start <= period <= end):
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

    return findings, not_evaluated


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
