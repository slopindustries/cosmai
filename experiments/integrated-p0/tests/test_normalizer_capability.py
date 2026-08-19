"""A normalizer on the platform — the kind `_UNBOUND_KINDS` refused until DP-019.

`addon_host.capabilities` bound `collector` and refused the other two by name, and the
reason it gave for `normalizer` was exact: *"`0002_domain.sql` creates no normalized-result
table, so `emit_result` has nowhere to write; what such a table holds is part of OQ-004."*
`0003_normalized_result.sql` is that table and DP-019 is that decision, so the refusal has
expired and this is what replaces it.

Four properties, four classes, and each one written against an add-on that does *not*
cooperate — because `ADVERSARIAL-REVIEW-2026-08-18.md` F1's lesson is that a control tested
only against a well-behaved add-on measures the add-on.

**The input is sealed and verified before the add-on sees a byte.** `NormalizeContext`'s
own docstring promises it. A tampered snapshot must fail the run rather than be normalized.

**Nothing reaches the outside.** A normalizer has no `fetch`, no credential, and no cursor.
That is asserted by construction — the context has no such field — and by the `source` row
constraint that refuses a normalizer an outbound profile.

**Results are written in the completion transaction.** The same DP-010 property collection
has, so a normalizer that lost its lease persists nothing.

**Determinism is checked rather than requested.** Two runs of one add-on over one snapshot
produce equal digests, and the control is that a *different* add-on version over the same
snapshot produces different ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.store import RawItemRow, canonical_body, digest_of
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = pytest.mark.usefixtures("database")

WORKER = "worker-1"
COLLECTOR_SOURCE = "probe-blog"
NORMALIZER_SOURCE = "probe-blog-normalized"
ADDON_ID = "normalizer.probe"
HANDLER = f"addon:{ADDON_ID}"

MANIFEST = """
[addon]
id = "{addon_id}"
version = "{version}"
kind = "normalizer"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"
output_contract_version = "{output}"

[config]
schema_version = "1"

[[config.field]]
name = "language"
type = "string"
required = false

[declares]
streams = []
"""

#: The ordinary normalizer: one snapshot item becomes one Schema 0.1 document.
NORMALIZER = """
import json

from addon_api import NormalizedResult, NormalizeOutcome


def run(context):
    results = []
    skipped = 0
    for item in context.read_snapshot():
        try:
            entry = json.loads(item.payload)
        except json.JSONDecodeError:
            skipped += 1
            continue
        results.append(
            NormalizedResult(
                source_item_key=item.item_key,
                body={
                    "schema_version": "0.1",
                    "record_type": "document",
                    "external_id": item.item_key,
                    "url": entry.get("link", item.item_key),
                    "title": entry.get("title", ""),
                    "excerpt": entry.get("description", ""),
                    "published_at": None,
                    "author": entry.get("bloggername"),
                    "language": context.config_field("language", "ko"),
                },
            )
        )
    context.emit_result(results)
    return NormalizeOutcome(results_emitted=len(results), skipped=skipped)
"""

#: Reports more than it emitted. The count cross-check collectors already have.
MISCOUNTING = """
from addon_api import NormalizeOutcome


def run(context):
    list(context.read_snapshot())
    return NormalizeOutcome(results_emitted=7)
"""

#: Emits a result naming an item the snapshot does not contain — lineage that points
#: nowhere, which is what `source_item_key` exists to prevent.
ORPHANING = """
from addon_api import NormalizedResult, NormalizeOutcome


def run(context):
    list(context.read_snapshot())
    context.emit_result([NormalizedResult(source_item_key="never-sealed", body={"a": 1})])
    return NormalizeOutcome(results_emitted=1)
"""

#: Returns the wrong type entirely.
WRONG_RETURN = """
def run(context):
    list(context.read_snapshot())
    return None
