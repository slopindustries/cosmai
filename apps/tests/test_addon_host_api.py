"""``addon_host.api``: the domain surface reused, plus `/collect` and `/import`.

New in M3 batch 3b — P0's own `POST /collect`/`POST /import` coverage lives inside
`experiments/integrated-p0/tests/test_domain_api.py`, one big module testing the whole
domain surface at once through `addon_host.api.extend_with_domain`. M2 built
`apps/tests/test_domain_api.py` against `domain.api.extend_with_domain` directly and
named the two routes it could not yet build (`docs/p1/M2-RECORD.md` §(d)); this file is
the M3 half of that split, and it deliberately does **not** re-test every domain route —
`test_domain_api.py`'s 42 cases already do, and re-running them through the composed
`addon_host.api` app would prove nothing `test_domain_api.py` had not already proved,
except that composition itself, which ``TestDomainRoutesStillServeThroughTheComposedApp``
below checks once rather than exhaustively.

**What "wired" means here, checked rather than assumed.** A route creates a `PENDING`
job whose `handler` is `f"addon:{addon_id}"` — the same string
`addon_host.registration.handler_name` derives and the same prefix a worker's
`capability_registry` registers under. `TestACollectJobReachesARealWorker` proves the
whole chain once: a job this route creates is claimable and reaches
`addon_host.capabilities`'s own refusal (`no source named`... would be wrong here since
the source *is* registered — the real assertion is that the add-on's `run` was actually
invoked), not `registration.capabilities_not_bound`'s "no capability layer bound" message
a mis-wired composition would produce instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from addon_host.api import extend_with_domain
from addon_host.registration import HANDLER_PREFIX
from addon_host.worker import capability_registry
from domain.store import DomainStore, SourceRow
from platform_core.api.app import create_app
from platform_core.config import PlatformConfig
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.worker import Worker, WorkerOptions

COLLECTOR_SOURCE = "probe-collector"
IMPORTER_SOURCE = "probe-importer"
NORMALIZER_SOURCE = "probe-normalizer"

PROBE_MANIFEST = """
[addon]
id = "collector.probe"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[declares]
hosts = ["api.example.com"]
endpoints = ["items"]
"""

#: Raises an exception type the contract's error taxonomy does not know, so
#: ``translated_failures`` reports it as "raised an unexpected RuntimeError" — a
#: different, later failure than ``registration.capabilities_not_bound``'s "no
#: capability layer bound", and one only reachable if `run` actually executed.
PROBE_SOURCE = """
def run(context):
    raise RuntimeError("collector.probe.run was reached")
