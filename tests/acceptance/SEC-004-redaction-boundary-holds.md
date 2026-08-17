# SEC-004 — The redaction boundary holds across logs, errors, API responses, and screenshots

- Status: `DRAFT`
- Family: `SEC`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — "Provenance and security"
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md), [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md)
- Input fixture and metadata: synthetic marker values generated in-test. No real credential exists in P0-A.
- Owner: Project team

## Intent

Protect the charter's exit criterion *"Logs, metrics, errors, and screenshots preserve the declared redaction boundary."*

[OQ-005](../../docs/open-questions/OQ-005-operations-contract.md) records this as a safety constraint rather than a hypothesis: *"Debug details require redaction and an explicit local access boundary even if no leak is observed during the experiment."* A run in which nothing leaked is therefore not evidence. The scenario deliberately injects values that **should** leak if the boundary is absent, so that a passing result means the mechanism worked rather than that nothing was tried.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: one worker and the operator API running.
- Configuration with secrets excluded: default redaction key set from the contract — `password`, `token`, `secret`, `authorization`, `cookie`, `api_key`, `apikey`, `credential`, matched case-insensitively.
- Time, retry, and concurrency assumptions: none.

## Action

1. Create a job whose opaque payload contains a distinctive marker value under each key in the redaction set, plus one marker under an ordinary key that must survive.
2. Run it with `handler = "fail_permanent"` so that the failure path, `error_summary`, and `error_detail` are all populated.
3. Read: the structured log file, the job and attempt through the operator API in its default representation, the operator API's protected-debug representation, and the dashboard job-detail screen.
4. Capture a screenshot of the dashboard job-detail screen.
5. Search every artifact from steps 3 and 4 for each marker value.

## Expected state transitions

No job state transition is under test here. The job follows `JOB-004`'s permanent-failure path; this scenario observes what that path emits.

## Expected durable effects

- Created or changed records: one `job` in `FAILED`, one `job_attempt` with `error_summary` and `error_detail` populated.
- Effects that must not occur: no marker value under a redacted key appears in the structured log, the default API representation, the dashboard, or the screenshot.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: present on every artifact, and not redacted — a redacted correlation identifier would make diagnosis impossible.
- Structured event or log fields: values under redacted keys are replaced by a redaction marker. The **key name** survives, because knowing that a token was present is diagnostic while its value is not.
- Metrics and units: metric labels carry no payload-derived values.
- Protected debug behavior: `error_detail` is absent from the API's default representation. It is reachable only through the explicit protected-debug representation, which is available only on the loopback binding (`SEC-002`). Even there, redacted keys stay redacted — protected does not mean unredacted.

## Failure classification and recovery

- Expected error class and code: `PLATFORM_PERMANENT`, from the handler used to reach the failure path.
- Retryable: no.
- Operator-visible explanation: `error_summary`, redacted, sufficient to identify the failure class.
- Safe retry or final action: n/a for this scenario.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_004`; the screenshot step runs with the `OPS` scenarios in S5.
- Assertions: for each redacted key, its marker value appears in **no** artifact; the marker under the ordinary key appears in the log and the API, proving the search would have found a leak; the redaction marker is present where a value was removed; `error_detail` is absent from the default API representation and present in the protected one; the correlation identifier is intact everywhere.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/` — including `platform.jsonl` and the dashboard screenshot. Structured logs use `.jsonl` because `.gitignore` excludes `*.log` and this evidence must be reviewable at the gate.
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: redaction is key-name based. A secret placed under an innocuous key is not detected, and P0-A produces no evidence about value-shape detection. Recorded rather than solved, because the P0-B `credential_ref` design under OQ-007 is what decides whether value-based detection is needed at all.
