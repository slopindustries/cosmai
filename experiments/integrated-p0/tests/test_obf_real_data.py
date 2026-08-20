"""The real Open Beauty Facts, end to end — one nightly delta import, sealed, and replayed.

`[확인 사실]` TASK-007's reason for existing: the charter's *"one REST source and one
dataset complete the end-to-end flow"* has had its dataset half filled by `SRC-002`, a
JSONL file this project wrote for itself. `SRC-003` measured a real dataset producer
(Open Beauty Facts) and recommended `NO-GO` on **product coverage** for the Korean
sunscreen/toner scope DP-011 fixed — but that recommendation is about content, not about
whether the mechanical import path works, and DP-026 moved the product scope to P1. What
is missing is evidence that a real external dataset's own bytes — not a self-authored
fixture — pass through the installed `importer.local.jsonl`, DP-024's input registry, and a
sealed snapshot. This is that evidence.

Like `test_naver_real_data.py`, nothing here is a double: the source is registered exactly
as an operator would register it, the job is created through `POST /sources/{id}/import` —
added 2026-08-20, and until then the dataset half of the charter's operator flow (item 12)
had no route at all — and `JobRunner` executes the installed add-on against the real
downloaded file.

**What is not committed.** No OBF row, in any form, anywhere in the working tree. DP-027
registered this source `data_class = "local"`; ODbL's share-alike attaches the moment a
derived store is *published*, and committing a fixture would be exactly that (`SRC-003`,
*What the licence requires of derived output*). The downloaded delta is decompressed under
this repository's gitignored `var/`, and this file asserts on shapes, counts, and digests.
`../evidence/obf-dataset/README.md` is where the digests and retrieval procedure go, and —
learning `naver-real-data/README.md`'s stated lesson — they are written down while the rows
in this run's database still exist, not after.

**Which two deltas.** `SRC-003` measured that OBF's delta index is a rolling window whose
newest two windows abut (one's `to_ts` is the next one's `from_ts`), and that the newest-at
capture-time and the one before it shared three `code`s across a real edit. This module
reads "take the most recent complete" delta and "a second, later delta whose window
overlaps" together as: the newest published delta is the *second* one, and the one just
before it is the *first*. Whether they share a `code` on the day this runs is a fact about
the source, checked and reported rather than assumed — the packet's own condition for
recording the changed-content case as unexercised.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host.api import extend_with_domain
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.transport import SocketTransport
from fastapi.testclient import TestClient
from platform_core.api.app import create_app
from platform_core.config import PlatformConfig
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from psycopg.types.json import Jsonb

pytestmark = [pytest.mark.usefixtures("database"), pytest.mark.network]

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
#: `AGENTS.md`'s `/var/` — this repository's gitignored root, not the machine's. DP-024 D5:
#: the operator's approved input root may sit inside the working tree; this one just never
#: enters it.
INPUT_ROOT = EXPERIMENT_ROOT.parents[1] / "var" / "samples" / "obf"

WORKER = "worker-obf"
SOURCE = "obf-dataset"
ADDON_ID = "importer.local.jsonl"
HANDLER = f"addon:{ADDON_ID}"

#: TASK-010: the normalizer half of the same operator flow. TASK-007 sealed a real snapshot
#: and stopped; TASK-008 built `normalizer.obf.product` and verified it against fixtures its
#: own author invented. Neither packet was asked to run one against the other — this is that
#: run, registered under its own source id the way `test_naver_real_data.py` registers
#: `naver-blog-normalized` beside `naver-blog`.
NORMALIZE_SOURCE = "obf-dataset-normalized"
NORMALIZE_ADDON_ID = "normalizer.obf.product"

#: The provider asks for an identifying User-Agent of the form
#: `AppName/Version (ContactEmail)`; `SRC-003` recorded the same requirement.
USER_AGENT = "cosmai-p0-obf-importer/0.1 (P0-B TASK-007, no public contact address)"
INDEX_URL = "https://static.openbeautyfacts.org/data/delta/index.txt"
DELTA_BASE = "https://static.openbeautyfacts.org/data/delta/"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FetchedDelta:
    """One nightly delta, downloaded once and recorded before its rows can move."""

    filename: str
    url: str
    fetched_at: str
    gz_bytes: int
    gz_sha256: str
    jsonl_path: Path
    jsonl_bytes: int
    jsonl_sha256: str
    codes: tuple[str, ...]


def _fetch_delta(filename: str) -> FetchedDelta:
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    url = DELTA_BASE + filename
    fetched_at = datetime.now(UTC).astimezone().isoformat()
    response = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True
    )
    response.raise_for_status()
    gz_bytes = response.content
    jsonl_bytes = gzip.decompress(gz_bytes)
    jsonl_path = INPUT_ROOT / filename.removesuffix(".gz")
    jsonl_path.write_bytes(jsonl_bytes)
    codes = tuple(
        json.loads(line)["code"] for line in jsonl_bytes.splitlines() if line.strip()
    )
    return FetchedDelta(
        filename=filename,
        url=url,
        fetched_at=fetched_at,
        gz_bytes=len(gz_bytes),
        gz_sha256=_sha256(gz_bytes),
        jsonl_path=jsonl_path,
        jsonl_bytes=len(jsonl_bytes),
        jsonl_sha256=_sha256(jsonl_bytes),
        codes=codes,
    )


@pytest.fixture(scope="module")
def deltas() -> tuple[FetchedDelta, FetchedDelta]:
    """The two most recent complete nightly deltas. Fetched once for the whole module — a
    second retrieval of the same URLs is not required by the acceptance criteria.

    F6 (`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md`): this docstring previously claimed
    a second fetch could not reproduce these bytes. It can, and does — `SRC-003`'s own ledger
    and three independent retrievals of delta A (08:30, 15:36, 16:16) all returned the same
    SHA-256, because the export server serves a fixed archived file per delta rather than a
    live query. `SRC-003`'s "a re-run will not reproduce these digests" is about its live
    **API** samples, not this archived delta export."""
    index = httpx.get(INDEX_URL, headers={"User-Agent": USER_AGENT}, timeout=30.0)
    index.raise_for_status()
    names = sorted(line.strip() for line in index.text.splitlines() if line.strip())
    if len(names) < 2:
        pytest.skip("fewer than two nightly deltas are published; nothing to compare")
    return _fetch_delta(names[-2]), _fetch_delta(names[-1])


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


@pytest.fixture
def client(database: PlatformConfig, logger: StructuredLogger) -> TestClient:
    app = create_app(database, logger, extend=extend_with_domain(database, logger))
    return TestClient(app)


def a_registry(domain: DomainStore, logger: StructuredLogger) -> HandlerRegistry:
    """The installed add-on set, bound to the real capability layer. No doubles — this is
    `importer.local.jsonl` exactly as `addons/` ships it, not a copy in `tmp_path`."""
    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(EXPERIMENT_ROOT / "addons", CONTRACT_VERSION),
        bind_capabilities(domain, SocketTransport(), logger=logger),
    )
    return registry


def register(domain: DomainStore, member: str) -> None:
    domain.register_source(
        SourceRow(
            source_id=SOURCE,
            addon_id=ADDON_ID,
            addon_version="0.1.0",
            kind="importer",
            # `code` is OBF's own row identity (`SRC-003`, *Row identity candidate*), and
            # the field this packet was told to key the importer on.
            config={"key_field": "code"},
            config_schema_version="1",
            input_profile={"root": str(INPUT_ROOT), "inputs": {"rows": member}},
            # DP-027: OBF is registered `local`. No redistribution basis is claimed here,
            # and nothing derived from this run is committed.
            data_class="local",
        )
    )


def repoint(connection: psycopg.Connection[Any], member: str) -> None:
    """Change which file `rows` names, as an operator revising the approved input profile
    between two imports of one source would. `DomainStore` has no update method for a
    registered source — nothing in P0-B needed one before this packet — so this reaches the
    row directly, the same way `test_domain_store.py`'s tamper tests reach `snapshot_item`
    rather than adding a store method for a single test's sake."""
    connection.execute(
        "update source set input_profile = %s where source_id = %s",
        (Jsonb({"root": str(INPUT_ROOT), "inputs": {"rows": member}}), SOURCE),
    )


