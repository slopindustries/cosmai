# P0 inherited defects and stated limits

- Status: `DRAFT` — `[확인 사실]` not `ACCEPTED_FOR_POC`, because nothing has accepted it: it is
  not one of the four artifacts the gate is defined to take, and no Decision Packet creates it.
- Created: 2026-08-20
- Owner: orchestrator session, from accepted task packets and their attack reports

`[확인 사실]` **Why this file exists.** Five task packets were accepted on 2026-08-20 with
findings recorded rather than repaired, and their dispositions said those findings were
"routed to the P1 Entry Gate". [`ADVERSARIAL-REVIEW-2026-08-20-CONSOLIDATION.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-CONSOLIDATION.md)
F6 measured that the destination did not exist — `P1-ENTRY-GATE-TEMPLATE.md` is a blank
template, the gate has never been held, and ten findings terminated at a document nobody had
written. A finding routed nowhere is a finding dropped with extra steps.

`[결정]` This register is that destination. It is **not** a defect tracker and nothing here is
scheduled: P0 is disposable and P1 rebuilds from contracts, so each row records a thing P1
must decide about, with the artifact that measured it.

`[확인 사실]` **This file is not one of the artifacts the gate is defined to accept.**
[`README.md`](README.md) names four — Architecture Synthesis, the disposition register,
`PoC Contract 0.1`, and the P1 reconstruction plan — and `AGENTS.md` names three of those
four, omitting Architecture Synthesis. Adding a fifth is an owner decision, not a thing this
file may assert about itself. `[확인 사실]` An earlier revision of this sentence said both
documents name four. An earlier revision of this paragraph
said "the P1 Entry Gate consumes this file", which claimed a process nobody accepted.
`[결정]` It is reachable instead from **two** of those four — the Architecture Synthesis, from
questions 2 and 5, and the disposition register, from two add-on rows — plus a pointer in
`project-state.md` §4, which is not one of the four. `PoC Contract 0.1` and the P1
reconstruction plan do not link it. `[확인 사실]` An earlier revision of this sentence claimed
three of the four, counted `project-state.md` among them, cited its §5 when the pointer is in
§4, and claimed a question-5 link that did not yet exist. The gate's *unresolved blocker* section is where its
contents belong; whether it becomes a fifth accepted artifact is for the owner to say.

`[확인 사실]` **Provenance is mixed and the split is not clean along section lines.** §§1–6
trace to committed attack reports. §7 is mostly worker handoffs, which are self-reported —
but not entirely: two of its items come from attack reports, and two others
(`config_field`, the layer-direction scan scope) are sourced to neither and are carried on
this file's own word. §8 traces to `B4-SCENARIO-COVERAGE.md`, which is an evidence document
rather than an attack report. `[확인 사실]` Two earlier revisions of this line were wrong in
opposite directions — the first claimed every row traced to an attack report, the second
claimed §7 was the only exception while the same edit added an attack-report finding to §7.
Nothing here was added that no review or handoff found.

## 1. Platform — one row can abort a run

| | |
|---|---|
| What | A payload carrying a lone surrogate (`{"code":"a\ud800"}`) is emitted by a normalizer and then raises `UnicodeEncodeError` inside `domain.store.canonical_body`. **One bad row ends the whole normalize run instead of being skipped and counted.** |
| Where | `experiments/integrated-p0/domain/store.py:132`, unguarded |
| Exposure | `normalizer.obf.product` and `normalizer.naver.blog` both; it predates both |
| Measured | [`ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md) |
| Why not repaired in P0 | Platform-level and outside every packet's allowed files. `[추론]` It is the most consequential row in this file: it converts a data-quality event into an availability event, and the add-on contract's promise that a bad item is *skipped and counted* does not hold above the add-on. |

`[확인 사실]` Related and unbounded by any contract: `domain.store.canonical_body` calls
`json.dumps` with default `allow_nan=True`, so a non-finite float in any add-on's body reaches
the store as a bare `NaN` literal. `normalizer.rule.baseline` enforces strictness inside itself
because that was the only place its packet could touch.

