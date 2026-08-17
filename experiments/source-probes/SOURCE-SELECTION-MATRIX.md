# P0-B Source Selection Matrix

- Status: `PLANNED`
- Related Open Question: [OQ-001](../../docs/open-questions/OQ-001-source-capability.md)
- Related experiments:
- Last updated:

Use one row per completed Source Capability Profile. Preserve links to measurements instead of copying unsupported conclusions into the matrix.

## Candidate comparison

| Candidate | Mode | G1 Rights | G2 Safe handling | G3 Replayable sample | G4 P0 relevance | G5 Timebox | Key limitations | Recommendation | Profile |
|---|---|---|---|---|---|---|---|---|---|
| `SRC-XXX` | `REST_API` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | | `PENDING` | |
| `SRC-XXX` | `DATASET_IMPORT` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | | `PENDING` | |

## Decision rules

- `GO`: every hard gate is `PASS` and no unresolved limitation blocks its named P0 use.
- `CONDITIONAL GO`: every hard gate is `PASS`, but remaining non-gate operating limitations are bounded and explicitly accepted.
- `NO-GO`: at least one hard gate is `FAIL`, or any hard gate remains `UNKNOWN` at the P0-B source-selection review.
- A numeric score, popularity, or convenient API shape cannot override a hard-gate result.

## Selected pair

- REST candidate:
- Dataset candidate:
- Accepted conditions:
- Decision Packet:
- Fixture or retrieval identities:
- Remaining uncertainty carried into P0-B implementation and integration:
