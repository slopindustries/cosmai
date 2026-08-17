# JOB-005 — Interruption before and after a durable effect reaches a documented state

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md) H1
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the charter's exit criterion *"Interrupted or expired work reaches a documented recoverable or final state,"* at the one place where at-least-once delivery is actually dangerous: the window between applying a durable effect and recording that it was applied.

The two interruption points are not symmetric in the code but must be symmetric in the outcome. Whether the process died before or after the effect, the job must end with exactly one effect and a terminal state. If the two cases diverge, the idempotency boundary is in the wrong place — and that is OQ-006 H1's falsification condition, not a bug to patch.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: one worker process, restarted after each interruption.
- Configuration with secrets excluded: lease duration short enough that expiry is observed without real waiting; `max_attempts = 3`.
- Time, retry, and concurrency assumptions: the handler terminates its own process on attempt 1 only, then behaves normally.

## Action

Run two cases independently, each from an empty state.

**Case A — interrupted before the effect.**
1. Create a job with `handler = "halt_before_effect"`, payload `{halt_on_attempt: 1}`, `max_attempts = 3`.
2. Let the worker claim it and terminate itself uncleanly, leaving the lease held and the attempt open.
3. Restart the worker and run until the job is terminal.

**Case B — interrupted after the effect.**
1. Same, with `handler = "halt_after_effect"`.
2. The handler inserts its `platform_effect` row and then terminates before the job's terminal transition is recorded.
3. Restart the worker and run until the job is terminal.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 2 | `job` | `PENDING` | `RUNNING` | `attempt_count = 1`, lease held |
| 2 | `job_attempt` #1 | open | open | Process died; the attempt is left open with `finished_at` null |
| 3 | `job_attempt` #1 | open | `ABANDONED` | Closed on reclaim, `error_class = LEASE_ABANDONED` |
| 3 | `job` | `RUNNING` (lease expired) | `RUNNING` | Reclaimed, `attempt_count = 2`, new lease |
| 3 | `job_attempt` #2 | open | `SUCCEEDED` | |
| 3 | `job` | `RUNNING` | `SUCCEEDED` | `terminal_reason` null |

## Expected durable effects

- Created or changed records: two `job_attempt` rows, the first `ABANDONED`; job `SUCCEEDED`; **exactly one `platform_effect` row in both cases.**
- Effects that must not occur: two `platform_effect` rows in case B; zero rows in either case; a job left `RUNNING` with no path forward (invariant I3).
- Idempotency or duplicate expectation: in case B the second attempt re-derives the same `effect_key` and its insert is suppressed. The suppression is counted, not silent.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one `correlation_id` survives the process restart and appears on both attempts. A correlation identifier that only lives in process memory would not, which is the point of storing it on the job.
- Structured event or log fields: a reclaim event naming the abandoned `attempt_no` and the expired lease; in case B, a suppressed-duplicate event carrying the `effect_key`.
- Metrics and units: abandoned-attempt counter incremented by 1 in both cases; suppressed-duplicate counter incremented by 1 in case B and 0 in case A; lease recovery latency recorded in milliseconds.
- Protected debug behavior: unchanged.

## Failure classification and recovery

- Expected error class and code: `LEASE_ABANDONED` on attempt 1 of both cases.
- Retryable: yes; recovery is automatic and consumes one attempt from the budget.
- Operator-visible explanation: the job shows an abandoned attempt and a successful one. An operator must be able to see that a worker died without reading logs.
- Safe retry or final action: none required.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_005`
- Assertions: the transition table for both cases; `SELECT count(*) FROM platform_effect` is exactly 1 in both; the suppressed-duplicate counter differs between the cases, proving the two interruption points were genuinely different and not both landing before the effect; invariants I1 and I3.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 12 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_005`
- Known limitation: the process is ended with `os._exit`, a clean kill at a chosen instruction. A real crash can land mid-statement, and PostgreSQL's own crash recovery is not exercised.
