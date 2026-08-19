"""Where a normalized result goes, and what a snapshot selects — DP-019 D3, D4, D5.

`project-state.md` §4 asks for three properties that are easy to state and easy to lose:
normalized results are **versioned and coexist** rather than being updated in place, a run
consumes a **sealed, hash-verifiable** input, and the normalizer is **deterministic**. Each
has a class here, and each is written so that losing the property fails rather than passes.

The determinism class is the one worth reading twice. "Two runs produced the same thing" is
only evidence when the two runs could have differed — so the assertions compare *digests the
store computed*, not values a test carried between calls.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from domain.store import (
    DomainStore,
    NormalizedResultRow,
    RawItemRow,
    SourceRow,
    canonical_body,
    digest_of,
)

pytestmark = pytest.mark.usefixtures("database")

SOURCE_ID = "probe"
ADDON = "normalizer.probe"
VERSION = "0.1.0"
OUTPUT_CONTRACT = "0.1"


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


@pytest.fixture
def source(domain: DomainStore) -> str:
    domain.register_source(
        SourceRow(
            source_id=SOURCE_ID,
            addon_id="collector.probe",
            addon_version="0.1.0",
            kind="collector",
            config_schema_version="1",
        )
    )
    return SOURCE_ID


@pytest.fixture
def snapshot_id(domain: DomainStore, source: str) -> Any:
    """A real sealed snapshot, because `normalized_result` has a foreign key to one.

    That key is DP-019's "lineage is not optional" as a database constraint: a result with
    no snapshot names bytes nobody can go back to, and reproducibility is the whole reason
    the snapshot is materialized rather than queried. An empty one is enough here — what
    these cases are about is the result rows.
    """
    return domain.seal_snapshot_from_raw(source)


def a_body(external_id: str = "post-1", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "0.1",
        "record_type": "document",
        "external_id": external_id,
        "url": f"https://blog.example.com/{external_id}",
        "title": "제품 후기",
        "excerpt": "본문 일부",
        "published_at": "2026-08-01",
        "author": "someone",
        "language": "ko",
    }
    body.update(overrides)
    return body


def a_result(key: str = "post-1", **overrides: Any) -> NormalizedResultRow:
    return NormalizedResultRow(
        source_item_key=key, body=a_body(key, **overrides), notes={}
    )


class TestCanonicalisingABody:
    """DP-019 D4. Determinism is a property of what is *stored*, so the canonical form is
    the store's and not each add-on's."""

    def test_key_order_does_not_change_the_digest(self) -> None:
        first = canonical_body({"b": 2, "a": 1})
        second = canonical_body({"a": 1, "b": 2})
        assert digest_of(first) == digest_of(second)

    def test_a_different_value_does_change_it(self) -> None:
        """The control. A canonicaliser that returned a constant would pass the test
        above."""
        assert digest_of(canonical_body({"a": 1})) != digest_of(canonical_body({"a": 2}))

    def test_it_is_compact_json_so_two_writers_cannot_differ_by_whitespace(self) -> None:
        assert canonical_body({"a": 1, "b": "x"}) == b'{"a":1,"b":"x"}'

    def test_non_ascii_survives_as_itself_rather_than_as_an_escape(self) -> None:
        """Korean text is the ordinary case for this source. `ensure_ascii` would store
        `\\uc81c` and make every digest depend on a serializer setting nobody stated."""
        assert "제품".encode() in canonical_body({"t": "제품"})


class TestRecordingResults:
    def test_a_result_is_stored_with_its_lineage(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        rows = domain.read_results(snapshot_id)
        assert len(rows) == 1
        assert rows[0]["source_item_key"] == "post-1"
        assert rows[0]["addon_id"] == ADDON
        assert rows[0]["output_contract_version"] == OUTPUT_CONTRACT

    def test_the_body_comes_back_as_it_went_in(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        assert domain.read_results(snapshot_id)[0]["body"] == a_body()

    def test_the_digest_is_computed_by_the_store_rather_than_supplied(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """An add-on that computed its own digest could report one that does not match what
        it wrote, and the determinism claim would rest on the add-on's arithmetic."""
        domain.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        stored = domain.read_results(snapshot_id)[0]
        assert stored["body_sha256"] == digest_of(canonical_body(a_body()))


