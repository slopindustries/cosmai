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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host import capabilities
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.outbound import OutboundProfile, PreparedRequest, Refusal
from domain.transport import TransportLimits, TransportResponse, TransportUnavailable
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger

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
{credential}
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

#: Returns something that is not a `CollectOutcome`. `[측정]` The guard that refuses this
#: had no test on either side of the capability layer — removing it still failed the run,
#: because the next line to touch the result crashes. A test asserting only "it failed"
#: cannot tell a checked refusal from a crash, which is why the case below reads the
#: summary. `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5.
WRONG_RETURN = """
def run(context):
    context.fetch("items", {})
    return None
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

#: Advances the declared stream to `None`. `[측정]` `ADVERSARIAL-REVIEW-2026-08-18.md` F6
#: measured the check that refuses this as GREEN, and it still was on 2026-08-19 — in both
#: the collector's copy and the importer's.
NULL_CURSOR = """
from addon_api import CollectOutcome


def run(context):
    context.fetch("items", {})
    context.advance_cursor("items", None)
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


class BudgetRecordingTransport(ScriptedTransport):
    """Records the `TransportLimits` of every hop, so the deadline can be asserted.

    A subclass rather than a field on `ScriptedTransport` because only two cases care, and
    a recorder every other case carries is a recorder every other case has to be read past.
    """

    def __init__(self, *scripted: TransportResponse | Refusal | BaseException) -> None:
        super().__init__(*scripted)
        self.budgets: list[TransportLimits | None] = []

    def send(
        self,
        request: PreparedRequest,
        profile: OutboundProfile,
        headers: Any = None,
        limits: TransportLimits | None = None,
    ) -> TransportResponse | Refusal:
        self.budgets.append(limits)
        return super().send(request, profile, headers, limits)


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
    root: Path,
    source: str = COLLECTOR,
    kind: str = "collector",
    streams: str = '"items"',
    needs_credential: bool = False,
) -> Path:
    package = root / ADDON_ID
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(
        MANIFEST.format(
            addon_id=ADDON_ID,
            kind=kind,
            streams=streams,
            declares=COLLECTOR_DECLARES if kind == "collector" else "",
            # Only a normalizer declares one; the manifest parser refuses it on any other
            # kind, which is that rule working rather than a fixture quirk.
            extra='output_contract_version = "1"' if kind == "normalizer" else "",
            credential="needs_credential = true" if needs_credential else "",
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
    needs_credential: bool = False,
    logger: StructuredLogger | None = None,
) -> RunOutcome:
    """Install, register, enqueue, and run one job through the real runner.

    Through `JobRunner` rather than by calling `invoke` directly, because the property
    under test in half these cases is the *transaction* the runner opens — and a test
    that called the capability layer itself would prove none of it.
    """
    install(root, addon_source, kind=kind, streams=streams, needs_credential=needs_credential)
    registry = HandlerRegistry()
    addons = load_addons(root, CONTRACT_VERSION)
    register_addons(registry, addons, bind_capabilities(domain, transport, logger))
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

    def test_a_collector_returning_the_wrong_type_is_refused_by_name(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=WRONG_RETURN
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        # The summary, not just the failure: a crash would also produce an error.
        assert "CollectOutcome" in outcome.error.summary, outcome.error.summary
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

    def test_a_cursor_value_of_none_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """`read_cursor` returns `None` for "never ran", so a stored null would be
        indistinguishable from it — and the add-on would restart from the beginning on
        every attempt with no error, no lost record, and every record collected again."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=NULL_CURSOR
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_cursor(SOURCE_ID, "items") is None


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

    def test_a_kind_this_host_does_not_bind_is_refused_by_name_and_with_a_reason(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`[측정]` This case has now outlived both of its subjects.

        It named `normalizer` until 2026-08-18 and asserted the refusal `_UNBOUND_KINDS`
        gave it — *"0002_domain.sql creates no normalized-result table"* — until DP-019
        created one. It named `importer` until 2026-08-19, when DP-024 defined the registry
        of approved local inputs and bound `open_input`. **`_UNBOUND_KINDS` is now empty**,
        so there is no real kind left to refuse.

        What the case was always testing is the property its docstring already claimed
        should outlive any particular kind: an unbound kind fails *by name and with a
        reason* rather than obscurely. That mechanism is the next contract's protection, so
        it is exercised against a temporary entry rather than deleted along with its last
        subject.
        """
        monkeypatch.setitem(
            capabilities._UNBOUND_KINDS, "importer", "a reason a future kind would carry"
        )
        domain.register_source(a_source(kind="importer", outbound_profile=None))

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(), kind="importer", streams=""
        )

        assert outcome.error is not None
        assert "no importer capabilities" in outcome.error.summary
        assert "a reason a future kind would carry" in outcome.error.summary

    def test_the_unbound_kind_list_is_empty(self) -> None:
        """The control on the case above, and the record of what DP-019 and DP-024 closed.

        Without this, a kind quietly re-added to `_UNBOUND_KINDS` would look like the
        monkeypatched case passing rather than like a capability the host stopped serving.
        """
        assert capabilities._UNBOUND_KINDS == {}, (
            f"a kind is refused rather than bound: {sorted(capabilities._UNBOUND_KINDS)}"
        )


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


class TestTheDurableScopeRequirementIsChecked:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F3.

    The class above proves atomicity only while the `DomainStore` and the `JobStore` share
    one connection, and that requirement lived in the `domain` fixture's docstring and
    nowhere else. The reviewer put the `DomainStore` on its own autocommit connection and
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
        store: JobStore,
        database: PlatformConfig,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The reviewer's mis-wiring, run through the real runner."""
        with connected(database, autocommit=True) as separate:
            outside = DomainStore(separate)
            outside.register_source(a_source())

            outcome = run_collect(tmp_path, store, outside, ScriptedTransport(a_page()))

            assert outcome.error is not None
            assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
            assert envelopes(separate) == 0
            assert outside.count_items(SOURCE_ID) == 0
            assert outside.read_cursor(SOURCE_ID, "items") is None

    def test_the_same_run_on_the_shared_connection_is_not_refused(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control. Without it the refusal above would pass against a check
        that refused every collection."""
        domain.register_source(a_source())

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert envelopes(connection) == 1


# --------------------------------------------------------------------------- #
# F1 — the page and record limits, counted by the platform
# --------------------------------------------------------------------------- #

#: Fetches until something stops it. Against `max_pages` this is the whole test; the
#: reviewer's version of it made 12 requests against a limit of 2 and succeeded.
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

#: Two pages, two items emitted from each, in two separate `emit_raw` calls.
TWO_PAGES = """
from addon_api import CollectOutcome, RawItem


def run(context):
    emitted = 0
    for page in range(2):
        response = context.fetch("items", {})
        items = [
            RawItem(
                item_key=f"{page}-{n}",
                payload=b"{}",
                content_type="application/json",
                envelope_ref=response.envelope_ref,
            )
            for n in range(2)
        ]
        context.emit_raw(items)
        emitted += len(items)
    return CollectOutcome(items_emitted=emitted)
"""

#: The page limit, caught and reported as success. A limit an add-on can absorb is advice.
SWALLOWS_THE_PAGE_LIMIT = """
from addon_api import CollectOutcome


def run(context):
    for _ in range(12):
        try:
            context.fetch("items", {})
        except BaseException:
            pass
    return CollectOutcome(items_emitted=0)
"""


def a_bounded_source(**limits: Any) -> SourceRow:
    """A source whose profile states the limits under test and leaves the rest default."""
    profile = {
        "hosts": ["api.example.com"],
        "endpoints": {"items": "/v1/items"},
        "port": 443,
        "limits": limits,
    }
    return a_source(outbound_profile=profile)


class TestThePageLimitIsEnforced:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F1.

    `p0-security.md` §Outbound requires a per-source page and record limit, and DP-008 D4
    puts every obligation in that section on the platform. `[측정]` Until 2026-08-18 the
    only consumer of `max_pages` in the tree was the one committed collector's own loop and
    `max_records` was read by nothing, so the integration test passed while proving only
    that the add-on cooperated. These are the counters, and each is written against an
    add-on that does *not* cooperate.
    """

    def test_a_collector_that_ignores_the_page_limit_is_stopped_at_it(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_bounded_source(max_pages=2))
        transport = ScriptedTransport(a_page(), a_page(), a_page(), a_page(), a_page())

        outcome = run_collect(tmp_path, store, domain, transport, addon_source=RUNAWAY_PAGES)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert len(transport.sent) == 2, "the third request must never have been sent"
        assert envelopes(connection) == 0

    def test_a_collector_inside_the_page_limit_is_not_stopped(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control. Without it the refusal above would pass against a counter
        that refused the first page."""
        domain.register_source(a_bounded_source(max_pages=20))
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.accepted
        assert len(transport.sent) == 1
        assert envelopes(connection) == 1

    def test_the_limit_permits_exactly_as_many_pages_as_it_states(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """Off-by-one, asserted rather than assumed: `max_pages=3` is three requests."""
        domain.register_source(a_bounded_source(max_pages=3))
        transport = ScriptedTransport(*[a_page() for _ in range(6)])

        run_collect(tmp_path, store, domain, transport, addon_source=RUNAWAY_PAGES)

        assert len(transport.sent) == 3

    def test_the_page_limit_cannot_be_swallowed(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """It goes through the same machinery as every other outbound refusal, so an add-on
        that catches it and reports success still fails the job."""
        domain.register_source(a_bounded_source(max_pages=1))
        transport = ScriptedTransport(a_page(), a_page())

        outcome = run_collect(
            tmp_path, store, domain, transport, addon_source=SWALLOWS_THE_PAGE_LIMIT
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert len(transport.sent) == 1
        assert envelopes(connection) == 0


class TestTheRecordLimitIsEnforced:
    def test_a_collector_that_emits_past_the_record_limit_is_refused(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_bounded_source(max_records=3))

        outcome = run_collect(
            tmp_path,
            store,
            domain,
            ScriptedTransport(a_page()),
            addon_source=RUNAWAY_RECORDS,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert envelopes(connection) == 0
        assert domain.count_items(SOURCE_ID) == 0

    def test_a_collector_inside_the_record_limit_persists_its_items(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The positive control for the assertion above."""
        domain.register_source(a_bounded_source(max_records=5000))

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert domain.count_items(SOURCE_ID) == 2

    def test_the_limit_counts_across_calls_rather_than_per_call(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """Two pages of two items each against a limit of three. Per-call counting would
        let this through, and the limit is on the run."""
        domain.register_source(a_bounded_source(max_records=3, max_pages=20))

        outcome = run_collect(
            tmp_path,
            store,
            domain,
            ScriptedTransport(a_page(), a_page()),
            addon_source=TWO_PAGES,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.count_items(SOURCE_ID) == 0


class TestTheRequestBudgetSpansTheRedirectChain:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F5, the multiplier half.

    *"`_fetch`'s redirect loop allows `max_redirects + 1` hops each with its own full
    read."* A per-hop timeout multiplies; one deadline pinned before the first hop does
    not. Asserted structurally here — that every hop is handed the same instant — because
    the wall-clock half of the property is `test_outbound_transport.py`'s, where there is a
    real socket to run out of time on.
    """

    def test_every_hop_of_one_fetch_shares_one_deadline(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())
        transport = BudgetRecordingTransport(
            a_page(status=302, location="https://api.example.com:443/v1/items"),
            a_page(),
        )

        run_collect(tmp_path, store, domain, transport)

        assert len(transport.budgets) == 2, "the redirect must have been followed"
        assert transport.budgets[0] is not None
        assert len({b.deadline for b in transport.budgets if b is not None}) == 1

    def test_the_deadline_is_pinned_rather_than_left_for_the_transport(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control for the assertion above: a `None` deadline would also compare equal
        across hops while bounding each hop separately."""
        domain.register_source(a_source())
        transport = BudgetRecordingTransport(a_page())

        run_collect(tmp_path, store, domain, transport)

        assert transport.budgets[0] is not None
        assert transport.budgets[0].deadline is not None


# --------------------------------------------------------------------------- #
# DP-018 — the credential the platform attaches and the add-on never sees
# --------------------------------------------------------------------------- #

CREDENTIAL_REF = "COSMA_SRC_PROBE_TOKEN"
CREDENTIAL_VALUE = "ncp-secret-value-42"


@pytest.fixture
def secret_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "secrets" / "env"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(f"{CREDENTIAL_REF}={CREDENTIAL_VALUE}\n", encoding="utf-8")
    store.chmod(0o600)
    monkeypatch.setenv("COSMA_SECRET_SOURCE", str(store))
    return store


def an_authenticated_source(ref: str = CREDENTIAL_REF, **overrides: Any) -> SourceRow:
    profile = {
        "hosts": ["api.example.com"],
        "endpoints": {"items": "/v1/items"},
        "port": 443,
        "credentials": [{"header": "X-NCP-APIGW-API-KEY", "ref": ref}],
    }
    return a_source(outbound_profile=profile, **overrides)


#: Reports whatever it can see. If a credential ever reaches an add-on, this finds it.
INSPECTING = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    seen = {
        "response_headers": dict(response.headers),
        "config": dict(context.config),
        "limits": context.limits.to_json(),
    }
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


class TestTheCredentialReachesTheRequestAndNothingElse:
    """DP-018. The add-on composes no URL, holds no credential, and opens no socket — and
    now the request it caused is authenticated anyway.

    Every assertion here is paired with the one that makes it mean something: the value is
    *present* on the wire, and *absent* everywhere the value could be recorded. Either half
    alone passes against a platform that attaches nothing at all.
    """

    def test_the_platform_attaches_the_credential_to_the_request(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        domain.register_source(an_authenticated_source())
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.accepted
        assert transport.headers[0]["X-NCP-APIGW-API-KEY"] == CREDENTIAL_VALUE

    def test_a_source_without_a_credential_sends_none(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control. Without it the assertion above could not tell attachment from a
        transport double that was handed a header by something else."""
        domain.register_source(a_source())
        transport = ScriptedTransport(a_page())

        run_collect(tmp_path, store, domain, transport)

        assert transport.headers[0] == {}

    def test_the_add_on_never_sees_the_value(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        """DP-008 D4, kept while a real request is authenticated. The add-on reports
        everything reachable from its context; the value is in none of it."""
        domain.register_source(an_authenticated_source())

        run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=INSPECTING
        )

        reported = _one_item_payload(domain)
        assert CREDENTIAL_VALUE not in reported
        assert CREDENTIAL_REF not in reported

    def test_the_value_is_in_no_recorded_envelope(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
        secret_store: Path,
    ) -> None:
        """`p0-security.md`: nothing recorded carries a credential. The header this source
        uses is in `PROTECTED_HEADERS`, which DP-018 D3 makes a precondition of using it —
        so this is the assertion that the precondition does what it was chosen for."""
        domain.register_source(an_authenticated_source())

        run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        row = connection.execute(
            "select request_summary::text, coalesce(response_headers::text, '') from raw_envelope"
        ).fetchone()
        assert row is not None
        assert CREDENTIAL_VALUE not in row[0] + row[1]
        # `[측정]` The control B7 asked for. `request_summary` is `{"url", "host"}` and can
        # never hold a header whatever `PROTECTED_HEADERS` contains, so the absence above is
        # only meaningful once something is known to have been recorded at all. The real
        # header-stripping assertion is `test_outbound_transport.py`'s, over a socket.
        assert "url" in row[0], "nothing was recorded, so the absence proves nothing"

    def test_the_value_is_in_no_log_line(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        log_stream: Any,
        secret_store: Path,
    ) -> None:
        """`[측정]` **This test was vacuous until 2026-08-19.**
        `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B7 instrumented it and found the stream
        held 1150 bytes, events `['job.transition']` only, and **zero `addon.*` events** —
        because `run_collect` bound no logger, so the capability layer's `_log` returned
        immediately. It could have written the credential in plaintext on every fetch and
        this assertion would have passed.

        A logger is now bound, and the control below asserts the capability layer actually
        wrote through it. An absence assertion over a stream nothing writes to is an
        assertion about the stream.
        """
        domain.register_source(an_authenticated_source())

        run_collect(tmp_path, store, domain, ScriptedTransport(a_page()), logger=logger)

        assert CREDENTIAL_VALUE not in log_stream.getvalue()

    def test_the_capability_layer_did_write_to_that_log(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        log_stream: Any,
        secret_store: Path,
    ) -> None:
        """The control the case above needs. Without it, binding a logger proves nothing —
        the stream could still be empty of anything the add-on layer produced."""
        domain.register_source(an_authenticated_source())

        run_collect(tmp_path, store, domain, ScriptedTransport(a_page()), logger=logger)

        assert "addon." in log_stream.getvalue(), "the capability layer logged nothing"


class TestAnUnresolvableCredentialStopsTheRequest:
    """`secret-setup.md` invariant 4, and DP-018 D5."""

    def test_a_missing_key_fails_the_job_as_configuration_invalid(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        domain.register_source(an_authenticated_source(ref="COSMA_SRC_PROBE_ABSENT"))
        transport = ScriptedTransport(a_page())

        outcome = run_collect(tmp_path, store, domain, transport)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID

    def test_no_anonymous_request_is_sent_in_its_place(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        """The failure this rule exists for: a source may answer an unauthenticated request
        with `200` and an error body, which would be stored as Raw and read as data."""
        domain.register_source(an_authenticated_source(ref="COSMA_SRC_PROBE_ABSENT"))
        transport = ScriptedTransport(a_page())

        run_collect(tmp_path, store, domain, transport)

        assert transport.sent == []

    def test_an_add_on_cannot_swallow_it_into_a_success(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        """The same rule the outbound refusals live under. A credential failure an add-on
        can absorb is a job that reports success having collected nothing, forever."""
        domain.register_source(an_authenticated_source(ref="COSMA_SRC_PROBE_ABSENT"))

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=SWALLOWING
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID

    def test_the_same_swallowing_add_on_succeeds_when_the_credential_resolves(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        """The positive control for the case above: the failure is the credential, not the
        swallowing."""
        domain.register_source(an_authenticated_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), addon_source=SWALLOWING
        )

        assert outcome.accepted


def _one_item_payload(domain: DomainStore) -> str:
    row = domain.read_source(SOURCE_ID)
    assert row is not None
    with domain.connection.cursor() as cursor:
        cursor.execute("select payload from raw_item")
        fetched = cursor.fetchone()
    assert fetched is not None
    return bytes(fetched[0]).decode("utf-8")


# --------------------------------------------------------------------------- #
# DP-020 — the body an add-on composes, through the capability layer
# --------------------------------------------------------------------------- #

#: What a DataLab collector looks like: one POST, a JSON body, a `results` array back.
POSTING = """
import json

from addon_api import CollectOutcome, RawItem


def run(context):
    asked = json.dumps({"startDate": "2026-08-01", "keywordGroups": [{"groupName": "a"}]})
    response = context.fetch("trend", {}, body=asked.encode("utf-8"))
    body = json.loads(response.body)
    items = [
        RawItem(
            item_key=group["title"],
            payload=json.dumps(group, sort_keys=True).encode("utf-8"),
            content_type="application/json",
            envelope_ref=response.envelope_ref,
        )
        for group in body["results"]
    ]
    context.emit_raw(items)
    return CollectOutcome(items_emitted=len(items))
"""

#: Sends a body to an endpoint the profile granted `GET`.
POSTING_TO_A_GET = """
from addon_api import CollectOutcome


def run(context):
    context.fetch("items", {}, body=b"{}")
    return CollectOutcome(items_emitted=0)
"""

#: Posts a body where the profile granted only GET, and absorbs the refusal.
SWALLOWING_A_BODY_REFUSAL = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.fetch("items", {}, body=b"{}")
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""

#: The same shape against the endpoint POST *was* granted for. The control.
SWALLOWING_A_GRANTED_POST = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.fetch("trend", {}, body=b"{}")
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""

TREND_PAGE = json.dumps({"results": [{"title": "a", "data": []}]}).encode("utf-8")


def a_posting_source(**limits: Any) -> SourceRow:
    profile: dict[str, Any] = {
        "hosts": ["api.example.com"],
        "endpoints": {
            "trend": {"path": "/search-trend/v1/search", "method": "POST"},
            "items": "/v1/items",
        },
        "port": 443,
    }
    if limits:
        profile["limits"] = limits
    return a_source(outbound_profile=profile)


class TestAnAddOnComposesItsBody:
    """DP-020 D2. The body is the add-on's, exactly as `params` always has been — and the
    destination is still the profile's, which is the property DP-008 D4 actually protects.
    """

    def test_the_body_reaches_the_transport(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_posting_source())
        transport = ScriptedTransport(a_page(body=TREND_PAGE))

        outcome = run_collect(tmp_path, store, domain, transport, addon_source=POSTING)

        assert outcome.accepted, outcome
        assert transport.sent[0].method == "POST"
        assert transport.sent[0].body is not None
        assert b"keywordGroups" in transport.sent[0].body

    def test_the_destination_is_still_the_profiles(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The control that matters. Whatever the body says, the host and path came from
        the operator-approved row."""
        domain.register_source(a_posting_source())
        transport = ScriptedTransport(a_page(body=TREND_PAGE))

        run_collect(tmp_path, store, domain, transport, addon_source=POSTING)

        assert transport.sent[0].host == "api.example.com"
        assert transport.sent[0].url.endswith("/search-trend/v1/search")

    def test_a_body_sent_to_a_get_endpoint_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """DP-020 D4. The add-on cannot upgrade a read the operator approved."""
        domain.register_source(a_posting_source())
        transport = ScriptedTransport(a_page())

        outcome = run_collect(
            tmp_path, store, domain, transport, addon_source=POSTING_TO_A_GET
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert transport.sent == []

    def test_an_oversized_body_is_refused_before_the_request(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_posting_source(max_request_bytes=8))
        transport = ScriptedTransport(a_page(body=TREND_PAGE))

        outcome = run_collect(tmp_path, store, domain, transport, addon_source=POSTING)

        assert outcome.error is not None
        assert transport.sent == []

    def test_a_body_refusal_cannot_be_swallowed(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """It goes through `_refused` like every other outbound rule, so an add-on that
        catches it and reports success still fails the job."""
        domain.register_source(a_posting_source())

        outcome = run_collect(
            tmp_path,
            store,
            domain,
            ScriptedTransport(a_page()),
            addon_source=SWALLOWING_A_BODY_REFUSAL,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT

    def test_the_same_add_on_succeeds_when_it_posts_where_post_was_granted(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The positive control for the case above: what failed was the refusal, not the
        swallowing."""
        domain.register_source(a_posting_source())

        outcome = run_collect(
            tmp_path,
            store,
            domain,
            ScriptedTransport(a_page(body=TREND_PAGE)),
            addon_source=SWALLOWING_A_GRANTED_POST,
        )

        assert outcome.accepted


# --------------------------------------------------------------------------- #
# F2 — the two doors ADVERSARIAL-REVIEW-2026-08-19 measured open
# --------------------------------------------------------------------------- #

#: Emits whatever came back without looking at the status. What the platform must catch.
IGNORES_STATUS = """
from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    context.emit_raw([
        RawItem("page-1", response.body, "application/json", envelope_ref=response.envelope_ref)
    ])
    return CollectOutcome(items_emitted=1)
"""

#: Sees the status, says what it decided, and emits anyway. The escape hatch, used properly.
ACCEPTS_STATUS = """
from addon_api import CollectOutcome, RawItem


def run(context):
    response = context.fetch("items", {})
    if response.status != 200:
        context.accept_status(response, "this source answers 404 when a query has no results")
    context.emit_raw([
        RawItem("page-1", response.body, "application/json", envelope_ref=response.envelope_ref)
    ])
    return CollectOutcome(items_emitted=1)
"""

#: Sees the status and raises, which is what all three real collectors do.
RAISES_ON_STATUS = """
from addon_api import AddonPermanent, CollectOutcome


def run(context):
    response = context.fetch("items", {})
    if response.status != 200:
        raise AddonPermanent(f"the source answered {response.status}")
    return CollectOutcome(items_emitted=0)
"""

#: Catches its own refusal. A control an add-on can absorb is not a control.
SWALLOWS_THE_STATUS_CHECK = """
from addon_api import CollectOutcome


def run(context):
    try:
        context.fetch("items", {})
    except BaseException:
        pass
    return CollectOutcome(items_emitted=0)
"""


class TestANonSuccessStatusCannotBeIgnored:
    """`ADVERSARIAL-REVIEW-2026-08-19.md` F2(b).

    The reviewer measured a collector that emitted from a `401` body: the job reported
    `SUCCEEDED` and a `{"errorCode": "SE01", "errorMessage": "unauthenticated"}` landed in
    `raw_item` as data. DP-018 D5 names that outcome as the one its rule exists to prevent,
    and the rule covered only a *named but unresolvable* credential.

    `[결정]` The platform does not decide what a status means — that is genuinely
    source-specific, and a `404` is "no results" to one API and "wrong endpoint" to another.
    What it enforces is that the add-on **decided**. Silence is a failure, which is the same
    shape `_check_no_refusal_was_swallowed` already has.
    """

    def test_emitting_from_a_non_success_response_without_deciding_fails_the_job(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain,
            ScriptedTransport(a_page(status=401, body=b'{"errorCode":"SE01"}')),
            addon_source=IGNORES_STATUS,
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.count_items(SOURCE_ID) == 0

    def test_returning_normally_after_one_fails_even_with_nothing_emitted(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """Not emitting is not deciding. A collector that saw a `401`, wrote nothing, and
        reported success has collected nothing and said everything was fine."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain,
            ScriptedTransport(a_page(status=503, body=b"{}")),
            addon_source=SWALLOWS_THE_STATUS_CHECK,
        )

        assert outcome.error is not None

    def test_an_add_on_that_raises_is_left_alone(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """What all three real collectors do. The check must not turn their own
        classification into a second, different failure."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain,
            ScriptedTransport(a_page(status=429, body=b"{}")),
            addon_source=RAISES_ON_STATUS,
        )

        assert outcome.error is not None
        assert "the source answered 429" in outcome.error.summary

    def test_an_add_on_that_accepts_the_status_may_emit_from_it(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The escape hatch, and the reason the platform does not simply refuse non-2xx: a
        source that answers `404` for an empty result set is a source whose `404` is data."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain,
            ScriptedTransport(a_page(status=404, body=b'{"items":[]}')),
            addon_source=ACCEPTS_STATUS,
        )

        assert outcome.accepted, outcome
        assert domain.count_items(SOURCE_ID) == 1

    def test_an_ordinary_success_needs_no_acceptance(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """The positive control. A check that demanded acceptance of every response would
        pass every assertion above and break every collector."""
        domain.register_source(a_source())

        outcome = run_collect(tmp_path, store, domain, ScriptedTransport(a_page()))

        assert outcome.accepted
        assert domain.count_items(SOURCE_ID) == 2

    def test_a_followed_redirect_is_not_a_status_to_decide(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        """A `302` the platform followed is not a response the add-on ever saw. Only the
        status of what `fetch` returns is the add-on's to judge."""
        domain.register_source(a_source())

        outcome = run_collect(
            tmp_path, store, domain,
            ScriptedTransport(
                a_page(status=302, location="https://api.example.com:443/v1/items"),
                a_page(),
            ),
        )

        assert outcome.accepted, outcome

    def test_the_envelope_is_still_recorded_when_the_run_fails(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """`[결정]` Raw losslessness is independent of add-on quality, so the refusal must not
        be implemented by discarding the response. It is not — the run fails before the
        completion transaction, so nothing persists at all, and the *reason* is in the
        attempt rather than in a half-written envelope."""
        domain.register_source(a_source())

        run_collect(
            tmp_path, store, domain,
            ScriptedTransport(a_page(status=401, body=b"{}")),
            addon_source=IGNORES_STATUS,
        )

        assert envelopes(connection) == 0


class TestADeclaredCredentialNeedMustBeGranted:
    """`ADVERSARIAL-REVIEW-2026-08-19.md` F2(a).

    The reviewer ran the real `collector.naver.blog` — which declares
    `needs_credential = true` — against a source whose profile granted none, with the secret
    store present and correct, and measured `gateway saw credentials: []`: **an anonymous
    request went out.** `needs_credential` is the add-on's request and the profile is the
    grant, and nothing compared them.
    """

    def test_a_source_granting_no_credential_to_an_add_on_that_needs_one_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())
        transport = ScriptedTransport(a_page())

        outcome = run_collect(
            tmp_path, store, domain, transport, addon_source=COLLECTOR, needs_credential=True
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
        assert transport.sent == [], "no anonymous request may be sent"

    def test_the_same_add_on_runs_once_the_profile_grants_one(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, secret_store: Path
    ) -> None:
        """The positive control. A check that refused every credential-needing add-on would
        pass above and make the three real collectors unrunnable."""
        domain.register_source(an_authenticated_source())

        outcome = run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page()), needs_credential=True
        )

        assert outcome.accepted, outcome

    def test_an_add_on_that_needs_none_is_unaffected(
        self, tmp_path: Path, store: JobStore, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())

        assert run_collect(
            tmp_path, store, domain, ScriptedTransport(a_page())
        ).accepted
