# P0 Execution Plan — Platform First, Domain Integration Second

- Status: `ACCEPTED_FOR_POC`
- Governing decision: [DP-005](decisions/DP-005-two-part-pre-p1-execution.md)
- Applies to: disposable P0 under `experiments/integrated-p0/` and source probes under `experiments/source-probes/`
- Last updated: 2026-08-17

## Purpose

All work before P1 is organized into two delivery stages. P0-A builds a source- and normalization-independent platform core. P0-B selects the real inputs, defines and implements the complete acquisition and normalization domain, verifies it with real data, synthesizes the evidence, and decides the disposition of P0 artifacts before P1 reconstruction.

Internal work packages are sequencing aids, not additional lifecycle stages.

## Stage summary

| Stage | Purpose | Required output | Source or normalization work allowed? | Exit |
|---|---|---|---|---|
| P0-A — Platform Core Construction and Verification | Build and test only infrastructure whose behavior is meaningful without a selected source or normalization contract. | Executable platform core, synthetic-handler failure evidence, and accepted P0-A Completion Gate. | No. | Platform `JOB`, `OPS`, and `SEC` obligations pass or carry an explicit accepted blocker. |
| P0-B — Domain Integration, Evidence Synthesis, and Disposition | Select inputs; define, implement, and test acquisition and normalization; then decide what P1 inherits as evidence or contract. | Source decisions, domain contracts, concrete components, real-data evidence, Architecture Synthesis, disposition register, `PoC Contract 0.1`, and P1 reconstruction plan. | Yes; all such work belongs here. | P0 Charter exit criteria and P1 Entry Gate are answered or explicitly blocked. |
| P1 — Clean Reconstruction | Rebuild from accepted contracts and promoted evidence. | Continuously operable prototype baseline. | Defined by the future P1 charter. | Not defined by P0. |

## P0-A work packages

### A1 — Baseline and experiment boundary

- close repository, toolchain, local PostgreSQL, Node, and test-runner readiness gaps;
- create the integrated P0-A experiment record from `experiments/EXPERIMENT-TEMPLATE.md`;
- fix the platform hypotheses, falsification conditions, procedures, evidence locations, stopping rules, and timebox;
- draft only source-neutral platform contracts and `JOB`, platform `OPS`, and platform `SEC` scenarios;
- record every acquisition, Raw, snapshot, normalization, and source-policy behavior as deferred.

### A2 — Platform core implementation

Implement under `experiments/integrated-p0/`:

1. PostgreSQL connection, migrations, source-neutral transaction foundations, and test isolation.
2. Handler-neutral job creation, claim, lease, attempt, retry scheduling, terminal state, interruption, and recovery.
3. API and worker lifecycle, health, configuration validation, and safe shutdown.
4. A source-neutral dashboard for platform health, generic job state, correlated logs and metrics, failure inspection, and safe retry.
5. Structured logs, metrics, correlation identifiers, redaction, loopback defaults, and secret-store location guards.
6. Synthetic handlers and failure injectors for success, retryable failure, permanent failure, duplicate execution, interruption, and invalid platform configuration.

Do not add source registration, outbound requests, acquisition payloads, Raw observation semantics, snapshots, normalized results, collector/importer/normalizer ports, or domain-shaped test doubles.

### A3 — Platform verification

At minimum verify:

- two workers cannot hold conflicting active ownership of one job;
- duplicate execution does not create an uncontrolled platform-level durable effect;
- interruption and lease expiry lead to a documented recoverable or final state;
- retries exhaust into an observable terminal state;
- operator diagnosis and safe retry work without direct database inspection;
- logs, errors, metrics, and screenshots preserve redaction;
- operator surfaces bind to loopback by default;
- the secret-store path cannot resolve inside the repository working tree;
- the evidence makes no claim about collection, Raw, snapshot, or normalization correctness.

Record direct outcomes as `[측정]` and classify failures before changing code or expectations.

### A4 — P0-A Completion Gate

Complete `experiments/integrated-p0/PLATFORM-CORE-GATE-TEMPLATE.md`. A `GO` or accepted `CONDITIONAL GO` is required before P0-B begins. The gate reviews platform evidence and the deferred-domain inventory; it does not select a source or approve a collector or normalizer.

## P0-B work packages

### B1 — Source exploration and selection

- define a bounded REST API and dataset candidate set;
- read and apply the Data Handling Convention and P0 Security Baseline before external access;
- narrow the agent sandbox before the first outbound probe;
- complete Source Capability Profiles and the Source Selection Matrix;
- record rights, agent-processing permission, replay procedures, hashes, capture time, schema, identity, rate, update, missingness, and duplicate behavior;
- select one REST source and one dataset through `GO` or explicitly accepted `CONDITIONAL GO`.

Probe code is disposable measurement code. It is not the integrated collector or importer and cannot be promoted into one silently.

### B2 — Decision use and domain contracts

- record a provisional decision consumer, trigger, output unit, evidence requirement, uncertainty representation, and human-review boundary;
- inspect representative source records;
- version experimental acquisition, Raw, job/error specialization, snapshot, normalization, operations, source-policy, and credential-scope contracts;
- draft `ACQ`, `RAW`, `SNP`, `NRM`, domain `OPS`, and domain `SEC` scenarios;
- define the smallest collector, importer, and normalizer interfaces and test doubles needed to challenge those contracts;
- record test-double limitations and real-source behaviors requiring direct verification.

Contracts and test doubles created here are hypotheses. They do not count as real-integration evidence.

### B3 — Concrete implementation

Implement only the selected pair and the bounded deterministic baseline:

- one REST collector with required authentication, pagination, rate, retry, response, identity, and mapping behavior;
- one dataset importer with required format, encoding, row identity, invalid/missing-row, duplicate, and changed-version behavior;
- one deterministic `rule-baseline@0.1` normalizer consuming a sealed snapshot and producing validated versioned results;
- the Raw, snapshot, result-lineage, source-policy, credential-scope, and domain dashboard behavior required by the accepted experimental contracts.

Run isolated component and contract tests before connecting each component to the platform core.

### B4 — Real-data integration and failure evidence

Run the required P0 flow and deliberately exercise:

- identical and changed input;
- retryable and permanent source failures;
- malformed and partially invalid dataset rows;
- duplicate delivery and process interruption around durable effects;
- parallel claims and lease recovery;
- normalization failure after Raw persistence;
- snapshot or manifest mismatch;
- invalid normalizer output;
- dashboard diagnosis and safe retry;
- credential, redaction, outbound-policy, redirect, DNS, response-bound, and loopback scenarios.

A P0-B failure that invalidates a P0-A premise sets the P0-A gate to `REOPENED`. A domain failure stays in P0-B unless it proves the platform boundary wrong.

### B5 — Evidence synthesis, disposition, and P1 entry

- answer every P0 Architecture Question with evidence or an explicit unresolved blocker;
- record accepted and rejected alternatives and the component, process, transaction, data, operations, and security boundaries that survived execution;
- complete `docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION-TEMPLATE.md`;
- write and accept `PoC Contract 0.1`;
- write and accept the P1 reconstruction plan;
- archive P0 implementation by Git tag or equivalent history;
- delete local or protected runtime artifacts only after their required hashes, metadata, evidence summaries, and retention responsibility are recorded;
- enter P1 only after the P1 Entry Gate accepts all required outputs.

## Timeboxes

P0-A and P0-B each receive a separately recorded timebox before their experiment status becomes `RUNNING`. The former M2 ten-day allocation is superseded. A timebox stops or reduces scope; it does not turn missing evidence into a pass.