"""


def install(root: Path, source: str = NORMALIZER, version: str = "0.1.0",
            output: str = "0.1") -> Path:
    package = root / ADDON_ID
    package.mkdir(parents=True, exist_ok=True)
    (package / "addon.toml").write_text(
        MANIFEST.format(addon_id=ADDON_ID, version=version, output=output), encoding="utf-8"
    )
    (package / "handler.py").write_text(source, encoding="utf-8")
    return package


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


@pytest.fixture
def sources(domain: DomainStore) -> None:
    """A collector source that owns the Raw, and a normalizer source that reads it.

    Two rows because DP-008 D5 puts `addon_id` on the source row and derives the handler
    from it, so the normalizer needs one of its own. The `source` table's
    `source_normalizer_reaches_nothing_outside_its_snapshot` constraint refuses to give the
    second an outbound profile or a credential — which is the asymmetry stated as SQL.
    """
    domain.register_source(
        SourceRow(
            source_id=COLLECTOR_SOURCE,
            addon_id="collector.probe",
            addon_version="0.1.0",
            kind="collector",
            config_schema_version="1",
        )
    )
    domain.register_source(
        SourceRow(
            source_id=NORMALIZER_SOURCE,
            addon_id=ADDON_ID,
            addon_version="0.1.0",
            kind="normalizer",
            config={"language": "ko"},
            config_schema_version="1",
        )
    )


def collect(domain: DomainStore, connection: psycopg.Connection[Any], *entries: Any) -> None:
    """Put Raw under the collector source, the way a real collection would leave it."""
    job_id, attempt_id = _job_and_attempt(connection)
    envelope = domain.record_envelope(
        COLLECTOR_SOURCE, job_id, attempt_id, "collector.probe", "0.1.0",
        body=b"{}", endpoint_ref="blog",
    )
    domain.record_items(
        envelope,
        COLLECTOR_SOURCE,
        [
            RawItemRow(
                item_key=entry["link"],
                payload=json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
            )
            for entry in entries
        ],
    )


def a_post(n: int) -> dict[str, Any]:
    return {
        "link": f"https://blog.example.com/{n}",
        "title": f"<b>수분크림</b> 후기 {n}",
        "description": "발림성이 좋다",
        "bloggername": "someone",
    }


def run_normalize(
    root: Path,
    store: JobStore,
    domain: DomainStore,
    snapshot_id: UUID,
    addon_source: str = NORMALIZER,
    version: str = "0.1.0",
    output: str = "0.1",
    source_id: str = NORMALIZER_SOURCE,
) -> RunOutcome:
    install(root, addon_source, version=version, output=output)
    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(root, CONTRACT_VERSION),
        bind_capabilities(domain, _NoTransport()),
    )
    store.create_job(
        HANDLER, {"source_id": source_id, "snapshot_id": str(snapshot_id)}, max_attempts=3
    )
    outcome = JobRunner(store, registry, WORKER, lease_seconds=60).run_once()
    assert outcome is not None
    return outcome


class _NoTransport:
    """A normalizer must never reach this. If it does, the test says so rather than the
    request silently succeeding against a double that answers everything."""

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("a normalizer opened a request")


def _job_and_attempt(connection: psycopg.Connection[Any]) -> tuple[UUID, UUID]:
    """A finished collect job and its closed attempt, for Raw to hang its lineage from.

    `SUCCEEDED` and `finished_at` set, so `claim_next` cannot take it. A `PENDING` row here
    is claimable, and the runner would execute *it* instead of the normalize job the test
    created — which is how this helper failed the first time it was used.
    """
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
    return job_id, attempt_id


class TestANormalizerNormalizes:
    def test_one_run_turns_every_snapshot_item_into_a_result(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1), a_post(2))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.accepted, outcome
        assert outcome.state is JobState.SUCCEEDED
        assert len(domain.read_results(snapshot_id)) == 2

    def test_the_result_carries_its_lineage_and_the_schema_version(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        run_normalize(tmp_path, store, domain, snapshot_id)

        result = domain.read_results(snapshot_id)[0]
        assert result["source_item_key"] == "https://blog.example.com/1"
        assert result["source_id"] == COLLECTOR_SOURCE
        assert result["addon_id"] == ADDON_ID
        assert result["output_contract_version"] == "0.1"
        assert result["body"]["schema_version"] == "0.1"

    def test_the_normalizer_reads_its_own_source_row_config(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """DP-019 D2: `language` is configuration and never detection."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        run_normalize(tmp_path, store, domain, snapshot_id)

        assert domain.read_results(snapshot_id)[0]["body"]["language"] == "ko"

    def test_an_empty_snapshot_succeeds_with_no_results(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, sources: None
    ) -> None:
        """"Nothing to normalize" is an ordinary state and must not read as a defect."""
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.accepted
        assert domain.read_results(snapshot_id) == []


