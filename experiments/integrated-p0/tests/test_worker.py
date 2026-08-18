"""The worker process: its limits, its shutdown, and what it leaves behind.

``jobs/`` is tested through ``JobRunner`` in one process, and that is where the
contract's state machine is proved. What cannot be proved that way is everything
this file is about — a process that starts, holds a connection, keeps asking for
work, and stops when told. JOB-005 and the `JOB-006`–`JOB-008` family then rest
on this behaving the way it says it does, so the lifecycle is established here
before a scenario depends on it.

Every test starts a real process with ``python -m platform_core.worker``. Nothing
is imported from the worker and driven in-process, because a signal handler, an
exit status, and a stream a parent reads are the three things an in-process test
would have had to simulate, and they are exactly what is under test.

The database is ``shared_database``: the processes started here connect to the
one the test can read. That is the same fixture the concurrency scenarios use,
for the same reason, and it is not an isolation mechanism.
"""

from __future__ import annotations

import json
import signal
import subprocess
import time
from typing import Any
from uuid import UUID

import psycopg
import pytest
from platform_core.config import PlatformConfig
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.worker import (
    EXIT_CONFIGURATION_INVALID,
    EXIT_OK,
    REPORT_EVENT,
    WorkerOptions,
    parse_arguments,
    parse_report,
)

from tests.conftest import (
    attempts_of,
    effects_of,
    log_events,
    run_worker,
    start_worker,
    wait_for_worker,
    wait_until,
    worker_command,
    worker_environment,
)

#: A poll short enough that a waiting worker is asked again within one test step.
FAST_POLL_MS = "20"

#: How long the handler in the shutdown test stays inside its attempt. Long
#: enough that a signal certainly arrives while it is running, and far shorter
#: than the lease it holds.
BUSY_SECONDS = 1.5


def state_of(store: JobStore, job_id: UUID) -> str:
    job = store.read_job(job_id)
    assert job is not None
    return str(job["state"])


# --------------------------------------------------------------------------- #
# Executing work
# --------------------------------------------------------------------------- #


def test_a_worker_asked_for_one_claim_executes_one_job_and_exits(
    shared_store: JobStore,
    shared_database: PlatformConfig,
    shared_connection: psycopg.Connection[Any],
) -> None:
    """The whole loop, once: claim, execute, record, report, exit."""
    job_id = shared_store.create_job("succeed", {"opaque": "value"}, max_attempts=3)

    finished = run_worker(shared_database, "--once", COSMA_POLL_MS=FAST_POLL_MS)

    assert finished.returncode == EXIT_OK, finished.stderr
    assert state_of(shared_store, job_id) == JobState.SUCCEEDED
    assert len(effects_of(shared_connection, job_id)) == 1
    attempt = attempts_of(shared_connection, job_id)[0]
    assert attempt["outcome"] == AttemptOutcome.SUCCEEDED
    # The attempt names the process that ran it, and the report names the same one.
    report = parse_report(finished.stdout)
    assert attempt["worker_id"] == report["worker_id"]
    assert report["jobs_executed"] == 1
    assert report["metrics"]["transitions"][JobState.SUCCEEDED] == 1


def test_a_worker_asked_for_one_claim_on_an_empty_queue_exits_without_waiting(
    shared_database: PlatformConfig,
) -> None:
    """`--once` is one claim attempt, not one job: an empty queue ends it too."""
    finished = run_worker(shared_database, "--once")

    assert finished.returncode == EXIT_OK, finished.stderr
    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 0
    assert report["metrics"]["claim_conflicts"] == 0


def test_a_worker_stops_after_the_number_of_jobs_it_was_given(
    shared_store: JobStore, shared_database: PlatformConfig
) -> None:
    """The job limit stops the loop between passes, leaving the rest claimable."""
    job_ids = [shared_store.create_job("succeed", {"n": n}, max_attempts=3) for n in range(3)]

    finished = run_worker(shared_database, "--max-jobs", "2", COSMA_POLL_MS=FAST_POLL_MS)

    assert finished.returncode == EXIT_OK, finished.stderr
    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 2
    assert "job limit" in report["stop_reason"]
    states = [state_of(shared_store, job_id) for job_id in job_ids]
    assert sorted(states) == [JobState.PENDING, JobState.SUCCEEDED, JobState.SUCCEEDED]


