"""Where a normalized result goes, and what a snapshot selects — DP-019 D3, D4, D5.

`project-state.md` §4 asks for three properties that are easy to state and easy to lose:
normalized results are **versioned and coexist** rather than being updated in place, a run
consumes a **sealed, hash-verifiable** input, and the normalizer is **deterministic**. Each
has a class here, and each is written so that losing the property fails rather than passes.

The determinism class is the one worth reading twice. "Two runs produced the same thing" is
only evidence when the two runs could have differed — so the assertions compare *digests the
store computed*, not values a test carried between calls.

Copy-adapted from ``experiments/integrated-p0/tests/test_normalized_results.py`` (M2 batch
2b): fixture names and schema-qualification adapted the same way
``test_domain_store.py``'s own docstring explains, no existing assertion changed. Three
classes are new here rather than in P0 — ``TestASameKeyTieIsBrokenBySequenceNotArrival``,
``TestManifestOrderIsUtf8BytewiseRegardlessOfCollation``, and
``TestPerRecordFaultTolerance`` — the batch's three mandatory regression tests for DP-029
D2/D3 and DP-030 D2.
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

SOURCE_ID = "probe"
ADDON = "normalizer.probe"
VERSION = "0.1.0"
OUTPUT_CONTRACT = "0.1"


@pytest.fixture
def source(domain_store: DomainStore) -> str:
    domain_store.register_source(
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
def snapshot_id(domain_store: DomainStore, source: str) -> Any:
    """A real sealed snapshot, because `normalized_result` has a foreign key to one.

    That key is DP-019's "lineage is not optional" as a database constraint: a result with
    no snapshot names bytes nobody can go back to, and reproducibility is the whole reason
    the snapshot is materialized rather than queried. An empty one is enough here — what
    these cases are about is the result rows.
    """
    return domain_store.seal_snapshot_from_raw(source)


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
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        rows = domain_store.read_results(snapshot_id)
        assert len(rows) == 1
        assert rows[0]["source_item_key"] == "post-1"
        assert rows[0]["addon_id"] == ADDON
        assert rows[0]["output_contract_version"] == OUTPUT_CONTRACT

    def test_the_body_comes_back_as_it_went_in(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        assert domain_store.read_results(snapshot_id)[0]["body"] == a_body()

    def test_the_digest_is_computed_by_the_store_rather_than_supplied(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """An add-on that computed its own digest could report one that does not match what
        it wrote, and the determinism claim would rest on the add-on's arithmetic."""
        domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        stored = domain_store.read_results(snapshot_id)[0]
        assert stored["body_sha256"] == digest_of(canonical_body(a_body()))


