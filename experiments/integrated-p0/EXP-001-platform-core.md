# EXP-001 — Source- and normalization-independent platform core

## Identity and status

- Experiment ID: `EXP-001`
- Type: `INTEGRATED_P0`
- Status: `RUNNING`
- Related Open Question or Decision Packet: OQ-005, OQ-006, OQ-007; [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md)
- Owner: Project team
- Created at: 2026-08-17T00:00:00+09:00
- Last executed at: in progress, 2026-08-17

The hypothesis, falsification condition, exit condition, and timebox below were fixed before the status became `RUNNING`. Any later revision is appended with its reason rather than overwriting the original boundary.

This is the P0-A integrated experiment required by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) and work package A1 of the [P0 Execution Plan](../../docs/p0-execution-plan.md). Its outcome feeds the P0-A Completion Gate.

## Question

Can a platform core that has no selected source, no acquisition model, and no normalization semantics produce execution, recovery, operator, and safety evidence that is interpretable on its own — that is, evidence P0-B can build on rather than evidence that only becomes meaningful once a domain exists?

## Hypothesis

Two claims from [Project State](../../docs/project-state.md) section 5 are in scope. They are not independent: H2 is the mechanism H1's execution claim depends on, so they share one experiment rather than being split.

`[가설]` **H1** — A source- and normalization-independent platform core can expose useful execution, recovery, operator, and safety evidence before P0-B introduces the domain pipeline.

`[가설]` **H2** — PostgreSQL job tables with at-least-once processing and idempotent platform effects are sufficient for P0 concurrency.

H2 restates OQ-006's H1 and H2 at the platform level. OQ-006's H3 (whether collector and normalizer jobs need separate state and retry policy) is **not** in scope; it cannot be tested without the domain.

## Falsification condition

**H1 is refuted if** any of the following is observed:

- a required platform behavior cannot be specified or tested without naming a source, an acquisition step, a Raw payload, a snapshot, or a normalized result;
- the platform surfaces built here cannot be exercised by a synthetic handler without that handler imitating a collector, importer, Raw payload, snapshot producer, or normalizer;
- an operator scenario in the `OPS` family cannot be completed without direct database inspection **and** the missing capability turns out to be domain-shaped rather than platform-shaped.

**H2 is refuted if** any of the following is observed:

- two workers hold conflicting active ownership of one job;
- an injected duplicate delivery produces a durable effect that the recorded idempotency boundary cannot detect or reconcile;
- a tested interruption leaves work permanently stranded, or reaches a state with no documented recovery or finalization path;
- retry exhaustion does not reach an observable terminal state.

A refutation of H2 does not automatically refute H1; it may instead mean the platform needs a different concurrency mechanism. The distinction is recorded in Interpretation, not assumed.

## Exit condition

The experiment stops at whichever comes first:

- every P0-A exit criterion in the [P0 Charter](../../docs/p0-charter.md) has a `PASS`, `FAIL`, or `NOT RUN` result with linked evidence; or
- the timebox below is exhausted.

**Timebox: 1 working day (8 hours), 2026-08-17.**

Timebox exhaustion reduces scope; it does not convert missing evidence into a pass. The pre-declared descope order is:

1. reduce the number of `OPS` scenarios to three;
2. fix the dashboard at three screens with no metrics visualisation;
3. defer the formal evidence run and record the gate as `CONDITIONAL GO`.

The following are never descoped, because the gate is meaningless without them: parallel-claim and duplicate-delivery evidence, the secret-store location and loopback guards, and the boundary guard test.

## Scope

### Included

- PostgreSQL runtime connection, migration mechanism, and source-neutral transaction foundations
- Handler-neutral job creation, claim, lease, attempt, retry scheduling, terminal state, interruption, and recovery
- API and worker process lifecycle, health, configuration validation, and safe shutdown
- A source-neutral operator surface for platform health, generic job state, correlated logs and metrics, failure inspection, and safe retry
- Structured logging, metrics, correlation identifiers, redaction, loopback binding, and the repository-external secret-store location guard at application startup
- Deterministic synthetic handlers and failure injectors for success, retryable failure, permanent failure, duplicate execution, interruption, and invalid configuration
- Replayable `JOB`, platform `OPS`, and platform `SEC` acceptance evidence

### Excluded

Every item below is deferred to P0-B and must be absent from this experiment's implementation **and** from its acceptance claims. This list is copied from the P0-A Completion Gate's deferred-domain inventory so that the inventory is maintained from the first commit rather than reconstructed at the gate.

- REST and dataset candidate exploration or selection
- Source rights decision, source fixture, or outbound request
- Source registration semantics or concrete host policy
- Collector or dataset-importer interface, test double, or implementation
- Raw response, Raw record, observation identity, or duplicate semantics
- Snapshot, manifest, or Raw-to-result lineage
- Normalized Schema 0.x, provider protocol, test double, or rules
- Acquisition- or normalization-specific dashboard behavior
- `ACQ`, `RAW`, `SNP`, or `NRM` pass claim

