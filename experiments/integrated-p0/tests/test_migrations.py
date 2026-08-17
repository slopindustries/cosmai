"""The numbered plain-SQL applier DP-006 D4 chose instead of Alembic.

Three properties are worth a test, and the third is the one that decays quietly.

* It applies every file once, in filename order.
* Applying twice is safe: the second pass does nothing and reports nothing.
* A file that fails leaves **neither** its schema change **nor** its version row.
  An applier that recorded the version first, or that ran every file in one
  transaction, would pass the first two and fail this one — and the symptom would
  be a database whose recorded state is a claim rather than a fact.

The real ``0001`` is exercised from an empty database rather than only through the
template fixture, so that the migration is observed applying, not merely observed
having been applied.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import psycopg
import pytest
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.db.migrate import (
    applied_versions,
    apply_migrations,
    migration_files,
)
from platform_core.errors import ConfigurationInvalidError
from platform_core.obs.logging import StructuredLogger

CONTRACT_TABLES = ("job", "job_attempt", "platform_effect", "schema_migrations")


def table_names(handle: psycopg.Connection[Any]) -> set[str]:
    rows = handle.execute(
        "select table_name from information_schema.tables where table_schema = 'public'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def write_migration(directory: Path, name: str, body: str) -> None:
    (directory / f"{name}.sql").write_text(body, encoding="utf-8")


def test_migration_files_are_discovered_in_filename_order(tmp_path: Path) -> None:
    for name in ("0010_third", "0001_first", "0002_second"):
        write_migration(tmp_path, name, "select 1")
    assert [path.stem for path in migration_files(tmp_path)] == [
        "0001_first",
        "0002_second",
        "0010_third",
    ]


def test_the_shipped_migration_creates_every_contract_table(
    empty_database: PlatformConfig,
) -> None:
    with connected(empty_database, autocommit=True) as handle:
        assert table_names(handle) == set()
        applied = apply_migrations(handle)
        assert applied == ("0001_platform_core",)
        # Equality, not containment: P0-A owns these four tables and no others.
        assert table_names(handle) == set(CONTRACT_TABLES)


def test_applying_the_shipped_migration_twice_is_safe(empty_database: PlatformConfig) -> None:
    with connected(empty_database, autocommit=True) as handle:
        first = apply_migrations(handle)
        second = apply_migrations(handle)
        assert first == ("0001_platform_core",)
        assert second == ()
        recorded = handle.execute(
            "select count(*) from schema_migrations where version = %s",
            ("0001_platform_core",),
        ).fetchone()
        assert recorded is not None and recorded[0] == 1


def test_a_migrated_database_reports_the_shipped_version_as_applied(
    database: PlatformConfig,
) -> None:
    """The template fixture already applied it, so a fresh clone has nothing to do."""
    with connected(database, autocommit=True) as handle:
        assert "0001_platform_core" in applied_versions(handle)
        assert apply_migrations(handle) == ()


def test_a_failed_migration_records_no_version_and_leaves_no_table(
    database: PlatformConfig,
    tmp_path: Path,
) -> None:
    write_migration(tmp_path, "0900_sound", "create table sound_probe (id integer)")
    write_migration(
        tmp_path,
        "0901_broken",
        "create table broken_probe (id integer); this is not a statement;",
    )
    with connected(database, autocommit=True) as handle:
        with pytest.raises(psycopg.Error):
            apply_migrations(handle, directory=tmp_path)
        recorded = applied_versions(handle)
        present = table_names(handle)
        assert "0900_sound" in recorded
        assert "sound_probe" in present
        # The failing file's own DDL is gone with its version row: one transaction.
        assert "0901_broken" not in recorded
        assert "broken_probe" not in present


def test_a_repeat_pass_skips_what_a_failed_pass_already_applied(
    database: PlatformConfig,
    tmp_path: Path,
) -> None:
    write_migration(tmp_path, "0900_sound", "create table sound_probe (id integer)")
    write_migration(tmp_path, "0901_broken", "this is not a statement;")
    with connected(database, autocommit=True) as handle:
        with pytest.raises(psycopg.Error):
            apply_migrations(handle, directory=tmp_path)
        write_migration(tmp_path, "0901_broken", "create table repaired_probe (id integer)")
        assert apply_migrations(handle, directory=tmp_path) == ("0901_broken",)
        assert "repaired_probe" in table_names(handle)


def test_the_applier_refuses_a_connection_that_is_not_autocommit(
    database: PlatformConfig,
) -> None:
    """Without autocommit each file would be a savepoint, not a transaction."""
    with connected(database) as handle, pytest.raises(ConfigurationInvalidError) as raised:
        apply_migrations(handle)
    assert "autocommit" in raised.value.summary


def test_each_applied_version_is_reported_as_a_structured_event(
    empty_database: PlatformConfig,
) -> None:
    stream = io.StringIO()
    logger = StructuredLogger(stream=stream)
    with connected(empty_database, autocommit=True) as handle:
        apply_migrations(handle, logger=logger)
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    applied = [event for event in events if event["event"] == "db.migration_applied"]
    settled = [event for event in events if event["event"] == "db.migrations_settled"]
    assert [event["version"] for event in applied] == ["0001_platform_core"]
    assert settled and settled[0]["applied"] == ["0001_platform_core"]
