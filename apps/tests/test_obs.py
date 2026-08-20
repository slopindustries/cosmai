"""The obs layer: correlation, redaction, structured logging, and metrics.

Copy-adapted from ``experiments/integrated-p0/tests/{test_correlation,
test_redaction, test_logging, test_metrics}.py``, consolidated into one file per
Task 5's file list. Only the source location changed; the assertions,
invariants under test, and detection-control discipline are P0's own.

CONTRACT-JOB@0.1 invariant I5 (correlation is total) and the "Provenance and
security" section (the redacted key set, containment matching, and
``error_summary`` masking) are what this file is evidence for. The redaction
scenario's own reasoning is why every masking assertion below is paired with a
detection control — a distinctive marker under an ordinary key that **must**
survive: without it, "no marker was found" and "nothing was ever searched"
produce the same green result.
"""

from __future__ import annotations

import io
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from platform_core.errors import ConfigurationInvalidError, ErrorClass, PlatformPermanentError
from platform_core.obs.correlation import (
    CORRELATION_FIELD,
    bind_correlation_id,
    correlation_context,
    current_correlation_id,
    new_correlation_id,
    release_correlation_id,
)
from platform_core.obs.logging import LEVELS, StructuredLogger
from platform_core.obs.metrics import TARGET_STATES, MetricsRegistry
from platform_core.obs.redaction import (
    CYCLE_MARKER,
    REDACTED_KEYS,
    REDACTION_MARKER,
    is_redacted_key,
    redact,
    redact_mapping,
    redact_text,
)

SENSITIVE_MARKER = "marker-must-not-leak-42"
ORDINARY_MARKER = "marker-must-survive-42"


# --------------------------------------------------------------------------- #
# Correlation
# --------------------------------------------------------------------------- #

GIVEN_ID = "correlation-under-test"
OTHER_ID = "correlation-under-test-2"


class TestCorrelation:
    def test_the_field_name_matches_the_contract(self) -> None:
        assert CORRELATION_FIELD == "correlation_id"

    def test_minted_identifiers_are_unique(self) -> None:
        minted = {new_correlation_id() for _ in range(100)}
        assert len(minted) == 100
        assert all(value for value in minted)

    def test_there_is_no_identifier_outside_a_scope(self) -> None:
        assert current_correlation_id() is None

    def test_a_scope_mints_an_identifier_when_none_is_given(self) -> None:
        with correlation_context() as value:
            assert value
            assert current_correlation_id() == value
        assert current_correlation_id() is None

    def test_a_scope_honours_an_identifier_it_is_given(self) -> None:
        with correlation_context(GIVEN_ID) as value:
            assert value == GIVEN_ID
            assert current_correlation_id() == GIVEN_ID

    def test_scopes_nest_and_restore(self) -> None:
        with correlation_context(GIVEN_ID):
            with correlation_context(OTHER_ID):
                assert current_correlation_id() == OTHER_ID
            assert current_correlation_id() == GIVEN_ID
        assert current_correlation_id() is None

    def test_a_scope_is_restored_after_an_exception(self) -> None:
        with pytest.raises(RuntimeError), correlation_context(GIVEN_ID):
            raise RuntimeError("handler failed")
        assert current_correlation_id() is None

    def test_bind_and_release_are_the_explicit_form(self) -> None:
        token = bind_correlation_id(GIVEN_ID)
        try:
            assert current_correlation_id() == GIVEN_ID
        finally:
            release_correlation_id(token)
        assert current_correlation_id() is None

    def test_an_empty_identifier_is_refused(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            bind_correlation_id("")

    def test_a_thread_does_not_observe_another_scope(self) -> None:
        """Two workers in one process must never share an identifier by accident."""
        seen: list[str | None] = []

        def observer() -> None:
            seen.append(current_correlation_id())

        with correlation_context(GIVEN_ID):
            thread = threading.Thread(target=observer)
            thread.start()
            thread.join()
            assert current_correlation_id() == GIVEN_ID

        assert seen == [None]


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #

#: The key set `CONTRACT-JOB@0.1` fixes, **written out as literals** so that a
#: key added or removed from the production set is a decision this test notices
#: rather than a derived assertion that moves with the code it is meant to pin.
CONTRACT_REDACTED_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)

ORDINARY_KEY = "note"


def flatten(value: Any) -> list[str]:
    """Every string anywhere in a redacted structure, keys and values alike."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            found.append(str(key))
            found.extend(flatten(item))
        return found
    if isinstance(value, list):
        return [text for item in value for text in flatten(item)]
    return [str(value)]


class TestRedaction:
    def test_the_redacted_key_set_is_exactly_what_the_contract_fixes(self) -> None:
        assert sorted(REDACTED_KEYS) == sorted(CONTRACT_REDACTED_KEYS)

    @pytest.mark.parametrize("key", sorted(CONTRACT_REDACTED_KEYS))
    def test_every_contract_key_is_masked(self, key: str) -> None:
        result = redact({key: SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER})
        assert result[key] == REDACTION_MARKER
        assert result[ORDINARY_KEY] == ORDINARY_MARKER, "detection control failed"

    @pytest.mark.parametrize("key", ["TOKEN", "Token", "ApiKey", "API_KEY", "Authorization"])
    def test_key_matching_ignores_case_and_separators(self, key: str) -> None:
        assert is_redacted_key(key)
        assert redact({key: SENSITIVE_MARKER})[key] == REDACTION_MARKER

    @pytest.mark.parametrize(
        "key", ["db_password", "X-Api-Key", "refreshToken", "user.credential"]
    )
    def test_a_sensitive_key_with_an_affix_is_still_masked(self, key: str) -> None:
        """Masking more than the contract's literal set is the safe direction."""
        assert redact({key: SENSITIVE_MARKER})[key] == REDACTION_MARKER

    @pytest.mark.parametrize(
        "key", ["note", "job_id", "correlation_id", "handler", "attempt_no"]
    )
    def test_ordinary_keys_are_untouched(self, key: str) -> None:
        assert not is_redacted_key(key)
        assert redact({key: ORDINARY_MARKER})[key] == ORDINARY_MARKER

    def test_key_names_survive_so_the_masking_is_diagnostic(self) -> None:
        """SEC-004: knowing a token was present is diagnostic; its value is not."""
        result = redact({"token": SENSITIVE_MARKER})
        assert "token" in result
        assert SENSITIVE_MARKER not in flatten(result)

    def test_nested_mappings_and_sequences_are_walked(self) -> None:
        payload = {
            "outer": {
                "items": [
                    {"password": SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER},
                    ("api_key", {"cookie": SENSITIVE_MARKER}),
                ]
            },
            ORDINARY_KEY: ORDINARY_MARKER,
        }
        result = redact(payload)
        strings = flatten(result)
        assert SENSITIVE_MARKER not in strings
        assert strings.count(ORDINARY_MARKER) == 2, "detection control failed"
        assert result[ORDINARY_KEY] == ORDINARY_MARKER

    def test_the_input_is_not_mutated(self) -> None:
        payload: dict[str, Any] = {
            "token": SENSITIVE_MARKER,
            "nested": {"secret": SENSITIVE_MARKER},
        }
        redact(payload)
        assert payload["token"] == SENSITIVE_MARKER
        assert payload["nested"]["secret"] == SENSITIVE_MARKER

    def test_a_cycle_terminates_instead_of_recursing(self) -> None:
        payload: dict[str, Any] = {"token": SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER}
        payload["self"] = payload
        result = redact(payload)
        assert result["self"] == CYCLE_MARKER
        assert result["token"] == REDACTION_MARKER
        assert result[ORDINARY_KEY] == ORDINARY_MARKER, "detection control failed"

    def test_a_repeated_but_acyclic_value_is_kept_twice(self) -> None:
        """A shared child is not a cycle; treating it as one would hide real fields."""
        shared = {ORDINARY_KEY: ORDINARY_MARKER}
        result = redact({"left": shared, "right": shared})
        assert result["left"] == {ORDINARY_KEY: ORDINARY_MARKER}
        assert result["right"] == {ORDINARY_KEY: ORDINARY_MARKER}

    def test_a_cyclic_sequence_terminates(self) -> None:
        items: list[Any] = [ORDINARY_MARKER]
        items.append(items)
        result = redact({"items": items})
        assert result["items"] == [ORDINARY_MARKER, CYCLE_MARKER]

    def test_non_string_keys_do_not_break_the_walk(self) -> None:
        result = redact({1: SENSITIVE_MARKER, None: ORDINARY_MARKER})
        assert result[1] == SENSITIVE_MARKER
        assert result[None] == ORDINARY_MARKER

    def test_redact_mapping_coerces_keys_for_json(self) -> None:
        result = redact_mapping({1: ORDINARY_MARKER, "token": SENSITIVE_MARKER})
        assert result == {"1": ORDINARY_MARKER, "token": REDACTION_MARKER}

    def test_redact_mapping_accepts_nothing(self) -> None:
        assert redact_mapping(None) == {}
        assert redact_mapping({}) == {}

    @pytest.mark.parametrize(
        "text",
        [
            f"failed with token={SENSITIVE_MARKER}",
            f'failed with "token": "{SENSITIVE_MARKER}"',
            f"failed with Authorization: {SENSITIVE_MARKER}",
        ],
    )
    def test_text_assignments_are_masked(self, text: str) -> None:
        masked = redact_text(text)
        assert SENSITIVE_MARKER not in masked
        assert REDACTION_MARKER in masked
        assert "token" in masked.lower() or "authorization" in masked.lower()

    def test_a_harmless_pair_in_front_does_not_shield_a_sensitive_one(self) -> None:
        """Regression: a leading ``rejected:`` pair used to swallow the real pair."""
        masked = redact_text(f"rejected: api_key={SENSITIVE_MARKER}")
        assert SENSITIVE_MARKER not in masked
        assert masked == f"rejected: api_key={REDACTION_MARKER}"

    def test_every_sensitive_pair_in_one_string_is_masked(self) -> None:
        masked = redact_text(
            f"token={SENSITIVE_MARKER} {ORDINARY_KEY}={ORDINARY_MARKER} "
            f"cookie={SENSITIVE_MARKER} password={SENSITIVE_MARKER}"
        )
        assert SENSITIVE_MARKER not in masked
        assert masked.count(REDACTION_MARKER) == 3
        assert ORDINARY_MARKER in masked, "detection control failed"

    @pytest.mark.parametrize(
        "key", ["api_key", "apikey", "api-key", "API KEY", "Api_Key", "X-Api-Key"]
    )
    def test_every_spelling_of_a_separated_key_is_masked(self, key: str) -> None:
        masked = redact_text(f"{key}={SENSITIVE_MARKER}")
        assert SENSITIVE_MARKER not in masked
        assert masked == f"{key}={REDACTION_MARKER}"

    def test_an_affixed_sensitive_key_is_masked_in_text_as_well(self) -> None:
        """Deliberately the same containment rule ``is_redacted_key`` applies."""
        assert is_redacted_key("mytoken_count")
        assert redact_text("mytoken_count=3") == f"mytoken_count={REDACTION_MARKER}"

    def test_an_authentication_scheme_survives_but_its_value_does_not(self) -> None:
        masked = redact_text(f"authorization: Bearer {SENSITIVE_MARKER}")
        assert SENSITIVE_MARKER not in masked
        assert masked == f"authorization: Bearer {REDACTION_MARKER}"

    def test_text_masking_leaves_ordinary_assignments_alone(self) -> None:
        text = f"handler=succeed attempt_no=2 {ORDINARY_KEY}={ORDINARY_MARKER}"
        assert redact_text(text) == text, "detection control failed"

    def test_text_masking_stops_at_the_end_of_the_value(self) -> None:
        masked = redact_text(f"token={SENSITIVE_MARKER}, {ORDINARY_KEY}={ORDINARY_MARKER}")
        assert ORDINARY_MARKER in masked, "detection control failed"
        assert SENSITIVE_MARKER not in masked


