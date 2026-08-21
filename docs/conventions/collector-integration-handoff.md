# Collector integration handoff guide

- Status: `DRAFT_FOR_REVIEW`
- Governing decision: [DP-012](../decisions/DP-012-independent-scraper-services.md)
- Scope: independent scraper REST services and COSMAI adapter add-ons
- External service and adapter owner for `trend-radar` and `yt-scrapper`: collector/backend owner
- Guide owner: delivery lead

## Purpose

This document is a handoff frame, not an instruction to merge scraper projects into
COSMAI. Each scraper runs independently as a REST service, stores its result first in its
own storage, and exposes a replayable export endpoint. COSMAI contains only the thin adapter
add-on that ingests that endpoint through the existing platform contract.

The collector/backend owner keeps ownership of the external service, first-stage storage,
adapter connection, and validation. The delivery lead records the common contract,
unresolved choices, and review evidence so those details do not live only in chat.

This guide does not authorize a source, change a scraper selector, choose a crawling
method, or approve storing review content. Source rights and data handling must be recorded
separately before a real run.

The reported existing services are `trend-radar` and the not-yet-complete `yt-scrapper`.
Their projects remain separate. The Naver service and its COSMAI adapter are owned by the
Cosmai delivery/backend team.

This guide makes later integration reviewable; it does not make `trend-radar` or
`yt-scrapper` deadline-critical. The required collection path is the Naver service and
adapter. Other adapters start after that path and its backend reliability checks pass.

## Ownership boundary

| Work | Owner |
|---|---|
| External scraper REST service, scheduling, parsing, and first-stage storage | Collector/backend owner |
| COSMAI REST adapter add-on and worker connection | Collector/backend owner |
| Raw, cursor, retry, and job integration tests | Collector/backend owner |
| Required fields, safety rules, review checklist, and unresolved-decision record | Delivery lead |
| Merge approval | Repository manager |

## Naver collector ownership

The repository already contains a direct `collector.naver.blog` prototype verified against
a local stub. It is reference evidence, not the selected final boundary. The Cosmai
delivery/backend team owns:

- an independent Naver REST collection service with first-stage storage;
- the two-header Naver credential inside that service, never in the COSMAI adapter;
- an export contract with stable record IDs, batch IDs, capture time, and cursor;
- a COSMAI adapter add-on that fetches the export endpoint through `CollectContext.fetch`;
- Raw, cursor, duplicate replay, failure classification, and redaction evidence.

The direct prototype is retained until P0 disposition records whether to archive or delete
it. It must not become a second active Naver ingestion path silently.

## Integration topology

```text
original source
  → independent scraper REST service
  → scraper-owned first-stage storage
  → versioned export endpoint
  → COSMAI adapter add-on
  → COSMAI Raw + cursor + job completion
  → normalization and analysis
```

COSMAI never imports scraper code or reads a scraper database. Scraper storage is the
service's operational store. COSMAI Raw is the evidence copy used for snapshots, replay,
normalization, and cards; it is not replaced by the external database.

## 1. Fill this in before connecting a collector

Create one copy of this table per source. Do not write secret values.

| Field | Value |
|---|---|
| Source name | `TBD` |
| `source_id` | `TBD` |
| External service repository, branch, and commit | `TBD` |
| Service schema version | `TBD` |
| Service run command and health endpoint | `TBD` |
| First-stage storage and retention owner | `TBD` |
| Adapter add-on ID, version, path, and commit | `TBD` |
| Service credential key name or `credential_ref` only | `TBD` |
| Approved service host and export endpoint references | `TBD` |
| Batch ID, record ID, and response checksum rules | `TBD` |
| Record types emitted | `TBD` |
| Cursor streams and cursor shape | `TBD` |
| Page, record, timeout, and quota limits | `TBD` |
| Data class: `public`, `local`, or `private` | `TBD` |
| Access and agent-processing basis | `TBD` |
| Raw retention and deletion rule | `TBD` |
| Known failures and recovery method | `TBD` |

## 2. Service and platform connection contract

The independent service owns original-source access and first-stage persistence. The
COSMAI adapter imports `addon_api` only. It does not import scraper modules, open either
database, read a credential value, or bypass the platform outbound policy.

| Concern | Required connection |
|---|---|
| Job input | Select a registered adapter `source_id`; do not accept an arbitrary service URL. |
| Network | Use `CollectContext.fetch(endpoint_ref, params)` against an approved service export endpoint. |
| Service response | Include `schema_version`, service commit, `batch_id`, generation time, items, `next_cursor`, `has_more`, and `item_count`. |
| Service item | Include stable `record_id`, `record_type`, original source identity, capture time, optional publication time and URL, and lossless payload. |
| Raw output | Map each service item to `RawItem(item_key, payload, content_type, envelope_ref, notes)` through `emit_raw`. |
| Position | Advance the COSMAI cursor only after every accepted service item was enlisted for Raw persistence. |
| Completion | Return `CollectOutcome`; do not write job state directly. |
| Persistence | Service storage commits independently. COSMAI Raw, cursor advancement, and accepted job completion share the COSMAI transaction. |
| Failures | Raise the matching add-on error. Do not catch and suppress a platform refusal. |

