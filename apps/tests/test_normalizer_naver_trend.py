"""`normalizer.naver.trend` — DataLab points into `Normalized Schema 0.2` trend records,
with DP-030 D2's record-level fault tolerance.

Ported from `experiments/integrated-p0/tests/test_normalizer_naver_trend.py`. The envelope,
determinism, and "computes nothing" classes below are carried over close to verbatim — those
properties are unchanged by DP-030. `TestWhatItSkips` and the dimension-admission tests are
rewritten: P0 silently skipped every malformed field on an otherwise-recognizable point;
DP-030 D2 makes that a contract-level defect (a record failure must degrade, not disappear),
so this add-on now emits those points with a missing-value substitution and a
`notes.normalize_error` note instead. See `addons/normalizer.naver.trend/handler.py`'s module
docstring for exactly where the skip/fallback line is drawn.
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
        _, results = normalize(a_point())
        assert results[0].body["segment"] == {"device": None, "gender": None, "ages": None}

    def test_a_stated_segment_is_carried(self) -> None:
        _, results = normalize(a_point(device="mo", gender="f", ages=["2", "3"]))
        assert results[0].body["segment"] == {
            "device": "mo",
            "gender": "f",
            "ages": ["2", "3"],
        }

    def test_no_result_carries_a_normalize_error_when_nothing_is_wrong(self) -> None:
        """The positive control for `TestDP030RecordLevelFallback` below."""
        _, results = normalize(a_point())
        assert "normalize_error" not in results[0].notes


class TestItComputesNothing:
    """DP-021 D3, and the reason it is a decision rather than an omission."""

    def test_the_ratio_is_the_number_the_source_reported(self) -> None:
        _, results = normalize(a_point(ratio=62.5))
        assert results[0].body["ratio"] == 62.5

    def test_the_window_travels_with_the_point_in_notes(self) -> None:
        _, results = normalize(a_point())
        assert results[0].notes["start_date"] == "2026-08-01"
        assert results[0].notes["end_date"] == "2026-08-14"

    def test_two_points_from_different_windows_are_not_rescaled(self) -> None:
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
    """The narrower skip set DP-030 D2 leaves: an item that is not a DataLab point at all,
    not merely a DataLab point with one bad field."""

    def test_an_item_that_is_not_json_is_skipped_and_counted(self) -> None:
        outcome, results = normalize(SnapshotItem("x|y", b"not json", "application/json"))
        assert isinstance(outcome, NormalizeOutcome)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_an_item_with_no_dimension_key_at_all_is_skipped(self) -> None:
        """A document item — a snapshot of blog Raw handed to this normalizer — is skipped
        item by item, same as P0. This is data selection, not a record failure."""
        document = SnapshotItem(
            "https://blog.naver.com/x/1",
            json.dumps({"link": "https://blog.naver.com/x/1", "title": "t"}).encode(),
            "application/json",
        )
        outcome, results = normalize(document)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_dimension_that_is_an_empty_string_is_treated_as_absent(self) -> None:
        outcome, results = normalize(a_point(dimension=""))
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_mixed_snapshot_normalizes_what_it_can(self) -> None:
        outcome, results = normalize(
            a_point(), SnapshotItem("x|y", b"{", "application/json")
        )
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1

    def test_the_count_it_reports_matches_what_it_emitted(self) -> None:
        outcome, results = normalize(a_point(), a_point(period="2026-08-08"))
        assert outcome.results_emitted == len(results) == 2

    def test_an_integer_over_the_4300_digit_conversion_limit_is_skipped_not_aborted(
        self,
    ) -> None:
        """B1 (REVIEW-M2-M7.md): `json.loads` raises a bare `ValueError` (not
        `json.JSONDecodeError`) on an integer past CPython's string-conversion limit; a
        narrow `except (json.JSONDecodeError, UnicodeDecodeError)` misses it and the whole
        run aborts instead of skipping the one bad item."""
        huge_int = SnapshotItem(
            "x|huge", b'{"dimension":"x","v":' + b"9" * 5000 + b"}", "application/json"
        )
        outcome, results = normalize(a_point(), huge_int)
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1

    def test_pathologically_deep_nesting_is_skipped_not_aborted(self) -> None:
        """B1's second reproduction: deep nesting raises `RecursionError`, also missed by
        the narrow tuple."""
        deep = SnapshotItem("x|deep", b"[" * 100_000 + b"]" * 100_000, "application/json")
        outcome, results = normalize(a_point(), deep)
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1


class TestDP030RecordLevelFallback:
    """DP-030 D2: a point that carries a `dimension` string — so it claims to be a DataLab
    record — is never dropped for a bad field. The field is substituted with `None`, the
    first offending field is named in `notes.normalize_error`, and the record is still
    emitted and counted in `results_emitted`, not `skipped`.
    """

    def test_a_point_with_no_numeric_ratio_is_emitted_with_a_null_ratio_and_a_note(
        self,
    ) -> None:
        outcome, results = normalize(a_point(ratio="a lot"))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["ratio"] is None
        assert results[0].notes["normalize_error"] == {
            "field": "ratio",
            "reason": "missing or not numeric",
        }

    def test_a_point_with_no_period_is_emitted_with_a_null_period_and_a_note(self) -> None:
        outcome, results = normalize(a_point(period=None))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["period"] is None
        assert results[0].notes["normalize_error"]["field"] == "period"
        # external_id still forms — the missing half is empty, not the literal text "None".
        assert results[0].body["external_id"] == "수분크림|"

    def test_a_point_with_no_title_is_emitted_with_a_null_series_and_a_note(self) -> None:
        outcome, results = normalize(a_point(title=None))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["series"] is None
        assert results[0].notes["normalize_error"]["field"] == "series"
        assert results[0].body["external_id"] == "|2026-08-01"

    def test_a_bad_time_unit_is_emitted_with_a_null_time_unit_and_a_note(self) -> None:
        outcome, results = normalize(a_point(timeUnit="fortnight"))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["time_unit"] is None
        assert results[0].notes["normalize_error"]["field"] == "time_unit"

    def test_a_dimension_the_schema_does_not_name_is_emitted_with_a_null_dimension(
        self,
    ) -> None:
        """DP-021 D2's own concern — an unrecognised dimension must not silently widen the
        enumeration — still holds: the record's `dimension` is `null`, never the raw value,
        so no record ever claims a dimension outside the three DP-021 D2 names. What
        changes from P0 is that the record now exists (with the note), instead of vanishing
        into a bare `skipped` count."""
        outcome, results = normalize(a_point(dimension="shopping_device"))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["dimension"] is None
        assert results[0].notes["normalize_error"] == {
            "field": "dimension",
            "reason": "'shopping_device' is not one of "
            "('search_keyword', 'shopping_category', 'shopping_keyword')",
        }

    def test_only_the_first_offending_field_is_named_but_every_bad_field_is_nulled(
        self,
    ) -> None:
        """Mirrors `domain.store._safe_canonical_body`'s own narrowing: a record with two
        simultaneously-bad fields gets one named reason, but no bad value survives into the
        body under any field."""
        outcome, results = normalize(a_point(period=None, ratio="a lot"))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].notes["normalize_error"]["field"] == "period"
        assert results[0].body["period"] is None
        assert results[0].body["ratio"] is None

    def test_the_run_summary_aggregates_the_error_record_count(self) -> None:
        outcome, results = normalize(
            a_point(), a_point(period="2026-08-08", ratio="a lot"), a_point(period="2026-09-01")
        )

        assert outcome.results_emitted == 3
        assert outcome.notes["error_records"] == 1
        assert len(results) == 3

    def test_a_record_failure_does_not_abort_the_run(self) -> None:
        """The falsification target this whole class exists for: what
        `P1-INHERITED-DEFECTS.md` §1 measured — one bad record ending the whole run — must
        not happen even before a record reaches `domain.store`."""
        outcome, results = normalize(
            a_point(ratio="bad"), a_point(period="2026-08-08"), a_point(period="2026-08-15")
        )

        assert outcome.results_emitted == 3
        assert len(results) == 3


class TestEveryDimensionDP014AdmitsIsNormalizedCleanly:
    @pytest.mark.parametrize(
        "dimension", ["search_keyword", "shopping_category", "shopping_keyword"]
    )
    def test_a_point_of_this_dimension_becomes_a_clean_record(self, dimension: str) -> None:
        outcome, results = normalize(a_point(dimension=dimension))

        assert (outcome.results_emitted, outcome.skipped) == (1, 0)
        assert results[0].body["dimension"] == dimension
        assert "normalize_error" not in results[0].notes

    def test_the_admitted_set_is_exactly_what_dp_014_fixed(self) -> None:
        module = load_entry().__globals__

        assert module["DIMENSIONS"] == (
            "search_keyword",
            "shopping_category",
            "shopping_keyword",
        )
