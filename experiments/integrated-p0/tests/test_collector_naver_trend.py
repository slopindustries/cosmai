"""The two DataLab collectors: Search Trend and Shopping Insight.

Both are `POST` with a JSON body (DP-020), both return the same nested shape —
`results[].data[]` of `{period, ratio}` — and both unroll it into one `raw_item` per point
(DP-021 D4). They are tested together because what is worth checking is almost entirely the
same, and the places they differ are the interesting ones: Search Trend groups keywords,
Shopping Insight groups categories or keywords *within* a category.

**These tests never open a socket.** The add-ons are called with a `CollectContext` whose
`fetch` is a recorder, which is the only way to assert on *the body the add-on composed* —
the thing DP-020 D2 made the add-on's. `test_operator_loop.py` runs the same add-ons through
the real capability layer, and the real-data scenario runs them against the real API.

`[가설]` Every response fixture here is the vendor's **documented** shape, fetched
2026-08-19 from `api.ncloud-docs.com/docs/naver-api-hub-search-trend` and
`.../naver-api-hub-shopping-insight-categories`. No capture existed when these were written.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from addon_api import AddonConfigInvalid, AddonManifest, CollectOutcome, FetchResponse, RawItem
from addon_api.context import CollectContext, Limits

ADDONS = Path(__file__).resolve().parents[1] / "addons"

TREND = ADDONS / "collector.naver.searchtrend"
SHOPPING = ADDONS / "collector.naver.shoppinginsight"


def load_entry(root: Path) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{root.name}_under_test", root / "handler.py")
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
        #: Every non-success status the add-on decided about, with its stated reason.
        #: Empty for all three collectors, which raise instead — recorded so a future one
        #: that accepts a status has to say so here rather than silently.
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


def a_trend_response(*series: dict[str, Any]) -> dict[str, Any]:
    return {
        "startDate": "2026-08-01",
        "endDate": "2026-08-14",
        "timeUnit": "week",
        "results": list(series) or [a_series(keywords=["수분크림"])],
    }


TREND_CONFIG: dict[str, Any] = {
    "start_date": "2026-08-01",
    "end_date": "2026-08-14",
    "time_unit": "week",
    "keyword_groups": json.dumps(
        [{"groupName": "수분크림", "keywords": ["수분크림", "수분 크림"]}], ensure_ascii=False
    ),
}

SHOPPING_CONFIG: dict[str, Any] = {
    "start_date": "2026-08-01",
    "end_date": "2026-08-14",
    "time_unit": "week",
    "mode": "categories",
    "categories": json.dumps(
        [{"name": "스킨케어", "param": ["50000002"]}], ensure_ascii=False
    ),
}


# --------------------------------------------------------------------------- #
# What both of them declare
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("root", [TREND, SHOPPING], ids=["searchtrend", "shoppinginsight"])
class TestBothManifests:
    def test_it_is_a_collector_that_needs_a_credential(self, root: Path) -> None:
        manifest = AddonManifest.load(root / "addon.toml")
        assert manifest.kind == "collector"
        assert manifest.declares.needs_credential is True

    def test_it_declares_the_api_hub_host_and_nothing_else(self, root: Path) -> None:
        """`[declares]` is a *request*; the source's profile is the grant (DP-008 D4). What
        matters here is that the request names the one host these APIs live on."""
        manifest = AddonManifest.load(root / "addon.toml")
        assert manifest.declares.hosts == ("naverapihub.apigw.ntruss.com",)

    def test_it_declares_exactly_one_cursor_stream(self, root: Path) -> None:
        """`_require_single_stream` refuses a multi-stream add-on while OQ-010 is open, so
        an add-on that declared two would be installable and unrunnable."""
        manifest = AddonManifest.load(root / "addon.toml")
        assert len(manifest.declares.streams) <= 1


# --------------------------------------------------------------------------- #
# Search Trend
# --------------------------------------------------------------------------- #


class TestSearchTrendComposesItsRequest:
    def test_it_posts_the_documented_body_to_the_declared_endpoint(self) -> None:
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

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
        """The API defaults each of these to "all". Sending an empty value is not the same
        request as sending none, so an unset field is absent rather than null."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(
            recorder.context({**TREND_CONFIG, "device": "mo", "gender": "f", "ages": "2,3"})
        )

        assert recorder.bodies[0]["device"] == "mo"
        assert recorder.bodies[0]["gender"] == "f"
        assert recorder.bodies[0]["ages"] == ["2", "3"]

    def test_an_unset_segment_field_is_absent_from_the_body(self) -> None:
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        for absent in ("device", "gender", "ages"):
            assert absent not in recorder.bodies[0]

    def test_a_cursor_resumes_from_the_day_after_the_last_window(self) -> None:
        """The cursor is the last `endDate` collected. Resuming from the day after is what
        makes a second run collect new intervals rather than re-collect the same ones."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG, cursor={"last_end_date": "2026-08-07"}))

        assert recorder.bodies[0]["startDate"] == "2026-08-08"

    def test_a_cursor_at_or_past_the_configured_end_collects_nothing(self) -> None:
        """Nothing to ask for is an ordinary state, not a failure — and it must cost no
        request, because a request that can only return an empty window still spends quota."""
        recorder = Recorder()

        outcome = load_entry(TREND)(
            recorder.context(TREND_CONFIG, cursor={"last_end_date": "2026-08-14"})
        )

        assert recorder.endpoints == []
        assert outcome.items_emitted == 0


class TestSearchTrendUnrollsThePoints:
    def test_one_item_per_series_and_period(self) -> None:
        recorder = Recorder(
            a_trend_response(
                a_series("수분크림", keywords=["수분크림"]),
                a_series("앰플", keywords=["앰플"]),
            )
        )

        outcome = load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert isinstance(outcome, CollectOutcome)
        assert outcome.items_emitted == 4
        assert len(recorder.emitted) == 4

    def test_the_item_key_is_the_series_and_the_period(self) -> None:
        """DP-021 D4. One row per `(series, period)`, and the key is that pair — which is
        what lets a snapshot order them and a duplicate collapse to the latest."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert [item.item_key for item in recorder.emitted] == [
            "수분크림|2026-08-01",
            "수분크림|2026-08-08",
        ]

    def test_each_item_carries_the_point_and_the_window_it_came_from(self) -> None:
        """DP-020's `ratio` is relative to the window's maximum, so a point without its
        window is a number on an unknown scale. The window travels with the point."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        payload = json.loads(recorder.emitted[0].payload)
        assert payload["period"] == "2026-08-01"
        assert payload["ratio"] == 100.0
        assert payload["title"] == "수분크림"
        assert payload["startDate"] == "2026-08-01"
        assert payload["endDate"] == "2026-08-14"
        assert payload["timeUnit"] == "week"

    def test_every_item_names_the_envelope_it_came_from(self) -> None:
        """`raw_item.envelope_id` is not null: an item without its original is an
        extraction nobody can check."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert {item.envelope_ref for item in recorder.emitted} == {"harness:1"}

    def test_the_cursor_advances_to_the_window_that_was_collected(self) -> None:
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert recorder.cursor is not None
        assert recorder.cursor[1] == {"last_end_date": "2026-08-14"}

    def test_a_response_with_no_series_emits_nothing_and_still_advances(self) -> None:
        """An empty window is an answer. Not advancing would make the next run ask the same
        question and get the same nothing, forever."""
        recorder = Recorder({**a_trend_response(), "results": []})

        outcome = load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert outcome.items_emitted == 0
        assert recorder.cursor is not None


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
        recorder = Recorder(a_trend_response())

        with pytest.raises(AddonConfigInvalid):
            load_entry(TREND)(recorder.context({**TREND_CONFIG, **change}))

        assert recorder.endpoints == [], "a refused configuration must cost no request"

    def test_more_than_five_keyword_groups_is_refused(self) -> None:
        """`[확인 사실]` The API documents a maximum of 5. Refusing locally turns a remote
        `SE01` — which says only "incorrect query request" — into something an operator can
        act on."""
        groups = [{"groupName": f"g{n}", "keywords": [f"k{n}"]} for n in range(6)]
        recorder = Recorder(a_trend_response())

        with pytest.raises(AddonConfigInvalid, match="5"):
            load_entry(TREND)(
                recorder.context({**TREND_CONFIG, "keyword_groups": json.dumps(groups)})
            )

    def test_a_valid_configuration_is_not_refused(self) -> None:
        """The positive control. A validator that refused everything would pass above."""
        recorder = Recorder(a_trend_response())

        assert load_entry(TREND)(recorder.context(TREND_CONFIG)).items_emitted == 2


