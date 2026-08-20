"""`normalizer.rule.baseline` — TASK-004: a normalizer that judges rather than reshapes.

`normalizer.naver.blog` and `normalizer.naver.trend` both reshape and abstain silently on
anything they cannot place in their output schema. This add-on's whole point is the thing
neither of them does: for a snapshot item that is structurally intact but wrong, report it —
name the rule, the field, what was expected, and what was there — rather than either
silently converting it (a bad `postdate` becomes `null`) or silently dropping it (a missing
`link` is skipped with no trace of why).

Every test below drives the add-on through its public entry point, `run(NormalizeContext)`,
the same way `test_normalizer_naver_blog.py` and `test_normalizer_naver_trend.py` do — never
by reaching into the module's private `_check_blog`/`_check_trend`/`_classify` helpers, so
these tests exercise the contract surface rather than the implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from addon_api import CONTRACT_VERSION, AddonManifest, NormalizedResult, NormalizeOutcome
from addon_api.context import NormalizeContext
from addon_api.errors import AddonOutputInvalid
from addon_api.results import SnapshotItem
from domain.store import canonical_body, digest_of

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
ADDON_ROOT = EXPERIMENT_ROOT / "addons" / "normalizer.rule.baseline"

#: Every rule that applies to a record of each kind, written out here rather than read from
#: the module, so that `clean: true`'s claim — every applicable rule ran — is checked
#: against a statement of the rule set and not against the module's own copy of it.
RULES_BY_KIND = {
    "document": {
        "blog.missing_link",
        "blog.missing_content",
        "blog.invalid_postdate",
        "blog.link_equals_bloggerlink",
    },
    "trend_point": {
        "trend.missing_field",
        "trend.unknown_dimension",
        "trend.unknown_time_unit",
        "trend.ratio_invalid",
        "trend.ratio_out_of_range",
        "trend.period_outside_window",
    },
}


def load_module() -> Any:
    """The add-on loaded by path, the way `addon_host` loads it.

    `[확인 사실]` This loader writes `__pycache__/handler.cpython-313.pyc` and validates it
    by `(mtime, size)`. An edit that preserves the file's byte length inside one mtime second
    is therefore invisible here — it cost TASK-004's review two false `SURVIVED` verdicts. If
    you are mutating `handler.py` to check that a control below goes red, run under
    `python -B` and change the file's length, or the result means nothing.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "normalizer_rule_baseline_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_entry() -> Any:
    return load_module().run


def a_blog_record(**overrides: Any) -> dict[str, Any]:
    """The same vendor-shaped fields `test_normalizer_naver_blog.py::an_item` uses.

    `[가설]` (handler.py's module docstring): this is the raw shape a snapshot item is
    assumed to carry, not DP-019's Schema 0.1 output shape.
    """
    record: dict[str, Any] = {
        "title": "촉촉한 수분크림 후기",
        "link": "https://blog.naver.com/someone/123",
        "description": "발림성이 좋고 수분감이 오래갑니다",
        "bloggername": "어떤블로거",
        "bloggerlink": "https://blog.naver.com/someone",
        "postdate": "20260801",
    }
    record.update(overrides)
    return record


def a_trend_record(**overrides: Any) -> dict[str, Any]:
    """The same vendor-shaped fields `test_normalizer_naver_trend.py::a_point` uses."""
    record: dict[str, Any] = {
        "dimension": "search_keyword",
        "title": "수분크림",
        "terms": ["수분크림", "수분 크림"],
        "period": "2026-08-01",
        "ratio": 62.5,
        "startDate": "2026-08-01",
        "endDate": "2026-08-14",
        "timeUnit": "week",
    }
    record.update(overrides)
    return record


