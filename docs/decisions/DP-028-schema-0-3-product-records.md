# DP-028 — The third record type, which DP-021 said would be what breaks it

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-20
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-20)` — the question was put with the
  alternative that changes no contract, and with what that alternative costs the gate
- Extends: [DP-021](DP-021-schema-0-2-trend-points.md) D1, whose own falsification table names
  this case; [DP-027](DP-027-dataset-standard-and-share-alike.md) D1, which selected the source
  without saying what its rows normalize into
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md) — its dataset
  half, [OQ-003](../open-questions/OQ-003-normalization-protocol.md)
- Affected contracts: [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md) §5
- Affected acceptance tests: none existing. The tests this decision requires are listed under
  *Required changes* and are written by [TASK-008](../agent-workflow/task-packets/TASK-008-obf-product-normalizer.md).

## Decision question

[DP-027](DP-027-dataset-standard-and-share-alike.md) D2 selected Open Beauty Facts as P0's
dataset source. The charter then asks that *"one REST source and one dataset complete the
end-to-end flow"*, and that flow ends in normalization.

`[확인 사실]` `PoC Contract 0.1` §5 contracts `record_type` ∈ {`document`, `trend_point`}. An
Open Beauty Facts row — a barcode, a name, a brand list, an ingredient text, revision
timestamps — is neither. So the dataset half cannot complete the flow without an answer to:
**what does a product row normalize into, and does the canonical schema change to hold it?**

Canonical schema is a consequential direction under `AGENTS.md`. This packet records the
owner's answer; it does not discover it.

## Candidates

1. **`Normalized Schema 0.3` adds a third union member, `product`.** A normalizer extracts
   structurally and judges nothing.
2. **Structural pass only.** Import, deduplicate, seal, verify — and record that no installed
   normalizer classifies this source, as a measurement rather than a defect.
3. **Map product rows onto `record_type: "document"`.**
4. **Defer the dataset's normalization half to P1** and close the charter's dataset line as an
   explicit blocker.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1 — A third member is additive: every 0.2 record is a valid 0.3 record and no stored row changes meaning | A reader that must know 0.3 exists in order to read a 0.2 `document` row correctly |
| H2 — A product row can be carried without deciding what the product *is* | The extraction cannot be written without a category, an ingredient taxonomy, or a brand identity — all of which DP-026 moved to P1 |
| H3 — The envelope survives a third shape | A field the envelope requires that a product row cannot supply, or a product field that has nowhere to go but the envelope |

## Evidence

`[확인 사실]` **DP-021 predicted this exact case and named it as its own refutation.** Its
falsification table reads: *"D1 — an envelope plus a type is enough | A source whose records
fit neither type and need a third."* `[추론]` The arrival of that source is therefore not a
surprise the schema failed to anticipate; it is the anticipated event, and H1 above is the
question of whether the union answers it by extension or by breaking.

`[측정]` **No installed normalizer can consume this source.** `normalizer.rule.baseline`
classifies on the vendor shapes of NAVER blog documents and DataLab trend points and returns
`skipped` for anything else, by construction and by its own test
(`TestTheSnapshotShapeAssumption`). `normalizer.naver.blog` and `normalizer.naver.trend` are
source-specific. `normalizer.conformance` states in its first line that it is the contract's
test double. `[추론]` Candidate 2 would therefore close the dataset half with either nothing
normalized or with the double, and a flow completed by a test double is the shape of evidence
this repository has already had to retract once.

`[측정]` **Fields are sparse, measured on real rows** —
[`SRC-003`](../../experiments/source-probes/SRC-003-open-beauty-facts.md), sample A of 36 rows
and a 100-row sunscreen sample:

| Field | Present |
|---|---|
| `code` | 36/36, and 100/100, 50/50 unique in every sample |
| `created_t`, `last_modified_t`, `rev` | 36/36 |
| `product_name` | 19/36; 82/100 in the sunscreen sample |
| `brands` | 25/36; 87/100 |
| `ingredients_text` | 12/36; 67/100 |
| `product_name_ko`, `ingredients_text_ko` | **0/36** |

`[추론]` A little over half the rows carry a name. So absence is the ordinary case here, not
the exception, and any body shape that makes a field required is a shape that would force a
normalizer to invent one. That is the failure mode `normalizer.rule.baseline` exists to
report, arriving through the schema instead.

`[확인 사실]` `code` survived real content change: 121/121 delta products resolved 23 hours
later with `created_t` identical, and the three whose `rev` and `last_modified_t` advanced kept
the same `code` (`SRC-003`). `[추론]` It is a usable `external_id`. It is the **source's**
identity for the row and not a canonical product identity, which is a different object that
DP-026 assigned to P1.

## Decision

`[결정]` **D1 — `Normalized Schema 0.3` is `0.2` plus a third union member, `product`.** The
envelope is unchanged — `schema_version`, `record_type`, `external_id`, `language`, provenance
— and `record_type` ∈ {`document`, `trend_point`, `product`}.

`[결정]` **D2 — 0.3 is additive, and no existing normalizer bumps its version.**
`normalizer.naver.blog` stays at `output_contract_version 0.1` and `normalizer.naver.trend` at
`0.2`, for DP-021 D5's reason: a new version number on identical bytes is the version axis
saying something false. `normalized_result` will hold `0.1`, `0.2`, and `0.3` rows side by
side, which is DP-019 D3's coexistence working rather than a migration waiting to happen. No
migration is required; `body` is already JSON and `schema_version` is already a string.

`[결정]` **D3 — the `product` body carries four fields and decides nothing.** The table
below fixes five rows because the first of them is the **envelope's** `external_id`, which
this decision also has to say where to get. `[확인 사실]` An earlier revision of this line
said "five fields" and read as though `external_id` were a body field; TASK-008's author
flagged the inconsistency from the packet that repeated it, on 2026-08-20. The table never
changed.

| Field | From | Null when |
|---|---|---|
| `external_id` (envelope) | `code` | never — a row without it is `skipped` and counted |
| `display_name` | `product_name`, verbatim | the source omits it or it is empty after trimming |
| `brands` | `brands_tags`, the source's own list, order preserved | never — an empty list when the source has none |
| `observed_at` | `last_modified_t`, Unix seconds → ISO-8601 UTC | the source omits it |
| `has_ingredients` | whether `ingredients_text` is present and non-empty | never |

`[결정]` **D4 — `has_ingredients` is a presence flag and not a quality judgment.** It records
that the source supplied ingredient text, not that the text is complete, correct, or usable.
`[확인 사실]` DP-027 D2 already recorded that no completeness threshold exists in this
repository to judge 26.5% against, and this field does not invent one.

`[결정]` **D5 — no category, no ingredient parsing, no brand identity, no canonical product.**
DP-026 D1 moved product, ingredient, and topic canonicalization to P1's first milestone, and
nothing here reaches into it. `brands` is the source's tag list carried forward, not a resolved
brand.

`[결정]` **D6 — what this decision is not evidence for.** DP-027 D2 recorded zero Korean
sunscreen and zero Korean toner rows in this source. A `product` record type does not change
that, and no gate claim may read "the dataset half is closed" as "the dataset is useful for the
product question".

## Rejected alternatives

- **Candidate 2, structural pass only.** Rejected: it closes the charter's dataset line with
  either an empty normalization step or the contract's own test double, and it leaves the
  charter's eighth architecture question — *which normalized fields survive contact with both
  real sources* — answered by one source. The saving is a few hours; the cost is the part of
  the gate a reader would most want to trust.
- **Candidate 3, map onto `document`.** Rejected: a product is not a document, and `document`'s
  body is built around authored text with a publication time. Reusing it would make the union
  discriminate on a type that no longer means anything, and would hide the very event DP-021
  asked to be told about.
- **Candidate 4, defer to P1.** Rejected by the owner on 2026-08-20 after it was put as the
  alternative. Recorded as available and not taken; it remains the fallback if TASK-007 or
  TASK-008 cannot produce a real run before the 08-26 freeze.

## Tradeoffs and risks

- Benefits: the charter's dataset half closes on a real external source with real normalization;
  the union is tested by extension rather than by argument; architecture question 8 gets a
  second real source.
- Costs: one more schema version at the end of a phase, and a third record type that P1
  inherits without a decision use behind it. `OQ-002` is resolved for P0 only; nothing here
  says a `product` record improves any decision.
- Failure modes: the body grows toward product semantics under deadline pressure. D5 exists to
  make that visible; the acceptance criteria in TASK-008 forbid a category field outright.
- Reversibility: high. Nothing else reads `product` rows, and 0.2 readers are unaffected by D2.

## Remaining uncertainty

- **Whether `product` is one type or the first of many.** A dataset of ingredients, or of
  reviews, would ask the same question again, and the answer "add a member" does not scale
  indefinitely. `OQ-003` still holds the schema question and is not closed by this packet.
- **`language`.** DP-019 D2 says language is stated by configuration and never detected.
  `[측정]` `product_name_ko` is 0/36 and no Hangul appears in any sampled `product_name`, so the
  configured value for this source is `en` and is a configuration claim, not a measurement of
  each row.
- **Deletion.** `SRC-003` measured that the delta export cannot express deletion. A `product`
  record therefore has no way to become absent, and nothing here changes that.

## Required changes

- Project State: §4 gains this packet; §5's hypothesis 5 keeps its refutation and gains the
  third shape as further input.
- Contract or schema: `PoC Contract 0.1` §5's `record_type` enumeration and its Schema version
  line. Limitation 3, *"No real dataset source exists"*, is **not** edited by this packet — it
  is edited when [TASK-007](../agent-workflow/task-packets/TASK-007-obf-dataset-end-to-end.md)
  produces the run, not when a decision anticipates it.
- Acceptance tests: determinism, each field's absence path, `skipped` for a row without `code`,
  and coexistence of a `0.3` result beside a `0.1` and a `0.2` result over one lineage.
- Migration or compatibility: none. Additive by D2.
- Implementation handoff: [TASK-008](../agent-workflow/task-packets/TASK-008-obf-product-normalizer.md).

## Falsification

| Claim | Falsified by |
|---|---|
| D1 — a third member extends rather than breaks the union | A 0.2 reader that misreads a stored `document` row once 0.3 exists |
| D2 — additive, so no existing normalizer bumps | A byte difference in any existing normalizer's output over an unchanged snapshot |
| D3 — four fields plus the envelope's identity are enough to carry a product row without loss of *identity* | A downstream reader that cannot trace a result to its sealed bytes without a sixth |
| D5 — extraction needs no product semantics | A rule in the normalizer that cannot be written without knowing what a sunscreen is |
