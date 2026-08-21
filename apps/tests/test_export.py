"""Streaming export: `/export/raw` and `/export/results` (M6 batch 6b; DP-033 D3).

Uses the same in-process `TestClient` pattern `tests/test_domain_api.py` does —
`apps/domain/export.py`'s own docstring is explicit that its generators open
their *own* connection rather than reusing a request-scoped one, so a
`TestClient` request here really does exercise the server-side-cursor path end
to end, not a shortcut around it.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from domain.api import extend_with_domain
from domain.store import DomainStore, NormalizedResultRow, RawItemRow, SourceRow
from platform_core.api.app import create_app
from platform_core.config import PlatformConfig
from platform_core.obs.logging import StructuredLogger

SOURCE_ID = "export-src"
NORMALIZER_SOURCE_ID = "export-norm-src"


@pytest.fixture
def client(
    platform_config: PlatformConfig, job_logger: StructuredLogger, domain_store: DomainStore
) -> TestClient:
    app = create_app(
        platform_config, job_logger, extend=extend_with_domain(platform_config, job_logger)
    )
    return TestClient(app)


@pytest.fixture
def registered(domain_store: DomainStore) -> None:
    domain_store.register_source(
        SourceRow(
            source_id=SOURCE_ID,
            addon_id="collector.smoke",
            addon_version="0.1.0",
            kind="collector",
            config={},
            config_schema_version="1",
        )
    )
    domain_store.register_source(
        SourceRow(
            source_id=NORMALIZER_SOURCE_ID,
            addon_id="normalizer.smoke",
            addon_version="0.1.0",
            kind="normalizer",
            config={},
            config_schema_version="1",
        )
    )


def put_raw(
    domain_store: DomainStore,
    job_connection: psycopg.Connection[Any],
    items: list[RawItemRow],
    source_id: str = SOURCE_ID,
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
        source_id, job_id, attempt_id, "collector.smoke", "0.1.0",
        body=b"{}", endpoint_ref="items",
    )
    domain_store.record_items(envelope, source_id, items)


def set_emitted_at(
    connection: psycopg.Connection[Any], item_key: str, when: str, source_id: str = SOURCE_ID
) -> None:
    connection.execute(
        "update cosmai.raw_item set emitted_at = %s where source_id = %s and item_key = %s",
        (when, source_id, item_key),
    )


class TestRawExportJsonl:
    def test_jsonl_default_splices_the_payload_verbatim(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(
            domain_store,
            job_connection,
            [RawItemRow("k1", b'{"b":2,"a":1}', "application/json")],
        )

        response = client.get("/export/raw", params={"source_id": SOURCE_ID})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert 'filename="raw-export-src.jsonl"' in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["item_key"] == "k1"
        assert record["content_type"] == "application/json"
        # Spliced verbatim: the original key order (`b` before `a`) survives,
        # which a `json.loads`/`json.dumps` round trip through Python's
        # (insertion-ordered but not sorted) dict would not by itself guarantee
        # unless the splice really did copy the original bytes untouched.
        assert list(record["payload"].keys()) == ["b", "a"]
        assert record["payload"] == {"b": 2, "a": 1}

    def test_a_non_json_payload_falls_back_to_an_escaped_string(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(domain_store, job_connection, [RawItemRow("k1", b"not json", "text/plain")])

        response = client.get("/export/raw", params={"source_id": SOURCE_ID})

        record = json.loads(response.text.splitlines()[0])
        assert record["payload"] == "not json"

    def test_a_pretty_printed_payload_is_re_serialized_compactly_not_spliced_verbatim(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """B3 (REVIEW-M2-M7.md): `json.loads` accepts embedded newlines, so a
        pretty-printed payload spliced in verbatim puts its own newlines inside what is
        supposed to be one JSONL line — one stored item becomes several unparseable
        physical lines and everything after it in the export is corrupted. The review's
        own reproduction payload."""
        put_raw(
            domain_store,
            job_connection,
            [
                RawItemRow("k1", b'{\n  "title": "hello"\n}', "application/json"),
                RawItemRow("k2", b'{"title": "second"}', "application/json"),
            ],
        )

        response = client.get("/export/raw", params={"source_id": SOURCE_ID})

        assert response.status_code == 200
        lines = response.text.splitlines()
        # The whole export must remain line-parseable: every physical line is its own
        # complete JSON object, and there is exactly one line per stored item.
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        by_key = {r["item_key"]: r for r in records}
        assert by_key["k1"]["payload"] == {"title": "hello"}
        assert by_key["k2"]["payload"] == {"title": "second"}

    def test_an_empty_source_is_zero_lines_not_an_error(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.get("/export/raw", params={"source_id": SOURCE_ID})

        assert response.status_code == 200
        assert response.text == ""

    def test_an_unregistered_source_is_404(self, client: TestClient, registered: None) -> None:
        assert client.get("/export/raw", params={"source_id": "nope"}).status_code == 404

    def test_a_source_id_is_required(self, client: TestClient, registered: None) -> None:
        assert client.get("/export/raw").status_code == 422


class TestRawExportCsv:
    def test_csv_escapes_quotes_and_newlines_and_round_trips(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        original = 'has "quotes" and\nnewlines, and a comma'
        put_raw(
            domain_store,
            job_connection,
            [RawItemRow("k1", original.encode("utf-8"), "text/plain")],
        )

        response = client.get(
            "/export/raw", params={"source_id": SOURCE_ID, "format": "csv"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        rows = list(csv.reader(io.StringIO(response.text)))
        assert rows[0] == ["item_key", "seq", "emitted_at", "content_type", "payload"]
        assert len(rows) == 2
        assert rows[1][0] == "k1"
        assert rows[1][4] == original

    def test_an_empty_source_is_a_header_only_file(
        self, client: TestClient, registered: None
    ) -> None:
        response = client.get(
            "/export/raw", params={"source_id": SOURCE_ID, "format": "csv"}
        )

        rows = list(csv.reader(io.StringIO(response.text)))
        assert rows == [["item_key", "seq", "emitted_at", "content_type", "payload"]]

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
    def test_a_payload_starting_with_a_formula_prefix_is_guarded(
        self,
        prefix: str,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        """M-S4 (REVIEW-M2-M7.md): RFC4180 quoting (`test_csv_escapes_quotes...` above)
        protects CSV *syntax*; it does nothing against a spreadsheet application
        evaluating a well-quoted cell as a formula because its content starts with one
        of these characters. A leading `'` defeats that without changing the content a
        reader that does not treat it as a formula marker sees."""
        original = f"{prefix}cmd|'/c calc'!A1"
        put_raw(
            domain_store,
            job_connection,
            [RawItemRow("k1", original.encode("utf-8"), "text/plain")],
        )

        response = client.get(
            "/export/raw", params={"source_id": SOURCE_ID, "format": "csv"}
        )

        rows = list(csv.reader(io.StringIO(response.text)))
        assert rows[1][4] == f"'{original}"


class TestRawExportScopeFilters:
    def test_from_and_to_bound_emitted_at(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(
            domain_store,
            job_connection,
            [
                RawItemRow("early", b'{"n":1}', "application/json"),
                RawItemRow("middle", b'{"n":2}', "application/json"),
                RawItemRow("late", b'{"n":3}', "application/json"),
            ],
        )
        set_emitted_at(job_connection, "early", "2020-01-01T00:00:00Z")
        set_emitted_at(job_connection, "middle", "2021-06-01T00:00:00Z")
        set_emitted_at(job_connection, "late", "2023-01-01T00:00:00Z")

        response = client.get(
            "/export/raw",
            params={
                "source_id": SOURCE_ID,
                "from": "2021-01-01T00:00:00Z",
                "to": "2022-01-01T00:00:00Z",
            },
        )

        keys = [json.loads(line)["item_key"] for line in response.text.splitlines()]
        assert keys == ["middle"]

    def test_key_prefix_matches_the_start_of_item_key_literally(
        self,
        client: TestClient,
        registered: None,
        domain_store: DomainStore,
        job_connection: psycopg.Connection[Any],
    ) -> None:
        put_raw(
            domain_store,
            job_connection,
            [
                RawItemRow("alpha-1", b'{"n":1}', "application/json"),
                RawItemRow("alpha-2", b'{"n":2}', "application/json"),
                RawItemRow("beta-1", b'{"n":3}', "application/json"),
            ],
        )

        response = client.get(
            "/export/raw", params={"source_id": SOURCE_ID, "key_prefix": "alpha-"}
        )

        keys = sorted(json.loads(line)["item_key"] for line in response.text.splitlines())
        assert keys == ["alpha-1", "alpha-2"]


class TestResultsExport:
    def test_jsonl_and_csv_both_redact_the_body_like_the_json_api_does(
        self, client: TestClient, registered: None, domain_store: DomainStore
    ) -> None:
        snapshot_id = domain_store.seal_snapshot(NORMALIZER_SOURCE_ID, members=())
        domain_store.record_results(
            snapshot_id,
            NORMALIZER_SOURCE_ID,
            "normalizer.smoke",
            "0.1.0",
            "1",
            [
                NormalizedResultRow(
                    source_item_key="k1",
                    body={"title": "ok", "api_key": "shhh"},
                )
            ],
        )

        jsonl = client.get(
            "/export/results", params={"source_id": NORMALIZER_SOURCE_ID}
        )
        record = json.loads(jsonl.text.splitlines()[0])
        assert record["body"]["title"] == "ok"
        assert record["body"]["api_key"] != "shhh"
        assert "shhh" not in jsonl.text

        csv_response = client.get(
            "/export/results", params={"source_id": NORMALIZER_SOURCE_ID, "format": "csv"}
        )
        assert "shhh" not in csv_response.text

    def test_an_empty_source_is_a_header_only_csv_and_zero_jsonl_lines(
        self, client: TestClient, registered: None
    ) -> None:
        csv_response = client.get(
            "/export/results", params={"source_id": NORMALIZER_SOURCE_ID, "format": "csv"}
        )
        rows = list(csv.reader(io.StringIO(csv_response.text)))
        assert len(rows) == 1

        jsonl_response = client.get(
            "/export/results", params={"source_id": NORMALIZER_SOURCE_ID}
        )
        assert jsonl_response.text == ""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
    def test_a_source_item_key_starting_with_a_formula_prefix_is_guarded(
        self, prefix: str, client: TestClient, registered: None, domain_store: DomainStore
    ) -> None:
        """M-S4 (REVIEW-M2-M7.md): the results CSV's equivalent of the raw CSV's guard.
        `source_item_key` is add-on-derived (a normalizer's `NormalizedResult.source_item_key`,
        ultimately from an upstream provider's own record), the same kind of untrusted
        string as a raw payload."""
        snapshot_id = domain_store.seal_snapshot(NORMALIZER_SOURCE_ID, members=())
        item_key = f"{prefix}cmd|'/c calc'!A1"
        domain_store.record_results(
            snapshot_id,
            NORMALIZER_SOURCE_ID,
            "normalizer.smoke",
            "0.1.0",
            "1",
            [NormalizedResultRow(source_item_key=item_key, body={"title": "ok"})],
        )

        csv_response = client.get(
            "/export/results", params={"source_id": NORMALIZER_SOURCE_ID, "format": "csv"}
        )

        rows = list(csv.reader(io.StringIO(csv_response.text)))
        assert rows[0][6] == "source_item_key"
        assert rows[1][6] == f"'{item_key}"


class TestLargeExportStreams:
    def test_ten_thousand_rows_stream_without_materializing_a_list(
        self,
        client: TestClient,
        registered: None,
        job_connection: psycopg.Connection[Any],
        domain_store: DomainStore,
    ) -> None:
        """H3 (DP-033 D3): a full-source export must not hold the whole result
        set in process memory at once. `apps/domain/export.py`'s own docstring
        records how — a named server-side cursor, fetched `BATCH_SIZE` rows at
        a time, never `fetchall()`. What this test actually measures is
        end-to-end correctness at volume (every one of 10,000 rows arrives,
        in order, uncorrupted) and that the request completes in bounded time;
        it does not itself measure process RSS — see `docs/p1/M6-RECORD.md`.
        """
        job_id, attempt_id = uuid4(), uuid4()
        job_connection.execute(
            "insert into cosmai.job (id, handler, payload, state, attempt_count, "
            "max_attempts, available_at, correlation_id) values "
            "(%s, 'x', '{}', 'SUCCEEDED', 1, 1, now(), 'c')",
            (job_id,),
        )
        job_connection.execute(
            "insert into cosmai.job_attempt (id, job_id, attempt_no, worker_id, "
            "correlation_id, finished_at, outcome) values "
            "(%s, %s, 1, 'w', 'c', now(), 'SUCCEEDED')",
            (attempt_id, job_id),
        )
        envelope_id = domain_store.record_envelope(
            SOURCE_ID, job_id, attempt_id, "collector.smoke", "0.1.0",
            body=b"{}", endpoint_ref="items",
        )
        job_connection.execute(
            """
            insert into cosmai.raw_item (id, envelope_id, source_id, item_key, payload,
                                          content_type, notes)
            select gen_random_uuid(), %(envelope_id)s, %(source_id)s,
                   'bulk-' || lpad(g::text, 6, '0'),
                   convert_to('{"n":' || g || '}', 'UTF8'),
                   'application/json', '{}'::jsonb
            from generate_series(1, 10000) as g
            """,
            {"envelope_id": envelope_id, "source_id": SOURCE_ID},
        )

        response = client.get("/export/raw", params={"source_id": SOURCE_ID})

        assert response.status_code == 200
        lines = response.text.splitlines()
        assert len(lines) == 10000
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        assert first["item_key"] == "bulk-000001"
        assert last["item_key"] == "bulk-010000"
        assert last["payload"] == {"n": 10000}
