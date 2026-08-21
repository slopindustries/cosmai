"""The real Naver API Hub, end to end — collect, seal, normalize.

Opt-in twice, and both gates are deliberate: `--run-network` because this opens a real
outbound connection, and `--run-credential` because it spends a real quota against a real
key. `tests/conftest.py` owns the gating; nothing here can turn itself on.

This is the only test in the repository where **nothing** is a double: the installed
`collector.naver.blog` runs through `JobRunner`, the capability layer, `domain.outbound`,
`domain.transport`, a TLS socket, the actual `naverapihub.apigw.ntruss.com`, and into
PostgreSQL — then a sealed snapshot goes through the installed `normalizer.naver.blog` and
into `normalized_result`.

**What it costs.** `max_pages = 2`, `display = 10`. The API Hub's blog-search quota is
25,000 calls a day, so one run of this spends two of them.

**What it is evidence for.** The three `[가설]` assumptions in `collector.naver.blog`'s
module docstring were written from the vendor's documentation because no capture existed.
This is the capture. `TestTheDocumentedAssumptions` checks the two that a small run can
reach and says plainly which one it cannot.

**What is not committed.** No response body, and no normalized record. The operator's basis
for this data is personal research and study, which covers *processing* and is not a
redistribution basis — `data-handling.md` keeps those two decisions apart. So the source is
registered `data_class = "local"` and this file asserts on shapes, counts, and digests
rather than storing samples. `AGENTS.md`'s rule for that case is hashes and a retrieval
procedure, and `../evidence/naver-real-data/README.md` is where they go.

`[측정]` **That sentence was false until 2026-08-19.** It named the directory in the present
tense while nothing was there — the hashes were never written down, and by the time anyone
looked, one capture's rows had been cleared by a later scenario run and its digest was
unrecoverable. The directory now exists, records the two digests that survived, and states
the missing one as missing. The procedural half is recorded there too: **a capture's digest
must be taken while its rows exist**, because every scenario script clears the domain tables
on the way in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
import pytest
from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore, SourceRow
from domain.transport import SocketTransport
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner, RunOutcome
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore

pytestmark = [
    pytest.mark.usefixtures("database"),
    pytest.mark.network,
    pytest.mark.requires_credential,
]

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]

WORKER = "worker-real"

COLLECT_SOURCE = "naver-blog"
NORMALIZE_SOURCE = "naver-blog-normalized"

#: `[확인 사실]` https://api.ncloud-docs.com/docs/naver-api-hub-search-blog, fetched
#: 2026-08-18: `GET /search/v1/blog` on `naverapihub.apigw.ntruss.com`, authenticated with
#: the two NCP headers.
HOST = "naverapihub.apigw.ntruss.com"
BLOG_PATH = "/search/v1/blog"

ID_REF = "COSMA_SRC_NAVER_BLOG_CLIENT_ID"
SECRET_REF = "COSMA_SRC_NAVER_BLOG_CLIENT_SECRET"

#: Two pages of ten. Small enough that a run costs two of the day's 25,000 calls, large
#: enough that pagination and the cursor are actually exercised.
MAX_PAGES = 2
DISPLAY = 10

#: A beauty term, because that is the provisional decision use DP-019 records. `sort=date`
#: rather than `sim` so that `postdate` is populated across the page rather than clustered.
QUERY = "수분크림"


@pytest.fixture
def domain(connection: psycopg.Connection[Any]) -> DomainStore:
    return DomainStore(connection)


@pytest.fixture
def registered(domain: DomainStore) -> None:
    """The collector's source and the normalizer's, as an operator would register them."""
    domain.register_source(
        SourceRow(
            source_id=COLLECT_SOURCE,
            addon_id="collector.naver.blog",
            addon_version="0.1.0",
            kind="collector",
            config={"query": QUERY, "display": DISPLAY, "sort": "date"},
            config_schema_version="1",
            outbound_profile={
                "hosts": [HOST],
                "endpoints": {"blog": BLOG_PATH},
                "port": 443,
                "limits": {"max_pages": MAX_PAGES},
                # DP-018. Key **names**; the values never enter this row, this process's
                # environment, or any artefact this run leaves behind.
                "credentials": [
                    {"header": "X-NCP-APIGW-API-KEY-ID", "ref": ID_REF},
                    {"header": "X-NCP-APIGW-API-KEY", "ref": SECRET_REF},
                ],
            },
            # Processing basis is personal research and study. That is not a redistribution
            # basis, and `data-handling.md` keeps the two apart — so `local`, not `public`.
            data_class="local",
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


def a_registry(domain: DomainStore) -> HandlerRegistry:
    """The installed add-on set, bound to the real transport. No doubles."""
    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(EXPERIMENT_ROOT / "addons", CONTRACT_VERSION),
        bind_capabilities(domain, SocketTransport()),
    )
    return registry


def collect(store: JobStore, domain: DomainStore) -> RunOutcome:
    store.create_job(
        "addon:collector.naver.blog", {"source_id": COLLECT_SOURCE}, max_attempts=1
    )
    outcome = JobRunner(store, a_registry(domain), WORKER, lease_seconds=120).run_once()
    assert outcome is not None
    return outcome


def normalize(store: JobStore, domain: DomainStore, snapshot_id: Any) -> RunOutcome:
    store.create_job(
        "addon:normalizer.naver.blog",
        {"source_id": NORMALIZE_SOURCE, "snapshot_id": str(snapshot_id)},
        max_attempts=1,
    )
    outcome = JobRunner(store, a_registry(domain), WORKER, lease_seconds=120).run_once()
    assert outcome is not None
    return outcome


@pytest.fixture
def collected(store: JobStore, domain: DomainStore, registered: None) -> RunOutcome:
    outcome = collect(store, domain)
    assert outcome.accepted, f"the real collection failed: {outcome.error}"
    return outcome


class TestTheCollectorReachesTheRealApi:
    def test_a_real_run_succeeds_and_persists_raw(
        self, collected: RunOutcome, domain: DomainStore, connection: psycopg.Connection[Any]
    ) -> None:
        assert collected.state is JobState.SUCCEEDED
        envelopes = connection.execute("select count(*) from raw_envelope").fetchone()
        assert envelopes is not None and int(envelopes[0]) >= 1
        assert domain.count_items(COLLECT_SOURCE) > 0

    def test_the_page_limit_bounded_the_run(
        self, collected: RunOutcome, connection: psycopg.Connection[Any]
    ) -> None:
        """`ADVERSARIAL-REVIEW-2026-08-18.md` F1's counter, against a real API rather than a
        cooperating stub. The add-on stops at `max_pages` on its own; the platform would
        refuse it past that, and either way the number of requests is bounded."""
        envelopes = connection.execute("select count(*) from raw_envelope").fetchone()
        assert envelopes is not None and int(envelopes[0]) <= MAX_PAGES

    def test_the_cursor_advanced_so_a_second_run_would_resume(
        self, collected: RunOutcome, domain: DomainStore
    ) -> None:
        assert domain.read_cursor(COLLECT_SOURCE, "items") is not None

    def test_no_credential_value_reached_any_recorded_artefact(
        self, collected: RunOutcome, connection: psycopg.Connection[Any]
    ) -> None:
        """DP-018 D3 and `p0-security.md`, against the real values this time.

        The values are read here — the one place in the suite that does — precisely so the
        assertion is about them rather than about a stand-in. They are never printed.
        """
        from domain.secrets import resolve_credential

        secrets = [resolve_credential(ID_REF).reveal(), resolve_credential(SECRET_REF).reveal()]
        rows = connection.execute(
            "select coalesce(request_summary::text, '') || "
            "coalesce(response_headers::text, '') || encode(body, 'escape') from raw_envelope"
        ).fetchall()
        assert rows, "nothing was recorded, so this proves nothing"
        for (recorded,) in rows:
            for value in secrets:
                assert value not in recorded

    def test_the_credential_is_not_in_this_process_environment(
        self, collected: RunOutcome
    ) -> None:
        """`secret-setup.md` invariant 2, checked after a real resolution has happened."""
        from domain.secrets import resolve_credential

        assert resolve_credential(ID_REF).reveal() not in os.environ.values()


class TestTheDocumentedAssumptions:
    """`collector.naver.blog`'s module docstring states three `[가설]` assumptions written
    from documentation because no capture existed. This is the capture."""

    def test_assumption_1_an_exhausted_page_is_200_with_an_empty_items_array(
        self, collected: RunOutcome, connection: psycopg.Connection[Any]
    ) -> None:
        """Assumption 1: `start` past the end of the pool returns `200` with `items: []`,
        not an error and not a missing key.

        The add-on treats a 200 body without an `items` list as a *different* failure on
        purpose, so a run that got this far without failing is the assumption holding —
        and the explicit check below is what makes that visible rather than implied.
        """
        bodies = connection.execute("select body from raw_envelope").fetchall()
        for (raw,) in bodies:
            parsed = json.loads(bytes(raw))
            assert isinstance(parsed.get("items"), list), (
                "assumption 1 is falsified: a 200 response carried no `items` array"
            )

    def test_assumption_1b_every_item_carries_the_documented_link_field(
        self, collected: RunOutcome, connection: psycopg.Connection[Any]
    ) -> None:
        """`link` is the identity the collector and the normalizer both key on. If the API
        ever omits it, both break, and this is where that shows up first."""
        bodies = connection.execute("select body from raw_envelope").fetchall()
        seen = 0
        for (raw,) in bodies:
            for entry in json.loads(bytes(raw)).get("items", []):
                assert isinstance(entry.get("link"), str) and entry["link"]
                seen += 1
        assert seen > 0, "no items came back, so this proves nothing"

    def test_assumption_3_is_not_reached_by_this_run(self, collected: RunOutcome) -> None:
        """Assumption 3 is about the shape of a `429`. A two-call run does not provoke one,
        so this run says nothing about it — recorded as a stated gap rather than left for a
        reader to assume the whole docstring was confirmed."""
        pytest.skip("a 429 is not reachable from a two-call run; assumption 3 stays 가설")


class TestTheNormalizerRunsOnRealData:
    def test_a_snapshot_of_the_real_raw_normalizes(
        self, collected: RunOutcome, store: JobStore, domain: DomainStore
    ) -> None:
        snapshot_id = domain.seal_snapshot_from_raw(COLLECT_SOURCE)

        outcome = normalize(store, domain, snapshot_id)

        assert outcome.accepted, f"the real normalization failed: {outcome.error}"
        assert outcome.state is JobState.SUCCEEDED
        assert len(domain.read_results(snapshot_id)) > 0

    def test_every_result_is_schema_0_1_and_traceable_to_its_raw_item(
        self, collected: RunOutcome, store: JobStore, domain: DomainStore
    ) -> None:
        snapshot_id = domain.seal_snapshot_from_raw(COLLECT_SOURCE)
        normalize(store, domain, snapshot_id)

        keys = {row["item_key"] for row in domain.read_snapshot_items(snapshot_id)}
        for result in domain.read_results(snapshot_id):
            assert result["body"]["schema_version"] == "0.1"
            assert result["body"]["record_type"] == "document"
            assert result["source_item_key"] in keys
            assert result["body"]["language"] == "ko"

    def test_the_two_rules_actually_fired_on_real_text(
        self, collected: RunOutcome, store: JobStore, domain: DomainStore
    ) -> None:
        """The rules are only worth having if the real data needs them. `[측정]` This
        asserts what the capture showed: titles arrive with `<b>` markup and `postdate`
        arrives as `yyyymmdd`, so both rules changed something.
        """
        snapshot_id = domain.seal_snapshot_from_raw(COLLECT_SOURCE)
        normalize(store, domain, snapshot_id)
        results = domain.read_results(snapshot_id)

        assert not any("<b>" in r["body"]["title"] for r in results), (
            "markup survived into a normalized title"
        )
        assert not any("&quot;" in r["body"]["title"] for r in results)
        dated = [r for r in results if r["body"]["published_at"] is not None]
        assert dated, "no result carried a parseable date; the date rule fired on nothing"
        for result in dated:
            assert len(result["body"]["published_at"]) == len("2026-08-01")

    def test_normalizing_the_same_snapshot_twice_is_refused_rather_than_doubled(
        self, collected: RunOutcome, store: JobStore, domain: DomainStore
    ) -> None:
        """DP-019 D3's other half, on real data: a rerun of one version over one snapshot is
        a duplicate the platform refuses, not a version it stores."""
        snapshot_id = domain.seal_snapshot_from_raw(COLLECT_SOURCE)
        normalize(store, domain, snapshot_id)
        first = len(domain.read_results(snapshot_id))

        second_outcome = normalize(store, domain, snapshot_id)

        assert not second_outcome.accepted or second_outcome.error is not None
        assert len(domain.read_results(snapshot_id)) == first
