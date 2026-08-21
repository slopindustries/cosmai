"""In-process counters and durations required by CONTRACT-JOB@0.1.

The contract's observability requirement names exactly what has to exist:
counters for transitions by target state, claim conflicts, suppressed duplicate
effect insertions, abandoned attempts, and completions the fencing rule refused;
durations for attempt execution and lease recovery latency. This module is that
list, plus one counter the contract's text implied but did not name:
``rejected_effects``, added in P1 when issue #4 found that applying an effect
went through no fence at all — see ``platform_core.jobs.store.APPLY_EFFECT``.

In-memory is sufficient because P0-A is single-host by declaration. A metrics
backend would add an operational dependency without reducing a named
uncertainty; the reading below is what the operator API returns in T5.2.

One rule is enforced rather than documented: the only label in the whole module
is the target state, and it must be one of the four states the contract defines.
SEC-004 requires that metric labels carry no payload-derived value, and a
registry that accepts an arbitrary label string is one payload interpolation away
from breaking that.

The four states themselves are not spelled here. ``platform_core.jobs.state`` is
where the state machine lives, and a second copy of a closed set is a copy that
can disagree with the CHECK constraint without anything noticing. Instrumentation
importing the state machine it labels is the direction that keeps one owner;
``platform_core.jobs`` therefore imports nothing, so the dependency stays acyclic.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any, Final

from platform_core.jobs.state import JOB_STATES

#: The job states of CONTRACT-JOB@0.1. The only permitted metric label values.
TARGET_STATES: Final[tuple[str, ...]] = JOB_STATES


@dataclass(frozen=True)
class DurationReading:
    """A closed-over view of one duration series, in milliseconds."""

    count: int
    total_ms: float
    min_ms: float
    max_ms: float

    @property
    def mean_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "count": float(self.count),
            "total_ms": self.total_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "mean_ms": self.mean_ms,
        }


@dataclass(frozen=True)
class MetricsReading:
    """An immutable point-in-time copy of every metric."""

    transitions: Mapping[str, int]
    claim_conflicts: int
    suppressed_duplicate_effects: int
    abandoned_attempts: int
    rejected_completions: int
    rejected_effects: int
    attempt_duration: DurationReading
    lease_recovery_latency: DurationReading

    def as_dict(self) -> dict[str, Any]:
        return {
            "transitions": dict(self.transitions),
            "claim_conflicts": self.claim_conflicts,
            "suppressed_duplicate_effects": self.suppressed_duplicate_effects,
            "abandoned_attempts": self.abandoned_attempts,
            "rejected_completions": self.rejected_completions,
            "rejected_effects": self.rejected_effects,
            "attempt_duration_ms": self.attempt_duration.as_dict(),
            "lease_recovery_latency_ms": self.lease_recovery_latency.as_dict(),
        }


class _Durations:
    """Running aggregate of one duration series. Not thread-safe on its own."""

    __slots__ = ("_count", "_maximum", "_minimum", "_total")

    def __init__(self) -> None:
        self._count = 0
        self._total = 0.0
        self._minimum = 0.0
        self._maximum = 0.0

    def add(self, milliseconds: float) -> None:
        if milliseconds < 0:
            raise ValueError("a duration in milliseconds cannot be negative")
        self._minimum = milliseconds if self._count == 0 else min(self._minimum, milliseconds)
        self._maximum = max(self._maximum, milliseconds)
        self._count += 1
        self._total += milliseconds

    def read(self) -> DurationReading:
        return DurationReading(
            count=self._count,
            total_ms=self._total,
            min_ms=self._minimum,
            max_ms=self._maximum,
        )


class MetricsRegistry:
    """The platform's metric set. One instance per process is expected."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._transitions: dict[str, int] = dict.fromkeys(TARGET_STATES, 0)
        self._claim_conflicts = 0
        self._suppressed_duplicate_effects = 0
        self._abandoned_attempts = 0
        self._rejected_completions = 0
        self._rejected_effects = 0
        self._attempt_duration = _Durations()
        self._lease_recovery_latency = _Durations()

    def record_transition(self, target_state: str, count: int = 1) -> None:
        """Count one state transition, labelled by the state it arrived at."""
        # A JobState member is a str whose value is the label, so a caller may
        # pass either; str() collapses the two spellings before the check.
        label = str(target_state)
        if label not in self._transitions:
            raise ValueError(
                f"unknown target state {target_state!r}; "
                f"permitted labels are {', '.join(TARGET_STATES)}"
            )
        with self._lock:
            self._transitions[label] += count

    def record_claim_conflict(self, count: int = 1) -> None:
        """Count one worker finding a job already claimed."""
        with self._lock:
            self._claim_conflicts += count

    def record_suppressed_duplicate_effect(self, count: int = 1) -> None:
        """Count one repeat effect insert that the idempotency key turned into a no-op."""
        with self._lock:
            self._suppressed_duplicate_effects += count

    def record_abandoned_attempt(self, count: int = 1) -> None:
        """Count one attempt closed because its lease expired."""
        with self._lock:
            self._abandoned_attempts += count

    def record_rejected_completion(self, count: int = 1) -> None:
        """Count one completion the fencing rule refused.

        The contract calls a stale worker's late write "the observable symptom",
        so this counter is the evidence that the refusal happened rather than
        that nothing was ever written.
        """
        with self._lock:
            self._rejected_completions += count

    def record_rejected_effect(self, count: int = 1) -> None:
        """Count one applied-effect write the fencing rule refused (issue #4).

        Distinct from :meth:`record_suppressed_duplicate_effect`: that counter is
        I1's idempotency working as designed on a legitimate repeat; this one is
        the fence stopping an attempt the platform has already abandoned from
        writing the job's durable effect at all.
        """
        with self._lock:
            self._rejected_effects += count

    def record_attempt_duration_ms(self, milliseconds: float) -> None:
        """Record how long one attempt's execution took."""
        with self._lock:
            self._attempt_duration.add(milliseconds)

    def record_lease_recovery_latency_ms(self, milliseconds: float) -> None:
        """Record the delay between a lease expiring and the work being reclaimed."""
        with self._lock:
            self._lease_recovery_latency.add(milliseconds)

    @contextmanager
    def measure_attempt(self) -> Iterator[None]:
        """Time a block and record it as an attempt execution, failures included."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.record_attempt_duration_ms((time.perf_counter() - started) * 1000.0)

    def read(self) -> MetricsReading:
        """Take a consistent copy of every metric. Safe to serialize."""
        with self._lock:
            return MetricsReading(
                transitions=dict(self._transitions),
                claim_conflicts=self._claim_conflicts,
                suppressed_duplicate_effects=self._suppressed_duplicate_effects,
                abandoned_attempts=self._abandoned_attempts,
                rejected_completions=self._rejected_completions,
                rejected_effects=self._rejected_effects,
                attempt_duration=self._attempt_duration.read(),
                lease_recovery_latency=self._lease_recovery_latency.read(),
            )

    def reset(self) -> None:
        """Return every metric to its starting value. For tests."""
        with self._lock:
            self._transitions = dict.fromkeys(TARGET_STATES, 0)
            self._claim_conflicts = 0
            self._suppressed_duplicate_effects = 0
            self._abandoned_attempts = 0
            self._rejected_completions = 0
            self._rejected_effects = 0
            self._attempt_duration = _Durations()
            self._lease_recovery_latency = _Durations()
