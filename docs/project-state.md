# Project State

- Project: Cosmai
- Version: 0.9
- Updated: 2026-08-19
- Phase: P0-B — Domain Integration, Evidence Synthesis, and Disposition
- Next gate: P1 Entry Gate (inside P0-B)

## Delivery lifecycle

Delivery has two active stages before P1. Work packages inside a stage do not create additional lifecycle stages.

| Stage | Purpose | Entry condition | Required output | Exit condition |
|---|---|---|---|---|
| P0-A — Platform Core Construction and Verification | Build and test the source- and normalization-independent platform foundation. | Project identity, disposable-P0 lifecycle, technology constraints, evidence protocol, and safety baseline are accepted. | Executable platform core, handler-neutral job and failure evidence, platform operator instrumentation, and a reviewed P0-A gate record. | The P0-A Completion Gate records `GO` or an explicitly accepted `CONDITIONAL GO` without claiming acquisition or normalization evidence. |
| P0-B — Domain Integration, Evidence Synthesis, and Disposition | Select sources; define and implement acquisition and normalization; verify the real-data flow; decide what P1 promotes, rebuilds, archives, deletes, or carries unresolved. | P0-A gate is accepted and the bounded P0-B experiment, safety review, and timebox are recorded. | Source decisions, domain contracts, the add-on contract and host, concrete collector/importer/normalizer add-ons, real-data and failure evidence, Architecture Synthesis, disposition register, `PoC Contract 0.1`, and P1 reconstruction plan. | Every P0 Charter exit criterion is answered and the P1 Entry Gate accepts the contract, disposition, and reconstruction plan, or records an explicit blocker. |
| P1 — Clean Reconstruction | Rebuild from accepted contracts and promoted evidence rather than harden P0 code. | P0-B P1 Entry Gate is accepted. | A clean, continuously operable prototype baseline. | Defined by the future P1 charter. |

No stage advances automatically because code appears to work. Update this file and the affected artifact statuses when a gate is accepted.

`[결정]` **The P0-A Completion Gate was accepted `GO` on 2026-08-17** with no conditions, at revision `f83fe3c`. Its record, the evidence it links, and an adversarial review of every `PASS` claim are in [`experiments/integrated-p0/`](../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md). P0-A produced no acquisition or normalization evidence and the gate says so in its own words; the nine things it explicitly does not claim are the boundary P0-B inherits.

## 1. Current program goal through P0-B

First build and test a source- and normalization-independent platform core. Then, in P0-B, select one REST source exposed by an independent scraper service and one dataset, define and implement the acquisition and normalization domain, execute realistic integrated failures, and produce evidence-backed R&D opportunity cards for Korean sunscreen and toner topics. Synthesize enough evidence to write `PoC Contract 0.1` and a P1 reconstruction plan.

P0 remains disposable. P1 is reconstructed from accepted contracts and evidence rather than evolved directly from P0 implementation modules.

### Where this stands, 2026-08-19

`[측정]` **Every P0-B work package's deliverables exist, measured against the execution
plan as it stood before [DP-011](decisions/DP-011-p0b-product-and-delivery-scope.md).**
B0–B3 were complete before this date; B1's *records* (`SRC-001`, `SRC-002`, the selection matrix), B4's evidence coverage,
and all four B5 outputs were written on 2026-08-19.

| Package | State |
|---|---|
| B0 add-on layer | complete |
| B1 source exploration and selection | complete — REST real, dataset a recorded structural substitution |
| B2 decision use and domain contracts | complete — folded into [`PoC Contract 0.1`](../contracts/experimental/POC-CONTRACT-0.1.md) by owner decision |
| B3 concrete implementation | complete — 3 collectors, 1 importer, 3 normalizers, dashboard |
| B4 real-data and failure evidence | complete with named gaps — [`B4-SCENARIO-COVERAGE.md`](../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md) |
| B5 synthesis, disposition, P1 entry | documents written; **acceptance pending** |

