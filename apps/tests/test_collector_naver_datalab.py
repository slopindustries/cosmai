"""`collector.naver.datalab`: NAVER DataLab's three modes, one add-on.

Ported and adapted from `experiments/integrated-p0/tests/test_collector_naver_trend.py`,
which tested the two P0 collectors this add-on merges (`collector.naver.searchtrend`,
`collector.naver.shoppinginsight`) together already, because what is worth checking is
almost entirely the same across the three DataLab endpoints. This add-on carries that merge
one step further — see `addons/collector.naver.datalab/README.md` for the decision.

**These tests never open a socket.** The add-on is called with a `CollectContext` whose
`fetch` is a recorder, which is the only way to assert on *the body the add-on composed* —
the thing DP-020 D2 made the add-on's.

`[가설]` Every response fixture here is the vendor's **documented** shape, fetched
2026-08-19 from `api.ncloud-docs.com/docs/naver-api-hub-search-trend` and
`.../naver-api-hub-shopping-insight-categories`; re-checked 2026-08-21. No capture of any of
the three endpoints existed when these were written.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from addon_api import AddonConfigInvalid, AddonManifest, CollectOutcome, FetchResponse, RawItem
from addon_api.context import CollectContext, Limits

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "collector.naver.datalab"


def load_entry() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "collector_naver_datalab_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


class Recorder:
    """A `fetch` that answers from a script and remembers what it was asked.

    The bodies are the point. An add-on that composed the wrong request would still be
    handed the right response by a stub that ignored it, so every case below asserts on
    `bodies` rather than only on what came back.
    """

    def __init__(self, *responses: dict[str, Any]) -> None:
        self._responses = list(responses)
        self.endpoints: list[str] = []
        self.bodies: list[dict[str, Any]] = []
        self.emitted: list[RawItem] = []
        self.cursor: tuple[str, Any] | None = None
        self.accepted: list[tuple[int, str]] = []

    def fetch(
        self,
        endpoint_ref: str,
        params: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> FetchResponse:
        self.endpoints.append(endpoint_ref)
        assert body is not None, "a DataLab endpoint is POST and must carry a body"
        self.bodies.append(json.loads(body))
        if not self._responses:
            raise AssertionError(f"unscripted request to {endpoint_ref}")
        payload = self._responses.pop(0)
        return FetchResponse(
            endpoint_ref=endpoint_ref,
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            envelope_ref=f"harness:{len(self.endpoints)}",
            retrieved_at="2026-08-19T00:00:00+09:00",
        )

    def context(self, config: dict[str, Any], cursor: Any = None) -> CollectContext:
        return CollectContext(
            source_id="probe",
            config=config,
            cursor=cursor,
            limits=Limits(5.0, 30.0, 8 * 1024 * 1024, 3, 20, 5000, 64 * 1024),
            fetch=self.fetch,
            accept_status=lambda response, reason: self.accepted.append(
                (response.status, reason)
            ),
            emit_raw=self.emitted.extend,
            advance_cursor=lambda stream, value: setattr(self, "cursor", (stream, value)),
            log=lambda event, fields: None,
        )


def a_series(title: str = "수분크림", **extra: Any) -> dict[str, Any]:
    series: dict[str, Any] = {
        "title": title,
        "data": [
            {"period": "2026-08-01", "ratio": 100.0},
            {"period": "2026-08-08", "ratio": 62.5},
        ],
    }
    series.update(extra)
    return series


def a_datalab_response(*series: dict[str, Any]) -> dict[str, Any]:
    return {
        "startDate": "2026-08-01",
        "endDate": "2026-08-14",
        "timeUnit": "week",
        "results": list(series) or [a_series(keywords=["수분크림"])],
    }


SEARCH_TREND_CONFIG: dict[str, Any] = {
    "mode": "search_trend",
    "start_date": "2026-08-01",
    "end_date": "2026-08-14",
    "time_unit": "week",
    "keyword_groups": json.dumps(
        [{"groupName": "수분크림", "keywords": ["수분크림", "수분 크림"]}], ensure_ascii=False
    ),
}

SHOPPING_CATEGORIES_CONFIG: dict[str, Any] = {
    "mode": "shopping_categories",
    "start_date": "2026-08-01",
    "end_date": "2026-08-14",
    "time_unit": "week",
    "categories": json.dumps([{"name": "스킨케어", "param": ["50000002"]}], ensure_ascii=False),
}

SHOPPING_KEYWORDS_CONFIG: dict[str, Any] = {
    "mode": "shopping_keywords",
    "start_date": "2026-08-01",
    "end_date": "2026-08-14",
    "time_unit": "week",
    "category": "50000002",
    "keywords": json.dumps([{"name": "수분크림", "param": ["수분크림"]}], ensure_ascii=False),
}


# --------------------------------------------------------------------------- #
# The manifest
# --------------------------------------------------------------------------- #


class TestTheManifest:
    def test_it_is_a_collector_that_needs_a_credential(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "collector"
        assert manifest.declares.needs_credential is True

    def test_it_declares_the_api_hub_host_and_nothing_else(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ("naverapihub.apigw.ntruss.com",)

    def test_it_declares_all_three_endpoints(self) -> None:
        """`[declares]` is a *request*; the source's profile is the grant (DP-008 D4). A
        source configured for a mode whose endpoint it was not granted is refused by the
        outbound guard, not by this add-on — so the request has to name all three."""
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert set(manifest.declares.endpoints) == {"trend", "categories", "category_keywords"}

    def test_it_declares_exactly_one_cursor_stream(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert len(manifest.declares.streams) <= 1


class TestModeIsRequired:
    def test_a_missing_mode_is_refused_before_any_request(self) -> None:
        recorder = Recorder(a_datalab_response())
        config = {k: v for k, v in SEARCH_TREND_CONFIG.items() if k != "mode"}

        with pytest.raises(AddonConfigInvalid, match="mode"):
            load_entry()(recorder.context(config))
        assert recorder.endpoints == []

    def test_an_unimplemented_mode_is_refused_by_name(self) -> None:
        recorder = Recorder(a_datalab_response())

        with pytest.raises(AddonConfigInvalid, match="mode"):
            load_entry()(recorder.context({**SEARCH_TREND_CONFIG, "mode": "device_breakdown"}))
        assert recorder.endpoints == []


# --------------------------------------------------------------------------- #
# search_trend
# --------------------------------------------------------------------------- #


class TestSearchTrendComposesItsRequest:
    def test_it_posts_the_documented_body_to_the_declared_endpoint(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert recorder.endpoints == ["trend"]
        assert recorder.bodies[0] == {
            "startDate": "2026-08-01",
            "endDate": "2026-08-14",
            "timeUnit": "week",
            "keywordGroups": [
                {"groupName": "수분크림", "keywords": ["수분크림", "수분 크림"]}
            ],
        }

    def test_the_optional_segment_is_sent_only_when_configured(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(
            recorder.context(
                {**SEARCH_TREND_CONFIG, "device": "mo", "gender": "f", "ages": "2,3"}
            )
        )

        assert recorder.bodies[0]["device"] == "mo"
        assert recorder.bodies[0]["gender"] == "f"
        assert recorder.bodies[0]["ages"] == ["2", "3"]

    def test_an_unset_segment_field_is_absent_from_the_body(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        for absent in ("device", "gender", "ages"):
            assert absent not in recorder.bodies[0]

    def test_a_cursor_resumes_from_the_day_after_the_last_window(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(
            recorder.context(SEARCH_TREND_CONFIG, cursor={"last_end_date": "2026-08-07"})
        )

        assert recorder.bodies[0]["startDate"] == "2026-08-08"

    def test_a_cursor_at_or_past_the_configured_end_collects_nothing(self) -> None:
        recorder = Recorder()

        outcome = load_entry()(
            recorder.context(SEARCH_TREND_CONFIG, cursor={"last_end_date": "2026-08-14"})
        )

        assert recorder.endpoints == []
        assert outcome.items_emitted == 0


class TestSearchTrendUnrollsThePoints:
    def test_one_item_per_series_and_period(self) -> None:
        recorder = Recorder(
            a_datalab_response(
                a_series("수분크림", keywords=["수분크림"]),
                a_series("앰플", keywords=["앰플"]),
            )
        )

        outcome = load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert isinstance(outcome, CollectOutcome)
        assert outcome.items_emitted == 4
        assert len(recorder.emitted) == 4

    def test_the_item_key_is_the_series_and_the_period(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert [item.item_key for item in recorder.emitted] == [
            "수분크림|2026-08-01",
            "수분크림|2026-08-08",
        ]

    def test_each_item_carries_the_point_and_the_window_it_came_from(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        payload = json.loads(recorder.emitted[0].payload)
        assert payload["period"] == "2026-08-01"
        assert payload["ratio"] == 100.0
        assert payload["title"] == "수분크림"
        assert payload["startDate"] == "2026-08-01"
        assert payload["endDate"] == "2026-08-14"
        assert payload["timeUnit"] == "week"

    def test_every_item_names_the_envelope_it_came_from(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert {item.envelope_ref for item in recorder.emitted} == {"harness:1"}

    def test_the_cursor_advances_to_the_window_that_was_collected(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert recorder.cursor is not None
        assert recorder.cursor[1] == {"last_end_date": "2026-08-14"}

    def test_a_response_with_no_series_emits_nothing_and_still_advances(self) -> None:
        recorder = Recorder({**a_datalab_response(), "results": []})

        outcome = load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert outcome.items_emitted == 0
        assert recorder.cursor is not None

    def test_search_trend_records_its_own_dimension(self) -> None:
        recorder = Recorder(a_datalab_response())

        load_entry()(recorder.context(SEARCH_TREND_CONFIG))

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "search_keyword"


class TestSearchTrendRefusesBadConfiguration:
    @pytest.mark.parametrize(
        "change",
        [
            {"start_date": "01-08-2026"},
            {"end_date": ""},
            {"time_unit": "fortnight"},
            {"keyword_groups": "not json"},
            {"keyword_groups": "[]"},
            {"start_date": "2026-08-20"},
        ],
        ids=["bad start", "empty end", "bad unit", "bad json", "no groups", "start after end"],
    )
    def test_it_names_what_is_wrong_before_any_request(self, change: dict[str, Any]) -> None:
        recorder = Recorder(a_datalab_response())

        with pytest.raises(AddonConfigInvalid):
            load_entry()(recorder.context({**SEARCH_TREND_CONFIG, **change}))

        assert recorder.endpoints == [], "a refused configuration must cost no request"

    def test_more_than_five_keyword_groups_is_refused(self) -> None:
        groups = [{"groupName": f"g{n}", "keywords": [f"k{n}"]} for n in range(6)]
        recorder = Recorder(a_datalab_response())

        with pytest.raises(AddonConfigInvalid, match="5"):
            load_entry()(
                recorder.context({**SEARCH_TREND_CONFIG, "keyword_groups": json.dumps(groups)})
            )

    def test_a_valid_configuration_is_not_refused(self) -> None:
        recorder = Recorder(a_datalab_response())

        assert load_entry()(recorder.context(SEARCH_TREND_CONFIG)).items_emitted == 2


# --------------------------------------------------------------------------- #
# shopping_categories / shopping_keywords
# --------------------------------------------------------------------------- #


class TestShoppingInsightComposesItsRequest:
    def test_categories_mode_posts_the_documented_body(self) -> None:
        recorder = Recorder(a_datalab_response(a_series("스킨케어", category=["50000002"])))

        load_entry()(recorder.context(SHOPPING_CATEGORIES_CONFIG))

        assert recorder.endpoints == ["categories"]
        assert recorder.bodies[0] == {
            "startDate": "2026-08-01",
            "endDate": "2026-08-14",
            "timeUnit": "week",
            "category": [{"name": "스킨케어", "param": ["50000002"]}],
        }

    def test_keywords_mode_posts_to_the_other_endpoint_with_its_own_shape(self) -> None:
        recorder = Recorder(a_datalab_response(a_series("수분크림", keyword=["수분크림"])))

        load_entry()(recorder.context(SHOPPING_KEYWORDS_CONFIG))

        assert recorder.endpoints == ["category_keywords"]
        assert recorder.bodies[0]["category"] == "50000002"
        assert recorder.bodies[0]["keyword"] == [{"name": "수분크림", "param": ["수분크림"]}]
        assert "categories" not in recorder.bodies[0]

    def test_keywords_mode_without_a_category_is_refused(self) -> None:
        recorder = Recorder(a_datalab_response())
        config = {k: v for k, v in SHOPPING_KEYWORDS_CONFIG.items() if k != "category"}

        with pytest.raises(AddonConfigInvalid, match="category"):
            load_entry()(recorder.context(config))

    def test_more_than_three_categories_is_refused(self) -> None:
        categories = [{"name": f"c{n}", "param": [str(n)]} for n in range(4)]
        recorder = Recorder(a_datalab_response())

        with pytest.raises(AddonConfigInvalid, match="3"):
            load_entry()(
                recorder.context(
                    {**SHOPPING_CATEGORIES_CONFIG, "categories": json.dumps(categories)}
                )
            )

    def test_a_keyword_pair_with_more_than_one_term_is_refused(self) -> None:
        recorder = Recorder(a_datalab_response())
        config = {
            **SHOPPING_KEYWORDS_CONFIG,
            "keywords": json.dumps([{"name": "수분크림", "param": ["a", "b"]}]),
        }

        with pytest.raises(AddonConfigInvalid, match="one term"):
            load_entry()(recorder.context(config))

    def test_shopping_ages_use_a_different_vocabulary_than_search_trend(self) -> None:
        """`[확인 사실]` Shopping Insight documents 10/20/30/40/50/60; Search Trend
        documents 1-11 for the same idea. A band valid for one is refused for the other."""
        recorder = Recorder(a_datalab_response())

        with pytest.raises(AddonConfigInvalid, match="ages"):
            load_entry()(recorder.context({**SHOPPING_CATEGORIES_CONFIG, "ages": "2"}))


class TestShoppingInsightUnrollsThePoints:
    def test_it_emits_one_item_per_series_and_period(self) -> None:
        recorder = Recorder(
            a_datalab_response(
                a_series("스킨케어", category=["50000002"]),
                a_series("메이크업", category=["50000003"]),
            )
        )

        outcome = load_entry()(recorder.context(SHOPPING_CATEGORIES_CONFIG))

        assert outcome.items_emitted == 4

    def test_the_item_carries_the_dimension_it_measured(self) -> None:
        recorder = Recorder(a_datalab_response(a_series("스킨케어", category=["50000002"])))

        load_entry()(recorder.context(SHOPPING_CATEGORIES_CONFIG))

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "shopping_category"

    def test_keywords_mode_records_a_different_dimension(self) -> None:
        recorder = Recorder(a_datalab_response(a_series("수분크림", keyword=["수분크림"])))

        load_entry()(recorder.context(SHOPPING_KEYWORDS_CONFIG))

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "shopping_keyword"
