# P0-A Platform Core Completion Gate

- Status: `DRAFT` — awaiting the captain's signature
- Governing decision: [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md)
- Integrated experiment: [EXP-001](EXP-001-platform-core.md), `COMPLETED`, outcome `SUPPORTED`
- Reviewed code revision: `139664424cf4ae21aa3ce054ba129afd617b9420` (`1396644`), branch `p0a/platform-core`
- Evidence directory: [`evidence/2026-08-17-1396644/`](evidence/2026-08-17-1396644/)
- Review date and timezone: 2026-08-17, Asia/Seoul (UTC+09:00)
- Reviewers: the project owner, with an [adversarial review](ADVERSARIAL-REVIEW-2026-08-17.md) of every `PASS` claim

## Gate question

Is the source- and normalization-independent platform core executable, tested, and bounded enough to begin P0-B without claiming that source, acquisition, Raw, snapshot, or normalization behavior has been proved?

**Recommendation: `GO`.**

The path here is worth stating, because the recommendation moved twice. The first draft said `GO` with criterion 6 marked `PASS` and a note inviting the reviewer to downgrade it — which declined a judgement the gate exists to make. An [adversarial review](ADVERSARIAL-REVIEW-2026-08-17.md) found three blocking defects in the record and was right about criterion 6, so the gate became `CONDITIONAL GO` with that cell as its condition.

Asked to defend the condition, I found I had specified it wrongly in both halves. The screenshot it demanded is the **weaker** artifact: the browser receives markup, so a value hidden by CSS or parked in an attribute is absent from a screenshot and present in what was delivered. And the log gap it claimed did not exist — a positive control was already there. The condition was discharged by asserting over the markup the renderer was already computing and discarding, which costs no dependency and is strictly stronger than a screenshot. Criterion 6 is now `PASS` on its own merits rather than by invitation.

The nine things this gate does not claim have their own section below.

## How to re-run everything below

Every command below was run at the reviewed revision. The first draft of this block did not survive that check: it cited a test count from one tree and a lint result from another, and its `mypy` claim was false at the revision it named.

```sh
./scripts/with-database.sh uv run pytest        # 507 passed, 2 skipped in 53.6 s
./scripts/with-database.sh uv run pytest -n 4   # 507 passed, 2 skipped
uv run ruff check . && uv run mypy .            # clean; strict, 46 source files
uv run pytest tests/environment                 # 21 passed — the boundary guard
cd experiments/integrated-p0/dashboard && npm run build
```

The two skips are the evidence-capture tests, which run only under `--capture-evidence=DIR`; with capture requested the suite is 509. Capturing is a separate act, which is why the recorded hashes can be verified at all:

```sh
./scripts/with-database.sh uv run pytest -k "ops_003 or sec_004" \
    --capture-evidence=experiments/integrated-p0/evidence/2026-08-17-1396644
```

`[확인 사실]` Full transcript: [`pytest-output.txt`](evidence/2026-08-17-1396644/pytest-output.txt). Environment, tool versions, and per-selector counts: [`ENVIRONMENT.md`](evidence/2026-08-17-1396644/ENVIRONMENT.md). The four artifact hashes in that directory's `README.md` verify with `shasum -a 256 -c`.

## Charter exit criteria

Each row is a criterion from the [P0 Charter](../../docs/p0-charter.md) "P0-A exit criteria" list, in its order.