def an_item(key: str, record: Mapping[str, Any] | None = None, **overrides: Any) -> SnapshotItem:
    payload = dict(record or {})
    payload.update(overrides)
    return SnapshotItem(
        item_key=key,
        payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def normalize(
    *items: SnapshotItem,
    config: dict[str, Any] | None = None,
    entry: Any = None,
) -> Any:
    """Drive the add-on over one snapshot. `entry` is for a deliberately altered module."""
    emitted: list[NormalizedResult] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
    outcome = (entry if entry is not None else load_entry())(context)
    return outcome, emitted


def rule_names(body: Mapping[str, Any]) -> set[str]:
    return {finding["rule"] for finding in body["findings"]}


def unevaluated_rules(body: Mapping[str, Any]) -> set[str]:
    return {entry["rule"] for entry in body["rules_not_evaluated"]}


def one_finding(body: Mapping[str, Any], rule: str, field: str | None = None) -> Any:
    """The single finding for `rule` (and `field`, where one rule covers several)."""
    matches = [
        finding
        for finding in body["findings"]
        if finding["rule"] == rule and (field is None or finding["field"] == field)
    ]
    assert len(matches) == 1, f"expected exactly one {rule} finding, got {body['findings']}"
    return matches[0]


class TestTheManifest:
    def test_it_declares_the_normalizer_kind_and_an_output_contract(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.1"
        assert manifest.supports(CONTRACT_VERSION)

    def test_it_declares_no_host_no_endpoint_no_stream_and_no_credential(self) -> None:
        """`streams` is included because the manifest writes `streams = []` explicitly.
        `[확인 사실]` That is the same value the loader derives from an omitted `[declares]`
        block, so the empty list is documentary — the manifest's comment used to claim it was
        a mechanism (TASK-004's review, F9) and no longer does."""
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
        assert manifest.declares.streams == ()
        assert manifest.declares.needs_credential is False


class TestClassification:
    """Which rule set applies is decided from key names, never from a value's meaning."""

    def test_a_blog_shaped_record_is_classified_as_a_document(self) -> None:
        _, results = normalize(an_item("k", a_blog_record()))
        assert results[0].body["record_kind"] == "document"

    def test_a_trend_shaped_record_is_classified_as_a_trend_point(self) -> None:
        _, results = normalize(an_item("k", a_trend_record()))
        assert results[0].body["record_kind"] == "trend_point"

    def test_a_record_with_neither_shapes_markers_is_skipped_as_unclassifiable(self) -> None:
        outcome, results = normalize(an_item("k", {"unrelated": "value"}))
        assert outcome.skipped == 1
        assert results == []

    def test_a_record_bearing_markers_of_both_shapes_is_skipped_as_unclassifiable(self) -> None:
        """The positive control for classification: this is not "prefer one shape" — an
        item carrying a marker from each is genuinely undecidable and is abstained on, not
        guessed at under either rule set."""
        both = a_blog_record()
        both["dimension"] = "search_keyword"  # a trend-only marker key
        outcome, results = normalize(an_item("k", both))
        assert outcome.skipped == 1
        assert results == []

    def test_the_skip_reason_names_which_kind_of_abstention_fired(self) -> None:
        outcome, _ = normalize(an_item("k", {"unrelated": "value"}))
        assert outcome.notes["skip_reasons"]["unclassifiable_record_kind"] == 1
        assert outcome.notes["skip_reasons"]["payload_not_a_json_object"] == 0


class TestTheSnapshotShapeAssumption:
    """The canary for handler.py's biggest `[가설]`.

    TASK-004's own text says Schema 0.1/0.2 "are the snapshot item shapes your rules
    operate over," read literally as: `read_snapshot()` yields DP-019/DP-021's *output*
    envelope. handler.py assumes the opposite — that a snapshot holds the same raw,
    vendor-shaped payload `normalizer.naver.blog`/`normalizer.naver.trend` already consume —
    and states why in its module docstring.

    This test encodes today's behavior under that assumption: a genuinely Schema-0.1-shaped
    body (the *output* of `normalizer.naver.blog`, not its input) carries none of this
    add-on's marker keys and is therefore unclassifiable. If a real platform capture shows
    `read_snapshot()` actually yields this shape, **this test's expectation is what should
    flip** — the add-on would need rewriting against `schema_version`/`record_type` instead
    of the vendor field names, and this whole classification step would become unnecessary.
    """

    def test_a_schema_0_1_enveloped_body_is_unclassifiable_under_todays_assumption(self) -> None:
        schema_0_1_output = {
            "schema_version": "0.1",
            "record_type": "document",
            "external_id": "https://blog.naver.com/someone/123",
            "url": "https://blog.naver.com/someone/123",
            "title": "촉촉한 수분크림 후기",
            "excerpt": "발림성이 좋고 수분감이 오래갑니다",
            "published_at": "2026-08-01",
            "author": "어떤블로거",
            "language": "ko",
        }
        outcome, results = normalize(an_item("k", schema_0_1_output))
        assert outcome.notes["skip_reasons"]["unclassifiable_record_kind"] == 1, (
            "if this fails, a real capture likely proved the literal reading of TASK-004's "
            "'snapshot item shapes' correct — see handler.py's module docstring for what "
            "changes"
        )
        assert results == []


class TestBlogRules:
    def test_a_fully_clean_blog_record_produces_no_findings(self) -> None:
        _, results = normalize(an_item("k", a_blog_record()))
        assert results[0].body["clean"] is True
        assert results[0].body["findings"] == []

    def test_missing_link_fires_when_the_key_is_absent(self) -> None:
        record = a_blog_record()
        del record["link"]
        _, results = normalize(an_item("k", record))
        assert "blog.missing_link" in rule_names(results[0].body)

    def test_missing_link_fires_when_the_value_is_blank(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(link="   ")))
        assert "blog.missing_link" in rule_names(results[0].body)

    def test_missing_link_does_not_fire_when_link_is_present(self) -> None:
        _, results = normalize(an_item("k", a_blog_record()))
        assert "blog.missing_link" not in rule_names(results[0].body)

    def test_missing_content_fires_when_title_and_description_are_both_blank(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(title="", description="  ")))
        assert "blog.missing_content" in rule_names(results[0].body)

    def test_missing_content_does_not_fire_when_only_one_is_blank(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(title="", description="fine")))
        assert "blog.missing_content" not in rule_names(results[0].body)

    def test_invalid_postdate_fires_on_a_malformed_value(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(postdate="not-a-date")))
        assert "blog.invalid_postdate" in rule_names(results[0].body)

    def test_invalid_postdate_fires_when_the_key_is_absent(self) -> None:
        record = a_blog_record()
        del record["postdate"]
        _, results = normalize(an_item("k", record))
        assert "blog.invalid_postdate" in rule_names(results[0].body)

    def test_invalid_postdate_fires_on_a_calendar_invalid_date(self) -> None:
        """`20260230` (February 30th) counts only 8 digits and a month/day in naive range,
        which is why this rule uses `datetime.date` rather than a range check — the same
        value `normalizer.naver.blog`'s own naive parser would silently accept."""
        _, results = normalize(an_item("k", a_blog_record(postdate="20260230")))
        assert "blog.invalid_postdate" in rule_names(results[0].body)

    def test_invalid_postdate_does_not_fire_on_a_valid_date(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(postdate="20260801")))
        assert "blog.invalid_postdate" not in rule_names(results[0].body)

    def test_link_equals_bloggerlink_fires_when_they_are_identical(self) -> None:
        _, results = normalize(
            an_item(
                "k",
                a_blog_record(
                    link="https://blog.naver.com/someone",
                    bloggerlink="https://blog.naver.com/someone",
                ),
            )
        )
        assert "blog.link_equals_bloggerlink" in rule_names(results[0].body)

    def test_link_equals_bloggerlink_does_not_fire_when_they_differ(self) -> None:
        _, results = normalize(an_item("k", a_blog_record()))
        assert "blog.link_equals_bloggerlink" not in rule_names(results[0].body)

    def test_a_blog_record_without_bloggerlink_is_judged_rather_than_crashing(self) -> None:
        """`collector.naver.blog` requires only `link`, so a vendor omission of
        `bloggerlink` is a live input rather than a hypothetical one. The guard that
        survives it used to be held together with a `# type: ignore[union-attr]` on the
        comparison: deleting the guard left mypy and this suite green while a real record
        died with `AttributeError` inside the run, losing the whole snapshot's results
        (TASK-004's review, F5). The guard is now structural and this record is one result.
        """
        record = a_blog_record()
        del record["bloggerlink"]
        outcome, results = normalize(an_item("k", record))
        assert outcome.results_emitted == 1
        assert "blog.link_equals_bloggerlink" not in rule_names(results[0].body)
        assert "blog.link_equals_bloggerlink" in unevaluated_rules(results[0].body)


