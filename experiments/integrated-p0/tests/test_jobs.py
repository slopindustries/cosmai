"""JOB-001 end to end, and the fencing rule the rest of the `JOB` family rests on.

Two things are being established here, and they are different in kind.

**JOB-001 is executed, not approximated.** The scenario document lists a
transition table, a durable-effect expectation, and a telemetry expectation, and
every row of all three is asserted below against the database and the log the run
actually produced. ``-k job_001`` selects exactly that scenario, which is the
command the document names as its verification procedure.

**Fencing is proved before the scenario that needs it exists.** JOB-006 runs a
worker that stalls past its lease in a separate process; that is T2 work. The
mechanism it depends on — a completion refused because the worker no longer owns
the lease, or because its own attempt is already closed — is testable in one
process today, and testing it now means a JOB-006 failure later can be attributed
to the worker lifecycle rather than to the rule. What is proved here is the
stronger half of the claim: the refused write changes *nothing*. The job keeps
the reclaiming worker's lease, both attempt rows keep the outcomes they had, and
no effect appears.

Everything under test is synthetic and `public`. No handler here fetches,
parses, or transforms anything; they succeed, fail, or leave one opaque effect,
because P0-A has no answer to what a job means and must not imply one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import StringIO
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import (
    ErrorClass,
    HandlerUnknownError,
    PlatformPermanentError,
    PlatformTransientError,
)
from platform_core.handlers.synthetic import SYNTHETIC_HANDLERS, synthetic_registry
from platform_core.jobs.registry import HandlerRegistry, JobContext, effect_key_for
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.state import (
    ATTEMPT_OUTCOMES,
    JOB_STATES,
    TRANSITIONS,
    AttemptOutcome,
    JobState,
)
from platform_core.jobs.store import CLAIM_NEXT, Backoff, JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from psycopg.rows import dict_row

WORKER = "worker-under-test"

LEASE_SECONDS = 5.0

MAX_ATTEMPTS = 3

#: A lease that is already over by the time the next statement runs. It is the
#: single-process stand-in for the interruption JOB-006 produces with a real one.
EXPIRED_LEASE = 0.0


# --------------------------------------------------------------------------- #
# Fixtures
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
def connection(database: PlatformConfig) -> Any:
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
def registry() -> HandlerRegistry:
    return synthetic_registry()


@pytest.fixture
def runner(store: JobStore, registry: HandlerRegistry) -> JobRunner:
    return JobRunner(store, registry, worker_id=WORKER, lease_seconds=LEASE_SECONDS)


# --------------------------------------------------------------------------- #
# Reading the database back
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


def public_tables(connection: psycopg.Connection[Any]) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select table_name from information_schema.tables where table_schema = 'public'"
        )
        return {str(row[0]) for row in cursor.fetchall()}


def constraint_body(connection: psycopg.Connection[Any], name: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = %s", (name,)
        )
        row = cursor.fetchone()
    assert row is not None, f"no constraint named {name}"
    return str(row[0])


def unwritten_effect(effect_key: str, payload: Any = None) -> bool:
    """The effect applier for context tests that must reach no database."""
    return True


def events(log_stream: StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_stream.getvalue().splitlines() if line.strip()]


def events_named(log_stream: StringIO, event: str) -> list[dict[str, Any]]:
    return [record for record in events(log_stream) if record["event"] == event]


def transitions(log_stream: StringIO) -> list[tuple[Any, Any]]:
    return [
        (record["from_state"], record["to_state"])
        for record in events_named(log_stream, "job.transition")
    ]


# --------------------------------------------------------------------------- #
# JOB-001 — successful execution
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScenarioRun:
    """One execution of JOB-001, with everything the document asks to be read."""

    job_id: UUID
    correlation_id: str
    job: dict[str, Any]
    attempts: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    tables: set[str]


@pytest.fixture
def job_001_run(
    store: JobStore,
    runner: JobRunner,
    connection: psycopg.Connection[Any],
) -> ScenarioRun:
    """The scenario's Action section: create, run to terminal, read everything back."""
    job_id = store.create_job("succeed", {"opaque": "value"}, max_attempts=MAX_ATTEMPTS)

    outcome = runner.run_once()
    assert outcome is not None, "the job was created due, so one pass must claim it"
    assert outcome.accepted, outcome.completion.reason

    # "Run the worker until the job leaves PENDING and reaches a terminal state."
    # A second pass must find nothing: a terminal job is not claimable.
    assert runner.run_once() is None

    job = store.read_job(job_id)
    assert job is not None
    return ScenarioRun(
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        job=job,
        attempts=attempts_of(connection, job_id),
        effects=effects_of(connection, job_id),
        tables=public_tables(connection),
    )


