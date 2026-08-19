# P0 Execution Plan — Platform First, Domain Integration Second

- Status: `ACCEPTED_FOR_POC`
- Governing decision: [DP-005](decisions/DP-005-two-part-pre-p1-execution.md)
- Applies to: disposable P0 under `experiments/integrated-p0/` and source probes under `experiments/source-probes/`
- Last updated: 2026-08-19

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

B0 and B1 run in parallel. `[추론]` B0 contains no source or decision semantics, so neither OQ-001 nor OQ-002 blocks it; B2 onward needs both.

### B0 — Add-on layer

Governed by [DP-008](decisions/DP-008-addon-architecture.md). Experiment record:
[EXP-002](../experiments/integrated-p0/EXP-002-addon-layer.md), `RUNNING`, owner Project team,
**timebox 6 hours** recorded 2026-08-18. Implement under `experiments/integrated-p0/`:

1. `addon_api` contract at `CONTRACT_VERSION = "1.0"`, and `addon_host` discovery, loading, and version gate.
2. `domain` source registry, cursor, Raw, and snapshot tables in migration `0002_domain.sql`.
3. Capability implementations, including the platform outbound guard that composes every request from a registered source profile.
4. The `addon_kit` generator, its template, the fixture-driven authoring harness (`addon_kit run`), the conformance suite, and `addons/normalizer.conformance/` as the smallest conforming add-on. The template lives at `addon_kit/template/`, deliberately outside the `addons/` tree the host scans, so a template cannot be discovered and registered as an add-on nobody installed. The harness is the authoring loop and is not integration evidence: it exercises an add-on's logic against the contract's shapes and cannot exercise the outbound guard, atomicity, retry and lease, or persistence.
5. Operator surfaces: installed add-on list, source create and edit rendered from the add-on's config schema, credential submission, and version and migration state.

B0 adds no dependency to `platform_core`. A dependency-direction test enforces that, and enforces that an add-on imports `addon_api` alone.

`SEC-002`, `SEC-003`, and `SEC-004` test the platform's own guard, so they run here against a synthetic registered source, before the first real outbound request exists. Passing them in B0 does not discharge B1's obligation to narrow the agent sandbox before that first real request.

### B1 — Source exploration and selection

- define a bounded REST API and dataset candidate set;
- read and apply the Data Handling Convention and P0 Security Baseline before external access;
- narrow the agent sandbox before the first outbound probe;
- complete Source Capability Profiles and the Source Selection Matrix;
- record rights, agent-processing permission, replay procedures, hashes, capture time, schema, identity, rate, update, missingness, and duplicate behavior;
- when the input is an independent scraper service, profile both the original source basis and the service export contract, deployment boundary, batch identity, cursor, and retention;
- select one REST source and one dataset through `GO` or explicitly accepted `CONDITIONAL GO`.

Probe code is disposable measurement code. It is not the integrated collector or importer and cannot be promoted into one silently.

### B2 — Decision use and domain contracts

- record a provisional decision consumer, trigger, output unit, evidence requirement, uncertainty representation, and human-review boundary;
- inspect representative source records;
- version experimental acquisition, Raw, job/error specialization, snapshot, normalization, operations, source-policy, and credential-scope contracts;
- version the independent service response and adapter configuration required by [DP-012](decisions/DP-012-independent-scraper-services.md);
- draft `ACQ`, `RAW`, `SNP`, `NRM`, domain `OPS`, and domain `SEC` scenarios;
- express those contracts against B0's add-on contract rather than against platform code, and record any capability the add-on contract must gain to carry them;
- record test-double limitations and real-source behaviors requiring direct verification. Under DP-008 a test double is itself an add-on — the smallest conforming one — so it is written and run the same way a real add-on is.

Contracts and test doubles created here are hypotheses. They do not count as real-integration evidence.

### B3 — Concrete implementation

Implement only the selected pair and the bounded deterministic baseline. Scraper services stay outside this repository; COSMAI components remain add-ons under `addons/`:

- one independent scraper REST service with first-stage storage, plus one thin COSMAI collector adapter add-on with version, batch, cursor, retry, response, identity, and replay validation;
- one dataset importer add-on with required format, encoding, row identity, invalid/missing-row, duplicate, and changed-version behavior;
- one deterministic `rule-baseline@0.1` normalizer add-on consuming a sealed snapshot and producing validated versioned results;
- the Raw, snapshot, result-lineage, source-policy, credential-scope, and domain dashboard behavior required by the accepted experimental contracts.