class TestASensitivePairInsideAValueIsMasked:
    """A `key=value` pair inside a string value is caught wherever the walk reaches.

    The key-name limit SEC-004 records still stands for a bare value with no key
    introducing it. Value-level redaction closes the gap for the common case
    where a summary quotes a header or query string verbatim.
    """

    def test_a_pair_inside_a_summary_string_is_masked(self) -> None:
        masked = redact({"error_summary": "the handler failed: token=super-secret-42"})
        assert masked["error_summary"] == "the handler failed: token=[REDACTED]"

    def test_the_same_holds_through_redact_mapping(self) -> None:
        masked = redact_mapping({"error_summary": "refused: api_key=abc123"})
        assert masked["error_summary"] == "refused: api_key=[REDACTED]"

    def test_a_pair_nested_in_a_list_is_masked(self) -> None:
        masked = redact({"notes": ["fine", "authorization: Bearer abc123"]})
        assert masked["notes"] == ["fine", "authorization: Bearer [REDACTED]"]

    def test_an_innocent_string_is_left_alone(self) -> None:
        """The control. A rule that rewrote every string would pass all three above."""
        original = "the handler failed after 3 attempts: state=RUNNING"
        assert redact({"error_summary": original})["error_summary"] == original

    def test_bytes_are_still_left_alone(self) -> None:
        """Raw payloads pass through this walk and must not be rewritten."""
        payload = b"token=not-text-and-not-ours"
        assert redact({"body": payload})["body"] == payload