def test_job_001_reaches_the_terminal_job_state_the_scenario_states(
    job_001_run: ScenarioRun,
) -> None:
    """Row 5 of the transition table: RUNNING to SUCCEEDED, lease cleared."""
    job = job_001_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["attempt_count"] == 1
    assert job["max_attempts"] == MAX_ATTEMPTS
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None
    assert job["terminal_reason"] is None
    assert job["created_at"] is not None
    assert job["correlation_id"]


def test_job_001_opens_and_closes_exactly_one_attempt(job_001_run: ScenarioRun) -> None:
    """Rows 3 and 4: one attempt, numbered 1, closed SUCCEEDED with no error."""
    assert len(job_001_run.attempts) == 1
    attempt = job_001_run.attempts[0]
    assert attempt["attempt_no"] == 1
    assert attempt["worker_id"] == WORKER
    assert attempt["started_at"] is not None
    assert attempt["finished_at"] is not None
    assert attempt["outcome"] == AttemptOutcome.SUCCEEDED
    assert attempt["error_class"] is None
    assert attempt["error_summary"] is None
    # "Protected debug behavior: error_detail is null throughout."
    assert attempt["error_detail"] is None
    # I5 — the attempt carries the job's correlation identifier.
    assert attempt["correlation_id"] == job_001_run.correlation_id


def test_job_001_produces_exactly_one_durable_effect(job_001_run: ScenarioRun) -> None:
    """The scenario's definition of "one durable effect" in P0-A."""
    assert len(job_001_run.effects) == 1
    effect = job_001_run.effects[0]
    assert effect["job_id"] == job_001_run.job_id
    assert effect["applied_at"] is not None


def test_job_001_writes_no_table_beyond_the_three_and_the_migration_ledger(
    job_001_run: ScenarioRun,
) -> None:
    """"No write to any table other than the three above and schema_migrations."

    Enforced as an absence of tables rather than an absence of rows: P0-A has
    exactly four, so a domain-shaped side channel would have to appear here first.
    """
    assert job_001_run.tables == {"job", "job_attempt", "platform_effect", "schema_migrations"}


def test_job_001_emits_one_event_per_transition_with_the_required_fields(
    job_001_run: ScenarioRun, log_stream: StringIO
) -> None:
    """The scenario's telemetry section, transition by transition."""
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
        assert record["ts"]


def test_job_001_carries_one_correlation_id_across_every_line_and_row(
    job_001_run: ScenarioRun, log_stream: StringIO
) -> None:
    """I5 — correlation is total: creation, claim, completion, and the attempt row."""
    identifiers = {record["correlation_id"] for record in events(log_stream)}
    assert identifiers == {job_001_run.correlation_id}
    assert {attempt["correlation_id"] for attempt in job_001_run.attempts} == {
        job_001_run.correlation_id
    }


def test_job_001_records_the_metrics_the_scenario_names(
    job_001_run: ScenarioRun, metrics: MetricsRegistry
) -> None:
    """Transition counter for SUCCEEDED, and an attempt duration in milliseconds."""
    reading = metrics.read()
    assert reading.transitions[JobState.SUCCEEDED] == 1
    assert reading.transitions[JobState.RUNNING] == 1
    assert reading.transitions[JobState.PENDING] == 1
    assert reading.transitions[JobState.FAILED] == 0
    assert reading.attempt_duration.count == 1
    assert reading.attempt_duration.total_ms >= 0.0
    # No deviation from the base path occurred, so none of these may have fired.
    assert reading.abandoned_attempts == 0
    assert reading.suppressed_duplicate_effects == 0
    assert reading.rejected_completions == 0


# --------------------------------------------------------------------------- #
# Fencing
# --------------------------------------------------------------------------- #


def reclaimed_pair(store: JobStore, handler: str = "succeed") -> tuple[Any, Any]:
    """A job claimed by one worker, then reclaimed by another after lease expiry."""
    job_id = store.create_job(handler, {"opaque": True}, max_attempts=MAX_ATTEMPTS)
    stale = store.claim_next("worker-stale", lease_seconds=EXPIRED_LEASE)
    assert stale is not None
    fresh = store.claim_next("worker-fresh", lease_seconds=LEASE_SECONDS)
    assert fresh is not None
    assert fresh.job_id == job_id
    assert fresh.reclaimed_from_attempt_no == stale.attempt_no
    return stale, fresh


