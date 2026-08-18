"""Tests for `addons/collector.naver.blog`, driven through `addon_kit.harness.run_addon`.

No capture of this source exists yet (see `handler.py`'s module docstring), so these fixtures
are synthetic bodies built to match the vendor docs' documented shape, not replayed real
responses. Three groups of tests exist for a reason beyond coverage:

- The three `[가설]` groups (`TestEmptyPageNotMissingItems`, `TestTotalIsNotTrustedForControl`,
  `TestRateLimitBody`) each encode one of `handler.py`'s three named assumptions, so that a real
  capture either confirms the assumption or fails one of these loudly, naming which assumption
  broke — that is the point of writing them down as separate, named groups rather than folding
  them into the general pagination tests.
- `TestErrorDetailDirect` bypasses `run_addon` on purpose. `addon_kit.harness._Recorder.fetch`
  hardcodes every response's headers to one `content-type` entry (see `addon_kit/harness.py`),
  so a `Retry-After` header cannot be produced through the harness at all, and `status` is fixed
  for an entire `run_addon` call, so a single run cannot script "page 1 succeeds, page 2 gets a
  429" either. `FetchResponse` is a plain, callable-free dataclass, so it can be built directly
  to exercise what the harness cannot.

Positive controls sit beside the assertions they guard, not in a separate section, because the
point of a positive control is that it fails if the assertion next to it stops meaning anything.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from addon_api import (
    AddonConfigInvalid,
    AddonPermanent,
    AddonTransient,
    CollectOutcome,
    FetchResponse,
)
from addon_kit.harness import HarnessError, load_fixtures, run_addon

ADDON_DIR = Path(__file__).resolve().parents[1] / "addons" / "collector.naver.blog"


def write_fixture(directory: Path, name: str, body: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def blog_item(n: int) -> dict[str, str]:
    return {
        "title": f"Post {n}",
        "link": f"https://blog.example/post/{n}",
        "description": f"Description {n}",
        "bloggername": "Example Blog",
        "bloggerlink": "https://blog.example",
        "postdate": "20260101",
    }


def page(
    items: list[dict[str, str]], *, total: int, start: int, display: int
) -> dict[str, Any]:
    return {
        "lastBuildDate": "Tue, 18 Aug 2026 00:00:00 +0900",
        "total": total,
        "start": start,
        "display": display,
        "items": items,
    }


def make_config(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {"query": "kimchi", "display": 10}
    base.update(overrides)
    return base


def fetch_calls(result: Any) -> list[Any]:
    return [interaction for interaction in result.interactions if interaction.kind == "fetch"]


def _load_handler_module() -> ModuleType:
    """Import `handler.py` by path, bypassing `run_addon` and its context entirely.

    Used only by `TestErrorDetailDirect`, to call `_header` and `_parse_page` directly against a
    hand-built `FetchResponse` the harness cannot produce.
    """
    spec = importlib.util.spec_from_file_location(
        "collector_naver_blog_handler_direct", ADDON_DIR / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPagination:
    def test_a_single_page_of_results_still_costs_a_second_request_to_confirm_exhaustion(
        self, tmp_path: Path
    ) -> None:
        """`total: 2` never licenses stopping after one page.

        See `TestTotalIsNotTrustedForControl`.
        """
        fx = tmp_path / "fx"
        write_fixture(
            fx, "blog.1.json", page([blog_item(1), blog_item(2)], total=2, start=1, display=10)
        )
        write_fixture(fx, "blog.2.json", page([], total=2, start=11, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config())
        assert not result.failed
        assert [item.item_key for item in result.raw_items] == [
            "https://blog.example/post/1", "https://blog.example/post/2"
        ]
        assert len(fetch_calls(result)) == 2
        assert result.cursors["items"] == 11
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.more_available is False
        assert result.outcome.notes["stopped_reason"] == "empty_page"
        assert not result.emitted_count_disagrees()

    def test_pagination_advances_start_by_display_across_several_pages(
        self, tmp_path: Path
    ) -> None:
        fx = tmp_path / "fx"
        write_fixture(
            fx, "blog.1.json", page([blog_item(1), blog_item(2)], total=4, start=1, display=2)
        )
        write_fixture(
            fx, "blog.2.json", page([blog_item(3), blog_item(4)], total=4, start=3, display=2)
        )
        write_fixture(fx, "blog.3.json", page([], total=4, start=5, display=2))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config(display=2))
        assert not result.failed
        calls = fetch_calls(result)
        assert [call.detail["params"]["start"] for call in calls] == ["1", "3", "5"]
        assert len(result.raw_items) == 4

    def test_a_result_missing_its_documented_link_field_is_a_permanent_failure(
        self, tmp_path: Path
    ) -> None:
        broken = {"title": "no link", "description": "d", "bloggername": "b",
                  "bloggerlink": "x", "postdate": "20260101"}
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([broken], total=1, start=1, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config())
        assert result.failed
        assert isinstance(result.failure, AddonPermanent)

    def test_a_raw_item_s_key_is_the_post_link_and_carries_the_page_s_envelope_ref(
        self, tmp_path: Path
    ) -> None:
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([blog_item(7)], total=1, start=1, display=10))
        write_fixture(fx, "blog.2.json", page([], total=1, start=11, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config())
        assert not result.failed
        [raw] = result.raw_items
        assert raw.item_key == "https://blog.example/post/7"
        assert raw.envelope_ref == "harness:blog.1.json"
        assert raw.content_type == "application/json"
        assert json.loads(raw.payload)["postdate"] == "20260101"


class TestEmptyPageNotMissingItems:
    """`[가설]` 1: `start` past the result pool returns `200` with `items: []`, not a missing
    key."""

    def test_an_empty_items_array_is_a_clean_stop_not_a_failure(self, tmp_path: Path) -> None:
        """The assumed case. See `TestPagination` for the full run this feeds into."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([], total=0, start=1, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config())
        assert not result.failed
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 0

    def test_a_200_body_missing_the_items_key_is_a_malformed_body_not_an_empty_page(
        self, tmp_path: Path
    ) -> None:
        """Positive control for the assumption: if the docs are wrong about this, this fails
        loudly naming assumption 1, instead of the collector silently treating "no key" the
        same as "empty array" and reporting a clean, wrong, zero-item stop."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json",
                      {"lastBuildDate": "x", "total": 5, "start": 1, "display": 10})
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config())
        assert result.failed
        assert isinstance(result.failure, AddonPermanent)
        assert "assumption 1" in result.failure.summary

    def test_a_200_body_that_is_not_valid_json_is_also_a_malformed_body(
        self, tmp_path: Path
    ) -> None:
        fx = tmp_path / "fx"
        fx.mkdir()
        (fx / "blog.1.json").write_text("not json {", encoding="utf-8")
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config())
        assert result.failed
        assert isinstance(result.failure, AddonPermanent)


class TestTotalIsNotTrustedForControl:
    """`[가설]` 2: `total` can drift between calls of the same query and must not drive the loop."""

    def test_a_total_that_shrinks_between_pages_does_not_stop_pagination_early(
        self, tmp_path: Path
    ) -> None:
        """`total` goes 5000 -> 2 -> 500 across three calls. An implementation that trusted
        `total` for termination could stop after page 1 (thinking `start` already exceeds a
        smaller `total` seen later) or loop forever chasing a moving target; this add-on
        notices neither, because it never reads `total` for control flow."""
        fx = tmp_path / "fx"
        write_fixture(
            fx, "blog.1.json", page([blog_item(1), blog_item(2)], total=5000, start=1, display=2)
        )
        write_fixture(
            fx, "blog.2.json", page([blog_item(3), blog_item(4)], total=2, start=3, display=2)
        )
        write_fixture(fx, "blog.3.json", page([], total=500, start=5, display=2))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx), config=make_config(display=2))
        assert not result.failed
        assert len(result.raw_items) == 4
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 4
        # `total` is logged, not enforced: the last-seen value survives into notes untouched.
        assert result.outcome.notes["last_observed_total"] == 500
        assert not result.emitted_count_disagrees()

    def test_total_reported_as_zero_on_a_nonempty_page_does_not_stop_the_run(
        self, tmp_path: Path
    ) -> None:
        """Positive control: if `total` *were* driving termination, `total: 0` alongside real
        items would be a direct contradiction an implementation might resolve by stopping. This
        one keeps going, because `items` is the only signal it reads."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([blog_item(1)], total=0, start=1, display=10))
        write_fixture(fx, "blog.2.json", page([], total=0, start=11, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config())
        assert not result.failed
        assert len(fetch_calls(result)) == 2
        assert len(result.raw_items) == 1


class TestStartCeiling:
    """`[확인 사실]` `start` is capped at 1000; this source cannot be exhaustively collected
    past that, and the add-on must stop cleanly there rather than loop or request an invalid
    `start`."""

    def test_the_ceiling_stops_the_run_before_a_further_request_is_made(
        self, tmp_path: Path
    ) -> None:
        items = [blog_item(i) for i in range(100)]
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page(items, total=5000, start=951, display=100))
        result = run_addon(
            ADDON_DIR, fixtures=load_fixtures(fx), config=make_config(display=100), cursor=951
        )
        assert not result.failed
        assert len(fetch_calls(result)) == 1
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.notes["stopped_reason"] == "start_ceiling"
        assert result.outcome.more_available is False

    def test_start_1000_is_still_a_legal_request_only_the_next_page_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Positive control for the ceiling test: proves the guard is `> 1000`, not `>= 951` or
        some other accidental early cutoff, by fetching the last legal `start` itself."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([blog_item(1)], total=1, start=1000, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config(display=10), cursor=1000)
        assert not result.failed
        calls = fetch_calls(result)
        assert len(calls) == 1
        assert calls[0].detail["params"]["start"] == "1000"
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.notes["stopped_reason"] == "start_ceiling"

    def test_pagination_is_not_simply_stopping_after_one_call_in_general(
        self, tmp_path: Path
    ) -> None:
        """Positive control for both tests above: away from the ceiling, a second call does
        happen, so "only one fetch" up there is the ceiling doing something, not a collector
        that never paginates at all."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([blog_item(1)], total=1, start=1, display=10))
        write_fixture(fx, "blog.2.json", page([], total=1, start=11, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config())
        assert len(fetch_calls(result)) == 2


class TestRateLimitBody:
    """`[가설]` 3: a 429's body shape and `Retry-After` header are both unreliable, so
    classification never depends on either. See `TestErrorDetailDirect` for what the harness
    cannot exercise about this."""

    def test_a_429_with_an_unparseable_body_is_still_transient(self, tmp_path: Path) -> None:
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", {"whatever": "shape"})
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config(), status=429)
        assert result.failed
        assert isinstance(result.failure, AddonTransient)


class TestDocumentedErrorStatuses:
    """`SE01-SE06`/`SE99`/`429` from the API docs, mapped to the class that decides retry."""

    @pytest.mark.parametrize(
        ("status", "expected_class"),
        [
            (400, AddonPermanent),   # SE01/SE02/SE04/SE06 — collapsed; see handler.py comment
            (404, AddonPermanent),   # SE05: bad endpoint
            (429, AddonTransient),   # RPS exceeded
            (500, AddonTransient),   # SE99: server error
            (401, AddonConfigInvalid),  # undocumented for this endpoint; general project mapping
            (403, AddonConfigInvalid),
        ],
    )
    def test_status_maps_to_the_documented_retry_class(
        self, tmp_path: Path, status: int, expected_class: type[Exception]
    ) -> None:
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", {"errorMessage": "boom", "errorCode": f"SE-{status}"})
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config(), status=status)
        assert result.failed
        assert isinstance(result.failure, expected_class)
        assert result.failure.detail is not None
        assert result.failure.detail["status"] == status

    def test_different_statuses_are_not_collapsed_into_one_class(self, tmp_path: Path) -> None:
        """Positive control for the parametrization above: proves the classifier discriminates
        rather than raising one constant class regardless of status."""
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", {})
        transient = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                               config=make_config(), status=500)
        permanent = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                               config=make_config(), status=400)
        assert type(transient.failure) is not type(permanent.failure)


class TestConfigValidation:
    def test_a_missing_query_is_refused_before_the_add_on_is_reached(self) -> None:
        """The host validates stored configuration, so the add-on is never asked.

        Amended 2026-08-18. This first asserted the *add-on* raised
        `AddonConfigInvalid`, which was true only because the harness was not
        validating configuration at all. It now validates, exactly as the host does,
        so a required field missing never reaches `run`.
        """
        with pytest.raises(HarnessError, match="'query' is required"):
            run_addon(ADDON_DIR, config={})

    def test_the_add_on_still_refuses_a_missing_query_on_its_own(self) -> None:
        """The defensive re-check, reached with validation off.

        Worth keeping and worth testing: the host validates when a source row is
        written, not when a job runs, so a row stored before a schema change can reach
        an add-on stale. `validate=False` is the only way to get there.
        """
        result = run_addon(ADDON_DIR, config={}, validate=False)
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)
        assert fetch_calls(result) == []

    def test_a_blank_query_is_rejected_even_though_required_only_checks_presence(self) -> None:
        """The host's `validate_config` accepts any `str` for a required string field, including
        `""` — this add-on re-checks non-empty itself, the same way the generated skeleton
        re-checks `base_path` despite `required = true`."""
        result = run_addon(ADDON_DIR, config={"query": "   "})
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)

    @pytest.mark.parametrize("display", [0, 101, -5])
    def test_display_outside_the_documented_1_100_range_is_a_config_error(
        self, display: int
    ) -> None:
        result = run_addon(ADDON_DIR, config={"query": "kimchi", "display": display})
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)
        assert fetch_calls(result) == []

    def test_an_unsupported_sort_value_is_a_config_error(self) -> None:
        result = run_addon(ADDON_DIR, config={"query": "kimchi", "sort": "popularity"})
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)

    def test_a_valid_sort_is_forwarded_as_a_request_parameter(self, tmp_path: Path) -> None:
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([], total=0, start=1, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config={"query": "kimchi", "sort": "date"})
        assert not result.failed
        assert fetch_calls(result)[0].detail["params"]["sort"] == "date"


class TestCursor:
    def test_a_resume_cursor_starts_from_where_the_previous_run_stopped(
        self, tmp_path: Path
    ) -> None:
        fx = tmp_path / "fx"
        write_fixture(fx, "blog.1.json", page([], total=0, start=501, display=10))
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(fx),
                            config=make_config(), cursor=501)
        assert not result.failed
        assert fetch_calls(result)[0].detail["params"]["start"] == "501"

    def test_a_cursor_of_the_wrong_shape_fails_rather_than_silently_restarting_at_1(self) -> None:
        """A string cursor is not treated as "no cursor" and restarted from 1 — that would
        silently re-collect from the beginning, which is worse than a loud failure."""
        result = run_addon(ADDON_DIR, config=make_config(), cursor="not-a-start-position")
        assert result.failed
        assert isinstance(result.failure, AddonPermanent)
        assert fetch_calls(result) == []


class TestErrorDetailDirect:
    """Bypasses `run_addon`: see the module docstring for why the harness cannot produce a
    `Retry-After` header or vary `status` within one run."""

    def test_retry_after_is_read_case_insensitively(self) -> None:
        handler = _load_handler_module()
        response = FetchResponse(
            endpoint_ref="blog", status=429, headers={"Retry-After": "30"},
            body=b"{}", envelope_ref="ref", retrieved_at="t",
        )
        assert handler._header(response.headers, "retry-after") == "30"

    def test_absence_of_retry_after_is_not_invented(self) -> None:
        """Positive control for the case-insensitive lookup: an unrelated header must not match."""
        handler = _load_handler_module()
        response = FetchResponse(
            endpoint_ref="blog", status=429, headers={"content-type": "application/json"},
            body=b"{}", envelope_ref="ref", retrieved_at="t",
        )
        assert handler._header(response.headers, "retry-after") is None

    def test_a_429_s_retry_after_and_error_body_both_reach_the_raised_detail(self) -> None:
        handler = _load_handler_module()
        response = FetchResponse(
            endpoint_ref="blog", status=429, headers={"Retry-After": "5"},
            body=json.dumps({"errorCode": "SE99", "errorMessage": "slow down"}).encode(),
            envelope_ref="ref", retrieved_at="t",
        )
        with pytest.raises(AddonTransient) as excinfo:
            handler._parse_page(response)
        detail = excinfo.value.detail
        assert detail is not None
        assert detail["retry_after"] == "5"
        assert detail["errorCode"] == "SE99"

    def test_a_429_with_neither_body_nor_header_is_still_classified_transient(self) -> None:
        """The other half of assumption 3: absence of both must not block classification."""
        handler = _load_handler_module()
        response = FetchResponse(
            endpoint_ref="blog", status=429, headers={}, body=b"",
            envelope_ref="ref", retrieved_at="t",
        )
        with pytest.raises(AddonTransient) as excinfo:
            handler._parse_page(response)
        assert excinfo.value.detail == {"status": 429}
