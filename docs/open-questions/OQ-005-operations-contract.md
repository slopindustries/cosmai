# OQ-005 — Dashboard and Operations Contract

- Status: `OPEN`
- Priority: P0-A platform evidence and P0-B domain evidence
- Owner: Project team
- Blocks: dashboard acceptance contract
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

What must an operator see and do in order to create, observe, diagnose, and recover collection and normalization work without direct database access?

## Why this cannot be decided yet

No complete P0 flow or injected failure has yet been operated through the dashboard, so the minimum navigation objects, telemetry, and recovery actions remain hypotheses.

## Scope

### Included

- Local P0 operator actions, navigation objects, correlated telemetry, safe retry, failure explanation, redaction, and debugging evidence.

### Excluded

- Polished UX, public deployment, production IAM, multi-tenant authorization, and a production observability product stack.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Sources, imports, jobs, snapshots, normalization runs, results, logs, and metrics form a sufficient P0 navigation model. | A required operator scenario cannot be completed without direct database inspection or an additional first-class object not represented by the model. |
| H2: Correlated structured events plus a small metrics set are sufficient for P0 diagnosis. | An injected failure cannot be classified and safely retried from the dashboard and documented APIs using that evidence. |

## Safety constraint

Debug details require redaction and an explicit local access boundary even if no leak is observed during the experiment. This is governed by the [P0 Security Baseline](../conventions/p0-security.md), not treated as a hypothesis that can be waived by a favorable sample.

## Alternatives

- Documented API and structured event view with minimal dashboard controls.
- Dashboard-centered control and diagnosis with API parity.
- Direct database inspection, which is retained only as a rejected fallback for required operator scenarios.

## Minimum experiment

### P0-A

- Implement the source-neutral dashboard foundation.
- Use handler-neutral synthetic work to inspect platform health, generic job state, correlated logs and metrics, retryable and permanent execution failure, lease expiry, and safe retry.
- Do not create source, import, Raw, snapshot, normalization-run, or result navigation objects.

### P0-B

- Add the domain navigation objects and actions justified by the selected source and accepted experimental contracts.
- Operate successful collection/import/normalization work and diagnose retryable, permanent, partial-import, normalization, and snapshot-integrity failures.
- Record any platform diagnostic gap that requires the P0-A gate to be reopened.

## Evidence

- Whether the operator can answer what ran, with which input, when, by which version, and why it failed.
- Time and number of steps needed to find and retry a failure.
- Missing identifiers, logs, metrics, and state transitions.
- Debug information that risks exposing credentials or sensitive source data.

## Exit condition

The accepted operator scenarios can be completed from the dashboard and documented APIs without direct database inspection, and the minimum telemetry contract is explicit.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution links accepted `OPS` and `SEC` scenarios, telemetry fields, operator actions, Decision Packet, and known diagnostic gaps.