def run_import(client: TestClient, store: JobStore, registry: HandlerRegistry) -> RunOutcome:
    response = client.post(f"/sources/{SOURCE}/import")
    assert response.status_code == 201, response.text
    outcome = JobRunner(store, registry, WORKER, lease_seconds=120).run_once()
    assert outcome is not None
    return outcome


def payloads_of(connection: psycopg.Connection[Any]) -> list[bytes]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select i.payload from raw_item i "
            "join raw_envelope e on e.id = i.envelope_id where e.source_id = %s",
            (SOURCE,),
        )
        return [bytes(row[0]) for row in cursor.fetchall()]


def import_finished_events(log_stream: StringIO) -> list[dict[str, Any]]:
    """Parse `addon.import.finished` out of the structured log, which is where the
    importer's skip counters land — `RunOutcome` carries no `CollectOutcome` field."""
    events = []
    for line in log_stream.getvalue().splitlines():
        record = json.loads(line)
        if record.get("event") == "addon.import.finished":
            events.append(record["fields"])
    return events


def normalize_complete_fields(log_stream: StringIO) -> dict[str, Any]:
    """Parse `addon.normalize.complete` out of the structured log — `handler.py`'s own
    `context.log("normalize.complete", {"results_emitted": ..., "skipped": ...})`, forwarded
    by `addon_host.capabilities._log` under `addon.{event}`. `NormalizeOutcome` itself is not
    on `RunOutcome`, so this is the counts' only way out of one run."""
    events = []
    for line in log_stream.getvalue().splitlines():
        record = json.loads(line)
        if record.get("event") == "addon.normalize.complete":
            events.append(record["fields"])
    return events[0] if len(events) == 1 else {"_events": events}


