"""``platform_core.jobs.runner`` against the real, schema-reset ``cosmai_test`` database.

Requires the shared PostgreSQL server reachable — run unsandboxed with
``COSMA_DB_HOST``/``COSMA_DB_PORT``/``COSMA_DB_NAME``/``COSMA_DB_USER`` and
``COSMA_SECRET_SOURCE`` set, per ``docs/conventions/secret-setup.md``.

Copy-adapted from ``experiments/integrated-p0/tests/test_jobs.py`` and
``test_job_failure_paths.py``'s runner-level cases. ``platform_core.handlers``
does not exist in this milestone (Task 6 builds ``jobs/`` and ``errors.py``
only), so the handlers exercised here are small test-local injectors — the same
shape as P0's ``platform_core/handlers/synthetic.py`` (``succeed``,
``fail_transient``, ``fail_permanent``) but scoped to this file rather than
production code, since nothing in Task 6's file list creates a handlers
package.

What's under test is ``run_once``'s three load-bearing decisions documented in
``runner.py``: the handler runs inside the job's correlation scope (I5), a
rejected completion is a return value rather than an exception, and an
unclassified exception is recorded as ``PLATFORM_PERMANENT`` rather than
retried.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from io import StringIO
from typing import Any
from uuid import uuid4

from platform_core.errors import ErrorClass, PlatformPermanentError, PlatformTransientError
from platform_core.jobs.registry import HandlerRegistry, JobContext, effect_key_for
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.correlation import current_correlation_id

WORKER = "worker-under-test"
LEASE_SECONDS = 30.0
EXPIRED_LEASE = 0.0


def events(log_stream: StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_stream.getvalue().splitlines() if line.strip()]


def events_named(log_stream: StringIO, event: str) -> list[dict[str, Any]]:
    return [record for record in events(log_stream) if record["event"] == event]


# --------------------------------------------------------------------------- #
# Test-local synthetic handlers — see the module docstring
# --------------------------------------------------------------------------- #


def succeed(context: JobContext) -> None:
    context.apply_effect(effect_key_for(context), {"attempt_no": context.attempt_no})


def fail_transient_once(context: JobContext) -> None:
    """Fails on attempt 1, succeeds from attempt 2 onward."""
    if context.attempt_no <= 1:
        raise PlatformTransientError(
            "injected retryable failure", {"attempt_no": context.attempt_no}
        )
    context.apply_effect(effect_key_for(context), {"attempt_no": context.attempt_no})


def always_fail_transient(context: JobContext) -> None:
    raise PlatformTransientError("injected retryable failure", {"attempt_no": context.attempt_no})


def fail_permanent(context: JobContext) -> None:
    raise PlatformPermanentError(
        "injected permanent failure", {"attempt_no": context.attempt_no}
    )


def raise_unclassified(context: JobContext) -> None:
    raise RuntimeError("not a PlatformError at all")


def records_correlation(seen: list[str | None]) -> Any:
    def _handler(context: JobContext) -> None:
        seen.append(current_correlation_id())
        context.apply_effect(effect_key_for(context), None)

    return _handler


def enlists_durable_work(sink: list[str]) -> Any:
    """Enlists a write and then succeeds — exercises the shared-transaction path."""

    def _handler(context: JobContext) -> None:
        context.enlist_durable_work(lambda: sink.append(str(context.job_id)))

    return _handler


def enlists_and_raises(sink: list[str]) -> Any:
    """Enlists a write, then the handler itself raises — the settle never runs."""

    def _handler(context: JobContext) -> None:
        context.enlist_durable_work(lambda: sink.append(str(context.job_id)))
        raise PlatformPermanentError("injected failure after enlisting")

    return _handler


def registry_of(**handlers: Any) -> HandlerRegistry:
    return HandlerRegistry(handlers)


# --------------------------------------------------------------------------- #
# The base path
# --------------------------------------------------------------------------- #


class TestRunOnce:
    def test_nothing_claimable_returns_none(self, job_store: JobStore) -> None:
        runner = JobRunner(job_store, registry_of(succeed=succeed), WORKER, LEASE_SECONDS)
        assert runner.run_once() is None

    def test_a_successful_handler_reaches_succeeded_with_one_effect(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job("succeed", {}, max_attempts=3)
        runner = JobRunner(job_store, registry_of(succeed=succeed), WORKER, LEASE_SECONDS)
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.accepted
        assert outcome.state is JobState.SUCCEEDED
        assert outcome.error is None
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "SUCCEEDED"

    def test_a_retryable_failure_reschedules_the_job(self, job_store: JobStore) -> None:
        job_id = job_store.create_job("fail", {}, max_attempts=3)
        runner = JobRunner(
            job_store, registry_of(fail=always_fail_transient), WORKER, LEASE_SECONDS
        )
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.PENDING
        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_TRANSIENT
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "PENDING"
        assert row["attempt_count"] == 1

    def test_a_permanent_failure_goes_terminal_on_the_first_attempt(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job("fail", {}, max_attempts=3)
        runner = JobRunner(job_store, registry_of(fail=fail_permanent), WORKER, LEASE_SECONDS)
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.FAILED
        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["terminal_reason"] == "PLATFORM_PERMANENT"

    def test_a_handler_that_recovers_eventually_succeeds(self, job_store: JobStore) -> None:
        job_id = job_store.create_job("flaky", {}, max_attempts=3)
        runner = JobRunner(
            job_store, registry_of(flaky=fail_transient_once), WORKER, LEASE_SECONDS
        )
        first = runner.run_once()
        assert first is not None
        assert first.state is JobState.PENDING
        # Backoff never rounds to zero (Backoff.delay_ms), so the second pass
        # has to wait for the reschedule to become due.
        time.sleep(0.1)
        second = runner.run_once()
        assert second is not None
        assert second.state is JobState.SUCCEEDED
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "SUCCEEDED"


# --------------------------------------------------------------------------- #
# HANDLER_UNKNOWN — not retried, terminal on the first claim
# --------------------------------------------------------------------------- #


class TestHandlerUnknown:
    def test_an_unregistered_handler_fails_the_job_without_retry(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job("not-registered", {}, max_attempts=3)
        runner = JobRunner(job_store, HandlerRegistry(), WORKER, LEASE_SECONDS)
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.FAILED
        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.HANDLER_UNKNOWN
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["state"] == "FAILED"
        assert row["terminal_reason"] == "HANDLER_UNKNOWN"
        assert row["attempt_count"] == 1


# --------------------------------------------------------------------------- #
# An exception the handler did not classify is PLATFORM_PERMANENT
# --------------------------------------------------------------------------- #


class TestUnclassifiedException:
    def test_an_unclassified_exception_is_recorded_as_platform_permanent(
        self, job_store: JobStore
    ) -> None:
        job_id = job_store.create_job("broken", {}, max_attempts=3)
        runner = JobRunner(
            job_store, registry_of(broken=raise_unclassified), WORKER, LEASE_SECONDS
        )
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.FAILED
        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "RuntimeError" in outcome.error.summary
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["terminal_reason"] == "PLATFORM_PERMANENT"
        # The exception's own text is protected detail, never the operator summary.
        assert "not a PlatformError at all" not in outcome.error.summary


# --------------------------------------------------------------------------- #
# A rejected completion is a value, not an exception
#
# ``run_once`` reports what ``JobStore`` told it (``runner.py``'s own claim), so
# the fencing mechanism itself — a stale worker's claim, reclaimed before it
# settles, refused without raising — is ``TestFencing`` in
# ``test_jobs_store.py``. What is runner-specific and worth its own coverage is
# only that ``run_once`` never turns a refusal into an exception; the case below
# checks exactly that boundary at the ``JobRunner`` API a caller actually uses.
# --------------------------------------------------------------------------- #


class TestRejectedCompletionIsAValue:
    def test_the_reclaiming_workers_run_once_succeeds_normally(
        self, job_store: JobStore
    ) -> None:
        """Sets up the same stale/reclaim pair as `test_jobs_store.py`, then drives
        the reclaiming half through `JobRunner.run_once` — the return value is a
        plain `RunOutcome`, not a raised exception, on both sides of a fence."""
        job_store.create_job("succeed", {}, max_attempts=3)
        stale = job_store.claim_next("stale-worker", EXPIRED_LEASE)
        assert stale is not None

        runner = JobRunner(job_store, registry_of(succeed=succeed), "worker-b", LEASE_SECONDS)
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.accepted
        assert outcome.state is JobState.SUCCEEDED

        # The stale worker's own completion, arriving after the reclaim, is a
        # refused `Completion` value rather than an exception from the store.
        refused = job_store.complete_success(stale.job_id, stale.attempt_id, "stale-worker")
        assert not refused.accepted


# --------------------------------------------------------------------------- #
# Correlation (I5): the handler runs inside the job's scope
# --------------------------------------------------------------------------- #


class TestCorrelation:
    def test_the_handler_observes_the_jobs_correlation_id_ambiently(
        self, job_store: JobStore
    ) -> None:
        seen: list[str | None] = []
        job_store.create_job("recorder", {}, max_attempts=1, correlation_id="corr-runner")
        runner = JobRunner(
            job_store, registry_of(recorder=records_correlation(seen)), WORKER, LEASE_SECONDS
        )
        outcome = runner.run_once()
        assert outcome is not None
        assert seen == ["corr-runner"]

    def test_no_correlation_scope_leaks_after_the_pass(self, job_store: JobStore) -> None:
        job_store.create_job("succeed", {}, max_attempts=1)
        runner = JobRunner(job_store, registry_of(succeed=succeed), WORKER, LEASE_SECONDS)
        runner.run_once()
        assert current_correlation_id() is None


# --------------------------------------------------------------------------- #
# Enlisted durable work shares the completion's transaction
# --------------------------------------------------------------------------- #


class TestDurableScope:
    def test_enlisted_work_commits_together_with_a_successful_completion(
        self, job_store: JobStore
    ) -> None:
        sink: list[str] = []
        job_id = job_store.create_job("enlist", {}, max_attempts=1)
        runner = JobRunner(
            job_store, registry_of(enlist=enlists_durable_work(sink)), WORKER, LEASE_SECONDS
        )
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.SUCCEEDED
        assert sink == [str(job_id)]

    def test_enlisted_work_rolls_back_when_the_handler_then_raises(
        self, job_store: JobStore
    ) -> None:
        """Enlisted work is handler code; a handler exception classifies it and
        the settle for that attempt never runs — I1's rollback-not-flag guarantee."""
        job_id = job_store.create_job("enlist_fail", {}, max_attempts=3)
        sink: list[str] = []
        runner = JobRunner(
            job_store, registry_of(enlist_fail=enlists_and_raises(sink)), WORKER, LEASE_SECONDS
        )
        outcome = runner.run_once()
        assert outcome is not None
        assert outcome.state is JobState.FAILED
        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        row = job_store.read_job(job_id)
        assert row is not None
        assert row["terminal_reason"] == "PLATFORM_PERMANENT"


def _payload(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return dict(mapping)


def test_effect_key_defaults_to_the_job_identity(job_store: JobStore) -> None:
    job_id = job_store.create_job("succeed", {}, max_attempts=1)
    seen: dict[str, Any] = {}

    def handler(context: JobContext) -> None:
        seen["key"] = effect_key_for(context)
        context.apply_effect(effect_key_for(context), None)

    runner = JobRunner(job_store, registry_of(succeed=handler), WORKER, LEASE_SECONDS)
    runner.run_once()
    assert seen["key"] == f"job/{job_id}"


def test_a_stated_effect_key_is_honoured(job_store: JobStore) -> None:
    stated = f"custom-{uuid4()}"
    job_store.create_job("succeed", _payload({"effect_key": stated}), max_attempts=1)
    seen: dict[str, Any] = {}

    def handler(context: JobContext) -> None:
        seen["key"] = effect_key_for(context)
        context.apply_effect(effect_key_for(context), None)

    runner = JobRunner(job_store, registry_of(succeed=handler), WORKER, LEASE_SECONDS)
    runner.run_once()
    assert seen["key"] == stated