# --------------------------------------------------------------------------- #
# Shopping Insight
# --------------------------------------------------------------------------- #


class TestShoppingInsightComposesItsRequest:
    def test_category_mode_posts_the_documented_body(self) -> None:
        recorder = Recorder(a_trend_response(a_series("스킨케어", category=["50000002"])))

        load_entry(SHOPPING)(recorder.context(SHOPPING_CONFIG))

        assert recorder.endpoints == ["categories"]
        assert recorder.bodies[0] == {
            "startDate": "2026-08-01",
            "endDate": "2026-08-14",
            "timeUnit": "week",
            "category": [{"name": "스킨케어", "param": ["50000002"]}],
        }

    def test_keyword_mode_posts_to_the_other_endpoint_with_its_own_shape(self) -> None:
        """`[확인 사실]` `/shopping/v1/category/keywords` takes a **single** `category`
        string and a `keyword` array, which is a different body from the categories
        endpoint's. Two endpoints, one add-on, because they answer the same question at two
        depths."""
        recorder = Recorder(a_trend_response(a_series("수분크림", keyword=["수분크림"])))

        load_entry(SHOPPING)(
            recorder.context(
                {
                    **SHOPPING_CONFIG,
                    "mode": "keywords",
                    "category": "50000002",
                    "keywords": json.dumps(
                        [{"name": "수분크림", "param": ["수분크림"]}], ensure_ascii=False
                    ),
                }
            )
        )

        assert recorder.endpoints == ["category_keywords"]
        assert recorder.bodies[0]["category"] == "50000002"
        assert recorder.bodies[0]["keyword"] == [{"name": "수분크림", "param": ["수분크림"]}]
        assert "categories" not in recorder.bodies[0]

    def test_keyword_mode_without_a_category_is_refused(self) -> None:
        recorder = Recorder(a_trend_response())

        with pytest.raises(AddonConfigInvalid, match="category"):
            load_entry(SHOPPING)(
                recorder.context(
                    {
                        **SHOPPING_CONFIG,
                        "mode": "keywords",
                        "keywords": json.dumps([{"name": "a", "param": ["a"]}]),
                    }
                )
            )

    def test_a_mode_the_add_on_does_not_implement_is_refused_by_name(self) -> None:
        recorder = Recorder(a_trend_response())

        with pytest.raises(AddonConfigInvalid, match="mode"):
            load_entry(SHOPPING)(recorder.context({**SHOPPING_CONFIG, "mode": "device"}))

    def test_more_than_three_categories_is_refused(self) -> None:
        """`[확인 사실]` The API documents a maximum of 3 category pairs."""
        categories = [{"name": f"c{n}", "param": [str(n)]} for n in range(4)]
        recorder = Recorder(a_trend_response())

        with pytest.raises(AddonConfigInvalid, match="3"):
            load_entry(SHOPPING)(
                recorder.context({**SHOPPING_CONFIG, "categories": json.dumps(categories)})
            )


class TestShoppingInsightUnrollsThePoints:
    def test_it_emits_one_item_per_series_and_period(self) -> None:
        recorder = Recorder(
            a_trend_response(
                a_series("스킨케어", category=["50000002"]),
                a_series("메이크업", category=["50000003"]),
            )
        )

        outcome = load_entry(SHOPPING)(recorder.context(SHOPPING_CONFIG))

        assert outcome.items_emitted == 4

    def test_the_item_carries_the_dimension_it_measured(self) -> None:
        """DP-021 D2: a reader of one row needs to know whether the ratio counts searches,
        category clicks, or keyword clicks within a category."""
        recorder = Recorder(a_trend_response(a_series("스킨케어", category=["50000002"])))

        load_entry(SHOPPING)(recorder.context(SHOPPING_CONFIG))

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "shopping_category"

    def test_keyword_mode_records_a_different_dimension(self) -> None:
        recorder = Recorder(a_trend_response(a_series("수분크림", keyword=["수분크림"])))

        load_entry(SHOPPING)(
            recorder.context(
                {
                    **SHOPPING_CONFIG,
                    "mode": "keywords",
                    "category": "50000002",
                    "keywords": json.dumps([{"name": "수분크림", "param": ["수분크림"]}]),
                }
            )
        )

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "shopping_keyword"

    def test_search_trend_records_its_own_dimension(self) -> None:
        """The control for the two above: three dimensions, three add-on paths, and none of
        them may report another's."""
        recorder = Recorder(a_trend_response())

        load_entry(TREND)(recorder.context(TREND_CONFIG))

        assert json.loads(recorder.emitted[0].payload)["dimension"] == "search_keyword"
