"""The capability layer's transactionality: buffered writes that end in one fence.

Copy-adapted from ``experiments/integrated-p0/tests/test_capabilities.py`` (M3
batch 3b), narrowed to the two classes the task packet names explicitly —
``TestACollectionIsAtomicThroughAnAddOn`` and
``TestTheDurableScopeRequirementIsChecked`` — plus the scaffolding they need
(``ScriptedTransport``, ``LeaseStealingTransport``, a synthetic ``collector.probe``
add-on, and ``run_collect``, the helper that drives one job through the real
``JobRunner`` rather than calling ``addon_host.capabilities`` directly, because the
property under test is the *transaction* the runner opens).

**What is deliberately not here.** P0's ``test_capabilities.py`` is 1750+ lines and
also covers refusal-cannot-be-swallowed, the page/record limits, the redirect
budget, credential attachment, and status handling — real evidence, but evidence
about ``domain.outbound``/``domain.transport`` policy that
``test_outbound_policy.py``/``test_outbound_transport.py`` already exercise
directly (M2 batch 2c), orchestrated here rather than reimplemented. This batch's
task packet named atomicity and the durable-scope check specifically; the rest is
flagged in ``docs/p1/M3-RECORD.md`` for the conformance suite (batch 3c) to weigh,
rather than silently expanded into here.

Fixture names follow this tree's convention: ``platform_config`` for P0's
``database``, ``job_store`` for ``store``, ``job_connection`` for ``connection``,
and ``domain_store`` (already built in ``apps/tests/conftest.py``, on the same
connection as ``job_store`` — the sharing P0's own ``domain`` fixture docstring
required) in place of a fixture this file would otherwise have to redefine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psycopg
import pytest

from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.outbound import OutboundProfile, PreparedRequest, Refusal
from domain.transport import TransportLimits, TransportResponse
from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("_migrations_applied")

WORKER = "worker-1"
ADDON_ID = "collector.probe"
ADDON_VERSION = "0.1.0"
HANDLER = f"addon:{ADDON_ID}"
SOURCE_ID = "probe"

MANIFEST = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[[config.field]]
name = "label"
type = "string"
required = false

[declares]
hosts = ["api.example.com"]
endpoints = ["items"]
streams = ["items"]
"""

