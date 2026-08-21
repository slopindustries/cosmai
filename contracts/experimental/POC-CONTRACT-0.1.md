# PoC Contract 0.1 — the domain contract P1 reconstructs from

- Status: `EXPERIMENTAL`
- Version: `0.1`
- Owner: Project team
- Related Open Question: [OQ-001](../../docs/open-questions/OQ-001-source-capability.md), [OQ-003](../../docs/open-questions/OQ-003-normalization-protocol.md), [OQ-004](../../docs/open-questions/OQ-004-snapshot-boundary.md), [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md), [OQ-009](../../docs/open-questions/OQ-009-credential-shape.md), [OQ-010](../../docs/open-questions/OQ-010-cursor-stream-read-back.md), [OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md), [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md)
- Related Decision Packet: DP-008, DP-010, DP-018, DP-019, DP-020, DP-021, DP-022, DP-023, DP-024
- Related experiments: [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md)
- Producers: P0-B `experiments/integrated-p0/` — **as evidence, not as an implementation P1 imports**
- Consumers: P1 reconstruction
- Last updated: 2026-08-19T+09:00

## Purpose and boundary

`[결정]` The project owner decided on 2026-08-19 to fold B2's eight domain contract
families — acquisition, Raw, job/error specialization, snapshot, normalization, operations,
source policy, credential scope — into **this one document** rather than write eight interim
contracts that P1 would then merge. What each section states is the behaviour P1 must
reproduce; how P0 implemented it is evidence, and
[`P0-ARTIFACT-DISPOSITION.md`](../../docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md)
records that no P0 code crosses into P1.

**Outside this contract.** Platform job execution is
[`CONTRACT-JOB-0.1`](CONTRACT-JOB-0.1.md) and is not restated here. Which decision the
product improves ([OQ-002](../../docs/open-questions/OQ-002-project-decision-contract.md))
is still open, so nothing here fixes normalized *meaning* beyond the envelope.

## Compatibility statement

- Compatibility obligation during P0: none. P0 is over; this document is the handover.
- Known incompatible changes: `Normalized Schema` 0.1 → 0.2 turned a flat document shape
  into a discriminated union. Anything written against 0.1's implicit "every record is a
  document" assumption breaks.
- Promotion or replacement condition: the P1 Entry Gate accepts or rejects this document.
  [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md) can replace §1
  entirely, and that is the largest single risk to this contract's shape.

---

## §1 Acquisition

`[결정]` **An add-on names; the operator's approved profile decides.** This is the load-bearing
rule of the whole contract and every other clause in this section follows from it.

- An add-on declares what it needs (`[declares]`: hosts, endpoints, inputs, streams,
  `needs_credential`). A declaration is a **request**, never a grant.
- The operator writes the grant onto the source row: `outbound_profile` for a collector,
  `input_profile` for an importer. An add-on can neither read nor widen it.
- A collector calls `fetch(endpoint_ref, params=None, body=None)`. The platform resolves the
  host, port, path, and method from the profile, attaches credentials, opens the socket,
  revalidates every redirect against the same policy, and bounds bytes and time.
- An importer calls `open_input(input_ref)` and receives an `OpenedInput(input_ref,
  envelope_ref, body)`. The platform resolves the path inside an approved root — **after**
  symlink resolution — reads it under `max_input_bytes`, and hands over bytes.
- An importer receives no network capability. A normalizer receives neither network nor
  credential nor cursor.
- **A refusal cannot be swallowed.** A refusal is recorded when it is raised; a run that
  returns normally after one fails anyway, with the refusal's own reason. Transport
  *failures* are not treated this way — absorbing a timeout is a collection decision, but
  overruling a rule is not the add-on's to make.
- **A non-success status must be decided.** The add-on either raises (the status is a
  failure) or calls `accept_status(response, reason)` (the status is data). Returning
  normally without deciding fails the run. `reason` is required and is logged.

`[측정]` Unresolved: a source answering `200` with an error body is invisible to this rule.
The platform reads a status, not a meaning, and no real source in P0 behaved this way.

## §2 Raw and provenance

