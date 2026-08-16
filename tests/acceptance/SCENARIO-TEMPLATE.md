# XXX-000 — Scenario title

- Status: `DRAFT | ACCEPTED_FOR_POC | CONTRACTED | SUPERSEDED`
- Family: `ACQ | RAW | JOB | SNP | NRM | OPS | SEC`
- Related contract and version:
- Related Open Question or Decision Packet:
- Input fixture and metadata:
- Owner:

## Intent

State the behavior or failure boundary this scenario protects. Do not describe implementation structure unless it is part of the contract.

## Preconditions

- Initial durable state:
- Worker or service state:
- Configuration with secrets excluded:
- Time, retry, and concurrency assumptions:

## Action

1.
2.
3.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
|  |  |  |  |  |

## Expected durable effects

- Created or changed records:
- Effects that must not occur:
- Idempotency or duplicate expectation:
- Lineage expectation:

## Expected telemetry

- Correlation identifiers:
- Structured event or log fields:
- Metrics and units:
- Protected debug behavior:

## Failure classification and recovery

- Expected error class and code:
- Retryable:
- Operator-visible explanation:
- Safe retry or final action:

## Verification

- Execution command or procedure:
- Assertions:
- Output and evidence location:
- Environment and versions:

## Result

- Last executed at:
- `PASS | FAIL | NOT RUN`
- Linked experiment measurement:
- Known limitation:
