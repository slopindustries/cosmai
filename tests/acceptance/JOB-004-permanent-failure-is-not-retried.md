# JOB-004 — A permanent failure terminates without spending the retry budget

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md)
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the distinction between a failure worth repeating and one that is not. A platform that retries everything wastes budget and hides the real cause; a platform that retries nothing cannot recover from transient conditions. The retryability decision must be carried by the error class, not inferred from the exception type at the call site.

This scenario also covers `HANDLER_UNKNOWN`, which is the other non-retryable class reachable in P0-A.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: one worker process.
- Configuration with secrets excluded: lease duration 5 s; `max_attempts = 5`, deliberately generous so that an unspent budget is visible.
- Time, retry, and concurrency assumptions: no contention.

## Action

1. Create job A with `handler = "fail_permanent"` and `max_attempts = 5`.
2. Create job B with `handler = "not-registered"` and `max_attempts = 5`.
3. Run the worker until neither job is claimable.
4. Read both jobs, their attempts, and `platform_effect`.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 3 | job A | `PENDING` | `RUNNING` | `attempt_count = 1` |
| 3 | attempt A#1 | open | `PERMANENT_FAILURE` | `error_class = PLATFORM_PERMANENT` |
| 3 | job A | `RUNNING` | `FAILED` | `terminal_reason = PLATFORM_PERMANENT`, `attempt_count = 1` |
| 3 | job B | `PENDING` | `RUNNING` | `attempt_count = 1` |
| 3 | attempt B#1 | open | `PERMANENT_FAILURE` | `error_class = HANDLER_UNKNOWN` |
| 3 | job B | `RUNNING` | `FAILED` | `terminal_reason = HANDLER_UNKNOWN`, `attempt_count = 1` |

## Expected durable effects

- Created or changed records: exactly one attempt per job; both jobs `FAILED`.
- Effects that must not occur: no `platform_effect` row for either job; no second attempt for either job even though four attempts of budget remain; job B's unknown handler must not be invoked.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one per job; the two jobs' events are separable by `correlation_id`.
- Structured event or log fields: the terminal event carries `terminal_reason` and `attempt_count`, so that "failed permanently on attempt 1" is distinguishable from "failed after exhausting the budget" (`JOB-003`).
- Metrics and units: two `FAILED` transition increments; zero retryable-failure increments.
- Protected debug behavior: `error_detail` populated for both; absent from the default API representation.

## Failure classification and recovery

- Expected error class and code: `PLATFORM_PERMANENT` for job A, `HANDLER_UNKNOWN` for job B.
- Retryable: no, for both.
- Operator-visible explanation: for job B the summary must name the unregistered handler, because that is the operator's actual next action.
- Safe retry or final action: for job B, register the handler and then safe retry. Blind safe retry without registering it must fail identically rather than loop.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k job_004`
- Assertions: the transition table above; `attempt_count == 1` for both jobs despite `max_attempts == 5`; no `platform_effect` rows; the two terminal reasons are distinct and both are readable from the API.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: retryability is decided by the synthetic handler declaring its error class. P0-A produces no evidence about classifying a failure whose class is genuinely ambiguous, which is a real P0-B question for source errors.
