"""JOB-001 through JOB-005, executed against the real ``cosmai_test`` schema.

Copy-adapted from ``experiments/integrated-p0/tests/test_jobs.py``,
``test_job_failure_paths.py``, and ``test_job_interruption.py``. Every test
below reproduces one ``tests/acceptance/JOB-00N-*.md`` document's Action,
"Expected state transitions", "Expected durable effects", and "Expected
telemetry" sections against ``apps/platform_core`` — using the real
``platform_core.handlers.synthetic`` handlers the worker process itself
registers, not a scenario-local stand-in.

**What changed from P0, and what did not.** P0 isolated each scenario with a
database cloned fresh from a migrated template; DP-032 gives this tree one
shared ``cosmai_test`` database, so isolation here is the row-level mechanism
``tests/conftest.py``'s ``job_store``/``_reset_job_tables`` already provide —
every test below depends on it, directly or through ``runner``. Nothing about
the interruption injection (``os._exit`` inside ``halt_before_effect`` /
``halt_after_effect``, JOB-005), the retryable-failure injector
(``fail_transient``), or the duplicate-effect mechanism (``platform_effect``'s
primary key) was changed: those are copied verbatim from
``platform_core.handlers.synthetic`` and ``platform_core.jobs.store``, which
are themselves copy-adaptations of the P0 modules (schema-qualified SQL only).

JOB-006 through JOB-008 need several worker *processes* racing one database
and live in ``test_job_scenarios_concurrency.py``; everything single-process
or single-worker-process lives here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import StringIO
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.rows import dict_row

from platform_core.config import PlatformConfig
from platform_core.errors import ErrorClass
from platform_core.handlers.synthetic import DEFAULT_EXIT_CODE
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.metrics import MetricsRegistry
from platform_core.worker import EXIT_OK, REPORT_EVENT, parse_report
from tests.conftest import (
    WORKER,
    attempts_of,
    effects_of,
    log_events,
    run_worker,
    wait_until,
)

#: The budget most scenarios ask for. JOB-003 and JOB-004 override it locally,
#: because their intent depends on a specific budget (exhausted vs. generous).
MAX_ATTEMPTS = 3

#: How long a scenario waits for a job to stop moving. Every wait here is for a
#: backoff measured in tens of milliseconds, so this is a failure report rather
#: than a duration anything depends on.
SETTLE_TIMEOUT_SECONDS = 10.0

RETRY_INTERVAL_SECONDS = 0.01

#: The lease and poll a JOB-005 worker process is started with, so the
#: interruption is observed without a real wait for the default 30s lease.
SHORT_LEASE_SECONDS = "1"
FAST_POLL_MS = "20"


# --------------------------------------------------------------------------- #
# Local reading helpers — the log and the effect table
# --------------------------------------------------------------------------- #


def events(log_stream: StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_stream.getvalue().splitlines() if line.strip()]


def events_named(log_stream: StringIO, event: str) -> list[dict[str, Any]]:
    return [record for record in events(log_stream) if record["event"] == event]


def transitions(log_stream: StringIO) -> list[tuple[Any, Any]]:
    return [
        (record["from_state"], record["to_state"])
        for record in events_named(log_stream, "job.transition")
    ]


def all_effects(connection: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("select * from cosmai.platform_effect")
        return cursor.fetchall()


def lease_has_expired(connection: psycopg.Connection[Any], job_id: UUID) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("select lease_expires_at < now() from cosmai.job where id = %s", (job_id,))
        row = cursor.fetchone()
    return bool(row is not None and row[0])


def run_until_terminal(
    runner: JobRunner,
    store: JobStore,
    job_id: UUID,
    timeout: float = SETTLE_TIMEOUT_SECONDS,
) -> list[RunOutcome]:
    """"Run the worker until the job reaches a terminal state", as a loop.

    Copy-adapted from ``experiments/integrated-p0/tests/test_job_failure_paths.py``.
    A pass that finds nothing means the job is waiting out its backoff, so the
    loop waits with it — the job is ``PENDING`` and not yet due, which is the
    scenario's own transition.
    """
    outcomes: list[RunOutcome] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = store.read_job(job_id)
        assert job is not None
        if JobState(job["state"]).is_terminal:
            return outcomes
        outcome = runner.run_once()
        if outcome is None:
            time.sleep(RETRY_INTERVAL_SECONDS)
            continue
        outcomes.append(outcome)
    raise AssertionError(f"job {job_id} did not reach a terminal state within {timeout}s")


def drain(runner: JobRunner, limit: int = 10) -> list[RunOutcome]:
    """Execute whatever is claimable right now, then stop."""
    outcomes: list[RunOutcome] = []
    for _ in range(limit):
        outcome = runner.run_once()
        if outcome is None:
            return outcomes
        outcomes.append(outcome)
    raise AssertionError(f"more than {limit} jobs were claimable; the queue should be finite")


# --------------------------------------------------------------------------- #
# JOB-001 — successful execution reaches a terminal state with one effect
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScenarioRun:
    job_id: UUID
    correlation_id: str
    job: dict[str, Any]
    attempts: list[dict[str, Any]]
    effects: list[dict[str, Any]]


@pytest.fixture
def job_001_run(
    job_store: JobStore, runner: JobRunner, job_connection: psycopg.Connection[Any]
) -> ScenarioRun:
    """The scenario's Action section: create, run to terminal, read everything back."""
    job_id = job_store.create_job("succeed", {"opaque": "value"}, max_attempts=MAX_ATTEMPTS)

    outcome = runner.run_once()
    assert outcome is not None, "the job was created due, so one pass must claim it"
    assert outcome.accepted, outcome.completion.reason
    # "Run the worker until the job leaves PENDING and reaches a terminal state."
    # A second pass must find nothing: a terminal job is not claimable.
    assert runner.run_once() is None

    job = job_store.read_job(job_id)
    assert job is not None
    return ScenarioRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        job=job,
        attempts=attempts_of(job_connection, job_id),
        effects=effects_of(job_connection, job_id),
    )


