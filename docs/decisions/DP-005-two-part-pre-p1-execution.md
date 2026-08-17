# DP-005 — Two-Part Pre-P1 Execution

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-17
- Owners: Project team
- Supersedes: [DP-004](DP-004-p0-implementation-order.md)
- Related Open Questions: OQ-001 through OQ-007
- Affected contracts: all P0 experimental contracts and future `PoC Contract 0.1`
- Affected acceptance tests: `ACQ`, `RAW`, `JOB`, `SNP`, `NRM`, `OPS`, `SEC`

## Decision question

How should all work before P1 be divided when source selection, acquisition, Raw semantics, snapshotting, and normalization must remain together rather than shape the platform core in advance?

## Evidence and reasoning

- `[확인 사실]` No REST source or dataset has been selected, and no integrated P0 implementation has executed.
- `[확인 사실]` OQ-001 through OQ-007 remain open.
- `[결정]` The project owner requires all collector, dataset importer, source-selection, and normalizer-related work to occur in the second part of pre-P1 execution.
- `[추론]` Selecting sources or defining acquisition and normalization contracts in the first part would violate that boundary even if the concrete adapters were deferred.
- `[가설]` A source- and normalization-independent platform core can expose useful execution, recovery, operator, and safety evidence before the domain pipeline is introduced. This is falsified if P0-B cannot integrate without materially replacing a P0-A boundary that P0-A claimed as complete.

## Decision

`[결정]` Replace the M0/M1/M2/M3 delivery sequence with two active pre-P1 stages:

1. `P0-A — Platform Core Construction and Verification`
2. `P0-B — Domain Integration, Evidence Synthesis, and Disposition`

P1 begins only after P0-B accepts `PoC Contract 0.1`, the artifact disposition register, and the P1 reconstruction plan.

## P0-A boundary

P0-A implements and verifies only platform behavior that does not require a selected source, dataset, Raw observation model, snapshot meaning, normalized schema, or normalizer provider.

### Included

- repository and development-environment readiness;
- PostgreSQL runtime connection, migration mechanism, and source-neutral transaction foundations;
- a handler-neutral job execution model with claims, leases, attempts, retry scheduling, terminal states, interruption, and recovery;
- API and worker process lifecycle, health, and control foundations;
- a source-neutral operator dashboard for platform health, generic job state, logs, metrics, and correlation;
- structured logging, metrics, correlation, redaction, loopback binding, and secret-store location guards;
- deterministic synthetic handlers and failure injectors that test platform execution without imitating collection or normalization;
- replayable `JOB`, platform-level `OPS`, and platform-level `SEC` acceptance evidence.

### Excluded

- REST API and dataset candidate exploration, access, rights review, profiling, selection, and source fixtures;
- source registration semantics, concrete outbound host policies, source credential authorization, pagination, rate, record mapping, and source identity;
- collector and dataset-importer interfaces, contracts, test doubles, and implementations;
- Raw response, Raw record, observation identity, duplicate, and changed-source-content contracts or implementations;
- normalization decision use, Schema 0.x, provider protocol, normalizer test doubles, rules, and result persistence;
- normalization snapshot, manifest, Raw-to-result lineage, and domain-specific dashboard behavior;
- `ACQ`, `RAW`, `SNP`, `NRM`, and domain-specific `OPS` or `SEC` acceptance claims.

P0-A must not create a generic acquisition or normalization framework under another name. A platform seam is allowed only when its behavior is independently testable without source or normalization semantics.

## P0-A Completion Gate

P0-A ends only when an accepted gate record links:

- the tested code revision and environment;
- executable database, migration, API, worker, dashboard, telemetry, and security foundations;
- handler-neutral job concurrency, duplicate execution, interruption, retry exhaustion, lease recovery, and terminal-state results;
- platform-level operator diagnosis and safe retry results;
- loopback, redaction, secret-store location, and protected-debug evidence;
- every source and normalization behavior deliberately deferred to P0-B;
- failures classified as implementation, specification, assumption, evaluation, or goal failures;
- a bounded P0-B entry plan with no claim that P0-A proved acquisition or normalization behavior.

The gate does not require a selected REST source, dataset, source fixture, acquisition contract, normalizer contract, or concrete-component interface.

## P0-B boundary and order

P0-B owns the complete source and normalization domain. It proceeds in this order:

1. explore bounded REST API and dataset candidates;
2. record rights, agent-processing permission, replay procedures, profiles, fixtures or hashes, and select one REST source and one dataset;
3. record a provisional decision consumer, output unit, evidence requirement, uncertainty representation, and human-review boundary;
4. draft and version experimental acquisition, Raw, snapshot, normalization, source-policy, credential-scope, operations, and error contracts;
5. define the smallest collector, importer, and normalizer interfaces and test doubles needed to test those contracts;
6. implement the selected REST collector, dataset importer, and deterministic `rule-baseline@0.1` normalizer;
7. run component, contract, real-data integration, failure, replay, tamper, concurrency, and operator scenarios;
8. classify any failure before changing an implementation or contract, reopening the affected P0-A boundary when its premise is falsified;
9. synthesize the architecture evidence, accept or reject alternatives, and write `PoC Contract 0.1`;
10. classify every material P0 artifact and runtime dataset for promotion, reconstruction, archive-only retention, deletion, or unresolved carry-forward;
11. accept a P1 reconstruction plan and enter P1.

P0-B may use internal readiness reviews, but they do not create a third delivery stage.

## Artifact disposition

Every material P0 artifact receives one of these explicit outcomes:

- `PROMOTE`: accepted contract, acceptance scenario, eligible fixture, decision, or evidence artifact;
- `REBUILD_FROM_CONTRACT`: behavior required in P1 but implemented again from the accepted contract;
- `ARCHIVE_REFERENCE_ONLY`: P0 implementation retained by Git tag or equivalent history but prohibited as a P1 runtime or package dependency;
- `DELETE_AFTER_EVIDENCE_CAPTURE`: runtime Raw data, restricted downloads, temporary databases, caches, or protected logs removed after required metadata, hashes, and retention evidence are recorded;
- `UNRESOLVED`: evidence is insufficient and the item remains an explicit P1 Open Question or blocker.

DP-001 remains binding: P0 implementation modules are not promoted into P1 by default, and P1 is reconstructed from accepted contracts and evidence.

## Tradeoffs and controls

- Benefit: the first part is not shaped by an unselected source or provisional normalization semantics.
- Cost: P0-B carries all domain discovery, contract, implementation, and real-data work.
- Risk: a platform abstraction created in P0-A may prove unusable in P0-B.
- Control: keep P0-A seams minimal, record assumptions, and reopen the gate when P0-B falsifies them.
- Risk: source discovery late in the lifecycle may expand scope.
- Control: bound the candidate set, require hard rights and replay gates, and remove scope rather than treating missing evidence as a pass.
- Reversibility: full inside disposable P0; P1 still starts from accepted contracts rather than P0 code.

## Required changes

- Replace the active M2 execution plan with a two-part P0 execution plan.
- Replace the Collector/Normalizer Implementation Gate with a P0-A Completion Gate.
- Move OQ-001 and every acquisition- or normalization-specific contract, test double, implementation, and acceptance claim into P0-B.
- Treat Architecture Synthesis and artifact disposition as P0-B exit work rather than a separate delivery stage.
- Update agent instructions, repository guides, Open Questions, experiments, contracts, security notes, and acceptance-test routing.
