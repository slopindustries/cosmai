# P0-A Platform Core Completion Gate

- Status: `DRAFT` — awaiting the captain's signature
- Governing decision: [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md)
- Integrated experiment: [EXP-001](EXP-001-platform-core.md), `COMPLETED`, outcome `SUPPORTED`
- Reviewed code revision: `60807cba3e65e094c5870e46499dffe4577bdfd7` (`60807cb`), branch `p0a/platform-core`
- Evidence directory: [`evidence/2026-08-17-60807cb/`](evidence/2026-08-17-60807cb/)
- Review date and timezone: 2026-08-17, Asia/Seoul (UTC+09:00)
- Reviewers: the project owner, with an adversarial review of every `PASS` claim attached below

## Gate question

Is the source- and normalization-independent platform core executable, tested, and bounded enough to begin P0-B without claiming that source, acquisition, Raw, snapshot, or normalization behavior has been proved?

**Recommendation: `GO`.** The reasoning, and the five things this gate explicitly does not claim, are in the Decision section.

## How to re-run everything below

```sh
./scripts/with-database.sh uv run pytest           # 509 passed in 57.6 s
./scripts/with-database.sh uv run pytest -n 4      # 509 passed in 25.4 s
uv run ruff check . && uv run mypy .               # clean, 46 source files, strict
uv run pytest tests/environment                    # 21 passed — the boundary guard
cd experiments/integrated-p0/dashboard && npm run build
```

`[측정]` Full transcript: [`evidence/2026-08-17-60807cb/pytest-output.txt`](evidence/2026-08-17-60807cb/pytest-output.txt). Environment and tool versions: [`ENVIRONMENT.md`](evidence/2026-08-17-60807cb/ENVIRONMENT.md) in the same directory.

## Charter exit criteria

Each row is a criterion from the [P0 Charter](../../docs/p0-charter.md) "P0-A exit criteria" list, in its order.

| # | Criterion | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| 1 | Parallel job claims do not create conflicting active ownership | `PASS` | `JOB-007`, 10 passed; 200 jobs × 4 worker processes × 5 repetitions × 2 sample sets; `having count(*) > 1` empty every time; per-worker distribution near-uniform around 50, so all four contended | Four processes on one host at P0 volume. Nothing about throughput, fairness, or starvation; a starved job is possible and undetected |
| 2 | Duplicate execution does not produce an uncontrolled platform-level durable effect | `PASS` | `JOB-008`, 12 passed; 20 jobs sharing one key → 1 row and 19 suppressions; **20 distinct keys → 20 rows and 0 suppressions**, which is what makes the 19 keyed rather than blanket; each suppression emits its own event | **The effect is one row with a primary-key conflict** — the easiest instance of the problem. See "What this gate does not claim", item 1 |
| 3 | Interrupted or expired work reaches a documented recoverable or final state | `PASS` | `JOB-005`, 12 passed, both interruption points; `JOB-006`, 5 passed, a live stalled worker; every expired lease reclaimed in 130–168 ms | Processes end via `os._exit`, a clean kill at a chosen instruction. A real crash can land mid-statement, and PostgreSQL's own crash recovery is unexercised |
| 4 | Retry exhaustion produces an observable terminal state | `PASS` | `JOB-003`, 6 passed; exhausted job distinguishable from a backing-off one by `state`, `terminal_reason`, and `attempt_count` against `max_attempts`; not re-claimed afterwards | Small attempt budgets keep the scenario fast; no evidence at large budgets |
| 5 | The operator can inspect and safely retry generic work without direct database access | `PASS` | `OPS-001`, 14 passed, **with both psycopg connect entry points patched during every assertion** and a control proving the seal raises; `OPS-002`, 11 passed, retry of an already-applied effect adds no row and moves the suppression counter by 1 | Unauthenticated. Anything on the host can retry any job — evidence about idempotency, never about authority |
| 6 | Logs, metrics, errors, and screenshots preserve the declared redaction boundary | `PASS` | `SEC-004`, 60 passed; 8 redacted keys absent from 5 rendered screens, the log, and both API representations; the ordinary key's marker present as the detection control; protected representation still redacted | **Step 4's screenshot is not executed.** Screens are asserted as text, so a value hidden by CSS or in a DOM attribute would pass. Redaction is key-name based throughout |
| 7 | Operator surfaces bind to loopback by default | `PASS` | `SEC-002`, 25 passed; a non-loopback bind is **refused**, not merely defaulted away from, and `0.0.0.0` is not silently corrected; no PostgreSQL TCP listener; `inet_server_addr() IS NULL` | Evidence about binding, not authorization |
| 8 | The platform rejects a secret-store path inside the repository working tree | `PASS` | `SEC-001`, 25 passed, both entrypoints; a link resolving inside the tree refused and one resolving outside accepted, proving resolved-path comparison; **an unreadable store outside the tree still starts**, proving the guard never opens the file | Location only. File permissions are checked by the launcher and not re-checked at startup |
| 9 | The gate lists every acquisition and normalization behavior deferred to P0-B | `PASS` | The deferred-domain inventory below, maintained from the first commit as EXP-001's `Scope > Excluded` rather than reconstructed here | The inventory is mechanically enforced for Python and SQL only — see item 5 |
| 10 | The gate records `GO` or an explicitly accepted `CONDITIONAL GO` | `DRAFT` | This document | Requires the captain's signature |

