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
from collections.abc import Mapping
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
        #: What the platform attached to each hop. A credential arrives here and nowhere
        #: else, so this is where a test can see one without one being recorded.
        self.headers: list[Mapping[str, str]] = []

    def send(
        self,
        request: PreparedRequest,
        profile: OutboundProfile,
        headers: Any = None,
        limits: TransportLimits | None = None,
    ) -> TransportResponse | Refusal:
        self.sent.append(request)
        self.headers.append(dict(headers or {}))
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


def install(
    root: Path, source: str = COLLECTOR, addon_id: str = ADDON_ID, manifest: str = MANIFEST
) -> Path:
    package = root / addon_id
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(manifest.format(addon_id=addon_id), encoding="utf-8")
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
    addon_id: str = ADDON_ID,
    manifest: str = MANIFEST,
    handler: str = HANDLER,
    logger: Any = None,
) -> RunOutcome:
    """Install, register, enqueue, and run one job through the real runner.

    Through `JobRunner` rather than by calling `invoke` directly, because the property
    under test in this file is the *transaction* the runner opens — and a test that
    called the capability layer itself would prove none of it.
    """
    install(root, addon_source, addon_id=addon_id, manifest=manifest)
    registry = HandlerRegistry()
    addons = load_addons(root, CONTRACT_VERSION)
    register_addons(registry, addons, bind_capabilities(domain_store, transport, logger))
    job_store.create_job(handler, {"source_id": source_id}, max_attempts=3)
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