`[확인 사실]` **[DP-011](decisions/DP-011-p0b-product-and-delivery-scope.md) and
[DP-012](decisions/DP-012-independent-scraper-services.md) were accepted the same day, on a
branch this work could not see.** They name a product scope — an evidence-backed R&D
opportunity card for sunscreen and toner, on a 2026-08-26 delivery boundary — and an
acquisition topology in which scraper runtimes and first-stage storage stay outside COSMAI.
The table above does not claim any of it, and neither does the work below.

| DP-011 / DP-012 scope | State |
|---|---|
| Opportunity card as the decision unit | not started |
| Sunscreen and toner canonicalization | not started |
| Deterministic trend baseline and classes | not started |
| Scraper-service REST adapter add-on | not started — the three collectors call the source directly |

`[확인 사실]` **Two acts remain and neither is a document.** The P0 archive tag does not
exist, and the P1 Entry Gate has not been held. Both are the project owner's:
`AGENTS.md` makes commits, pushes, and tags things that happen when asked, and a gate that
accepted itself would not be a gate.

`[결정]` Until that gate is held, P0-B is **complete as work against the pre-DP-011
plan, not started against DP-011's, and unaccepted as a stage**. The distinction matters: `apps/` stays empty, and `SEC-006`'s waiver
([DP-023](decisions/DP-023-sec-006-waived-for-p0.md)) has not yet expired.

## 2. P0 product decision and long-term goal

`ACCEPTED_FOR_POC` in [DP-011](decisions/DP-011-p0b-product-and-delivery-scope.md).

Cosmai helps a cosmetics-company R&D or product-planning reviewer decide whether a canonical sunscreen- or toner-related topic deserves review, monitoring, evidence expansion, or rejection. The first decision unit is an evidence-backed R&D opportunity card, not a consumer recommendation, formula recommendation, sales forecast, or autonomous approval.

The delivery is backend- and ingestion-first. Source quality takes priority over source count; product, ingredient, topic, and evidence identity must be canonical and traceable. Deterministic trend classes precede any optional LLM explanation. Long-term product semantics and learned prediction targets remain open beyond P0.

## 2.1 Delivery control

- `[결정]` Functional freeze: **2026-08-26**.
- `[결정]` Independent verification, corrections, and handoff: **2026-08-27**.
- `[결정]` Required flow: one selected independent scraper REST service through a COSMAI adapter and one selected dataset through Raw, deduplication, sealed snapshot, canonical normalization, deterministic trend classification, evidence card, and operator inspection.
- `[결정]` Stretch only after the required flow passes: a second live channel and an evidence-citing LLM explanation renderer.
- `[결정]` Not in this delivery: AutoML, deep learning, sales prediction, broad cosmetics coverage, or access to an unapproved storefront.

