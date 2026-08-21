"""`collector.trendradar.rest`: pagination/bucket logic, filters-echo refusal, cursor
resume, conformance, and host-loading.

Fixture bodies below are hand-assembled from the real, committed captures in
`apps/tests/fixtures/public/collector.trendradar.rest/` (see that directory's
`MANIFEST.md` for provenance) rather than replayed byte-for-byte: the live instance
was still collecting while those captures were taken (`/api/v1/health` showed a
`"running"` run), so two live calls a few seconds apart do not make a clean,
deterministic two-page sequence — real field names, value shapes, and the response
envelope are kept; the specific rows in each page are chosen here so a scenario tests
exactly one thing (a short first page, a full first page and a mixed second page,
a silently-dropped filter).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from addon_api import AddonConfigInvalid, AddonPermanent, CollectOutcome
from addon_host.loading import load_addon
from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.harness import load_fixtures, run_addon

APPS_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = APPS_ROOT / "addons" / "collector.trendradar.rest"

RANK_FILTERABLE = ["source", "board", "category_key", "product_key", "captured_at"]
PRICE_FILTERABLE = ["source", "product_key", "captured_at"]
PRODUCT_FILTERABLE = ["source", "product_key"]


def _load_handler_module() -> Any:
    """Load `handler.py` directly, the same way `addon_kit.harness` does.

    For `_Budget`, which is pure add-on-internal bookkeeping with no `CollectContext`
    dependency — testing it this way is cheaper than driving 20+ fixture pages
    through the harness just to observe `context.limits.max_pages` (fixed at 20 by
    `addon_kit.harness.default_limits`) being reached.
    """
    spec = importlib.util.spec_from_file_location(
        "trendradar_handler_under_test", ADDON_DIR / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rank_row(
    product_key: str,
    captured_at: str,
    *,
    rank: int = 1,
    board: str = "sale_rising",
    source: str = "daisomall",
) -> dict[str, Any]:
    return {
        "source": source,
        "board": board,
        "category_key": "CTGR_01050",
        "product_key": product_key,
        "captured_at": captured_at,
        "category_name": "뷰티/위생",
        "rank": rank,
        "product_name": f"product {product_key}",
        "brand": None,
        "price": 1000,
        "discount_rate": None,
        "review_count": 10,
        "review_rating": 4.5,
        "rank_delta": None,
        "is_new": False,
    }


def _price_row(product_key: str, captured_at: str, source: str = "daisomall") -> dict[str, Any]:
    return {
        "source": source,
        "product_key": product_key,
        "captured_at": captured_at,
        "price": 1000,
        "discount_rate": None,
    }


def _product_row(product_key: str, source: str = "daisomall") -> dict[str, Any]:
    return {
        "source": source,
        "product_key": product_key,
        "captured_at": "2026-08-21T02:00:00+00:00",
        "name": f"product {product_key}",
        "brand": None,
        "volume": None,
        "url": None,
        "ingredients": None,
        "first_seen_at": "2026-08-01T00:00:00+00:00",
        "last_seen_at": "2026-08-21T02:00:00+00:00",
    }


def _new_product_row(product_key: str, source: str = "daisomall") -> dict[str, Any]:
    return {
        "source": source,
        "product_key": product_key,
        "captured_at": "2026-08-21T02:00:00+00:00",
        "name": f"new product {product_key}",
        "brand": None,
        "listed_at": None,
    }


def _records_body(
    table: str,
    *,
    filterable: list[str],
    filters: dict[str, str],
    rows: list[dict[str, Any]],
    limit: int,
    offset: int = 0,
    total: int | None = None,
) -> dict[str, Any]:
    return {
        "table": table,
        "filterable": filterable,
        "filters": filters,
        "total": total if total is not None else len(rows),
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }


def _runs_body(entries: list[tuple[str, str]]) -> dict[str, Any]:
    """`(captured_at, sources_csv)` pairs, wrapped in the documented `/api/v1/runs` shape."""
    return {
        "runs": [
            {
                "id": f"11111111-1111-1111-1111-{index:012d}",
                "captured_at": captured_at,
                "started_at": captured_at,
                "finished_at": captured_at,
                "status": "ok",
                "sources": sources_csv,
                "datasets": "ranking",
                "note": None,
                "requests": 1,
                "records": 1,
                "retries": 0,
                "source_count": len(sources_csv.split(",")),
                "not_ok": 0,
            }
            for index, (captured_at, sources_csv) in enumerate(entries, start=1)
        ]
    }


def _write_pages(directory: Path, endpoint: str, bodies: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, body in enumerate(bodies, start=1):
        (directory / f"{endpoint}.{index}.json").write_text(json.dumps(body), encoding="utf-8")


class TestHostLoading:
    def test_the_real_addon_loads_through_the_host(self) -> None:
        loaded = load_addon(ADDON_DIR / "addon.toml")
        assert loaded.manifest.addon_id == "collector.trendradar.rest"
        assert loaded.manifest.kind == "collector"
        assert loaded.manifest.declares.needs_credential is False
        assert loaded.manifest.declares.streams == ("buckets",)
        assert callable(loaded.entry)


class TestBudget:
    def test_spend_advances_and_exhausted_trips_at_the_bound(self) -> None:
        handler = _load_handler_module()
        budget = handler._Budget(2)
        assert not budget.exhausted
        budget.spend()
        assert not budget.exhausted
        budget.spend()
        assert budget.exhausted


class TestHourBucketFirstRun:
    def test_a_short_first_page_is_emitted_whole_and_advances_the_cursor(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall,glowpick")])],
        )
        rows = [
            _rank_row("1083245", "2026-08-21T02:00:00+00:00", rank=3),
            _rank_row("1017947", "2026-08-21T02:00:00+00:00", rank=2),
            _rank_row("1083259", "2026-08-21T02:00:00+00:00", rank=1),
        ]
        _write_pages(
            fixtures_dir,
            "records_rank_snapshot",
            [
                _records_body(
                    "rank_snapshot",
                    filterable=RANK_FILTERABLE,
                    filters={"source": "daisomall"},
                    rows=rows,
                    limit=10,
                    total=3,
                )
            ],
        )

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={
                "tables": "rank_snapshot",
                "sources": "daisomall",
                "page_limit": 10,
                "runs_lookback": 5,
            },
        )

        assert not result.failed, result.failure
        assert not result.emitted_count_disagrees()
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 3
        assert len(result.raw_items) == 3
        keys = sorted(item.item_key for item in result.raw_items)
        assert keys == [
            "rank_snapshot|daisomall|sale_rising|CTGR_01050|1017947|2026-08-21T02:00:00+00:00",
            "rank_snapshot|daisomall|sale_rising|CTGR_01050|1083245|2026-08-21T02:00:00+00:00",
            "rank_snapshot|daisomall|sale_rising|CTGR_01050|1083259|2026-08-21T02:00:00+00:00",
        ]
        for item in result.raw_items:
            assert item.content_type == "application/json"
            payload = json.loads(item.payload)
            assert payload["source"] == "daisomall"
        cursor = result.cursors["buckets"]
        assert cursor["hour_bucket"]["rank_snapshot"]["daisomall"] == "2026-08-21T02:00:00+00:00"


class TestHourBucketSkipAndResume:
    def test_no_new_bucket_is_never_fetched(self, tmp_path: Path) -> None:
        """`run_high_water` at or before the stored cursor skips the table+source
        entirely — proven here by supplying *no* `records_rank_snapshot` fixture at
        all: if the skip did not fire, the harness would raise, naming the missing
        fixture, rather than the test silently passing on an empty page."""
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall")])],
        )

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "rank_snapshot", "sources": "daisomall", "page_limit": 10},
            cursor={
                "hour_bucket": {"rank_snapshot": {"daisomall": "2026-08-21T02:00:00+00:00"}},
                "full_scan": {},
            },
        )

        assert not result.failed, result.failure
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 0

    def test_multi_page_catch_up_stops_at_the_known_row_and_keeps_the_newest(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall")])],
        )
        page1 = _records_body(
            "rank_snapshot",
            filterable=RANK_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[
                _rank_row("a", "2026-08-21T02:00:00+00:00", rank=1),
                _rank_row("b", "2026-08-21T02:00:00+00:00", rank=2),
                _rank_row("c", "2026-08-21T02:00:00+00:00", rank=3),
            ],
            limit=3,
            offset=0,
            total=5,
        )
        page2 = _records_body(
            "rank_snapshot",
            filterable=RANK_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[
                _rank_row("d", "2026-08-21T01:00:00+00:00", rank=4),
                _rank_row("e", "2026-08-21T00:00:00+00:00", rank=5),  # == cutoff: excluded
            ],
            limit=3,
            offset=3,
            total=5,
        )
        _write_pages(fixtures_dir, "records_rank_snapshot", [page1, page2])

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "rank_snapshot", "sources": "daisomall", "page_limit": 3},
            cursor={
                "hour_bucket": {"rank_snapshot": {"daisomall": "2026-08-21T00:00:00+00:00"}},
                "full_scan": {},
            },
        )

        assert not result.failed, result.failure
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 4  # page1's 3 + page2's "d"
        cursor = result.cursors["buckets"]
        # the newest row overall (page1) is kept, not page2's "d"
        assert cursor["hour_bucket"]["rank_snapshot"]["daisomall"] == "2026-08-21T02:00:00+00:00"


class TestFiltersEchoRefusal:
    def test_a_silently_dropped_filter_refuses_the_page(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall")])],
        )
        # `board` was requested (boards="sale_rising") but the response echoes only
        # `source` -- a simulated silent drop, since the live target never actually
        # does this for a recognized PK-column key (docs/api.md).
        body = _records_body(
            "rank_snapshot",
            filterable=RANK_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_rank_row("a", "2026-08-21T02:00:00+00:00")],
            limit=10,
        )
        _write_pages(fixtures_dir, "records_rank_snapshot", [body])

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={
                "tables": "rank_snapshot",
                "sources": "daisomall",
                "boards": "sale_rising",
                "page_limit": 10,
            },
        )

        assert result.failed
        assert isinstance(result.failure, AddonPermanent)
        assert "filters" in result.failure.summary
        assert not result.raw_items


class TestFullScanTable:
    def test_full_scan_pages_to_a_short_page_and_records_a_completion_marker(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path / "fx"
        page1 = _records_body(
            "product",
            filterable=PRODUCT_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_product_row("p1"), _product_row("p2")],
            limit=2,
            offset=0,
            total=3,
        )
        page2 = _records_body(
            "product",
            filterable=PRODUCT_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_product_row("p3")],
            limit=2,
            offset=2,
            total=3,
        )
        _write_pages(fixtures_dir, "records_product", [page1, page2])

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "product", "sources": "daisomall", "page_limit": 2},
        )

        assert not result.failed, result.failure
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 3
        cursor = result.cursors["buckets"]
        assert cursor["full_scan"]["product"]["daisomall"] == "1970-01-01T00:00:00Z"
        keys = sorted(item.item_key for item in result.raw_items)
        assert keys == ["product|daisomall|p1", "product|daisomall|p2", "product|daisomall|p3"]

    def test_a_table_without_board_keys_correctly(self, tmp_path: Path) -> None:
        """`price_point` has no `board` column; its natural key is 3 columns."""
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall")])],
        )
        body = _records_body(
            "price_point",
            filterable=PRICE_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_price_row("p1", "2026-08-21T02:00:00+00:00")],
            limit=10,
        )
        _write_pages(fixtures_dir, "records_price_point", [body])

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "price_point", "sources": "daisomall", "page_limit": 10},
        )

        assert not result.failed, result.failure
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 1
        assert result.raw_items[0].item_key == "price_point|daisomall|p1|2026-08-21T02:00:00+00:00"


class TestSourceDiscovery:
    def test_sources_are_discovered_when_not_configured(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fx"
        _write_pages(fixtures_dir, "sources", [{"sources": ["daisomall"]}])
        # No `runs` fixture: `new_product` is a full-scan table, so the runs-based
        # discovery is never called for this table selection -- its absence is part
        # of what this test proves.
        body = _records_body(
            "new_product",
            filterable=PRODUCT_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_new_product_row("np1")],
            limit=10,
        )
        _write_pages(fixtures_dir, "records_new_product", [body])

        result = run_addon(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "new_product", "page_limit": 10},
        )

        assert not result.failed, result.failure
        assert isinstance(result.outcome, CollectOutcome)
        assert result.outcome.items_emitted == 1
        assert result.outcome.notes["sources"] == ["daisomall"]


class TestConfigValidation:
    @pytest.mark.parametrize(
        "config",
        [
            {"tables": "not_a_real_table"},
            {"tables": "rank_snapshot", "page_limit": 0},
            {"tables": "rank_snapshot", "page_limit": 1001},
            {"tables": "rank_snapshot", "runs_lookback": 0},
            {"tables": "rank_snapshot", "runs_lookback": 201},
        ],
    )
    def test_an_invalid_field_is_refused_as_config_invalid(
        self, tmp_path: Path, config: dict[str, Any]
    ) -> None:
        result = run_addon(ADDON_DIR, fixtures=load_fixtures(tmp_path), config=config)
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)


class TestConformance:
    def test_the_real_addon_is_conformant_including_cursor_resume(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fx"
        _write_pages(
            fixtures_dir,
            "runs",
            [_runs_body([("2026-08-21T02:00:00+00:00", "daisomall")])],
        )
        body = _records_body(
            "rank_snapshot",
            filterable=RANK_FILTERABLE,
            filters={"source": "daisomall"},
            rows=[_rank_row("a", "2026-08-21T02:00:00+00:00")],
            limit=10,
        )
        _write_pages(fixtures_dir, "records_rank_snapshot", [body])

        report = run_conformance(
            ADDON_DIR,
            fixtures=load_fixtures(fixtures_dir),
            config={"tables": "rank_snapshot", "sources": "daisomall", "page_limit": 10},
        )

        assert report.passed, format_conformance_report(report)
        names = [check.name for check in report.checks]
        assert "cursor_resume_scenario" in names
