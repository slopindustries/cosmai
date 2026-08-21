# OQ-006 — Job Concurrency and Recovery

- Status: `OPEN`
- Priority: P0-A platform claims and P0-B domain effects
- Owner: Project team
- Blocks: worker, transaction, retry, and scale-out contract
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — `COMPLETED` 2026-08-17, covers the P0-A minimum experiment below. H1 and H2 are in scope at the platform level; H3 is not testable without the domain and stays with P0-B.
- Resolution Decision Packet: not created

## Question

Can a PostgreSQL-backed platform job model provide correct generic concurrency and recovery, and does that model remain correct when P0-B introduces collector, importer, and normalizer effects?

## Why this cannot be decided yet

No implementation has yet injected concurrent claims, duplicate delivery, interruption around durable effects, lease expiry, retry exhaustion, or unknown outcomes.

## Scope

### Included

- PostgreSQL-backed P0 claims, leases, attempts, retry scheduling, idempotent durable effects, terminal states, and collector/normalizer recovery differences.

### Excluded

- Production throughput targets, distributed brokers, multi-region consensus, exactly-once claims, and final scale infrastructure.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: At-least-once delivery plus idempotent effects can contain duplicate execution in P0. | Injected duplicate delivery or an unknown outcome produces an uncontrolled durable duplicate effect that the recorded idempotency boundary cannot detect or recover. |
| H2: `FOR UPDATE SKIP LOCKED`, attempts, leases, and `available_at` are sufficient for P0 claims and recovery. | A tested interruption leaves work permanently stranded, permits conflicting active ownership, or reaches a state with no documented recovery or finalization path. |
| H3: Collector and normalizer jobs require separate state and retry policy even on shared infrastructure. | The same tested state transitions, retry classification, lease behavior, and terminal states satisfy both domains without source- or provider-specific exceptions. |

### A prediction H3 must confirm or refute

[DP-008](../decisions/DP-008-addon-architecture.md) records the two components as asymmetric in kind: a collector consumes the outside world, holds position state, and fails partially and resumably; a normalizer consumes a sealed hash-verified snapshot, holds no state, and cannot fail partially because its input is fixed before it runs.

`[추론]` If that asymmetry is real, H3 is true for a **structural** reason and not an empirical one, and the evidence should show the difference in the *resumption* path rather than in claim, lease, or terminal-state behavior. A measurement that finds the two domains differing in lease or claim behavior instead would mean this prediction is wrong and the asymmetry is not where DP-008 located it.

`[추론]` This prediction is not evidence. It is recorded so that a P0-B result agreeing with it cannot be read as confirmation that was never at risk.

### Open finding F16 — an intermittent flake bearing on H2

`[측정]` During B0, `test_job_002_shares_one_correlation_id_across_both_attempts` failed once
under `pytest -n 4` and passed on re-execution. Serial execution has not failed. `[확인 사실]`
The failure reproduces at revision `d714b3b` with the B0 working tree stashed, so it predates
the add-on layer.

`[확인 사실]` The [P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md)
records the suite passing "sequentially and under `-n 4`". That is now known to describe the
runs that were observed rather than a stable property.

`[추론]` The assertion that fails compares a set of correlation identifiers against one
expected value, so the failure means a log record carried an identifier the scenario did not
create. A runner claiming a job left behind by an earlier test in a shared database would
produce exactly that, since `claim_next` takes the next available job rather than a named one.
Unconfirmed.

This bears directly on **H2**, and on whether the P0-A test isolation described in DP-006 D3
holds under parallel execution. Classify it — implementation, specification, assumption,
evaluation, or goal — before changing a test or a fixture. It must be resolved or explicitly
carried before the P1 Entry Gate.

## Alternatives

- PostgreSQL job tables with at-least-once execution and idempotent effects.
- A dedicated message broker introduced only if P0 falsifies the database-backed model.
- Synchronous orchestration, retained as a comparison but expected to fail independent recovery requirements.

## Minimum experiment

### P0-A

- Implement the handler-neutral platform job core and run at least two workers against a shared queue using synthetic generic handlers that do not imitate collection or normalization.
- Terminate a worker after claim and after a durable side effect.
- Deliver the same job more than once.
- Exhaust retryable work into a final failure state.
- Recover an expired lease.

### P0-B

- Repeat the relevant claim, interruption, duplicate, and recovery scenarios with the concrete collector, importer, and normalizer.
- Record where source or rule effects differ from the platform evidence and whether the P0-A gate must be reopened.

## Evidence

