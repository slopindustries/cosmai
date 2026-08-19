"""The domain tables, and the atomicity that is B0.2's whole point.

The last class here is the reason this file exists. Everything before it checks that
a table holds what DP-008 D5 says it holds; ``TestCollectionIsAtomic`` checks the
thing the P0-A Completion Gate recorded as its **first** limitation — every
duplicate-suppression result there rests on one row with a primary-key conflict, and
a durable effect spanning several statements was untested. A collection is such an
effect: an envelope, its items, a cursor, and the completion that closes the attempt.

Divergence has two shapes and both are silent. A cursor that moved without its Raw
loses records with nothing to notice it by. Raw without its cursor collects the same
records again, forever.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from domain import DomainStore, RawItemRow, SnapshotMember, SourceRow, digest_of
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("database")

ADDON_ID = "collector.demo"
ADDON_VERSION = "0.1.0"


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    """A domain store on the same connection the job store uses.

    One connection is not incidental: the atomicity tests below need the domain
    writes and the fenced completion to be inside one transaction, which they cannot
    be if each store holds its own connection.
    """
    return DomainStore(connection)


def a_source(source_id: str = "demo", **overrides: Any) -> SourceRow:
    values: dict[str, Any] = {
        "source_id": source_id,
        "addon_id": ADDON_ID,
        "addon_version": ADDON_VERSION,
        "kind": "collector",
        "config": {"base_path": "/v1/items"},
        "config_schema_version": "1",
        "credential_ref": f"COSMA_SRC_{source_id.upper()}_TOKEN",
        "outbound_profile": {"hosts": ["api.example.com"]},
    }
    values.update(overrides)
    return SourceRow(**values)


def claim_one(store: JobStore, handler: str = "addon:collector.demo") -> tuple[UUID, UUID]:
    """Create and claim one job, returning ``(job_id, attempt_id)``."""
    job_id = store.create_job(handler, {"source_id": "demo"}, max_attempts=3)
    claimed = store.claim_next("worker-1", lease_seconds=60)
    assert claimed is not None
    assert claimed.job_id == job_id
    return claimed.job_id, claimed.attempt_id


class TestSourceRegistry:
    def test_a_registered_source_reads_back_as_it_was_written(self, domain: DomainStore) -> None:
        domain.register_source(a_source())
        row = domain.read_source("demo")
        assert row is not None
        assert row["addon_id"] == ADDON_ID
        assert row["kind"] == "collector"
        assert row["config"] == {"base_path": "/v1/items"}
        assert row["credential_ref"] == "COSMA_SRC_DEMO_TOKEN"
        assert row["enabled"] is True

    def test_an_unregistered_source_reads_as_absent_rather_than_raising(
        self, domain: DomainStore
    ) -> None:
        assert domain.read_source("never-registered") is None

    def test_a_credential_value_cannot_be_stored_where_a_key_name_belongs(
        self, domain: DomainStore
    ) -> None:
        """DP-008 D6, enforced by the database rather than by whoever writes the row.

        `secret-setup.md` says `credential_ref` is exactly a key name and gives the
        naming convention. A real token pasted here does not match it, so the mistake
        the invariant is about is refused rather than merely forbidden in prose.
        """
        with pytest.raises(psycopg.errors.CheckViolation, match="credential_ref_is_a_key_name"):
            domain.register_source(a_source(credential_ref="sk-live-abc123XYZ"))

    def test_the_key_name_check_is_a_shape_check_and_says_so(
        self, domain: DomainStore
    ) -> None:
        """The positive control, and the limit of what the constraint claims.

        A value shaped like a key name passes. That is the honest boundary: this is a
        shape check that makes one mistake structurally hard, not a secrecy
        mechanism. Asserting it keeps the constraint from being read as more than it
        is.
        """
        domain.register_source(a_source(credential_ref="COSMA_SRC_DEMO_TOKEN"))
        row = domain.read_source("demo")
        assert row is not None and row["credential_ref"] == "COSMA_SRC_DEMO_TOKEN"

    def test_a_source_may_have_no_credential_at_all(self, domain: DomainStore) -> None:
        domain.register_source(a_source(credential_ref=None))
        row = domain.read_source("demo")
        assert row is not None and row["credential_ref"] is None

    def test_a_normalizer_source_cannot_be_granted_a_credential(
        self, domain: DomainStore
    ) -> None:
        """DP-008 D4's asymmetry at the moment a *grant* could break it.

        `addon_api` already refuses a normalizer that **declares** a credential. This
        refuses a normalizer source that was **granted** one. Same rule, two
        different moments, and neither implies the other.
        """
        with pytest.raises(psycopg.errors.CheckViolation, match="reaches_nothing_outside"):
            domain.register_source(
                a_source(kind="normalizer", outbound_profile=None,
                         credential_ref="COSMA_SRC_DEMO_TOKEN")
            )

    def test_a_normalizer_source_cannot_be_granted_an_outbound_profile(
        self, domain: DomainStore
    ) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="reaches_nothing_outside"):
            domain.register_source(
                a_source(kind="normalizer", credential_ref=None,
                         outbound_profile={"hosts": ["api.example.com"]})
            )

    def test_a_normalizer_source_with_neither_is_accepted(self, domain: DomainStore) -> None:
        """The positive control for the two refusals above."""
        domain.register_source(
            a_source(kind="normalizer", credential_ref=None, outbound_profile=None)
        )
        row = domain.read_source("demo")
        assert row is not None and row["kind"] == "normalizer"

    def test_an_unknown_kind_is_refused(self, domain: DomainStore) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="kind_is_known"):
            domain.register_source(a_source(kind="scraper"))

    def test_an_unknown_data_class_is_refused(self, domain: DomainStore) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="data_class_is_known"):
            domain.register_source(a_source(data_class="secret"))


class TestOnlyAnImporterReadsALocalInput:
    """DP-024 D6 as SQL. Each kind has exactly one input surface, held where the
    capability layer cannot be the only thing holding it."""

    def test_an_importer_may_hold_an_input_profile(self, domain: DomainStore) -> None:
        domain.register_source(
            SourceRow(
                source_id="dataset-import",
                addon_id="importer.probe",
                addon_version="0.1.0",
                kind="importer",
                config_schema_version="1",
                input_profile={"root": "/tmp/approved", "inputs": {"rows": "a.jsonl"}},
            )
        )

        stored = domain.read_source("dataset-import")
        assert stored is not None
        assert stored["input_profile"] == {"root": "/tmp/approved", "inputs": {"rows": "a.jsonl"}}

    def test_a_collector_may_not_hold_one(self, domain: DomainStore) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="only_an_importer_reads"):
            domain.register_source(
                SourceRow(
                    source_id="collector-with-a-file",
                    addon_id="collector.probe",
                    addon_version="0.1.0",
                    kind="collector",
                    config_schema_version="1",
                    input_profile={"root": "/tmp/approved", "inputs": {}},
                )
            )

    def test_a_normalizer_may_not_hold_one(self, domain: DomainStore) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="only_an_importer_reads"):
            domain.register_source(
                SourceRow(
                    source_id="normalizer-with-a-file",
                    addon_id="normalizer.probe",
                    addon_version="0.1.0",
                    kind="normalizer",
                    config_schema_version="1",
                    input_profile={"root": "/tmp/approved", "inputs": {}},
                )
            )

    def test_an_importer_may_not_be_granted_an_outbound_profile(self, domain: DomainStore) -> None:
        with pytest.raises(psycopg.errors.CheckViolation, match="granted_no_outbound_profile"):
            domain.register_source(
                SourceRow(
                    source_id="importer-that-fetches",
                    addon_id="importer.probe",
                    addon_version="0.1.0",
                    kind="importer",
                    config_schema_version="1",
                    outbound_profile={"hosts": ["api.example.com"], "endpoints": {}},
                )
            )

    def test_an_importer_may_still_need_a_credential(self, domain: DomainStore) -> None:
        """`addon_api.manifest` says `needs_credential` stays legal for an importer,
        because the platform may need one to open a protected input. A constraint
        forbidding it would contradict the contract rather than enforce it."""
        domain.register_source(
            SourceRow(
                source_id="protected-dataset",
                addon_id="importer.probe",
                addon_version="0.1.0",
                kind="importer",
                config_schema_version="1",
                credential_ref="COSMA_SRC_PROTECTED_DATASET_KEY",
                input_profile={"root": "/tmp/approved", "inputs": {"rows": "a.jsonl"}},
            )
        )

        assert domain.read_source("protected-dataset") is not None


class TestCursor:
    def test_a_source_with_no_cursor_reads_as_none(self, domain: DomainStore) -> None:
        domain.register_source(a_source())
        assert domain.read_cursor("demo") is None

    def test_a_cursor_is_stored_opaquely_and_returned_unchanged(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        """The platform does not interpret a cursor, so it must survive untouched."""
        domain.register_source(a_source())
        _, attempt_id = claim_one(store)
        awkward = {"next": None, "page": 3, "seen": ["a", "b"], "nested": {"deep": True}}
        domain.advance_cursor("demo", awkward, attempt_id)
        assert domain.read_cursor("demo") == awkward

    def test_advancing_twice_replaces_rather_than_accumulates(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        domain.register_source(a_source())
        _, attempt_id = claim_one(store)
        domain.advance_cursor("demo", {"page": 1}, attempt_id)
        domain.advance_cursor("demo", {"page": 2}, attempt_id)
        assert domain.read_cursor("demo") == {"page": 2}

    def test_streams_of_one_source_do_not_share_a_position(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        domain.register_source(a_source())
        _, attempt_id = claim_one(store)
        domain.advance_cursor("demo", {"page": 1}, attempt_id, stream="items")
        domain.advance_cursor("demo", {"page": 9}, attempt_id, stream="reviews")
        assert domain.read_cursor("demo", stream="items") == {"page": 1}
        assert domain.read_cursor("demo", stream="reviews") == {"page": 9}

    def test_a_cursor_records_which_attempt_moved_it(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The audit half of atomicity: a cursor is traceable to its Raw."""
        domain.register_source(a_source())
        _, attempt_id = claim_one(store)
        domain.advance_cursor("demo", {"page": 1}, attempt_id)
        row = connection.execute(
            "select updated_by_attempt from source_cursor where source_id = 'demo'"
        ).fetchone()
        assert row is not None and row[0] == attempt_id

    def test_a_cursor_cannot_name_an_attempt_that_does_not_exist(
        self, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            domain.advance_cursor("demo", {"page": 1}, uuid4())


class TestRaw:
    def test_an_envelope_records_its_digest_and_provenance(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        body = b'{"data": [1, 2]}'
        envelope_id = domain.record_envelope(
            "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
            body=body, content_type="application/json", endpoint_ref="items",
        )
        row = connection.execute(
            "select body, body_sha256, addon_id, addon_version, endpoint_ref, input_ref "
            "from raw_envelope where id = %s",
            (envelope_id,),
        ).fetchone()
        assert row is not None
        assert bytes(row[0]) == body
        assert row[1] == digest_of(body)
        assert (row[2], row[3]) == (ADDON_ID, ADDON_VERSION)
        assert (row[4], row[5]) == ("items", None)

    def test_a_payload_that_is_not_utf8_survives_unchanged(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """Lossless means bytes, not text. A source is not obliged to send valid UTF-8."""
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        body = b"\x00\x01\xfe\xff binary"
        envelope_id = domain.record_envelope(
            "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION, body=body, endpoint_ref="items"
        )
        row = connection.execute(
            "select body from raw_envelope where id = %s", (envelope_id,)
        ).fetchone()
        assert row is not None and bytes(row[0]) == body

    def test_an_envelope_naming_both_an_endpoint_and_an_input_is_refused(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        """Provenance that named both origins would be ambiguous about its own source."""
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        with pytest.raises(psycopg.errors.CheckViolation, match="names_one_origin"):
            domain.record_envelope(
                "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
                body=b"{}", endpoint_ref="items", input_ref="/data/file.csv",
            )

    def test_an_envelope_naming_neither_origin_is_refused(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        """An envelope that named no origin could not be traced to a request at all."""
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        with pytest.raises(psycopg.errors.CheckViolation, match="names_one_origin"):
            domain.record_envelope(
                "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION, body=b"{}"
            )

    def test_an_importer_envelope_names_its_input_instead(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The positive control for the two refusals above: one origin is accepted."""
        domain.register_source(a_source(kind="importer", outbound_profile=None))
        job_id, attempt_id = claim_one(store)
        envelope_id = domain.record_envelope(
            "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
            body=b"col\n1\n", input_ref="fixture:rows.csv", content_type="text/csv",
        )
        row = connection.execute(
            "select endpoint_ref, input_ref from raw_envelope where id = %s", (envelope_id,)
        ).fetchone()
        assert row is not None and (row[0], row[1]) == (None, "fixture:rows.csv")

    def test_items_may_repeat_a_key_because_duplicate_policy_is_still_open(
        self, domain: DomainStore, store: JobStore
    ) -> None:
        """Not an oversight. A unique index here would answer an open contract question.

        What duplicate and changed-content policy `item_key` feeds is P0-B contract
        work that has not happened. Enforcing uniqueness now would decide it silently,
        so this records the current permissiveness as deliberate.
        """
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        envelope_id = domain.record_envelope(
            "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION, body=b"{}", endpoint_ref="items"
        )
        identifiers = domain.record_items(
            envelope_id, "demo",
            [RawItemRow("same", b"first", "application/json"),
             RawItemRow("same", b"second", "application/json")],
        )
        assert len(set(identifiers)) == 2
        assert domain.count_items("demo") == 2


class TestSnapshot:
    def test_a_sealed_snapshot_reads_back_in_the_order_it_fixed(
        self, domain: DomainStore
    ) -> None:
        domain.register_source(a_source())
        members = [
            SnapshotMember(0, "b", b"second", "application/json"),
            SnapshotMember(1, "a", b"first", "application/json"),
        ]
        snapshot_id = domain.seal_snapshot("demo", members)
        read = domain.read_snapshot_items(snapshot_id)
        assert [item["item_key"] for item in read] == ["b", "a"]

    def test_a_sealed_snapshot_verifies(self, domain: DomainStore) -> None:
        domain.register_source(a_source())
        snapshot_id = domain.seal_snapshot(
            "demo", [SnapshotMember(0, "a", b"payload", "application/json")]
        )
        assert domain.snapshot_tampering(snapshot_id) == ()

    def test_an_altered_payload_is_detected(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        """Tamper detection, which is the whole reason the digests are stored."""
        domain.register_source(a_source())
        snapshot_id = domain.seal_snapshot(
            "demo", [SnapshotMember(0, "a", b"payload", "application/json")]
        )
        connection.execute(
            "update snapshot_item set payload = %s where snapshot_id = %s",
            (b"tampered", snapshot_id),
        )
        problems = domain.snapshot_tampering(snapshot_id)
        assert any("no longer matches its digest" in problem for problem in problems)
        assert any("manifest digest differs" in problem for problem in problems)

    def test_a_removed_member_is_detected(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        domain.register_source(a_source())
        snapshot_id = domain.seal_snapshot(
            "demo",
            [SnapshotMember(0, "a", b"one", "application/json"),
             SnapshotMember(1, "b", b"two", "application/json")],
        )
        connection.execute(
            "delete from snapshot_item where snapshot_id = %s and ordinal = 1", (snapshot_id,)
        )
        problems = domain.snapshot_tampering(snapshot_id)
        assert any("2 members but 1" in problem for problem in problems)

    def test_a_snapshot_cannot_hold_one_key_twice(self, domain: DomainStore) -> None:
        """Unlike `raw_item`, this one *is* unique, and for a stated reason.

        A normalizer must produce byte-identical output from one snapshot (OQ-003).
        Two members with one key would make its output depend on which was read last.
        """
        domain.register_source(a_source())
        with pytest.raises(psycopg.errors.UniqueViolation, match="one_per_key"):
            domain.seal_snapshot(
                "demo",
                [SnapshotMember(0, "same", b"one", "application/json"),
                 SnapshotMember(1, "same", b"two", "application/json")],
            )

    def test_verification_of_a_snapshot_that_does_not_exist_says_so(
        self, domain: DomainStore
    ) -> None:
        missing = uuid4()
        assert domain.snapshot_tampering(missing) == (f"snapshot {missing} does not exist",)


class TestCollectionIsAtomic:
    """The P0-A gate's first recorded limitation, exercised for real.

    The gate's own words: every duplicate-suppression result there rests on one row
    with a primary-key conflict, and a durable effect spanning several statements is
    untested. A collection is four statements — an envelope, its items, a cursor, and
    the fenced completion — and the two ways they can diverge are both silent.

    These tests drive `JobStore` directly rather than through an add-on. The add-on
    layer is not what makes this correct; the transaction boundary is, and testing it
    without the add-on means a later add-on bug cannot be mistaken for this working.
    """

    def collect(
        self,
        domain: DomainStore,
        store: JobStore,
        connection: psycopg.Connection[Any],
        cursor_value: Any,
        fail_after_writes: bool = False,
    ) -> bool:
        """One collection, in one transaction, completion last.

        Returns whether it committed. This is the pattern `domain.store`'s docstring
        specifies and the one B0.3's capability layer must use.
        """
        job_id, attempt_id = claim_one(store)
        try:
            with connection.transaction():
                envelope_id = domain.record_envelope(
                    "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
                    body=b'{"data": [1]}', endpoint_ref="items",
                )
                domain.record_items(
                    envelope_id, "demo", [RawItemRow("item-1", b"1", "application/json")]
                )
                domain.advance_cursor("demo", cursor_value, attempt_id)
                if fail_after_writes:
                    raise RuntimeError("interrupted after the writes, before completion")
                completion = store.complete_success(job_id, attempt_id, "worker-1")
                assert completion, "the fence refused a completion this test expected to pass"
        except RuntimeError:
            return False
        return True

    def test_a_committed_collection_leaves_raw_and_cursor_agreeing(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        domain.register_source(a_source())
        assert self.collect(domain, store, connection, {"page": 1}) is True

        assert domain.count_items("demo") == 1
        assert domain.read_cursor("demo") == {"page": 1}
        row = connection.execute("select state from job").fetchone()
        assert row is not None and row[0] == JobState.SUCCEEDED.value

    def test_an_interruption_before_completion_leaves_no_raw_and_no_cursor(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """Neither half of the divergence. This is the test the gate's limitation asks for.

        Raw without a cursor would collect the same records again. A cursor without Raw
        would skip them forever. One transaction makes both impossible, and the job
        stays claimable so the work is not lost either.
        """
        domain.register_source(a_source())
        assert self.collect(domain, store, connection, {"page": 1}, fail_after_writes=True) is False

        assert domain.count_items("demo") == 0
        assert domain.read_cursor("demo") is None
        row = connection.execute("select count(*) from raw_envelope").fetchone()
        assert row is not None and row[0] == 0

        # The claim is **not** rolled back, and that is correct rather than a leak:
        # `claim_next` committed before this transaction opened, so the job is still
        # RUNNING with an open attempt. Recovery is the platform's existing
        # lease-expiry path (`LEASE_ABANDONED`), which P0-A tested. What one
        # transaction buys is not an undone claim but an undone *effect*.
        state = connection.execute("select state from job").fetchone()
        assert state is not None and state[0] == JobState.RUNNING.value
        open_attempts = connection.execute(
            "select count(*) from job_attempt where finished_at is null"
        ).fetchone()
        assert open_attempts is not None and open_attempts[0] == 1

    def test_the_interruption_test_is_not_passing_because_nothing_was_written(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The positive control for the test above.

        Its assertions are all absences, so it would pass just as well against a store
        that never wrote anything. This proves the same code path does write when it is
        allowed to reach the end.
        """
        domain.register_source(a_source())
        assert self.collect(domain, store, connection, {"page": 1}) is True
        assert domain.count_items("demo") == 1
        assert domain.read_cursor("demo") is not None

    def test_a_worker_that_lost_its_lease_persists_neither_raw_nor_cursor(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """Why the fenced completion goes last rather than first.

        A worker whose lease expired has had its work given to someone else. If it
        completed first and wrote Raw afterwards, or wrote Raw in a transaction of its
        own, the same records would land twice. Here the fence refuses, the refusal
        raises, and the writes go with it.
        """
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)

        # A different worker now owns the job: this is what an expired lease and a
        # reclaim leave behind, without waiting for a real expiry.
        connection.execute(
            "update job set lease_owner = 'worker-2' where id = %s", (job_id,)
        )

        class LeaseLost(RuntimeError):
            pass

        with pytest.raises(LeaseLost), connection.transaction():
            envelope_id = domain.record_envelope(
                "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
                body=b'{"data": [1]}', endpoint_ref="items",
            )
            domain.record_items(
                envelope_id, "demo", [RawItemRow("item-1", b"1", "application/json")]
            )
            domain.advance_cursor("demo", {"page": 1}, attempt_id)
            completion = store.complete_success(job_id, attempt_id, "worker-1")
            if not completion:
                raise LeaseLost("the fence refused: this worker no longer owns the lease")

        assert domain.count_items("demo") == 0
        assert domain.read_cursor("demo") is None

    def test_the_fence_accepts_the_same_sequence_when_the_lease_is_still_held(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The positive control for the lease test: the only difference is the owner."""
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        with connection.transaction():
            envelope_id = domain.record_envelope(
                "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
                body=b'{"data": [1]}', endpoint_ref="items",
            )
            domain.record_items(
                envelope_id, "demo", [RawItemRow("item-1", b"1", "application/json")]
            )
            domain.advance_cursor("demo", {"page": 1}, attempt_id)
            assert store.complete_success(job_id, attempt_id, "worker-1")

        assert domain.count_items("demo") == 1
        assert domain.read_cursor("demo") == {"page": 1}

    def test_a_second_collection_advances_the_cursor_without_losing_earlier_raw(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """Raw accumulates, the cursor moves. `project-state.md` §4: Raw is append-only."""
        domain.register_source(a_source())
        assert self.collect(domain, store, connection, {"page": 1}) is True
        assert self.collect(domain, store, connection, {"page": 2}) is True

        assert domain.count_items("demo") == 2
        assert domain.read_cursor("demo") == {"page": 2}


class TestTheShapeChecksTheDatabaseHolds:
    """`[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` M3 measured seven database CHECKs
    as **GREEN**: every one could be deleted and nothing noticed.

    They are cheap to write and load-bearing in a specific way — they are the last place a
    malformed digest or a negative count can be stopped, after every application path has
    already agreed to write it. Each case below writes a **valid** row through the ordinary
    path and then updates one column past the constraint, so what is under test is the
    constraint rather than the writer that happens to precede it.
    """

    def _envelope(self, domain: DomainStore, store: JobStore) -> UUID:
        domain.register_source(a_source())
        job_id, attempt_id = claim_one(store)
        return domain.record_envelope(
            "demo", job_id, attempt_id, ADDON_ID, ADDON_VERSION,
            body=b"{}", endpoint_ref="items",
        )

    def test_a_raw_envelope_digest_must_look_like_a_sha256(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        envelope_id = self._envelope(domain, store)

        with pytest.raises(psycopg.errors.CheckViolation, match="raw_envelope_digest_is_a_sha256"):
            connection.execute(
                "update raw_envelope set body_sha256 = %s where id = %s",
                ("not-a-digest", envelope_id),
            )

    def test_an_uppercase_digest_is_refused_too(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The pattern is lowercase hex on purpose: two spellings of one digest would make
        equality comparisons depend on who wrote the row."""
        envelope_id = self._envelope(domain, store)

        with pytest.raises(psycopg.errors.CheckViolation, match="raw_envelope_digest_is_a_sha256"):
            connection.execute(
                "update raw_envelope set body_sha256 = %s where id = %s",
                ("A" * 64, envelope_id),
            )

    def test_a_valid_digest_still_updates(
        self, domain: DomainStore, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The control. A constraint that refused every update would pass both cases above."""
        envelope_id = self._envelope(domain, store)

        connection.execute(
            "update raw_envelope set body_sha256 = %s where id = %s", ("a" * 64, envelope_id)
        )

    def _snapshot(self, domain: DomainStore) -> UUID:
        domain.register_source(a_source())
        return domain.seal_snapshot(
            "demo", [SnapshotMember(0, "a", b"first", "application/json")]
        )

    def test_a_snapshot_manifest_digest_must_look_like_a_sha256(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        snapshot_id = self._snapshot(domain)

        with pytest.raises(
            psycopg.errors.CheckViolation, match="snapshot_manifest_digest_is_a_sha256"
        ):
            connection.execute(
                "update snapshot set manifest_sha256 = %s where id = %s", ("nope", snapshot_id)
            )

    def test_a_snapshot_item_count_cannot_be_negative(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        snapshot_id = self._snapshot(domain)

        with pytest.raises(
            psycopg.errors.CheckViolation, match="snapshot_item_count_is_not_negative"
        ):
            connection.execute(
                "update snapshot set item_count = -1 where id = %s", (snapshot_id,)
            )

    def test_a_snapshot_item_digest_must_look_like_a_sha256(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        snapshot_id = self._snapshot(domain)

        with pytest.raises(
            psycopg.errors.CheckViolation, match="snapshot_item_digest_is_a_sha256"
        ):
            connection.execute(
                "update snapshot_item set payload_sha256 = %s where snapshot_id = %s",
                ("nope", snapshot_id),
            )

    def test_a_snapshot_item_ordinal_is_zero_based(
        self, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        """The ordinal is the replay order. A negative one would sort before the first
        member and change what a snapshot replays."""
        snapshot_id = self._snapshot(domain)

        with pytest.raises(
            psycopg.errors.CheckViolation, match="snapshot_item_ordinal_is_zero_based"
        ):
            connection.execute(
                "update snapshot_item set ordinal = -1 where snapshot_id = %s", (snapshot_id,)
            )

    def test_an_attempt_number_is_one_based(
        self, store: JobStore, connection: psycopg.Connection[Any]
    ) -> None:
        """`job_attempt.attempt_no` is how a retry is distinguished from a first try, and
        `0` would make the first attempt indistinguishable from "none yet"."""
        _, attempt_id = claim_one(store)

        with pytest.raises(
            psycopg.errors.CheckViolation, match="job_attempt_number_is_one_based"
        ):
            connection.execute(
                "update job_attempt set attempt_no = 0 where id = %s", (attempt_id,)
            )
