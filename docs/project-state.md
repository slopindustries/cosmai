# Project State

- Project: CosmaSignal
- Version: 0.3
- Updated: 2026-08-17
- Phase: P0-A — Platform Core Construction and Verification
- Next gate: P0-A Completion Gate

## Delivery lifecycle

Delivery has two active stages before P1. Work packages inside a stage do not create additional lifecycle stages.

| Stage | Purpose | Entry condition | Required output | Exit condition |
|---|---|---|---|---|
| P0-A — Platform Core Construction and Verification | Build and test the source- and normalization-independent platform foundation. | Project identity, disposable-P0 lifecycle, technology constraints, evidence protocol, and safety baseline are accepted. | Executable platform core, handler-neutral job and failure evidence, platform operator instrumentation, and a reviewed P0-A gate record. | The P0-A Completion Gate records `GO` or an explicitly accepted `CONDITIONAL GO` without claiming acquisition or normalization evidence. |
| P0-B — Domain Integration, Evidence Synthesis, and Disposition | Select sources; define and implement acquisition and normalization; verify the real-data flow; decide what P1 promotes, rebuilds, archives, deletes, or carries unresolved. | P0-A gate is accepted and the bounded P0-B experiment, safety review, and timebox are recorded. | Source decisions, domain contracts, concrete collector/importer/normalizer, real-data and failure evidence, Architecture Synthesis, disposition register, `PoC Contract 0.1`, and P1 reconstruction plan. | Every P0 Charter exit criterion is answered and the P1 Entry Gate accepts the contract, disposition, and reconstruction plan, or records an explicit blocker. |
| P1 — Clean Reconstruction | Rebuild from accepted contracts and promoted evidence rather than harden P0 code. | P0-B P1 Entry Gate is accepted. | A clean, continuously operable prototype baseline. | Defined by the future P1 charter. |

No stage advances automatically because code appears to work. Update this file and the affected artifact statuses when a gate is accepted.

## 1. Current program goal through P0-B

First build and test a source- and normalization-independent platform core. Then, in P0-B, select one REST source and one dataset, define and implement the acquisition and normalization domain, execute realistic integrated failures, and synthesize enough evidence to write `PoC Contract 0.1` and a P1 reconstruction plan.

P0 remains disposable. P1 is reconstructed from accepted contracts and evidence rather than evolved directly from P0 implementation modules.

## 2. Final product goal

`OPEN`

The final meaning of beauty trend intelligence, its decision consumer, and the decision or R&D action it should improve have not been fixed. P0-A must not invent an answer. P0-B must record a provisional decision use before defining the concrete normalizer, while final product semantics may remain unresolved.

## 3. Artifact states

### Open Questions

Open Questions use `OPEN`, `EXPLORING`, `RESOLVED`, `DEFERRED`, and `SUPERSEDED`. Definitions and transition rules are in [Open Questions](open-questions/README.md).

### Decisions and contracts

```text
DRAFT
→ ACCEPTED_FOR_POC
→ CONTRACTED
→ STABLE
→ SUPERSEDED
```

- `DRAFT`: proposed but not accepted as a project constraint.
- `ACCEPTED_FOR_POC`: selected for P0 or P1 scope, not a permanent product commitment.
- `CONTRACTED`: versioned interface or data meaning with compatibility obligations.
- `STABLE`: repeatedly validated and not currently under challenge.
- `SUPERSEDED`: replaced by a recorded decision and migration path where required.

### Experiments

Experiments use `PLANNED`, `RUNNING`, `COMPLETED`, `INCONCLUSIVE`, and `ABORTED`. Definitions are in [Experiment Template](../experiments/EXPERIMENT-TEMPLATE.md).

Claim-level evidence labels such as `[확인 사실]` and `[가설]` are different from these decision states. Their definitions and usage rules are in [Evidence Labels](conventions/evidence-labels.md).

## 4. Accepted for P0

