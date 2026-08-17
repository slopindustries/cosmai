"""The schema of CONTRACT-JOB@0.1, and the connection that reaches it.

Everything here is deliberately SQL against a real cluster. No state machine, no
claim query, and no handler exists yet — the point of this file is to establish
which of the contract's invariants hold **without** application code, so that when
T1.3 writes that code a failure can be attributed to the code rather than to the
schema underneath it.

The sharpest of those is I2. A job may never have two ``job_attempt`` rows with
``finished_at IS NULL``, and a partial unique index makes the second insert fail
in the database. That leaves the invariant's other half — the fencing rule that
refuses a stale worker's late completion — as something the application still
owes, and JOB-006 is where it is paid. Neither half implies the other, so this
file proves the half it can and says which one it did not.

Isolation is tested here rather than assumed, because every other test in this
tree depends on it. ``test_isolation_holds_under_parallel_workers`` writes a value
that is constant across its parameters: if two of them ever shared a database, the
second write would collide on a primary key instead of quietly passing.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from platform_core.config import PlatformConfig
from platform_core.db.connection import connect, connected, connection_parameters
from platform_core.errors import ConfigurationInvalidError
from psycopg import errors
from psycopg.types.json import Jsonb

INSERT_JOB = (
    "insert into job (id, handler, payload, state, max_attempts, correlation_id) "
    "values (%s, %s, %s, %s, %s, %s)"
)

INSERT_ATTEMPT = (
    "insert into job_attempt (id, job_id, attempt_no, worker_id, correlation_id) "
    "values (%s, %s, %s, %s, %s)"
)

CLOSE_ATTEMPT = "update job_attempt set finished_at = now(), outcome = %s where id = %s"

INSERT_EFFECT = "insert into platform_effect (effect_key, job_id, payload) values (%s, %s, %s)"

DESCRIBE_COLUMNS = (
    "select column_name, data_type, is_nullable, column_default "
    "from information_schema.columns "
    "where table_schema = 'public' and table_name = %s"
)

TIMESTAMP = "timestamp with time zone"

# (data type, is_nullable) per the contract's "Schema or message shape" tables.
JOB_COLUMNS = {
    "id": ("uuid", "NO"),
    "handler": ("text", "NO"),
    # Required, though JSON `null` is a legal value for it.
    "payload": ("jsonb", "NO"),
    "state": ("text", "NO"),
    "attempt_count": ("integer", "NO"),
    "max_attempts": ("integer", "NO"),
    "available_at": (TIMESTAMP, "NO"),
    "lease_owner": ("text", "YES"),
    "lease_expires_at": (TIMESTAMP, "YES"),
    "terminal_reason": ("text", "YES"),
    "correlation_id": ("text", "NO"),
    "created_at": (TIMESTAMP, "NO"),
    "updated_at": (TIMESTAMP, "NO"),
}

ATTEMPT_COLUMNS = {
    "id": ("uuid", "NO"),
    "job_id": ("uuid", "NO"),
    "attempt_no": ("integer", "NO"),
    "worker_id": ("text", "NO"),
    "started_at": (TIMESTAMP, "NO"),
    "finished_at": (TIMESTAMP, "YES"),
    "outcome": ("text", "YES"),
    "error_class": ("text", "YES"),
    "error_summary": ("text", "YES"),
    "error_detail": ("jsonb", "YES"),
    "correlation_id": ("text", "NO"),
}

EFFECT_COLUMNS = {
    "effect_key": ("text", "NO"),
    "job_id": ("uuid", "NO"),
    "applied_at": (TIMESTAMP, "NO"),
    "payload": ("jsonb", "YES"),
}

# Every timestamp the contract says the database generates.
DATABASE_CLOCK_COLUMNS = (
    ("job", "available_at"),
    ("job", "created_at"),
    ("job", "updated_at"),
    ("job_attempt", "started_at"),
    ("platform_effect", "applied_at"),
)

STATES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")

OUTCOMES = ("SUCCEEDED", "RETRYABLE_FAILURE", "PERMANENT_FAILURE", "ABANDONED")

Connection = psycopg.Connection[Any]


def add_job(
    handle: Connection,
    handler: str = "succeed",
    state: str = "PENDING",
    max_attempts: int = 3,
    payload: Any = None,
) -> UUID:
    job_id = uuid4()
    handle.execute(
        INSERT_JOB,
        (job_id, handler, Jsonb(payload), state, max_attempts, f"corr-{job_id}"),
    )
    return job_id


def open_attempt(handle: Connection, job_id: UUID, attempt_no: int = 1, worker: str = "w1") -> UUID:
    attempt_id = uuid4()
    handle.execute(INSERT_ATTEMPT, (attempt_id, job_id, attempt_no, worker, f"corr-{job_id}"))
    return attempt_id


def columns_of(handle: Connection, table: str) -> dict[str, tuple[str, str]]:
    rows = handle.execute(DESCRIBE_COLUMNS, (table,)).fetchall()
    return {str(row[0]): (str(row[1]), str(row[2])) for row in rows}


def default_of(handle: Connection, table: str, column: str) -> str | None:
    for row in handle.execute(DESCRIBE_COLUMNS, (table,)).fetchall():
        if str(row[0]) == column:
            return None if row[3] is None else str(row[3])
    raise AssertionError(f"{table}.{column} does not exist")


def one(handle: Connection, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
    row = handle.execute(statement, parameters).fetchone()
    assert row is not None
    return row[0]


# --------------------------------------------------------------------------- shape


@pytest.mark.parametrize(
    ("table", "expected"),
    [("job", JOB_COLUMNS), ("job_attempt", ATTEMPT_COLUMNS), ("platform_effect", EFFECT_COLUMNS)],
)
def test_each_table_has_exactly_the_contract_fields(
    db_connection: Connection,
    table: str,
    expected: dict[str, tuple[str, str]],
) -> None:
    """Equality, not containment: an extra column is a schema the contract did not fix."""
    assert columns_of(db_connection, table) == expected


@pytest.mark.parametrize(("table", "column"), DATABASE_CLOCK_COLUMNS)
def test_timestamps_default_to_the_database_clock(
    db_connection: Connection,
    table: str,
    column: str,
) -> None:
    """"Ordering, time, and identity": an application clock cannot decide a lease."""
    assert default_of(db_connection, table, column) == "now()"


def test_a_row_written_without_timestamps_gets_them_from_the_database(
    db_connection: Connection,
) -> None:
    job_id = add_job(db_connection)
    row = db_connection.execute(
        "select created_at, now() - created_at from job where id = %s", (job_id,)
    ).fetchone()
    assert row is not None
    created, skew = row[0], row[1]
    assert created.tzinfo is not None
    assert skew.total_seconds() >= 0


def test_the_attempt_budget_floor_is_a_database_constraint(db_connection: Connection) -> None:
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        add_job(db_connection, max_attempts=0)


def test_attempt_count_may_not_exceed_the_budget(db_connection: Connection) -> None:
    """I4, held by the database so that a state machine defect surfaces at the write."""
    job_id = add_job(db_connection, max_attempts=2)
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        db_connection.execute("update job set attempt_count = 3 where id = %s", (job_id,))


# ----------------------------------------------------------------------- enumerations


@pytest.mark.parametrize("state", STATES)
def test_every_contract_state_is_accepted(db_connection: Connection, state: str) -> None:
    job_id = add_job(db_connection)
    lease = "w1" if state == "RUNNING" else None
    expires = "now() + interval '30 seconds'" if state == "RUNNING" else "null"
    reason = "'PLATFORM_PERMANENT'" if state == "FAILED" else "null"
    db_connection.execute(
        "update job set state = %s, lease_owner = %s, "
        f"lease_expires_at = {expires}, terminal_reason = {reason} where id = %s",
        (state, lease, job_id),
    )
    assert one(db_connection, "select state from job where id = %s", (job_id,)) == state


@pytest.mark.parametrize("state", ["pending", "QUEUED", "CANCELLED", ""])
def test_a_state_outside_the_contract_is_refused(db_connection: Connection, state: str) -> None:
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        add_job(db_connection, state=state)


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_every_contract_outcome_is_accepted(db_connection: Connection, outcome: str) -> None:
    job_id = add_job(db_connection)
    attempt_id = open_attempt(db_connection, job_id)
    db_connection.execute(CLOSE_ATTEMPT, (outcome, attempt_id))
    assert one(db_connection, "select outcome from job_attempt where id = %s", (attempt_id,)) == (
        outcome
    )


def test_an_outcome_outside_the_contract_is_refused(db_connection: Connection) -> None:
    job_id = add_job(db_connection)
    attempt_id = open_attempt(db_connection, job_id)
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        db_connection.execute(CLOSE_ATTEMPT, ("CANCELLED", attempt_id))


def test_an_attempt_may_not_close_without_saying_how(db_connection: Connection) -> None:
    """A closed attempt with no outcome would still read as open to the I2 index."""
    job_id = add_job(db_connection)
    attempt_id = open_attempt(db_connection, job_id)
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        db_connection.execute(
            "update job_attempt set finished_at = now() where id = %s", (attempt_id,)
        )


# -------------------------------------------------------------------------- invariants


def test_i2_a_job_may_not_have_two_open_attempts(db_connection: Connection) -> None:
    """I2, proved with SQL alone. No worker, no lease, no application code."""
    job_id = add_job(db_connection)
    open_attempt(db_connection, job_id, attempt_no=1, worker="w1")
    with pytest.raises(errors.UniqueViolation), db_connection.transaction():
        open_attempt(db_connection, job_id, attempt_no=2, worker="w2")


def test_i2_permits_a_new_attempt_once_the_previous_one_is_closed(
    db_connection: Connection,
) -> None:
    """The index is partial. A reclaim closes the abandoned attempt, then opens one."""
    job_id = add_job(db_connection)
    first = open_attempt(db_connection, job_id, attempt_no=1, worker="w1")
    db_connection.execute(CLOSE_ATTEMPT, ("ABANDONED", first))
    open_attempt(db_connection, job_id, attempt_no=2, worker="w2")
    assert one(db_connection, "select count(*) from job_attempt where job_id = %s", (job_id,)) == 2


def test_i2_constrains_one_job_and_not_the_table(db_connection: Connection) -> None:
    """Two different jobs may each have an open attempt at the same instant."""
    first = add_job(db_connection)
    second = add_job(db_connection)
    open_attempt(db_connection, first)
    open_attempt(db_connection, second)
    assert one(db_connection, "select count(*) from job_attempt where finished_at is null") == 2


def test_attempt_numbers_are_unique_within_a_job(db_connection: Connection) -> None:
    job_id = add_job(db_connection)
    first = open_attempt(db_connection, job_id, attempt_no=1)
    db_connection.execute(CLOSE_ATTEMPT, ("RETRYABLE_FAILURE", first))
    with pytest.raises(errors.UniqueViolation), db_connection.transaction():
        open_attempt(db_connection, job_id, attempt_no=1)


def test_i1_a_repeated_effect_key_is_refused(db_connection: Connection) -> None:
    """The database half of I1. The handler owns the other half: a stable key."""
    job_id = add_job(db_connection)
    db_connection.execute(INSERT_EFFECT, ("effect-1", job_id, Jsonb({"n": 1})))
    with pytest.raises(errors.UniqueViolation), db_connection.transaction():
        db_connection.execute(INSERT_EFFECT, ("effect-1", job_id, Jsonb({"n": 2})))


def test_an_effect_key_is_independent_of_the_attempt_that_wrote_it(
    db_connection: Connection,
) -> None:
    """A retried job keeps its identity and reproduces its key; that is what I1 tests."""
    job_id = add_job(db_connection)
    first = open_attempt(db_connection, job_id, attempt_no=1)
    db_connection.execute(INSERT_EFFECT, ("stable-key", job_id, Jsonb(None)))
    db_connection.execute(CLOSE_ATTEMPT, ("RETRYABLE_FAILURE", first))
    open_attempt(db_connection, job_id, attempt_no=2)
    with pytest.raises(errors.UniqueViolation), db_connection.transaction():
        db_connection.execute(INSERT_EFFECT, ("stable-key", job_id, Jsonb(None)))
    assert one(db_connection, "select count(*) from platform_effect") == 1


def test_an_effect_must_name_a_job_that_exists(db_connection: Connection) -> None:
    with pytest.raises(errors.ForeignKeyViolation), db_connection.transaction():
        db_connection.execute(INSERT_EFFECT, ("orphan", uuid4(), Jsonb(None)))


def test_a_payload_may_be_json_null_but_not_a_missing_column(
    db_connection: Connection,
) -> None:
    """The contract's "Explicit null": JSON null is a value the platform passes on."""
    job_id = add_job(db_connection, payload=None)
    assert one(db_connection, "select payload from job where id = %s", (job_id,)) is None
    assert one(db_connection, "select payload is null from job where id = %s", (job_id,)) is False
    with pytest.raises(errors.NotNullViolation), db_connection.transaction():
        db_connection.execute(
            "insert into job (id, handler, payload, state, max_attempts, correlation_id) "
            "values (%s, 'succeed', null, 'PENDING', 1, 'c')",
            (uuid4(),),
        )