def test_a_worker_that_lost_its_lease_cannot_record_success(
    store: JobStore, connection: psycopg.Connection[Any], metrics: MetricsRegistry
) -> None:
    """The contract's fencing rule, and its "changes nothing" clause."""
    stale, fresh = reclaimed_pair(store)
    before = store.read_job(stale.job_id)
    attempts_before = attempts_of(connection, stale.job_id)

    refused = store.complete_success(stale.job_id, stale.attempt_id, stale.worker_id)

    assert not refused
    assert refused.reason is not None
    assert refused.state is None
    # Nothing moved: same state, same lease holder, same deadline, same counts.
    assert store.read_job(stale.job_id) == before
    assert attempts_of(connection, stale.job_id) == attempts_before
    assert before is not None
    assert before["lease_owner"] == fresh.worker_id
    assert before["state"] == JobState.RUNNING
    assert all_effects(connection) == []
    assert metrics.read().rejected_completions == 1


@pytest.mark.parametrize(
    "error",
    [
        PlatformTransientError("a stale retryable failure"),
        PlatformPermanentError("a stale permanent failure"),
    ],
    ids=["retryable", "permanent"],
)
def test_a_worker_that_lost_its_lease_cannot_record_a_failure_either(
    store: JobStore, connection: psycopg.Connection[Any], error: Any
) -> None:
    """Fencing covers every outcome, not just the one that would look like a win."""
    stale, _ = reclaimed_pair(store)
    before = store.read_job(stale.job_id)
    attempts_before = attempts_of(connection, stale.job_id)

    if error.retryable:
        refused = store.complete_retryable(
            stale.job_id, stale.attempt_id, stale.worker_id, error
        )
    else:
        refused = store.complete_permanent(
            stale.job_id, stale.attempt_id, stale.worker_id, error
        )

    assert not refused
    assert store.read_job(stale.job_id) == before
    assert attempts_of(connection, stale.job_id) == attempts_before


def test_the_reclaiming_worker_can_still_complete_after_the_stale_write_is_refused(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    """The refusal protects the live worker rather than merely blocking the dead one."""
    stale, fresh = reclaimed_pair(store)
    assert not store.complete_success(stale.job_id, stale.attempt_id, stale.worker_id)

    accepted = store.complete_success(fresh.job_id, fresh.attempt_id, fresh.worker_id)

    assert accepted
    assert accepted.state == JobState.SUCCEEDED
    assert accepted.attempt_no == fresh.attempt_no
    outcomes = [attempt["outcome"] for attempt in attempts_of(connection, fresh.job_id)]
    assert outcomes == [AttemptOutcome.ABANDONED, AttemptOutcome.SUCCEEDED]


def test_a_completion_is_refused_when_the_attempt_is_closed_even_if_the_lease_is_held(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    """The fence has two halves, and neither implies the other.

    Here the worker still owns the lease — it is the same worker — but the attempt
    it names has already been closed. Holding a lease is not permission to write
    an outcome twice.
    """
    job_id = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)
    claimed = store.claim_next(WORKER, lease_seconds=LEASE_SECONDS)
    assert claimed is not None
    assert store.complete_retryable(
        claimed.job_id, claimed.attempt_id, WORKER, PlatformTransientError("first outcome")
    )
    # Reclaim so the job is RUNNING under the same worker again, with a new attempt.
    store.read_job(job_id)
    with connection.cursor() as cursor:
        cursor.execute("update job set available_at = now() where id = %s", (job_id,))
    again = store.claim_next(WORKER, lease_seconds=LEASE_SECONDS)
    assert again is not None
    assert again.attempt_id != claimed.attempt_id

    refused = store.complete_success(job_id, claimed.attempt_id, WORKER)

    assert not refused
    job = store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.RUNNING


def test_a_completion_naming_a_job_that_is_not_running_is_refused(store: JobStore) -> None:
    """A PENDING job has no lease to hold, so nothing may be recorded against it."""
    job_id = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)

    refused = store.complete_success(job_id, uuid4(), WORKER)

    assert not refused
    job = store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.PENDING
    assert job["attempt_count"] == 0