### Project and lifecycle

- `[결정]` Project and GitHub organization name: **CosmaSignal**.
- `[결정]` P0 is a disposable Architecture Discovery Prototype.
- `[결정]` P1 will be reconstructed after P0-B accepts Architecture Synthesis, `PoC Contract 0.1`, artifact disposition, and a P1 reconstruction plan.
- `[결정]` The repository is a monorepo for backend, dashboard, contracts, experiments, and tests.
- `[결정]` [DP-005](decisions/DP-005-two-part-pre-p1-execution.md) divides all pre-P1 delivery into P0-A and P0-B.

### Technology constraints

- `[결정]` Backend language: Python.
- `[결정]` Primary database: PostgreSQL.
- `[결정]` Dashboard: React and TypeScript.
- `[결정]` P0-B must support both REST API collection and existing dataset import.

Framework and library selections such as FastAPI, SQLAlchemy, Alembic, HTTPX, React Router, TanStack Query, and MUI are strong P0 defaults. Two different questions follow from that and the answer differs:

- **Adopting one is optional.** A default is a starting point, not an obligation, and AGENTS.md still applies: an abstraction that reduces no named uncertainty should not be introduced. Declining a default requires a recorded reason, not contrary evidence — there is nothing to have evidence about until something is in use.
- **Replacing one already in use requires contrary evidence**, because work has been built on it and the cost of changing is real.

`[결정]` This distinction was added on 2026-08-17 by [DP-006](decisions/DP-006-p0a-platform-foundation.md). The original sentence said only that these defaults "remain replaceable if an experiment produces contrary evidence", which read strictly would have required P0-A to adopt every one of them before it could decline any. DP-006 declined five, and the ambiguity was flagged there rather than resolved silently. The reviewer accepted the adoption-versus-replacement reading and asked for this clarification so that P0-B does not meet the same question again with FastAPI and HTTPX.

### P0-A boundary

P0-A implements only source- and normalization-independent platform behavior:

- PostgreSQL runtime, migrations, and source-neutral transaction foundations;
- handler-neutral jobs, workers, API lifecycle, and safe shutdown;
- generic claim, lease, retry, terminal-state, interruption, and recovery behavior;
- a source-neutral operator dashboard, logs, metrics, correlation, and safe retry;
- redaction, loopback binding, secret-store location guards, synthetic handlers, and platform failure injection.

P0-A does not explore or select sources and does not implement acquisition, Raw, snapshot, or normalization contracts, ports, test doubles, persistence, domain UI, or acceptance claims.

### P0-B boundary

P0-B owns all source and normalization work:

```text
bounded candidate exploration and rights review
→ REST source and dataset selection
→ provisional decision use
→ acquisition, Raw, snapshot, normalization, operations, source-policy, and credential contracts
→ collector/importer/normalizer interfaces and test doubles
→ concrete collector/importer/rule-baseline implementation
→ component, real-data, failure, replay, concurrency, and operator verification
→ Architecture Synthesis and artifact disposition
→ PoC Contract 0.1 and P1 reconstruction plan
→ P1 Entry Gate
```

Source probes are measurements inside P0-B. They are not integrated collector or importer implementations and cannot satisfy those obligations retroactively.

### Data and workflow principles

The following accepted principles become executable domain behavior in P0-B, not P0-A:

- `[결정]` Imported external datasets remain untrusted Raw data.
- `[결정]` Raw data preserves original payload and provenance and is logically append-only.
- `[결정]` Collection and normalization are independently controlled job domains.
- `[결정]` Normalization is started explicitly by an operator-created run or an optional schedule; collection does not implicitly trigger it.
- `[결정]` A normalization run consumes a sealed, materialized, hash-verifiable input snapshot.
- `[결정]` Normalized results are versioned and coexist; they are not updated in place as the single truth.
- `[결정]` P0 includes at least one deterministic rule-based normalizer.
- `[결정]` Dashboard control, logs, metrics, and debugging evidence are part of P0 instrumentation.