class TestTrendRules:
    def test_a_fully_clean_trend_record_produces_no_findings(self) -> None:
        _, results = normalize(an_item("k", a_trend_record()))
        assert results[0].body["clean"] is True
        assert results[0].body["findings"] == []

    @pytest.mark.parametrize("field_name", ["dimension", "title", "period", "timeUnit"])
    def test_missing_field_fires_when_a_required_field_is_absent(self, field_name: str) -> None:
        record = a_trend_record()
        del record[field_name]
        _, results = normalize(an_item("k", record))
        assert "trend.missing_field" in rule_names(results[0].body)

    @pytest.mark.parametrize("field_name", ["dimension", "title", "period", "timeUnit"])
    def test_missing_field_fires_when_a_required_field_is_only_whitespace(
        self, field_name: str
    ) -> None:
        """`blog.missing_link` has had a blank-value test since TASK-004; this rule's
        blank-value branch had none, and dropping `or not value.strip()` left the suite
        green (TASK-004's review, F10)."""
        _, results = normalize(an_item("k", a_trend_record(**{field_name: "   "})))
        assert "trend.missing_field" in rule_names(results[0].body)

    def test_missing_field_does_not_fire_when_all_required_fields_are_present(self) -> None:
        _, results = normalize(an_item("k", a_trend_record()))
        assert "trend.missing_field" not in rule_names(results[0].body)

    def test_unknown_dimension_fires_on_a_dimension_outside_dp_021_d2(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(dimension="shopping_device")))
        assert "trend.unknown_dimension" in rule_names(results[0].body)

    @pytest.mark.parametrize(
        "dimension", ["search_keyword", "shopping_category", "shopping_keyword"]
    )
    def test_unknown_dimension_does_not_fire_on_an_admitted_dimension(
        self, dimension: str
    ) -> None:
        _, results = normalize(an_item("k", a_trend_record(dimension=dimension)))
        assert "trend.unknown_dimension" not in rule_names(results[0].body)

    def test_unknown_time_unit_fires_on_a_unit_outside_dp_021_d2(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(timeUnit="year")))
        assert "trend.unknown_time_unit" in rule_names(results[0].body)

    @pytest.mark.parametrize("time_unit", ["date", "week", "month"])
    def test_unknown_time_unit_does_not_fire_on_an_admitted_unit(self, time_unit: str) -> None:
        _, results = normalize(an_item("k", a_trend_record(timeUnit=time_unit)))
        assert "trend.unknown_time_unit" not in rule_names(results[0].body)

    def test_ratio_invalid_fires_when_ratio_is_not_numeric(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio="a lot")))
        assert "trend.ratio_invalid" in rule_names(results[0].body)

    def test_ratio_invalid_fires_when_ratio_is_a_bool(self) -> None:
        """`bool` is a subtype of `int` in Python; a naive `isinstance(x, int | float)`
        would silently accept `True` as the number 1."""
        _, results = normalize(an_item("k", a_trend_record(ratio=True)))
        assert "trend.ratio_invalid" in rule_names(results[0].body)

    def test_ratio_invalid_does_not_fire_when_ratio_is_numeric(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=62.5)))
        assert "trend.ratio_invalid" not in rule_names(results[0].body)

    def test_ratio_out_of_range_fires_above_100(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=100.5)))
        assert "trend.ratio_out_of_range" in rule_names(results[0].body)

    def test_ratio_out_of_range_fires_below_0(self) -> None:
        """`[가설]` (handler.py's module docstring): a negative ratio is assumed invalid,
        though DP-021 D3 only quotes the vendor on the *maximum*. A real capture with a
        negative ratio would falsify this half of the rule."""
        _, results = normalize(an_item("k", a_trend_record(ratio=-0.1)))
        assert "trend.ratio_out_of_range" in rule_names(results[0].body)

    @pytest.mark.parametrize("ratio", [0, 50, 100, 0.0, 100.0])
    def test_ratio_out_of_range_does_not_fire_within_bounds(self, ratio: float) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=ratio)))
        assert "trend.ratio_out_of_range" not in rule_names(results[0].body)

    def test_period_outside_window_fires_when_period_precedes_the_window(self) -> None:
        _, results = normalize(
            an_item(
                "k",
                a_trend_record(period="2026-07-31", startDate="2026-08-01", endDate="2026-08-14"),
            )
        )
        assert "trend.period_outside_window" in rule_names(results[0].body)

    def test_period_outside_window_fires_when_period_follows_the_window(self) -> None:
        _, results = normalize(
            an_item(
                "k",
                a_trend_record(period="2026-08-15", startDate="2026-08-01", endDate="2026-08-14"),
            )
        )
        assert "trend.period_outside_window" in rule_names(results[0].body)

    def test_period_outside_window_does_not_fire_when_period_is_within_bounds(self) -> None:
        _, results = normalize(an_item("k", a_trend_record()))
        assert "trend.period_outside_window" not in rule_names(results[0].body)

    def test_period_outside_window_does_not_fire_when_the_window_cannot_be_parsed(self) -> None:
        """A malformed or missing `startDate`/`endDate` makes this specific cross-field
        check inapplicable — it is not, by itself, one of DP-021 D2's required fields, so
        its absence is not a violation this rule set names (see handler.py's docstring)."""
        record = a_trend_record()
        del record["startDate"]
        _, results = normalize(an_item("k", record))
        assert "trend.period_outside_window" not in rule_names(results[0].body)