- Claim exclusivity and lease behavior.
- Duplicate side effects and idempotency results.
- Recovery time and state transitions.
- Transaction boundaries and unknown-outcome cases.
- Collector-versus-normalizer retry differences.

## Exit condition

Every injected failure ends in a documented recoverable or final state, duplicate delivery does not produce uncontrolled effects, and the team can specify the P1 job state machine and transaction boundaries.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution links failure-injection measurements, accepted state/error contracts, Decision Packet, and remaining scale limits.

## M1 Task 10 remeasurement — 2026-08-21

Two measurements the P1 Entry Gate carried forward from P0-A, rerun against `apps/` (the
reconstruction tree) rather than `experiments/integrated-p0/`. Both are appended below rather
than replacing the P0-A figures above, which remain a record of what was measured against the
old tree.

**Environment.** WSL2 (`Linux 6.18.33.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC`,
x86_64), PostgreSQL 18.6 in the `tubedepth-postgres` docker container, reached over loopback TCP
(`127.0.0.1:5433`, DP-032) rather than P0-A's local Unix socket. `[측정]` Background load on the
host was not independently profiled or held constant — unlike P0-A's deliberate "under CPU
contention" runs, these are ordinary-session measurements and say nothing about a loaded machine.

### Measurement 1 — JOB-007 case B (200 jobs × 4 worker processes), ten repetitions

Implemented in `apps/tests/concurrency/test_job_007_parallel.py`, driven by
`apps/tests/concurrency/run_measurements.sh`. Each repetition is a separate `pytest` process
invocation (not a parametrize loop in one process), matching how the P0-A baseline above (0/30
normal, 1/3/1 under CPU contention) was itself measured as repeated process invocations.

`[측정]` **Result: 0/10 failures.** Wall-clock 14s total (~1.1s/repetition). Claim distribution
across the four workers was even in every repetition (49–51 claims each of 200); `claim_conflicts`
ranged 0–2 per run; `suppressed_duplicate_effects` and `rejected_completions` were 0 in every
repetition, as JOB-007 case B requires.

Reproduction (`COSMA_DB_NAME=cosmai_test`, not the production `cosmai` named in an earlier
revision of this line — see the note after Measurement 2):

