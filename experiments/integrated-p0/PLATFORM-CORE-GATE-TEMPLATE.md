# P0-A Platform Core Completion Gate

- Status: `DRAFT | GO | CONDITIONAL GO | NO-GO | REOPENED`
- Governing decision: [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md)
- Integrated experiment:
- Reviewed code revision:
- Review date and timezone:
- Reviewers:

## Gate question

Is the source- and normalization-independent platform core executable, tested, and bounded enough to begin P0-B without claiming that source, acquisition, Raw, snapshot, or normalization behavior has been proved?

## Platform implementation and verification

| Platform surface | Contract/version | Required scenarios | Result | Evidence | Remaining limitation |
|---|---|---|---|---|---|
| PostgreSQL connection, migration, and transaction foundations |  |  | `PASS | FAIL | NOT RUN` |  |  |
| Handler-neutral job claim, lease, retry, and recovery |  |  | `PASS | FAIL | NOT RUN` |  |  |
| API and worker lifecycle |  |  | `PASS | FAIL | NOT RUN` |  |  |
| Platform dashboard, logs, metrics, correlation, and safe retry |  |  | `PASS | FAIL | NOT RUN` |  |  |
| Redaction, secret-store guard, and loopback boundary |  |  | `PASS | FAIL | NOT RUN` |  |  |

## Synthetic-handler coverage

| Platform behavior | Represented? | Evidence | Limitation carried into P0-B |
|---|---|---|---|
| Successful execution | `YES | PARTIAL | NO` |  |  |
| Retryable and permanent failure | `YES | PARTIAL | NO` |  |  |
| Duplicate execution | `YES | PARTIAL | NO` |  |  |
| Interruption and lease expiry | `YES | PARTIAL | NO` |  |  |
| Invalid platform configuration | `YES | PARTIAL | NO` |  |  |

Synthetic handlers must not imitate a collector, dataset importer, Raw payload, snapshot producer, or normalizer.

## Deferred-domain inventory

Confirm that each item is absent from P0-A implementation and acceptance claims.

- [ ] REST and dataset candidate exploration or selection
- [ ] Source rights decision, source fixture, or outbound request
- [ ] Source registration semantics or concrete host policy
- [ ] Collector or dataset-importer interface, test double, or implementation
- [ ] Raw response, Raw record, observation identity, or duplicate semantics
- [ ] Snapshot, manifest, or Raw-to-result lineage
- [ ] Normalized Schema 0.x, provider protocol, test double, or rules
- [ ] Acquisition- or normalization-specific dashboard behavior
- [ ] `ACQ`, `RAW`, `SNP`, or `NRM` pass claim

## P0-B entry readiness

- Deferred Open Questions:
- Platform assumptions P0-B must challenge:
- Known extension points and why each is source-neutral:
- P0-B experiment owner:
- P0-B proposed timebox:
- External-input safety review required before first probe: `YES`

## Decision

- Outcome: `GO | CONDITIONAL GO | NO-GO`
- `[결정]`:
- Accepted conditions:
- Blocking failures:
- Failure classification:
- P0-A work package to reopen for each blocker:

`GO` requires every mandatory platform scenario to pass. `CONDITIONAL GO` may accept only bounded limitations that do not make P0-B evidence uninterpretable. `NO-GO` returns work to a named P0-A work package.

## Reopen rule

If P0-B shows that a claimed P0-A boundary must be materially replaced:

1. classify the failure;
2. append the observation and affected assumption;
3. set this gate to `REOPENED`;
4. return to the named P0-A work package;
5. re-review this gate before relying on the revised platform claim.
