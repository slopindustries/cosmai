# P0 Charter — Disposable Two-Part Architecture Prototype

- Status: `ACCEPTED_FOR_POC`
- Owner: Project team
- Timebox: recorded separately for P0-A and P0-B before each experiment becomes `RUNNING`
- Midpoint review: defined in each stage experiment record
- Exit mechanism: P0-B P1 Entry Gate

The stage definitions and gate conditions are maintained in [Project State](project-state.md#delivery-lifecycle). The binding order is defined by [DP-005](decisions/DP-005-two-part-pre-p1-execution.md) and the [P0 Execution Plan](p0-execution-plan.md).

## Purpose

P0 exists to expose architecture problems through executable platform failures and later real acquisition and normalization behavior. It is not a preview of production quality and is not the codebase from which P1 will be incrementally hardened.

## Binding execution order

```text
P0-A — source- and normalization-independent platform core
→ P0-A Completion Gate
→ P0-B — source exploration, domain contracts, concrete integration, real-data evidence
→ Architecture Synthesis and artifact disposition inside P0-B
→ PoC Contract 0.1 and P1 reconstruction plan
→ P1 Entry Gate
→ P1 clean reconstruction
```

Source selection and every acquisition-, Raw-, snapshot-, and normalization-specific artifact belong to P0-B. P0-A must not create domain interfaces, contracts, fixtures, test doubles, or implementations under generic names.

## P0-A required platform core

P0-A must provide executable and tested:

- PostgreSQL runtime connection, migration mechanism, and source-neutral transaction foundations;
- handler-neutral job orchestration with claims, leases, attempts, retry scheduling, terminal states, interruption, and recovery;
- API and worker process lifecycle, health, configuration validation, and safe shutdown;
- source-neutral dashboard control for platform health, generic job state, logs, metrics, failure inspection, and safe retry;
- structured logs, metrics, correlation, redaction, loopback binding, and secret-store location guards;
- deterministic synthetic handlers and failure injectors that do not imitate collection, import, Raw, snapshot, or normalization behavior.

### P0-A exit criteria

- Parallel job claims do not create conflicting active ownership.
- Duplicate execution does not produce an uncontrolled platform-level durable effect.
- Interrupted or expired work reaches a documented recoverable or final state.
- Retry exhaustion produces an observable terminal state.
- The operator can inspect and safely retry generic work without direct database access.
- Logs, metrics, errors, and screenshots preserve the declared redaction boundary.
- Operator surfaces bind to loopback by default.
- The platform rejects a secret-store path inside the repository working tree.
- The gate lists every acquisition and normalization behavior deferred to P0-B.
- The P0-A Completion Gate records `GO` or an explicitly accepted `CONDITIONAL GO`.

P0-A completion is not evidence that a real collector, dataset importer, Raw model, snapshot, or normalizer will work.

## P0-B required domain flow

P0-B must:

1. explore and measure a bounded REST API and dataset candidate set;
2. record rights and agent-processing basis, replay instructions, profiles, fixtures or hashes;
3. select one REST source and one dataset through `GO` or explicitly accepted `CONDITIONAL GO`;
4. record a provisional decision consumer, output unit, evidence requirement, uncertainty representation, and human-review boundary;
5. version experimental acquisition, Raw, snapshot, normalization, source-policy, credential-scope, operations, and error contracts;
6. define and test the smallest collector, importer, and normalizer interfaces and test doubles;
7. implement one selected REST collector, one selected dataset importer, and one deterministic `rule-baseline@0.1` normalizer;
8. preserve both input modes as untrusted, lossless Raw artifacts and observations;
9. re-run identical and changed input to observe identity and duplicate policy;
10. create a sealed normalization snapshot independently from collection;
11. store versioned normalized results with Raw-to-result lineage;
12. operate, inspect, diagnose, and safely retry the domain flow through the dashboard;
13. exercise multiple workers and realistic domain failures;
14. synthesize the evidence, classify P0 artifacts, accept `PoC Contract 0.1`, and accept a P1 reconstruction plan.

## Architecture questions P0 must answer

- Did the P0-A platform boundary survive P0-B without material replacement?
- Can one Raw envelope preserve both REST and dataset inputs without semantic loss?
- Where are the correct transaction and idempotency boundaries for platform and domain effects?
- Does the job state machine support independent collection and normalization recovery?
- Does the sealed snapshot protect reproducibility from Raw-store evolution?
- Which component and process boundaries are useful rather than ceremonial?
- Which dashboard actions and telemetry are actually needed to operate the pipeline?
- Which normalized fields survive contact with both real sources?

## Required instrumentation

- Structured logs with correlation, job, run, source, and attempt identifiers where those identifiers exist.
- Job state transitions and timestamps.
- Error class, retryability, summarized message, and protected debug detail.
- Counters and durations for platform execution and, in P0-B, acquisition, parsing, persistence, snapshotting, and normalization.
- In P0-B, duplicate, invalid, skipped, missing-field, input, output, and manifest-hash evidence.

## Minimum safety boundary

P0 follows the active [P0 Security Baseline](conventions/p0-security.md).

P0-A must enforce loopback defaults, redaction, protected debug behavior, and repository-external secret-store location without resolving a real source credential or defining a source policy.

Before the first P0-B external probe, the project must apply Data Handling, narrow the agent sandbox, and record the exact external-input boundary. P0-B must then use registered source identifiers, bounded HTTPS host policies, redirect and DNS revalidation, response and timeout limits, credential references, and protected evidence handling.

Production IAM and secret-management products remain non-goals.

## Failure scenarios

### P0-A

- two workers attempt to claim one generic job;
- duplicate generic execution;
- interruption before and after a platform-level durable effect;
- lease expiry and retry exhaustion;
- invalid configuration, unsafe secret-store path, redaction, and loopback exposure checks.

### P0-B

- REST timeout and rate limiting;
- malformed or partially invalid dataset rows;
- interruption after acquisition but before completion acknowledgement;
- duplicate domain-job delivery;
- normalization failure after Raw persistence;
- snapshot or manifest mismatch;
- a provider result that fails output validation;
- source-policy, redirect, DNS, response-bound, credential, and protected-debug failures.

## P0-B exit criteria

P0 may end only when all of the following are true:

- One REST source and one dataset complete the end-to-end flow.
- Source rights or permitted experimental use are recorded.
- Identical input replay demonstrates the chosen idempotency behavior.
- Changed source content creates a traceable new observation or version.
- Parallel worker claims do not corrupt job state or create uncontrolled duplicate effects.
- Collection and normalization failures can be recovered independently.
- A sealed snapshot replays the same exact normalizer input and detects tampering.
- Different normalizer or schema versions can coexist for the same Raw lineage.
- The dashboard identifies what ran, its input, state, failure, and retry action without direct database inspection.
- Required platform and domain `SEC` scenarios pass within the declared local boundary.
- Every Architecture Question is answered with evidence or an explicit unresolved blocker.
- The Architecture Synthesis, artifact disposition register, `PoC Contract 0.1`, and P1 reconstruction plan are accepted.

Passing a performance target or producing polished UI is not required.

## Preservation and disposition policy

Every material artifact receives one explicit outcome in the P0 Artifact Disposition Register:

- `PROMOTE`;
- `REBUILD_FROM_CONTRACT`;
- `ARCHIVE_REFERENCE_ONLY`;
- `DELETE_AFTER_EVIDENCE_CAPTURE`;
- `UNRESOLVED`.

P0 implementation modules, migrations, temporary UI, source-specific shortcuts, and experimental orchestration are `ARCHIVE_REFERENCE_ONLY` by default. P0 is archived by Git tag or equivalent history. No P0 implementation may become a P1 runtime or package dependency.

Accepted contracts, scenarios, eligible fixtures, decisions, error taxonomies, and evidence may be deliberately promoted. Runtime Raw data, restricted downloads, local databases, caches, and protected logs follow their rights, classification, retention, and deletion records. “Discard” never means destroying the evidence required to justify a decision.

## Non-goals

- Production SLA, multi-region operation, or high availability.
- Kafka, Kubernetes, fine-grained MSA, or distributed database design.
- Final ontology or `Normalized Schema 1.0`.
- ML or LLM model selection.
- Production identity provider or secret-management product selection.
- Broad source coverage, forecasting, autonomous agents, or polished UX.