| # | Criterion | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| 1 | Parallel job claims do not create conflicting active ownership | `PASS` | `JOB-007`, 10 passed; 200 jobs × 4 worker processes × 5 repetitions × 2 sample sets; `having count(*) > 1` empty every time; attempt count equal to job count exactly | `[추론]` **Contention is inferred, not asserted.** The per-worker distribution is printed, not asserted and not captured — one worker taking all 200 would pass. EXP-001 records a range from `33` to `57` per worker, so "near-uniform" overstates it. `claim_conflicts` read 0 in almost every run and is not a usable contention measure. Also: four processes on one host at P0 volume, nothing about throughput, fairness, or starvation |
| 2 | Duplicate execution does not produce an uncontrolled platform-level durable effect | `PASS` | `JOB-008`, 12 passed; 20 jobs sharing one key → 1 row and 19 suppressions; **20 distinct keys → 20 rows and 0 suppressions**, which is what makes the 19 keyed rather than blanket; each suppression emits its own event | **The effect is one row with a primary-key conflict** — the easiest instance of the problem. See "What this gate does not claim", item 1 |
| 3 | Interrupted or expired work reaches a documented recoverable or final state | `PASS` | `JOB-005`, 12 passed, both interruption points; `JOB-006`, 5 passed, a live stalled worker; every expired lease reclaimed in 130–168 ms | Processes end via `os._exit`, a clean kill at a chosen instruction. A real crash can land mid-statement, and PostgreSQL's own crash recovery is unexercised |
| 4 | Retry exhaustion produces an observable terminal state | `PASS` | `JOB-003`, 6 passed; exhausted job distinguishable from a backing-off one by `state`, `terminal_reason`, and `attempt_count` against `max_attempts`; not re-claimed afterwards | Small attempt budgets keep the scenario fast; no evidence at large budgets |
| 5 | The operator can inspect and safely retry generic work without direct database access | `PASS` | `OPS-001`, 14 passed, **with both psycopg connect entry points patched during every assertion** and a control proving the seal raises; `OPS-002`, 11 passed, retry of an already-applied effect adds no row and moves the suppression counter by 1 | Unauthenticated. Anything on the host can retry any job — evidence about idempotency, never about authority |
| 6 | Logs, metrics, errors, and screenshots preserve the declared redaction boundary | `PASS` | `SEC-004`, 72 passed. Every surface carries a positive control. **Screens:** 8 redacted keys absent from 5 screens in **both** the visible text and the markup a browser would receive, with the ordinary key's marker present in both. A value withheld by the default representation is absent from that screen's markup **searched by value, not by key** — proven to fire by planting a leak into an attribute. **Log:** `test_sec_004_the_structured_log_masks_a_payload_it_is_handed` hands the logger a marked payload and asserts the ordinary marker survives and the redaction count is exact; the platform additionally never writes a payload into an event, so the guarantee is tested *and* structural. **Metrics:** two assertions plus a closed label set | **No value is rendered into an image, so no image is captured.** That is the one channel the markup search cannot reach, and P0-A renders no images — the residue is empty rather than narrow. The charter's "screenshots" concerns screenshots as evidence artifacts and binds P0-B, which will capture domain screens. Redaction remains key-name based, and the value-based assertion covers only what the API withholds |
| 7 | Operator surfaces bind to loopback by default | `PASS` | `SEC-002`, 25 passed; a non-loopback bind is **refused**, not merely defaulted away from, and `0.0.0.0` is not silently corrected; no PostgreSQL TCP listener; `inet_server_addr() IS NULL` | Evidence about binding, not authorization |
| 8 | The platform rejects a secret-store path inside the repository working tree | `PASS` | `SEC-001`, 25 passed, both entrypoints; a link resolving inside the tree refused and one resolving outside accepted, proving resolved-path comparison; **an unreadable store outside the tree still starts**, proving the guard never opens the file | Location only. File permissions are checked by the launcher and not re-checked at startup |
| 9 | The gate lists every acquisition and normalization behavior deferred to P0-B | `PASS` | The deferred-domain inventory below, now reconciled item by item against [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) §Excluded, which is the binding authority. `[확인 사실]` The nine-item list is present in EXP-001's first commit, so "maintained from the first commit" holds | The first draft cited EXP-001 as the source while EXP-001 cited the gate — circular, and six DP-005 behaviors were missing as a result. They are added below. Enforcement is mechanical for Python and SQL identifiers only — see items 5 and 8 |
| 10 | The gate records `GO` or an explicitly accepted `CONDITIONAL GO` | `DRAFT` | This document | Requires the captain's signature |

Two further charter requirements are not numbered exit criteria and are recorded for completeness:

| Requirement | Result | Evidence |
|---|---|---|
| PostgreSQL runtime, migration mechanism, source-neutral transaction foundations | `PASS` | `0001_platform_core.sql` applied idempotently; the schema's constraints verified with `psql` alone, no Python involved |
| API and worker process lifecycle, health, configuration validation, safe shutdown | `PASS` | `SEC-003`, 44 passed, cases a–f; a stop signal lets the running attempt finish first; `OPS-004`, 11 passed, health reflects the database and recovers without a restart |
| Structured logs, metrics, **correlation**, redaction — and DP-005's "telemetry foundations" | `PASS` | `OPS-003`, 8 passed. One `correlation_id` returned the events of two worker processes across a process death, with a control proving an unrelated job's events are excluded. Captured artifact: [`ops-003-correlated-events.json`](evidence/2026-08-17-1396644/ops-003-correlated-events.json) and the log it was filtered from. Omitted from the first draft of this table, which left a DP-005 bullet unlinked |

## Synthetic-handler coverage

| Platform behavior | Represented? | Evidence | Limitation carried into P0-B |
|---|---|---|---|
| Successful execution | `YES` | `JOB-001`, `succeed` | — |
| Retryable and permanent failure | `YES` | `JOB-002`, `JOB-003`, `JOB-004`; `fail_transient`, `fail_permanent`, `apply_effect_then_fail`, and an unregistered handler name | Retryability is **declared** by the handler. No evidence about classifying a genuinely ambiguous failure, which is a real P0-B question for source errors |
| Duplicate execution | `YES` | `JOB-008` cases A, B, C; `JOB-005` case B; `OPS-002` case A | Single-row effect only |
| Interruption and lease expiry | `YES` | `JOB-005` (`halt_before_effect`, `halt_after_effect`), `JOB-006` (`stall`) | `os._exit` rather than a real crash |
| Invalid platform configuration | `YES` | `SEC-003` cases a–f across both entrypoints | P0-A has no credential setting, so this proves the refusal mechanism, not that it holds for a credential |

`[확인 사실]` No synthetic handler imitates a collector, dataset importer, Raw payload, snapshot producer, or normalizer. Each either succeeds, fails with a declared class, applies one opaque effect, or ends its own process.

`[확인 사실]` `tests/environment/test_p0a_boundary_guard.py` enforces the vocabulary over **Python identifiers, and identifiers inside `.sql` files**, and it fired once on real code during S1. `[확인 사실]` It does **not** cover string literals that are not recognised as SQL: an adversarial review planted `sql.Identifier("observation")`, a `"raw_response"` API-key constant, and a list of domain-shaped column names in a P0-A module and the guard passed, while one real identifier failed it immediately. `psycopg.sql.Identifier` is how this codebase composes dynamic identifiers and API response keys are string literals throughout, so this is a live gap, not a hypothetical one. Recorded in item 8 below.

## Deferred-domain inventory

Each item confirmed absent from P0-A implementation **and** from its acceptance claims.

- [x] REST and dataset candidate exploration or selection
- [x] Source rights decision, source fixture, or outbound request
- [x] Source registration semantics or concrete host policy
- [x] Collector or dataset-importer interface, test double, or implementation
- [x] Raw response, Raw record, observation identity, or duplicate semantics
- [x] Snapshot, manifest, or Raw-to-result lineage
- [x] Normalized Schema 0.x, provider protocol, test double, or rules
- [x] Acquisition- or normalization-specific dashboard behavior
- [x] `ACQ`, `RAW`, `SNP`, or `NRM` pass claim

Reconciled against [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) §Excluded, which named six behaviors the nine items above do not spell out. Each is confirmed absent:

- [x] Pagination, rate policy, record mapping, and source identity
- [x] Changed-source-content semantics
- [x] Normalization decision use, and normalized result persistence
- [x] **Domain-specific `OPS` or `SEC` acceptance claims** — this one bounds what P0-A did claim. Four `OPS` and four `SEC` scenarios executed, and every one is platform-level: they concern job state, attempts, correlation, health, metrics, configuration, binding, the secret-store location, and redaction. None names a source, a Raw payload, a snapshot, or a normalizer.
- [x] `credential_ref` resolution or authorization semantics
- [x] Any outbound request whatsoever

**How each was confirmed.** The nine items are EXP-001's `Scope > Excluded` list, copied there at S0 so the inventory was maintained from the first commit. The boundary guard turns the vocabulary half into a failing test for `.py` and `.sql`. `[확인 사실]` The dashboard is TypeScript and is checked by **file name only**; its vocabulary was held by fixing the substitutions before the code existed, and a recorded grep found no occurrence. That is a measurement at one moment, not a gate — see item 5 below.