def test_a_worker_with_nothing_to_do_waits_and_then_honours_its_time_limit(
    shared_database: PlatformConfig,
) -> None:
    """An empty queue is not an error; the loop waits and asks again."""
    started = time.monotonic()

    finished = run_worker(
        shared_database, "--max-seconds", "0.4", COSMA_POLL_MS=FAST_POLL_MS
    )

    assert finished.returncode == EXIT_OK, finished.stderr
    assert time.monotonic() - started >= 0.4
    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 0
    assert "time limit" in report["stop_reason"]


# --------------------------------------------------------------------------- #
# Shutdown
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT], ids=["sigterm", "sigint"])
def test_a_stop_signal_lets_the_running_attempt_finish_first(
    shared_store: JobStore,
    shared_database: PlatformConfig,
    shared_connection: psycopg.Connection[Any],
    number: signal.Signals,
) -> None:
    """Safe shutdown, at the moment where it is not free.

    The signal arrives while a handler is inside its attempt. A worker that
    stopped there would leave the attempt open and the lease held — which is
    exactly the interruption JOB-005 injects deliberately — so what is asserted
    is the opposite: the attempt closes, the job reaches a terminal state, and
    only then does the process exit.
    """
    job_id = shared_store.create_job("stall", {"stall_seconds": BUSY_SECONDS}, max_attempts=3)
    worker = start_worker(shared_database, COSMA_POLL_MS=FAST_POLL_MS)
    try:
        wait_until(
            lambda: state_of(shared_store, job_id) == JobState.RUNNING, "the job is running"
        )
        worker.send_signal(number)
        finished = wait_for_worker(worker)
    finally:
        if worker.poll() is None:  # pragma: no cover - only on an assertion failure
            worker.kill()

    assert finished.returncode == EXIT_OK, finished.stderr
    assert state_of(shared_store, job_id) == JobState.SUCCEEDED
    attempt = attempts_of(shared_connection, job_id)[0]
    assert attempt["outcome"] == AttemptOutcome.SUCCEEDED
    assert attempt["finished_at"] is not None
    assert len(effects_of(shared_connection, job_id)) == 1
    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 1
    assert number.name in report["stop_reason"]


def test_a_stop_signal_ends_a_worker_that_is_waiting_on_an_empty_queue(
    shared_store: JobStore, shared_database: PlatformConfig
) -> None:
    """The wait is taken in slices, so a signal does not have to outlast a poll.

    One job is executed first so that the worker is known to be past its startup
    and inside the loop when the signal is sent; the queue is empty from then on.
    """
    job_id = shared_store.create_job("succeed", None, max_attempts=3)
    worker = start_worker(shared_database, COSMA_POLL_MS="500")
    try:
        wait_until(
            lambda: state_of(shared_store, job_id) == JobState.SUCCEEDED, "the job has succeeded"
        )
        worker.send_signal(signal.SIGTERM)
        finished = wait_for_worker(worker, timeout=5.0)
    finally:
        if worker.poll() is None:  # pragma: no cover - only on an assertion failure
            worker.kill()

    assert finished.returncode == EXIT_OK, finished.stderr
    report = parse_report(finished.stdout)
    assert report["jobs_executed"] == 1
    assert signal.SIGTERM.name in report["stop_reason"]


# --------------------------------------------------------------------------- #
# Identity, configuration, and the report
# --------------------------------------------------------------------------- #


