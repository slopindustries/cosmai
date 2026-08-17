# OPS-002 — Retry from the operator surface, and it is genuinely safe

- Status: `DRAFT`
- Family: `OPS`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — invariant I1, and the `FAILED → PENDING` transition
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H2
- Input fixture and metadata: synthetic; the exhausted job is the one `JOB-003` produces.
- Owner: Project team

## Intent

The charter's exit criterion says the operator can *"inspect and safely retry"* generic work. `OPS-001` owns inspect. The word this scenario is about is **safely**.

A retry button that re-runs work is easy. A retry that is safe has to hold two things at once: work that already produced its durable effect must not produce a second one, and work the operator did not mean to touch must not move. The first is invariant I1 reached through the operator path rather than through a worker race — `JOB-008` established it under concurrency, and this establishes that the operator surface does not bypass it. The second is why the refusals are asserted here rather than assumed.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: the operator API running; a worker available to run the retried job.
- Configuration with secrets excluded: default.
- Time, retry, and concurrency assumptions: none. The retry is requested while no worker holds the job.

## Action

**Case a — a permitted retry that is safe.**
1. Run a job to `FAILED` by retry exhaustion, using a handler that applies its durable effect on an attempt that then fails, so an effect exists **before** the retry.
2. Read the effect count.
3. Request a retry through the API.
4. Let a worker run the job to `SUCCEEDED`.
5. Read the effect count and the attempt history again.

**Case b — a retry the operator did not mean.** Request a retry on a `SUCCEEDED` job.

**Case c — a retry on work in flight.** Request a retry on a `RUNNING` job whose lease is held.

**Case d — a retry on nothing.** Request a retry on a job identity that does not exist.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| a.3 | `job` | `FAILED` | `PENDING` | `attempt_count` reset to 0, `available_at = now()`, prior attempts retained |
| a.4 | `job` | `PENDING` → `RUNNING` → `SUCCEEDED` | | A new attempt, numbered above every attempt the job ever had |
| b | `job` | `SUCCEEDED` | `SUCCEEDED` | Refused: safe retry starts from `FAILED` only |
| c | `job` | `RUNNING` | `RUNNING` | Refused: the same rule, and the lease holder is unaffected |
| d | — | — | — | Not found; nothing is created |

## Expected durable effects

- Created or changed records: case a ends with one more `job_attempt` than it started with and the job `SUCCEEDED`. Cases b, c, and d change nothing at all.
- Effects that must not occur: **the effect count is the same before and after case a's retry.** The retried attempt re-derives the same `effect_key` and its insert is suppressed. A second row here would mean the operator surface can create the duplicate that the worker path is protected against.
- Idempotency or duplicate expectation: the suppression is counted and logged, as in `JOB-008`.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: the retried job keeps its original `correlation_id`, so the whole history — including the attempts from before the retry — remains reachable by one handle. A retry that mints a new identifier would sever the operator's view of why the job was retried in the first place.
- Structured event or log fields: one event recording that a retry was requested and accepted, and one recording a refusal, each naming the job and the state it was in. A refusal that logs nothing leaves an operator unable to explain why the button did nothing.
- Metrics and units: the suppressed-duplicate counter moves by exactly 1 in case a.
- Protected debug behavior: unchanged.

## Failure classification and recovery

- Expected error class and code: the refusals in cases b and c are not platform failures; they are a rejected request. The response must say which state the job was in and which state a retry requires.
- Retryable: n/a.
- Operator-visible explanation: "this job is `SUCCEEDED`; a retry starts from `FAILED`" is actionable. "Bad request" is not.
- Safe retry or final action: case a *is* the final action.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_002`
- Assertions:
  - case a's effect count is identical before and after, and the suppressed-duplicate counter moved by 1 — **the counter is what distinguishes "suppressed" from "never attempted"**;
  - case a's new attempt number is above every attempt the job previously had, and the earlier attempts are still readable;
  - cases b and c leave the whole job row unchanged, compared field by field including `updated_at`;
  - case c's lease holder and its open attempt are untouched;
  - case d creates nothing;
  - every refusal names the current state and the required state.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 11 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_002`. Evidence directory: `experiments/integrated-p0/evidence/2026-08-17-60807cb/`.
- All four cases executed. `POST /jobs/{id}/retry` accepts only from `FAILED`; cases b and c return `409` naming the state the job was in and the state a retry requires, and their job rows compare equal field by field including `updated_at`; case d returns `404` and the job count is unchanged.
- Ambiguity resolved in favour of the Action text, and recorded rather than assumed: this scenario's *Input fixture* line says the exhausted job is the one `JOB-003` produces, but `JOB-003` uses `fail_transient`, which fails *before* it reaches its effect — so that fixture cannot satisfy Action step 1's "a handler that applies its durable effect on an attempt that then fails". A synthetic injector `apply_effect_then_fail` was added for exactly this. Without it, case a's "the effect count is the same before and after" would have been true for the uninteresting reason that there was never an effect to duplicate.
- How the counter assertion was read: metrics are per process, so "moved by exactly 1" is observed as `0` in the shutdown report of the worker that exhausted the job and `1` in the report of the worker that ran the retried attempt. Two registries rather than one delta, which is a consequence of `CONTRACT-JOB@0.1` keeping metrics in process memory, and it still distinguishes "suppressed" from "never attempted" because the second process is the one that re-derived the key.
- Case d also emits a refusal event, which this scenario's telemetry section did not require. A `404` on a retry is the case where an operator was acting on a stale list, and leaving it out of the log would make the one confusing outcome the only unexplainable one.
- Known limitation: the retry is unauthenticated, as is everything on the loopback binding (`SEC-002`). Anything running on the host can retry any job, so this is evidence that retry is *idempotent*, not that it is *authorized*. Authorization is outside P0 and must be revisited before anything real is stored.
- Known limitation: case c's lease is held by a name this process claimed under, not by a separate worker process. The refusal path never reads `lease_owner`, so the holder's identity is not what is under test; `JOB-006` is where a real second process contends.
