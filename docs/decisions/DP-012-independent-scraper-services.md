# DP-012 — Independent scraper services and COSMAI REST adapters

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project owner and delivery team
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md), [OQ-007](../open-questions/OQ-007-credential-scope.md), [OQ-009](../open-questions/OQ-009-credential-shape.md)
- Affected contracts: experimental acquisition contract, source profile, adapter response schema
- Affected acceptance tests: `ACQ`, `RAW`, domain `OPS`, `SEC-002`, `SEC-003`, `SEC-004`

## Decision question

Should source-specific scraper projects be merged into COSMAI, or should COSMAI ingest
their stored results through a small REST adapter add-on?

## Candidates

1. Merge each scraper project, its runtime, and its storage code into COSMAI.
2. Keep each scraper as an independent REST service with its own first-stage storage, and
   add only an in-repository COSMAI adapter add-on.
3. Let every COSMAI add-on call the original external source directly.
4. Export files manually and use only the dataset importer path.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: A thin REST adapter preserves the source boundary without coupling COSMAI to scraper code or storage. | An adapter must import scraper modules, read the scraper database directly, or know source-specific runtime internals. |
| H2: Stable record IDs, batch IDs, and cursors are enough to recover safely without a distributed transaction. | Replaying an acknowledged or interrupted batch loses a record, creates an uncontrolled duplicate, or advances the COSMAI cursor past unpersisted Raw. |
| H3: The existing `CollectContext.fetch` boundary can call an approved scraper-service endpoint. | The adapter requires an arbitrary URL, direct socket, credential value, or platform-core import. |
| H4: First-stage scraper storage and COSMAI Raw serve different purposes without creating ambiguous truth. | A reviewer cannot determine which service batch and original source record produced a COSMAI Raw item. |

## Experiment

- Scope: the Naver service adapter is the required P0 path. `trend-radar` receives a
  compatibility review but its adapter is not deadline-critical. The YouTube adapter starts
  only after `yt-scrapper` declares a stable export contract and the required path passes.
- Environment and versions: independent service commit plus COSMAI adapter commit are both
  recorded for every run.
- Input and fixture identity: sanitized service-response fixtures with schema version,
  batch ID, record IDs, cursor, capture time, and hash.
- Procedure: replay the same batch, interrupt before COSMAI completion, resume from the
  previous cursor, change one record, and verify Raw lineage and job outcome.
- Known limitations: the external service repositories and their current API schemas were
  reported by the implementation owner but were not independently inspected when this
  packet was written.

## Evidence

`[확인 사실]` [DP-008](DP-008-addon-architecture.md) already requires an in-repository
collector add-on to use `CollectContext.fetch(endpoint_ref, params)`, emit Raw through the
contract, and avoid direct database, credential, URL, and socket access.

`[확인 사실]` The COSMAI domain layer already stores registered sources, opaque cursor
streams, Raw envelopes, and Raw items. It can therefore treat an approved scraper REST
endpoint as the collector add-on's bounded source without importing the scraper project.

`[확인 사실]` The project owner selected independent scraper REST services with first-stage
storage and a COSMAI adapter-only integration. The reported existing services are
`trend-radar` and the not-yet-complete `yt-scrapper`. Their readiness remains to be verified
from branch, commit, response fixture, and replay evidence.

`[확인 사실]` The implementation owner reported that integrating `trend-radar` is not
technically urgent and that `yt-scrapper` is not complete. This packet therefore fixes the
boundary without putting either integration ahead of the required Naver path.

`[추론]` A service database commit and a COSMAI Raw commit cannot share the existing local
PostgreSQL transaction. Pretending otherwise would create a hidden distributed transaction.
Stable batches and idempotent replay are the smaller and testable recovery boundary.

## Decision

`[결정]` Candidate 2 is accepted for P0.

```text
original source
  → independent scraper REST service
  → scraper-owned first-stage storage
  → versioned export endpoint
  → COSMAI collector adapter add-on
  → COSMAI Raw + cursor + job completion
  → normalization and analysis
```

- Scraper repositories, scraper scheduling, source-specific parsing, browser automation,
  and first-stage storage remain outside the COSMAI repository.
- COSMAI stores only the adapter add-on, its manifest, sanitized fixtures, tests, and the
  service contract needed to ingest results.
- The adapter calls a registered service `endpoint_ref` through platform `fetch`; it never
  reads the scraper database and never accepts an arbitrary URL.
- COSMAI Raw remains required. It is the immutable ingestion and evidence boundary for the
  exact service batch used by a snapshot; the scraper database remains operational
  first-stage storage, not COSMAI's canonical evidence store.
- No distributed transaction is introduced. The service exposes replayable batches and
  COSMAI commits Raw, its ingestion cursor, and accepted job completion atomically on its
  side.
