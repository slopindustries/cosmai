# CONTRACT-JOB@0.1 — Handler-neutral platform job execution

- Status: `EXPERIMENTAL`
- Version: `0.1`
- Owner: Project team
- Related Open Question: [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md), [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md)
- Related Decision Packet: [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md)
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Producers: `platform_core.jobs`, `platform_core.handlers`, `platform_core.worker`
- Consumers: `platform_core.api`, the operator dashboard, `tests/acceptance/JOB-*`, `tests/acceptance/SEC-*`
- Last updated: 2026-08-17T00:00:00+09:00

## Purpose and boundary

This contract fixes how the P0-A platform runs work whose meaning it does not know. A job names a registered handler and carries an opaque payload; the platform owns claiming, leasing, attempts, retry scheduling, terminal states, recovery, and the single durable effect a handler is permitted to produce.

**Outside this contract:** what any handler computes, where its input came from, what its output means, and whether the work is acquisition or normalization. P0-A has no answer to any of those and must not imply one. A handler that needed source identity, payload structure, or result semantics to be specified here would be outside the P0-A boundary defined by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md).

The contract deliberately says nothing about throughput, scale-out beyond a single host, or scheduling fairness.

## Compatibility statement

- **Compatibility obligation during P0:** none beyond P0-A. This version exists so that `JOB` and `SEC` scenarios have something stable to test against within one experiment.
- **Known incompatible changes:** P0-B will need per-domain retry policy and additional durable effects. Both are expected to change the state machine. OQ-006 H3 is the open question that decides how.
- **Promotion or replacement condition:** this version is not a promotion candidate. What may be promoted is the recorded evidence about where the idempotency and transaction boundaries belong, carried into `PoC Contract 0.1` by P0-B's Architecture Synthesis.

Experimental status permits replacement without migration inside P0. It does not permit changing behavior here without changing the version and the affected scenarios.

## Schema or message shape

Authoritative SQL lives in `experiments/integrated-p0/platform_core/db/migrations/`. The shape below is the contract; column order and index choices are implementation detail.

### `job`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | uuid | yes | Job identity. Stable across attempts. |
| `handler` | text | yes | Name of a registered handler. Not a source, adapter, or provider identifier. |
| `payload` | jsonb | yes | Opaque to the platform. Passed to the handler unchanged. |
| `state` | text | yes | `PENDING` \| `RUNNING` \| `SUCCEEDED` \| `FAILED` |
| `attempt_count` | int | yes | Attempts started, including abandoned ones. Starts at 0. |
| `max_attempts` | int | yes | Attempt budget. Must be ≥ 1. |
| `available_at` | timestamptz | yes | Earliest time the job may be claimed. |
| `lease_owner` | text | null when not `RUNNING` | Identity of the worker holding the job. |
| `lease_expires_at` | timestamptz | null when not `RUNNING` | Time after which the lease is void. |
| `terminal_reason` | text | null until terminal | Error class for `FAILED`; `null` for `SUCCEEDED`. |
| `correlation_id` | text | yes | Assigned at creation. Present on every log line and attempt for this job. |
| `created_at` / `updated_at` | timestamptz | yes | |

### `job_attempt`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | uuid | yes | |
| `job_id` | uuid | yes | |
| `attempt_no` | int | yes | 1-based. Unique per job. |
| `worker_id` | text | yes | |
| `started_at` | timestamptz | yes | |
| `finished_at` | timestamptz | null while open | |
| `outcome` | text | null while open | `SUCCEEDED` \| `RETRYABLE_FAILURE` \| `PERMANENT_FAILURE` \| `ABANDONED` |
| `error_class` | text | null on success | See the error table below. |
| `error_summary` | text | null on success | Operator-visible. Redacted. |
| `error_detail` | jsonb | null on success | **Protected debug detail.** Never returned by the API by default. |
| `correlation_id` | text | yes | Copied from the job. |

### `platform_effect`

