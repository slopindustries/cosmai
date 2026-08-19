"""Every write CONTRACT-JOB@0.1 permits, as hand-written SQL (DP-006 D5).

There is no mapper and no query builder here on purpose. The three statements a
gate reviewer has to be able to read — the claim, the fenced completion, and the
idempotent effect insert — are the evidence this experiment exists to produce, so
they appear in full rather than as arguments to something that assembles them.

Four properties are structural rather than conventional.

**One statement per operation.** Each method below issues exactly one SQL
statement (``claim_next`` may issue a second, purely observational one; it is
marked). Nothing here depends on a transaction the caller has to remember to
open: under an autocommit connection every operation is its own transaction, and
under a manual one the caller's transaction simply contains it. That is also why
a rejected completion needs no rollback — the statement that would have written
it matched no rows.

**Claiming and recovery are the same statement.** The contract requires it, and
the reason is that a separate sweep for expired leases is a component whose
absence strands work. One statement over "``PENDING`` and due, or ``RUNNING`` with
an expired lease" cannot be half-deployed.

**A completion is fenced.** Every completion statement begins with the same
``fenced`` CTE: the job must still be ``RUNNING``, its ``lease_owner`` must still
be this worker, and this worker's own attempt row must still be open. If any of
those has changed, the CTE yields nothing, every dependent update matches nothing,
and the method returns a rejection instead of raising. Refusing is not an error
condition — a stale worker waking up after a reclaim is expected behavior under
at-least-once delivery — so the caller is told, the refusal is counted, and the
decision about what to do next stays with the caller.

**The database owns every timestamp.** ``now()`` is stable within a statement, so
a claim's lease deadline, its attempt's ``started_at``, and its job's
``updated_at`` are the same instant by construction. No worker clock is consulted
for a lease or availability decision, which is what keeps clock skew between
processes out of I2.

The one thing that is not a single statement is the attempt number.
``attempt_count`` cannot supply it: an operator safe retry resets that counter to
zero while the contract keeps the earlier attempts, so a second life of the same
job would reuse ``attempt_no = 1`` and collide with
``job_attempt_number_is_unique_per_job``. The number therefore comes from
``max(attempt_no) + 1`` within the claim statement, and ``attempt_count`` stays
what the contract calls it — the attempt budget consumed, not a row label.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from platform_core.config import PlatformConfig
from platform_core.errors import ConfigurationInvalidError, ErrorClass, PlatformError
from platform_core.jobs.state import JOB_STATES, AttemptOutcome, JobState
from platform_core.obs.correlation import correlation_context, new_correlation_id
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry

Jitter = Callable[[], float]
"""A source of a fraction in ``[0, 1)``. Injectable so backoff can be exact in a test."""

#: The summary written onto an attempt whose lease expired under it. It names a
#: class of failure and quotes nothing, as the contract requires of a summary.
ABANDONED_SUMMARY: Final = "the lease expired before this attempt recorded an outcome"

#: What a rejected completion is told. There is deliberately no attempt to say
#: which half of the fence failed: finding out would mean reading the rows the
#: statement just refused to trust, and the answer would be stale on arrival.
REJECTED_REASON: Final = (
    "the completion was refused: this worker no longer holds the lease, "
    "or its attempt is already closed"
)


@dataclass(frozen=True)
class Backoff:
    """Bounded exponential backoff with jitter, in milliseconds.

    The contract calls the parameters configuration rather than contract, so the
    only fixed properties are the ones a scenario can rest on: the delay grows
    with the attempt, never exceeds ``max_ms``, and never reaches zero. Full
    jitter would allow zero and let an exhausted retry storm re-collide, so the
    window is the upper half of the exponential — ``[ceiling/2, ceiling]``.
    """

    base_ms: int
    max_ms: int
    jitter: Jitter = field(default=random.random)

    @classmethod
    def from_config(cls, config: PlatformConfig, jitter: Jitter | None = None) -> Backoff:
        return cls(
            base_ms=config.retry_base_ms,
            max_ms=config.retry_max_ms,
            jitter=random.random if jitter is None else jitter,
        )

    def delay_ms(self, attempt_count: int) -> float:
        """The delay before the attempt after ``attempt_count`` may start."""
        exponent = max(attempt_count - 1, 0)
        ceiling = float(min(self.max_ms, self.base_ms * 2**exponent))
        half = ceiling / 2.0
        fraction = min(max(self.jitter(), 0.0), 1.0)
        return half + half * fraction


@dataclass(frozen=True)
class ClaimedJob:
    """One job handed to one worker, with the attempt row that fences its writes."""

    job_id: UUID
    attempt_id: UUID
    attempt_no: int
    handler: str
    payload: Any
    correlation_id: str
    worker_id: str
    attempt_count: int
    max_attempts: int
    lease_expires_at: datetime
    reclaimed_from_attempt_no: int | None = None

    @property
    def is_last_attempt(self) -> bool:
        """Whether a retryable failure now would exhaust the budget."""
        return self.attempt_count >= self.max_attempts


@dataclass(frozen=True)
class Completion:
    """What a completion statement did, including refusing to do anything."""

    accepted: bool
    state: JobState | None = None
    outcome: AttemptOutcome | None = None
    attempt_no: int | None = None
    terminal_reason: str | None = None
    reason: str | None = None

    def __bool__(self) -> bool:
        return self.accepted


# --------------------------------------------------------------------------- #
# Statements
# --------------------------------------------------------------------------- #

CREATE_JOB = """
insert into job (id, handler, payload, state, attempt_count, max_attempts,
                 available_at, correlation_id)
