"""The worker that actually hosts add-ons — `ADVERSARIAL-REVIEW-2026-08-18.md` F3.

The finding: *"`bind_capabilities` has three call sites, all in tests.
`platform_core/worker.py` never wires the capability layer at all."* Every claim EXP-003
made about a collector on the platform therefore rested on a test's own wiring, and the
place the real wiring would go was the place the shared-connection requirement was least
visible.

**Why the wiring is not in `platform_core/worker.py`.** DP-008 D1 says `platform_core`
gains no dependency on the add-on layer, and `tests/environment/test_addon_layer_direction.py`
enforces it: `platform_core` may import nothing local. A worker that imported
`addon_host.capabilities` and `domain.store` would fail that guard. So `platform_core.worker`
gained one source-neutral seam instead — `registry_for`, a callable handed the connection
that returns the handler table for it — and the add-on half lives here, in `addon_host`,
where DP-008 D1 already permits both imports.

`registry_for` is per *connection* and not per process on purpose. `Worker._reopen` replaces
the connection after a transient database failure, and a capability layer still holding the
previous connection's `DomainStore` would be exactly the mis-wiring F3 is about — the
`DomainStore` writing outside the transaction that completes the attempt. Rebuilding the
table with the connection makes that unrepresentable rather than merely tested.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import psycopg
import pytest
from addon_host.registration import HANDLER_PREFIX
from addon_host.worker import capability_registry, main
from domain.store import DomainStore
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.worker import EXIT_OK, Worker, WorkerOptions

from tests.conftest import worker_environment

pytestmark = pytest.mark.usefixtures("database")

#: The one add-on committed to `addons/`. Named rather than discovered, because a test that
#: asserted "some add-on was registered" would pass against an empty directory.
NAVER = "collector.naver.blog"

NAVER_HANDLER = f"{HANDLER_PREFIX}{NAVER}"


class RefusingTransport:
    """A transport that must never be reached. These cases all refuse before any request.

    A stub rather than the real `SocketTransport`, so that a wiring defect shows up as this
    assertion rather than as an outbound connection from a test run.
    """

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("no case in this module may reach the network")


def run_one_job(
    database: PlatformConfig,
    store: JobStore,
    handler: str,
    payload: Any,
) -> tuple[int, StringIO]:
    """Run one in-process worker pass over one job, and return its exit status and log."""
    job_id = store.create_job(handler, payload, max_attempts=1)
    log = StringIO()
    worker = Worker(
        database,
        WorkerOptions(once=True),
        StructuredLogger(stream=log, level="DEBUG"),
        registry_for=capability_registry(RefusingTransport()),
        report_stream=StringIO(),
    )
    code = worker.run()
    assert store.read_job(job_id) is not None
    return code, log


class TestTheAddOnWorkerBindsTheCapabilityLayer:
    def test_the_installed_add_on_is_registered_under_its_handler_name(
        self, connection: psycopg.Connection[Any]
    ) -> None:
        registry = capability_registry(RefusingTransport())(connection)
        assert NAVER_HANDLER in registry.names()

    def test_the_platform_handlers_are_still_registered_beside_it(
        self, connection: psycopg.Connection[Any]
    ) -> None:
        """The add-on table is added to the synthetic one, not substituted for it. A worker
        that lost `succeed` would break every P0-A scenario silently."""
        registry = capability_registry(RefusingTransport())(connection)
        assert "succeed" in registry.names()

    def test_a_collect_job_reaches_the_capability_layer_rather_than_the_stated_refusal(
        self, database: PlatformConfig, store: JobStore
    ) -> None:
        """The finding itself, as a behavioural assertion.

        `registration.capabilities_not_bound` is the default `Invoke` and fails a job with
        *"this host has no capability layer bound"*. Reaching `_require_source`'s refusal
        instead is what proves `bind_capabilities` is the one installed — and it is a
        refusal, so it needs no source row, no credential, and no socket.
        """
        code, _ = run_one_job(database, store, NAVER_HANDLER, {"source_id": "not-registered"})

        assert code == EXIT_OK
        attempts = store.read_attempts(store.list_jobs()[0]["id"])
        assert len(attempts) == 1
        assert attempts[0]["error_class"] == ErrorClass.PLATFORM_PERMANENT.value
        assert "no source named" in attempts[0]["error_summary"]
        assert "no capability layer bound" not in attempts[0]["error_summary"]

    def test_an_unregistered_handler_name_still_fails_as_handler_unknown(
        self, database: PlatformConfig, store: JobStore
    ) -> None:
        """The control for the case above: the registry is a real one and can still miss."""
        run_one_job(database, store, f"{HANDLER_PREFIX}collector.absent", {"source_id": "x"})

        attempts = store.read_attempts(store.list_jobs()[0]["id"])
        assert attempts[0]["error_class"] == ErrorClass.HANDLER_UNKNOWN.value


class TestTheTableIsRebuiltWithTheConnection:
    def test_each_connection_gets_a_domain_store_on_that_connection(
        self, database: PlatformConfig
    ) -> None:
        """`Worker._reopen` replaces the connection; the capability layer must follow it.

        Asserted through `capability_registry` rather than by reaching into the worker,
        because the property is that *the builder* is per connection.
        """
        build = capability_registry(RefusingTransport())
        with connected(database, autocommit=True) as first, connected(
            database, autocommit=True
        ) as second:
            assert build(first) is not build(second)
            assert DomainStore(first).connection is first
            assert DomainStore(second).connection is second


class TestTheEntrypoint:
    def test_the_process_entrypoint_runs_one_pass_and_exits_cleanly(
        self, database: PlatformConfig, store: JobStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`python -m addon_host.worker` is the P0-B entrypoint. Run in-process here; the
        subprocess form is exercised by the naver collector's real-data scenario."""
        for name, value in worker_environment(database).items():
            monkeypatch.setenv(name, value)
        store.create_job(NAVER_HANDLER, {"source_id": "not-registered"}, max_attempts=1)

        assert main(["--once"]) == EXIT_OK
        assert store.list_jobs()[0]["state"] == JobState.FAILED.value
