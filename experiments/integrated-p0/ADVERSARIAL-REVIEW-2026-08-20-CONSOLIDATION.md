# Adversarial Review — Document consolidation, 2026-08-20

- Subject: uncommitted diff against `HEAD` (`2fb0f73`) in `docs/project-state.md`,
  `contracts/experimental/POC-CONTRACT-0.1.md`,
  `docs/architecture-synthesis/architecture-synthesis-v0.1.md`.
- Author of subject: orchestrator (the same session that accepted the five packets summarized).
- Reviewer: `adversarial-reviewer`, separate session. Date: 2026-08-20.
- Status: **COMPLETE**.

## Why this report exists with no packet beside it

`[확인 사실]` `docs/agent-workflow/README.md`'s threshold exempts a documentation correction
from a task packet. It does not exempt it from the attacker. This review is that rule applied:
no packet was written, and an independent report is still required. A reader who finds no
packet beside this report should not read that as the report being unauthorized.

## What was reviewed

`[측정]` `git diff HEAD` over the three paths: 3 files, +76 / −19. No other file in the
working tree was touched by this review; nothing was staged, reset, committed, or edited.

## Result

**`FAIL`** — the consolidation is substantially faithful, but it carries three blocking
defects. Nothing in it is fabricated. Every error runs in one direction: the record reads
better than the work it summarizes.

`[추론]` Three items block: a contradiction the diff created inside one file (**F1**), ten
findings routed to a P1 Entry Gate document that has never been created (**F6**), and a
`[측정]` figure that exists nowhere but in this diff (**F11**). The rest are scope widenings
of narrow measurements — the exact failure mode this work was warned about.

## Findings

| # | Where | Claim | Severity | Class |
|---|---|---|---|---|
| F1 | `POC-CONTRACT-0.1.md` limitation 5 | left saying Raw-store evolution is "unproved" while the same diff says it is exercised | **Blocking** | specification |
| F2 | synthesis Q2 headline | "the test is no longer weaker than the question" | **Major** | evaluation |
| F3 | synthesis Q2 | "zero skips of every counter" in "either real delta" | **Moderate** | evaluation |
| F4 | synthesis Q8 | "the three products whose `rev` advanced between two deltas" | **Moderate** | evaluation |
| F5 | contract limitation 3 | label roles mixed; struck heading defeats the "still binding" replacement | **Moderate** | specification |
| F6 | all three files | ten findings "routed to the P1 Entry Gate"; **the gate does not exist** and none was carried | **Blocking** | scope |
| F7 | synthesis Q5 | one new gap named, a larger one (collation → different manifest) dropped | **Major** | evaluation |
| F8 | synthesis Q5, project-state §5 | F-B's narrowing **was** correctly inherited — held under attack | — | held |
| F9 | synthesis Q8 | new `[가설]` and `[추론]` written under cover of consolidation; "independently chosen" overstates | **Moderate** | scope |
| F10 | `P0-ARTIFACT-DISPOSITION.md` | a gate-required register now contradicts the diff and was not touched | **Moderate** | specification |
| F11 | project-state §5 | `20,000 differential comparisons` is a sum no report states; "two attacks" is three; two `FAIL` verdicts dropped | **Blocking** | evaluation |
| F12 | project-state §5 | an open defect (`clean: true`) reported in the past tense | **Moderate** | evaluation |
| F13 | project-state §5 | "five of the ten cannot fire" is four on the source's own table | **Minor**, inherited | evaluation |
| F14 | project-state §5 | five more open rule-baseline items reach no reader | **Moderate** | scope |

---

### F1 — Blocking. The contract now contradicts itself, inside the diff

**Claimed.** `docs/project-state.md` §5: *"Raw-store evolution **was** exercised."*
`architecture-synthesis-v0.1.md` Q5: *"`YES, NARROWLY` for evolution since 2026-08-20."*

**Why it is false as a record.** `contracts/experimental/POC-CONTRACT-0.1.md`'s "Known
limitations and unresolved semantics" list is **untouched at item 5** by this diff:

```text
5. **Snapshot replay across Raw-store evolution is unproved** (§4).
```

`[측정]` `git diff HEAD -- contracts/experimental/POC-CONTRACT-0.1.md` changes exactly one
hunk, at limitation 3. Limitation 5 is not in the diff.

`[추론]` The consolidation reached into this exact list to strike limitation 3 and left
limitation 5 standing while asserting elsewhere in the same commit that limitation 5's subject
is now measured. A P1 Entry Gate reader consulting the contract's own limitations list — the
document `project-state.md` §1 B2 points them at — is told the opposite of what the synthesis
tells them, with no cross-reference reconciling the two.

**This is the more dangerous direction of the error, not the safer one.** Limitation 5 as
written is *too strong a disclaimer*, and F-B of `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2`
means the honest text is neither "unproved" nor "proved" but the narrowing the other two files
carry. Leaving it at "unproved" is not conservative; it is a third, different answer.

**Reproduction.** `git diff HEAD -- contracts/experimental/POC-CONTRACT-0.1.md`, then
`grep -n "Raw-store evolution" contracts/experimental/POC-CONTRACT-0.1.md docs/project-state.md docs/architecture-synthesis/architecture-synthesis-v0.1.md`.

---

### F2 — Major. "The test is no longer weaker than the question" is not what the sources support

**Claimed.** Synthesis Q2 headline, replacing *"`YES` for the shapes tested, and the test is
weaker than the question"*:

> **`YES`, and since 2026-08-20 the test is no longer weaker than the question.**

**Why it is unproven.** The paragraph it replaces named **three** unexercised things:
*"Encoding surprises, embedded newlines in quoted strings, and duplicate row identities within
one file are unexercised."* The new text retires only **partial validity**, and does so by
saying it stays proved on SRC-002 fixtures. It says nothing about the other two, and the
headline generalizes from the one it addressed to all of them.

`[확인 사실]` Duplicate row identity within one file remains unexercised by construction: the
test asserts the opposite — `test_obf_real_data.py` asserts
`len(set(first.codes)) == len(first.codes)` with the comment *"the delta held a duplicate
code; SRC-003 measured none in three samples, so this would itself be worth recording."* A
real file with no duplicates cannot exercise duplicate handling.

`[추론]` A headline stating that a test is no longer weaker than its question, when the
question's named weaknesses are two-thirds still open, is the exact upgrade this consolidation
was supposed to avoid. The body of the section is honest; the headline is not, and the
headline is what a gate reader quotes.

**Reproduction.** Compare the removed paragraph (`git diff HEAD` at
`architecture-synthesis-v0.1.md` lines 54–72) against the added one, and
`grep -n "len(set(first.codes))" experiments/integrated-p0/tests/test_obf_real_data.py`.

---

### F3 — Moderate. "Zero skips of every counter" in "either real delta" was measured on one delta and three counters

**Claimed.** Synthesis Q2: *"No malformed row appeared in **either** real delta — the importer
reported zero skips of **every** counter."* Labelled `[측정]`.

**What was measured.** `experiments/integrated-p0/tests/test_obf_real_data.py:346`,
`test_every_skip_counter_the_importer_reported_is_recorded`:

```python
first, _second = deltas
events = import_finished_events(log_stream)
assert len(events) == 1
...
for counter in ("malformed_json", "not_an_object", "missing_key_field"):
    assert fields[counter] == 0
```

`[측정]` The second delta is bound and discarded (`_second`). Exactly **one**
`addon.import.finished` event is asserted to exist, and three named counters are checked on
it. The claim is therefore: three counters, one delta.

`[추론]` "Either real delta" and "every counter" are both wider than the assertion. The wider
form may well be true — nothing suggests delta B held a malformed line — but this sentence
carries a `[측정]` label, and per `evidence-labels.md` a `[측정]` states what a procedure
observed, not what the observer expects would hold on an input the procedure skipped.

---

### F4 — Moderate. The "three `rev`-advanced products" merges two different measurements of three

**Claimed.** Synthesis Q8, labelled `[측정]`:

> The nearest thing is the three Open Beauty Facts products whose `rev` advanced **between two
> deltas**, and their normalized bodies were not diffed.

**What the sources measured.** Two different threes, in two different comparisons:

1. `[확인 사실]` `experiments/source-probes/SRC-003-open-beauty-facts.md:328–342` — 121 delta-A
   codes resolved against the **live API** 23 hours later; *"products whose `rev` advanced
   between the two: **3**"*, named as `7891010974312` (5→7), `5906721183488` (13→14),
   `4047196060247` (2→12). The comparison is **delta A vs. the live API**, not delta vs. delta.
2. `[확인 사실]` `ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md:31` — delta A ∩ delta B is
   *"exactly those three"* codes. That measurement is of **code overlap**, and the report
   confirms the sealed members' bytes match delta B and differ from delta A. It does not
   report `rev`.

`[측정]` `experiments/integrated-p0/tests/test_obf_real_data.py:439`,
`test_the_second_later_delta_advances_shared_codes_without_editing_raw_in_place`, asserts that
each overlapping code yields **two `raw_item` rows** and that the union seals at 244. It does
not read or compare `rev` at all.

`[추론]` So "whose `rev` advanced between two deltas" is a splice: it takes the `rev`-advance
from measurement 1 and the between-two-deltas scope from measurement 2, because both produced
the number three over the same three codes. It is very likely true. **No committed artifact
states it**, and it is labelled `[측정]`. That is a derived claim presented as an observed one.

`[추론]` A second, smaller problem in the same sentence: *"their normalized bodies were not
diffed"* is an absence of work, not a value obtained from a procedure. Per
`evidence-labels.md`'s decision order it is `[확인 사실]` at best; it is carried inside a
`[측정]` bullet.

---

### F5 — Moderate. Limitation 3's replacement mislabels, and the strike defeats the binding half

**Claimed.** The strike-through is defended in its own text: *"Struck rather than deleted: a
reader comparing this contract to the gate record needs to see that the limitation existed and
when it stopped applying."* And: *"What replaces it is narrower and **still binding**."*

**On the act of striking.** `[추론]` Striking rather than deleting is the right call and the
stated reason is a good one. The finding is not the strike; it is what the strike does to the
sentences under it.

**Why the replacement does not bind as written.**

`[확인 사실]` The document's structure is a numbered list titled *"Known limitations and
unresolved semantics"*. Item 3's **entire heading and body** are inside `~~…~~`. The two
paragraphs beneath it are not struck, but they are subordinate to a heading a reader has been
told to disregard. A reader skimming the list for what still constrains P1 sees seven items,
one of them crossed out. `[추론]` The binding content — *"zero Korean sunscreen and zero
Korean toner rows … no product-relevant dataset evidence"*, and ODbL share-alike inheritance —
is DP-027 D2's and D3's, and it is now the only place in this list where a live constraint
lives under a dead heading. If it still binds, it is a limitation and belongs as its own
numbered item.

**Label roles are mixed in both replacement paragraphs.**

- `[측정]` **Closed 2026-08-20.** — "Closed" is a status the project adopted, i.e. `[결정]`.
  The measurement is the clause after it (delta exports pass through the importer into Raw, a
  sealed snapshot, and `normalizer.obf.product@0.1`). One bullet, two roles.
- `[결정]` **… The source holds zero Korean sunscreen and zero Korean toner rows (DP-027 D2)**
  — that is a count read off DP-027's own table (`countries_tags_en=south-korea&categories_tags_en=sunscreen` → **0**;
  `…=toner` → **0**), i.e. `[확인 사실]`. The `[결정]` is the decision to keep OBF anyway.
  `evidence-labels.md`'s "하나의 문장에 역할을 섞지 않는다" is the rule broken, in the file
  where mislabelling costs the most.

`[확인 사실]` DP-027 D2's zeroes **do** survive into the replacement — the substantive worry
that the strike would read as "the limitation is gone" is not realized in the prose. It is
realized only in the markup and the numbering.

---

### F6 — Blocking. Ten findings were "routed to the gate". The gate does not exist, and the consolidation was the last chance to carry them

**Claimed.** `TASK-011-obf-record-repairs.md:207`: *"Findings B, C, D, and E are recorded and
routed to the P1 Entry Gate as stated limitations rather than to a fourth round."*
`TASK-008-obf-product-normalizer.md:307`: the platform surrogate defect *"goes to the gate as
an inherited platform defect."*

**Why the routing is empty.**

`[측정]` `find . -path ./.git -prune -o -iname '*gate*' -print` over the working tree returns
`docs/architecture-synthesis/P1-ENTRY-GATE-TEMPLATE.md` and the two P0-A
`PLATFORM-CORE-GATE*` files. **No instantiated P1 Entry Gate document exists.** The template's
"Blocking limitation" column is empty.

`[측정]` `grep -rn "surrogate\|UnicodeEncode\|canonical_body\|d800" docs/project-state.md
contracts/experimental/POC-CONTRACT-0.1.md docs/architecture-synthesis/` exits `1` — **zero
hits** across all three standing-record files, before and after this diff.

`[확인 사실]` Ten findings routed to that non-existent destination, none of which appears in
any of the three files this diff touches:

| Finding | Substance | Where it actually lives |
|---|---|---|
| TASK-011 B | the per-field control pins **presence, not value**; M5/M6/M7/M9 fabricate `observed_at`, `brands`, `language` and the suite stays green | `ADVERSARIAL-REVIEW-2026-08-20-OBF-RECORD-REPAIRS.md:116`, `TASK-011:225` |
| TASK-011 C | run-time computation is not delta-proof | same review `:143` |
| TASK-011 D | a softener survives in `evidence/obf-dataset/README.md:12` | same review `:187` |
| TASK-011 E | AC-5's `git status` check is unverifiable in a shared tree | same review `:315` |
| TASK-008 F2 | criterion 2's lineage clause passes by **fixture coincidence**; M4 leaves all 41 tests green | `ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md:244` |
| TASK-008 F3 | criterion 6's "no row updated in place" is **unfalsifiable**; the report asks by name that *"a reader of the P1 Entry Gate should be told"* | same report `:282` |
| TASK-008 F4 | three frozen `[가설]` unlabelled; a class docstring cites DP-028 D3 for a rule D3 does not contain | same report `:290` |
| TASK-008 F5 | `notes["skipped_item_keys"]` asserted as a tuple the wire cannot preserve | same report `:330` |
| TASK-008 F6 | two skip reasons indistinguishable | same report `:358` |
| **platform surrogate** | `{"code":"a\ud800"}` → `UnicodeEncodeError` in `domain.store.canonical_body`; **one malformed row aborts a whole normalize run** rather than being skipped and counted | same report `:402–421`; `domain/store.py:145` still unguarded |

`[추론]` Each route terminates at an adversarial review reachable only through its own task
packet, or at a document that has never been created. `grep -rn "OBF-RECORD-REPAIRS"` returns
one hit in the whole repository — that review's own packet. This diff is the act that was
supposed to close the loop, and it consolidated only results, never limitations.

**This is worse than an omission on one item.** The surrogate defect is **counter-signalled**
by new text in this diff. Synthesis Q2's added paragraph tells a gate reader:

> No malformed row appeared in either real delta … so partial-validity handling is still
> proved on SRC-002's deliberately broken fixtures rather than on a real file.

`[추론]` A reader takes from that sentence that malformed-row handling is *merely unexercised
on real data*. The measured fact is stronger and worse: on a malformed row of a shape that has
been produced, the run **aborts at the persistence boundary**. Adding a reassuring `[측정]`
about an area where a known-open abort exists, in the same edit that fails to carry the abort,
is the sharpest instance of this consolidation's failure mode.

**Reproduction.** The two `grep`/`find` commands above; then
`sed -n '402,421p' experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`
and `sed -n '132,147p' experiments/integrated-p0/domain/store.py`.

---

### F7 — Major. Question 5 gained one new gap and dropped a larger one

**Claimed.** Synthesis Q5's new headline: *"`YES` for tampering; `YES, NARROWLY` for evolution
since 2026-08-20; **and one new gap**."* The gap named is the `emitted_at`/`uuid4` tie-break.

**What was left out.** `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-D, **Major**:

> `[측정]` … Under `und-x-icu` the same four keys seal in a different order, so **the same Raw
> produces a different manifest digest**, hence a different snapshot identity, on a cluster
> that differs only in locale.

`[추론]` That is a defect in *reproducibility* — the exact word question 5 asks about — and it
is larger than the tie-break, because it moves the manifest digest for **every** snapshot
rather than only for tied duplicates. Question 5's surviving first `[측정]` still reads
*"Two real captures were sealed with recorded manifest digests"* with no note that the digest
is a function of an unrecorded cluster property.

**Mitigating, and it matters.** `[확인 사실]` F-D **was** carried, into two committed
documents a gate reader plausibly reads:
`docs/decisions/DP-019-normalized-schema-0-1-and-results.md:82–101` and
`docs/open-questions/OQ-004-snapshot-boundary.md:91`. So this is a Major omission from the
synthesis, not a lost finding. Contrast F6, where nothing was carried anywhere.

`[확인 사실]` Also uncarried and genuinely lost from question 5: F-F, *"the host path is still
unguarded"* — reversing member order in `_NormalizeRun.execute` leaves `112 passed` of 113
green, so nothing on the host path asserts a normalizer received the sealed bytes.

---

### F8 — Moderate. Question 5 and hypothesis 4 **do** carry F-B's narrowing, and that is the strongest part of this diff

Stated because a `FAIL` should not bury what held.

`[측정]` `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-B established that `queried_reader`
is *not* OQ-004's first listed alternative, and that against the reference-preserving design
OQ-004 does name, *"steps 1–3 all agree with the sealed design; only the purge separates
them."*

`[확인 사실]` Both subject files carry that narrowing, in substance and in the right direction:

- synthesis Q5: *"Narrowly, because against the design OQ-004 actually names — references to
  append-only Raw rows, fixed at seal — only the purge separates the two."*
- `project-state.md` §5: the same sentence, with the OQ-004 link.

`[추론]` This is the case where the consolidation inherited the bad half along with the good
half, and did it without being asked to. The headline `YES, NARROWLY` is honest work.

`[추론]` One residue: F-A — that a one-statement collation migration **does** discriminate,
falsifying the worker's `[가설]` — is not carried. It cuts in the sealed design's favour, so
the omission does not overstate; it does leave the synthesis asserting a three-mutation
taxonomy the source measured to be incomplete.

---

### F9 — Moderate. Question 8's closing paragraphs are new analysis, not consolidation

**Claimed.** Two paragraphs added at the end of question 8: a `[가설]` that the union grows one
member per source shape, and a `[확인 사실]` that no source has tested the question's own word
"survive".

**Judgment.**

`[확인 사실]` Neither paragraph appears in any of the five packets or their attack reports.
Both are written on 2026-08-20 by the orchestrator, in an edit whose stated purpose is to move
already-measured results into the standing record.

`[추론]` **The `[확인 사실]` paragraph is the more defensible of the two and the more valuable.**
It says the answer does not answer the question as worded — all three comparisons are of
*schemas at the point of normalization*, and nothing measures whether fields stay correct over
time. That is a limitation of the existing record, correctly labelled, and a gate reader needs
it. New writing that *narrows* an existing claim is the one kind of new writing a consolidation
can justify.

`[추론]` **The `[가설]` paragraph is not.** It is forward-looking design analysis about P1's
source set, it has no evidence in P0, and it belongs in an Open Question, not in the answer to
a charter question. Per `AGENTS.md`, *"단순히 모르는 항목을 모두 가설이라고 부르지 않는다.
질문만 있는 경우 Open Question으로 기록한다."* It does carry a falsification condition, which
is the minimum `evidence-labels.md` demands, so this is a placement finding, not a labelling
one.

`[추론]` **The `[추론]` between them overstates independence.** *"Two sources could have been a
coincidence of pairing; three **independently chosen** shapes are a pattern."* Two of the three
shapes — a blog document and a DataLab trend point — come from the **same provider**, NAVER.
Their shapes differ; their choice was not independent. And "are a pattern" is stated flatly for
n=3. The weaker sentence the evidence supports is that a third shape did not rescue the strong
form — which the paragraph above it already says, measured.

---

### F10 — Moderate. A register the gate requires now contradicts the diff, and was not touched

`[확인 사실]` `docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:43`, the
`addons/importer.local.jsonl` row, still reads:

> Exists to prove the import *path*; **reads a file this project authored**

`[추론]` That is the sentence this consolidation exists to retire — it is the same claim as
the struck contract limitation 3 and as the removed synthesis paragraph *"The dataset half is
self-authored."* Two of its three instances were corrected; the third was not.

`[확인 사실]` The same register carries **no row** for `addons/normalizer.obf.product` or
`addons/normalizer.rule.baseline`, the two add-ons this round of work produced. `[확인 사실]`
`AGENTS.md` makes artifact disposition one of the things the P0-B P1 Entry Gate must accept, so
this is not an incidental file.

`[추론]` The consolidation's own boundary — three files — is defensible as a scope choice. What
is not defensible is that the boundary was drawn without noting that a fourth, gate-required
document now disagrees with the three.

---

### F11 — Blocking. `20,000 differential comparisons` is a sum the orchestrator computed. No report states it

**Claimed.** `docs/project-state.md:253`, labelled `[측정]`:

> across two independent attacks the rules' decisions were unchanged under **26 + 11
> mutations and 20,000 differential comparisons**.

**Why it is false as a `[측정]`.**

`[측정]` `grep -rn "20,000\|20000" docs experiments contracts` returns the uncommitted
project-state line and two unrelated hits (`"A"*200000`). **The figure 20,000 exists nowhere
else in the repository.**

`[측정]` Every committed source keeps the two figures apart:

```text
docs/agent-workflow/task-packets/TASK-009…md:105
  the ten rules survived 26 + 11 mutations and 16,000 + 4,000 differential comparisons.
docs/agent-workflow/task-packets/TASK-009…md:449
  (the ten rules' 26+11 mutations and 16,000+4,000 differential comparisons)
docs/agent-workflow/task-packets/TASK-006…md:348
  the ten rules unchanged across 16,000 differential comparisons against `07c599b`
docs/agent-workflow/task-packets/TASK-009…md:622
  4,000 differential comparisons with zero [divergence]
```

`[추론]` The orchestrator preserved `26 + 11` unsummed and summed `16,000 + 4,000` into
`20,000` in the same sentence. The source deliberately wrote them as a pair. This is a derived
number presented as a measured one — the named failure mode, in the one file a P1 Entry Gate
reader will quote from.

**Three further defects in the same sentence.**

1. `[확인 사실]` **"Two independent attacks" is three.** 26 is `ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md:69`;
   11 and 16,000 are `…-RULE-BASELINE-R2.md:68`, `:139`; 4,000 is a **third** review,
   `…-COVERAGE-CLAIM.md:19`. Summing across the third attack while claiming two is what makes
   the merged figure look like one procedure's output.
2. `[추론]` **The two kinds of number measure incompatible things and are joined by one verb.**
   The mutations measure *test sensitivity* — a killed mutant is one whose decision **did**
   change and the suite caught it. The differential comparisons measure that a refactor
   *did not* change the decisions. "The rules' decisions were unchanged under 26 + 11
   mutations" is not what mutation testing showed; it inverts it.
3. `[확인 사실]` **26 is a filtered subset of an attack that returned `FAIL`.**
   `…-RULE-BASELINE.md:26` — *"38 mutations applied and restored"*; `:69` — *"26 of 26
   **rule-behaviour** mutations were killed."* Of the other twelve, M28, M31, M35 and M36
   **survived**, which is why `:7` reads `Result: FAIL`. `…-RULE-BASELINE-R2.md:8` is also
   `FAIL`. The coverage review is `FAIL` in rounds 1 and 2 and `PASS` only in round 3.
   `[추론]` A sentence built from three attacks, two of which returned `FAIL`, that reports
   only their killed-mutant subtotals, reads to a gate as a clean sweep. Not one of the three
   verdicts is carried.

**Reproduction.** The two `grep`s above, then
`grep -n "^- Result" experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE*.md`.

---

### F12 — Moderate. "`clean: true` **could** be emitted" reports an open defect in the past tense

**Claimed.** `project-state.md:253`: *"`clean: true` **could** be emitted for a record a rule
never evaluated. Three review rounds established that `_coverage` cannot catch it … and the
record **now says so** instead of claiming a control."*

**What traces.** `[확인 사실]` "Three review rounds" is right — rounds 1/2/3 inside
`ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md` (`:9`, `:394`, `:653`). `[확인 사실]`
"Computed by subtraction" is right and readable at `addons/normalizer.rule.baseline/handler.py:404`:
`return [rule for rule in applicable if rule not in unevaluated]`.

**What does not.** `[확인 사실]` Two distinct defects are merged. R1's F2 — a rule whose *input*
could not be read — **was** repaired in TASK-006. R2's F1 — a rule **declared** in
`RULES_BY_KIND` that reaches no verdict is subtracted into `rules_evaluated`, and the record is
emitted `clean: true` with no `AddonOutputInvalid` — is **open**:

```text
ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md:900
  F1's gap (a declared rule reaching no verdict is subtracted into `rules_evaluated`, and
  the record can be `clean: true`) … remain **stated and not closed**.
```

`[추론]` The past tense plus *"the record now says so"* reads as an item closed by
documentation. The honest statement is that the artifact **can still** assert coverage it does
not have for any rule added without an abstention branch, and that only review — not a control
— prevents it. `AGENTS.md`: *"Do not describe a convention as a control."* The consolidated
sentence does not do that outright, but it is the sentence a reader will use to stop asking.

---

### F13 — Minor, inherited. "Five of the ten cannot fire" is four, on the source's own table

`[확인 사실]` `ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md:223` says *"five of ten rules
cannot fire"*, so the consolidation copied its source faithfully. The source's own
reachability table (`:232–246`) has five **rows** marked "No" spanning **four distinct rules**
— `trend.missing_field` appears three times (`dimension` **No**, `title` **No**, `period`
"Barely", `timeUnit` **Yes**).

`[추론]` So `trend.missing_field` **is** reachable from a NAVER collector and counting it among
rules that "cannot fire" is wrong on the evidence beneath it. This is not the consolidation's
error to originate, but a consolidation is the moment to catch it, and R1's own required
follow-up (`:515`) asked for the opposite of what was done: *"should carry F4 verbatim …
Recording the reachability table is worth more to the P1 Entry Gate than recording the rule
count."* The rule count was recorded; the table was dropped.

