"""A Raw store evolves after a snapshot is sealed. Does the snapshot still replay — and
would a snapshot built the other way have?

The P0 Charter's fifth Architecture Question asks whether the sealed snapshot protects
reproducibility from Raw-store evolution. ``docs/project-state.md`` §5 states the hypothesis
as *"sufficient for replay despite later Raw-store **changes or** migration"* — two things,
and only one of them is a migration.

**This file was rewritten because its first version measured only the migration, and could
not tell the two designs apart.** ``ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md`` F2: the
attacker replaced ``domain.store.READ_SNAPSHOT_ITEMS`` with a read-time re-query of
``raw_item`` — and every test of the surviving class passed anyway.
``addon_api.results.SnapshotItem`` carries exactly ``item_key``, ``payload`` and
``content_type``, so a column **added** to ``raw_item`` cannot reach a normalizer under
either design. The scenario was green for a reason weaker than the one it claimed.

So the alternative is no longer something an attacker installs by hand. ``queried_reader``
is that design — DP-019 D5's selection re-run against ``raw_item`` at read time, projected
to the three fields the contract defines — and it is a drop-in for
``DomainStore.read_snapshot_items``, so the two are read side by side on every run.

**``queried_reader`` is the re-query design, and it is not OQ-004's first alternative.**
`[확인 사실]` An earlier revision of this docstring attached OQ-004's *"preserve only
references to append-only Raw observations"* to it, which is wrong: this reader preserves no
references at all, it re-runs a selection. `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md`
F-B is the correction, and it did the work rather than only naming the error — it
implemented the reference design (ordinals and ``raw_item.id`` fixed at seal, bytes fetched
at read) and drove it over this same timeline. `[측정]` **It agrees with the sealed design
at the seal, after the migration, and after the later collection.** Only the purge separates
them.

`[추론]` So step 3 below is a real property of the re-query design and **not** the general
claim that a snapshot beats every alternative. Against OQ-004's reference design the
discriminating case is the purge alone. Read step 3 as scoped to the design named beside it.

**The timeline, and what each step is for.** One fixture, four moments:

1. *at the seal* — both designs read. They must agree, or nothing below means anything:
   this is the positive control for the alternative implementation itself.
2. *after the migration* — ``0005`` adds a column and rewrites every ``raw_item`` row.
   Both designs still agree. **That is F2, kept as a measurement** rather than as a
   sentence in a review: an additive migration does not discriminate, and a green run over
   one is not evidence for sealing.
3. *after later Raw observations* — a third collection supersedes a key the snapshot named
   and adds one it did not. OQ-004's own minimum experiment asks for exactly this: *"add
   later Raw observations and simulate a changed Raw-store projection; replay only from the
   snapshot"*. The queried design now replays different bytes under the same key. The
   sealed one does not move.
4. *after the Raw rows are purged* — DP-005's ``DELETE_AFTER_EVIDENCE_CAPTURE`` disposition,
   which ``0002_domain.sql`` names as the reason it declined a DELETE trigger on Raw. The
   queried design replays nothing at all.

Steps 3 and 4 are what makes this experiment discriminate. Step 2 is what proves it needed
to.

**Both halves of the hypothesis are still asserted at every step**, because either alone is
weaker than the claim: the manifest verifies, *and* the bytes a normalizer would read are
the bytes that were sealed, member for member, in the order the snapshot fixed.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from domain import DomainStore, RawItemRow, SourceRow, digest_of
from domain.migrate import MIGRATIONS_DIRECTORY as DOMAIN_MIGRATIONS
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.db.migrate import apply_migrations
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from psycopg.rows import dict_row

#: The Raw-store *migration* under test. Named once, because three things have to agree
#: about it: what the fixture withholds before sealing, what it applies afterwards, and
#: what the idempotency guard at the bottom re-executes on purpose.
MIGRATION_UNDER_TEST = "0005_raw_item_payload_digest"

SOURCE_ID = "demo"
ADDON_ID = "collector.demo"
ADDON_VERSION = "0.1.0"

#: Deliberately not all ASCII and not all valid UTF-8. "Byte-identical" over three
#: printable JSON documents would also hold for a store that round-tripped through `str`,
#: which is the mistake `test_a_payload_that_is_not_utf8_survives_unchanged` already exists
#: to catch one layer down.
FIRST_COLLECTION = (
    RawItemRow("item-001", '{"title": "제주 여행"}'.encode(), "application/json"),
    RawItemRow("item-002", b"\xff\xfe\x00 not utf-8 at all", "application/octet-stream"),
    RawItemRow("item-003", '{"title": "부산 맛집"}'.encode(), "application/json"),
)

#: One key collected a second time, so DP-019 D5's "a duplicate key collapses to the
#: latest" is inside what gets sealed rather than a rule the scenario steps around.
SECOND_COLLECTION = (
    RawItemRow("item-002", b"\x00\x01\x02 the second reading", "application/octet-stream"),
)

#: The evolution that discriminates, and the least dramatic form of it: the collector runs
#: again *after* the snapshot was sealed. One key the snapshot named is superseded and one
#: key it never saw arrives. Nothing here is a migration and nothing is a mistake — it is
#: the ordinary operation of a source, which is why it is the case a snapshot has to
#: survive. OQ-004's minimum experiment asks for it by name.
LATER_COLLECTION = (
    RawItemRow("item-002", b"\x00\x01\x02 the third reading", "application/octet-stream"),
    RawItemRow("item-004", '{"title": "강릉 카페"}'.encode(), "application/json"),
)

#: What sealing the first two collections must produce, by DP-019 D5: every `raw_item` of
#: one source, ordered by `item_key`, latest row per key. Written out rather than derived,
#: so that an equality between two reads of the same empty list cannot pass for evidence.
SEALED_MEMBERS = (
    (0, "item-001", '{"title": "제주 여행"}'.encode(), "application/json"),
    (1, "item-002", b"\x00\x01\x02 the second reading", "application/octet-stream"),
    (2, "item-003", '{"title": "부산 맛집"}'.encode(), "application/json"),
)

#: What a **queried** snapshot would hand the normalizer once the later collection has
#: landed. Written out for the same reason `SEALED_MEMBERS` is: "the two designs differ" is
#: a claim about *what* the other one replays, and a bare `!=` would not say it. Member 1
#: is the same `item_key` carrying different bytes — the failure mode that would not
#: announce itself — and member 3 is an item the sealed snapshot never selected.
QUERIED_AFTER_LATER_OBSERVATIONS = (
    (0, "item-001", '{"title": "제주 여행"}'.encode(), "application/json"),
    (1, "item-002", b"\x00\x01\x02 the third reading", "application/octet-stream"),
    (2, "item-003", '{"title": "부산 맛집"}'.encode(), "application/json"),
    (3, "item-004", '{"title": "강릉 카페"}'.encode(), "application/json"),
)

#: The alternative design, as a drop-in for `DomainStore.read_snapshot_items`: DP-019 D5's
#: selection re-run against `raw_item` when the normalizer reads, projected to exactly the
#: fields `SnapshotItem` carries. `0003_normalized_result.sql` names this design as the one
#: materializing was chosen over — "reproducibility is the whole reason a snapshot is
#: materialized rather than queried" — and OQ-004 lists it as an alternative, so it is the
#: repository's own and not a straw one.
#:
#: Copied from `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md` mutant M4, which is the mutant
#: this file now has to kill.
QUERIED_SNAPSHOT_ITEMS = """
select row_number() over (order by latest.item_key) - 1 as ordinal,
       latest.item_key, latest.payload, latest.content_type,
       encode(sha256(latest.payload), 'hex') as payload_sha256
