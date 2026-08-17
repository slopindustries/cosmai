# JOB-007 — Parallel claims never create conflicting active ownership

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — invariant I2
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md) H2
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the charter's first P0-A exit criterion: *"Parallel job claims do not create conflicting active ownership."*

This is the scenario that tests `FOR UPDATE SKIP LOCKED` under real contention rather than in principle. It runs real worker processes against one database, because a single-process test with threads shares a connection pool and a transaction manager and would not exercise the mechanism that matters.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: four worker processes with distinct identities, started as close to simultaneously as the harness allows.
- Configuration with secrets excluded: lease duration comfortably longer than the handler's runtime, so that nothing expires during the run and every observation is about claiming rather than recovery.
- Time, retry, and concurrency assumptions: all jobs are due at creation, so every worker races for the same rows.

## Action

**Case A — one job, four workers.**
1. Create a single job with `handler = "succeed"`.
2. Start four workers simultaneously.
3. Wait for the job to reach a terminal state, then stop the workers.

**Case B — many jobs, four workers.**
1. Create 200 jobs with `handler = "succeed"`, all due immediately.
2. Start four workers simultaneously.
3. Wait until no job is claimable, then stop the workers.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| A.3 | `job` | `PENDING` → `RUNNING` → `SUCCEEDED` | | Exactly one attempt, one `lease_owner` |
| B.3 | each `job` | `PENDING` → `RUNNING` → `SUCCEEDED` | | Exactly one attempt each |

## Expected durable effects

- Created or changed records: case A — one `job_attempt`, one `platform_effect`. Case B — 200 jobs `SUCCEEDED`, exactly 200 `job_attempt` rows, exactly 200 `platform_effect` rows.
- Effects that must not occur: any job with two attempts; any job with two open attempts at any instant; any job left `PENDING` after the workers drain the queue; any duplicate `platform_effect` row.
- Idempotency or duplicate expectation: no duplicate execution is expected here. `JOB-008` owns the case where one happens anyway.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one per job; every attempt carries its job's identifier.
- Structured event or log fields: claim events carry `worker_id`, so the distribution of work across the four workers is observable. A run in which one worker claimed all 200 jobs passes the invariant but indicates the others never contended — the evidence must show which happened.
- Metrics and units: claim-conflict counter recorded; 200 `SUCCEEDED` transitions in case B.
- Protected debug behavior: unchanged.

## Failure classification and recovery

- Expected error class and code: none.
- Retryable: n/a.
- Operator-visible explanation: n/a.
- Safe retry or final action: none.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -m concurrency -k job_007`
- Assertions: `SELECT job_id FROM job_attempt GROUP BY job_id HAVING count(*) > 1` returns no rows; the count of `job_attempt` equals the count of jobs; the count of `platform_effect` equals the count of jobs; no job remains non-terminal; **the run is repeated at least five times** and every repetition holds, because a single passing run of a race is weak evidence.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`, including the per-worker claim distribution.
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: four workers on one host at P0 scale. This is evidence about correctness under contention, not about throughput, fairness, or behavior at production concurrency. A starved job is possible and is not detected.
