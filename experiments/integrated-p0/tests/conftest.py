"""Database fixtures for the P0-A tests.

DP-006 D3 is the specification, and its whole point is that two things which look
alike are not the same mechanism:

============  ===========================================  ==========================
              Purpose                                      Requirement
============  ===========================================  ==========================
Isolation     Concurrently running tests must not corrupt  each test gets a database
              each other's state                           of its own
Concurrency   A3 must show that two workers cannot hold     several worker processes
evidence      conflicting active ownership of one job      against **one** database
============  ===========================================  ==========================

So ``database`` clones a private database per test, and ``shared_database`` hands
a test one database that every process it starts will connect to. A concurrency
test given a private database per process would pass while testing nothing, which
is the failure D3 exists to prevent.

**How the template is built.** A session fixture creates ``cosma_p0_template``
once and applies the migrations to it; each test's database is then a
``CREATE DATABASE ... TEMPLATE`` clone, which PostgreSQL serves by copying files
rather than replaying SQL. Under ``pytest-xdist`` a session fixture runs once per
worker process, so the build is guarded by a file lock and a marker in the run's
shared temporary directory: the first worker through builds, the rest wait and
find it ready. The lock is ``fcntl.flock`` rather than a dependency, and the
applier's idempotence is the second line of defence if the marker were ever wrong.

**Why everything here is autocommit.** ``CREATE DATABASE`` and ``DROP DATABASE``
cannot run inside a transaction block. That is also why the maintenance
connections are opened and closed around each statement rather than held.

Pass ``--keep-database`` to leave the per-test databases behind for inspection;
the names are printed as they are kept, and ``dropdb`` removes them.

**Note on the shared database's scope.** D3 requires one database shared by the
processes a concurrency test starts, and that is what ``shared_database``
provides. It is still cloned per test rather than being one long-lived database
shared by every concurrency test in the run, because two such tests landing on
two ``pytest-xdist`` workers at once would otherwise see each other's jobs. The
evidence D3 asks for is about processes inside one test, so this is the narrower
reading that keeps ``-n`` usable; if a later scenario needs the wider one, it
needs a serial marker as well and that is a change to record, not to assume.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from dataclasses import replace
from itertools import count
from pathlib import Path
from typing import Any

import psycopg
import pytest
from platform_core.config import PlatformConfig, load_config
from platform_core.db.connection import connect, connected
from platform_core.db.migrate import apply_migrations
from platform_core.errors import PlatformError
from psycopg import sql

TEMPLATE_DATABASE = "cosma_p0_template"

XDIST_WORKER_VARIABLE = "PYTEST_XDIST_WORKER"

KEEP_OPTION = "--keep-database"

_serial = count()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        KEEP_OPTION,
        action="store_true",
        default=False,
        help="keep each test's cloned database instead of dropping it, for debugging",
    )


def worker_environment(config: PlatformConfig) -> dict[str, str]:
    """Environment for a process a test starts, pointing it at ``config``.

    A concurrency test spawns real workers, and they read their configuration the
    way every other process does. Returning a fresh mapping rather than mutating
    ``os.environ`` keeps one test's database out of the next test's processes.
    """
    values = dict(os.environ)
    values.update(
        {
            "COSMA_DB_HOST": str(config.db_host),
            "COSMA_DB_NAME": config.db_name,
            "COSMA_DB_USER": config.db_user,
        }
    )
    return values


def _label() -> str:
    """A per-process name fragment, so two test workers cannot pick one name."""
    return os.environ.get(XDIST_WORKER_VARIABLE, "main")


def _unique_database_name(kind: str) -> str:
    return f"cosma_p0_{kind}_{_label()}_{os.getpid()}_{next(_serial)}"


def _run_scoped_directory(factory: pytest.TempPathFactory) -> Path:
    """A directory shared by every test worker of this run, and only this run."""
    base = factory.getbasetemp()
    # Under xdist each worker gets `<run>/popen-gwN`; the run directory is its
    # parent. Without xdist there is one process and the base is already the run.
    return base.parent if os.environ.get(XDIST_WORKER_VARIABLE) else base


def _drop_database(handle: psycopg.Connection[Any], name: str) -> None:
    # WITH (FORCE) ends any connection left behind by a crashed test process,
    # which would otherwise make cleanup fail for reasons unrelated to the test.
    handle.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name)))


def _create_database(handle: psycopg.Connection[Any], name: str, template: str | None) -> None:
    statement = sql.SQL("create database {}").format(sql.Identifier(name))
    if template is not None:
        statement += sql.SQL(" template {}").format(sql.Identifier(template))
    handle.execute(statement)


def _build_template(config: PlatformConfig) -> None:
    """Recreate the template and apply the migrations to it, once per run."""
    with connected(config, autocommit=True) as maintenance:
        _drop_database(maintenance, TEMPLATE_DATABASE)
        _create_database(maintenance, TEMPLATE_DATABASE, None)
    with connected(config, database=TEMPLATE_DATABASE, autocommit=True) as handle:
        apply_migrations(handle)


@pytest.fixture(scope="session")
def platform_database() -> PlatformConfig:
    """Configuration for the local cluster, or a skip explaining how to get one."""
    try:
        config = load_config()
    except PlatformError as error:
        pytest.skip(f"no local database configured ({error.summary}); use scripts/with-database.sh")
    try:
        connect(config).close()
    except PlatformError as error:
        pytest.skip(f"local database unreachable ({error.summary}); use scripts/with-database.sh")
    return config


@pytest.fixture(scope="session")
def migrated_template(
    platform_database: PlatformConfig,
    tmp_path_factory: pytest.TempPathFactory,
) -> str:
    """The name of a database with every migration applied. Built once per run."""
    shared = _run_scoped_directory(tmp_path_factory)
    marker = shared / "cosma-p0-template.ready"
    with (shared / "cosma-p0-template.lock").open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if not marker.exists():
                _build_template(platform_database)
                marker.write_text(TEMPLATE_DATABASE, encoding="utf-8")
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return TEMPLATE_DATABASE


def _database_of_its_own(
    config: PlatformConfig,
    template: str | None,
    kind: str,
    keep: bool,
) -> Iterator[PlatformConfig]:
    name = _unique_database_name(kind)
    with connected(config, autocommit=True) as maintenance:
        _create_database(maintenance, name, template)
    try:
        yield replace(config, db_name=name)
    finally:
        if keep:
            print(f"\n{KEEP_OPTION}: kept {name}")
        else:
            with connected(config, autocommit=True) as maintenance:
                _drop_database(maintenance, name)


@pytest.fixture
def database(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[PlatformConfig]:
    """A private, migrated database for one test. This is the isolation mechanism."""
    keep = bool(request.config.getoption(KEEP_OPTION))
    yield from _database_of_its_own(platform_database, migrated_template, "test", keep)


@pytest.fixture
def empty_database(
    platform_database: PlatformConfig,
    request: pytest.FixtureRequest,
) -> Iterator[PlatformConfig]:
    """A private database with no migration applied, for testing the applier itself."""
    keep = bool(request.config.getoption(KEEP_OPTION))
    yield from _database_of_its_own(platform_database, None, "empty", keep)


@pytest.fixture
def shared_database(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[PlatformConfig]:
    """One migrated database for every process a ``concurrency`` test starts.

    Distinct from ``database`` in intent, not in privilege: nothing here isolates
    the processes from each other, because their contention is the evidence.
    """
    keep = bool(request.config.getoption(KEEP_OPTION))
    yield from _database_of_its_own(platform_database, migrated_template, "shared", keep)


@pytest.fixture
def db_connection(database: PlatformConfig) -> Iterator[psycopg.Connection[Any]]:
    """An open connection to this test's private database."""
    with connected(database) as handle:
        yield handle
