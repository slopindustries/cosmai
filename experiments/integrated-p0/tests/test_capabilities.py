"""The capability layer: H2, and the refusals that make it worth claiming.

`EXP-003`'s hypothesis is that **every** outbound obligation in `p0-security.md` can stay
on the platform while a collector still does useful work. These tests are the evidence.
The collector here composes no URL, holds no credential, and opens no socket; what it does
is name an endpoint, carve items out of what comes back, and say where it stopped.

Three shapes of claim live here and they are kept apart on purpose.

**It works.** A collect job through the real `JobRunner` leaves an envelope, its items, and
a cursor, and the job succeeds. Resumption reads the cursor back.

**It refuses.** `SEC-002`, `SEC-003`: an unregistered source, an undeclared endpoint, a
redirect out of policy. Each names the rule that refused it rather than failing generically.

**It cannot be talked out of refusing.** The one this file exists for. An add-on that
catches the refusal and returns success still fails the job, because a security control an
add-on can swallow is not a control. Its positive control is directly below it: the *same*
swallowing add-on against an *allowed* endpoint succeeds — so the failure above is the
refusal and not the swallowing.

Every absence assertion here is paired. "Nothing was persisted" is checked against a
sibling that persists, because a capability layer that wrote nothing at all would pass the
absence half of every one of these.
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
from domain.transport import TransportLimits, TransportResponse, TransportUnavailable
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("database")

WORKER = "worker-1"
ADDON_ID = "collector.probe"
ADDON_VERSION = "0.1.0"
HANDLER = f"addon:{ADDON_ID}"
SOURCE_ID = "probe"

MANIFEST = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "{kind}"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"
{extra}
[config]
schema_version = "1"

[[config.field]]
name = "label"
type = "string"
required = false

[declares]
{declares}
streams = [{streams}]
"""

#: A collector asks for a host and an endpoint name; a normalizer may declare neither, and
#: `_check_kind_consistency` refuses the manifest at load time if it tries. That refusal is
#: the contract working, so the fixture states the two shapes rather than working around it.
COLLECTOR_DECLARES = 'hosts = ["api.example.com"]\nendpoints = ["items"]'


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

#: Catches everything and reports success. What a control has to survive.
SWALLOWING = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.fetch(context.config_field("label", "items"), {})
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""

#: Claims more than it emitted.
MISCOUNTING = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    context.emit_raw([
        RawItem("one", b"1", "application/json", envelope_ref=response.envelope_ref)
    ])
    return CollectOutcome(items_emitted=7)
"""

#: Emits an item whose provenance points at nothing.
ORPHANING = """
from addon_api import CollectOutcome, RawItem


def run(context):
    context.fetch("items", {})
    context.emit_raw([RawItem("one", b"1", "application/json", envelope_ref="made-up")])
    return CollectOutcome(items_emitted=1)
"""

#: Writes a stream it never declared.
WRONG_STREAM = """
from addon_api import CollectOutcome


def run(context):
    context.fetch("items", {})
    context.advance_cursor("elsewhere", 2)
    return CollectOutcome(items_emitted=0)
"""

PAGE = json.dumps({"items": [{"id": 1}, {"id": 2}], "next": 3}).encode("utf-8")


# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #


class ScriptedTransport:
    """One hop per scripted entry, in order. Records every request it was handed.

    A double rather than a socket because what these tests check — buffering, the
    transaction boundary, the count cross-check, the unswallowable refusal — is not the
    socket. `tests/test_outbound_transport.py` is where a real one runs.
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