def test_a_lease_belongs_to_a_running_job_and_to_no_other(db_connection: Connection) -> None:
    """The contract's "Not applicable" rule, held by the database."""
    job_id = add_job(db_connection)
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        db_connection.execute("update job set lease_owner = 'w1' where id = %s", (job_id,))


def test_a_terminal_reason_belongs_to_a_failed_job(db_connection: Connection) -> None:
    job_id = add_job(db_connection)
    db_connection.execute(
        "update job set state = 'SUCCEEDED', lease_owner = null, lease_expires_at = null "
        "where id = %s",
        (job_id,),
    )
    with pytest.raises(errors.CheckViolation), db_connection.transaction():
        db_connection.execute("update job set terminal_reason = 'x' where id = %s", (job_id,))


def test_the_claim_query_has_an_index_for_each_of_its_two_halves(
    db_connection: Connection,
) -> None:
    """One statement covers dispatch and recovery, so each predicate needs an index."""
    definitions = [
        str(row[0])
        for row in db_connection.execute(
            "select indexdef from pg_indexes where tablename = 'job'"
        ).fetchall()
    ]
    assert any("state = 'PENDING'" in text and "available_at" in text for text in definitions)
    assert any("state = 'RUNNING'" in text and "lease_expires_at" in text for text in definitions)


