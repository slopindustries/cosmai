# OQ-006 — Job Concurrency and Recovery

- Status: `OPEN`
- Priority: P0 — required evidence for the P1 contract
- Owner: Project team
- Blocks: worker, transaction, retry, and scale-out contract
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

Can a PostgreSQL-backed job model provide correct P0 concurrency and recovery for independently scalable collector and normalizer workers?

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

- Run at least two workers against a shared queue.
- Terminate a worker after claim and after a durable side effect.
- Deliver the same job more than once.
- Exhaust retryable work into a final failure state.
- Recover an expired lease.

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