def test_two_worker_processes_do_not_share_an_identity(
    shared_database: PlatformConfig,
) -> None:
    """The lease column is an identity, so two processes may never answer to one.

    This is a precondition of the fencing rule rather than a test of it: a
    reclaim can only refuse a stale worker's write if the two are distinguishable.
    """
    first = run_worker(shared_database, "--once")
    second = run_worker(shared_database, "--once")

    assert parse_report(first.stdout)["worker_id"] != parse_report(second.stdout)["worker_id"]
    assert parse_report(first.stdout)["pid"] != parse_report(second.stdout)["pid"]


def test_a_worker_identity_can_be_stated_for_a_test_that_needs_to_name_it(
    shared_store: JobStore,
    shared_database: PlatformConfig,
    shared_connection: psycopg.Connection[Any],
) -> None:
    job_id = shared_store.create_job("succeed", None, max_attempts=3)

    finished = run_worker(shared_database, "--once", "--worker-id", "named-worker")

    assert finished.returncode == EXIT_OK, finished.stderr
    assert attempts_of(shared_connection, job_id)[0]["worker_id"] == "named-worker"
    assert parse_report(finished.stdout)["worker_id"] == "named-worker"


def test_a_worker_given_invalid_configuration_refuses_to_start(
    shared_database: PlatformConfig,
) -> None:
    """The configuration failure path of a process entrypoint.

    SEC-003 is the scenario that executes the whole case table; what is claimed
    here is only that the worker entrypoint takes that path at all — it exits
    non-zero, says which setting was wrong, and leaves no report, because it
    never reached the loop that writes one.
    """
    environment = worker_environment(shared_database)
    del environment["COSMA_DB_NAME"]

    finished = subprocess.run(
        worker_command("--once"),
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert finished.returncode == EXIT_CONFIGURATION_INVALID
    refusals = [
        record
        for record in log_events(finished.stderr)
        if record["event"] == "worker.configuration_invalid"
    ]
    assert len(refusals) == 1
    assert refusals[0]["error_class"] == "CONFIGURATION_INVALID"
    assert "COSMA_DB_NAME" in refusals[0]["error_summary"]
    assert REPORT_EVENT not in finished.stdout


def test_the_report_is_the_only_thing_written_to_standard_output(
    shared_store: JobStore, shared_database: PlatformConfig
) -> None:
    """The stream is reserved for it, which is what makes it parseable at all.

    The structured log goes to standard error, so a reader of the report never
    has to separate the two.
    """
    shared_store.create_job("succeed", None, max_attempts=3)

    finished = run_worker(shared_database, "--once")

    lines = [line for line in finished.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == REPORT_EVENT
    assert log_events(finished.stderr), "the structured log belongs on standard error"


def test_the_worker_logs_its_start_and_its_stop(
    shared_database: PlatformConfig,
) -> None:
    finished = run_worker(shared_database, "--once", COSMA_POLL_MS=FAST_POLL_MS)

    events = log_events(finished.stderr)
    started = [record for record in events if record["event"] == "worker.started"]
    stopped = [record for record in events if record["event"] == "worker.stopped"]
    assert len(started) == len(stopped) == 1
    assert started[0]["poll_ms"] == int(FAST_POLL_MS)
    assert "halt_before_effect" in started[0]["handlers"]
    assert stopped[0]["exit_code"] == EXIT_OK
    assert stopped[0]["worker_id"] == started[0]["worker_id"]


# --------------------------------------------------------------------------- #
# The command line and the report format, without a process
# --------------------------------------------------------------------------- #


def test_the_command_line_defaults_to_an_unbounded_loop() -> None:
    assert parse_arguments([]) == WorkerOptions()


def test_the_command_line_reads_every_limit() -> None:
    options = parse_arguments(
        ["--once", "--max-jobs", "4", "--max-seconds", "2.5", "--worker-id", "w1"]
    )
    assert options == WorkerOptions(
        once=True, max_jobs=4, max_seconds=2.5, worker_id="w1"
    )


def test_a_missing_report_is_an_error_rather_than_an_empty_reading() -> None:
    """A process that left no report says nothing, and must not read as zero counters."""
    with pytest.raises(ValueError, match=REPORT_EVENT):
        parse_report("not a report\n")