# --------------------------------------------------------------------------- #
# Structured logging
# --------------------------------------------------------------------------- #

FIXED_TIME = datetime(2026, 8, 17, 9, 30, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


@pytest.fixture
def stream() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def logger(stream: io.StringIO) -> StructuredLogger:
    return StructuredLogger(stream=stream, level="DEBUG", clock=fixed_clock)


def lines_of(stream: io.StringIO) -> list[dict[str, Any]]:
    text = stream.getvalue()
    assert text.endswith("\n") or not text
    return [json.loads(line) for line in text.splitlines()]


def one_line(stream: io.StringIO) -> dict[str, Any]:
    written = lines_of(stream)
    assert len(written) == 1, written
    return written[0]


class TestStructuredLogging:
    def test_one_event_is_one_json_object(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        logger.info("job.claimed", job_id="j-1")
        logger.info("job.finished", job_id="j-1")
        written = lines_of(stream)
        assert len(written) == 2
        assert [line["event"] for line in written] == ["job.claimed", "job.finished"]

    def test_a_multiline_value_stays_on_one_line(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        logger.info("job.failed", note="first\nsecond")
        assert len(stream.getvalue().splitlines()) == 1
        assert one_line(stream)["note"] == "first\nsecond"

    def test_the_structural_fields_are_present(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        with correlation_context(GIVEN_ID):
            logger.info(
                "job.state_changed", job_id="j-1", from_state="PENDING", to_state="RUNNING"
            )
        line = one_line(stream)
        assert line["ts"] == "2026-08-17T09:30:00+00:00"
        assert line["level"] == "INFO"
        assert line["event"] == "job.state_changed"
        assert line["correlation_id"] == GIVEN_ID
        assert line["from_state"] == "PENDING"

    def test_the_timestamp_carries_an_offset(self, stream: io.StringIO) -> None:
        logger = StructuredLogger(stream=stream)
        logger.info("platform.started")
        parsed = datetime.fromisoformat(one_line(stream)["ts"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() is not None

    def test_the_correlation_identifier_is_picked_up_ambiently(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        """Invariant I5 must not depend on every call site remembering."""
        with correlation_context(GIVEN_ID):
            logger.info("job.claimed")
        assert one_line(stream)["correlation_id"] == GIVEN_ID

    def test_an_explicit_identifier_wins_over_the_scope(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        with correlation_context(GIVEN_ID):
            logger.info("job.claimed", correlation_id="explicit-id")
        assert one_line(stream)["correlation_id"] == "explicit-id"

    def test_a_line_outside_a_scope_still_has_the_field(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        logger.info("platform.started")
        assert one_line(stream)["correlation_id"] is None

    def test_sensitive_fields_are_masked_and_ordinary_ones_survive(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        logger.info(
            "job.failed",
            payload={"token": SENSITIVE_MARKER, "note": ORDINARY_MARKER},
            api_key=SENSITIVE_MARKER,
        )
        text = stream.getvalue()
        assert SENSITIVE_MARKER not in text
        assert ORDINARY_MARKER in text, "detection control failed"
        line = one_line(stream)
        assert line["api_key"] == REDACTION_MARKER
        assert line["payload"] == {"token": REDACTION_MARKER, "note": ORDINARY_MARKER}

    def test_the_correlation_identifier_is_never_masked(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        """SEC-004: a masked correlation identifier would make diagnosis impossible."""
        with correlation_context(GIVEN_ID):
            logger.info("job.claimed")
        assert one_line(stream)["correlation_id"] == GIVEN_ID

    def test_protected_detail_does_not_render_into_a_line(
        self, logger: StructuredLogger, stream: io.StringIO
    ) -> None:
        error = PlatformPermanentError("injected permanent failure", {"note": ORDINARY_MARKER})
        logger.error("job.failed", error_class=error.error_class.value, detail=error.detail)
        text = stream.getvalue()
        assert ORDINARY_MARKER not in text
        assert ErrorClass.PLATFORM_PERMANENT.value in text

    @pytest.mark.parametrize("level", sorted(LEVELS))
    def test_every_level_writes_its_own_name(self, stream: io.StringIO, level: str) -> None:
        logger = StructuredLogger(stream=stream, level="DEBUG")
        logger.log(level, "platform.event")
        assert one_line(stream)["level"] == level

    def test_a_level_below_the_threshold_writes_nothing(self, stream: io.StringIO) -> None:
        logger = StructuredLogger(stream=stream, level="WARNING")
        logger.info("job.claimed")
        logger.debug("job.claimed")
        assert stream.getvalue() == ""
        logger.warning("lease.expired")
        assert len(lines_of(stream)) == 1

    def test_the_threshold_is_reported(self, stream: io.StringIO) -> None:
        logger = StructuredLogger(stream=stream, level="warning")
        assert logger.level == "WARNING"
        assert not logger.is_enabled_for("INFO")
        assert logger.is_enabled_for("ERROR")

    def test_an_unknown_level_is_a_configuration_failure(self, stream: io.StringIO) -> None:
        with pytest.raises(ConfigurationInvalidError) as raised:
            StructuredLogger(stream=stream, level="LOUD")
        assert raised.value.error_class is ErrorClass.CONFIGURATION_INVALID
        assert not raised.value.retryable

    def test_a_reserved_field_cannot_be_overwritten(self, logger: StructuredLogger) -> None:
        with pytest.raises(ValueError, match="reserved log fields"):
            logger.log("INFO", "job.claimed", ts="not a timestamp")

    def test_a_file_target_is_written_as_jsonl(self, tmp_path: Path) -> None:
        path = tmp_path / "evidence" / "platform.jsonl"
        with StructuredLogger.to_path(path, clock=fixed_clock) as logger:
            logger.info("platform.started", api_host="127.0.0.1")
        written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert written[0]["event"] == "platform.started"
        assert written[0]["api_host"] == "127.0.0.1"

    def test_a_file_target_appends_rather_than_truncates(self, tmp_path: Path) -> None:
        path = tmp_path / "platform.jsonl"
        for event in ("platform.started", "platform.stopped"):
            with StructuredLogger.to_path(path) as logger:
                logger.info(event)
        assert len(path.read_text(encoding="utf-8").splitlines()) == 2

    def test_a_dot_log_target_is_refused(self, tmp_path: Path) -> None:
        """.gitignore excludes *.log, and SEC-004 needs this file at the gate."""
        with pytest.raises(ConfigurationInvalidError, match=r"\.jsonl"):
            StructuredLogger.to_path(tmp_path / "platform.log")
        assert not (tmp_path / "platform.log").exists()

    def test_closing_leaves_a_stream_it_did_not_open(self, stream: io.StringIO) -> None:
        logger = StructuredLogger(stream=stream)
        logger.close()
        assert not stream.closed


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


@pytest.fixture
def metrics() -> MetricsRegistry:
    return MetricsRegistry()


class TestMetrics:
    def test_a_fresh_registry_reads_as_zero(self, metrics: MetricsRegistry) -> None:
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
        self, metrics: MetricsRegistry, state: str
    ) -> None:
        metrics.record_transition(state)
        metrics.record_transition(state)
        reading = metrics.read()
        assert reading.transitions[state] == 2
        assert sum(reading.transitions.values()) == 2

    @pytest.mark.parametrize("label", ["", "pending", "CLAIMED", "job-42", "handler=succeed"])
    def test_a_label_outside_the_state_set_is_refused(
        self, metrics: MetricsRegistry, label: str
    ) -> None:
        """SEC-004: no metric label may carry a payload-derived value."""
        with pytest.raises(ValueError, match="unknown target state"):
            metrics.record_transition(label)

    def test_the_remaining_counters_are_independent(self, metrics: MetricsRegistry) -> None:
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

    def test_durations_aggregate(self, metrics: MetricsRegistry) -> None:
        for milliseconds in (5.0, 15.0, 10.0):
            metrics.record_attempt_duration_ms(milliseconds)
        duration = metrics.read().attempt_duration
        assert duration.count == 3
        assert duration.total_ms == pytest.approx(30.0)
        assert duration.min_ms == pytest.approx(5.0)
        assert duration.max_ms == pytest.approx(15.0)
        assert duration.mean_ms == pytest.approx(10.0)

    def test_lease_recovery_latency_is_a_separate_series(self, metrics: MetricsRegistry) -> None:
        metrics.record_attempt_duration_ms(4.0)
        metrics.record_lease_recovery_latency_ms(400.0)
        reading = metrics.read()
        assert reading.attempt_duration.count == 1
        assert reading.lease_recovery_latency.count == 1
        assert reading.lease_recovery_latency.max_ms == pytest.approx(400.0)

    def test_a_negative_duration_is_refused(self, metrics: MetricsRegistry) -> None:
        with pytest.raises(ValueError, match="negative"):
            metrics.record_attempt_duration_ms(-1.0)

    def test_measuring_a_block_records_an_attempt_duration(
        self, metrics: MetricsRegistry
    ) -> None:
        with metrics.measure_attempt():
            pass
        duration = metrics.read().attempt_duration
        assert duration.count == 1
        assert duration.total_ms >= 0.0

    def test_a_failing_block_is_still_measured(self, metrics: MetricsRegistry) -> None:
        with pytest.raises(RuntimeError), metrics.measure_attempt():
            raise RuntimeError("handler failed")
        assert metrics.read().attempt_duration.count == 1

    def test_a_reading_does_not_change_afterwards(self, metrics: MetricsRegistry) -> None:
        metrics.record_transition("SUCCEEDED")
        reading = metrics.read()
        metrics.record_transition("SUCCEEDED")
        assert reading.transitions["SUCCEEDED"] == 1
        assert metrics.read().transitions["SUCCEEDED"] == 2

    def test_a_reading_serializes_to_plain_values(self, metrics: MetricsRegistry) -> None:
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

    def test_reset_returns_every_metric_to_zero(self, metrics: MetricsRegistry) -> None:
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