"""


class RefusingTransport:
    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("this test never sends a request")


@pytest.fixture
def client(
    platform_config: PlatformConfig, job_logger: StructuredLogger, domain_store: DomainStore
) -> TestClient:
    """Depends on ``domain_store`` so its table reset runs before and after every test
    here, the same reason ``test_domain_api.py``'s own ``client`` fixture gives.
    """
    app = create_app(
        platform_config, job_logger, extend=extend_with_domain(platform_config, job_logger)
    )
    return TestClient(app)


def register(domain_store: DomainStore, source_id: str, kind: str, addon_id: str) -> None:
    domain_store.register_source(
        SourceRow(source_id=source_id, addon_id=addon_id, addon_version="0.1.0", kind=kind)
    )


@pytest.fixture(autouse=True)
def _sources(domain_store: DomainStore) -> Iterator[None]:
    register(domain_store, COLLECTOR_SOURCE, "collector", "collector.probe")
    register(domain_store, IMPORTER_SOURCE, "importer", "importer.probe")
    register(domain_store, NORMALIZER_SOURCE, "normalizer", "normalizer.probe")
    yield


class TestCollect:
    def test_a_collect_request_creates_a_pending_job_named_for_the_add_on(
        self, client: TestClient, job_store: JobStore
    ) -> None:
        response = client.post(f"/sources/{COLLECTOR_SOURCE}/collect")
        assert response.status_code == 201
        job_id = response.json()["job_id"]
        job = job_store.read_job(job_id)
        assert job is not None
        assert job["handler"] == f"{HANDLER_PREFIX}collector.probe"
        assert job["payload"] == {"source_id": COLLECTOR_SOURCE}
        assert job["state"] == JobState.PENDING.value

    def test_an_unregistered_source_is_404(self, client: TestClient) -> None:
        assert client.post("/sources/nope/collect").status_code == 404

    def test_a_normalizer_source_cannot_be_told_to_collect(self, client: TestClient) -> None:
        response = client.post(f"/sources/{NORMALIZER_SOURCE}/collect")
        assert response.status_code == 409

    def test_an_importer_source_cannot_be_told_to_collect(self, client: TestClient) -> None:
        assert client.post(f"/sources/{IMPORTER_SOURCE}/collect").status_code == 409

    def test_a_disabled_source_cannot_be_told_to_collect(
        self, client: TestClient, domain_store: DomainStore
    ) -> None:
        register(domain_store, "probe-disabled", "collector", "collector.probe")
        with domain_store.connection.transaction():
            domain_store.connection.execute(
                "update cosmai.source set enabled = false where source_id = %s",
                ("probe-disabled",),
            )
        assert client.post("/sources/probe-disabled/collect").status_code == 409


class TestImport:
    def test_an_import_request_creates_a_pending_job_named_for_the_add_on(
        self, client: TestClient, job_store: JobStore
    ) -> None:
        response = client.post(f"/sources/{IMPORTER_SOURCE}/import")
        assert response.status_code == 201
        job_id = response.json()["job_id"]
        job = job_store.read_job(job_id)
        assert job is not None
        assert job["handler"] == f"{HANDLER_PREFIX}importer.probe"
        assert job["payload"] == {"source_id": IMPORTER_SOURCE}

    def test_an_unregistered_source_is_404(self, client: TestClient) -> None:
        assert client.post("/sources/nope/import").status_code == 404

    def test_a_collector_source_cannot_be_told_to_import(self, client: TestClient) -> None:
        assert client.post(f"/sources/{COLLECTOR_SOURCE}/import").status_code == 409


class TestDomainRoutesStillServeThroughTheComposedApp:
    """`addon_host.api` reuses `domain.api.extend_with_domain`; this checks the reuse
    actually happened rather than a second, diverging copy of the same routes."""

    def test_list_sources_reaches_the_registered_rows(self, client: TestClient) -> None:
        response = client.get("/sources")
        assert response.status_code == 200
        ids = {row["source_id"] for row in response.json()["sources"]}
        assert {COLLECTOR_SOURCE, IMPORTER_SOURCE, NORMALIZER_SOURCE} <= ids

    def test_read_raw_for_a_registered_source_still_works(self, client: TestClient) -> None:
        response = client.get(f"/sources/{COLLECTOR_SOURCE}/raw")
        assert response.status_code == 200
        assert response.json()["item_count"] == 0


class TestACollectJobReachesARealWorker:
    """The chain a mis-wired composition would break silently: a job this route
    created, claimed by a worker whose registry this batch's own `capability_registry`
    built, actually invokes the add-on rather than failing on
    `registration.capabilities_not_bound`'s stated refusal.
    """

    def test_the_job_this_route_created_invokes_the_add_on(
        self,
        tmp_path: Path,
        client: TestClient,
        domain_store: DomainStore,
        job_store: JobStore,
        platform_config: PlatformConfig,
    ) -> None:
        package = tmp_path / "collector.probe"
        package.mkdir()
        (package / "addon.toml").write_text(PROBE_MANIFEST, encoding="utf-8")
        (package / "handler.py").write_text(PROBE_SOURCE, encoding="utf-8")

        # An outbound profile granting exactly what the manifest declares, so
        # `_require_profile` (`no approved outbound profile`) does not refuse this
        # collector before `run` is ever called — the profile is never actually used,
        # since `run` raises on its own first line before calling `context.fetch`.
        source_id = "probe-wired"
        domain_store.register_source(
            SourceRow(
                source_id=source_id,
                addon_id="collector.probe",
                addon_version="0.1.0",
                kind="collector",
                outbound_profile={"hosts": ["api.example.com"], "endpoints": {"items": "/items"}},
            )
        )

        response = client.post(f"/sources/{source_id}/collect")
        assert response.status_code == 201
        job_id = response.json()["job_id"]

        log = StringIO()
        worker = Worker(
            platform_config,
            WorkerOptions(once=True),
            StructuredLogger(stream=log, level="DEBUG"),
            registry_for=capability_registry(RefusingTransport(), root=tmp_path),
            report_stream=StringIO(),
        )
        worker.run()

        job = job_store.read_job(job_id)
        assert job is not None
        assert job["state"] == JobState.FAILED.value
        attempts = job_store.read_attempts(job["id"])
        assert attempts, "no attempt was recorded"
        # "raised an unexpected RuntimeError" is `translate`'s wording for an exception
        # outside the contract's taxonomy — proof the capability layer actually called
        # `run` rather than refusing beforehand with "no capability layer bound".
        summary = attempts[-1]["error_summary"]
        assert "RuntimeError" in summary
        assert "capability layer" not in summary