## What this gate does not claim

Listed separately from the limitation column because each is a place where a reader could reasonably over-read a `PASS`.

1. **The idempotency boundary is not shown to hold for a realistic durable effect.** Every duplicate-suppression result rests on one row and one primary-key conflict. A P0-B acquisition or normalization effect spans several statements and probably several tables, where the question becomes transactional. This is the sharp form of OQ-006 H1 and the largest gap P0-A leaves.
2. **The transient database-failure path is unexercised.** `CONTRACT-JOB@0.1` classifies SQLSTATE classes `08`, `53`, and `57` as transient. `[확인 사실]` No scenario kills a connection mid-statement, so that branch is written and reviewable but carries no measurement. A connect-time failure is deliberately non-retryable, and `SEC-001`/`SEC-003` depend on that.
3. **Nothing is authenticated or authorized.** The API, the dashboard, the retry action, and the database are reachable by anything running on the host. P0-A produced binding evidence (`SEC-002`) and idempotency evidence (`OPS-002`) — never authority evidence.
4. **No screen is captured as an image.** The operator screens are asserted in two forms — the visible text and the markup a browser receives — which covers the attribute and hidden-element channels a screenshot would miss. What neither reaches is a value rendered into an image; P0-A renders none, so that residue is empty. P0-B will capture domain screens and inherits the charter's obligation about screenshots as artifacts.
5. **The frontend's vocabulary boundary is conventional, not mechanical.** Extending the guard to TypeScript was declined deliberately: a Python-side regex scanner would have to treat `//`, `/* */`, JSDoc, template literals, and JSX text as prose, and that same guard's SQL detector already misfired once for exactly this reason. A future contributor who does not read `dashboard/README.md` gets no warning from a test.
6. **One host, one PostgreSQL version, four worker processes, one day.** No evidence about clock skew larger than a lease between machines, throughput, fairness, or starvation.
7. **The root test session imports experiment code.** `tests/conftest.py` calls `platform_core.config.secret_store_location_problem` so that the secret-store guard has one implementation rather than two that can disagree. It is a test-session dependency and not a runtime or package one, so DP-001 is unaffected — but the repository's own test session **stops guarding when `experiments/integrated-p0/` is disposed of**. This belongs in the P0-B artifact disposition register, and it is the item most easily lost, since the failure mode is a collection error in a P0-B session that nobody is expecting.
8. **The boundary guard does not read string literals that are not SQL, or TypeScript at all.** An adversarial review put `sql.Identifier("observation")` and a `"raw_response"` API-key constant into a P0-A module and the guard passed. The vocabulary is mechanically enforced for identifiers and conventionally enforced everywhere else.
9. **P0-A completion is not evidence that a real collector, dataset importer, Raw model, snapshot, or normalizer will work.** The charter says this in as many words and it is repeated here because it is the misreading with the largest consequence.

## P0-B entry readiness

- **Deferred Open Questions.** [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md), [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md), and [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md) each have their P0-A minimum experiment completed and each remains `OPEN`. None may be closed on P0-A evidence: OQ-005 needs domain navigation objects, OQ-006 needs H3 and a realistic effect, OQ-007 needs a credential to resolve. [OQ-001](../../docs/open-questions/OQ-001-source-capability.md) through [OQ-004](../../docs/open-questions/OQ-004-snapshot-boundary.md) are untouched by P0-A, as DP-005 requires.
- **Platform assumptions P0-B must challenge**, in the order they are likely to break:
  1. that one `effect_key` and one unique index are a sufficient idempotency boundary;
  2. that a connect-time failure should never be retried — a collector mid-run may need the other answer;
  3. that a lease-expiry reclaim consuming an attempt is correct when the crash was unrelated to the job;
  4. that one correlation identifier per job suffices, when a collection run over many pages is a fan-out;
  5. that metrics may live in process memory, which already prevents the platform from reporting that no worker is running.
