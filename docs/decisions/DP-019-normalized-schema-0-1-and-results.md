# DP-019 — Normalized Schema 0.1, the result table, and what a snapshot selects

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project team
- Narrows: [OQ-003](../open-questions/OQ-003-normalization-protocol.md) and [OQ-004](../open-questions/OQ-004-snapshot-boundary.md). Neither is closed — see "What stays open".
- Records a provisional answer to: [OQ-002](../open-questions/OQ-002-project-decision-contract.md), as `project-state.md` §2 requires before a concrete normalizer exists
- Affected contracts: `NormalizedResult.body`, a new `normalized_result` table, `snapshot.selection`
- Affected acceptance tests: the normalization scenarios, and the determinism claim

## Decision question

`addon_api` already fixes the normalizer's protocol — `NormalizeContext`, `SnapshotItem`,
`NormalizedResult`, `NormalizeOutcome`. Three things it does not fix stop any normalizer
from running: what a result **means**, where a result is **stored**, and what a snapshot
**selects**. `addon_host._UNBOUND_KINDS` refuses every normalizer today and says so in those
words.

## The provisional decision use

`[결정]` **Which beauty topics are being written about, when, and by whom — over a stated
window and a stated query — so that a reader can decide which of them is worth investigating
further.**

`[추론]` This is deliberately the *weakest* useful decision. It is provisional in the sense
`project-state.md` §2 means: it is enough to make a concrete normalizer definable, and it
does not claim to be the product's decision. OQ-002 stays `OPEN`. What it fixes is only that
Schema 0.1 must carry a document's identity, its time, its author, and its text — because a
reader answering the question above needs those four and nothing else has been shown to be
needed.

## Decision

**D1 — `Normalized Schema 0.1` is a document record, and it is structural.** One snapshot
item becomes at most one result whose `body` is:

| Field | Meaning | Absent when |
|---|---|---|
| `schema_version` | Always `"0.1"` | never |
| `record_type` | Always `"document"` in 0.1 | never |
| `external_id` | The source's own identity for the document | never |
| `url` | Where it can be read | never |
| `title` | Plain text, source markup removed | never (empty string if the source gave none) |
| `excerpt` | Plain text, source markup removed | never (empty string) |
| `published_at` | ISO-8601 date, or `null` | the source gave no parseable date |
| `author` | Display name, or `null` | the source gave none |
| `language` | BCP-47 tag stated by the source's configuration, never inferred | never |

`[결정]` **No interpretation.** No sentiment, no topic, no ingredient extraction, no
scoring. `project-state.md` §4 requires at least one deterministic rule-based normalizer and
OQ-003 H1 asks whether structural normalization plus a small rule layer is enough to test
the pipeline; a schema carrying an inference would answer a *product* question by
implication while claiming to answer a plumbing one. Markup removal and date parsing are the
only two rules, and both are reversible against the preserved Raw.

**D2 — `language` is configuration, not detection.** A detected language is a guess
presented in the same field as facts. The source row states it; `[가설]` that this is
adequate is falsified by the first source carrying more than one language.

**D3 — Results are versioned rows that coexist.** `normalized_result` is append-only per
`(snapshot_id, addon_id, addon_version, output_contract_version, source_item_key)`.
`project-state.md` §4: normalized results are versioned and coexist, not updated in place.
Two normalizer versions over one snapshot therefore both persist and can be compared, which
is the whole point of the version axis DP-008 D9 named.

**D4 — Determinism is enforced, not requested.** `NormalizeContext`'s docstring already
requires byte-identical output from one snapshot. The host canonicalizes `body` on the way
in (sorted keys, no whitespace) and stores a digest of it, so two runs of one add-on over one
snapshot produce equal digests or a test says they did not.

**D5 — A snapshot selects every `raw_item` of one source, ordered by `(item_key)`.**
`[결정]` The narrowest selection that can exist, chosen because OQ-004 owns the general
question and a richer selection would answer it by implication. `item_key` and not
`emitted_at` because the ordering must be a property of the data and not of when collection
happened — a re-collection that produced identical items must produce an identical snapshot.
Duplicate `item_key`s within a source collapse to the **latest** `emitted_at`, which is a
choice and not a fact: `raw_item` deliberately has no uniqueness constraint because duplicate
policy is an open question, and `snapshot_item` requires one row per key.

**D6 — Normalization is started by an operator-created job naming a `snapshot_id`.**
`project-state.md` §4: collection never triggers normalization. Sealing a snapshot and
running a normalizer over it are two operator acts, not one.

## What stays open

- **OQ-003 is not closed.** Its minimum experiment requires 50–100 annotated records across
  **both** sources and a comparison of two schema candidates. One source is selected and no
  capture of it exists yet. Schema 0.1 is written from the vendor's documented response
  shape, and `[가설]` that it survives contact with a real capture is exactly what the first
  authenticated run tests. H2 — that source-specific meaning can stay in Raw — is untested
  until the second source exists.
- **OQ-004 is not closed.** D5 fixes one selection; the question also asks what a snapshot's
  identity is across a change of storage backend, and nothing here addresses that.
- **OQ-002 stays `OPEN`.** The decision use above is provisional and is recorded so that the
  normalizer is definable, not so that the product is defined.

## Falsification

| Claim | Falsified by |
|---|---|
| D1 is enough to test the pipeline | A real capture whose useful content cannot be placed in these nine fields without loss a reader would notice |
| D2 — stated language is adequate | One source returning documents in more than one language |
| D5 — every item of one source, by `item_key` | A source whose useful snapshot is a time window or a subset, making "all of it" either too large or meaningless |
| D4 — determinism is achievable here | A rule whose output depends on locale, platform, or dictionary version |
