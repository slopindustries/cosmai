# SRC-XXX — Source Capability Profile

Copy this file into the candidate probe directory. Complete only the section for its acquisition mode, and mark untested behavior as `UNKNOWN` rather than guessing.

## Identity

- Candidate ID: `SRC-XXX`
- Acquisition mode: `REST_API | DATASET_IMPORT`
- Provider or producer:
- Distributor, if different:
- Endpoint or dataset page:
- Content channel or domain:
- Related experiment:
- Profile captured at: ISO 8601 timestamp with timezone

## Rights and processing basis

- Terms or license URL and version/date:
- Permitted experimental use:
- Redistribution permitted: `YES | NO | CONDITIONAL | UNKNOWN`
- Agent processing permitted: `YES | NO | CONDITIONAL | UNKNOWN`
- Attribution or deletion obligation:
- Evidence and unresolved interpretation:

Do not infer permission from technical accessibility. `UNKNOWN` cannot pass the rights gate.

## Hard gates

| Gate | Result | Evidence or blocking reason |
|---|---|---|
| G1 — Access and rights permit the recorded P0 experiment. | `PASS | FAIL | UNKNOWN` | |
| G2 — Data can be handled without exposing prohibited secrets, personal data, or restricted content. | `PASS | FAIL | UNKNOWN` | |
| G3 — A representative sample can be retrieved or reconstructed with recorded identity, time, and hashes. | `PASS | FAIL | UNKNOWN` | |
| G4 — The sample exercises at least one named P0 architecture question. | `PASS | FAIL | UNKNOWN` | |
| G5 — Required access, volume, rate, and cost fit the P0-B timebox. | `PASS | FAIL | UNKNOWN` | |

Any `FAIL` produces `NO-GO`. `UNKNOWN` means the candidate remains `PENDING`; if it is unresolved at the P0-B source-selection review, the candidate is `NO-GO`. `CONDITIONAL GO` still requires every hard gate to pass and may carry only bounded, non-gate operating limitations accepted by a Decision Packet.

## REST API capability

- Authentication shape with secret excluded:
- Allowed HTTPS hosts:
- Endpoint and method:
- Pagination or cursor behavior:
- Rate and quota behavior:
- Retry and `Retry-After` behavior:
- Response envelope:
- Provider record identifier:
- Event, publication, and update timestamps:
- Correction and deletion behavior:
- Redirect behavior:
- Observed schema or response drift:

## Dataset capability

- File format and compression:
- Dataset version or release date:
- Encoding and delimiter:
- Row identity candidate:
- Event, publication, and update timestamps:
- Duplicate behavior:
- Missing and invalid values:
- File and representative subset sizes:
- Version, correction, and deletion behavior:

## Measured data profile

Record each statement using the project evidence labels.

- Sample identity and size:
- Field profile:
- Null counts or rates:
- Duplicate counts or rates:
- Invalid record counts or rates:
- Payload or row size distribution:
- Time coverage:
- Observed failures and limits:

## Reproduction and artifacts

- Reproduction command:
- Environment and versions:
- Retrieval procedure:
- Original content hash and algorithm:
- Redistributable fixture or local-only metadata location:
- Redaction or transformation:

## Recommendation

- Outcome: `GO | CONDITIONAL GO | NO-GO`
- Conditions or blocking gates:
- P0 questions this candidate can test:
- Known representativeness limits:
- Proposed next action:

`GO` requires every hard gate to pass. `CONDITIONAL GO` also requires every hard gate to pass, but records explicit bounded operating conditions. It cannot bypass an unknown or failed gate.
