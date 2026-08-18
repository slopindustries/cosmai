"""The socket half of the guard, against a real server — and `collector.naver.blog` on it.

`test_outbound_policy.py` covers everything `domain.outbound` can decide without a socket,
which is most of it. What is left needs one: a name that resolves, a connection that opens,
bytes that keep arriving, and a clock that runs out. `SEC-004` is entirely in that half —
"oversized/slow response는 bounded failure로 종료되고 worker를 무기한 점유하지 않는다" is
not a claim a pure function can make.

**The known obstacle, decided in advance.** `EXP-003` records it: the DNS rule blocks
loopback, so a local stub is unreachable through the production path unless something is
relaxed. What is relaxed is the per-source `allow_loopback` flag, and the experiment record
fixed the price in advance — **two** tests, not one. `TestLoopbackIsOnlyReachableByFlag`
holds both: with the flag off a loopback address is actually refused, and no source in the
repository sets it. The first is the positive control without which the second proves
nothing.

**The certificate.** The stub speaks real TLS with a certificate generated per session, and
`SocketTransport` takes its `ssl.SSLContext` as a constructor argument. That is a
*per-process* trust anchor and not a per-source one: no `source` row, profile field, or
environment variable can widen it, and `test_the_default_context_rejects_this_stub` is the
control proving the trust is doing work rather than being absent.

The last class runs the installed `addons/collector.naver.blog` through `JobRunner`, the
capability layer, and this transport, over a socket, into the database. It is the only test
in the suite where nothing between the add-on and the bytes is a double. It carries no
credential — `OQ-009` has not settled what one looks like — so the stub demands none, and
what it therefore does **not** show is stated in its own docstring rather than implied.
"""

from __future__ import annotations

import json
import ssl
import subprocess
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.outbound import OutboundProfile, Refusal, RefusalReason, resolve
from domain.transport import SocketTransport, TransportLimits, TransportUnavailable
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]

#: Small enough that a test can exceed it in one write, and nowhere near a real limit.
SMALL_BODY_LIMIT = 2048
#: The stub sleeps far longer than this, so a bounded failure is the only way out.
SHORT_READ_TIMEOUT = 1.0

BLOG_PAGE_SIZE = 10


# --------------------------------------------------------------------------- #
# A real HTTPS stub
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A self-signed certificate for `localhost`, generated once per session.

    `openssl` rather than a library because neither `cryptography` nor `trustme` is a
    dependency of this experiment, and adding one to reach a stub would be a dependency
    the deliverable does not need.
    """
    directory = tmp_path_factory.mktemp("tls")
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


class StubHandler(BaseHTTPRequestHandler):
    """Four behaviours, one per rule that needs a live server to be exercised."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        parts = urlsplit(self.path)
        match parts.path:
            case "/v1/items":
                self._json({"items": [{"id": 1}, {"id": 2}], "next": 3})
            case "/v1/huge":
                self._bytes(b"x" * (SMALL_BODY_LIMIT * 4))
            case "/v1/slow":
                time.sleep(SHORT_READ_TIMEOUT * 6)
                self._bytes(b"late")
            case "/v1/redirect":
                self.send_response(302)
                self.send_header("Location", "https://elsewhere.example.net/v1/items")
                self.send_header("Content-Length", "0")
                self.end_headers()
            case "/blog":
                self._json(self._blog_page(parse_qs(parts.query)))
            case _:
                self._bytes(b"not found", status=404)

    @staticmethod
    def _blog_page(query: dict[str, list[str]]) -> dict[str, Any]:
        """The documented Naver blog-search shape: one full page, then an empty one.

        Matches the vendor documentation rather than a capture — no capture of this source
        exists, which `addons/collector.naver.blog` says in its own module docstring.
        """
        start = int(query.get("start", ["1"])[0])
        if start > 1:
            return {"total": BLOG_PAGE_SIZE, "start": start, "display": 0, "items": []}
        return {
            "total": BLOG_PAGE_SIZE,
            "start": start,
            "display": BLOG_PAGE_SIZE,
            "items": [
                {"title": f"post {n}", "link": f"https://blog.example.com/{n}"}
                for n in range(BLOG_PAGE_SIZE)
            ],
        }

    def _json(self, body: object, status: int = 200) -> None:
        self._bytes(json.dumps(body).encode("utf-8"), status, "application/json")

    def _bytes(self, body: bytes, status: int = 200, kind: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        # A header the guard must strip on the way out. Its absence downstream is checked
        # against the presence of Content-Type, so "nothing was recorded" cannot pass.
        self.send_header("Set-Cookie", "session=must-not-be-recorded")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Silent. The suite's output is the evidence, and a request log is not part of it."""


@pytest.fixture(scope="session")
def stub(certificate: tuple[Path, Path]) -> Iterator[int]:
    """A TLS server on loopback, on whatever port the OS gives. Yields the port."""
    key, cert = certificate
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert, keyfile=key)
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
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
def trusting(certificate: tuple[Path, Path]) -> SocketTransport:
    _, cert = certificate
    context = ssl.create_default_context(cafile=str(cert))
    return SocketTransport(context)