def register_normalizer(domain: DomainStore) -> None:
    """`normalizer.obf.product`, registered beside the importer's `obf-dataset` source —
    an operator adding the normalization step the same way `test_naver_real_data.py`
    registers `naver-blog-normalized` beside `naver-blog`."""
    domain.register_source(
        SourceRow(
            source_id=NORMALIZE_SOURCE,
            addon_id=NORMALIZE_ADDON_ID,
            addon_version="0.1.0",
            kind="normalizer",
            config={"language": "en"},
            config_schema_version="1",
        )
    )


def run_normalize(
    store: JobStore, registry: HandlerRegistry, snapshot_id: UUID
) -> RunOutcome:
    store.create_job(
        f"addon:{NORMALIZE_ADDON_ID}",
        {"source_id": NORMALIZE_SOURCE, "snapshot_id": str(snapshot_id)},
        max_attempts=1,
    )
    outcome = JobRunner(store, registry, WORKER, lease_seconds=120).run_once()
    assert outcome is not None
    return outcome


@pytest.fixture
def imported(
    client: TestClient,
    store: JobStore,
    domain: DomainStore,
    logger: StructuredLogger,
    deltas: tuple[FetchedDelta, FetchedDelta],
) -> RunOutcome:
    first, _second = deltas
    register(domain, first.jsonl_path.name)
    outcome = run_import(client, store, a_registry(domain, logger))
    assert outcome.accepted, f"the real import failed: {outcome.error}"
    assert outcome.state is JobState.SUCCEEDED
    return outcome


