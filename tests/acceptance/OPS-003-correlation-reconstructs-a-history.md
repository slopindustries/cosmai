# OPS-003 — One correlation identifier reconstructs a history that spans process deaths

- Status: `DRAFT`
- Family: `OPS`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — invariant I5
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H2
- Input fixture and metadata: synthetic; the history is the one `JOB-005` case B and `JOB-006` produce.
- Owner: Project team

## Intent

[OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) H2 claims that *"correlated structured events plus a small metrics set are sufficient for P0 diagnosis."* Its falsification condition is an injected failure that cannot be classified from that evidence.

The hardest history P0-A can produce is the one that crosses a process boundary: a worker claims a job, dies mid-attempt, and a different process finishes it. Nothing in either process's memory spans that gap. If the correlation identifier does not either, then an operator investigating a job that "took two tries" has to correlate two processes by timestamp and guesswork, and H2 is refuted for exactly the case where diagnosis matters most.

`JOB-005` and `JOB-006` already proved the *platform* recovers. This scenario asks whether the recovery is **legible** afterwards.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: the operator API running; worker processes started and killed by the scenario.
- Configuration with secrets excluded: structured log directed somewhere the API can read it. **Where is an implementation choice**, recorded with its rationale — this scenario fixes the operator requirement, not the transport.
- Time, retry, and concurrency assumptions: the first process is killed after it applies its durable effect, so the recovering attempt has a suppression to explain.

## Action

1. Create a job whose handler applies its effect and then ends its own process on the first attempt.
2. Start a worker; let it claim, apply the effect, and die.
3. Let the lease expire. Start a second worker; let it reclaim and finish the job.
4. Read the job and its attempts through the API, and note the `correlation_id`.
5. Ask the API for the structured events carrying that `correlation_id`.
6. From step 5's response alone, answer: how many attempts there were, which one was abandoned and why, which process ran each, whether a durable effect was applied more than once, and how the job ended.

## Expected state transitions

None new. The job follows `JOB-005` case B's path.

## Expected durable effects

- Created or changed records: none. Steps 4–6 are read-only.
- Effects that must not occur: the query in step 5 must not require a process identity, a time range, or an attempt number as a second key. One handle is the claim under test.
- Idempotency or duplicate expectation: exactly one `platform_effect` row, and the suppression is visible in the events rather than only in a counter.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: **one identifier covers both processes.** The events from the process that died and the process that recovered carry the same `correlation_id` and differ by `worker_id`. This is invariant I5 observed across a boundary that no in-memory context survives.
- Structured event or log fields: the returned events include the claim, the effect suppression, the reclaim that closed the abandoned attempt, and the terminal transition. Each carries `job_id`, `worker_id`, and `attempt_no` where it applies.
- Metrics and units: not under test; `OPS-004` owns metrics.
- Protected debug behavior: a returned event carrying protected detail must be redacted exactly as `SEC-004` requires. Serving events through the API must not become a second route to what the attempt representation withholds.

## Failure classification and recovery

- Expected error class and code: `LEASE_ABANDONED` on the first attempt, readable from the events without opening the attempt representation.
- Retryable: yes, and it was retried automatically. The events must show that no operator action was needed, or an operator will take one anyway.
- Operator-visible explanation: "a worker died after doing the work; the next attempt found the effect already applied and finished the job." Every clause of that sentence must be derivable from step 5's response.
- Safe retry or final action: none required. A job that recovered by itself must not read as one awaiting attention.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_003`
- Assertions:
  - all five questions in step 6 are answered from the correlated events alone;
  - the response contains events from **both** `worker_id` values, and their `correlation_id` is identical — a run where only one process's events came back would satisfy a weaker assertion and prove nothing;
  - a **control**: events for a second, unrelated job are present in the log and absent from this query, so the filter is doing work rather than returning everything;
  - the abandoned attempt's `error_class` is present in the events;
  - the suppression event names the `effect_key`;
  - values under redacted keys are masked in the returned events.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/` — including the correlated event set as captured, since it is the artifact the gate reviewer would otherwise have to take on trust.
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 8 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_003`. Captured event set: `experiments/integrated-p0/evidence/2026-08-17-60807cb/ops-003-correlated-events.json`, with the log it was filtered from beside it as `platform.jsonl`.
- **Transport choice, with its rationale, as the preconditions require.** The structured log goes to one JSON Lines file named by a new `COSMA_LOG_FILE` setting, which every process reads through the same configuration path, and `GET /events?correlation_id=…` filters it. A table was rejected: telemetry inside the schema `CONTRACT-JOB@0.1` fixes would need a migration and a contract amendment to reach a result the file already gives, and it would make the log two things that can disagree. The file must end in `.jsonl` and the setting is refused otherwise, because `.gitignore` excludes `*.log` and a log the evidence directory silently dropped would be worse than none. The path is resolved once at startup and a request supplies only an identifier, so no query can become a read of an arbitrary file.
- All five of step 6's questions were answered from step 5's response alone: nine events came back for one identifier, carrying two distinct `worker_id` values with an identical `correlation_id`, the claim of each attempt, `job.effect_applied` once, `job.attempt_abandoned` with `error_class = LEASE_ABANDONED` on attempt 1, `job.effect_suppressed` naming the `effect_key`, and the terminal transition to `SUCCEEDED` on attempt 2.
- The control ran: a second, unrelated job's events were in the same file and reachable by their own identifier, and neither its `correlation_id` nor its `job_id` appears in this query's response.
- Redaction was tested at the API rather than at the writer. The platform masks every event before it reaches the file, so searching a real log for a marker would prove only that nothing was attempted; a line was therefore appended past the logger carrying an unmasked value under a redacted key and protected detail under `error_detail`. The response masked the first, withheld the second and reported only its presence, and the ordinary marker beside them survived as the detection control.
- Reading of "each carries `job_id`, `worker_id`, and `attempt_no` where it applies", recorded because it is a place a stricter reading would fail: `job.effect_applied` and `job.effect_suppressed` carry `job_id` and `effect_key` but no `worker_id` or `attempt_no`, because the store issues them and does not know the attempt; `job.attempt_abandoned` names the recovering process as `reclaimed_by` rather than `worker_id`, since the abandoned attempt's own worker is not the one writing the line. Question 3 is answered from the claim transitions, which do carry `worker_id`. If the intent was that every event carry all three, that is a change to the event shape and needs a decision.
- Known limitation: correlation is per job. P0-A has no operation that fans out across several jobs, so nothing here establishes that one identifier can span a batch — which is exactly the shape a P0-B collection run over many pages will have. Recorded as a P0-B question rather than answered.
- Known limitation: the transport is a local append-only file. It is unrotated and unbounded, the query is a linear scan, and it is reachable only on the host that wrote it. That is adequate for a single-host P0-A and is not a design for anything else; a P0-B decision about where correlated events live should not read this result as evidence that a file is sufficient.
