# JOB-006 — An expired lease is reclaimed, and the worker that lost it cannot complete the job

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — invariant I2
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md) H2
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

`JOB-005` covers the interruption where the losing worker is dead. This scenario covers the harder one, where it is merely slow: a worker exceeds its lease, another worker reclaims the job, and then the first worker wakes up and tries to finish.

If a stale completion is accepted, invariant I2 has been violated retroactively — two workers did hold the job, and the platform simply did not notice. A lease that is only a timer, with no check at completion time, provides no exclusivity at all. This scenario is what distinguishes the two.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: two worker processes, A and B, with distinct worker identities.
- Configuration with secrets excluded: lease duration set short (for example 1 s); `max_attempts = 3`.
- Time, retry, and concurrency assumptions: the handler stalls for longer than the lease on its first attempt only.

## Action

1. Create a job with `handler = "stall"`, payload requesting a stall longer than the lease on attempt 1, `max_attempts = 3`.
2. Start worker A. It claims the job and enters the stall.
3. Wait until the lease has expired.
4. Start worker B. It reclaims the job and runs it to completion.
5. Let worker A finish stalling and attempt to record its own completion.
6. Read the job, all attempts, and `platform_effect`.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 2 | `job` | `PENDING` | `RUNNING` | `lease_owner = A`, `attempt_count = 1` |
| 4 | `job_attempt` #1 | open | `ABANDONED` | `error_class = LEASE_ABANDONED`, closed by B's reclaim |
| 4 | `job` | `RUNNING` (lease expired) | `RUNNING` | `lease_owner = B`, `attempt_count = 2` |
| 4 | `job_attempt` #2 | open | `SUCCEEDED` | |
| 4 | `job` | `RUNNING` | `SUCCEEDED` | |
| 5 | `job` | `SUCCEEDED` | `SUCCEEDED` | **A's completion is rejected and changes nothing** |
| 5 | `job_attempt` #1 | `ABANDONED` | `ABANDONED` | A must not reopen or overwrite its closed attempt |

## Expected durable effects

- Created or changed records: exactly two `job_attempt` rows; job `SUCCEEDED`; exactly one `platform_effect` row.
- Effects that must not occur: A's late completion must not set `finished_at` on attempt 1, must not change the job's terminal state, must not clear B's work, and must not insert a second `platform_effect` row.
- Idempotency or duplicate expectation: A and B derive the same `effect_key`; whichever insert lands second is suppressed.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one `correlation_id`, shared by both workers' events. The events are distinguishable by `worker_id`.
- Structured event or log fields: a reclaim event when B takes the job, and a **rejected-completion** event when A tries to finish, naming A's `worker_id` and why the completion was refused.
- Metrics and units: abandoned-attempt counter incremented by 1; claim-conflict or rejected-completion counter incremented by 1; lease recovery latency recorded.
- Protected debug behavior: unchanged.

## Failure classification and recovery

- Expected error class and code: `LEASE_ABANDONED` on attempt 1.
- Retryable: yes, and it was retried by B automatically.
- Operator-visible explanation: the job succeeded, with one abandoned attempt visible. A silently discarded rejected completion would leave an operator unable to explain why a worker reported success for a job it did not own.
- Safe retry or final action: none required.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -m concurrency -k job_006`
- Assertions: the transition table; A's completion attempt returns a refusal rather than succeeding; attempt 1 remains `ABANDONED` with its original `finished_at`; exactly one `platform_effect` row; invariant I2 holds across the whole timeline, not only at the end.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: both workers run on one host against one database, so this says nothing about clock skew larger than the lease duration between separate machines. Recorded in the contract's known limitations.
