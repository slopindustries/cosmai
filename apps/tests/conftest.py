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

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import psycopg
import pytest
from psycopg.rows import dict_row

from domain.store import DomainStore
from platform_core.config import DEFAULT_API_HOST, PlatformConfig, load_config
from platform_core.db.connection import connect
from platform_core.db.migrate import SCHEMA, apply_migrations
from platform_core.jobs.store import Backoff, JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry

#: DP-032 D1: the dedicated test database, distinct from the production
#: `cosmai` database `apps/db/provision.sql` also created. Read from
#: `COSMA_TEST_DB` (default `cosmai_test`) rather than `COSMA_DB_NAME`, so a
#: test run can never reach `cosmai` by way of an operator's ordinary shell
#: configuration, while still letting each M2-M7 lane point at its own
#: provisioned database (`apps/db/provision.md`'s 2026-08-21 section) instead
#: of racing another lane's parallel `pytest` run over one shared schema reset
#: (OQ-006).
TEST_DATABASE = os.environ.get("COSMA_TEST_DB", "cosmai_test")


#: M-X8 (``docs/agent-workflow/reviews/REVIEW-M2-M7.md``): fixtures whose transitive
#: closure means "this test actually touches the database" — every fixture in this
#: file whose own body calls :func:`connect` directly. `job_connection` and
#: `_migrations_applied` are the two most-used; `migrator_connection` and
#: `runtime_connection` (round-2 re-review, N2: the first version of this set omitted
#: both, so a test requesting either one alone — `test_migrate.py`, `test_db_connection.py`
#: — would have wrongly read as DB-free) also open a connection independently, not
#: through either of the first two. Every *other* DB-backed fixture in this file
#: (`domain_store`, `job_store`, `_reset_job_tables`, …) depends transitively on one of
#: these four, so this set is exhaustive over fixtures a test can request — not a guess:
#: `test_every_db_touching_conftest_fixture_is_in_the_detection_set` in
#: `test_outbound_policy.py` introspects this module's own AST and asserts it.
_DB_TOUCHING_FIXTURES: Final = frozenset(
    {"job_connection", "_migrations_applied", "migrator_connection", "runtime_connection"}
)

#: Set by :func:`pytest_collection_modifyitems` before fixtures run, so
#: :func:`_reset_schema` can read it. A module attribute rather than a
#: ``pytest.Config`` stash because the schema-reset fixture has no route to the
#: session's `Config` other than importing this module either way, and this keeps the
#: two functions in the same file next to each other.
_SESSION_NEEDS_DATABASE: bool = True


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run ``test_migrate.py`` before any test that needs the schema populated, and
    record whether *any* selected test needs a database at all.

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

    **M-X8's fix.** `_reset_schema` below is session-scoped *and* autouse, so it used
    to open a database connection before a single test ran — including a run of
    `apps/tests/test_outbound_policy.py` alone, whose own module docstring says "a
    security test that needs a server standing up is a security test that eventually
    gets skipped." Computed here (collection time, before any fixture executes) rather
    than inside `_reset_schema` itself, because a fixture cannot see the full selected
    item list — only what its own test requested.
    """
    items.sort(key=lambda item: (0 if "test_migrate.py" in str(item.fspath) else 1,))
    global _SESSION_NEEDS_DATABASE
    _SESSION_NEEDS_DATABASE = any(
        not _DB_TOUCHING_FIXTURES.isdisjoint(getattr(item, "fixturenames", ()))
        for item in items
    )


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
    "deviations" section. The five statements below (`revoke`, `grant usage`,
    and three `alter default privileges`) are `apps/db/provision_db.sql`'s
    Part B grants, reissued verbatim so a reset schema is left in the same
    state a freshly provisioned one is.

    **M-X8 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`).** Skipped entirely when
    `pytest_collection_modifyitems` found no selected test whose fixture closure
    touches the database at all (`_SESSION_NEEDS_DATABASE`) — `platform_config` above
    only reads environment variables, so resolving it costs nothing even with the
    server down; this is the statement that would have opened the refused connection.
    """
    if not _SESSION_NEEDS_DATABASE:
        return
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
# never see a row a previous test left behind. Nothing *here* is `autouse` — a
# test that does not ask for `job_store` opens no connection of its own through
# this block.
#
# That is not the same as "runnable without a live server", and this comment
# used to say it was. `_reset_schema` above (`:91`) is `scope="session",
# autouse=True`: pytest instantiates it once for the whole session regardless
# of which test triggers collection first, and it opens a migrator connection
# to do so. `[측정]` REVIEW-M1 F6: running any of `test_config.py`/
# `test_obs.py`/`test_secrets.py` — the modules this comment claimed were
# server-free — against a dead port fails with 173 errors, not zero, because
# `_reset_schema` still has to run before the first test in the session
# collects. Every module in this suite needs a live server; what varies is only
# whether a given test also opens a `job_store` connection of its own.
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


