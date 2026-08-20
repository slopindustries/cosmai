"""SEC-002 and SEC-004 executed against a running operator API.

Copy-adapted from ``experiments/integrated-p0/tests/test_api.py``. Both
scenarios say in as many words that a document's claim is not evidence.
SEC-002: *"'Bound to loopback' as a claim in a document is not evidence; the
recorded address is."* SEC-004: *"A run in which nothing leaked is therefore not
evidence."* So every test here works from an artefact that was produced rather
than described — the address read back off a socket the process bound, and the
bytes an HTTP response and a log file actually contained.

**What DP-032 changes, and what it drops.** P0-A's database was a repository-
local Unix-socket cluster with no TCP listener at all (DP-006 D2); two of
P0-A's SEC-002 checks existed only to prove that absence —
``no_postgresql_tcp_listener`` and ``the_database_session_is_not_a_tcp_connection``.
DP-032 D1/D3 deliberately puts the database on a real TCP listener (the shared
server, loopback-bound but TCP), so both checks would now assert something
DP-032 made false on purpose; they are dropped rather than ported, and the
drop is recorded in the Task 7/8 report as a deviation rather than silently
omitted. Every other SEC-002 check is about the *operator API's* own bind
address, which SEC-002 still constrains exactly as P0-A did, and every SEC-004
check is about redaction, which DP-032 does not touch at all.

Three mechanics are worth reading before the tests.

**The probe collects, then the tests assert.** ``redaction_probe`` runs the
whole of SEC-004's Action — create the marked job, fail it permanently, read
all four representations, stop the API — and freezes the results. Each test is
then a read-only assertion over the same set of artefacts. It is module-scoped
and owns its own job row rather than a cloned database (P0 had one per test;
DP-032 gives P1 one shared ``cosmai_test`` — see ``tests/conftest.py``'s module
docstring), so its teardown deletes only the rows it created, by id, and never
races the blanket ``_reset_job_tables`` another module's test might run: every
test in *this* module reads the probe's frozen artefacts or touches no job
table at all, so nothing here calls a blanket reset while the probe's row is
still live.

**Every marker is injected to be found.** The payload carries a distinctive
value under every key in the contract's redaction set *and* one under an
ordinary key. The ordinary one is the detection control: if it were also
missing, "no marker was found" would be indistinguishable from "the search does
not work".

**The platform does not log payloads, so the log search needs its own control.**
Searching the worker's log for a marker that the platform was never going to
write there is a weak assertion on its own.
``test_sec_004_the_structured_log_masks_a_payload_it_is_handed`` supplies the
missing half by handing the marked payload straight to a logger and observing
what comes out.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from platform_core.api.__main__ import (
    EXIT_CONFIGURATION_INVALID,
    EXIT_OK,
    EXIT_UNAVAILABLE,
)
from platform_core.api.app import DEFAULT, PROTECTED, PROTECTED_FIELD, attempt_view
from platform_core.config import DEFAULT_API_HOST, PlatformConfig
from platform_core.db.connection import connect
from platform_core.db.migrate import SCHEMA
from platform_core.errors import ErrorClass, PlatformPermanentError
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from platform_core.obs.redaction import REDACTION_MARKER
from platform_core.worker import (
    EXIT_CONFIGURATION_INVALID as WORKER_EXIT_CONFIGURATION_INVALID,
)
from platform_core.worker import EXIT_OK as WORKER_EXIT_OK
from platform_core.worker import EXIT_UNAVAILABLE as WORKER_EXIT_UNAVAILABLE
from platform_core.worker import parse_report
from tests.conftest import (
    LEASE_SECONDS,
    WORKER,
    api_command,
    free_port,
    log_events,
    run_worker,
    running_api,
    wait_for_worker,
    worker_environment,
)
from tests.test_obs import CONTRACT_REDACTED_KEYS

IPV6_LOOPBACK = "::1"

MAX_ATTEMPTS = 3

REQUEST_TIMEOUT_SECONDS = 10.0

#: Long enough to let an interpreter start; a process that was supposed to
#: refuse its configuration and is still alive after this is the failure, not
#: the wait.
REFUSAL_TIMEOUT_SECONDS = 30.0

#: One distinctive value per redacted key, so a leak says which key leaked.
SENSITIVE_MARKERS: dict[str, str] = {
    key: f"marker-must-not-leak-{key}-42" for key in sorted(CONTRACT_REDACTED_KEYS)
}

ORDINARY_KEY = "note"

ORDINARY_MARKER = "marker-must-survive-42"

MARKED_PAYLOAD: dict[str, Any] = {**SENSITIVE_MARKERS, ORDINARY_KEY: ORDINARY_MARKER}

UNRELATED_NAME = "COSMA_TYPO_LEASE_SECONDS"

UNRELATED_VALUE = "45"


@pytest.fixture(autouse=True)
def _schema_ready(_migrations_applied: None) -> None:
    """Every test in this module eventually asks the API to touch the job
    tables — even a SEC-002 bind test does, through ``/health`` — so this file
    cannot rely on collection order putting ``test_migrate.py`` (or another
    module's `job_store`-dependent test) ahead of it to have applied the
    migrations first. `[측정]` Without this, running ``test_api.py`` on its own
    (or first in the suite) fails several tests with ``relation "cosmai.job"
    does not exist``, because `tests/conftest.py`'s session-scoped
    `_reset_schema` only creates an *empty* schema — populating it is
    `_migrations_applied`'s job, and nothing here was requesting it. Autouse,
    function-scoped, depending on the session-scoped fixture: applied once,
    the same as every other module that needs it.
    """


def refused_api(config: PlatformConfig, **overrides: str) -> subprocess.CompletedProcess[str]:
    """Start the API entrypoint and collect the exit it was expected to make.

    Not ``running_api``: that one waits for a listening socket, and the whole
    point of these cases is that no socket is ever bound.
    """
    process = subprocess.Popen(
        api_command(),
        env=worker_environment(config, **overrides),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return wait_for_worker(process, timeout=REFUSAL_TIMEOUT_SECONDS)


# --------------------------------------------------------------------------- #
# SEC-002 — the bound address, observed
# --------------------------------------------------------------------------- #


def started_event(finished: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    events = [record for record in log_events(finished.stderr) if record["event"] == "api.started"]
    assert len(events) == 1, finished.stderr
    return events[0]


@pytest.mark.parametrize("host", [DEFAULT_API_HOST, IPV6_LOOPBACK])
def test_sec_002_the_api_binds_a_loopback_address_and_records_the_one_it_got(
    platform_config: PlatformConfig, host: str
) -> None:
    """Steps 1, 2 and 7. The recorded address comes off the socket, not the setting.

    ``::1`` is in the same test as ``127.0.0.1`` because the scenario's step 7 is
    the same observation on the other family: IPv6 loopback is loopback, and an
    implementation that only understood dotted quads would refuse it.
    """
    with running_api(platform_config, host=host) as api:
        response = httpx.get(f"{api.base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"
    finished = api.collected()
    assert finished.returncode == EXIT_OK, finished.stderr

    started = started_event(finished)
    assert ipaddress.ip_address(started["host"]).is_loopback
    assert started["host"] == host
    assert started["port"] == api.port
    print(f"\n[measured] SEC-002: the API bound to {started['host']}:{started['port']}")


def test_sec_002_the_api_is_unreachable_from_every_non_loopback_address_of_the_host(
    platform_config: PlatformConfig,
) -> None:
    """Step 3, over every non-loopback address of this host that a client could aim at."""
    addresses = _non_loopback_addresses()
    if not addresses:  # pragma: no cover - depends on the host
        pytest.skip("this host has no non-loopback address to attempt a connection from")
    with running_api(platform_config) as api:
        assert httpx.get(f"{api.base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS).status_code
        for address in addresses:
            with pytest.raises(OSError):
                socket.create_connection((address, api.port), timeout=1.0).close()
    assert api.collected().returncode == EXIT_OK
    print(f"\n[measured] SEC-002: no connection accepted on host addresses {addresses}")


def _non_loopback_addresses() -> list[str]:
    """Every non-loopback address of this host that a client could aim at.

    Two sources, because neither is complete on its own: the host's own name
    may resolve to nothing useful, and the routing table knows only the
    address that would be used to leave the machine. No packet is sent — a
    connected UDP socket only picks a route.
    """
    found: set[str] = set()
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None):
            found.add(str(entry[4][0]).split("%")[0])
    except OSError:
        pass
    for family, target in ((socket.AF_INET, "192.0.2.1"), (socket.AF_INET6, "2001:db8::1")):
        try:
            with socket.socket(family, socket.SOCK_DGRAM) as probe:
                probe.connect((target, 9))
                found.add(str(probe.getsockname()[0]).split("%")[0])
        except OSError:
            continue
    routable: list[str] = []
    for candidate in sorted(found):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not address.is_loopback and not address.is_link_local:
            routable.append(candidate)
    return routable


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "example.com", "localhost"])
def test_sec_002_the_api_entrypoint_refuses_a_non_loopback_bind(
    platform_config: PlatformConfig, host: str
) -> None:
    """Step 6. ``CONFIGURATION_INVALID``, and no listener anywhere."""
    finished = refused_api(platform_config, COSMA_API_HOST=host)
    assert finished.returncode == EXIT_CONFIGURATION_INVALID, finished.stderr
    assert "CONFIGURATION_INVALID" in finished.stderr
    assert "COSMA_API_HOST" in finished.stderr
    assert host in finished.stderr, "the rejected address is named"
    assert "api.started" not in finished.stderr, "nothing was bound"


def test_sec_002_the_wildcard_bind_is_not_quietly_replaced_by_loopback(
    platform_config: PlatformConfig,
) -> None:
    """The behavior SEC-002 forbids by name, observed on the process rather than the parser.

    A configuration guard that refused ``0.0.0.0`` while the entrypoint bound
    loopback anyway would satisfy every unit test and none of the scenario. The
    proof is that the port stays closed.
    """
    port = free_port(DEFAULT_API_HOST)
    finished = refused_api(platform_config, COSMA_API_HOST="0.0.0.0", COSMA_API_PORT=str(port))
    assert finished.returncode == EXIT_CONFIGURATION_INVALID, finished.stderr
    with pytest.raises(OSError):
        socket.create_connection((DEFAULT_API_HOST, port), timeout=1.0).close()


def test_sec_002_the_two_entrypoints_use_the_same_exit_statuses() -> None:
    """One documented number per condition, in both processes.

    Two spellings of one closed set drift, and a supervisor that learned to
    tell ``78`` from ``1`` on the worker would silently mis-read the API.
    """
    assert EXIT_OK == WORKER_EXIT_OK
    assert EXIT_UNAVAILABLE == WORKER_EXIT_UNAVAILABLE
    assert EXIT_CONFIGURATION_INVALID == WORKER_EXIT_CONFIGURATION_INVALID


# --------------------------------------------------------------------------- #
# The API's own behavior, which the SEC-004 assertions rest on
# --------------------------------------------------------------------------- #


def test_an_unknown_job_is_a_404(platform_config: PlatformConfig) -> None:
    absent = uuid4()
    with running_api(platform_config) as api:
        for path in (f"/jobs/{absent}", f"/jobs/{absent}/attempts"):
            response = httpx.get(f"{api.base_url}{path}", timeout=REQUEST_TIMEOUT_SECONDS)
            assert response.status_code == 404, response.text


def test_an_unrecognised_debug_value_is_rejected_rather_than_read_as_default(
    platform_config: PlatformConfig,
) -> None:
    """A typo must not be interpreted, in either direction."""
    absent = uuid4()
    with running_api(platform_config) as api:
        response = httpx.get(
            f"{api.base_url}/jobs/{absent}/attempts",
            params={"debug": "PROTECTED"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    assert response.status_code == 422, response.text


def test_sec_003_case_f_the_api_entrypoint_reports_an_unknown_variable_and_runs(
    platform_config: PlatformConfig,
) -> None:
    """SEC-003 case f for the second entrypoint: reported, and it still serves."""
    with running_api(platform_config, **{UNRELATED_NAME: UNRELATED_VALUE}) as api:
        assert (
            httpx.get(f"{api.base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS).status_code == 200
        )
    finished = api.collected()
    assert finished.returncode == EXIT_OK, finished.stderr
    recorded = log_events(finished.stderr)
    warnings = [record for record in recorded if record["event"] == "api.configuration_warning"]
    assert len(warnings) == 1, recorded
    assert UNRELATED_NAME in warnings[0]["detail"]
    assert not [record for record in recorded if "configuration_invalid" in record["event"]]


# --------------------------------------------------------------------------- #
# SEC-004 — the redaction boundary across every artefact one failure produces
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RedactionProbe:
    """Every artefact SEC-004 step 3 names, captured once and then only read."""

    job_id: UUID
    correlation_id: str
    worker_log: str
    worker_report: dict[str, Any]
    api_log: str
    default_job: dict[str, Any]
    default_attempts: dict[str, Any]
    protected_attempts: dict[str, Any]

    @property
    def artefacts(self) -> dict[str, str]:
        """Each artefact as text under a name, so a failure says where it was found."""
        return {
            "worker metric report": json.dumps(self.worker_report),
            **self.job_artefacts,
        }

    @property
    def job_artefacts(self) -> dict[str, str]:
        """The artefacts that are about one job, and must therefore carry its identity.

        The worker's metric report is excluded: it is a per-process reading
        with no job context, so requiring a correlation identifier in it would
        be asserting a shape CONTRACT-JOB@0.1 does not give it.
        """
        return {
            "worker structured log": self.worker_log,
            "API structured log": self.api_log,
            "default job representation": json.dumps(self.default_job),
            "default attempts representation": json.dumps(self.default_attempts),
            "protected attempts representation": json.dumps(self.protected_attempts),
        }

    @property
    def attempt(self) -> Mapping[str, Any]:
        attempts = self.default_attempts["attempts"]
        assert len(attempts) == 1, attempts
        first: Mapping[str, Any] = attempts[0]
        return first

    @property
    def protected_attempt(self) -> Mapping[str, Any]:
        attempts = self.protected_attempts["attempts"]
        assert len(attempts) == 1, attempts
        first: Mapping[str, Any] = attempts[0]
        return first


@pytest.fixture(scope="module")
def redaction_probe(platform_config: PlatformConfig) -> Iterator[RedactionProbe]:
    """SEC-004's Action, steps 1 to 3, with every artefact frozen for inspection.

    Module-scoped, so one execution serves every read-only assertion below
    instead of replaying a several-second setup once per test. DP-032 gives
    this fixture no database of its own to clone (P0's ``cloned_database``);
    it creates exactly one job in the shared ``cosmai_test`` database and
    deletes exactly that job's rows, by id, on the way out — see the module
    docstring for why that does not race another test's blanket reset.
    """
    quiet = StructuredLogger(stream=StringIO(), level="DEBUG")
    with connect(platform_config, autocommit=True) as handle:
        store = JobStore(handle, platform_config, logger=quiet, metrics=MetricsRegistry())
        job_id = store.create_job("fail_permanent", MARKED_PAYLOAD, max_attempts=MAX_ATTEMPTS)
        row = store.read_job(job_id)
    assert row is not None
    correlation_id = str(row["correlation_id"])

    try:
        # 2. Run it so the failure path, error_summary and error_detail are populated.
        finished = run_worker(platform_config, "--once")
        assert finished.returncode == 0, finished.stderr

        # 3. Read every representation while the API is up.
        with (
            running_api(platform_config) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            default_job = client.get(f"/jobs/{job_id}")
            default_attempts = client.get(f"/jobs/{job_id}/attempts")
            protected_attempts = client.get(
                f"/jobs/{job_id}/attempts", params={"debug": PROTECTED}
            )
        api_process = api.collected()
        for response in (default_job, default_attempts, protected_attempts):
            assert response.status_code == 200, response.text

        yield RedactionProbe(
            job_id=job_id,
            correlation_id=correlation_id,
            worker_log=finished.stderr,
            worker_report=parse_report(finished.stdout),
            api_log=api_process.stderr,
            default_job=default_job.json(),
            default_attempts=default_attempts.json(),
            protected_attempts=protected_attempts.json(),
        )
    finally:
        with connect(platform_config, autocommit=True) as handle:
            handle.execute(f"delete from {SCHEMA}.platform_effect where job_id = %s", (job_id,))
            handle.execute(f"delete from {SCHEMA}.job_attempt where job_id = %s", (job_id,))
            handle.execute(f"delete from {SCHEMA}.job where id = %s", (job_id,))


def test_sec_004_the_failure_path_was_actually_reached(redaction_probe: RedactionProbe) -> None:
    """The precondition. Every assertion below is about what this failure emitted."""
    assert redaction_probe.default_job["state"] == JobState.FAILED
    assert redaction_probe.default_job["terminal_reason"] == ErrorClass.PLATFORM_PERMANENT
    attempt = redaction_probe.attempt
    assert attempt["outcome"] == AttemptOutcome.PERMANENT_FAILURE
    assert attempt["error_class"] == ErrorClass.PLATFORM_PERMANENT
    assert attempt["error_summary"], "a summary is populated"
    assert attempt["error_detail_present"] is True, "there is protected detail to withhold"


@pytest.mark.parametrize("key", sorted(SENSITIVE_MARKERS))
def test_sec_004_no_marker_under_a_redacted_key_appears_in_any_artefact(
    redaction_probe: RedactionProbe, key: str
) -> None:
    marker = SENSITIVE_MARKERS[key]
    for name, text in redaction_probe.artefacts.items():
        assert marker not in text, f"{key} leaked into the {name}"


def test_sec_004_the_ordinary_marker_survives_so_the_search_would_have_found_a_leak(
    redaction_probe: RedactionProbe,
) -> None:
    """The detection control. Without it the test above proves nothing."""
    payload = redaction_probe.default_job["payload"]
    assert payload[ORDINARY_KEY] == ORDINARY_MARKER
    assert ORDINARY_MARKER in json.dumps(redaction_probe.default_job)


@pytest.mark.parametrize("key", sorted(SENSITIVE_MARKERS))
def test_sec_004_the_key_name_survives_and_the_marker_says_a_value_was_removed(
    redaction_probe: RedactionProbe, key: str
) -> None:
    """Knowing a token was present is diagnostic; its value is not."""
    payload = redaction_probe.default_job["payload"]
    assert key in payload, "the key name survives"
    assert payload[key] == REDACTION_MARKER


def test_sec_004_error_detail_is_absent_from_the_default_representation(
    redaction_probe: RedactionProbe,
) -> None:
    assert redaction_probe.default_attempts["representation"] == DEFAULT
    assert PROTECTED_FIELD not in redaction_probe.attempt
    assert PROTECTED_FIELD not in json.dumps(redaction_probe.default_job)


def test_sec_004_error_detail_is_present_in_the_protected_representation(
    redaction_probe: RedactionProbe,
) -> None:
    """Reachable, explicitly, and only through the representation that says so."""
    assert redaction_probe.protected_attempts["representation"] == PROTECTED
    detail = redaction_probe.protected_attempt[PROTECTED_FIELD]
    assert detail, "the protected representation carries the detail it exists for"


def test_sec_004_the_correlation_identifier_is_intact_in_every_artefact(
    redaction_probe: RedactionProbe,
) -> None:
    """A redacted correlation identifier would make diagnosis impossible."""
    identifier = redaction_probe.correlation_id
    for name, text in redaction_probe.job_artefacts.items():
        assert identifier in text, f"the correlation identifier is missing from the {name}"
    assert redaction_probe.attempt["correlation_id"] == identifier
    assert redaction_probe.default_job["correlation_id"] == identifier


def test_sec_004_metric_labels_carry_no_payload_derived_value(
    redaction_probe: RedactionProbe,
) -> None:
    """The metric labels are the closed sets of ``jobs.state``, not payload data."""
    metrics = json.dumps(redaction_probe.worker_report["metrics"])
    for marker in (*SENSITIVE_MARKERS.values(), ORDINARY_MARKER):
        assert marker not in metrics
    assert redaction_probe.worker_report["metrics"]["transitions"][JobState.FAILED] == 1


def test_sec_004_protected_does_not_mean_unredacted(job_store: JobStore) -> None:
    """The clause the probe above cannot reach, with its own detection control.

    ``fail_permanent`` builds its own detail, so the markers in that job's
    payload never enter ``error_detail`` and the probe's protected
    representation is therefore only evidence that detail is *reachable*. Here
    the detail itself carries a marker under every redacted key, written
    through the same completion path a handler uses, and the protected
    representation is read back from the stored row. The ordinary marker in
    the same mapping survives, which is what makes the masking an observation
    rather than an absence.
    """
    job_id = job_store.create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
    claimed = job_store.claim_next(WORKER, LEASE_SECONDS)
    assert claimed is not None
    completion = job_store.complete_permanent(
        job_id,
        claimed.attempt_id,
        WORKER,
        PlatformPermanentError(
            "the permanent failure injector refused this attempt",
            {**MARKED_PAYLOAD, "attempt_no": claimed.attempt_no},
        ),
    )
    assert completion.accepted

    rows = job_store.read_attempts(job_id)
    assert len(rows) == 1
    view = attempt_view(rows[0], protected=True)
    # `default=str` because this is the row as the store returns it, before the
    # endpoint's encoder has turned its identifiers and timestamps into strings.
    rendered = json.dumps(view, default=str)
    detail = view[PROTECTED_FIELD]
    for key, marker in SENSITIVE_MARKERS.items():
        assert detail[key] == REDACTION_MARKER, key
        assert marker not in rendered
    assert detail[ORDINARY_KEY] == ORDINARY_MARKER, "detection control failed"
    assert detail["attempt_no"] == claimed.attempt_no, "the diagnosis survives"
    assert PROTECTED_FIELD not in attempt_view(rows[0], protected=False)


def test_sec_004_the_structured_log_masks_a_payload_it_is_handed() -> None:
    """The log channel's own detection control.

    The platform never writes a payload into an event, so searching a real log
    for a marker is an assertion about what was not attempted. This attempts
    it.
    """
    stream = StringIO()
    StructuredLogger(stream=stream, level="DEBUG").info("probe.event", payload=MARKED_PAYLOAD)
    written = stream.getvalue()
    for key, marker in SENSITIVE_MARKERS.items():
        assert marker not in written, key
        assert key in written, "the key name survives"
    assert ORDINARY_MARKER in written, "detection control failed"
    assert written.count(REDACTION_MARKER) == len(SENSITIVE_MARKERS)