values (%(id)s, %(handler)s, %(payload)s, 'PENDING', 0, %(max_attempts)s,
        now() + make_interval(secs => %(available_in_seconds)s), %(correlation_id)s)
returning id, correlation_id, available_at
"""

# The whole state machine's entry point. One statement, five parts:
#
#   candidate  the row this worker is allowed to take, locked and skipped over by
#              anyone else. The predicate is the contract's, verbatim: PENDING and
#              due, or RUNNING with a lease that has run out.
#   abandoned  the previous attempt, if the candidate was a reclaim. Closing it is
#              what keeps I2 true when the reclaim opens a new one.
#   exhausted  a candidate whose budget is already spent. I4 is a CHECK, so
#              incrementing past it would raise; the contract's answer is a
#              terminal transition instead, and this is where it happens.
#   started    the claim itself: budget consumed, lease granted.
#   opened     the new attempt row. It reads `abandoned` so that the close is
#              ordered before this insert; two open attempts for one job would
#              otherwise race the partial unique index within one statement.
#
# `materialized` is explicit because correctness depends on it: `candidate` is
# referenced four times and must lock exactly one row exactly once.
CLAIM_NEXT = """
with candidate as materialized (
    select j.id, j.state, j.handler, j.payload, j.attempt_count, j.max_attempts,
           j.correlation_id, j.lease_expires_at
    from job j
    where (j.state = 'PENDING' and j.available_at <= now())
       or (j.state = 'RUNNING' and j.lease_expires_at < now())
    order by j.available_at
    for update skip locked
    limit 1
),
abandoned as (
    update job_attempt a
    set finished_at = now(),
        outcome = 'ABANDONED',
        error_class = 'LEASE_ABANDONED',
        error_summary = %(abandoned_summary)s
    from candidate c
    where a.job_id = c.id and a.finished_at is null
    returning a.job_id, a.attempt_no, c.lease_expires_at as expired_at
),
exhausted as (
    update job j
    set state = 'FAILED',
        lease_owner = null,
        lease_expires_at = null,
        terminal_reason = case
            when c.state = 'RUNNING' then 'LEASE_ABANDONED'
            else 'PLATFORM_TRANSIENT'
        end,
        updated_at = now()
    from candidate c
    where j.id = c.id and c.attempt_count >= c.max_attempts
    returning j.id, j.terminal_reason
),
started as (
    update job j
    set state = 'RUNNING',
        attempt_count = j.attempt_count + 1,
        lease_owner = %(worker_id)s,
        lease_expires_at = now() + make_interval(secs => %(lease_seconds)s),
        updated_at = now()
    from candidate c
    where j.id = c.id and c.attempt_count < c.max_attempts
    returning j.id, j.attempt_count, j.lease_expires_at
),
opened as (
    insert into job_attempt (id, job_id, attempt_no, worker_id, correlation_id)
    select gen_random_uuid(),
           s.id,
           coalesce((select max(a.attempt_no) from job_attempt a where a.job_id = s.id), 0) + 1,
           %(worker_id)s,
           c.correlation_id
    from started s
    join candidate c on c.id = s.id
    left join abandoned ab on ab.job_id = s.id
    returning id, job_id, attempt_no
),
-- Why the conflict answer is computed here and not in a second statement.
--
-- `candidate` skips locked rows silently, so a worker that takes nothing cannot
-- tell an empty queue from one somebody else is holding. Asking afterwards used
-- to answer that, but the worker's connection is autocommit: a second statement
-- is a second transaction and therefore a second `now()`. A job becoming due in
-- the gap was absent from the claim and present in the question, and got counted
-- as a conflict that never happened. Measured at 3 in 400 trials with one job
-- scheduled 1.2 ms ahead and nothing else running, and it made
-- `test_job_002` fail 2 times in 30 runs of an unmutated tree.
--
-- Here there is no gap: one statement, one read view, one clock. A row that is
-- claimable in this scan but was not taken above is one another transaction
-- holds. The `not exists` guard keeps the scan off the hot path — when a row was
-- claimed there is nothing to explain.
conflict as (
    select j.id, j.correlation_id
    from job j
    where not exists (select 1 from candidate)
      and ((j.state = 'PENDING' and j.available_at <= now())
        or (j.state = 'RUNNING' and j.lease_expires_at < now()))
    order by j.available_at
    limit 1
)
-- Driven from a one-row relation so the statement always returns exactly one row:
-- the conflict answer has to come back even when nothing was claimed, and
-- `job_id is null` is what "nothing was claimable" reads as.
select c.id as job_id,
       c.state as from_state,
       c.handler, c.payload, c.correlation_id, c.max_attempts,
       s.attempt_count, s.lease_expires_at,
       o.id as attempt_id, o.attempt_no,
       ab.attempt_no as abandoned_attempt_no,
       extract(epoch from (now() - ab.expired_at)) * 1000 as recovery_latency_ms,
       e.terminal_reason as exhausted_reason,
       cf.id is not null as conflict_exists,
       cf.correlation_id as conflict_correlation_id