Run the conformance suite and isolated component tests against each add-on before connecting it to the platform core. An add-on that needs a capability B0 did not grant is evidence about the contract, not a reason to widen a grant in place: record it and amend the contract with its version raised.

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

| Package | Timebox | Recorded | Experiment |
|---|---|---|---|
| P0-A | 1 day | 2026-08-17 | [EXP-001](../experiments/integrated-p0/EXP-001-platform-core.md) — `COMPLETED` |
| B0 — Add-on layer | 6 hours | 2026-08-18 | [EXP-002](../experiments/integrated-p0/EXP-002-addon-layer.md) — `COMPLETED`; box expired at 6.4 h with B0.3–B0.5 unbuilt |
| B0.3 — Capability layer and outbound guard | 2.5 hours | 2026-08-18 | [EXP-003](../experiments/integrated-p0/EXP-003-capability-layer.md) — `RUNNING` |
| B1 — Source exploration | not yet recorded | — | not created |

B1 must record its own owner and timebox before its status becomes `RUNNING`.

## Delivery window: 2026-08-19 to 2026-08-27

This window implements [DP-011](decisions/DP-011-p0b-product-and-delivery-scope.md).
It does not change the P0 lifecycle, promote P0 code into P1, or convert missing evidence
into a pass.

> `[결정]` **Superseded in part on 2026-08-20 by
> [DP-026](decisions/DP-026-p0-closure-scope-and-collector-topology.md).** P0 now closes
> against [`p0-charter.md`](p0-charter.md)'s P0-B exit criteria; DP-011's product scope —
> the opportunity card, sunscreen and toner canonicalization, and deterministic trend
> classes — and DP-012's scraper-service adapter move to **P1's first milestone**. The
> dated critical path below is kept as written rather than edited, because it is the plan
> the 08-19 measurement was taken against and rewriting it would make that measurement
> unreadable; the rows it still binds are marked. What replaces it for P0 closure is the
> charter's exit criteria, its three open gaps — a real dataset, `rule-baseline@0.1`, and
> snapshot survival across Raw-store evolution — the P1 Entry Gate, the archive tag, and
> the merge to `main`.

### Starting measurement

`[확인 사실]` The starting revision is `c0a266d` on `dev`.

`[확인 사실]` **The fourth column exists because this table and
[`project-state.md`](project-state.md) appeared to disagree and did not.** This table
measured what was *committed* at `c0a266d`; `project-state.md` measured what was in the
working tree on the same day. Both were right about different things, and a reader meeting
"B4 — Not started" beside "B4 — complete with named gaps" cannot tell that without being
told. The column records what has since become history, and — more usefully — where the
committed work still does not meet this plan's criterion.

