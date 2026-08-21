"""The scheduler process: which sources it wakes, and which it refuses to.

Every test starts a real process with ``python -m scheduler`` (M6 batch 6a),
the same shape ``tests/test_worker.py`` uses for ``platform_core.worker`` and
for the same reason its own docstring gives: a signal handler, an exit status,
and a stream a parent reads are the three things an in-process test would have
had to simulate, and are exactly what a process boundary is for.

Fixtures follow ``apps/tests/conftest.py``'s convention: ``domain_store`` (and
therefore ``job_connection``/``_reset_domain_tables``) seeds sources and
schedules directly, on the same database the spawned scheduler process is
pointed at (``platform_config``), so a row this test writes is visible to the
subprocess without going through the HTTP surface `apps/domain/api.py` also
exposes over the same store methods.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from domain.store import DomainStore, SourceRow
from platform_core.config import PlatformConfig
from platform_core.jobs.state import JobState
from scheduler.__main__ import EXIT_OK, HANDLER_PREFIX, SOURCE_ID_FIELD, parse_report
from tests.conftest import run_scheduler

#: A poll short enough that a long-running scheduler test is asked again soon;
#: only ``--once`` tests are used here, so this mostly documents intent.
FAST_POLL_MS = "20"

ADDON_ID = "collector.smoke"
HANDLER = f"{HANDLER_PREFIX}{ADDON_ID}"


@pytest.fixture(autouse=True)
def _schema_ready(_migrations_applied: None) -> None:
    """Every test here starts a scheduler process that reads `cosmai.schedule`
    and `cosmai.job`; see `tests/test_worker.py`'s identical fixture for why
    this cannot rely on collection order alone."""


def register_collector(
    domain_store: DomainStore, source_id: str, *, enabled: bool = True
) -> None:
    domain_store.register_source(
        SourceRow(
            source_id=source_id,
            addon_id=ADDON_ID,
            addon_version="0.1.0",
            kind="collector",
            config={},
            config_schema_version="1",
            enabled=enabled,
        )
    )


def jobs_for(connection: psycopg.Connection[Any], source_id: str) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "select id, handler, payload, state from cosmai.job "
            "where handler = %s and payload ->> %s = %s",
            (HANDLER, SOURCE_ID_FIELD, source_id),
        )
        return cursor.fetchall()


def force_due(connection: psycopg.Connection[Any], source_id: str) -> None:
    """Push a schedule's `next_run_at` into the past, bypassing the interval —
    for a test that needs "due again" without waiting or re-upserting (which
    would only set `next_run_at` to `now()` when it was already null)."""
    connection.execute(
        "update cosmai.schedule set next_run_at = now() - interval '1 second' "
        "where source_id = %s",
        (source_id,),
    )


def push_out(connection: psycopg.Connection[Any], source_id: str) -> None:
    """The opposite of `force_due`: not due for another hour."""
    connection.execute(
        "update cosmai.schedule set next_run_at = now() + interval '1 hour' "
        "where source_id = %s",
        (source_id,),
    )


def insert_job(connection: psycopg.Connection[Any], source_id: str, state: str) -> None:
    """A job row in `state`, carrying the same handler/payload shape a
    scheduler-created collect job would — for the RUNNING half of "duplicate
    suppressed while pending/running", which a scheduler pass alone cannot
    reach (it only ever creates `PENDING` jobs).

    `job_lease_is_held_exactly_while_running` is a same-row CHECK, so a
    `RUNNING` row's lease columns have to be set in the same `insert` that sets
    its state — a follow-up `update` would fail on the insert before it ever
    ran.
    """
    job_id = uuid4()
    lease_expires_at_sql = "now() + interval '30 seconds'" if state == "RUNNING" else "null"
    lease_owner = "w" if state == "RUNNING" else None
    connection.execute(
        "insert into cosmai.job (id, handler, payload, state, attempt_count, "
        "max_attempts, available_at, correlation_id, lease_owner, lease_expires_at) values "
        f"(%s, %s, %s, %s, 0, 3, now(), 'c', %s, {lease_expires_at_sql})",
        (job_id, HANDLER, Jsonb({SOURCE_ID_FIELD: source_id}), state, lease_owner),
    )


class TestADueScheduleWakesItsSource:
    def test_a_due_enabled_schedule_creates_a_collect_job_and_advances_next_run_at(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        register_collector(domain_store, "due-src")
        domain_store.upsert_schedule("due-src", 3600, True)

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        report = parse_report(finished.stdout)
        assert report["jobs_created"] == 1
        assert report["duplicates_suppressed"] == 0

        rows = jobs_for(job_connection, "due-src")
        assert len(rows) == 1
        assert rows[0]["state"] == JobState.PENDING
        assert rows[0]["payload"] == {SOURCE_ID_FIELD: "due-src"}

        schedule = domain_store.read_schedule("due-src")
        assert schedule is not None
        assert schedule["last_run_at"] is not None
        # Advanced by the interval from `now()`, not from the old `next_run_at` —
        # `apps/scheduler/store.py`'s own `ADVANCE_SCHEDULE` docstring. Give the
        # comparison slack for the time the pass itself took.
        assert schedule["next_run_at"] > schedule["last_run_at"]

    def test_a_schedule_not_yet_due_is_ignored(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        register_collector(domain_store, "future-src")
        domain_store.upsert_schedule("future-src", 3600, True)
        push_out(job_connection, "future-src")

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        report = parse_report(finished.stdout)
        assert report["jobs_created"] == 0
        assert jobs_for(job_connection, "future-src") == []


class TestDisabledIsIgnored:
    def test_a_disabled_schedule_is_ignored(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        register_collector(domain_store, "off-schedule-src")
        domain_store.upsert_schedule("off-schedule-src", 60, False)

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        assert parse_report(finished.stdout)["jobs_created"] == 0
        assert jobs_for(job_connection, "off-schedule-src") == []

    def test_a_schedule_on_a_disabled_source_is_ignored(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        register_collector(domain_store, "off-source-src", enabled=False)
        domain_store.upsert_schedule("off-source-src", 60, True)

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        assert parse_report(finished.stdout)["jobs_created"] == 0
        assert jobs_for(job_connection, "off-source-src") == []


class TestDuplicateSuppression:
    @pytest.mark.parametrize("state", ["PENDING", "RUNNING"])
    def test_a_second_pass_is_suppressed_while_a_job_is_still_in_flight(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
        state: str,
    ) -> None:
        register_collector(domain_store, "dup-src")
        domain_store.upsert_schedule("dup-src", 60, True)
        insert_job(job_connection, "dup-src", state)

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        report = parse_report(finished.stdout)
        assert report["jobs_created"] == 0
        assert report["duplicates_suppressed"] == 1
        # The one job already there, and no second one.
        assert len(jobs_for(job_connection, "dup-src")) == 1

    def test_a_terminal_job_does_not_suppress_the_next_pass(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        """`SUCCEEDED`/`FAILED` are not "in flight" — only `PENDING`/`RUNNING`
        suppress (`apps/scheduler/store.py`'s `NON_TERMINAL_JOB_EXISTS`)."""
        register_collector(domain_store, "done-src")
        domain_store.upsert_schedule("done-src", 60, True)
        insert_job(job_connection, "done-src", "SUCCEEDED")

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        report = parse_report(finished.stdout)
        assert report["jobs_created"] == 1
        assert report["duplicates_suppressed"] == 0
        assert len(jobs_for(job_connection, "done-src")) == 2

    def test_once_the_in_flight_job_clears_a_forced_due_pass_creates_one(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        platform_config: PlatformConfig,
    ) -> None:
        register_collector(domain_store, "clears-src")
        domain_store.upsert_schedule("clears-src", 60, True)
        insert_job(job_connection, "clears-src", "PENDING")

        suppressed = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
        assert parse_report(suppressed.stdout)["duplicates_suppressed"] == 1

        # A suppressed pass leaves `next_run_at` untouched, so it is still due
        # without needing `force_due` — but the job that caused the suppression
        # is still PENDING too, so it has to be closed out before a second
        # collect job is the *correct* next action rather than a second
        # duplicate.
        job_connection.execute(
            "update cosmai.job set state = 'SUCCEEDED', lease_owner = null, "
            "lease_expires_at = null where handler = %s and payload ->> %s = %s",
            (HANDLER, SOURCE_ID_FIELD, "clears-src"),
        )
        force_due(job_connection, "clears-src")

        finished = run_scheduler(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)

        assert finished.returncode == EXIT_OK, finished.stderr
        report = parse_report(finished.stdout)
        assert report["jobs_created"] == 1
        assert report["duplicates_suppressed"] == 0
