"""JOB-006, JOB-007, and JOB-008 executed: several worker processes, one database.

These three scenarios carry the charter's first two P0-A exit criteria — parallel
claims never create conflicting active ownership, and duplicate execution never
produces an uncontrolled durable effect — and they are the evidence OQ-006 H1 and
H2 are judged on. Every test here therefore starts real processes against the
``shared_database`` fixture. A threaded single-process version would share a
connection pool and a transaction manager, and ``FOR UPDATE SKIP LOCKED`` would
never be asked the question this file exists to ask.

Four mechanics are worth reading before the tests.

**Stopping a fleet safely.** A worker writes its metric report on a clean exit
only, so a process killed before it installed its signal handlers leaves nothing
to read and the suppressed-duplicate sum would silently lose a term.
``run_fleet`` therefore waits until every worker has a backend on the database
before it signals anything. ``Worker.run`` installs the handlers and then opens
the connection, so a visible backend is proof that a stop signal will be honored
rather than fatal. That is the only readiness signal available: a worker claiming
nothing writes nothing, and its log is on a pipe the parent cannot read until the
process ends.

**The claim distribution is recorded, not asserted.** JOB-007 says in as many
words that a run in which one worker claimed everything passes the invariant
while proving nothing about contention, and that the evidence must show which
happened. Asserting a spread would be asserting a scheduling property the
contract explicitly declines to offer ("no fairness or priority semantics"), so
the numbers are printed and the invariant is what fails a run.

**Counters come back from the processes that hold them.** Metrics are in memory,
one registry per process. The suppression counts that separate JOB-008's three
cases are summed from the reports the workers write to standard output as they
exit; the fixture's own ``shared_store`` metrics belong to the test, not to them.

**JOB-008 case A diverges from its scenario document, deliberately.** The case
asks for an operator safe retry applied to a `SUCCEEDED` job. CONTRACT-JOB@0.1's
transition table permits safe retry only from `FAILED`, and ``JobStore`` refuses
anything else. That conflict is not resolved here: the refusal is recorded as its
own test, and the sequential-replay evidence the case carries is taken through a
second delivery of one effect key instead. See the two case A tests below.
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
from platform_core.config import PlatformConfig
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import EFFECT_KEY_FIELD
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.worker import EXIT_OK, parse_report

from tests.conftest import (
    all_effects,
    attempts_of,
    log_events,
    run_worker,
    start_worker,
    wait_for_worker,
    wait_until,
)

#: Every scenario in this module runs several worker processes against one
#: database, which is what the marker selects.
pytestmark = pytest.mark.concurrency

#: The four worker identities. Stated rather than generated so an attempt row, a
#: log line, and a printed distribution all name the same thing.
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

NON_TERMINAL_JOBS = """
select count(*) from job where state not in ('SUCCEEDED', 'FAILED')
"""

CLAIMABLE_JOBS = """
select count(*) from job
where (state = 'PENDING' and available_at <= now())
   or (state = 'RUNNING' and lease_expires_at < now())
"""

TOTAL_ATTEMPTS = """
select count(*) from job_attempt
"""

OPEN_ATTEMPTS = """
select count(*) from job_attempt where finished_at is null
"""

# The assertion JOB-007 names as its central one: I2 leaves no job with a second
# attempt, so this must always come back empty.
JOBS_WITH_SEVERAL_ATTEMPTS = """
select job_id from job_attempt group by job_id having count(*) > 1
"""

CLAIMS_BY_WORKER = """
select worker_id, count(*) from job_attempt group by worker_id order by worker_id
"""

JOBS_BY_STATE = """
select state, count(*) from job group by state
"""

# Whether a worker process has reached its loop. It opens the connection right
# after installing its stop handlers, so a backend here means a signal is safe.
OTHER_BACKENDS = """
select count(*) from pg_stat_activity
where datname = current_database() and pid <> pg_backend_pid()
"""

LEASE_HAS_EXPIRED = """
select lease_expires_at < now() from job where id = %s
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


