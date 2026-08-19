"""The operator's domain surface: sources, collection, snapshots, normalization, results.

`platform_core.api` navigates three kinds of thing — platform health, jobs, attempts — and
its own docstring says a fourth would refute OQ-005 H1 and must be *named* rather than added
quietly. This is that naming. P0-B's operator has four more objects and they are not
reducible to jobs: a **source** is a registered configuration, a **snapshot** is a sealed
input, a **result** is versioned output, and **raw** is what a collection produced. An
operator who can only see jobs can see that a collection ran and not what it collected.

**Why the routes are not in `platform_core.api`.** DP-008 D1: `platform_core` may import
nothing local, and `tests/environment/test_addon_layer_direction.py` enforces it. So the
platform's `create_app` gained one source-neutral seam — `extend`, a callable handed the
app — and the domain half lives in `addon_host.api`, exactly as `RegistryFor` and
`addon_host.worker` split the worker.

**What every write here is, and is not.** `p0-security.md` requires operator input to select
a **registered `source_id`** rather than turn a URL into a request. Every write below takes
an identifier of something already in the database; none takes a host, a path, a URL, or a
credential. The test that matters most in this file is the one that tries to.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from addon_host.api import extend_with_domain
from domain import DomainStore, SourceRow
from domain.store import RawItemRow
from fastapi.testclient import TestClient
from platform_core.api.app import create_app
from platform_core.config import PlatformConfig
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger

pytestmark = pytest.mark.usefixtures("database")

COLLECT_SOURCE = "probe-blog"
NORMALIZE_SOURCE = "probe-blog-normalized"
IMPORT_SOURCE = "probe-rows"


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


@pytest.fixture
def client(database: PlatformConfig, logger: StructuredLogger) -> TestClient:
    app = create_app(database, logger, extend=extend_with_domain(database, logger))
    return TestClient(app)


@pytest.fixture
def registered(domain: DomainStore) -> None:
    domain.register_source(
        SourceRow(
            source_id=COLLECT_SOURCE,
            addon_id="collector.naver.blog",
            addon_version="0.1.0",
            kind="collector",
            config={"query": "수분크림", "display": 10},
            config_schema_version="1",
            outbound_profile={
                "hosts": ["naverapihub.apigw.ntruss.com"],
                "endpoints": {"blog": "/search/v1/blog"},
                "port": 443,
                "credentials": [
                    {
                        "header": "X-NCP-APIGW-API-KEY-ID",
                        "ref": "COSMA_SRC_PROBE_BLOG_CLIENT_ID",
                    }
                ],
            },
        )
    )
    domain.register_source(
        SourceRow(
            source_id=IMPORT_SOURCE,
            addon_id="importer.local.jsonl",
            addon_version="0.1.0",
            kind="importer",
            config={"key_field": "id"},
            config_schema_version="1",
            input_profile={"root": "/tmp/approved", "inputs": {"rows": "rows.jsonl"}},
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


def put_raw(domain: DomainStore, connection: psycopg.Connection[Any], *keys: str) -> None:
    job_id, attempt_id = uuid4(), uuid4()
    connection.execute(
        "insert into job (id, handler, payload, state, attempt_count, max_attempts, "
        "available_at, correlation_id) values (%s, 'x', %s, 'SUCCEEDED', 1, 1, now(), 'c')",
        (job_id, json.dumps({})),
    )
    connection.execute(
        "insert into job_attempt (id, job_id, attempt_no, worker_id, correlation_id, "
        "finished_at, outcome) values (%s, %s, 1, 'w', 'c', now(), 'SUCCEEDED')",
        (attempt_id, job_id),
    )
    envelope = domain.record_envelope(
        COLLECT_SOURCE, job_id, attempt_id, "collector.naver.blog", "0.1.0",
        body=b'{"items":[]}', endpoint_ref="blog",
    )
    domain.record_items(
        envelope,
        COLLECT_SOURCE,
        [
            RawItemRow(
                item_key=key,
                payload=json.dumps({"link": key, "title": "t"}).encode("utf-8"),
                content_type="application/json",
            )
            for key in keys
        ],
    )


class TestListingSources:
    def test_every_registered_source_is_listed(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.get("/sources")

        assert response.status_code == 200
        assert {row["source_id"] for row in response.json()["sources"]} == {
            COLLECT_SOURCE,
            NORMALIZE_SOURCE,
            IMPORT_SOURCE,
        }

    def test_a_source_reports_its_add_on_kind_and_whether_it_is_enabled(
        self, client: TestClient, registered: None
    ) -> None:
        row = client.get(f"/sources/{COLLECT_SOURCE}").json()

        assert row["addon_id"] == "collector.naver.blog"
        assert row["kind"] == "collector"
        assert row["enabled"] is True

    def test_the_credential_ref_name_is_shown_and_no_value_ever_is(
        self, client: TestClient, registered: None
    ) -> None:
        """`secret-setup.md`: the ref is a key **name** and may be shown; the value may not.
        An operator needs to see which key a source expects in order to put it in the store.
        """
        row = client.get(f"/sources/{COLLECT_SOURCE}").json()

        refs = [part["ref"] for part in row["outbound_profile"]["credentials"]]
        assert refs == ["COSMA_SRC_PROBE_BLOG_CLIENT_ID"]
        assert "value" not in json.dumps(row["outbound_profile"]["credentials"])

    def test_an_unregistered_source_is_404_rather_than_an_empty_success(
        self, client: TestClient, registered: None
    ) -> None:
        assert client.get("/sources/nope").status_code == 404


class TestStartingACollection:
    def test_it_creates_a_job_for_the_source_s_add_on(
        self, client: TestClient, registered: None, store: JobStore
    ) -> None:
        response = client.post(f"/sources/{COLLECT_SOURCE}/collect")

        assert response.status_code == 201
        job = store.read_job(UUID(response.json()["job_id"]))
        assert job is not None
        assert job["handler"] == "addon:collector.naver.blog"
        assert job["payload"] == {"source_id": COLLECT_SOURCE}
        assert job["state"] == JobState.PENDING.value

    def test_a_normalizer_source_cannot_be_told_to_collect(
        self, client: TestClient, registered: None
    ) -> None:
        """The kinds are not interchangeable, and the refusal says which it got."""
        response = client.post(f"/sources/{NORMALIZE_SOURCE}/collect")

        assert response.status_code == 409
        assert "normalizer" in response.json()["detail"]

    def test_a_disabled_source_is_refused(
        self, client: TestClient, registered: None, connection: psycopg.Connection[Any]
    ) -> None:
        connection.execute(
            "update source set enabled = false where source_id = %s", (COLLECT_SOURCE,)
        )

        assert client.post(f"/sources/{COLLECT_SOURCE}/collect").status_code == 409

    def test_an_unregistered_source_cannot_be_collected(
        self, client: TestClient, registered: None
    ) -> None:
        assert client.post("/sources/nope/collect").status_code == 404


class TestTheOperatorCannotTurnThisIntoAUrlFetcher:
    """`p0-security.md`'s central outbound rule, at the operator surface.

    "operator input selects a registered `source_id`; it must not turn an arbitrary URL into
    an outbound request." Every write in this module takes an identifier of a row that
    already exists. These are the attempts to do otherwise.
    """

    @pytest.mark.parametrize(
        "attempt",
        [
            "https://evil.test/steal",
            "../../etc/passwd",
            "probe-blog/../nope",
        ],
    )
    def test_a_url_or_path_offered_as_a_source_id_is_simply_not_a_source(
        self, client: TestClient, registered: None, attempt: str
    ) -> None:
        response = client.post(f"/sources/{attempt}/collect")

        assert response.status_code in (404, 405), response.text
        assert "raw_envelope" not in response.text

    def test_a_request_body_cannot_add_a_host_or_an_endpoint(
        self, client: TestClient, registered: None, connection: psycopg.Connection[Any]
    ) -> None:
        """The profile is written by registration and is not reachable from a job request.
        Anything sent here is ignored rather than merged."""
        client.post(
            f"/sources/{COLLECT_SOURCE}/collect",
            json={"hosts": ["evil.test"], "endpoints": {"x": "/steal"}, "url": "https://e/x"},
        )

        row = connection.execute(
            "select outbound_profile::text from source where source_id = %s", (COLLECT_SOURCE,)
        ).fetchone()
        assert row is not None
        assert "evil.test" not in row[0]


class TestRawIsVisible:
    def test_a_source_reports_what_it_has_collected(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a", "b")

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert body["envelope_count"] == 1
        assert body["item_count"] == 2

    def test_a_source_with_nothing_collected_reports_zero_rather_than_404(
        self, client: TestClient, registered: None
    ) -> None:
        """"Nothing collected yet" is an ordinary state and must be distinguishable from
        "no such source"."""
        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert body["envelope_count"] == 0
        assert body["item_count"] == 0

    def test_no_recorded_response_header_reaches_the_operator_unstripped(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a")

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert "authorization" not in json.dumps(body).lower()


class TestSealingASnapshot:
    def test_an_operator_can_seal_what_has_been_collected(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a", "b")

        response = client.post(f"/sources/{COLLECT_SOURCE}/snapshots")

        assert response.status_code == 201
        snapshot = domain.read_snapshot(UUID(response.json()["snapshot_id"]))
        assert snapshot is not None
        assert snapshot["item_count"] == 2

    def test_a_sealed_snapshot_is_listed_with_its_verification_state(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a")
        client.post(f"/sources/{COLLECT_SOURCE}/snapshots")

        listed = client.get("/snapshots").json()["snapshots"]

        assert len(listed) == 1
        assert listed[0]["verifies"] is True
        assert listed[0]["item_count"] == 1

    def test_a_tampered_snapshot_says_so_and_names_the_problem(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The operator surface for the property `snapshot_tampering` computes. A dashboard
        that only showed "sealed" would make a tampered input look ready to run."""
        put_raw(domain, connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]
        connection.execute(
            "update snapshot_item set payload = %s where snapshot_id = %s",
            (b"tampered", UUID(snapshot_id)),
        )

        body = client.get(f"/snapshots/{snapshot_id}").json()

        assert body["verifies"] is False
        assert body["problems"]

    def test_a_snapshot_that_does_not_exist_is_404(self, client: TestClient) -> None:
        assert client.get(f"/snapshots/{uuid4()}").status_code == 404


