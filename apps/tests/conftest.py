"""Database fixtures for the apps/ test session.

Copy-adapted from ``experiments/integrated-p0/tests/conftest.py``'s DB-fixture
half, at the size DP-032's placement actually needs. P0-A's fixtures existed to
serve a repo-local, disposable, freely `CREATE DATABASE`-able cluster: a
per-test cloned database (`database`) for isolation and a shared one
(`shared_database`) for concurrency evidence, built from a
`CREATE DATABASE ... TEMPLATE` clone of a once-per-run migrated template.

None of that applies here. DP-032 gives P1 exactly two fixed databases on a
shared server it does not own outright — `cosmai` (production) and
`cosmai_test` (this session) — provisioned once by `apps/db/provision.sql`, not
created or dropped by a test run. There is nothing to clone and nowhere to
clone it: cloning would mean `CREATE DATABASE` against a server other services
also use, which is exactly the kind of operation DP-032 D1's role separation
(rule 6, "no startup DDL") exists to keep out of an ordinary test run. What a
test run may do instead is reset its own dedicated database's one schema.

So the whole isolation mechanism collapses to one session-scoped step: drop and
recreate schema `cosmai` inside `cosmai_test`, once, at session start, over a
migrator connection already `SET ROLE`'d to `cosmai_owner` — the same
connection shape and the same privilege the real deploy-time migrator uses.
Tests that need the schema populated call `apply_migrations` themselves, using
`migrator_connection`; ordinary behavioural tests (a future task's job store,
once it exists) use `runtime_connection`, which — per DP-032's role separation
— cannot run DDL even if a test tried to.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import psycopg
import pytest

from platform_core.config import PlatformConfig, load_config
from platform_core.db.connection import connect
from platform_core.db.migrate import SCHEMA

#: DP-032 D1: the dedicated test database, distinct from the production
#: `cosmai` database `apps/db/provision.sql` also created. Forced here rather
#: than trusted to `COSMA_DB_NAME`, so a test run can never reach `cosmai` by
#: way of an operator's ordinary shell configuration.
TEST_DATABASE = "cosmai_test"


@pytest.fixture(scope="session")
def platform_config() -> PlatformConfig:
    """Configuration for the shared server, pinned at the dedicated test database."""
    config = load_config()
    return replace(config, db_name=TEST_DATABASE)


@pytest.fixture(scope="session", autouse=True)
def _reset_schema(platform_config: PlatformConfig) -> None:
    """Reset schema `cosmai` in `cosmai_test`, once per test session.

    Runs over a migrator connection (`connect(role="migrator")`), which
    connects as `cosmai_migrator` and `SET ROLE`s itself to `cosmai_owner`
    before this fixture ever issues a statement — the DDL privilege a
    `DROP SCHEMA`/`CREATE SCHEMA` pair needs, and the same privilege the real
    deploy-time migration runs under.

    **Why the grants are reissued here too.** `ALTER DEFAULT PRIVILEGES` is
    keyed to the schema's OID, not its name — `apps/db/provision_db.sql` binds
    `cosmai_runtime`'s default SELECT/INSERT/UPDATE/DELETE grant to the schema
    OID that existed at provisioning time. `drop schema ... cascade` destroys
    that OID; the `create schema` right after it allocates a new one that the
    provisioning-time binding does not cover, so a table a migration creates
    afterwards would be owned by `cosmai_owner` with no grant to
    `cosmai_runtime` at all — `runtime_connection` would see an empty
    `information_schema.tables`, not a permission error, which is the failure
    mode that makes this easy to miss without a behavioural check. `[측정]`
    Found by exercising `runtime_connection` against a real `SELECT` after a
    reset, not by reading the grant statements; see the task-3-4 report's
    "deviations" section. The four statements below are
    `apps/db/provision_db.sql`'s Part B grants, reissued verbatim so a reset
    schema is left in the same state a freshly provisioned one is.
    """
    with connect(platform_config, role="migrator") as connection:
        connection.execute(f"drop schema if exists {SCHEMA} cascade")
        connection.execute(f"create schema {SCHEMA}")
        connection.execute(f"revoke all on schema {SCHEMA} from public")
        connection.execute(f"grant usage on schema {SCHEMA} to cosmai_runtime")
        connection.execute(
            f"alter default privileges for role cosmai_owner in schema {SCHEMA} "
            "grant select, insert, update, delete on tables to cosmai_runtime"
        )
        connection.execute(
            f"alter default privileges for role cosmai_owner in schema {SCHEMA} "
            "grant usage, select on sequences to cosmai_runtime"
        )
        connection.execute(
            f"alter default privileges for role cosmai_owner in schema {SCHEMA} "
            "revoke execute on functions from public"
        )


@pytest.fixture
def migrator_connection(platform_config: PlatformConfig) -> Iterator[psycopg.Connection[Any]]:
    """A migrator connection, `SET ROLE`'d to `cosmai_owner`, for DDL-level tests."""
    with connect(platform_config, role="migrator") as connection:
        yield connection


@pytest.fixture
def runtime_connection(platform_config: PlatformConfig) -> Iterator[psycopg.Connection[Any]]:
    """An ordinary runtime connection — DML only, no CREATE/ALTER/DROP."""
    with connect(platform_config, role="runtime") as connection:
        yield connection