from (select 1) probe
left join candidate c on true
left join started s on s.id = c.id
left join opened o on o.job_id = c.id
left join abandoned ab on ab.job_id = c.id
left join exhausted e on e.id = c.id
left join conflict cf on true
"""


# The fence, shared by all three completion paths and identical in each.
#
# `for update of j` locks the job row and only the job row. Locking the attempt
# too would invert the order a reclaim takes its locks in — job first, then
# attempt — and two workers finishing and reclaiming the same job would deadlock.
# Holding the job row is sufficient: a reclaim cannot get past `candidate`
# without it, and one that committed earlier is already visible here.
_FENCE = """
with fenced as materialized (
    select j.id as job_id, a.id as attempt_id, a.attempt_no
    from job j
    join job_attempt a
      on a.job_id = j.id
     and a.id = %(attempt_id)s
     and a.finished_at is null
    where j.id = %(job_id)s
      and j.state = 'RUNNING'
      and j.lease_owner = %(worker_id)s
    for update of j
),
attempt_closed as (
    update job_attempt a
    set finished_at = now(),
        outcome = %(outcome)s,
        error_class = %(error_class)s,
        error_summary = %(error_summary)s,
        error_detail = %(error_detail)s
    from fenced f
    where a.id = f.attempt_id and a.finished_at is null
    returning a.attempt_no
),
"""

_SETTLE = """
job_settled as (
    update job j
    set {assignments},
        updated_at = now()
    from fenced f
    where j.id = f.job_id
    returning j.state, j.attempt_count, j.max_attempts, j.terminal_reason, j.handler,
              j.correlation_id, j.available_at
)
select js.state, js.attempt_count, js.max_attempts, js.terminal_reason, js.handler,
       js.correlation_id, js.available_at, ac.attempt_no
