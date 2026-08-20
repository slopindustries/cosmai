# OQ-004 — Sealed Snapshot Boundary

- Status: `RESOLVED`
- Priority: P0-B — required domain evidence for the P1 contract
- Owner: Project team
- Blocks: reproducibility and storage contract
- Related experiments: not started
- Resolution Decision Packet: [DP-029](../decisions/DP-029-p1-snapshot-identity.md)

## Question

What exact data and metadata must be materialized so a normalization run can distrust future Raw-store state and still replay its original input?

## Why this cannot be decided yet

The project has not yet materialized real Raw observations, replayed normalization after Raw changes, or tested tamper detection across a storage representation boundary.

## Scope

### Included

- Snapshot item bytes, manifest, identity, hashes, selection description, contract versions, lineage, replay, and tamper detection.

### Excluded

- Final database or object-store topology, backup platform, multi-region replication, and production retention policy.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: A materialized item set, canonical bytes, manifest, hashes, selection description, and contract versions are sufficient for replay. | An unmodified snapshot cannot reproduce identical verified normalizer input, or replay requires unrecorded Raw-store state. |
| H2: Snapshot identity can remain independent of the storage backend. | Moving the exact bytes and manifest to another tested backend changes the logical snapshot identity or prevents integrity verification. |
| H3: P0 can test the boundary without deciding the future storage topology. | Every feasible P0 representation embeds backend-specific identity or behavior that prevents the required replay and tamper experiment. |

## Alternatives

- Preserve only references to append-only Raw observations.
- Materialize snapshot items and manifest in PostgreSQL.
- Materialize a backend-neutral artifact and manifest outside the Raw query path.

## Minimum experiment

- Use P0-B fixture-derived Raw observations to implement and test sealed snapshot creation.
- Run a normalizer test double and record all inputs and hashes.
- Add later Raw observations and simulate a changed Raw-store projection.
- Replay only from the snapshot.
- Tamper with one snapshot item and confirm detection.
- Create snapshots from observations produced by the concrete collector and importer.
- Run the concrete normalizer twice from the same snapshot and verify identical, hash-verified input.

All snapshot contracts, test doubles, persistence, and measurements belong to P0-B. P0-A must not create a snapshot abstraction under another name.

## Evidence

- Manifest completeness.
- Replay equality.
- Tamper-detection result.
- Storage size and creation duration.
- Lineage from selection to snapshot item to normalized result.

### What P0-B measured, 2026-08-20

`[측정]` **The exit condition's middle clause is now met for the re-query design.** TASK-005
built the minimum experiment this question asked for — *"add later Raw observations and
simulate a changed Raw-store projection; replay only from the snapshot"* — and drove a
read-time re-query of `raw_item` beside the sealed reading over one timeline: at the seal,
after an additive migration, after a later collection that supersedes a sealed key, and after
a purge of every Raw row. The sealed snapshot verifies and replays byte-identically at all
four steps; the re-query design replays different bytes at step three and nothing at step
four. Independently reproduced, and the discrimination survives four mutations of the seal
and read.

`[측정]` **Against this question's *first* alternative it is narrower than that.**
`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-B implemented the reference design this
question actually names — *"preserve only references to append-only Raw observations"*,
ordinals and row ids fixed at seal with bytes fetched at read — and it agrees with the sealed
design at the seal, after the migration, **and after the later collection**. Only the purge
separates them. So a materialized snapshot beats a re-query, and beats a reference design
only when the referenced rows are gone.

`[측정]` **A purge does not discharge an erasure obligation.** After `delete from raw_item`,
`snapshot_item` still holds the bytes and the manifest still verifies — and `raw_envelope`,
the lossless original the items were carved from, is untouched. So deleting Raw rows leaves
**two** further copies. `[추론]` This bears on DP-005's `DELETE_AFTER_EVIDENCE_CAPTURE`, which
assigns the disposition to the local database rather than to rows: whatever discharges an
erasure obligation, it is not one `delete` against `raw_item`. Recorded here because a
snapshot's persistence is the property this question owns, and this is its cost.

`[확인 사실]` **Still unmeasured: backend-independent identity.** D5's *"ordered by
`item_key`"* fixes no collation, so two clusters differing only in locale seal different
manifests from identical Raw — see the note added to
[DP-019](../decisions/DP-019-normalized-schema-0-1-and-results.md) D5. This question's H2 is
where that belongs.

`[측정]` **Which member wins when two observations of one key are sealed together is decided
by `emitted_at`, and `emitted_at` is a transaction timestamp.** Measured 2026-08-20 by the
attacker on [TASK-007/TASK-010](../agent-workflow/task-packets/TASK-010-obf-real-snapshot-normalized.md)
(`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md` F2), on real Open Beauty Facts rows:

- Two imports 59 ms apart produced distinct `emitted_at` values, `emitted_at desc` decided, and
  all three overlapping members were byte-identical to the later delta's lines. The known
  `uuid4` tie-break did **not** produce this result — that was checked, not assumed.
- `[측정]` Forcing the two `emitted_at` values equal and re-sealing 12 times drops the decision
  to `id desc` on a `uuid4`, and **2 of the 3 keys then selected the older payload**.

`[확인 사실]` `emitted_at` defaults to `now()`, which in PostgreSQL is the **transaction**
timestamp, not the statement's. `[추론]` So "the later import wins" holds per *import
transaction* and not per row, and nothing in the tests, the contract, or `DP-019` D5 states
that two imports must be separate transactions. A batching change that put two imports in one
transaction would make snapshot member selection non-deterministic without any test noticing.

`[결정]` Recorded here rather than repaired: this question owns snapshot member identity, the
P0 evidence stands as measured, and the repair — an explicit ordering key, or a stated
constraint that one import is one transaction — is a contract decision P1 makes. It joins
TASK-003's two open items, which named the same tie-break from the other direction.

## Exit condition

Two independent runs consume identical verified input from the same snapshot, later Raw changes do not affect the input, and corruption is detected before normalization.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution records the accepted identity and manifest contract, tested storage representation, evidence, and remaining future-topology uncertainty.

Resolved for P1 on 2026-08-21 by [DP-029](../decisions/DP-029-p1-snapshot-identity.md). D1
closes materialization: a P1 snapshot copies member bytes at seal rather than referencing
`raw_item`. D2 closes the same-key tie: an explicit monotonic `bigint` sequence on
`raw_item` selects the maximum-sequence row, replacing the `emitted_at`/`uuid4` behavior
measured above. D3 closes manifest-member ordering: a fixed UTF-8 bytewise comparison,
independent of collation. The measurements recorded above stand as the evidence for all
three and are preserved rather than superseded. DP-029 D4 additionally routes the erasure
obligation this question surfaced — a purge leaving `snapshot_item` and `raw_envelope`
copies behind — to [`SR-003`](../conventions/security-recommendations.md) as an
unimplemented, explicitly-scoped P1 gap rather than closing it here.
