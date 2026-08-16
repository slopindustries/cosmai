# Project State

- Project: CosmaSignal
- Version: 0.1
- Updated: 2026-08-16
- Phase: M0 — Project Bootstrap
- Next gate: M1 Source Capability Exploration

## Delivery lifecycle

Milestones describe delivery progress. They are different from Open Question, Decision Packet, contract, and experiment statuses.

| Stage | Purpose | Entry condition | Required output | Exit condition |
|---|---|---|---|---|
| M0 — Project Bootstrap | Establish the decision boundary, evidence protocol, safety baseline, and working templates. | Project identity and P0 lifecycle are accepted. | Active project documents, agent instructions, templates, validated local configuration, and a reviewed bootstrap commit. | The repository can begin source experiments without relying on hidden chat context. |
| M1 — Source Capability Exploration | Test real REST and dataset candidates and select replayable P0 inputs. | M0 exit condition is met and OQ-001 has bounded candidates. | Completed source probes, capability profiles, selection matrix, rights basis, fixtures or hashes, and a source decision. | One REST source and one dataset receive `GO` or an explicitly accepted `CONDITIONAL GO`. |
| M2 — Integrated P0 Execution | Run the disposable end-to-end architecture experiment. | M1 outputs are accepted, the P0 timebox is confirmed, and required experimental contracts can be drafted. | Executable P0, experiment records, failure evidence, acceptance results, and proposed contracts. | Every P0 Charter exit criterion is answered with evidence or recorded as an explicit unresolved blocker. |
| M3 — Architecture Synthesis | Convert P0 evidence into scoped architecture decisions. | M2 reaches its exit review. | Architecture Synthesis, accepted and rejected alternatives, promoted fixtures and tests, and `PoC Contract 0.1`. | The synthesis gate accepts the contract and a P1 reconstruction plan. |
| P1 — Reconstruction | Rebuild from accepted contracts rather than promote P0 code. | M3 accepts `PoC Contract 0.1`. | A clean, continuously operable prototype baseline. | Defined by the P1 charter after Architecture Synthesis. |

No stage advances automatically because code appears to work. Update this file and the affected artifact statuses when a gate is accepted.

## 1. Current program goal through M2

Create a disposable but integrated P0 that uses real data to test the architecture from source acquisition through Raw storage, sealed normalization input, versioned normalization output, and operator observation.

P0 must generate enough evidence to write `PoC Contract 0.1`. P1 will then be reconstructed from that contract and the accepted tests rather than evolved directly from P0 code.

## 2. Final product goal

`OPEN`

The final meaning of beauty trend intelligence, its decision consumer, and the decision or R&D action it should improve have not been fixed. This does not block source sampling or ingestion experiments, but it blocks `Normalized Schema 1.0` and final quality criteria.

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
- `[결정]` P1 will be reconstructed after Architecture Synthesis.
- `[결정]` The repository is a monorepo for backend, dashboard, contracts, experiments, and tests.

### Technology constraints

- `[결정]` Backend language: Python.
- `[결정]` Primary database: PostgreSQL.
- `[결정]` Dashboard: React and TypeScript.
- `[결정]` REST API and existing dataset import are both required acquisition modes.

Framework and library selections such as FastAPI, SQLAlchemy, Alembic, HTTPX, React Router, TanStack Query, and MUI are strong P0 defaults but remain replaceable if an experiment produces contrary evidence.

### Data and workflow principles

- `[결정]` Imported external datasets remain untrusted Raw data.
- `[결정]` Raw data preserves original payload and provenance and is logically append-only.
- `[결정]` Collection and normalization are independently controlled job domains.
- `[결정]` Normalization is started explicitly by an operator-created run or an optional schedule; collection does not implicitly trigger it.
- `[결정]` A normalization run consumes a sealed, materialized, hash-verifiable input snapshot.
- `[결정]` Normalized results are versioned and coexist; they are not updated in place as the single truth.
- `[결정]` P0 includes at least one deterministic rule-based normalizer.
- `[결정]` Dashboard control, logs, metrics, and debugging evidence are part of P0 instrumentation.

## 5. Architecture hypotheses

These are not yet contracts.

- `[가설]` A shared Raw envelope plus source-specific payload can represent both REST responses and dataset rows without loss.
- `[가설]` PostgreSQL job tables with at-least-once processing and idempotent writes are sufficient for P0 concurrency.
- `[가설]` API/control, collector worker, normalizer worker, and dashboard are useful execution boundaries.
- `[가설]` A materialized snapshot plus manifest and hashes is sufficient for replay despite later Raw-store changes or migration.
- `[가설]` One small `Normalized Schema 0.x` can express useful common meaning across the first two sources.
- `[가설]` A rule baseline can expose schema and quality problems before ML or LLM providers are introduced.

## 6. Open questions

| ID | Status | Priority | Question | Blocks |
|---|---|---:|---|---|
| [OQ-001](open-questions/OQ-001-source-capability.md) | `OPEN` | P0 | Which REST and dump sources are usable and representative? | Source contract, fixtures, P0 ingestion |
| [OQ-002](open-questions/OQ-002-project-decision-contract.md) | `OPEN` | P0 | Which decision should the final product improve? | Schema 1.0, final quality metrics |
| [OQ-003](open-questions/OQ-003-normalization-protocol.md) | `OPEN` | P0 | What are Schema 0.x and the normalizer provider protocol? | Normalization P0 |
| [OQ-004](open-questions/OQ-004-snapshot-boundary.md) | `OPEN` | P0 | What exactly must a sealed snapshot materialize? | Reproducibility contract |
| [OQ-005](open-questions/OQ-005-operations-contract.md) | `OPEN` | P0 | Which operator actions and evidence must the dashboard expose? | Dashboard acceptance contract |
| [OQ-006](open-questions/OQ-006-job-concurrency.md) | `OPEN` | P0 | Is the PostgreSQL job model sufficient and correct under failure? | Worker and retry contract |
| [OQ-007](open-questions/OQ-007-credential-scope.md) | `OPEN` | P0 | Which credentials may a worker resolve, and what enforces that limit? | Credential handling and worker boundary contract |

Priority expresses the order of evidence work, not long-term business importance.

## 7. Local implementation choices

Implementation may choose these without a Decision Packet when behavior and accepted constraints do not change:

- function, class, module, and component names;
- helper and internal folder decomposition inside an experiment;
- equivalent parsing or iteration algorithms;
- minor dashboard layout and styling;
- polling intervals within documented operational bounds;
- test helper libraries.

## 8. Specification frontier

We can specify invariants now: provenance, lossless Raw preservation, independent recovery, snapshot replay, versioned normalization, idempotency, and observable state.

We must not yet freeze provider-specific fields, final normalized semantics, universal D0–D4 maturity claims, production service topology, scale infrastructure, or final product analytics.

## 9. Historical context

The reasoning path from the initial ingestion idea to the current disposable P0 lifecycle is recorded in [HIST-001](history/HIST-001-initial-concept-to-p0.md).

History documents are non-authoritative. They explain why ideas changed, but current decisions and implementation requirements come from this Project State, accepted Decision Packets, and versioned contracts.