def test_a_rejected_completion_is_logged_with_the_jobs_correlation_id(
    store: JobStore, log_stream: StringIO
) -> None:
    """I5 holds on the refusal path too, where the refused statement returned nothing."""
    stale, _ = reclaimed_pair(store)
    job = store.read_job(stale.job_id)
    assert job is not None

    store.complete_success(stale.job_id, stale.attempt_id, stale.worker_id)

    rejected = events_named(log_stream, "job.completion_rejected")
    assert len(rejected) == 1
    assert rejected[0]["correlation_id"] == job["correlation_id"]
    assert rejected[0]["worker_id"] == stale.worker_id


# --------------------------------------------------------------------------- #
# Claiming
# --------------------------------------------------------------------------- #


def test_two_transactions_cannot_claim_one_job(
    store: JobStore, database: PlatformConfig, metrics: MetricsRegistry
) -> None:
    """SKIP LOCKED exclusivity, with the losing side genuinely contending.

    The second connection is not in autocommit, so its claim statement holds the
    row lock for as long as its transaction stays open. That is the window a
    second worker would have to squeeze into, and this test says it cannot. It is
    the single-process form of JOB-007; the multi-process form is T2's.
    """
    store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)

    with connected(database) as holding:
        with holding.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                CLAIM_NEXT,
                {
                    "worker_id": "worker-holding",
                    "lease_seconds": LEASE_SECONDS,
                    "abandoned_summary": "held open by an uncommitted transaction",
                },
            )
            held = cursor.fetchone()
        assert held is not None, "the holding transaction must have taken the row"

        # The row is locked and uncommitted, so this worker sees nothing to claim.
        assert store.claim_next(WORKER, lease_seconds=LEASE_SECONDS) is None
        # ... but it can tell that something claimable exists, which is the
        # difference between an empty queue and a contended one.
        assert metrics.read().claim_conflicts == 1

        holding.rollback()

    # With the holder gone the job is claimable again, and the rolled-back claim
    # left no attempt behind.
    recovered = store.claim_next(WORKER, lease_seconds=LEASE_SECONDS)
    assert recovered is not None
    assert recovered.attempt_no == 1


def test_a_claim_that_finds_an_empty_queue_is_not_counted_as_a_conflict(
    store: JobStore, metrics: MetricsRegistry
) -> None:
    assert store.claim_next(WORKER, lease_seconds=LEASE_SECONDS) is None
    assert metrics.read().claim_conflicts == 0


def test_a_job_scheduled_for_later_is_not_claimable_yet(store: JobStore) -> None:
    store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS, available_in_seconds=600)
    assert store.claim_next(WORKER, lease_seconds=LEASE_SECONDS) is None


def test_reclaiming_an_expired_lease_closes_the_previous_attempt_as_abandoned(
    store: JobStore, connection: psycopg.Connection[Any], metrics: MetricsRegistry
) -> None:
    """One statement does dispatch and recovery, so this is the recovery half."""
    stale, fresh = reclaimed_pair(store)
    rows = attempts_of(connection, stale.job_id)

    assert [row["attempt_no"] for row in rows] == [1, 2]
    assert rows[0]["outcome"] == AttemptOutcome.ABANDONED
    assert rows[0]["error_class"] == ErrorClass.LEASE_ABANDONED
    assert rows[0]["finished_at"] is not None
    assert rows[1]["finished_at"] is None
    # I2 — never two open attempts, which the partial unique index also holds.
    assert sum(1 for row in rows if row["finished_at"] is None) == 1
    reading = metrics.read()
    assert reading.abandoned_attempts == 1
    assert reading.lease_recovery_latency.count == 1


