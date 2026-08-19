"""The whole operator loop, through the real API process and the real worker process.

`test_domain_api.py` checks each route in isolation against an in-process app. This
checks the thing an operator actually does, in the order they do it, through HTTP, with
nothing in the loop that a test constructed by hand:

    register → POST /collect → worker runs → POST /snapshots → POST /normalize
             → worker runs → GET /results → the dashboard screen those responses make

Two processes are started for real — `python -m addon_host` and `python -m addon_host.worker`
— because the point is that the composed entrypoints exist and work, not that
`create_app` can be called. The add-on layer is discovered from `addons/`, so the add-ons
under test are the installed ones.

**The transport is a stub, and the credential is a fixture.** This scenario runs on every
`pytest` invocation, so it must not spend a real quota or need a real key; what it proves is
that the *loop* closes. `test_naver_real_data.py` is the same collector and normalizer
against the real API, gated behind `--run-network --run-credential`. Neither is sufficient
alone: this one would pass against a source that does not exist, and that one says nothing
about the operator surface.

**The dashboard is rendered from the responses this run produced**, not from a fixture. A
screen assertion over hand-written JSON proves the renderer works and says nothing about
whether the API returns what the renderer reads.
"""

from __future__ import annotations

import fcntl
import json
import os
import ssl
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
import pytest
from domain import DomainStore, SourceRow
from platform_core.config import PlatformConfig
from platform_core.jobs.store import JobStore

from tests.conftest import (
    accepts_connections,
    free_port,
    wait_for_worker,
    wait_until,
    worker_environment,
)
from tests.test_dashboard import MARKUP_SECTION, VISIBLE_SECTION, toolchain_absent

pytestmark = pytest.mark.usefixtures("database")

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = EXPERIMENT_ROOT / "dashboard"

COLLECT_SOURCE = "naver-blog-loop"
NORMALIZE_SOURCE = "naver-blog-loop-normalized"

ID_REF = "COSMA_SRC_NAVER_BLOG_LOOP_CLIENT_ID"
SECRET_REF = "COSMA_SRC_NAVER_BLOG_LOOP_CLIENT_SECRET"
ID_VALUE = "loop-client-id"
SECRET_VALUE = "loop-client-secret"

PAGE_SIZE = 3

REQUEST_TIMEOUT = 15.0


# --------------------------------------------------------------------------- #
# A stand-in for the API Hub, demanding what the real one demands
# --------------------------------------------------------------------------- #


class BlogStub(BaseHTTPRequestHandler):
    """One full page of blog results, then an empty one. Authenticated.

    The shape is the vendor's documented one and the two NCP headers are required, so a
    run that gets through it exercised DP-018's attachment. It is still a stub: what it
    cannot tell anyone is whether the real endpoint agrees.
    """

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        parts = urlsplit(self.path)
        if parts.path != "/search/v1/blog":
            self._json({"errorCode": "SE05", "errorMessage": "Invalid search api"}, 404)
            return
        if not self.headers.get("X-NCP-APIGW-API-KEY-ID") or not self.headers.get(
            "X-NCP-APIGW-API-KEY"
        ):
            self._json({"errorCode": "SE01", "errorMessage": "unauthenticated"}, 401)
            return
        start = int(dict(_pairs(parts.query)).get("start", "1"))
        if start > 1:
            self._json({"total": PAGE_SIZE, "start": start, "display": 0, "items": []})
            return
        self._json(
            {
                "total": PAGE_SIZE,
                "start": start,
                "display": PAGE_SIZE,
                "items": [
                    {
                        "title": f"촉촉한 <b>수분크림</b> 후기 {n}",
                        "link": f"https://blog.naver.com/loop/{n}",
                        "description": f"발림성 {n}",
                        "bloggername": f"블로거{n}",
                        "bloggerlink": "https://blog.naver.com/loop",
                        "postdate": "20260801",
                    }
                    for n in range(PAGE_SIZE)
                ],
            }
        )

    def _json(self, body: object, status: int = 200) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        """Silent. The suite's output is the evidence."""


