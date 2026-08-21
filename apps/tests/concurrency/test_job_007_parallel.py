"""OQ-006's carried JOB-007 measurement, on the new tree.

Requires the shared PostgreSQL server reachable — run unsandboxed with
``COSMA_DB_HOST``/``COSMA_DB_PORT``/``COSMA_DB_NAME``/``COSMA_DB_USER`` and
``COSMA_SECRET_SOURCE`` set, per ``docs/conventions/secret-setup.md``.

This is JOB-007 case B — 200 jobs, four worker processes racing one database —
copy-adapted a second time from
``apps/tests/acceptance/test_job_scenarios_concurrency.py`` (itself
copy-adapted from ``experiments/integrated-p0/tests/test_job_concurrency.py``).
It is deliberately a separate file rather than a shared import: Task 9's
acceptance file runs this case as part of the scenario's own five-repetition
acceptance evidence, and this file is the instrument
``run_measurements.sh`` drives ten more times as OQ-006's own carried
measurement — a distinct question (does the claim statement still hold at
this scale, measured today, on this host) from Task 9's (does the scenario
pass at all).

**Why one test per process invocation, not a parametrized loop.** OQ-006's P0
baseline (0/30 normally, 1/3/1 under CPU contention) was measured as repeated
*process* invocations, each a clean interpreter with no state carried from the
previous run beyond what the database itself holds. A ``pytest`` parametrize
loop inside one process cannot rule out that a passing repetition benefited
from GC pressure, a warmed connection, or an import cache the previous
repetition built — exactly the kind of accidental coupling a raw concurrency
measurement should not carry. ``run_measurements.sh`` therefore invokes this
file once per repetition and reads the process exit code, the same way OQ-006's
original P0 measurement was taken.
"""

from __future__ import annotations

import signal
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from platform_core.config import PlatformConfig
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.worker import EXIT_OK, parse_report
from tests.conftest import (
    log_events,
    start_worker,
    wait_for_worker,
    wait_until,
)

FLEET: tuple[str, ...] = ("worker-a", "worker-b", "worker-c", "worker-d")

FAST_POLL_MS = "20"

MAX_ATTEMPTS = 3

FLEET_MAX_SECONDS = "90"

#: JOB-007 case B's own job count (``tests/acceptance/JOB-007-*.md``).
PARALLEL_JOBS = 200

NON_TERMINAL_JOBS = "select count(*) from cosmai.job where state not in ('SUCCEEDED', 'FAILED')"

JOBS_WITH_SEVERAL_ATTEMPTS = """
select job_id from cosmai.job_attempt group by job_id having count(*) > 1
"""

TOTAL_ATTEMPTS = "select count(*) from cosmai.job_attempt"

OPEN_ATTEMPTS = "select count(*) from cosmai.job_attempt where finished_at is null"

CLAIMS_BY_WORKER = "select worker_id, count(*) from cosmai.job_attempt group by worker_id"

JOBS_BY_STATE = "select state, count(*) from cosmai.job group by state"

OTHER_BACKENDS = """
select count(*) from pg_stat_activity
where datname = current_database() and pid <> pg_backend_pid()
"""


def _rows(
    connection: psycopg.Connection[Any], statement: str, *parameters: Any
) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters or None)
        return cursor.fetchall()


def _count(connection: psycopg.Connection[Any], statement: str) -> int:
    return int(_rows(connection, statement)[0][0])


def non_terminal_jobs(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, NON_TERMINAL_JOBS)


def total_attempts(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, TOTAL_ATTEMPTS)


def open_attempts(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, OPEN_ATTEMPTS)


def other_backends(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, OTHER_BACKENDS)


def jobs_with_several_attempts(connection: psycopg.Connection[Any]) -> list[UUID]:
    return [row[0] for row in _rows(connection, JOBS_WITH_SEVERAL_ATTEMPTS)]


def claims_by_worker(connection: psycopg.Connection[Any]) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in _rows(connection, CLAIMS_BY_WORKER)}


def jobs_by_state(connection: psycopg.Connection[Any]) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in _rows(connection, JOBS_BY_STATE)}


