"""Import, seal, normalize — the whole dataset path, through the installed host worker.

New for M4. `experiments/integrated-p0/tests/test_obf_real_data.py`'s
`TestARealDeltaImportsThroughTheInstalledHost`/`TestTheNormalizerRunsOnTheRealSnapshot`
proved this same joining scenario against a live Open Beauty Facts download — this pair is
not ported, on purpose: it needs a live network fetch, and this batch's brief is that the
importer/normalizer pair is fully offline. What replaces it is this file: the same shape of
evidence — a real `source.input_profile` naming a real file, a real `JobRunner` running the
installed `importer.local.jsonl` and `normalizer.obf.product`, a real sealed snapshot in
between — over a structural fixture (DP-022) this file writes itself instead of a download.
That is this batch's live smoke: nothing here builds a `NormalizeContext` by hand or calls a
handler's `run` directly, unlike every class in `test_normalizer_obf_product.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("_migrations_applied")

ADDONS_ROOT = Path(__file__).resolve().parents[1] / "addons"
IMPORT_SOURCE = "obf-fixture-dataset"
NORMALIZE_SOURCE = "obf-fixture-dataset-normalized"
IMPORTER_ID = "importer.local.jsonl"
NORMALIZER_ID = "normalizer.obf.product"
WORKER = "worker-obf-e2e"

#: One structurally plausible Open Beauty Facts row per line (DP-022): the shapes SRC-003
#: measured — a barcode `code`, sparse `product_name`, `brands_tags` as a list, a Unix
#: `last_modified_t` — and no row anyone actually contributed. The third and fourth rows are
#: deliberately sparse and deliberately unusable respectively, so this fixture exercises
#: presence and skip together rather than only the fully-populated case.
ROWS = (
    {
        "code": "8801234567890",
        "product_name": "Example Whitening Cream",
        "brands_tags": ["brand-alpha", "brand-beta"],
        "ingredients_text": "aqua, glycerin, parfum",
        "last_modified_t": 1735689600,
    },
    {
        "code": "8800000000002",
        "product_name": "Example Sunscreen",
        "brands_tags": ["brand-gamma"],
        "ingredients_text": "aqua, titanium dioxide",
        "last_modified_t": 1735689700,
    },
    {
        # Sparse: no product_name, no brands_tags, no ingredients_text — SRC-003's
        # measured ordinary case, not the exception.
        "code": "8800000000003",
        "last_modified_t": 1735689800,
    },
    {
        # No usable code at all: skipped by the normalizer, never by the importer —
        # the importer only requires the configured key_field ("code"), which this row has.
        "code": "   ",
        "product_name": "Unusable Row",
    },
)


class _NoTransport:
    """Neither add-on in this file should ever reach this. DP-024 D6 / DP-008 D4."""

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("neither add-on in this file should ever open a request")


def a_registry(domain: DomainStore) -> HandlerRegistry:
    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(ADDONS_ROOT, CONTRACT_VERSION),
        bind_capabilities(domain, _NoTransport()),
    )
    return registry


def write_dataset(tmp_path: Path) -> Path:
    directory = tmp_path / "datasets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "obf-fixture.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS) + "\n",
        encoding="utf-8",
    )
    return directory


def register_importer(domain: DomainStore, approved_root: Path) -> None:
    domain.register_source(
        SourceRow(
            source_id=IMPORT_SOURCE,
            addon_id=IMPORTER_ID,
            addon_version="0.1.0",
            kind="importer",
            config={"key_field": "code"},
            config_schema_version="1",
            input_profile={"root": str(approved_root), "inputs": {"rows": "obf-fixture.jsonl"}},
            data_class="local",
        )
    )


def register_normalizer(domain: DomainStore) -> None:
    domain.register_source(
        SourceRow(
            source_id=NORMALIZE_SOURCE,
            addon_id=NORMALIZER_ID,
            addon_version="0.1.0",
            kind="normalizer",
            config={"language": "en"},
            config_schema_version="1",
        )
    )


def run_import(job_store: JobStore, registry: HandlerRegistry) -> RunOutcome:
    job_store.create_job(f"addon:{IMPORTER_ID}", {"source_id": IMPORT_SOURCE}, max_attempts=1)
    outcome = JobRunner(job_store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


def run_normalize(
    job_store: JobStore, registry: HandlerRegistry, snapshot_id: UUID
) -> RunOutcome:
    job_store.create_job(
        f"addon:{NORMALIZER_ID}",
        {"source_id": NORMALIZE_SOURCE, "snapshot_id": str(snapshot_id)},
        max_attempts=1,
    )
    outcome = JobRunner(job_store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


@pytest.fixture
def imported(tmp_path: Path, job_store: JobStore, domain_store: DomainStore) -> RunOutcome:
    register_importer(domain_store, write_dataset(tmp_path))
    outcome = run_import(job_store, a_registry(domain_store))
    assert outcome.accepted, f"the fixture import failed: {outcome.error}"
    assert outcome.state is JobState.SUCCEEDED
    return outcome


class TestTheDatasetImportsThroughTheInstalledHost:
    def test_every_row_is_imported_as_raw(
        self, imported: RunOutcome, domain_store: DomainStore
    ) -> None:
        assert domain_store.count_items(IMPORT_SOURCE) == len(ROWS)
        assert domain_store.raw_summary(IMPORT_SOURCE)["envelope_count"] == 1

    def test_the_cursor_records_lines_read(
        self, imported: RunOutcome, domain_store: DomainStore
    ) -> None:
        assert domain_store.read_cursor(IMPORT_SOURCE, "rows") == {"lines_read": len(ROWS)}


class TestTheSnapshotSealsAndVerifies:
    def test_sealing_carries_every_imported_item(
        self, imported: RunOutcome, domain_store: DomainStore
    ) -> None:
        snapshot_id = domain_store.seal_snapshot_from_raw(IMPORT_SOURCE)
        assert domain_store.snapshot_tampering(snapshot_id) == ()
        items = domain_store.read_snapshot_items(snapshot_id)
        assert len(items) == len(ROWS)


class TestTheNormalizerRunsOnTheSealedSnapshot:
    """The joining scenario this file exists for: `importer.local.jsonl`'s own Raw bytes,
    sealed, read back by `normalizer.obf.product` through the same `JobRunner` path a
    worker process uses — not a hand-built `NormalizeContext`."""

    def test_a_fixture_snapshot_normalizes_through_the_host(
        self, imported: RunOutcome, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        snapshot_id = domain_store.seal_snapshot_from_raw(IMPORT_SOURCE)
        register_normalizer(domain_store)

        outcome = run_normalize(job_store, a_registry(domain_store), snapshot_id)

        assert outcome.accepted, f"the fixture normalization failed: {outcome.error}"
        assert outcome.state is JobState.SUCCEEDED

        results = domain_store.read_results(snapshot_id)
        # Three rows carry a usable code (rows 1-3); the fourth's code is blank after
        # trim and is skipped by the normalizer, per DP-028 D3.
        assert len(results) == 3
        for result in results:
            assert result["output_contract_version"] == "0.3"
            assert result["body"]["record_type"] == "product"

    def test_field_presence_matches_the_fixture_not_a_smoothed_average(
        self, imported: RunOutcome, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        """The sparse third row (no `product_name`, no `brands_tags`, no
        `ingredients_text`) must still abstain correctly rather than the run silently
        filling in a value for every field on every row."""
        snapshot_id = domain_store.seal_snapshot_from_raw(IMPORT_SOURCE)
        register_normalizer(domain_store)
        run_normalize(job_store, a_registry(domain_store), snapshot_id)

        results = {r["source_item_key"]: r["body"] for r in domain_store.read_results(snapshot_id)}
        sparse = results["8800000000003"]
        assert sparse["display_name"] is None
        assert sparse["brands"] == []
        assert sparse["has_ingredients"] is False
        assert sparse["observed_at"] == "2025-01-01T00:03:20Z"

        full = results["8801234567890"]
        assert full["display_name"] == "Example Whitening Cream"
        assert full["brands"] == ["brand-alpha", "brand-beta"]
        assert full["has_ingredients"] is True

    def test_lineage_traces_every_result_to_a_snapshot_item(
        self, imported: RunOutcome, job_store: JobStore, domain_store: DomainStore
    ) -> None:
        snapshot_id = domain_store.seal_snapshot_from_raw(IMPORT_SOURCE)
        register_normalizer(domain_store)
        run_normalize(job_store, a_registry(domain_store), snapshot_id)

        keys = {item["item_key"] for item in domain_store.read_snapshot_items(snapshot_id)}
        for result in domain_store.read_results(snapshot_id):
            assert result["source_item_key"] in keys
