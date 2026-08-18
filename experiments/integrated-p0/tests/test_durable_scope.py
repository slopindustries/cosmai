"""Enlisted durable work, and the P0-A gap it closes.

The [P0-A Completion Gate](../PLATFORM-CORE-GATE-2026-08-17.md) records as the first
thing it does not claim: *"Every duplicate-suppression result rests on one row and one
primary-key conflict. A P0-B acquisition or normalization effect spans several statements
and probably several tables, where the question becomes transactional. This is the sharp
form of OQ-006 H1 and the largest gap P0-A leaves."*

These tests are that gap, with a multi-statement effect and no key to deduplicate on.

The scenario that decides the design is the reclaimed worker. A worker that stalled past
its lease has had its work given to someone else; if it commits its writes and only then
meets the fence, both workers' rows are present and nothing can tell them apart. So the
completion goes **inside** the transaction and **last**, and its refusal discards the
writes rather than following them.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import pytest
from platform_core.errors import PlatformPermanentError, PlatformTransientError
from platform_core.jobs.registry import HandlerRegistry, JobContext
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("database")

WORKER = "worker-1"

#: A durable effect with no unique key to collide on — which is the shape the gate says
#: `platform_effect` could not represent. Two rows per run, so a partial write is
#: distinguishable from none and from two.
MULTI_STATEMENT = """
create table if not exists probe_effect (
    id     bigserial primary key,
    job_id uuid not null,
    part   text not null
)
"""


@pytest.fixture
def probe(connection: psycopg.Connection[Any]) -> None:
    connection.execute(MULTI_STATEMENT)


def rows(connection: psycopg.Connection[Any]) -> int:
    row = connection.execute("select count(*) from probe_effect").fetchone()
    return 0 if row is None else int(row[0])


def write_two(connection: psycopg.Connection[Any], job_id: UUID) -> None:
    for part in ("first", "second"):
        connection.execute(
            "insert into probe_effect (job_id, part) values (%s, %s)", (job_id, part)
        )


def run_one(
    store: JobStore, registry: HandlerRegistry, handler_name: str
) -> Any:
    job_id = store.create_job(handler_name, {"n": 1}, max_attempts=3)
    runner = JobRunner(store, registry, WORKER, lease_seconds=60)
    outcome = runner.run_once()
    assert outcome is not None and outcome.claimed.job_id == job_id
    return outcome


class TestEnlistedWorkCommitsWithTheCompletion:
    def test_a_multi_statement_effect_and_its_completion_both_land(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            context.enlist_durable_work(lambda: write_two(connection, context.job_id))

        registry.register("collect", handler)
        outcome = run_one(store, registry, "collect")

        assert outcome.accepted
        assert outcome.state is JobState.SUCCEEDED
        assert rows(connection) == 2

    def test_a_handler_that_enlists_nothing_takes_the_path_it_always_did(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        """P0-A's evidence is untouched by this change, and that is asserted rather than
        assumed."""
        registry = HandlerRegistry()
        registry.register("plain", lambda context: None)
        outcome = run_one(store, registry, "plain")

        assert outcome.accepted
        assert outcome.state is JobState.SUCCEEDED
        assert rows(connection) == 0


class TestTheFenceDiscardsTheWritesOfAWorkerThatLostItsLease:
    """The scenario the design exists for."""

    def test_a_reclaimed_worker_writes_nothing(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            # The lease is taken while this handler runs — exactly what a stall past the
            # lease deadline followed by a reclaim leaves behind.
            connection.execute(
                "update job set lease_owner = 'worker-2' where id = %s", (context.job_id,)
            )
            context.enlist_durable_work(lambda: write_two(connection, context.job_id))

        registry.register("collect", handler)
        outcome = run_one(store, registry, "collect")

        assert not outcome.accepted, "the fence should have refused this completion"
        assert rows(connection) == 0, "a refused completion must discard the writes"

    def test_the_same_handler_writes_when_the_lease_is_still_held(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        """The positive control. Without it the assertion above would pass against a
        runner that never ran enlisted work at all."""
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            context.enlist_durable_work(lambda: write_two(connection, context.job_id))

        registry.register("collect", handler)
        outcome = run_one(store, registry, "collect")

        assert outcome.accepted
        assert rows(connection) == 2

    def test_a_refusal_is_reported_as_a_value_rather_than_raised(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        """`run_once` reports what the store told it; that contract is unchanged.

        The rollback needs an exception internally, and this asserts it does not escape.
        """
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            connection.execute(
                "update job set lease_owner = 'worker-2' where id = %s", (context.job_id,)
            )
            context.enlist_durable_work(lambda: write_two(connection, context.job_id))

        registry.register("collect", handler)
        outcome = run_one(store, registry, "collect")  # must not raise
        assert outcome.completion.accepted is False


class TestEnlistedWorkThatFails:
    def test_a_failure_inside_enlisted_work_leaves_nothing_behind(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            def work() -> None:
                connection.execute(
                    "insert into probe_effect (job_id, part) values (%s, 'first')",
                    (context.job_id,),
                )
                raise PlatformTransientError("the second statement failed")

            context.enlist_durable_work(work)

        registry.register("collect", handler)
        runner = JobRunner(store, registry, WORKER, lease_seconds=60)
        store.create_job("collect", {"n": 1}, max_attempts=3)

        with pytest.raises(PlatformTransientError):
            runner.run_once()

        assert rows(connection) == 0, "a partial multi-statement effect must not survive"

    def test_a_handler_that_fails_before_enlisting_is_unaffected(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            raise PlatformPermanentError("refused before doing anything")

        registry.register("collect", handler)
        outcome = run_one(store, registry, "collect")

        assert outcome.state is JobState.FAILED
        assert rows(connection) == 0


class TestOrdering:
    def test_enlisted_work_runs_before_the_completion(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        """Order is the whole design: writes first, fence last.

        Reversed, the fence would pass and the writes could still fail — which is the
        arrangement the platform already had and the gate recorded as untested.
        """
        seen: list[str] = []
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            def work() -> None:
                row = connection.execute(
                    "select state from job where id = %s", (context.job_id,)
                ).fetchone()
                assert row is not None
                seen.append(str(row[0]))
                write_two(connection, context.job_id)

            context.enlist_durable_work(work)

        registry.register("collect", handler)
        run_one(store, registry, "collect")

        assert seen == [JobState.RUNNING.value], "the job was already completed too early"

    def test_several_enlisted_pieces_run_in_the_order_they_were_enlisted(
        self, store: JobStore, connection: psycopg.Connection[Any], probe: None
    ) -> None:
        order: list[int] = []
        registry = HandlerRegistry()

        def handler(context: JobContext) -> None:
            for n in range(3):
                context.enlist_durable_work(lambda n=n: order.append(n))  # type: ignore[misc]

        registry.register("collect", handler)
        run_one(store, registry, "collect")
        assert order == [0, 1, 2]
