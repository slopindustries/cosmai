"""`collector.naver.datalab` and `normalizer.naver.trend` as *installed* add-ons.

Two things `test_collector_naver_datalab.py` and `test_normalizer_naver_trend.py` do not
check, because both load the entry point directly from `handler.py` by file path: that the
real `apps/addons/` directory (`addon_host`'s `DEFAULT_ADDON_DIR`) actually discovers,
parses, and registers both manifests without a database — and that each passes
`addon_kit.conformance`'s generic suite (manifest validity, the contract-range gate,
kind-capability conformance through one harness run, and the cursor-resume scenario for the
collector).

No database is needed for either: discovery/registration is local and synchronous
(`addon_host.registration.install_addons`, the same call a real process makes at start, with
`capabilities_not_bound` standing in for the capability layer this file has no need to
bind), and `addon_kit.conformance` is built on `addon_kit.harness` alone, never `addon_host`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from addon_api import CONTRACT_VERSION, SnapshotItem
from addon_host import DEFAULT_ADDON_DIR
from addon_host.loading import load_addons
from addon_host.registration import HANDLER_PREFIX, install_addons
from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.harness import load_fixtures
from platform_core.jobs.registry import HandlerRegistry

ADDONS_ROOT = Path(__file__).resolve().parents[1] / "addons"
COLLECTOR_ROOT = ADDONS_ROOT / "collector.naver.datalab"
NORMALIZER_ROOT = ADDONS_ROOT / "normalizer.naver.trend"


def write_fixture(directory: Path, name: str, body: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def a_datalab_fixture(**series_extra: Any) -> dict[str, Any]:
    series: dict[str, Any] = {
        "title": "수분크림",
        "keywords": ["수분크림"],
        "data": [{"period": "2026-08-01", "ratio": 100.0}],
    }
    series.update(series_extra)
    return {
        "startDate": "2026-08-01",
        "endDate": "2026-08-01",
        "timeUnit": "date",
        "results": [series],
    }


SEARCH_TREND_CONFIG: dict[str, Any] = {
    "mode": "search_trend",
    "start_date": "2026-08-01",
    "end_date": "2026-08-01",
    "time_unit": "date",
    "keyword_groups": json.dumps(
        [{"groupName": "수분크림", "keywords": ["수분크림"]}], ensure_ascii=False
    ),
}


# --------------------------------------------------------------------------- #
# The real apps/addons/ directory — discovery and registration, no database
# --------------------------------------------------------------------------- #


class TestTheRealAddonsDirectoryDiscoversBoth:
    def test_both_addons_live_under_the_default_addon_root(self) -> None:
        assert DEFAULT_ADDON_DIR == ADDONS_ROOT
        assert (COLLECTOR_ROOT / "addon.toml").is_file()
        assert (NORMALIZER_ROOT / "addon.toml").is_file()

    def test_load_addons_parses_both_manifests(self) -> None:
        loaded = {addon.manifest.addon_id: addon for addon in load_addons(ADDONS_ROOT)}

        assert "collector.naver.datalab" in loaded
        assert "normalizer.naver.trend" in loaded
        assert loaded["collector.naver.datalab"].manifest.kind == "collector"
        assert loaded["normalizer.naver.trend"].manifest.kind == "normalizer"

    def test_install_addons_registers_both_under_the_addon_namespace(self) -> None:
        registry = HandlerRegistry()

        installed = install_addons(registry, root=ADDONS_ROOT, contract=CONTRACT_VERSION)

        ids = {addon.manifest.addon_id for addon in installed}
        assert {"collector.naver.datalab", "normalizer.naver.trend"} <= ids
        assert f"{HANDLER_PREFIX}collector.naver.datalab" in registry
        assert f"{HANDLER_PREFIX}normalizer.naver.trend" in registry


# --------------------------------------------------------------------------- #
# addon_kit conformance — the suite an author runs before a host ever sees it
# --------------------------------------------------------------------------- #


class TestCollectorConformance:
    def test_every_check_passes(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fixtures"
        write_fixture(fixtures_dir, "trend.1.json", a_datalab_fixture())

        report = run_conformance(
            COLLECTOR_ROOT, fixtures=load_fixtures(fixtures_dir), config=SEARCH_TREND_CONFIG
        )

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "collector.naver.datalab"
        names = {check.name for check in report.checks}
        assert names == {
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
            "kind_capability_conformance",
            "cursor_resume_scenario",
        }

    def test_shopping_categories_mode_also_conforms(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fixtures"
        write_fixture(
            fixtures_dir,
            "categories.1.json",
            a_datalab_fixture(category=["50000002"]),
        )
        config = {
            "mode": "shopping_categories",
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "time_unit": "date",
            "categories": json.dumps(
                [{"name": "스킨케어", "param": ["50000002"]}], ensure_ascii=False
            ),
        }

        report = run_conformance(
            COLLECTOR_ROOT, fixtures=load_fixtures(fixtures_dir), config=config
        )

        assert report.passed, format_conformance_report(report)


class TestNormalizerConformance:
    def test_every_check_passes(self) -> None:
        snapshot = [
            SnapshotItem(
                item_key="수분크림|2026-08-01",
                payload=json.dumps(
                    {
                        "dimension": "search_keyword",
                        "title": "수분크림",
                        "terms": ["수분크림"],
                        "period": "2026-08-01",
                        "ratio": 100.0,
                        "startDate": "2026-08-01",
                        "endDate": "2026-08-01",
                        "timeUnit": "date",
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                content_type="application/json",
            )
        ]

        report = run_conformance(NORMALIZER_ROOT, snapshot=snapshot, config={"language": "ko"})

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "normalizer.naver.trend"
        # A normalizer holds no cursor, so there is nothing to resume from.
        assert "cursor_resume_scenario" not in {check.name for check in report.checks}
