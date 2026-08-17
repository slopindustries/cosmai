# JOB-002 — A retryable failure is rescheduled and a later attempt succeeds

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md)
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the rule that a retryable failure returns the job to a claimable state rather than a terminal one, that the attempt budget is spent one attempt at a time, and that the earlier failure remains inspectable after a later attempt succeeds.

The last point matters for the operator contract: a job that eventually succeeded must still show that it failed first, or `OPS` diagnosis has nothing to work from.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: one worker process.
- Configuration with secrets excluded: lease duration 5 s; `max_attempts = 3`; backoff base set small enough that the scenario completes without real waiting.
- Time, retry, and concurrency assumptions: no contention. The handler fails transiently on its first attempt only.

## Action

1. Create a job with `handler = "fail_transient"`, payload requesting one transient failure, and `max_attempts = 3`.
2. Run the worker until the job reaches a terminal state.
3. Read the job, all attempts in `attempt_no` order, and `platform_effect`.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 2 | `job` | `PENDING` | `RUNNING` | `attempt_count = 1` |
| 2 | `job_attempt` #1 | open | `RETRYABLE_FAILURE` | `error_class = PLATFORM_TRANSIENT`, `finished_at` set |
| 2 | `job` | `RUNNING` | `PENDING` | lease cleared, `available_at` moved into the future by backoff |
| 2 | `job` | `PENDING` | `RUNNING` | second claim, `attempt_count = 2` |
| 2 | `job_attempt` #2 | open | `SUCCEEDED` | `error_class` null |
| 2 | `job` | `RUNNING` | `SUCCEEDED` | `terminal_reason` null |

## Expected durable effects

- Created or changed records: two `job_attempt` rows with `attempt_no` 1 and 2; exactly one `platform_effect` row.
- Effects that must not occur: the failed attempt must not produce a `platform_effect` row; the job must not reach `FAILED`; `attempt_count` must not skip a value.
- Idempotency or duplicate expectation: the successful attempt writes the effect once. Only one row exists even though two attempts ran.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one `correlation_id` shared by both attempts and every event.
- Structured event or log fields: the failure event carries `error_class`, `attempt_no = 1`, and a redacted `error_summary`. The reschedule event carries the new `available_at`.
- Metrics and units: transition counter for `RETRYABLE_FAILURE` incremented by 1; `SUCCEEDED` by 1; attempt duration recorded for both.
- Protected debug behavior: `error_detail` for attempt 1 is populated but is not present in the default API representation of the attempt.

## Failure classification and recovery

- Expected error class and code: `PLATFORM_TRANSIENT` on attempt 1.
- Retryable: yes.
- Operator-visible explanation: a redacted summary naming the transient class, visible on the attempt.
- Safe retry or final action: none required; recovery is automatic.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_002`
- Assertions: the transition table above; `available_at` after the first failure is strictly greater than the failure time; attempt 1 remains readable after the job succeeds; exactly one `platform_effect` row.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 7 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_002`
- Known limitation: backoff is compressed for test speed, so the observed timing is not evidence about the production backoff curve.
