# OQ-001 — Source Capability

- Status: `OPEN`
- Priority: P0 — first exploration
- Owner: Project team
- Blocks: source contract, representative fixtures, P0 ingestion
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

Which one REST API source and which one existing dataset can lawfully and usefully test CosmaSignal's first integrated ingestion flow?

## Why this cannot be decided yet

No provider has been tested for access, rights, authentication, pagination, rate limiting, identifiers, update semantics, schema drift, completeness, or representative content.

## Scope

### Included

- A bounded M1 candidate set containing REST API and existing dataset options.
- Rights, safe handling, retrieval, identity, time, replay, data profile, and P0 usefulness.

### Excluded

- Final production source portfolio, broad market coverage, production SLA, and long-term provider procurement.

## Hypotheses and falsification

These hypotheses apply only to the candidate set recorded in the M1 source-selection experiment. They do not claim that every possible external source has been searched.

| Hypothesis | Falsification condition |
|---|---|
| H1: At least one evaluated REST source can support repeat collection evidence. | Every evaluated REST candidate fails a hard gate, or none provides a usable observation identity and repeat/retrieval procedure within the M1 timebox. |
| H2: At least one evaluated dataset can test import and normalization behavior. | Every evaluated dataset fails a hard gate, or none contains a lawfully usable, replayable sample with enough structural variation to exercise missing, invalid, duplicate, or changed input. |
| H3: A small capability profile is sufficient for the first REST source. | A consistent source recommendation cannot be made without undocumented source-specific knowledge or a material behavior that the profile cannot represent. |

## Alternatives

- Select one REST and one dataset candidate with all hard gates passed.
- Accept a candidate with bounded non-gate operating limitations through `CONDITIONAL GO`.
- Record `NO-GO` for one or both modes and expand or change the bounded candidate set.

## Minimum experiment

### REST

- Capture at least three pages or 100 representative records, whichever occurs first.
- Repeat collection after a meaningful interval.
- Exercise one retryable failure or provider limit.
- Record authentication, pagination, rate, response envelope, identifiers, timestamps, corrections, and deletion behavior.

### Dataset

- Inspect schema and usage rights before import.
- Import a representative subset with at least one invalid or missing value case.
- Repeat identical import and import one intentionally changed version.
- Record file format, encoding, row identity, timestamps, duplicates, missingness, and distribution constraints.

## Evidence

- One completed [Source Capability Profile](../../experiments/source-probes/SOURCE-CAPABILITY-TEMPLATE.md) per candidate.
- An aggregate [Source Selection Matrix](../../experiments/source-probes/SOURCE-SELECTION-MATRIX.md).
- Retrieval instructions with secrets excluded.
- Small redistributable fixtures or hashes plus retrieval instructions.
- Capture timestamps and relevant HTTP headers with credentials redacted.
- Field profile, null counts, duplicate counts, and sample payload sizes.

## Exit condition

Each acquisition mode has one explicit `GO`, `CONDITIONAL GO`, or `NO-GO` decision, and the selected samples can be replayed without relying on undocumented operator knowledge.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution requires a Decision Packet linked to the selected profiles, matrix, fixtures or hashes, and remaining M2 conditions.