from job_settled js
left join attempt_closed ac on true
"""

_SUCCEED_ASSIGNMENTS = """
        state = 'SUCCEEDED',
        lease_owner = null,
        lease_expires_at = null"""

_PERMANENT_ASSIGNMENTS = """
        state = 'FAILED',
        lease_owner = null,
        lease_expires_at = null,
        terminal_reason = %(terminal_reason)s"""

# The budget test lives in SQL rather than in a prior read, so the decision uses
# the same row version the update writes. Reading first and deciding in Python
# would leave a window in which the two disagree.
_RETRYABLE_ASSIGNMENTS = """
        state = case when j.attempt_count >= j.max_attempts then 'FAILED' else 'PENDING' end,
        lease_owner = null,
        lease_expires_at = null,
        terminal_reason = case
            when j.attempt_count >= j.max_attempts then %(terminal_reason)s
        end,
        available_at = case
            when j.attempt_count >= j.max_attempts then j.available_at
            else now() + make_interval(secs => %(delay_seconds)s)
        end"""

COMPLETE_SUCCESS = _FENCE + _SETTLE.format(assignments=_SUCCEED_ASSIGNMENTS)
COMPLETE_PERMANENT = _FENCE + _SETTLE.format(assignments=_PERMANENT_ASSIGNMENTS)
COMPLETE_RETRYABLE = _FENCE + _SETTLE.format(assignments=_RETRYABLE_ASSIGNMENTS)

APPLY_EFFECT = """
insert into platform_effect (effect_key, job_id, payload)
values (%(effect_key)s, %(job_id)s, %(payload)s)
on conflict (effect_key) do nothing
returning effect_key
"""

REQUEST_RETRY = """
update job
set state = 'PENDING',
    attempt_count = 0,
    available_at = now(),
    lease_owner = null,
    lease_expires_at = null,
    terminal_reason = null,
    updated_at = now()
where id = %(job_id)s and state = 'FAILED'
returning correlation_id, handler
"""

READ_JOB = """
select id, handler, payload, state, attempt_count, max_attempts, available_at,
       lease_owner, lease_expires_at, terminal_reason, correlation_id,
       created_at, updated_at
from job
where id = %(job_id)s
"""

# The same columns as READ_JOB, because an operator scanning a list and an operator
# opening one job should not be reading two different shapes of the same row.
#
# The `%(state)s::text is null` form is what makes one statement serve both the
# filtered and the unfiltered list. The cast is required rather than cosmetic:
# without it the server cannot infer a type for a parameter compared only against
# null. Newest first, because the failure an operator is looking for is almost
# always the most recent one; `id` breaks ties so that paging is stable when two
# jobs share a creation instant.
LIST_JOBS = """
select id, handler, payload, state, attempt_count, max_attempts, available_at,
       lease_owner, lease_expires_at, terminal_reason, correlation_id,
       created_at, updated_at
from job
where %(state)s::text is null or state = %(state)s::text
order by created_at desc, id desc
limit %(limit)s offset %(offset)s
"""

COUNT_JOBS = """
select count(*) as matched
from job
where %(state)s::text is null or state = %(state)s::text
"""

# Every state that has at least one job, for the platform-health summary. States
# with none are absent from the result and are filled in by the caller, so a
# reader never has to know whether a missing key means zero or means the state
# does not exist.
COUNT_BY_STATE = """
select state, count(*) as jobs
from job
group by state
"""

# `error_detail` is selected. Which representation may show it is decided one
# layer up, by `api.app`, and SEC-004 requires the default one not to — a read
# that omitted the column here would make the protected representation impossible
# instead of making the default one safe.
READ_ATTEMPTS = """
select id, job_id, attempt_no, worker_id, started_at, finished_at, outcome,
       error_class, error_summary, error_detail, correlation_id