# --------------------------------------------------------------------------- #
# Domain-store fixtures (M2 batch 2b)
#
# Copy-adapted in spirit from ``experiments/integrated-p0/tests/conftest.py``'s
# ``domain``/``database`` block, at the size DP-032's one-shared-database
# placement needs — the same trade ``job_store`` above already makes against
# P0's per-test cloned database. ``domain_store`` shares ``job_connection``
# with ``job_store`` on purpose: P0's own atomicity tests
# (``TestCollectionIsAtomic`` in ``test_domain_store.py``) need the domain
# writes and the fenced completion inside **one** transaction, which they
# cannot be if each store held its own connection.
# --------------------------------------------------------------------------- #


@pytest.fixture
def _reset_domain_tables(
    job_connection: psycopg.Connection[Any], _reset_job_tables: None
) -> Iterator[None]:
    """Clear the domain tables before and after a test, so no row outlives it.

    Depends on ``_reset_job_tables`` (not merely ``job_connection``) so the two
    resets nest correctly around the foreign keys ``raw_envelope.job_id`` and
    ``raw_envelope.attempt_id`` put between the domain and job tables:
    pytest's fixture-teardown order is the reverse of setup order, so this
    fixture's own ``_clear()`` runs — on both setup and teardown — while
    ``_reset_job_tables``'s job/job_attempt rows are still present, and a
    domain row referencing one created during the test is always gone before
    that job row's own cleanup tries to delete it.
    """

    def _clear() -> None:
        job_connection.execute("delete from cosmai.normalized_result")
        job_connection.execute("delete from cosmai.snapshot_item")
        job_connection.execute("delete from cosmai.snapshot")
        job_connection.execute("delete from cosmai.raw_item")
        job_connection.execute("delete from cosmai.raw_envelope")
        job_connection.execute("delete from cosmai.source_cursor")
        job_connection.execute("delete from cosmai.schedule")
        job_connection.execute("delete from cosmai.source")

    _clear()
    yield
    _clear()


@pytest.fixture
def domain_store(
    job_connection: psycopg.Connection[Any], _reset_domain_tables: None
) -> DomainStore:
    return DomainStore(job_connection)


# --------------------------------------------------------------------------- #
# Process helpers for worker/API integration tests (Tasks 7-8)
#
# Copy-adapted from ``experiments/integrated-p0/tests/conftest.py``'s process
# half. P0 spawned a worker or the API against a database cloned fresh for the
# test (``shared_database``); DP-032 gives P1 exactly one shared `cosmai_test`
# database (see the module docstring above), so every helper here points a
# spawned process at ``platform_config`` and leaves table-level isolation to
# whichever fixture the test itself uses to touch the job tables — ordinarily
# `job_store`'s `_reset_job_tables`. A test that needs an empty queue and does
# not otherwise request `job_store` depends on `_reset_job_tables` directly.
# --------------------------------------------------------------------------- #

