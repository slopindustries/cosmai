# OQ-004 — Sealed Snapshot Boundary

- Status: `OPEN`
- Priority: P0 — required evidence for the P1 contract
- Owner: Project team
- Blocks: reproducibility and storage contract
- Related experiments: not started
- Resolution Decision Packet: not created

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

- Select Raw observations and create a sealed snapshot.
- Run normalization and record all inputs and hashes.
- Add later Raw observations and simulate a changed Raw-store projection.
- Replay only from the snapshot.
- Tamper with one snapshot item and confirm detection.

## Evidence

- Manifest completeness.
- Replay equality.
- Tamper-detection result.
- Storage size and creation duration.
- Lineage from selection to snapshot item to normalized result.

## Exit condition

Two independent runs consume identical verified input from the same snapshot, later Raw changes do not affect the input, and corruption is detected before normalization.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution records the accepted identity and manifest contract, tested storage representation, evidence, and remaining future-topology uncertainty.