from job_attempt
where job_id = %(job_id)s
order by attempt_no
"""


class JobStore:
    """Data access for CONTRACT-JOB@0.1. One instance per connection.

    The connection is the caller's. Nothing here commits, opens a transaction, or
    closes anything, because the transaction boundary is one of the things this
    experiment is meant to observe rather than hide. Every method is one
    statement, so an autocommit connection gives one transaction per operation,
    which is what the worker uses.
    """

    def __init__(
        self,
        connection: psycopg.Connection[Any],
        config: PlatformConfig,
        logger: StructuredLogger | None = None,
        metrics: MetricsRegistry | None = None,
        backoff: Backoff | None = None,
    ) -> None:
        self._connection = connection
        self._config = config
        self._logger = StructuredLogger() if logger is None else logger
        self._metrics = MetricsRegistry() if metrics is None else metrics
        self._backoff = Backoff.from_config(config) if backoff is None else backoff

    @property
    def metrics(self) -> MetricsRegistry:
        return self._metrics

    @property
    def logger(self) -> StructuredLogger:
        return self._logger

    @property
    def backoff(self) -> Backoff:
        return self._backoff

    # ----------------------------------------------------------------- create

    def create_job(
        self,
        handler: str,
        payload: Any,
        max_attempts: int,
        available_in_seconds: float = 0.0,
        correlation_id: str | None = None,
    ) -> UUID:
        """Persist a new ``PENDING`` job and return its identity.

        ``available_in_seconds`` is a delay rather than an instant on purpose. The
        contract's "Ordering, time, and identity" rule is that the database
        generates every timestamp a lease or availability decision reads; an
        absolute ``available_at`` from a caller would be the one application clock
        the platform trusts, and a skewed one would make a job due early.
        """
        if not handler or not handler.strip():
            raise ConfigurationInvalidError(
                "a job must name a handler; it is rejected at creation and not persisted"
            )
        if max_attempts < 1:
            raise ConfigurationInvalidError(
                f"a job needs an attempt budget of at least one, not {max_attempts}; "
                "it is rejected at creation and not persisted"
            )
        job_id = uuid4()
        assigned = new_correlation_id() if correlation_id is None else correlation_id
        parameters = {
            "id": job_id,
            "handler": handler,
            "payload": Jsonb(payload),
            "max_attempts": max_attempts,
            "available_in_seconds": float(available_in_seconds),
            "correlation_id": assigned,
        }
        with self._cursor() as cursor:
            cursor.execute(CREATE_JOB, parameters)
            row = cursor.fetchone()
        assert row is not None
        with correlation_context(assigned):
            self._transition(
                job_id=job_id,
                handler=handler,
                attempt_no=0,
                from_state=None,
                to_state=JobState.PENDING,
                available_at=row["available_at"],
            )
        return job_id

    # ------------------------------------------------------------------ claim

    def claim_next(self, worker_id: str, lease_seconds: float) -> ClaimedJob | None:
        """Take the next claimable job, recovering an expired lease if that is what it is.

        Returns ``None`` when nothing was claimable — including when the only
        claimable row had already spent its budget, which this statement settles
        as ``FAILED`` rather than leaving for a sweep that does not exist.
        """
        parameters = {
            "worker_id": worker_id,
            "lease_seconds": float(lease_seconds),
            "abandoned_summary": ABANDONED_SUMMARY,
        }
        with self._cursor() as cursor:
            cursor.execute(CLAIM_NEXT, parameters)
            row = cursor.fetchone()
        if row is None or row["job_id"] is None:
            self._note_claim_conflict(row)
            return None

        if row["abandoned_attempt_no"] is not None:
            self._metrics.record_abandoned_attempt()
            self._metrics.record_lease_recovery_latency_ms(
                max(float(row["recovery_latency_ms"] or 0.0), 0.0)
            )

        if row["attempt_id"] is None:
            self._settled_without_claiming(row)
            return None

        claimed = ClaimedJob(
            job_id=row["job_id"],
            attempt_id=row["attempt_id"],
            attempt_no=row["attempt_no"],
            handler=row["handler"],
            payload=row["payload"],
            correlation_id=row["correlation_id"],
            worker_id=worker_id,
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            lease_expires_at=row["lease_expires_at"],
            reclaimed_from_attempt_no=row["abandoned_attempt_no"],
        )
        with correlation_context(claimed.correlation_id):
            if claimed.reclaimed_from_attempt_no is not None:
                self._logger.warning(
                    "job.attempt_abandoned",
                    job_id=claimed.job_id,
                    handler=claimed.handler,
                    attempt_no=claimed.reclaimed_from_attempt_no,
                    error_class=ErrorClass.LEASE_ABANDONED.value,
                    reclaimed_by=worker_id,
                )
            self._transition(
                job_id=claimed.job_id,
                handler=claimed.handler,
                attempt_no=claimed.attempt_no,
                from_state=JobState(row["from_state"]),
                to_state=JobState.RUNNING,
                worker_id=worker_id,
                lease_expires_at=claimed.lease_expires_at,
            )
        return claimed

    # ------------------------------------------------------------- completion

    def complete_success(self, job_id: UUID, attempt_id: UUID, worker_id: str) -> Completion:
        """Record a handler that returned normally. Fenced."""
        return self._complete(
            statement=COMPLETE_SUCCESS,
            job_id=job_id,
            attempt_id=attempt_id,
            worker_id=worker_id,
            outcome=AttemptOutcome.SUCCEEDED,
            error=None,
        )

    def complete_permanent(
        self, job_id: UUID, attempt_id: UUID, worker_id: str, error: PlatformError
    ) -> Completion:
        """Record a failure the contract does not permit retrying. Fenced."""
        if error.retryable:
            raise ValueError(
                f"{error.error_class.value} is retryable; "
                "use complete_retryable so the attempt budget decides"
            )
        return self._complete(
            statement=COMPLETE_PERMANENT,
            job_id=job_id,
            attempt_id=attempt_id,
            worker_id=worker_id,
            outcome=AttemptOutcome.PERMANENT_FAILURE,
            error=error,
            extra={"terminal_reason": error.error_class.value},
        )

    def complete_retryable(
        self, job_id: UUID, attempt_id: UUID, worker_id: str, error: PlatformError
    ) -> Completion:
        """Reschedule with backoff, or go terminal if the budget is spent. Fenced.

        Which of the two happened is decided inside the statement and reported
        back in ``Completion.state``; the delay is computed here because backoff
        parameters are configuration and jitter has to be injectable for a test.
        """
        if not error.retryable:
            raise ValueError(
                f"{error.error_class.value} is not retryable; use complete_permanent"
            )
        attempt_no = self._attempt_number(attempt_id)
        return self._complete(
            statement=COMPLETE_RETRYABLE,
            job_id=job_id,
            attempt_id=attempt_id,
            worker_id=worker_id,
            outcome=AttemptOutcome.RETRYABLE_FAILURE,
            error=error,
            extra={
                "terminal_reason": error.error_class.value,
                "delay_seconds": self._backoff.delay_ms(attempt_no) / 1000.0,
            },
        )

    # ----------------------------------------------------------------- effect

    def apply_effect(self, job_id: UUID, effect_key: str, payload: Any = None) -> bool:
        """Apply the one durable effect a P0-A handler may produce.

        Returns ``False`` when the key was already present. That is not a failure:
        at-least-once delivery makes a repeat expected, and I1 is held by the
        primary key rather than by anyone checking first. The suppression is
        counted and logged so that a duplicate is observable rather than silent.
        """
        parameters = {"effect_key": effect_key, "job_id": job_id, "payload": Jsonb(payload)}
        with self._cursor() as cursor:
            cursor.execute(APPLY_EFFECT, parameters)
            row = cursor.fetchone()
        if row is None:
            self._metrics.record_suppressed_duplicate_effect()
            self._logger.info(
                "job.effect_suppressed",
                job_id=job_id,
                effect_key=effect_key,
            )
            return False
        self._logger.info("job.effect_applied", job_id=job_id, effect_key=effect_key)
        return True

    # -------------------------------------------------------------- operator

    def request_retry(self, job_id: UUID) -> bool:
        """The operator's safe retry: ``FAILED`` back to ``PENDING``, budget restored.

        Earlier attempts are kept — they are the diagnosis the operator acted on.
        Only ``attempt_count`` resets, which is why an attempt's number comes from
        the attempts themselves and not from that counter.
        """
        with self._cursor() as cursor:
            cursor.execute(REQUEST_RETRY, {"job_id": job_id})
            row = cursor.fetchone()
        if row is None:
            with correlation_context(self._correlation_of(job_id)):
                self._logger.warning(
                    "job.retry_refused",
                    job_id=job_id,
                    reason="only a FAILED job may be safely retried",
                )
            return False
        with correlation_context(row["correlation_id"]):
            self._transition(
                job_id=job_id,
                handler=row["handler"],
                attempt_no=0,
                from_state=JobState.FAILED,
                to_state=JobState.PENDING,
                trigger="operator safe retry",
            )
        return True

    # ------------------------------------------------------------------ reads

    def read_job(self, job_id: UUID) -> dict[str, Any] | None:
        """One job row, for an operator surface or a test assertion."""
        with self._cursor() as cursor:
            cursor.execute(READ_JOB, {"job_id": job_id})
            return cursor.fetchone()

    def list_jobs(
        self,
        state: JobState | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """A page of jobs, newest first, optionally of one state only.

        The operator path OPS-001 takes to *find* a failure before inspecting it.
        ``state`` is a ``JobState`` rather than a string so that the closed set of
        the CHECK constraint is the only thing that can reach the statement.
        """
        parameters = {
            "state": None if state is None else state.value,
            "limit": int(limit),
            "offset": int(offset),
        }
        with self._cursor() as cursor:
            cursor.execute(LIST_JOBS, parameters)
            return cursor.fetchall()

    def count_jobs(self, state: JobState | None = None) -> int:
        """How many jobs the same filter matches, so a page can say what it is part of.

        A second statement, and therefore a second instant: under a concurrent
        write it can disagree with the page it accompanies by one job. That is
        acceptable for an operator count and is not acceptable for anything that
        decides a transition, which is why no transition reads it.
        """
        with self._cursor() as cursor:
            cursor.execute(COUNT_JOBS, {"state": None if state is None else state.value})
            row = cursor.fetchone()
        return 0 if row is None else int(row["matched"])

    def count_by_state(self) -> dict[str, int]:
        """Jobs per state, with every state present even when it holds none.

        Read by ``/health``. Its second job is to be a statement the database has
        to answer *from the platform schema*: a database that exists but has no
        ``job`` table fails here, which is the honest answer for platform health
        and is what a bare ``select 1`` would have called healthy.
        """
        counted = dict.fromkeys(JOB_STATES, 0)
        with self._cursor() as cursor:
            cursor.execute(COUNT_BY_STATE)
            for row in cursor.fetchall():
                counted[str(row["state"])] = int(row["jobs"])
        return counted

    def read_attempts(self, job_id: UUID) -> list[dict[str, Any]]:
        """Every attempt of one job, oldest first, with the protected column included.

        Ordered by ``attempt_no`` rather than by ``started_at`` because the number
        is the contract's ordering and is unique per job, while two attempts could
        in principle share a start instant.
        """
        with self._cursor() as cursor:
            cursor.execute(READ_ATTEMPTS, {"job_id": job_id})
            return cursor.fetchall()

    # -------------------------------------------------------------- internals

    def durable_scope(self) -> AbstractContextManager[None]:
        """A transaction that a handler's writes and its completion share.

        The P0-A Completion Gate recorded this as **the largest gap P0-A leaves**:
        every duplicate-suppression result there rests on one row and one primary-key
        conflict, while "a P0-B acquisition or normalization effect spans several
        statements and probably several tables, where the question becomes
        transactional". This is that transaction.

        Why the completion has to be inside it, rather than following it: a worker that
        stalled past its lease has had its work handed to someone else. If it commits its
        writes and *then* meets the fence, the refusal comes too late — the rows are
        already there and the other worker's are too. Inside one transaction the refusal
        discards them, which is the only ordering that makes at-least-once delivery safe
        for an effect the platform cannot deduplicate by key.

        Nothing here is source-aware, and that is what keeps this module inside its own
        boundary. A transaction is not a domain concept; it is the generic mechanism the
        gate said P0-B would need.
        """
        return self._transaction()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._connection.transaction():
            yield

    def _cursor(self) -> psycopg.Cursor[dict[str, Any]]:
        return self._connection.cursor(row_factory=dict_row)

    def _attempt_number(self, attempt_id: UUID) -> int:
        """The attempt's own number, for the backoff curve.

        Read separately because backoff is computed in Python. It is only an
        input to a delay: if it were stale the completion would still be fenced,
        and the worst outcome is a job that waits for the wrong number of
        milliseconds.
        """
        with self._cursor() as cursor:
            cursor.execute(
                "select attempt_no from job_attempt where id = %(attempt_id)s",
                {"attempt_id": attempt_id},
            )
            row = cursor.fetchone()
        return 1 if row is None else int(row["attempt_no"])

    def _complete(
        self,
        statement: str,
        job_id: UUID,
        attempt_id: UUID,
        worker_id: str,
        outcome: AttemptOutcome,
        error: PlatformError | None,
        extra: Mapping[str, Any] | None = None,
    ) -> Completion:
        parameters: dict[str, Any] = {
            "job_id": job_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "outcome": outcome.value,
            "error_class": None if error is None else error.error_class.value,
            "error_summary": None if error is None else error.summary,
            "error_detail": None if error is None else Jsonb(error.detail.for_protected_debug()),
        }
        if extra is not None:
            parameters.update(extra)
        with self._cursor() as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
        if row is None:
            return self._rejected(job_id, attempt_id, worker_id, outcome)
        state = JobState(row["state"])
        completion = Completion(
            accepted=True,
            state=state,
            outcome=outcome,
            attempt_no=row["attempt_no"],
            terminal_reason=row["terminal_reason"],
        )
        # `attempt_count` is on every completion event because two terminal
        # events that differ only in how much budget was spent — exhausted after
        # the last attempt, or refused on the first — would otherwise read the
        # same. `available_at` is on the reschedule event because "returned to
        # the queue" is not an observation until it says when.
        scheduled = {"available_at": row["available_at"]} if state is JobState.PENDING else {}
        with correlation_context(row["correlation_id"]):
            self._transition(
                job_id=job_id,
                handler=row["handler"],
                attempt_no=completion.attempt_no,
                from_state=JobState.RUNNING,
                to_state=state,
                outcome=outcome.value,
                error_class=None if error is None else error.error_class.value,
                # The operator-visible half of the failure, and only that half.
                # It was redacted when the error was built and is redacted again
                # on the way into the line; the protected detail stays out.
                error_summary=None if error is None else error.summary,
                terminal_reason=row["terminal_reason"],
                attempt_count=row["attempt_count"],
                max_attempts=row["max_attempts"],
                **scheduled,
            )
        return completion

    def _rejected(
        self, job_id: UUID, attempt_id: UUID, worker_id: str, outcome: AttemptOutcome
    ) -> Completion:
        """Refuse a completion, change nothing, and leave the evidence that it happened.

        The refused statement returned no row, so it also returned no
        ``correlation_id``, and I5 admits no log line about a job without one.
        Reading it back costs one statement on a path that is rare by
        construction, and a rejection nobody can correlate is the one this
        experiment would most want to trace.
        """
        self._metrics.record_rejected_completion()
        with correlation_context(self._correlation_of(job_id)):
            self._logger.warning(
                "job.completion_rejected",
                job_id=job_id,
                attempt_id=attempt_id,
                worker_id=worker_id,
                intended_outcome=outcome.value,
                reason=REJECTED_REASON,
            )
        return Completion(accepted=False, reason=REJECTED_REASON)

    def _correlation_of(self, job_id: UUID) -> str | None:
        """This job's correlation identifier, or ``None`` if there is no such job."""
        with self._cursor() as cursor:
            cursor.execute(
                "select correlation_id from job where id = %(job_id)s", {"job_id": job_id}
            )
            row = cursor.fetchone()
        return None if row is None else str(row["correlation_id"])

    def _settled_without_claiming(self, row: Mapping[str, Any]) -> None:
        """A candidate whose budget was already spent went terminal instead."""
        with correlation_context(row["correlation_id"]):
            self._transition(
                job_id=row["job_id"],
                handler=row["handler"],
                attempt_no=row["abandoned_attempt_no"],
                from_state=JobState(row["from_state"]),
                to_state=JobState.FAILED,
                terminal_reason=row["exhausted_reason"],
                trigger="attempt budget spent",
            )

    def _note_claim_conflict(self, row: Mapping[str, Any] | None) -> None:
        """Count a claim that found nothing while something was claimable.

        The answer arrives with the claim rather than after it, so it was read
        from the same read view and the same clock — see `CLAIM_NEXT`.

        The line carries the held job's `correlation_id` because I5 makes
        correlation total and this line concerns a job. The row is readable: the
        other transaction holds a write lock, which does not block this read.
        """
        if row is None or not row["conflict_exists"]:
            return
        self._metrics.record_claim_conflict()
        self._logger.info(
            "job.claim_conflict",
            correlation_id=row["conflict_correlation_id"],
            reason="a claimable job is held elsewhere",
        )

    def _transition(
        self,
        job_id: UUID,
        handler: str | None,
        attempt_no: int | None,
        from_state: JobState | None,
        to_state: JobState,
        **fields: Any,
    ) -> None:
        """One structured event per state transition, and one counter increment.

        I5 is why ``correlation_id`` is not an argument: the logger reads the
        ambient identifier, so a caller cannot forget it. Every caller here enters
        the job's correlation scope first.
        """
        self._metrics.record_transition(to_state.value)
        self._logger.info(
            "job.transition",
            job_id=job_id,
            handler=handler,
            attempt_no=attempt_no,
            from_state=None if from_state is None else from_state.value,
            to_state=to_state.value,
            **fields,
        )
