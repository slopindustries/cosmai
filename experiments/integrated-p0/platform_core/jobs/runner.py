"""One pass of the execution loop: claim, run, record.

This is deliberately a single pass rather than a loop. T2 adds the process
worker — signal handling, shutdown, the poll interval — and it will do that by
calling ``run_once`` repeatedly. Keeping the pass separate means a test can
observe exactly one execution without starting a process, and it means the part
of the worker that is hard to test (lifecycle) is not entangled with the part
that carries the contract (execution).

Three decisions are worth reading before the code.

**The handler is run inside the job's correlation scope.** I5 says correlation is
total, and a handler that logs through the platform logger inherits the scope
without being handed the identifier.

**A rejected completion is a return value, not an exception.** ``run_once``
reports what the store told it. A worker that stalled past its lease and was
reclaimed will be refused here, and the correct response is to go back and claim
something else — not to fail, and certainly not to retry the write.

**An unclassified exception is treated as permanent.** The contract's error table
has no row for "the handler raised something the platform does not recognize",
and retryability there is a property of the error class rather than of the call
site. The platform has no basis for asserting that a retry of an error it could
not classify would behave differently, so it does not assert one; it records
``PLATFORM_PERMANENT`` with a summary saying the exception was unclassified. This
is recorded as an ambiguity in the contract rather than resolved by it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from platform_core.errors import PlatformError, PlatformPermanentError
from platform_core.jobs.registry import DurableWork, HandlerRegistry, JobContext
from platform_core.jobs.state import JobState
from platform_core.jobs.store import ClaimedJob, Completion, JobStore
from platform_core.obs.correlation import correlation_context


@dataclass(frozen=True)
class RunOutcome:
    """What one pass did. ``None`` from ``run_once`` means nothing was claimable."""

    claimed: ClaimedJob
    completion: Completion
    error: PlatformError | None = None

    @property
    def state(self) -> JobState | None:
        return self.completion.state

    @property
    def accepted(self) -> bool:
        return self.completion.accepted


class _CompletionRefused(Exception):
    """Internal: unwinds the durable scope when the fence refuses.

    Never leaves this module. It exists because a rollback needs an exception and a
    refusal is not an error — ``run_once`` still reports the refusal as a value.
    """


class JobRunner:
    """Executes claimed jobs against one store and one handler table."""

    def __init__(
        self,
        store: JobStore,
        registry: HandlerRegistry,
        worker_id: str,
        lease_seconds: float,
    ) -> None:
        self._store = store
        self._registry = registry
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def run_once(self) -> RunOutcome | None:
        """Claim at most one job, execute it, and record the outcome."""
        claimed = self._store.claim_next(self._worker_id, self._lease_seconds)
        if claimed is None:
            return None
        with correlation_context(claimed.correlation_id):
            return self._execute(claimed)

    def _execute(self, claimed: ClaimedJob) -> RunOutcome:
        try:
            handler = self._registry.resolve(claimed.handler)
        except PlatformError as unknown:
            # HANDLER_UNKNOWN is not retryable, so this is terminal on the first
            # claim exactly as the contract's "Unknown" rule requires.
            return RunOutcome(claimed, self._record(claimed, unknown), unknown)

        enlisted: list[DurableWork] = []
        context = JobContext(
            job_id=claimed.job_id,
            attempt_id=claimed.attempt_id,
            payload=claimed.payload,
            attempt_no=claimed.attempt_no,
            attempt_count=claimed.attempt_count,
            max_attempts=claimed.max_attempts,
            correlation_id=claimed.correlation_id,
            worker_id=claimed.worker_id,
            apply_effect=self._effect_applier(claimed),
            enlist_durable_work=enlisted.append,
        )
        try:
            with self._store.metrics.measure_attempt():
                handler(context)
        except PlatformError as failure:
            return RunOutcome(claimed, self._record(claimed, failure), failure)
        except Exception as unexpected:  # noqa: BLE001 - classified, then recorded
            classified = self._unclassified(unexpected)
            return RunOutcome(claimed, self._record(claimed, classified), classified)
        return RunOutcome(claimed, self._settle(claimed, enlisted), None)

    def _settle(self, claimed: ClaimedJob, enlisted: list[DurableWork]) -> Completion:
        """Commit the handler's enlisted work and its completion together, or neither.

        A handler that enlisted nothing takes the same path it always did — one
        statement, one transaction — so P0-A's evidence is untouched by this.

        With work enlisted, both go inside one transaction and **the completion goes
        last**. A worker that stalled past its lease is refused by the fence, and the
        refusal must discard the writes rather than follow them: by the time it stalled,
        another worker had already been given the same work, so writes that survived
        would be a duplicate the platform cannot deduplicate by key. Raising is how a
        refusal becomes a rollback; it is caught immediately below and reported as the
        refusal it is, because ``run_once`` reports what the store told it rather than
        failing.

        **Enlisted work that raises unwinds the transaction and then escapes.** This
        docstring said the error is "classified like any other handler failure", and that
        was false: `_execute` wraps only `handler(context)`, and the call to this method
        sits outside that `try`. `ADVERSARIAL-REVIEW-2026-08-18.md` F2 measured what follows —
        the job stays `RUNNING` with its attempt open and its lease held, and in the real
        worker `classify` turns the raw database error into `ConfigurationInvalidError`, so
        the process exits reporting "cannot reach the platform database" for what was an
        add-on's output defect.

        `[확인 사실]` `test_durable_scope.py`'s
        `test_a_failure_inside_enlisted_work_leaves_nothing_behind` wraps `run_once()` in
        `pytest.raises` and asserts only that no row survived, so the
        escape was visible in this module's own evidence and went unremarked. Corrected
        here rather than repaired, because bringing the settle inside the classification
        without double-recording a completion is a change that needs its own tests.
        """
        if not enlisted:
            return self._record(claimed, None)

        refusal: Completion | None = None
        try:
            with self._store.durable_scope():
                for work in enlisted:
                    work()
                completion = self._record(claimed, None)
                if not completion:
                    refusal = completion
                    raise _CompletionRefused
        except _CompletionRefused:
            assert refusal is not None
            return refusal
        return completion


    def _effect_applier(self, claimed: ClaimedJob) -> Callable[[str, Any], bool]:
        def apply(effect_key: str, payload: Any = None) -> bool:
            return self._store.apply_effect(claimed.job_id, effect_key, payload)

        return apply

    def _record(self, claimed: ClaimedJob, error: PlatformError | None) -> Completion:
        """Send the outcome through the fence, whichever outcome it is."""
        if error is None:
            return self._store.complete_success(
                claimed.job_id, claimed.attempt_id, claimed.worker_id
            )
        if error.retryable:
            return self._store.complete_retryable(
                claimed.job_id, claimed.attempt_id, claimed.worker_id, error
            )
        return self._store.complete_permanent(
            claimed.job_id, claimed.attempt_id, claimed.worker_id, error
        )

    @staticmethod
    def _unclassified(exception: BaseException) -> PlatformError:
        """Give an unrecognized exception a class, without quoting its message.

        The type name is the platform's own vocabulary; the message could contain
        anything the payload put there, so it goes to the protected detail, which
        is redacted on the way in and never reaches an operator surface by default.
        """
        return PlatformPermanentError(
            f"the handler raised an unclassified {type(exception).__name__}",
            {"exception_type": type(exception).__name__, "exception_text": str(exception)},
        )