class TestVersionsCoexist:
    """`project-state.md` §4: results are versioned and coexist; they are not updated in
    place as the single truth."""

    def test_two_add_on_versions_over_one_snapshot_both_survive(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain_store.record_results(
            snapshot_id, source, ADDON, "0.1.0", OUTPUT_CONTRACT, [a_result()]
        )
        domain_store.record_results(
            snapshot_id, source, ADDON, "0.2.0", OUTPUT_CONTRACT, [a_result(title="다시")]
        )

        versions = sorted(row["addon_version"] for row in domain_store.read_results(snapshot_id))
        assert versions == ["0.1.0", "0.2.0"]

    def test_two_output_contract_versions_also_coexist(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain_store.record_results(snapshot_id, source, ADDON, VERSION, "0.1", [a_result()])
        domain_store.record_results(snapshot_id, source, ADDON, VERSION, "0.2", [a_result()])

        assert len(domain_store.read_results(snapshot_id)) == 2

    def test_rerunning_one_version_over_one_snapshot_is_refused_rather_than_doubled(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """The other half of "coexist": the same run twice is a duplicate, not a version.
        Without this, an at-least-once retry silently doubles every result."""
        domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            domain_store.record_results(
                snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
            )

    def test_reading_can_be_narrowed_to_one_version(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        domain_store.record_results(
            snapshot_id, source, ADDON, "0.1.0", OUTPUT_CONTRACT, [a_result()]
        )
        domain_store.record_results(
            snapshot_id, source, ADDON, "0.2.0", OUTPUT_CONTRACT, [a_result()]
        )

        narrowed = domain_store.read_results(snapshot_id, addon_version="0.2.0")
        assert [row["addon_version"] for row in narrowed] == ["0.2.0"]


class TestSealingASnapshotFromRaw:
    """DP-019 D5. The selection is every `raw_item` of one source, ordered by `item_key`."""

    def _collect(self, domain_store: DomainStore, job_connection: Any, *keys: str) -> None:
        envelope = _an_envelope(domain_store, job_connection)
        domain_store.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(item_key=k, payload=k.encode(), content_type="application/json")
             for k in keys],
        )

    def test_every_item_of_the_source_becomes_a_member(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        self._collect(domain_store, job_connection, "b", "a", "c")

        snapshot_id = domain_store.seal_snapshot_from_raw(source)

        members = domain_store.read_snapshot_items(snapshot_id)
        assert [m["item_key"] for m in members] == ["a", "b", "c"]

    def test_the_order_is_the_key_and_not_the_arrival(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """A re-collection that produced identical items must produce an identical
        snapshot, so the ordering cannot depend on when collection happened."""
        self._collect(domain_store, job_connection, "z")
        self._collect(domain_store, job_connection, "a")

        members = domain_store.read_snapshot_items(domain_store.seal_snapshot_from_raw(source))
        assert [m["ordinal"] for m in members] == [0, 1]
        assert [m["item_key"] for m in members] == ["a", "z"]

    def test_a_duplicate_key_collapses_to_the_latest(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """`raw_item` permits duplicates on purpose — duplicate policy is an open question —
        and `snapshot_item` requires one row per key. DP-019 D5 records this as a choice."""
        self._collect(domain_store, job_connection, "a")
        envelope = _an_envelope(domain_store, job_connection)
        domain_store.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(item_key="a", payload=b"newer", content_type="application/json")],
        )

        members = domain_store.read_snapshot_items(domain_store.seal_snapshot_from_raw(source))
        assert len(members) == 1
        assert bytes(members[0]["payload"]) == b"newer"

    def test_a_source_with_no_raw_seals_an_empty_snapshot_rather_than_failing(
        self, domain_store: DomainStore, source: str
    ) -> None:
        """An empty snapshot is an ordinary state — a source collected nothing — and a
        normalizer over it reports zero results. Failing here would make "nothing to
        normalize" indistinguishable from a defect."""
        assert a_snapshot(domain_store, source)["item_count"] == 0

    def test_the_sealed_snapshot_verifies(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        self._collect(domain_store, job_connection, "a", "b")

        assert domain_store.snapshot_tampering(domain_store.seal_snapshot_from_raw(source)) == ()

    def test_two_seals_of_unchanged_raw_agree_on_their_manifest(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """The reproducibility claim, stated where it can fail. Two snapshots of the same
        Raw are different rows with the same manifest digest."""
        self._collect(domain_store, job_connection, "a", "b")

        first = a_snapshot(domain_store, source)
        second = a_snapshot(domain_store, source)

        assert first["id"] != second["id"]
        assert first["manifest_sha256"] == second["manifest_sha256"]

    def test_a_changed_item_changes_the_manifest(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """The control for the case above. Equal manifests mean nothing unless an unequal
        input produces an unequal manifest."""
        self._collect(domain_store, job_connection, "a")
        first = a_snapshot(domain_store, source)
        self._collect(domain_store, job_connection, "b")
        second = a_snapshot(domain_store, source)

        assert first["manifest_sha256"] != second["manifest_sha256"]

    def test_the_selection_records_what_was_taken(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """`snapshot.selection` is prose for a human reading a run afterwards, and DP-019
        D5 is the prose it should carry."""
        self._collect(domain_store, job_connection, "a")

        selection = a_snapshot(domain_store, source)["selection"]
        assert selection["source_id"] == SOURCE_ID
        assert selection["rule"] == "every raw_item of one source, ordered by item_key"


class TestASameKeyTieIsBrokenBySequenceNotArrival:
    """M2 batch 2b mandatory regression 1 — DP-029 D2.

    P0's tie-break was `emitted_at desc, id desc`. `emitted_at` is a
    **transaction** timestamp, not a per-row order, and DP-029's own evidence
    (`docs/decisions/DP-029-p1-snapshot-identity.md`) forced two imports to an
    equal `emitted_at` and re-sealed 12 times: the `uuid4` fallback selected the
    *older* payload in 2 of 3 keys. `raw_item.seq` (`generated always as
    identity`) replaces that fallback with an explicit, monotonically increasing
    per-row order, independent of which transaction wrote which row.
    """

    def test_twelve_re_seals_all_pick_the_higher_sequence_row(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """Two rows, same key, written inside **one transaction** — so `emitted_at`
        is provably equal for both, the exact condition DP-029's evidence forced
        by hand. Re-sealing 12 times (DP-029's own repetition count) must select
        the higher-`seq` row — the second one written — every time.
        """
        envelope = _an_envelope(domain_store, job_connection)
        with job_connection.transaction():
            domain_store.record_items(
                envelope, SOURCE_ID, [RawItemRow("tied", b"older", "application/json")]
            )
            domain_store.record_items(
                envelope, SOURCE_ID, [RawItemRow("tied", b"newer", "application/json")]
            )

        distinct_emitted_at = job_connection.execute(
            "select count(distinct emitted_at) from cosmai.raw_item where item_key = 'tied'"
        ).fetchone()
        assert distinct_emitted_at is not None and distinct_emitted_at[0] == 1, (
            "the two rows must share one emitted_at to reproduce the tie DP-029 measured"
        )

        for attempt in range(12):
            snapshot_id = domain_store.seal_snapshot_from_raw(SOURCE_ID)
            members = domain_store.read_snapshot_items(snapshot_id)
            assert len(members) == 1, f"re-seal {attempt}"
            assert bytes(members[0]["payload"]) == b"newer", f"re-seal {attempt}"


class TestManifestOrderIsUtf8BytewiseRegardlessOfCollation:
    """M2 batch 2b mandatory regression 2 — DP-029 D3.

    DP-019 D5 fixed no collation for "ordered by `item_key`", and DP-029's own
    evidence found that a collation-only column change (no value altered)
    reordered every member a read-time selection returned. This store orders
    manifest members by `convert_to(item_key, 'UTF8')` in
    `SELECT_SNAPSHOT_MEMBERS` (`apps/domain/store.py`) — PostgreSQL's `bytea`
    comparison is always unsigned-byte order, so the result is fixed regardless
    of the connection's or the column's collation.
    """

    #: 'B' (0x42) < 'a' (0x61) < 'é' (0xC3 0xA9) in UTF-8 bytewise order. An ICU
    #: ("und-x-icu") reading of the same three keys — verified against this
    #: cluster below rather than assumed — orders them 'a', 'B', 'é' instead:
    #: case is a low-weight sort key in a linguistic collation and has no
    #: meaning at all to a byte comparison. This is DP-029's own falsification
    #: shape (`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-D), reproduced as
    #: a live comparison rather than a claim about what a collation "would" do.
    KEYS = ("é", "a", "B")

    def test_the_store_orders_members_by_utf8_bytes_not_by_a_linguistic_reading(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        envelope = _an_envelope(domain_store, job_connection)
        domain_store.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(k, k.encode("utf-8"), "text/plain") for k in self.KEYS],
        )

        icu_reading = [
            str(row[0])
            for row in job_connection.execute(
                "select item_key from cosmai.raw_item where source_id = %s "
                'order by item_key collate "und-x-icu"',
                (SOURCE_ID,),
            ).fetchall()
        ]
        assert icu_reading == ["a", "B", "é"], "the ICU reading itself must diverge to discriminate"

        members = domain_store.read_snapshot_items(domain_store.seal_snapshot_from_raw(SOURCE_ID))
        bytewise_reading = [m["item_key"] for m in members]
        assert bytewise_reading == ["B", "a", "é"]
        assert bytewise_reading != icu_reading

    def test_the_manifest_digest_is_stable_across_reseals(
        self, domain_store: DomainStore, source: str, job_connection: psycopg.Connection[Any]
    ) -> None:
        """The order is a property of the bytes, not of the run: two seals of the
        same Raw over these keys must agree on the manifest digest."""
        envelope = _an_envelope(domain_store, job_connection)
        domain_store.record_items(
            envelope,
            SOURCE_ID,
            [RawItemRow(k, k.encode("utf-8"), "text/plain") for k in self.KEYS],
        )

        first = domain_store.read_snapshot(domain_store.seal_snapshot_from_raw(SOURCE_ID))
        second = domain_store.read_snapshot(domain_store.seal_snapshot_from_raw(SOURCE_ID))
        assert first is not None and second is not None
        assert first["manifest_sha256"] == second["manifest_sha256"]


class TestPerRecordFaultTolerance:
    """M2 batch 2b mandatory regression 3 — DP-030 D2; repairs
    `P1-INHERITED-DEFECTS.md` §1.

    P0's `canonical_body` raised `UnicodeEncodeError` on a lone surrogate
    (`{"code": "a\\ud800"}`, P1-INHERITED-DEFECTS.md §1's own example) and — with
    the default `allow_nan=True` — silently wrote a bare `NaN`/`Infinity`
    literal for a non-finite float rather than rejecting it at all. Either one
    ended the whole normalize run for one bad record. `record_results` now
    catches both failure modes per record via `_safe_canonical_body`: the
    offending field is replaced with `null`, a `notes.normalize_error {field,
    reason}` entry is written, and the run continues.
    """

    def test_a_lone_surrogate_does_not_abort_the_run(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """One bad row plus two good ones: three stored results, exactly one
        flagged, and the call itself must not raise."""
        results = [
            a_result("good-1"),
            NormalizedResultRow(source_item_key="bad-1", body={"code": "a\ud800"}, notes={}),
            a_result("good-2"),
        ]

        summary = domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, results
        )

        assert summary.written == 3
        assert summary.error_records == 1

        rows = {row["source_item_key"]: row for row in domain_store.read_results(snapshot_id)}
        assert set(rows) == {"good-1", "bad-1", "good-2"}
        assert "normalize_error" not in rows["good-1"]["notes"]
        assert "normalize_error" not in rows["good-2"]["notes"]

        error = rows["bad-1"]["notes"]["normalize_error"]
        assert error == {"field": "code", "reason": error["reason"]}
        assert "surrogates" in error["reason"]
        assert rows["bad-1"]["body"]["code"] is None

    def test_a_non_finite_float_takes_the_same_path(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """DP-030 D2 closes P0's `allow_nan=True` gap: a NaN now fails
        `canonical_body` (`allow_nan=False`) instead of reaching the store as a
        bare `NaN` literal, and routes through the same per-record fallback as a
        lone surrogate rather than a separate code path or an aborted run."""
        results = [
            NormalizedResultRow(
                source_item_key="bad-nan", body={"score": float("nan")}, notes={}
            )
        ]

        summary = domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, results
        )

        assert summary.written == 1
        assert summary.error_records == 1
        row = domain_store.read_results(snapshot_id)[0]
        assert row["body"]["score"] is None
        assert row["notes"]["normalize_error"]["field"] == "score"

    def test_a_good_batch_carries_no_error_notes(
        self, domain_store: DomainStore, source: str, snapshot_id: Any
    ) -> None:
        """The positive control: nothing here should ever flag a clean record."""
        summary = domain_store.record_results(
            snapshot_id, source, ADDON, VERSION, OUTPUT_CONTRACT, [a_result()]
        )
        assert summary.written == 1
        assert summary.error_records == 0
        assert "normalize_error" not in domain_store.read_results(snapshot_id)[0]["notes"]


def a_snapshot(domain_store: DomainStore, source_id: str) -> dict[str, Any]:
    """Seal, then read back. `read_snapshot` returns `None` for a snapshot that does not
    exist, and every caller here has just created one — so the assertion is the narrowing."""
    row = domain_store.read_snapshot(domain_store.seal_snapshot_from_raw(source_id))
    assert row is not None
    return row


def _an_envelope(domain_store: DomainStore, job_connection: psycopg.Connection[Any]) -> Any:
    """A job, an attempt, and an envelope to hang items from. Raw needs all three."""
    job_id = uuid4()
    job_connection.execute(
        "insert into cosmai.job (id, handler, payload, state, attempt_count, max_attempts, "
        "available_at, correlation_id) values (%s, 'x', %s, 'PENDING', 0, 1, now(), 'c')",
        (job_id, json.dumps({})),
    )
    attempt_id = uuid4()
    job_connection.execute(
        "insert into cosmai.job_attempt (id, job_id, attempt_no, worker_id, correlation_id) "
        "values (%s, %s, (select coalesce(max(attempt_no), 0) + 1 from cosmai.job_attempt "
        "where job_id = %s), 'w', 'c')",
        (attempt_id, job_id, job_id),
    )
    return domain_store.record_envelope(
        SOURCE_ID, job_id, attempt_id, "collector.probe", "0.1.0",
        body=b"{}", endpoint_ref="items",
    )
