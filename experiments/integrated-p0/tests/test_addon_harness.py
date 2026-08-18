"""The authoring loop: `addon_kit run`, and the conformance normalizer it runs.

Two things are under test and they are different in kind.

`TestHarness` checks that the loop is honest — that it builds the contract's own
context types, serves fixtures in order, reports what an add-on did, and refuses
rather than inventing data when a fixture is missing. A harness that quietly returned
an empty page would let a paginating add-on look finished while being untested, which
is worse than no harness.

`TestConformanceNormalizer` checks the smallest conforming add-on, and the assertion
that matters is determinism: OQ-003 requires one snapshot to produce byte-identical
output after canonical serialization. That is testable against rules this trivial,
which is exactly why the rules are trivial.

What neither class checks is integration. `addon_kit.harness`'s docstring lists the
four platform behaviours it cannot exercise — the outbound guard, atomicity, retry
and lease, and persistence — and a green run here is not evidence about any of them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from addon_api import (
    AddonConfigInvalid,
    AddonManifest,
    AddonPermanent,
    CollectContext,
    ImportContext,
    NormalizeContext,
    NormalizeOutcome,
    SnapshotItem,
)
from addon_kit.generator import new_addon
from addon_kit.harness import HarnessError, format_report, load_fixtures, run_addon

CONFORMANCE_NORMALIZER = Path(__file__).resolve().parents[1] / "addons" / "normalizer.conformance"


def write_fixture(directory: Path, name: str, body: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def write_addon(directory: Path, kind: str, body: str, addon_id: str = "probe.addon") -> Path:
    """A hand-written add-on, so a test can control exactly what `run` does."""
    target = new_addon(addon_id, kind, directory)  # type: ignore[arg-type]
    (target / "handler.py").write_text(body, encoding="utf-8")
    return target


class TestFixtureLoading:
    def test_fixtures_are_grouped_by_endpoint_in_call_order(self, tmp_path: Path) -> None:
        write_fixture(tmp_path, "items.2.json", {"page": 2})
        write_fixture(tmp_path, "items.1.json", {"page": 1})
        write_fixture(tmp_path, "reviews.1.json", {"page": 1})
        loaded = load_fixtures(tmp_path)
        assert set(loaded) == {"items", "reviews"}
        assert [path.name for path in loaded["items"]] == ["items.1.json", "items.2.json"]

    def test_ten_sorts_after_nine_rather_than_after_one(self, tmp_path: Path) -> None:
        """Call order is numeric. Lexical order would serve page 10 second."""
        for index in (1, 2, 9, 10):
            write_fixture(tmp_path, f"items.{index}.json", {"page": index})
        loaded = load_fixtures(tmp_path)
        assert [path.name for path in loaded["items"]][-1] == "items.10.json"

    def test_a_file_that_is_not_named_like_a_fixture_is_ignored(self, tmp_path: Path) -> None:
        write_fixture(tmp_path, "items.1.json", {"page": 1})
        (tmp_path / "README.md").write_text("notes", encoding="utf-8")
        assert set(load_fixtures(tmp_path)) == {"items"}

    def test_a_missing_directory_is_refused_rather_than_read_as_empty(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(HarnessError, match="does not exist"):
            load_fixtures(tmp_path / "absent")


class TestHarness:
    def test_a_generated_collector_runs_untouched(self, tmp_path: Path) -> None:
        """The template's acceptance test at the contract level.

        If a freshly generated add-on cannot run without being edited, the template is
        wrong. This is not integration evidence — see the module docstring.
        """
        addon = new_addon("collector.generated", "collector", tmp_path / "generated")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", {"data": [1]}).parent
        )
        result = run_addon(addon, fixtures=fixtures, config={"base_path": "items"})
        assert not result.failed
        assert len(result.raw_items) == 1
        assert result.cursors

    def test_the_add_on_receives_the_contract_s_own_context_type(self, tmp_path: Path) -> None:
        """The one thing the harness must not get wrong.

        An author coding against what the harness passes must be coding against the
        contract. A look-alike context would teach a fiction that only surfaced at
        integration.
        """
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome

SEEN: list[object] = []

def run(context: CollectContext) -> CollectOutcome:
    SEEN.append(type(context))
    context.log("seen", {"type": type(context).__name__})
    return CollectOutcome(items_emitted=0)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        result = run_addon(addon)
        assert result.logs[0][1]["type"] == CollectContext.__name__

    def test_each_kind_receives_its_own_context(self, tmp_path: Path) -> None:
        expected = {
            "collector": CollectContext.__name__,
            "importer": ImportContext.__name__,
            "normalizer": NormalizeContext.__name__,
        }
        outcome_import = {
            "collector": "CollectOutcome", "importer": "CollectOutcome",
            "normalizer": "NormalizeOutcome",
        }
        for kind, context_name in expected.items():
            outcome = outcome_import[kind]
            field = "items_emitted" if outcome == "CollectOutcome" else "results_emitted"
            body = f'''
from __future__ import annotations
from typing import Any
from addon_api.results import {outcome}

def run(context: Any) -> {outcome}:
    context.log("seen", {{"type": type(context).__name__}})
    return {outcome}({field}=0)
'''
            addon = write_addon(tmp_path / kind, kind, body, addon_id=f"probe.{kind}")
            result = run_addon(addon)
            assert result.logs[0][1]["type"] == context_name, kind

    def test_repeated_calls_to_one_endpoint_are_served_in_order(self, tmp_path: Path) -> None:
        """A paginating collector must see page 1 then page 2, not page 1 twice."""
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome, RawItem

def run(context: CollectContext) -> CollectOutcome:
    emitted = 0
    for _ in range(2):
        response = context.fetch("items", {})
        context.emit_raw([RawItem(item_key=response.body.decode(), payload=response.body,
                                  content_type="application/json")])
        emitted += 1
    return CollectOutcome(items_emitted=emitted)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        fixture_dir = tmp_path / "fx"
        write_fixture(fixture_dir, "items.1.json", {"page": 1})
        write_fixture(fixture_dir, "items.2.json", {"page": 2})
        result = run_addon(addon, fixtures=load_fixtures(fixture_dir))
        assert [item.item_key for item in result.raw_items] == [
            '{"page": 1}', '{"page": 2}'
        ]

    def test_asking_past_the_last_fixture_is_refused_by_name(self, tmp_path: Path) -> None:
        """Not an empty page. An empty page would let an untested add-on look finished."""
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome

def run(context: CollectContext) -> CollectOutcome:
    context.fetch("items", {})
    context.fetch("items", {})
    return CollectOutcome(items_emitted=0)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        fixture_dir = tmp_path / "fx"
        write_fixture(fixture_dir, "items.1.json", {"page": 1})
        with pytest.raises(HarnessError, match="call 2 of endpoint 'items'"):
            run_addon(addon, fixtures=load_fixtures(fixture_dir))

    def test_an_addon_failure_is_reported_rather_than_raised(self, tmp_path: Path) -> None:
        """An add-on's failure is a result to look at, not an exception to escape.

        `HarnessError` means the question was never put to the add-on; an `AddonError`
        means it answered. Conflating them would make a missing fixture and a genuine
        permanent failure look alike.
        """
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.errors import AddonConfigInvalid
from addon_api.results import CollectOutcome

def run(context: CollectContext) -> CollectOutcome:
    raise AddonConfigInvalid("base_path is not configured", {"source_id": context.source_id})
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        result = run_addon(addon)
        assert result.failed
        assert isinstance(result.failure, AddonConfigInvalid)
        assert result.outcome is None

    def test_a_count_that_disagrees_with_what_was_emitted_is_surfaced(
        self, tmp_path: Path
    ) -> None:
        """The platform cross-checks these and fails the attempt, so the loop shows it."""
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome, RawItem

def run(context: CollectContext) -> CollectOutcome:
    context.emit_raw([RawItem(item_key="a", payload=b"1", content_type="application/json")])
    return CollectOutcome(items_emitted=7)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        result = run_addon(addon)
        assert not result.failed
        assert result.emitted_count_disagrees()

    def test_an_honest_count_does_not_trip_the_warning(self, tmp_path: Path) -> None:
        """The positive control for the check above."""
        addon = new_addon("collector.honest", "collector", tmp_path / "honest")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", {"data": [1]}).parent
        )
        result = run_addon(addon, fixtures=fixtures, config={"base_path": "items"})
        assert not result.emitted_count_disagrees()

    def test_the_transcript_names_what_was_requested_and_emitted(
        self, tmp_path: Path
    ) -> None:
        addon = new_addon("collector.reported", "collector", tmp_path / "reported")
        fixtures = load_fixtures(
            write_fixture(tmp_path / "fx", "items.1.json", {"data": [1]}).parent
        )
        result = run_addon(addon, fixtures=fixtures, config={"base_path": "items"})
        manifest = AddonManifest.load(addon / "addon.toml")
        report = format_report(result, manifest)
        assert "collector.reported@0.1.0" in report
        assert "fetch" in report and "emit_raw" in report and "advance_cursor" in report

    def test_a_cursor_passed_in_reaches_the_add_on_unchanged(self, tmp_path: Path) -> None:
        body = '''
from __future__ import annotations
from addon_api.context import CollectContext
from addon_api.results import CollectOutcome

def run(context: CollectContext) -> CollectOutcome:
    context.log("cursor", {"value": context.cursor})
    return CollectOutcome(items_emitted=0)
'''
        addon = write_addon(tmp_path / "a", "collector", body)
        result = run_addon(addon, cursor={"next": "abc", "page": 3})
        assert result.logs[0][1]["value"] == {"next": "abc", "page": 3}


class TestConformanceNormalizer:
    """The smallest conforming add-on, and the property OQ-003 requires of it."""

    def item(self, key: str, payload: bytes) -> SnapshotItem:
        return SnapshotItem(item_key=key, payload=payload, content_type="application/json")

    def test_the_same_snapshot_produces_byte_identical_output_twice(self) -> None:
        """OQ-003's determinism requirement, on rules chosen to make it checkable."""
        snapshot = [
            self.item("a", b'{"Name":"  Alpha ","Count":2}'),
            self.item("b", b'{"name":"Beta","count":3}'),
        ]
        first = run_addon(CONFORMANCE_NORMALIZER, snapshot=snapshot)
        second = run_addon(CONFORMANCE_NORMALIZER, snapshot=snapshot)

        def canonical(result: Any) -> bytes:
            return json.dumps(
                [entry.to_json() for entry in result.results],
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")

        assert canonical(first) == canonical(second)

    def test_two_key_orderings_of_one_record_fold_to_one_result(self) -> None:
        """Why `_fold` sorts. Insertion order would leak input order into output."""
        result = run_addon(
            CONFORMANCE_NORMALIZER,
            snapshot=[
                self.item("a", b'{"Name":"Alpha","Count":2}'),
                self.item("b", b'{"count":2,"NAME":"Alpha"}'),
            ],
        )
        assert result.results[0].body == result.results[1].body

    def test_the_rules_are_structural_and_carry_no_domain_meaning(self) -> None:
        """The boundary OQ-002 draws, asserted rather than only described.

        Keys are folded and whitespace trimmed. No field is renamed to a domain term,
        no value is interpreted, and nothing is inferred — that is `rule-baseline@0.1`'s
        to do in B3, after OQ-002 accepts a decision consumer.
        """
        result = run_addon(
            CONFORMANCE_NORMALIZER,
            snapshot=[self.item("a", b'{"Product Name":" Serum ","SPF":50,"note":null}')],
        )
        assert result.results[0].body == {"product name": "Serum", "spf": 50}

    def test_false_and_zero_survive_while_null_and_blank_are_dropped(self) -> None:
        """An absent value and a falsey value are different facts."""
        result = run_addon(
            CONFORMANCE_NORMALIZER,
            snapshot=[self.item("a", b'{"ok":false,"count":0,"gone":null,"blank":"  "}')],
        )
        assert result.results[0].body == {"count": 0, "ok": False}

    def test_an_unparseable_item_is_skipped_when_lenient(self) -> None:
        result = run_addon(CONFORMANCE_NORMALIZER, snapshot=[self.item("a", b"not json")])
        assert not result.failed
        assert isinstance(result.outcome, NormalizeOutcome)
        assert (result.outcome.results_emitted, result.outcome.skipped) == (0, 1)

    def test_an_unparseable_item_fails_permanently_when_strict(self) -> None:
        """Retryability belongs to the class. Re-reading a sealed snapshot cannot help."""
        result = run_addon(
            CONFORMANCE_NORMALIZER,
            snapshot=[self.item("a", b"not json")],
            config={"strict": True},
        )
        assert isinstance(result.failure, AddonPermanent)

    def test_bytes_that_are_not_utf8_fail_even_when_lenient(self) -> None:
        """A sealed snapshot holding non-text is a defect in what was sealed."""
        result = run_addon(CONFORMANCE_NORMALIZER, snapshot=[self.item("a", b"\xff\xfe")])
        assert isinstance(result.failure, AddonPermanent)

    def test_the_add_on_can_be_made_to_emit_output_the_contract_rejects(self) -> None:
        """So the conformance suite has something real to catch.

        An add-on with no way to produce bad output cannot demonstrate that bad output
        is caught, which would leave `AddonOutputInvalid` untested against anything.
        """
        result = run_addon(
            CONFORMANCE_NORMALIZER,
            snapshot=[self.item("a", b'{"name":"Alpha"}')],
            config={"fail_output": True},
        )
        assert result.results[0].body == {"": None}

    def test_an_empty_snapshot_is_an_ordinary_run(self) -> None:
        result = run_addon(CONFORMANCE_NORMALIZER, snapshot=[])
        assert not result.failed
        assert isinstance(result.outcome, NormalizeOutcome)
        assert result.outcome.results_emitted == 0

    def test_the_normalizer_receives_no_fetch_no_cursor_and_no_credential(self) -> None:
        """DP-008 D4's asymmetry, at the moment an add-on could reach for one.

        A capability withheld is stronger than a capability documented as unused, and
        this is what withheld looks like from inside an add-on.
        """
        manifest = AddonManifest.load(CONFORMANCE_NORMALIZER / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.declares.hosts == ()
        assert manifest.declares.needs_credential is False
        assert manifest.declares.streams == ()
        assert not hasattr(NormalizeContext, "fetch")
        assert "cursor" not in NormalizeContext.__dataclass_fields__