## 2. `normalizer.rule.baseline@0.1` — six stated gaps

| Gap | Measured in | State |
|---|---|---|
| A rule declared in `RULES_BY_KIND` that reaches no verdict is subtracted into `rules_evaluated` and the record is emitted `clean: true`. `_coverage` **cannot** catch it. What stands between a future rule missing its abstention branch and a wrong `clean` is review. | [`…-RULE-BASELINE-R2.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md) F1, [`…-COVERAGE-CLAIM.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md) | Stated in the module docstring after three rounds. Unenforced by design — the alternative re-plumbs the evaluation path of the add-on that *is* the measured evidence. |
| The `BOUNDED` marker is forgeable: a source key spelled identically produces a byte-identical `found`. | `…-RULE-BASELINE-R2.md` F2 | Stated in the comment. |
| `source_item_key` is unbounded while `found` is bounded. | `…-RULE-BASELINE-R2.md` F4 | Recorded only. |
| `output_contract_version` is unfalsifiable — nothing distinguishes a correct value from a wrong one. | `…-RULE-BASELINE.md`, `…-RULE-BASELINE-R2.md` | Routed by both reviews. `[확인 사실]` It is nonetheless cited as evidence in `PoC Contract 0.1`'s replacement for limitation 3, which a P1 reader should weigh accordingly. |
| Determinism as this add-on holds it (identical across interpreters and hash seeds) is stronger than anything the contract requires of a normalizer; whether every add-on is held to it, or only to same-process stability, is stated nowhere. | `…-RULE-BASELINE.md` | Recorded only. |
| The by-path add-on loader caches bytecode by `(mtime, size)`, so a same-size edit within one mtime second silently runs stale code. It produced two false `SURVIVED` verdicts in a reviewer's first pass. | `…-RULE-BASELINE.md` F13 | `[추론]` Bears on the trustworthiness of any mutation count in this repository, including those quoted in `project-state.md` §5. |

## 3. `normalizer.obf.product@0.1` — five weak assertions behind holding properties

`[측정]` The add-on survived its attack: 24 of 30 mutants died and determinism held across
seven hash seeds. What follows are **tests weaker than their names**, not broken behaviour —
each property was separately measured to hold.

- **F2** — the lineage assertion passes by fixture coincidence (`item_key` derived from `code`);
  `addon_host._check_lineage` holds it at runtime, which the packet never ran.
- **F3** — the coexistence assertion cannot go red for "no row updated in place": there is no
  UPDATE path, so collision is impossible. Verified independently against a live cluster.
- **F4** — five of six documentation gaps the author had to decide are labelled where a test
  reader will not look.
- **F5** — `notes` over-pins a container its own JSON contract drops (tuple → list).
- **F6** — the two skip *reasons* are asserted by nothing.

Source: `…-OBF-PRODUCT.md`.

## 4. The dataset evidence record — presence guarded, value not

- **B** — the field-presence control pins **presence, not value**. `observed_at` replaced by a
  constant epoch on all 121 rows, `brands` replaced by `["xx:FABRICATED"]` (which also passes
  the `xx:` prefix test), and `language` rewritten all stay green. The record's *content*
  claims rest on one manual reading.
- **C** — "computed at run time" is not "delta-proof": an abstaining `observed_at` value, or a
  seal that dedupes, makes it red for a non-defect.
- **D** — one softening clause survives above the disclaimer and in the test module docstring.
- **E** — `git status` cannot attribute changes in a tree several sessions write. A digest
  check is what a future packet should ask for.

