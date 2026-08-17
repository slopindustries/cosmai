# JOB-008 — Duplicate execution does not produce an uncontrolled durable effect

- Status: `DRAFT`
- Family: `JOB`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — invariant I1
- Related Open Question or Decision Packet: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md) H1
- Input fixture and metadata: synthetic, generated in-test.
- Owner: Project team

## Intent

Protect the charter's second P0-A exit criterion: *"Duplicate execution does not produce an uncontrolled platform-level durable effect."*

The word to hold on to is *uncontrolled*. At-least-once delivery means duplicate execution is expected behavior, not a defect. The platform's obligation is that a repeat is detected and reconciled, not that it never happens. A design that merely tries hard to avoid duplicates and has no detection has not satisfied this criterion, even if no duplicate is observed during the run — which is why the scenario forces one rather than waiting for it.

`JOB-005` case B reaches a duplicate through interruption. This scenario reaches it directly and concurrently, so the suppression is tested against a real race rather than against a sequential replay.

## Preconditions

- Initial durable state: migrations applied; tables empty.
- Worker or service state: case A single worker; cases B and C four workers.
- Configuration with secrets excluded: lease duration comfortably longer than the handler runtime.
- Time, retry, and concurrency assumptions: the handler derives `effect_key` from its payload rather than from the job identity, so that distinct jobs can deliberately collide.

## Action

**Case A — sequential replay.** Create a job with `handler = "succeed"` and a fixed `effect_key`. Run it to `SUCCEEDED`. Apply an operator safe retry so the same job runs again. Read `platform_effect`.

**Case B — concurrent collision.** Create 20 jobs that all derive the *same* `effect_key`, all due immediately. Start four workers. Wait until every job is terminal.

**Case C — no false suppression.** Create 20 jobs with 20 *distinct* `effect_key` values, all due immediately. Start four workers. Wait until every job is terminal.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| A | `job` | `SUCCEEDED` → `PENDING` → `RUNNING` → `SUCCEEDED` | | Safe retry resets `attempt_count`; prior attempts retained |
| B | each `job` | `PENDING` → `RUNNING` → `SUCCEEDED` | | All 20 succeed; none fails because of the collision |
| C | each `job` | `PENDING` → `RUNNING` → `SUCCEEDED` | | |

A collided insert is a suppression, not a failure. A job whose effect was already applied has done its work and must reach `SUCCEEDED`.

## Expected durable effects

- Created or changed records: case A — two `job_attempt` rows, **one** `platform_effect` row. Case B — 20 jobs `SUCCEEDED`, 20 attempts, **exactly one** `platform_effect` row. Case C — 20 jobs `SUCCEEDED`, 20 attempts, **exactly 20** `platform_effect` rows.
- Effects that must not occur: more than one row per `effect_key` under any concurrency (invariant I1); a job failing because another job got there first; in case C, any suppression at all.
- Idempotency or duplicate expectation: the entire point. Case C is the control that proves suppression is keyed rather than blanket.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: one per job; the suppressed-duplicate event carries the correlation identifier of the job that was suppressed **and** the `effect_key`, so an operator can find the job that won.
- Structured event or log fields: a suppressed-duplicate event per suppression, naming `effect_key` and `job_id`.
- Metrics and units: suppressed-duplicate counter — 1 in case A, 19 in case B, **0 in case C**. Case C's zero is what makes the other two numbers meaningful.
- Protected debug behavior: `effect_key` is a synthetic platform value and is not redacted. It must not be derived from anything a redaction rule would remove.

## Failure classification and recovery

- Expected error class and code: none. Suppression is not an error.
- Retryable: n/a.
- Operator-visible explanation: a job whose effect was suppressed still shows as succeeded, and the suppression is discoverable from its events.
- Safe retry or final action: case A exercises operator safe retry, which must be genuinely safe — that is what "safe" means in the charter's exit criterion about retry from the dashboard.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -m concurrency -k job_008`
- Assertions: the row counts above, exactly; the suppressed-duplicate counter matches 1 / 19 / 0; every job reaches `SUCCEEDED` in all three cases; case A's first attempt is still readable after the retry; **cases B and C are each repeated at least five times.**
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: the durable effect is one row with a primary-key conflict. Real acquisition and normalization effects in P0-B span several statements and possibly several tables, and the boundary that holds here is not evidence that it holds there. That gap is OQ-006 H1 and must be re-tested in P0-B.