- **One envelope per original**, recorded by the platform **before** the add-on sees the
  bytes. Losslessness therefore does not depend on add-on quality: an add-on that carves a
  response badly has produced bad items over a preserved original.
- The envelope carries a REST response (`endpoint_ref`, `status`, `response_headers`,
  `request_summary`) or a local input (`input_ref`); the response-shaped fields are absent
  for an importer rather than faked.
- `request_summary` carries the URL without its query string. A query string is the part an
  add-on controls, and is therefore the part a log must not hold.
- **Every item names an envelope this run produced.** An item that does not is refused
  (`AddonOutputInvalid`): an extraction nobody can trace back is not checkable.
- Item payload is **the bytes as read**. Re-serialization is prohibited — it reorders keys
  and normalizes numbers, and Raw that differs from the source bytes is not lossless.
- Required provenance per envelope: `source_id`, `job_id`, `attempt_id`, `addon_id`,
  `addon_version`, `retrieved_at`, `body_sha256`, and either `endpoint_ref` or `input_ref`.

## §3 Transaction and idempotency boundary

`[결정]` DP-010. **All domain durable work runs inside the transaction that completes the
attempt, with the fenced completion last.**

- `emit_raw` and `advance_cursor` **buffer**. Nothing is written when they are called.
- The whole collection — every envelope, every item, the cursor — is handed to the
  completion transaction as one unit.
- A worker that lost its lease persists **neither Raw nor cursor**.
- The host must verify it is *inside* that transaction at the moment of writing, by asking
  the connection's transaction status. `[측정]` "Never commits" and "is inside the fence's
  transaction" are different properties, and P0 shipped the first believing it was the
  second.
- `envelope_ref` is a **run-scoped handle, not a row id**. The row does not exist while the
  add-on holds it.
- Idempotency keys: `platform_effect`'s primary key for platform effects;
  `normalized_result`'s unique index on (run, item) for normalization. **A rerun is a
  duplicate, not a version.**

## §4 Snapshot

- A snapshot **materializes** its members rather than referencing Raw rows, and records a
  manifest digest plus a digest per member.
- Verification checks both, and reports *which* failed — "the manifest digest differs" and
  "member 3 was edited" need different operator actions.
- A normalizer's input is a sealed snapshot and nothing else. Verification happens **before
  the add-on sees a byte**.
- A snapshot cannot hold one item key twice.
- Sealing is a **separate operator act** from collecting.

`[측정]` Unproved: replay across Raw-store *evolution*. No migration changed the Raw tables
after a snapshot was sealed. The design makes it plausible; nothing measured it.

## §5 Normalization

- Normalization is a **separate job**, started by an operator naming a sealed snapshot.
  Collection never starts it (DP-019 D6).
- Output is `Normalized Schema 0.2`: a common **envelope** (`schema_version`,
  `record_type`, `external_id`, provenance) and a **per-type body**, as a discriminated
  union. `record_type` ∈ {`document`, `trend_point`}.
- `[결정]` **`Normalized Schema 0.3` adds a third member, `product`**
  ([DP-028](../../docs/decisions/DP-028-schema-0-3-product-records.md)), for the dataset
  source DP-027 selected. It is additive: a 0.2 record is a valid 0.3 record, no existing
  normalizer bumps its `output_contract_version`, and no migration is required.
  `[확인 사실]` **No installed add-on emits a `product` record yet.** The decision is
  recorded; the implementation is TASK-008. Until that packet is accepted, this line states
  a contracted shape with no producer, and a reader should not take it as evidence that the
  dataset half of §1 has run.
- `[측정]` **The strong form of the schema hypothesis is refuted.** Across a blog document
  and a DataLab trend point the only overlap is identity, time, and provenance. Any P1 design
  assuming a common flat normalized table across heterogeneous sources is designing against
  measured evidence.
- **Determinism is required.** The same snapshot and the same normalizer version must
  produce byte-identical results after canonical serialization. A normalizer that reads a
  clock or a random source breaks this, and its context offers neither.
- `source_item_key` is required on every result: a result that cannot be traced to the
  sealed bytes is an interpretation nobody can check.