`[추론]` One narrowing in the same clause: R1:230 says the collectors *"refuse **or
synthesise**"* those fields. `dimension` is a module constant — synthesis, not refusal. The
consolidation keeps only "refuse", which makes the guard sound stronger than it is.

---

### F14 — Moderate. Five more open rule-baseline items reach no reader

`[확인 사실]` `project-state.md:253` is the **only** mention of the rule baseline in the
standing record. Open items not carried, each stated in a committed review:

| Item | Where | Status |
|---|---|---|
| `BOUNDED` marker forgeable — a source `ratio` keyed `"<bounded by the rule baseline>"` yields a `found` byte-identical to a genuine bound | `…-RULE-BASELINE-R2.md:320` | open |
| `source_item_key` unbounded — a 300,000-character key passes into `NormalizedResult` untouched; only `found` is bounded | `…-RULE-BASELINE-R2.md:322` | open |
| `output_contract_version` is unfalsifiable — no artifact defines the body shape, three add-ons declare `"0.1"` for three unrelated shapes, and TASK-006 changed a stored body shape with nothing noticing | `…-RULE-BASELINE.md:106`, `…-R2.md:355` | open, **routed to the gate by both reviews** |
| the determinism reading is undecided against `PoC Contract 0.1` Invariant 9 | `…-R2.md:118` | open |
| the by-path loader's `(mtime, size)` bytecode cache produced two false `SURVIVED` verdicts | `…-RULE-BASELINE.md:110` | open; affects any future mutation evidence in this repo |

`[추론]` `output_contract_version` is the one that most deserves the gate: the consolidation's
own contract limitation 3 replacement asserts *"`normalizer.obf.product@0.1` at contract
`0.3`"* as evidence of a working path, while the reviews record that the contract version
string is checked by nothing.

---

## What I tried and could not break

Stated plainly, because it is a large part of the result.

- `[측정]` **"Twelve times" and "two of three keys selected the older payload"** trace exactly,
  to `OQ-004-snapshot-boundary.md:104–105` and `ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md:117–128`.
  The wording is the source's, the scope is the source's, and the report's own care — that the
  `uuid4` tie-break was **not** what produced the real 3-code result — is preserved by the
  consolidation's "Forcing a tie drops the decision to a `uuid4`".
- `[측정]` **"121 and 126 products"** trace to `SRC-003:328`, `TASK-007:229`, and
  `ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md:29–33`, which recomputed both from the bytes
  and matched. The digests, the 3-code overlap and the 244-member union all reproduce.
- `[측정]` **"Four mutations of the seal and read"** traces: S-a…S-d in
  `…-SNAPSHOT-R2.md`, and the report confirms the discrimination class's positive control was
  among the failures in **each** of the four. "Not decorative" is the source's own judgment.
- `[측정]` **"All four steps"** is the source's four-step timeline (at seal / after migration /
  after later observations / after purge), not a miscount of the three mutations named.
- `[확인 사실]` **DP-027 D2's zeroes survive into the contract's replacement text** — the worry
  that the strike would read as "the limitation is gone" is not realized in the prose (only in
  the markup, F5).
- `[확인 사실]` **F-B's narrowing was inherited, not just the good half** (F8). This is the
  single best thing in the diff.
- `[확인 사실]` **DP-019 and OQ-004 already carry the collation defect** (F7), so that Major is
  findable even though the synthesis dropped it.
- `[확인 사실]` "Ten deterministic rules", "every rule is killed by at least one mutation",
  "built and tested on 2026-08-20 on fixtures", the `_coverage`-by-subtraction mechanism, and
  the "three review rounds" count all trace correctly.

## Limits of this review

- `[확인 사실]` No test suite was run: instructed not to, and the database may be held by another
  task. Every verification here is against committed text, committed test source, and `git diff`.
- `[확인 사실]` Nothing was staged, reset, committed, or edited. The four subject files are
  untouched by me. `git status --short` shows the same three modified files it showed at the
  start of this review, plus this report.
- `[추론]` F6's ten findings were traced through `grep` for their distinctive terms. A finding
  restated in wholly different words in a document I did not read could have been missed; the
  surrogate defect, which I grepped four ways, could not have been.

## Required follow-up

1. **F1 and F11 are blocking and cheap.** Update contract limitation 5 or say why it stands;
   restore `16,000 + 4,000` and the three attack verdicts.
2. **F6 is blocking and is not cheap.** Ten findings, one of which is a run-aborting platform
   defect with no guard in `domain/store.py`, are routed to a document that does not exist.
   Either instantiate `P1-ENTRY-GATE` from its template with a populated "Blocking limitation"
   column, or add them to the contract's limitations list. Consolidating results while
   limitations wait for a destination is what makes a standing record read better than the
   work it summarizes.
3. **F2's headline** should return to a claim the body supports.
4. `[추론]` The pattern across F2, F3, F4, F11 and F12 is one direction: every widening favours
   the result. None of the four errors makes the record look worse than the sources. That is
   worth the orchestrator's attention independent of any single item, and it is the reason a
   consolidation written by the party that accepted the packets needs a separate reader.

---

# Round 2 — re-attack of the repairs, 2026-08-20

- Subject: `git diff HEAD` (`2fb0f73`) over `docs/project-state.md`,
  `contracts/experimental/POC-CONTRACT-0.1.md`,
  `docs/architecture-synthesis/architecture-synthesis-v0.1.md`, plus the new untracked
  `docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`.
- Reviewer: `adversarial-reviewer`, same session lineage as round 1. Round 1's `FAIL` stands
  as written and is not amended.
- Scope: exactly the items the round-2 brief named. No new area was opened.

## Result

**`FAIL`**, and narrowly — this round is much closer than round 1. **F6, the round-1 finding
that mattered most, is substantially repaired**: the register exists, every routed finding is
in it, and the surrogate defect is stated at full severity in three places. **F1, F2, F3, F4
and F7 are closed.**

`[추론]` Two things block. **R2-1**: the sentence written to repair F11 contains two new
`[측정]` figures that its sources do not support, one of them inverted. That is the fifth
occurrence of this session's named failure mode, and it is in the same sentence F11 was about.
**R2-3**: the new register says the P1 Entry Gate consumes it, while
`docs/architecture-synthesis/README.md` — the directory's index and the document that
enumerates what the gate accepts — does not list it. F6 was "routed to a destination that does
not exist"; the destination now exists and the gate's own index still does not point at it.

## Round-2 findings

| # | Where | Claim | Severity | Class |
|---|---|---|---|---|
| R2-1 | `project-state.md` §5, rule-baseline bullet | "four others survived" is inverted, and 16,000 is attributed to the wrong attack | **Blocking** | evaluation |
| R2-2 | `P1-INHERITED-DEFECTS.md:18` | `[확인 사실]` "Every row traces to a committed attack report" is false for at least three bullets in §7 | **Major** | evaluation |
| R2-3 | `P1-INHERITED-DEFECTS.md:16` vs `architecture-synthesis/README.md:41` | "The P1 Entry Gate consumes this file" is contradicted by the gate's own list of accepted outputs | **Blocking**, narrowly | scope |
| R2-4 | `P1-INHERITED-DEFECTS.md:132` | "Both captured deltas were clean" — the exact widening round 1 raised as F3, reintroduced in the new file after being fixed in the old one | **Moderate** | evaluation |
| R2-5 | synthesis Q5 headline | "and one new gap" while the body now names two | **Minor** | evaluation |
| R2-6 | synthesis Q2 | of the three weaknesses the replaced paragraph named, "embedded newlines in quoted strings" is dropped without mention | **Minor** | scope |
| R2-7 | `project-state.md` §5 | F9's "independently chosen" overstatement was not fixed and has now propagated into a second file | **Moderate** | scope |

---

### R2-1 — Blocking. The F11 replacement is itself wrong, twice

**Claimed.** `docs/project-state.md:259`, labelled `[측정]`:

> The first applied 38 mutations, of which the 26 aimed at rule behaviour were all killed and
> **four others survived**; the second killed 11 more; **the third compared 16,000 and then
> 4,000** pre- and post-change outputs and found zero divergence.

**What the brief asked for, and what holds.** `[확인 사실]` `26 + 11` are kept unsummed; the
`20,000` is gone; three attacks are counted, not two; mutations and differential comparisons are
no longer joined under one verb, and the sentence says so explicitly; `[확인 사실]` **two of the
three returned `FAIL`** is correct — `…-RULE-BASELINE.md:7` `FAIL`, `…-RULE-BASELINE-R2.md:8`
`FAIL`, `…-COVERAGE-CLAIM.md:655` `PASS` in round 3. All five of those are real repairs.

**Defect 1 — "four others survived" is inverted.** `[확인 사실]`
`ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md` states no survivor total anywhere. It does name
mutations that left the suite green, each with its measured result:

| Mutation | Where | Observed |
|---|---|---|
| M09 | `:102` (F5) | `mypy` → `Success`; suite → `57 passed` |
| M13 | `:107` (F10) | dropping `or not value.strip()` leaves `57 passed` |
| M28 | `:98` (F1) | gutting `_finding`'s body leaves **57 passed** |
| M29 | `:296` (F6) | `notes` never read by any test |
| M30 | `:292` (F6) | counters never advance; `57 passed` |
| M31 | `:294`, `:417` (F6) | clean/dirty swapped; **"M31 genuinely survives"** |
| M35 | `:100` (F3) | set-ordered `expected`; `TestItIsDeterministic` reports `2 passed` |
| M36 | `:298` (F7) | `rule_report_version` dropped; never asserted |

`[측정]` That is **eight** named survivors, not four. `[확인 사실]` None of them can be inside
the 26, because `:69` reads *"26 of 26 rule-behaviour mutations were killed."* `[확인 사실]`
`:417` names exactly one further mutation of the remaining twelve as killed (*"M32 is killed"*).

`[추론]` So of the twelve non-rule-behaviour mutations, at least eight survived and at most four
were killed. The sentence says four survived. **The figure is not merely unsourced — it is the
killed count reported as the survived count.** A gate reader takes from it that 34 of 38
mutations died; the source supports at most 30, and names eight specific test gaps.

**Defect 2 — 16,000 belongs to the second attack, not the third.** `[확인 사실]`
`ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md:139–150`: *"**No, on 16 000 differential
comparisons.** … I loaded the `07c599b` handler and the `70fa293` handler side by side in one
process and ran both over 8 000 randomly generated blog- and trend-shaped records … 8 000
further cases."* That is the **second** attacker's own experiment, in the same report that
killed the 11.

`[확인 사실]` The 4,000 is the third attacker's: `…-COVERAGE-CLAIM.md:151` — *"Differential
fuzz, `$TMPDIR/probes/diffl.py`: 4 000 records (seed 20260820)"*, `:158` *"differential
comparisons: 4000, divergences: 0"*.

`[추론]` Round 1's F11 was that a derived sum hid which attack produced what. The replacement
keeps the numbers apart and then attributes both to one attack. The specific harm is that it
makes the third attack — the only one of the three that ended `PASS` — look like it carried
four fifths of the differential evidence, when its own contribution is 4,000 of 20,000.

**Reproduction.**
`sed -n '137,152p' experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md`;
`sed -n '149,159p' experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md`;
`grep -n "M09\|M13\|M28\|M29\|M30\|M31\|M35\|M36\|M32 is killed" experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md`.

`[추론]` One smaller widening in the same bullet, stated but not ranked: *"two of the three
returned `FAIL` — on claims made about the rules, **never on the rules themselves**."* The first
attack's own summary (`:13–16`) is *"The `FAIL` is not about the rules … **plus one live
misstatement in the emitted body** (`clean: true` for a record a rule never evaluated)"*, and
that finding is classed `implementation`. The consolidation keeps the first half of the source's
sentence and drops the qualifier. The register does carry the substance (§2), so this is a
wording widening, not a lost finding.

---

### R2-2 — Major. The register asserts a traceability it does not have

**Claimed.** `P1-INHERITED-DEFECTS.md:18`, labelled `[확인 사실]`:

> Every row traces to a committed attack report. Nothing was added here that a review did not
> find.

**Why it is false.** `[측정]` §7's bullets, checked by `grep` across `docs/` and `experiments/`:

| Bullet | Result of `grep` outside this new file |
|---|---|
| *"`NormalizeContext.config_field` returns `Any`, so every handler re-checks types defensively"* | **no hit**. The only other `config_field` discussion is `EXP-002-addon-layer.md:307`, about `CollectContext.config_field`'s docstring — a different claim about a different type. |
| *"`test_addon_layer_direction.py` does **not** scan `tests/` … Nothing documents that scope"* | **no hit.** Twelve documents cite the test; none states its scan scope. |
| *"The `database` / `connection` fixtures **skip silently** when no cluster is reachable"* | **no hit.** |
| *"`addon_kit run` has no path that meaningfully runs a normalizer"* | `…-OBF-PRODUCT.md:517` says *"Not exercised, by me or by the worker"* — an absence of use, not an absence of a path. The register's form is the stronger claim. |

`[추론]` The four claims may well be true, and they are the kind of thing a P1 reader benefits
from. That is not the finding. The finding is that they sit under a blanket
`[확인 사실]` guaranteeing every row is review-traced, in a file created **specifically** to
answer a review that measured findings routed nowhere. `[확인 사실]` §7's own preamble labels
them `[측정]` and attributes them to *"workers writing against the documentation alone"* —
`grep` over TASK-004 and TASK-008 finds no such worker report. A `[측정]` names the input,
environment, and procedure that produced it; these name none.

