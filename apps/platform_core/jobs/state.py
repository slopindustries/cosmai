"""The state machine of CONTRACT-JOB@0.1, as the one place its values are named.

Both enumerations here are also CHECK constraints in
``db/migrations/0001_platform_core.sql``. Two spellings of one closed set drift,
and the drift is invisible until a state the database rejects reaches it, so
``tests/test_jobs_store.py`` reads the constraint definitions back out of the
catalog and compares them with these members rather than trusting that they
still agree.

The members are ``StrEnum`` because the columns are ``text``: a member can be
passed straight to psycopg as a parameter and compared with a value read back
without either side converting. That also lets ``obs.metrics`` keep accepting
plain strings while this module is its single source for what the labels are.

The transition table is expressed here as data as well. It is not consulted at
run time — the store's SQL is what actually enforces the machine — but it makes
"eight transitions, these eight" checkable rather than a claim in prose.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class JobState(StrEnum):
    """The four states of ``job.state``. The only permitted metric labels."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        """Whether the contract permits no further automatic transition out."""
        return self in _TERMINAL_STATES

    @property
    def is_claimable_state(self) -> bool:
        """Whether a job in this state can still be handed to a worker.

        I3 — no stranded state: every job is terminal or reachable from here.
        ``RUNNING`` qualifies because a lease expires; the store's claim
        statement, not this property, decides whether one has.
        """
        return not self.is_terminal


class AttemptOutcome(StrEnum):
    """The four closed outcomes of ``job_attempt.outcome``. Null while open."""

    SUCCEEDED = "SUCCEEDED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    ABANDONED = "ABANDONED"


_TERMINAL_STATES: Final[frozenset[JobState]] = frozenset({JobState.SUCCEEDED, JobState.FAILED})

#: Every ``job.state`` value, in the contract's order. ``obs.metrics`` uses this
#: as its label allowlist instead of repeating the four strings.
JOB_STATES: Final[tuple[str, ...]] = tuple(state.value for state in JobState)

#: Every ``job_attempt.outcome`` value.
ATTEMPT_OUTCOMES: Final[tuple[str, ...]] = tuple(outcome.value for outcome in AttemptOutcome)

Transition = tuple[JobState | None, JobState, str]
"""(from state, to state, trigger). ``None`` is the job not yet existing."""

#: The "State transitions" table of CONTRACT-JOB@0.1, all eight rows.
TRANSITIONS: Final[tuple[Transition, ...]] = (
    (None, JobState.PENDING, "created"),
    (JobState.PENDING, JobState.RUNNING, "claimed when due"),
    (JobState.RUNNING, JobState.RUNNING, "reclaimed after lease expiry"),
    (JobState.RUNNING, JobState.SUCCEEDED, "handler returned"),
    (JobState.RUNNING, JobState.PENDING, "retryable failure within budget"),
    (JobState.RUNNING, JobState.FAILED, "retryable failure with the budget spent"),
    (JobState.RUNNING, JobState.FAILED, "permanent failure"),
    (JobState.FAILED, JobState.PENDING, "operator safe retry"),
)


def is_permitted_transition(origin: JobState | None, target: JobState) -> bool:
    """Whether the contract's table contains a row for this pair."""
    return any(row[0] == origin and row[1] == target for row in TRANSITIONS)