- **Versions coexist.** Two normalizer versions or two output-contract versions over one
  snapshot are two sets of rows, both readable. There is no "current" flag and no UPDATE
  path.

## §6 Source policy and outbound

- Requests go only to a host, port, path, and method the profile approved. Everything else
  is refused **by rule**, with a named reason an operator surface can render.
- Every redirect is revalidated by the same function that validated the first request.
  `[측정]` Path-range containment compares **resolved segments**, never string prefixes — a
  dot segment walked out of an approved range once.
- Resolved addresses are range-checked; **every** address must pass, not merely the first.
  Loopback requires an explicit per-source flag.
- One `fetch` has one deadline covering connect, request write, redirects, and body read.
  `[측정]` Socket timeouts alone do not bound a response: a server sending one byte per
  (timeout − ε) trips none of them.
- `max_pages` and `max_records` bound the run and are counted **by the platform**, not by
  the add-on.
- `max_request_bytes` counts bytes, including a body supplied as a sequence of chunks.
- `max_input_bytes` bounds one local input, checked **before** the first chunk.

`[측정]` Unresolved: rate limiting and `Retry-After` were never observed. No P0 evidence
describes what this contract should say about them.

## §7 Credential scope

- A credential is a set of **named parts**, each a secret-store **key name** filling one
  **protected** header, declared in the operator-approved profile.
- Resolution happens at the worker boundary, from a secret source **outside the repository
  working tree**. The platform refuses a secret-store path inside it.
- The source row stores a `credential_ref` that must match `^COSMA_SRC_[A-Z0-9_]+$` — a
  shape check, not a secrecy mechanism, so that pasting a real token in fails structurally.
- **An add-on never sees a credential**: not the value, not the key name, not the header
  name. No add-on's executable code may contain one, and this is scanned across **every**
  installed add-on, discovered from the filesystem rather than listed.
- Protected headers are stripped from anything recorded — envelopes, logs, API responses,
  and screens.

`[측정]` Unresolved: OQ-009 H1's query-parameter and signed-request cases. Only the header
case has evidence.

## §8 Operations

- Four operator actions, one per act: **collect, seal, normalize, read**. Sealing and
  normalizing are separate deliberate acts and must not be combined into one control.
- **Correlation is total**: every log line, attempt row, and API response concerning a job
  carries its `correlation_id`.
- An operator must be able to answer *what ran, on what input, in what state, why it failed,
  and what retry is safe* **without touching the database**.
- A refused retry states the current state and the required state, and leaves the job row
  unchanged field by field.
- A snapshot's verification state is its **own column**, never folded into a status word.
- Redaction is a single point. The redacted key set is fixed by contract, matched
  case-insensitively and by containment, and applies to logs, error summaries, and API
  responses alike.
- Required telemetry: job state transitions with timestamps; error class, retryability,
  summary, and protected detail; counters and durations for acquisition, parsing,
  persistence, snapshotting, and normalization; duplicate, invalid, skipped, missing-field,
  and manifest-hash evidence.

`[측정]` `claim_conflicts` is **not** a contention measure. P0 recorded this twice — once as
insensitivity, once as false positives — and P1 should not adopt it as one.

---

## Error behavior

| Error class | Trigger | Retryable | Durable state | Safe operator action |
|---|---|---|---|---|
| `PLATFORM_TRANSIENT` | transport failure, lease contention | yes | none written | wait for the retry |
| `PLATFORM_PERMANENT` | unregistered/disabled source, kind or add-on mismatch, refused request or input, unswallowed refusal, orphaned item | no | none written | fix the source row or the add-on, then re-run |
| `CONFIGURATION_INVALID` | stored config fails the declared schema; the host is assembled outside the completion transaction | no | none written | fix the configuration; the offending field names are carried |
| `ADDON_OUTPUT_INVALID` | miscounted output, wrong return type, undeclared cursor stream, item naming no envelope | no | none written | fix the add-on |
| `HANDLER_UNKNOWN` | no add-on for the job's handler | no | none written | install or enable the add-on |

`[결정]` Every one of these refuses **before** writing. There is no partial-write state to
reason about in any failure path this contract defines.