def claimable_jobs(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, CLAIMABLE_JOBS)


def total_attempts(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, TOTAL_ATTEMPTS)


def open_attempts(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, OPEN_ATTEMPTS)


def other_backends(connection: psycopg.Connection[Any]) -> int:
    return _count(connection, OTHER_BACKENDS)


def jobs_with_several_attempts(connection: psycopg.Connection[Any]) -> list[UUID]:
    return [row[0] for row in _rows(connection, JOBS_WITH_SEVERAL_ATTEMPTS)]


def claims_by_worker(connection: psycopg.Connection[Any]) -> dict[str, int]:
    """How many attempts each worker opened. The contention evidence."""
    return {str(row[0]): int(row[1]) for row in _rows(connection, CLAIMS_BY_WORKER)}


def jobs_by_state(connection: psycopg.Connection[Any]) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in _rows(connection, JOBS_BY_STATE)}


def lease_has_expired(connection: psycopg.Connection[Any], job_id: UUID) -> bool:
    """Ask the database, which owns every timestamp a lease decision reads."""
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
        """Every structured event of one kind, across every worker in the fleet."""
        return [
            record
            for finished in self.finished
            for record in log_events(finished.stderr)
            if record["event"] == name
        ]


def streams_of(finished: Sequence[subprocess.CompletedProcess[str]]) -> str:
    """What the workers were saying, for a test that gave up waiting for them."""
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

    The workers are started as close together as ``Popen`` allows and are given no
    job limit, because a limit would decide the distribution this scenario is
    supposed to observe. They stop on a signal once the test's condition holds.
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

    Printed rather than asserted: the contract offers no fairness guarantee, so a
    skewed run is a fact about this host and not a failure. Visible under
    ``pytest -s``, and included in the failure message of any assertion that
    depends on it.
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


@dataclass(frozen=True)
class FencedRun:
    """The scenario's timeline, read at the two moments that separate its halves."""

    job_id: UUID
    correlation_id: str
    stalled: subprocess.CompletedProcess[str]
    reclaiming: subprocess.CompletedProcess[str]
    stalled_report: dict[str, Any]
    reclaiming_report: dict[str, Any]
    #: Read while the stalled worker was provably still inside its handler.
    job_after_reclaim: dict[str, Any]
    attempts_after_reclaim: list[dict[str, Any]]
    effects_after_reclaim: list[dict[str, Any]]
    #: Read after it woke, applied its effect, and tried to record its outcome.
    job: dict[str, Any]
    attempts: list[dict[str, Any]]
    effects: list[dict[str, Any]]


