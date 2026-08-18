"""JOB-005 executed: a process killed on either side of its one durable effect.

This is the scenario that cannot be run in one process. Both other single-process
stand-ins — a lease set to zero, a handler that raises — leave the interpreter
alive and its cleanup running, and the interruption being tested is the one where
nothing gets to clean up. So each case starts a real worker with
``python -m platform_core.worker``, lets its handler end that process with
``os._exit``, waits for the lease it was holding to expire, and starts another.

The two cases differ by one line inside the handler and must not differ in the
outcome: one effect, one abandoned attempt, one success. What must differ is the
evidence that they were genuinely different interruptions, and there are two
independent forms of it here — the effect table right after the first process
died, and the count of suppressed inserts the second process reports on the way
out. If both cases had landed before the effect, the first would show one row
where it should show none and the second would report a suppression that never
happened.

**Reading a counter out of a process that is no longer running.** Metrics live in
memory, so the parent of a worker cannot see them; the worker writes a JSON
report to its standard output as it exits and the parent parses that. The first
process of each case leaves no report at all, which is correct — it was killed,
and what remains of it is the database row and the log lines it had already
flushed. The counter that carries the scenario's evidence belongs to the second
process, which exits cleanly.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from io import StringIO
from typing import Any
from uuid import UUID

import psycopg
import pytest
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass
from platform_core.handlers.synthetic import DEFAULT_EXIT_CODE
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from platform_core.worker import EXIT_OK, REPORT_EVENT, parse_report

from tests.conftest import (
    all_effects,
    attempts_of,
    cloned_database,
    effects_of,
    keep_databases,
    log_events,
    run_worker,
    wait_until,
)

#: Short enough that the recovery is observed without a real wait, and long
#: enough that the second worker's own attempt cannot expire under it.
SHORT_LEASE_SECONDS = "1"

FAST_POLL_MS = "20"

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Case:
    """One of the scenario's two interruption points, and what separates them."""

    handler: str
    #: Effect rows in existence at the moment the interrupted process died.
    effects_when_interrupted: int
    #: Suppressed inserts the recovering process is expected to report.
    suppressed_on_recovery: int


CASES = (
    Case("halt_before_effect", effects_when_interrupted=0, suppressed_on_recovery=0),
    Case("halt_after_effect", effects_when_interrupted=1, suppressed_on_recovery=1),
)


@dataclass(frozen=True)
class InterruptionRun:
    """Everything the scenario asks to be read, in the order it happened."""

    case: Case
    job_id: UUID
    correlation_id: str
    interrupted: subprocess.CompletedProcess[str]
    job_while_interrupted: dict[str, Any]
    attempts_while_interrupted: list[dict[str, Any]]
    effects_when_interrupted: list[dict[str, Any]]
    recovered: subprocess.CompletedProcess[str]
    report: dict[str, Any]
    job: dict[str, Any]
    attempts: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    #: The fixture's own connection to the database this case ran against. Carried
    #: so a test can still read the *whole* effect table live rather than being
    #: handed a separate connection to a different, empty database — the fixture is
    #: module-scoped and owns the database, see the note on its scope below.
    connection: psycopg.Connection[Any]


def lease_has_expired(connection: psycopg.Connection[Any], job_id: UUID) -> bool:
    """Ask the database, which owns every timestamp a lease decision reads."""
    with connection.cursor() as cursor:
        cursor.execute(
            "select lease_expires_at < now() from job where id = %s", (job_id,)
        )
        row = cursor.fetchone()
    return bool(row is not None and row[0])