Additionally excluded: `credential_ref` resolution and authorization semantics (OQ-007 assigns these to P0-B); OQ-006 H3; production topology, scale targets, and polished UX.

## Inputs and provenance

| Input | Source or provider | Captured at | License or usage basis | Version or hash | Storage note |
| --- | --- | --- | --- | --- | --- |
| Synthetic job payloads | Generated in-test by `platform_core.handlers` | n/a | Project-authored, no third-party rights | Deterministic from test fixtures | Not persisted outside the disposable local cluster |
| Synthetic secret-store fixtures | Generated in-test under `tmp_path` | n/a | Project-authored | n/a | Never written inside the working tree |

This experiment consumes no external data, makes no outbound request, and uses no real credential. Data class is `public` throughout, which is why the evidence directory is committed.

## Environment

- Code revision: recorded at execution time in each evidence directory
- Runtime and dependency versions: Python 3.13 (pinned by `.python-version`), dependencies resolved by `uv.lock`; Node and PostgreSQL supplied either by the optional Nix shell or by the host
- External service or database versions: PostgreSQL as resolved locally; exact version recorded per evidence run
- Relevant configuration with secrets removed: repository-local cluster at `var/postgres` with `listen_addresses = ''`, Unix socket only, no role password ([DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D2). Operator surfaces bind to loopback by default.
- Reproduction command: `./scripts/with-database.sh uv run pytest`

## Procedure

Executed as six vertical slices. The order is deliberate: the Execution Plan's A2.1–A2.6 is a component list, and following it literally would build the least uncertain surfaces (API, dashboard) before the most uncertain one (concurrency).

1. **S0 — Foundation.** Record [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md); write [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md); draft the `JOB` and `SEC` acceptance scenarios; create the module layout, database launcher, and boundary guard.
2. **S1 — Execution skeleton.** Configuration validation, structured logging with the redaction boundary and correlation identifiers, database connection and migrations, and job create/claim/execute/terminal with a synthetic success handler. The log schema and the redaction boundary are built together here; adding redaction later would make the `SEC` evidence retrospective.
3. **S2 — Failure surface.** Retry scheduling, attempt records, retry exhaustion, permanent failure, lease acquisition and expiry, and interruption injected both before and after a durable effect.
4. **S3 — Concurrency.** Two worker processes against one database: claim exclusivity under `FOR UPDATE SKIP LOCKED`, duplicate delivery, and idempotent `platform_effect` behavior. **This is the decision point for H2.** If H2 is refuted here, the experiment stops and reports rather than continuing to S5.
5. **S4 — Safety.** Secret-store location guard on the application startup path, loopback binding default, invalid-configuration rejection as a non-retryable configuration failure, and redaction verified across logs, errors, and API responses.
6. **S5 — Operator surface.** Operator HTTP API first, then the `OPS` scenarios written against the failures S2 and S3 actually produced, then the minimal dashboard, then worker lifecycle and safe shutdown.
7. **S6 — Evidence and gate.** Formal evidence run, this record's Observations and Result, the gate record, and an adversarial review of every `PASS` claim before the gate is signed.

Concurrency, retries, failure injection, and cleanup are specified per scenario in `tests/acceptance/`. Lease durations are configurable and set short in tests so that expiry is observed without real elapsed time.

## Evidence collection

- Metrics and units: job state transition counts, attempt counts, claim conflicts observed (count), duplicate durable effects observed (count), retry exhaustion latency (ms), lease recovery latency (ms)
- Log or trace location: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/platform.jsonl`
- Output artifact location: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/`
- Integrity check or hash procedure: each evidence directory contains `ENVIRONMENT.md` recording the code revision, tool versions, and reproduction command. Structured logs use `.jsonl` rather than `.log` because `.gitignore` excludes `*.log` and the evidence must be reviewable from the repository.

## Observations

Record direct experimental outcomes as `[측정]`. Include input size, environment, execution time, units, and error bounds or known limits.

Slice results are appended as they are produced. The formal evidence run in S6 supersedes none of them; it repeats them from one recorded revision so the gate reads a single consistent set.

### S0 — environment and boundary

```text
[측정] The repository-local cluster starts and is reachable over its Unix socket only.
```

- procedure: `./scripts/with-database.sh sh -c 'psql -h "$COSMA_DB_HOST" -d "$COSMA_DB_NAME" -Atc "select current_database(), version(), inet_server_addr() is null"'`
- observed: `cosma_p0|PostgreSQL 18.4 on aarch64-apple-darwin25.6.0, compiled by clang version 21.1.8, 64-bit|t`
- corroboration: `lsof -nP -iTCP -sTCP:LISTEN` lists no PostgreSQL process
- captured_at: 2026-08-17
- limitation: this is partial `SEC-002` evidence covering the database only. The operator API does not exist yet, and no scenario has been run.

```text
[측정] The boundary guard fails on a real violation rather than only on a planted one.
```

- procedure: `uv run pytest tests/environment/test_p0a_boundary_guard.py` against S1 work in progress
- observed: 10 findings across two files, all on the identifier `normaliz*`, none from comments or docstrings
- classification: **specification failure**, not implementation failure. The `normaliz*` entry targets the domain sense (`Normalized Schema 0.x`, the normalizer provider protocol) and cannot distinguish it from "normalize a key to lowercase". Weakening the entry would let `normalized_result` pass later, so the guard was kept and the identifiers were renamed. The substitutes (`casefold`, `canonical`, `fold`) are recorded in the guard's own docstring so the next task does not rediscover this.
- captured_at: 2026-08-17
- limitation: says nothing about whether the guard's other entries are correctly scoped. Only `normaliz*` has been tested against real code so far.

### S1 — configuration, logging, redaction, correlation, metrics

```text
[측정] The platform instrumentation layer passes its checks without a database.
```

- procedure: `uv run pytest`, `uv run ruff check .`, `uv run mypy .`
- observed: 163 passed in 1.07 s; ruff clean; mypy strict clean across 19 source files; boundary guard green
- environment: Python 3.13, dependencies from `uv.lock`, no PostgreSQL involved
- captured_at: 2026-08-17
- limitation: partial `SEC-003` and `SEC-004` coverage only. No entrypoint exists, so "the process exits non-zero" is observed through a configuration-loading subprocess rather than through the worker or API. `SEC-004` needs the API's two representations and a dashboard screenshot, none of which exist yet.

```text
[측정] The text-redaction path failed on a sensitive value that a harmless pair preceded.
```

- procedure: `redact_text('rejected: api_key=marker-must-not-leak-42')` during S1
- observed: the input was returned unchanged. The pattern matched `key='rejected'` and swallowed `api_key=marker-must-not-leak-42` as its value, so the sensitive key was never tested. The same input without the leading pair masked correctly.
- classification: **implementation failure.** The test asserted the contract; the pattern admitted any key rather than only a sensitive one.
- resolution: the pattern is generated from the redacted-key set, so a harmless pair cannot shield a sensitive one. Regression tests cover a preceding harmless pair, several sensitive pairs in one string, six spellings of a separated key, and a detection control.
- captured_at: 2026-08-17
- limitation: key-based matching cannot reach a value written into prose with no key beside it. That limit is now stated as a producer obligation in the contract rather than left to the masking function.

```text
[추론] A detection control is what turned this from an untested path into a caught defect.
```

SEC-004 requires a marker under an ordinary key precisely so that "nothing leaked" is distinguishable from "nothing was looked at." The failing case here is the same shape one step earlier: had the scenario asked only that a sensitive value be absent, the unchanged string would have satisfied it — the marker was absent from the output for the trivial reason that the output was the input. Supporting measurements: the failing assertion above, and the passing control asserting an ordinary key's value survives.

### S1 — schema, migrations, and test isolation

```text
[측정] Two of the contract's invariants are enforced by the database, provable without application code.
```

- procedure: `psql -f` against a fresh clone of the migrated template, no Python involved
- observed:
  - a second attempt with `finished_at IS NULL` on one job → `duplicate key value violates unique constraint "job_attempt_one_open_per_job"`; open attempts remain 1 (**I2, claim half**)
  - after closing attempt 1, a second attempt inserts normally and total attempts becomes 2 — so the index constrains concurrency rather than reclaim
  - setting `finished_at` without an `outcome` → `violates check constraint "job_attempt_closes_with_an_outcome"`
  - a duplicate `effect_key` → `violates unique constraint "platform_effect_pkey"`; effects remain 1 (**I1, database half**)
  - `attempt_count` above `max_attempts` → `violates check constraint "job_attempts_stay_within_budget"` (**I4**)
  - `state = 'WEIRD'` → `violates check constraint "job_state_is_known"`
- environment: PostgreSQL 18.4, migration `0001_platform_core.sql`
- captured_at: 2026-08-17
- limitation: **this is only the claim half of I2.** The contract's fencing rule also requires refusing a stale worker's late write, and no index can express that — a reclaimed worker's own attempt is already closed, but nothing in SQL alone stops it updating the `job` row. That half is owed by the state machine and is `JOB-006`'s evidence.

```text
[측정] Test isolation holds under parallel workers, and the concurrency fixture deliberately does not isolate.
```

- procedure: `./scripts/with-database.sh uv run pytest -q` and the same with `-n 4`
- observed: 219 passed sequentially in 4.7 s; 219 passed in 2.8 s across four workers, no flake across repeats. Without the launcher, 164 pass and 55 skip with a message naming the launcher rather than failing on a missing database.
- captured_at: 2026-08-17
- limitation: isolation is per test, by cloning a migrated template. The `concurrency` fixture is the deliberate exception — it hands several worker processes one database, because that is what `JOB-006`, `JOB-007`, and `JOB-008` are evidence about. It is currently unused; no concurrency scenario has run yet.

```text
[추론] Writing the invariants as database constraints moved three of them out of reach of an implementation mistake.
```

I1's suppression, I2's claim exclusivity, and I4's attempt budget now fail at insert time regardless of what the state machine believes. The state machine still owes the fencing half of I2, the transition rules, and I3 — none of which a constraint can express — so this narrows what the concurrency scenarios have to establish rather than replacing them. Supporting measurements: the pure-SQL run above, and the two invariants it could not cover.

### S1 — state machine, fencing, and JOB-001

```text
[측정] A worker that lost its lease cannot record a completion, and its refusal changes nothing.
```

- procedure: claim a job as worker A with a 1 s lease; expire the lease; reclaim as worker B; snapshot the `job` and `job_attempt` rows; call `complete_success` as A; compare
- observed:
  - reclaim closed attempt 1 as `ABANDONED` with `error_class = LEASE_ABANDONED`, and open attempts remained 1 — so the claim statement closed the old attempt before opening the new one
  - A's completion returned `accepted=False` with the reason naming both fence halves
  - the `job` row and the `job_attempt` row were **byte-identical to their pre-call snapshots**, compared field by field including `updated_at`
  - `platform_effect` remained empty
  - `rejected_completions=1`, `abandoned_attempts=1`, `lease_recovery_latency` recorded once at 1000.2 ms
  - the refusal logged at `WARNING` carrying the job's `correlation_id` (I5 holds on the refusal path)
  - worker B then completed normally and the job reached `SUCCEEDED`
- environment: PostgreSQL 18.4, `platform_core.jobs.store`, single process
- captured_at: 2026-08-17
- limitation: the stale worker is simulated by expiring the lease directly rather than by a process that actually stalls. `JOB-006` is the real form and needs two processes.

```text
[측정] JOB-001 executes.
```

- procedure: `./scripts/with-database.sh uv run pytest -k job_001`
- observed: 7 passed. Full suite 262 passed sequentially and under `-n 4`; ruff, mypy strict across 34 files, and the boundary guard all clean.
- captured_at: 2026-08-17
- limitation: `JOB-002` through `JOB-008` remain `NOT RUN`. The store supports their paths — retry exhaustion, lease recovery, duplicate suppression, and parallel claim exclusivity each pass in single-process form — but a single-process test is not the evidence those scenarios ask for.

```text
[추론] Making the refusal return a value rather than raise is what made "changes nothing" checkable.
```

An exception would have left the caller to decide whether anything had been written, and the natural implementation — attempt the write, catch the violation — would already have touched the row. Fencing the write inside the statement's own `WHERE` means a refused completion never reaches the row at all, which is why the before-and-after comparison above is exact rather than approximate. Supporting measurements: the identical row snapshots, and the empty `platform_effect`.

### S2 — failure surface, worker process, JOB-002 through JOB-005

```text
[측정] The four single-job failure scenarios execute.
```

- procedure: `./scripts/with-database.sh uv run pytest -k job_00N` for N in 2..5
- observed: JOB-002 7 passed, JOB-003 6 passed, JOB-004 7 passed, JOB-005 12 passed. Full suite 311 passed sequentially (32 s) and under `-n 4` (19 s); ruff, mypy strict across 38 files, and the boundary guard clean.
- environment: PostgreSQL 18.4, `python -m platform_core.worker`, Python 3.13
- captured_at: 2026-08-17
- limitation: every one of these runs a single job through a single worker at a time. Nothing here is evidence about contention; `JOB-006` through `JOB-008` are.

```text
[측정] Interruption before and after the durable effect are distinguishable, and both end with one effect row.
```

- procedure: `JOB-005` cases A and B, each from an empty state. A worker subprocess claims the job, the handler ends the process with `os._exit` either side of the effect, the lease is expired, and a second worker finishes the job.
- observed: both cases end with exactly one `platform_effect` row, two attempts, the first `ABANDONED`, and the job `SUCCEEDED`. The recovering worker's `suppressed_duplicate_effects` is **0 in case A and 1 in case B**, while `abandoned_attempts`, `lease_recovery_latency` count, and `rejected_completions` are identical across both.
- captured_at: 2026-08-17
- limitation: the process is ended with `os._exit`, which is a clean kill at a chosen instruction. A real crash can land mid-statement, and PostgreSQL's own crash recovery is not exercised here.

```text
[추론] Without the suppressed-duplicate counter, this scenario would pass even if both cases stopped at the same place.
```

Both cases end with one effect row, so the effect table cannot say whether the recovering attempt wrote it or found it already written. The counter is the only observation that separates them, which is why the scenario demanded it in advance rather than accepting the row count as sufficient. Supporting measurements: the 0-versus-1 counter above against identical row states.

```text
[측정] An exhausted job is distinguishable from a backing-off one using only the fields an operator surface renders.
```

- procedure: `JOB-003` leaves one job failed by exhaustion and a second waiting out its backoff, then compares both through `read_job`
- observed: `state` differs (`FAILED` versus `PENDING`), `terminal_reason` is set only on the exhausted one, and `attempt_count` against `max_attempts` shows whether budget remains. The exhausted job is not claimed again after a further claim cycle.
- captured_at: 2026-08-17
- limitation: this is a store-level read. Whether the operator API and dashboard actually render those three fields is `OPS` work in S5, and a field that exists but is not shown does not satisfy the charter's diagnosis criterion.

### S3 — concurrency, and the midpoint review of OQ-006

```text
[측정] Four contending workers never created conflicting active ownership.
```

- procedure: `JOB-007`. Case A one job and four worker processes; case B 200 jobs and four workers; five repetitions each, run twice
- observed: `select job_id from job_attempt group by job_id having count(*) > 1` returned no rows in all ten repetitions. Attempt count equalled job count exactly (1 and 200). No job remained non-terminal and no row remained claimable.
- per-worker claim distribution, case B, ten repetitions: `57/52/52/39`, `50/49/51/50`, `50/51/49/50`, `52/52/42/54`, `50/51/49/50`, `49/51/49/51`, `51/51/50/48`, `49/51/50/50`, `51/49/50/50`, `55/56/33/56`. All four workers claimed in every repetition. Case A's single job was won by three different workers across five repetitions.
- environment: PostgreSQL 18.4, four `python -m platform_core.worker` processes on one database
- captured_at: 2026-08-17
- limitation: four workers on one host at P0 volume. This is evidence about correctness under contention, not about throughput, fairness, or production concurrency. `claim_conflicts` read 0 in almost every run — `SKIP LOCKED` skips to another row rather than returning empty, so that counter is not a usable contention measure and the distribution above is.

```text
[측정] A live worker that lost its lease is refused at completion time, and it did try.
```

- procedure: `JOB-006`. Worker A claims and stalls past a 1 s lease; worker B reclaims and finishes; A wakes and attempts its own completion. Five repetitions.
- observed: A's own report carried `rejected_completions=1` and `suppressed_duplicate_effects=1` — the second proves A's handler ran to its end and reached `apply_effect`, so A was awake and trying rather than dead. A recorded `transitions[RUNNING]=1` and `transitions[SUCCEEDED]=0`. One `job.completion_rejected` line on A's stderr carried `worker_id=worker-a`, the job's `correlation_id`, and `intended_outcome=SUCCEEDED`. B recorded `abandoned_attempts=1` with lease recovery latency 129.8–167.5 ms.
- the whole job row, both attempt rows, and the entire effect table were compared between the instant B finished and the instant A had exhausted its attempts: identical. Attempt 1 kept its `ABANDONED` outcome and B's `finished_at`.
- captured_at: 2026-08-17
- limitation: the fence tests lease ownership rather than expiry, so this is refusal after a reclaim. A worker whose lease expired but whom nobody reclaimed still owns its job and its completion is accepted — deliberate, and now stated in the contract.

```text
[측정] Duplicate suppression is keyed, not blanket.
```

- procedure: `JOB-008`. Case B 20 jobs sharing one `effect_key`, case C 20 jobs with distinct keys, four workers each, five repetitions each
- observed: case B produced exactly one `platform_effect` row and 19 suppressions, every repetition, with all 20 jobs `SUCCEEDED`. Case C produced exactly 20 rows and **0 suppressions**, every repetition. Each suppression emitted its own `job.effect_suppressed` event carrying the `effect_key` and the correlation identifier of the job that lost.
- captured_at: 2026-08-17
- limitation: the durable effect is one row with a primary-key conflict. Nothing here concerns a multi-statement or multi-table effect, which is H1's P0-B half.

```text
[측정] No flakiness across 13 consecutive runs of the concurrency set.
```

- procedure: 5 × `-n 4`, 5 × serial, 3 × `-n 8` (deliberate over-subscription: eight pytest workers each starting four worker processes against one database), plus two full-suite runs each way, then three further repetitions during review
- observed: 0 failures, 0 reruns. No assertion was loosened to obtain a pass. Full suite 338 passed serially in 71 s and 37 s under `-n 4`.
- captured_at: 2026-08-17
- limitation: one host, one PostgreSQL version, one hardware profile. A slower or more loaded machine may expose ordering this did not.

## Midpoint review — OQ-006 verdict at S3

The plan placed the review here because this is where the two hypotheses that can actually fail are decided. Both are supported at P0-A scope; neither is proved beyond it.

`[추론]` **H2 — `FOR UPDATE SKIP LOCKED`, attempts, leases, and `available_at` are sufficient for P0 claims and recovery: supported.** Its falsification condition has three limbs and none fired. No work was permanently stranded: 200 jobs × 5 repetitions × 4 contending workers left zero non-terminal jobs and zero open attempts every time. No conflicting active ownership appeared in any of twenty concurrent repetitions, and `JOB-006` established the harder half — that a *live* worker which lost its lease is refused at completion time rather than merely out-scheduled. Every expired lease was reclaimed automatically within 130–168 ms, consuming an attempt as the contract requires.

`[추론]` **H1 — at-least-once delivery plus idempotent effects can contain duplicate execution: supported, and the containment is keyed.** Case C's zero is what makes case B's nineteen mean something: without it, the same nineteen would be equally consistent with unconditional suppression. Each suppression is discoverable rather than merely counted, which is what the charter's word *uncontrolled* rules out — the platform detects and reconciles a repeat instead of hoping to avoid one.

`[추론]` **The evidence does not extend past a single-row effect.** Real acquisition and normalization effects in P0-B will span several statements and probably several tables, and a primary-key conflict is the easiest possible case of the problem H1 names. This is the largest single gap P0-A leaves, and the P0-A gate must not present it as settled.

**H3 remains untestable in P0-A**, as DP-005 says: whether collector and normalizer jobs need separate state and retry policy cannot be asked before the domain exists.

**Review outcome: continue to S4 and S5.** No falsification condition fired, so the platform premise the remaining slices build on is intact.

### Conduct findings carried into S4, not deferred to the gate

The midpoint review also looked for problems in how the experiment is being run, on the reasoning that a defect in the record is as capable of producing a false `GO` as a defect in the platform. Three would compound if left.

```text
[측정] Fixture duplication is 31 of the suite's 71 seconds.
```

- procedure: `./scripts/with-database.sh uv run pytest --durations=12`
- observed: the five `JOB-006` tests each pay 6.22–6.24 s in **setup**, replaying one 6 s stall five times under a function-scoped fixture. `JOB-005` has the same shape at roughly 1.4 s × 8. Suite runtime has gone 7 s → 32 s → 71 s across S1, S2, and S3.
- `[추론]` The number is not the problem; the shape is, because it is the shape S5's operator scenarios will copy when they start processes to exercise the dashboard. A suite that passes two minutes stops being run, and a regression suite nobody runs is equivalent to none. Fixed in S4 rather than recorded as a limitation.

```text
[확인 사실] SEC-003 reads `NOT RUN` while 30 tests named after it pass.
```

- `sec_003` selects 30 passing tests; `sec_001`, `sec_002`, and `sec_004` select none. All four scenario records read `NOT RUN`.
- `[추론]` The `NOT RUN` is correct — S1 covered configuration rejection but not the entrypoint half the scenario requires — but a reviewer cannot distinguish that honesty from an oversight, and the passing tests make S4 look already done. This is the exact shape the charter's timebox rule forbids: missing evidence reading as a pass. S4 must reconcile all four records against what it actually establishes.

```text
[확인 사실] The evidence directory every scenario names does not exist.
```

- `experiments/integrated-p0/evidence/` is absent. Every measurement so far lives in this record's prose.
- `[추론]` Left until S6, capturing evidence becomes one large step that descope ladder item 3 would remove entirely, leaving the gate with prose claims and no artifacts. Started in S4 instead, so that each slice adds to it.

All three were acted on in S4. Fixture scope: the five `JOB-006` tests now share one run, and `[측정]` the suite went from 71 s to 45 s while growing from 338 to 428 tests — 26 s recovered from what was pure duplication. Only one 6.24 s setup remains where there were five. The `SEC` records were reconciled against what S4 actually established, which is why one of the four still reads `NOT RUN`. The evidence directory remains the open item and moves to S5.

Two further findings need no action now and are recorded so they are not mistaken for oversights. The boundary guard reads `.py` and `.sql` only, so the TypeScript dashboard will be checked by path name alone — the directory does not exist yet, and the decision belongs to S5, where a UI naming things `records` is the actual temptation. And all twelve scenarios remain `DRAFT` while eight read `PASS`, which is coherent: `DRAFT` means not yet accepted as a project constraint, and the gate is where that acceptance happens.

### S4 — the safety boundary

```text
[측정] Three of the four SEC scenarios pass; the fourth is partially executed and recorded as such.
```

- procedure: `./scripts/with-database.sh uv run pytest -k sec_00N`
- observed: `SEC-001` 25 passed, `SEC-002` 25 passed, `SEC-003` 44 passed, `SEC-004` 24 passed. Suite total 428 passed in 45 s serially and 20 s under `-n 4`; ruff, mypy strict across 44 files, and the boundary guard clean.
- `SEC-004` is recorded `NOT RUN` despite its 24 passing tests: the log and both API representations are covered, but the scenario's Action also requires the dashboard job-detail screen and a screenshot, and no dashboard exists yet. A `PASS` there would be the failure mode this experiment's own conduct review named.
- captured_at: 2026-08-17
- limitation: `SEC-001` guards location only, not file permissions. `SEC-002` is evidence about binding, not authorization — anything on the host reaches the API and the database with no credential.

```text
[측정] The application-startup guard and the test-session guard refuse the same paths because they are the same guard.
```

- procedure: `SEC-001` cases a–f against both `python -m platform_core.worker` and `python -m platform_core.api`
- observed: a store inside the tree is refused by both entrypoints with `CONFIGURATION_INVALID` and no database connection attempted. A symbolic link from outside the tree resolving inside it is refused; one resolving outside is accepted — so the comparison is on resolved paths. An unset store starts normally, and an **unreadable** store outside the tree also starts normally, which is the observation that the guard never opens the file. The refusal names the path, the tree root, and the convention, and does not dump the environment.
- `tests/conftest.py` now calls `platform_core.config.secret_store_location_problem` rather than keeping its own copy, and asserts that both halves measure the same tree root.
- captured_at: 2026-08-17
- limitation: this makes the repository's root test session import experiment code. It is a test-session dependency, not a runtime or package one, so DP-001 is unaffected — but the session stops guarding when `experiments/integrated-p0/` is disposed of, and that obligation belongs in the P0-B artifact disposition register.

```text
[추론] One guard with two callers is the only reading of "the same guard" that cannot drift.
```

`secret-setup.md` asks for "the same guard" at application startup and at test-session start. Two implementations of one guard is a contradiction: they can disagree, and the one that disagrees is the leak. The cost is the import direction noted above, whose failure mode is a loud collection error when P0 is deleted — strictly better than a silent divergence nobody is looking for. Supporting measurements: the paired entrypoint cases above, and the root-equality assertion that fires if the two halves ever measure different trees.

### S5 — the operator surface

```text
[측정] Every operator question was answered without the database, and the seal that proves it fires.
```

- procedure: `OPS-001`, three failure shapes, six questions each, answered through HTTP only. `psycopg.connect` and `psycopg.Connection.connect` are both replaced for the duration of every assertion, and a control test shows the replacement raises.
- observed: 14 passed. All six questions answered from `GET /jobs`, `GET /jobs/{id}`, and `GET /jobs/{id}/attempts`. **No fourth navigation object was required**, and a test asserts the set of consulted paths is a subset of health, jobs, and attempts, so a fourth added later fails rather than passing unnoticed.
- three derived fields were added to answer questions 5 and 6 without the operator doing the contract's arithmetic: `attempts_remaining`, `attempt_budget_spent`, `error_class_retryable`. All are computed from columns the contract already fixes; no stored field was added.
- captured_at: 2026-08-17
- limitation: OQ-005's evidence list also asks "by which version". P0-A has no versioned producer, so the question has no answer here and is left absent rather than approximated by the code revision.

```text
[측정] Retry through the operator surface does not bypass the idempotency boundary.
```

- procedure: `OPS-002`. A job applies its effect on an attempt that then fails, exhausts its budget, is retried through `POST /jobs/{id}/retry`, and runs to `SUCCEEDED`.
- observed: 11 passed. The effect count is identical before and after, and the suppressed-duplicate counter reads 0 in the exhausting worker's report and 1 in the retried worker's — which is what separates "suppressed" from "never attempted". Refusals on a `SUCCEEDED` job and a `RUNNING` job return `409` naming both the current and the required state, and their job rows compare equal field by field including `updated_at`. A retry on an unknown identity returns `404` and creates nothing.
- captured_at: 2026-08-17
- limitation: unauthenticated, like everything on the loopback binding. This is evidence that retry is idempotent, not that it is authorized.

```text
[측정] One correlation identifier reconstructs a history that crosses a process death.
```

- procedure: `OPS-003`. A worker applies its effect and ends its own process; a second worker reclaims and finishes; `GET /events?correlation_id=` is asked once.
- observed: 8 passed. Nine events returned for one identifier, carrying two distinct `worker_id` values with an identical `correlation_id` — invariant I5 across a boundary no in-memory context survives. The claim of each attempt, `job.effect_applied` once, `job.attempt_abandoned` with `LEASE_ABANDONED`, `job.effect_suppressed` naming the `effect_key`, and the terminal transition are all present. The control holds: an unrelated job's events are in the same file and absent from the response.
- captured_at: 2026-08-17
- limitation: correlation is per job. P0-A has no operation fanning out across several jobs, which is exactly the shape a P0-B collection run over many pages will have.

```text
[측정] Health reflects the database, not the API's own liveness, and recovers without a restart.
```

- procedure: `OPS-004`. A second API process was pointed at a database that did not exist — the variant the scenario permits — and that database was then created while the process kept running. Stopping the shared cluster was rejected because it would take the rest of the run down.
- observed: 11 passed. Unhealthy with a reason naming the database, then healthy again with the same `pid` and exactly one `api.started` event. Transition counts match the jobs run; the `FAILED` count moves by exactly 1; three control counters stay at 0 across both steps.
- captured_at: 2026-08-17
- limitation: metrics are per process and in memory, so the platform can report that nothing has been claimed but not that no worker is running. Step 5 shows the consequence.

```text
[추론] A scenario of mine asked which error class a health check produces. The answer is none.
```

`OPS-004` originally classified an unreachable database as `PLATFORM_TRANSIENT` under the contract's SQLSTATE rule, and the implementation measured `CONFIGURATION_INVALID` instead. Both the scenario and the contract were wrong in different ways. `[측정]` A connect-time failure carries `sqlstate = None`, so the rule's transient branch is unreachable from a failure to connect; the contract meanwhile already listed "a socket directory with no socket" under `CONFIGURATION_INVALID`, contradicting my scenario independently of what psycopg reports. `[추론]` The deeper error was mine and was a category one: health reports reachability, and no job failed, so nothing is classified. The contract now separates the three situations it had collapsed — a connect failure at startup, which must stay non-retryable because `SEC-001` and `SEC-003` depend on a supervisor failing identically; a statement failure on a live connection, which is where the `08`/`53`/`57` branches actually apply; and a running process whose database goes away, which classifies nothing.

`[확인 사실]` **The transient branch is unexercised.** No scenario kills a connection mid-statement, so classes `08`, `53`, and `57` have never been reached. The contract now says so, and the gate must record it as written-but-unmeasured rather than as verified behavior.

```text
[추론] Evidence capture was split by what the artifact's nature is, not by convenience.
```

`experiments/integrated-p0/evidence/2026-08-17-5b26d47/` holds what does not depend on the final revision: the environment, a real structured-log sample, the correlated event set `OPS-003` demands as an artifact, and the `SEC-002` readings. The full pytest transcript stays with S6, because a copy taken now would describe a working tree nobody can check out. The split is what keeps descope ladder item 3 from leaving the gate with prose and no artifacts.

One judgement in that directory was reversed on review. `sec-002-listeners.txt` first committed the whole `lsof` listing, reasoning that `SEC-002` calls a claim in a document insufficient. That reasoning holds against a *filtered* listing, and the replacement is not one: it records how many sockets were listening and how many were PostgreSQL, both complete answers to a narrower question, with the total kept so a zero cannot read as a failed command. The original named unrelated processes on this machine, their pids, and their ports — host state that is not this project's data, and `public` in [Data Handling](../../docs/conventions/data-handling.md) means redistributable.

## Interpretation

```text
[추론] not yet available
```

## Result

- Outcome: `SUPPORTED | REFUTED | INCONCLUSIVE` — not yet determined
- Falsification condition met: `NOT TESTED`
- Exit condition met: `NO`
- Known limitations: to be recorded

## Impact and next action

- Uncertainty reduced: to be recorded
- New uncertainty discovered: to be recorded
- Proposed next experiment: P0-B B1 source exploration, after the P0-A Completion Gate is accepted
- Proposed contract change: to be recorded
- Proposed Decision Packet update: [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) is proposed for acceptance at the gate together with the evidence showing whether each of its choices held

## Artifacts

- Experiment record: this file
- Code: `experiments/integrated-p0/platform_core/`, `experiments/integrated-p0/dashboard/`, `scripts/with-database.sh`
- Fixture or retrieval procedure: synthetic, generated in-test; no external retrieval
- Logs, metrics, traces, or screenshots: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/`
- Output and hashes: recorded per evidence directory in `ENVIRONMENT.md`
- Data class and retention responsibility: `public`; synthetic only; retained in the repository as gate evidence, with disposition decided by the P0-B artifact disposition register

## Completion checklist

- [ ] The hypothesis is falsifiable.
- [ ] The falsification and exit conditions were fixed before interpreting the result.
- [ ] Inputs, rights, environment, versions, and hashes are recorded.
- [ ] The procedure is replayable without relying on undocumented session context.
- [ ] Observations and interpretations use the project evidence labels correctly.
- [ ] Secrets, restricted inputs, and raw conversations are absent.
- [ ] The result includes limitations and a concrete next action.