The dated owners, stop rules, and acceptance evidence are in the [P0 Execution Plan](p0-execution-plan.md#delivery-window-2026-08-19-to-2026-08-27).

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

- `[결정]` Project and GitHub organization name: **Cosmai**.
- `[결정]` P0 is a disposable Architecture Discovery Prototype.
- `[결정]` P1 will be reconstructed after P0-B accepts Architecture Synthesis, `PoC Contract 0.1`, artifact disposition, and a P1 reconstruction plan.
- `[결정]` The repository is a monorepo for backend, dashboard, contracts, experiments, and tests.
- `[결정]` [DP-005](decisions/DP-005-two-part-pre-p1-execution.md) divides all pre-P1 delivery into P0-A and P0-B.
- `[결정]` [DP-008](decisions/DP-008-addon-architecture.md) makes collectors, importers, and normalizers in-repository add-ons behind a contract, superseding DP-005's P0-B order steps 4–6 and DP-006's module layout.
- `[결정]` [DP-010](decisions/DP-010-durable-work-in-the-completion-transaction.md) lets a handler enlist work into the transaction that completes its attempt, closing the gap the P0-A gate recorded first. It restates DP-008 D1's principle: `platform_core` stays **source-neutral**, not frozen.
- `[결정]` [DP-012](decisions/DP-012-independent-scraper-services.md) keeps scraper runtimes and first-stage storage outside COSMAI. COSMAI integrates their versioned export endpoints through in-repository collector adapter add-ons.
- `[결정]` [DP-018](decisions/DP-018-credential-parts-and-attachment.md) makes a credential a set of named parts, each a secret-store key name filling one **protected** header, declared in the source's operator-approved outbound profile. Resolves OQ-009 for P0-B.
- `[결정]` [DP-019](decisions/DP-019-normalized-schema-0-1-and-results.md) fixes `Normalized Schema 0.1`, the `normalized_result` table, and what a snapshot selects. It also records the **provisional decision use** §2 requires before a concrete normalizer exists.
- `[결정]` [DP-020](decisions/DP-020-request-method-and-body.md) puts the request method on the approved profile and the request body with the add-on, and bumps `addon_api` to contract 1.1. Two of the three selected NAVER endpoints are `POST` with a JSON body and were unreachable without it.
- `[결정]` [DP-021](decisions/DP-021-schema-0-2-trend-points.md) makes Schema 0.2 a discriminated union on `record_type` so a document and a trend point can share one table.
- `[결정]` [DP-025](decisions/DP-025-two-branch-record-reconciliation.md) reconciles the two decision records that grew from `c0a266d` without seeing each other: the published numbers stand, the P0-B packets moved to DP-018–DP-024 and OQ-013–OQ-014, OQ-014 closes into DP-012 carrying its measurement as falsification input, and the P0-B completion claim states the plan it is measured against.

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

P0-B owns all source and normalization work. [DP-008](decisions/DP-008-addon-architecture.md) splits it into two tracks that run in parallel and then converge:

```text
add-on track                          source track
(no source or decision semantics)     (blocked by OQ-001 and OQ-002)

add-on contract, host, and            bounded candidate exploration
  version gate                          and rights review
→ source registry, cursor, Raw,       → REST source and dataset selection
    and snapshot tables               → provisional decision use
→ platform outbound guard
→ conformance suite, template,
    and generator
→ add-on operator surfaces
                        ↓                         ↓
        acquisition, Raw, snapshot, normalization, operations,
          source-policy, and credential contracts
        → independent scraper service and collector adapter, importer, and normalizer add-on implementations
        → component, real-data, failure, replay, concurrency, and operator verification
        → Architecture Synthesis and artifact disposition
        → PoC Contract 0.1 and P1 reconstruction plan
        → P1 Entry Gate
```

`[추론]` The add-on track carries no source or decision semantics, so neither OQ-001 nor OQ-002 blocks it. What OQ-002 blocks is the content of the normalizer's rules, not the protocol they are written against.

Source probes are measurements inside P0-B. They are not integrated service adapters or importer implementations and cannot satisfy those obligations retroactively.

### Add-on architecture

`[결정]` Collectors, importers, and normalizers are in-repository add-ons behind a contract, accepted in [DP-008](decisions/DP-008-addon-architecture.md). A new source adds a directory, not platform code.

- `[결정]` One package format and manifest; capabilities granted by `kind`. A collector receives a platform-composed `fetch`, an importer receives a platform-opened input, a normalizer receives a hash-verified snapshot.
- `[결정]` An add-on never receives a credential, never composes a URL, and never holds a database handle. Every outbound obligation in the [P0 Security Baseline](conventions/p0-security.md) stays on the platform.
- `[결정]` Add-ons depend on the contract package alone. `platform_core` gains no dependency on the add-on layer, and a dependency-direction test enforces both directions.
- `[결정]` Four version axes carry defined failures: contract, add-on, config schema, and normalizer output contract.
- `[결정]` In-process add-ons are trusted code. Isolation is contractual and test-enforced, not enforced by the operating system.
- `[결정]` Source-specific scraper code, scheduling, and first-stage storage may run as independent REST services under [DP-012](decisions/DP-012-independent-scraper-services.md). COSMAI keeps only a thin collector adapter, never imports the scraper project, and never reads its database directly.
- `[결정]` The service database and COSMAI transaction are independent. Replayable `batch_id`, stable `record_id`, and cursor semantics replace a distributed transaction; COSMAI still commits Raw, its cursor, and accepted job completion atomically.

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

### Project memory and agent workflow

- `[결정]` [DP-013](decisions/DP-013-agent-workflow-and-project-memory.md) makes repository documents, rather than session memory, the project record.
- `[결정]` Consequential directions require an explicit owner question and a recorded answer before implementation.
- `[결정]` Agent work is separated into orchestrator, planner, worker, and attacker responsibilities and handed off through bounded task packets and review reports.
- `[결정]` The full agent flow applies by the threshold recorded in [Agent Operating Model](agent-workflow/README.md), not to every change.
- `[결정]` [DP-014](decisions/DP-014-agent-memory-scope-and-area-exception.md) fixes what project memory covers: this repository is where a project fact belongs, and the convention does not regulate a private memory store. It also accepts that documents changing the project's operating method belong to no development area.
- `[확인 사실]` **One** part of that model is enforced: `tests/environment/test_agent_packet_record.py` rejects an `ACCEPTED` packet with no resolvable attack report. The rest is convention and is listed as such rather than implied. An earlier revision of this line also claimed `adversarial-reviewer` cannot write; that was false — its frontmatter denies three edit tools but not `Bash`. [REVIEW-TASK-001](agent-workflow/reviews/REVIEW-TASK-001.md) F1 measured the write.

## 5. Architecture hypotheses

These are not contracts.

- `[가설]` A source- and normalization-independent platform core can expose useful execution, recovery, operator, and safety evidence before P0-B introduces the domain pipeline.
- `[가설]` PostgreSQL job tables with at-least-once processing and idempotent platform effects are sufficient for P0 concurrency.
- `[가설]` A shared Raw envelope plus source-specific payload can represent both REST responses and dataset rows without loss. `[측정]` **Supported for the shapes tested, 2026-08-19.** One `raw_envelope` carried a REST response and a local file through the same completion transaction; `endpoint_ref` and `status` became nullable and `input_ref` joined them ([DP-024](decisions/DP-024-local-input-registry.md)) — a column becoming optional, not a second table. The dataset half is self-authored, so nothing here is evidence about a real producer.
- `[가설]` A materialized snapshot plus manifest and hashes is sufficient for replay despite later Raw-store changes or migration. `[측정]` **Half tested, 2026-08-19.** Tampering is detected and named. **Raw-store evolution was never exercised** — no migration changed the Raw tables after a snapshot was sealed — so the half the hypothesis is actually about has no evidence.
- `[가설]` One small `Normalized Schema 0.x` can express useful common meaning across the first two sources. `[측정]` **Refuted in its strong form on 2026-08-19.** Against a blog document and a DataLab trend point the only overlap is identity, time, and provenance — the fields any record needs to *be* a record — and there is no common domain meaning between "someone wrote this" and "people searched this much". [DP-021](decisions/DP-021-schema-0-2-trend-points.md) adopts the weaker form: one schema carries a common **envelope** and a per-type body. The Architecture Synthesis should carry the refutation rather than restate the hypothesis.
- `[가설]` A rule baseline can expose schema and quality problems before ML or LLM providers are introduced. `[측정]` **Not tested in P0.** No quality baseline was built; the normalizers extract, they do not judge.

The first two hypotheses can begin in P0-A. Acquisition and normalization hypotheses are tested only in P0-B.

## 6. Open questions

| ID | Status | Stage | Question | Blocks |
|---|---|---|---|---|
| [OQ-001](open-questions/OQ-001-source-capability.md) | `OPEN` | P0-B | Which REST and dataset sources are usable and representative? | Source contract, fixtures, P0-B ingestion |
| [OQ-002](open-questions/OQ-002-project-decision-contract.md) | `RESOLVED` | P0-B | Which decision should the final product improve? | Resolved for P0 by DP-011; long-term learned targets remain outside P0 |
| [OQ-003](open-questions/OQ-003-normalization-protocol.md) | `OPEN` | P0-B | What are Schema 0.x and the normalizer provider protocol? | P0-B normalization |
| [OQ-004](open-questions/OQ-004-snapshot-boundary.md) | `OPEN` | P0-B | What exactly must a sealed snapshot materialize? | Reproducibility contract |
| [OQ-005](open-questions/OQ-005-operations-contract.md) | `OPEN` | P0-A/P0-B | Which platform and domain actions and evidence must the dashboard expose? | Dashboard acceptance contract |
| [OQ-006](open-questions/OQ-006-job-concurrency.md) | `OPEN` | P0-A/P0-B | Is the PostgreSQL job model sufficient under platform and domain failures? | Worker, retry, and transaction contract |
| [OQ-007](open-questions/OQ-007-credential-scope.md) | `OPEN` | P0-A/P0-B | What does the platform protect before a source exists, and which real credentials may a domain worker resolve? | Secret guard and source credential contract |
| [OQ-008](open-questions/OQ-008-operator-reexecution-authority.md) | `OPEN` | P0-B | May an operator re-execute work that already succeeded, and what distinguishes that from retrying a failure? | Operator action set in `PoC Contract 0.1` |
| [OQ-009](open-questions/OQ-009-credential-shape.md) | `RESOLVED` | P0-B | How is a source's credential declared, and where does each part of it go? | Resolved for P0-B by [DP-018](decisions/DP-018-credential-parts-and-attachment.md) on one source's evidence; H1's query-parameter and signed-request cases stay open |
| [OQ-010](open-questions/OQ-010-cursor-stream-read-back.md) | `OPEN` | P0-B | Which cursor does an add-on read back when it writes several streams? | Multi-stream collectors and importers, conformance resume scenario |
| [OQ-011](open-questions/OQ-011-agent-memory-and-area-boundary.md) | `RESOLVED` | P0-B | Do the two rules the operating-model adoption wrote without asking — the private-memory rule and the development-area exception — bind? | Resolved 2026-08-19 by DP-014: the memory rule narrowed to the repository half, the area exception accepted |
| [OQ-013](open-questions/OQ-013-addon-responsibility-boundary.md) | `OPEN` | P0-B | What is an add-on responsible for, and what holds a judgment no other layer can check? | Repair shape for mutation review B5; any fourth collector; the P1 add-on contract |
| [OQ-014](open-questions/OQ-014-externalized-acquisition.md) | `RESOLVED` | P0-B | Should acquisition leave this service and be read over REST from a service that accumulates it? | Answered by [DP-012](decisions/DP-012-independent-scraper-services.md), accepted the same day on another branch. OQ-014's measurement is carried into DP-012 as falsification input |

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

## 9. Candidate services

Services beyond the current P0-B scope are recorded in the [service register](service-register.md)
as `[가설]` candidates rather than as a roadmap. `[추론]` Naming a future service and a
milestone for it would answer [OQ-002](open-questions/OQ-002-project-decision-contract.md)
by implication, because choosing what to build is choosing which decision to improve.
The register records what each candidate would consume, produce, and require instead.

## 10. Historical context

The reasoning path from the initial ingestion idea to the disposable P0 lifecycle is recorded in [HIST-001](history/HIST-001-initial-concept-to-p0.md). DP-004 is retained as a superseded decision record.

History documents are non-authoritative. Current requirements come from this Project State, active accepted Decision Packets, and versioned contracts.
