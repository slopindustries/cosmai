"""The metric set CONTRACT-JOB@0.1 requires, and the label rule SEC-004 imposes.

Two things matter here beyond arithmetic: a reading is a stable copy an operator
API can serialize, and the only label the registry accepts is a job state. A
registry that took an arbitrary label string would be one interpolation away from
putting payload-derived text into a metric name.
"""

from __future__ import annotations

import pytest
from platform_core.obs.metrics import TARGET_STATES, MetricsRegistry


@pytest.fixture
def metrics() -> MetricsRegistry:
    return MetricsRegistry()


def test_a_fresh_registry_reads_as_zero(metrics: MetricsRegistry) -> None:
    reading = metrics.read()
    assert reading.transitions == dict.fromkeys(TARGET_STATES, 0)
    assert reading.claim_conflicts == 0
    assert reading.suppressed_duplicate_effects == 0
    assert reading.abandoned_attempts == 0
    assert reading.rejected_completions == 0
    assert reading.attempt_duration.count == 0
    assert reading.lease_recovery_latency.count == 0


@pytest.mark.parametrize("state", TARGET_STATES)
def test_transitions_are_counted_by_target_state(
    metrics: MetricsRegistry, state: str
) -> None:
    metrics.record_transition(state)
    metrics.record_transition(state)
    reading = metrics.read()
    assert reading.transitions[state] == 2
    assert sum(reading.transitions.values()) == 2


@pytest.mark.parametrize("label", ["", "pending", "CLAIMED", "job-42", "handler=succeed"])
def test_a_label_outside_the_state_set_is_refused(
    metrics: MetricsRegistry, label: str
) -> None:
    """SEC-004: no metric label may carry a payload-derived value."""
    with pytest.raises(ValueError, match="unknown target state"):
        metrics.record_transition(label)


def test_the_remaining_counters_are_independent(metrics: MetricsRegistry) -> None:
    metrics.record_claim_conflict()
    metrics.record_suppressed_duplicate_effect()
    metrics.record_suppressed_duplicate_effect()
    metrics.record_abandoned_attempt(3)
    metrics.record_rejected_completion(4)
    reading = metrics.read()
    assert reading.claim_conflicts == 1
    assert reading.suppressed_duplicate_effects == 2
    assert reading.abandoned_attempts == 3
    assert reading.rejected_completions == 4


def test_durations_aggregate(metrics: MetricsRegistry) -> None:
    for milliseconds in (5.0, 15.0, 10.0):
        metrics.record_attempt_duration_ms(milliseconds)
    duration = metrics.read().attempt_duration
    assert duration.count == 3
    assert duration.total_ms == pytest.approx(30.0)
    assert duration.min_ms == pytest.approx(5.0)
    assert duration.max_ms == pytest.approx(15.0)
    assert duration.mean_ms == pytest.approx(10.0)


def test_lease_recovery_latency_is_a_separate_series(metrics: MetricsRegistry) -> None:
    metrics.record_attempt_duration_ms(4.0)
    metrics.record_lease_recovery_latency_ms(400.0)
    reading = metrics.read()
    assert reading.attempt_duration.count == 1
    assert reading.lease_recovery_latency.count == 1
    assert reading.lease_recovery_latency.max_ms == pytest.approx(400.0)


def test_a_negative_duration_is_refused(metrics: MetricsRegistry) -> None:
    with pytest.raises(ValueError, match="negative"):
        metrics.record_attempt_duration_ms(-1.0)


def test_measuring_a_block_records_an_attempt_duration(metrics: MetricsRegistry) -> None:
    with metrics.measure_attempt():
        pass
    duration = metrics.read().attempt_duration
    assert duration.count == 1
    assert duration.total_ms >= 0.0


def test_a_failing_block_is_still_measured(metrics: MetricsRegistry) -> None:
    with pytest.raises(RuntimeError), metrics.measure_attempt():
        raise RuntimeError("handler failed")
    assert metrics.read().attempt_duration.count == 1


def test_a_reading_does_not_change_afterwards(metrics: MetricsRegistry) -> None:
    metrics.record_transition("SUCCEEDED")
    reading = metrics.read()
    metrics.record_transition("SUCCEEDED")
    assert reading.transitions["SUCCEEDED"] == 1
    assert metrics.read().transitions["SUCCEEDED"] == 2


def test_a_reading_serializes_to_plain_values(metrics: MetricsRegistry) -> None:
    metrics.record_transition("FAILED")
    metrics.record_attempt_duration_ms(2.5)
    payload = metrics.read().as_dict()
    assert payload["transitions"]["FAILED"] == 1
    assert payload["attempt_duration_ms"]["count"] == pytest.approx(1.0)
    assert set(payload) == {
        "transitions",
        "claim_conflicts",
        "suppressed_duplicate_effects",
        "abandoned_attempts",
        "rejected_completions",
        "attempt_duration_ms",
        "lease_recovery_latency_ms",
    }


def test_reset_returns_every_metric_to_zero(metrics: MetricsRegistry) -> None:
    metrics.record_transition("RUNNING")
    metrics.record_claim_conflict()
    metrics.record_rejected_completion()
    metrics.record_attempt_duration_ms(1.0)
    metrics.reset()
    reading = metrics.read()
    assert reading.transitions == dict.fromkeys(TARGET_STATES, 0)
    assert reading.claim_conflicts == 0
    assert reading.rejected_completions == 0
    assert reading.attempt_duration.count == 0
