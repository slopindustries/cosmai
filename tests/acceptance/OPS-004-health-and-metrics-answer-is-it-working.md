# OPS-004 — Health and metrics distinguish a working platform from a stalled one

- Status: `DRAFT`
- Family: `OPS`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — "Expected behavior", observability
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H2
- Input fixture and metadata: synthetic.
- Owner: Project team

## Intent

`OPS-001` through `OPS-003` are about one job an operator already suspects. This one is about the question that comes first: **is anything wrong at all?**

The failure mode worth protecting against is a health endpoint that reports the API's own liveness and calls it platform health. An API that answers `ok` while no worker has claimed anything for an hour is worse than no health endpoint, because it converts an outage into a report of normal operation.

This is the scenario the plan's descope ladder removes first if the timebox runs short. It is written anyway, because a descoped scenario that exists as a document is a recorded gap, while one that was never written is an unrecorded one.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: the operator API running. Workers are started and stopped by the scenario.
- Configuration with secrets excluded: default.
- Time, retry, and concurrency assumptions: none.

## Action

1. With no worker running and no jobs, read health and metrics.
2. Stop the database, read health, and start it again. *(If stopping the shared cluster is unsafe in the harness, point the API at a database that does not exist instead and record which was done.)*
3. Create several jobs, run a worker to completion, and read metrics again.
4. Drive one job to `FAILED`, and read metrics again.
5. Create a job and leave it `PENDING` with no worker running. Read health.

## Expected state transitions

None. Health and metrics are observations.

## Expected durable effects

- Created or changed records: none from reading. Steps 3 and 4 change state by ordinary means and are not part of what is under test.
- Effects that must not occur: health must not create, claim, or modify a job. A liveness check with a side effect is a scheduled outage.
- Idempotency or duplicate expectation: repeated reads return the same answer for the same state.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: not applicable to health; these are platform-wide observations rather than per-job ones.
- Structured event or log fields: an unhealthy result is logged with its reason, so an operator who was not watching the dashboard can still find out when it started.
- Metrics and units: transition counts by target state, claim conflicts, suppressed duplicate effects, abandoned attempts, rejected completions, attempt durations, and lease recovery latency — the set `CONTRACT-JOB@0.1` requires. Counts are cumulative; durations carry a count so that a zero total is distinguishable from no observations.
- Protected debug behavior: no metric label carries a payload-derived value (`SEC-004`).

## Failure classification and recovery

- Expected error class and code: step 2 reports unhealthy with a reason naming the database. A `CONFIGURATION_INVALID` at startup is a different case and belongs to `SEC-003`; this is a database that was reachable and stopped being so, which is `PLATFORM_TRANSIENT` in the contract's SQLSTATE rule.
- Retryable: yes, and health must return to healthy once the database returns, without restarting the API. An API that has to be restarted to notice recovery turns a transient fault into an outage.
- Operator-visible explanation: "the database is unreachable", not "internal error".
- Safe retry or final action: none; this scenario reads.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_004`
- Assertions:
  - step 1 reports healthy with a reachable database and zeroed counters;
  - step 2 reports **unhealthy**, and the reason names the database — this is the load-bearing assertion, because it is what separates platform health from API liveness;
  - health returns to healthy after the database does, with no API restart;
  - step 3's transition counts match the jobs actually run, and step 4's `FAILED` count moves by exactly 1;
  - a **control**: at least one counter stays at 0 across steps 3 and 4 (no claim conflicts occur in a single-worker run), so a metrics surface that incremented everything would be caught;
  - step 5 reports healthy — a queue with no worker is a real condition an operator should see, but P0-A defines no liveness expectation for workers, so it is **not** an unhealthy platform. What it must not do is read as identical to an empty queue.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: metrics are per process and in memory. The API reports its own counters, and a worker's counters live and die with that worker — which is why `JOB-005` and `JOB-006` read a worker's counters from its shutdown report instead. A fleet-wide metrics view needs an aggregation P0-A does not have, and step 5 shows the consequence: the platform cannot tell an operator that no worker is running, only that nothing has been claimed. Both are P0-B questions about the operations contract.