class TestAFindingNamesTheParticulars:
    """`rule` alone is a label; the other three fields are what make a finding actionable.

    `[측정]` Before TASK-006 every assertion in this file went through `rule_names`, which
    reads `finding["rule"]` and nothing else. Replacing `_finding`'s return with
    `{"rule": rule, "field": "", "expected": "", "found": None}` left the suite green
    (TASK-004's review, F1) — three quarters of the payload the packet asked for, held by
    nothing. One firing of every rule is checked below: which field, what was expected, and
    what was actually there.
    """

    def test_missing_link_names_the_field_the_expectation_and_the_value(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(link="   ")))
        finding = one_finding(results[0].body, "blog.missing_link")
        assert finding["field"] == "link"
        assert finding["expected"] == "a non-empty string identifying the post"
        assert finding["found"] == "   "

    def test_missing_content_names_both_fields_it_read(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(title="", description="  ")))
        finding = one_finding(results[0].body, "blog.missing_content")
        assert finding["field"] == "content"
        assert finding["expected"] == "at least one of title or description non-empty"
        assert finding["found"] == {"title": "", "description": "  "}

    def test_invalid_postdate_reports_the_value_that_is_not_a_date(self) -> None:
        _, results = normalize(an_item("k", a_blog_record(postdate="20260230")))
        finding = one_finding(results[0].body, "blog.invalid_postdate")
        assert finding["field"] == "postdate"
        assert finding["expected"] == "an 8-digit yyyymmdd date that exists on the calendar"
        assert finding["found"] == "20260230"

    def test_link_equals_bloggerlink_reports_both_sides_of_the_comparison(self) -> None:
        same = "https://blog.naver.com/someone"
        _, results = normalize(an_item("k", a_blog_record(link=same, bloggerlink=same)))
        finding = one_finding(results[0].body, "blog.link_equals_bloggerlink")
        assert finding["field"] == "bloggerlink"
        assert finding["expected"] == "different from `link` (a post is not the blog's home page)"
        assert finding["found"] == {"link": same, "bloggerlink": same}

    @pytest.mark.parametrize("field_name", ["dimension", "title", "period", "timeUnit"])
    def test_missing_field_names_the_field_that_was_absent(self, field_name: str) -> None:
        record = a_trend_record()
        del record[field_name]
        _, results = normalize(an_item("k", record))
        finding = one_finding(results[0].body, "trend.missing_field", field_name)
        assert finding["expected"] == "a non-empty string"
        assert finding["found"] is None

    def test_unknown_dimension_reports_the_value_and_the_admitted_names(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(dimension="shopping_device")))
        finding = one_finding(results[0].body, "trend.unknown_dimension")
        assert finding["field"] == "dimension"
        assert finding["expected"] == "one of search_keyword, shopping_category, shopping_keyword"
        assert finding["found"] == "shopping_device"

    def test_unknown_time_unit_reports_the_value_and_the_admitted_names(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(timeUnit="year")))
        finding = one_finding(results[0].body, "trend.unknown_time_unit")
        assert finding["field"] == "timeUnit"
        assert finding["expected"] == "one of date, week, month"
        assert finding["found"] == "year"

    def test_ratio_invalid_reports_the_non_numeric_value(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio="a lot")))
        finding = one_finding(results[0].body, "trend.ratio_invalid")
        assert finding["field"] == "ratio"
        assert finding["expected"] == "a number"
        assert finding["found"] == "a lot"

    def test_ratio_out_of_range_reports_the_value_and_the_bound_it_broke(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=100.5)))
        finding = one_finding(results[0].body, "trend.ratio_out_of_range")
        assert finding["field"] == "ratio"
        assert finding["expected"] == (
            "between 0 and 100 inclusive (DP-021 D3: the window's maximum is fixed at 100)"
        )
        assert finding["found"] == 100.5

    def test_period_outside_window_reports_all_three_dates_it_compared(self) -> None:
        _, results = normalize(
            an_item(
                "k",
                a_trend_record(period="2026-08-15", startDate="2026-08-01", endDate="2026-08-14"),
            )
        )
        finding = one_finding(results[0].body, "trend.period_outside_window")
        assert finding["field"] == "period"
        assert finding["expected"] == "within [startDate, endDate]"
        assert finding["found"] == {
            "period": "2026-08-15",
            "startDate": "2026-08-01",
            "endDate": "2026-08-14",
        }