def test_job_001_reaches_succeeded_with_one_attempt_and_no_stranded_lease(
    job_001_run: ScenarioRun,
) -> None:
    """JOB-001, transition table rows 2-5; CONTRACT-JOB@0.1 I2, I4."""
    job = job_001_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 1
    assert job["max_attempts"] == MAX_ATTEMPTS
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None
    assert job["terminal_reason"] is None
    assert len(job_001_run.attempts) == 1
    attempt = job_001_run.attempts[0]
    assert attempt["attempt_no"] == 1
    assert attempt["worker_id"] == WORKER
    assert attempt["outcome"] == AttemptOutcome.SUCCEEDED
    assert attempt["error_class"] is None
    # Protected debug behavior: "error_detail is null throughout."
    assert attempt["error_detail"] is None
    assert attempt["correlation_id"] == job_001_run.correlation_id


def test_job_001_produces_exactly_one_durable_effect(job_001_run: ScenarioRun) -> None:
    """JOB-001's own definition of "one durable effect" in P0-A/P1; I1."""
    assert len(job_001_run.effects) == 1
    effect = job_001_run.effects[0]
    assert effect["job_id"] == job_001_run.job_id
    assert effect["applied_at"] is not None


def test_job_001_telemetry_carries_one_correlation_id_through_every_transition(
    job_001_run: ScenarioRun, log_stream: StringIO
) -> None:
    """JOB-001's telemetry section; I5 — correlation is total."""
    assert transitions(log_stream) == [
        (None, JobState.PENDING),
        (JobState.PENDING, JobState.RUNNING),
        (JobState.RUNNING, JobState.SUCCEEDED),
    ]
    for record in events_named(log_stream, "job.transition"):
        assert record["correlation_id"] == job_001_run.correlation_id
        assert record["job_id"] == str(job_001_run.job_id)
        assert record["handler"] == "succeed"
        assert record["attempt_no"] is not None
    identifiers = {record["correlation_id"] for record in events(log_stream)}
    assert identifiers == {job_001_run.correlation_id}


