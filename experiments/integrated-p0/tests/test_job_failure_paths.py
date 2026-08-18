"""JOB-002, JOB-003, and JOB-004 executed: the three failure paths of one process.

The three scenarios divide the failure surface by what the platform is entitled
to do next, and they are written together because each one's evidence is partly
that it is *not* one of the others:

* JOB-002 — a failure the contract permits repeating, repeated once, recovering.
* JOB-003 — the same failure repeated until the budget is gone, ending terminal.
* JOB-004 — a failure the contract forbids repeating, ending terminal with four
  attempts of budget untouched.

None of them needs a second process: the interruption points that do are
JOB-005's. What they do need is real time, because a rescheduled job is not
claimable until its backoff has passed, and mutating ``available_at`` to skip the
wait would remove the one thing JOB-002 asks to be observed. The configured
backoff base is small enough that waiting it out costs milliseconds, which is
what the scenarios mean by "compressed backoff".

Everything here is synthetic and `public`. The handlers succeed, fail, or refuse;
none of them computes anything, and no payload below means anything to the
platform.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any
from uuid import UUID

import psycopg
import pytest
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.metrics import MetricsRegistry

from tests.conftest import (
    all_effects,
    attempts_of,
    effects_of,
    events,
    events_named,
    transitions,
)

#: How long a scenario waits for a job to stop moving. Every wait here is for a
#: backoff measured in tens of milliseconds, so this is a failure report rather
#: than a duration anything depends on.
SETTLE_TIMEOUT_SECONDS = 10.0

#: How often a waiting loop tries again. Short enough that the backoff, rather
#: than the polling, decides when the second attempt happens.
RETRY_INTERVAL_SECONDS = 0.01


def run_until_terminal(
    runner: JobRunner,
    store: JobStore,
    job_id: UUID,
    timeout: float = SETTLE_TIMEOUT_SECONDS,
) -> list[RunOutcome]:
    """"Run the worker until the job reaches a terminal state", as a loop.

    A pass that finds nothing means the job is waiting out its backoff, so the
    loop waits with it. That wait is the scenario's own transition — the job is
    ``PENDING`` and not yet due — and the deadline is only here so that a job
    which never settles is reported as one.
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


@dataclass(frozen=True)
class ScenarioRun:
    """One scenario's Action section, read back the way its document asks."""

    job_id: UUID
    correlation_id: str
    job: dict[str, Any]
    attempts: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    outcomes: list[RunOutcome]


def read_back(
    store: JobStore,
    connection: psycopg.Connection[Any],
    job_id: UUID,
    outcomes: list[RunOutcome],
) -> ScenarioRun:
    job = store.read_job(job_id)
    assert job is not None
    return ScenarioRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        job=job,
        attempts=attempts_of(connection, job_id),
        effects=effects_of(connection, job_id),
        outcomes=outcomes,
    )


# --------------------------------------------------------------------------- #
# JOB-002 — a retryable failure is rescheduled and a later attempt succeeds
# --------------------------------------------------------------------------- #


@pytest.fixture
def job_002_run(
    store: JobStore,
    runner: JobRunner,
    connection: psycopg.Connection[Any],
) -> ScenarioRun:
    """Create a job that fails once, run it to terminal, read everything back."""
    job_id = store.create_job(
        "fail_transient", {"fail_until_attempt": 1}, max_attempts=3
    )
    outcomes = run_until_terminal(runner, store, job_id)
    return read_back(store, connection, job_id, outcomes)


def test_job_002_spends_the_budget_one_attempt_at_a_time(job_002_run: ScenarioRun) -> None:
    """Rows 1, 4 and 6 of the transition table: two claims, two attempts, success."""
    job = job_002_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 2
    assert job["max_attempts"] == 3
    assert job["terminal_reason"] is None
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None
    assert [outcome.state for outcome in job_002_run.outcomes] == [
        JobState.PENDING,
        JobState.SUCCEEDED,
    ]


def test_job_002_closes_the_first_attempt_as_a_retryable_failure(
    job_002_run: ScenarioRun,
) -> None:
    """Rows 2 and 5: the failure is classified, and the success carries no class."""
    first, second = job_002_run.attempts
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert first["error_class"] == ErrorClass.PLATFORM_TRANSIENT
    assert first["finished_at"] is not None
    assert second["outcome"] == AttemptOutcome.SUCCEEDED
    assert second["error_class"] is None
    assert second["error_summary"] is None