class TestARealDeltaImportsThroughTheInstalledHost:
    def test_a_real_run_succeeds_and_persists_raw(
        self, imported: RunOutcome, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        envelopes = connection.execute(
            "select count(*) from raw_envelope where source_id = %s", (SOURCE,)
        ).fetchone()
        assert envelopes is not None and int(envelopes[0]) == 1
        assert domain.count_items(SOURCE) > 0

    def test_the_payload_is_the_sources_own_line_bytes_not_a_reserialization(
        self,
        imported: RunOutcome,
        deltas: tuple[FetchedDelta, FetchedDelta],
        connection: psycopg.Connection[Any],
    ) -> None:
        """Digest a line from the downloaded file and find that digest among the stored
        payloads — the check the acceptance criteria ask for, done by hash rather than by
        direct byte comparison so it also demonstrates nothing was re-serialized: a
        `json.dumps` round trip through Python would reorder keys and change the digest."""
        first, _second = deltas
        source_line_digests = {
            _sha256(line)
            for line in first.jsonl_path.read_bytes().splitlines()
            if line.strip()
        }
        stored = payloads_of(connection)
        assert stored, "nothing was recorded, so this proves nothing"
        for payload in stored:
            assert _sha256(payload) in source_line_digests

    def test_item_and_unique_code_counts_are_recorded(
        self, imported: RunOutcome, deltas: tuple[FetchedDelta, FetchedDelta], domain: DomainStore
    ) -> None:
        first, _second = deltas
        assert domain.count_items(SOURCE) == len(first.codes)
        assert len(set(first.codes)) == len(first.codes), (
            "the delta held a duplicate code; SRC-003 measured none in three samples, so "
            "this would itself be worth recording"
        )

    def test_every_skip_counter_the_importer_reported_is_recorded(
        self, imported: RunOutcome, deltas: tuple[FetchedDelta, FetchedDelta], log_stream: StringIO
    ) -> None:
        """`[측정]` A real nightly delta is expected to hold no malformed line, per the
        packet's own excluded scope. This asserts what the run actually reported rather
        than assuming it — if a counter is ever non-zero, this test names it."""
        first, _second = deltas
        events = import_finished_events(log_stream)
        assert len(events) == 1
        fields = events[0]
        assert fields["emitted"] == len(first.codes)
        assert fields["lines"] == len(first.codes)
        for counter in ("malformed_json", "not_an_object", "missing_key_field"):
            assert fields[counter] == 0, (
                f"{counter} was {fields[counter]}, not zero — a real delta produced a "
                "skip this packet's evidence record must name"
            )


class TestASealedSnapshotVerifiesAndDetectsTampering:
    def test_the_snapshot_verifies_as_sealed(
        self, imported: RunOutcome, client: TestClient
    ) -> None:
        response = client.post(f"/sources/{SOURCE}/snapshots")
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["item_count"] > 0
        assert body["verifies"] is True
        assert body["problems"] == []

    def test_a_mutated_member_is_detected_and_named(
        self,
        imported: RunOutcome,
        client: TestClient,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
    ) -> None:
        """Acceptance criterion 4's own requirement: show the detector can fail. Verified
        clean *before* the mutation, then mutated, then verified tampered — so the pass
        above is not the only thing this test could have produced."""
        sealed = client.post(f"/sources/{SOURCE}/snapshots")
        snapshot_id = UUID(sealed.json()["snapshot_id"])
        assert domain.snapshot_tampering(snapshot_id) == (), (
            "verified clean before the mutation below — the control that shows the "
            "detector is capable of passing, not only of failing"
        )

        connection.execute(
            "update snapshot_item set payload = %s where snapshot_id = %s and ordinal = 0",
            (b'{"code": "tampered"}', snapshot_id),
        )

        problems = domain.snapshot_tampering(snapshot_id)
        assert any("no longer matches its digest" in problem for problem in problems)
        assert any("manifest digest differs" in problem for problem in problems)

        via_api = client.get(f"/snapshots/{snapshot_id}")
        assert via_api.json()["verifies"] is False


class TestIdenticalReplayIsRecordedAsCounts:
    def test_a_second_identical_import_is_recorded_rather_than_asserted(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        deltas: tuple[FetchedDelta, FetchedDelta],
    ) -> None:
        """Charter exit criterion 3, with counts. `raw_item` carries no uniqueness
        constraint (`domain/store.py`'s own docstring on `seal_snapshot_from_raw`) — Raw is
        logically append-only, so a replay is *not* refused at the Raw level. The chosen
        idempotency behavior lives one layer up: a snapshot collapses a repeated `code` to
        its latest occurrence, so a snapshot sealed after the replay carries the same item
        count as one sealed before it, even though `raw_item` now holds it twice."""
        first, _second = deltas
        before = client.post(f"/sources/{SOURCE}/snapshots").json()

        second_outcome = run_import(client, store, a_registry(domain, logger))
        assert second_outcome.accepted, f"the replay failed: {second_outcome.error}"

        after = client.post(f"/sources/{SOURCE}/snapshots").json()

        assert domain.count_items(SOURCE) == 2 * len(first.codes)
        assert before["item_count"] == len(first.codes)
        assert after["item_count"] == len(first.codes)
        assert before["manifest_sha256"] == after["manifest_sha256"], (
            "identical rows re-imported and re-sealed must select an identical manifest"
        )


class TestChangedContentIsANewObservation:
    def test_the_second_later_delta_advances_shared_codes_without_editing_raw_in_place(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        connection: psycopg.Connection[Any],
        deltas: tuple[FetchedDelta, FetchedDelta],
    ) -> None:
        first, second = deltas
        overlap = set(first.codes) & set(second.codes)
        if not overlap:
            pytest.skip(
                "the two most recent deltas share no code on this run; the changed-"
                "content scenario is recorded as absent and unexercised rather than "
                "manufactured, per the packet's stopping condition"
            )

        repoint(connection, second.jsonl_path.name)
        outcome = run_import(client, store, a_registry(domain, logger))
        assert outcome.accepted, f"the second import failed: {outcome.error}"

        with connection.cursor() as cursor:
            for code in overlap:
                cursor.execute(
                    "select count(*) from raw_item where source_id = %s and item_key = %s",
                    (SOURCE, code),
                )
                count = cursor.fetchone()
                assert count is not None and count[0] == 2, (
                    f"{code} should appear as two raw_item rows — a new observation, not "
                    "an edit of the first"
                )

        sealed = client.post(f"/sources/{SOURCE}/snapshots").json()
        assert sealed["item_count"] == len(set(first.codes) | set(second.codes))

        snapshot_id = UUID(sealed["snapshot_id"])
        items = {
            row["item_key"]: bytes(row["payload"])
            for row in domain.read_snapshot_items(snapshot_id)
        }
        second_lines = {
            json.loads(line)["code"]: line
            for line in second.jsonl_path.read_bytes().splitlines()
            if line.strip()
        }
        for code in overlap:
            assert items[code] == second_lines[code], (
                f"the snapshot should select {code}'s later occurrence, not its first"
            )


class TestTheNormalizerRunsOnTheRealSnapshot:
    """TASK-010: the joining scenario neither TASK-007 nor TASK-008 was asked to write. The
    attack report on TASK-008 measured that no real Open Beauty Facts row had ever reached
    `normalizer.obf.product` — every prior `product` record came from `a_row()` in that
    add-on's own test file. This class runs the installed add-on through `JobRunner` and the
    host's normalize path, over the snapshot `TestARealDeltaImportsThroughTheInstalledHost`
    already proved carries the source's own bytes — the same path
    `test_naver_real_data.py`'s `TestTheNormalizerRunsOnRealData` uses for
    `normalizer.naver.blog`, not a hand-built `NormalizeContext`.

    Per TASK-010's packet: **the add-on is not this task's to fix.** If a real row makes it
    behave wrongly, that is reported and this class stops rather than repairing it — the
    add-on already survived an independent attack (24 of 30 mutants dead, determinism across
    seven hash seeds), and a fix made here would erase that independence.
    """

    def test_a_real_snapshot_normalizes_through_the_host(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        log_stream: StringIO,
    ) -> None:
        sealed = client.post(f"/sources/{SOURCE}/snapshots").json()
        snapshot_id = UUID(sealed["snapshot_id"])
        register_normalizer(domain)

        outcome = run_normalize(store, a_registry(domain, logger), snapshot_id)

        assert outcome.accepted, f"the real normalization failed: {outcome.error}"
        assert outcome.state is JobState.SUCCEEDED

        fields = normalize_complete_fields(log_stream)
        results = domain.read_results(snapshot_id)
        assert fields["results_emitted"] + fields["skipped"] == sealed["item_count"], (
            "results_emitted plus skipped must add up to the snapshot's own item count "
            f"({sealed['item_count']}); got {fields}"
        )
        assert fields["results_emitted"] == len(results), (
            "the add-on's own reported count disagrees with what was actually persisted"
        )
        assert not (fields["results_emitted"] == 0 and fields["skipped"] == sealed["item_count"]), (
            "the normalizer skipped every real row — an honest zero, reported rather than "
            "presented as a pass (TASK-010's stopping condition)"
        )

    def test_every_result_is_schema_0_3_and_traces_to_the_sealed_snapshot(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
    ) -> None:
        sealed = client.post(f"/sources/{SOURCE}/snapshots").json()
        snapshot_id = UUID(sealed["snapshot_id"])
        register_normalizer(domain)
        run_normalize(store, a_registry(domain, logger), snapshot_id)

        keys = {row["item_key"] for row in domain.read_snapshot_items(snapshot_id)}
        results = domain.read_results(snapshot_id)
        assert results, "nothing was emitted; the schema-version claim below proves nothing"
        for result in results:
            assert result["output_contract_version"] == "0.3"
            assert result["body"]["record_type"] == "product"
            assert result["source_item_key"] in keys

    def test_field_presence_over_real_rows_is_recorded_not_smoothed(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
        deltas: tuple[FetchedDelta, FetchedDelta],
    ) -> None:
        """`[측정]` SRC-003 measured `product_name` present in 19 of 36 sampled rows — so a
        run where every field is populated on every record is itself suspicious, not a sign
        of success. This asserts that the run does not smooth away the sparsity; the actual
        counts go in `evidence/obf-dataset/README.md`.

        F1 (`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md`): `not all(...)` only fires when
        *every* field is full on *every* row, so any one field going wrong survives as long as
        another stays sparse — proven by an `... or "FABRICATED"` mutant on `_display_name`
        that pushed `display_name` to 121/121 while the suite stayed green. Below, each
        field's presence is pinned individually against a count computed from `first`'s own
        bytes at run time, not a literal — a later delta's rolling window changes which rows
        are sparse, and a hard-coded count would fail then for the wrong reason.
        """
        sealed = client.post(f"/sources/{SOURCE}/snapshots").json()
        snapshot_id = UUID(sealed["snapshot_id"])
        register_normalizer(domain)
        run_normalize(store, a_registry(domain, logger), snapshot_id)

        results = domain.read_results(snapshot_id)
        assert results
        presence = {
            "display_name": sum(
                1 for r in results if r["body"]["display_name"] is not None
            ),
            "brands": sum(1 for r in results if r["body"]["brands"]),
            "observed_at": sum(1 for r in results if r["body"]["observed_at"] is not None),
            "has_ingredients_true": sum(
                1 for r in results if r["body"]["has_ingredients"] is True
            ),
        }
        assert not all(count == len(results) for count in presence.values()), (
            f"every field populated on every one of {len(results)} records: suspicious "
            f"per SRC-003's sparsity measurement — observed presence was {presence}"
        )

        first, _second = deltas
        rows = [
            json.loads(line)
            for line in first.jsonl_path.read_bytes().splitlines()
            if line.strip()
        ]
        expected = {
            "display_name": sum(
                1
                for row in rows
                if isinstance(row.get("product_name"), str) and row["product_name"].strip()
            ),
            "brands": sum(
                1
                for row in rows
                if isinstance(row.get("brands_tags"), list) and len(row["brands_tags"]) > 0
            ),
            "observed_at": sum(
                1
                for row in rows
                if isinstance(row.get("last_modified_t"), int | float)
                and not isinstance(row.get("last_modified_t"), bool)
            ),
            "has_ingredients_true": sum(
                1
                for row in rows
                if isinstance(row.get("ingredients_text"), str)
                and row["ingredients_text"].strip()
            ),
        }
        assert presence == expected, (
            f"per-field presence diverged from {first.filename}'s own bytes: emitted "
            f"{presence}, source computes {expected}"
        )

    def test_the_brands_tags_prefix_measurement_is_confirmed_or_contradicted(
        self,
        imported: RunOutcome,
        client: TestClient,
        store: JobStore,
        domain: DomainStore,
        logger: StructuredLogger,
    ) -> None:
        """`[측정]` TASK-008's `Review` section: the orchestrator read the two delta files
        under `var/samples/obf/` directly and found `brands_tags` present as a `list` on
        26/121 rows of delta A, and every one of the 70 values across both deltas carrying an
        `xx:` language prefix. This asserts the same claim over this run's own persisted
        `normalized_result` rows — through the normalizer rather than by reading the delta
        file directly — so a future delta whose export drops the prefix contradicts it here,
        loudly, rather than silently. Whether to strip the prefix is a schema question for
        the owner (TASK-010's packet); this test only confirms or contradicts what the
        source, unmodified by the add-on, actually sent.
        """
        sealed = client.post(f"/sources/{SOURCE}/snapshots").json()
        snapshot_id = UUID(sealed["snapshot_id"])
        register_normalizer(domain)
        run_normalize(store, a_registry(domain, logger), snapshot_id)

        results = domain.read_results(snapshot_id)
        tagged = [r["body"]["brands"] for r in results if r["body"]["brands"]]
        assert tagged, "no record carried a brands value; the xx: prefix claim is moot"
        for tags in tagged:
            assert isinstance(tags, list)
            assert all(isinstance(tag, str) for tag in tags)

        all_tags = [tag for tags in tagged for tag in tags]
        prefixed = [tag for tag in all_tags if tag.startswith("xx:")]
        assert len(prefixed) == len(all_tags), (
            f"{len(all_tags) - len(prefixed)} of {len(all_tags)} brands_tags values lacked "
            "the xx: language prefix TASK-008's Review section measured — contradicting "
            "that record rather than confirming it"
        )
