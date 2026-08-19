"""`normalizer.naver.trend` — DataLab points into `Normalized Schema 0.2` trend records.

One normalizer for both DataLab collectors, because both produce the same Raw item: a
`{dimension, title, terms, period, ratio, startDate, endDate, timeUnit}` object that the
collector already unrolled from the response's nesting (DP-021 D4).

**It computes nothing.** DP-021 D3: `ratio` is documented as relative to the window's
maximum, so two windows are two scales and any arithmetic across them is arithmetic in
mixed units. The normalizer carries the number and the window it came from, and the class
that matters most in this file is the one asserting it does not do more than that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from addon_api import CONTRACT_VERSION, AddonManifest, NormalizedResult, NormalizeOutcome
from addon_api.context import NormalizeContext
from addon_api.results import SnapshotItem

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "normalizer.naver.trend"


def load_entry() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "normalizer_naver_trend_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def a_point(**overrides: Any) -> SnapshotItem:
    payload: dict[str, Any] = {
        "dimension": "search_keyword",
        "title": "수분크림",
        "terms": ["수분크림", "수분 크림"],
        "period": "2026-08-01",
        "ratio": 100.0,
        "startDate": "2026-08-01",
        "endDate": "2026-08-14",
        "timeUnit": "week",
    }
    payload.update(overrides)
    return SnapshotItem(
        item_key=f"{payload['title']}|{payload['period']}",
        payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def normalize(*items: SnapshotItem, config: dict[str, Any] | None = None) -> Any:
    emitted: list[NormalizedResult] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {"language": "ko"},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
    return load_entry()(context), emitted


class TestTheManifest:
    def test_it_declares_schema_0_2_as_its_output_contract(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.2"
        assert manifest.supports(CONTRACT_VERSION)

    def test_it_declares_no_host_no_endpoint_and_no_credential(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
        assert manifest.declares.needs_credential is False


class TestTheEnvelopeAndTheRecord:
    def test_every_schema_0_2_trend_field_is_present(self) -> None:
        _, results = normalize(a_point())
        assert set(results[0].body) == {
            "schema_version",
            "record_type",
            "external_id",
            "language",
            "series",
            "dimension",
            "terms",
            "period",
            "time_unit",
            "ratio",
            "segment",
        }

    def test_it_names_schema_0_2_and_the_trend_record_type(self) -> None:
        """DP-021 D1. The discriminator is what lets one table hold documents and points."""
        _, results = normalize(a_point())
        assert results[0].body["schema_version"] == "0.2"
        assert results[0].body["record_type"] == "trend_point"

    def test_the_external_id_is_the_series_and_the_period(self) -> None:
        _, results = normalize(a_point())
        assert results[0].body["external_id"] == "수분크림|2026-08-01"
        assert results[0].source_item_key == "수분크림|2026-08-01"

    def test_the_series_terms_and_dimension_come_through_unchanged(self) -> None:
        _, results = normalize(a_point())
        body = results[0].body
        assert body["series"] == "수분크림"
        assert body["terms"] == ["수분크림", "수분 크림"]
        assert body["dimension"] == "search_keyword"

    def test_the_language_is_configuration_and_not_detection(self) -> None:
        _, results = normalize(a_point(), config={"language": "en"})
        assert results[0].body["language"] == "en"

    def test_the_segment_is_all_null_when_the_request_asked_for_no_filter(self) -> None:
        """DP-021 D2: the segment is always present and each part is null when unset. A
        missing key and "all devices" are different claims."""
        _, results = normalize(a_point())
        assert results[0].body["segment"] == {"device": None, "gender": None, "ages": None}

    def test_a_stated_segment_is_carried(self) -> None:
        _, results = normalize(a_point(device="mo", gender="f", ages=["2", "3"]))
        assert results[0].body["segment"] == {
            "device": "mo",
            "gender": "f",
            "ages": ["2", "3"],
        }


class TestItComputesNothing:
    """DP-021 D3, and the reason it is a decision rather than an omission."""

    def test_the_ratio_is_the_number_the_source_reported(self) -> None:
        _, results = normalize(a_point(ratio=62.5))
        assert results[0].body["ratio"] == 62.5

    def test_the_window_travels_with_the_point_in_notes(self) -> None:
        """`ratio` is relative to its window's maximum, so a reader who does not know the
        window is reading a number on an unknown scale."""
        _, results = normalize(a_point())
        assert results[0].notes["start_date"] == "2026-08-01"
        assert results[0].notes["end_date"] == "2026-08-14"

    def test_two_points_from_different_windows_are_not_rescaled(self) -> None:
        """The falsification target: a normalizer that "helpfully" normalised the two onto
        one scale would be inventing a comparison the source does not support."""
        _, results = normalize(
            a_point(ratio=100.0, startDate="2026-08-01", endDate="2026-08-14"),
            a_point(period="2026-09-01", ratio=100.0,
                    startDate="2026-09-01", endDate="2026-09-14"),
        )
        assert [row.body["ratio"] for row in results] == [100.0, 100.0]
        assert results[0].notes["end_date"] != results[1].notes["end_date"]

    def test_it_carries_no_field_it_could_not_read_from_the_point(self) -> None:
        _, results = normalize(a_point())
        for invented in ("trend", "score", "rank", "change", "delta", "moving_average"):
            assert invented not in results[0].body


class TestItIsDeterministic:
    def test_two_runs_over_one_input_produce_equal_bodies(self) -> None:
        _, one = normalize(a_point(), a_point(period="2026-08-08"))
        _, two = normalize(a_point(), a_point(period="2026-08-08"))
        assert [row.body for row in one] == [row.body for row in two]

    def test_the_order_follows_the_snapshot(self) -> None:
        first, second = a_point(period="2026-08-08"), a_point(period="2026-08-01")
        _, results = normalize(first, second)
        assert [row.source_item_key for row in results] == [first.item_key, second.item_key]


class TestWhatItSkips:
    def test_an_item_that_is_not_json_is_skipped_and_counted(self) -> None:
        outcome, results = normalize(SnapshotItem("x|y", b"not json", "application/json"))
        assert isinstance(outcome, NormalizeOutcome)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_point_with_no_numeric_ratio_is_skipped(self) -> None:
        """A record whose measurement is missing is not a measurement. Skipping keeps the
        rest of the snapshot, and the bad item is still in Raw to be looked at."""
        outcome, results = normalize(a_point(ratio="a lot"))
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)

    def test_a_point_with_no_period_is_skipped(self) -> None:
        outcome, _ = normalize(a_point(period=None))
        assert outcome.skipped == 1

    def test_a_dimension_the_schema_does_not_name_is_skipped(self) -> None:
        """DP-021 D2 enumerates three dimensions and its own falsification condition is a
        fourth. Skipping rather than passing it through is what makes that condition
        observable instead of silently widening the enumeration."""
        outcome, _ = normalize(a_point(dimension="shopping_device"))
        assert outcome.skipped == 1

    def test_a_document_item_is_skipped_rather_than_mangled(self) -> None:
        """A snapshot of blog Raw handed to this normalizer produces nothing. That is the
        honest outcome — and the operator surface shows a run with zero results rather than
        a table of records built from fields that were not there."""
        document = SnapshotItem(
            "https://blog.naver.com/x/1",
            json.dumps({"link": "https://blog.naver.com/x/1", "title": "t"}).encode(),
            "application/json",
        )
        outcome, results = normalize(document)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_mixed_snapshot_normalizes_what_it_can(self) -> None:
        """The positive control for every skip above."""
        outcome, results = normalize(
            a_point(), SnapshotItem("x|y", b"{", "application/json")
        )
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1

    def test_the_count_it_reports_matches_what_it_emitted(self) -> None:
        outcome, results = normalize(a_point(), a_point(period="2026-08-08"))
        assert outcome.results_emitted == len(results) == 2


class TestEveryDimensionDP014AdmitsIsNormalized:
    """`[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` M4.

    `DIMENSIONS` admits three and every test used `search_keyword`, so **dropping two of
    the three was GREEN** — a normalizer that silently skipped every Shopping Insight point
    would have looked correct. The ShoppingInsight collector emits all three, so the gap was
    between two committed add-ons rather than in a hypothetical future one.
    """

    @pytest.mark.parametrize(
        "dimension", ["search_keyword", "shopping_category", "shopping_keyword"]
    )
    def test_a_point_of_this_dimension_becomes_a_record(self, dimension: str) -> None:
        outcome, results = normalize(a_point(dimension=dimension))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["dimension"] == dimension

    def test_the_admitted_set_is_exactly_what_dp_014_fixed(self) -> None:
        """The contract pin. A dimension quietly added or removed is a schema change, and
        the test above would follow it rather than notice it."""
        module = load_entry().__globals__

        assert module["DIMENSIONS"] == (
            "search_keyword",
            "shopping_category",
            "shopping_keyword",
        )

    def test_a_dimension_outside_that_set_is_skipped_rather_than_emitted(self) -> None:
        """The control: a rule that admitted everything would pass all four cases above."""
        outcome, results = normalize(a_point(dimension="something_else"))

        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []
