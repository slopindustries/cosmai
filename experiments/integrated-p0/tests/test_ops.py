"""OPS-001 to OPS-004 executed against a running operator API.

The four `OPS` scenarios test one charter criterion — *"the operator can inspect and
safely retry generic work without direct database access"* — from four directions,
and each names one assertion as the one that carries the result. Those four are why
this module is shaped the way it is.

**OPS-001: the verification opens no database connection.** The scenario says why in
as many words: *"A test that reaches into `psycopg` to confirm what the API said has
not established that the API was enough; it has established that the database was."*
So the probe fixture does the setup — it creates the jobs and runs the workers,
neither of which is a claim about the API — and every assertion afterwards reads a
frozen HTTP response. ``psycopg`` is sealed off while those assertions run, and
``test_ops_001_the_database_is_sealed_off_during_verification`` shows the seal is
real rather than decorative. Without that control the other tests would only be
evidence that nobody happened to open a connection.

**OPS-002: the suppressed-duplicate counter moved by exactly 1.** Case a ends with
the same number of effect rows it started with, which is also what a retry that
never ran would produce. The counter is what separates "the retried attempt
re-derived the key and was suppressed" from "the retried attempt never happened", so
it is read out of a worker's shutdown report on both sides of the retry.

**OPS-003: an unrelated job's events are in the log and absent from the answer.** A
filter that returned everything would satisfy every other assertion in that
scenario. A second job runs into the same log, and its events must not come back.

**OPS-004: at least one counter stays at 0.** A metrics surface that incremented
everything would match the expected transition counts by accident, so counters that
must not move are asserted beside the ones that must.

Two mechanics are shared with the rest of the suite. Each scenario's Action runs once
in a module-scoped fixture and is frozen, because every assertion over it is
read-only and replaying a multi-process timeline per assertion costs seconds for
nothing. And each probe clones a database of its own, so two scenarios cannot see
each other's jobs — several assertions here are counts over the whole table.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from platform_core.api.app import (
    HEALTHY,
    PROTECTED_FIELD,
    REACHABLE,
    RETRY_REQUIRES,
    UNHEALTHY,
    UNREACHABLE,
)
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass
from platform_core.handlers.synthetic import DEFAULT_EXIT_CODE
from platform_core.jobs.state import JOB_STATES, AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from platform_core.worker import EXIT_OK, parse_report
from psycopg import sql

from tests.conftest import (
    EXPERIMENT_ROOT,
    LEASE_SECONDS,
    WORKER,
    all_effects,
    cloned_database,
    effects_of,
    keep_databases,
    log_events,
    run_worker,
    running_api,
    wait_until,
)

REQUEST_TIMEOUT_SECONDS = 10.0

MAX_ATTEMPTS = 3

#: Short enough that a lease expiry is observed without a real wait, long enough
#: that the recovering worker's own attempt cannot expire under it.
SHORT_LEASE_SECONDS = "1"

FAST_POLL_MS = "20"

#: A backoff base of 1 ms, so OPS-001 case a's second attempt is due at once rather
#: than after the default 100 ms window. The scenario states no timing assumption,
#: so shortening it changes nothing it observes.
FAST_RETRY_BASE_MS = "1"

#: A bound on every worker a probe starts, so a scenario that stopped making
#: progress fails with its own message instead of hanging.
WORKER_BUDGET_SECONDS = "20"

#: A value that must never appear in a metric label or a returned event.
SENSITIVE_MARKER: Final = "marker-must-not-leak-ops-42"

#: The detection control beside it: a value under an ordinary key that must survive.
ORDINARY_MARKER: Final = "marker-must-survive-ops-42"

MARKED_PAYLOAD: Final[dict[str, Any]] = {"api_key": SENSITIVE_MARKER, "note": ORDINARY_MARKER}

#: The three kinds of thing the P0-A navigation model has (OQ-005 H1). A required
#: answer needing a fourth would refute H1 and would have to be named as such.
NAVIGATION_KINDS: Final[frozenset[str]] = frozenset({"health", "jobs", "attempts"})


# --------------------------------------------------------------------------- #
# Frozen HTTP responses
#
# Every assertion below reads one of these rather than making a request, which is
# what lets one execution of a scenario's Action serve all of its assertions — and,
# for OPS-001, what lets the database be sealed off while they run.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Fetched:
    """One response: where it came from, its status, and its decoded body."""

    path: str
    status_code: int
    body: Any

    @property
    def json(self) -> dict[str, Any]:
        assert isinstance(self.body, dict), f"{self.path} returned {self.body!r}"
        return self.body

    @property
    def text(self) -> str:
        """The whole response as text, for a search over everything it contained."""
        return json.dumps(self.body, ensure_ascii=False, default=str)

    @property
    def navigation_kind(self) -> str:
        """Which kind of thing this path addressed, for the OQ-005 H1 assertion."""
        parts = [part for part in self.path.split("?")[0].split("/") if part]
        if not parts:
            return "root"
        if parts[0] != "jobs":
            return parts[0]
        return "attempts" if parts[-1] == "attempts" else "jobs"


def keys_anywhere(body: Any) -> set[str]:
    """Every mapping key anywhere inside a decoded response.

    A substring search over the rendered text cannot answer "does this response
    carry ``error_detail``": ``error_detail_present`` contains those characters and
    is required to be there. The question is about keys, so the keys are collected.
    """
    if isinstance(body, Mapping):
        found = set(body)
        for value in body.values():
            found |= keys_anywhere(value)
        return found
    if isinstance(body, list):
        return {key for item in body for key in keys_anywhere(item)}
    return set()


def _decoded(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:  # pragma: no cover - a non-JSON body is itself the failure
        return response.text


def fetch(client: httpx.Client, path: str, **params: Any) -> Fetched:
    response = client.get(path, params=params or None)
    return Fetched(path=path, status_code=response.status_code, body=_decoded(response))


def post(client: httpx.Client, path: str) -> Fetched:
    response = client.post(path)
    return Fetched(path=path, status_code=response.status_code, body=_decoded(response))


@dataclass(frozen=True)
class Owned:
    """A cloned database, and the store and connection a probe drives it through."""

    config: PlatformConfig
    store: JobStore
    connection: psycopg.Connection[Any]


@contextmanager
def owned_database(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[Owned]:
    """A database of one probe's own, with a store and a connection on it.

    A context manager rather than a fixture because each of the four probes needs
    one of its own: a shared database would let one scenario's jobs be counted by
    another's assertions, and several of them are counts over the whole table. The
    store's log goes nowhere — a probe's own writes are setup, not evidence.
    """
    with (
        cloned_database(
            platform_database, migrated_template, "shared", keep_databases(request)
        ) as config,
        connected(config, autocommit=True) as connection,
    ):
        store = JobStore(
            connection,
            config,
            logger=StructuredLogger(stream=StringIO(), level="DEBUG"),
            metrics=MetricsRegistry(),
        )
        yield Owned(config=config, store=store, connection=connection)


def create_clone(config: PlatformConfig, name: str, template: str) -> None:
    with connected(config, autocommit=True) as maintenance:
        maintenance.execute(
            sql.SQL("create database {} template {}").format(
                sql.Identifier(name), sql.Identifier(template)
            )
        )


def drop_clone(config: PlatformConfig, name: str) -> None:
    with connected(config, autocommit=True) as maintenance:
        maintenance.execute(
            sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name))
        )


# --------------------------------------------------------------------------- #
# OPS-001 — six questions, answered without touching the database
# --------------------------------------------------------------------------- #

#: A handler name nothing registers. Case c's failure is that this is not a typo the
#: platform can resolve, and its summary has to say so by name.
UNREGISTERED_HANDLER: Final = "handler-nobody-registered"


@dataclass(frozen=True)
class Case:
    """One of OPS-001's three failures, and what an operator must be able to read."""

    label: str
    handler: str
    max_attempts: int
    payload: dict[str, Any]
    terminal_reason: str
    attempts_expected: int
    #: Whether the failing class itself permits a further attempt. In case a it does
    #: while the job does not, and the scenario requires both to be readable.
    class_is_retryable: bool


