"""The JSON Lines log: one line, one object, always redacted, always correlated.

SEC-004 reads this file as gate evidence, so the properties under test are the
ones that make that reading trustworthy — the line parses, the marker under a
sensitive key is gone, the marker under an ordinary key is still there, and the
correlation identifier is intact.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from platform_core.errors import ConfigurationInvalidError, ErrorClass, PlatformPermanentError
from platform_core.obs.correlation import correlation_context
from platform_core.obs.logging import LEVELS, StructuredLogger
from platform_core.obs.redaction import REDACTION_MARKER

SENSITIVE_MARKER = "marker-must-not-leak-42"
ORDINARY_MARKER = "marker-must-survive-42"
GIVEN_ID = "correlation-under-test"
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


def test_one_event_is_one_json_object(logger: StructuredLogger, stream: io.StringIO) -> None:
    logger.info("job.claimed", job_id="j-1")
    logger.info("job.finished", job_id="j-1")
    written = lines_of(stream)
    assert len(written) == 2
    assert [line["event"] for line in written] == ["job.claimed", "job.finished"]


def test_a_multiline_value_stays_on_one_line(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    logger.info("job.failed", note="first\nsecond")
    assert len(stream.getvalue().splitlines()) == 1
    assert one_line(stream)["note"] == "first\nsecond"


def test_the_structural_fields_are_present(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    with correlation_context(GIVEN_ID):
        logger.info("job.state_changed", job_id="j-1", from_state="PENDING", to_state="RUNNING")
    line = one_line(stream)
    assert line["ts"] == "2026-08-17T09:30:00+00:00"
    assert line["level"] == "INFO"
    assert line["event"] == "job.state_changed"
    assert line["correlation_id"] == GIVEN_ID
    assert line["from_state"] == "PENDING"


def test_the_timestamp_carries_an_offset(stream: io.StringIO) -> None:
    logger = StructuredLogger(stream=stream)
    logger.info("platform.started")
    parsed = datetime.fromisoformat(one_line(stream)["ts"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None


def test_the_correlation_identifier_is_picked_up_ambiently(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    """Invariant I5 must not depend on every call site remembering."""
    with correlation_context(GIVEN_ID):
        logger.info("job.claimed")
    assert one_line(stream)["correlation_id"] == GIVEN_ID


def test_an_explicit_identifier_wins_over_the_scope(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    with correlation_context(GIVEN_ID):
        logger.info("job.claimed", correlation_id="explicit-id")
    assert one_line(stream)["correlation_id"] == "explicit-id"


def test_a_line_outside_a_scope_still_has_the_field(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    logger.info("platform.started")
    assert one_line(stream)["correlation_id"] is None


def test_sensitive_fields_are_masked_and_ordinary_ones_survive(
    logger: StructuredLogger, stream: io.StringIO
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
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    """SEC-004: a masked correlation identifier would make diagnosis impossible."""
    with correlation_context(GIVEN_ID):
        logger.info("job.claimed")
    assert one_line(stream)["correlation_id"] == GIVEN_ID


def test_protected_detail_does_not_render_into_a_line(
    logger: StructuredLogger, stream: io.StringIO
) -> None:
    error = PlatformPermanentError("injected permanent failure", {"note": ORDINARY_MARKER})
    logger.error("job.failed", error_class=error.error_class.value, detail=error.detail)
    text = stream.getvalue()
    assert ORDINARY_MARKER not in text
    assert ErrorClass.PLATFORM_PERMANENT.value in text


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_every_level_writes_its_own_name(stream: io.StringIO, level: str) -> None:
    logger = StructuredLogger(stream=stream, level="DEBUG")
    logger.log(level, "platform.event")
    assert one_line(stream)["level"] == level


def test_a_level_below_the_threshold_writes_nothing(stream: io.StringIO) -> None:
    logger = StructuredLogger(stream=stream, level="WARNING")
    logger.info("job.claimed")
    logger.debug("job.claimed")
    assert stream.getvalue() == ""
    logger.warning("lease.expired")
    assert len(lines_of(stream)) == 1


def test_the_threshold_is_reported(stream: io.StringIO) -> None:
    logger = StructuredLogger(stream=stream, level="warning")
    assert logger.level == "WARNING"
    assert not logger.is_enabled_for("INFO")
    assert logger.is_enabled_for("ERROR")


def test_an_unknown_level_is_a_configuration_failure(stream: io.StringIO) -> None:
    with pytest.raises(ConfigurationInvalidError) as raised:
        StructuredLogger(stream=stream, level="LOUD")
    assert raised.value.error_class is ErrorClass.CONFIGURATION_INVALID
    assert not raised.value.retryable


def test_a_reserved_field_cannot_be_overwritten(logger: StructuredLogger) -> None:
    with pytest.raises(ValueError, match="reserved log fields"):
        logger.log("INFO", "job.claimed", ts="not a timestamp")


def test_a_file_target_is_written_as_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "evidence" / "platform.jsonl"
    with StructuredLogger.to_path(path, clock=fixed_clock) as logger:
        logger.info("platform.started", api_host="127.0.0.1")
    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert written[0]["event"] == "platform.started"
    assert written[0]["api_host"] == "127.0.0.1"


def test_a_file_target_appends_rather_than_truncates(tmp_path: Path) -> None:
    path = tmp_path / "platform.jsonl"
    for event in ("platform.started", "platform.stopped"):
        with StructuredLogger.to_path(path) as logger:
            logger.info(event)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_a_dot_log_target_is_refused(tmp_path: Path) -> None:
    """.gitignore excludes *.log, and SEC-004 needs this file at the gate."""
    with pytest.raises(ConfigurationInvalidError, match=r"\.jsonl"):
        StructuredLogger.to_path(tmp_path / "platform.log")
    assert not (tmp_path / "platform.log").exists()


def test_closing_leaves_a_stream_it_did_not_open(stream: io.StringIO) -> None:
    logger = StructuredLogger(stream=stream)
    logger.close()
    assert not stream.closed