from (
    select distinct on (item_key) item_key, payload, content_type, emitted_at, id
    from raw_item
    where source_id = (select source_id from snapshot where id = %(snapshot_id)s)
    order by item_key, emitted_at desc, id desc
) latest
order by latest.item_key
"""

#: The same selection handed on as the whole row. **No design here reads this** — it is a
#: strictly wider projection than the contract defines, and it exists only to show *why*
#: the migration cannot discriminate: the added column is plainly there in the row, and
#: plainly invisible through the three fields a normalizer receives. An earlier revision of
#: this file offered a difference measured this way as evidence that the designs differ,
#: which is the mistake the attack report's F2 named.
WHOLE_RAW_ROW = """
select to_jsonb(latest) as row
from (
    select distinct on (item_key) *
    from raw_item
    where source_id = %(source_id)s
    order by item_key, emitted_at desc, id desc
) latest
order by latest.item_key
"""

DESCRIBE_RAW_ITEM = """
select column_name, data_type, is_nullable, is_generated, generation_expression
from information_schema.columns
where table_schema = 'public' and table_name = 'raw_item'
"""

#: What a table rewrite moves. `information_schema` cannot see it — a `stored` and a
#: `virtual` generated column describe identically there — so the rewrite claim is read
#: from `pg_class` or it is not read at all.
RAW_ITEM_FILENODE = "select relfilenode from pg_class where relname = 'raw_item'"

#: `'s'` stored, `'v'` virtual, `''` not generated. PostgreSQL 18 makes `VIRTUAL` the
#: default when `generated always as (…)` names neither, so this is a live distinction.
DIGEST_COLUMN_KIND = """
select attgenerated from pg_attribute
where attrelid = 'raw_item'::regclass and attname = 'payload_sha256'
"""

#: One design's answer to "what does this normalizer read?", as `DomainStore` shapes it.
SnapshotReader = Callable[[UUID], list[dict[str, Any]]]


@dataclass(frozen=True)
class Replayed:
    """One member as a normalizer receives it.

    ``addon_host.capabilities._NormalizeRun.execute`` builds a ``SnapshotItem`` per row of
    a reader — key, payload bytes, content type, in ordinal order — and hands the sequence
    to the add-on. This is that projection, plus the digest the member carries, because a
    replay that matched the bytes while contradicting its own digest would be reproducible
    and untrustworthy at the same time.
    """

    ordinal: int
    item_key: str
    payload: bytes
    content_type: str
    payload_sha256: str


@dataclass(frozen=True)
class Reading:
    """What each of the two designs replays at one moment on the timeline."""

    sealed: tuple[Replayed, ...]
    queried: tuple[Replayed, ...]


@dataclass(frozen=True)
class Evolution:
    """One sealing, three things that happen to Raw afterwards, and every reading taken."""

    handle: psycopg.Connection[Any]
    domain: DomainStore
    snapshot_id: UUID
    manifest_sha256: str

    #: Taken before the migration was applied. Every comparison afterwards is against this.
    at_seal: Reading
    after_the_migration: Reading
    after_later_observations: Reading
    after_the_purge: Reading

    #: What the applier applied *after* the snapshot existed. Must be the migration under
    #: test and nothing else: that is what makes "sealed first" a measurement.
    applied_after_sealing: tuple[str, ...]

    #: `pg_class.relfilenode` on either side of that call. A `stored` generated column
    #: rewrites the table and moves this; a `virtual` one does not move it at all.
    filenode_before: int
    filenode_after: int
    generated_kind: str

    #: The whole Raw row, on either side of the migration. Not a design — see WHOLE_RAW_ROW.
    whole_row_before: tuple[Mapping[str, Any], ...]
    whole_row_after: tuple[Mapping[str, Any], ...]

    #: Rows, non-null digests, and digests that agree with `sha256(payload)`, counted
    #: immediately after the migration — before steps 3 and 4 change what Raw holds.
    digest_agreement: tuple[int, int, int]

    #: How many `raw_item` rows the disposition purge removed.
    purged: int


def replayed(read: SnapshotReader, snapshot_id: UUID) -> tuple[Replayed, ...]:
    return tuple(
        Replayed(
            ordinal=int(row["ordinal"]),
            item_key=str(row["item_key"]),
            payload=bytes(row["payload"]),
            content_type=str(row["content_type"]),
            payload_sha256=str(row["payload_sha256"]),
        )
        for row in read(snapshot_id)
    )


def reading(sealed: SnapshotReader, queried: SnapshotReader, snapshot_id: UUID) -> Reading:
    return Reading(replayed(sealed, snapshot_id), replayed(queried, snapshot_id))


def contract_fields(members: Sequence[Replayed]) -> list[tuple[int, str, bytes, str]]:
    """The three fields ``SnapshotItem`` carries, and the ordinal that fixes their order."""
    return [(m.ordinal, m.item_key, m.payload, m.content_type) for m in members]


def queried_reader(handle: psycopg.Connection[Any]) -> SnapshotReader:
    """The design a snapshot was chosen over, as a reader with the sealed one's signature.

    The attack report installed this by editing ``domain.store.READ_SNAPSHOT_ITEMS``. Here
    the test drives it, so that "the queried design would have broken" is asserted on every
    run instead of once, by hand, by someone trying to falsify the claim.
    """

    def read(snapshot_id: UUID) -> list[dict[str, Any]]:
        with handle.cursor(row_factory=dict_row) as cursor:
            cursor.execute(QUERIED_SNAPSHOT_ITEMS, {"snapshot_id": snapshot_id})
            return list(cursor.fetchall())

    return read


def whole_rows(handle: psycopg.Connection[Any], source_id: str) -> tuple[Mapping[str, Any], ...]:
    rows = handle.execute(WHOLE_RAW_ROW, {"source_id": source_id}).fetchall()
    return tuple(dict(row[0]) for row in rows)


def filenode(handle: psycopg.Connection[Any]) -> int:
    row = handle.execute(RAW_ITEM_FILENODE).fetchone()
    assert row is not None
    return int(row[0])


def staged_without(directory: Path, excluded: str) -> Path:
    """Every domain migration but one, copied where the applier can be pointed at them.

    The test-isolation template applies the whole directory, so a snapshot sealed against a
    ``database`` fixture would already have lived through ``0005``. Withholding the file is
    the only way to seal *before* the evolution rather than after it.
    """
    staged = directory / "before-the-evolution"
    staged.mkdir()
    present = {path.stem for path in DOMAIN_MIGRATIONS.glob("*.sql")}
    assert excluded in present, f"{excluded}.sql is not in {DOMAIN_MIGRATIONS}"
    for path in sorted(DOMAIN_MIGRATIONS.glob("*.sql")):
        if path.stem != excluded:
            shutil.copy(path, staged / path.name)
    return staged


def collect(domain: DomainStore, store: JobStore, items: Sequence[RawItemRow]) -> None:
    """One collection: a claimed attempt, its envelope, and the items carved out of it."""
    store.create_job("addon:collector.demo", {"source_id": SOURCE_ID}, max_attempts=3)
    claimed = store.claim_next("worker-1", lease_seconds=60)
    assert claimed is not None
    envelope_id = domain.record_envelope(
        SOURCE_ID,
        claimed.job_id,
        claimed.attempt_id,
        ADDON_ID,
        ADDON_VERSION,
        body=b'{"items": []}',
        content_type="application/json",
        endpoint_ref="items",
    )
    domain.record_items(envelope_id, SOURCE_ID, items)
    completed = store.complete_success(claimed.job_id, claimed.attempt_id, "worker-1")
    assert completed


@pytest.fixture
def evolution(
    empty_database: PlatformConfig, logger: StructuredLogger, tmp_path: Path
) -> Iterator[Evolution]:
    """Seal, then evolve Raw three ways, reading both designs at every step."""
    staged = staged_without(tmp_path, MIGRATION_UNDER_TEST)
    with connected(empty_database, autocommit=True) as handle:
        apply_migrations(handle)
        earlier = apply_migrations(handle, directory=staged)
        assert MIGRATION_UNDER_TEST not in earlier, "the evolution was applied before sealing"

        domain = DomainStore(handle)
        store = JobStore(handle, empty_database, logger=logger)
        domain.register_source(
            SourceRow(
                source_id=SOURCE_ID,
                addon_id=ADDON_ID,
                addon_version=ADDON_VERSION,
                kind="collector",
                config={"base_path": "/v1/items"},
                outbound_profile={"hosts": ["api.example.com"]},
            )
        )
        collect(domain, store, FIRST_COLLECTION)
        collect(domain, store, SECOND_COLLECTION)
        # `emitted_at` is what DP-019 D5's "latest wins" resolves on, and both rows would
        # carry the same value if the two collections shared a transaction. They do not —
        # this connection is autocommit — but a tie would make which payload gets sealed
        # depend on a random uuid, so it is checked rather than assumed.
        assert distinct_emitted_at(handle, "item-002") == 2

        # (1) the seal, and the two readers that are compared at every step after it.
        snapshot_id = domain.seal_snapshot_from_raw(SOURCE_ID)
        sealed_read = domain.read_snapshot_items
        queried_read = queried_reader(handle)

        at_seal = reading(sealed_read, queried_read, snapshot_id)
        snapshot = domain.read_snapshot(snapshot_id)
        assert snapshot is not None
        whole_row_before = whole_rows(handle, SOURCE_ID)
        filenode_before = filenode(handle)

        # (2) the migration.
        applied = apply_migrations(handle, directory=DOMAIN_MIGRATIONS)
        after_the_migration = reading(sealed_read, queried_read, snapshot_id)
        filenode_after = filenode(handle)
        kind = handle.execute(DIGEST_COLUMN_KIND).fetchone()
        assert kind is not None
        whole_row_after = whole_rows(handle, SOURCE_ID)
        agreement = handle.execute(
            "select count(*), count(payload_sha256), "
            "count(*) filter (where payload_sha256 = encode(sha256(payload), 'hex')) "
            "from raw_item where source_id = %s",
            (SOURCE_ID,),
        ).fetchone()
        assert agreement is not None

        # (3) later Raw observations, which is what OQ-004's minimum experiment asks for.
        collect(domain, store, LATER_COLLECTION)
        assert distinct_emitted_at(handle, "item-002") == 3
        after_later_observations = reading(sealed_read, queried_read, snapshot_id)

        # (4) the disposition purge. `0002_domain.sql` declined a DELETE trigger on Raw
        # precisely so that DP-005's `DELETE_AFTER_EVIDENCE_CAPTURE` could be honoured, so
        # this is a permitted operation on this store and not an act of vandalism.
        purged = handle.execute(
            "delete from raw_item where source_id = %s", (SOURCE_ID,)
        ).rowcount
        after_the_purge = reading(sealed_read, queried_read, snapshot_id)

        yield Evolution(
            handle=handle,
            domain=domain,
            snapshot_id=snapshot_id,
            manifest_sha256=str(snapshot["manifest_sha256"]),
            at_seal=at_seal,
            after_the_migration=after_the_migration,
            after_later_observations=after_later_observations,
            after_the_purge=after_the_purge,
            applied_after_sealing=applied,
            filenode_before=filenode_before,
            filenode_after=filenode_after,
            generated_kind=str(kind[0]),
            whole_row_before=whole_row_before,
            whole_row_after=whole_row_after,
            digest_agreement=(int(agreement[0]), int(agreement[1]), int(agreement[2])),
            purged=purged,
        )


def distinct_emitted_at(handle: psycopg.Connection[Any], item_key: str) -> int:
    row = handle.execute(
        "select count(distinct emitted_at) from raw_item where item_key = %s", (item_key,)
    ).fetchone()
    assert row is not None
    return int(row[0])


class TestASealedSnapshotSurvivesRawStoreEvolution:
    """Hypothesis 4 of ``project-state.md`` §5, on the half that had no evidence."""

    def test_the_snapshot_was_sealed_before_the_evolution_was_applied(
        self, evolution: Evolution
    ) -> None:
        """The precondition the rest of this class is worthless without.

        The applier reports the versions *this call* applied. One version, and it is the
        one that changes `raw_item`, means the snapshot existed while the Raw table still
        had its old shape.
        """
        assert evolution.applied_after_sealing == (MIGRATION_UNDER_TEST,)

    def test_the_migration_rewrote_every_raw_row_that_predates_it(
        self, evolution: Evolution
    ) -> None:
        """Not cosmetic, and the rows that predate it were rewritten rather than left alone.

        A migration that only added a catalogue entry would leave the sealed snapshot alone
        for an uninteresting reason. `0005` declares the column `stored`, so PostgreSQL
        rewrites the heap and every `raw_item` row written before it is written again.

        `[측정]` **That claim used to rest on one word nothing checked.** Attack report F3:
        changing `stored` to `virtual` in the migration left all nine tests of the earlier
        revision green, because `information_schema` describes the two identically —
        `('text', 'NO', 'ALWAYS', "encode(sha256(payload), 'hex'::text)")` either way — and
        PostgreSQL 18 makes `VIRTUAL` the default when the keyword is omitted. So the
        rewrite is now read from `pg_class`, where it is visible.

        `[측정]` Run on 2026-08-20 against PostgreSQL 18.4. With the migration as shipped,
        `relfilenode` moves across the applier call — `253091` to `253202`, read by
        inverting the assertion below to `==`. With the single word `stored` changed to
        `virtual` and nothing else:

            >       assert evolution.filenode_after != evolution.filenode_before
            E       AssertionError: assert 246363 != 246363
            1 failed, 11 passed in 1.74s

        No rewrite at all, which is what the claim would have been asserting into thin air.
        """
        columns = {
            str(row[0]): (str(row[1]), str(row[2]), str(row[3]))
            for row in evolution.handle.execute(DESCRIBE_RAW_ITEM).fetchall()
        }
        assert columns["payload_sha256"] == ("text", "NO", "ALWAYS")

        assert evolution.filenode_after != evolution.filenode_before
        assert evolution.generated_kind == "s"

        # Four items were written before the column existed; four now carry a correct
        # digest. Counted in the fixture at this point on the timeline, because steps 3
        # and 4 add rows and then remove all of them.
        assert evolution.digest_agreement == (4, 4, 4)

    def test_the_sealed_snapshot_still_verifies(self, evolution: Evolution) -> None:
        """Half one, at the end of the timeline. `snapshot_tampering` returns reasons, so
        an empty tuple is "no reason"."""
        assert evolution.domain.snapshot_tampering(evolution.snapshot_id) == ()
        after = evolution.domain.read_snapshot(evolution.snapshot_id)
        assert after is not None
        assert str(after["manifest_sha256"]) == evolution.manifest_sha256
        assert int(after["item_count"]) == len(SEALED_MEMBERS)

    def test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step(
        self, evolution: Evolution
    ) -> None:
        """Half two, and the one the hypothesis is actually about.

        Verification alone is weaker: it says the snapshot is consistent with its own
        manifest, not that the manifest describes the bytes this scenario put into Raw. So
        the replay is compared against `SEALED_MEMBERS`, which was written down before the
        run, as well as against the reading taken at the seal.
        """
        steps = (
            evolution.at_seal,
            evolution.after_the_migration,
            evolution.after_later_observations,
            evolution.after_the_purge,
        )
        for step in steps:
            assert step.sealed == evolution.at_seal.sealed
            assert contract_fields(step.sealed) == list(SEALED_MEMBERS)

    def test_each_member_still_matches_the_digest_it_was_sealed_with(
        self, evolution: Evolution
    ) -> None:
        """The per-member half of verification, recomputed outside the store.

        `snapshot_tampering` recomputes each member's digest with the same `digest_of` the
        sealing used, so on its own it could agree with itself about bytes that had changed
        underneath both. Recomputing here over the **last** read of the timeline says the
        same thing from outside that method, and is what makes "verifies" and "is the
        sealed bytes" two claims rather than one restated.
        """
        for member in evolution.after_the_purge.sealed:
            assert digest_of(member.payload) == member.payload_sha256


class TestTheExperimentTellsTheTwoDesignsApart:
    """The reason this file was rewritten: the earlier one could not.

    Every test here reads the queried design as well as the sealed one. Two of them record
    an evolution that does **not** discriminate, which is not a failure of the experiment
    but the measurement that makes the other two mean something.

    `[측정]` **The control for the class, run on 2026-08-20 against PostgreSQL 18.4.** The
    attack report's acceptance test is its mutant M4 — install the queried design in the
    sealed design's place and the hypothesis class must go red, *not only* the tamper
    control. M4 edited `domain.store.READ_SNAPSHOT_ITEMS`, which this packet forbids
    touching, so it was run here in the only place a worker may: the fixture's
    `sealed_read = domain.read_snapshot_items` became `sealed_read = queried_reader(handle)`,
    which puts the same rows in front of the same assertions.

        >           assert step.sealed == evolution.at_seal.sealed
        E           assert (Replayed(ord...7d103254ea6')) == (Replayed(ord...2e30a8a3e4d'))
        E             At index 1 diff:
        E               Replayed(ordinal=1, item_key='item-002',
        E                 payload=b'\x00\x01\x02 the third reading', …
        E                 payload_sha256='ab372498…')
        E               != Replayed(ordinal=1, item_key='item-002',
        E                 payload=b'\x00\x01\x02 the second reading', …
        E                 payload_sha256='ca7fe1bf…')
        E             Left contains one more item: Replayed(ordinal=3, item_key='item-004', …
        3 failed, 9 passed in 1.72s

    The one that matters is the first:
    `TestASealedSnapshotSurvivesRawStoreEvolution::test_the_normalizer_reads_byte_for_byte_
    what_was_sealed_at_every_step`. Under the additive migration alone — the whole of the
    earlier revision — that mutant left every test of that class green.

    `[확인 사실]` The substitution is not identical to M4. `snapshot_tampering` still calls
    the real `read_snapshot_items`, so under M4 it would have failed too and here it does
    not. What is being measured is the byte-identity claim, which is the half the hypothesis
    is about; the other two failures are this class comparing the queried design against
    itself.
    """

    def test_the_queried_reader_reproduces_the_sealed_reading_before_anything_moves(
        self, evolution: Evolution
    ) -> None:
        """The positive control for the alternative implementation.

        Without this, "the queried design replays something else" could be a broken helper
        rather than a property of the design. At the seal — same Raw, no evolution yet — the
        two must be indistinguishable, ordinals and digests included.
        """
        assert evolution.at_seal.queried == evolution.at_seal.sealed
        assert contract_fields(evolution.at_seal.queried) == list(SEALED_MEMBERS)

    def test_an_added_column_does_not_tell_the_two_designs_apart(
        self, evolution: Evolution
    ) -> None:
        """Attack report F2, kept as a measurement instead of as a sentence in a review.

        `0005` really rewrites `raw_item` — the test above measures the heap moving — and it
        changes nothing a normalizer receives, under **either** design. The added column is
        plainly present in the Raw row and plainly absent from the three fields
        `SnapshotItem` carries, so an additive migration cannot discriminate, and a scenario
        green over one is not evidence that sealing is what protected it.

        `[추론]` This generalizes past one migration, and it is why the two steps below are
        changes to the rows rather than to the schema. A migration of `raw_item` can add a
        column, tighten a constraint, or rewrite the values in one — and the first two
        cannot reach a three-field projection under either design, while the third is a
        statement that rewrites Raw, which `0002_domain.sql` records this store as not
        having. What would
        discriminate is dropping or renaming `item_key`, `payload`, or `content_type`; that
        breaks `domain.store.INSERT_ITEM` and `SELECT_SNAPSHOT_MEMBERS` in the same
        statement, so it is not an evolution of the Raw store alone.

        `[측정]` **This docstring once carried a `[가설]` that no schema migration this
        repository can legitimately apply tells the two designs apart, and it was falsified
        the same day.** `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-A exhibited one:
        `alter table raw_item alter column item_key type text collate "und-x-icu"` changes no
        value in any column, drops and renames nothing, leaves `INSERT_ITEM` and
        `SELECT_SNAPSHOT_MEMBERS` working — and reorders **every** member the queried design
        replays, while the sealed snapshot is unmoved and still verifies. The three-way
        taxonomy above misses a fourth category: *change how the selection resolves without
        changing a value*. It bites here rather than in principle, because real `item_key`s
        are URLs and `f"{title}|{period}"`, and this cluster is `initdb --locale=C`.

        `[결정]` The migration is **not** added. The owner chose the narrower claim on
        2026-08-20 rather than spend the gate's remaining time widening the evidence, so the
        refutation is recorded here and the migration axis stays unexercised. What this class
        measures is therefore exactly what its name says — that an added column does *not*
        tell the designs apart — and not the stronger claim the old `[가설]` made for it.
        """
        assert evolution.after_the_migration.queried == evolution.after_the_migration.sealed

        # And the difference the migration does make, in a projection no design reads.
        assert evolution.whole_row_after != evolution.whole_row_before
        added = set(evolution.whole_row_after[0]) - set(evolution.whole_row_before[0])
        assert added == {"payload_sha256"}
        for key in ("item_key", "payload", "id"):
            assert [row[key] for row in evolution.whole_row_after] == [
                row[key] for row in evolution.whole_row_before
            ]

    def test_later_raw_observations_change_what_the_queried_design_replays(
        self, evolution: Evolution
    ) -> None:
        """The discrimination, in the form that would not announce itself.

        The collector ran again. DP-019 D5's selection is "latest per key", so re-running it
        at read time now resolves `item-002` to bytes that did not exist when the snapshot
        was sealed, and picks up an `item-004` the snapshot never selected. A normalizer
        behind the queried design would have produced different output from the same
        snapshot id — the determinism OQ-003 requires, lost without a single error.

        The sealed design is unmoved, which the class above asserts at this same step.
        """
        queried = evolution.after_later_observations.queried
        sealed = evolution.after_later_observations.sealed

        assert queried != sealed
        assert contract_fields(queried) == list(QUERIED_AFTER_LATER_OBSERVATIONS)

        # Named rather than left to the tuple comparison: one key kept its name and changed
        # its bytes, and one key appeared. Those are two different ways to break a replay.
        superseded = next(m for m in queried if m.item_key == "item-002")
        was_sealed = next(m for m in sealed if m.item_key == "item-002")
        assert superseded.payload != was_sealed.payload
        assert {m.item_key for m in queried} - {m.item_key for m in sealed} == {"item-004"}

    def test_purging_the_raw_rows_leaves_the_queried_design_with_nothing(
        self, evolution: Evolution
    ) -> None:
        """The same discrimination at its loudest, and a cost worth recording.

        DP-005 gives Raw the `DELETE_AFTER_EVIDENCE_CAPTURE` disposition, and
        `0002_domain.sql` declined a DELETE trigger on the Raw tables *for that reason* — so
        removing these rows is an operation this schema deliberately left available. Once
        they are gone the queried design has no input at all, while the sealed snapshot
        still verifies and still replays its three members.

        `[추론]` The cost is the mirror image of the benefit: a purge that reaches Raw does
        **not** reach the copy inside `snapshot_item`, so an erasure obligation is not
        discharged by deleting Raw alone. That belongs to OQ-004 rather than to this test,
        which only records that the bytes are still here.

        The empty tuple below is an absence, and its positive control is one test up:
        `test_the_queried_reader_reproduces_the_sealed_reading_before_anything_moves` shows
        the same reader returning three members over the same snapshot id. Emptiness here is
        the purge, not a reader that never worked.
        """
        assert evolution.purged == len(FIRST_COLLECTION) + len(SECOND_COLLECTION) + len(
            LATER_COLLECTION
        )
        assert evolution.after_the_purge.queried == ()
        assert contract_fields(evolution.after_the_purge.sealed) == list(SEALED_MEMBERS)
        assert evolution.domain.snapshot_tampering(evolution.snapshot_id) == ()


class TestTheScenarioCanFail:
    """The mutation control. It was run, and what it printed is recorded here.

    Without it, `TestASealedSnapshotSurvivesRawStoreEvolution` is a class whose every
    assertion is that nothing changed — which is exactly what a scenario measuring nothing
    reports.
    """

    def test_both_halves_go_red_when_a_sealed_payload_is_altered(
        self, evolution: Evolution
    ) -> None:
        """One member's bytes are changed in the store rather than in the test's copy, and
        both halves report it — verification names the member, and the replay stops matching
        what was sealed.

        `[측정]` Run on 2026-08-20 against PostgreSQL 18.4, by moving this `update` into the
        `evolution` fixture immediately after `applied = apply_migrations(handle,
        directory=DOMAIN_MIGRATIONS)`, so that the scenario's own assertions ran against a
        snapshot altered right after the migration. **Five tests went red:**

            test_the_sealed_snapshot_still_verifies
            test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step
            test_each_member_still_matches_the_digest_it_was_sealed_with
            test_an_added_column_does_not_tell_the_two_designs_apart
            test_purging_the_raw_rows_leaves_the_queried_design_with_nothing
            5 failed, 7 passed in 1.74s

            >       assert evolution.domain.snapshot_tampering(evolution.snapshot_id) == ()
            E       assert ("member 1 ('...e sealed one') == ()
            E         Left contains 2 more items, first extra item:
            E           "member 1 ('item-002') no longer matches its digest"

            >           assert step.sealed == evolution.at_seal.sealed
            E           At index 1 diff: Replayed(ordinal=1, item_key='item-002',
            E             payload=b'tampered', content_type='application/octet-stream',
            E             payload_sha256='ca7fe1bf…')
            E             != Replayed(… payload=b'\\x00\\x01\\x02 the second reading', …)

            >           assert digest_of(member.payload) == member.payload_sha256
            E           AssertionError: assert 'd121be310300...631f69445bc57'
            E             == 'ca7fe1bf75c9...d4f2a0a9a83e1'

        The third is forced by arithmetic this docstring can print, and it is why the count
        cannot be two: the stored `payload_sha256` still reads `ca7fe1bf…`, which is
        `sha256(b'\\x00\\x01\\x02 the second reading')`, while the payload beside it is now
        `b'tampered'`, whose digest is `d121be31…`. Tamper detection is a recomputation and
        not a comparison of two stored fields, which is the property that makes the first
        assertion worth making at all.

        `[확인 사실]` The revision of this file that TASK-003 handed over recorded
        `2 failed, 7 passed` for this procedure, and attack report F1 measured `3 failed,
        6 passed` against the file in the tree — a number no revision containing the digest
        test could produce. The record above was produced by running the procedure against
        *this* file and copying what came back.

        `[추론]` Two of the five are in the discrimination class, which is not incidental:
        the mutation moves the sealed reading, so the queried design stops agreeing with it
        where it should. `test_the_queried_reader_reproduces_the_sealed_reading_before_
        anything_moves` still passes, because that reading is taken before the `update`.
        """
        evolution.handle.execute(
            "update snapshot_item set payload = %s where snapshot_id = %s and ordinal = 1",
            (b"tampered", evolution.snapshot_id),
        )

        problems = evolution.domain.snapshot_tampering(evolution.snapshot_id)
        assert "member 1 ('item-002') no longer matches its digest" in problems
        assert "the recomputed manifest digest differs from the sealed one" in problems

        now = replayed(evolution.domain.read_snapshot_items, evolution.snapshot_id)
        assert now != evolution.at_seal.sealed
        assert contract_fields(now) != list(SEALED_MEMBERS)


class TestTheEvolutionIsSafeToApplyTwice:
    """Idempotency of the migration, in this file because `test_migrations.py` exercises the
    platform directory only: its guard covers `0001` and nothing under `domain/migrations/`.
    """

    def test_a_second_pass_applies_the_new_migration_no_second_time(
        self, empty_database: PlatformConfig
    ) -> None:
        with connected(empty_database, autocommit=True) as handle:
            apply_migrations(handle)
            first = apply_migrations(handle, directory=DOMAIN_MIGRATIONS)
            second = apply_migrations(handle, directory=DOMAIN_MIGRATIONS)
            assert MIGRATION_UNDER_TEST in first
            assert second == ()
            recorded = handle.execute(
                "select count(*) from schema_migrations where version = %s",
                (MIGRATION_UNDER_TEST,),
            ).fetchone()
            assert recorded is not None and recorded[0] == 1

    def test_the_second_pass_skips_the_file_rather_than_the_file_being_harmless(
        self, empty_database: PlatformConfig
    ) -> None:
        """The positive control for the guard above, and the reason it is worth having.

        `alter table ... add column` is not idempotent and is not written to be:
        `platform_core.db.migrate` reserves conditional DDL for the one bootstrap statement.
        What is idempotent is the *applier*, and a guard that could not tell the two apart
        would pass against a migration file that happened to do nothing at all.
        """
        with connected(empty_database, autocommit=True) as handle:
            apply_migrations(handle)
            apply_migrations(handle, directory=DOMAIN_MIGRATIONS)
            body = (DOMAIN_MIGRATIONS / f"{MIGRATION_UNDER_TEST}.sql").read_text(encoding="utf-8")
            with pytest.raises(psycopg.errors.DuplicateColumn):
                handle.execute(body)
