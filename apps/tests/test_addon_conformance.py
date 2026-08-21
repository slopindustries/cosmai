"""``addon_kit.conformance``: the suite an author runs against any add-on.

New in M3 batch 3c, not copy-adapted — `addon_kit/conformance.py`'s own module
docstring explains why P0 has no conformance-suite module to copy from (it named the
work and deliberately deferred it, and nothing in the P0 tree ever built it as a
runnable tool). These tests are this module's own acceptance evidence: manifest
validity, the contract-range gate, kind-capability conformance through one harness
run, the cursor resume scenario, and the deliberate absence of a determinism check
(DP-030 D1).
"""

from __future__ import annotations

from pathlib import Path

from addon_api import SnapshotItem
from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.generator import new_addon
from addon_kit.harness import load_fixtures


def write_fixture(directory: Path, name: str, body: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(body)
    return path


def write_addon(directory: Path, kind: str, body: str, addon_id: str = "probe.addon") -> Path:
    target = new_addon(addon_id, kind, directory)  # type: ignore[arg-type]
    (target / "handler.py").write_text(body, encoding="utf-8")
    return target


class TestAGeneratedCollectorIsConformant:
    """The template's own acceptance test, one level above `test_addon_kit.py`'s: not
    just "does it run once" but "does it pass every check this module offers"."""

    def test_every_check_passes(self, tmp_path: Path) -> None:
        addon = new_addon("collector.conformant", "collector", tmp_path / "a")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}').parent
        )

        report = run_conformance(addon, fixtures=fixtures, config={"base_path": "items"})

        assert report.passed, format_conformance_report(report)
        names = [check.name for check in report.checks]
        assert names == [
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
            "kind_capability_conformance",
            "cursor_resume_scenario",
        ]
        assert all(check.passed for check in report.checks)

    def test_the_report_names_the_addon(self, tmp_path: Path) -> None:
        addon = new_addon("collector.named", "collector", tmp_path / "a")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}').parent
        )

        report = run_conformance(addon, fixtures=fixtures, config={"base_path": "items"})

        assert report.addon_id == "collector.named"


class TestManifestValidity:
    def test_an_invalid_manifest_fails_the_first_check_and_stops(self, tmp_path: Path) -> None:
        target = tmp_path / "bad"
        target.mkdir()
        (target / "addon.toml").write_text("[addon\nid = 'broken'\n", encoding="utf-8")

        report = run_conformance(target)

        assert not report.passed
        assert report.addon_id is None
        assert [check.name for check in report.checks] == ["manifest_is_valid"]
        assert not report.checks[0].passed