def _pairs(query: str) -> Iterator[tuple[str, str]]:
    for chunk in query.split("&"):
        if "=" in chunk:
            name, _, value = chunk.partition("=")
            yield name, value


@pytest.fixture(scope="session")
def loop_certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    directory = tmp_path_factory.mktemp("loop-tls")
    key, cert = directory / "stub.key", directory / "stub.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    return key, cert


@pytest.fixture(scope="session")
def blog_stub(loop_certificate: tuple[Path, Path]) -> Iterator[int]:
    key, cert = loop_certificate
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert, keyfile=key)
    server = ThreadingHTTPServer(("127.0.0.1", 0), BlogStub)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def secret_store(tmp_path: Path) -> Path:
    store = tmp_path / "secrets" / "env"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(
        f"{ID_REF}={ID_VALUE}\n{SECRET_REF}={SECRET_VALUE}\n", encoding="utf-8"
    )
    store.chmod(0o600)
    return store


@pytest.fixture
def registered(
    connection: psycopg.Connection[Any], blog_stub: int, loop_certificate: tuple[Path, Path]
) -> None:
    """Both sources, as an operator would register them before opening the dashboard."""
    domain = DomainStore(connection)
    domain.register_source(
        SourceRow(
            source_id=COLLECT_SOURCE,
            addon_id="collector.naver.blog",
            addon_version="0.1.0",
            kind="collector",
            config={"query": "수분크림", "display": PAGE_SIZE},
            config_schema_version="1",
            outbound_profile={
                "hosts": ["localhost"],
                "endpoints": {"blog": "/search/v1/blog"},
                "port": blog_stub,
                "allow_loopback": True,
                "limits": {"max_pages": 3},
                "credentials": [
                    {"header": "X-NCP-APIGW-API-KEY-ID", "ref": ID_REF},
                    {"header": "X-NCP-APIGW-API-KEY", "ref": SECRET_REF},
                ],
            },
        )
    )
    domain.register_source(
        SourceRow(
            source_id=NORMALIZE_SOURCE,
            addon_id="normalizer.naver.blog",
            addon_version="0.1.0",
            kind="normalizer",
            config={"language": "ko"},
            config_schema_version="1",
        )
    )