def test_job_001_records_the_metrics_the_scenario_names(
    job_001_run: ScenarioRun, job_metrics: MetricsRegistry
) -> None:
    """JOB-001's metrics section: one SUCCEEDED transition, no deviation counters."""
    reading = job_metrics.read()
    assert reading.transitions[JobState.SUCCEEDED] == 1
    assert reading.attempt_duration.count == 1
    assert reading.abandoned_attempts == 0
    assert reading.suppressed_duplicate_effects == 0
    assert reading.rejected_completions == 0


# --------------------------------------------------------------------------- #
# JOB-002 — a retryable failure is rescheduled and a later attempt succeeds
# --------------------------------------------------------------------------- #


@pytest.fixture
def job_002_run(
    job_store: JobStore, runner: JobRunner, job_connection: psycopg.Connection[Any]
) -> ScenarioRun:
    """Create a job that fails once, run it to terminal, read everything back."""
    job_id = job_store.create_job(
        "fail_transient", {"fail_until_attempt": 1}, max_attempts=MAX_ATTEMPTS
    )
    run_until_terminal(runner, job_store, job_id)
    job = job_store.read_job(job_id)
    assert job is not None
    return ScenarioRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        job=job,
        attempts=attempts_of(job_connection, job_id),
        effects=effects_of(job_connection, job_id),
    )


def test_job_002_spends_the_budget_one_attempt_at_a_time(job_002_run: ScenarioRun) -> None:
    """JOB-002 transition rows 1, 4, 6: two claims, two attempts, then success."""
    job = job_002_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 2
    assert job["terminal_reason"] is None
    assert job["lease_owner"] is None
    first, second = job_002_run.attempts
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert first["error_class"] == ErrorClass.PLATFORM_TRANSIENT
    assert second["outcome"] == AttemptOutcome.SUCCEEDED
    assert second["error_class"] is None


def test_job_002_reschedules_into_the_future_and_keeps_the_failure_readable(
    job_002_run: ScenarioRun,
) -> None:
    """JOB-002's Intent: a job that eventually succeeded must still show it failed first."""
    failed_at = job_002_run.attempts[0]["finished_at"]
    assert job_002_run.job["available_at"] > failed_at
    first = job_002_run.attempts[0]
    assert first["error_summary"]
    # Protected debug detail is recorded; the summary quotes no payload value.
    assert first["error_detail"] == {"attempt_no": 1, "fails_through_attempt": 1}
    assert "fail_until_attempt" not in first["error_summary"]


def test_job_002_leaves_exactly_one_effect_from_the_second_attempt(
    job_002_run: ScenarioRun,
) -> None:
    """JOB-002: the failed attempt must not produce an effect; only the successful one does."""
    assert len(job_002_run.effects) == 1
    assert job_002_run.effects[0]["payload"]["attempt_no"] == 2


def test_job_002_shares_one_correlation_id_and_counts_both_transitions(
    job_002_run: ScenarioRun, log_stream: StringIO, job_metrics: MetricsRegistry
) -> None:
    """JOB-002 telemetry and metrics; I5 across a reschedule."""
    assert {attempt["correlation_id"] for attempt in job_002_run.attempts} == {
        job_002_run.correlation_id
    }
    assert {record["correlation_id"] for record in events(log_stream)} == {
        job_002_run.correlation_id
    }
    reading = job_metrics.read()
    assert reading.transitions[JobState.SUCCEEDED] == 1
    assert reading.suppressed_duplicate_effects == 0
    assert reading.abandoned_attempts == 0
    assert reading.rejected_completions == 0


# --------------------------------------------------------------------------- #
# JOB-003 — retry exhaustion produces an observable terminal state
# --------------------------------------------------------------------------- #

JOB_003_MAX_ATTEMPTS = 2