- **Known extension points, and why each is source-neutral.** The handler registry takes a name and a callable and knows nothing else. `job.payload` is `jsonb` the platform never interprets. `platform_effect.payload` is structureless by decision ([DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D8) precisely so it cannot become a Raw envelope. The error table is a closed set of platform classes with no source dimension. None of these is an acquisition or normalization framework under another name; each is testable without source semantics, which is DP-005's own condition for an allowed seam.
- **P0-B experiment owner:** to be recorded when B1 is scoped.
- **P0-B proposed timebox:** to be recorded before the B1 experiment status becomes `RUNNING`, as DP-005 requires. P0-A's one-day timebox is not a precedent — B1 involves external sources and rights review.
- **External-input safety review required before first probe: `YES`.** `docs/conventions/p0-security.md` requires `allowedDomains` narrowed to the registered source hosts, `deniedDomains` stated, `autoAllowBashIfSandboxed` reconsidered, and the adjustment recorded in the first probe's experiment record. **`[확인 사실]` This has not been done, and P0-A ran with a deliberately broad sandbox that must not carry into P0-B.**

## Decision

- Outcome: `GO` — **proposed**, pending signature.
- `[결정]` (proposed): The source- and normalization-independent platform core is executable, tested, and bounded. P0-B may begin with source exploration under B1.
- **Accepted conditions: none.** Criterion 6's condition was discharged rather than carried: the markup a browser receives is now asserted over, including a key-independent search for values the default representation withholds, and both were shown to fire against planted leaks. No dependency was added and [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D6's floor stands.
- The items in "What this gate does not claim" are **not** conditions. Each is a boundary of what was measured rather than a defect in what was built, and each is carried into P0-B rather than fixed here.
- Blocking failures: none in the platform. **Three in this document's first draft**, all found by the [adversarial review](ADVERSARIAL-REVIEW-2026-08-17.md) and all fixed at the revision now under review: a `mypy` error introduced by the gate commit itself, so the gate's own "clean, strict" claim was false at the revision it named; an evidence directory named for a revision whose tree could not have produced its contents — **the second time in two commits**, which is what showed the naming was bound to nothing; and three of four recorded hashes failing their own verification instruction, because the scenarios rewrote the artifacts on every run.

  The common cause of the last two was mine and structural: a test that writes into committed evidence during a run cannot name the revision that produced it, because the name is only knowable afterwards. Capture is now opt-in, the artifacts land in a commit that changes no code, and the claim is checkable with `git diff` rather than asserted in prose.
- Failure classification: no exit criterion failed. Defects found and fixed during execution, each classified before being patched:
  - one **implementation** failure — `redact_text` returned a sensitive value unchanged whenever a harmless pair preceded it;
  - three **specification** failures — a boundary guard that parsed English prose as SQL, a scenario asking for a safe retry the contract forbids, and a scenario asking which error class a health check produces;
  - three **record** failures found by adversarial review, listed above.

  `[확인 사실]` The first four are recorded in EXP-001's Observations with the measurement that exposed each. **One correction to the first draft's claim:** the safe-retry conflict is recorded in EXP-001's Interpretation and in `JOB-008`'s revision note, but not as an Observation, and `test_job_concurrency.py` still says resolving it "needs a Decision Packet" while the scenario was amended in place instead. AGENTS.md requires a consequential ambiguity to become an Open Question or Decision Packet rather than be resolved silently. **This is an open action, recorded here rather than closed.**
- P0-A work package to reopen for each blocker: none.
- **[DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) is `ACCEPTED_FOR_POC` as of 2026-08-17.** All eight of its decisions held under execution. Its recorded tension with Project State section 4 — declining five named library defaults without contrary evidence, on the argument that nothing was in use so the question was adoption rather than replacement — was the one item put to the reviewer to decide rather than ratify.

  `[결정]` The reviewer accepted that reading and required the sentence itself be clarified, which is now done: Project State section 4 separates adopting a default (optional, needs a recorded reason) from replacing one already in use (needs contrary evidence). The clarification matters beyond this packet — P0-B meets the same question again with FastAPI and HTTPX, and would otherwise have had to re-argue it.

## Reopen rule

If P0-B shows that a claimed P0-A boundary must be materially replaced:

1. classify the failure;
2. append the observation and the affected assumption to EXP-001;
3. set this gate to `REOPENED`;
4. return to the named P0-A work package;
5. re-review this gate before relying on the revised platform claim.

The assumption most likely to trigger this is the first in "Platform assumptions P0-B must challenge". A P0-B failure that stays inside the domain does **not** reopen this gate; only one that falsifies a platform premise does.