def test_job_002_moves_available_at_into_the_future_when_it_reschedules(
    job_002_run: ScenarioRun, log_stream: StringIO
) -> None:
    """Row 3, and the assertion the document states in its own words.

    The comparison is between two database timestamps — when the attempt closed
    and when the job said it would next be due — so it is a statement about the
    platform's scheduling and not about the clock this test runs on.
    """
    failed_at = job_002_run.attempts[0]["finished_at"]
    # The job kept the availability the reschedule gave it: a success does not
    # rewrite it, so the row still shows when the second attempt became due.
    assert job_002_run.job["available_at"] > failed_at
    rescheduled = [
        record
        for record in events_named(log_stream, "job.transition")
        if record["to_state"] == JobState.PENDING and record["from_state"] == JobState.RUNNING
    ]
    assert len(rescheduled) == 1
    assert datetime.fromisoformat(rescheduled[0]["available_at"]) > failed_at
    assert rescheduled[0]["attempt_no"] == 1
    assert rescheduled[0]["error_class"] == ErrorClass.PLATFORM_TRANSIENT
    assert rescheduled[0]["error_summary"]


def test_job_002_leaves_exactly_one_effect_and_the_failed_attempt_left_none(
    job_002_run: ScenarioRun,
) -> None:
    """The failed attempt must not produce an effect, and the successful one must.

    Which attempt wrote it is readable from the effect's own opaque value, so
    "attempt 1 wrote nothing" is observed rather than inferred from a count.
    """
    assert len(job_002_run.effects) == 1
    assert job_002_run.effects[0]["payload"]["attempt_no"] == 2