<!-- [측정] 2026-08-21, M7 sweep: port corrected 5433→5434 — the shared server was replaced
mid-M6 (`apps/db/provision.md`'s addendum); command otherwise unchanged. -->

```sh
cd apps
COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime \
  ../scripts/with-secret-source.sh env JOB_007_REPETITIONS=10 F16_REPETITIONS=0 \
  bash tests/concurrency/run_measurements.sh
```

### Measurement 2 — F16 rerun: the correlation-id test under `-n 4`, twenty repetitions

P0's flake was in `test_job_002_shares_one_correlation_id_across_both_attempts`. Its apps/
counterpart is `test_job_002_shares_one_correlation_id_and_counts_both_transitions`
(`apps/tests/acceptance/test_job_scenarios.py`, from Task 9). Reran that one test, selected by
node id, twenty times under `pytest -n 4`, each repetition a separate process.

`[측정]` **Result: 0/20 failures.** Wall-clock 16s total (~0.6–0.8s/repetition, most of it xdist
worker startup).

Reproduction (`COSMA_DB_NAME=cosmai_test`; see the note below):

<!-- [측정] 2026-08-21, M7 sweep: port corrected 5433→5434, same reason as above. -->

```sh
cd apps
COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime \
  ../scripts/with-secret-source.sh env JOB_007_REPETITIONS=0 F16_REPETITIONS=20 \
  bash tests/concurrency/run_measurements.sh
```

`[측정]` 2026-08-21, REVIEW-M1 F8: both recipes above named `COSMA_DB_NAME=cosmai` (the
production database) in an earlier revision of this section — harmless only because
`tests/conftest.py`'s `platform_config` fixture forces `cosmai_test` regardless of what the
environment names, but a recipe that names the wrong database by accident is a control that
happened to hold, not one that was checked. Corrected to the database the run actually needs.

### What these two results do NOT establish

- `[추론]` Selecting one test by node id under `-n 4` hands it to exactly one of the four launched
  xdist worker processes; the other three never execute a test item and never run the
  session-scoped `_reset_schema` fixture at all. F16's suspected P0 mechanism — a runner claiming
  a job an earlier test left behind in a *shared* database — depended on several tests actually
  running concurrently across workers. A single isolated test cannot reproduce that contention
  regardless of how many times it is repeated, so **0/20 here is evidence the named test does not
  fail on its own under `-n 4` process overhead; it is not evidence that P1's test isolation holds
  under genuine parallel test execution**, and F16 should not be marked resolved on this basis
  alone.
- Neither measurement is at production scale, across machines, or under deliberate CPU
  contention the way P0-A's "1·3·1" figures were produced; both are single-machine,
  single-session observations on whatever load this host carried at measurement time.
- Task 9's own `apps/tests/acceptance/test_job_scenarios_concurrency.py` already reruns JOB-007
  case B five times in one pytest session, as the scenario's own acceptance evidence. This
  measurement's ten additional, process-isolated repetitions are the distinct thing OQ-006 asked
  to be carried forward — not a duplicate of Task 9's evidence, and not replaced by it.

### An adjacent finding, surfaced while investigating F16's `-n 4` condition — record, not fix

`[측정]` Out of scope for the two carried measurements above, but directly bears on the same
question (OQ-006 H2; whether DP-006 D3's test isolation holds under parallel execution) and is
significant enough to record per this task's instruction that a reproduced failure is a result,
not a bug to silently patch. Running the **whole** `apps/` suite under `-n 4` with no test
selection —

<!-- [측정] 2026-08-21, M7 sweep: port corrected 5433→5434, same reason as above. -->

```sh
cd apps
COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime \
  ../scripts/with-secret-source.sh uv run python -m pytest tests -n 4 -q
```

— collapses almost the entire suite, reproduced twice: **19 passed, 299 errors** on the first run
and **19 passed, 300 errors** on the second (of 318–319 collected items each time; the whole
suite passes 318/318 serially). The dominant error signatures are
`platform_core.errors.ConfigurationInvalidError: cannot reach the platform database` and
`psycopg.errors.UniqueViolation: duplicate key value violates unique constraint`, spread across
nearly every module that touches the database (`test_jobs_store.py`, `test_obs.py`,
`test_secrets.py`, `test_worker.py`, and others).

`[추론]` The likely cause is structural, not the same probabilistic flake F16 named. **P0's**
`migrated_template`/`shared_database` fixtures built one private database per xdist worker,
keyed off `PYTEST_XDIST_WORKER` in the database name, so each worker's own session-scoped setup
never touched another worker's database. **P1 has no such key to build on**: DP-032 gives it
exactly one fixed `cosmai_test` database, and `apps/tests/conftest.py`'s `_reset_schema` is
`scope="session", autouse=True`, issuing `drop schema cosmai cascade` / `create schema cosmai`
against that one database. Under `pytest-xdist`, "session" scope is per **xdist-worker process**
— with `-n 4` and enough test items to keep all four busy, all four processes each run their own
`_reset_schema` once, racing the same DROP/CREATE-SCHEMA pair against the same physical schema
with no coordination between them, while other workers' tests are concurrently reading and
writing through it. This is inferred from the fixture's own code and the error signature, not
confirmed with a debugger or a query-log trace, and no fix was attempted — out of this task's
boundary (measurement only; Task 10 touches `apps/tests/acceptance/**`, `apps/tests/concurrency/**`,
this document, and its own report).

This does not change either measurement's PASS result above — the F16 rerun's single-test
selection sidesteps exactly this mechanism, which is itself part of why the previous bullet says
that result cannot be read as isolation holding under genuine parallel execution. Whether `-n 4`
across the apps/ suite must simply never be run against the shared `cosmai_test` database, or
`_reset_schema` needs its own coordination for a parallel session, is unresolved and is recorded
here for whoever picks it up next rather than decided or patched by this task.

## 2026-08-21 — `25P03` (idle-in-transaction timeout) left non-retryable, open

`[결정]` REVIEW-M1 F3's fix-wave reclassified `55P03` (lock not available) as
`PLATFORM_TRANSIENT` in `platform_core.db.connection.classify`, reachable now that DP-032's
`provision.sql` sets `lock_timeout='5s'`. `25P03` (idle-in-transaction timeout, from the same
`provision.sql`'s `idle_in_transaction_session_timeout='15s'`) was deliberately left
`CONFIGURATION_INVALID` — an idle transaction is a worker that stopped making progress, not
contention with another transaction, so the two SQLSTATEs were not given the same answer.
Whether that distinction is the right one, and whether `25P03` should instead retry a bounded
number of times, is unresolved and is carried here rather than decided by the fix wave that
found it. See `docs/p1/M1-RECORD.md` §c deviation 8 and REVIEW-M1 F3.