Source: [`…-OBF-RECORD-REPAIRS.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-RECORD-REPAIRS.md).

## 5. Snapshot identity — two ways identical Raw seals differently

- **Member selection under a tie.** Which observation of one key wins is decided by
  `emitted_at`, which defaults to `now()` — a **transaction** timestamp. "The later import
  wins" therefore holds per import and not per row, and nothing states that two imports must be
  separate transactions. Forcing a tie and re-sealing twelve times drops the decision to
  `id desc` on a `uuid4`; two of three keys then selected the **older** payload.
- **Collation.** DP-019 D5 orders members by `item_key` and fixes no collation, so two clusters
  differing only in locale seal **different manifest digests from identical Raw**.

Both are carried in [OQ-004](../open-questions/OQ-004-snapshot-boundary.md); the second is also
in DP-019. Sources: `…-OBF-REAL-DATA.md` F2, `…-SNAPSHOT-R2.md` F-D.

`[측정]` Also from OQ-004, and a cost rather than a defect: **a purge does not discharge an
erasure obligation.** After deleting every `raw_item`, `snapshot_item` still holds the bytes and
`raw_envelope` holds the lossless original.

## 6. The dataset itself — a working path over irrelevant rows

`[측정]` [DP-027](../decisions/DP-027-dataset-standard-and-share-alike.md) D2: **zero Korean
sunscreen rows and zero Korean toner rows.** P0 has a working dataset path and **no
product-relevant dataset evidence**. Ingredient completeness is 26.5% database-wide with no
threshold in this repository to judge it against.

`[결정]` D3: ODbL share-alike, the attribution notice, and the machine-readable-copy offer all
attach on **first publication** — the first card, export, or public dashboard built on this
data. P1 inherits it as an obligation, not as a closed item. The attribution name is itself
unsettled: the provider's terms page names Open Food Facts while its data page names Open
Beauty Facts. [OQ-015](../open-questions/OQ-015-share-alike-data-class.md) holds the taxonomy
question.

## 7. Contract and harness gaps the add-on authors hit

`[확인 사실]` **These trace to worker handoffs, not to attack reports** — unlike every other
section of this file, and the distinction matters because a handoff is self-reported and an
attack report is independent. They are the gaps two add-on authors hit while writing against
the documentation alone, recorded in
[TASK-008](../agent-workflow/task-packets/TASK-008-obf-product-normalizer.md) and
[TASK-006](../agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md):

- `NormalizeContext.config_field` returns `Any`, so every handler re-checks types defensively.
- `addon_kit run` has no path that meaningfully runs a normalizer; every normalizer's tests
  build a `NormalizeContext` by hand.
- `tests/environment/test_addon_layer_direction.py` does **not** scan `tests/`, so a test file
  may import `domain.store` and `psycopg` directly without violating the add-on layer rule.
  Nothing documents that scope.
- The `database` / `connection` fixtures skip via `platform_database`'s own skip when no cluster
  is reachable. `[확인 사실]` It reports as `SKIPPED`, **not** as a silent pass —
  [TASK-008](../agent-workflow/task-packets/TASK-008-obf-product-normalizer.md)'s handoff says
  so in as many words, and an earlier revision of this bullet inverted it. What remains true is
  the weaker thing: a reader of a summary line, rather than of the run, can take a skipped
  criterion for a covered one. That happened in this session — TASK-008's coexistence criterion
  was reported as exercised on one run and skipped on another.
- Neither the contract nor `canonical_body` bounds a body or requires strict JSON.
- [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) holds the general
  question: what is an add-on responsible for that no other layer can check?

`[측정]` **The host path itself is unguarded, and this is not an add-on's finding.** Reversing
member order in `_NormalizeRun.execute` leaves 112 of 113 tests green. Found by
[`…-SNAPSHOT-R2.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md)
F-F, Major and out of that packet's scope, and carried by nothing until now.

## 8. What P0 never tested at all

- **B4's named coverage gaps**, including DNS as a failure mode — address ranges are checked
  and tested, DNS resolution itself is not. See
  [`B4-SCENARIO-COVERAGE.md`](../../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md)'s
  `NOT EXERCISED` rows, which are the point of that document.
- **Whether normalized fields survive over time.** Every schema answer compares shapes at the
  moment of normalization. No source was normalized twice across a real content change and the
  bodies diffed.
- **Malformed rows from a real producer.** The importer's three skip counters were all zero on
  the delta the test checks them for; the second delta's counters were not asserted. So
  partial-validity handling is proved on self-authored fixtures. Embedded newlines inside
  quoted strings remain unexercised, and duplicate row identity within one file cannot be
  exercised by that test at all — it asserts uniqueness rather than handling.