@pytest.fixture
def job_003_run(
    job_store: JobStore, runner: JobRunner, job_connection: psycopg.Connection[Any]
) -> ScenarioRun:
    """A handler that fails on every attempt, run until the job stops being claimable."""
    job_id = job_store.create_job("fail_transient", None, max_attempts=JOB_003_MAX_ATTEMPTS)
    run_until_terminal(runner, job_store, job_id)
    job = job_store.read_job(job_id)
    assert job is not None
    return ScenarioRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        job=job,
        attempts=attempts_of(job_connection, job_id),
        effects=effects_of(job_connection, job_id),
    )


def test_job_003_ends_failed_with_the_budget_exactly_spent(job_003_run: ScenarioRun) -> None:
    """JOB-003 transition row 4; CONTRACT-JOB@0.1 I4."""
    job = job_003_run.job
    assert job["state"] == JobState.FAILED
    assert job["attempt_count"] == JOB_003_MAX_ATTEMPTS == job["max_attempts"]
    assert job["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert job["lease_owner"] is None
    assert [a["attempt_no"] for a in job_003_run.attempts] == [1, 2]
    for attempt in job_003_run.attempts:
        assert attempt["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
        assert attempt["error_class"] == ErrorClass.PLATFORM_TRANSIENT
    assert job_003_run.effects == []


def test_job_003_is_not_claimed_again_after_a_further_claim_interval(
    job_003_run: ScenarioRun,
    runner: JobRunner,
    job_store: JobStore,
    job_connection: psycopg.Connection[Any],
) -> None:
    """JOB-003 step 4: an exhausted job stops being work, not just stops being due."""
    would_have_waited = job_store.backoff.delay_ms(JOB_003_MAX_ATTEMPTS) / 1000.0
    deadline = time.monotonic() + would_have_waited * 3 + 0.05
    while time.monotonic() < deadline:
        assert runner.run_once() is None
        time.sleep(RETRY_INTERVAL_SECONDS)
    assert len(attempts_of(job_connection, job_003_run.job_id)) == 2
    job = job_store.read_job(job_003_run.job_id)
    assert job is not None
    assert job["state"] == JobState.FAILED


def test_job_003_an_exhausted_job_is_distinguishable_from_a_backing_off_one(
    job_003_run: ScenarioRun, job_store: JobStore, runner: JobRunner
) -> None:
    """JOB-003's load-bearing assertion, read through the fields an operator surface uses."""
    waiting_id = job_store.create_job("fail_transient", None, max_attempts=3)
    assert runner.run_once() is not None
    waiting = job_store.read_job(waiting_id)
    exhausted = job_store.read_job(job_003_run.job_id)
    assert waiting is not None and exhausted is not None
    assert (waiting["state"], exhausted["state"]) == (JobState.PENDING, JobState.FAILED)
    assert waiting["terminal_reason"] is None
    assert exhausted["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert waiting["attempt_count"] < waiting["max_attempts"]
    assert exhausted["attempt_count"] == exhausted["max_attempts"]


def test_job_003_terminal_event_says_the_budget_was_spent(
    job_003_run: ScenarioRun, log_stream: StringIO
) -> None:
    """JOB-003's telemetry: exhaustion is distinguishable from a permanent failure."""
    terminal = [
        record
        for record in events_named(log_stream, "job.transition")
        if record["to_state"] == JobState.FAILED
    ]
    assert len(terminal) == 1
    assert terminal[0]["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert terminal[0]["attempt_count"] == terminal[0]["max_attempts"] == JOB_003_MAX_ATTEMPTS
    assert terminal[0]["correlation_id"] == job_003_run.correlation_id


# --------------------------------------------------------------------------- #
# JOB-004 — a permanent failure terminates without spending the retry budget
# --------------------------------------------------------------------------- #

JOB_004_MAX_ATTEMPTS = 5
UNREGISTERED_HANDLER = "not-registered"


@dataclass(frozen=True)
class TwoJobRun:
    permanent: ScenarioRun
    unknown: ScenarioRun


@pytest.fixture
def job_004_run(
    job_store: JobStore, runner: JobRunner, job_connection: psycopg.Connection[Any]
) -> TwoJobRun:
    """Two jobs with generous budgets, run until neither is claimable."""
    permanent_id = job_store.create_job(
        "fail_permanent", {"opaque": True}, max_attempts=JOB_004_MAX_ATTEMPTS
    )
    unknown_id = job_store.create_job(
        UNREGISTERED_HANDLER, {"opaque": True}, max_attempts=JOB_004_MAX_ATTEMPTS
    )
    drain(runner)

    def _read(job_id: UUID) -> ScenarioRun:
        job = job_store.read_job(job_id)
        assert job is not None
        return ScenarioRun(
            job_id=job_id,
            correlation_id=str(job["correlation_id"]),
            job=job,
            attempts=attempts_of(job_connection, job_id),
            effects=effects_of(job_connection, job_id),
        )

    return TwoJobRun(permanent=_read(permanent_id), unknown=_read(unknown_id))


def test_job_004_both_jobs_fail_on_their_first_attempt_with_budget_untouched(
    job_004_run: TwoJobRun,
) -> None:
    """JOB-004 transition rows 3, 6: terminal with four attempts of budget never spent."""
    for run in (job_004_run.permanent, job_004_run.unknown):
        assert run.job["state"] == JobState.FAILED
        assert run.job["attempt_count"] == 1
        assert run.job["max_attempts"] == JOB_004_MAX_ATTEMPTS
        assert len(run.attempts) == 1
        assert run.attempts[0]["outcome"] == AttemptOutcome.PERMANENT_FAILURE
        assert run.effects == []


def test_job_004_the_two_terminal_reasons_are_different(job_004_run: TwoJobRun) -> None:
    """JOB-004 covers both non-retryable classes reachable in this platform."""
    assert job_004_run.permanent.job["terminal_reason"] == ErrorClass.PLATFORM_PERMANENT
    assert job_004_run.unknown.job["terminal_reason"] == ErrorClass.HANDLER_UNKNOWN
    assert job_004_run.permanent.attempts[0]["error_class"] == ErrorClass.PLATFORM_PERMANENT
    assert job_004_run.unknown.attempts[0]["error_class"] == ErrorClass.HANDLER_UNKNOWN


def test_job_004_the_unknown_handler_summary_names_the_handler(
    job_004_run: TwoJobRun, registry: HandlerRegistry
) -> None:
    """JOB-004: the operator's next action is to register it, so the summary says which."""
    summary = job_004_run.unknown.attempts[0]["error_summary"]
    assert UNREGISTERED_HANDLER in summary
    assert UNREGISTERED_HANDLER not in registry
    assert job_004_run.unknown.attempts[0]["error_detail"]["requested"] == UNREGISTERED_HANDLER


def test_job_004_the_two_jobs_events_are_separable_by_correlation_id(
    job_004_run: TwoJobRun, log_stream: StringIO
) -> None:
    """JOB-004 telemetry: one identifier per job, and neither event stream mixes."""
    assert job_004_run.permanent.correlation_id != job_004_run.unknown.correlation_id
    for run in (job_004_run.permanent, job_004_run.unknown):
        about = [
            record for record in events(log_stream) if record.get("job_id") == str(run.job_id)
        ]
        assert about
        assert {record["correlation_id"] for record in about} == {run.correlation_id}


# --------------------------------------------------------------------------- #
# JOB-005 — interruption before and after a durable effect reaches a
# documented state
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class HaltCase:
    """One of the scenario's two interruption points, and what separates them."""

    handler: str
    #: Effect rows in existence at the moment the interrupted process died.
    effects_when_interrupted: int
    #: Suppressed inserts the recovering process is expected to report.
    suppressed_on_recovery: int


HALT_CASES = (
    HaltCase("halt_before_effect", effects_when_interrupted=0, suppressed_on_recovery=0),
    HaltCase("halt_after_effect", effects_when_interrupted=1, suppressed_on_recovery=1),
)


@pytest.mark.parametrize("case", HALT_CASES, ids=[case.handler for case in HALT_CASES])
def test_job_005_interruption_on_either_side_of_the_effect_reaches_one_effect_and_one_success(
    case: HaltCase,
    job_store: JobStore,
    platform_config: PlatformConfig,
    job_connection: psycopg.Connection[Any],
) -> None:
    """JOB-005 cases A and B; CONTRACT-JOB@0.1 I1, I3; OQ-006 H1.

    Copy-adapted from ``experiments/integrated-p0/tests/test_job_interruption.py``.
    A real worker process claims the job and ends itself with ``os._exit`` on
    either side of applying its one durable effect (``halt_before_effect`` /
    ``halt_after_effect`` in ``platform_core.handlers.synthetic``, unmodified
    from P0), and a second process recovers it. Whether the process died before
    or after the effect, the job must end with exactly one effect and a
    terminal state — the two interruption points are not symmetric in the code
    but must be symmetric in the outcome.
    """
    job_id = job_store.create_job(case.handler, {"halt_on_attempt": 1}, max_attempts=3)

    # 2. Let the worker claim it and terminate itself uncleanly.
    interrupted = run_worker(
        platform_config,
        "--once",
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    assert interrupted.returncode == DEFAULT_EXIT_CODE
    # A killed process writes no report; the database is what it left behind.
    assert REPORT_EVENT not in interrupted.stdout

    job_while_interrupted = job_store.read_job(job_id)
    assert job_while_interrupted is not None
    assert job_while_interrupted["state"] == JobState.RUNNING
    attempts_while_interrupted = attempts_of(job_connection, job_id)
    assert len(attempts_while_interrupted) == 1
    assert attempts_while_interrupted[0]["finished_at"] is None
    effects_while_interrupted = effects_of(job_connection, job_id)
    assert len(effects_while_interrupted) == case.effects_when_interrupted

    # The lease outlives the process that held it; the platform waits it out.
    wait_until(
        lambda: lease_has_expired(job_connection, job_id),
        "the lease of the interrupted worker has expired",
    )

    # 3. Restart the worker and run until the job is terminal.
    recovered = run_worker(
        platform_config,
        "--once",
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    assert recovered.returncode == EXIT_OK, recovered.stderr
    report = parse_report(recovered.stdout)

    job = job_store.read_job(job_id)
    assert job is not None
    first, second = attempts_of(job_connection, job_id)
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["outcome"] == AttemptOutcome.ABANDONED
    assert first["error_class"] == ErrorClass.LEASE_ABANDONED
    assert first["finished_at"] is not None
    assert second["outcome"] == AttemptOutcome.SUCCEEDED
    assert second["worker_id"] != first["worker_id"], "a different process recovered it"
    assert job["state"] == JobState.SUCCEEDED
    assert job["terminal_reason"] is None
    assert job["attempt_count"] == 2
    assert job["lease_owner"] is None

    # I1, at the one place at-least-once delivery is actually dangerous.
    effects = effects_of(job_connection, job_id)
    assert len(effects) == 1
    assert all_effects(job_connection) == effects

    # The scenario's own proof that the two interruption points were different.
    metrics = report["metrics"]
    assert metrics["suppressed_duplicate_effects"] == case.suppressed_on_recovery
    assert metrics["abandoned_attempts"] == 1
    assert metrics["transitions"][JobState.SUCCEEDED] == 1
    assert metrics["rejected_completions"] == 0

    # I5 across a process boundary — the correlation identifier is stored on
    # the job, not held only in the process that was killed.
    identifier = job["correlation_id"]
    assert {a["correlation_id"] for a in (first, second)} == {identifier}
    for finished in (interrupted, recovered):
        about = [
            record
            for record in log_events(finished.stderr)
            if record.get("job_id") == str(job_id)
        ]
        assert about, "each process logged about the job it claimed"
        assert {record["correlation_id"] for record in about} == {identifier}

    reclaimed = [
        record
        for record in log_events(recovered.stderr)
        if record["event"] == "job.attempt_abandoned"
    ]
    assert len(reclaimed) == 1
    assert reclaimed[0]["attempt_no"] == 1
    assert reclaimed[0]["error_class"] == ErrorClass.LEASE_ABANDONED
