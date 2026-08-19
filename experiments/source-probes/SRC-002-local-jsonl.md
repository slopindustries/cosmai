# SRC-002 — Locally authored JSONL — Source Capability Profile

⚠️ `[확인 사실]` **This is not an external dataset, and it must not be read as one.** B1 asks
for a dataset *candidate* — a real one, with rights, a producer, and a release. What is
recorded here is a file this project writes for itself.

`[결정]` The substitution was made deliberately on 2026-08-19 and accepted by the project
owner. What it buys and what it costs are stated below rather than left for a reader to
work out from the absence of a provider name.

## Identity

- Candidate ID: `SRC-002`
- Acquisition mode: `DATASET_IMPORT`
- Provider or producer: **this project** — the file is authored by the test that reads it
- Distributor, if different: none
- Endpoint or dataset page: none; a path under an operator-approved root
- Content channel or domain: one JSON object per line
- Related experiment: [EXP-003](../integrated-p0/EXP-003-capability-layer.md);
  [DP-024](../../docs/decisions/DP-024-local-input-registry.md)
- Profile captured at: 2026-08-19

## Rights and processing basis

- Terms or license URL and version/date: not applicable — the project authored the content
- Permitted experimental use: unrestricted
- Redistribution permitted: `YES`
- Agent processing permitted: `YES`
- Attribution or deletion obligation: none
- Evidence and unresolved interpretation: `[추론]` The rights gate passes **trivially**, and a
  trivial pass is not evidence that the rights machinery works. What tested that machinery was
  SRC-001, where the answer was `NO` for redistribution and the pipeline had to hold that.

## Hard gates

| Gate | Result | Evidence or blocking reason |
|---|---|---|
| G1 — Access and rights permit the recorded P0 experiment. | `PASS` (trivially) | Self-authored |
| G2 — Data can be handled without exposing prohibited secrets, personal data, or restricted content. | `PASS` (trivially) | Synthetic rows carry none |
| G3 — A representative sample can be retrieved or reconstructed with recorded identity, time, and hashes. | `PASS` | The rows are written by `tests/test_importer_local_jsonl.py` and are reproduced exactly on every run |
| G4 — The sample exercises at least one named P0 architecture question. | `PASS` | It is the only thing that exercises `ImportContext` and DP-024's input registry at all, and the only route to B4's malformed-row scenarios |
| G5 — Required access, volume, rate, and cost fit the P0-B timebox. | `PASS` | No access, no quota, no cost |

## Dataset capability

- File format and compression: JSONL, uncompressed, UTF-8
- Dataset version or release date: none — written per test run
- Encoding and delimiter: UTF-8; one record per `\n`
- Row identity candidate: an operator-configured `key_field`, defaulting to nothing —
  `importer.local.jsonl` requires it and refuses a run without one
- Event, publication, and update timestamps: none
- Duplicate behavior: `[측정]` Not exercised. Duplicate `item_key`s within one file are not
  tested, and the platform's behaviour there is **`UNKNOWN`**.
- Missing and invalid values: `[측정]` Exercised in four shapes — malformed JSON, valid JSON
  that is not an object, a row missing the key field, and a file of nothing but bad rows.
  Each skips the bad row, keeps the good ones, and reports counts in the outcome.
- File and representative subset sizes: two to four rows per case; a few hundred bytes
- Version, correction, and deletion behavior: none

## Measured data profile

- Sample identity and size: `[측정]` 2–4 rows per test case
- Field profile: `id`, `title`, `body`
- Null counts or rates: `[측정]` Zero, by construction
- Duplicate counts or rates: `UNKNOWN` — not exercised
- Invalid record counts or rates: `[측정]` Deliberately varied per case, 0 to 100%
- Payload or row size distribution: `[측정]` Tens of bytes per row
- Time coverage: not applicable
- Observed failures and limits: `[측정]` A member escaping the approved root, a name the
  profile does not hold, and a source with no profile each fail the run permanently and
  persist nothing.

## Reproduction and artifacts

- Reproduction command: `./scripts/with-database.sh uv run pytest -q -k importer_local_jsonl`
- Environment and versions: Python 3.13, PostgreSQL 18, `uv`
- Retrieval procedure: none — the rows are authored in the test
- Original content hash and algorithm: not applicable; the content is deterministic source
- Redistributable fixture or local-only metadata location: the rows are in the test file
- Redaction or transformation: none needed

## Recommendation

- Outcome: **`CONDITIONAL GO`**, as a **structural stand-in and not as a dataset source**
- Conditions or blocking gates:
  - `[결정]` It may be cited as evidence that the **import path** works — `open_input`, the
    approved-input registry, containment, byte bounds, Raw and cursor through the completion
    transaction, and malformed-row handling.
  - `[결정]` It may **not** be cited as evidence about dataset *sources*. Nothing here
    measures a real producer's encoding, drift, correction, deletion, licensing, or size.
- P0 questions this candidate can test: DP-024's registry; B4's malformed and partially
  invalid dataset rows; the third of DP-008 D4's three capability sets.
- Known representativeness limits: `[추론]` The largest one is the rights gate. B1's dataset
  requirement exists partly to make the project confront a *second* rights situation, and a
  self-authored file confronts none. `OQ-001` therefore stays `OPEN` for the dataset half:
  **the import mechanism is tested and no dataset source has been selected.**
- Proposed next action: `[결정]` None in P0. Selecting a real dataset is P1 work, and
  [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md) may change what
  "importer" means before it happens.