The only durable effect a P0-A handler may produce. Fixed by [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D8.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `effect_key` | text | yes, primary key | Chosen by the handler. Independent of attempt number. The entire idempotency mechanism. |
| `job_id` | uuid | yes | |
| `applied_at` | timestamptz | yes | |
| `payload` | jsonb | no | **Opaque synthetic value with no schema.** |

`payload` carries no provenance fields, no identity semantics, and no version. Giving it structure would make this table a Raw envelope and would place P0-A outside its boundary. `observation`, `record`, `item`, and `document` are prohibited names for this table and its columns.

### `schema_migrations`

`version text primary key`, `applied_at timestamptz`. Applied in filename order by `platform_core.db`.

## Semantics

### Invariants

- **I1 — Single durable effect per key.** At most one `platform_effect` row exists per `effect_key`, regardless of how many attempts execute or how they are interrupted.
- **I2 — No conflicting active ownership.** A job never has two `job_attempt` rows with `finished_at IS NULL` at the same time. Equivalently, at most one worker holds a valid lease on a job at any instant.
- **I3 — No stranded state.** Every job is either terminal (`SUCCEEDED`, `FAILED`) or claimable — `PENDING` with `available_at` in the past or future, or `RUNNING` with an expired lease. There is no state from which no transition is possible.
- **I4 — Bounded attempts.** `attempt_count` never exceeds `max_attempts`. Reaching it forces a terminal transition.
- **I5 — Correlation is total.** Every log line, attempt row, and API response concerning a job carries its `correlation_id`.

### State transitions

| From | To | Trigger | Required side effect |
|---|---|---|---|
| — | `PENDING` | Job created | `correlation_id` assigned, `attempt_count = 0` |
| `PENDING` | `RUNNING` | Claim, when `available_at <= now()` | `attempt_count += 1`, new open `job_attempt`, lease set |
| `RUNNING` (lease expired) | `RUNNING` | Reclaim by another worker | Previous attempt closed as `ABANDONED`, `attempt_count += 1`, new open attempt, new lease |
| `RUNNING` | `SUCCEEDED` | Handler returns normally | Attempt closed `SUCCEEDED`, lease cleared |
| `RUNNING` | `PENDING` | Retryable failure, `attempt_count < max_attempts` | Attempt closed `RETRYABLE_FAILURE`, lease cleared, `available_at` set by backoff |
| `RUNNING` | `FAILED` | Retryable failure, `attempt_count >= max_attempts` | Attempt closed `RETRYABLE_FAILURE`, `terminal_reason` set |
| `RUNNING` | `FAILED` | Permanent failure | Attempt closed `PERMANENT_FAILURE`, `terminal_reason` set |
| `FAILED` | `PENDING` | Operator safe retry | `attempt_count` reset to 0, `available_at = now()`, prior attempts retained |

**A lease-expiry reclaim consumes an attempt.** Without this, a handler that reliably kills its worker would be retried forever. The cost is that a worker crash unrelated to the job also spends budget; this is recorded as a known limitation rather than solved in P0-A.

Claiming is a single statement using `FOR UPDATE SKIP LOCKED` over rows that are `PENDING` and due, or `RUNNING` with an expired lease. One statement handles both dispatch and recovery, so there is no separate sweep whose absence could strand work.

**A completion is fenced.** A worker's attempt to record any outcome — success, failure, or reschedule — is accepted only if that worker still owns the current lease **and** its own attempt row is still open. Otherwise the write is refused, changes nothing, and is recorded as a rejected completion.

This rule is what makes I2 an invariant rather than a hope. A lease that is only a timer, with no check at completion time, does not provide exclusivity: a worker that stalls past its lease, is reclaimed, and then wakes up would overwrite the reclaiming worker's result, and the two workers would have held the job at once with nothing to show it. The stale worker's late write is the observable symptom, so refusing it and counting the refusal is what turns the invariant into evidence. `JOB-006` is its acceptance scenario.

### Missing, null, unknown, and not-applicable values

- **Missing:** a job without `handler` or `max_attempts` is rejected at creation as `CONFIGURATION_INVALID`. It is never persisted in a partial state.
- **Explicit null:** `payload` may be JSON `null`. The platform passes it through; interpreting it is the handler's business.
- **Unknown:** a `handler` name that is not registered fails the job as `HANDLER_UNKNOWN` on its first claim. It is not retried.
- **Not applicable:** `lease_owner`, `lease_expires_at`, and `terminal_reason` are null outside the states where the table above assigns them meaning.

### Ordering, time, and identity

- **Identity boundary:** `job.id` identifies the unit of work. `effect_key` identifies the durable effect. They are deliberately separate — a retried job keeps its `id` and reproduces the same `effect_key`, which is what makes I1 testable.
- **Timestamp semantics and timezone:** all timestamps are `timestamptz`, generated by the database (`now()`), and compared in UTC. Application-generated timestamps are not used for lease or availability decisions, so that a clock skew between worker processes cannot violate I2.
- **Ordering guarantee:** none across jobs. Claim order is unspecified; `SKIP LOCKED` deliberately permits reordering under contention. Within one job, `attempt_no` is strictly increasing.
- **Duplicate or replay meaning:** delivery is at-least-once. A duplicate execution is expected behavior, not an error. It is contained by I1, not prevented.

## Expected behavior

- **Valid input behavior:** a job with a registered handler and a due `available_at` is claimed by exactly one worker, executed once per attempt, and reaches a terminal state within `max_attempts`.
- **Idempotency behavior:** the platform provides at-least-once execution and an idempotent effect table. A handler is responsible for computing a stable `effect_key`; the platform is responsible for making a repeat insert a no-op. Neither alone is sufficient, and the contract records both halves so that a P0-B failure can be attributed to the right one.
- **Retry behavior:** retryable failures are rescheduled with bounded exponential backoff plus jitter, subject to `max_attempts`. Backoff parameters are configuration, not contract.
- **Durable effects:** exactly one — a `platform_effect` row. No other table is written by a handler in P0-A.
- **Observability requirements:** every state transition emits one structured log event carrying `correlation_id`, `job_id`, `handler`, `attempt_no`, the from- and to-states, and a timestamp. Counters exist for transitions by target state, claim conflicts, duplicate effect insertions suppressed, attempts abandoned, and completions rejected by the fencing rule. Durations are recorded for attempt execution and for lease recovery latency.

## Error behavior

| Error code or class | Trigger | Retryable | Durable state | Safe operator action |
|---|---|---|---|---|
| `PLATFORM_TRANSIENT` | Synthetic retryable failure injector | Yes | Attempt closed `RETRYABLE_FAILURE`; job `PENDING` or `FAILED` on exhaustion | Wait, or safe retry after exhaustion |
| `PLATFORM_PERMANENT` | Synthetic permanent failure injector | No | Attempt closed `PERMANENT_FAILURE`; job `FAILED` | Inspect, then safe retry only after the cause is understood |
| `HANDLER_UNKNOWN` | `handler` is not registered | No | Job `FAILED` on first claim | Register the handler, then safe retry |
| `LEASE_ABANDONED` | Lease expired while `RUNNING` | Yes | Previous attempt closed `ABANDONED`; job reclaimable | None; recovery is automatic |
| `CONFIGURATION_INVALID` | Invalid platform configuration, or a job rejected at creation | No | Process refuses to start, or the job is not persisted | Correct the configuration |

`error_summary` is the operator-visible string and is redacted. `error_detail` is protected debug detail: it is never included in an API response by default, and it is emitted to logs only at the debug level. An unstructured exception message is never the only external error contract — `error_class` is always set.

## Provenance and security

- **Required provenance fields:** `correlation_id` on every job, attempt, log event, and API response. This is platform provenance, not source provenance; source and Raw provenance are P0-B concerns.
- **Credential handling:** P0-A resolves no credential. The platform verifies only that the configured secret-store location lies outside the repository working tree, and refuses to start otherwise. `credential_ref` semantics belong to P0-B under [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md).
- **Redacted or prohibited fields:** any mapping key matching, case-insensitively, `password`, `token`, `secret`, `authorization`, `cookie`, `api_key`, `apikey`, or `credential` is replaced with a redaction marker in structured logs, error summaries, and API responses. `error_detail` is additionally protected as described above.
- **Data class constraints:** every value handled in P0-A is synthetic and `public`. No fixture, log, or screenshot may contain a real credential.
- **Outbound or source policy constraints:** P0-A makes no outbound request. The database is reachable only over a local Unix socket and has no TCP listener at all. Operator surfaces bind to loopback, and a non-loopback bind is refused as `CONFIGURATION_INVALID` rather than merely being off by default — the charter asks for a default, and P0-A has no reason to need the weaker form. `SEC-002` is the acceptance scenario.

## Examples

### Valid

A job with `handler = "succeed"`, `max_attempts = 3`, and an opaque payload: claimed once, one attempt closed `SUCCEEDED`, one `platform_effect` row, job `SUCCEEDED`. Executable form: `tests/acceptance/JOB-001-successful-execution.md`.

### Invalid

- Missing `handler` at creation → `CONFIGURATION_INVALID`, nothing persisted.
- `handler = "not-registered"` → `HANDLER_UNKNOWN`, job `FAILED` after one attempt, no `platform_effect` row.
- Two workers claiming one due job → exactly one attempt opens; the other observes no claimable row. Executable form: `tests/acceptance/JOB-007-parallel-claim-exclusivity.md`.
- Duplicate delivery of a job whose handler already applied its effect → second attempt's insert is suppressed, `platform_effect` still has one row. Executable form: `tests/acceptance/JOB-008-duplicate-delivery-idempotency.md`.

## Acceptance criteria

- **Related acceptance scenario IDs:** `JOB-001` … `JOB-008`, `SEC-001` … `SEC-004`, and the `OPS` scenarios written in S5.
- **Required deterministic result:** I1 through I5 hold across every scenario, on repeated runs, including under injected interruption and duplicate delivery.
- **Required failure evidence:** each row of the error table above is reached by at least one scenario, and the resulting durable state and operator action are observed rather than asserted from the code.

## Known limitations and unresolved semantics

- A lease-expiry reclaim spends an attempt even when the worker crash was unrelated to the job. Accepted for P0-A; revisit if P0-B shows it masks real failures.
- The at-least-once boundary is tested only against a single-table effect. Whether it holds for a multi-step durable effect is exactly OQ-006 H1 and is untestable until P0-B.
- No fairness or priority semantics. A starved job is possible under sustained contention and is not detected.
- Single-host execution only. Nothing here has been tested across machines or against clock skew larger than the lease duration.
- Backoff parameters are configuration rather than contract, so two deployments can differ in observable retry timing.

## Change record

| Version | Date | Change | Evidence or decision |
|---|---|---|---|
| `0.1` | 2026-08-17 | Initial experimental version, written before implementation | [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md), [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) |