## 5. Architecture hypotheses

These are not contracts.

- `[가설]` A source- and normalization-independent platform core can expose useful execution, recovery, operator, and safety evidence before P0-B introduces the domain pipeline.
- `[가설]` PostgreSQL job tables with at-least-once processing and idempotent platform effects are sufficient for P0 concurrency.
- `[가설]` A shared Raw envelope plus source-specific payload can represent both REST responses and dataset rows without loss.
- `[가설]` A materialized snapshot plus manifest and hashes is sufficient for replay despite later Raw-store changes or migration.
- `[가설]` One small `Normalized Schema 0.x` can express useful common meaning across the first two sources.
- `[가설]` A rule baseline can expose schema and quality problems before ML or LLM providers are introduced.

The first two hypotheses can begin in P0-A. Acquisition and normalization hypotheses are tested only in P0-B.

## 6. Open questions

| ID | Status | Stage | Question | Blocks |
|---|---|---|---|---|
| [OQ-001](open-questions/OQ-001-source-capability.md) | `OPEN` | P0-B | Which REST and dataset sources are usable and representative? | Source contract, fixtures, P0-B ingestion |
| [OQ-002](open-questions/OQ-002-project-decision-contract.md) | `OPEN` | P0-B | Which decision should the final product improve? | Concrete normalizer, Schema 1.0, final quality metrics |
| [OQ-003](open-questions/OQ-003-normalization-protocol.md) | `OPEN` | P0-B | What are Schema 0.x and the normalizer provider protocol? | P0-B normalization |
| [OQ-004](open-questions/OQ-004-snapshot-boundary.md) | `OPEN` | P0-B | What exactly must a sealed snapshot materialize? | Reproducibility contract |
| [OQ-005](open-questions/OQ-005-operations-contract.md) | `OPEN` | P0-A/P0-B | Which platform and domain actions and evidence must the dashboard expose? | Dashboard acceptance contract |
| [OQ-006](open-questions/OQ-006-job-concurrency.md) | `OPEN` | P0-A/P0-B | Is the PostgreSQL job model sufficient under platform and domain failures? | Worker, retry, and transaction contract |
| [OQ-007](open-questions/OQ-007-credential-scope.md) | `OPEN` | P0-A/P0-B | What does the platform protect before a source exists, and which real credentials may a domain worker resolve? | Secret guard and source credential contract |
| [OQ-008](open-questions/OQ-008-operator-reexecution-authority.md) | `OPEN` | P0-B | May an operator re-execute work that already succeeded, and what distinguishes that from retrying a failure? | Operator action set in `PoC Contract 0.1` |

Stage expresses evidence routing, not long-term business importance.

## 7. Local implementation choices

Implementation may choose these without a Decision Packet when behavior and accepted constraints do not change:

- function, class, module, and component names;
- helper and internal folder decomposition inside an experiment;
- equivalent parsing or iteration algorithms;
- minor dashboard layout and styling;
- polling intervals within documented operational bounds;
- test helper libraries.

## 8. Specification frontier

P0-A may specify only platform invariants such as generic ownership, lease recovery, observable state, redaction, loopback exposure, and secret-store location guards.

P0-A must not freeze source identity, provider fields, Raw semantics, snapshot selection, normalized semantics, source-specific retry policy, or concrete credential authorization. P0-B may propose those as experimental contracts after source evidence exists. Production topology, scale infrastructure, final product analytics, and `Normalized Schema 1.0` remain outside P0.

## 9. Historical context

The reasoning path from the initial ingestion idea to the disposable P0 lifecycle is recorded in [HIST-001](history/HIST-001-initial-concept-to-p0.md). DP-004 is retained as a superseded decision record.

History documents are non-authoritative. Current requirements come from this Project State, active accepted Decision Packets, and versioned contracts.
