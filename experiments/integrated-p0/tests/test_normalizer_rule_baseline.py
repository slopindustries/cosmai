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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from addon_api import CONTRACT_VERSION, AddonManifest, NormalizedResult, NormalizeOutcome
from addon_api.context import NormalizeContext
from addon_api.results import SnapshotItem
from domain.store import canonical_body, digest_of

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "normalizer.rule.baseline"


def load_entry() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "normalizer_rule_baseline_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


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


def normalize(*items: SnapshotItem, config: dict[str, Any] | None = None) -> Any:
    emitted: list[NormalizedResult] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
    outcome = load_entry()(context)
    return outcome, emitted


def rule_names(body: Mapping[str, Any]) -> set[str]:
    return {finding["rule"] for finding in body["findings"]}


class TestTheManifest:
    def test_it_declares_the_normalizer_kind_and_an_output_contract(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.1"
        assert manifest.supports(CONTRACT_VERSION)

    def test_it_declares_no_host_no_endpoint_and_no_credential(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
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