`[추론]` This is exactly the question the brief asked — whether findings were added under cover
of registering them. The answer is yes for §7, and **no everywhere else**: §§1–6 and §8 all
trace, checked individually below.

**Reproduction.** `grep -rn "config_field" --include="*.md" docs experiments`;
`grep -rniE "skip(s|ped)? silently|cluster is (not )?reachable" --include="*.md" docs experiments`;
`sed -n '515,520p' experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`.

---

### R2-3 — Blocking, narrowly. The gate's own index does not know the register exists

**Claimed.** `P1-INHERITED-DEFECTS.md:16`, labelled `[결정]`: *"The P1 Entry Gate consumes this
file."*

**What contradicts it.** `[확인 사실]`
`docs/architecture-synthesis/README.md` is the directory's index. Its table (`:7–13`) lists five
outputs and does not list `P1-INHERITED-DEFECTS.md`. Its closing line (`:41`) enumerates what
the gate accepts:

```text
It starts only after the P0-B P1 Entry Gate accepts Architecture Synthesis, the disposition
register, `PoC Contract 0.1`, and the reconstruction plan.
```

`[확인 사실]` `AGENTS.md` states the same four. `[확인 사실]`
`P1-ENTRY-GATE-TEMPLATE.md` — the document that will be instantiated at the gate, whose
*"Blocking limitation"* column round 1 measured as empty — contains **no reference** to the
register either.

`[측정]` `grep -rn "P1-INHERITED-DEFECTS" --include="*.md" .` returns exactly two hits:
`docs/project-state.md:243` and `architecture-synthesis-v0.1.md:86`.

`[추론]` Two of two links are real and both are in documents a gate reader reads, so this is
weaker than F6 by a wide margin. It blocks because of what F6 was: a routing that terminates
where nobody looks. A reader who starts at `architecture-synthesis/README.md`, which is where
the gate's inputs are enumerated, is told the gate accepts four documents, one of which is the
disposition register — and the disposition register (F10, below) is still the one that
disagrees with the diff. The register's `[결정]` describes a consumption that no document
carrying the gate's definition has been updated to perform. `AGENTS.md`: *"Do not describe a
convention as a control."* Either the README and the template name it, or the sentence is a
statement of intent and should read as one.

`[추론]` Also worth the orchestrator's attention: the register carries no `Status` transition
into the README's table, so a reader cannot tell whether it is `DRAFT` like its neighbours. Its
own header says `ACCEPTED_FOR_POC`, which is a stronger status than the Architecture Synthesis
it hangs off (`DRAFT_FOR_GATE`), and per `README.md:15` *"Acceptance is the P1 Entry Gate's act
and not these documents'."* A document that declares itself accepted while its parent is a draft
is the case that line was written against. Stated, not ranked separately.

---

### R2-4 — Moderate. F3's widening was fixed in the synthesis and reintroduced in the register

`[확인 사실]` Synthesis Q2's replacement is correct and is the fix F3 asked for:

> The importer's three skip counters were all zero **on the delta the test checks them for; the
> second delta's counters were not asserted.**

`[확인 사실]` `P1-INHERITED-DEFECTS.md:132`, §8, written in the same session:

> **Malformed rows from a real producer.** **Both captured deltas were clean**; partial-validity
> handling is proved on self-authored fixtures.

`[측정]` `test_obf_real_data.py:346` binds and discards the second delta (`first, _second =
deltas`), asserts exactly one `addon.import.finished` event, and checks three counters on it.
`[추론]` "Both captured deltas were clean" is the sentence F3 was raised against, restored
verbatim in scope in a new file, three files away from its correction. It is very likely true;
it is not measured, and it is presented flatly in a register whose value is that its rows are
measured.

---

### R2-5 — Minor. Q5's headline counts one gap; its body carries two

`[확인 사실]` Headline: *"`YES` for tampering; `YES, NARROWLY` for evolution since 2026-08-20;
**and one new gap**."* `[확인 사실]` The body now closes with two `[측정]`/`[확인 사실]`
paragraphs: the `emitted_at`/`uuid4` tie-break, and — added by this round's F7 repair — *"**A
second identity gap belongs beside it** and this answer previously omitted it"* (collation).
`[추론]` The headline was not updated when the second was added. This is a small, direct
consequence of the F7 fix, and it matters only because round 1 established that the headline is
the line a gate reader quotes.

---

### R2-6 — Minor. One of the three named weaknesses left without being mentioned

`[확인 사실]` The paragraph Q2 replaces named three unexercised things: *"Encoding surprises,
embedded newlines in quoted strings, and duplicate row identities within one file."* The
replacement addresses encoding (the surrogate abort) and duplicate identity (retired by
construction, correctly). `[측정]` `grep -rn "embedded newline" --include="*.md"` finds it in
`evidence/B4-SCENARIO-COVERAGE.md:44` and in this report, and **nowhere in the new text**.

`[추론]` Not lost from the repository — B4 still carries it as a named gap, which is why this is
Minor rather than a second F7. The section now says *"What stays unexercised is narrower than
before"* and enumerates; one item of the original three left the enumeration silently.

---

### R2-7 — Moderate. F9's overstatement was not fixed and now appears in two files

`[확인 사실]` Synthesis Q8 still reads *"Two sources could have been a coincidence of pairing;
three **independently chosen** shapes are a pattern."* `[확인 사실]` `project-state.md:257` now
carries the same claim: *"Two sources could be coincidence; three **of independently chosen
shapes** is the pattern."*

`[확인 사실]` Two of the three shapes — a blog document and a DataLab trend point — come from
one provider, NAVER. `[추론]` The shapes are three; the choices are not independent. Round 1
raised this as part of F9; the repair round did not address it, and the consolidation propagated
it into `project-state.md`, which is the file a gate reader quotes from. The forward-looking
`[가설]` about the union growing one member per source shape is likewise unchanged and still
belongs in an Open Question.

---

## Round-1 findings: disposition after re-attack

### Closed

`[확인 사실]` **F1 — closed.** Contract limitation 5 is now struck alongside 3, with a
replacement that carries the narrowing (*"only the purge separates the two designs"*) and both
identity gaps. `[측정]` `grep -n "Raw-store evolution" contracts/experimental/POC-CONTRACT-0.1.md
docs/project-state.md docs/architecture-synthesis/architecture-synthesis-v0.1.md` no longer
returns three different answers. `[확인 사실]` I read all seven limitations: **1, 2, 4, 6 and 7
are consistent with the diff** — none of them asserts something the consolidation now measures.
`[확인 사실]` The replacement binds in substance: it names two gaps, says both bind, and does
not defer them. Its own line even records why it was struck late, which is the right kind of
record. The `[결정]`/`[측정]` split inside it still mixes roles — see F5, still open.

`[확인 사실]` **F2 — closed.** *"the test is no longer weaker than the question"* → *"the test is
**closer** to the question — not level with it."* The body now retires duplicate identity by
construction and states the encoding case at full severity. R2-6 is the residue.

`[확인 사실]` **F3 — closed in the synthesis.** Scope narrowed to one delta and the three named
counters. Reintroduced in the new file as R2-4.

`[확인 사실]` **F4 — closed, and this is the cleanest repair in the diff.** Q8 now separates the
two measurements explicitly and says so: three codes in both deltas *"whose normalized bodies
were never diffed against each other"*, and *"those same three `code`s were separately measured
by SRC-003 as having advanced `rev` and `last_modified_t` against the live API 23 hours later —
a **different comparison**, and no artifact states that the delta-to-delta pair shows the same
advance."* `[확인 사실]` Every element verifies: `SRC-003:334–338` reports `rev` advanced on 3
and `last_modified_t` on *"3 (the same 3)"*, naming `7891010974312`, `5906721183488`,
`4047196060247`; `…-OBF-REAL-DATA.md:31` confirms the delta A ∩ delta B overlap is *"exactly
those three"*. The two threes really are the same three codes, and the sentence now says which
comparison produced which.

`[확인 사실]` **F7 — closed.** Q5 gains the collation paragraph, correctly attributed to DP-019
D5 and to the same review that established the discrimination. R2-5 is the residue.

`[확인 사실]` **F6 — substantially repaired, blocked only by R2-3.** Checked as a destination:

| Round-1 routed finding | In the register? |
|---|---|
| TASK-011 B (presence not value; M5/M6/M7/M9 green) | §4 **B** — yes, with the fabricated values named |
| TASK-011 C (run-time computation not delta-proof) | §4 **C** — yes |
| TASK-011 D (softener survives) | §4 **D** — yes |
| TASK-011 E (`git status` unverifiable in a shared tree) | §4 **E** — yes, and it names the digest check a future packet should ask for |
| TASK-008 F2 (lineage by fixture coincidence) | §3 — yes |
| TASK-008 F3 (criterion 6 unfalsifiable) | §3 — yes |
| TASK-008 F4 (frozen `[가설]` unlabelled) | §3 — yes |
| TASK-008 F5 (`skipped_item_keys` tuple) | §3 — yes |
| TASK-008 F6 (two skip reasons indistinguishable) | §3 — yes |
| platform surrogate | §1, **its own section, first** — yes |

`[확인 사실]` **The surrogate row is not softened; it is stated harder than round 1 asked.** §1
carries the mechanism (`{"code":"a\ud800"}` → `UnicodeEncodeError` in `domain.store.canonical_body`),
the consequence in bold (*"One bad row ends the whole normalize run instead of being skipped and
counted"*), the exposure (`normalizer.obf.product` **and** `normalizer.naver.blog`, predating
both), and the judgment *"the most consequential row in this file … it converts a data-quality
event into an availability event."* `[측정]` The line reference is right this time:
`domain/store.py:132` is `def canonical_body`, and the function is unguarded — `json.dumps(...,
ensure_ascii=False).encode("utf-8")` raises on a lone surrogate. Round 1's `:145` pointed at the
`return`. `[확인 사실]` The `allow_nan` note beside it traces to `…-RULE-BASELINE.md:108`
(*"`ratio: NaN` → `canonical_body` emits the literal `NaN`"*).

`[확인 사실]` **The counter-signal is gone.** Synthesis Q2's reassuring paragraph now carries the
abort itself, in bold, with the link — the single sharpest item in round 1 is answered directly.

`[측정]` Rows I checked individually and could not break: §3's *"24 of 30 mutants died and
determinism held across seven hash seeds"* (`…-OBF-PRODUCT.md:531–533`, verbatim); §5's twelve
re-seals and two-of-three-older-payload (round 1 already verified); §5's purge/erasure cost
(OQ-004); §6's zero Korean sunscreen and toner rows and the 26.5% with no threshold
(`SRC-003:181`, `DP-027` D2, `DP-028:121`); §6's ODbL first-publication and the Open Food
Facts / Open Beauty Facts naming conflict; §8's DNS row
(`B4-SCENARIO-COVERAGE.md:114`, verbatim in substance). **§§1–6 and §8 trace. §7 does not
(R2-2).**

`[추론]` One label point on §1, stated and not ranked: `…-OBF-PRODUCT.md:515` records *"Whether a
real export row can contain a lone surrogate. The crash is `[측정]`; its reachability from real
data is `[가설]`."* Neither §1 nor Q2 carries that `[가설]`. The error runs toward making the
record look **worse** than the source, which is the opposite of this session's usual direction,
so it is noted rather than charged.

### Still open — what the orchestrator is carrying

`[확인 사실]` Stated plainly because the brief asked for it, not to pad the round.

