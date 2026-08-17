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

**Why the process helpers are here.** ``start_worker`` and its neighbours are
used by more than one scenario module, and they are the other half of the same
mechanism: a database a spawned process can reach is only useful together with
the environment that points the process at it. They are plain functions rather
than fixtures because a scenario decides how many processes it starts and when,
which is exactly what its Action section describes.

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
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from io import StringIO
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from platform_core.config import PlatformConfig, load_config
from platform_core.db.connection import connect, connected
from platform_core.db.migrate import apply_migrations
from platform_core.errors import PlatformError
from platform_core.handlers.synthetic import synthetic_registry
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.store import Backoff, JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from psycopg import sql
from psycopg.rows import dict_row

TEMPLATE_DATABASE = "cosma_p0_template"

XDIST_WORKER_VARIABLE = "PYTEST_XDIST_WORKER"

KEEP_OPTION = "--keep-database"

#: The import root a spawned process needs on its path. ``platform_core`` lives
#: inside it, and this file is two levels down from it.
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]

#: How long a test waits for a worker process it started. Generous enough that a
#: loaded machine does not fail the run, short enough that a stuck worker is
#: reported as one rather than as a hung session.
WORKER_TIMEOUT_SECONDS = 30.0

#: The identity a single-process test claims under.
WORKER = "worker-under-test"

LEASE_SECONDS = 5.0

MAX_ATTEMPTS = 3

#: A lease that is already over by the time the next statement runs. It is the
#: single-process stand-in for the interruption a killed process produces.
EXPIRED_LEASE = 0.0

_serial = count()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        KEEP_OPTION,
        action="store_true",
        default=False,
        help="keep each test's cloned database instead of dropping it, for debugging",
    )


def worker_environment(config: PlatformConfig, **overrides: str) -> dict[str, str]:
    """Environment for a process a test starts, pointing it at ``config``.

    A test spawns real workers, and they read their configuration the way every
    other process does. Returning a fresh mapping rather than mutating
    ``os.environ`` keeps one test's database out of the next test's processes.

    ``PYTHONPATH`` is set for the same reason the pytest configuration sets its
    path: the experiment directory's name contains a hyphen, so ``platform_core``
    is importable only when that directory is on the path, and a child process
    inherits pytest's environment rather than its ``sys.path``.

    ``overrides`` states any further ``COSMA_`` settings the test wants, so that a
    scenario asking for a short lease or a fast poll says so where it is read.
    """
    values = dict(os.environ)
    values.update(
        {
            "COSMA_DB_HOST": str(config.db_host),
            "COSMA_DB_NAME": config.db_name,
            "COSMA_DB_USER": config.db_user,
            "PYTHONPATH": os.pathsep.join(
                [str(EXPERIMENT_ROOT), *([p] if (p := os.environ.get("PYTHONPATH")) else [])]
            ),
        }
    )
    values.update(overrides)
    return values


def worker_command(*arguments: str) -> list[str]:
    """The command line DP-006 D1 fixes for the worker process."""
    return [sys.executable, "-m", "platform_core.worker", *arguments]