@pytest.fixture(params=CASES, ids=[case.handler for case in CASES], scope="module")
def job_005_run(
    request: pytest.FixtureRequest,
    platform_database: PlatformConfig,
    migrated_template: str,
) -> Iterator[InterruptionRun]:
    """The scenario's Action section for one case, from an empty database.

    Module-scoped, so each of the two cases runs its Action once rather than once
    per assertion — five replays of a 1.4 s interruption per case, for five
    read-only assertions. Every test below reads the frozen ``InterruptionRun`` and
    writes nothing, which is the property that makes the wider scope sound; the
    first test that needs to write needs a function-scoped ``shared_database``
    instead.

    A parametrized fixture is instantiated once per parameter, so creating the
    database *inside* it gives each case a database of its own. That matters: both
    cases assert that the whole effect table holds exactly one row, and two cases
    sharing one database would make the second of them read two.
    """
    case: Case = request.param
    with cloned_database(
        platform_database, migrated_template, "shared", keep_databases(request)
    ) as shared_database, connected(shared_database, autocommit=True) as shared_connection:
        shared_store = JobStore(
            shared_connection,
            shared_database,
            logger=StructuredLogger(stream=StringIO(), level="DEBUG"),
            metrics=MetricsRegistry(),
        )
        yield _interruption_run(case, shared_store, shared_connection, shared_database)


