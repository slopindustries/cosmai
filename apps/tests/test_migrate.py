"""``platform_core.db.migrate`` against the real, schema-reset `cosmai_test` database.

Requires the shared PostgreSQL server (`apps/db/provision.sql` databases and
roles) to be reachable — run unsandboxed with `COSMA_DB_HOST`/`COSMA_DB_PORT`/
`COSMA_DB_NAME`/`COSMA_DB_USER` and `COSMA_SECRET_SOURCE` set, per
`docs/conventions/secret-setup.md`.

The three cases the brief names — apply succeeds from an empty schema, a
reapply is a no-op, applied versions are recorded — are one linear story, not
three independent starting points: `tests/conftest.py`'s `_reset_schema`
fixture resets schema `cosmai` exactly once per session, so the first test here
is the one that actually starts from empty, and the tests after it observe the
state that one left behind. Each uses its own fresh `migrator_connection`
(a new session-level connection object, not a shared one), so "a reapply is a
no-op" is evidence about the database's recorded state, not merely about one
open connection remembering what it already did.

**N2 (round-2 re-review, `docs/agent-workflow/reviews/REVIEW-M2-M7.md` batch):**
"starts from empty" is only true because every test here requests
`migrator_connection`, which `tests/conftest.py`'s `_DB_TOUCHING_FIXTURES` now
covers (it did not before this fix wave) — that is what makes
`pytest_collection_modifyitems` actually run `_reset_schema` before this
module's tests, standalone or not, rather than this module silently running
against whatever schema state a prior session happened to leave. `[측정]`
Verified both ways: run alone against the live server, 5 passed (schema reset,
"starts from empty" holds); run alone with `COSMA_DB_PORT` pointed at a dead
port, 5 errors after ~130s (`psycopg`'s own connect timeout) with
`platform_core.errors.ConfigurationInvalidError: cannot reach the platform
database` — not a hang forever, not a silent pass against stale state.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from platform_core.config import ConfigurationInvalidError
from platform_core.db.migrate import SCHEMA, apply_migrations

#: M2 batch 2a added `0002_domain.sql` beside `0001_platform_core.sql` in this
#: same directory (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §M2) —
#: the platform and domain migrations for P1 apply through one applier and
#: one directory, unlike P0's separate `platform_core`/`domain` migration
#: directories (see `0002_domain.sql`'s own header for why P0 needed the split
#: and P1 does not).
EXPECTED_VERSIONS = ["0001_platform_core", "0002_domain"]


def _tables_in_schema(connection: psycopg.Connection[Any]) -> set[str]:
    rows = connection.execute(
        "select table_name from information_schema.tables where table_schema = %s",
        (SCHEMA,),
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_apply_migrations_requires_an_autocommit_connection(
    migrator_connection: psycopg.Connection[Any],
) -> None:
    migrator_connection.autocommit = False
    with pytest.raises(ConfigurationInvalidError) as raised:
        apply_migrations(migrator_connection)
    assert "autocommit" in raised.value.summary


def test_apply_migrations_from_an_empty_schema_applies_0001(
    migrator_connection: psycopg.Connection[Any],
) -> None:
    applied = apply_migrations(migrator_connection)
    assert applied == EXPECTED_VERSIONS
    tables = _tables_in_schema(migrator_connection)
    assert {
        "job",
        "job_attempt",
        "platform_effect",
        "schema_migrations",
        "source",
        "source_cursor",
        "raw_envelope",
        "raw_item",
        "snapshot",
        "snapshot_item",
        "normalized_result",
        "schedule",
    } <= tables


def test_reapplying_migrations_is_a_no_op(migrator_connection: psycopg.Connection[Any]) -> None:
    applied = apply_migrations(migrator_connection)
    assert applied == []


def test_applied_versions_are_recorded_in_schema_migrations(
    migrator_connection: psycopg.Connection[Any],
) -> None:
    rows = migrator_connection.execute(
        f"select version, applied_at from {SCHEMA}.schema_migrations"
    ).fetchall()
    versions = {str(row[0]): row[1] for row in rows}
    for expected in EXPECTED_VERSIONS:
        assert expected in versions
        assert versions[expected] is not None


def test_the_runtime_role_cannot_run_ddl(runtime_connection: psycopg.Connection[Any]) -> None:
    """DP-032 D1's role separation: the runtime role is DML only, no CREATE."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime_connection.execute(f"create table {SCHEMA}.must_fail (id int)")
    # The failed statement left an aborted transaction; roll it back so the
    # fixture's own `with connect(...)` teardown does not try to commit one.
    runtime_connection.rollback()
