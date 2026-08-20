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
from io import StringIO
from typing import Any

import psycopg
import pytest

from platform_core.config import PlatformConfig, load_config
from platform_core.db.connection import connect
from platform_core.db.migrate import SCHEMA, apply_migrations
from platform_core.jobs.store import Backoff, JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry

#: DP-032 D1: the dedicated test database, distinct from the production
#: `cosmai` database `apps/db/provision.sql` also created. Forced here rather
#: than trusted to `COSMA_DB_NAME`, so a test run can never reach `cosmai` by
#: way of an operator's ordinary shell configuration.
TEST_DATABASE = "cosmai_test"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run ``test_migrate.py`` before any test that needs the schema populated.

    ``test_migrate.py``'s own docstring assumes its first test is the one that
    "actually starts from empty": `_reset_schema` above resets schema `cosmai`
    but does not apply any migration, so the first caller of
    `apply_migrations` in the session is the one whose return value names the
    version as newly applied. Job-table tests (`test_jobs_store.py`,
    `test_jobs_runner.py`) also need the schema populated and pull in
    `_migrations_applied` (below) to guarantee it — but pytest's default
    alphabetical collection order sorts both ahead of `test_migrate.py`, which
    would let `_migrations_applied` apply the migration first and falsify
    "starts from empty" for no reason connected to what either module tests.
    Sorting `test_migrate.py`'s items first removes the ordering accident
    without changing what either module asserts; `apply_migrations` is
    idempotent, so `_migrations_applied` running after it is a no-op.
    """
    items.sort(key=lambda item: (0 if "test_migrate.py" in str(item.fspath) else 1,))


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


# --------------------------------------------------------------------------- #
# Job-store/-runner fixtures (Task 6)
#
# Copy-adapted in spirit from ``experiments/integrated-p0/tests/conftest.py``'s
# store/runner block, at the size DP-032's placement needs. P0 isolated each
# test with a per-test cloned database (``CREATE DATABASE ... TEMPLATE``);
# DP-032 gives P1 exactly one shared `cosmai_test` database with no cloning
# (see the module docstring above), so isolation here is row-level instead:
# `_reset_job_tables` clears `job`/`job_attempt`/`platform_effect` before and
# after every test that requests `job_store`, so a `claim_next` in one test can
# never see a row a previous test left behind. Nothing here is `autouse` — a
# test that does not ask for `job_store` never opens a database connection at
# all, which is what keeps `test_config.py`/`test_obs.py`/`test_secrets.py`
# runnable without a live server.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def _migrations_applied(platform_config: PlatformConfig) -> None:
    """Apply every migration once per session, so job-table tests find a real schema.

    Independent of `test_migrate.py`'s own tests, which apply migrations as the
    subject under test rather than as a fixture another module can rely on —
    collection order (`test_jobs_store.py` sorts before `test_migrate.py`) must
    not decide whether the schema is populated when a job-store test runs.
    """
    with connect(platform_config, role="migrator") as connection:
        apply_migrations(connection)


@pytest.fixture
def job_connection(
    platform_config: PlatformConfig, _migrations_applied: None
) -> Iterator[psycopg.Connection[Any]]:
    """An autocommit runtime connection, so each store statement is its own transaction."""
    with connect(platform_config, role="runtime", autocommit=True) as connection:
        yield connection


@pytest.fixture
def log_stream() -> StringIO:
    return StringIO()


@pytest.fixture
def job_logger(log_stream: StringIO) -> StructuredLogger:
    return StructuredLogger(stream=log_stream, level="DEBUG")


@pytest.fixture
def job_metrics() -> MetricsRegistry:
    return MetricsRegistry()


@pytest.fixture
def _reset_job_tables(job_connection: psycopg.Connection[Any]) -> Iterator[None]:
    """Clear the job tables before and after a test, so no row outlives it."""

    def _clear() -> None:
        job_connection.execute("delete from cosmai.platform_effect")
        job_connection.execute("delete from cosmai.job_attempt")
        job_connection.execute("delete from cosmai.job")

    _clear()
    yield
    _clear()


@pytest.fixture
def job_store(
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
    job_logger: StructuredLogger,
    job_metrics: MetricsRegistry,
    _reset_job_tables: None,
) -> JobStore:
    # A jitter of zero makes every backoff the low edge of its window, so a test
    # that asserts on scheduling asserts on a number rather than on a range.
    return JobStore(
        job_connection,
        platform_config,
        logger=job_logger,
        metrics=job_metrics,
        backoff=Backoff(
            platform_config.retry_base_ms, platform_config.retry_max_ms, jitter=lambda: 0.0
        ),
    )