Two further charter requirements are not numbered exit criteria and are recorded for completeness:

| Requirement | Result | Evidence |
|---|---|---|
| PostgreSQL runtime, migration mechanism, source-neutral transaction foundations | `PASS` | `0001_platform_core.sql` applied idempotently; the schema's constraints verified with `psql` alone, no Python involved |
| API and worker process lifecycle, health, configuration validation, safe shutdown | `PASS` | `SEC-003`, 44 passed, cases a–f; a stop signal lets the running attempt finish first; `OPS-004`, 11 passed, health reflects the database and recovers without a restart |

## Synthetic-handler coverage

| Platform behavior | Represented? | Evidence | Limitation carried into P0-B |
|---|---|---|---|
| Successful execution | `YES` | `JOB-001`, `succeed` | — |
| Retryable and permanent failure | `YES` | `JOB-002`, `JOB-003`, `JOB-004`; `fail_transient`, `fail_permanent`, `apply_effect_then_fail`, and an unregistered handler name | Retryability is **declared** by the handler. No evidence about classifying a genuinely ambiguous failure, which is a real P0-B question for source errors |
| Duplicate execution | `YES` | `JOB-008` cases A, B, C; `JOB-005` case B; `OPS-002` case A | Single-row effect only |
| Interruption and lease expiry | `YES` | `JOB-005` (`halt_before_effect`, `halt_after_effect`), `JOB-006` (`stall`) | `os._exit` rather than a real crash |
| Invalid platform configuration | `YES` | `SEC-003` cases a–f across both entrypoints | P0-A has no credential setting, so this proves the refusal mechanism, not that it holds for a credential |

`[확인 사실]` No synthetic handler imitates a collector, dataset importer, Raw payload, snapshot producer, or normalizer. Each either succeeds, fails with a declared class, applies one opaque effect, or ends its own process. `tests/environment/test_p0a_boundary_guard.py` enforces this for every Python identifier and every SQL object name under the experiment tree, and it fired once on real code during S1.

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

Additionally absent: `credential_ref` resolution or authorization semantics, and any outbound request whatsoever.

**How each was confirmed.** The nine items are EXP-001's `Scope > Excluded` list, copied there at S0 so the inventory was maintained from the first commit. The boundary guard turns the vocabulary half into a failing test for `.py` and `.sql`. `[확인 사실]` The dashboard is TypeScript and is checked by **file name only**; its vocabulary was held by fixing the substitutions before the code existed, and a recorded grep found no occurrence. That is a measurement at one moment, not a gate — see item 5 below.

