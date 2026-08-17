# SEC-003 — Invalid platform configuration fails loudly and is not retryable

- Status: `DRAFT`
- Family: `SEC`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)
- Related Open Question or Decision Packet: [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md)
- Input fixture and metadata: synthetic environment variables, set per case in-test.
- Owner: Project team

## Intent

Protect the rule in [Secret Setup](../../docs/conventions/secret-setup.md): *"Credential이 없거나 해석되지 않으면 non-retryable configuration failure로 종료한다. 빈 값이나 fallback credential로 계속하지 않는다."*

P0-A has no credential to resolve, so the testable half of that rule is the general one: a process given invalid configuration must refuse to start, name what is wrong, and not substitute a default. A platform that silently falls back is one whose later security evidence means nothing, because no one can tell which configuration actually ran.

## Preconditions

- Initial durable state: irrelevant; the process must fail before touching the database.
- Worker or service state: no process running.
- Configuration with secrets excluded: a valid baseline environment, mutated one variable at a time per case.
- Time, retry, and concurrency assumptions: none.

## Action

For each case, start the worker entrypoint and then the API entrypoint with the stated environment and observe the exit.

| Case | Mutation |
|---|---|
| a | `COSMA_DB_HOST` unset |
| b | `COSMA_DB_NAME` unset |
| c | `COSMA_DB_HOST` set to a path that does not exist |
| d | a required numeric setting (lease duration) set to a non-numeric string |
| e | a required numeric setting set to zero or a negative value |
| f | an unknown `COSMA_`-prefixed variable present alongside a valid baseline |

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| a–e | process | starting | exited non-zero | Refused before opening a database connection |
| f | process | starting | running | An unknown variable is reported, not fatal |

Case f is deliberately not fatal: rejecting unknown variables would make the process fail on unrelated environment noise. It must still be visible, because a typo in a real setting name presents exactly this way.

## Expected durable effects

- Created or changed records: none. No migration runs, no job row, no `platform_effect` row.
- Effects that must not occur: no partial startup; no connection attempt in cases a–e; no default value substituted for a missing or invalid setting.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: none required; the failure precedes job context.
- Structured event or log fields: one structured event carrying the error class, the offending setting name, and why it was rejected. The offending **value** is included only when it is not a candidate secret; `SEC-004` owns the redaction rule that decides this.
- Metrics and units: none required.
- Protected debug behavior: the message must be actionable without printing the whole environment. Dumping the environment on a configuration error is a leak channel that [Secret Setup](../../docs/conventions/secret-setup.md) names explicitly.

## Failure classification and recovery

- Expected error class and code: `CONFIGURATION_INVALID`.
- Retryable: no. A supervisor restarting the process must fail identically rather than eventually succeed.
- Operator-visible explanation: the setting name and the reason, on stderr and in the structured log.
- Safe retry or final action: correct the configuration and restart. No in-band recovery exists.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_003`
- Assertions: cases a–e exit non-zero with `CONFIGURATION_INVALID` and name the offending setting; no database connection is attempted in those cases; case f starts and emits a warning naming the unknown variable; no case prints the full environment.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 44 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_003`
- Known limitation: P0-A has no credential setting, so this proves the refusal mechanism rather than that it holds for a real credential. That remains a P0-B obligation under OQ-007.
