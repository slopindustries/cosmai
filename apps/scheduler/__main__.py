"""The scheduler process entrypoint: ``python -m scheduler`` (M6 batch 6a).

Copy-adapted **in spirit** from ``apps/platform_core/worker.py`` — same
lifecycle shape (configuration resolved first and a refusal is fatal,
cooperative shutdown that never interrupts an in-flight pass, a per-process
identity, a JSON report written to standard output on clean exit, and a
database failure classified before it decides anything) — because polling a
table for due work and claiming a job from one are the same kind of process
even though what each does with a connection differs. Mirrored rather than
imported: ``Worker`` is not a reusable base class (nothing in this tree makes
it one), and this is a sibling process entrypoint outside ``platform_core``
entirely, for the same reason ``domain.api`` mirrors rather than imports
``addon_host.registration``'s handler-prefix constant — this module's own
``no import of addon_host`` instruction extends the same reasoning to
importing ``platform_core.worker`` itself as though it were a library.

**What one pass does.** ``SchedulerStore.due_source_ids`` names every
candidate: a ``schedule`` row that is ``enabled``, whose source is also
``enabled``, and whose ``next_run_at`` is due. For each candidate, in one
transaction: ``lock_schedule`` locks the row and re-applies the same predicate
(a concurrent writer may have changed it since the scan — see
``apps/scheduler/store.py``'s docstring); a row that no longer matches comes
back ``None`` and this pass moves on. Otherwise: skip if a ``PENDING`` or
``RUNNING`` job already carries this exact handler and ``source_id`` — the
duplicate suppression the M6 brief names — or create the collect job and
advance ``next_run_at``/``last_run_at`` together with it, so a job and its
schedule's next due time are never observed out of step with each other.

**The handler name.** ``addon:<addon_id>``, derived from the locked source row
— the same convention ``domain.api``'s ``HANDLER_PREFIX``/``SOURCE_ID_FIELD``
already use for the normalize job it creates, mirrored here (not imported; see
above) for the same reason ``domain.api`` itself gives for mirroring
``addon_host.registration``'s copy: *"M3 must keep this string in sync with
its own"* — this module is now a third place that string has to keep meaning
the same thing. M3's ``addon_host`` is what will eventually claim a job with
this handler; until it lands, a job this process creates is real (listed,
read, retried through the ordinary job surface) but stays ``PENDING`` — the
same gap ``domain.api``'s own docstring already records for
``POST /snapshots/{id}/normalize``.

**What duplicate suppression does and does not answer.** DP-033's own
"Remaining uncertainty" section (D5) notes that a scheduled run against a
source whose previous run already succeeded is close to, but not the same as,
OQ-008's re-execution question. This module suppresses a *second concurrent*
job for one source — the case CONTRACT-JOB@0.1's own ``effect_key`` idempotency
does not already resolve, because two distinct jobs are two distinct effect
keys. It does not refuse to schedule a source whose most recent collection
already succeeded; that is OQ-008's question and stays open, exactly as D5
records.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from threading import current_thread, main_thread
from types import FrameType
from typing import Any, Final, TextIO

import psycopg

from platform_core.config import PlatformConfig, load_config
from platform_core.db.connection import classify, connect, describe
from platform_core.errors import ErrorClass, PlatformError
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from scheduler.store import SchedulerStore

EXIT_OK: Final = 0

#: The platform could not run, but the configuration was not what was wrong —
#: the same split ``platform_core.worker``/``platform_core.api`` make.
EXIT_UNAVAILABLE: Final = 1

#: ``EX_CONFIG`` from ``sysexits.h``, the status every other P1 entrypoint uses
#: for the same condition.
EXIT_CONFIGURATION_INVALID: Final = 78

STOP_SIGNALS: Final[tuple[signal.Signals, ...]] = (signal.SIGTERM, signal.SIGINT)

#: How often the stop flag is consulted while the loop waits between passes.
SIGNAL_CHECK_SECONDS: Final = 0.05

#: The single object written to standard output at shutdown.
REPORT_EVENT: Final = "scheduler.report"

#: The identity a scheduler's own connection always opens under. It never does
#: DDL, so ``runtime`` is the only role its connection — and therefore its
#: failure classification — ever names, matching ``platform_core.worker``.
_ROLE: Final = "runtime"

#: Mirrored from ``domain.api.HANDLER_PREFIX``/``domain.api.SOURCE_ID_FIELD`` —
#: see this module's own docstring for why this is a mirror and not an import.
#: Must stay in sync with ``domain.api``'s copy.
HANDLER_PREFIX: Final = "addon:"
SOURCE_ID_FIELD: Final = "source_id"

#: A scheduled collect job's attempt budget. The same three every other P0/P1
#: job uses (``domain.api.MAX_ATTEMPTS``, P0's own collect job): a transient
#: network failure is the case the budget exists for.
MAX_ATTEMPTS: Final = 3


@dataclass(frozen=True)
class SchedulerOptions:
    """Everything the command line can say. Configuration lives in the
    environment — the same split ``platform_core.worker.WorkerOptions`` makes."""

    once: bool = False
    max_jobs: int | None = None
    max_seconds: float | None = None
    scheduler_id: str | None = None


def default_scheduler_id() -> str:
    """An identity no second process on this host can pick by accident."""
    return f"{socket.gethostname()}-{os.getpid()}"


def parse_arguments(argv: Sequence[str] | None = None) -> SchedulerOptions:
    """Read the command line into ``SchedulerOptions``."""
    parser = argparse.ArgumentParser(
        prog="python -m scheduler",
        description=(
            "Poll cosmai.schedule and create a collect job for every due, "
            "enabled source, until asked to stop."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="attempt exactly one pass over the due sources and exit",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        metavar="N",
        help="exit after N collect jobs have been created",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        metavar="S",
        help="exit after S seconds, checked between passes and never inside one",
    )
    parser.add_argument(
        "--scheduler-id",
        metavar="ID",
        help="override the generated scheduler identity; it must be unique per process",
    )
    parsed = parser.parse_args(argv)
    return SchedulerOptions(
        once=bool(parsed.once),
        max_jobs=parsed.max_jobs,
        max_seconds=parsed.max_seconds,
        scheduler_id=parsed.scheduler_id,
    )


def parse_report(text: str) -> dict[str, Any]:
    """Read the shutdown report out of a scheduler's captured standard output.

    Defined here, not in a test, for the reason ``platform_core.worker.
    parse_report`` gives for its own copy: the report is this module's
    interface to whoever started the process, and a parser on the other side
    of that boundary would be a second, undeclared copy of it.
    """
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            candidate = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("event") == REPORT_EVENT:
            return candidate
    raise ValueError(f"no {REPORT_EVENT} object was written to standard output")


class Scheduler:
    """One process worth of the polling loop."""

    def __init__(
        self,
        config: PlatformConfig,
        options: SchedulerOptions,
        logger: StructuredLogger,
        metrics: MetricsRegistry | None = None,
        report_stream: TextIO | None = None,
    ) -> None:
        self._config = config
        self._options = options
        self._logger = logger
        self._metrics = MetricsRegistry() if metrics is None else metrics
        self._report_stream: TextIO = sys.stdout if report_stream is None else report_stream
        self._scheduler_id = options.scheduler_id or default_scheduler_id()
        self._poll_seconds = config.poll_ms / 1000.0
        self._connection: psycopg.Connection[Any] | None = None
        self._processed = 0
        self._suppressed = 0
        self._stopping = False
        self._stop_signal: str | None = None

    @property
    def scheduler_id(self) -> str:
        return self._scheduler_id

    @property
    def processed(self) -> int:
        """How many collect jobs this process created. A suppressed duplicate
        does not count — the same "claims that found nothing do not count"
        convention ``platform_core.worker.Worker.processed`` states."""
        return self._processed

    # ------------------------------------------------------------------- loop

    def run(self) -> int:
        """Run until a limit, a signal, or a configuration failure. Returns the
        exit status."""
        restore = self._install_signal_handlers()
        started = time.monotonic()
        deadline = (
            None if self._options.max_seconds is None else started + self._options.max_seconds
        )
        exit_code = EXIT_OK
        reason = "the loop ended"
        try:
            self._open()
            self._log_started()
            while True:
                stopped = self._stop_reason(deadline)
                if stopped is not None:
                    reason = stopped
                    break
                created = self._one_pass()
                if self._options.once:
                    reason = "one pass was attempted"
                    break
                if not created:
                    self._wait(deadline)
        except PlatformError as failure:
            exit_code = (
                EXIT_CONFIGURATION_INVALID
                if failure.error_class is ErrorClass.CONFIGURATION_INVALID
                else EXIT_UNAVAILABLE
            )
            reason = "the platform refused to continue"
            self._logger.error(
                "scheduler.refused",
                scheduler_id=self._scheduler_id,
                error_class=failure.error_class.value,
                error_summary=failure.summary,
            )
        finally:
            self._close()
            for number, previous in restore:
                signal.signal(number, previous)
        self._log_stopped(reason, exit_code)
        self._write_report(reason, exit_code)
        return exit_code

    def _stop_reason(self, deadline: float | None) -> str | None:
        if self._stopping:
            return f"a stop was requested by {self._stop_signal}"
        if self._options.max_jobs is not None and self._processed >= self._options.max_jobs:
            return "the job limit was reached"
        if deadline is not None and time.monotonic() >= deadline:
            return "the time limit was reached"
        return None

    def _one_pass(self) -> bool:
        """Scan for due sources and act on each. Returns whether at least one
        collect job was created — the wait between passes is skipped when one
        was, the same "do not wait after doing something" shape
        ``platform_core.worker.Worker._one_pass`` gives its own loop."""
        assert self._connection is not None
        try:
            due = SchedulerStore(self._connection).due_source_ids()
        except psycopg.Error as error:
            self._recover_from(error)
            return False
        created_any = False
        for source_id in due:
            if self._options.max_jobs is not None and self._processed >= self._options.max_jobs:
                break
            try:
                created = self._process_source(source_id)
            except psycopg.Error as error:
                self._recover_from(error, source_id=source_id)
                return created_any
            if created:
                self._processed += 1
                created_any = True
        return created_any

    def _process_source(self, source_id: str) -> bool:
        """Lock, check, and (if due to) create one collect job — one
        transaction, so the lock, the duplicate check, and the advance
        `[가설]` should never be observed in three different states by a
        concurrent reader. Design intent, not a measured property: M-C5
        (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`) is explicit that every
        scheduler test to date is a sequential `--once` run, none against two
        processes racing the same source."""
        assert self._connection is not None
        store = SchedulerStore(self._connection)
        with self._connection.transaction():
            schedule = store.lock_schedule(source_id)
            if schedule is None:
                return False
            handler = f"{HANDLER_PREFIX}{schedule['addon_id']}"
            if store.non_terminal_job_exists(handler, SOURCE_ID_FIELD, source_id):
                self._suppressed += 1
                self._logger.info(
                    "scheduler.duplicate_suppressed",
                    scheduler_id=self._scheduler_id,
                    source_id=source_id,
                    handler=handler,
                )
                return False
            job_store = JobStore(
                self._connection, self._config, logger=self._logger, metrics=self._metrics
            )
            job_id = job_store.create_job(
                handler, {SOURCE_ID_FIELD: source_id}, max_attempts=MAX_ATTEMPTS
            )
            store.advance(source_id)
        self._logger.info(
            "scheduler.job_created",
            scheduler_id=self._scheduler_id,
            source_id=source_id,
            handler=handler,
            job_id=str(job_id),
        )
        return True

    def _recover_from(self, error: psycopg.Error, source_id: str | None = None) -> None:
        """Classify a driver failure and either reopen (transient) or raise
        (everything else) — ``platform_core.worker.Worker._one_pass``'s own
        response to the same condition."""
        failure = classify(error, describe(self._config, _ROLE))
        if not failure.retryable:
            raise failure from error
        self._logger.warning(
            "scheduler.pass_failed",
            scheduler_id=self._scheduler_id,
            source_id=source_id,
            error_class=failure.error_class.value,
            error_summary=failure.summary,
        )
        self._reopen()

    def _wait(self, deadline: float | None) -> None:
        """Pause before scanning again, giving up early on a stop."""
        limit = time.monotonic() + self._poll_seconds
        if deadline is not None:
            limit = min(limit, deadline)
        while not self._stopping:
            remaining = limit - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(SIGNAL_CHECK_SECONDS, remaining))

    # ------------------------------------------------------------ connection

    def _open(self) -> None:
        """Open the connection. Autocommit, like every other short-lived P1
        connection in this tree — `_process_source` opens its own explicit
        transaction around the one pass that needs one, the same
        ``connect(autocommit=True)`` + ``with handle.transaction():`` pattern
        ``domain.api``'s own ``seal_snapshot`` route already uses."""
        self._connection = connect(self._config, role=_ROLE, autocommit=True)

    def _reopen(self) -> None:
        self._close()
        self._open()

    def _close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
        self._connection = None

    # --------------------------------------------------------------- signals

    def _install_signal_handlers(self) -> list[tuple[signal.Signals, Any]]:
        if current_thread() is not main_thread():
            return []
        restore: list[tuple[signal.Signals, Any]] = []
        for number in STOP_SIGNALS:
            restore.append((number, signal.getsignal(number)))
            signal.signal(number, self._request_stop)
        return restore

    def _request_stop(self, number: int, frame: FrameType | None) -> None:
        self._stopping = True
        self._stop_signal = signal.Signals(number).name

    # ---------------------------------------------------------- observability

    def _log_started(self) -> None:
        self._logger.info(
            "scheduler.started",
            scheduler_id=self._scheduler_id,
            pid=os.getpid(),
            poll_ms=self._config.poll_ms,
            once=self._options.once,
            max_jobs=self._options.max_jobs,
            max_seconds=self._options.max_seconds,
        )

    def _log_stopped(self, reason: str, exit_code: int) -> None:
        self._logger.info(
            "scheduler.stopped",
            scheduler_id=self._scheduler_id,
            pid=os.getpid(),
            jobs_created=self._processed,
            duplicates_suppressed=self._suppressed,
            stop_reason=reason,
            exit_code=exit_code,
        )

    def _write_report(self, reason: str, exit_code: int) -> None:
        report = {
            "event": REPORT_EVENT,
            "scheduler_id": self._scheduler_id,
            "pid": os.getpid(),
            "jobs_created": self._processed,
            "duplicates_suppressed": self._suppressed,
            "stop_reason": reason,
            "exit_code": exit_code,
            "metrics": self._metrics.read().as_dict(),
        }
        self._report_stream.write(json.dumps(report, ensure_ascii=False) + "\n")
        self._report_stream.flush()


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve configuration, then run one scheduler. Returns the process exit status."""
    options = parse_arguments(argv)
    try:
        config = load_config()
    except PlatformError as invalid:
        StructuredLogger().error(
            "scheduler.configuration_invalid",
            error_class=invalid.error_class.value,
            error_summary=invalid.summary,
        )
        return EXIT_CONFIGURATION_INVALID
    logger = StructuredLogger.resolved(config.log_file, config.log_level)
    try:
        for warning in config.warnings():
            logger.warning("scheduler.configuration_warning", detail=warning)
        return Scheduler(config, options, logger).run()
    finally:
        logger.close()


if __name__ == "__main__":  # pragma: no cover - exercised as a process, not imported
    sys.exit(main())