# ------------------------------------------------------------------------- connection


def test_a_connection_carries_no_credential(database: PlatformConfig) -> None:
    """DP-006 D2: a socket directory, a database, and a user. Nothing else exists."""
    parameters = connection_parameters(database)
    assert set(parameters) == {"host", "dbname", "user"}
    assert parameters["host"].startswith("/")


def test_the_connection_is_a_local_socket_with_no_network_peer(
    db_connection: Connection,
) -> None:
    """``listen_addresses = ''`` leaves no address for the server to report."""
    assert one(db_connection, "select inet_server_addr()") is None


def test_an_absent_database_is_a_configuration_failure(database: PlatformConfig) -> None:
    """It is not retryable: no amount of waiting creates the database."""
    absent = replace(database, db_name=f"{database.db_name}_absent")
    with pytest.raises(ConfigurationInvalidError) as raised:
        connect(absent)
    assert raised.value.retryable is False
    assert absent.db_name in raised.value.summary


def test_the_context_manager_closes_what_it_opened(database: PlatformConfig) -> None:
    with connected(database) as handle:
        assert handle.closed is False
    assert handle.closed is True


# -------------------------------------------------------------------------- isolation


@pytest.mark.parametrize("run", range(8))
def test_isolation_holds_under_parallel_workers(db_connection: Connection, run: int) -> None:
    """Each parameter writes the same key. A shared database would collide on it.

    This is the isolation half of DP-006 D3, and it is the assumption every other
    test in this tree rests on. Run it with ``-n 4`` and the parameters land on
    different processes at the same time, which is the case worth checking.
    """
    assert one(db_connection, "select current_database()").startswith("cosma_p0_test_")
    assert one(db_connection, "select count(*) from job") == 0
    job_id = add_job(db_connection, handler=f"run-{run}")
    db_connection.execute(INSERT_EFFECT, ("shared-if-isolation-fails", job_id, Jsonb(None)))
    db_connection.commit()
    assert one(db_connection, "select count(*) from job") == 1
    assert one(db_connection, "select handler from job") == f"run-{run}"