- Canonical product, ingredient, topic, and evidence IDs are assigned downstream. An
  external service record ID is a Raw identity, not a canonical COSMAI identity.
- The same pattern applies to the Naver collector owned by the Cosmai delivery/backend
  team: an independent Naver collection service plus an in-repository adapter. The current
  direct `collector.naver.blog` prototype is evidence and reference code until its P0
  disposition is recorded; it is not silently treated as the final boundary.

### Minimum service response contract

Endpoint names are service-specific, but an adapter cannot be reviewed without these
semantics:

```text
schema_version
service_name and service_commit
batch_id and generated_at
items[]:
  record_type
  record_id
  original_source
  source_record_id
  source_url when available
  published_at when available
  captured_at
  payload
next_cursor
has_more
item_count
```

`record_id` is stable within the service. `batch_id + record_id` is replayable. The adapter
validates `schema_version`, `item_count`, stable IDs, and cursor shape before enlisting Raw
writes. A response that cannot satisfy the contract does not advance the cursor.

Service authentication, if needed, is resolved by the platform through `credential_ref`.
The registered outbound profile names only the approved service host and endpoint paths.
Original source credentials, cookies, and protected headers never cross the service API.

## Rejected alternatives

- Candidate 1 couples deployments, dependencies, storage migrations, and source-specific
  failures to COSMAI without improving the analysis contract.
- Candidate 3 remains valid only for a bounded probe. It is not the selected delivery
  boundary because the team has already separated scraper operation and first-stage storage.
- Candidate 4 loses incremental collection and operator recovery and is kept only as an
  explicit fallback for a replayable dataset.

## Tradeoffs and risks

- Benefits: independent failure domains, no scraper-code merge, small COSMAI adapters, and
  source services reusable outside COSMAI.
- Costs: one additional network hop, two storage layers, service schema versioning, and
  separate deployment observability.
- Failure modes: mutable batches, unstable record IDs, cursor drift, service/API version
  mismatch, partial pages, and an unavailable service.
- Reversibility: adapters can be replaced source by source; COSMAI Raw and downstream
  contracts do not depend on scraper implementation language or database.

## Falsification input carried from OQ-014, 2026-08-20

`[확인 사실]` [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) asked this same
question on the same day, on the domain branch, and could not see this packet. It closed
against this decision rather than competing with it. What it measured, and what this packet
had assumed, is recorded here so the decision carries its own counter-evidence.

`[측정]` **Relocation does not shrink the source-specific work.** Measured on the three
collectors this repository already runs: 235–292 lines each, of which 13–15% is
source-independent plumbing and the remainder is source-specific. Roughly 250 lines per
source *move* rather than disappear. Two DataLab collectors share 165 identical lines.

`[추론]` **This adds a falsification condition H1 does not cover.** H1 asks whether an
adapter can stay thin without importing scraper code. It can. The risk the measurement names
is on the far side: the same duplication re-grows in the external services, now outside
`tests/environment/test_addon_layer_direction.py`, which is the guard that made it visible
here at all. A boundary that exports duplication and its detector together has not reduced
the duplication; it has stopped counting it.

**H5 (added):** The relocated source-specific work is cheaper to maintain outside than
inside. *Falsified by* two scraper services re-growing shared source-independent helpers
independently, with no equivalent of the layer-direction guard reporting it.

`[확인 사실]` **H1's premise is unmeasured.** Nothing in P0 measured collector scheduling
contention or proximity to a source rate limit — quota consumption was 2 of 25,000/day and 2
of 50,000/month. Whether separating acquisition from consumption removes real pressure, or
decoupling nobody needed, is not evidence this project holds. It belongs in this packet's
experiment section before the P1 Entry Gate reads the decision as settled.

`[결정]` **The decision stands; its confidence does not rise.** This section exists so a
reader meets the counter-evidence at the decision rather than in a closed question.

## Remaining uncertainty

- Exact export endpoints and response schemas of `trend-radar` and `yt-scrapper`.
- Whether services run on loopback, a private network, or approved HTTPS; each choice needs
  a matching outbound profile and security evidence.
- Naver service repository, deployment owner, and schedule.
- Per-service retention, deletion, access basis, and personal-data minimization.

## Required changes

- Project State: record the independent-service and adapter-only boundary.
- Contract or schema: version the minimum service response and adapter configuration.
- Acceptance tests: identical batch replay, interruption, cursor resume, schema mismatch,
  item-count mismatch, unavailable service, redaction, and changed record.
- Migration or compatibility: no COSMAI schema change is required by this decision alone.
- Implementation handoff: keep scraper code outside this repository; submit each adapter as
  an `addons/*` change with sanitized service-response fixtures.
