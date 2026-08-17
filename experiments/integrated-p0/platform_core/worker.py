"""The worker process entrypoint: ``python -m platform_core.worker`` (DP-006 D1).

``jobs.runner`` owns one pass — claim, execute, record. This module owns
everything around it that only exists once there is a process: configuration,
the connection, the loop, the signals that stop it, and the report it leaves
behind. Keeping the two apart is what lets a test observe one execution without
starting a process, and lets this file be about lifecycle only.

Five decisions are worth reading before the code.

**Configuration is resolved before anything else, and a refusal is fatal.**
SEC-003 requires a process given invalid configuration to exit non-zero without
substituting a default and without reaching the database. ``load_config`` is
therefore the first thing ``main`` calls, and its failure returns an exit status
rather than continuing on a partial configuration.

**Shutdown is cooperative and never interrupts an attempt.** ``SIGTERM`` and
``SIGINT`` set a flag; the flag is consulted between passes and while the loop is
waiting on an empty queue, never inside one. A signal that abandoned a running
attempt would produce exactly the interruption JOB-005 injects deliberately, and
a worker that did that on every restart would make the lease-expiry evidence
meaningless. The cost is that a stop waits for the current attempt, bounded by
the handler rather than by this module.

**Identity is per process.** Several of these run at once from T3 onward, and two
workers sharing a ``worker_id`` would make the lease column unable to say which
process holds a job — the fencing rule reads it as an identity. The default is
host and process id; ``--worker-id`` overrides it for a test that wants to name a
particular process in an assertion.

**A metric reading is written to standard output at shutdown.** Metrics are in
memory, so a process that started another one cannot read its counters. The two
ways to carry them across that boundary are a structured log a reader parses back
and a report the process writes on the way out. This module does the second, on
standard output, which nothing else writes to: the structured log is the
contract's observability surface and inventing a metrics event inside it would
add a telemetry shape CONTRACT-JOB@0.1 does not describe, while one JSON object
on a stream reserved for it is unambiguous to parse. It is written only on a
clean exit, which is itself evidence — a process that was interrupted leaves no
report, and the database and the log are what remain of it.

**A database failure is classified before it decides anything.** The contract
classifies by SQLSTATE: connection, resource, and operator-intervention classes
are transient, and everything else is a statement about how the process was
configured. A transient failure reopens the connection and the loop continues; a
configuration failure ends the process, because no number of retries creates a
database that was never there.
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
from platform_core.handlers.synthetic import synthetic_registry
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry

EXIT_OK: Final = 0

#: Anything the platform classifies as ``PLATFORM_TRANSIENT`` at startup: the
#: process could not run, but the configuration was not what was wrong.
EXIT_UNAVAILABLE: Final = 1

#: ``EX_CONFIG`` from ``sysexits.h``, the status ``scripts/with-database.sh``
#: already uses for the same condition. SEC-003 only requires "non-zero"; using
#: one documented number makes a supervisor able to tell the two apart.
EXIT_CONFIGURATION_INVALID: Final = 78

#: The signals that ask for a clean stop.
STOP_SIGNALS: Final[tuple[signal.Signals, ...]] = (signal.SIGTERM, signal.SIGINT)

#: How often the stop flag is consulted while the loop is waiting. A signal does
#: not cut a ``sleep`` short, so the wait is taken in slices and this is the
#: worst-case delay between a signal arriving and the loop noticing it.
SIGNAL_CHECK_SECONDS: Final = 0.05

#: The single object written to standard output at shutdown.
REPORT_EVENT: Final = "worker.report"


@dataclass(frozen=True)
class WorkerOptions:
    """Everything the command line can say. Configuration lives in the environment.

    The three limits exist so a test can bound a process it started. None of them
    changes what one pass does; they only decide when the loop stops asking for
    another job.
    """

    once: bool = False
    max_jobs: int | None = None
    max_seconds: float | None = None
    worker_id: str | None = None


def default_worker_id() -> str:
    """An identity no second process on this host can pick by accident."""
    return f"{socket.gethostname()}-{os.getpid()}"


def parse_arguments(argv: Sequence[str] | None = None) -> WorkerOptions:
    """Read the command line into ``WorkerOptions``."""
    parser = argparse.ArgumentParser(
        prog="python -m platform_core.worker",
        description=(
            "Run the P0-A platform worker: claim jobs, execute their handlers, "
            "and record the outcomes until asked to stop."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="attempt exactly one claim and exit, whether or not a job was found",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        metavar="N",
        help="exit after N jobs have been executed",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        metavar="S",
        help="exit after S seconds, checked between passes and never inside one",
    )
    parser.add_argument(
        "--worker-id",
        metavar="ID",
        help="override the generated worker identity; it must be unique per process",
    )
    parsed = parser.parse_args(argv)
    return WorkerOptions(
        once=bool(parsed.once),
        max_jobs=parsed.max_jobs,
        max_seconds=parsed.max_seconds,
        worker_id=parsed.worker_id,
    )


def parse_report(text: str) -> dict[str, Any]:
    """Read the shutdown report out of a worker's captured standard output.

    Defined here rather than in a test because the report is this module's
    interface to whoever started the process, and a parser written on the other
    side of that boundary would be a second, undeclared copy of it.
    """
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            candidate = json.loads(stripped)
        except json.JSONDecodeError:
            # A process that died mid-write leaves a partial line. It is not a
            # report, and the caller's problem is the missing report rather than
            # the shape of what was found instead.
            continue
        if isinstance(candidate, dict) and candidate.get("event") == REPORT_EVENT:
            return candidate
    raise ValueError(f"no {REPORT_EVENT} object was written to standard output")


class Worker:
    """One process worth of the execution loop.

    Holds the connection, the store, the runner, and the metric registry, so that
    a reconnection replaces the first three while the counters continue.
    """

    def __init__(
        self,
        config: PlatformConfig,
        options: WorkerOptions,
        logger: StructuredLogger,
        registry: HandlerRegistry | None = None,
        metrics: MetricsRegistry | None = None,
        report_stream: TextIO | None = None,
    ) -> None:
        self._config = config
        self._options = options
        self._logger = logger
        self._registry = synthetic_registry() if registry is None else registry
        self._metrics = MetricsRegistry() if metrics is None else metrics
        self._report_stream: TextIO = sys.stdout if report_stream is None else report_stream
        self._worker_id = options.worker_id or default_worker_id()
        self._poll_seconds = config.poll_ms / 1000.0
        self._connection: psycopg.Connection[Any] | None = None
        self._runner: JobRunner | None = None
        self._processed = 0
        self._stopping = False
        self._stop_signal: str | None = None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def metrics(self) -> MetricsRegistry:
        return self._metrics

    @property
    def processed(self) -> int:
        """How many jobs this process executed. Claims that found nothing do not count."""
        return self._processed

    # ------------------------------------------------------------------- loop

    def run(self) -> int:
        """Run until a limit, a signal, or a configuration failure. Returns the exit status."""
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
                executed = self._one_pass()
                if self._options.once:
                    reason = "one claim was attempted"
                    break
                if not executed:
                    self._wait(deadline)
        except PlatformError as failure:
            exit_code = (
                EXIT_CONFIGURATION_INVALID
                if failure.error_class is ErrorClass.CONFIGURATION_INVALID
                else EXIT_UNAVAILABLE
            )
            reason = "the platform refused to continue"
            self._logger.error(
                "worker.refused",
                worker_id=self._worker_id,
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
        """Why the loop should not ask for another job, or ``None`` to continue."""
        if self._stopping:
            return f"a stop was requested by {self._stop_signal}"
        if self._options.max_jobs is not None and self._processed >= self._options.max_jobs:
            return "the job limit was reached"
        if deadline is not None and time.monotonic() >= deadline:
            return "the time limit was reached"
        return None

    def _one_pass(self) -> bool:
        """One claim and, if something was claimable, one execution.

        Returns whether a job was executed. A driver failure is classified here
        rather than propagated: the loop's response to a transient condition is
        to reopen and carry on, and to anything else it is to stop, which is what
        the contract's SQLSTATE rule says.
        """
        assert self._runner is not None
        try:
            outcome = self._runner.run_once()
        except psycopg.Error as error:
            failure = classify(error, describe(self._config))
            if not failure.retryable:
                raise failure from error
            self._logger.warning(
                "worker.claim_failed",
                worker_id=self._worker_id,
                error_class=failure.error_class.value,
                error_summary=failure.summary,
            )
            self._reopen()
            return False
        if outcome is None:
            return False
        self._processed += 1
        return True

    def _wait(self, deadline: float | None) -> None:
        """Pause before asking an empty queue again, giving up early on a stop."""
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
        """Open the connection and build what depends on it.

        Autocommit, so every store statement is its own transaction. The claim,
        the fenced completion, and the effect insert are each meant to stand
        alone, and a worker holding one long transaction across them would make
        the boundaries this experiment exists to observe invisible.
        """
        self._connection = connect(self._config, autocommit=True)
        store = JobStore(
            self._connection, self._config, logger=self._logger, metrics=self._metrics
        )
        self._runner = JobRunner(
            store,
            self._registry,
            worker_id=self._worker_id,
            lease_seconds=float(self._config.lease_seconds),
        )

    def _reopen(self) -> None:
        self._close()
        self._open()

    def _close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
        self._connection = None
        self._runner = None

    # --------------------------------------------------------------- signals

    def _install_signal_handlers(self) -> list[tuple[signal.Signals, Any]]:
        """Take over the stop signals, returning what to put back afterwards.

        Restoring matters because ``Worker`` is also used in-process by a test,
        and a handler left installed would outlive the run that set it. Signal
        handlers can only be set from the main thread, so a worker running
        anywhere else keeps the process default and stops on its limits instead.
        """
        if current_thread() is not main_thread():
            return []
        restore: list[tuple[signal.Signals, Any]] = []
        for number in STOP_SIGNALS:
            restore.append((number, signal.getsignal(number)))
            signal.signal(number, self._request_stop)
        return restore

    def _request_stop(self, number: int, frame: FrameType | None) -> None:
        """Ask the loop to stop. Deliberately does nothing else.

        A handler runs between bytecodes, so anything it touched could be
        observed half-written by the attempt it interrupted. Setting a flag the
        loop reads at a point of its own choosing is the whole mechanism.
        """
        self._stopping = True
        self._stop_signal = signal.Signals(number).name

    # ---------------------------------------------------------- observability

    def _log_started(self) -> None:
        self._logger.info(
            "worker.started",
            worker_id=self._worker_id,
            pid=os.getpid(),
            handlers=list(self._registry.names()),
            lease_seconds=self._config.lease_seconds,
            poll_ms=self._config.poll_ms,
            once=self._options.once,
            max_jobs=self._options.max_jobs,
            max_seconds=self._options.max_seconds,
        )

    def _log_stopped(self, reason: str, exit_code: int) -> None:
        self._logger.info(
            "worker.stopped",
            worker_id=self._worker_id,
            pid=os.getpid(),
            jobs_executed=self._processed,
            stop_reason=reason,
            exit_code=exit_code,
        )

    def _write_report(self, reason: str, exit_code: int) -> None:
        """Leave the metric reading where the process that started this one can read it."""
        report = {
            "event": REPORT_EVENT,
            "worker_id": self._worker_id,
            "pid": os.getpid(),
            "jobs_executed": self._processed,
            "stop_reason": reason,
            "exit_code": exit_code,
            "metrics": self._metrics.read().as_dict(),
        }
        self._report_stream.write(json.dumps(report, ensure_ascii=False) + "\n")
        self._report_stream.flush()


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve configuration, then run one worker. Returns the process exit status."""
    options = parse_arguments(argv)
    try:
        config = load_config()
    except PlatformError as invalid:
        # No configuration means no log level and no database, so this is the one
        # event written by a logger the configuration did not choose.
        StructuredLogger().error(
            "worker.configuration_invalid",
            error_class=invalid.error_class.value,
            error_summary=invalid.summary,
        )
        return EXIT_CONFIGURATION_INVALID
    logger = StructuredLogger(level=config.log_level)
    for warning in config.warnings():
        logger.warning("worker.configuration_warning", detail=warning)
    return Worker(config, options, logger).run()


if __name__ == "__main__":  # pragma: no cover - exercised as a process, not imported
    sys.exit(main())