## Provenance and security

- Required provenance: source URL or input name, capture time, add-on identity and version,
  attempt lineage, payload digest.
- Data classes `public` / `local` / `private` per `data-handling.md`. **Redistribution
  permission and agent-processing permission are separate decisions**, and the second does
  not imply the first.
- A `local` source's payloads are not committed. The repository holds digests and retrieval
  instructions. A fixture shaped like `local` data is **generated** (DP-022), never redacted
  from a real capture.
- `SEC-006` is **waived for P0 only** (DP-023) and must be satisfied before P1 runs against
  real sources.

## Acceptance criteria

- Related acceptance scenario IDs: JOB-001…008, OPS-001…004, SEC-001…004 in
  [`tests/acceptance/`](../../tests/acceptance/). ⚠️ Those `SEC-00N` are **scenario** ids and
  are not the `SEC-00N` requirement ids in `p0-security.md`; cite through that file's mapping
  table.
- Required deterministic result: identical snapshot and normalizer version → byte-identical
  canonical output; a rerun refused rather than doubled.
- Required failure evidence: [`B4-SCENARIO-COVERAGE.md`](../../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md),
  including its `NOT EXERCISED` rows.

## Known limitations and unresolved semantics

`[확인 사실]` **Two of the seven are struck through and still binding, which is a shape worth
naming rather than leaving to be inferred.** A struck heading means *the limitation as first
written no longer holds*; the text beneath it is not commentary but the constraint that
replaced it, and it binds. Items 3 and 5 are both in that form as of 2026-08-20. `[결정]` They
are struck rather than deleted because a reader comparing this contract to the gate record
needs to see that each limitation existed and when it stopped applying — but the form is a
compromise, and a `0.2` of this contract should carry them as ordinary items with dated
history instead. Raised as F5 by
[`ADVERSARIAL-REVIEW-2026-08-20-CONSOLIDATION.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-CONSOLIDATION.md).

1. **The acquisition seam may move.** [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md)
   proposes that acquisition leave the service entirely. That would rewrite §1.
2. **Judgments only an add-on can make are unchecked** ([OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md)).
3. ~~**No real dataset source exists.** §1's importer half is proved as a mechanism only.~~
   `[측정]` **Closed 2026-08-20.** Open Beauty Facts delta exports pass through the installed importer into Raw, a sealed snapshot, and `normalizer.obf.product@0.1` at contract `0.3`, over the host path. Struck rather than deleted: a reader comparing this contract to the gate record needs to see that the limitation existed and when it stopped applying.
   `[결정]` **What replaces it is narrower and still binding.** The source holds zero Korean sunscreen and zero Korean toner rows ([DP-027](../../docs/decisions/DP-027-dataset-standard-and-share-alike.md) D2), so P0 has a working dataset path and **no product-relevant dataset evidence**. ODbL's share-alike attaches on first publication, which P1 inherits (D3).
4. **Multi-stream cursors are refused, not answered** ([OQ-010](../../docs/open-questions/OQ-010-cursor-stream-read-back.md)).
5. ~~**Snapshot replay across Raw-store evolution is unproved** (§4).~~
   `[측정]` **Exercised 2026-08-20 and true in a narrower form than this line assumed.** A sealed snapshot replays byte-identically across an additive migration, a superseding collection, and a purge of every Raw row. `[측정]` But against the reference design [OQ-004](../../docs/open-questions/OQ-004-snapshot-boundary.md) names — references fixed at seal — **only the purge separates the two designs**. `[결정]` Two gaps replace it and both bind: member selection under an `emitted_at` tie falls to a `uuid4`, and `emitted_at` is a *transaction* timestamp; and D5's ordering fixes no collation, so two clusters differing only in locale seal different manifests from identical Raw. `[확인 사실]` Struck 2026-08-20 together with limitation 3; an earlier revision of this list struck 3 alone and left this one contradicting it.
6. **Rate limiting, deep pagination, redirects, and drift are unobserved against a real
   source** (§6).
7. **`200`-with-an-error-body has no real subject** (§1).