def a_profile(port: int, **overrides: Any) -> OutboundProfile:
    values: dict[str, Any] = {
        "hosts": ["localhost"],
        "endpoints": {
            "items": "/v1/items",
            "huge": "/v1/huge",
            "slow": "/v1/slow",
            "hop": "/v1/redirect",
            "blog": "/blog",
        },
        "port": port,
        "limits": {},
        "allow_loopback": True,
    }
    values.update(overrides)
    return OutboundProfile(
        hosts=tuple(values["hosts"]),
        endpoints=values["endpoints"],
        port=values["port"],
        limits={**OutboundProfile(hosts=(), endpoints={}).limits, **values["limits"]},
        allow_loopback=values["allow_loopback"],
    )


def prepared(profile: OutboundProfile, endpoint: str = "items", **params: str) -> Any:
    request = resolve(endpoint, profile, params or None)
    assert not isinstance(request, Refusal), request
    return request


# --------------------------------------------------------------------------- #
# It reaches a real server
# --------------------------------------------------------------------------- #


class TestARealRoundTrip:
    def test_an_approved_endpoint_comes_back_with_its_bytes(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        profile = a_profile(stub)
        response = trusting.send(prepared(profile), profile)

        assert not isinstance(response, Refusal), response
        assert response.status == 200
        assert json.loads(response.body)["next"] == 3
        # `localhost` may resolve to both families. Every address it returned was checked,
        # and the socket was opened to one of those and to nothing else.
        assert "127.0.0.1" in response.addresses

    def test_a_protected_header_never_reaches_the_caller(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        profile = a_profile(stub)
        response = trusting.send(prepared(profile), profile)

        assert not isinstance(response, Refusal)
        assert not any(k.lower() == "set-cookie" for k in response.headers)
        # The control: the same response's ordinary headers *did* survive, so the assertion
        # above is about stripping and not about an empty mapping.
        assert any(k.lower() == "content-type" for k in response.headers)

    def test_a_redirect_comes_back_unfollowed(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        """One call is one hop. Revalidating the destination is the caller's."""
        profile = a_profile(stub)
        response = trusting.send(prepared(profile, "hop"), profile)

        assert not isinstance(response, Refusal)
        assert response.status == 302
        assert response.location == "https://elsewhere.example.net/v1/items"

    def test_the_default_context_rejects_this_stub(self, stub: int) -> None:
        """The control for every test above: the trust is doing work.

        Without this, a `SocketTransport` that verified nothing would pass all of them.
        """
        profile = a_profile(stub)
        with pytest.raises(TransportUnavailable):
            SocketTransport().send(prepared(profile), profile)


# --------------------------------------------------------------------------- #
# SEC-004 — bounded failures
# --------------------------------------------------------------------------- #


class TestBoundedFailures:
    def test_an_oversized_response_is_refused_by_rule(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        """`SEC-004`, the size half. Enforced while reading, not after."""
        profile = a_profile(stub, limits={"max_response_bytes": SMALL_BODY_LIMIT})
        outcome = trusting.send(prepared(profile, "huge"), profile)

        assert isinstance(outcome, Refusal)
        assert outcome.reason is RefusalReason.RESPONSE_TOO_LARGE

    def test_a_body_inside_the_limit_is_not_refused(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        """The control. A transport that refused everything would pass the test above."""
        profile = a_profile(stub, limits={"max_response_bytes": SMALL_BODY_LIMIT})
        outcome = trusting.send(prepared(profile), profile)

        assert not isinstance(outcome, Refusal)

    def test_a_slow_response_ends_within_its_read_timeout(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        """`SEC-004`, the time half: the worker is not occupied indefinitely.

        The assertion is on elapsed wall-clock, not on the exception alone. A transport
        that failed after the stub finished sleeping would raise the same exception and
        occupy the worker for the whole six seconds.
        """
        profile = a_profile(stub)
        bounds = TransportLimits(read_timeout_s=SHORT_READ_TIMEOUT)

        started = time.monotonic()
        with pytest.raises(TransportUnavailable):
            trusting.send(prepared(profile, "slow"), profile, limits=bounds)
        elapsed = time.monotonic() - started

        assert elapsed < SHORT_READ_TIMEOUT * 3, f"the read ran for {elapsed:.1f}s"


# --------------------------------------------------------------------------- #
# The flag, and its price
# --------------------------------------------------------------------------- #


class TestLoopbackIsOnlyReachableByFlag:
    """`EXP-003`'s known obstacle, with the two tests it fixed in advance."""

    def test_with_the_flag_off_a_loopback_address_is_actually_refused(
        self, stub: int, trusting: SocketTransport
    ) -> None:
        profile = a_profile(stub, allow_loopback=False)
        outcome = trusting.send(prepared(profile), profile)

        assert isinstance(outcome, Refusal)
        assert outcome.reason is RefusalReason.ADDRESS_RANGE_BLOCKED

    def test_no_source_or_add_on_in_the_repository_sets_it(self) -> None:
        """The flag exists for tests. If it ever appears elsewhere, this names the file."""
        found = sorted(
            path.relative_to(REPO_ROOT)
            for path in EXPERIMENT_ROOT.rglob("*.py")
            if "__pycache__" not in path.parts and "allow_loopback" in path.read_text("utf-8")
        )
        permitted = {
            Path("experiments/integrated-p0/domain/outbound.py"),
            Path("experiments/integrated-p0/tests/test_outbound_policy.py"),
            Path("experiments/integrated-p0/tests/test_outbound_transport.py"),
        }
        assert set(found) <= permitted, f"allow_loopback appeared in {set(found) - permitted}"
        # The control: the scan can find things. An empty result would satisfy the subset
        # assertion above just as well, and would mean the scan read nothing.
        assert Path("experiments/integrated-p0/domain/outbound.py") in found


# --------------------------------------------------------------------------- #
# The whole thing, end to end
# --------------------------------------------------------------------------- #


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


class TestTheInstalledCollectorRunsThroughThePlatform:
    """`EXP-003` step 4, and the only test here where nothing is a double.

    `addons/collector.naver.blog` — the installed add-on, not a fixture — runs through
    `JobRunner`, the capability layer, `domain.outbound`, `domain.transport`, a TLS socket,
    and into PostgreSQL. The add-on composes no URL, holds no credential, and opens no
    socket, which is H2 stated as an executable claim.

    What this does **not** show, stated rather than implied:

    - **No credential is attached.** `OQ-009` has not settled what a two-part credential
      looks like, so the stub demands none. Everything about credential resolution and
      header attachment is untested here.
    - **The stub is not the provider.** Its response shape is the vendor documentation's;
      no capture of the real source exists, which the add-on's own docstring says. The
      three `[가설]` assumptions in that docstring are not confirmed by this passing.
    - **Loopback is reachable only because the source's profile says so**, which no
      committed source does — see `TestLoopbackIsOnlyReachableByFlag`.
    """

    def test_it_collects_a_page_and_stores_raw_with_a_cursor(
        self,
        stub: int,
        certificate: tuple[Path, Path],
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        _, cert = certificate
        domain.register_source(
            SourceRow(
                source_id="naver-blog-stub",
                addon_id="collector.naver.blog",
                addon_version="0.1.0",
                kind="collector",
                config={"query": "cosmai", "display": BLOG_PAGE_SIZE},
                config_schema_version="1",
                outbound_profile={
                    "hosts": ["localhost"],
                    "endpoints": {"blog": "/blog"},
                    "port": stub,
                    "allow_loopback": True,
                    "limits": {"max_pages": 5},
                },
            )
        )
        registry = HandlerRegistry()
        transport = SocketTransport(ssl.create_default_context(cafile=str(cert)))
        addons = load_addons(EXPERIMENT_ROOT / "addons", CONTRACT_VERSION)
        register_addons(registry, addons, bind_capabilities(domain, transport))

        store.create_job(
            "addon:collector.naver.blog", {"source_id": "naver-blog-stub"}, max_attempts=3
        )
        outcome = JobRunner(store, registry, "worker-1", lease_seconds=60).run_once()

        assert outcome is not None and outcome.accepted, outcome
        assert outcome.state is JobState.SUCCEEDED
        assert domain.count_items("naver-blog-stub") == BLOG_PAGE_SIZE
        # Two requests for one page of results: the add-on cannot trust `total`, so it pays
        # a second call to confirm exhaustion. Its own docstring says why.
        pages = connection.execute("select count(*) from raw_envelope").fetchone()
        assert pages is not None and int(pages[0]) == 2
        assert domain.read_cursor("naver-blog-stub", "items") == BLOG_PAGE_SIZE + 1

    def test_no_recorded_envelope_carries_a_protected_header(
        self,
        stub: int,
        certificate: tuple[Path, Path],
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """`SEC-001`'s Raw-metadata half, on rows a real socket produced.

        The stub sets `Set-Cookie` on every response, so the absence below is an absence of
        something that was genuinely there — and the control asserts the header mapping is
        populated, so an empty jsonb could not pass.
        """
        self.test_it_collects_a_page_and_stores_raw_with_a_cursor(
            stub, certificate, store, domain, connection
        )
        rows = connection.execute("select response_headers from raw_envelope").fetchall()
        assert rows
        for (headers,) in rows:
            assert headers, "the envelope recorded no headers at all"
            assert not any(k.lower() == "set-cookie" for k in headers)
            assert any(k.lower() == "content-type" for k in headers)