class TestContractRangeConformance:
    def test_a_manifest_requiring_an_unsupported_range_fails_and_stops(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "a"
        target.mkdir()
        (target / "addon.toml").write_text(
            """
[addon]
id = "collector.future"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=99.0"

[config]
schema_version = "1"

[declares]
hosts = ["api.example.com"]
endpoints = ["items"]
""",
            encoding="utf-8",
        )
        (target / "handler.py").write_text("def run(context):\n    return None\n", encoding="utf-8")

        report = run_conformance(target)

        assert not report.passed
        names = [check.name for check in report.checks]
        assert names == ["manifest_is_valid", "contract_range_is_satisfiable"]
        assert not report.checks[-1].passed
        assert "requires" in report.checks[-1].detail

    def test_the_addon_s_module_is_never_imported_when_the_range_fails(
        self, tmp_path: Path
    ) -> None:
        """The same ordering guarantee `addon_host.loading`'s own version gate makes:
        a range failure must not have run the module on the way to being refused."""
        target = tmp_path / "a"
        target.mkdir()
        (target / "addon.toml").write_text(
            """
[addon]
id = "collector.future"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=99.0"

[config]
schema_version = "1"
""",
            encoding="utf-8",
        )
        (target / "handler.py").write_text(
            "from pathlib import Path\n"
            "Path(__file__).with_name('imported').write_text('yes')\n"
            "def run(context):\n"
            "    return None\n",
            encoding="utf-8",
        )

        run_conformance(target)

        assert not (target / "imported").exists()


class TestKindCapabilityConformance:
    def test_an_addon_that_raises_fails_this_check(self, tmp_path: Path) -> None:
        body = (
            "from addon_api.context import CollectContext\n"
            "from addon_api.errors import AddonPermanent\n"
            "from addon_api.results import CollectOutcome\n\n\n"
            "def run(context: CollectContext) -> CollectOutcome:\n"
            "    raise AddonPermanent('always broken')\n"
        )
        addon = write_addon(tmp_path / "a", "collector", body)

        report = run_conformance(addon, config={"base_path": "items"})

        assert not report.passed
        by_name = {check.name: check for check in report.checks}
        assert not by_name["kind_capability_conformance"].passed
        assert "AddonPermanent" in by_name["kind_capability_conformance"].detail

    def test_a_miscounting_addon_fails_this_check(self, tmp_path: Path) -> None:
        body = (
            "from addon_api.context import CollectContext\n"
            "from addon_api.results import CollectOutcome, RawItem\n\n\n"
            "def run(context: CollectContext) -> CollectOutcome:\n"
            "    context.emit_raw([RawItem('a', b'1', 'application/json')])\n"
            "    return CollectOutcome(items_emitted=99)\n"
        )
        addon = write_addon(tmp_path / "a", "collector", body)

        report = run_conformance(addon, config={"base_path": "items"})

        assert not report.passed
        by_name = {check.name: check for check in report.checks}
        assert not by_name["kind_capability_conformance"].passed
        assert "disagrees" in by_name["kind_capability_conformance"].detail

    def test_a_missing_required_field_fails_at_entry_resolution(self, tmp_path: Path) -> None:
        """The harness validates configuration exactly as the host does — `addon_kit
        run`'s own tests already pin this; `entry_is_resolvable` is where it surfaces
        here, because the harness refuses before the entry point is even called."""
        addon = new_addon("collector.needsconfig", "collector", tmp_path / "a")

        report = run_conformance(addon, config={})

        assert not report.passed
        by_name = {check.name: check for check in report.checks}
        assert not by_name["entry_is_resolvable"].passed


class TestTheCursorResumeScenario:
    def test_an_addon_that_rejects_its_own_cursor_fails_resume(self, tmp_path: Path) -> None:
        body = '''
from addon_api.context import CollectContext
from addon_api.errors import AddonPermanent
from addon_api.results import CollectOutcome


def run(context: CollectContext) -> CollectOutcome:
    if context.cursor is not None:
        raise AddonPermanent("cannot resume")
    context.fetch("items", {})
    context.advance_cursor("items", {"page": 2})
    return CollectOutcome(items_emitted=0)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}').parent
        )

        report = run_conformance(addon, fixtures=fixtures, config={"base_path": "items"})

        assert not report.passed
        by_name = {check.name: check for check in report.checks}
        assert not by_name["cursor_resume_scenario"].passed
        assert "cannot resume" in by_name["cursor_resume_scenario"].detail

    def test_an_addon_that_advances_no_cursor_is_not_failed_for_it(self, tmp_path: Path) -> None:
        """The positive control: a declared stream that this particular run never
        advanced is "nothing to resume from", not a failure."""
        body = '''
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome


def run(context: CollectContext) -> CollectOutcome:
    context.fetch("items", {})
    return CollectOutcome(items_emitted=0)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}').parent
        )

        report = run_conformance(addon, fixtures=fixtures, config={"base_path": "items"})

        by_name = {check.name: check for check in report.checks}
        assert by_name["cursor_resume_scenario"].passed

    def test_a_normalizer_gets_no_resume_check(self, tmp_path: Path) -> None:
        """Nothing to resume from: a normalizer holds no cursor at all."""
        addon = new_addon("normalizer.conformant", "normalizer", tmp_path / "a")
        snapshot = [
            SnapshotItem(item_key="a", payload=b'{"x": 1}', content_type="application/json")
        ]

        report = run_conformance(addon, snapshot=snapshot, config={"strict": False})

        assert report.passed
        assert "cursor_resume_scenario" not in {check.name for check in report.checks}