No distributed transaction is introduced. The service must make `batch_id + record_id`
replayable so an interrupted COSMAI run can request the same batch again safely. A schema,
item-count, stable-ID, or cursor validation failure must not advance the COSMAI cursor.

The service may use a browser, source credential, or source-specific database internally,
but those details never cross its REST boundary. The adapter sees only the approved export
contract. Record a decision before adding any new platform capability.

## 3. Stable item keys

Use the service's stable `record_id`. Prefix the record type so unlike records cannot
collide.

```text
product/<service_record_id>
review/<service_record_id>
channel/<youtube_channel_id>
video/<youtube_video_id>
comment/<youtube_comment_id>
```

If an original source exposes no stable identifier, the service documents its deterministic
composite key and collision risk. Do not use a canonical COSMAI product or ingredient ID as
a Raw key. Canonicalization happens after Raw persistence.

`payload` preserves the source item without semantic loss. Generated metadata such as
`record_type` may be placed in `notes`, but it must not replace or rewrite the source item.
Never place a token, cookie, request authorization header, or unnecessary reviewer
identifier in `payload` or `notes`.

## 4. Source-specific minimums

### Commerce and review sources

- Emit product and review records separately.
- A review must retain a traceable source product identifier.
- Record the source publication time when present and the capture time independently.
- Preserve pagination or watermark state in a named cursor stream.
- Ratings, option names, rankings, and review counts remain source observations. Do not
  relabel them as sales or market share.

### YouTube

- Keep channel, video, comment, and statistics-snapshot records distinguishable.
- Use YouTube IDs as Raw identities.
- Preserve `publishedAt` separately from capture time.
- Keep video/comment page tokens in separate cursor streams when their recovery differs.
- Record quota usage and expected cases such as disabled comments or deleted videos.
- A later statistics capture is a new observation; it must not silently overwrite the
  earlier capture used by an analysis run.

## 5. Failure and limit checklist

Before a real run, verify all of the following:

- page and record limits are enforced even if the collector loops incorrectly;
- the same service batch can be replayed without uncontrolled duplicate effects;
- schema version, batch ID, item count, record IDs, and cursor shape are validated;
- connect/read deadlines and response-size limits end as classified failures;
- HTTP 429, transient network failures, and eligible 5xx responses follow bounded retry;
- invalid credentials and invalid configuration fail without retry;
- malformed source output does not advance the cursor;
- a failed Raw write leaves neither a cursor advance nor a successful job completion;
- duplicate delivery does not create an uncontrolled durable effect;
- logs and errors contain no secret, cookie, protected header, or full Raw payload;
- collection and normalization can be retried independently.

## 6. Minimum review evidence

Each source handoff includes:

1. Branch name and commit hash.
2. External service and adapter commits recorded separately.
3. A command that runs the adapter against a sanitized service-response fixture.
4. A command for the approved local real-source run, naming credential keys only.
5. Fixture origin, capture time, rights basis, transformation, and SHA-256.
6. Tests for first page, next page, empty result, malformed record, retryable failure,
   terminal failure, cursor resume, and duplicate replay.
7. Measured service item count, emitted count, Raw count, cursor value, job outcome, and redacted failure
   example.
8. Known limitations and a recovery procedure another team member can follow.

Do not commit `.env` files, API keys, cookies, real credentials, unrestricted Raw dumps,
or unredacted personal data.

## 7. Decisions that require an explicit answer

The collector/backend owner records one choice and its reason before implementation.

| Question | A | B | C | Default |
|---|---|---|---|---|
| Where does scraper code run? | Independent REST service | COSMAI repository | Adapter process | A |
| How does COSMAI read results? | Versioned export endpoint | Service database | Shared filesystem | A |
| Where does source-specific parsing live? | External service | COSMAI adapter | Platform core | A |
| What happens to ambiguous identity? | `REVIEW_REQUIRED` | Force the closest match | Drop silently | A |
| What is committed to Git? | Sanitized fixture and metadata | Real Raw sample | Credential-bearing example | A |

Choosing B or C for source access, or changing the add-on contract, requires a recorded
project decision. No default in this table is proof that the source is permitted or that
the existing scraper is compatible.

## 8. Ready-for-review checklist

- [ ] Source table in section 1 is complete.
- [ ] External service and COSMAI adapter are separate repositories or clearly separate diffs.
- [ ] Service response version, batch identity, replay, and cursor rules are documented.
- [ ] No platform-core change is source-specific.
- [ ] Stable Raw keys and cursor recovery are tested.
- [ ] Real-source rights and data class are recorded.
- [ ] Secrets and non-redistributable Raw data are absent from Git.
- [ ] Focused tests and the repository test suite pass.
- [ ] The repository manager has approved merge scope.