class TestVersionsCoexist:
    """`project-state.md` §4: results are versioned and coexist; they are not updated in
    place as the single truth."""

    def test_two_add_on_versions_over_one_snapshot_both_survive(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain.record_results(
            snapshot_id, source, ADDON, "0.1.0", OUTPUT_CONTRACT, [a_result()]
        )
        domain.record_results(
            snapshot_id, source, ADDON, "0.2.0", OUTPUT_CONTRACT, [a_result(title="다시")]
        )

        versions = sorted(row["addon_version"] for row in domain.read_results(snapshot_id))
        assert versions == ["0.1.0", "0.2.0"]

    def test_two_output_contract_versions_also_coexist(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain.record_results(snapshot_id, source, ADDON, VERSION, "0.1", [a_result()])
        domain.record_results(snapshot_id, source, ADDON, VERSION, "0.2", [a_result()])

        assert len(domain.read_results(snapshot_id)) == 2

    def test_rerunning_one_version_over_one_snapshot_is_refused_rather_than_doubled(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """The other half of "coexist": the same run twice is a duplicate, not a version.
        Without this, an at-least-once retry silently doubles every result."""
        domain.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            domain.record_results(
                snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
            )

    def test_reading_can_be_narrowed_to_one_version(
        self, domain: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain.record_results(snapshot_id, source, ADDON, "0.1.0", OUTPUT_CONTRACT, [a_result()])
        domain.record_results(snapshot_id, source, ADDON, "0.2.0", OUTPUT_CONTRACT, [a_result()])

        narrowed = domain.read_results(snapshot_id, addon_version="0.2.0")
        assert [row["addon_version"] for row in narrowed] == ["0.2.0"]


class TestSealingASnapshotFromRaw:
    """DP-019 D5. The selection is every `raw_item` of one source, ordered by `item_key`."""

    def _collect(self, domain: DomainStore, connection: Any, *keys: str) -> None:
        envelope = _an_envelope(domain, connection)
        domain.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(item_key=k, payload=k.encode(), content_type="application/json")
             for k in keys],
        )

    def test_every_item_of_the_source_becomes_a_member(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        self._collect(domain, connection, "b", "a", "c")

        snapshot_id = domain.seal_snapshot_from_raw(source)

        members = domain.read_snapshot_items(snapshot_id)
        assert [m["item_key"] for m in members] == ["a", "b", "c"]

    def test_the_order_is_the_key_and_not_the_arrival(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        """A re-collection that produced identical items must produce an identical
        snapshot, so the ordering cannot depend on when collection happened."""
        self._collect(domain, connection, "z")
        self._collect(domain, connection, "a")

        members = domain.read_snapshot_items(domain.seal_snapshot_from_raw(source))
        assert [m["ordinal"] for m in members] == [0, 1]
        assert [m["item_key"] for m in members] == ["a", "z"]

    def test_a_duplicate_key_collapses_to_the_latest(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        """`raw_item` permits duplicates on purpose — duplicate policy is an open question —
        and `snapshot_item` requires one row per key. DP-019 D5 records this as a choice."""
        self._collect(domain, connection, "a")
        envelope = _an_envelope(domain, connection)
        domain.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(item_key="a", payload=b"newer", content_type="application/json")],
        )

        members = domain.read_snapshot_items(domain.seal_snapshot_from_raw(source))
        assert len(members) == 1
        assert bytes(members[0]["payload"]) == b"newer"

    def test_a_source_with_no_raw_seals_an_empty_snapshot_rather_than_failing(
        self, domain: DomainStore, source: str
    ) -> None:
        """An empty snapshot is an ordinary state — a source collected nothing — and a
        normalizer over it reports zero results. Failing here would make "nothing to
        normalize" indistinguishable from a defect."""
        assert a_snapshot(domain, source)["item_count"] == 0

    def test_the_sealed_snapshot_verifies(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        self._collect(domain, connection, "a", "b")

        assert domain.snapshot_tampering(domain.seal_snapshot_from_raw(source)) == ()

    def test_two_seals_of_unchanged_raw_agree_on_their_manifest(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        """The reproducibility claim, stated where it can fail. Two snapshots of the same
        Raw are different rows with the same manifest digest."""
        self._collect(domain, connection, "a", "b")

        first = a_snapshot(domain, source)
        second = a_snapshot(domain, source)

        assert first["id"] != second["id"]
        assert first["manifest_sha256"] == second["manifest_sha256"]

    def test_a_changed_item_changes_the_manifest(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        """The control for the case above. Equal manifests mean nothing unless an unequal
        input produces an unequal manifest."""
        self._collect(domain, connection, "a")
        first = a_snapshot(domain, source)
        self._collect(domain, connection, "b")
        second = a_snapshot(domain, source)

        assert first["manifest_sha256"] != second["manifest_sha256"]

    def test_the_selection_records_what_was_taken(
        self, domain: DomainStore, source: str, connection: psycopg.Connection[Any]
    ) -> None:
        """`snapshot.selection` is prose for a human reading a run afterwards, and DP-019
        D5 is the prose it should carry."""
        self._collect(domain, connection, "a")

        selection = a_snapshot(domain, source)["selection"]
        assert selection["source_id"] == SOURCE_ID
        assert selection["rule"] == "every raw_item of one source, ordered by item_key"


def a_snapshot(domain: DomainStore, source_id: str) -> dict[str, Any]:
    """Seal, then read back. `read_snapshot` returns `None` for a snapshot that does not
    exist, and every caller here has just created one — so the assertion is the narrowing."""
    row = domain.read_snapshot(domain.seal_snapshot_from_raw(source_id))
    assert row is not None
    return row


def _an_envelope(domain: DomainStore, connection: psycopg.Connection[Any]) -> Any:
    """A job, an attempt, and an envelope to hang items from. Raw needs all three."""
    job_id = uuid4()
    connection.execute(
        "insert into job (id, handler, payload, state, attempt_count, max_attempts, "
        "available_at, correlation_id) values (%s, 'x', %s, 'PENDING', 0, 1, now(), 'c')",
        (job_id, json.dumps({})),
    )
    attempt_id = uuid4()
    connection.execute(
        "insert into job_attempt (id, job_id, attempt_no, worker_id, correlation_id) "
        "values (%s, %s, (select coalesce(max(attempt_no), 0) + 1 from job_attempt "
        "where job_id = %s), 'w', 'c')",
        (attempt_id, job_id, job_id),
    )
    return domain.record_envelope(
        SOURCE_ID, job_id, attempt_id, "collector.probe", "0.1.0",
        body=b"{}", endpoint_ref="items",
    )