def test_job_002_keeps_the_first_attempt_readable_after_the_job_succeeds(
    job_002_run: ScenarioRun,
) -> None:
    """The scenario's Intent: a job that eventually succeeded must still show the failure.

    Read after the job is terminal, from the row an operator surface would read.
    """
    assert job_002_run.job["state"] == JobState.SUCCEEDED
    first = job_002_run.attempts[0]
    assert first["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert first["error_summary"]
    # Protected debug detail is recorded, and the summary quotes no payload value.
    assert first["error_detail"] == {"attempt_no": 1, "fails_through_attempt": 1}
    assert "fail_until_attempt" not in first["error_summary"]


def test_job_002_shares_one_correlation_id_across_both_attempts(
    job_002_run: ScenarioRun, log_stream: StringIO
) -> None:
    """I5 across a reschedule: the identifier belongs to the job, not to the attempt."""
    assert {attempt["correlation_id"] for attempt in job_002_run.attempts} == {
        job_002_run.correlation_id
    }
    assert {record["correlation_id"] for record in events(log_stream)} == {
        job_002_run.correlation_id
    }


def test_job_002_counts_both_attempts_and_both_transitions(
    job_002_run: ScenarioRun, metrics: MetricsRegistry
) -> None:
    """The scenario's metrics, mapped onto the counters the contract defines.

    The document names a counter for `RETRYABLE_FAILURE`; the contract's
    observability list defines transition counters by *target job state*, and the
    target of a retryable failure within budget is `PENDING`. The two creation
    and reschedule increments therefore land in one counter, which is recorded
    here rather than smoothed over.
    """
    reading = metrics.read()
    assert reading.transitions[JobState.PENDING] == 2  # created, then rescheduled
    assert reading.transitions[JobState.RUNNING] == 2
    assert reading.transitions[JobState.SUCCEEDED] == 1
    assert reading.transitions[JobState.FAILED] == 0
    assert reading.attempt_duration.count == 2
    assert reading.suppressed_duplicate_effects == 0
    assert reading.abandoned_attempts == 0
    assert reading.rejected_completions == 0


# --------------------------------------------------------------------------- #
# JOB-003 — retry exhaustion produces an observable terminal state
# --------------------------------------------------------------------------- #

JOB_003_MAX_ATTEMPTS = 2


@pytest.fixture
def job_003_run(
    store: JobStore,
    runner: JobRunner,
    connection: psycopg.Connection[Any],
) -> ScenarioRun:
    """A handler that fails on every attempt, run until the job stops being claimable."""
    job_id = store.create_job("fail_transient", None, max_attempts=JOB_003_MAX_ATTEMPTS)
    outcomes = run_until_terminal(runner, store, job_id)
    return read_back(store, connection, job_id, outcomes)


def test_job_003_ends_failed_with_the_budget_exactly_spent(job_003_run: ScenarioRun) -> None:
    """Row 4: the terminal transition names the class that kept failing."""
    job = job_003_run.job
    assert job["state"] == JobState.FAILED
    assert job["attempt_count"] == JOB_003_MAX_ATTEMPTS == job["max_attempts"]
    assert job["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None


def test_job_003_records_two_retryable_failures_and_no_third_attempt(
    job_003_run: ScenarioRun,
) -> None:
    """Rows 1 and 3, and invariant I4 in the durable state."""
    assert [attempt["attempt_no"] for attempt in job_003_run.attempts] == [1, 2]
    for attempt in job_003_run.attempts:
        assert attempt["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
        assert attempt["error_class"] == ErrorClass.PLATFORM_TRANSIENT
        assert attempt["error_detail"] is not None


def test_job_003_produces_no_durable_effect(
    job_003_run: ScenarioRun, connection: psycopg.Connection[Any]
) -> None:
    assert job_003_run.effects == []
    assert all_effects(connection) == []


def test_job_003_is_not_claimed_again_after_a_further_claim_interval(
    job_003_run: ScenarioRun,
    runner: JobRunner,
    store: JobStore,
    connection: psycopg.Connection[Any],
) -> None:
    """Step 4. An exhausted job stops being work, not just stops being due.

    The wait is longer than the backoff the second failure would have used had
    the job been rescheduled, so "no third claim" is a statement about the
    terminal state rather than about having looked too early.
    """
    would_have_waited = store.backoff.delay_ms(JOB_003_MAX_ATTEMPTS) / 1000.0
    deadline = time.monotonic() + would_have_waited * 3 + 0.05
    while time.monotonic() < deadline:
        assert runner.run_once() is None
        time.sleep(RETRY_INTERVAL_SECONDS)

    assert len(attempts_of(connection, job_003_run.job_id)) == 2
    job = store.read_job(job_003_run.job_id)
    assert job is not None
    assert job["state"] == JobState.FAILED
    assert job["attempt_count"] == JOB_003_MAX_ATTEMPTS


def test_job_003_terminal_event_says_the_budget_was_spent(
    job_003_run: ScenarioRun, log_stream: StringIO
) -> None:
    """The telemetry line that separates exhaustion from a permanent failure."""
    terminal = [
        record
        for record in events_named(log_stream, "job.transition")
        if record["to_state"] == JobState.FAILED
    ]
    assert len(terminal) == 1
    assert terminal[0]["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert terminal[0]["attempt_count"] == terminal[0]["max_attempts"] == JOB_003_MAX_ATTEMPTS
    assert terminal[0]["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert terminal[0]["correlation_id"] == job_003_run.correlation_id
    assert transitions(log_stream)[-1] == (JobState.RUNNING, JobState.FAILED)


def test_job_003_an_exhausted_job_is_distinguishable_from_a_backing_off_one(
    job_003_run: ScenarioRun, store: JobStore, runner: JobRunner
) -> None:
    """The scenario's load-bearing assertion, from the fields alone.

    A second job is failed once and left waiting out its backoff, and the two are
    compared through ``read_job`` — the row an operator surface renders. Three
    fields separate them and each says something the others do not: ``state``
    says whether the platform will act again, ``terminal_reason`` says why it
    stopped, and ``attempt_count`` against ``max_attempts`` says whether anything
    is left to try.
    """
    waiting_id = store.create_job("fail_transient", None, max_attempts=3)
    assert runner.run_once() is not None
    waiting = store.read_job(waiting_id)
    exhausted = store.read_job(job_003_run.job_id)
    assert waiting is not None and exhausted is not None

    assert (waiting["state"], exhausted["state"]) == (JobState.PENDING, JobState.FAILED)
    assert waiting["terminal_reason"] is None
    assert exhausted["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    assert waiting["attempt_count"] < waiting["max_attempts"]
    assert exhausted["attempt_count"] == exhausted["max_attempts"]
    # Both are failures of the same class, so the class alone does not separate
    # them: what does is that one job is still claimable and the other is not.
    assert waiting["available_at"] > exhausted["updated_at"]


# --------------------------------------------------------------------------- #
# JOB-004 — a permanent failure terminates without spending the retry budget
# --------------------------------------------------------------------------- #

JOB_004_MAX_ATTEMPTS = 5

UNREGISTERED_HANDLER = "not-registered"


@dataclass(frozen=True)
class TwoJobRun:
    """JOB-004 reads two jobs, and half its evidence is that they differ."""

    permanent: ScenarioRun
    unknown: ScenarioRun
    outcomes: list[RunOutcome]


@pytest.fixture
def job_004_run(
    store: JobStore,
    runner: JobRunner,
    connection: psycopg.Connection[Any],
) -> TwoJobRun:
    """Two jobs with generous budgets, run until neither is claimable."""
    permanent_id = store.create_job(
        "fail_permanent", {"opaque": True}, max_attempts=JOB_004_MAX_ATTEMPTS
    )
    unknown_id = store.create_job(
        UNREGISTERED_HANDLER, {"opaque": True}, max_attempts=JOB_004_MAX_ATTEMPTS
    )
    outcomes = drain(runner)
    return TwoJobRun(
        permanent=read_back(store, connection, permanent_id, outcomes),
        unknown=read_back(store, connection, unknown_id, outcomes),
        outcomes=outcomes,
    )


def test_job_004_both_jobs_fail_on_their_first_attempt(job_004_run: TwoJobRun) -> None:
    """Rows 3 and 6: terminal with four attempts of budget never touched."""
    for run in (job_004_run.permanent, job_004_run.unknown):
        assert run.job["state"] == JobState.FAILED
        assert run.job["attempt_count"] == 1
        assert run.job["max_attempts"] == JOB_004_MAX_ATTEMPTS
        assert run.job["lease_owner"] is None
        assert len(run.attempts) == 1
        assert run.attempts[0]["outcome"] == AttemptOutcome.PERMANENT_FAILURE


def test_job_004_the_two_terminal_reasons_are_different(job_004_run: TwoJobRun) -> None:
    """The scenario covers both non-retryable classes, and they must stay apart."""
    assert job_004_run.permanent.job["terminal_reason"] == ErrorClass.PLATFORM_PERMANENT
    assert job_004_run.unknown.job["terminal_reason"] == ErrorClass.HANDLER_UNKNOWN
    assert (
        job_004_run.permanent.attempts[0]["error_class"] == ErrorClass.PLATFORM_PERMANENT
    )
    assert job_004_run.unknown.attempts[0]["error_class"] == ErrorClass.HANDLER_UNKNOWN


def test_job_004_the_unknown_handler_summary_names_the_handler(
    job_004_run: TwoJobRun, registry: HandlerRegistry
) -> None:
    """The operator's next action is to register it, so the summary has to say which.

    Handler names are configuration rather than payload, which is why naming one
    in an operator-visible summary does not breach the redaction boundary.
    """
    summary = job_004_run.unknown.attempts[0]["error_summary"]
    assert UNREGISTERED_HANDLER in summary
    assert UNREGISTERED_HANDLER not in registry
    # Nothing was invoked on its behalf: the failure is the resolution failing.
    assert job_004_run.unknown.attempts[0]["error_detail"]["requested"] == UNREGISTERED_HANDLER


def test_job_004_neither_job_leaves_a_durable_effect(
    job_004_run: TwoJobRun, connection: psycopg.Connection[Any]
) -> None:
    assert job_004_run.permanent.effects == []
    assert job_004_run.unknown.effects == []
    assert all_effects(connection) == []


def test_job_004_nothing_is_retried_and_the_queue_is_empty_afterwards(
    job_004_run: TwoJobRun, runner: JobRunner
) -> None:
    assert len(job_004_run.outcomes) == 2
    assert all(outcome.state == JobState.FAILED for outcome in job_004_run.outcomes)
    assert runner.run_once() is None


def test_job_004_counts_two_terminal_transitions_and_no_reschedule(
    job_004_run: TwoJobRun, metrics: MetricsRegistry
) -> None:
    """"Two FAILED transition increments; zero retryable-failure increments."

    A retryable failure inside budget arrives at `PENDING`, so a reschedule would
    show up as a third increment on that counter beyond the two creations.
    """
    reading = metrics.read()
    assert reading.transitions[JobState.FAILED] == 2
    assert reading.transitions[JobState.PENDING] == 2
    assert reading.transitions[JobState.RUNNING] == 2
    assert reading.transitions[JobState.SUCCEEDED] == 0


def test_job_004_the_two_jobs_events_are_separable_by_correlation_id(
    job_004_run: TwoJobRun, log_stream: StringIO
) -> None:
    """One identifier per job, and every event about a job carries only its own."""
    assert job_004_run.permanent.correlation_id != job_004_run.unknown.correlation_id
    for run in (job_004_run.permanent, job_004_run.unknown):
        about = [
            record
            for record in events(log_stream)
            if record.get("job_id") == str(run.job_id)
        ]
        assert about
        assert {record["correlation_id"] for record in about} == {run.correlation_id}
