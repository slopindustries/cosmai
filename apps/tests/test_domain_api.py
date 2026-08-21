"""The operator's domain surface: sources, raw browsing, snapshots, results, credentials.

Copy-adapted from ``experiments/integrated-p0/tests/test_domain_api.py`` (M2 batch 2d),
narrowed to what ``apps/domain/api.py`` actually serves — see that module's own docstring
for exactly which two P0 routes (``/collect``, ``/import``) are not reproduced and why.
Fixture names follow this tree's convention (``domain_store``/``job_store``/
``job_connection``, ``apps/tests/conftest.py``) and every ad-hoc SQL string is schema-
qualified (``cosmai.<table>``, DP-032 D1/D3). ``client`` builds the app in-process with
FastAPI's ``TestClient`` rather than spawning a real process — the same pattern P0 used,
and there is no P1 process entrypoint for this surface yet (``apps/domain/api.py``'s own
docstring: M3 decides where this module ends up living).

Two classes are new here rather than in P0:

- ``TestRawItemsAreBrowsable`` — the paginated raw-item read path (spec §신규 API,
  ``GET /sources/{id}/raw/items``; DP-033 D2), which P0 never had.
- ``TestWritingACredential`` — the credential write path (DP-034 D1/D2), which P0
  designed (DP-008 D6) but never built; this batch is the first implementation.

**Why the routes are not in ``platform_core.api``.** DP-008 D1: ``platform_core`` may
import nothing local, and ``tests/environment/test_addon_layer_direction.py`` enforces it.

**What every write here is, and is not.** ``p0-security.md`` requires operator input to
select a **registered ``source_id``** rather than turn a URL into a request. Every write
below takes an identifier of something already in the database, or (the credential write)
a value whose destination the identifier and a fixed naming convention already determine —
none takes a host, a path, or a URL.
"""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from domain.api import extend_with_domain
from domain.store import DomainStore, NormalizedResultRow, RawItemRow, SourceRow
from platform_core.api.app import create_app
from platform_core.config import PlatformConfig
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger

COLLECT_SOURCE = "probe-blog"
NORMALIZE_SOURCE = "probe-blog-normalized"
IMPORT_SOURCE = "probe-rows"