| Package | State at the starting revision | Completion evidence still missing | Committed since this measurement, on `p0b/domain-and-synthesis` |
|---|---|---|---|
| P0-A | `COMPLETED`, gate accepted `GO` | None for the P0-A boundary; domain claims remain outside that gate. | `[확인 사실]` Unchanged. |
| B0 / EXP-002 | Closed by timebox; contract, host, domain tables, authoring kit, conformance normalizer, and first collector exist | Full conformance suite and domain operator surfaces. | `addon_api` 1.0 → 1.3, written down as [`CONTRACT-ADDON@1.3`](../contracts/experimental/CONTRACT-ADDON-1.3.md); the host binds all three kinds; `addon_host` gained an API, a worker, and an entrypoint. Domain operator surfaces exist for collector and normalizer only — **no route creates an import job**. |
| EXP-003 | Procedure complete, status `RUNNING`, result `PARTIAL` | Ten adversarial-review findings are unrepaired: 3 blocking, 3 major, 3 moderate, 1 minor. | Status still `RUNNING`. `[측정]` The five blocking work items are repaired, the mutation review's B series is repaired, and `SEC-006` is waived rather than satisfied ([DP-023](decisions/DP-023-sec-006-waived-for-p0.md)). The experiment is not closed. |
| B1 | Not started | Rights and capability profiles, source matrix, one REST and one dataset decision, real captures. | `SRC-001` (NAVER API Hub), `SRC-002`, and the selection matrix are committed. **The REST half is real; the dataset half is not.** `SRC-002` is a file this project writes for itself, recorded as a deliberate substitution — so B1's dataset decision, in this plan's sense, is still open. |
| B2 | Product decision now fixed by DP-011; other domain contracts not started | Sample-driven Schema 0.x, Raw/snapshot/normalization/operations contracts and scenarios. | [`PoC Contract 0.1`](../contracts/experimental/POC-CONTRACT-0.1.md), Schema 0.1 ([DP-019](decisions/DP-019-normalized-schema-0-1-and-results.md)) and Schema 0.2 ([DP-021](decisions/DP-021-schema-0-2-trend-points.md)) are committed. **None of it is DP-011's product schema** — no card, product, ingredient, or topic identity. |
| B3 | A direct Naver add-on prototype exists but has run only against a local stub; the selected independent-service boundary and adapter do not yet exist; structural normalizer only | Naver service and adapter, real-source run, importer, semantic rule baseline, normalized-result lineage, cards, domain operator behavior. | Three collectors, one importer, three normalizers, and a domain operator screen. `[확인 사실]` **They call the source directly.** The independent-service boundary and adapter [DP-012](decisions/DP-012-independent-scraper-services.md) selects do not exist, and neither does a rule baseline, a trend evaluator, or a card. |
| B4 | Not started | Real-data replay, failure, concurrency, recovery, security, and operator evidence. | [`B4-SCENARIO-COVERAGE.md`](../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md) and real captures against the live API on 2026-08-19, with digests for two of three and the third recorded as a lost-digest gap. Covers platform and acquisition failure; covers nothing about cards or trend classes. |
| B5 | Not started | Architecture Synthesis, disposition, `PoC Contract 0.1`, reconstruction plan, and P1 Entry Gate. | Architecture Synthesis v0.1, artifact disposition, and the P1 reconstruction plan are written. `[확인 사실]` They synthesize the pre-DP-011 delivery. The P1 Entry Gate has not been held. |

### Branch and agent-work disposition

`[확인 사실]` Checked against GitHub on 2026-08-19:

| Artifact | State | Delivery treatment |
|---|---|---|
| `main` | P0-A and the initial P0-B add-on work are accepted through PR #2. Its history has the gate merge commit that `dev` does not. | Do not work from it; `main` moves only at an accepted gate. |
| `dev` | Current at `c0a266d`, with six subsequent work commits not yet accepted into `main`. It contains EXP-003, its review, and the latest P0-B truth. | All deadline work branches from this revision or a later `dev`. |
| `.claude/agents/` on `dev` | `mechanical` and `addon-author` implement bounded work; `adversarial-reviewer` attacks claims with `Write`, `Edit`, and `NotebookEdit` denied. `[확인 사실]` **That is not "no write access"** — `Bash` remains, and [REVIEW-TASK-001](agent-workflow/reviews/REVIEW-TASK-001.md) F1 measured an attacker writing through it. An earlier revision of this row said "without write access". | Use these roles; keep implementation and adversarial review separate. The separation is a convention held by whoever assigns the work, not a barrier. |
| `feat/agent-operating-model` and its duplicate remote branch | `[확인 사실]` Reapplied on 2026-08-19 as `agent/operating-model`, branched from `6d1e965`: `b437013` merges it with `b702c79` preserved as a parent, the Decision Packet is renumbered [DP-013](decisions/DP-013-agent-workflow-and-project-memory.md), and `933bbae` records an independent review that returned `FAIL` on two blocking findings. No contract under `contracts/` is affected, which is the contract-reconciliation half of the earlier instruction. | Not merged into `dev` or `main`. `TASK-001` is `REWORK`; a second independent review is the condition for acceptance. Do not bundle it into the product-scope PR or treat any report as merge approval. |
| `p0a/platform-core` and `sooho` | Historical tips with no unique work beyond the accepted line. | No merge action. |

The current repository therefore has a worker/attacker split but no approved dedicated
planner subagent. The delivery lead remains the planner and issues one bounded work packet
at a time; restoring the larger operating model is not on the product critical path.

`[확인 사실]` Both sentences still hold as delivery statements on 2026-08-19. The operating
model was reapplied on a working branch (`agent/operating-model`) and has not entered `dev` or
`main`, so the delivery lead remains the planner and no deadline work depends on it. `[결정]`
What the reapplication changes is where the model's rules are written down, not who is doing
the deadline work.

### B1 bounded candidate set

The source/data owner profiles this set before expanding it:

| Mode | Candidate | Why it is bounded here | Hard check |
|---|---|---|---|
| REST service, primary | Independent Naver Blog collection service backed by the [Naver Blog Search API](https://developers.naver.com/docs/serviceapi/search/blog/blog.md) | The delivery team owns it, the source is Korean-market relevant, and a direct add-on prototype provides reference behavior without fixing the final boundary. | Original API terms and two-part credential, service export schema, stable batch and record IDs, retrievable-window truncation, adapter cursor, and repeat capture. |
| REST service, later adapter candidate | `trend-radar` export API | The implementation owner reports that it already runs independently and can be integrated without merging projects, but that integration is not urgent. | Compatibility review now; implementation only after the required Naver path. Before that: repository commit, runnable service, response fixture, source rights, stable batch/record identity, pagination, retention, and adapter replay. |
| REST service, second-channel stretch | `yt-scrapper`, only after its export contract is complete and YouTube quota is confirmed | It adds a distinct live channel while staying independently deployable. | Readiness, public-video/comment scope, quota budget, stable identity, dates, service schema, and time remaining after the required flow passes. |
| Dataset, primary | [Open Beauty Facts full export](https://support.openfoodfacts.org/help/en-gb/11-open-beauty-facts/70-where-can-i-download-open-beauty-facts-data) | It is a replayable cosmetics product/ingredient file with an open-data basis. | ODbL obligations, Korean sunscreen/toner coverage, ingredient completeness, stable row identity, and manageable fixture extraction. |
| Dataset, domestic fallback | [KHISS cosmetics industry statistics](https://www.data.go.kr/data/3081174/fileData.do) | It is a downloadable Korean cosmetics CSV and can exercise a distinct dataset path. | It is `NO-GO` if its aggregation level cannot contribute traceable evidence to the selected card or a small shared schema. |
| Canonical reference, not counted as a required input mode | [MFDS cosmetic ingredient information](https://www.data.go.kr/data/15111774/openapi.do) | Official standard name, English name, CAS number, origin/definition, and aliases can support ingredient identity. | Automatic development approval, field stability, usage basis, and no false treatment as product-demand evidence. |

Expanding beyond this table requires recording why every listed candidate failed a hard
check. A credential, reachable URL, or convenient CSV is not itself a `GO`.

### Five-person ownership

One person owns each row. Review does not transfer ownership.

| Role | Owns | Must hand off |
|---|---|---|
| Delivery lead | Scope control, owner decisions, representative communication, gate records, demo and final acceptance | Daily status against this table; no silent scope additions. |
| Platform/backend | EXP-003 findings, worker/capability wiring, credential and outbound policy, job recovery, independent Naver service, and its COSMAI adapter | Reproduction commands, service/adapter commits, versioned fixture, and passing focused/full suites. |
| Source/data — one-week member | B1 rights and capability profiles, source matrix, retained hashes/fixtures, selected collector configuration, dataset importer | Finish source decisions and importer by 2026-08-23; write a complete handoff by 2026-08-24. This role owns no unresolved item after that date. |
| Domain/trend | Schema 0.x, canonical product/ingredient/topic mapping, rule baseline, deterministic trend classes and evidence-card data | Mapping review sample, threshold fixtures, replay hashes, and abstention cases. |
| Operator/LLM | Domain API/dashboard, run inspection and retry, card presentation; optional grounded explanation only after required flow passes | Operator script/screens, evidence-link checks, and an LLM-off demo path. |

The one-week member is assigned a bounded, early-finishing artifact stream. Their work is
not allowed to remain the only place where a source retrieval or importer behavior is known.

### Dated critical path

| Date | Required work | Exit check | Stop or fallback rule |
|---|---|---|---|
| **08-19** | Accept DP-011 and DP-012; audit repository and branches; freeze two-category scope; assign owners; create the B1 experiment with its one-day timebox; start EXP-003 F2/F3/F1 and B1 candidate profiles in parallel. | This plan and both decisions are reviewed; every task has one owner and an artifact path; B1 is not `RUNNING` before its experiment record exists. | No new source, model, or UI feature enters without removing an item of equal or greater cost. |
| **08-20** | Repair F2, F3, and F1; re-measure EXP-003. Fix the service export/adapter contract and complete bounded rights and capability checks for REST-service and dataset candidates. Draft Schema 0.x from representative fields. | Each blocker has a regression test; the export contract names version, batch, record, cursor, and replay semantics; REST and dataset each have a profile and decision. | If the Naver service or export contract cannot run by noon, select another already approved REST-service candidate; do not revive two active Naver paths silently. |
| **08-21** | Repair F4, F5, and F7; add full mutation coverage for protected headers/importer refusal. Run the independent Naver service and its adapter through COSMAI with secrets outside the tree. | Service commit and adapter commit are recorded; identical batch replay, interrupted resume, credential, deadline, page, record, and refusal scenarios pass. | No real access means `NO-GO`; never replace it with an unapproved crawl or direct database read. |
| **08-22** | Implement and conform the selected dataset importer. Verify identical and changed imports, invalid rows, Raw lineage, duplicate policy, and sealed snapshot hashing. | Same file replays idempotently; changed file creates a traceable version; tampering is detected. | Reduce fixture size, not provenance or replay checks. |
| **08-23** | Implement `rule-baseline@0.1` for category, product, ingredient, and topic semantics. Add a disposable P0 trend evaluator over stored normalized results for DP-011 metrics and card payloads; do not create a permanent add-on kind by assumption. | Frozen input produces byte-identical normalized results and cards; ambiguous mappings abstain; every card claim has evidence IDs. | Drop fuzzy auto-merge before lowering precision; manual review is an accepted result. |
| **08-24** | Connect the complete run to the domain operator surface: source/run status, input and snapshot identity, failure, safe retry, normalized result, and card. Complete the one-week member's handoff. | A new operator can follow the runbook without direct database access or oral context. | Keep the LLM renderer off. A deterministic card is the required product. |
| **08-25** | Run B4: identical/changed input, partial source response, invalid dataset rows, interruption, duplicate delivery, lease recovery, normalization failure, manifest mismatch, and security scenarios. | Each failure is classified; collection and normalization recover independently; no secret or Raw payload leaks. | Fix only blocking correctness/reliability defects. Defer visual polish and second-channel work. |
| **08-26** | Functional freeze. Complete B5 synthesis, disposition, `PoC Contract 0.1`, P1 reconstruction plan, and the P1 Entry Gate. Run the end-to-end demo from clean instructions. | Gate records `GO`, accepted `CONDITIONAL GO`, or explicit blocker; required acceptance table below is filled with artifact links. | No feature work after freeze. An explicit blocker is preferable to an unsupported pass. |
| **08-27** | Independent adversarial verification, corrections to blocking findings only, owner demo, handoff, and tag or equivalent immutable revision. | Independent reviewer reproduces the required flow and cannot break the accepted claims within the declared boundary. | Any unfixed blocker changes the gate, not the evidence wording. |

### Required acceptance for functional freeze

| Area | Pass condition |
|---|---|
| Acquisition | One approved independent scraper REST service through a COSMAI adapter and one approved dataset complete the bounded end-to-end flow with rights, service and adapter commits, batch and source identity, capture time, and retrieval procedure recorded. |
| Reliability | Identical replay, changed input, duplicate delivery, interruption, retry exhaustion, and collection-versus-normalization recovery behave as contracted. |
| Canonical data | Sunscreen and toner records map to stable product, ingredient, topic, and evidence identifiers; ambiguous mappings abstain. |
| Trend | Every class is reproducible from stored windows, counts, thresholds, and code version; insufficient data cannot receive a positive trend class. |
| Evidence card | Every material statement resolves to stored `evidence_id` values and original URLs; unsupported sales, efficacy, or market-share claims are absent. |
| Operations | An operator can inspect source, run, input, snapshot, result, failure, and retry without direct database access. |
| Security and data handling | Secrets remain outside the tree; outbound, credential, redaction, response-bound, and data-retention scenarios pass. |
| Handoff | Clean runbook, source profile, importer procedure, schema/threshold version, known limitations, and P1 disposition are stored in the repository. |

### Scope order when time is lost

Cut in this order, from first to last:

1. LLM explanation renderer.
2. Second live channel, including YouTube.
3. `trend-radar` adapter implementation; retain only its contract compatibility notes.
4. Visual dashboard polish and exported briefs.
5. Additional seeds and alias coverage outside the reviewed sample.
6. Non-blocking moderate/minor EXP-003 findings only when the gate records them explicitly.

Do not cut provenance, Raw lineage, replay, snapshot hashes, canonical review status,
deterministic trend inputs, blocking security findings, or operator failure visibility.
