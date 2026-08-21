"""``platform_core.jobs.store`` against the real, schema-reset ``cosmai_test`` database.

Requires the shared PostgreSQL server reachable — run unsandboxed with
``COSMA_DB_HOST``/``COSMA_DB_PORT``/``COSMA_DB_NAME``/``COSMA_DB_USER`` and
``COSMA_SECRET_SOURCE`` set, per ``docs/conventions/secret-setup.md``.

Copy-adapted from ``experiments/integrated-p0/tests/test_jobs.py``,
``test_job_concurrency.py``, and ``test_job_failure_paths.py``: same claim
statement, same fencing rule, same backoff curve — only the schema
qualification (``cosmai.``) and the fixture names changed, since DP-032 gives
this tree one shared test database rather than a template clone per test (see
``conftest.py``'s ``_reset_job_tables``).

Every scenario here maps to a CONTRACT-JOB@0.1 clause:

* **I1** — duplicate effect suppression (``TestApplyEffect``).
* **I2** — the fenced rejection of a stale worker's completion
  (``TestFencing``).
* **I3/I4** — the exhausted-budget transition and the reclaim-into-exhausted
  case (``TestClaimNext``).
* **I5** — correlation on every transition (``TestCorrelation``).
* The "State transitions" table — terminal states and the operator safe retry
  (``TestCompletion``, ``TestRequestRetry``).
* The retry-backoff curve (``TestCompletion::test_retryable_failure_reschedules_with_backoff``).

The transient-error branch (SQLSTATE ``08``/``53``/``57``) is exercised at
``platform_core.db.connection``, not here — CONTRACT-JOB@0.1 records that
branch as unexercised in P0-A, and nothing in this file changes that.
"""

from __future__ import annotations

import json
import time
from io import StringIO
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.errors import (
    ConfigurationInvalidError,
    PlatformPermanentError,
    PlatformTransientError,
)
from platform_core.jobs.state import ATTEMPT_OUTCOMES, JOB_STATES, JobState
from platform_core.jobs.store import ABANDONED_SUMMARY, REJECTED_REASON, JobStore
from platform_core.obs.metrics import MetricsRegistry

HANDLER = "succeed"

#: A lease that is already over by the time the next statement runs — the
#: single-connection stand-in for "the worker that held this crashed".
EXPIRED_LEASE = 0.0

LEASE_SECONDS = 30.0


def events(log_stream: StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_stream.getvalue().splitlines() if line.strip()]


def events_named(log_stream: StringIO, event: str) -> list[dict[str, Any]]:
    return [record for record in events(log_stream) if record["event"] == event]


def attempts_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "select * from cosmai.job_attempt where job_id = %s order by attempt_no", (job_id,)
        )
        return cursor.fetchall()