@pytest.fixture
def job_006_run(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
) -> FencedRun:
    """The scenario's Action section, from an empty database.

    ``stall_on_attempt`` is what makes both workers able to run the same short
    lease: attempt 1 sleeps past it and attempt 2 does not, which is the
    scenario's stated precondition.
    """
    job_id = shared_store.create_job(
        "stall",
        {"stall_seconds": STALL_SECONDS, "stall_on_attempt": 1},
        max_attempts=MAX_ATTEMPTS,
    )

    # 2. Worker A claims the job and enters the stall.
    stalling = start_worker(
        shared_database,
        "--once",
        "--worker-id",
        STALLED,
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    try:
        wait_until(
            lambda: lease_owner(shared_store, job_id) == STALLED,
            f"{STALLED} holds the lease",
        )
        # 3. The lease runs out under a worker that is still alive.
        wait_until(
            lambda: lease_has_expired(shared_connection, job_id),
            f"the lease held by {STALLED} has expired",
        )

        # 4. Worker B reclaims the job and runs it to completion.
        reclaiming = run_worker(
            shared_database,
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
        job_after_reclaim = shared_store.read_job(job_id)
        assert job_after_reclaim is not None
        attempts_after_reclaim = attempts_of(shared_connection, job_id)
        effects_after_reclaim = all_effects(shared_connection)

        # 5. A finishes stalling and attempts to record its own completion.
        stalled = wait_for_worker(stalling)
    finally:
        if stalling.poll() is None:  # pragma: no cover - only on an assertion failure
            stalling.kill()

    job = shared_store.read_job(job_id)
    assert job is not None
    stalled_report = parse_report(stalled.stdout)
    reclaiming_report = parse_report(reclaiming.stdout)
    # The scenario asks for lease recovery latency to be recorded, and for the
    # refusal to be visible rather than inferred from an unchanged table.
    print(
        f"\n[measured] JOB-006: {STALLED} rejected_completions="
        f"{stalled_report['metrics']['rejected_completions']}"
        f", suppressed_duplicate_effects="
        f"{stalled_report['metrics']['suppressed_duplicate_effects']}"
        f"; {RECLAIMING} abandoned_attempts="
        f"{reclaiming_report['metrics']['abandoned_attempts']}"
        f", lease_recovery_latency_ms="
        f"{reclaiming_report['metrics']['lease_recovery_latency_ms']['max_ms']:.1f}"
    )
    return FencedRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        stalled=stalled,
        reclaiming=reclaiming,
        stalled_report=stalled_report,
        reclaiming_report=reclaiming_report,
        job_after_reclaim=job_after_reclaim,
        attempts_after_reclaim=attempts_after_reclaim,
        effects_after_reclaim=effects_after_reclaim,
        job=job,
        attempts=attempts_of(shared_connection, job_id),
        effects=all_effects(shared_connection),
    )


def test_job_006_the_reclaiming_worker_abandons_the_stalled_attempt_and_finishes(
    job_006_run: FencedRun,
) -> None:
    """Rows 2 to 4 of the transition table: recovery from a live worker's lease."""
    assert job_006_run.reclaiming.returncode == EXIT_OK, job_006_run.reclaiming.stderr
    first, second = job_006_run.attempts
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["worker_id"] == STALLED
    assert first["outcome"] == AttemptOutcome.ABANDONED
    assert first["error_class"] == ErrorClass.LEASE_ABANDONED
    assert first["finished_at"] is not None
    assert second["worker_id"] == RECLAIMING
    assert second["outcome"] == AttemptOutcome.SUCCEEDED

    job = job_006_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 2
    assert job["terminal_reason"] is None
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None

    metrics = job_006_run.reclaiming_report["metrics"]
    assert metrics["abandoned_attempts"] == 1
    assert metrics["lease_recovery_latency_ms"]["count"] == 1
    assert metrics["transitions"][JobState.SUCCEEDED] == 1
    assert metrics["rejected_completions"] == 0


def test_job_006_the_stalled_worker_really_did_try_to_complete_its_lost_attempt(
    job_006_run: FencedRun,
) -> None:
    """The precondition every other JOB-006 assertion rests on.

    A stalled worker that never reached its completion would leave the rest of
    this scenario proving nothing: the durable state would be unchanged because
    nothing was attempted, not because the fence refused it. Two independent
    observations say it was attempted — the suppressed insert its handler made on
    the way out, and the completion the fence then refused.
    """
    assert job_006_run.stalled.returncode == EXIT_OK, job_006_run.stalled.stderr
    metrics = job_006_run.stalled_report["metrics"]
    assert metrics["suppressed_duplicate_effects"] == 1, "the handler ran to its end"
    assert metrics["rejected_completions"] >= 1, "the completion was attempted"
    # It claimed, and it recorded no terminal transition of its own.
    assert metrics["transitions"][JobState.RUNNING] == 1
    assert metrics["transitions"][JobState.SUCCEEDED] == 0
    assert job_006_run.stalled_report["jobs_executed"] == 1


def test_job_006_the_refusal_names_the_worker_that_was_refused(
    job_006_run: FencedRun,
) -> None:
    """The scenario's telemetry requirement, and the operator's explanation.

    A silently discarded stale completion would leave an operator unable to say
    why a worker reported success for a job it did not own.
    """
    refusals = [
        record
        for record in log_events(job_006_run.stalled.stderr)
        if record["event"] == "job.completion_rejected"
    ]
    assert len(refusals) == 1
    assert refusals[0]["worker_id"] == STALLED
    assert refusals[0]["job_id"] == str(job_006_run.job_id)
    assert refusals[0]["correlation_id"] == job_006_run.correlation_id
    assert refusals[0]["intended_outcome"] == AttemptOutcome.SUCCEEDED
    assert refusals[0]["reason"]

    reclaims = [
        record
        for record in log_events(job_006_run.reclaiming.stderr)
        if record["event"] == "job.attempt_abandoned"
    ]
    assert len(reclaims) == 1
    assert reclaims[0]["attempt_no"] == 1
    assert reclaims[0]["reclaimed_by"] == RECLAIMING
    assert reclaims[0]["error_class"] == ErrorClass.LEASE_ABANDONED
    # I5: one correlation identifier, two workers, distinguishable by worker_id.
    assert reclaims[0]["correlation_id"] == job_006_run.correlation_id
    assert {attempt["correlation_id"] for attempt in job_006_run.attempts} == {
        job_006_run.correlation_id
    }


def test_job_006_the_late_completion_changes_nothing_at_all(
    job_006_run: FencedRun,
) -> None:
    """Rows 5 and 6, as a comparison rather than as a list of fields.

    Every column of the job, of both attempts, and of the effect table is
    compared between the moment the reclaim finished and the moment the stalled
    worker had run out of things to try. Naming individual fields would have let
    an overwritten ``updated_at`` or a reopened attempt through.
    """
    assert job_006_run.job == job_006_run.job_after_reclaim
    assert job_006_run.attempts == job_006_run.attempts_after_reclaim
    assert job_006_run.effects == job_006_run.effects_after_reclaim
    # Stated separately because it is the row the scenario calls out by name.
    assert job_006_run.attempts[0]["finished_at"] == (
        job_006_run.attempts_after_reclaim[0]["finished_at"]
    )
    assert job_006_run.attempts[0]["outcome"] == AttemptOutcome.ABANDONED


def test_job_006_leaves_exactly_one_effect(job_006_run: FencedRun) -> None:
    """I1 across a fence: both workers derived the same key, one row exists."""
    assert len(job_006_run.effects) == 1
    assert job_006_run.effects[0]["job_id"] == job_006_run.job_id
    assert job_006_run.effects[0]["effect_key"] == f"job/{job_006_run.job_id}"


# --------------------------------------------------------------------------- #
# JOB-007 — parallel claims never create conflicting active ownership
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_007_case_a_one_job_and_four_workers_open_exactly_one_attempt(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
    repetition: int,
) -> None:
    """Four workers race for one row. Exactly one of them may win."""
    job_id = shared_store.create_job("succeed", {"n": repetition}, max_attempts=MAX_ATTEMPTS)

    fleet = run_fleet(
        shared_database,
        shared_connection,
        lambda: non_terminal_jobs(shared_connection) == 0,
        "the job has reached a terminal state",
    )

    distribution = claims_by_worker(shared_connection)
    record_distribution(f"JOB-007 case A rep {repetition}", distribution, fleet)

    job = shared_store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 1
    assert job["lease_owner"] is None
    attempts = attempts_of(shared_connection, job_id)
    assert len(attempts) == 1, attempts
    assert attempts[0]["worker_id"] in FLEET
    assert len(all_effects(shared_connection)) == 1
    assert jobs_with_several_attempts(shared_connection) == []
    assert open_attempts(shared_connection) == 0
    assert sum(distribution.values()) == 1
    assert fleet.jobs_executed == 1


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_007_case_b_two_hundred_jobs_leave_one_attempt_and_one_effect_each(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
    repetition: int,
) -> None:
    """The scenario's central assertion, under sustained contention.

    Everything asserted here is a count that can only be right if every one of
    the 200 races resolved to a single owner. A second attempt anywhere, an
    unclaimed row left behind, or a duplicate effect would each move exactly one
    of these numbers.
    """
    for n in range(PARALLEL_JOBS):
        shared_store.create_job("succeed", {"n": n}, max_attempts=MAX_ATTEMPTS)

    fleet = run_fleet(
        shared_database,
        shared_connection,
        lambda: non_terminal_jobs(shared_connection) == 0,
        f"all {PARALLEL_JOBS} jobs have reached a terminal state",
    )

    distribution = claims_by_worker(shared_connection)
    record_distribution(f"JOB-007 case B rep {repetition}", distribution, fleet)

    assert jobs_with_several_attempts(shared_connection) == []
    assert jobs_by_state(shared_connection) == {JobState.SUCCEEDED: PARALLEL_JOBS}
    assert total_attempts(shared_connection) == PARALLEL_JOBS
    assert len(all_effects(shared_connection)) == PARALLEL_JOBS
    assert claimable_jobs(shared_connection) == 0
    assert open_attempts(shared_connection) == 0
    assert fleet.jobs_executed == PARALLEL_JOBS
    # No duplicate execution is expected in this scenario; JOB-008 owns the case
    # where one happens anyway, and a suppression here would mean one did.
    assert fleet.suppressed_duplicate_effects == 0
    assert fleet.rejected_completions == 0
    assert fleet.abandoned_attempts == 0
    assert set(distribution) <= set(FLEET), distribution
    assert sum(distribution.values()) == PARALLEL_JOBS, distribution


# --------------------------------------------------------------------------- #
# JOB-008 — duplicate execution does not produce an uncontrolled durable effect
# --------------------------------------------------------------------------- #


def test_job_008_case_a_the_safe_retry_of_a_succeeded_job_is_refused(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
) -> None:
    """JOB-008 case A as written is not executable, and this is why.

    The case asks for a job driven to `SUCCEEDED` and then replayed by an
    operator safe retry, giving the transition `SUCCEEDED` to `PENDING`.
    CONTRACT-JOB@0.1's transition table has no such row — safe retry is defined
    only from `FAILED` — and ``JobStore.request_retry`` matches the contract.

    Rather than weaken either document, the conflict is recorded executably: the
    scenario's Action is performed and the platform's actual answer is asserted.
    Resolving it needs a Decision Packet, because either the contract gains a
    transition or the scenario loses one. Until then the replay evidence case A
    carries is taken by the test below.
    """
    job_id = shared_store.create_job(
        "succeed", {EFFECT_KEY_FIELD: "case-a/fixed"}, max_attempts=MAX_ATTEMPTS
    )
    finished = run_worker(shared_database, "--once", COSMA_POLL_MS=FAST_POLL_MS)
    assert finished.returncode == EXIT_OK, finished.stderr

    job = shared_store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.SUCCEEDED

    assert shared_store.request_retry(job_id) is False

    unchanged = shared_store.read_job(job_id)
    assert unchanged == job, "a refused retry changes nothing"
    assert len(attempts_of(shared_connection, job_id)) == 1
    assert len(all_effects(shared_connection)) == 1


def test_job_008_case_a_a_sequential_repeat_of_one_effect_key_is_suppressed(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
) -> None:
    """Case A's evidence, taken through the replay the contract does permit.

    Two deliveries of one effect key, executed one after the other by a single
    worker, with no concurrency and no interruption anywhere: two attempts run,
    the second finds the key already present, and one row exists. Reaching the
    duplicate through a second delivery rather than through a retry of the same
    job is the divergence recorded in the test above; what the case is actually
    about — a sequential repeat is detected and reconciled rather than doubled —
    is unaffected, because I1 is keyed on ``effect_key`` and not on job identity.
    """
    key = "case-a/replayed"
    first = shared_store.create_job("succeed", {EFFECT_KEY_FIELD: key}, max_attempts=MAX_ATTEMPTS)
    second = shared_store.create_job("succeed", {EFFECT_KEY_FIELD: key}, max_attempts=MAX_ATTEMPTS)

    finished = run_worker(
        shared_database, "--max-jobs", "2", "--max-seconds", "20", COSMA_POLL_MS=FAST_POLL_MS
    )
    assert finished.returncode == EXIT_OK, finished.stderr

    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 2
    assert report["metrics"]["suppressed_duplicate_effects"] == 1
    for job_id in (first, second):
        job = shared_store.read_job(job_id)
        assert job is not None
        assert job["state"] == JobState.SUCCEEDED, "a suppression is not a failure"
    assert total_attempts(shared_connection) == 2
    effects = all_effects(shared_connection)
    assert len(effects) == 1
    assert effects[0]["effect_key"] == key


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_008_case_b_twenty_colliding_jobs_leave_one_effect_and_nineteen_suppressions(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
    repetition: int,
) -> None:
    """A duplicate forced rather than waited for, and reconciled under a real race.

    Twenty jobs derive one key, so nineteen inserts must collide. All twenty
    still succeed: a job whose effect was already applied has done its work.
    """
    key = f"case-b/{repetition}"
    for n in range(COLLIDING_JOBS):
        shared_store.create_job(
            "succeed", {EFFECT_KEY_FIELD: key, "n": n}, max_attempts=MAX_ATTEMPTS
        )

    fleet = run_fleet(
        shared_database,
        shared_connection,
        lambda: non_terminal_jobs(shared_connection) == 0,
        f"all {COLLIDING_JOBS} colliding jobs have reached a terminal state",
    )

    distribution = claims_by_worker(shared_connection)
    record_distribution(f"JOB-008 case B rep {repetition}", distribution, fleet)

    assert jobs_by_state(shared_connection) == {JobState.SUCCEEDED: COLLIDING_JOBS}
    assert total_attempts(shared_connection) == COLLIDING_JOBS
    assert jobs_with_several_attempts(shared_connection) == []
    effects = all_effects(shared_connection)
    assert len(effects) == 1, effects
    assert effects[0]["effect_key"] == key
    assert fleet.suppressed_duplicate_effects == COLLIDING_JOBS - 1

    # The suppression is discoverable from the job that lost, not only counted.
    suppressions = fleet.events("job.effect_suppressed")
    assert len(suppressions) == COLLIDING_JOBS - 1
    assert {record["effect_key"] for record in suppressions} == {key}
    assert all(record["correlation_id"] for record in suppressions)
    assert len({record["job_id"] for record in suppressions}) == COLLIDING_JOBS - 1


@pytest.mark.parametrize("repetition", range(REPETITIONS))
def test_job_008_case_c_twenty_distinct_effect_keys_are_never_suppressed(
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
    repetition: int,
) -> None:
    """The control that makes case B's nineteen mean something.

    Without a run in which the counter stays at zero, "nineteen suppressed" is
    equally consistent with a platform that suppresses unconditionally. Same
    number of jobs, same four workers, same race — only the keys differ.
    """
    for n in range(COLLIDING_JOBS):
        shared_store.create_job(
            "succeed",
            {EFFECT_KEY_FIELD: f"case-c/{repetition}/{n}"},
            max_attempts=MAX_ATTEMPTS,
        )

    fleet = run_fleet(
        shared_database,
        shared_connection,
        lambda: non_terminal_jobs(shared_connection) == 0,
        f"all {COLLIDING_JOBS} distinctly keyed jobs have reached a terminal state",
    )

    distribution = claims_by_worker(shared_connection)
    record_distribution(f"JOB-008 case C rep {repetition}", distribution, fleet)

    assert jobs_by_state(shared_connection) == {JobState.SUCCEEDED: COLLIDING_JOBS}
    assert total_attempts(shared_connection) == COLLIDING_JOBS
    effects = all_effects(shared_connection)
    assert len(effects) == COLLIDING_JOBS
    assert len({row["effect_key"] for row in effects}) == COLLIDING_JOBS
    assert fleet.suppressed_duplicate_effects == 0
    assert fleet.events("job.effect_suppressed") == []