def test_a_reclaim_with_the_budget_already_spent_goes_terminal_instead(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    """I4 is a CHECK constraint, so the claim has to settle rather than exceed it."""
    job_id = store.create_job("succeed", None, max_attempts=1)
    claimed = store.claim_next("worker-stale", lease_seconds=EXPIRED_LEASE)
    assert claimed is not None

    assert store.claim_next(WORKER, lease_seconds=LEASE_SECONDS) is None

    job = store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.FAILED
    assert job["attempt_count"] == 1
    assert job["terminal_reason"] == ErrorClass.LEASE_ABANDONED
    assert job["lease_owner"] is None
    rows = attempts_of(connection, job_id)
    assert len(rows) == 1
    assert rows[0]["outcome"] == AttemptOutcome.ABANDONED


# --------------------------------------------------------------------------- #
# Effects
# --------------------------------------------------------------------------- #


def test_a_repeated_effect_key_is_suppressed_and_counted(
    store: JobStore, connection: psycopg.Connection[Any], metrics: MetricsRegistry
) -> None:
    """I1 — one durable effect per key, held by the primary key rather than a check."""
    job_id = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)

    assert store.apply_effect(job_id, "shared-key", {"first": True}) is True
    assert store.apply_effect(job_id, "shared-key", {"second": True}) is False

    rows = effects_of(connection, job_id)
    assert len(rows) == 1
    assert rows[0]["payload"] == {"first": True}
    assert metrics.read().suppressed_duplicate_effects == 1


def test_a_suppressed_effect_is_logged(store: JobStore, log_stream: StringIO) -> None:
    job_id = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)
    store.apply_effect(job_id, "shared-key")
    store.apply_effect(job_id, "shared-key")
    assert len(events_named(log_stream, "job.effect_suppressed")) == 1