def effects_of(connection: psycopg.Connection[Any], job_id: UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("select * from cosmai.platform_effect where job_id = %s", (job_id,))
        return cursor.fetchall()


# --------------------------------------------------------------------------- #
# create_job
# --------------------------------------------------------------------------- #


class TestCreateJob:
    def test_a_valid_job_is_pending_with_a_fresh_correlation_id(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job(HANDLER, {"n": 1}, max_attempts=3)
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "PENDING"
        assert row["attempt_count"] == 0
        assert row["max_attempts"] == 3
        assert row["correlation_id"]
        assert row["lease_owner"] is None

    def test_a_stated_correlation_id_is_honoured(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, None, max_attempts=1, correlation_id="given-id")
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["correlation_id"] == "given-id"

    def test_a_null_payload_is_a_legal_value(self, job_store: JobStore) -> None:
        """The contract's 'Explicit null' rule: JSON null is distinct from absent."""
        job_id = job_store.create_job(HANDLER, None, max_attempts=1)
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["payload"] is None

    def test_a_missing_handler_is_rejected_at_creation(self, job_store: JobStore) -> None:
        with pytest.raises(ConfigurationInvalidError, match="handler"):
            job_store.create_job("", {}, max_attempts=1)

    def test_a_budget_below_one_is_rejected_at_creation(self, job_store: JobStore) -> None:
        with pytest.raises(ConfigurationInvalidError, match="attempt budget"):
            job_store.create_job(HANDLER, {}, max_attempts=0)

    def test_creation_emits_one_transition_and_counts_it(
        self, job_store: JobStore, log_stream: StringIO, job_metrics: MetricsRegistry
    ) -> None:
        job_store.create_job(HANDLER, {}, max_attempts=1, correlation_id="corr-create")
        lines = events_named(log_stream, "job.transition")
        assert len(lines) == 1
        assert lines[0]["from_state"] is None
        assert lines[0]["to_state"] == "PENDING"
        assert lines[0]["correlation_id"] == "corr-create"
        assert job_metrics.read().transitions["PENDING"] == 1


# --------------------------------------------------------------------------- #
# claim_next
# --------------------------------------------------------------------------- #


class TestClaimNext:
    def test_nothing_claimable_returns_none(self, job_store: JobStore) -> None:
        assert job_store.claim_next("worker-a", LEASE_SECONDS) is None

    def test_a_due_pending_job_is_claimed_once(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, {"n": 1}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.attempt_no == 1
        assert claimed.attempt_count == 1
        assert claimed.max_attempts == 3
        assert claimed.handler == HANDLER
        assert claimed.reclaimed_from_attempt_no is None
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "RUNNING"
        assert row["lease_owner"] == "worker-a"

    def test_a_second_claim_finds_nothing(self, job_store: JobStore) -> None:
        job_store.create_job(HANDLER, {}, max_attempts=3)
        assert job_store.claim_next("worker-a", LEASE_SECONDS) is not None
        assert job_store.claim_next("worker-b", LEASE_SECONDS) is None

    def test_a_not_yet_due_job_is_not_claimed(self, job_store: JobStore) -> None:
        job_store.create_job(HANDLER, {}, max_attempts=1, available_in_seconds=60.0)
        assert job_store.claim_next("worker-a", LEASE_SECONDS) is None

    def test_an_expired_lease_is_reclaimed_and_the_prior_attempt_abandoned(
        self,
        job_store: JobStore,
        job_connection: psycopg.Connection[Any],
        job_metrics: MetricsRegistry,
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        first = job_store.claim_next("worker-a", EXPIRED_LEASE)
        assert first is not None
        second = job_store.claim_next("worker-b", LEASE_SECONDS)
        assert second is not None
        assert second.job_id == job_id
        assert second.attempt_no == 2
        assert second.attempt_count == 2
        assert second.reclaimed_from_attempt_no == 1

        rows = attempts_of(job_connection, job_id)
        assert len(rows) == 2
        assert rows[0]["outcome"] == "ABANDONED"
        assert rows[0]["error_class"] == "LEASE_ABANDONED"
        assert rows[0]["error_summary"] == ABANDONED_SUMMARY
        assert rows[0]["finished_at"] is not None
        assert rows[1]["finished_at"] is None

        reading = job_metrics.read()
        assert reading.abandoned_attempts == 1
        assert reading.lease_recovery_latency.count == 1

    def test_a_reclaim_that_finds_the_budget_spent_goes_terminal_without_a_new_attempt(
        self,
        job_store: JobStore,
        job_connection: psycopg.Connection[Any],
        job_metrics: MetricsRegistry,
    ) -> None:
        """I3/I4: the reclaim-into-exhausted-budget transition CONTRACT-JOB@0.1 names.

        Contract row 8's required side effect has two halves: the prior attempt
        closes `ABANDONED`, and no new attempt opens. The state/terminal_reason
        assertions below only ever exercised the first half by inference — a
        mutation that draws the `opened` CTE from `candidate` instead of `started`
        (opening a new attempt on every exhausted reclaim, in violation of I2/I3)
        left this test green (REVIEW-M1 F1). These three lines read the
        `job_attempt` table directly so that "no new attempt opened" is asserted,
        not assumed.
        """
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)
        first = job_store.claim_next("worker-a", EXPIRED_LEASE)
        assert first is not None
        second = job_store.claim_next("worker-b", LEASE_SECONDS)
        assert second is None

        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "FAILED"
        assert row["terminal_reason"] == "LEASE_ABANDONED"
        assert row["lease_owner"] is None
        assert job_metrics.read().abandoned_attempts == 1

        rows = attempts_of(job_connection, job_id)
        assert len(rows) == 1, "no new attempt was opened over the exhausted budget"
        assert rows[0]["outcome"] == "ABANDONED"
        assert rows[0]["finished_at"] is not None

    def test_a_claim_conflict_is_counted_when_the_row_is_held_elsewhere(
        self, job_store: JobStore, platform_config: PlatformConfig, job_metrics: MetricsRegistry
    ) -> None:
        """A worker mid-claim (uncommitted) makes a concurrent claim observe a conflict.

        P0's own measurement (`store.py`'s ``CLAIM_NEXT`` comment) is why the
        conflict answer has to come from the same statement and the same clock
        as the claim itself; this reproduces the two-transaction setup that
        distinguishes a real conflict from an empty queue.
        """
        job_store.create_job(HANDLER, {}, max_attempts=1)
        holder = connect(platform_config, role="runtime", autocommit=False)
        try:
            holding_store = JobStore(holder, platform_config)
            claimed = holding_store.claim_next("worker-holding", LEASE_SECONDS)
            assert claimed is not None  # locked, but not yet committed

            result = job_store.claim_next("worker-b", LEASE_SECONDS)
            assert result is None
            assert job_metrics.read().claim_conflicts == 1
        finally:
            holder.rollback()
            holder.close()


# --------------------------------------------------------------------------- #
# Fencing (I2) — completion is accepted only for the current lease holder
# --------------------------------------------------------------------------- #


class TestFencing:
    def test_a_stale_workers_completion_is_refused_and_counted(
        self, job_store: JobStore, job_metrics: MetricsRegistry, log_stream: StringIO
    ) -> None:
        """JOB-006: fencing after a reclaim, the case where two workers genuinely contend."""
        job_store.create_job(HANDLER, {}, max_attempts=3)
        stale = job_store.claim_next("worker-a", EXPIRED_LEASE)
        assert stale is not None
        reclaimed = job_store.claim_next("worker-b", LEASE_SECONDS)
        assert reclaimed is not None

        completion = job_store.complete_success(stale.job_id, stale.attempt_id, "worker-a")
        assert not completion.accepted
        assert completion.reason == REJECTED_REASON
        assert job_metrics.read().rejected_completions == 1
        rejections = events_named(log_stream, "job.completion_rejected")
        assert len(rejections) == 1
        assert rejections[0]["worker_id"] == "worker-a"

        # The reclaiming worker's own completion is unaffected by the refusal.
        follow_up = job_store.complete_success(
            reclaimed.job_id, reclaimed.attempt_id, "worker-b"
        )
        assert follow_up.accepted
        assert follow_up.state is JobState.SUCCEEDED

    def test_the_fence_tests_ownership_not_expiry(self, job_store: JobStore) -> None:
        """A lease that ran out but was never reclaimed still belongs to its worker."""
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", EXPIRED_LEASE)
        assert claimed is not None
        completion = job_store.complete_success(job_id, claimed.attempt_id, "worker-a")
        assert completion.accepted


# --------------------------------------------------------------------------- #
# Completion — terminal states and retry backoff
# --------------------------------------------------------------------------- #


class TestCompletion:
    def test_success_clears_the_lease_and_reaches_a_terminal_state(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        completion = job_store.complete_success(job_id, claimed.attempt_id, "worker-a")
        assert completion.accepted
        assert completion.state is JobState.SUCCEEDED
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "SUCCEEDED"
        assert row["lease_owner"] is None
        assert row["terminal_reason"] is None

    def test_permanent_failure_goes_terminal_on_the_first_attempt(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        error = PlatformPermanentError("injected permanent failure")
        completion = job_store.complete_permanent(job_id, claimed.attempt_id, "worker-a", error)
        assert completion.state is JobState.FAILED
        assert completion.terminal_reason == "PLATFORM_PERMANENT"
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "FAILED"
        assert row["terminal_reason"] == "PLATFORM_PERMANENT"

    def test_complete_permanent_refuses_a_retryable_error(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        with pytest.raises(ValueError, match="retryable"):
            job_store.complete_permanent(
                job_id, claimed.attempt_id, "worker-a", PlatformTransientError("x")
            )

    def test_complete_retryable_refuses_a_non_retryable_error(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        with pytest.raises(ValueError, match="not retryable"):
            job_store.complete_retryable(
                job_id, claimed.attempt_id, "worker-a", PlatformPermanentError("x")
            )

    def test_retryable_failure_reschedules_with_backoff(self, job_store: JobStore) -> None:
        """Zero jitter (the ``job_store`` fixture) pins the delay to the window's low edge."""
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        error = PlatformTransientError("injected retryable failure")
        completion = job_store.complete_retryable(job_id, claimed.attempt_id, "worker-a", error)
        assert completion.accepted
        assert completion.state is JobState.PENDING
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "PENDING"
        assert row["lease_owner"] is None
        # base_ms=100 (the default), attempt_no=1 => exponent 0, ceiling=base_ms,
        # jitter=0 (the job_store fixture) => half the ceiling: 50ms. available_at
        # and updated_at share one statement-level now(), so their difference is
        # exactly the computed delay rather than an estimate across two clocks.
        delay = (row["available_at"] - row["updated_at"]).total_seconds()
        assert delay == pytest.approx(0.05, abs=0.005)

    def test_retryable_failure_goes_terminal_once_the_budget_is_spent(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=2)
        for attempt in range(2):
            if attempt > 0:
                # The reschedule's backoff delay (zero jitter, but never zero
                # delay itself — see Backoff.delay_ms) has to actually elapse
                # before the job is due again.
                time.sleep(0.1)
            claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
            assert claimed is not None
            completion = job_store.complete_retryable(
                job_id, claimed.attempt_id, "worker-a", PlatformTransientError("injected")
            )
        assert completion.state is JobState.FAILED
        assert completion.terminal_reason == "PLATFORM_TRANSIENT"
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "FAILED"
        assert row["attempt_count"] == 2


# --------------------------------------------------------------------------- #
# apply_effect (I1)
# --------------------------------------------------------------------------- #


class TestApplyEffect:
    def test_the_first_application_is_accepted(
        self, job_store: JobStore, job_connection: psycopg.Connection[Any]
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)
        applied = job_store.apply_effect(job_id, f"job/{job_id}", {"n": 1})
        assert applied
        rows = effects_of(job_connection, job_id)
        assert len(rows) == 1

    def test_a_repeat_key_is_suppressed_and_counted(
        self,
        job_store: JobStore,
        job_connection: psycopg.Connection[Any],
        job_metrics: MetricsRegistry,
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)
        key = f"job/{job_id}"
        assert job_store.apply_effect(job_id, key, {"n": 1})
        assert not job_store.apply_effect(job_id, key, {"n": 2})
        rows = effects_of(job_connection, job_id)
        assert len(rows) == 1
        assert job_metrics.read().suppressed_duplicate_effects == 1

    def test_two_different_jobs_can_share_one_key(self, job_store: JobStore) -> None:
        """The contract's identity boundary: `job.id` and `effect_key` are separate."""
        shared_key = f"shared-{uuid4()}"
        job_a = job_store.create_job(HANDLER, {}, max_attempts=1)
        job_b = job_store.create_job(HANDLER, {}, max_attempts=1)
        assert job_store.apply_effect(job_a, shared_key)
        assert not job_store.apply_effect(job_b, shared_key)


# --------------------------------------------------------------------------- #
# Operator safe retry
# --------------------------------------------------------------------------- #


class TestRequestRetry:
    def test_a_failed_job_is_returned_to_pending_with_budget_restored(
        self, job_store: JobStore, job_connection: psycopg.Connection[Any]
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        job_store.complete_permanent(
            job_id, claimed.attempt_id, "worker-a", PlatformPermanentError("injected")
        )
        assert job_store.request_retry(job_id)
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "PENDING"
        assert row["attempt_count"] == 0
        assert row["terminal_reason"] is None
        # Prior attempts are retained, not erased.
        assert len(attempts_of(job_connection, job_id)) == 1

    def test_only_a_failed_job_may_be_retried(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)  # PENDING
        assert not job_store.request_retry(job_id)
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "PENDING"

    def test_a_second_life_reuses_the_next_attempt_number_not_one(
        self, job_store: JobStore, job_connection: psycopg.Connection[Any]
    ) -> None:
        """attempt_no keeps counting; only attempt_count resets (contract's own note)."""
        job_id = job_store.create_job(HANDLER, {}, max_attempts=1)
        first = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert first is not None
        job_store.complete_permanent(
            job_id, first.attempt_id, "worker-a", PlatformPermanentError("injected")
        )
        job_store.request_retry(job_id)
        second = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert second is not None
        assert second.attempt_no == 2
        rows = attempts_of(job_connection, job_id)
        assert [row["attempt_no"] for row in rows] == [1, 2]


# --------------------------------------------------------------------------- #
# Correlation (I5)
# --------------------------------------------------------------------------- #


class TestCorrelation:
    def test_every_transition_carries_the_jobs_correlation_id(
        self, job_store: JobStore, log_stream: StringIO
    ) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3, correlation_id="corr-flow")
        claimed = job_store.claim_next("worker-a", LEASE_SECONDS)
        assert claimed is not None
        job_store.complete_success(job_id, claimed.attempt_id, "worker-a")
        lines = events_named(log_stream, "job.transition")
        assert len(lines) == 3
        assert all(line["correlation_id"] == "corr-flow" for line in lines)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


class TestReads:
    def test_read_job_returns_none_for_an_unknown_id(self, job_store: JobStore) -> None:
        assert job_store.read_job(uuid4()) is None

    def test_list_and_count_agree_on_a_state_filter(self, job_store: JobStore) -> None:
        job_store.create_job(HANDLER, {}, max_attempts=1)
        job_store.create_job(HANDLER, {}, max_attempts=1)
        listed = job_store.list_jobs(state=JobState.PENDING)
        assert len(listed) == 2
        assert job_store.count_jobs(state=JobState.PENDING) == 2
        assert job_store.count_jobs(state=JobState.RUNNING) == 0

    def test_count_by_state_reports_every_state(self, job_store: JobStore) -> None:
        job_store.create_job(HANDLER, {}, max_attempts=1)
        counted = job_store.count_by_state()
        assert set(counted) == set(JOB_STATES)
        assert counted["PENDING"] == 1

    def test_read_attempts_is_ordered_oldest_first(self, job_store: JobStore) -> None:
        job_id = job_store.create_job(HANDLER, {}, max_attempts=3)
        first = job_store.claim_next("worker-a", EXPIRED_LEASE)
        assert first is not None
        second = job_store.claim_next("worker-b", LEASE_SECONDS)
        assert second is not None
        rows = job_store.read_attempts(job_id)
        assert [row["attempt_no"] for row in rows] == [1, 2]


# --------------------------------------------------------------------------- #
# The state machine matches the CHECK constraints (drift guard)
# --------------------------------------------------------------------------- #


def _check_clause(connection: psycopg.Connection[Any], constraint: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = %s",
            (constraint,),
        )
        row = cursor.fetchone()
    assert row is not None, f"constraint {constraint!r} not found"
    return str(row[0])


class TestStateMachineMatchesTheDatabase:
    def test_job_state_matches_the_check_constraint(
        self, job_connection: psycopg.Connection[Any]
    ) -> None:
        clause = _check_clause(job_connection, "job_state_is_known")
        for state in JOB_STATES:
            assert state in clause

    def test_attempt_outcome_matches_the_check_constraint(
        self, job_connection: psycopg.Connection[Any]
    ) -> None:
        clause = _check_clause(job_connection, "job_attempt_outcome_is_known")
        for outcome in ATTEMPT_OUTCOMES:
            assert outcome in clause
