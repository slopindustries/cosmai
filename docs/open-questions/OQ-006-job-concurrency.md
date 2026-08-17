# OQ-006 — Job Concurrency and Recovery

- Status: `OPEN`
- Priority: P0-A platform claims and P0-B domain effects
- Owner: Project team
- Blocks: worker, transaction, retry, and scale-out contract
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — `RUNNING`, covers the P0-A minimum experiment below. H1 and H2 are in scope at the platform level; H3 is not testable without the domain and stays with P0-B.
- Resolution Decision Packet: not created

## Question

Can a PostgreSQL-backed platform job model provide correct generic concurrency and recovery, and does that model remain correct when P0-B introduces collector, importer, and normalizer effects?

## Why this cannot be decided yet

No implementation has yet injected concurrent claims, duplicate delivery, interruption around durable effects, lease expiry, retry exhaustion, or unknown outcomes.

## Scope

### Included

- PostgreSQL-backed P0 claims, leases, attempts, retry scheduling, idempotent durable effects, terminal states, and collector/normalizer recovery differences.

### Excluded

- Production throughput targets, distributed brokers, multi-region consensus, exactly-once claims, and final scale infrastructure.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: At-least-once delivery plus idempotent effects can contain duplicate execution in P0. | Injected duplicate delivery or an unknown outcome produces an uncontrolled durable duplicate effect that the recorded idempotency boundary cannot detect or recover. |
| H2: `FOR UPDATE SKIP LOCKED`, attempts, leases, and `available_at` are sufficient for P0 claims and recovery. | A tested interruption leaves work permanently stranded, permits conflicting active ownership, or reaches a state with no documented recovery or finalization path. |
| H3: Collector and normalizer jobs require separate state and retry policy even on shared infrastructure. | The same tested state transitions, retry classification, lease behavior, and terminal states satisfy both domains without source- or provider-specific exceptions. |

## Alternatives

- PostgreSQL job tables with at-least-once execution and idempotent effects.
- A dedicated message broker introduced only if P0 falsifies the database-backed model.
- Synchronous orchestration, retained as a comparison but expected to fail independent recovery requirements.

## Minimum experiment

### P0-A

- Implement the handler-neutral platform job core and run at least two workers against a shared queue using synthetic generic handlers that do not imitate collection or normalization.
- Terminate a worker after claim and after a durable side effect.
- Deliver the same job more than once.
- Exhaust retryable work into a final failure state.
- Recover an expired lease.

### P0-B

- Repeat the relevant claim, interruption, duplicate, and recovery scenarios with the concrete collector, importer, and normalizer.
- Record where source or rule effects differ from the platform evidence and whether the P0-A gate must be reopened.

## Evidence

- Claim exclusivity and lease behavior.
- Duplicate side effects and idempotency results.
- Recovery time and state transitions.
- Transaction boundaries and unknown-outcome cases.
- Collector-versus-normalizer retry differences.

## Exit condition

Every injected failure ends in a documented recoverable or final state, duplicate delivery does not produce uncontrolled effects, and the team can specify the P1 job state machine and transaction boundaries.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution links failure-injection measurements, accepted state/error contracts, Decision Packet, and remaining scale limits.