## What this gate does not claim

Listed separately from the limitation column because each is a place where a reader could reasonably over-read a `PASS`.

1. **The idempotency boundary is not shown to hold for a realistic durable effect.** Every duplicate-suppression result rests on one row and one primary-key conflict. A P0-B acquisition or normalization effect spans several statements and probably several tables, where the question becomes transactional. This is the sharp form of OQ-006 H1 and the largest gap P0-A leaves.
2. **The transient database-failure path is unexercised.** `CONTRACT-JOB@0.1` classifies SQLSTATE classes `08`, `53`, and `57` as transient. `[확인 사실]` No scenario kills a connection mid-statement, so that branch is written and reviewable but carries no measurement. A connect-time failure is deliberately non-retryable, and `SEC-001`/`SEC-003` depend on that.
3. **Nothing is authenticated or authorized.** The API, the dashboard, the retry action, and the database are reachable by anything running on the host. P0-A produced binding evidence (`SEC-002`) and idempotency evidence (`OPS-002`) — never authority evidence.
4. **`SEC-004` step 4 is not executed.** The operator screens are asserted as rendered text from the real component tree, not captured as pixels. A value hidden by CSS or parked in a DOM attribute would pass. `dashboard/README.md` records the manual capture procedure. A reviewer who weighs this differently should read criterion 6 as `CONDITIONAL`.
5. **The frontend's vocabulary boundary is conventional, not mechanical.** Extending the guard to TypeScript was declined deliberately: a Python-side regex scanner would have to treat `//`, `/* */`, JSDoc, template literals, and JSX text as prose, and that same guard's SQL detector already misfired once for exactly this reason. A future contributor who does not read `dashboard/README.md` gets no warning from a test.
6. **One host, one PostgreSQL version, four worker processes, one day.** No evidence about clock skew larger than a lease between machines, throughput, fairness, or starvation.
7. **P0-A completion is not evidence that a real collector, dataset importer, Raw model, snapshot, or normalizer will work.** The charter says this in as many words and it is repeated here because it is the misreading with the largest consequence.

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
- Accepted conditions: none required for `GO`. The seven items in "What this gate does not claim" are limitations recorded for P0-B, not conditions on this gate — each is a boundary of what was measured rather than a defect in what was built. A reviewer who judges item 4 material should record `CONDITIONAL GO` with criterion 6 as its condition.
- Blocking failures: none.
- Failure classification: no exit criterion failed. Four defects were found and fixed during execution, each classified before being patched — one implementation failure (`redact_text` shielded by a preceding harmless pair) and three specification failures (a boundary guard reading prose as SQL, a scenario asking for a safe retry the contract forbids, a scenario asking which error class a health check produces). All four are recorded in EXP-001's Observations with the measurement that exposed them.
- P0-A work package to reopen for each blocker: none.
- **Also proposed for acceptance:** [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md), currently `DRAFT`. All eight of its decisions held under execution. Its recorded tension with Project State section 4 — declining three named library defaults without contrary evidence, on the argument that nothing was in use so the question was adoption rather than replacement — is the one item a reviewer should decide rather than ratify. If that reading is rejected, the correct outcome is to adopt those defaults in P0-A, not to leave the choice unrecorded.

## Reopen rule

If P0-B shows that a claimed P0-A boundary must be materially replaced:

1. classify the failure;
2. append the observation and the affected assumption to EXP-001;
3. set this gate to `REOPENED`;
4. return to the named P0-A work package;
5. re-review this gate before relying on the revised platform claim.

The assumption most likely to trigger this is the first in "Platform assumptions P0-B must challenge". A P0-B failure that stays inside the domain does **not** reopen this gate; only one that falsifies a platform premise does.