def test_two_jobs_may_choose_the_same_effect_key(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    """JOB-008 needs this: the key is the handler's choice, not the job's identity."""
    first = store.create_job("succeed", {"effect_key": "collide"}, max_attempts=MAX_ATTEMPTS)
    second = store.create_job("succeed", {"effect_key": "collide"}, max_attempts=MAX_ATTEMPTS)

    assert store.apply_effect(first, "collide") is True
    assert store.apply_effect(second, "collide") is False

    assert len(all_effects(connection)) == 1


def test_an_effect_key_does_not_depend_on_the_attempt_number() -> None:
    """The independence I1 rests on, checked without a database."""
    payload = {"effect_key": "stated"}
    keys = {
        effect_key_for(
            JobContext(
                job_id=UUID(int=7),
                payload=payload,
                attempt_no=number,
                attempt_count=number,
                max_attempts=MAX_ATTEMPTS,
                correlation_id="c",
                worker_id=WORKER,
                apply_effect=unwritten_effect,
            )
        )
        for number in (1, 2, 3)
    }
    assert keys == {"stated"}


def test_a_job_without_a_stated_key_derives_one_from_its_identity() -> None:
    context = JobContext(
        job_id=UUID(int=7),
        payload=None,
        attempt_no=2,
        attempt_count=2,
        max_attempts=MAX_ATTEMPTS,
        correlation_id="c",
        worker_id=WORKER,
        apply_effect=unwritten_effect,
    )
    assert effect_key_for(context) == f"job/{UUID(int=7)}"


# --------------------------------------------------------------------------- #
# Handlers and the registry
# --------------------------------------------------------------------------- #


def test_an_unregistered_handler_fails_the_job_on_its_first_claim(
    store: JobStore, connection: psycopg.Connection[Any], registry: HandlerRegistry
) -> None:
    """The contract's "Unknown" rule: HANDLER_UNKNOWN, one attempt, no effect."""
    job_id = store.create_job("not-registered", None, max_attempts=MAX_ATTEMPTS)
    runner = JobRunner(store, registry, worker_id=WORKER, lease_seconds=LEASE_SECONDS)

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.FAILED
    job = store.read_job(job_id)
    assert job is not None
    assert job["terminal_reason"] == ErrorClass.HANDLER_UNKNOWN
    assert job["attempt_count"] == 1
    rows = attempts_of(connection, job_id)
    assert len(rows) == 1
    assert rows[0]["outcome"] == AttemptOutcome.PERMANENT_FAILURE
    assert rows[0]["error_class"] == ErrorClass.HANDLER_UNKNOWN
    assert effects_of(connection, job_id) == []
    # Not retried: a terminal job is not claimable, whatever the budget said.
    assert runner.run_once() is None


def test_an_unknown_handler_names_itself_without_quoting_a_payload(
    registry: HandlerRegistry,
) -> None:
    with pytest.raises(HandlerUnknownError) as raised:
        registry.resolve("not-registered")
    assert "not-registered" in raised.value.summary
    assert raised.value.error_class is ErrorClass.HANDLER_UNKNOWN
    assert raised.value.retryable is False


def test_the_registry_refuses_to_rebind_a_name(registry: HandlerRegistry) -> None:
    with pytest.raises(ValueError, match="already registered"):
        registry.register("succeed", lambda context: None)


def test_every_synthetic_handler_is_registered(registry: HandlerRegistry) -> None:
    assert set(registry.names()) == set(SYNTHETIC_HANDLERS)


def test_a_permanent_failure_is_terminal_on_its_first_attempt(
    store: JobStore, runner: JobRunner, connection: psycopg.Connection[Any]
) -> None:
    job_id = store.create_job("fail_permanent", None, max_attempts=MAX_ATTEMPTS)

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.FAILED
    job = store.read_job(job_id)
    assert job is not None
    assert job["terminal_reason"] == ErrorClass.PLATFORM_PERMANENT
    rows = attempts_of(connection, job_id)
    assert rows[0]["outcome"] == AttemptOutcome.PERMANENT_FAILURE
    # error_summary is operator-visible; error_detail is protected but recorded.
    assert rows[0]["error_summary"]
    assert rows[0]["error_detail"] == {"attempt_no": 1}
    assert effects_of(connection, job_id) == []


def test_a_retryable_failure_reschedules_the_job_with_backoff(
    store: JobStore, runner: JobRunner
) -> None:
    job_id = store.create_job("fail_transient", None, max_attempts=MAX_ATTEMPTS)

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.PENDING
    job = store.read_job(job_id)
    assert job is not None
    assert job["attempt_count"] == 1
    assert job["lease_owner"] is None
    assert job["terminal_reason"] is None
    # Rescheduled into the future, so it is not immediately claimable again.
    assert store.claim_next(WORKER, lease_seconds=LEASE_SECONDS) is None


def test_a_transient_handler_that_recovers_leaves_one_effect(
    store: JobStore, runner: JobRunner, connection: psycopg.Connection[Any]
) -> None:
    """The failure injector is a switch, not a story about what the work was."""
    job_id = store.create_job(
        "fail_transient", {"fail_until_attempt": 1}, max_attempts=MAX_ATTEMPTS
    )
    assert runner.run_once() is not None
    with connection.cursor() as cursor:
        cursor.execute("update job set available_at = now() where id = %s", (job_id,))

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.SUCCEEDED
    assert len(effects_of(connection, job_id)) == 1
    assert len(attempts_of(connection, job_id)) == 2


def test_a_retryable_failure_on_the_last_attempt_is_terminal(
    store: JobStore, runner: JobRunner, connection: psycopg.Connection[Any]
) -> None:
    """The budget decides inside the completion statement, not in a prior read."""
    job_id = store.create_job("fail_transient", None, max_attempts=1)

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.FAILED
    job = store.read_job(job_id)
    assert job is not None
    assert job["attempt_count"] == 1
    assert job["terminal_reason"] == ErrorClass.PLATFORM_TRANSIENT
    rows = attempts_of(connection, job_id)
    assert rows[0]["outcome"] == AttemptOutcome.RETRYABLE_FAILURE


def test_an_unclassified_exception_is_given_a_class_without_quoting_its_message(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    """The contract's error table has no row for this, so the platform names one."""

    def explode(context: JobContext) -> None:
        raise RuntimeError("a message that must not become the error contract")

    registry = HandlerRegistry({"explode": explode})
    job_id = store.create_job("explode", None, max_attempts=MAX_ATTEMPTS)
    runner = JobRunner(store, registry, worker_id=WORKER, lease_seconds=LEASE_SECONDS)

    outcome = runner.run_once()

    assert outcome is not None
    assert outcome.state == JobState.FAILED
    rows = attempts_of(connection, job_id)
    assert rows[0]["error_class"] == ErrorClass.PLATFORM_PERMANENT
    assert "RuntimeError" in rows[0]["error_summary"]
    assert "must not become the error contract" not in rows[0]["error_summary"]


# --------------------------------------------------------------------------- #
# Operator safe retry
# --------------------------------------------------------------------------- #


def test_a_safe_retry_restores_the_budget_and_keeps_the_earlier_attempts(
    store: JobStore, runner: JobRunner, connection: psycopg.Connection[Any]
) -> None:
    """The last transition of the contract's table, and the reason attempt_no
    cannot be attempt_count: the numbers keep climbing while the counter resets."""
    job_id = store.create_job("fail_permanent", None, max_attempts=MAX_ATTEMPTS)
    assert runner.run_once() is not None
    before = attempts_of(connection, job_id)
    assert len(before) == 1

    assert store.request_retry(job_id) is True

    job = store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.PENDING
    assert job["attempt_count"] == 0
    assert job["terminal_reason"] is None
    assert job["lease_owner"] is None
    # Prior attempts retained, unchanged.
    assert attempts_of(connection, job_id) == before

    # The next claim must not collide with the attempt the earlier life left.
    claimed = store.claim_next(WORKER, lease_seconds=LEASE_SECONDS)
    assert claimed is not None
    assert claimed.attempt_no == 2
    assert claimed.attempt_count == 1
    assert len(attempts_of(connection, job_id)) == 2


def test_a_safe_retry_is_refused_for_a_job_that_is_not_failed(store: JobStore) -> None:
    job_id = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)
    assert store.request_retry(job_id) is False
    job = store.read_job(job_id)
    assert job is not None
    assert job["state"] == JobState.PENDING


# --------------------------------------------------------------------------- #
# Creation
# --------------------------------------------------------------------------- #


def test_a_job_with_no_handler_is_refused_and_not_persisted(
    store: JobStore, connection: psycopg.Connection[Any]
) -> None:
    from platform_core.errors import ConfigurationInvalidError

    with pytest.raises(ConfigurationInvalidError):
        store.create_job("", None, max_attempts=MAX_ATTEMPTS)
    with pytest.raises(ConfigurationInvalidError):
        store.create_job("succeed", None, max_attempts=0)
    with connection.cursor() as cursor:
        cursor.execute("select count(*) from job")
        row = cursor.fetchone()
    assert row is not None
    assert row[0] == 0


def test_a_json_null_payload_is_distinguishable_from_an_empty_one(store: JobStore) -> None:
    """The contract keeps "no payload given" and "the payload is null" apart."""
    explicit = store.create_job("succeed", None, max_attempts=MAX_ATTEMPTS)
    mapping = store.create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
    first = store.read_job(explicit)
    second = store.read_job(mapping)
    assert first is not None and second is not None
    assert first["payload"] is None
    assert second["payload"] == {}


# --------------------------------------------------------------------------- #
# Backoff
# --------------------------------------------------------------------------- #


def test_backoff_grows_with_the_attempt_and_stays_inside_its_window() -> None:
    backoff = Backoff(base_ms=100, max_ms=1000, jitter=lambda: 1.0)
    assert backoff.delay_ms(1) == 100
    assert backoff.delay_ms(2) == 200
    assert backoff.delay_ms(3) == 400
    # Bounded by retry_max_ms however many attempts have passed.
    assert backoff.delay_ms(20) == 1000


def test_backoff_jitter_never_reaches_zero_and_never_exceeds_the_ceiling() -> None:
    low = Backoff(base_ms=100, max_ms=1000, jitter=lambda: 0.0)
    high = Backoff(base_ms=100, max_ms=1000, jitter=lambda: 1.0)
    for attempt in range(1, 6):
        assert 0 < low.delay_ms(attempt) <= high.delay_ms(attempt) <= 1000


def test_backoff_is_configuration_rather_than_contract(database: PlatformConfig) -> None:
    backoff = Backoff.from_config(database, jitter=lambda: 0.0)
    assert backoff.base_ms == database.retry_base_ms
    assert backoff.max_ms == database.retry_max_ms


# --------------------------------------------------------------------------- #
# The state machine and the schema agree
# --------------------------------------------------------------------------- #


def quoted_values(definition: str) -> set[str]:
    return set(re.findall(r"'([A-Z_]+)'", definition))


def test_the_job_states_match_the_check_constraint(
    connection: psycopg.Connection[Any],
) -> None:
    """One closed set, two spellings. This is where they are made to agree."""
    assert quoted_values(constraint_body(connection, "job_state_is_known")) == set(JOB_STATES)


def test_the_attempt_outcomes_match_the_check_constraint(
    connection: psycopg.Connection[Any],
) -> None:
    body = constraint_body(connection, "job_attempt_outcome_is_known")
    assert quoted_values(body) == set(ATTEMPT_OUTCOMES)


def test_the_transition_table_has_the_eight_rows_the_contract_lists() -> None:
    assert len(TRANSITIONS) == 8
    assert {row[1] for row in TRANSITIONS} == set(JobState)
    assert JobState.SUCCEEDED.is_terminal
    assert JobState.FAILED.is_terminal
    assert not JobState.PENDING.is_terminal
    assert not JobState.RUNNING.is_terminal