#: The directory a spawned process needs on its import path. `platform_core`
#: lives directly under it, one level above this file — the analogue of P0's
#: `EXPERIMENT_ROOT`, needed for a different reason (there, an unimportable
#: hyphenated directory name; here, simply that a child process does not
#: inherit pytest's own `pythonpath` setting).
APPS_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: How long a test waits for a worker or API process it started. Generous
#: enough that a loaded machine does not fail the run, short enough that a
#: stuck process is reported as one rather than as a hung session.
PROCESS_TIMEOUT_SECONDS: Final = 30.0

#: The identity and lease a test claims under when it drives the store directly
#: rather than through a spawned process (`test_sec_004_protected_does_not_mean_unredacted`).
WORKER: Final = "worker-under-test"

LEASE_SECONDS: Final = 5.0


def worker_environment(config: PlatformConfig, **overrides: str) -> dict[str, str]:
    """Environment for a process a test starts, pointing it at ``config``.

    Used for the API entrypoint too, and named after the worker only because
    that was the first process a test started. Returning a fresh mapping rather
    than mutating ``os.environ`` keeps one test's overrides out of the next
    process; ``overrides`` states any further ``COSMA_`` settings a test wants
    (a short lease, a fast poll, a deliberately broken variable), and a caller
    that wants a setting *removed* can still delete a key from the mapping this
    returns.

    ``COSMA_TEST_DB`` (M2 batch 2a) is dropped from the copied environment
    before it reaches a spawned process. It selects *this session's* database
    (see ``TEST_DATABASE`` above) and is not one of ``platform_core.config``'s
    settings, so a spawned worker or API process has no use for it — and
    because it is ``COSMA_``-prefixed, an operator who set it in their shell to
    pick a lane's database (`apps/db/provision.md`'s 2026-08-21 section) would
    otherwise make every spawned process log an unrelated
    ``api.configuration_warning``/``worker.configuration_warning`` for an
    "unknown COSMA_-prefixed variable" that has nothing to do with that
    process's own configuration — `[측정]` this broke
    ``test_sec_003_case_f_the_api_entrypoint_reports_an_unknown_variable_and_runs``
    (`tests/test_api.py`), which counts exactly one such warning for the one
    variable *it* injects.
    """
    values = dict(os.environ)
    values.pop("COSMA_TEST_DB", None)
    values.update(
        {
            "COSMA_DB_HOST": str(config.db_host),
            "COSMA_DB_PORT": str(config.db_port),
            "COSMA_DB_NAME": config.db_name,
            "COSMA_DB_USER": config.db_user,
            "COSMA_DB_PASSWORD_REF": config.db_password_ref,
            "PYTHONPATH": os.pathsep.join(
                [str(APPS_ROOT), *([p] if (p := os.environ.get("PYTHONPATH")) else [])]
            ),
        }
    )
    values.update(overrides)
    return values


def worker_command(*arguments: str) -> list[str]:
    """The command line DP-006 D1 fixes for the worker process."""
    return [sys.executable, "-m", "platform_core.worker", *arguments]


def scheduler_command(*arguments: str) -> list[str]:
    """The command line M6 batch 6a fixes for the scheduler process."""
    return [sys.executable, "-m", "scheduler", *arguments]


def api_command(*arguments: str) -> list[str]:
    """The command line DP-006 D1 fixes for the operator API process."""
    return [sys.executable, "-m", "platform_core.api", *arguments]


