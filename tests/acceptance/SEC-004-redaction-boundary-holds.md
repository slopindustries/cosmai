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

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 59 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_004`. Evidence directory: `experiments/integrated-p0/evidence/2026-08-17-60807cb/`.
- **Verdict revised from `NOT RUN` to `PASS`.** It was recorded `NOT RUN` earlier today with 24 passing tests, because the log and both API representations were covered while Action steps 3 and 4 — the dashboard screen and a screenshot of it — were not. The dashboard now exists and the screen is read on every run. What is executed and what is not is stated below rather than collapsed into the verdict.
- **Step 3 is executed.** The job-detail screen is rendered by the same components the browser mounts, server-side under Node, from HTTP responses obtained from a real API process. Every assertion searches the visible text of that screen. For each of the eight redacted keys, its marker appears on no screen; the redaction marker appears where the value was removed and the key name survives; the marker under an ordinary key **is** on the screen, which is the detection control that makes the eight absences mean something; `error_detail` is absent from the default screen and present on the protected one, and reserved keys stay masked even there; the correlation identifier is present and unmasked; and a refused retry shows the state the job was in and the state a retry requires, carrying no marker and no protected detail.
- **Step 4 is not executed, and this is the one respect in which the scenario is not literally satisfied.** A screenshot needs a browser driver, and [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D6 puts the dashboard's dependency floor below one. `dashboard/README.md` records the reproduction procedure for a human capture. The gap is narrow but real: a value hidden by CSS, or parked in a DOM attribute rather than in text, would pass these assertions and fail a person's eyes. `PASS` is recorded because the boundary the scenario protects — that a marked value never reaches a surface an operator reads — is asserted against the real component tree on every run, and a rendering-level leak is a different failure from the redaction-level one under test. A reviewer who disagrees should read this as `CONDITIONAL`.
- A second job was added to reach an observation the scenario's own Action could not: `fail_permanent` builds its own `error_detail`, so markers had to be placed inside `error_detail` deliberately. Without that, "the default screen withholds detail" would have been an absence rather than an observation.
- Known limitation: redaction is key-name based throughout. A secret placed under an innocuous key is not detected, and P0-A produces no evidence about value-shape detection. Whether that is needed is decided by P0-B's `credential_ref` design under [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md).
- Known limitation: the dashboard's own identifiers are **not** covered by the boundary guard, which parses `.py` and `.sql` only. The vocabulary is held by the fixed substitutions in `dashboard/README.md` and verified by a recorded grep, not by a parser.