def _interruption_run(
    case: Case,
    shared_store: JobStore,
    shared_connection: psycopg.Connection[Any],
    shared_database: PlatformConfig,
) -> InterruptionRun:
    """Steps 1 to 3 of one case, as one timeline."""
    job_id = shared_store.create_job(
        case.handler, {"halt_on_attempt": 1}, max_attempts=MAX_ATTEMPTS
    )

    # 2. Let the worker claim it and terminate itself uncleanly.
    interrupted = run_worker(
        shared_database,
        "--once",
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    job_while_interrupted = shared_store.read_job(job_id)
    assert job_while_interrupted is not None
    attempts_while_interrupted = attempts_of(shared_connection, job_id)
    effects_when_interrupted = effects_of(shared_connection, job_id)

    # The lease outlives the process that held it; the platform waits it out.
    wait_until(
        lambda: lease_has_expired(shared_connection, job_id),
        "the lease of the interrupted worker has expired",
    )

    # 3. Restart the worker and run until the job is terminal.
    recovered = run_worker(
        shared_database,
        "--once",
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )
    job = shared_store.read_job(job_id)
    assert job is not None
    return InterruptionRun(
        case=case,
        job_id=job_id,
        correlation_id=str(job["correlation_id"]),
        interrupted=interrupted,
        job_while_interrupted=job_while_interrupted,
        attempts_while_interrupted=attempts_while_interrupted,
        effects_when_interrupted=effects_when_interrupted,
        recovered=recovered,
        report=parse_report(recovered.stdout),
        job=job,
        attempts=attempts_of(shared_connection, job_id),
        effects=effects_of(shared_connection, job_id),
        connection=shared_connection,
    )


def test_job_005_the_killed_process_leaves_the_attempt_open_and_the_lease_held(
    job_005_run: InterruptionRun,
) -> None:
    """Row 2: the process died, so nothing closed the attempt or cleared the lease.

    This is the durable state an operator would find while a worker is gone and
    its lease has not yet expired — the job looks exactly like one being worked
    on, which is why the lease deadline rather than the state is what recovers it.
    """
    assert job_005_run.interrupted.returncode == DEFAULT_EXIT_CODE
    # A killed process writes no report; the database is what it left behind.
    assert REPORT_EVENT not in job_005_run.interrupted.stdout

    job = job_005_run.job_while_interrupted
    assert job["state"] == JobState.RUNNING
    assert job["attempt_count"] == 1
    assert job["lease_owner"] is not None
    assert job["lease_expires_at"] is not None
    assert len(job_005_run.attempts_while_interrupted) == 1
    open_attempt = job_005_run.attempts_while_interrupted[0]
    assert open_attempt["attempt_no"] == 1
    assert open_attempt["finished_at"] is None
    assert open_attempt["outcome"] is None


def test_job_005_the_two_cases_are_interrupted_on_different_sides_of_the_effect(
    job_005_run: InterruptionRun,
) -> None:
    """The precondition the rest of the scenario's evidence depends on.

    Read from the effect table at the moment the process died, before any
    recovery: one case had already applied its effect and the other had not. If
    this were equal for both, the counter compared further down would be
    comparing one interruption point with itself.
    """
    assert len(job_005_run.effects_when_interrupted) == (
        job_005_run.case.effects_when_interrupted
    )


def test_job_005_recovery_abandons_the_first_attempt_and_succeeds_on_the_second(
    job_005_run: InterruptionRun,
) -> None:
    """Rows 3 to 6, identically in both cases."""
    assert job_005_run.recovered.returncode == EXIT_OK, job_005_run.recovered.stderr
    first, second = job_005_run.attempts
    assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
    assert first["outcome"] == AttemptOutcome.ABANDONED
    assert first["error_class"] == ErrorClass.LEASE_ABANDONED
    assert first["finished_at"] is not None
    assert first["error_summary"]
    assert second["outcome"] == AttemptOutcome.SUCCEEDED
    assert second["worker_id"] != first["worker_id"], "a different process recovered it"

    job = job_005_run.job
    assert job["state"] == JobState.SUCCEEDED
    assert job["terminal_reason"] is None
    assert job["attempt_count"] == 2
    assert job["lease_owner"] is None
    assert job["lease_expires_at"] is None


def test_job_005_leaves_exactly_one_effect_in_both_cases(
    job_005_run: InterruptionRun,
) -> None:
    """I1, at the one place at-least-once delivery is actually dangerous.

    Both counts matter and neither implies the other: one row for this job, and one
    row in the table, so a second effect written under a different key would be
    caught as well.
    """
    assert len(job_005_run.effects) == 1
    assert len(all_effects(job_005_run.connection)) == 1
    assert job_005_run.effects[0]["job_id"] == job_005_run.job_id


def test_job_005_the_suppressed_duplicate_counter_separates_the_two_cases(
    job_005_run: InterruptionRun,
) -> None:
    """The scenario's own proof that the interruption points were different.

    Both cases end with one effect row, so the effect table alone cannot say
    whether the second attempt wrote it or found it already there. The counter
    can: it moves only in the case whose first attempt had already applied the
    effect before its process died.
    """
    metrics = job_005_run.report["metrics"]
    assert metrics["suppressed_duplicate_effects"] == (
        job_005_run.case.suppressed_on_recovery
    )
    # Recovery itself is identical in both cases and is counted as such.
    assert metrics["abandoned_attempts"] == 1
    assert metrics["lease_recovery_latency_ms"]["count"] == 1
    assert metrics["transitions"][JobState.SUCCEEDED] == 1
    assert metrics["rejected_completions"] == 0
    assert job_005_run.report["jobs_executed"] == 1


def test_job_005_the_correlation_id_survives_the_process_restart(
    job_005_run: InterruptionRun,
) -> None:
    """I5 across a process boundary, which is why the identifier is stored on the job.

    Both attempt rows and the log lines of both processes carry it, including the
    process that was killed — its lines had already been flushed when it died.
    """
    identifier = job_005_run.correlation_id
    assert {attempt["correlation_id"] for attempt in job_005_run.attempts} == {identifier}

    for finished in (job_005_run.interrupted, job_005_run.recovered):
        about = [
            record
            for record in log_events(finished.stderr)
            if record.get("job_id") == str(job_005_run.job_id)
        ]
        assert about, "each process logged about the job it claimed"
        assert {record["correlation_id"] for record in about} == {identifier}

    reclaimed = [
        record
        for record in log_events(job_005_run.recovered.stderr)
        if record["event"] == "job.attempt_abandoned"
    ]
    assert len(reclaimed) == 1
    assert reclaimed[0]["attempt_no"] == 1
    assert reclaimed[0]["error_class"] == ErrorClass.LEASE_ABANDONED
    assert reclaimed[0]["correlation_id"] == identifier
