# JOB-003 — Retry exhaustion produces an observable terminal state

- Status: `ACCEPTED_FOR_POC`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md)
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the P0-A charter exit criterion *"Retry exhaustion produces an observable terminal state."*

"Observable" is the load-bearing word. A job that stops being retried but looks identical to one still waiting for backoff has not reached an observable terminal state, and an operator cannot tell the difference without reading the database.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: one worker process.
- Configuration with secrets excluded: lease duration 5 s; `max_attempts = 2`; compressed backoff.
- Time, retry, and concurrency assumptions: the handler fails transiently on every attempt.

## Action

1. Create a job with `handler = "fail_transient"`, payload requesting failure on every attempt, and `max_attempts = 2`.
2. Run the worker until the job stops being claimable.
3. Read the job, all attempts, and `platform_effect`.
4. Continue running the worker for at least one further claim interval.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 2 | `job_attempt` #1 | open | `RETRYABLE_FAILURE` | `error_class = PLATFORM_TRANSIENT` |
| 2 | `job` | `RUNNING` | `PENDING` | `attempt_count = 1`, backoff applied |
| 2 | `job_attempt` #2 | open | `RETRYABLE_FAILURE` | `error_class = PLATFORM_TRANSIENT` |
| 2 | `job` | `RUNNING` | `FAILED` | `attempt_count = 2 = max_attempts`, `terminal_reason = PLATFORM_TRANSIENT`, lease cleared |
| 4 | `job` | `FAILED` | `FAILED` | no further claim occurs |

## Expected durable effects

- Created or changed records: exactly two `job_attempt` rows, both `RETRYABLE_FAILURE`; job `FAILED` with `terminal_reason` set.
- Effects that must not occur: no `platform_effect` row; no third attempt; `attempt_count` never exceeds `max_attempts` (invariant I4).
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one `correlation_id` across both attempts and the terminal event.
- Structured event or log fields: the terminal event distinguishes exhaustion from a permanent failure — `to_state = FAILED` with `terminal_reason = PLATFORM_TRANSIENT` and `attempt_count = max_attempts`.
- Metrics and units: transition counter for `FAILED` incremented by 1; two `RETRYABLE_FAILURE` increments.
- Protected debug behavior: `error_detail` populated on both attempts; absent from the default API representation.

## Failure classification and recovery

- Expected error class and code: `PLATFORM_TRANSIENT`, recorded as `terminal_reason` on exhaustion.
- Retryable: the class is retryable; the job is not, because the budget is spent. These are deliberately different facts and both must be visible.
- Operator-visible explanation: the job is failed, the cause was transient, and the budget is exhausted — all readable without database access.
- Safe retry or final action: operator safe retry resets `attempt_count` to 0 and returns the job to `PENDING`, retaining prior attempts. Exercised by the `OPS` family, not here.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_003`
- Assertions: the transition table above; `attempt_count == max_attempts`; no `platform_effect` row; the job is not claimed again in step 4; a failed-by-exhaustion job is distinguishable from a backing-off job using only the fields the API exposes.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 6 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_003`
- Known limitation: the exhausted-versus-backing-off distinction is read through the store. Whether an operator surface renders those fields is `OPS` work; a field that exists but is not shown does not satisfy the charter's diagnosis criterion.
