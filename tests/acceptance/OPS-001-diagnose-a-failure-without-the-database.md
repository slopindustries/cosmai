# OPS-001 — An operator explains a failure without touching the database

- Status: `DRAFT`
- Family: `OPS`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H1
- Input fixture and metadata: synthetic; the failures are the ones `JOB-003`, `JOB-004`, and `JOB-005` already produce.
- Owner: Project team

## Intent

Protect the charter's exit criterion *"The operator can inspect and safely retry generic work without direct database access."* This scenario owns the inspect half; `OPS-002` owns the retry half.

[OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H1's falsification condition is the test: *"A required operator scenario cannot be completed without direct database inspection or an additional first-class object not represented by the model."* So the scenario is written as a question about sufficiency, and the way to make it answerable is to forbid the shortcut — **the verification opens no database connection at all.** A test that reaches into `psycopg` to confirm what the API said has not established that the API was enough; it has established that the database was.

The P0-A navigation model under test is exactly three kinds of thing: platform health, jobs, and attempts. If a required answer needs a fourth, that is H1 refuted, and the fourth must be named rather than quietly added.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: the operator API running on its loopback binding; a worker available to produce the failures.
- Configuration with secrets excluded: default, `COSMA_API_HOST` unset so `SEC-002`'s default applies.
- Time, retry, and concurrency assumptions: none. Each case's job is driven to a terminal state before it is inspected.

## Action

Produce three failures, then answer the questions below **through the HTTP API only**.

| Case | How it is produced | The failure an operator sees |
|---|---|---|
| a | `fail_transient` with `max_attempts = 2` | exhausted its retry budget |
| b | `fail_permanent` | failed on its first attempt with budget left |
| c | an unregistered handler name | failed because nothing was registered to run it |

For each case, answer using only API responses:

1. **What ran?** the handler name and the job identity.
2. **With which input?** the opaque payload as it was submitted.
3. **When?** creation, each attempt's start, and the terminal transition.
4. **Why did it fail?** an error class and an operator-readable summary.
5. **Is anything left to try?** attempts spent against the budget.
6. **Is there detail being withheld?** whether protected debug detail exists for the attempt.

## Expected state transitions

None. The jobs reach their terminal states by the paths `JOB-003`, `JOB-004`, and `JOB-005` already record; this scenario observes what the operator surface says about them afterwards.

## Expected durable effects

- Created or changed records: none. Inspection is read-only, and a `GET` that writes would be its own defect.
- Effects that must not occur: no navigation object beyond health, jobs, and attempts is required to answer questions 1–6.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none. Lineage is a P0-B concern and its absence here is not a gap.

## Expected telemetry

- Correlation identifiers: every response concerning a job carries its `correlation_id`, which is the handle `OPS-003` uses to reach the log.
- Structured event or log fields: not under test here; `OPS-003` owns the log.
- Metrics and units: not under test here; `OPS-004` owns metrics.
- Protected debug behavior: question 6 is answered by a boolean in the default representation. Its absence would leave an operator unable to distinguish "there is no detail" from "there is detail you are not being shown", and the second is when asking for the protected representation is worth doing. The boolean carries no payload-derived value.

## Failure classification and recovery

- Expected error class and code: `PLATFORM_TRANSIENT` as the terminal reason for case a, `PLATFORM_PERMANENT` for case b, `HANDLER_UNKNOWN` for case c.
- Retryable: the class in case a is retryable while the job is not, because the budget is spent. Both facts must be readable, and they are different facts.
- Operator-visible explanation: case c's summary must name the handler that was not registered, because registering it is the operator's actual next action. A summary that says only "unknown handler" describes the failure without enabling the fix.
- Safe retry or final action: `OPS-002`.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_001`
- Assertions:
  - all six questions are answered for all three cases from API responses alone;
  - **the verification opens no database connection** — this is the load-bearing assertion, and it is what makes the others mean something;
  - the exhausted case (a) and the permanent case (b) are distinguishable by the fields the API returns, not by inference from timing;
  - case c's summary contains the unregistered handler's name;
  - no response contains `error_detail` unless the protected representation was asked for;
  - a job identity that does not exist returns a not-found status rather than an empty success, so an operator can tell a wrong identifier from a job with no history.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: OQ-005's evidence list also asks "by which version". P0-A has no versioned provider — no normalizer, no schema version, no source revision — so that question has no P0-A answer and is deliberately absent rather than approximated by the code revision. It becomes answerable in P0-B and must not be recorded as satisfied here.