class TestCleanMeansEveryApplicableRuleRan:
    """The claim `clean: true` makes, and the only reading under which it is true.

    `[측정]` TASK-004's review found the one place where the stored artefact said something
    untrue: a trend point without `startDate` was emitted as
    `{"clean": true, "findings": []}` with `skipped: 0`, while `trend.period_outside_window`
    had never run (F2). Item-level abstention was counted and named; rule-level abstention
    was silent and then reported as a pass.

    So `clean` now means *every rule applicable to this record kind reached a verdict, and
    none fired*, and the body carries the coverage that claim rests on. A record with no
    findings and an unread rule is neither clean nor judged wrong, and the two are told apart
    by `findings` being empty while `rules_not_evaluated` is not.
    """

    @pytest.mark.parametrize(
        "record_builder",
        [
            a_blog_record,
            lambda: a_blog_record(link="", bloggerlink=""),
            a_trend_record,
            lambda: a_trend_record(ratio="a lot", dimension="  ", timeUnit=None),
        ],
        ids=["clean blog", "empty blog", "clean trend", "unreadable trend"],
    )
    def test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly(
        self, record_builder: Any
    ) -> None:
        """Whatever happens to a record, every applicable rule is accounted for once — as
        evaluated or as not evaluated, never both and never neither."""
        _, results = normalize(an_item("k", record_builder()))
        body = results[0].body
        evaluated = set(body["rules_evaluated"])
        assert evaluated.isdisjoint(unevaluated_rules(body))
        assert evaluated | unevaluated_rules(body) == RULES_BY_KIND[body["record_kind"]]

    def test_every_rule_that_fired_is_listed_as_evaluated(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=101, timeUnit="year")))
        body = results[0].body
        assert rule_names(body) <= set(body["rules_evaluated"])
        assert rule_names(body)

    def test_a_trend_point_whose_window_is_absent_is_not_reported_clean(self) -> None:
        """The F2 reproduction. DP-021 D2 does not require `startDate`, so this record is not
        defective and no rule fires — but `trend.period_outside_window` cannot run, and
        saying `clean: true` here is a claim about coverage that nothing established."""
        record = a_trend_record()
        del record["startDate"]
        outcome, results = normalize(an_item("k", record))
        body = results[0].body
        assert body["findings"] == []
        assert body["clean"] is False
        assert unevaluated_rules(body) == {"trend.period_outside_window"}
        assert outcome.skipped == 0
        assert outcome.notes["not_fully_checked"] == 1

    def test_a_blog_document_whose_bloggerlink_is_absent_is_not_reported_clean(self) -> None:
        """The same shape on the blog side, named in F2 alongside the trend case."""
        record = a_blog_record()
        del record["bloggerlink"]
        _, results = normalize(an_item("k", record))
        body = results[0].body
        assert body["findings"] == []
        assert body["clean"] is False
        assert unevaluated_rules(body) == {"blog.link_equals_bloggerlink"}

    def test_an_unevaluated_rule_carries_the_field_and_the_reason_it_could_not_run(
        self,
    ) -> None:
        record = a_trend_record()
        del record["endDate"]
        _, results = normalize(an_item("k", record))
        (abstention,) = results[0].body["rules_not_evaluated"]
        assert abstention["rule"] == "trend.period_outside_window"
        assert abstention["field"] == "period"
        assert "not a parseable calendar date" in abstention["reason"]

    def test_a_record_every_rule_could_read_is_clean(self) -> None:
        """The positive control for the three tests above: `clean: false` has to be
        reachable *and* unreachable, or the narrowing would be indistinguishable from
        hard-coding `clean` to `false`."""
        _, results = normalize(an_item("k", a_trend_record()))
        body = results[0].body
        assert body["clean"] is True
        assert body["rules_not_evaluated"] == []
        assert set(body["rules_evaluated"]) == RULES_BY_KIND["trend_point"]

    def test_a_judged_record_is_not_clean_even_when_every_rule_ran(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio=101)))
        body = results[0].body
        assert body["clean"] is False
        assert body["rules_not_evaluated"] == []

    def test_a_verdict_outside_the_record_kinds_rule_set_fails_the_run(self) -> None:
        """The positive control for the guard that keeps `clean` honest as rules are added.

        Today's ten rules cannot reach it — that is what the guard is for — so what gets
        altered is the rule set it checks against. Without a control here the guard would be
        an assertion nobody had seen fail, which is the same class of claim F2 was about.
        """
        module = load_module()
        module.RULES_BY_KIND = {
            "document": tuple(
                rule for rule in module.BLOG_RULES if rule != "blog.missing_link"
            ),
            "trend_point": module.TREND_RULES,
        }
        record = a_blog_record()
        del record["link"]
        with pytest.raises(AddonOutputInvalid) as raised:
            normalize(an_item("k", record), entry=module.run)
        assert raised.value.detail is not None
        assert raised.value.detail["outside_the_rule_set"] == ["blog.missing_link"]


