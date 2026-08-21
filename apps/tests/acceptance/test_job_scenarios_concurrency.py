"""JOB-006, JOB-007, and JOB-008: several worker processes, one database.

Copy-adapted from ``experiments/integrated-p0/tests/test_job_concurrency.py``.
These three scenarios carry the charter's first two P0-A exit criteria —
parallel claims never create conflicting active ownership, and duplicate
execution never produces an uncontrolled durable effect — and they are the
evidence OQ-006 H1 and H2 are judged on. Every test here starts real worker
*processes* against the shared ``cosmai_test`` database, because a
threaded single-process version would share a connection pool and a
transaction manager and would never ask ``FOR UPDATE SKIP LOCKED`` the
question this file exists to ask.

**What changed from P0, and what did not.** P0 gave each concurrency test a
database cloned fresh (``shared_database``) so several worker processes could
contend on it without touching another test's rows; DP-032 gives this tree one
shared ``cosmai_test`` database always, so that same sharing is simply the
ambient state — every test below depends on ``job_store`` (directly or through
``platform_config``) for the isolation ``_reset_job_tables`` provides instead.
Nothing about the claim statement, the fencing rule, or the effect-key
suppression under test was changed.

JOB-007 and JOB-008 both require their race to be repeated: this file reruns
each case ``REPETITIONS`` times, matching the scenario documents' own
"repeated at least five times" assertion. Task 10 reruns JOB-007 case B a
further ten times on its own, as OQ-006's carried measurement — that is a
distinct, deeper measurement of the same claim, not a duplicate of this file's
acceptance evidence.
"""

from __future__ import annotations

import signal
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.rows import dict_row

from platform_core.config import PlatformConfig
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import EFFECT_KEY_FIELD
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.worker import EXIT_OK, parse_report
from tests.conftest import (
    attempts_of,
    log_events,
    run_worker,
    start_worker,
    wait_for_worker,
    wait_until,
)

#: The four worker identities. Stated rather than generated so an attempt row,
#: a log line, and a printed distribution all name the same thing.
FLEET: tuple[str, ...] = ("worker-a", "worker-b", "worker-c", "worker-d")

FAST_POLL_MS = "20"

MAX_ATTEMPTS = 3

#: A backstop, not a schedule. A fleet is stopped by signal once the queue has
#: drained; this only bounds a worker whose test has already given up on it.
FLEET_MAX_SECONDS = "90"

#: JOB-007 and JOB-008 each require at least five repetitions, because one
#: passing run of a race is weak evidence.
REPETITIONS = 5

#: JOB-007 case B. Enough rows that four workers overlap for a while.
PARALLEL_JOBS = 200

#: JOB-008 cases B and C.
COLLIDING_JOBS = 20

# --------------------------------------------------------------------------- #
# JOB-006 constants
# --------------------------------------------------------------------------- #

#: The worker that stalls past its lease and wakes up too late.
STALLED = FLEET[0]

#: The worker that reclaims the job while the first one is still asleep.
RECLAIMING = FLEET[1]

SHORT_LEASE_SECONDS = "1"

#: Comfortably longer than the lease, the reclaim, and the reclaiming worker's
#: whole run, so that the stalled worker is provably still inside its handler
#: when the durable state is read for comparison.
STALL_SECONDS = 6.0


# --------------------------------------------------------------------------- #
# Reading the shared database
# --------------------------------------------------------------------------- #

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

LEASE_HAS_EXPIRED = "select lease_expires_at < now() from cosmai.job where id = %s"


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


def lease_has_expired(connection: psycopg.Connection[Any], job_id: UUID) -> bool:
    rows = _rows(connection, LEASE_HAS_EXPIRED, job_id)
    return bool(rows and rows[0][0])


def lease_owner(store: JobStore, job_id: UUID) -> str | None:
    job = store.read_job(job_id)
    assert job is not None
    owner = job["lease_owner"]
    return None if owner is None else str(owner)


# --------------------------------------------------------------------------- #
# Running a fleet of workers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Fleet:
    """What a set of worker processes did, read from outside them."""

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
    """Start the workers, let them drain the queue, stop them, and read their reports.

    Copy-adapted verbatim from ``experiments/integrated-p0/tests/test_job_concurrency.py``.
    """
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