class TestStartingANormalization:
    def test_it_creates_a_job_naming_the_snapshot_and_the_normalizer(
        self, client: TestClient, registered: None, domain: DomainStore, store: JobStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        response = client.post(
            f"/snapshots/{snapshot_id}/normalize", json={"source_id": NORMALIZE_SOURCE}
        )

        assert response.status_code == 201
        job = store.read_job(UUID(response.json()["job_id"]))
        assert job is not None
        assert job["handler"] == "addon:normalizer.naver.blog"
        assert job["payload"] == {
            "source_id": NORMALIZE_SOURCE,
            "snapshot_id": snapshot_id,
        }

    def test_collection_does_not_start_normalization_by_itself(
        self, client: TestClient, registered: None, store: JobStore
    ) -> None:
        """`project-state.md` §4 and DP-019 D6: normalization is started explicitly. This is
        that rule as an assertion — a collect request creates exactly one job."""
        client.post(f"/sources/{COLLECT_SOURCE}/collect")

        assert len(store.list_jobs()) == 1

    def test_a_collector_source_cannot_be_told_to_normalize(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        response = client.post(
            f"/snapshots/{snapshot_id}/normalize", json={"source_id": COLLECT_SOURCE}
        )

        assert response.status_code == 409

    def test_normalizing_a_snapshot_that_does_not_exist_is_404(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.post(
            f"/snapshots/{uuid4()}/normalize", json={"source_id": NORMALIZE_SOURCE}
        )
        assert response.status_code == 404


class TestReadingResults:
    def _one_result(
        self, domain: DomainStore, connection: psycopg.Connection[Any], client: TestClient
    ) -> Any:
        put_raw(domain, connection, "https://blog.example.com/1")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]
        domain.record_results(
            UUID(snapshot_id),
            COLLECT_SOURCE,
            "normalizer.naver.blog",
            "0.1.0",
            "0.1",
            [
                _row(
                    "https://blog.example.com/1",
                    {"schema_version": "0.1", "record_type": "document", "title": "t"},
                )
            ],
        )
        return snapshot_id

    def test_a_snapshot_s_results_are_readable_with_their_versions(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        snapshot_id = self._one_result(domain, connection, client)

        body = client.get(f"/snapshots/{snapshot_id}/results").json()

        assert body["results"][0]["addon_version"] == "0.1.0"
        assert body["results"][0]["output_contract_version"] == "0.1"
        assert body["results"][0]["body"]["schema_version"] == "0.1"

    def test_a_result_carries_the_raw_item_key_it_came_from(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """The lineage the P0 Charter asks for, at the surface an operator reads."""
        snapshot_id = self._one_result(domain, connection, client)

        body = client.get(f"/snapshots/{snapshot_id}/results").json()

        assert body["results"][0]["source_item_key"] == "https://blog.example.com/1"

    def test_a_snapshot_with_no_results_reports_an_empty_list(
        self, client: TestClient, registered: None, domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        assert client.get(f"/snapshots/{snapshot_id}/results").json()["results"] == []


class TestThePlatformSurfaceIsUnchanged:
    """The seam must add and never replace. Every P0-A scenario reads these."""

    def test_health_still_answers(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_jobs_still_answers(self, client: TestClient) -> None:
        assert client.get("/jobs").status_code == 200

    def test_an_app_built_without_the_seam_has_no_domain_routes(
        self, database: PlatformConfig, logger: StructuredLogger
    ) -> None:
        """`platform_core.api` on its own is still source-neutral, which is what DP-008 D1
        requires and what keeps the P0-A gate's evidence standing."""
        plain = TestClient(create_app(database, logger))

        assert plain.get("/sources").status_code == 404
        assert plain.get("/health").status_code == 200


def _row(key: str, body: dict[str, Any]) -> Any:
    from domain.store import NormalizedResultRow

    return NormalizedResultRow(source_item_key=key, body=body)


class TestStartingAnImport:
    """The dataset half of the charter's required flow item 12.

    `[확인 사실]` Until this existed, no route created an importer job. `DP-024`, the input
    registry, migration `0004`, and `importer.local.jsonl` were reachable only from tests —
    so the charter's *"operate, inspect, diagnose, and safely retry the domain flow through
    the dashboard"* held for the REST half and not for the dataset half.
    """

    def test_it_creates_a_job_for_the_source_s_importer(
        self, client: TestClient, registered: None, store: JobStore
    ) -> None:
        response = client.post(f"/sources/{IMPORT_SOURCE}/import")

        assert response.status_code == 201
        job = store.read_job(UUID(response.json()["job_id"]))
        assert job is not None
        assert job["handler"] == "addon:importer.local.jsonl"
        assert job["payload"] == {"source_id": IMPORT_SOURCE}
        assert job["state"] == JobState.PENDING.value

    def test_a_collector_source_cannot_be_told_to_import(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.post(f"/sources/{COLLECT_SOURCE}/import")

        assert response.status_code == 409
        assert "collector" in response.json()["detail"]

    def test_an_importer_source_still_cannot_be_told_to_collect(
        self, client: TestClient, registered: None
    ) -> None:
        """The control. Adding a second verb must not make the first one permissive."""
        response = client.post(f"/sources/{IMPORT_SOURCE}/collect")

        assert response.status_code == 409
        assert "importer" in response.json()["detail"]

    def test_a_disabled_importer_is_refused(
        self, client: TestClient, registered: None, connection: psycopg.Connection[Any]
    ) -> None:
        connection.execute(
            "update source set enabled = false where source_id = %s", (IMPORT_SOURCE,)
        )

        assert client.post(f"/sources/{IMPORT_SOURCE}/import").status_code == 409

    def test_an_unregistered_source_cannot_be_imported(
        self, client: TestClient, registered: None
    ) -> None:
        assert client.post("/sources/nope/import").status_code == 404


class TestAnImporterCanSealASnapshot:
    """A dataset that cannot be sealed cannot be normalized, so it cannot finish the flow."""

    def test_an_importer_s_raw_can_be_sealed(
        self,
        client: TestClient,
        registered: None,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain, connection, "row-1", "row-2")
        connection.execute(
            "update raw_envelope set source_id = %s where source_id = %s",
            (IMPORT_SOURCE, COLLECT_SOURCE),
        )
        connection.execute(
            "update raw_item set source_id = %s where source_id = %s",
            (IMPORT_SOURCE, COLLECT_SOURCE),
        )

        response = client.post(f"/sources/{IMPORT_SOURCE}/snapshots")

        assert response.status_code == 201, response.text
        assert response.json()["item_count"] == 2

    def test_a_normalizer_source_still_cannot_seal(
        self, client: TestClient, registered: None
    ) -> None:
        """The control: widening to two kinds must not widen to all of them."""
        response = client.post(f"/sources/{NORMALIZE_SOURCE}/snapshots")

        assert response.status_code == 409
        assert "normalizer" in response.json()["detail"]


class TestTheOperatorReadsBackTheInputGrantTheyApproved:
    """`profile_view`'s docstring claims *"Everything here is the operator's own grant read
    back to them"*. `input_profile` reached no response at all, so for an importer the
    sentence was false: an operator could approve a root and a member list and then have no
    way to see what they had approved.
    """

    def test_an_importer_s_input_profile_is_returned(
        self, client: TestClient, registered: None
    ) -> None:
        body = client.get(f"/sources/{IMPORT_SOURCE}").json()

        assert body["input_profile"] == {
            "root": "/tmp/approved",
            "inputs": {"rows": "rows.jsonl"},
        }

    def test_a_collector_has_no_input_profile_rather_than_an_empty_one(
        self, client: TestClient, registered: None
    ) -> None:
        """`None` says this source reads no files; `{}` would read as an approved-nothing
        grant, and migration `0004` refuses the column on a non-importer for that reason."""
        assert client.get(f"/sources/{COLLECT_SOURCE}").json()["input_profile"] is None