class TestWhatAFindingEchoes:
    """A finding names the offending value; it does not copy it into the database.

    `[측정]` TASK-004's review measured both halves of this (F11). Size: a `ratio` of
    `{"nested": "A" * 200000}` produced a 200 175-byte `canonical_body` from a 200 179-byte
    input, and `domain.store.record_results` stores that body as `Jsonb`. Strictness:
    `json.loads` accepts the bare `NaN` literal that both NAVER collectors' `json.dumps`
    defaults write, and `canonical_body` wrote it straight back out — a literal PostgreSQL's
    `jsonb` rejects, which would fail the transaction holding every result in the run.
    """

    def test_a_huge_value_is_bounded_before_it_reaches_the_body(self) -> None:
        _, results = normalize(an_item("k", a_trend_record(ratio={"nested": "A" * 200_000})))
        body = results[0].body
        assert "trend.ratio_invalid" in rule_names(body)
        assert len(canonical_body(body)) < 8192

    def test_a_bounded_value_still_says_what_was_there(self) -> None:
        """The control for the bound: a smaller report is only useful if it still names the
        value's shape rather than deleting it."""
        _, results = normalize(an_item("k", a_trend_record(ratio="B" * 500)))
        finding = one_finding(results[0].body, "trend.ratio_invalid")
        assert finding["found"].startswith("B" * 200)
        assert "300 more characters omitted" in finding["found"]

    def test_a_short_value_is_echoed_untouched(self) -> None:
        """The other control: bounding must not reach values it has no business rewriting."""
        _, results = normalize(an_item("k", a_trend_record(ratio="a lot")))
        assert one_finding(results[0].body, "trend.ratio_invalid")["found"] == "a lot"

    def test_a_non_finite_ratio_produces_strict_json(self) -> None:
        payload = json.dumps({**a_trend_record(), "ratio": float("nan")})
        assert "NaN" in payload, "the input has to carry the literal for this to prove anything"
        _, results = normalize(
            SnapshotItem("k", payload.encode("utf-8"), "application/json")
        )
        body = results[0].body
        assert "trend.ratio_out_of_range" in rule_names(body)
        assert_strict_json(canonical_body(body))

    def test_the_strict_json_check_can_fail(self) -> None:
        """The positive control for the assertion above. `canonical_body` is not this
        add-on's to change, and it emits `NaN` for a non-finite float — so the check has to
        be shown catching exactly what the add-on now keeps out."""
        with pytest.raises(AssertionError):
            assert_strict_json(canonical_body({"found": float("nan")}))