#: The ordinary collector: one page, items out of it, a cursor, an honest count.
COLLECTOR = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {"page": "1"})
    body = json.loads(response.body)
    items = [
        RawItem(
            item_key=str(entry["id"]),
            payload=json.dumps(entry, sort_keys=True).encode("utf-8"),
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
        for entry in body["items"]
    ]
    context.emit_raw(items)
    context.advance_cursor("items", body["next"])
    context.log("page", {"count": len(items)})
    return CollectOutcome(items_emitted=len(items))
"""

PAGE = json.dumps({"items": [{"id": 1}, {"id": 2}], "next": 3}).encode("utf-8")


# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #


class ScriptedTransport:
    """One hop per scripted entry, in order. Records every request it was handed.

    A double rather than a socket because what these tests check — buffering, the
    transaction boundary — is not the socket. ``tests/test_outbound_transport.py``
    is where a real one runs.
    """

    def __init__(self, *scripted: TransportResponse | Refusal | BaseException) -> None:
        self.scripted = list(scripted)
        self.sent: list[PreparedRequest] = []

    def send(
        self,
        request: PreparedRequest,
        profile: OutboundProfile,
        headers: Any = None,
        limits: TransportLimits | None = None,
    ) -> TransportResponse | Refusal:
        self.sent.append(request)
        if not self.scripted:
            raise AssertionError(f"the run made an unscripted request to {request.url}")
        nxt = self.scripted.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class LeaseStealingTransport(ScriptedTransport):
    """Answers the request, and takes the lease while doing so.

    A stall past the lease deadline followed by a reclaim leaves exactly this: another
    worker owns the job, and this one is still holding a response it is about to write.
    The theft happens *inside* `send` because that is where a real collector spends the
    time it could stall in.
    """

    def __init__(self, connection: psycopg.Connection[Any], *scripted: Any) -> None:
        super().__init__(*scripted)
        self._connection = connection

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        self._connection.execute("update cosmai.job set lease_owner = 'worker-2'")
        return super().send(request, profile, headers, limits)


def a_page(body: bytes = PAGE, status: int = 200) -> TransportResponse:
    return TransportResponse(
        status=status,
        headers={"Content-Type": "application/json"},
        body=body,
        location=None,
        addresses=("203.0.113.7",),
    )


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def install(root: Path, source: str = COLLECTOR) -> Path:
    package = root / ADDON_ID
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(MANIFEST.format(addon_id=ADDON_ID), encoding="utf-8")
    (package / "handler.py").write_text(source, encoding="utf-8")
    return package


def a_source(**overrides: Any) -> SourceRow:
    values: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "addon_id": ADDON_ID,
        "addon_version": ADDON_VERSION,
        "kind": "collector",
        "config": {"label": "items"},
        "config_schema_version": "1",
        "outbound_profile": {
            "hosts": ["api.example.com"],
            "endpoints": {"items": "/v1/items"},
            "port": 443,
        },
    }
    values.update(overrides)
    return SourceRow(**values)


def run_collect(
    root: Path,
    job_store: JobStore,
    domain_store: DomainStore,
    transport: ScriptedTransport,
    source_id: str = SOURCE_ID,
    addon_source: str = COLLECTOR,
) -> RunOutcome:
    """Install, register, enqueue, and run one job through the real runner.

    Through `JobRunner` rather than by calling `invoke` directly, because the property
    under test in this file is the *transaction* the runner opens — and a test that
    called the capability layer itself would prove none of it.
    """
    install(root, addon_source)
    registry = HandlerRegistry()
    addons = load_addons(root, CONTRACT_VERSION)
    register_addons(registry, addons, bind_capabilities(domain_store, transport))
    job_store.create_job(HANDLER, {"source_id": source_id}, max_attempts=3)
    outcome = JobRunner(job_store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


def envelopes(connection: psycopg.Connection[Any]) -> int:
    row = connection.execute("select count(*) from cosmai.raw_envelope").fetchone()
    return 0 if row is None else int(row[0])


class TestACollectionIsAtomicThroughAnAddOn:
    """`EXP-003` H2a. `test_domain_store.py`'s own atomicity tests prove this at the
    store level with no add-on involved, on purpose — so that a later add-on bug could
    not be mistaken for the transaction working. This is the other half: the same
    property when an add-on is what drives it, through the real runner and the real
    capability layer.
    """

    def test_a_reclaimed_worker_persists_neither_raw_nor_cursor(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        domain_store.register_source(a_source())
        transport = LeaseStealingTransport(job_connection, a_page())

        outcome = run_collect(tmp_path, job_store, domain_store, transport)

        assert not outcome.accepted, "the fence should have refused this completion"
        assert len(transport.sent) == 1, "the run must have got far enough to have writes"
        # Both halves of the divergence. Raw without a cursor re-collects forever; a cursor
        # without Raw loses records with nothing to notice it by.
        assert envelopes(job_connection) == 0
        assert domain_store.count_items(SOURCE_ID) == 0
        assert domain_store.read_cursor(SOURCE_ID, "items") is None

    def test_the_same_run_persists_everything_when_the_lease_is_still_held(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control. Without it the assertions above would pass equally well
        against a capability layer that enlisted nothing and wrote nothing, ever."""
        domain_store.register_source(a_source())

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert envelopes(job_connection) == 1
        assert domain_store.count_items(SOURCE_ID) == 2
        assert domain_store.read_cursor(SOURCE_ID, "items") == 3

    def test_the_job_stays_claimable_so_the_work_is_not_lost(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """Discarding the writes must not discard the work. The other worker still has it."""
        domain_store.register_source(a_source())

        run_collect(
            tmp_path, job_store, domain_store, LeaseStealingTransport(job_connection, a_page())
        )

        row = job_connection.execute("select state from cosmai.job").fetchone()
        assert row is not None and row[0] != JobState.SUCCEEDED.value


class TestTheDurableScopeRequirementIsChecked:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F3.

    The class above proves atomicity only while the `DomainStore` and the `JobStore` share
    one connection, and that requirement lived in a fixture's docstring and nowhere else in
    P0. The independent review put the `DomainStore` on its own autocommit connection and
    measured the fence still refusing while `raw_envelope`, `raw_item`, and the cursor all
    survived it: *"never commits" and "is inside the fence's transaction" are different
    properties, and only the second is what H2a claims.*

    So the property is checked where it is used rather than described where it is set up.
    The check is on the connection's transaction status at the moment the durable work
    runs, which is the only moment at which the answer is not a guess about wiring.
    """

    def test_a_domain_store_outside_the_completion_transaction_is_refused(
        self,
        tmp_path: Path,
        job_store: JobStore,
        platform_config: PlatformConfig,
        job_connection: psycopg.Connection[Any],
        domain_store: DomainStore,
    ) -> None:
        """The reviewer's mis-wiring, run through the real runner.

        ``domain_store`` is otherwise unused here — this test writes through its own
        ``outside`` store on a *separate* connection, which is the point — but it is
        still requested so ``conftest.py``'s ``_reset_domain_tables`` runs before and
        after, the same table-level isolation every other test in this module gets
        through its own use of the fixture.
        """
        del domain_store
        with connect(platform_config, role="runtime", autocommit=True) as separate:
            outside = DomainStore(separate)
            outside.register_source(a_source())

            outcome = run_collect(tmp_path, job_store, outside, ScriptedTransport(a_page()))

            assert outcome.error is not None
            assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
            assert envelopes(separate) == 0
            assert outside.count_items(SOURCE_ID) == 0
            assert outside.read_cursor(SOURCE_ID, "items") is None

    def test_the_same_run_on_the_shared_connection_is_not_refused(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control. Without it the refusal above would pass against a check
        that refused every collection."""
        domain_store.register_source(a_source())

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert envelopes(job_connection) == 1