| # | Status after round 2 |
|---|---|
| **F5** | **Open, and now doubled.** Limitation 3 is unchanged. Limitation 5 acquired the same shape: an entire struck heading with live binding content beneath it, and the same role mixing — its `[결정]` *"Two gaps replace it and both bind"* joins two measured gaps to a decision to treat them as binding. Two of seven items in *"Known limitations and unresolved semantics"* are now crossed out with constraints underneath. |
| **F9** | **Open, and propagated.** See R2-7. The `[가설]` about union growth is unchanged in the synthesis and now also in `project-state.md`. |
| **F10** | **Open, untouched.** `[측정]` `git status --porcelain` does not list `P0-ARTIFACT-DISPOSITION.md`. `[확인 사실]` Its `addons/importer.local.jsonl` row still reads *"reads a file this project authored"* — the claim contract limitation 3 was struck for. It still carries **no row** for `normalizer.obf.product` or `normalizer.rule.baseline`. `[추론]` This now matters more than in round 1: the disposition register **is** one of the four documents `README.md:41` says the gate accepts, and the new register (which the gate's list omits, R2-3) is the one that got written. |
| **F12** | **Mitigated, not closed.** `project-state.md`'s sentence is unchanged — *"the record now says so"*, past tense. `[확인 사실]` But `P1-INHERITED-DEFECTS.md` §2 row 1 states it correctly and openly: *"the record **is** emitted `clean: true` … What stands between a future rule missing its abstention branch and a wrong `clean` is **review**."* A reader who follows the new pointer gets the honest form. A reader who stops at `project-state.md` does not. |
| **F13** | **Open, unchanged.** *"Five of the ten cannot fire"* is still four distinct rules on `…-RULE-BASELINE.md:232–246`, and the reachability table R1 asked to be carried is still not carried. Minor and inherited, as in round 1. |
| **F14** | **Partly closed.** `[확인 사실]` Two of the five reach the register: the forgeable `BOUNDED` marker (§2) and the unbounded `source_item_key` (§2). **Three do not**: `output_contract_version` is unfalsifiable — *"routed to the gate by both reviews"*, and the one round 1 said most deserved it, while contract limitation 3's replacement still cites *"`normalizer.obf.product@0.1` at contract `0.3`"* as evidence; the determinism reading undecided against `PoC Contract 0.1` Invariant 9; and the by-path loader's `(mtime, size)` bytecode cache that produced two false `SURVIVED` verdicts, which bears on any future mutation evidence in this repository — including R2-1's. `[추론]` §2's heading, *"three stated gaps"*, reads as an exhaustive count of the rule baseline's open items. It is three of six. |
| **F7 residue** | **Open.** F-F — reversing member order in `_NormalizeRun.execute` leaves 112 of 113 green, so nothing on the host path asserts a normalizer received the sealed bytes — is carried nowhere, including in the new register. |
| **F8 residue** | **Open.** F-A — a one-statement collation migration *does* discriminate, falsifying the worker's `[가설]` — is still uncarried. It cuts in the design's favour, so it overstates nothing. |

## What I tried and could not break, round 2

- `[측정]` **The three attacks' `FAIL`/`PASS` verdicts.** `grep -n "Result" over the three
  rule-baseline reviews: `FAIL`, `FAIL`, and `FAIL`/`FAIL`/`PASS` across the coverage review's
  three rounds. *"Two of the three returned `FAIL`"* is right, and *"never on the rules
  themselves"* is close to the first report's own summary sentence.
- `[확인 사실]` **`26 + 11` unsummed, `20,000` gone.** `grep -rn "20,000\|20000"` over `docs`,
  `experiments`, `contracts` returns only the two unrelated `"A"*200000` hits. The blocking half
  of F11 is genuinely repaired; R2-1 is a different error in the replacement.
- `[확인 사실]` **The two threes in Q8 really are the same three codes**, so the unspliced
  sentence is not merely cautious — it is right. I tried to find a reading under which the new
  wording overstates and could not.
- `[확인 사실]` **Contract limitations 1, 2, 4, 6 and 7** were each read against the diff for a
  second F1. None contradicts it.
- `[확인 사실]` **Every one of the ten routed findings is in the register**, checked by name
  against the two reviews that raised them, not by keyword.
- `[측정]` **The register's §§1–6 and §8 numbers, digests, percentages and line references** all
  reproduce against their cited sources. The failure is confined to §7 and to one sentence in
  §8.

## Limits of this round

- `[확인 사실]` No test suite was run and no database was touched, per instruction. Every
  verification is against committed text, committed test source, `git diff HEAD`, and the one
  untracked subject file.
- `[확인 사실]` Nothing was staged, reset, committed, or edited. `git status --porcelain` shows
  the same three modified files and the same two untracked subject/report files it showed at the
  start. This report is the only thing I wrote, and it was appended.
- `[추론]` R2-1's survivor count is a lower bound. I enumerated the mutations the first review
  names as leaving the suite green; the review does not publish a full M01–M38 table, so a
  ninth survivor named nowhere is possible. The direction of the finding does not depend on the
  exact number: eight named survivors already falsify "four".
- `[추론]` R2-2 rests on `grep` over `docs/` and `experiments/`. A §7 bullet stated in wholly
  different words in a document I did not read could have been missed. The blanket
  `[확인 사실]` above it is falsified by one unsourced bullet, and I found at least three.

## Required follow-up

1. **R2-1 is blocking and is one sentence.** *"four others survived"* is the killed count; the
   sources name at least eight survivors of the twelve. And 16,000 is the second attack's, not
   the third's. `[추론]` Do not write a fourth version of this sentence without re-deriving both
   figures from the reports rather than from the previous version of the sentence — that is how
   this one was produced.
2. **R2-3 is blocking and is two lines.** Either add the register to
   `architecture-synthesis/README.md`'s table and to `:41`'s list of what the gate accepts, or
   change the register's `[결정]` to say what is true today: that it is offered to the gate, not
   consumed by it. Also reconcile its `ACCEPTED_FOR_POC` header against `README.md:15`.
3. **R2-2 is cheap.** Narrow the `[확인 사실]` to the sections it holds for, and either source
   §7's four bullets or relabel them as this session's observations with the procedure that
   produced them.
4. `[추론]` **The pattern round 1 named has not reversed, but it has thinned.** Round 1: every
   error made the record read better than the work. Round 2: R2-1 and R2-7 still run that way,
   R2-4 and R2-6 are scope residue, and the surrogate row runs the *other* way — stated harder
   than its source. `[추론]` The repairs are honest work. What is not yet reliable is the
   arithmetic in the sentences written to replace bad arithmetic, and that is the third time in
   this consolidation that the fix, not the original, has been the defect.

---

# Round 3 — re-attack of the round-2 repairs, 2026-08-20

- Subject: `git diff HEAD` (`2fb0f73`) over `docs/project-state.md`,
  `contracts/experimental/POC-CONTRACT-0.1.md`,
  `docs/architecture-synthesis/architecture-synthesis-v0.1.md`,
  `docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md`, plus the untracked
  `docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`.
- Reviewer: `adversarial-reviewer`, same session lineage as rounds 1 and 2. Rounds 1 and 2
  stand as written and are not amended.
- Scope: exactly the items the round-3 brief named. No new area was opened.

## Result

**`FAIL`**, narrowly and for the fourth time in the same place: not in the claim, but in the
sentence written to repair the claim.

`[확인 사실]` **R2-1 is closed.** Every figure in the rewritten mutation sentence verifies
against the three reports, including the two the previous version got wrong. This is the first
version of that sentence that is arithmetically correct, and the method that produced it —
re-deriving from the reports — is visible in the result.

`[추론]` **R2-3 is half closed and still blocks**, for a reason that is not the one round 2
gave. The register's own `[결정]` is now honest: it says plainly that it is not one of the four
artifacts the gate is defined to accept and that adding a fifth is the owner's call. That is the
right answer. But (a) `docs/project-state.md:243` **still carries the sentence R2-3 was raised
against** — *"which the P1 Entry Gate consumes"* — so the two standing-record documents now
state opposite things about the same process, with the false one in the file a gate reader
quotes; and (b) the paragraph written to replace the false claim contains three false
reachability statements of its own.

## Round-3 findings

| # | Where | Claim | Severity | Class |
|---|---|---|---|---|
| R3-1 | `project-state.md:243–245` vs `P1-INHERITED-DEFECTS.md:18–26` | *"which the P1 Entry Gate consumes"* survives in `project-state.md` after being retracted in the register; the two contradict each other | **Blocking**, narrowly | scope |
| R3-2 | `P1-INHERITED-DEFECTS.md:23–26` | the replacement's own reachability `[결정]` is wrong in three parts: Q5 carries no link, "three of those four" is two, and the `project-state.md` pointer is in §4 | **Major** | evaluation |
| R3-3 | `P1-INHERITED-DEFECTS.md:28–29` vs `:121–126` | the unnarrowed blanket *"Every row traces to a committed attack report"* now contradicts §7's new preamble; two §7 bullets still trace to neither, one traces to an attack report, one inverts its source | **Moderate** | evaluation |
| R3-4 | `P0-ARTIFACT-DISPOSITION.md:45` vs `P1-INHERITED-DEFECTS.md:46` | *"three unenforced properties … §2"* against §2's new heading *"six stated gaps"* — introduced by the F14 repair | **Moderate** | specification |
| R3-5 | `P1-INHERITED-DEFECTS.md:54` | the determinism-strength row cites the first review; the question is the second's | **Minor** | evaluation |
| R3-6 | `P1-INHERITED-DEFECTS.md:19` | *"`README.md` and `AGENTS.md` name four"* — `AGENTS.md` names three | **Minor** | evaluation |
| R3-7 | `P0-ARTIFACT-DISPOSITION.md:32` | `Normalized Schema 0.2` row untouched while the same edit adopts Schema 0.3 — the same class as F10, in the same file F10 repaired | **Minor** | specification |

---

### R2-1 — closed. Every figure now traces

**Claimed.** `docs/project-state.md`, hypothesis 6:

> `[측정]` The first applied 38 mutations and killed all 26 that were aimed at rule behaviour;
> **the survivors were outside rule behaviour and are what its `FAIL` was about**, and its own
> report publishes no survivor total, so none is stated here. The second killed 11 more and ran
> 16,000 differential comparisons with zero divergence; the third ran 4,000 more, also zero.

`[측정]` Checked one clause at a time against the three reports:

| Clause | Source | Verdict |
|---|---|---|
| 38 mutations applied | `…-RULE-BASELINE.md:26` — *"38 mutations applied and restored, one at a time"* | holds |
| all 26 aimed at rule behaviour killed | `:69` — *"26 of 26 rule-behaviour mutations were killed"* | holds |
| survivors were outside rule behaviour | follows from `:69`; the eight named survivors (M09, M13, M28, M29, M30, M31, M35, M36) are all outside the 26 | holds |
| the report publishes no survivor total | `grep -niE "surviv\|killed\|mutation"` over the whole report returns no total; the only counts are 38, 26 of 26, and `:417`'s single *"M32 is killed"* | **holds** |
| the second killed 11 more | `…-RULE-BASELINE-R2.md:67` — *"Eleven mutations of my own … Eleven applied, eleven killed. No `SURVIVED`"*; the m1–m11 table at `:70–82` | holds |
| the second ran 16,000 comparisons | `:139` *"No, on 16 000 differential comparisons"*, `:327`, `:389` — the **second** attacker's own experiment | **holds; the round-2 misattribution is corrected** |
| the third ran 4,000 more, zero | `…-COVERAGE-CLAIM.md:151`, `:158` — *"differential comparisons: 4000, divergences: 0"* | holds |
| three attacks, two returned `FAIL` | `…-RULE-BASELINE.md:7` `FAIL`; `…-R2.md:8` `FAIL`; `…-COVERAGE-CLAIM.md:655` `PASS` in round 3 | holds |

**On the brief's question: is refusing to state a survivor total honest, or a dodge?**

`[추론]` **Honest, and understated rather than evasive.** The report genuinely publishes no
total, and inventing one would have been the fourth arithmetic error in this sentence's history.
But the record can say more than it does without deriving anything: `38 − 26 = 12` is the
report's own arithmetic, and the report **names eight of those twelve** as leaving the suite
green. *"At least eight of the twelve non-rule-behaviour mutations survived, each a named test
gap"* is a statement the source supports directly.

`[추론]` What stops this from being a dodge is the clause beside it: *"the survivors … are what
its `FAIL` was about"*. A reader told that the survivors caused the `FAIL` cannot infer they
were trivial. The omission understates a number; it does not misdirect. Compared to the two
previous versions — one inverted, one misattributed — this is the correct direction of caution.

`[추론]` One residue, stated and not ranked. *"…are what its `FAIL` was about"* is not the whole
of it. `…-RULE-BASELINE.md`'s F2 (`clean: true` for a record a rule never evaluated, class
`implementation`, found by probe A/B) and F4 (five of ten rules cannot fire, class `goal`, found
by source reading) are Major findings behind that `FAIL` and are **not** mutation survivors.
Both are carried elsewhere in the same `project-state.md` bullet, so nothing is lost; the
sentence is narrower than the report, not wider. Noted because rounds 1 and 2 found every error
running the other way.

---

### R2-3 — half closed. See R3-1 and R3-2

`[확인 사실]` **The retraction itself is correct and is the right answer to the brief's
substance question.** `P1-INHERITED-DEFECTS.md:18–22` now reads:

> `[확인 사실]` **This file is not one of the artifacts the gate is defined to accept.**
> [`README.md`](README.md) and `AGENTS.md` name four … and adding a fifth is an owner decision,
> not a thing this file may assert about itself.

`[확인 사실]` `docs/architecture-synthesis/README.md:41` names Architecture Synthesis, the
disposition register, `PoC Contract 0.1`, and the reconstruction plan, and does not name this
file. The retraction agrees with it.

**Is a register the gate is not defined to accept a real destination, or an honest label on a
broken route?** `[추론]` **Both, and the honest label is worth having.** F6's defect was that
ten findings terminated at a document nobody had written; that is fully repaired and stays
repaired — every routed finding is in the register and reachable from documents the gate does
accept. What is *not* repaired is that the gate's definition still does not mention it, so a
reader who works from the gate's inputs rather than from the synthesis can complete the gate
without ever opening it. The register now says so instead of claiming otherwise, which converts
a false statement into a stated open item — and per `AGENTS.md` that is exactly the right
handling for a consequential direction the orchestrator may not decide alone. It blocks only
because of R3-1 and R3-2, not because the retraction is wrong.

---

### R3-1 — Blocking, narrowly. The retracted sentence is still standing in `project-state.md`

**Claimed.** `docs/project-state.md:243–245`, labelled `[결정]`, **unchanged by this round**:

> `[결정]` **Findings that P0 recorded rather than repaired are registered in**
> [`P1-INHERITED-DEFECTS.md`](architecture-synthesis/P1-INHERITED-DEFECTS.md), **which the P1
> Entry Gate consumes.**