def assert_strict_json(encoded: bytes) -> None:
    """Fail unless `encoded` is JSON no reader has to be lenient to accept.

    `json.loads` is lenient by default: it accepts `NaN`, `Infinity`, and `-Infinity`, which
    are not JSON and which PostgreSQL's `jsonb` rejects. `parse_constant` is the hook that
    sees exactly those three.
    """

    def reject(name: str) -> Any:
        raise AssertionError(f"not strict JSON: the body carries the bare literal {name}")

    json.loads(encoded.decode("utf-8"), parse_constant=reject)


class TestAbstention:
    """`skipped` is reserved for "this rule cannot decide at all" — never for "decided and
    wrong". The last test here is the positive control that distinguishes the two."""

    def test_an_item_that_is_not_json_is_skipped_and_counted(self) -> None:
        outcome, results = normalize(SnapshotItem("k", b"not json", "application/json"))
        assert isinstance(outcome, NormalizeOutcome)
        assert outcome.results_emitted == 0
        assert outcome.skipped == 1
        assert results == []

    def test_a_json_array_is_skipped_because_it_is_not_an_object(self) -> None:
        outcome, results = normalize(
            SnapshotItem("k", json.dumps([1, 2, 3]).encode(), "application/json")
        )
        assert outcome.skipped == 1
        assert results == []

    def test_the_skip_reason_names_a_malformed_payload_distinctly(self) -> None:
        outcome, _ = normalize(SnapshotItem("k", b"not json", "application/json"))
        assert outcome.notes["skip_reasons"]["payload_not_a_json_object"] == 1
        assert outcome.notes["skip_reasons"]["unclassifiable_record_kind"] == 0

    def test_a_mixed_snapshot_normalizes_what_it_can(self) -> None:
        """The positive control for every skip case above: one bad item does not lose the
        rest of the snapshot."""
        outcome, results = normalize(
            an_item("good", a_blog_record()),
            SnapshotItem("bad", b"not json", "application/json"),
        )
        assert outcome.results_emitted == 1
        assert outcome.skipped == 1
        assert len(results) == 1

    def test_an_item_with_findings_is_emitted_not_skipped(self) -> None:
        """The positive control that skip is about undecidability, not about wrongness: a
        record this add-on *can* judge — and judges as wrong — is still one result, not an
        abstention. Without this control, an implementation that skipped every item with a
        finding would look identical to the abstention tests above."""
        record = a_blog_record()
        del record["link"]
        outcome, results = normalize(an_item("k", record))
        assert outcome.results_emitted == 1
        assert outcome.skipped == 0
        assert len(results) == 1
        assert results[0].body["clean"] is False


class TestOutcomeCounts:
    """Every number this add-on reports about its own run, asserted.

    `[측정]` Before TASK-006, `documents_checked`, `trend_points_checked`, `clean`, and
    `with_findings` were read by no test: setting the kind counters to never advance, or
    swapping the clean and with-findings counters, both left the suite green (TASK-004's
    review, F6). A count nobody checks is a claim, not an observation.
    """

    def test_the_count_it_reports_matches_what_it_emitted(self) -> None:
        outcome, results = normalize(
            an_item("a", a_blog_record()), an_item("b", a_trend_record())
        )
        assert outcome.results_emitted == len(results) == 2

    def test_the_order_follows_the_snapshot(self) -> None:
        first = an_item("first", a_blog_record())
        second = an_item("second", a_trend_record())
        _, results = normalize(second, first)
        assert [row.source_item_key for row in results] == ["second", "first"]

    def test_it_counts_each_record_kind_separately(self) -> None:
        outcome, _ = normalize(
            an_item("a", a_blog_record()),
            an_item("b", a_blog_record()),
            an_item("c", a_trend_record()),
        )
        assert outcome.notes["documents_checked"] == 2
        assert outcome.notes["trend_points_checked"] == 1

    def test_it_counts_clean_and_with_findings_apart(self) -> None:
        """Two clean and one dirty, because one of each would survive a swap of the two
        counters — the exact mutation that went unnoticed."""
        dirty = a_blog_record()
        del dirty["link"]
        outcome, _ = normalize(
            an_item("a", a_blog_record()),
            an_item("b", a_blog_record()),
            an_item("c", dirty),
        )
        assert outcome.notes["clean"] == 2
        assert outcome.notes["with_findings"] == 1
        assert outcome.notes["not_fully_checked"] == 0

    def test_every_emitted_record_lands_in_exactly_one_of_the_three_buckets(self) -> None:
        """The invariant that makes the three counts mean something together: a record is
        clean, judged wrong, or not fully checked, and never two of those or none."""
        incomplete = a_trend_record()
        del incomplete["startDate"]
        dirty = a_trend_record(ratio=101)
        outcome, results = normalize(
            an_item("a", a_blog_record()),
            an_item("b", incomplete),
            an_item("c", dirty),
        )
        buckets = ["clean", "with_findings", "not_fully_checked"]
        assert [outcome.notes[name] for name in buckets] == [1, 1, 1]
        assert sum(outcome.notes[name] for name in buckets) == outcome.results_emitted
        assert len(results) == 3

    def test_it_names_its_own_report_version(self) -> None:
        outcome, results = normalize(an_item("a", a_blog_record()))
        assert outcome.notes["rule_report_version"] == "0.1"
        assert results[0].body["rule_report_version"] == "0.1"

    def test_each_results_notes_name_the_rules_that_fired_and_the_rules_that_did_not(
        self,
    ) -> None:
        record = a_blog_record(link="   ")
        _, results = normalize(an_item("k", record))
        assert results[0].notes["rules_fired"] == ["blog.missing_link"]
        assert results[0].notes["rules_not_evaluated"] == ["blog.link_equals_bloggerlink"]

    def test_a_clean_records_notes_name_nothing(self) -> None:
        """The positive control for the pair above: the lists are empty when nothing
        happened, so a note that always names something would not pass both."""
        _, results = normalize(an_item("k", a_blog_record()))
        assert results[0].notes["rules_fired"] == []
        assert results[0].notes["rules_not_evaluated"] == []


