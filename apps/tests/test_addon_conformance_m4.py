"""`addon_kit.conformance` run against this batch's two installed add-ons.

New for M4: `tests/test_addon_conformance.py` (M3 batch 3c) is the conformance module's own
acceptance evidence, built against generated probe add-ons in `tmp_path`. This file is the
next layer up — the same suite run against the two real add-ons this batch ships,
`apps/addons/importer.local.jsonl` and `apps/addons/normalizer.obf.product` — so a report
that either is conformant is the harness's own transcript, not an inference from the
handler-level test files' passing.
"""

from __future__ import annotations

from pathlib import Path

from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.harness import load_fixtures

ADDONS_ROOT = Path(__file__).resolve().parents[1] / "addons"
IMPORTER_ROOT = ADDONS_ROOT / "importer.local.jsonl"
NORMALIZER_ROOT = ADDONS_ROOT / "normalizer.obf.product"

GOOD_ROW = '{"id": "p-1", "title": "hello"}'


def write_rows_fixture(directory: Path, *lines: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "rows.1.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return directory


class TestImporterLocalJsonlIsConformant:
    def test_every_check_passes(self, tmp_path: Path) -> None:
        fixtures = load_fixtures(write_rows_fixture(tmp_path / "fx", GOOD_ROW))

        report = run_conformance(
            IMPORTER_ROOT, fixtures=fixtures, config={"key_field": "id"}
        )

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "importer.local.jsonl"
        names = [check.name for check in report.checks]
        assert names == [
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
            "kind_capability_conformance",
            "cursor_resume_scenario",
        ]

    def test_a_row_missing_the_key_field_still_conforms(self, tmp_path: Path) -> None:
        """Conformance is about the contract being honoured, not about every row
        being usable — `importer.local.jsonl` skipping a keyless row and reporting it in
        `notes` is the add-on doing its job, not failing it."""
        fixtures = load_fixtures(
            write_rows_fixture(tmp_path / "fx", GOOD_ROW, '{"title": "no id here"}')
        )

        report = run_conformance(
            IMPORTER_ROOT, fixtures=fixtures, config={"key_field": "id"}
        )

        assert report.passed, format_conformance_report(report)

    def test_a_missing_key_field_configuration_fails_conformance(self, tmp_path: Path) -> None:
        fixtures = load_fixtures(write_rows_fixture(tmp_path / "fx", GOOD_ROW))

        report = run_conformance(IMPORTER_ROOT, fixtures=fixtures, config={})

        assert not report.passed
        assert [check.name for check in report.checks] == [
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
        ]
        assert not report.checks[-1].passed


class TestNormalizerObfProductIsConformant:
    def test_every_check_passes(self) -> None:
        report = run_conformance(NORMALIZER_ROOT)

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "normalizer.obf.product"
        # A normalizer declares no stream, so the cursor-resume check never runs —
        # `run_conformance`'s own docstring: "a normalizer, or a stream-less add-on, does
        # not [get it], because there is nothing to resume from."
        names = [check.name for check in report.checks]
        assert names == [
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
            "kind_capability_conformance",
        ]

    def test_it_conforms_against_a_real_shaped_snapshot(self) -> None:
        """The empty-snapshot run above proves the contract shapes hold; this one proves
        the same against a structurally realistic Open Beauty Facts row (DP-022)."""
        from addon_api import SnapshotItem

        row = (
            b'{"code": "8801234567890", "product_name": "Example Cream", '
            b'"brands_tags": ["brand-alpha"], "ingredients_text": "aqua", '
            b'"last_modified_t": 1735689600}'
        )
        snapshot = [
            SnapshotItem(item_key="8801234567890", payload=row, content_type="application/json")
        ]

        report = run_conformance(NORMALIZER_ROOT, snapshot=snapshot, config={"language": "en"})

        assert report.passed, format_conformance_report(report)