**What contradicts it.** `[확인 사실]` `P1-INHERITED-DEFECTS.md:21–22`, written in the same
session: *"An earlier revision of this paragraph said 'the P1 Entry Gate consumes this file',
which claimed a process nobody accepted."* `[측정]` `git diff HEAD -- docs/project-state.md`
does not touch lines 243–245 in this round; the clause is byte-identical to the round-2 subject.

`[추론]` This is round 1's **F1** repeating in a new file pair: a claim retired in one document
and left standing in another, with no cross-reference reconciling them. It is worse here than F1
was, because the surviving copy is the *false* one and it lives in `docs/project-state.md` —
the file every other document in this consolidation treats as the standing record, and the file
round 1 established is what a gate reader quotes. A reader who reads only `project-state.md` is
told the gate consumes a document the register itself says the gate is not defined to accept.

`[추론]` It is Blocking rather than Major on round 2's own calibration: R2-3 blocked on a
statement of process nobody accepted, and that statement is still in the repository, in the
higher-traffic of the two files.

**Reproduction.**
`sed -n '242,246p' docs/project-state.md`;
`sed -n '18,26p' docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`;
`git diff HEAD -- docs/project-state.md | grep -c "Entry.*Gate consumes"` → `0` (the clause is
in neither the `+` nor the `-` side of this round's hunks below §4).

---

### R3-2 — Major. The paragraph written to fix a reachability finding states three false reachabilities

**Claimed.** `P1-INHERITED-DEFECTS.md:23–26`, labelled `[결정]`:

> It is reachable instead from **three of those four**: the Architecture Synthesis links it from
> **questions 2 and 5**, the disposition register links it from two add-on rows, and
> `project-state.md` **§5** points at it.

`[측정]` `grep -rn "P1-INHERITED-DEFECTS" --include="*.md" .` over the whole tree returns four
inbound links outside the register and this report:

```text
docs/project-state.md:243
docs/architecture-synthesis/architecture-synthesis-v0.1.md:92
docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:44
docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:45
```

**Defect 1 — question 5 does not link it.** `[측정]` `architecture-synthesis-v0.1.md`'s only
occurrence is line **92**. `grep -n "^### "` puts question 2 at line 42 and question 3 at line
96, so line 92 is inside **question 2**. Question 5 spans lines 137–177; I read all forty-one
lines of it. It links `OQ-004`, `TASK-005`, and `DP-019`, and **does not link the register at
all**. The paragraph claims two entry points from the synthesis and there is one.

**Defect 2 — "three of those four" is two of those four.** `[확인 사실]` The four named in the
preceding sentence are Architecture Synthesis, the disposition register, `PoC Contract 0.1`, and
the P1 reconstruction plan. The three enumerated are Architecture Synthesis, the disposition
register, and **`project-state.md` — which is not one of the four**. `[측정]` Neither
`contracts/experimental/POC-CONTRACT-0.1.md` nor `P1-RECONSTRUCTION-PLAN.md` appears in the grep
above; neither links the register. So the true statement is *two* of the four, plus
`project-state.md` outside the set.

**Defect 3 — the `project-state.md` pointer is in §4, not §5.** `[측정]`
`grep -n "^## " docs/project-state.md` puts `## 4. Accepted for P0` at line 125 and
`## 5. Architecture hypotheses` at line **248**. The pointer is at line **243** — the last
paragraph of §4. A gate reader sent to §5 finds the hypotheses and no pointer.

`[추론]` The severity is Major rather than Minor because of what this paragraph is *for*. Round 2
blocked on a routing claim that could not be followed. The repair is a routing claim that also
cannot be followed, in a `[결정]` — a label that per `evidence-labels.md` records an adopted
choice, not an unverified guess about where links point. `[추론]` And the failure mode is
identical to R2-1's: the sentence was written from an intended state rather than re-derived by
following the links. That is now the fourth occurrence.

**Reproduction.** `grep -rn "P1-INHERITED-DEFECTS" --include="*.md" .`;
`grep -n "^### " docs/architecture-synthesis/architecture-synthesis-v0.1.md`;
`grep -n "^## " docs/project-state.md`.

---

### R3-3 — Moderate. R2-2's repair added a caveat without narrowing the blanket it contradicts

**Claimed.** `P1-INHERITED-DEFECTS.md:28–29`, **unchanged**:

> `[확인 사실]` Every row traces to a committed attack report. Nothing was added here that a
> review did not find.

`P1-INHERITED-DEFECTS.md:121–126`, **new this round**:

> `[확인 사실]` **These trace to worker handoffs, not to attack reports** — unlike every other
> section of this file … recorded in [TASK-008] and [TASK-006].

`[추론]` The two `[확인 사실]` are in direct contradiction inside one file, ninety lines apart.
The repair narrowed §7's own claim and left the blanket that governs §7 unamended, so the file
now asserts both that every row is attack-traced and that §7's rows are not. Whichever a reader
reaches first is the one they carry.

**And §7's new attribution does not hold for four of its six bullets.** `[측정]` Checked against
both named packets:

| Bullet | Result |
|---|---|
| `addon_kit run` has no path that meaningfully runs a normalizer | **traces.** `TASK-008:245–250` — *"not used to exercise this add-on end-to-end; per `addon-authoring.md`, it is not integration evidence for a normalizer in any case."* Round 2's objection is answered. |
| `NormalizeContext.config_field` returns `Any` | **no source.** `grep -rn "config_field" --include="*.md" docs experiments` returns four hits, none in TASK-008 or TASK-006; the nearest is `EXP-002-addon-layer.md:307`, about `CollectContext.config_field`'s docstring. Unchanged from round 2. |
| `test_addon_layer_direction.py` does not scan `tests/` | **no source.** TASK-008's three mentions (`:114`, `:138`, `:187`) are that the test *passes*; neither packet states its scan scope. Unchanged from round 2. |
| the `database`/`connection` fixtures **skip silently** | **inverts its source.** `TASK-008:236–241`: *"that one class will report as `SKIPPED` via `platform_database`'s own skip rather than as a failure **or a silent pass**."* The handoff's point is that the skip is *visible*; the register calls it silent. The consequence the register draws — *"a criterion can appear covered while never executing"* — is the handoff's real worry and is fair; the adjective is not. |
| *"Neither the contract nor `canonical_body` bounds a body or requires strict JSON"* | **traces to an attack report**, `…-RULE-BASELINE.md` F11 — which the new sentence *"not to attack reports"* explicitly denies. |
| the OQ-013 bullet | a pointer to an Open Question, neither handoff nor attack report. |

`[추론]` Downgraded from round 2's Major to Moderate: `addon_kit run` is now sourced, and the new
preamble at least tells a reader that §7 is self-reported and why that matters — which is the
substantive half of what R2-2 asked for. What remains is that the sentence naming the source is
wrong for four of six bullets, and the blanket above it was not narrowed.

---

### R3-4 — Moderate. The F14 repair updated a heading and not the row that points at it

`[확인 사실]` `P1-INHERITED-DEFECTS.md:46` now reads `## 2. `normalizer.rule.baseline@0.1` — **six** stated gaps`,
and the table beneath it has six rows. That is the F14 repair and it is correct.

`[확인 사실]` `docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:45`, added by **this same
diff**: *"Its **three** unenforced properties are in [P1-INHERITED-DEFECTS](P1-INHERITED-DEFECTS.md) §2."*

`[추론]` The row was written against §2's previous heading (*"three stated gaps"*, the wording
round 2 measured) and not revisited when §2 went to six. A gate reader following the disposition
register — one of the four documents the gate **is** defined to accept — is told to expect three
items and finds six, with no way to know which three the register meant. `[추론]` Same class as
round 1's F1 and this round's R3-1: a number retired in one file and left standing in another,
both edited in the same session.

**Reproduction.** `grep -n "unenforced properties" docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md`;
`grep -n "^## 2\." docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`.

---

### R3-5 — Minor. The determinism row cites the wrong review

`[확인 사실]` `P1-INHERITED-DEFECTS.md:54` attributes *"Determinism as this add-on holds it …
whether every add-on is held to it … is stated nowhere"* to `…-RULE-BASELINE.md`.

`[측정]` `grep -c "Invariant 9" experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md`
→ **0**. The question is the **second** review's: `…-RULE-BASELINE-R2.md:114`
(*"`POC-CONTRACT-0.1`'s Invariant 9 … does not name a process"*), `:343–344`, and `:421–423`,
which routes it to the gate by name. The first review's determinism finding (F3) is a different
claim — that the *proof* was blind to hash-order nondeterminism — and it was closed by TASK-006
(m8, m3b).

`[추론]` Minor because the substance is right and the correct source is one file away. It is
recorded because this register's entire value proposition is that each row names the artifact
that measured it; a row that names the wrong one is a route a reader follows and abandons.

---

### R3-6 — Minor. `AGENTS.md` names three of the four, not four

`[확인 사실]` `P1-INHERITED-DEFECTS.md:19`: *"[`README.md`](README.md) and `AGENTS.md` name four
— Architecture Synthesis, the disposition register, `PoC Contract 0.1`, and the P1
reconstruction plan."*

`[확인 사실]` `README.md:41` names four. `AGENTS.md`'s P0 boundary names **three**: *"until the
P0-B P1 Entry Gate accepts `PoC Contract 0.1`, artifact disposition, and the P1 reconstruction
plan."* Architecture Synthesis is not in `AGENTS.md`'s list.

`[추론]` Minor and in the safe direction — the register credits the gate's definition with more
than it says, which makes its own exclusion look more considered, not less. Recorded because it
sits in the same sentence as R3-2's count error, and both are the same act: writing a set's size
without enumerating the set.

---

### R3-7 — Minor. F10's file still carries one stale row of the same class F10 was

`[확인 사실]` `P0-ARTIFACT-DISPOSITION.md:32`, untouched by this diff:

> | `Normalized Schema 0.2` | DP-019 + DP-021 | … | `PROMOTE` | … | The discriminated-union
> form, carrying the refutation of the strong hypothesis with it |

`[확인 사실]` The same diff establishes, in three places, that DP-028 adopted **Schema 0.3** and
that `normalizer.obf.product` is *"Schema 0.3's only producer"* — the row directly above it, at
`:44`, says so. So the register's promoted-artifact row names a superseded version while an
add-on row two lines down names its successor.

`[추론]` Minor, not Moderate: the row is not *false* — Schema 0.2 existed and its form is what is
promoted — but `PROMOTE` on a version string the same file supersedes is the exact reading error
F10 was raised to prevent. `[측정]` I checked the rest of this file for the same class and found
none: all nine add-ons under `experiments/integrated-p0/addons/` now have a row
(`ls addons/` → 9; `grep -n "^| \`addons/"` covers `collector.naver.*` (3),
`normalizer.naver.*` + `conformance` (3), `importer.local.jsonl`, `normalizer.obf.product`,
`normalizer.rule.baseline`), which is the completion F10 asked for.

---

## Round-2 findings: disposition after re-attack

### Closed

`[확인 사실]` **R2-1 — closed.** Every figure re-derived from the three reports; table above.
The two defects round 2 named are both gone and no new figure was introduced.

`[확인 사실]` **R2-4 — closed.** `P1-INHERITED-DEFECTS.md:149–153` now reads *"The importer's
three skip counters were all zero **on the delta the test checks them for; the second delta's
counters were not asserted**"* — the synthesis's wording, verbatim in scope. *"Both captured
deltas were clean"* is gone. `[측정]` `grep -n "Both captured deltas"` returns no hit outside
this report.

`[확인 사실]` **R2-5 — closed.** Q5's headline is now *"`YES` for tampering; `YES, NARROWLY` for
evolution since 2026-08-20; **and two new identity gaps**"*, and the body carries exactly two:
the `emitted_at`/`uuid4` tie-break and the collation gap.

`[확인 사실]` **R2-6 — closed, and better than asked.** Q2 gains a dedicated `[확인 사실]`
paragraph: *"The third weakness that paragraph named — embedded newlines inside quoted strings —
is still unexercised and is not retired."* `[측정]` It verifies against the add-on's own source:
`addons/importer.local.jsonl/handler.py:13–15` carries the `[가설]` *"One line is one record.
False for a JSONL file with embedded newlines inside a string … such a line is counted as
malformed rather than silently joined to its neighbour"*, and `:45` is
`for line_number, raw_line in enumerate(opened.body.splitlines(), start=1)`. The register's §8
carries the same gap. All three of the replaced paragraph's named weaknesses are now accounted
for, each with its own disposition.

`[확인 사실]` **R2-7 / F9 — closed on the overstatement.** Both files now carry the caveat:
synthesis Q8, *"three is a pattern — with the caveat that two of the three come from one
provider, so what varies across them is record shape, not provider"*; `project-state.md`
hypothesis 5, the same clause. The word *"independently"* is gone from both. `[추론]` Residue,
unchanged and stated not ranked: F9's other half — the forward-looking `[가설]` about the union
growing one member per source shape — is still inside a charter answer rather than an Open
Question. It carries a falsification condition, so this remains a placement point.