class TestItIsDeterministic:
    """DP-019 D4's determinism claim, asserted on digests the store would compute — the
    pattern `TestDeterminism` in `test_normalizer_capability.py` uses — rather than on raw
    dict equality alone, so the assertion is about the bytes a reader downstream would
    actually see."""

    def test_two_runs_over_one_input_produce_equal_digests(self) -> None:
        _, one = normalize(
            an_item("a", a_blog_record()), an_item("b", a_trend_record(dimension="unknown"))
        )
        _, two = normalize(
            an_item("a", a_blog_record()), an_item("b", a_trend_record(dimension="unknown"))
        )
        first_digests = [digest_of(canonical_body(row.body)) for row in one]
        second_digests = [digest_of(canonical_body(row.body)) for row in two]
        assert first_digests == second_digests

    def test_a_different_input_produces_a_different_digest(self) -> None:
        """The control. Equal digests mean nothing unless unequal input gives unequal
        digests."""
        _, clean = normalize(an_item("a", a_blog_record()))
        _, dirty = normalize(an_item("a", a_blog_record(link="")))
        assert digest_of(canonical_body(clean[0].body)) != digest_of(canonical_body(dirty[0].body))

    def test_the_digests_are_the_same_under_different_hash_seeds(self, tmp_path: Path) -> None:
        """The control the two tests above cannot be: they run in one process.

        `[측정]` `canonical_body` sorts keys, so key order cannot move a digest, and both
        calls above share one interpreter, so anything derived from a hash-randomised
        iteration order is identical between them and different between runs of the suite.
        TASK-004's review made the point with the smallest realistic mistake for this module
        — joining a `set` instead of a tuple into an `expected` string, in a file that
        already holds two `frozenset`s — and measured **four distinct digests over six
        `PYTHONHASHSEED` values while the determinism tests reported `2 passed`** (F3).

        So this one digests the same snapshot in a fresh interpreter per seed. The snapshot
        deliberately reaches every rule's `expected` string and every abstention reason,
        because those are the strings a set would leak its order into.
        """
        probe = tmp_path / "probe.py"
        probe.write_text(SEED_PROBE, encoding="utf-8")
        payloads = json.dumps(
            [
                a_blog_record(),
                {"link": "", "title": "", "description": "", "postdate": "20260230"},
                a_trend_record(),
                a_trend_record(dimension="shopping_device", timeUnit="year", ratio=101),
                {"period": "2026-08-01", "terms": [], "ratio": "a lot"},
                a_trend_record(period="2026-09-01"),
            ],
            ensure_ascii=False,
        )
        digests_by_seed = {
            seed: subprocess.run(
                [sys.executable, "-B", str(probe), str(ADDON_ROOT / "handler.py")],
                input=payloads,
                capture_output=True,
                text=True,
                check=True,
                cwd=tmp_path,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": str(EXPERIMENT_ROOT),
                    "PYTHONHASHSEED": seed,
                },
                timeout=60,
            ).stdout.strip()
            for seed in ("0", "1", "2", "3", "4", "5")
        }
        assert len(set(digests_by_seed.values())) == 1, digests_by_seed
        assert digests_by_seed["0"].count(",") == 5, digests_by_seed["0"]


#: Digest one snapshot in a fresh interpreter, so a value derived from hash-randomised
#: iteration order shows up as a different digest instead of being identical to itself.
SEED_PROBE = '''
"""Print the digests `domain.store` would compute for one snapshot's result bodies."""

import importlib.util
import json
import sys

from addon_api.context import NormalizeContext
from addon_api.results import SnapshotItem
from domain.store import canonical_body, digest_of

spec = importlib.util.spec_from_file_location("handler_under_seed", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

items = [
    SnapshotItem(
        item_key=str(index),
        payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
    for index, payload in enumerate(json.loads(sys.stdin.read()))
]
emitted = []
module.run(
    NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config={},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
)
print(",".join(digest_of(canonical_body(row.body)) for row in emitted))
'''