def record_distribution(label: str, distribution: dict[str, int], fleet: Fleet) -> None:
    """Print the per-worker claim distribution JOB-007 requires the evidence to show.

    Printed rather than asserted: the contract offers no fairness guarantee, so
    a skewed run is a fact about this host and not a failure.
    """
    spread = ", ".join(f"{name}={distribution.get(name, 0)}" for name in FLEET)
    unnamed = {name: n for name, n in distribution.items() if name not in FLEET}
    print(
        f"\n[measured] {label}: claims per worker {spread}"
        + (f" plus unexpected {unnamed}" if unnamed else "")
        + f"; claim_conflicts={fleet.claim_conflicts}"
        + f"; suppressed_duplicate_effects={fleet.suppressed_duplicate_effects}"
        + f"; rejected_completions={fleet.rejected_completions}"
    )


# --------------------------------------------------------------------------- #
# JOB-006 — an expired lease is reclaimed, and the worker that lost it is fenced
# --------------------------------------------------------------------------- #


def test_job_006_an_expired_lease_is_reclaimed_and_the_stalled_worker_is_fenced(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
) -> None:
    """JOB-006; CONTRACT-JOB@0.1 I2; OQ-006 H2.

    Worker A claims a job whose handler stalls past its 1-second lease; worker
    B reclaims it and finishes; A then wakes and tries to record its own
    completion. If a stale completion were accepted, I2 would be violated
    retroactively — two workers would have held the job at once with nothing
    to show it. This is the harder half of ``JOB-005``'s interruption: the
    losing worker here is merely slow, not dead.
    """
    job_id = job_store.create_job(
        "stall",
        {"stall_seconds": STALL_SECONDS, "stall_on_attempt": 1},
        max_attempts=MAX_ATTEMPTS,
    )

    # 2. Worker A claims the job and enters the stall.
    stalling = start_worker(
        platform_config,
        "--once",
        "--worker-id",
        STALLED,
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    try:
        wait_until(
            lambda: lease_owner(job_store, job_id) == STALLED, f"{STALLED} holds the lease"
        )
        # 3. The lease runs out under a worker that is still alive.
        wait_until(
            lambda: lease_has_expired(job_connection, job_id),
            f"the lease held by {STALLED} has expired",
        )

        # 4. Worker B reclaims the job and runs it to completion.
        reclaiming = run_worker(
            platform_config,
            "--max-jobs",
            "1",
            "--max-seconds",
            "20",
            "--worker-id",
            RECLAIMING,
            COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
            COSMA_POLL_MS=FAST_POLL_MS,
        )

        # The durable state before A's late write, which is the whole comparison.
        assert stalling.poll() is None, (
            f"{STALLED} left its handler before the reclaimed state could be read; "
            f"raise STALL_SECONDS (currently {STALL_SECONDS})"
        )
        job_after_reclaim = job_store.read_job(job_id)
        assert job_after_reclaim is not None
        attempts_after_reclaim = attempts_of(job_connection, job_id)
        effects_after_reclaim = all_effects(job_connection)

        # 5. A finishes stalling and attempts to record its own completion.
        stalled = wait_for_worker(stalling)
    finally:
        if stalling.poll() is None:  # pragma: no cover - only on an assertion failure
            stalling.kill()

    assert reclaiming.returncode == EXIT_OK, reclaiming.stderr
    assert stalled.returncode == EXIT_OK, stalled.stderr

    job = job_store.read_job(job_id)
    assert job is not None
    first, second = attempts_of(job_connection, job_id)
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["worker_id"] == STALLED
    assert first["outcome"] == AttemptOutcome.ABANDONED
    assert first["error_class"] == ErrorClass.LEASE_ABANDONED
    assert second["worker_id"] == RECLAIMING
    assert second["outcome"] == AttemptOutcome.SUCCEEDED
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 2
    assert job["lease_owner"] is None

    reclaiming_metrics = parse_report(reclaiming.stdout)["metrics"]
    assert reclaiming_metrics["abandoned_attempts"] == 1
    assert reclaiming_metrics["transitions"][JobState.SUCCEEDED] == 1
    assert reclaiming_metrics["rejected_completions"] == 0

    stalled_metrics = parse_report(stalled.stdout)["metrics"]
    assert stalled_metrics["suppressed_duplicate_effects"] == 1, "the handler ran to its end"
    assert stalled_metrics["rejected_completions"] >= 1, "the completion was attempted"
    assert stalled_metrics["transitions"][JobState.SUCCEEDED] == 0

    # Rows 5-6: the late completion changes nothing at all — compared field by
    # field between the moment of the reclaim and the moment A gave up.
    assert job == job_after_reclaim
    assert attempts_of(job_connection, job_id) == attempts_after_reclaim
    assert all_effects(job_connection) == effects_after_reclaim
    assert len(all_effects(job_connection)) == 1

    refusals = [
        record
        for record in log_events(stalled.stderr)
        if record["event"] == "job.completion_rejected"
    ]
    assert len(refusals) == 1
    assert refusals[0]["worker_id"] == STALLED
    assert refusals[0]["job_id"] == str(job_id)
    assert refusals[0]["correlation_id"] == job["correlation_id"]
    assert refusals[0]["intended_outcome"] == AttemptOutcome.SUCCEEDED


# --------------------------------------------------------------------------- #
# JOB-007 — parallel claims never create conflicting active ownership
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_007_case_a_one_job_and_four_workers_open_exactly_one_attempt(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
    repetition: int,
) -> None:
    """JOB-007 case A; CONTRACT-JOB@0.1 I2; OQ-006 H2. Four workers race for one row."""
    job_id = job_store.create_job("succeed", {"n": repetition}, max_attempts=MAX_ATTEMPTS)

    fleet = run_fleet(
        platform_config,
        job_connection,
        lambda: non_terminal_jobs(job_connection) == 0,
        "the job has reached a terminal state",
    )

    distribution = claims_by_worker(job_connection)
    record_distribution(f"JOB-007 case A rep {repetition}", distribution, fleet)

    job = job_store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 1
    assert job["lease_owner"] is None
    attempts = attempts_of(job_connection, job_id)
    assert len(attempts) == 1, attempts
    assert attempts[0]["worker_id"] in FLEET
    assert len(all_effects(job_connection)) == 1
    assert jobs_with_several_attempts(job_connection) == []
    assert open_attempts(job_connection) == 0
    assert sum(distribution.values()) == 1
    assert fleet.jobs_executed == 1


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_007_case_b_two_hundred_jobs_leave_one_attempt_and_one_effect_each(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
    repetition: int,
) -> None:
    """JOB-007 case B; CONTRACT-JOB@0.1 I2; OQ-006 H2.

    Everything asserted here is a count that can only be right if every one of
    the 200 races resolved to a single owner. Task 10 reruns this case a
    further ten times as OQ-006's carried measurement; this is the scenario's
    own five-repetition acceptance evidence.
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
    record_distribution(f"JOB-007 case B rep {repetition}", distribution, fleet)

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


# --------------------------------------------------------------------------- #
# JOB-008 — duplicate execution does not produce an uncontrolled durable effect
# --------------------------------------------------------------------------- #


def test_job_008_case_a_the_safe_retry_of_a_succeeded_job_is_refused(
    job_store: JobStore, job_connection: psycopg.Connection[Any], platform_config: PlatformConfig
) -> None:
    """JOB-008 case A, first half — the divergence the scenario document itself records.

    Copy-adapted from ``experiments/integrated-p0/tests/test_job_concurrency.py``.
    The case as originally written asks for a safe retry of a ``SUCCEEDED``
    job; CONTRACT-JOB@0.1's transition table permits safe retry only from
    ``FAILED``, and the store matches the contract. The conflict is recorded
    executably rather than resolved by editing either document.
    """
    job_id = job_store.create_job(
        "succeed", {EFFECT_KEY_FIELD: "case-a/fixed"}, max_attempts=MAX_ATTEMPTS
    )
    finished = run_worker(platform_config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
    assert finished.returncode == EXIT_OK, finished.stderr

    job = job_store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.SUCCEEDED

    assert job_store.request_retry(job_id) is False

    unchanged = job_store.read_job(job_id)
    assert unchanged == job, "a refused retry changes nothing"
    assert len(attempts_of(job_connection, job_id)) == 1
    assert len(all_effects(job_connection)) == 1


def test_job_008_case_a_a_sequential_repeat_of_one_effect_key_is_suppressed(
    job_store: JobStore, job_connection: psycopg.Connection[Any], platform_config: PlatformConfig
) -> None:
    """JOB-008 case A, second half — the replay evidence the case actually carries.

    CONTRACT-JOB@0.1 I1. Two deliveries of one effect key, run sequentially by
    one worker with no concurrency and no interruption: the second finds the
    key already present, and one row exists. I1 is keyed on ``effect_key``, not
    on job identity, so this reaches the same duplicate the scenario document
    describes without inventing a transition the contract forbids.
    """
    key = "case-a/replayed"
    first = job_store.create_job("succeed", {EFFECT_KEY_FIELD: key}, max_attempts=MAX_ATTEMPTS)
    second = job_store.create_job("succeed", {EFFECT_KEY_FIELD: key}, max_attempts=MAX_ATTEMPTS)

    finished = run_worker(
        platform_config, "--max-jobs", "2", "--max-seconds", "20", COSMA_POLL_MS=FAST_POLL_MS
    )
    assert finished.returncode == EXIT_OK, finished.stderr

    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 2
    assert report["metrics"]["suppressed_duplicate_effects"] == 1
    for job_id in (first, second):
        job = job_store.read_job(job_id)
        assert job is not None
        assert job["state"] == JobState.SUCCEEDED, "a suppression is not a failure"
    assert total_attempts(job_connection) == 2
    effects = all_effects(job_connection)
    assert len(effects) == 1
    assert effects[0]["effect_key"] == key


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_008_case_b_twenty_colliding_jobs_leave_one_effect_and_nineteen_suppressions(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
    repetition: int,
) -> None:
    """JOB-008 case B; CONTRACT-JOB@0.1 I1. A duplicate forced, not waited for."""
    key = f"case-b/{repetition}"
    for n in range(COLLIDING_JOBS):
        job_store.create_job("succeed", {EFFECT_KEY_FIELD: key, "n": n}, max_attempts=MAX_ATTEMPTS)

    fleet = run_fleet(
        platform_config,
        job_connection,
        lambda: non_terminal_jobs(job_connection) == 0,
        f"all {COLLIDING_JOBS} colliding jobs have reached a terminal state",
    )

    distribution = claims_by_worker(job_connection)
    record_distribution(f"JOB-008 case B rep {repetition}", distribution, fleet)

    assert jobs_by_state(job_connection) == {JobState.SUCCEEDED: COLLIDING_JOBS}
    assert total_attempts(job_connection) == COLLIDING_JOBS
    assert jobs_with_several_attempts(job_connection) == []
    effects = all_effects(job_connection)
    assert len(effects) == 1, effects
    assert effects[0]["effect_key"] == key
    assert fleet.suppressed_duplicate_effects == COLLIDING_JOBS - 1

    suppressions = fleet.events("job.effect_suppressed")
    assert len(suppressions) == COLLIDING_JOBS - 1
    assert {record["effect_key"] for record in suppressions} == {key}
    assert len({record["job_id"] for record in suppressions}) == COLLIDING_JOBS - 1


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_008_case_c_twenty_distinct_effect_keys_are_never_suppressed(
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
    platform_config: PlatformConfig,
    repetition: int,
) -> None:
    """JOB-008 case C; the control that makes case B's nineteen suppressions mean something."""
    for n in range(COLLIDING_JOBS):
        job_store.create_job(
            "succeed", {EFFECT_KEY_FIELD: f"case-c/{repetition}/{n}"}, max_attempts=MAX_ATTEMPTS
        )

    fleet = run_fleet(
        platform_config,
        job_connection,
        lambda: non_terminal_jobs(job_connection) == 0,
        f"all {COLLIDING_JOBS} distinctly keyed jobs have reached a terminal state",
    )

    distribution = claims_by_worker(job_connection)
    record_distribution(f"JOB-008 case C rep {repetition}", distribution, fleet)

    assert jobs_by_state(job_connection) == {JobState.SUCCEEDED: COLLIDING_JOBS}
    assert total_attempts(job_connection) == COLLIDING_JOBS
    effects = all_effects(job_connection)
    assert len(effects) == COLLIDING_JOBS
    assert len({row["effect_key"] for row in effects}) == COLLIDING_JOBS
    assert fleet.suppressed_duplicate_effects == 0
    assert fleet.events("job.effect_suppressed") == []