def a_page(body: bytes = PAGE, status: int = 200, location: str | None = None) -> TransportResponse:
    return TransportResponse(
        status=status,
        headers={"Content-Type": "application/json"},
        body=body,
        location=location,
        addresses=("203.0.113.7",),
    )


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def install(
    root: Path, source: str = COLLECTOR, kind: str = "collector", streams: str = '"items"'
) -> Path:
    package = root / ADDON_ID
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(
        MANIFEST.format(
            addon_id=ADDON_ID,
            kind=kind,
            streams=streams,
            declares=COLLECTOR_DECLARES if kind == "collector" else "",
            extra="" if kind == "collector" else 'output_contract_version = "1"',
        ),
        encoding="utf-8",
    )
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
    store: JobStore,
    domain: DomainStore,
    transport: ScriptedTransport,
    source_id: str = SOURCE_ID,
    addon_source: str = COLLECTOR,
    kind: str = "collector",
    streams: str = '"items"',
) -> RunOutcome:
    """Install, register, enqueue, and run one job through the real runner.

    Through `JobRunner` rather than by calling `invoke` directly, because the property
    under test in half these cases is the *transaction* the runner opens — and a test
    that called the capability layer itself would prove none of it.
    """
    install(root, addon_source, kind=kind, streams=streams)
    registry = HandlerRegistry()
    addons = load_addons(root, CONTRACT_VERSION)
    register_addons(registry, addons, bind_capabilities(domain, transport))
    store.create_job(HANDLER, {"source_id": source_id}, max_attempts=3)
    outcome = JobRunner(store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    """On the runner's own connection, so enlisted writes and the fence share a transaction."""
    return DomainStore(connection)


def envelopes(connection: psycopg.Connection[Any]) -> int:
    row = connection.execute("select count(*) from raw_envelope").fetchone()
    return 0 if row is None else int(row[0])


# --------------------------------------------------------------------------- #
# It works
# --------------------------------------------------------------------------- #


class TestACollectorCollects:
    def test_one_run_leaves_an_envelope_its_items_and_a_cursor(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """H2's positive half: the add-on named an endpoint and everything else was ours."""
        domain.register_source(a_source())
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.accepted and outcome.state is JobState.SUCCEEDED
        assert envelopes(connection) == 1
        assert domain.count_items(SOURCE_ID) == 2
        assert domain.read_cursor(SOURCE_ID, "items") == 3

    def test_the_platform_built_the_url_the_add_on_never_saw(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())
        transport = ScriptedTransport(a_page())

        run_collect(tmp_path, store, domain, transport)

        assert len(transport.sent) == 1
        assert transport.sent[0].url.startswith("https://api.example.com:443/v1/items?")
        assert transport.sent[0].host == "api.example.com"

    def test_the_envelope_keeps_the_bytes_and_the_items_keep_their_provenance(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """Losslessness is the platform's, not the add-on's: the whole page is stored."""
        domain.register_source(a_source())
        run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        row = connection.execute(
            "select body, status, endpoint_ref, addon_id, addon_version, attempt_id "
            "from raw_envelope"
        ).fetchone()
        assert row is not None
        assert bytes(row[0]) == PAGE
        assert (row[1], row[2], row[3], row[4]) == (200, "items", ADDON_ID, ADDON_VERSION)

        linked = connection.execute(
            "select count(*) from raw_item i join raw_envelope e on i.envelope_id = e.id"
        ).fetchone()
        assert linked is not None and int(linked[0]) == 2

    def test_a_second_run_resumes_from_the_cursor_the_first_one_wrote(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The read/write pair OQ-010 is about, on the single-stream path that is bound."""
        domain.register_source(a_source())
        install(tmp_path, COLLECTOR)
        registry = HandlerRegistry()
        transport = ScriptedTransport(a_page(), a_page(json.dumps(
            {"items": [{"id": 3}], "next": 4}
        ).encode("utf-8")))
        register_addons(
            registry, load_addons(tmp_path, CONTRACT_VERSION), bind_capabilities(domain, transport)
        )
        runner = JobRunner(store, registry, WORKER, lease_seconds=60)

        store.create_job(HANDLER, {"source_id": SOURCE_ID}, max_attempts=3)
        assert (first := runner.run_once()) is not None and first.accepted
        assert domain.read_cursor(SOURCE_ID, "items") == 3

        store.create_job(HANDLER, {"source_id": SOURCE_ID}, max_attempts=3)
        assert (second := runner.run_once()) is not None and second.accepted
        assert domain.read_cursor(SOURCE_ID, "items") == 4
        assert domain.count_items(SOURCE_ID) == 3


# --------------------------------------------------------------------------- #
# It refuses — SEC-002, SEC-003
# --------------------------------------------------------------------------- #


class TestTheGuardRefuses:
    def test_an_unregistered_source_is_refused_before_any_request(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """`SEC-002`, first half. The refusal is *before* execution, so nothing was sent."""
        domain.register_source(a_source())
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport, source_id="not-registered")

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "not-registered" in outcome.error.summary
        # The absence assertion. Its control is the class above, where the same scripted
        # transport is consumed exactly once by a source that *is* registered.
        assert transport.sent == []

    def test_an_endpoint_the_profile_does_not_grant_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """`SEC-002`, second half. `[declares]` is a request; the profile is the grant."""
        domain.register_source(a_source(config={"label": "ungranted"}))
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport, addon_source=SWALLOWING)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert transport.sent == []
        assert envelopes(connection) == 0

    def test_a_redirect_out_of_policy_is_refused_and_not_followed(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """`SEC-003`. The transport follows nothing; the same policy decides the second hop."""
        domain.register_source(a_source())
        transport = ScriptedTransport(
            a_page(status=302, location="https://elsewhere.example.net/v1/items"),
            a_page(),
        )

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert len(transport.sent) == 1, "the redirect was followed"
        assert envelopes(connection) == 0

    def test_a_redirect_inside_policy_is_followed_and_recorded(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control for the test above: this guard does not refuse every redirect."""
        domain.register_source(a_source())
        transport = ScriptedTransport(
            a_page(status=307, location="https://api.example.com/v1/items?page=2"),
            a_page(),
        )

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.accepted and outcome.state is JobState.SUCCEEDED
        assert len(transport.sent) == 2

    def test_a_transport_failure_is_transient_rather_than_permanent(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """A blip must not burn a job. Classified here, not by the generic translator."""
        domain.register_source(a_source())
        transport = ScriptedTransport(TransportUnavailable("the far end timed out"))

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_TRANSIENT
        assert outcome.state is JobState.PENDING


# --------------------------------------------------------------------------- #
# It cannot be talked out of refusing
# --------------------------------------------------------------------------- #


class TestARefusalCannotBeSwallowed:
    """The failure mode this file exists for.

    `fetch` raises a `PlatformError`, and nothing stops add-on code from catching it —
    `except BaseException` is legal Python. If that were the end of it, a collector could
    turn every outbound rule into a suggestion and still report success.
    """

    def test_an_add_on_that_catches_the_refusal_still_fails_the_job(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_source(config={"label": "ungranted"}))

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(), addon_source=SWALLOWING
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "continued past an outbound refusal" in outcome.error.summary
        assert envelopes(connection) == 0

    def test_the_same_swallowing_add_on_succeeds_on_a_granted_endpoint(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The positive control. Without it the test above would also pass over a host that
        failed every job that used a `try` block."""
        domain.register_source(a_source(config={"label": "items"}))

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=SWALLOWING
        )

        assert outcome.accepted and outcome.state is JobState.SUCCEEDED


# --------------------------------------------------------------------------- #
# What an add-on claims is checked against what it did
# --------------------------------------------------------------------------- #


class TestOutputIsChecked:
    def test_a_collector_that_miscounts_is_refused_and_persists_nothing(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=MISCOUNTING
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert envelopes(connection) == 0
        assert domain.count_items(SOURCE_ID) == 0

    def test_an_item_naming_no_envelope_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=ORPHANING
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT

    def test_a_cursor_on_an_undeclared_stream_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=WRONG_STREAM
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_cursor(SOURCE_ID, "elsewhere") is None


# --------------------------------------------------------------------------- #
# Stated limits — OQ-010, and the kinds nothing binds
# --------------------------------------------------------------------------- #


class TestStatedLimits:
    def test_an_add_on_declaring_two_streams_is_refused_by_name(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """OQ-010's interim position, as a refusal rather than a guess."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(), streams='"items", "comments"'
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert "OQ-010" in outcome.error.summary

    def test_a_source_row_that_fails_the_schema_is_configuration_invalid(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """Not "the add-on raised something unexpected", which is what it read as before.

        `[측정]` Found on 2026-08-18 by the first integration run. `ConfigValidationError` is
        a plain `Exception`, so the generic translator classified an operator-fixable row as
        an unanticipated add-on defect — the same class it gives a handler that crashed.
        """
        domain.register_source(a_source(config={"label": 7}))

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport())

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
        # The field name is in the operator-facing summary. `detail` is a ProtectedDetail
        # and withholds its contents from `str()`, which is redaction working as intended.
        assert "label" in outcome.error.summary

    def test_a_source_row_that_satisfies_the_schema_is_not_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control: the check above is about the schema, not about every source."""
        domain.register_source(a_source(config={"label": "items"}))

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        assert outcome.accepted

    def test_a_normalizer_is_refused_with_the_reason_stated(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source(kind="normalizer", outbound_profile=None))

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(), kind="normalizer", streams=""
        )

        assert outcome.error is not None
        assert "no normalizer capabilities" in outcome.error.summary


# --------------------------------------------------------------------------- #
# H2a — atomicity, through a real add-on this time
# --------------------------------------------------------------------------- #


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
        self._connection.execute("update job set lease_owner = 'worker-2'")
        return super().send(request, profile, headers, limits)


class TestACollectionIsAtomicThroughAnAddOn:
    """`EXP-003` H2a. `TestCollectionIsAtomic` proved this at the store level with no
    add-on involved, on purpose — so that a later add-on bug could not be mistaken for
    the transaction working. This is the other half: the same property when an add-on is
    what drives it, through the real runner and the real capability layer.
    """

    def test_a_reclaimed_worker_persists_neither_raw_nor_cursor(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_source())
        transport = LeaseStealingTransport(connection, a_page())

        outcome = run_collect(tmp_path, store, domain, transport)

        assert not outcome.accepted, "the fence should have refused this completion"
        assert len(transport.sent) == 1, "the run must have got far enough to have writes"
        # Both halves of the divergence. Raw without a cursor re-collects forever; a cursor
        # without Raw loses records with nothing to notice it by.
        assert envelopes(connection) == 0
        assert domain.count_items(SOURCE_ID) == 0
        assert domain.read_cursor(SOURCE_ID, "items") is None

    def test_the_same_run_persists_everything_when_the_lease_is_still_held(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control. Without it the assertions above would pass equally well
        against a capability layer that enlisted nothing and wrote nothing, ever."""
        domain.register_source(a_source())

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert envelopes(connection) == 1
        assert domain.count_items(SOURCE_ID) == 2
        assert domain.read_cursor(SOURCE_ID, "items") == 3

    def test_the_job_stays_claimable_so_the_work_is_not_lost(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """Discarding the writes must not discard the work. The other worker still has it."""
        domain.register_source(a_source())

        run_collect(tmp_path, store, domain, LeaseStealingTransport(connection, a_page()))

        row = connection.execute("select state from job").fetchone()
        assert row is not None and row[0] != JobState.SUCCEEDED.value