class Operator:
    """The dashboard's HTTP client, as a test can drive it."""

    def __init__(self, base: str) -> None:
        self.base = base

    def _call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        import urllib.error
        import urllib.request

        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"accept": "application/json"}
        if data is not None:
            headers["content-type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as failure:
            return failure.code, json.loads(failure.read())

    def get(self, path: str) -> Any:
        status, body = self._call("GET", path)
        assert status == 200, (path, status, body)
        return body

    def post(self, path: str, body: Any = None) -> tuple[int, Any]:
        return self._call("POST", path, body)


@pytest.fixture
def api(
    database: PlatformConfig, secret_store: Path, loop_certificate: tuple[Path, Path]
) -> Iterator[Operator]:
    """`python -m addon_host` — the composed platform and domain surface, as a process."""
    _, cert = loop_certificate
    port = free_port("127.0.0.1")
    environment = worker_environment(
        database,
        COSMA_API_HOST="127.0.0.1",
        COSMA_API_PORT=str(port),
        COSMA_SECRET_SOURCE=str(secret_store),
        SSL_CERT_FILE=str(cert),
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "addon_host"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_until(
            lambda: accepts_connections("127.0.0.1", port) or process.poll() is not None,
            f"the domain API accepts a connection on 127.0.0.1:{port}",
        )
        assert process.poll() is None, (
            "the API exited before accepting a connection:\n"
            f"{wait_for_worker(process).stderr}"
        )
        yield Operator(f"http://127.0.0.1:{port}")
    finally:
        process.terminate()
        wait_for_worker(process)


def run_worker(
    database: PlatformConfig, secret_store: Path, certificate: tuple[Path, Path]
) -> subprocess.CompletedProcess[str]:
    """`python -m addon_host.worker`, until it has executed exactly one job.

    `--max-jobs 1` and not a time limit. Each phase of the loop creates exactly one job,
    so the worker has nothing else to do once it has run it, and a time limit means every
    phase waits out the clock — `[측정]` this module took 6m14s that way and takes about a
    minute this way. `--max-seconds` stays as the backstop: if the job never arrives, the
    run ends with a report rather than hanging until pytest's own timeout.

    `SSL_CERT_FILE` points the worker's default TLS context at the stub's certificate.
    That is a *process* trust anchor and not a per-source one — no `source` row or profile
    field can widen it — which is the same property `SocketTransport`'s constructor
    argument gives, reached the way a real deployment would reach it.
    """
    _, cert = certificate
    return subprocess.run(
        [
            sys.executable, "-m", "addon_host.worker",
            "--max-jobs", "1", "--max-seconds", "30",
        ],
        env=worker_environment(
            database,
            COSMA_SECRET_SOURCE=str(secret_store),
            SSL_CERT_FILE=str(cert),
            COSMA_POLL_MS="50",
        ),
        capture_output=True,
        text=True,
        timeout=60,
    )


#: What `npm run domain:build` produces. Built once per session, then run per render.
DOMAIN_BUNDLE = DASHBOARD / "dist-domain-text" / "assets" / "domain-text.js"

BUILD_LOCK = DASHBOARD / ".domain-build.lock"


def build_domain_renderer() -> None:
    """Build the domain render entry, unless it is already current.

    `[측정]` The first version of this file ran `npm run domain` per render — a build and
    a run — and the module took **6m15s**. The build is the same inputs to the same
    output every time, so it happens once here and each render is a `node` invocation.
    Rebuilt from mtimes and taken under a file lock, which is what `test_dashboard.py`
    does with its own bundle and for the same two reasons: a run that changed nothing
    should not pay for a build, and two `pytest-xdist` workers must not write one output
    directory at once.
    """
    watched = [
        DASHBOARD / "package.json",
        DASHBOARD / "tsconfig.json",
        DASHBOARD / "vite.config.ts",
        *sorted((DASHBOARD / "src").iterdir()),
    ]
    inputs = [path for path in watched if path.is_file()]
    with BUILD_LOCK.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if DOMAIN_BUNDLE.is_file():
                built = DOMAIN_BUNDLE.stat().st_mtime
                if all(path.stat().st_mtime <= built for path in inputs):
                    return
            finished = subprocess.run(
                ["npm", "run", "--silent", "domain:build"],
                cwd=DASHBOARD,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            assert finished.returncode == 0, (
                f"the domain renderer did not build\n{finished.stdout}\n{finished.stderr}"
            )
            assert DOMAIN_BUNDLE.is_file(), f"the build produced no {DOMAIN_BUNDLE}"
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@pytest.fixture(scope="session", autouse=True)
def domain_renderer() -> None:
    """Skip rather than fail where the dashboard toolchain is not installed.

    Its dependencies are not part of the Python environment, so a checkout that has
    never run `npm install` would otherwise fail this scenario for a reason that has
    nothing to do with the operator loop.
    """
    absent = toolchain_absent()
    if absent is not None:
        pytest.skip(absent)
    build_domain_renderer()


def render_screen(payload: dict[str, Any]) -> tuple[str, str]:
    """The dashboard screen those responses make: visible text, and markup.

    Both forms, for the reason `detail-text.tsx` gives: the text is what a person
    reads, and the markup is the stronger of the two to search, because a value in an
    attribute is absent from the text and has still been delivered.
    """
    finished = subprocess.run(
        ["node", str(DOMAIN_BUNDLE)],
        cwd=DASHBOARD,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, f"the screen did not render\n{finished.stderr}"
    header, _, body = finished.stdout.partition("\n")
    assert header == VISIBLE_SECTION, f"no {VISIBLE_SECTION!r} header: {finished.stdout[:200]!r}"
    text, found, markup = body.partition(f"{MARKUP_SECTION}\n")
    assert found, f"the renderer printed no {MARKUP_SECTION!r} section"
    return text.strip(), markup.strip()


@pytest.fixture
def loop(
    api: Operator,
    database: PlatformConfig,
    secret_store: Path,
    loop_certificate: tuple[Path, Path],
    registered: None,
    store: JobStore,
) -> dict[str, Any]:
    """Drive the whole loop once and return every response it produced."""
    status, created = api.post(f"/sources/{COLLECT_SOURCE}/collect")
    assert status == 201, created
    collect_worker = run_worker(database, secret_store, loop_certificate)

    status, sealed = api.post(f"/sources/{COLLECT_SOURCE}/snapshots")
    assert status == 201, sealed
    snapshot_id = sealed["snapshot_id"]

    status, normalizing = api.post(
        f"/snapshots/{snapshot_id}/normalize", {"source_id": NORMALIZE_SOURCE}
    )
    assert status == 201, normalizing
    normalize_worker = run_worker(database, secret_store, loop_certificate)

    return {
        "collect_job": created,
        "collect_worker": collect_worker,
        "snapshot_id": snapshot_id,
        "normalize_job": normalizing,
        "normalize_worker": normalize_worker,
        "sources": api.get("/sources"),
        "raw": {COLLECT_SOURCE: api.get(f"/sources/{COLLECT_SOURCE}/raw")},
        "snapshots": api.get("/snapshots"),
        "results": api.get(f"/snapshots/{snapshot_id}/results"),
        "jobs": api.get("/jobs"),
    }


class TestTheLoopCloses:
    def test_collection_ran_and_left_raw(self, loop: dict[str, Any]) -> None:
        assert loop["raw"][COLLECT_SOURCE]["item_count"] == PAGE_SIZE
        assert loop["raw"][COLLECT_SOURCE]["envelope_count"] >= 1

    def test_the_snapshot_sealed_what_was_collected_and_verifies(
        self, loop: dict[str, Any]
    ) -> None:
        snapshot = loop["snapshots"]["snapshots"][0]
        assert snapshot["item_count"] == PAGE_SIZE
        assert snapshot["verifies"] is True

    def test_normalization_produced_one_schema_0_1_record_per_item(
        self, loop: dict[str, Any]
    ) -> None:
        results = loop["results"]["results"]
        assert len(results) == PAGE_SIZE
        for result in results:
            assert result["body"]["schema_version"] == "0.1"
            assert result["body"]["record_type"] == "document"

    def test_every_job_the_operator_started_succeeded(
        self, loop: dict[str, Any], store: JobStore
    ) -> None:
        states = {job["state"] for job in loop["jobs"]["jobs"]}
        assert states == {"SUCCEEDED"}, loop["collect_worker"].stderr

    def test_the_two_worker_runs_each_executed_a_job(self, loop: dict[str, Any]) -> None:
        """Two runs, two jobs. If normalization had been started by collection — which
        `project-state.md` §4 forbids — the first run would have executed both."""
        for phase in ("collect_worker", "normalize_worker"):
            report = json.loads(
                [line for line in loop[phase].stdout.splitlines() if line.startswith("{")][-1]
            )
            assert report["jobs_executed"] == 1, phase


class TestTheDashboardShowsIt:
    """The screen, rendered from the responses the run above produced.

    Not from a fixture: a screen assertion over hand-written JSON proves the renderer
    works and says nothing about whether the API returns what the renderer reads.
    """

    @pytest.fixture
    def screen(self, loop: dict[str, Any]) -> tuple[str, str]:
        return render_screen(
            {
                "sources": loop["sources"],
                "raw": loop["raw"],
                "snapshots": loop["snapshots"],
                "results": loop["results"],
                "open_source": COLLECT_SOURCE,
                "open_snapshot": loop["snapshot_id"],
            }
        )

    def test_the_source_and_what_it_collected_are_on_the_screen(
        self, screen: tuple[str, str]
    ) -> None:
        visible, _ = screen
        assert COLLECT_SOURCE in visible
        assert "collector" in visible
        assert str(PAGE_SIZE) in visible

    def test_the_snapshot_reports_that_it_verifies(self, screen: tuple[str, str]) -> None:
        visible, _ = screen
        assert "snapshot_id" in visible
        assert "verifies" in visible

    def test_the_normalized_records_are_on_the_screen(self, screen: tuple[str, str]) -> None:
        """The end of the loop: real collected text, normalized, on a screen."""
        visible, _ = screen
        assert "수분크림" in visible
        assert "2026-08-01" in visible
        assert "https://blog.naver.com/loop/0" in visible

    def test_the_markup_removal_rule_is_visible_in_its_effect(
        self, screen: tuple[str, str]
    ) -> None:
        """The source data carries `<b>` around the matched term. The screen must show the
        term without it — and the markup is searched rather than the text, because a tag
        that survived into the data would be gone from the text and still delivered."""
        _, markup = screen
        assert "촉촉한 수분크림 후기 0" in markup

    def test_the_normalizer_and_its_two_version_axes_are_shown(
        self, screen: tuple[str, str]
    ) -> None:
        visible, _ = screen
        assert "normalizer.naver.blog@0.1.0" in visible
        assert "out 0.1" in visible

    def test_the_credential_key_name_is_shown_and_no_value_is(
        self, screen: tuple[str, str]
    ) -> None:
        """`secret-setup.md`: the ref is a key name and may be shown; the value may not.
        Both halves are asserted, because either alone is satisfied by a blank screen."""
        visible, markup = screen
        assert ID_REF in visible
        assert "X-NCP-APIGW-API-KEY-ID" in visible
        assert ID_VALUE not in markup
        assert SECRET_VALUE not in markup

    def test_the_approved_endpoint_and_its_method_are_shown(
        self, screen: tuple[str, str]
    ) -> None:
        """An operator approving a source has to be able to see what it will request."""
        visible, _ = screen
        assert "/search/v1/blog" in visible
        assert "GET" in visible


class TestWhatTheScreenRefuses:
    def test_a_normalizer_source_offers_no_collect_button(
        self, loop: dict[str, Any]
    ) -> None:
        """The kinds are not interchangeable, and the screen says so before the API has
        to. The API refuses it too — `test_domain_api.py` has that half."""
        _, markup = render_screen(
            {
                "sources": loop["sources"],
                "raw": loop["raw"],
                "snapshots": loop["snapshots"],
                "results": {"results": []},
                "open_source": NORMALIZE_SOURCE,
                "open_snapshot": None,
            }
        )
        rows = markup.split("<tr")
        normalizer_row = next(row for row in rows if NORMALIZE_SOURCE in row)
        assert "collect</button>" not in normalizer_row
        assert "runs on a snapshot" in normalizer_row

    def test_a_snapshot_that_does_not_verify_cannot_be_normalized_from_the_screen(
        self, loop: dict[str, Any]
    ) -> None:
        """A tampered input must not look ready to run. The button is disabled and the
        problems are printed, because "the manifest digest differs" is what an operator
        acts on."""
        broken = json.loads(json.dumps(loop["snapshots"]))
        broken["snapshots"][0]["verifies"] = False
        broken["snapshots"][0]["problems"] = ["member 0 no longer matches its digest"]

        visible, markup = render_screen(
            {
                "sources": loop["sources"],
                "raw": loop["raw"],
                "snapshots": broken,
                "results": {"results": []},
                "open_source": None,
                "open_snapshot": None,
            }
        )

        assert "no longer matches its digest" in visible
        # Located in the snapshot's own row, not anywhere in the page. B7 measured that
        # "somewhere in the markup" is satisfied by a disabled control the operator was
        # never looking at.
        row = _snapshot_row(markup, loop["snapshot_id"])
        assert f">{NORMALIZE_SOURCE}</button>" in row
        assert "disabled" in row

    def test_a_verifying_snapshot_offers_the_button(self, loop: dict[str, Any]) -> None:
        """The positive control. A screen that disabled everything would pass above.

        `[측정]` **It did not do that until 2026-08-19.**
        `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B7: it split on `<tr` and took the first
        row containing the normalizer's name — but `SourceTable` renders before
        `SnapshotTable`, so it was inspecting the normalizer's **source** row, which carries
        no button at all. Making every normalize button `disabled` was GREEN, and so was
        leaving a disabled source's buttons live.

        The snapshot row is now identified by the thing only it contains — the snapshot's own
        identifier — and the button is located inside it rather than inferred from the row's
        text.
        """
        snapshot_id = loop["snapshot_id"]
        _, markup = render_screen(
            {
                "sources": loop["sources"],
                "raw": loop["raw"],
                "snapshots": loop["snapshots"],
                "results": {"results": []},
                "open_source": None,
                "open_snapshot": None,
            }
        )

        row = _snapshot_row(markup, snapshot_id)
        assert f">{NORMALIZE_SOURCE}</button>" in row, "the normalize button is not on this row"
        assert "disabled" not in row


def _snapshot_row(markup: str, snapshot_id: str) -> str:
    """The one table row for this snapshot.

    Identified by the snapshot's short identifier, which appears on no other row, rather
    than by the normalizer's name — which appears on the normalizer's *source* row too, and
    that is the row B7 found these assertions reading.
    """
    short = snapshot_id[:8]
    rows = [f"<tr{part}" for part in markup.split("<tr")[1:]]
    matching = [row for row in rows if short in row]
    assert len(matching) == 1, f"expected one row for snapshot {short}, found {len(matching)}"
    return matching[0]


def _unused_guard() -> None:
    """`os` and `time` are imported for the process fixtures' benefit under some
    platforms; naming them here keeps the linter honest about why they are present."""
    assert os is not None and time is not None


class TestTheImporterHasAnOperatorControlToo:
    """charter required flow 12, for the dataset half.

    `[확인 사실]` Until 2026-08-20 the screen offered `collect` and `seal snapshot` to a
    collector and the words *"runs on a snapshot"* to everything else — so an importer,
    which runs on neither a snapshot nor a socket, was told it runs on a snapshot and
    given no control at all. The API had no route to give it one.
    """

    def _screen_with_an_importer(self, loop: dict[str, Any]) -> tuple[str, str]:
        sources = json.loads(json.dumps(loop["sources"]))
        sources["sources"].append(
            {
                "source_id": "probe-rows",
                "addon_id": "importer.local.jsonl",
                "addon_version": "0.1.0",
                "kind": "importer",
                "config": {"key_field": "id"},
                "config_schema_version": "1",
                "credential_ref": None,
                "outbound_profile": None,
                "input_profile": {"root": "/approved", "inputs": {"rows": "rows.jsonl"}},
                "data_class": "local",
                "enabled": True,
                "created_at": "2026-08-20T00:00:00+00:00",
                "updated_at": "2026-08-20T00:00:00+00:00",
            }
        )
        return render_screen(
            {
                "sources": sources,
                "raw": loop["raw"],
                "snapshots": loop["snapshots"],
                "results": {"results": []},
                "open_source": "probe-rows",
                "open_snapshot": None,
            }
        )

    def test_an_importer_row_offers_import_and_seal(self, loop: dict[str, Any]) -> None:
        _, markup = self._screen_with_an_importer(loop)

        row = next(row for row in markup.split("<tr") if "probe-rows" in row)
        assert "import</button>" in row
        assert "seal snapshot</button>" in row

    def test_an_importer_row_offers_no_collect(self, loop: dict[str, Any]) -> None:
        """It opens no socket. `manifest.py` refuses an importer that declares a host."""
        _, markup = self._screen_with_an_importer(loop)

        row = next(row for row in markup.split("<tr") if "probe-rows" in row)
        assert "collect</button>" not in row

    def test_a_collector_row_still_offers_no_import(self, loop: dict[str, Any]) -> None:
        """The control. Adding a verb to one kind must not add it to the others."""
        _, markup = self._screen_with_an_importer(loop)

        row = next(row for row in markup.split("<tr") if COLLECT_SOURCE in row)
        assert "collect</button>" in row
        assert "import</button>" not in row

    def test_the_approved_input_grant_is_read_back_on_the_screen(
        self, loop: dict[str, Any]
    ) -> None:
        """An operator approved a root and a member list; they have to be able to see it."""
        visible, _ = self._screen_with_an_importer(loop)

        assert "/approved" in visible
        assert "rows.jsonl" in visible