class TestAStaleConfigSchemaVersionIsRefused:
    """M-P1 (REVIEW-M2-M7.md), now fixed rather than merely registered: the addon
    template's and every real add-on's README used to state "a source configured under
    an older schema is marked `NEEDS_MIGRATION` and refuses to run until an operator
    reconfigures it" — `config_schema_version` was parsed, stored, and echoed on every
    source read, but nothing ever compared the stored value against the manifest's, so
    the sentence was false of the code. `_resolved_source_row` now refuses at
    load/dispatch time, before any job-specific work runs, naming both versions
    (`CONFIGURATION_INVALID`, not a `NEEDS_MIGRATION` state — no such state exists
    anywhere in this codebase; that was always the README's own wording, not a
    mechanism this fix built). The READMEs were corrected in the same round of this fix
    wave to describe the `CONFIGURATION_INVALID` mechanism this class tests, so they no
    longer say `NEEDS_MIGRATION` either."""

    def test_a_stored_version_older_than_the_manifests_is_refused(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        domain_store.register_source(a_source(config_schema_version="0"))

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
        assert "'0'" in outcome.error.summary
        assert "'1'" in outcome.error.summary

    def test_a_stored_version_newer_than_the_manifests_is_also_refused(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The rule is a mismatch, not "too old" — a manifest rolled back to an earlier
        schema must refuse a row a newer build already migrated, too."""
        domain_store.register_source(a_source(config_schema_version="2"))

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
        assert "'2'" in outcome.error.summary
        assert "'1'" in outcome.error.summary

    def test_a_matching_version_runs_normally(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. Without it the refusal above would also fire when
        nothing at all was wrong."""
        domain_store.register_source(a_source(config_schema_version="1"))

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted


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


# --------------------------------------------------------------------------- #
# Deferred from batch 3b, picked up in 3c: refusal-swallowing, limits, and
# credential attachment — the three behaviors the 3c task packet named
# explicitly. One strong test per behavior (plus the positive control this
# codebase's own convention pairs every absence assertion with — see this
# module's own docstring and every P0 file quoted in it), not the full 1750
# lines of P0's `test_capabilities.py`. `docs/p1/M3-RECORD.md` names what is
# still not carried (the redirect-budget class, the miscount/output-shape
# refusals, the full status/body-refusal matrix) and why.
# --------------------------------------------------------------------------- #


def a_bounded_source(**limits: Any) -> SourceRow:
    """A source whose profile states the limits under test and leaves the rest default."""
    profile = {
        "hosts": ["api.example.com"],
        "endpoints": {"items": "/v1/items"},
        "port": 443,
        "limits": limits,
    }
    return a_source(outbound_profile=profile)


#: Fetches until something stops it. Against `max_pages` this is the whole test; the
#: independent review's version of it made 12 requests against a limit of 2 and succeeded
#: (`ADVERSARIAL-REVIEW-2026-08-18.md` F1).
RUNAWAY_PAGES = """
from addon_api import CollectOutcome


def run(context):
    for _ in range(12):
        context.fetch("items", {})
    return CollectOutcome(items_emitted=0)
"""

#: Emits far more items than the record limit permits, out of one page.
RUNAWAY_RECORDS = """
from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    items = [
        RawItem(
            item_key=str(n),
            payload=b"{}",
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
        for n in range(50)
    ]
    context.emit_raw(items)
    return CollectOutcome(items_emitted=len(items))
"""


class TestThePageLimitIsEnforced:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F1. `p0-security.md` §Outbound requires a
    per-source page limit and DP-008 D4 puts it on the platform; this is the counter,
    written against an add-on that does not cooperate.
    """

    def test_a_collector_that_ignores_the_page_limit_is_stopped_at_it(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        domain_store.register_source(a_bounded_source(max_pages=2))
        transport = ScriptedTransport(a_page(), a_page(), a_page(), a_page(), a_page())

        outcome = run_collect(
            tmp_path, job_store, domain_store, transport, addon_source=RUNAWAY_PAGES
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert len(transport.sent) == 2, "the third request must never have been sent"
        assert envelopes(job_connection) == 0

    def test_a_collector_inside_the_page_limit_is_not_stopped(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. Without it the refusal above would pass against a
        counter that refused the first page."""
        domain_store.register_source(a_bounded_source(max_pages=20))

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted


class TestTheRecordLimitIsEnforced:
    def test_a_collector_that_emits_past_the_record_limit_is_refused(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        domain_store.register_source(a_bounded_source(max_records=3))

        outcome = run_collect(
            tmp_path,
            job_store,
            domain_store,
            ScriptedTransport(a_page()),
            addon_source=RUNAWAY_RECORDS,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert envelopes(job_connection) == 0
        assert domain_store.count_items(SOURCE_ID) == 0

    def test_a_collector_inside_the_record_limit_persists_its_items(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control for the assertion above."""
        domain_store.register_source(a_bounded_source(max_records=5000))

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert domain_store.count_items(SOURCE_ID) == 2


# --------------------------------------------------------------------------- #
# max_request_bytes — DP-020 D2/D3, the body is the add-on's, the bound is not
# --------------------------------------------------------------------------- #

POSTING_ADDON_ID = "collector.posting"
POSTING_HANDLER = f"addon:{POSTING_ADDON_ID}"

POSTING_MANIFEST = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[declares]
hosts = ["api.example.com"]
endpoints = ["trend"]
"""

POSTING = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    asked = json.dumps({"keywordGroups": [{"groupName": "a"}]})
    response = context.fetch("trend", {}, body=asked.encode("utf-8"))
    context.emit_raw([
        RawItem(
            item_key="a",
            payload=response.body,
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
    ])
    return CollectOutcome(items_emitted=1)
"""

TREND_PAGE = json.dumps({"results": [{"title": "a"}]}).encode("utf-8")


def a_posting_source(**limits: Any) -> SourceRow:
    profile: dict[str, Any] = {
        "hosts": ["api.example.com"],
        "endpoints": {"trend": {"path": "/search-trend/v1/search", "method": "POST"}},
        "port": 443,
    }
    if limits:
        profile["limits"] = limits
    return SourceRow(
        source_id=SOURCE_ID,
        addon_id=POSTING_ADDON_ID,
        addon_version=ADDON_VERSION,
        kind="collector",
        config={},
        config_schema_version="1",
        outbound_profile=profile,
    )


class TestTheRequestBodyLimitIsEnforced:
    """DP-020 D2 gives an add-on a body; DP-020 D3 says the platform bounds it, not the
    add-on's own restraint. `max_request_bytes` is counted before the request is sent.
    """

    def test_an_oversized_body_is_refused_before_the_request(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        domain_store.register_source(a_posting_source(max_request_bytes=8))
        transport = ScriptedTransport(a_page(body=TREND_PAGE))

        outcome = run_collect(
            tmp_path,
            job_store,
            domain_store,
            transport,
            addon_source=POSTING,
            addon_id=POSTING_ADDON_ID,
            manifest=POSTING_MANIFEST,
            handler=POSTING_HANDLER,
        )

        assert outcome.error is not None
        assert transport.sent == [], "an oversized body must never reach the transport"

    def test_the_same_body_is_accepted_within_a_stated_limit(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. Without it the refusal above would pass against a bound
        that refused every request regardless of size."""
        domain_store.register_source(a_posting_source())
        transport = ScriptedTransport(a_page(body=TREND_PAGE))

        outcome = run_collect(
            tmp_path,
            job_store,
            domain_store,
            transport,
            addon_source=POSTING,
            addon_id=POSTING_ADDON_ID,
            manifest=POSTING_MANIFEST,
            handler=POSTING_HANDLER,
        )

        assert outcome.accepted, outcome
        assert len(transport.sent) == 1


# --------------------------------------------------------------------------- #
# Undecided status — a response the add-on neither raised on nor called
# accept_status about (contract 1.3 invariant 5, not invariant 4 — see B6,
# REVIEW-M2-M7.md: this section banner previously read "Refusal-swallowing", which is
# the *other* rule, tested in `TestARefusalCannotBeSwallowed` below).
# --------------------------------------------------------------------------- #

#: Emits whatever came back without looking at the status. What the platform must catch
#: (`ADVERSARIAL-REVIEW-2026-08-19.md` F2(b): a collector that emitted from a `401` body
#: reported `SUCCEEDED`, and the error body landed in `raw_item` as data).
IGNORES_STATUS = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    context.emit_raw([
        RawItem(
            item_key="a",
            payload=response.body,
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
    ])
    return CollectOutcome(items_emitted=1)
"""


class TestANonSuccessStatusCannotBeIgnored:
    """`ADVERSARIAL-REVIEW-2026-08-19.md` F2(b), contract 1.2's `accept_status`.

    The platform does not decide what a status *means* — a `404` is "no results" to one
    API and "wrong endpoint" to another — but it does enforce that the add-on **decided**:
    raised on it, or called `accept_status` with a reason. Silence fails the run.
    """

    def test_emitting_from_a_non_success_response_without_deciding_fails_the_job(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        domain_store.register_source(a_source())

        outcome = run_collect(
            tmp_path,
            job_store,
            domain_store,
            ScriptedTransport(a_page(status=401, body=b'{"errorCode":"SE01"}')),
            addon_source=IGNORES_STATUS,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain_store.count_items(SOURCE_ID) == 0

    def test_an_ordinary_success_needs_no_decision(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. A check that demanded a decision on every response would
        pass the assertion above and break every ordinary collector."""
        domain_store.register_source(a_source())

        outcome = run_collect(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert domain_store.count_items(SOURCE_ID) == 2


# --------------------------------------------------------------------------- #
# It cannot be talked out of refusing — contract 1.3 invariant 4
# --------------------------------------------------------------------------- #

#: Catches everything and reports success. What a control has to survive. Ported
#: verbatim from `experiments/integrated-p0/tests/test_capabilities.py`'s `SWALLOWING`
#: (controller Ruling 3: the P0 original is the spec).
SWALLOWING = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.fetch(context.config_field("label", "items"), {})
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""

IMPORT_ADDON_ID = "importer.probe"
IMPORT_HANDLER = f"addon:{IMPORT_ADDON_ID}"

IMPORT_MANIFEST = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "importer"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[[config.field]]
name = "input_name"
type = "string"
required = false

[declares]
inputs = ["rows"]
streams = ["rows"]
"""

#: The importer's mirror of `SWALLOWING`. Catches whatever `open_input` raises and
#: reports success having read nothing. P0 never wrote this add-on or this class of
#: test — `capabilities.py`'s importer `_check_no_refusal_was_swallowed` (`:1159`,
#: called `:969`) is P1-only code, and B6 (REVIEW-M2-M7.md) found it untested anywhere
#: in the tree.
SWALLOWING_IMPORT = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.open_input(context.config_field("input_name", "rows"))
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""


def an_import_source(**overrides: Any) -> SourceRow:
    values: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "addon_id": IMPORT_ADDON_ID,
        "addon_version": "0.1.0",
        "kind": "importer",
        "config": {"input_name": "rows"},
        "config_schema_version": "1",
        "input_profile": None,
    }
    values.update(overrides)
    return SourceRow(**values)


class _NoTransport:
    """An importer must never reach this. DP-024 D6. Same double
    `test_importer_local_jsonl.py` uses, redefined here so this file's importer coverage
    does not import from another test module."""

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("an importer opened a request")


def run_import(
    root: Path,
    job_store: JobStore,
    domain_store: DomainStore,
    source_id: str = SOURCE_ID,
    addon_source: str = SWALLOWING_IMPORT,
    addon_id: str = IMPORT_ADDON_ID,
    manifest: str = IMPORT_MANIFEST,
    handler: str = IMPORT_HANDLER,
) -> RunOutcome:
    """The importer's mirror of `run_collect`: install, register, enqueue, run for real."""
    install(root, addon_source, addon_id=addon_id, manifest=manifest)
    registry = HandlerRegistry()
    addons = load_addons(root, CONTRACT_VERSION)
    register_addons(registry, addons, bind_capabilities(domain_store, _NoTransport()))
    job_store.create_job(handler, {"source_id": source_id}, max_attempts=3)
    outcome = JobRunner(job_store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


class TestARefusalCannotBeSwallowed:
    """The failure mode this file exists for. Ported from P0's class of the same name
    (`experiments/integrated-p0/tests/test_capabilities.py:519`) for the collector path,
    unchanged in substance, plus a new pair of cases for the importer path P0 never
    wrote (`capabilities.py`'s two `_check_no_refusal_was_swallowed` implementations —
    collector `:868`/called `:397`, importer `:1159`/called `:969` — are separate code
    and B6 found only the collector half exercised).

    `fetch`/`open_input` raise a `PlatformError`, and nothing stops add-on code from
    catching it — `except BaseException` is legal Python. If that were the end of it, a
    collector or importer could turn every outbound or input rule into a suggestion and
    still report success. `capabilities.py:807`'s own docstring says the *status* check
    above (`TestANonSuccessStatusCannotBeIgnored`) is *"weaker than
    `_check_no_refusal_was_swallowed` beside it"* — this class is that stronger control.
    """

    def test_a_collector_that_catches_the_refusal_still_fails_the_job(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        domain_store.register_source(a_source(config={"label": "ungranted"}))

        outcome = run_collect(
            tmp_path, job_store, domain_store, ScriptedTransport(), addon_source=SWALLOWING
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "continued past an outbound refusal" in outcome.error.summary
        assert envelopes(job_connection) == 0

    def test_the_same_swallowing_collector_succeeds_on_a_granted_endpoint(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. Without it the test above would also pass over a host
        that failed every job that used a `try` block."""
        domain_store.register_source(a_source(config={"label": "items"}))

        outcome = run_collect(
            tmp_path, job_store, domain_store, ScriptedTransport(a_page()), addon_source=SWALLOWING
        )

        assert outcome.accepted and outcome.state is JobState.SUCCEEDED

    def test_an_importer_that_catches_the_refusal_still_fails_the_job(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The input name it asks for (`"rows"`) is declared by the manifest but not by
        this source's *approved* profile — `input_profile=None` means "this source has
        no approved input profile, so it reads nothing" (`INPUT_NOT_DECLARED`'s sibling,
        `SOURCE_HAS_NO_PROFILE`), the importer's exact analogue of an ungranted
        endpoint."""
        domain_store.register_source(an_import_source())

        outcome = run_import(tmp_path, job_store, domain_store, addon_source=SWALLOWING_IMPORT)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "an input was refused and the importer did not stop" in outcome.error.summary
        assert domain_store.count_items(SOURCE_ID) == 0

    def test_the_same_swallowing_importer_succeeds_on_an_approved_input(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The positive control. Without it the test above would also pass over an
        importer that failed every job that used a `try` block."""
        dataset_dir = tmp_path / "dataset_root"
        dataset_dir.mkdir()
        (dataset_dir / "rows.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")
        domain_store.register_source(
            an_import_source(
                input_profile={"root": str(dataset_dir), "inputs": {"rows": "rows.jsonl"}}
            )
        )

        outcome = run_import(tmp_path, job_store, domain_store, addon_source=SWALLOWING_IMPORT)

        assert outcome.accepted and outcome.state is JobState.SUCCEEDED


# --------------------------------------------------------------------------- #
# DP-018 — the credential the platform attaches and the add-on never sees
# --------------------------------------------------------------------------- #

CREDENTIAL_ADDON_ID = "collector.credentialed"
CREDENTIAL_HANDLER = f"addon:{CREDENTIAL_ADDON_ID}"
CREDENTIAL_REF = "COSMA_SRC_PROBE_TOKEN"
CREDENTIAL_VALUE = "ncp-secret-value-42"

CREDENTIAL_MANIFEST = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[declares]
hosts = ["api.example.com"]
endpoints = ["items"]
streams = ["items"]
needs_credential = true
"""

#: Reports whatever it can see. If a credential ever reaches an add-on, this finds it.
INSPECTING = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    seen = {"response_headers": dict(response.headers), "config": dict(context.config)}
    context.emit_raw([
        RawItem(
            item_key="seen",
            payload=json.dumps(seen, sort_keys=True).encode("utf-8"),
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
    ])
    return CollectOutcome(items_emitted=1)
"""


@pytest.fixture
def secret_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "secrets" / "env"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(f"{CREDENTIAL_REF}={CREDENTIAL_VALUE}" + "\n", encoding="utf-8")
    store.chmod(0o600)
    monkeypatch.setenv("COSMA_SECRET_SOURCE", str(store))
    return store


def an_authenticated_source() -> SourceRow:
    profile = {
        "hosts": ["api.example.com"],
        "endpoints": {"items": "/v1/items"},
        "port": 443,
        "credentials": [{"header": "X-NCP-APIGW-API-KEY", "ref": CREDENTIAL_REF}],
    }
    return SourceRow(
        source_id=SOURCE_ID,
        addon_id=CREDENTIAL_ADDON_ID,
        addon_version=ADDON_VERSION,
        kind="collector",
        config={},
        config_schema_version="1",
        outbound_profile=profile,
    )


def _run_credentialed(
    tmp_path: Path,
    job_store: JobStore,
    domain_store: DomainStore,
    transport: ScriptedTransport,
    addon_source: str = COLLECTOR,
) -> RunOutcome:
    return run_collect(
        tmp_path,
        job_store,
        domain_store,
        transport,
        addon_source=addon_source,
        addon_id=CREDENTIAL_ADDON_ID,
        manifest=CREDENTIAL_MANIFEST,
        handler=CREDENTIAL_HANDLER,
    )


class TestTheCredentialReachesTheRequestAndNothingElse:
    """DP-018. The add-on composes no URL, holds no credential, and opens no socket — and
    the request it caused is authenticated anyway. Every assertion here is paired with the
    one that makes it mean something: the value is *present* on the wire and *absent*
    everywhere it could be recorded — either half alone passes against a platform that
    attaches nothing at all.
    """

    def test_the_platform_attaches_the_credential_to_the_request(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore, secret_store: Path
    ) -> None:
        domain_store.register_source(an_authenticated_source())
        transport = ScriptedTransport(a_page())

        outcome = _run_credentialed(tmp_path, job_store, domain_store, transport)

        reason = outcome.error.summary if outcome.error else outcome
        assert outcome.state is JobState.SUCCEEDED, reason
        assert transport.headers[0]["X-NCP-APIGW-API-KEY"] == CREDENTIAL_VALUE

    def test_a_source_without_a_credential_sends_none(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The control. Without it the assertion above could not tell attachment from a
        transport double that was handed a header by something else."""
        domain_store.register_source(a_source())
        transport = ScriptedTransport(a_page())

        run_collect(tmp_path, job_store, domain_store, transport)

        assert transport.headers[0] == {}

    def test_the_add_on_never_sees_the_value(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore, secret_store: Path
    ) -> None:
        """DP-008 D4, kept while a real request is authenticated. The add-on reports
        everything reachable from its context; the value is in none of it."""
        domain_store.register_source(an_authenticated_source())

        _run_credentialed(
            tmp_path, job_store, domain_store, ScriptedTransport(a_page()), addon_source=INSPECTING
        )

        with domain_store.connection.cursor() as cursor:
            cursor.execute("select payload from cosmai.raw_item")
            row = cursor.fetchone()
        assert row is not None
        reported = bytes(row[0]).decode("utf-8")
        assert CREDENTIAL_VALUE not in reported
        assert CREDENTIAL_REF not in reported

    def test_the_value_is_in_no_recorded_envelope(
        self,
        tmp_path: Path,
        job_store: JobStore,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        secret_store: Path,
    ) -> None:
        """`p0-security.md`: nothing recorded carries a credential. The header this source
        uses is in `PROTECTED_HEADERS`, which DP-018 D3 makes a precondition of using it —
        this is the assertion that the precondition does what it was chosen for."""
        domain_store.register_source(an_authenticated_source())

        outcome = _run_credentialed(tmp_path, job_store, domain_store, ScriptedTransport(a_page()))
        reason = outcome.error.summary if outcome.error else outcome
        assert outcome.state is JobState.SUCCEEDED, reason

        row = job_connection.execute(
            "select request_summary::text, coalesce(response_headers::text, '') "
            "from cosmai.raw_envelope"
        ).fetchone()
        assert row is not None
        assert CREDENTIAL_VALUE not in row[0] + row[1]
        # The real header-stripping assertion, over a socket, is `test_outbound_transport.py`'s;
        # this is the control that says something was actually recorded to check.
        assert "url" in row[0], "nothing was recorded, so the absence proves nothing"


class TestACredentialPartMustNameAProtectedHeader:
    """DP-018 D3, checked directly against `domain.outbound` rather than through a run:
    `strip_protected_headers` only strips what `PROTECTED_HEADERS` names, so a profile
    free to attach *any* header to *any* name could authenticate a request with a header
    that reaches recorded Raw untouched — a credential in Raw with every other rule still
    satisfied. `[측정]` P0 built and enforced this rule (`domain/outbound.py`'s
    `_read_credentials`) but — as far as this tree's copy of its test suite shows — never
    actually tested it; this is new coverage, not a copy-adapt.
    """

    def test_a_credential_naming_an_unprotected_header_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a protected header"):
            OutboundProfile.from_row(
                {
                    "hosts": ["api.example.com"],
                    "endpoints": {"items": "/v1/items"},
                    "credentials": [{"header": "X-Custom-Header", "ref": CREDENTIAL_REF}],
                }
            )

    def test_a_credential_naming_a_protected_header_is_accepted(self) -> None:
        """The positive control. Without it the refusal above could pass against a
        function that rejects every credential regardless of the header it names."""
        profile = OutboundProfile.from_row(
            {
                "hosts": ["api.example.com"],
                "endpoints": {"items": "/v1/items"},
                "credentials": [{"header": "X-NCP-APIGW-API-KEY", "ref": CREDENTIAL_REF}],
            }
        )
        assert profile is not None
        assert profile.credentials[0].header == "X-NCP-APIGW-API-KEY"


# --------------------------------------------------------------------------- #
# The cursor resume scenario — OQ-010, on the single-stream path that is bound
# --------------------------------------------------------------------------- #


class TestASecondRunResumesFromTheFirstsCursor:
    """The read/write pair OQ-010 is about, through the real runner and two attempts."""

    def test_a_second_run_resumes_from_the_cursor_the_first_one_wrote(
        self, tmp_path: Path, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        domain_store.register_source(a_source())
        install(tmp_path, COLLECTOR)
        registry = HandlerRegistry()
        transport = ScriptedTransport(
            a_page(),
            a_page(json.dumps({"items": [{"id": 3}], "next": 4}).encode("utf-8")),
        )
        register_addons(
            registry,
            load_addons(tmp_path, CONTRACT_VERSION),
            bind_capabilities(domain_store, transport),
        )
        runner = JobRunner(job_store, registry, WORKER, lease_seconds=60)

        job_store.create_job(HANDLER, {"source_id": SOURCE_ID}, max_attempts=3)
        first = runner.run_once()
        assert first is not None and first.accepted
        assert domain_store.read_cursor(SOURCE_ID, "items") == 3

        job_store.create_job(HANDLER, {"source_id": SOURCE_ID}, max_attempts=3)
        second = runner.run_once()
        assert second is not None and second.accepted
        assert domain_store.read_cursor(SOURCE_ID, "items") == 4
        assert domain_store.count_items(SOURCE_ID) == 3