@pytest.fixture
def client(
    platform_config: PlatformConfig, job_logger: StructuredLogger, domain_store: DomainStore
) -> TestClient:
    """Depends on ``domain_store`` (not merely ``job_connection``) so its table reset
    runs before and after every test here, the same way every other domain-store test
    in this suite gets a clean ``source``/``raw_item``/``snapshot`` set — the app itself
    opens its own connection per request (``apps/domain/api.py``'s own docstring) and
    does not share ``domain_store``'s.
    """
    app = create_app(
        platform_config, job_logger, extend=extend_with_domain(platform_config, job_logger)
    )
    return TestClient(app)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated copy of the real secret store, outside the repository, at the
    permissions the launcher enforces. ``TestWritingACredential`` reads and writes it
    directly to check what ``POST /sources/{id}/credentials`` actually did to the file.

    A **copy** and not an empty file: every route this fixture's tests drive still
    opens an ordinary database connection first (``source_or_404``), which resolves
    ``COSMA_DB_RUNTIME`` through the very same ``COSMA_SECRET_SOURCE`` this fixture
    repoints — an empty store would make every request in this class fail before it
    ever reached the credential-write logic under test, on an unrelated database
    connection failure. Copying preserves those keys so the write path is the only
    thing under test, while the copy itself is disposable — its own test's writes to
    it never touch the real store a session-wide fixture needs.
    """
    real = Path(os.environ["COSMA_SECRET_SOURCE"]).expanduser()
    path = tmp_path / "env"
    path.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv("COSMA_SECRET_SOURCE", str(path))
    return path


@pytest.fixture
def registered(domain_store: DomainStore) -> None:
    domain_store.register_source(
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
    domain_store.register_source(
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
    domain_store.register_source(
        SourceRow(
            source_id=NORMALIZE_SOURCE,
            addon_id="normalizer.naver.blog",
            addon_version="0.1.0",
            kind="normalizer",
            config={"language": "ko"},
            config_schema_version="1",
        )
    )


def put_raw(
    domain_store: DomainStore, job_connection: psycopg.Connection[Any], *keys: str
) -> None:
    job_id, attempt_id = uuid4(), uuid4()
    job_connection.execute(
        "insert into cosmai.job (id, handler, payload, state, attempt_count, max_attempts, "
        "available_at, correlation_id) values (%s, 'x', %s, 'SUCCEEDED', 1, 1, now(), 'c')",
        (job_id, json.dumps({})),
    )
    job_connection.execute(
        "insert into cosmai.job_attempt (id, job_id, attempt_no, worker_id, correlation_id, "
        "finished_at, outcome) values (%s, %s, 1, 'w', 'c', now(), 'SUCCEEDED')",
        (attempt_id, job_id),
    )
    envelope = domain_store.record_envelope(
        COLLECT_SOURCE, job_id, attempt_id, "collector.naver.blog", "0.1.0",
        body=b'{"items":[]}', endpoint_ref="blog",
    )
    domain_store.record_items(
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
        assert client.get(f"/sources/{COLLECT_SOURCE}").json()["input_profile"] is None


class TestRawIsVisible:
    def test_a_source_reports_what_it_has_collected(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a", "b")

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert body["envelope_count"] == 1
        assert body["item_count"] == 2

    def test_a_source_with_nothing_collected_reports_zero_rather_than_404(
        self, client: TestClient, registered: None
    ) -> None:
        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert body["envelope_count"] == 0
        assert body["item_count"] == 0

    def test_no_recorded_response_header_reaches_the_operator_unstripped(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw").json()

        assert "authorization" not in json.dumps(body).lower()


class TestRawItemsAreBrowsable:
    """New in P1 (spec §신규 API; DP-033 D1/D2). ``GET /sources/{id}/raw/items``."""

    def test_a_page_of_items_comes_back_with_their_payload_as_text(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a", "b", "c")

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw/items").json()

        assert body["returned"] == 3
        assert [item["item_key"] for item in body["items"]] == ["a", "b", "c"]
        first = body["items"][0]
        assert json.loads(first["payload"]) == {"link": "a", "title": "t"}
        assert isinstance(first["seq"], int)
        assert first["content_type"] == "application/json"

    def test_a_script_tag_in_a_payload_survives_as_text_not_markup(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """DP-033 D2: the response carries no rendering directive — the payload is a
        JSON string field, not HTML the client could be tricked into interpreting."""
        job_id, attempt_id = uuid4(), uuid4()
        job_connection.execute(
            "insert into cosmai.job (id, handler, payload, state, attempt_count, "
            "max_attempts, available_at, correlation_id) values "
            "(%s, 'x', %s, 'SUCCEEDED', 1, 1, now(), 'c')",
            (job_id, json.dumps({})),
        )
        job_connection.execute(
            "insert into cosmai.job_attempt (id, job_id, attempt_no, worker_id, "
            "correlation_id, finished_at, outcome) values "
            "(%s, %s, 1, 'w', 'c', now(), 'SUCCEEDED')",
            (attempt_id, job_id),
        )
        envelope = domain_store.record_envelope(
            COLLECT_SOURCE, job_id, attempt_id, "collector.naver.blog", "0.1.0",
            body=b"{}", endpoint_ref="blog",
        )
        domain_store.record_items(
            envelope,
            COLLECT_SOURCE,
            [RawItemRow("bad", b"<script>alert(1)</script>", "text/html")],
        )

        body = client.get(f"/sources/{COLLECT_SOURCE}/raw/items").json()

        assert body["items"][0]["payload"] == "<script>alert(1)</script>"
        assert isinstance(body["items"][0]["payload"], str)

    def test_non_utf8_bytes_are_replaced_rather_than_breaking_the_response(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        job_id, attempt_id = uuid4(), uuid4()
        job_connection.execute(
            "insert into cosmai.job (id, handler, payload, state, attempt_count, "
            "max_attempts, available_at, correlation_id) values "
            "(%s, 'x', %s, 'SUCCEEDED', 1, 1, now(), 'c')",
            (job_id, json.dumps({})),
        )
        job_connection.execute(
            "insert into cosmai.job_attempt (id, job_id, attempt_no, worker_id, "
            "correlation_id, finished_at, outcome) values "
            "(%s, %s, 1, 'w', 'c', now(), 'SUCCEEDED')",
            (attempt_id, job_id),
        )
        envelope = domain_store.record_envelope(
            COLLECT_SOURCE, job_id, attempt_id, "collector.naver.blog", "0.1.0",
            body=b"{}", endpoint_ref="blog",
        )
        domain_store.record_items(
            envelope,
            COLLECT_SOURCE,
            [RawItemRow("bin", b"\xff\xfe not utf-8", "application/octet-stream")],
        )

        response = client.get(f"/sources/{COLLECT_SOURCE}/raw/items")

        assert response.status_code == 200
        assert "�" in response.json()["items"][0]["payload"]

    def test_paging_moves_through_the_items_in_sequence_order(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a", "b", "c")

        first = client.get(f"/sources/{COLLECT_SOURCE}/raw/items?limit=2").json()
        second = client.get(f"/sources/{COLLECT_SOURCE}/raw/items?offset=2&limit=2").json()

        assert [item["item_key"] for item in first["items"]] == ["a", "b"]
        assert [item["item_key"] for item in second["items"]] == ["c"]

    def test_a_source_with_no_raw_reports_an_empty_page_rather_than_404(
        self, client: TestClient, registered: None
    ) -> None:
        body = client.get(f"/sources/{COLLECT_SOURCE}/raw/items").json()

        assert body["items"] == []
        assert body["returned"] == 0

    def test_an_unregistered_source_is_404(self, client: TestClient, registered: None) -> None:
        assert client.get("/sources/nope/raw/items").status_code == 404

    def test_an_out_of_range_limit_is_a_422(
        self, client: TestClient, registered: None
    ) -> None:
        assert client.get(f"/sources/{COLLECT_SOURCE}/raw/items?limit=0").status_code == 422
        assert (
            client.get(f"/sources/{COLLECT_SOURCE}/raw/items?limit=99999").status_code == 422
        )


class TestScheduleReadAndWrite:
    """`GET|PUT /sources/{id}/schedule` (M6 batch 6a; DP-033 D5). `apps/scheduler`
    is what actually acts on what these tests write; the process-level "due →
    job created" / "duplicate suppressed" / "disabled ignored" scenarios live
    in `tests/test_scheduler.py`, against `scheduler.store.SchedulerStore`
    directly and via a spawned `python -m scheduler` process — this class only
    covers the HTTP surface `PUT` upserts through."""

    def test_an_unconfigured_source_reports_the_unset_shape_not_a_404(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.get(f"/sources/{COLLECT_SOURCE}/schedule")

        assert response.status_code == 200
        assert response.json() == {
            "source_id": COLLECT_SOURCE,
            "interval_seconds": None,
            "enabled": False,
            "next_run_at": None,
            "last_run_at": None,
        }

    def test_an_unregistered_source_is_404(self, client: TestClient, registered: None) -> None:
        assert client.get("/sources/nope/schedule").status_code == 404
        assert (
            client.put("/sources/nope/schedule", json={"interval_seconds": 60, "enabled": True})
            .status_code
            == 404
        )

    def test_put_then_get_round_trips_and_next_run_at_is_due_immediately(
        self, client: TestClient, registered: None
    ) -> None:
        put = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 3600, "enabled": True},
        )

        assert put.status_code == 200
        body = put.json()
        assert body["source_id"] == COLLECT_SOURCE
        assert body["interval_seconds"] == 3600
        assert body["enabled"] is True
        assert body["next_run_at"] is not None
        assert body["last_run_at"] is None

        get = client.get(f"/sources/{COLLECT_SOURCE}/schedule")
        assert get.json() == body

    def test_editing_the_interval_of_an_already_due_schedule_keeps_next_run_at(
        self, client: TestClient, registered: None
    ) -> None:
        """Changing the cadence is not itself a request to run right now
        (`apps/domain/store.py`'s `UPSERT_SCHEDULE` docstring)."""
        first = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": True},
        ).json()

        second = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 120, "enabled": True},
        ).json()

        assert second["interval_seconds"] == 120
        assert second["next_run_at"] == first["next_run_at"]

    def test_disabling_then_re_enabling_a_never_run_schedule_stays_due(
        self, client: TestClient, registered: None
    ) -> None:
        enabled = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": True},
        ).json()

        disabled = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": False},
        ).json()
        assert disabled["enabled"] is False
        assert disabled["next_run_at"] == enabled["next_run_at"]

        re_enabled = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": True},
        ).json()
        assert re_enabled["next_run_at"] == enabled["next_run_at"]

    def test_a_normalizer_source_cannot_be_scheduled(
        self, client: TestClient, registered: None
    ) -> None:
        """D5: collection runs on a schedule; the optional normalization hook is
        not built by this batch — see `apps/domain/api.py`'s `write_schedule`."""
        response = client.put(
            f"/sources/{NORMALIZE_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": True},
        )

        assert response.status_code == 409

    def test_a_non_positive_interval_is_a_422(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 0, "enabled": True},
        )

        assert response.status_code == 422

    def test_a_non_boolean_enabled_is_a_422(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.put(
            f"/sources/{COLLECT_SOURCE}/schedule",
            json={"interval_seconds": 60, "enabled": "yes"},
        )

        assert response.status_code == 422


class TestSealingASnapshot:
    def test_an_operator_can_seal_what_has_been_collected(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a", "b")

        response = client.post(f"/sources/{COLLECT_SOURCE}/snapshots")

        assert response.status_code == 201
        snapshot = domain_store.read_snapshot(UUID(response.json()["snapshot_id"]))
        assert snapshot is not None
        assert snapshot["item_count"] == 2

    def test_a_sealed_snapshot_is_listed_with_its_verification_state(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
        client.post(f"/sources/{COLLECT_SOURCE}/snapshots")

        listed = client.get("/snapshots").json()["snapshots"]

        assert len(listed) == 1
        assert listed[0]["verifies"] is True
        assert listed[0]["item_count"] == 1

    def test_a_tampered_snapshot_says_so_and_names_the_problem(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]
        job_connection.execute(
            "update cosmai.snapshot_item set payload = %s where snapshot_id = %s",
            (b"tampered", UUID(snapshot_id)),
        )

        body = client.get(f"/snapshots/{snapshot_id}").json()

        assert body["verifies"] is False
        assert body["problems"]

    def test_a_snapshot_that_does_not_exist_is_404(self, client: TestClient) -> None:
        assert client.get(f"/snapshots/{uuid4()}").status_code == 404

    def test_an_importer_s_raw_can_be_sealed(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "row-1", "row-2")
        job_connection.execute(
            "update cosmai.raw_envelope set source_id = %s where source_id = %s",
            (IMPORT_SOURCE, COLLECT_SOURCE),
        )
        job_connection.execute(
            "update cosmai.raw_item set source_id = %s where source_id = %s",
            (IMPORT_SOURCE, COLLECT_SOURCE),
        )

        response = client.post(f"/sources/{IMPORT_SOURCE}/snapshots")

        assert response.status_code == 201, response.text
        assert response.json()["item_count"] == 2

    def test_a_normalizer_source_still_cannot_seal(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.post(f"/sources/{NORMALIZE_SOURCE}/snapshots")

        assert response.status_code == 409
        assert "normalizer" in response.json()["detail"]


class TestStartingANormalization:
    """`docs/p1/M2-RECORD.md` records that the job this creates stays `PENDING` until M3
    registers an `addon:*` handler — see `apps/domain/api.py`'s own docstring."""

    def test_it_creates_a_job_naming_the_snapshot_and_the_normalizer(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_store: JobStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        response = client.post(
            f"/snapshots/{snapshot_id}/normalize", json={"source_id": NORMALIZE_SOURCE}
        )

        assert response.status_code == 201
        job = job_store.read_job(UUID(response.json()["job_id"]))
        assert job is not None
        assert job["handler"] == "addon:normalizer.naver.blog"
        assert job["payload"] == {
            "source_id": NORMALIZE_SOURCE,
            "snapshot_id": snapshot_id,
        }
        assert job["state"] == "PENDING"

    def test_a_collector_source_cannot_be_told_to_normalize(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
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

    def test_a_normalize_request_with_no_source_id_is_a_422(
        self, client: TestClient, registered: None, domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        assert client.post(f"/snapshots/{snapshot_id}/normalize").status_code == 422


class TestReadingResults:
    def _one_result(
        self,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
        client: TestClient,
    ) -> Any:
        put_raw(domain_store, job_connection, "https://blog.example.com/1")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]
        domain_store.record_results(
            UUID(snapshot_id),
            COLLECT_SOURCE,
            "normalizer.naver.blog",
            "0.1.0",
            "0.1",
            [
                NormalizedResultRow(
                    source_item_key="https://blog.example.com/1",
                    body={"schema_version": "0.1", "record_type": "document", "title": "t"},
                )
            ],
        )
        return snapshot_id

    def test_a_snapshot_s_results_are_readable_with_their_versions(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        snapshot_id = self._one_result(domain_store, job_connection, client)

        body = client.get(f"/snapshots/{snapshot_id}/results").json()

        assert body["results"][0]["addon_version"] == "0.1.0"
        assert body["results"][0]["output_contract_version"] == "0.1"
        assert body["results"][0]["body"]["schema_version"] == "0.1"

    def test_a_result_carries_the_raw_item_key_it_came_from(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        snapshot_id = self._one_result(domain_store, job_connection, client)

        body = client.get(f"/snapshots/{snapshot_id}/results").json()

        assert body["results"][0]["source_item_key"] == "https://blog.example.com/1"

    def test_a_snapshot_with_no_results_reports_an_empty_list(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, "a")
        snapshot_id = client.post(f"/sources/{COLLECT_SOURCE}/snapshots").json()["snapshot_id"]

        assert client.get(f"/snapshots/{snapshot_id}/results").json()["results"] == []


class TestWritingACredential:
    """New in P1 (DP-034 D1/D2). ``POST /sources/{id}/credentials``."""

    def test_the_file_gains_the_key_and_the_response_carries_no_value(
        self,
        client: TestClient,
        registered: None,
        store: Path,
    ) -> None:
        response = client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "the-actual-secret-42"},
        )

        assert response.status_code == 204
        assert response.text == ""
        assert "the-actual-secret-42" not in response.text

        content = store.read_text(encoding="utf-8")
        assert "COSMA_SRC_PROBE_BLOG_CLIENT_ID=the-actual-secret-42" in content

    def test_the_ref_uppercases_and_transliterates_the_source_id(
        self, client: TestClient, registered: None, store: Path
    ) -> None:
        """`COLLECT_SOURCE` is `"probe-blog"`; the hyphen becomes an underscore."""
        client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "token", "value": "v1"},
        )

        content = store.read_text(encoding="utf-8")
        assert "COSMA_SRC_PROBE_BLOG_TOKEN=v1" in content

    def test_a_second_post_replaces_rather_than_duplicates(
        self, client: TestClient, registered: None, store: Path
    ) -> None:
        client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "first-value"},
        )
        response = client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "second-value"},
        )

        assert response.status_code == 204
        content = store.read_text(encoding="utf-8")
        assert content.count("COSMA_SRC_PROBE_BLOG_CLIENT_ID=") == 1
        assert "COSMA_SRC_PROBE_BLOG_CLIENT_ID=second-value" in content
        assert "first-value" not in content

    def test_the_store_s_mode_is_unchanged_by_the_write(
        self, client: TestClient, registered: None, store: Path
    ) -> None:
        import stat

        before = stat.S_IMODE(store.stat().st_mode)
        client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "v1"},
        )
        after = stat.S_IMODE(store.stat().st_mode)
        assert before == after == 0o600

    def test_an_unregistered_source_is_404(self, client: TestClient, registered: None) -> None:
        response = client.post(
            "/sources/nope/credentials", json={"purpose": "token", "value": "v1"}
        )
        assert response.status_code == 404

    def test_an_empty_purpose_is_refused(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.post(
            f"/sources/{COLLECT_SOURCE}/credentials", json={"purpose": "", "value": "v1"}
        )
        assert response.status_code == 422

    def test_an_empty_value_is_refused(self, client: TestClient, registered: None) -> None:
        response = client.post(
            f"/sources/{COLLECT_SOURCE}/credentials", json={"purpose": "token", "value": ""}
        )
        assert response.status_code == 422

    def test_an_unresolvable_store_is_configuration_invalid(
        self,
        client: TestClient,
        registered: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DP-034 D1: no silent fallback to creating a store somewhere else."""
        monkeypatch.delenv("COSMA_SECRET_SOURCE", raising=False)

        response = client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "v1"},
        )

        assert response.status_code == 422
        assert response.json()["error_class"] == "CONFIGURATION_INVALID"
        assert "v1" not in response.text

    def test_the_value_never_reaches_the_log_stream(
        self,
        client: TestClient,
        registered: None,
        log_stream: StringIO,
    ) -> None:
        client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "a-value-nothing-should-echo"},
        )

        assert "a-value-nothing-should-echo" not in log_stream.getvalue()

    def test_the_credential_ref_itself_is_visible_in_the_log(
        self,
        client: TestClient,
        registered: None,
        log_stream: StringIO,
    ) -> None:
        """The M2 batch 2c redaction exemption, exercised end to end: the ref name is
        diagnostic and safe to log even though a substring of it matches `credential`."""
        client.post(
            f"/sources/{COLLECT_SOURCE}/credentials",
            json={"purpose": "client_id", "value": "v1"},
        )

        assert "COSMA_SRC_PROBE_BLOG_CLIENT_ID" in log_stream.getvalue()


class TestThePlatformSurfaceIsUnchanged:
    """The seam must add and never replace. Every P0-A/M1 scenario reads these."""

    def test_health_still_answers(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_jobs_still_answers(self, client: TestClient) -> None:
        assert client.get("/jobs").status_code == 200

    def test_an_app_built_without_the_seam_has_no_domain_routes(
        self, platform_config: PlatformConfig, job_logger: StructuredLogger
    ) -> None:
        plain = TestClient(create_app(platform_config, job_logger))

        assert plain.get("/sources").status_code == 404
        assert plain.get("/health").status_code == 200
