# OQ-003 — Normalization Protocol and Schema 0.x

- Status: `OPEN`
- Priority: P0 after representative source samples
- Owner: Project team
- Blocks: normalizer implementation and normalization acceptance tests
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

What minimal provider protocol and provisional normalized schema can process both selected sources without presenting guesses as source facts?

## Why this cannot be decided yet

Representative records, source-specific ambiguity, the bounded product decision, and actual cross-source field coverage have not yet been measured.

## Scope

### Included

- Experimental Schema 0.x, provider input/output/error behavior, rule baseline, version and lineage fields, ambiguity, and human-review metadata.

### Excluded

- Schema 1.0, final ontology, universal normalization maturity levels, ML/LLM provider selection, and production quality targets.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Structural normalization and a small deterministic rule layer are enough to test the P0 pipeline. | The minimum P0 output cannot be validated across both selected sources without an unplanned probabilistic or human-only interpretation step. |
| H2: Source-specific fields can remain in Raw while Schema 0.x contains only provisional cross-source meaning. | A field required by the bounded P0 decision or lineage flow cannot be represented without promoting incompatible source-specific semantics into the common schema. |
| H3: Method, depth, quality, and human-review status are independent dimensions. | Representative annotations show that two or more dimensions cannot vary independently or produce internally consistent metadata. |
| H4: The proposed D0–D4 linear model will require modification. | Every reviewed transformation can be ordered consistently on one axis without incomparable capabilities, skipped stages, or regressions. |

## Alternatives

- Structural-only common output with source-specific meaning retained in Raw.
- A small cross-source Schema 0.x plus source-specific extensions.
- Separate source schemas with a later projection boundary.

## Minimum experiment

- Manually inspect and annotate 50–100 representative records across both sources.
- Compare at least two small schema candidates.
- Implement one deterministic `rule-baseline@0.1` against a sealed snapshot.
- Repeat the same run and compare outputs byte-for-byte after canonical serialization.
- Record ambiguous, unrepresentable, missing, and review-required cases.

## Evidence

- Field coverage and null rate by source.
- Parse and validation failures.
- Determinism result.
- Raw-to-output lineage completeness.
- Ambiguity and human-review rates.
- Error taxonomy and examples rejected from the common schema.

## Exit condition

The team accepts a versioned experimental Schema 0.x, provider input/output/error contract, rule baseline behavior, and explicit list of semantics that remain unresolved. This does not create Schema 1.0.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution links the accepted experimental contract, fixture coverage, deterministic measurements, Decision Packet, and unresolved semantics.
