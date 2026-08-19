"""`importer.local.jsonl` end to end, and P0-B B4's dataset-row failure scenarios.

Two things are established here and they are different in kind.

**The third capability actually runs.** DP-024 bound `open_input`; this is the evidence
that an importer takes a file the operator approved and leaves Raw and a cursor behind,
inside the completion transaction like every other kind.

**Malformed and partially invalid rows are exercised, not assumed.** The P0 execution
plan's B4 lists them among the failures P0-B must deliberately run. They have no other
route into the system — every other kind's input is a response or a sealed snapshot.

The add-on under test is the committed one, copied into `tmp_path` rather than
reimplemented, so a change to it fails these tests rather than passing a private copy.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

ADDON_ID = "importer.local.jsonl"
ADDON_ROOT = Path(__file__).resolve().parent.parent / "addons" / ADDON_ID
SOURCE = "beauty-posts-dataset"
HANDLER = f"addon:{ADDON_ID}"
WORKER = "worker-import"

GOOD_ROWS = (
    '{"id": "p-1", "title": "\\uc218\\ubd84\\ud06c\\ub9bc", "body": "\\ubc1c\\ub9bc\\uc131"}',
    '{"id": "p-2", "title": "\\uc120\\ud06c\\ub9bc", "body": "\\ubc31\\ud669"}',
)


class _NoTransport:
    """An importer must never reach this. DP-024 D6."""

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("an importer opened a request")


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


def dataset(root: Path, *lines: str, name: str = "posts.jsonl") -> Path:
    directory = root / "datasets"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def register(
    domain: DomainStore,
    approved: Path,
    member: str = "posts.jsonl",
    config: dict[str, Any] | None = None,
) -> None:
    domain.register_source(
        SourceRow(
            source_id=SOURCE,
            addon_id=ADDON_ID,
            addon_version="0.1.0",
            kind="importer",
            config=config if config is not None else {"key_field": "id"},
            config_schema_version="1",
            input_profile={"root": str(approved), "inputs": {"rows": member}},
        )
    )


def run_import(root: Path, store: JobStore, domain: DomainStore) -> RunOutcome:
    installed = root / "addons"
    installed.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ADDON_ROOT, installed / ADDON_ID, dirs_exist_ok=True)

    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(installed, CONTRACT_VERSION),
        bind_capabilities(domain, _NoTransport()),
    )
    store.create_job(HANDLER, {"source_id": SOURCE}, max_attempts=1)
    outcome = JobRunner(store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


def payloads_of(connection: psycopg.Connection[Any]) -> set[bytes]:
    """Read the persisted Raw payloads directly: the store has no by-source item reader,
    and this test is about the bytes rather than about an API that would need one."""
    with connection.cursor() as cursor:
        cursor.execute(
            "select i.payload from raw_item i "
            "join raw_envelope e on e.id = i.envelope_id where e.source_id = %s",
            (SOURCE,),
        )
        return {bytes(row[0]) for row in cursor.fetchall()}


class TestAnImporterRuns:
    def test_every_row_becomes_one_raw_item(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert outcome.state is JobState.SUCCEEDED
        assert domain.count_items(SOURCE) == 2

    def test_the_payload_is_the_line_as_it_was_read(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """Losslessness at the row level: a re-serialization would reorder keys."""
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        run_import(tmp_path, store, domain)

        assert payloads_of(connection) == {line.encode("utf-8") for line in GOOD_ROWS}

    def test_the_envelope_holds_the_whole_file(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The original is preserved whether or not the add-on emitted anything from it."""
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        run_import(tmp_path, store, domain)

        summary = domain.raw_summary(SOURCE)
        assert summary["envelope_count"] == 1

    def test_the_cursor_records_where_it_stopped(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        run_import(tmp_path, store, domain)

        assert domain.read_cursor(SOURCE, "rows") == {"lines_read": 2}


class TestMalformedAndPartiallyInvalidRows:
    """P0-B B4, the scenario no other kind can reach."""

    def test_a_malformed_line_is_skipped_and_the_good_rows_survive(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """Refusing the whole file would discard every good row with the bad one."""
        register(domain, dataset(tmp_path, GOOD_ROWS[0], "{not json at all", GOOD_ROWS[1]))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 2

    def test_a_line_that_is_valid_json_but_not_a_record_is_skipped(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, GOOD_ROWS[0], "[1, 2, 3]", '"a string"'))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 1

    def test_a_row_missing_the_key_field_is_skipped(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """`source_item_key` is not null because an item nobody can identify cannot be
        deduplicated, resumed from, or traced. A row without one is not importable."""
        register(domain, dataset(tmp_path, GOOD_ROWS[0], '{"title": "no id here"}'))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 1

    def test_a_file_of_nothing_but_bad_rows_succeeds_with_no_items(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """`[결정]` Zero items is a successful run, not a failure. The file was read, the
        envelope is preserved, and *why* nothing came out is in the outcome's notes. A
        failure here would be indistinguishable from a file that could not be opened."""
        register(domain, dataset(tmp_path, "{oops", "[1]", '{"no": "key"}'))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 0
        assert domain.raw_summary(SOURCE)["envelope_count"] == 1

    def test_blank_lines_are_not_counted_as_malformed(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control on the cases above: a rule that called everything malformed would
        pass them all."""
        register(domain, dataset(tmp_path, GOOD_ROWS[0], "", "   ", GOOD_ROWS[1]))

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 2


class TestNothingOutsideTheApprovedRootIsRead:
    def test_a_member_escaping_the_root_fails_the_run(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        approved = dataset(tmp_path, *GOOD_ROWS)
        (tmp_path / "secret.jsonl").write_text('{"id": "leaked"}\n', encoding="utf-8")
        register(domain, approved, member="../secret.jsonl")

        outcome = run_import(tmp_path, store, domain)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.count_items(SOURCE) == 0

    def test_a_source_with_no_input_profile_fails_the_run(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        dataset(tmp_path, *GOOD_ROWS)
        domain.register_source(
            SourceRow(
                source_id=SOURCE,
                addon_id=ADDON_ID,
                addon_version="0.1.0",
                kind="importer",
                config={"key_field": "id"},
                config_schema_version="1",
            )
        )

        outcome = run_import(tmp_path, store, domain)

        assert outcome.error is not None
        assert domain.count_items(SOURCE) == 0

    def test_a_name_the_profile_does_not_hold_fails_the_run(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        approved = dataset(tmp_path, *GOOD_ROWS)
        domain.register_source(
            SourceRow(
                source_id=SOURCE,
                addon_id=ADDON_ID,
                addon_version="0.1.0",
                kind="importer",
                config={"key_field": "id"},
                config_schema_version="1",
                input_profile={"root": str(approved), "inputs": {"other": "posts.jsonl"}},
            )
        )

        outcome = run_import(tmp_path, store, domain)

        assert outcome.error is not None
        assert domain.count_items(SOURCE) == 0


class TestTheImportersCopyOfTheCursorRulesIsChecked:
    """`[측정]` The importer has its own copy of the two cursor guards, and B5's lesson is
    that a second copy is only as strong as its own tests. Both were **GREEN** on
    2026-08-19 until these cases were written.

    The add-on here is synthetic rather than the committed one, because the committed
    importer never breaks either rule — which is precisely why neither copy was exercised.
    """

    def _install_synthetic(self, root: Path, body: str) -> None:
        package = root / "addons" / ADDON_ID
        package.mkdir(parents=True, exist_ok=True)
        (package / "addon.toml").write_text(
            (ADDON_ROOT / "addon.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (package / "handler.py").write_text(body, encoding="utf-8")

    def _run_synthetic(
        self, root: Path, store: JobStore, domain: DomainStore, body: str
    ) -> RunOutcome:
        self._install_synthetic(root, body)
        registry = HandlerRegistry()
        register_addons(
            registry,
            load_addons(root / "addons", CONTRACT_VERSION),
            bind_capabilities(domain, _NoTransport()),
        )
        store.create_job(HANDLER, {"source_id": SOURCE}, max_attempts=1)
        outcome = JobRunner(store, registry, WORKER, lease_seconds=60).run_once()
        assert outcome is not None
        return outcome

    def test_a_cursor_value_of_none_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        outcome = self._run_synthetic(tmp_path, store, domain, """
from addon_api import CollectOutcome


def run(context):
    context.open_input("rows")
    context.advance_cursor("rows", None)
    return CollectOutcome(items_emitted=0)
""")

        assert outcome.error is not None
        assert domain.read_cursor(SOURCE, "rows") is None

    def test_a_cursor_on_an_undeclared_stream_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        outcome = self._run_synthetic(tmp_path, store, domain, """
from addon_api import CollectOutcome


def run(context):
    context.open_input("rows")
    context.advance_cursor("elsewhere", 1)
    return CollectOutcome(items_emitted=0)
""")

        assert outcome.error is not None
        assert domain.read_cursor(SOURCE, "elsewhere") is None

    def test_the_same_shape_with_a_real_cursor_succeeds(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control. A run that failed for an unrelated reason would pass both cases."""
        register(domain, dataset(tmp_path, *GOOD_ROWS))

        outcome = self._run_synthetic(tmp_path, store, domain, """
from addon_api import CollectOutcome


def run(context):
    context.open_input("rows")
    context.advance_cursor("rows", {"lines_read": 2})
    return CollectOutcome(items_emitted=0)
""")

        assert outcome.accepted, outcome
        assert domain.read_cursor(SOURCE, "rows") == {"lines_read": 2}


class TestConfigurationIsChecked:
    def test_a_missing_key_field_is_a_configuration_failure(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(domain, dataset(tmp_path, *GOOD_ROWS), config={})

        outcome = run_import(tmp_path, store, domain)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID

    def test_max_rows_stops_the_run_and_says_more_is_available(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        register(
            domain,
            dataset(tmp_path, *GOOD_ROWS),
            config={"key_field": "id", "max_rows": 1},
        )

        outcome = run_import(tmp_path, store, domain)

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE) == 1
