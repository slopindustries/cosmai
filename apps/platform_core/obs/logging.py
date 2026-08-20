"""JSON Lines structured logging for the P1 platform core.

One line is one JSON object, with ``ts``, ``level``, ``event``,
``correlation_id``, and the event's own fields. The format is chosen for the
gate: SEC-004 has to search the log for marker values, and a grep over a line
oriented file that is also machine-parseable is the cheapest way to make that
review honest.

Three things are deliberate.

* **Every field is redacted before it is written.** The logger does not trust its
  callers, because a payload the platform never interprets is exactly the kind of
  value that ends up interpolated into an event by accident.
* **The correlation identifier is picked up ambiently.** Invariant I5 says
  correlation is total; a logger that required it as an argument would make I5
  depend on nobody ever forgetting.
* **A log file must be named ``.jsonl``.** ``.gitignore`` excludes ``*.log``, and
  SEC-004 requires the log to be reviewable evidence at the gate. A file the
  evidence directory silently drops is worse than no file, so the wrong suffix is
  a configuration failure rather than a surprise at review time.

No third-party logging dependency is used. The standard library would work too;
writing the line directly is fewer moving parts than a handler, a formatter, and
a filter whose combined behavior would itself need a test.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from types import TracebackType
from typing import Any, Final, TextIO

from platform_core.errors import ConfigurationInvalidError
from platform_core.obs.correlation import CORRELATION_FIELD, current_correlation_id
from platform_core.obs.redaction import redact_mapping

#: Level names and their severity, matching the standard library's numbering.
LEVELS: Final[Mapping[str, int]] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

DEFAULT_LEVEL: Final = "INFO"

#: Structural fields an event's own payload may not overwrite.
RESERVED_FIELDS: Final[frozenset[str]] = frozenset({"ts", "level", "event"})

LOG_SUFFIX: Final = ".jsonl"


def require_known_level(level: str) -> str:
    """Return ``level`` casefolded to its canonical name, or refuse it outright."""
    candidate = level.strip().upper()
    if candidate not in LEVELS:
        raise ConfigurationInvalidError(
            f"unknown log level {level!r}; permitted levels are {', '.join(LEVELS)}"
        )
    return candidate


class StructuredLogger:
    """A JSON Lines writer. Thread-safe; one instance per process is expected."""

    def __init__(
        self,
        stream: TextIO | None = None,
        level: str = DEFAULT_LEVEL,
        clock: Callable[[], datetime] | None = None,
        owns_stream: bool = False,
    ) -> None:
        self._stream: TextIO = sys.stderr if stream is None else stream
        self._level = require_known_level(level)
        self._threshold = LEVELS[self._level]
        self._clock: Callable[[], datetime] = clock if clock is not None else _utc_now
        self._owns_stream = owns_stream
        self._lock = Lock()

    @classmethod
    def to_path(
        cls,
        path: Path,
        level: str = DEFAULT_LEVEL,
        clock: Callable[[], datetime] | None = None,
    ) -> StructuredLogger:
        """Append to a ``.jsonl`` file, creating its directory if needed."""
        if path.suffix != LOG_SUFFIX:
            raise ConfigurationInvalidError(
                f"a structured log path must end in {LOG_SUFFIX}, not {path.suffix!r}: "
                "the repository ignores *.log, and gate evidence has to stay reviewable"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("a", encoding="utf-8")
        return cls(stream=stream, level=level, clock=clock, owns_stream=True)

    @classmethod
    def resolved(cls, path: Path | None, level: str = DEFAULT_LEVEL) -> StructuredLogger:
        """The logger an entrypoint runs with: the configured file, or standard error.

        Both process entrypoints make the same choice, and OPS-003 depends on their
        making it identically — its whole claim is that one identifier reaches the
        events of several processes, which is only true if the processes write to
        the same place. The choice therefore lives here rather than twice in the two
        ``__main__`` modules. ``PlatformConfig`` is deliberately not the argument:
        ``config`` imports this module, so taking the path keeps that one-way.
        """
        return cls(level=level) if path is None else cls.to_path(path, level=level)

    @property
    def level(self) -> str:
        return self._level

    def is_enabled_for(self, level: str) -> bool:
        return LEVELS[require_known_level(level)] >= self._threshold

    def log(self, level: str, event: str, **fields: Any) -> None:
        """Write one event. Unknown levels and reserved field names are errors."""
        canonical = require_known_level(level)
        if LEVELS[canonical] < self._threshold:
            return
        collisions = RESERVED_FIELDS.intersection(fields)
        if collisions:
            raise ValueError(
                f"event {event!r} would overwrite reserved log fields: "
                f"{', '.join(sorted(collisions))}"
            )
        stated = fields.pop(CORRELATION_FIELD, None)
        record: dict[str, Any] = {
            "ts": self._clock().isoformat(),
            "level": canonical,
            "event": event,
            CORRELATION_FIELD: stated if stated else current_correlation_id(),
        }
        record.update(redact_mapping(fields))
        self._write(record)

    def debug(self, event: str, **fields: Any) -> None:
        self.log("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self.log("INFO", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self.log("WARNING", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.log("ERROR", event, **fields)

    def critical(self, event: str, **fields: Any) -> None:
        self.log("CRITICAL", event, **fields)

    def close(self) -> None:
        """Close the stream, but only one this logger opened itself."""
        if self._owns_stream and not self._stream.closed:
            self._stream.close()

    def __enter__(self) -> StructuredLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _write(self, record: Mapping[str, Any]) -> None:
        # ``default=str`` keeps an unexpected object from turning one bad field
        # into a lost line. ProtectedDetail renders as its withheld marker here.
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()


def _utc_now() -> datetime:
    return datetime.now(UTC)