class TestTheInputIsSealedAndVerified:
    def test_a_tampered_snapshot_fails_the_run_before_the_add_on_sees_a_byte(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        connection.execute(
            "update snapshot_item set payload = %s where snapshot_id = %s",
            (b'{"link":"tampered"}', snapshot_id),
        )

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_results(snapshot_id) == []

    def test_an_untampered_snapshot_of_the_same_shape_runs(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """The positive control. A verifier that refused everything would pass above."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        assert run_normalize(tmp_path, store, domain, snapshot_id).accepted

    def test_a_job_naming_no_snapshot_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, sources: None
    ) -> None:
        install(tmp_path)
        registry = HandlerRegistry()
        register_addons(
            registry, load_addons(tmp_path, CONTRACT_VERSION),
            bind_capabilities(domain, _NoTransport()),
        )
        store.create_job(HANDLER, {"source_id": NORMALIZER_SOURCE}, max_attempts=1)

        outcome = JobRunner(store, registry, WORKER, lease_seconds=60).run_once()

        assert outcome is not None and outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT

    def test_a_job_naming_a_snapshot_that_does_not_exist_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore, sources: None
    ) -> None:
        outcome = run_normalize(tmp_path, store, domain, uuid4())

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT


class TestOutputIsChecked:
    def test_a_normalizer_that_miscounts_is_refused_and_persists_nothing(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id, addon_source=MISCOUNTING)

        assert outcome.error is not None
        assert domain.read_results(snapshot_id) == []

    def test_a_result_naming_an_item_the_snapshot_does_not_hold_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """Lineage that points nowhere is the normalizer's version of an item with no
        envelope, and `raw_item.envelope_id` is not null for the same reason."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id, addon_source=ORPHANING)

        assert outcome.error is not None
        assert domain.read_results(snapshot_id) == []

    def test_a_normalizer_returning_the_wrong_type_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id, addon_source=WRONG_RETURN)

        assert outcome.error is not None
        # `[측정]` This asserted only that the run failed, and removing the type check kept
        # it green: the next line to read the result crashes, so the run fails either way.
        # Reading the summary is what distinguishes a checked refusal from a crash. B5.
        assert "NormalizeOutcome" in outcome.error.summary, outcome.error.summary


class TestDeterminism:
    """DP-019 D4, and OQ-003's requirement that one snapshot produce byte-identical output.

    Asserted on digests the *store* computed, so the two runs could genuinely have differed.
    """

    def test_two_runs_of_one_version_over_one_snapshot_agree(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1), a_post(2))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        run_normalize(tmp_path, store, domain, snapshot_id)
        first = [row["body_sha256"] for row in domain.read_results(snapshot_id)]

        # A second snapshot of the same Raw, so the unique index does not refuse the rerun.
        second_snapshot = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        run_normalize(tmp_path / "again", store, domain, second_snapshot)
        second = [row["body_sha256"] for row in domain.read_results(second_snapshot)]

        assert first == second

    def test_a_different_body_produces_a_different_digest(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """The control. Equal digests mean nothing unless unequal input gives unequal
        digests."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        run_normalize(tmp_path, store, domain, snapshot_id)
        stored = domain.read_results(snapshot_id)[0]

        assert stored["body_sha256"] == digest_of(canonical_body(stored["body"]))
        assert stored["body_sha256"] != digest_of(canonical_body({"different": True}))


class TestANormalizerReachesNothingOutside:
    def test_a_normalizer_source_cannot_be_granted_an_outbound_profile(
        self, domain: DomainStore
    ) -> None:
        """The `source` table's own constraint. DP-008 D4's asymmetry as SQL, so it holds
        whatever the capability layer does."""
        with pytest.raises(psycopg.errors.CheckViolation):
            domain.register_source(
                SourceRow(
                    source_id="bad-normalizer",
                    addon_id=ADDON_ID,
                    addon_version="0.1.0",
                    kind="normalizer",
                    config_schema_version="1",
                    outbound_profile={"hosts": ["api.example.com"], "endpoints": {}},
                )
            )

    def test_the_run_opens_no_request(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """`_NoTransport` raises on any send, so a passing run is the assertion."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        assert run_normalize(tmp_path, store, domain, snapshot_id).accepted


class TestTheDurableScopeRequirementIsCheckedForNormalizersToo:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F3, for the run that did not exist when F3 was
    written.

    `[측정]` Found on 2026-08-19 by re-running F3's own mutation against the whole suite:
    `_NormalizeRun._require_completion_transaction` could be **deleted entirely** and all
    1070 tests still passed. The collector's copy of the same guard is covered; this one had
    nothing behind it.

    That is the shape F1 and F3 are both about — a control that exists, reads correctly, and
    is held up by nothing — reproduced in code written *after* reading the review that
    named it. It is recorded here rather than quietly fixed, because the useful part is that
    duplicating a guard duplicated the code and not the evidence.
    """

    def test_a_domain_store_outside_the_completion_transaction_is_refused(
        self,
        tmp_path: Path,
        store: JobStore,
        database: PlatformConfig,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
        sources: None,
    ) -> None:
        """The mis-wiring F3 measured, against a normalize run.

        The snapshot is sealed on the *shared* connection — it has to exist before the run —
        and the run itself is given a `DomainStore` on a separate autocommit one. Results
        would then survive a completion the fence refused, which is what H2a forbids.
        """
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        with connected(database, autocommit=True) as separate:
            outside = DomainStore(separate)

            outcome = run_normalize(tmp_path, store, outside, snapshot_id)

            assert outcome.error is not None
            assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
            assert outside.read_results(snapshot_id) == []

    def test_the_same_run_on_the_shared_connection_is_not_refused(
        self,
        tmp_path: Path,
        store: JobStore,
        domain: DomainStore,
        connection: psycopg.Connection[Any],
        sources: None,
    ) -> None:
        """The positive control. Without it the refusal above would pass against a check
        that refused every normalization."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.accepted
        assert len(domain.read_results(snapshot_id)) == 1


class TestTheNormalizersOwnSourceRowIsChecked:
    """The same four clauses a collect run checks, checked on the normalize side too.

    `[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5 measured these: `enabled`,
    `kind`, and the configuration schema were **GREEN** on this side — the guard existed in
    both `_CollectRun` and `_NormalizeRun`, and only the collector's copy was tested.
    A duplicated guard is only as strong as its least-tested copy, and nothing about the
    collector's tests reaches this code.
    """

    def test_a_disabled_normalizer_source_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        connection.execute(
            "update source set enabled = false where source_id = %s", (NORMALIZER_SOURCE,)
        )

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_results(snapshot_id) == []

    def test_a_source_of_the_wrong_kind_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """A collector's row may hold an outbound grant and a credential. Running a
        normalizer against one would be a normalizer inheriting both.

        `[측정]` The row names **this add-on** on purpose. Pointing the run at the ordinary
        collector row instead left the `addon_id` clause to do the refusing, and removing
        the `kind` clause stayed GREEN — the same mistake, one layer up, that made B5 a
        finding in the first place.
        """
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        domain.register_source(
            SourceRow(
                source_id="wrong-kind-same-addon",
                addon_id=ADDON_ID,
                addon_version="0.1.0",
                kind="collector",
                config={"language": "ko"},
                config_schema_version="1",
            )
        )

        outcome = run_normalize(
            tmp_path, store, domain, snapshot_id, source_id="wrong-kind-same-addon"
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_results(snapshot_id) == []

    def test_a_source_naming_a_different_add_on_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """DP-008 D5 derives the handler from `addon_id`. A row naming another add-on would
        run this add-on's code under another add-on's registered identity and version."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        domain.register_source(
            SourceRow(
                source_id="normalizer-impostor",
                addon_id="normalizer.somebody.else",
                addon_version="0.1.0",
                kind="normalizer",
                config={"language": "ko"},
                config_schema_version="1",
            )
        )

        outcome = run_normalize(
            tmp_path, store, domain, snapshot_id, source_id="normalizer-impostor"
        )

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.PLATFORM_PERMANENT
        assert domain.read_results(snapshot_id) == []

    def test_a_configuration_the_schema_rejects_is_refused(
        self, tmp_path: Path, store: JobStore, domain: DomainStore,
        connection: psycopg.Connection[Any], sources: None,
    ) -> None:
        """`[측정]` B5: `test_normalizer_capability.py` contained no configuration-schema
        test at all, so this whole clause was carried by the collector's copy."""
        collect(domain, connection, a_post(1))
        snapshot_id = domain.seal_snapshot_from_raw(COLLECTOR_SOURCE)
        connection.execute(
            "update source set config = %s where source_id = %s",
            (json.dumps({"language": 123}), NORMALIZER_SOURCE),
        )

        outcome = run_normalize(tmp_path, store, domain, snapshot_id)

        assert outcome.error is not None
        assert outcome.error.error_class is ErrorClass.CONFIGURATION_INVALID
        assert domain.read_results(snapshot_id) == []