def start_worker(
    config: PlatformConfig, *arguments: str, **overrides: str
) -> subprocess.Popen[str]:
    """Start a worker process against ``config`` and return it still running.

    Both streams are captured: the structured log is written to standard error
    and the shutdown report to standard output, and a test that started the
    process is the only reader either has.
    """
    return subprocess.Popen(
        worker_command(*arguments),
        env=worker_environment(config, **overrides),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for_worker(
    process: subprocess.Popen[str], timeout: float = PROCESS_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Collect a process's exit status and both of its streams.

    On a timeout the process is killed and its streams are still collected, so a
    test that hangs reports what the process was saying rather than nothing.
    """
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
        raise AssertionError(
            f"the process did not exit within {timeout}s\nstdout:\n{out}\nstderr:\n{err}"
        ) from None
    return subprocess.CompletedProcess(process.args, process.returncode, out, err)


def run_worker(
    config: PlatformConfig,
    *arguments: str,
    timeout: float = PROCESS_TIMEOUT_SECONDS,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    """Run a worker process to completion. The common case in a scenario."""
    return wait_for_worker(start_worker(config, *arguments, **overrides), timeout=timeout)


def start_scheduler(
    config: PlatformConfig, *arguments: str, **overrides: str
) -> subprocess.Popen[str]:
    """Start a scheduler process against ``config`` and return it still running.

    Named after ``start_worker`` and shaped identically — see that function's
    own docstring for why both streams are captured.
    """
    return subprocess.Popen(
        scheduler_command(*arguments),
        env=worker_environment(config, **overrides),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_scheduler(
    config: PlatformConfig,
    *arguments: str,
    timeout: float = PROCESS_TIMEOUT_SECONDS,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    """Run a scheduler process to completion. The common case in a scenario."""
    return wait_for_worker(start_scheduler(config, *arguments, **overrides), timeout=timeout)


def free_port(host: str) -> int:
    """A port nothing is listening on, for an API a test is about to start.

    Bound, read back, and released, which leaves a window in which something
    else could take it. A collision here shows up as a bind failure the test
    reports.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def accepts_connections(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_until(
    predicate: Callable[[], bool],
    description: str,
    timeout: float = PROCESS_TIMEOUT_SECONDS,
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
    """The structured events a process wrote, in order.

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


def attempts_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"select * from {SCHEMA}.job_attempt where job_id = %s order by attempt_no",
            (job_id,),
        )
        return cursor.fetchall()


def effects_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"select * from {SCHEMA}.platform_effect where job_id = %s", (job_id,))
        return cursor.fetchall()


@dataclass
class RunningApi:
    """An API process a test started, where to reach it, and what it left behind."""

    process: subprocess.Popen[str]
    host: str
    port: int
    finished: subprocess.CompletedProcess[str] | None = None

    @property
    def base_url(self) -> str:
        # A literal IPv6 address needs brackets in a URL; IPv4 must not have them.
        located = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{located}:{self.port}"

    def collected(self) -> subprocess.CompletedProcess[str]:
        """The exit status and both streams. Available once the block has ended."""
        assert self.finished is not None, "the API has not been stopped yet"
        return self.finished


@contextmanager
def running_api(
    config: PlatformConfig,
    host: str = DEFAULT_API_HOST,
    **overrides: str,
) -> Iterator[RunningApi]:
    """Start the API entrypoint, wait until it accepts a connection, then stop it.

    Stopped with ``SIGTERM`` rather than killed, because the entrypoint shuts
    down cleanly on it and both ``api.started`` and ``api.stopped`` are part of
    what SEC-002 reads. The process is always reaped on the way out — including
    when the body raised — and its streams are left on ``RunningApi.collected()``.
    """
    port = free_port(host)
    process = subprocess.Popen(
        api_command(),
        env=worker_environment(
            config, COSMA_API_HOST=host, COSMA_API_PORT=str(port), **overrides
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    api = RunningApi(process=process, host=host, port=port)
    try:
        wait_until(
            lambda: accepts_connections(host, port) or process.poll() is not None,
            f"the API accepts a connection on {host}:{port}",
        )
        assert process.poll() is None, (
            "the API exited before it accepted a connection:\n"
            f"{wait_for_worker(process).stderr}"
        )
        yield api
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        api.finished = wait_for_worker(process)