class TestDeterminismIsDeliberatelyNotChecked:
    """DP-030 D1. A normalizer that produces different output on two runs still
    passes — the obligation was struck down at the contract level, and a generic
    conformance suite re-imposing it would be the exact thing the decision forbids.
    """

    def test_a_non_deterministic_normalizer_still_passes(self, tmp_path: Path) -> None:
        body = '''
import random

from addon_api.context import NormalizeContext
from addon_api.results import NormalizedResult, NormalizeOutcome


def run(context: NormalizeContext) -> NormalizeOutcome:
    results = [
        NormalizedResult(source_item_key=item.item_key, body={"roll": random.random()})
        for item in context.read_snapshot()
    ]
    context.emit_result(results)
    return NormalizeOutcome(results_emitted=len(results))
'''
        addon = write_addon(tmp_path / "a", "normalizer", body, addon_id="normalizer.random")
        snapshot = [SnapshotItem(item_key="a", payload=b"{}", content_type="application/json")]

        report = run_conformance(addon, snapshot=snapshot)

        assert report.passed, format_conformance_report(report)
        by_name = {check.name: check for check in report.checks}
        assert by_name["kind_capability_conformance"].passed


class TestTheReportFormat:
    def test_a_passing_report_reads_conformant(self, tmp_path: Path) -> None:
        addon = new_addon("collector.formatted", "collector", tmp_path / "a")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}').parent
        )
        report = run_conformance(addon, fixtures=fixtures, config={"base_path": "items"})

        text = format_conformance_report(report)

        assert "collector.formatted@0.1.0" in text
        assert "CONFORMANT" in text
        assert "NOT CONFORMANT" not in text

    def test_a_failing_report_reads_not_conformant(self, tmp_path: Path) -> None:
        target = tmp_path / "bad"
        target.mkdir()
        (target / "addon.toml").write_text("not toml at all [[[", encoding="utf-8")

        report = run_conformance(target)

        text = format_conformance_report(report)
        assert "NOT CONFORMANT" in text
        assert "[FAIL]" in text


class TestTheCliWiring:
    def test_run_conformance_exits_zero_on_a_conformant_addon(self, tmp_path: Path) -> None:
        from addon_kit.__main__ import main

        addon = new_addon("collector.cli", "collector", tmp_path / "a")
        write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}')

        exit_code = main(
            [
                "run",
                str(addon),
                "--conformance",
                "--fixtures",
                str(tmp_path / "fx"),
                "--config",
                '{"base_path": "items"}',
            ]
        )

        assert exit_code == 0

    def test_run_conformance_exits_nonzero_on_a_bad_manifest(self, tmp_path: Path) -> None:
        from addon_kit.__main__ import main

        target = tmp_path / "bad"
        target.mkdir()
        (target / "addon.toml").write_text("not toml [[[", encoding="utf-8")

        exit_code = main(["run", str(target), "--conformance"])

        assert exit_code == 1

    def test_an_ordinary_run_is_unaffected_by_the_new_flag(self, tmp_path: Path) -> None:
        """The positive control: --conformance is opt-in, not a change to the default
        `addon_kit run` path `test_addon_kit.py` already pins."""
        from addon_kit.__main__ import main

        addon = new_addon("collector.ordinary", "collector", tmp_path / "a")
        write_fixture(tmp_path / "fx", "items.1.json", b'{"data": [1]}')

        exit_code = main(
            [
                "run",
                str(addon),
                "--fixtures",
                str(tmp_path / "fx"),
                "--config",
                '{"base_path": "items"}',
            ]
        )

        assert exit_code == 0
