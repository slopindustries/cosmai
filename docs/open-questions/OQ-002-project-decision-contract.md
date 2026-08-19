# OQ-002 — Final Project Decision Contract

- Status: `RESOLVED`
- Priority: P0-B; resolved by owner direction before source sampling and validated during B1/B2
- Owner: Project team
- Blocks: no current P0 item; long-term learned targets and organization-wide workflows remain outside this resolution
- Related experiments: P0-B source and integrated-flow experiments remain to be executed
- Resolution Decision Packet: [DP-011](../decisions/DP-011-p0b-product-and-delivery-scope.md)

## Question

Which user or R&D decision should Cosmai improve, and what evidence must the system provide for that decision?

## Why this required a decision

“Understanding trends” did not identify the decision consumer, action, time horizon, acceptable uncertainty, evidence standard, or cost of false positive and false negative results. DP-011 fixes a reversible P0 answer without claiming that the final organization-wide workflow is settled.

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

P0-A does not explore or resolve this question. P0-B does not require a final product answer before source sampling, but it does require an accepted provisional P0 consumer, output unit, evidence requirement, and human-review boundary before the concrete normalizer is designed against an otherwise undefined use.

## Resolution

`[결정]` Resolved for P0 by [DP-011](../decisions/DP-011-p0b-product-and-delivery-scope.md): a cosmetics R&D or product-planning reviewer receives an evidence-backed opportunity card for a canonical sunscreen or toner topic and chooses `REVIEW_NOW`, `WATCH`, `EXPAND_EVIDENCE`, or `REJECT`.

The card carries deterministic trend metrics, uncertainty, provenance, `evidence_id` values, and original URLs. Cosmai abstains when the evidence gate fails. It does not approve a formula, make a safety or efficacy claim, predict sales, or replace human review.

Long-term consumers, learned prediction targets, and organization-wide workflows remain outside this resolved P0 scope and require a later decision.

The owner decision is a reversible `ACCEPTED_FOR_POC` default. B1/B2 must still apply it to representative source records; failure of H1 or H2 reopens this question rather than changing the evidence-card definition silently.