`[확인 사실]` **F10 — closed but for R3-7.** The importer row now reads *"Since 2026-08-20 it
also reads a real external file"* with the DP-027 link and names the earlier claim it replaces;
rows exist for `normalizer.obf.product` and `normalizer.rule.baseline`. `[측정]` Both new rows
verify: `grep -c "def test_" tests/test_normalizer_obf_product.py` → **41**, matching *"(41
cases)"*; §3 lists exactly five weak assertions (F2–F6), matching *"its five weak assertions"*;
`normalizer.rule.baseline` is the only add-on that emits verdicts. The `§2` count is R3-4.

`[확인 사실]` **F14 — closed on the three additions, and six is now defensible.** All three
additions trace:

| Addition | Source | Verdict |
|---|---|---|
| `output_contract_version` unfalsifiable | `…-RULE-BASELINE.md` F7 (*"AC5 is not checkable: no contract defines this `0.1`, no validator exists"*); `…-R2.md:423` routes it to the gate by name | holds |
| determinism strength vs Invariant 9 | `…-R2.md:114`, `:343`, `:421` | holds — cited to the wrong report, R3-5 |
| `(mtime, size)` bytecode cache | `…-RULE-BASELINE.md` F13 and `:413–417` (*"reported **M31** and **M32** as `SURVIVED` … M32 is killed"*) | holds |

`[측정]` I checked the cross-reference the `output_contract_version` row makes — that it *"is
nonetheless cited as evidence in `PoC Contract 0.1`'s replacement for limitation 3"*. It is
correct and not a conflation: `addons/normalizer.obf.product/addon.toml:19` is
`output_contract_version = "0.3"`, so limitation 3's *"`normalizer.obf.product@0.1` at contract
`0.3`"* really is the field the register says is unfalsifiable. `[확인 사실]` And R1 F7's
underlying point verifies: `grep -rn "output_contract_version" addons/*/addon.toml` shows
`normalizer.conformance`, `normalizer.rule.baseline`, and `normalizer.naver.blog` all declaring
`"0.1"` for three unrelated body shapes.

`[추론]` **Is six the true count?** Close enough to stand, with one open item outside it. The
three residues round 2 listed as uncarried resolve as follows:

| Residue | Status |
|---|---|
| **F7's residue, F-F** — reversing member order in `_NormalizeRun.execute` leaves 112 of 113 green, so nothing on the host path asserts a normalizer received the sealed bytes | **still uncarried.** `[측정]` `grep -rn "_NormalizeRun" --include="*.md" docs` returns no hit. Not in §1, not in §5, not in the synthesis. This is a *platform* gap, not a rule-baseline one, so §2's six is not wrong because of it — but §1 is the section it belongs in and it is not there. **Moderate, carried forward from round 1.** |
| **F8's residue, F-A** — a one-statement collation migration *does* discriminate, falsifying the worker's `[가설]` | **still uncarried.** Cuts in the design's favour, so it overstates nothing. Minor. |
| **F13** — *"five of the ten cannot fire"* is four distinct rules on `…-RULE-BASELINE.md:232–246` | **still uncarried and unchanged.** `project-state.md` hypothesis 6 still reads *"Five of the ten cannot fire"*, and the reachability table R1 asked to be carried is still carried nowhere. Minor and inherited, as in rounds 1 and 2. |

`[확인 사실]` **F5 — closed.** The limitation list gains the preamble the finding asked for:
*"Two of the seven are struck through and still binding, which is a shape worth naming rather
than leaving to be inferred. A struck heading means the limitation as first written no longer
holds; the text beneath it is not commentary but the constraint that replaced it, and it
binds."* `[확인 사실]` The count verifies — seven numbered items, 3 and 5 struck. `[확인 사실]`
The preamble also concedes the form is a compromise and names `0.2` as where it should be fixed,
which is the honest version of a repair that could not be made inside this edit's scope.
`[추론]` The role-mixing half of F5 is unaddressed inside the two replacement items, but the
preamble makes the *structure* legible, which was the load-bearing half. Not carried forward.

`[확인 사실]` **F12 — closed on the new claim, unchanged on the old one.** Hypothesis 4 now adds:
*"It reached that state through a `FAIL` and a rework: TASK-003's first attempt did not
discriminate, and TASK-005 is the experiment that does."* `[측정]` Both halves verify —
`TASK-003-snapshot-survives-raw-store-evolution.md:3` is `Status: REWORK`, `:254` is
`Result: FAIL`, `:260` is *"What failed is discrimination"*, and `:256` names TASK-005 as the
successor. That is a `FAIL` carried into the standing record, which is the first time this
consolidation has done it. `[추론]` Round 1's F12 was about a *different* sentence — hypothesis
6's *"`clean: true` **could** be emitted … and the record now says so"* — which is unchanged.
It remains **mitigated, not closed**: the register's §2 row 1 states it correctly and openly
(*"the record **is** emitted `clean: true` … What stands between a future rule missing its
abstention branch and a wrong `clean` is review"*), so a reader who follows the pointer gets the
honest form. Same disposition as round 2.

### Still open

| # | Status after round 3 |
|---|---|
| **R2-2** | **Downgraded to Moderate, open.** See R3-3. |
| **R2-3** | **Half closed, still blocking** via R3-1 and R3-2. |
| **F7 residue (F-F)** | **Open, Moderate.** Uncarried anywhere, including §1 of the register where it belongs. |
| **F8 residue (F-A)** | **Open, Minor.** Overstates nothing. |
| **F13** | **Open, Minor, inherited.** *"Five of the ten"* is four; the reachability table is still not carried. |
| **F9's `[가설]` placement** | **Open, Minor.** Forward-looking design analysis inside a charter answer. |
| **Register status header** | **Open, Minor, and now sharper.** `P1-INHERITED-DEFECTS.md:3` is still `Status: ACCEPTED_FOR_POC` while `:18` says the gate is not defined to accept it, and `README.md:15` says *"Acceptance is the P1 Entry Gate's act and not these documents'. A draft that declared itself accepted would be the gate deciding its own outcome."* A file that retracts its acceptance in prose and keeps it in its header. Round 2 asked for this reconciliation; it was not made. |

## What I tried and could not break, round 3

Stated plainly, because it is most of the result.

- `[측정]` **The whole mutation sentence.** Eight clauses, checked one at a time against three
  reports. Every one holds. I specifically tried to find a survivor total in
  `…-RULE-BASELINE.md` that would falsify *"publishes no survivor total"* — `grep` for
  `surviv`, `SURVIVED`, `killed`, and `mutation` across the file returns 14 lines and none is a
  total. The claim is true.
- `[측정]` **The 16,000 attribution, reversed.** I checked whether 16,000 could belong to the
  third attack after all. `…-COVERAGE-CLAIM.md` contains 4,000 and no other comparison count;
  `…-R2.md` contains 16,000 at `:139`, `:327`, and `:389`, all inside the second attacker's own
  procedure. The new attribution is right and the round-2 one was wrong.
- `[측정]` **The embedded-newlines paragraph against the add-on's source**, not just against the
  documents. `handler.py:13–15` and `:45` say what Q2 says they say.
- `[측정]` **Hypothesis 4's `FAIL`-and-rework claim** against TASK-003's own header and Review
  section. It holds, and it is the first `FAIL` this consolidation has carried into
  `project-state.md` rather than summarized past.
- `[측정]` **The disposition register's completeness.** Nine add-ons on disk, nine rows. F10's
  substantive ask is met; R3-7 is a different row.
- `[측정]` **The `output_contract_version` cross-reference**, which looked like a conflation of
  schema version with contract version and is not — `addon.toml:19` settles it.
- `[확인 사실]` **The seven-item / two-struck count** in the contract preamble, read line by line.
- `[확인 사실]` **R2-4, R2-5, R2-6, R2-7 are all genuinely closed**, each checked in both files
  rather than in the one the finding named.

## Limits of this round

- `[확인 사실]` No test suite was run and no database was touched, per instruction. Every
  verification is against committed text, committed test and add-on source, `git diff HEAD`,
  and the one untracked subject file.
- `[확인 사실]` Nothing was staged, reset, committed, or edited. `git status --short` shows the
  same four modified files and the same two untracked subject/report files it showed at the
  start. This report is the only thing I wrote, and it was appended.
- `[추론]` R3-3 rests on `grep` over `docs/` and `experiments/` plus a full read of both named
  packets' handoff sections. A §7 bullet stated in wholly different words in a document I did
  not read could have been missed.
- `[추론]` R3-2's defect 1 rests on reading question 5 in full and on a whole-tree `grep`. If a
  link to the register is intended for question 5, it is not in the file.

## Required follow-up

1. **R3-1 is blocking and is four words.** Delete *"which the P1 Entry Gate consumes"* from
   `project-state.md:244` and replace it with the register's own retraction, or link to it.
   `[추론]` It is the same defect as round 1's F1 — a claim retired in one file and left in
   another — and it is the third time in this consolidation that a repair has been applied to
   one of two files that carry the same sentence. A `grep` for the retired wording before
   declaring a retraction complete would have caught all three.
2. **R3-2 is Major and is one sentence.** Follow the four links before restating them: the
   synthesis links it once (question 2, not 5), the disposition register twice, and
   `project-state.md` §4 — which is not one of the four artifacts, so the count is two of four
   plus one outside the set.
3. **R3-3 and R3-4 are cheap.** Narrow `:28`'s blanket to §§1–6 and §8; fix the disposition
   row's *"three"* to *"six"*.
4. `[추론]` **On the pattern, which has now changed direction.** Rounds 1 and 2 found every error
   running one way: the record read better than the work. Round 3 does not. R2-1's residue
   understates, R3-6 is in the safe direction, and the new `FAIL`-and-rework sentence in
   hypothesis 4 carries a failure the record previously smoothed over. What persists is not
   optimism but a **method** defect: four rounds running, the sentence written to repair a
   claim has been produced from the intended state rather than re-derived from the artifact,
   and it has been wrong each time in a way one `grep` would have caught. `[추론]` That is the
   thing worth the orchestrator's attention now — not the direction of the errors, which has
   corrected, but the absence of a verification step between writing a corrective sentence and
   publishing it.

---

# Round 4 — re-attack of the round-3 repairs

- Date: 2026-08-20
- Subject: `git diff HEAD` (`2fb0f73`) over `docs/project-state.md`,
  `docs/architecture-synthesis/architecture-synthesis-v0.1.md`,
  `docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md`,
  `contracts/experimental/POC-CONTRACT-0.1.md`, plus the untracked
  `docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`
- Reviewer: attacker, rounds 1–4, no packet

## Result

**`PASS`.** `[측정]` R3-1 (Blocking), R3-2 (Major), and R3-4 (Moderate) are closed and were each
re-derived from the artifacts rather than from the repair's own description. F-F is carried, at
the severity its source gave it. Nothing open is blocking and nothing open is Major.

| # | Where | What | Severity | Class |
|---|---|---|---|---|
| R4-1 | `P1-INHERITED-DEFECTS.md:31–33` | The scoped traceability sentence is false in **both** directions: §8 traces to no attack report, and §7 now contains two attack-report items | **Moderate** | evidence |
| R4-2 | `P1-INHERITED-DEFECTS.md:149–152` | F-F, a platform finding, is filed in the section titled "gaps the add-on authors hit" | Minor | placement |

`[추론]` **The method defect round 3 named has corrected, at least once.** Every clause of the
reachability sentence now survives being followed link by link, including the two clauses round 3
had to correct twice. The register also now records what its earlier revisions claimed and why
they were wrong, which is the first time in four rounds that a repair has carried its own
retraction rather than quietly overwriting.

## The reachability claim — checked clause by clause

`P1-INHERITED-DEFECTS.md:23–28`, labelled `[결정]`:

> It is reachable instead from **two** of those four — the Architecture Synthesis, from
> questions 2 and 5, and the disposition register, from two add-on rows — plus a pointer in
> `project-state.md` §4, which is not one of the four. `PoC Contract 0.1` and the P1
> reconstruction plan do not link it.

`[측정]` `grep -rn "P1-INHERITED-DEFECTS" --include="*.md" .`, excluding the register and this
report, returns exactly five inbound links:

```text
docs/project-state.md:243
docs/architecture-synthesis/architecture-synthesis-v0.1.md:92
docs/architecture-synthesis/architecture-synthesis-v0.1.md:179
docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:44
docs/architecture-synthesis/P0-ARTIFACT-DISPOSITION.md:45
```

| Clause | Verdict |
|---|---|
| synthesis links it from **question 2** | `[측정]` **holds.** `grep -n "^### "` puts Q2 at 42 and Q3 at 96; `:92` is inside Q2. |
| synthesis links it from **question 5** | `[측정]` **holds, and is new this round.** Q5 spans 137–180 (Q6 at 181); `:179` — *"Both gaps, and the erasure cost above, are registered in … §5"* — is inside it. This is the clause round 3 falsified; the link now exists. `[측정]` And the target is right: register §5 carries both identity gaps and the erasure cost. |
| disposition register links it from **two add-on rows** | `[측정]` **holds.** `:44` (`normalizer.obf.product` → §3) and `:45` (`normalizer.rule.baseline` → §2). No third. |
| `project-state.md` pointer is in **§4** | `[측정]` **holds.** `## 4. Accepted for P0` is line 125, `## 5.` is line **250**; the pointer is at 243. Round 3's `§5` is corrected. |
| **two** of those four | `[측정]` **holds.** Two of {Architecture Synthesis, disposition register, `PoC Contract 0.1`, reconstruction plan}, with `project-state.md` correctly placed outside the set. |
| `PoC Contract 0.1` and the reconstruction plan **do not** link it | `[측정]` **holds.** Neither `contracts/experimental/POC-CONTRACT-0.1.md` nor `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md` (which exists) appears in the grep. |

`[확인 사실]` The self-correction at `:26–28` is also accurate on all four of its counts: the
earlier revision did claim three of four, did count `project-state.md` among them, did cite §5,
and did claim a question-5 link that did not then exist.

## R3-1 — closed

`[측정]` `grep -rniE "gate (will )?consume|Entry Gate consumes" --include="*.md" .` returns, outside
this report, only two hits and both are **retractions**: `P1-INHERITED-DEFECTS.md:22` and
`project-state.md:246` (*"An earlier revision of this sentence said the gate consumes it, which
asserted a process nobody accepted"*). `[확인 사실]` `project-state.md:243–245` now states the same
position as the register — not one of the four, a fifth is the owner's decision. No file asserts
consumption or an equivalent. The round-1 F1 pattern is broken here for the first time.

## R3-3 — half closed. See R4-1

`[확인 사실]` **The `database`/`connection` bullet is fixed and no longer inverts its source.**
`:138–144` now reads *"It reports as `SKIPPED`, **not** as a silent pass"*, which is
`TASK-008:236–241` verbatim in substance, and names the inversion it replaces. `[측정]` Its added
consequence — *"TASK-008's coexistence criterion was reported as exercised on one run and skipped
on another"* — also verifies, and against an independent artifact rather than the handoff:
`…-OBF-PRODUCT.md:44` reproduces `1 passed` with the three `COSMA_DB_*` variables set, and
`:57–62` shows `40 passed, 1 skipped` with them unset. This was the strongest of round 3's four
sub-defects and it is closed.

`[측정]` **Still unsourced, unchanged from rounds 2 and 3:** `NormalizeContext.config_field`
returns `Any` (`grep -rn "config_field" --include="*.md" docs experiments` → no hit in TASK-008 or
TASK-006), and `test_addon_layer_direction.py` does not scan `tests/` (TASK-006's only two
mentions, `:124` and `:201`, are command lines). Two of six bullets, down from four.

## R3-4 — closed

`[확인 사실]` `P0-ARTIFACT-DISPOSITION.md:45` now reads *"Its **six** stated gaps are in
[P1-INHERITED-DEFECTS](P1-INHERITED-DEFECTS.md) §2"*; `P1-INHERITED-DEFECTS.md:50` is
*"§2 … **six** stated gaps"* and the table beneath has six rows. `[측정]` I checked the neighbouring
row while I was there: `:44`'s *"five weak assertions … §3"* matches §3's five bullets (F2–F6).

## F-F — carried, and correctly

`[확인 사실]` `P1-INHERITED-DEFECTS.md:149–152` states it at the severity its source gave it:
`…-SNAPSHOT-R2.md:91` is *"reversing member order in `_NormalizeRun.execute` leaves `112 passed`
of 113 green | **Major**, out of packet scope"*, and `:376` repeats it as a heading. The register's
*"112 of 113 tests green … Major and out of that packet's scope"* matches both.

`[측정]` *"Carried by nothing until now"* **is true for the standing record.**
`grep -rniE "_NormalizeRun|member order|host projection" --include="*.md" docs contracts` returns
hits only in `TASK-003:234`, `TASK-005:72` and `:261–262`, `OQ-013:73`, and this register. The two
task packets are the *source-side* record; no synthesis answer, no `project-state.md` hypothesis,
no contract, and no disposition row carried it. This register is its first destination.

---

### R4-1 — Moderate. The scoped traceability sentence is now false in both directions

**Claimed.** `P1-INHERITED-DEFECTS.md:31–33`, **new this round**, labelled `[확인 사실]`:

> Every row in §§1–6 and §8 traces to a committed attack report, and nothing was added there that
> a review did not find. **§7 is the exception and says so in its own words**: its rows come from
> worker handoffs, which are self-reported.

**Direction 1 — §8 traces to no attack report at all.** `[측정]` Its three bullets:

| Bullet | Source it actually names or came from |
|---|---|
| B4's named coverage gaps, DNS | `evidence/B4-SCENARIO-COVERAGE.md`, an **evidence** document (`Status: COMPLETE with named gaps`), self-authored by the work package. `[측정]` `grep -rln "DNS" experiments/integrated-p0/*.md` returns `EXP-002`, `EXP-003`, and this report — **no attack report**. |
| whether normalized fields survive over time | no source cited; the wording is `architecture-synthesis-v0.1.md:259`'s. |
| malformed rows from a real producer | no source cited; the duplicate-row and embedded-newline clauses are `B4-SCENARIO-COVERAGE.md:44`'s. |

`[추론]` So the sentence credits §8 — the section whose whole subject is *untested* ground — with
independent adversarial backing it does not have. That is the direction R2-2 was raised about:
asserting a traceability the file does not have, in the register whose one value proposition is
that each row names the artifact that measured it. §6 is weaker still but defensible: its D2
numbers were independently re-derived in `…-OBF-RECORD-REPAIRS.md:172–173`, though its D3
share-alike `[결정]` is a decision packet's, not a review's.

**Direction 2 — §7 now holds two attack-report items, so it is not the self-reported exception
either.** `[확인 사실]` `:145` (*"Neither the contract nor `canonical_body` bounds a body or requires
strict JSON"*) traces to `…-RULE-BASELINE.md` F11 (`:108`, `:373`) — carried over from round 3. And
`[확인 사실]` the F-F paragraph added **this round** at `:149–152` cites `…-SNAPSHOT-R2.md` and says
in its own first clause *"this is not an add-on's finding"*. The repair that scoped the blanket to
exempt §7 was written in the same edit that put a second attack-report finding into §7.

`[추론]` Moderate, not Major: both errors are legible to a reader who reads the rows, because every
row names its own source and the F-F paragraph contradicts the preamble explicitly rather than
silently. It is recorded because it is the third revision of the same sentence, and because the
fix is to drop the section list and let each row's own citation carry the claim — a blanket over a
file whose sections have different provenance is the wrong shape, not the wrong wording.

**Reproduction.** `sed -n '31,33p;149,152p;154,168p' docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`;
`grep -rln "DNS" experiments/integrated-p0/*.md`;
`grep -n "F11" experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md`.

---

### R4-2 — Minor. F-F is filed under a heading that excludes it

`[확인 사실]` §7 is *"Contract and harness gaps the add-on authors hit"*. F-F is a host-path defect
found by an independent reviewer, and round 3 named §1 (*"Platform — one row can abort a run"*) as
where it belongs. `[추론]` Minor because the content is present, correct, and self-labelled; a
reader who reaches it is not misled. It costs a reader who scans headings for platform findings —
the same reader §1 exists for. Folding it into §1 would also remove half of R4-1.

---

## Round-3 findings: disposition after re-attack

### Closed

`[확인 사실]` **R3-1 — closed.** No file asserts the gate consumes the register; both files carry the
retraction. Section above.

`[확인 사실]` **R3-2 — closed.** All six clauses re-derived by following links. Table above. `[추론]`
This is the finding that had been wrong twice; the third writing is right, and it is right because
the sentence was produced by counting rather than by intent — the correction paragraph beside it
enumerates what the earlier counts got wrong.

`[확인 사실]` **R3-4 — closed.** Six against six, plus the neighbouring five checked.

`[확인 사실]` **F-F — closed as a carry.** Correct severity, correct measurement, correct source,
and *"carried by nothing until now"* verified by whole-tree grep. Placement is R4-2.

### Still open

| # | Status after round 4 | Severity |
|---|---|---|
| **R4-1** | New. The §§1–6/§8 blanket is false for §8, and §7 is not the self-reported exception it is called. | **Moderate** |
| **R3-3 residue** | `config_field` and the `test_addon_layer_direction.py` scan are still attributed to TASK-008/TASK-006 and appear in neither. Two of six, down from four. | Moderate |
| **R4-2** | F-F filed in §7 rather than §1. | Minor |
| **R3-5** | Open, unchanged. `:58` still cites `…-RULE-BASELINE.md` for a question only `…-R2.md` asks. | Minor |
| **R3-6** | Open, unchanged. `:19` still says `README.md` **and** `AGENTS.md` name four; `AGENTS.md` names three. | Minor |
| **R3-7** | Open, unchanged. `P0-ARTIFACT-DISPOSITION.md:32` still `PROMOTE`s `Normalized Schema 0.2` while `:44` calls `normalizer.obf.product` *"Schema 0.3's only producer"*. | Minor |
| **F8's F-A** | Open, uncarried. Cuts in the design's favour; overstates nothing. | Minor |
| **F13** | Open, uncarried, inherited. `project-state.md:262` still reads *"Five of the ten cannot fire"*; the source's own table shows four distinct rules. The reachability table round 1 asked for is still carried nowhere. | Minor |
| **F9's `[가설]` placement** | Open, unchanged. Forward-looking design analysis with a falsification condition, inside a charter answer rather than an Open Question. | Minor |
| **Register status header** | Open, unchanged. `:3` is `Status: ACCEPTED_FOR_POC` while `:18` says the gate is not defined to accept it, against `README.md:15`. | Minor |

`[추론]` Nine open items, none blocking, none Major. Eight of the nine are the same item they were
in round 2 or round 3 and are being carried knowingly; only R4-1 and R4-2 are new, and both were
introduced by this round's repairs.

## What I tried and could not break, round 4

- `[측정]` **Every clause of the reachability sentence**, by following each of the five inbound
  links to its line and locating that line inside a numbered section. Six clauses, six holds. I
  specifically tried to find a sixth inbound link that would break *"two of those four"* —
  `architecture-synthesis/README.md` does not link it, and neither contract nor plan does.
- `[측정]` **The `database` bullet's added consequence**, which read like an unsourced flourish.
  It is not: `…-OBF-PRODUCT.md:57–62` has both the `40 passed, 1 skipped` run and the `41 passed`
  one, in one report.
- `[측정]` **F-F's severity against its source**, not against round 1's summary of it —
  `…-SNAPSHOT-R2.md:91` and `:376` both say Major, out of packet scope.
- `[측정]` **"Carried by nothing until now"**, by three different spellings across `docs/` and
  `contracts/`. Only the two task packets that generated it, which are not the standing record.
- `[측정]` **`project-state.md`'s new pointer paragraph against the register's**, sentence by
  sentence. They now say the same thing, including the "fifth artifact is the owner's decision"
  clause and the ten-findings origin.
- `[확인 사실]` **The register's `[결정]`/`[확인 사실]` split on the reachability paragraph.** The
  measured link counts are under `[결정]` where round 3 objected they belonged under measurement —
  but the following `[확인 사실]` sentence carries the measurement of what the earlier revision got
  wrong, so a reader gets both roles. Not raised as a finding.
- `[확인 사실]` **The gate's "unresolved blocker" destination**, which looked like a reference to a
  section that does not exist. `P1-ENTRY-GATE-TEMPLATE.md:12` and its required-output row `:24`
  (*Open Question and blocker inventory*) are a real destination. Not a finding.

## Limits of this round

- `[확인 사실]` No test suite was run, no database touched, no network used, and the sandbox was not
  disabled. Every verification is against committed text, committed report and add-on source,
  `git diff HEAD`, and the one untracked subject file.
- `[확인 사실]` Nothing was staged, reset, committed, or edited. `git status --short` shows the same
  four modified files and the same two untracked subject/report files as at the start. This
  Round 4 section is the only thing I wrote, and it was appended.
- `[추론]` R4-1's direction 1 rests on `grep` for `DNS` and `NOT EXERCISED` across
  `experiments/integrated-p0/*.md`. An attack report that raised B4's DNS gap in wholly different
  words would falsify it.
- `[확인 사실]` `contracts/experimental/POC-CONTRACT-0.1.md` is in the diff but was not changed by
  this round's repairs; it was re-attacked in round 3 (F5, F1) and was not re-read line by line
  here.

## Required follow-up

1. **R4-1 is the only item above Minor and the fix is a deletion.** Drop *"Every row in §§1–6 and
   §8 traces to a committed attack report"* and *"§7 is the exception"* entirely; each row already
   names its own source, and §7's preamble already tells a reader that a handoff is self-reported.
   A blanket over a file whose eight sections have four different kinds of provenance cannot be
   made true by narrowing its scope — this is the third attempt.
2. **R4-2 is a move.** F-F belongs in §1 beside the other platform row. Doing it removes half of
   R4-1 as a side effect.
3. `[추론]` **On the pattern.** Round 3 named the method defect: a corrective sentence produced from
   the intended state rather than re-derived from the artifact. Round 4 measures that it did not
   recur where it had recurred three times — the reachability sentence is right, and it is right
   *because* the writer enumerated. It recurred once, in a smaller place: the traceability blanket
   was re-scoped from the §7 exception without checking §8, and without noticing that the same
   edit was adding an attack-report finding to §7. `[추론]` The generalisation worth keeping is
   narrow and cheap: a sentence that quantifies over sections or documents must be written by
   visiting them. When the count is small enough to check, an unchecked count is the defect.