def all_effects(connection: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("select * from cosmai.platform_effect")
        return cursor.fetchall()


@dataclass(frozen=True)
class Fleet:
    finished: tuple[subprocess.CompletedProcess[str], ...]
    reports: tuple[dict[str, Any], ...]

    def _sum(self, metric: str) -> int:
        return sum(int(report["metrics"][metric]) for report in self.reports)

    @property
    def suppressed_duplicate_effects(self) -> int:
        return self._sum("suppressed_duplicate_effects")

    @property
    def claim_conflicts(self) -> int:
        return self._sum("claim_conflicts")

    @property
    def rejected_completions(self) -> int:
        return self._sum("rejected_completions")

    @property
    def abandoned_attempts(self) -> int:
        return self._sum("abandoned_attempts")

    @property
    def jobs_executed(self) -> int:
        return sum(int(report["jobs_executed"]) for report in self.reports)

    def events(self, name: str) -> list[dict[str, Any]]:
        return [
            record
            for finished in self.finished
            for record in log_events(finished.stderr)
            if record["event"] == name
        ]


def streams_of(finished: Sequence[subprocess.CompletedProcess[str]]) -> str:
    return "\n".join(
        f"--- {process.args} exited {process.returncode}\n{process.stderr[-2000:]}"
        for process in finished
    )


def run_fleet(
    config: PlatformConfig,
    connection: psycopg.Connection[Any],
    until: Callable[[], bool],
    description: str,
    names: Sequence[str] = FLEET,
) -> Fleet:
    """Start the workers, let them drain the queue, stop them, and read their reports."""
    processes = [
        start_worker(
            config,
            "--worker-id",
            name,
            "--max-seconds",
            FLEET_MAX_SECONDS,
            COSMA_POLL_MS=FAST_POLL_MS,
        )
        for name in names
    ]
    unmet: AssertionError | None = None
    try:
        wait_until(
            lambda: other_backends(connection) >= len(names),
            f"all {len(names)} workers have connected and can be stopped safely",
        )
        wait_until(until, description)
    except AssertionError as gave_up:
        unmet = gave_up
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    finished = tuple(wait_for_worker(process) for process in processes)
    if unmet is not None:
        raise AssertionError(f"{unmet}\n{streams_of(finished)}") from unmet
    for stopped in finished:
        assert stopped.returncode == EXIT_OK, stopped.stderr
    return Fleet(finished=finished, reports=tuple(parse_report(p.stdout) for p in finished))


def test_job_007_case_b_two_hundred_jobs_across_four_workers_leave_one_attempt_and_one_effect_each(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
) -> None:
    """JOB-007 case B, as one measured repetition; CONTRACT-JOB@0.1 I2; OQ-006 H2.

    Identical assertions to
    ``tests/acceptance/test_job_scenarios_concurrency.py``'s case B test — the
    scenario has exactly one correct outcome regardless of which document cites
    it. What differs is only how this file is invoked: once per process, by
    ``run_measurements.sh``, so that ``run_measurements.sh``'s pass/fail tally
    across ten repetitions is the OQ-006 measurement rather than a within-session
    parametrization.
    """
    for n in range(PARALLEL_JOBS):
        job_store.create_job("succeed", {"n": n}, max_attempts=MAX_ATTEMPTS)

    fleet = run_fleet(
        platform_config,
        job_connection,
        lambda: non_terminal_jobs(job_connection) == 0,
        f"all {PARALLEL_JOBS} jobs have reached a terminal state",
    )

    distribution = claims_by_worker(job_connection)
    spread = ", ".join(f"{name}={distribution.get(name, 0)}" for name in FLEET)
    print(
        f"\n[measured] JOB-007 case B: claims per worker {spread}"
        f"; claim_conflicts={fleet.claim_conflicts}"
        f"; suppressed_duplicate_effects={fleet.suppressed_duplicate_effects}"
        f"; rejected_completions={fleet.rejected_completions}"
    )

    assert jobs_with_several_attempts(job_connection) == []
    assert jobs_by_state(job_connection) == {JobState.SUCCEEDED: PARALLEL_JOBS}
    assert total_attempts(job_connection) == PARALLEL_JOBS
    assert len(all_effects(job_connection)) == PARALLEL_JOBS
    assert open_attempts(job_connection) == 0
    assert fleet.jobs_executed == PARALLEL_JOBS
    assert fleet.suppressed_duplicate_effects == 0
    assert fleet.rejected_completions == 0
    assert fleet.abandoned_attempts == 0
    assert set(distribution) <= set(FLEET), distribution
    assert sum(distribution.values()) == PARALLEL_JOBS, distribution