CASES: Final[tuple[Case, ...]] = (
    Case(
        label="a-exhausted",
        handler="fail_transient",
        max_attempts=2,
        payload={"case": "a"},
        terminal_reason=ErrorClass.PLATFORM_TRANSIENT.value,
        attempts_expected=2,
        class_is_retryable=True,
    ),
    Case(
        label="b-permanent",
        handler="fail_permanent",
        max_attempts=MAX_ATTEMPTS,
        payload={"case": "b"},
        terminal_reason=ErrorClass.PLATFORM_PERMANENT.value,
        attempts_expected=1,
        class_is_retryable=False,
    ),
    Case(
        label="c-unknown-handler",
        handler=UNREGISTERED_HANDLER,
        max_attempts=MAX_ATTEMPTS,
        payload={"case": "c"},
        terminal_reason=ErrorClass.HANDLER_UNKNOWN.value,
        attempts_expected=1,
        class_is_retryable=False,
    ),
)

#: Executions the three cases need between them: two for case a, one each for b and
#: c. Stated, so the worker stops for a reason the scenario named.
OPS_001_EXECUTIONS: Final = sum(case.attempts_expected for case in CASES)


@dataclass(frozen=True)
class Ops001Probe:
    """Every answer OPS-001 asks for, as HTTP responses and nothing else."""

    identities: Mapping[str, UUID]
    failures: Fetched
    jobs: Mapping[str, Fetched]
    attempts: Mapping[str, Fetched]
    absent_job: Fetched
    absent_attempts: Fetched

    @property
    def question_responses(self) -> tuple[Fetched, ...]:
        """Exactly the responses questions 1 to 6 are answered from."""
        return (self.failures, *self.jobs.values(), *self.attempts.values())

    def attempt_rows(self, label: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = self.attempts[label].json["attempts"]
        return rows

    def last_attempt(self, label: str) -> dict[str, Any]:
        return self.attempt_rows(label)[-1]


@pytest.fixture(scope="module")
def ops_001_probe(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[Ops001Probe]:
    """OPS-001's Action: produce the three failures, then read the API dry.

    All the database work is here, before any assertion runs. None of it is a claim
    about the operator surface; it is the scenario's precondition, and the scenario
    puts job creation and worker execution outside what the verification may not do.
    """
    with owned_database(platform_database, migrated_template, request) as owned:
        identities = {
            case.label: owned.store.create_job(
                case.handler, case.payload, max_attempts=case.max_attempts
            )
            for case in CASES
        }
        finished = run_worker(
            owned.config,
            "--max-jobs",
            str(OPS_001_EXECUTIONS),
            "--max-seconds",
            WORKER_BUDGET_SECONDS,
            COSMA_POLL_MS=FAST_POLL_MS,
            COSMA_RETRY_BASE_MS=FAST_RETRY_BASE_MS,
        )
        assert finished.returncode == EXIT_OK, finished.stderr
        assert parse_report(finished.stdout)["jobs_executed"] == OPS_001_EXECUTIONS

        absent = uuid4()
        with (
            running_api(owned.config) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            probe = Ops001Probe(
                identities=identities,
                failures=fetch(client, "/jobs", state=JobState.FAILED.value),
                jobs={
                    case.label: fetch(client, f"/jobs/{identities[case.label]}")
                    for case in CASES
                },
                attempts={
                    case.label: fetch(client, f"/jobs/{identities[case.label]}/attempts")
                    for case in CASES
                },
                absent_job=fetch(client, f"/jobs/{absent}"),
                absent_attempts=fetch(client, f"/jobs/{absent}/attempts"),
            )
        assert api.collected().returncode == EXIT_OK, api.collected().stderr
        yield probe


def _refuse_connection(*arguments: Any, **keywords: Any) -> Any:
    raise AssertionError(
        "OPS-001's verification opened a database connection. The scenario's "
        "load-bearing assertion is that it does not: an answer confirmed against the "
        "database is evidence about the database, not about the operator API."
    )


@pytest.fixture
def ops_001(ops_001_probe: Ops001Probe, monkeypatch: pytest.MonkeyPatch) -> Ops001Probe:
    """The frozen answers, with ``psycopg`` sealed off for the duration of the test.

    Depending on the probe rather than being autouse is what orders the two: the
    probe is built first, with the driver available, and the seal is installed after
    it. ``monkeypatch`` removes the seal at the end of each test, which is what still
    lets the probe's own database be dropped on the way out.
    """
    monkeypatch.setattr(psycopg, "connect", _refuse_connection)
    monkeypatch.setattr(psycopg.Connection, "connect", _refuse_connection)
    return ops_001_probe


def test_ops_001_the_database_is_sealed_off_during_verification(ops_001: Ops001Probe) -> None:
    """The control for the load-bearing assertion, which is otherwise unfalsifiable.

    Every other OPS-001 test claims to answer its question from HTTP responses alone,
    and that claim is worth something only if an attempt to reach the database would
    have been caught. Both doors are checked: ``psycopg.connect`` is the only one
    ``platform_core.db.connection`` uses, and ``Connection.connect`` is the one a
    caller reaching past it would find.
    """
    assert ops_001.failures.status_code == 200, "the probe ran before the seal went up"
    for door in (psycopg.connect, psycopg.Connection.connect):
        with pytest.raises(AssertionError, match="opened a database connection"):
            door("")


def test_ops_001_the_navigation_model_needs_no_fourth_kind_of_thing(
    ops_001: Ops001Probe,
) -> None:
    """OQ-005 H1: three kinds answered all six questions, and a fourth would refute it."""
    used = {response.navigation_kind for response in ops_001.question_responses}
    assert used <= NAVIGATION_KINDS, f"a fourth navigation object was required: {used}"
    assert used == {"jobs", "attempts"}, used


def test_ops_001_the_failures_are_findable_before_any_of_them_is_named(
    ops_001: Ops001Probe,
) -> None:
    """The operator's entry point: a list filtered by state, not a known identifier."""
    assert ops_001.failures.status_code == 200, ops_001.failures.body
    listing = ops_001.failures.json
    assert listing["state"] == JobState.FAILED
    assert listing["matched"] == len(CASES)
    listed = {job["id"] for job in listing["jobs"]}
    assert listed == {str(identity) for identity in ops_001.identities.values()}


@pytest.mark.parametrize("case", CASES, ids=[case.label for case in CASES])
def test_ops_001_all_six_questions_are_answered_from_api_responses_alone(
    ops_001: Ops001Probe, case: Case
) -> None:
    """Questions 1 to 6 for one case, out of two responses and no connection."""
    job = ops_001.jobs[case.label].json
    rows = ops_001.attempt_rows(case.label)

    # 1. What ran?
    assert job["id"] == str(ops_001.identities[case.label])
    assert job["handler"] == case.handler

    # 2. With which input?
    assert job["payload"] == case.payload

    # 3. When? Creation, each attempt's start, and the terminal transition.
    assert job["created_at"], "creation is timestamped"
    assert job["updated_at"], "the terminal transition is timestamped"
    assert len(rows) == case.attempts_expected
    assert all(row["started_at"] for row in rows), "every attempt says when it started"
    assert rows[-1]["finished_at"], "the last attempt says when it closed"

    # 4. Why did it fail? A class, and an operator-readable summary.
    last = rows[-1]
    assert job["state"] == JobState.FAILED
    assert job["terminal_reason"] == case.terminal_reason
    assert last["error_class"] == case.terminal_reason
    assert isinstance(last["error_summary"], str)
    assert last["error_summary"].strip()

    # 5. Is anything left to try? Attempts spent against the budget.
    assert job["attempt_count"] == case.attempts_expected
    assert job["max_attempts"] == case.max_attempts
    assert job["attempts_remaining"] == case.max_attempts - case.attempts_expected

    # 6. Is there detail being withheld?
    assert isinstance(last["error_detail_present"], bool)


def test_ops_001_the_exhausted_case_and_the_permanent_case_are_distinguishable(
    ops_001: Ops001Probe,
) -> None:
    """From the fields, not from timing — and the two facts case a mixes stay apart.

    In case a the error *class* is retryable while the *job* is not, because the
    budget is spent. The scenario is explicit that both must be readable and that
    they are different facts, so each is read from the field that owns it: the
    class's retryability from the attempt, the job's from its budget.
    """
    exhausted = ops_001.jobs["a-exhausted"].json
    permanent = ops_001.jobs["b-permanent"].json

    assert exhausted["terminal_reason"] != permanent["terminal_reason"]
    assert exhausted["attempt_budget_spent"] is True
    assert exhausted["attempts_remaining"] == 0
    assert permanent["attempt_budget_spent"] is False
    assert permanent["attempts_remaining"] > 0

    assert ops_001.last_attempt("a-exhausted")["error_class_retryable"] is True
    assert ops_001.last_attempt("b-permanent")["error_class_retryable"] is False
    assert ops_001.last_attempt("a-exhausted")["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert ops_001.last_attempt("b-permanent")["outcome"] == AttemptOutcome.PERMANENT_FAILURE


@pytest.mark.parametrize("case", CASES, ids=[case.label for case in CASES])
def test_ops_001_each_error_class_reports_its_own_retryability(
    ops_001: Ops001Probe, case: Case
) -> None:
    """The contract's error table, readable rather than remembered."""
    assert ops_001.last_attempt(case.label)["error_class_retryable"] is case.class_is_retryable


def test_ops_001_the_unknown_handler_summary_names_the_handler_to_register(
    ops_001: Ops001Probe,
) -> None:
    """Registering it is the operator's next action, so the summary has to name it."""
    summary = ops_001.last_attempt("c-unknown-handler")["error_summary"]
    assert UNREGISTERED_HANDLER in summary, summary


def test_ops_001_no_default_response_carries_protected_detail(ops_001: Ops001Probe) -> None:
    """The protected representation was not asked for, so it must be nowhere.

    The presence *flag* is expected in every attempt — question 6 is answered by it —
    so the key set is what gets checked rather than the rendered text, in which
    ``error_detail_present`` contains ``error_detail`` as a substring.
    """
    for response in ops_001.question_responses:
        assert PROTECTED_FIELD not in keys_anywhere(response.body), response.path
    for case in CASES:
        assert ops_001.last_attempt(case.label)["error_detail_present"] is not None


def test_ops_001_an_unknown_identity_is_not_found_rather_than_an_empty_success(
    ops_001: Ops001Probe,
) -> None:
    """So an operator can tell a wrong identifier from a job with no history."""
    assert ops_001.absent_job.status_code == 404, ops_001.absent_job.body
    assert ops_001.absent_attempts.status_code == 404, ops_001.absent_attempts.body


def test_ops_001_every_response_about_a_job_carries_its_correlation_id(
    ops_001: Ops001Probe,
) -> None:
    """I5, and the handle OPS-003 then uses to reach the log."""
    for case in CASES:
        identifier = ops_001.jobs[case.label].json["correlation_id"]
        assert identifier, case.label
        assert ops_001.attempts[case.label].json["correlation_id"] == identifier
        assert {row["correlation_id"] for row in ops_001.attempt_rows(case.label)} == {identifier}
        listed = [
            job
            for job in ops_001.failures.json["jobs"]
            if job["id"] == str(ops_001.identities[case.label])
        ]
        assert [job["correlation_id"] for job in listed] == [identifier]


# --------------------------------------------------------------------------- #
# OPS-002 — the retry is permitted where it is safe and refused where it is not
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Ops002Run:
    """The four cases, each frozen on both sides of the request that was made."""

    # Case a — a permitted retry that is safe.
    job_a: UUID
    effects_before: int
    report_before: dict[str, Any]
    attempts_a_before: Fetched
    retry_a: Fetched
    report_after: dict[str, Any]
    effects_after: int
    job_a_after: Fetched
    attempts_a_after: Fetched
    # Case b — a retry the operator did not mean.
    job_b_before: Fetched
    retry_b: Fetched
    job_b_after: Fetched
    # Case c — a retry on work in flight.
    job_c_before: Fetched
    attempts_c_before: Fetched
    retry_c: Fetched
    job_c_after: Fetched
    attempts_c_after: Fetched
    # Case d — a retry on nothing.
    retry_d: Fetched
    total_before: int
    total_after: int
    api: subprocess.CompletedProcess[str]

    def events_named(self, event: str) -> list[dict[str, Any]]:
        return [record for record in log_events(self.api.stderr) if record["event"] == event]


@pytest.fixture(scope="module")
def ops_002_run(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[Ops002Run]:
    """OPS-002's four cases, in order, against one database.

    Strictly sequential, and that is load-bearing rather than tidy. Each worker run
    claims whatever is claimable, so a case's job is created only once the previous
    case's worker has stopped — otherwise case c's `RUNNING` job, whose whole point
    is that nothing may touch it, is exactly what the next worker would claim.
    """
    with owned_database(platform_database, migrated_template, request) as owned:
        store = owned.store

        # a.1 — a job that applies its effect and then fails, run until exhausted.
        job_a = store.create_job("apply_effect_then_fail", {"case": "a"}, max_attempts=1)
        before = run_worker(owned.config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
        assert before.returncode == EXIT_OK, before.stderr
        exhausted = store.read_job(job_a)
        assert exhausted is not None and exhausted["state"] == JobState.FAILED, exhausted

        # a.2 — the effect count, read before the retry.
        effects_before = len(all_effects(owned.connection))

        with (
            running_api(owned.config) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            attempts_a_before = fetch(client, f"/jobs/{job_a}/attempts")

            # a.3 — request the retry through the API.
            retry_a = post(client, f"/jobs/{job_a}/retry")

            # a.4 — let a worker run the retried job to SUCCEEDED.
            after = run_worker(owned.config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
            assert after.returncode == EXIT_OK, after.stderr

            # a.5 — the effect count and the attempt history, read again.
            effects_after = len(all_effects(owned.connection))
            job_a_after = fetch(client, f"/jobs/{job_a}")
            attempts_a_after = fetch(client, f"/jobs/{job_a}/attempts")

            # b — a retry on a SUCCEEDED job.
            job_b = store.create_job("succeed", {"case": "b"}, max_attempts=MAX_ATTEMPTS)
            succeeded = run_worker(owned.config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
            assert succeeded.returncode == EXIT_OK, succeeded.stderr
            job_b_before = fetch(client, f"/jobs/{job_b}")
            retry_b = post(client, f"/jobs/{job_b}/retry")
            job_b_after = fetch(client, f"/jobs/{job_b}")

            # c — a retry on a RUNNING job whose lease is held. Claimed in this
            # process rather than by a worker, so the lease is held by a name the
            # assertions know and no handler is running to end the attempt.
            job_c = store.create_job("stall", {"case": "c"}, max_attempts=MAX_ATTEMPTS)
            claimed = store.claim_next(WORKER, LEASE_SECONDS)
            assert claimed is not None and claimed.job_id == job_c, claimed
            job_c_before = fetch(client, f"/jobs/{job_c}")
            attempts_c_before = fetch(client, f"/jobs/{job_c}/attempts")
            retry_c = post(client, f"/jobs/{job_c}/retry")
            job_c_after = fetch(client, f"/jobs/{job_c}")
            attempts_c_after = fetch(client, f"/jobs/{job_c}/attempts")

            # d — a retry on a job identity that does not exist.
            total_before = fetch(client, "/jobs").json["matched"]
            retry_d = post(client, f"/jobs/{uuid4()}/retry")
            total_after = fetch(client, "/jobs").json["matched"]

        yield Ops002Run(
            job_a=job_a,
            effects_before=effects_before,
            report_before=parse_report(before.stdout),
            attempts_a_before=attempts_a_before,
            retry_a=retry_a,
            report_after=parse_report(after.stdout),
            effects_after=effects_after,
            job_a_after=job_a_after,
            attempts_a_after=attempts_a_after,
            job_b_before=job_b_before,
            retry_b=retry_b,
            job_b_after=job_b_after,
            job_c_before=job_c_before,
            attempts_c_before=attempts_c_before,
            retry_c=retry_c,
            job_c_after=job_c_after,
            attempts_c_after=attempts_c_after,
            retry_d=retry_d,
            total_before=total_before,
            total_after=total_after,
            api=api.collected(),
        )


def test_ops_002_case_a_the_retry_was_accepted_and_the_job_finished(
    ops_002_run: Ops002Run,
) -> None:
    """The precondition every other case-a assertion rests on."""
    assert ops_002_run.retry_a.status_code == 200, ops_002_run.retry_a.body
    accepted = ops_002_run.retry_a.json
    assert accepted["accepted"] is True
    assert accepted["previous_state"] == JobState.FAILED
    assert accepted["current_state"] == JobState.PENDING
    assert accepted["job"]["attempt_count"] == 0, "the attempt budget was restored"
    assert ops_002_run.job_a_after.json["state"] == JobState.SUCCEEDED


def test_ops_002_case_a_the_effect_count_is_unchanged_and_the_suppression_counted(
    ops_002_run: Ops002Run,
) -> None:
    """The invariant, and the counter that makes it mean something.

    One effect row before and one after is also what a retry that never ran would
    produce. The counter separates the two: it moves by exactly 1, in the process
    that executed the retried attempt, because that attempt re-derived the same
    ``effect_key`` and its insert was suppressed.
    """
    assert ops_002_run.effects_before == 1
    assert ops_002_run.effects_after == ops_002_run.effects_before

    assert ops_002_run.report_before["metrics"]["suppressed_duplicate_effects"] == 0
    assert ops_002_run.report_after["metrics"]["suppressed_duplicate_effects"] == 1


def test_ops_002_case_a_the_new_attempt_is_numbered_above_every_earlier_one(
    ops_002_run: Ops002Run,
) -> None:
    """And the earlier attempts are still readable — they are the diagnosis acted on."""
    before: list[dict[str, Any]] = ops_002_run.attempts_a_before.json["attempts"]
    after: list[dict[str, Any]] = ops_002_run.attempts_a_after.json["attempts"]
    assert [row["attempt_no"] for row in before] == [1]
    assert [row["attempt_no"] for row in after] == [1, 2]
    assert len(after) == len(before) + 1

    retained, fresh = after
    assert retained["outcome"] == AttemptOutcome.RETRYABLE_FAILURE
    assert retained["error_class"] == ErrorClass.PLATFORM_TRANSIENT
    assert retained["error_summary"] == before[0]["error_summary"]
    assert fresh["outcome"] == AttemptOutcome.SUCCEEDED


def test_ops_002_case_a_keeps_its_original_correlation_id(ops_002_run: Ops002Run) -> None:
    """A retry that minted a new identifier would sever the history it was based on."""
    identifier = ops_002_run.attempts_a_before.json["correlation_id"]
    assert identifier
    assert ops_002_run.retry_a.json["correlation_id"] == identifier
    assert ops_002_run.job_a_after.json["correlation_id"] == identifier
    assert {row["correlation_id"] for row in ops_002_run.attempts_a_after.json["attempts"]} == {
        identifier
    }


@pytest.mark.parametrize("case", ["b", "c"])
def test_ops_002_a_refusal_names_the_current_state_and_the_required_state(
    ops_002_run: Ops002Run, case: str
) -> None:
    """An actionable refusal names both states; "bad request" names neither."""
    refusal = {"b": ops_002_run.retry_b, "c": ops_002_run.retry_c}[case]
    expected = {"b": JobState.SUCCEEDED, "c": JobState.RUNNING}[case]
    assert refusal.status_code == 409, refusal.body
    body = refusal.json
    assert body["accepted"] is False
    assert body["current_state"] == expected
    assert body["required_state"] == RETRY_REQUIRES.value
    assert expected.value in body["reason"]
    assert RETRY_REQUIRES.value in body["reason"]
    assert "bad request" not in body["reason"].lower()


@pytest.mark.parametrize("case", ["b", "c"])
def test_ops_002_a_refused_retry_leaves_the_job_row_unchanged_field_by_field(
    ops_002_run: Ops002Run, case: str
) -> None:
    """``updated_at`` included: a refusal that touched the row would show up there."""
    before = {"b": ops_002_run.job_b_before, "c": ops_002_run.job_c_before}[case]
    after = {"b": ops_002_run.job_b_after, "c": ops_002_run.job_c_after}[case]
    assert after.json == before.json


def test_ops_002_case_c_leaves_the_lease_holder_and_its_open_attempt_untouched(
    ops_002_run: Ops002Run,
) -> None:
    """The refusal must not disturb the worker that legitimately holds the job."""
    held = ops_002_run.job_c_after.json
    assert held["state"] == JobState.RUNNING
    assert held["lease_owner"] == WORKER
    assert held["lease_expires_at"]
    assert ops_002_run.attempts_c_after.json == ops_002_run.attempts_c_before.json
    still_open = [
        row for row in ops_002_run.attempts_c_after.json["attempts"] if row["finished_at"] is None
    ]
    assert len(still_open) == 1, still_open
    assert still_open[0]["worker_id"] == WORKER


def test_ops_002_case_d_is_not_found_and_creates_nothing(ops_002_run: Ops002Run) -> None:
    assert ops_002_run.retry_d.status_code == 404, ops_002_run.retry_d.body
    assert ops_002_run.total_after == ops_002_run.total_before


def test_ops_002_every_retry_decision_is_logged_with_the_job_and_its_state(
    ops_002_run: Ops002Run,
) -> None:
    """A refusal that logged nothing would leave an operator unable to explain it."""
    accepted = ops_002_run.events_named("api.retry_accepted")
    assert len(accepted) == 1, accepted
    assert accepted[0]["job_id"] == str(ops_002_run.job_a)
    assert accepted[0]["from_state"] == JobState.FAILED
    assert accepted[0]["to_state"] == JobState.PENDING
    assert accepted[0]["correlation_id"] == ops_002_run.retry_a.json["correlation_id"]

    refused = ops_002_run.events_named("api.retry_refused")
    # Cases b, c and d: the two wrong states, and the identity that does not exist.
    assert len(refused) == 3, refused
    assert [record["required_state"] for record in refused] == [RETRY_REQUIRES.value] * 3
    assert {record["current_state"] for record in refused} == {
        JobState.SUCCEEDED.value,
        JobState.RUNNING.value,
        None,
    }
    assert all(record["job_id"] for record in refused)


# --------------------------------------------------------------------------- #
# OPS-003 — one identifier, two processes, one history
# --------------------------------------------------------------------------- #

#: The event a foreign writer puts into the log, to show the API redacts on the way
#: out rather than trusting that everything in the file was already masked.
FOREIGN_EVENT: Final = "probe.foreign_line"

#: A correlation identifier no job was ever given.
UNKNOWN_CORRELATION: Final = "correlation-nobody-assigned"


@dataclass(frozen=True)
class Ops003Run:
    """The recovered job, the control job, and what the API returned for each."""

    job_id: UUID
    correlation_id: str
    other_job_id: UUID
    other_correlation_id: str
    job: Fetched
    attempts: Fetched
    events: Fetched
    other_events: Fetched
    unknown_events: Fetched
    log_file: Path
    #: Effect rows for the recovered job, and for the whole table. Neither implies
    #: the other: a second row under a different key would pass the first count.
    effects_for_job: int
    effects_total: int
    interrupted: subprocess.CompletedProcess[str]
    recovered: subprocess.CompletedProcess[str]

    @property
    def records(self) -> list[dict[str, Any]]:
        returned: list[dict[str, Any]] = self.events.json["events"]
        return returned

    def named(self, event: str) -> list[dict[str, Any]]:
        return [record for record in self.records if record["event"] == event]


def lease_has_expired(connection: psycopg.Connection[Any], job_id: UUID) -> bool:
    """Ask the database, which owns every timestamp a lease decision reads."""
    with connection.cursor() as cursor:
        cursor.execute("select lease_expires_at < now() from job where id = %s", (job_id,))
        row = cursor.fetchone()
    return bool(row is not None and row[0])


def logged_worker(config: PlatformConfig, log_file: Path) -> subprocess.CompletedProcess[str]:
    """One worker pass whose events go into the shared log rather than to its own stderr.

    The three settings are spelled out rather than unpacked from a mapping so that
    ``run_worker``'s own ``timeout`` keyword cannot be shadowed by an environment
    override, which is a collision the type checker is right to object to.
    """
    return run_worker(
        config,
        "--once",
        COSMA_LOG_FILE=str(log_file),
        COSMA_LEASE_SECONDS=SHORT_LEASE_SECONDS,
        COSMA_POLL_MS=FAST_POLL_MS,
    )


def append_foreign_event(path: Path, correlation_id: str, job_id: UUID) -> None:
    """Write one line the platform's own logger did not write.

    SEC-004's boundary is a property of the API, not of the writers behind it. The
    platform redacts every event before it reaches the file, so searching a real log
    for a marker proves only that nothing was attempted. This attempts it: a line
    carrying an unmasked value under a redacted key, and protected detail under the
    column name the attempt representation withholds. ``note`` is the detection
    control — if it were also missing, "no marker was found" would be
    indistinguishable from "the search does not work".
    """
    line = {
        "ts": datetime.now(UTC).isoformat(),
        "level": "WARNING",
        "event": FOREIGN_EVENT,
        "correlation_id": correlation_id,
        "job_id": str(job_id),
        "api_key": SENSITIVE_MARKER,
        "note": ORDINARY_MARKER,
        PROTECTED_FIELD: {"password": SENSITIVE_MARKER},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


@pytest.fixture(scope="module")
def ops_003_run(
    platform_database: PlatformConfig,
    migrated_template: str,
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> Iterator[Ops003Run]:
    """OPS-003's Action: a process dies mid-attempt and another finishes the job.

    Every process writes into one ``.jsonl`` file named by ``COSMA_LOG_FILE``, which
    is the transport choice the scenario leaves open; the rationale is recorded on
    ``config._log_file``. The workers all run to completion before the API starts, so
    no two processes append at once and the file's order is the timeline's order.
    """
    log_file = tmp_path_factory.mktemp("ops-003") / "platform.jsonl"
    with owned_database(platform_database, migrated_template, request) as owned:
        # 1. A job whose handler applies its effect and then ends its own process.
        job_id = owned.store.create_job(
            "halt_after_effect", {"halt_on_attempt": 1}, max_attempts=MAX_ATTEMPTS
        )

        # 2. Let a worker claim it, apply the effect, and die.
        interrupted = logged_worker(owned.config, log_file)
        assert interrupted.returncode == DEFAULT_EXIT_CODE, interrupted.stderr

        # 3. Let the lease expire, then let a second worker reclaim and finish it.
        wait_until(
            lambda: lease_has_expired(owned.connection, job_id),
            "the lease of the interrupted worker has expired",
        )
        recovered = logged_worker(owned.config, log_file)
        assert recovered.returncode == EXIT_OK, recovered.stderr

        # The control: a second, unrelated job whose events land in the same log.
        other_job_id = owned.store.create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
        unrelated = logged_worker(owned.config, log_file)
        assert unrelated.returncode == EXIT_OK, unrelated.stderr

        with (
            running_api(owned.config, COSMA_LOG_FILE=str(log_file)) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            # 4. Read the job and its attempts, and note the correlation identifier.
            job = fetch(client, f"/jobs/{job_id}")
            attempts = fetch(client, f"/jobs/{job_id}/attempts")
            correlation_id = job.json["correlation_id"]
            other = fetch(client, f"/jobs/{other_job_id}")

            append_foreign_event(log_file, correlation_id, job_id)

            # 5. Ask the API for the structured events carrying that identifier.
            events = fetch(client, "/events", correlation_id=correlation_id)
            other_events = fetch(client, "/events", correlation_id=other.json["correlation_id"])
            unknown_events = fetch(client, "/events", correlation_id=UNKNOWN_CORRELATION)

        yield Ops003Run(
            job_id=job_id,
            correlation_id=correlation_id,
            other_job_id=other_job_id,
            other_correlation_id=other.json["correlation_id"],
            job=job,
            attempts=attempts,
            events=events,
            other_events=other_events,
            unknown_events=unknown_events,
            log_file=log_file,
            effects_for_job=len(effects_of(owned.connection, job_id)),
            effects_total=len(all_effects(owned.connection)),
            interrupted=interrupted,
            recovered=recovered,
        )


def test_ops_003_one_identifier_returns_the_events_of_both_processes(
    ops_003_run: Ops003Run,
) -> None:
    """Invariant I5 across a boundary no in-memory context survives.

    A run in which only one process's events came back would satisfy every other
    assertion here, so the two ``worker_id`` values are asserted directly.
    """
    assert ops_003_run.events.status_code == 200, ops_003_run.events.body
    assert ops_003_run.records, "the correlated history is not empty"
    assert {record["correlation_id"] for record in ops_003_run.records} == {
        ops_003_run.correlation_id
    }
    workers = {record["worker_id"] for record in ops_003_run.records if record.get("worker_id")}
    assert len(workers) == 2, workers


def test_ops_003_the_five_questions_are_answered_from_the_correlated_events_alone(
    ops_003_run: Ops003Run,
) -> None:
    """Step 6, entirely out of step 5's response."""
    claims = [
        record
        for record in ops_003_run.named("job.transition")
        if record["to_state"] == JobState.RUNNING
    ]

    # 1. How many attempts there were.
    assert [record["attempt_no"] for record in claims] == [1, 2]

    # 2. Which one was abandoned, and why.
    abandoned = ops_003_run.named("job.attempt_abandoned")
    assert len(abandoned) == 1, abandoned
    assert abandoned[0]["attempt_no"] == 1
    assert abandoned[0]["error_class"] == ErrorClass.LEASE_ABANDONED

    # 3. Which process ran each.
    first, second = (record["worker_id"] for record in claims)
    assert first != second
    assert abandoned[0]["reclaimed_by"] == second

    # 4. Whether a durable effect was applied more than once.
    assert len(ops_003_run.named("job.effect_applied")) == 1
    assert len(ops_003_run.named("job.effect_suppressed")) == 1

    # 5. How the job ended.
    terminal = [
        record
        for record in ops_003_run.named("job.transition")
        if record["to_state"] == JobState.SUCCEEDED
    ]
    assert len(terminal) == 1, terminal
    assert terminal[0]["attempt_no"] == 2


def test_ops_003_the_suppression_event_names_the_effect_key(ops_003_run: Ops003Run) -> None:
    """The clause "found the effect already applied" needs the key to be legible."""
    suppressed = ops_003_run.named("job.effect_suppressed")[0]
    assert suppressed["effect_key"] == f"job/{ops_003_run.job_id}"
    assert suppressed["job_id"] == str(ops_003_run.job_id)


def test_ops_003_the_recovery_needed_no_operator_action(ops_003_run: Ops003Run) -> None:
    """A job that recovered by itself must not read as one awaiting attention."""
    triggers = [record.get("trigger") for record in ops_003_run.named("job.transition")]
    assert "operator safe retry" not in triggers, triggers
    assert ops_003_run.named("api.retry_accepted") == []
    assert ops_003_run.job.json["state"] == JobState.SUCCEEDED
    assert ops_003_run.job.json["terminal_reason"] is None


def test_ops_003_an_unrelated_jobs_events_are_in_the_log_and_not_in_the_answer(
    ops_003_run: Ops003Run,
) -> None:
    """The control. Without it, a filter that returned everything would pass."""
    assert ops_003_run.other_correlation_id != ops_003_run.correlation_id
    other: list[dict[str, Any]] = ops_003_run.other_events.json["events"]
    assert other, "the unrelated job's events really are in the log"

    text = ops_003_run.events.text
    assert ops_003_run.other_correlation_id not in text
    assert str(ops_003_run.other_job_id) not in text


def test_ops_003_exactly_one_durable_effect_survives_the_process_death(
    ops_003_run: Ops003Run,
) -> None:
    """I1 at the point where at-least-once delivery is actually dangerous.

    One row for the recovered job, and two in the table — the control job applied
    one of its own. Both counts matter: a duplicate written under a different key
    would satisfy the first and be caught by the second.
    """
    assert ops_003_run.effects_for_job == 1
    assert ops_003_run.effects_total == 2


def test_ops_003_values_under_redacted_keys_are_masked_in_the_returned_events(
    ops_003_run: Ops003Run,
) -> None:
    """SEC-004 through the event route, with the API as the boundary.

    The line under test was written past the platform's own logger, so this is an
    assertion about the response rather than about the writer. The ordinary marker
    survives, which is what makes the masking an observation and not an absence.
    """
    foreign = ops_003_run.named(FOREIGN_EVENT)
    assert len(foreign) == 1, foreign
    line = foreign[0]
    assert line["api_key"] != SENSITIVE_MARKER
    assert line["note"] == ORDINARY_MARKER, "detection control failed"
    assert SENSITIVE_MARKER not in ops_003_run.events.text
    assert PROTECTED_FIELD not in line, "the event route is not a second way in"
    assert line["error_detail_present"] is True


def test_ops_003_an_unknown_correlation_id_is_an_empty_history_not_a_failure(
    ops_003_run: Ops003Run,
) -> None:
    """A correlation identifier is a query value, not a stored identity to 404 on."""
    assert ops_003_run.unknown_events.status_code == 200, ops_003_run.unknown_events.body
    assert ops_003_run.unknown_events.json["returned"] == 0
    assert ops_003_run.unknown_events.json["events"] == []


# --------------------------------------------------------------------------- #
# OPS-004 — is anything wrong at all?
# --------------------------------------------------------------------------- #

#: Jobs step 3 runs to completion. Several, so that a transition count is a count.
OPS_004_SUCCEEDING_JOBS: Final = 3


@dataclass(frozen=True)
class Ops004Run:
    """Health and metrics at each of the scenario's five steps."""

    # Step 1 — nothing running, nothing queued.
    health_empty: Fetched
    health_empty_again: Fetched
    metrics_empty: Fetched
    # Step 2 — a database that is not there, and then is.
    absent_name: str
    metrics_before_recovery: Fetched
    health_absent: Fetched
    health_recovered: Fetched
    metrics_after_recovery: Fetched
    absent_api: subprocess.CompletedProcess[str]
    # Steps 3 and 4 — work run, then one failure.
    report_succeeded: dict[str, Any]
    report_failed: dict[str, Any]
    metrics_after_work: Fetched
    metrics_after_failure: Fetched
    # Step 5 — a queue nobody is working on.
    health_pending: Fetched

    @property
    def transitions_succeeded(self) -> Mapping[str, int]:
        counted: Mapping[str, int] = self.report_succeeded["metrics"]["transitions"]
        return counted

    @property
    def transitions_failed(self) -> Mapping[str, int]:
        counted: Mapping[str, int] = self.report_failed["metrics"]["transitions"]
        return counted

    def absent_api_events(self, event: str) -> list[dict[str, Any]]:
        return [record for record in log_events(self.absent_api.stderr) if record["event"] == event]


@pytest.fixture(scope="module")
def ops_004_run(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[Ops004Run]:
    """OPS-004's five steps against API processes that are never restarted.

    Step 2 is done by pointing a second API at a database that does not exist and
    then creating it, rather than by stopping the cluster — which the scenario
    permits, and which is the only safe choice here because the cluster is shared
    with every other test in the run. Creating the database afterwards is also what
    makes "health returns to healthy without an API restart" observable at all: a
    process configured for a name that never appears could not recover.
    """
    absent_name = f"cosma_p0_ops004_{os.getpid()}_{uuid4().hex[:8]}"
    with owned_database(platform_database, migrated_template, request) as owned:
        with (
            running_api(owned.config) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            # 1. No worker, no jobs.
            health_empty = fetch(client, "/health")
            health_empty_again = fetch(client, "/health")
            metrics_empty = fetch(client, "/metrics")

            # 2. A database that is not reachable, then the same process after it is.
            try:
                with (
                    running_api(replace(owned.config, db_name=absent_name)) as absent_api,
                    httpx.Client(
                        base_url=absent_api.base_url, timeout=REQUEST_TIMEOUT_SECONDS
                    ) as absent_client,
                ):
                    metrics_before_recovery = fetch(absent_client, "/metrics")
                    health_absent = fetch(absent_client, "/health")
                    create_clone(owned.config, absent_name, migrated_template)
                    health_recovered = fetch(absent_client, "/health")
                    metrics_after_recovery = fetch(absent_client, "/metrics")
            finally:
                drop_clone(owned.config, absent_name)

            # 3. Several jobs, run to completion by one worker.
            for index in range(OPS_004_SUCCEEDING_JOBS):
                owned.store.create_job(
                    "succeed", {**MARKED_PAYLOAD, "index": index}, max_attempts=MAX_ATTEMPTS
                )
            succeeded = run_worker(
                owned.config,
                "--max-jobs",
                str(OPS_004_SUCCEEDING_JOBS),
                "--max-seconds",
                WORKER_BUDGET_SECONDS,
                COSMA_POLL_MS=FAST_POLL_MS,
            )
            assert succeeded.returncode == EXIT_OK, succeeded.stderr
            metrics_after_work = fetch(client, "/metrics")

            # 4. One job driven to FAILED.
            owned.store.create_job("fail_permanent", {}, max_attempts=MAX_ATTEMPTS)
            failed = run_worker(owned.config, "--once", COSMA_POLL_MS=FAST_POLL_MS)
            assert failed.returncode == EXIT_OK, failed.stderr
            metrics_after_failure = fetch(client, "/metrics")

            # 5. A job left PENDING with no worker running.
            owned.store.create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
            health_pending = fetch(client, "/health")

        yield Ops004Run(
            health_empty=health_empty,
            health_empty_again=health_empty_again,
            metrics_empty=metrics_empty,
            absent_name=absent_name,
            metrics_before_recovery=metrics_before_recovery,
            health_absent=health_absent,
            health_recovered=health_recovered,
            metrics_after_recovery=metrics_after_recovery,
            absent_api=absent_api.collected(),
            report_succeeded=parse_report(succeeded.stdout),
            report_failed=parse_report(failed.stdout),
            metrics_after_work=metrics_after_work,
            metrics_after_failure=metrics_after_failure,
            health_pending=health_pending,
        )


def test_ops_004_step_1_is_healthy_with_a_reachable_database_and_zeroed_counters(
    ops_004_run: Ops004Run,
) -> None:
    assert ops_004_run.health_empty.status_code == 200, ops_004_run.health_empty.body
    health = ops_004_run.health_empty.json
    assert health["status"] == HEALTHY
    assert health["database"] == REACHABLE
    assert health["jobs_by_state"] == dict.fromkeys(JOB_STATES, 0)

    metrics = ops_004_run.metrics_empty.json["metrics"]
    assert metrics["transitions"] == dict.fromkeys(JOB_STATES, 0)
    assert metrics["claim_conflicts"] == 0
    assert metrics["suppressed_duplicate_effects"] == 0
    assert metrics["abandoned_attempts"] == 0
    assert metrics["rejected_completions"] == 0
    # A zero total stays distinguishable from no observations, as the scenario asks.
    assert metrics["attempt_duration_ms"]["count"] == 0
    assert metrics["lease_recovery_latency_ms"]["count"] == 0


def test_ops_004_reading_health_twice_returns_the_same_answer(ops_004_run: Ops004Run) -> None:
    """Repeated reads of one state agree, and neither created anything to disagree about."""
    assert ops_004_run.health_empty_again.json == ops_004_run.health_empty.json
    assert ops_004_run.health_empty_again.json["jobs_by_state"] == dict.fromkeys(JOB_STATES, 0)


def test_ops_004_step_2_reports_unhealthy_and_the_reason_names_the_database(
    ops_004_run: Ops004Run,
) -> None:
    """The load-bearing assertion: what separates platform health from API liveness."""
    assert ops_004_run.health_absent.status_code == 503, ops_004_run.health_absent.body
    body = ops_004_run.health_absent.json
    assert body["status"] == UNHEALTHY
    assert body["database"] == UNREACHABLE
    assert body["database_name"] == ops_004_run.absent_name
    assert ops_004_run.absent_name in body["error_summary"], body["error_summary"]
    assert "internal error" not in body["error_summary"].lower()


def test_ops_004_health_returns_to_healthy_without_an_api_restart(
    ops_004_run: Ops004Run,
) -> None:
    """The same process, before and after.

    An API that had to be restarted to notice recovery would turn a transient fault
    into an outage, so the process identity is compared rather than assumed.
    ``/metrics`` answers without a database, so its ``pid`` is readable on both sides
    of the outage, and the startup event says the process was started exactly once.
    """
    assert ops_004_run.health_recovered.status_code == 200, ops_004_run.health_recovered.body
    assert ops_004_run.health_recovered.json["status"] == HEALTHY
    pid = ops_004_run.metrics_before_recovery.json["pid"]
    assert ops_004_run.metrics_after_recovery.json["pid"] == pid
    started = ops_004_run.absent_api_events("api.started")
    assert len(started) == 1, "the API was started once and never restarted"
    assert started[0]["pid"] == pid


def test_ops_004_an_unhealthy_result_is_logged_with_its_reason(ops_004_run: Ops004Run) -> None:
    """So an operator who was not watching can still find out when it started."""
    failures = ops_004_run.absent_api_events("api.health_failed")
    assert len(failures) == 1, failures
    assert failures[0]["database"] == ops_004_run.absent_name
    assert ops_004_run.absent_name in failures[0]["error_summary"]


def test_ops_004_step_3_transition_counts_match_the_jobs_actually_run(
    ops_004_run: Ops004Run,
) -> None:
    """Read from the worker's shutdown report, because those are the counters that moved.

    Metrics are per process and in memory. The jobs were run by a worker, so its
    report is where their transitions are; ``/metrics`` on the API reports the API's
    own counters, which is the limitation the scenario records and the test below
    measures rather than assumes.
    """
    assert ops_004_run.report_succeeded["jobs_executed"] == OPS_004_SUCCEEDING_JOBS
    assert ops_004_run.transitions_succeeded == {
        JobState.PENDING: 0,
        JobState.RUNNING: OPS_004_SUCCEEDING_JOBS,
        JobState.SUCCEEDED: OPS_004_SUCCEEDING_JOBS,
        JobState.FAILED: 0,
    }


def test_ops_004_step_4_moves_the_failed_count_by_exactly_one(ops_004_run: Ops004Run) -> None:
    assert ops_004_run.transitions_succeeded[JobState.FAILED] == 0
    assert ops_004_run.transitions_failed[JobState.FAILED] == 1
    assert ops_004_run.transitions_failed[JobState.SUCCEEDED] == 0
    assert ops_004_run.report_failed["jobs_executed"] == 1


def test_ops_004_a_control_counter_stays_at_zero_across_steps_3_and_4(
    ops_004_run: Ops004Run,
) -> None:
    """A metrics surface that incremented everything would be caught here.

    No claim conflict can occur in a single-worker run, and nothing was abandoned or
    refused, so these counters must not have moved at all.
    """
    for report in (ops_004_run.report_succeeded, ops_004_run.report_failed):
        metrics = report["metrics"]
        assert metrics["claim_conflicts"] == 0, report
        assert metrics["abandoned_attempts"] == 0, report
        assert metrics["rejected_completions"] == 0, report
        assert metrics["lease_recovery_latency_ms"]["count"] == 0, report


def test_ops_004_the_api_metrics_are_this_process_only(ops_004_run: Ops004Run) -> None:
    """The recorded limitation, measured rather than taken from the code.

    A worker drove four jobs to terminal states between these readings and the API's
    counters did not move, because they are a different process's memory. A
    fleet-wide view needs an aggregation P0-A does not have.
    """
    for reading in (ops_004_run.metrics_after_work, ops_004_run.metrics_after_failure):
        assert reading.json["metrics"]["transitions"] == dict.fromkeys(JOB_STATES, 0)
        assert reading.json["pid"] == ops_004_run.metrics_empty.json["pid"]


def test_ops_004_no_metric_label_carries_a_payload_derived_value(
    ops_004_run: Ops004Run,
) -> None:
    """SEC-004. The step-3 jobs carried markers under a redacted and an ordinary key."""
    for reading in (
        ops_004_run.metrics_empty,
        ops_004_run.metrics_after_work,
        ops_004_run.metrics_after_failure,
    ):
        assert set(reading.json["metrics"]["transitions"]) == set(JOB_STATES)
        assert SENSITIVE_MARKER not in reading.text
        assert ORDINARY_MARKER not in reading.text
    worker_metrics = json.dumps(ops_004_run.report_succeeded["metrics"])
    assert SENSITIVE_MARKER not in worker_metrics
    assert ORDINARY_MARKER not in worker_metrics


def test_ops_004_step_5_is_healthy_but_does_not_read_as_an_empty_queue(
    ops_004_run: Ops004Run,
) -> None:
    """P0-A defines no worker liveness expectation, so a waiting queue is healthy.

    What it must not be is indistinguishable from an empty one. The platform still
    cannot tell an operator that no worker is running — only that nothing has been
    claimed — and that gap is the scenario's recorded limitation rather than
    something this assertion closes.
    """
    assert ops_004_run.health_pending.status_code == 200
    pending = ops_004_run.health_pending.json
    assert pending["status"] == HEALTHY
    assert pending["jobs_by_state"][JobState.PENDING] == 1
    assert pending["jobs_by_state"] != ops_004_run.health_empty.json["jobs_by_state"]


# ---------------------------------------------------------------------------
# Evidence capture
# ---------------------------------------------------------------------------
#
# OPS-003 names its evidence location and says the captured event set is "the
# artifact the gate reviewer would otherwise have to take on trust". Writing it
# from the fixture that the assertions above run against is what keeps the two
# from disagreeing: an artifact produced by a separate collector can drift from
# the code that was asserted, and a reviewer has no way to tell.


def evidence_directory() -> Path:
    """The single directory named for the revision under review, or None."""
    root = EXPERIMENT_ROOT / "evidence"
    if not root.is_dir():
        return root / "absent"
    dated = sorted(child for child in root.iterdir() if child.is_dir())
    return dated[-1] if dated else root / "absent"


def test_ops_003_the_evidence_artifacts_are_written(ops_003_run: Ops003Run) -> None:
    """Write the correlated event set and the log it came from.

    Regenerated on every run of this module, so neither file can describe behaviour
    the assertions above did not check. The assertions remain the authority.
    """
    target = evidence_directory()
    if not target.is_dir():
        pytest.skip(f"no evidence directory at {target}")

    payload = {
        "captured_from": "experiments/integrated-p0/tests/test_ops.py::ops_003_run",
        "job_id": str(ops_003_run.job_id),
        "correlation_id": ops_003_run.correlation_id,
        "response": ops_003_run.events.json,
        "job": ops_003_run.job.json,
        "attempts": ops_003_run.attempts.json,
        "control": {
            "job_id": str(ops_003_run.other_job_id),
            "correlation_id": ops_003_run.other_correlation_id,
            "events_returned_by_its_own_identifier": len(
                ops_003_run.other_events.json["events"]
            ),
            "present_in_this_response": any(
                record.get("job_id") == str(ops_003_run.other_job_id)
                for record in ops_003_run.records
            ),
        },
        "unknown_identifier_returned": len(ops_003_run.unknown_events.json["events"]),
    }
    (target / "ops-003-correlated-events.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (target / "platform.jsonl").write_text(
        ops_003_run.log_file.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # The capture is evidence only if it carries what was asserted, and hides what
    # SEC-004 requires hidden.
    written = (target / "ops-003-correlated-events.json").read_text(encoding="utf-8")
    assert ops_003_run.correlation_id in written
    assert SENSITIVE_MARKER not in written
    assert payload["control"]["present_in_this_response"] is False