def start_worker(
    config: PlatformConfig, *arguments: str, **overrides: str
) -> subprocess.Popen[str]:
    """Start a worker process against ``config`` and return it still running.

    Both streams are captured: the structured log is written to standard error
    and the shutdown report to standard output, and a test that started the
    process is the only reader either has. They are read by
    ``communicate``/``wait_for_worker`` rather than left to fill their pipes.
    """
    return subprocess.Popen(
        worker_command(*arguments),
        env=worker_environment(config, **overrides),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for_worker(
    process: subprocess.Popen[str], timeout: float = WORKER_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Collect a worker's exit status and both of its streams.

    On a timeout the process is killed and its streams are still collected, so a
    test that hangs reports what the worker was saying rather than nothing.
    """
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
        raise AssertionError(
            f"the worker did not exit within {timeout}s\nstdout:\n{out}\nstderr:\n{err}"
        ) from None
    return subprocess.CompletedProcess(process.args, process.returncode, out, err)


def run_worker(
    config: PlatformConfig,
    *arguments: str,
    timeout: float = WORKER_TIMEOUT_SECONDS,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    """Run a worker process to completion. The common case in a scenario."""
    return wait_for_worker(start_worker(config, *arguments, **overrides), timeout=timeout)


def wait_until(
    predicate: Callable[[], bool],
    description: str,
    timeout: float = WORKER_TIMEOUT_SECONDS,
    interval: float = 0.02,
) -> None:
    """Wait for something a separate process is expected to do, or say what it was.

    Used instead of a fixed sleep so that a test states the condition it depends
    on. The timeout is a failure report, not a duration anything is timed against.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting until {description}")


def log_events(text: str) -> list[dict[str, Any]]:
    """The structured events a worker process wrote, in order.

    The log is JSON Lines on standard error; anything else on that stream — a
    traceback from a process that died badly, for instance — is skipped rather
    than allowed to fail the parse, because a test asserting on events should
    fail on the missing event and not on the noise beside it.
    """
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            events.append(record)
    return events


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


# --------------------------------------------------------------------------- #
# One store, one runner, and somewhere to read the log back from
#
# Every `JOB` scenario that runs in this process needs the same five objects, and
# a second copy of them in each module is a second place for a jitter or a lease
# duration to drift. A module that needs different ones — a worker test whose
# store must reach the database its child processes use — overrides the fixture
# by defining its own, which is the ordinary pytest mechanism.
# --------------------------------------------------------------------------- #


@pytest.fixture
def log_stream() -> StringIO:
    return StringIO()


@pytest.fixture
def logger(log_stream: StringIO) -> StructuredLogger:
    return StructuredLogger(stream=log_stream, level="DEBUG")


@pytest.fixture
def metrics() -> MetricsRegistry:
    return MetricsRegistry()


@pytest.fixture
def connection(database: PlatformConfig) -> Iterator[psycopg.Connection[Any]]:
    """An autocommit connection, so each store statement is its own transaction."""
    with connected(database, autocommit=True) as handle:
        yield handle


@pytest.fixture
def store(
    connection: psycopg.Connection[Any],
    database: PlatformConfig,
    logger: StructuredLogger,
    metrics: MetricsRegistry,
) -> JobStore:
    # A jitter of zero makes every backoff the low edge of its window, so a test
    # that asserts on scheduling asserts on a number rather than on a range.
    return JobStore(
        connection,
        database,
        logger=logger,
        metrics=metrics,
        backoff=Backoff(database.retry_base_ms, database.retry_max_ms, jitter=lambda: 0.0),
    )


@pytest.fixture
def shared_connection(shared_database: PlatformConfig) -> Iterator[psycopg.Connection[Any]]:
    """An autocommit connection to the database a test's own processes will use."""
    with connected(shared_database, autocommit=True) as handle:
        yield handle


@pytest.fixture
def shared_store(
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
    logger: StructuredLogger,
    metrics: MetricsRegistry,
) -> JobStore:
    """The test's own view of the database its worker processes are using.

    Its metrics and log are the test's, not theirs: a process has its own
    registry in its own memory, which is why a worker reports one on the way out.
    """
    return JobStore(shared_connection, shared_database, logger=logger, metrics=metrics)


@pytest.fixture
def registry() -> HandlerRegistry:
    return synthetic_registry()


@pytest.fixture
def runner(store: JobStore, registry: HandlerRegistry) -> JobRunner:
    return JobRunner(store, registry, worker_id=WORKER, lease_seconds=LEASE_SECONDS)


# --------------------------------------------------------------------------- #
# Reading the database and the log back
# --------------------------------------------------------------------------- #


def attempts_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "select * from job_attempt where job_id = %s order by attempt_no", (job_id,)
        )
        return cursor.fetchall()


def effects_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("select * from platform_effect where job_id = %s", (job_id,))
        return cursor.fetchall()


def all_effects(connection: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("select * from platform_effect")
        return cursor.fetchall()


def events(log_stream: StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_stream.getvalue().splitlines() if line.strip()]


def events_named(log_stream: StringIO, event: str) -> list[dict[str, Any]]:
    return [record for record in events(log_stream) if record["event"] == event]


def transitions(log_stream: StringIO) -> list[tuple[Any, Any]]:
    return [
        (record["from_state"], record["to_state"])
        for record in events_named(log_stream, "job.transition")
    ]
