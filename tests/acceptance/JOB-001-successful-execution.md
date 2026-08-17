# JOB-001 — Successful execution reaches a terminal state with exactly one durable effect

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md)
- Input fixture and metadata: synthetic, generated in-test. No external input.
- Owner: Project team

## Intent

Protect the base path every other `JOB` scenario is a deviation from: a job with a registered handler is claimed exactly once, executed once, produces exactly one durable effect, and reaches `SUCCEEDED`.

This scenario also fixes what "one durable effect" means in P0-A. The effect is a `platform_effect` row and nothing else; a second durable write appearing here would mean the platform grew a domain-shaped side channel.

## Preconditions

- Initial durable state: migrations applied; `job`, `job_attempt`, and `platform_effect` empty.
- Worker or service state: exactly one worker process.
- Configuration with secrets excluded: local Unix-socket database, no password; lease duration 5 s; `max_attempts = 3`.
- Time, retry, and concurrency assumptions: no contention, no injected failure, `available_at` in the past at creation.

## Action

1. Create a job with `handler = "succeed"`, an opaque payload, and `max_attempts = 3`.
2. Run the worker until the job leaves `PENDING` and reaches a terminal state.
3. Read the job, its attempts, and `platform_effect`.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 1 | `job` | — | `PENDING` | `created_at` set, `correlation_id` assigned, `attempt_count = 0` |
| 2 | `job` | `PENDING` | `RUNNING` | `lease_owner` and `lease_expires_at` set, `attempt_count = 1` |
| 2 | `job_attempt` | — | open, `attempt_no = 1` | `started_at` set, `finished_at` null |
| 3 | `job_attempt` | open | `SUCCEEDED` | `finished_at` set, `error_class` null |
| 3 | `job` | `RUNNING` | `SUCCEEDED` | lease cleared, `terminal_reason` null |

## Expected durable effects

- Created or changed records: one `job` row in `SUCCEEDED`; exactly one `job_attempt` row; exactly one `platform_effect` row whose `job_id` matches.
- Effects that must not occur: no second `platform_effect` row; no second attempt; no write to any table other than the three above and `schema_migrations`.
- Idempotency or duplicate expectation: not exercised here. `JOB-008` owns it.
- Lineage expectation: none. Lineage is a P0-B concern and must not appear.

## Expected telemetry

- Correlation identifiers: the job's `correlation_id` appears on the creation event, the claim event, the completion event, and the attempt row.
- Structured event or log fields: `correlation_id`, `job_id`, `handler`, `attempt_no`, `from_state`, `to_state`, timestamp. One event per transition in the table above.
- Metrics and units: transition counter for `to_state = SUCCEEDED` incremented by 1; attempt duration recorded in milliseconds.
- Protected debug behavior: `error_detail` is null throughout; nothing protected is emitted.

## Failure classification and recovery

- Expected error class and code: none.
- Retryable: n/a.
- Operator-visible explanation: n/a.
- Safe retry or final action: none required.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_001`
- Assertions: the transition table above; exactly one row in each of `job_attempt` and `platform_effect`; invariants I1, I2, I4, and I5 from the contract.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 7 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_001`
- Known limitation: single worker, no contention; says nothing about behavior under concurrent claims.
