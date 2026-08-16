# P0 Charter — Disposable Integrated Architecture Prototype

- Status: `ACCEPTED_FOR_POC`
- Owner: Project team
- Provisional timebox: 10 active working days from the recorded M2 start
- Confirmation point: M1 exit review, before entering M2
- Provisional midpoint review: after 5 active working days
- Exit mechanism: Architecture Synthesis Gate

The stage definitions and gate conditions are maintained in [Project State](project-state.md#delivery-lifecycle).

## Purpose

P0 exists to expose architecture problems with real data and realistic failure behavior. It is not a preview of production quality and is not the codebase from which P1 will be incrementally hardened.

## Required end-to-end flows

1. Register and manually run one REST API source.
2. Import one existing dataset from a supported file format.
3. Preserve both as untrusted, lossless Raw artifacts and observations.
4. Re-run identical and changed input to observe identity and duplicate policy.
5. Create a sealed normalization snapshot independently from collection.
6. Run a deterministic rule-based normalizer against the snapshot.
7. Store versioned normalized results with Raw-to-result lineage.
8. Use a minimal dashboard to create, observe, inspect, and retry work.
9. Exercise multiple workers, retryable failures, permanent failures, and interrupted work.

## Architecture questions P0 must answer

- Can one Raw envelope preserve both REST and dataset inputs without semantic loss?
- Where are the correct transaction and idempotency boundaries?
- Does the proposed job state machine support independent collection and normalization recovery?
- Does the sealed snapshot protect reproducibility from Raw-store evolution?
- Which component and process boundaries are useful rather than ceremonial?
- Which dashboard actions and telemetry are actually needed to operate the pipeline?
- Which normalized fields survive contact with both real sources?

## Required instrumentation

- Structured logs with correlation, job, run, source, and attempt identifiers.
- Job state transitions and timestamps.
- Error class, retryability, summarized message, and protected debug detail.
- Counters and durations for acquisition, parsing, persistence, snapshotting, and normalization.
- Duplicate, invalid, skipped, and missing-field counts.
- Input and output record counts plus manifest hashes.

## Minimum safety boundary

P0 follows the active [P0 Security Baseline](conventions/p0-security.md). In particular:

- bind operator surfaces to localhost by default;
- accept only registered source identifiers rather than arbitrary operator-supplied URLs;
- restrict outbound requests by source-specific HTTPS host policy and bounded network behavior;
- resolve credentials at the worker boundary and persist only references;
- redact secrets and protected source data from logs, traces, errors, screenshots, and fixtures.

Production IAM and secret-management products remain non-goals. The minimum safety boundary is an invariant, not a production platform selection.

## Failure scenarios

P0 must deliberately exercise:

- REST timeout and rate limiting;
- malformed or partially invalid dataset rows;
- process interruption after acquisition but before completion acknowledgement;
- duplicate job delivery;
- two workers attempting to claim work concurrently;
- normalization failure after Raw persistence;
- snapshot or manifest mismatch;
- a provider result that fails output validation.

## Exit criteria

P0 may end when all of the following are true:

- One REST source and one dataset complete the end-to-end flow.
- Source rights or permitted experimental use are recorded.
- Identical input replay demonstrates the chosen idempotency behavior.
- Changed source content creates a traceable new observation or version.
- Parallel worker claims do not corrupt job state or create uncontrolled duplicate effects.
- Collection and normalization failures can be recovered independently.
- A sealed snapshot replays the same exact normalizer input and detects tampering.
- Different normalizer or schema versions can coexist for the same Raw lineage.
- The dashboard identifies what ran, its input, its state, its failure, and its retry action without direct database inspection.
- Required `SEC` acceptance scenarios pass without exposing the P0 beyond its declared local boundary.
- The team can answer the Architecture Questions above and write `PoC Contract 0.1`.

Passing a performance target or producing polished UI is not required to exit P0.

## Preservation policy

### Eligible for deliberate promotion

- Source capability matrices and Decision Packets.
- Redistributable, representative, hashed fixtures.
- Acceptance scenarios and deterministic expected outputs.
- Error taxonomy and state-machine observations.
- Accepted versioned schemas and API contracts.
- Architecture Synthesis and rejected-alternative records.

### Not promoted by default

- P0 backend and dashboard implementation modules.
- P0 database migrations.
- Source-specific hard-coded shortcuts.
- Temporary UI structure and styling.
- Experimental orchestration and deployment files.

P0 will be archived by Git tag or equivalent history. “Discard” means no automatic code promotion, not evidence destruction.

## Non-goals

- Production SLA, multi-region operation, or high availability.
- Kafka, Kubernetes, fine-grained MSA, or distributed database design.
- Final ontology or `Normalized Schema 1.0`.
- ML or LLM model selection.
- Production identity provider or secret-management product selection.
- Broad source coverage, forecasting, autonomous agents, or polished UX.
