# OQ-002 — Final Project Decision Contract

- Status: `OPEN`
- Priority: P0, but does not block initial source sampling
- Owner: Project team
- Blocks: `Normalized Schema 1.0`, final quality metrics, final product workflows
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

Which user or R&D decision should CosmaSignal improve, and what evidence must the system provide for that decision?

## Why this cannot be decided yet

“Understanding trends” does not identify the decision consumer, action, time horizon, acceptable uncertainty, evidence standard, or cost of false positive and false negative results.

## Scope

### Included

- One bounded initial consumer, trigger, decision, output unit, evidence requirement, uncertainty representation, and review action.

### Excluded

- Every future persona, forecasting, autonomous decisions, final ontology, and organization-wide R&D workflow redesign.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: A traceable R&D review candidate is a useful provisional decision unit. | For every named consumer scenario, the candidate does not lead to a specific review action, or the evidence required for the action cannot be traced to the selected source records. |
| H2: One bounded decision contract can guide Schema 1.0 and final quality criteria. | The selected consumer scenarios require materially incompatible output units, evidence standards, or error tradeoffs that cannot be represented as one scoped contract. |

These are working hypotheses, not a final product contract.

## Alternatives

- Signal-level record for review.
- Canonical topic or entity-centered review unit.
- Evidence-backed opportunity card.
- A different decision unit discovered by manual scenario application.

## Minimum exploration

- Write two or three concrete operator or R&D questions.
- Apply each question manually to representative records from OQ-001.
- Identify the minimum evidence, normalized fields, uncertainty, and review action required.
- Compare whether a signal-level record, canonical topic, opportunity card, or another output is the useful decision unit.

## Evidence

- Named decision consumer and decision.
- Input evidence and expected output examples.
- False-positive and false-negative consequences.
- Human-review boundary.
- Success and non-goal statements.

## Exit condition

A Project Decision Contract states: consumer, trigger, decision, output unit, evidence requirements, uncertainty representation, review responsibility, success criteria, and explicit non-goals.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. The accepted Project Decision Contract and its Decision Packet close this question while preserving unresolved future consumers and workflows.
