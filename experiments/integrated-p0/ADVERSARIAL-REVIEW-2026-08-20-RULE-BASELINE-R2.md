# ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2 — Attack report

- Packet: [`TASK-006-rule-baseline-claims-repair.md`](../../docs/agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md)
- Worker revision: `70fa293` ("Make a record say what it checked, since \"clean\" was saying more than it knew"), `HEAD` on `dev`
- Prior report this packet answers: [`ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md`](ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md) (`FAIL`, on TASK-004)
- Attacker: `adversarial-reviewer`, separate session
- Date: 2026-08-20
- Result: `FAIL`

`[결정]` The `FAIL` rests on **one** finding, F1. Everything else this packet set out to do
survived every attack performed, including the two the previous review broke the add-on on
(determinism and `clean`). The repair F1 needs is small. It is blocking because what it
overstates is a *control*, in a repository whose `AGENTS.md` says in as many words: *"Do not
describe a convention as a control."*

---

## Environment

`[측정]` `/home/user1/github_prj/Main/cosmai`, branch `dev` at `70fa293`. CPython from
`.venv` (`python3.13`). **No database was started or contacted**; the scoped suite needs
none, which reproduces the packet's claim. `scripts/with-database.sh` was not run.

`[측정]` **The full suite was not run**, per the task's instruction that the local
PostgreSQL cluster is contended. The worker handoff's `1393 passed, 14 skipped` is therefore
**not reproduced here** and is neither confirmed nor contradicted by this report.

### Mutation method, and how the bytecode cache was defeated

`[확인 사실]` `test_normalizer_rule_baseline.py::load_module` loads `handler.py` by path and
writes `__pycache__/handler.cpython-313.pyc`, validated by `(mtime, size)`. That cache gave
TASK-004's reviewer two false `SURVIVED` verdicts.

`[측정]` Every mutation below was driven by `mutate2.sh` (session scratchpad, outside the
repository), which for each mutant:

1. restored `handler.py` from a byte-exact pristine copy (`sha256`
   `b197ce7bfa9799c27ea47b5d9ca0ccd5470c201d8059477af56ef17b9bfe2509`, 32319 bytes — the same
   baseline size the packet records);
2. applied the edit and **asserted the file's byte length changed**, aborting otherwise;
3. asserted the mutant still parses (`ast.parse`) — this caught one mutation of my own that
   was silently a syntax error and would have produced a meaningless "95 failed";
4. **deleted `__pycache__/` outright** before the run, so no stale `.pyc` could be validated
   at all;
5. restored the pristine file and deleted `__pycache__/` again afterwards.

`[추론]` Deleting the cache directory is strictly stronger than the size-assertion the worker
relied on: there is no `.pyc` left to be believed.

---

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| Scoped suite passes, no database | `.venv/bin/python -m pytest -q -p no:cacheprovider experiments/integrated-p0/tests/test_normalizer_rule_baseline.py tests/environment/test_addon_layer_direction.py` | `103 passed in 0.82s`; rerun after all mutations `103 passed in 0.85s` | matches handoff exactly |
| ruff clean | `.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` | `All checks passed!` | matches |
| mypy clean | `.venv/bin/mypy .../handler.py .../test_normalizer_rule_baseline.py` | `Success: no issues found in 2 source files` | matches |
| add-on check | `./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline` | `normalizer.rule.baseline  ok` | matches |
| No `# type: ignore` remains (F5) | `grep -n "type: ignore" .../handler.py` | no match; both ignores present at `07c599b` are gone | AC4 |
| Baseline file size 32319 | `stat -c%s .../handler.py` | `32319` | the packet's mutation table is arithmetically consistent with the shipped file |
| Only allowed files were written | `git show --stat 70fa293` | 4 files: the packet, `addon.toml`, `handler.py`, `test_normalizer_rule_baseline.py` | AC / scope |
| The packet's `Review` section was not touched by the worker | `git diff 33a03ab HEAD -- <packet>` filtered on `Review` | no hunk | independence held |

### Every claimed control, independently mutated

`[측정]` Eleven mutations of my own, each written from the reported claim rather than copied
from the worker's harness. **Eleven applied, eleven killed.** No `SURVIVED`.

| # | Mutation | bytes | Suite | Killed by |
|---|---|---|---|---|
| m1 | `_finding` returns `{"rule": rule, "field": "", "expected": "", "found": None}` | 32319→32305 | **15 failed**, 83 passed | `TestAFindingNamesTheParticulars` (F1 of the old report) |
| m2 | `clean = not findings and not not_evaluated` → `clean = not findings` | →32307 | **2 failed**, 96 passed | `TestCleanMeansEveryApplicableRuleRan` (F2) |
| m3b | `', '.join(TREND_DIMENSIONS)` → `', '.join(set( TREND_DIMENSIONS ))` | →32326 | **2 failed**, 96 passed | `test_unknown_dimension_reports_the_value…` **and** `test_the_digests_are_the_same_under_different_hash_seeds` |
| m4 | `clean` / `with_findings` counters swapped | →32347 | **1 failed**, 97 passed | `TestOutcomeCounts::test_it_counts_clean_and_with_findings_apart` |
| m5 | `_coverage`'s `raise` disabled (`if False and (…)`) | →32341 | **1 failed**, 97 passed | `test_a_verdict_outside_the_record_kinds_rule_set_fails_the_run` |
| m6 | the window rule's abstention append → `pass` (F2's original silence) | →32220 | **3 failed**, 95 passed | `TestCleanMeansEveryApplicableRuleRan`, `TestOutcomeCounts` |
| m7 | `_bound_found` echoes verbatim (`bounded = value`) | →32334 | **1 failed**, 97 passed | `TestWhatAFindingEchoes` |
| m8 | `_coverage`'s return → `list({rule for rule in applicable …})` — **order only** | →32325 | **1 failed**, 97 passed | **only** `test_the_digests_are_the_same_under_different_hash_seeds` |
| m9 | an eleventh rule name added to `BLOG_RULES` only | →32360 | **2 failed**, 96 passed | `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly` |
| m10 | `if not link_text or not bloggerlink_text:` → `if not link_text:` (F5) | →32344 | **2 failed**, 96 passed | `test_a_blog_record_without_bloggerlink_is_judged_rather_than_crashing` |
| m11 | `clean` / `not_fully_checked` counters swapped | →32361 | **2 failed**, 96 passed | `test_it_counts_clean_and_with_findings_apart`, `test_a_trend_point_whose_window_is_absent…` |

`[측정]` **m8 is the load-bearing one.** It changes nothing but the *order* of
`rules_evaluated`, touches no string any test spells out, and 97 of the 98 tests pass. Only
the six-interpreter seed control sees it. That is the exact defect class TASK-004's review
demonstrated the old same-process digest test was blind to, and this control is not blind to
it.

---

## Determinism: which reading, and does the evidence distinguish them?

`[측정]` **The strong reading, and the evidence does distinguish them.**

- `test_the_digests_are_the_same_under_different_hash_seeds` spawns **six fresh interpreters**
  (`PYTHONHASHSEED` `0`–`5`, `-B`, a clean `env`), digests the same six-item snapshot in each
  with `domain.store.canonical_body` / `digest_of`, and asserts one distinct digest string.
  It is not same-process stability.
- `[측정]` It carries its own positive control against vacuity:
  `assert digests_by_seed["0"].count(",") == 5` — five commas means six result bodies were
  actually emitted, so a probe that produced nothing cannot pass. `check=True` turns a probe
  crash into an error rather than a pass.
- `[측정]` The snapshot really does reach every one of the ten rules' `expected` strings and
  all four abstention reasons; I read the six payloads against the ten rule bodies and each
  string is produced by at least one of them. Those are the strings a `set` would leak its
  iteration order into.
- `[측정]` The control does not depend on the runner's own seed. With m8 applied and the
  **parent** pytest process pinned to `PYTHONHASHSEED` `0`, `1`, `2`, `3`, the seed test
  failed in all four runs (`1 failed, 2 passed` each time). Pristine, it passed in all four.

`[추론]` So the packet's own open question stands and is worth carrying to the gate: this
add-on now holds itself to *identical across interpreters and hash seeds*, and
`POC-CONTRACT-0.1`'s Invariant 9 ("byte-identical canonical output") does not name a process.
Whether every normalizer is held to the same reading is undecided, and the two readings differ
by exactly the class m8 belongs to.

---

## The three-bucket summary

`[측정]` It sums to `results_emitted` **structurally**, not incidentally: `clean_count`,
`dirty_count`, and `incomplete_count` are incremented by one `if / elif / else` executed once
per loop iteration that survives both `continue`s, and `results.append` happens in the same
iteration; `results_emitted=len(results)`. There is no path that increments two buckets or
none.

`[측정]` A deliberate swap fails, in both directions: m4 (`clean` ↔ `with_findings`) and m11
(`clean` ↔ `not_fully_checked`) each went red. `[추론]` The three-way test
`test_every_emitted_record_lands_in_exactly_one_of_the_three_buckets` alone would *not* have
caught m4 — it asserts `[1, 1, 1]`, which a swap preserves. The kill comes from
`test_it_counts_clean_and_with_findings_apart`, which deliberately uses 2/1/0. Both tests are
needed and both are present.

---

## Did the repair regress the ten rules?

`[측정]` **No, on 16 000 differential comparisons.** `_check_blog` and `_check_trend` were
restructured (`(findings, not_evaluated)` tuples, explicit `if abstain / elif fire`), which is
the one part the packet was forbidden to change in what it decides. I loaded the `07c599b`
handler and the `70fa293` handler side by side in one process and ran both over 8 000
randomly generated blog- and trend-shaped records drawn from a value pool of empty strings,
whitespace, `None`, `bool`, ints, floats in and out of range, lists, dicts, valid and
calendar-invalid dates, and known and unknown enum names:

- 8 000 cases comparing `(record_kind, {(rule, field)})` and skip behaviour → **0 differing**;
- 8 000 further cases comparing the *whole* finding — `(rule, field, expected, found)` with
  `found` canonically serialized → **0 differing**.

`[추론]` That is materially stronger than the handoff's own "an argument from reading plus a
green suite". Combined with the previous review's 26 surviving rule mutations, AC8 holds.

`[확인 사실]` F4's factual claim in the module docstring is also true, checked against source
rather than taken on trust: `collector.naver.blog` raises `AddonPermanent` when `link` is
absent, non-string, or empty (`handler.py:235`); `collector.naver.searchtrend` sets
`DIMENSION = "search_keyword"` from a module constant and raises on a non-numeric `ratio`
and an empty `title` (`:256`, `:259`); `collector.naver.shoppinginsight` maps its validated
`mode` to `"shopping_category"` / `"shopping_keyword"` and raises on the same two (`:279`,
`:282`). All three dimension values fall inside `TREND_DIMENSIONS`, so
`trend.unknown_dimension` is indeed unreachable from them.

---

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| **F1** A rule declared in `RULES_BY_KIND` that reaches no verdict and appends no abstention is reported as **evaluated**, the record as **`clean: true`**, and `_coverage` does **not** raise | specification | The module docstring, `_coverage`'s docstring, and the packet handoff all state that a rule added without its abstention branch *fails the run*. It does not. | `clean = True`, `rules_evaluated` lists the rule that never ran, `rules_not_evaluated = []`, no `AddonOutputInvalid` | **Blocking** | `probe_phantom.py`, below |
| **F2** The `BOUNDED` marker is forgeable **byte-identically** from untrusted input | implementation | The constant's comment: *"an untrusted key spelled the same way cannot be mistaken for this marker or shadow it"* | a source `ratio` of `{"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}` produces a `found` byte-identical to a genuine over-size bound | Moderate | `probe_forge2.py`, below |
| **F3** `addon.toml` cross-references a `handler.py` docstring heading that does not exist | evaluation | a cross-reference resolves | `grep -c "Question: output_contract_version" handler.py` → `0` | Minor | one grep |
| **F4** `source_item_key` is unbounded while `found` is bounded | implementation (out of packet scope) | — | a 300 000-character item key passes through into `NormalizedResult` untouched | Minor / record only | `probe_found.py` §E |
| — attempted and **held**: forcing a non-strict JSON body | — | body is `json.dumps(allow_nan=False)`-acceptable | `NaN` at top level, `Infinity` inside a list, `-Infinity` at depth 2 → all three strict | — | `probe_found.py` §D |
| — attempted and **held**: unbounded body via many large findings | — | `found` bounded | 5 findings each fed a 200 000-character value → `canonical_body` **2 571 bytes** | — | `probe_found.py` §C |

### F1 — the blocking finding, in full

**What is claimed.** Three places say the same thing.

- `handler.py` module docstring: *"`_coverage` below raises `AddonOutputInvalid` rather than
  emit a body where they do not — because the only way `clean` quietly starts meaning less
  again is a rule added without its abstention branch."*
- `_coverage`'s own docstring: *"the two ways the bookkeeping can lie are refused here"*.
- The packet's Worker handoff, consequence 3: *"The way `clean` quietly starts meaning less
  again is a rule added without its abstention branch, and that now fails the run instead of
  shrinking the claim."*

**Why it is false.** `_coverage` never observes that a rule ran. It computes

```python
return [rule for rule in applicable if rule not in unevaluated]
```

— coverage by **subtraction from the declared set**. It raises only on a name *outside* the
set (`stray`) or a rule that both fired and abstained (`contradictory`). The direction it
claims to catch is the third one, and that one is silent: a rule that is in
`RULES_BY_KIND[kind]`, reaches no verdict, and appends nothing is subtracted from nothing, so
it lands in `rules_evaluated`, and `clean` — `not findings and not not_evaluated` — is `True`.

`[측정]` Reproduction (no repository file was modified; the pristine module is loaded and its
rule set extended in memory, simulating an eleventh blog rule whose implementation has a fire
branch but no abstention branch):

```python
m.BLOG_RULES = m.BLOG_RULES + ("blog.phantom_no_abstention_branch",)
m.RULES_BY_KIND = {"document": m.BLOG_RULES, "trend_point": m.TREND_RULES}
# then run() over a perfectly ordinary blog record
```

Observed:

```text
no AddonOutputInvalid raised: True
clean            = True
rules_evaluated  = ['blog.missing_link', 'blog.missing_content', 'blog.invalid_postdate',
                    'blog.link_equals_bloggerlink', 'blog.phantom_no_abstention_branch']
not_evaluated    = []
outcome.notes[clean] = 1
```

A stored `normalized_result.body` now asserts that `blog.phantom_no_abstention_branch` was
evaluated on this record. It was not. That is F2 of the previous review, one level up: a
claim about coverage that nothing established.

**Why the existing test does not catch it.**
`test_a_verdict_outside_the_record_kinds_rule_set_fails_the_run` drives the guard by
*removing* a rule from `RULES_BY_KIND` — the `stray` direction. Nothing drives the direction
above.

**The honest counterweight, measured.** `[측정]` The test file writes its own
`RULES_BY_KIND` out by hand *"rather than read from the module"*, and that duplicate is a
genuine control: m9 (adding the phantom to the module's set only) fails
`test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly` in two parametrizations. So an
author who adds a rule and forgets the test's list **is** caught. `[추론]` The author who
updates the test's list — which adding a rule ordinarily requires, since the new rule must
appear in the expected set for its own tests — is not caught by anything. The protection that
exists is a duplicated list, and it protects against forgetting the *list*, not against
forgetting the *abstention branch*.

**Failure class: specification.** `[추론]` The code is defensible; the sentence describing it
is not. `AGENTS.md` requires *"Do not describe a convention as a control"*, and this describes
"the author remembers the abstention branch" as "the run fails". The same requirement is why
the previous review's F9 (`streams = []` claiming a mechanism that does not exist) was a
finding, and this packet corrected that comment. It replaced it with a larger instance of the
same thing.

**Two repairs, either sufficient; the second is better.**

1. Correct the three sentences: say that `_coverage` refuses a verdict outside the kind's set
   and a rule that both fired and abstained, that `rules_evaluated` is derived by subtraction
   and therefore inherits the correctness of each checker's abstention branches, and that a
   declared-but-never-reached rule is *not* detected. Label it `[결정]`, not a control.
2. Make the claim true: have `_check_blog` / `_check_trend` return the rules they actually
   reached, and let `_coverage` raise when `reached | abstained != set(applicable)`. Then a
   rule added without either branch fails the run, exactly as written today. `[추론]` The
   test that would go red for it is the mirror of m9 — a phantom in the set with no branch —
   which today is green.

### F2 — the bounded-value marker is forgeable

**What is claimed.** `handler.py:210–213`: *"The one key under which a bounded stand-in
appears. It replaces the whole value rather than being added beside it, so an untrusted key
spelled the same way cannot be mistaken for this marker or shadow it."*

**Why it is false.** The `shadow it` half holds — the marker does replace the whole value.
The `mistaken for` half does not. `_bounded` passes a small mapping through unchanged, so a
source that supplies a one-key object with that exact key and a matching string value produces
a `found` indistinguishable from a genuine bound.

`[측정]` Reproduction:

```text
genuine (a dict of 8 keys, each key 600 characters, so the encoding exceeds FOUND_MAX_BYTES):
  {"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}
forged  (source ratio = {"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}):
  {"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}
BYTE-IDENTICAL: True
```

The truncation form is forgeable too, structurally:

```text
source ratio = {"<bounded…>": {"kept": {"x": 1}, "keys_omitted": 99}}
→ found     = {"<bounded…>": {"kept": "<dict omitted below depth 2>", "keys_omitted": 99}}
```

`[추론]` Severity is Moderate, not blocking: the consequence is that a reader of a diagnostic
field can be lied to about *why* a value is small. No rule verdict changes, no size or
strictness guarantee is broken (both were separately attacked above and held). But it is the
same class of sentence as F1 — a comment asserting a property the code does not have — and
should go in the same correction pass. The cheap fix is to weaken the comment; the real fix is
to make the marker unforgeable (e.g. escape any source key equal to `BOUNDED`, or carry the
marker in a sibling field the source cannot occupy).

### F3 — a dangling cross-reference

`[측정]` `addon.toml` says *"See handler.py's docstring, \"Question: output_contract_version
collides in spelling with an unrelated schema\"."* `grep -c "Question: output_contract_version"
handler.py` → `0`. The reasoning does exist in the docstring, under the heading *"Another
documentation gap, unrelated to input shape."* `[확인 사실]` The line predates this task
(`07c599b`), but it is three lines above the comment this task rewrote to fix the previous
review's F9, in a file this packet was allowed to edit. Minor.

### F4 — recorded for the gate, not against this packet

`[측정]` F11's bound covers `found` and only `found`. `NormalizedResult.source_item_key` is
copied from `SnapshotItem.item_key` unbounded — a 300 000-character key passes through whole.
`[추론]` That is outside this packet's allowed files and belongs with the handoff's own
observation that neither `CONTRACT-ADDON@1.3` nor `domain.store.canonical_body` bounds
anything or requires strict JSON. It reinforces that point rather than contradicting it: the
bound and the strictness live in one add-on because that is the only place this packet could
put them.

---

## Acceptance criteria, one by one

| # | Criterion | Verdict | Basis |
|---|---|---|---|
| 1 | `clean: true` cannot be recorded for a record with an unevaluated applicable rule, and a test fails if it is | **Qualified** | Holds for today's ten rules (m2, m6 killed). "Cannot" is too strong: F1 shows a declared rule that reaches no verdict is reported evaluated and the record `clean`. |
| 2 | `field`/`expected`/`found` asserted for every rule that sets them; blanking `_finding` goes red | `PASS` | all ten rules have a `TestAFindingNamesTheParticulars` case; m1 → 15 failed |
| 3 | A determinism control that goes red for a hash-order-dependent value, and how it was verified | `PASS` | m8 (order-only) red, and red only there; m3b red; independent of the parent seed |
| 4 | Removing the `bloggerlink_ok` guard goes red, or the guard is gone with no ignore | `PASS` | both — no `type: ignore` remains, and m10 → 2 failed |
| 5 | `NormalizeOutcome`'s counts asserted; a `clean`/`with_findings` swap goes red | `PASS` | m4, m11 both red; the three buckets sum structurally |
| 6 | `found` bounded; a non-finite `ratio` produces strict JSON | `PASS` | m7 red; `NaN`/`Infinity`/`-Infinity` strict at three depths; 5×200 KB → 2 571-byte body |
| 7 | The docstring records F4's reason; the `streams` comment no longer claims a false distinction | `PASS` on both, with F3 noted | F4's factual half independently verified against all three collectors |
| 8 | The ten rules are unchanged | `PASS` | 16 000 differential fuzz comparisons, 0 divergence |

---

## Scope and decision-boundary review

- **Allowed-file compliance:** `[측정]` `PASS`. `git show --stat 70fa293` lists exactly four
  files: `handler.py`, `addon.toml`, `test_normalizer_rule_baseline.py`, and the packet — whose
  `Status` and `Worker handoff` the packet's own Excluded list permits. The `Review` section was
  not touched (`git diff 33a03ab HEAD` on the packet shows no hunk there). No `docs/project-state.md`,
  no Decision Packet, no `contracts/**`.
- **Accepted-decision compliance:** `[측정]` `PASS`. No rule was added or removed; DP-021 D2's
  three dimensions and three time units and DP-021 D3's `[0, 100]` are unchanged; DP-019's and
  DP-021's version strings are untouched. The owner's 2026-08-20 decision (hypothesis 6 closes
  on fixture evidence, no rule added to make one fire) is honoured — the F4 repair is prose only.
- **Unanswered consequential direction:** `[추론]` Two, both correctly raised by the handoff
  rather than resolved: (a) whether Invariant 9's determinism means across-process or
  same-process, and (b) whether a report-shape change owes an `output_contract_version` bump when
  no artefact defines the version and no validator checks it. `[결정]` Holding `"0.1"` and
  recording why is the right call for a packet forbidden to touch `contracts/**`; the question
  belongs at the gate.
- **Prohibited material exposure:** `[측정]` None. No credential, cookie, private dataset, or
  personal data appears in the add-on, the tests, or the packet. `context.log` emits only counts
  and rule names — no untrusted value reaches the log line.

---

## Restoration proof

`[측정]` Eleven mutations were applied to `handler.py` through `Bash` and every one was
restored from a byte-exact pristine copy taken before the first:

```text
sha256sum experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
b197ce7bfa9799c27ea47b5d9ca0ccd5470c201d8059477af56ef17b9bfe2509   (identical to the pre-attack hash)
diff -q $TMPDIR/handler_pristine.py <that file>   → byte-identical
git diff --stat -- experiments/                    → (empty)
pytest (scoped, after all mutations)               → 103 passed in 0.85s
```

`[확인 사실]` **`git diff --quiet` over the whole tree exits `1`, and none of it is mine.**
`git status --short` reports `M contracts/experimental/POC-CONTRACT-0.1.md` and
`M docs/project-state.md`, plus untracked `docs/agent-workflow/task-packets/TASK-007-…`,
`TASK-008-…`, and `docs/decisions/DP-028-…`. The tree was clean of all five when this review
began; they appeared during it. `[추론]` A concurrent session is working in `docs/` and
`contracts/`. This attacker touched no file outside
`experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py` (restored) and this
report. Every other artefact of this review — the mutation harness, the five probe scripts —
is in the session scratchpad outside the repository, deliberately.

---

## Conclusion

`FAIL`, on one finding.

`[측정]` Seven of the eight acceptance criteria pass under attack, and they pass for the right
reason: eleven independent mutations, all killed, each watched going red, with the bytecode
cache removed rather than merely invalidated. The two claims the previous review actually broke
the add-on on are now genuinely held — an order-only mutation of `rules_evaluated` is caught by
the six-interpreter seed control and by nothing else, and both directions of a bucket-counter
swap go red. The ten rules the previous review could not break are unchanged in what they
decide, on 16 000 differential comparisons against `07c599b`. This is good work and most of it
is not in question.

`[추론]` What fails is narrow and specific. This packet exists because the add-on's *claims*
outran its *evidence*. In closing four such claims it introduced a fifth, in the very mechanism
that closes the largest of them: `_coverage` is described three times — in the module docstring,
in its own docstring, and in the packet's Worker handoff — as the thing that makes a rule added
without an abstention branch fail the run, and it is measurably not that. Coverage is computed
by subtracting abstentions from a declared list, so an unreached rule is asserted to have run.
Accepting the packet as written would put that sentence into the decision record as a control,
which is the one thing `AGENTS.md` names outright.

`[결정]` The repair is small — correct three sentences, or spend a dozen lines making the claim
true by having each checker report the rules it actually reached. Either closes it. F2 and F3
should ride along in the same edit. `[추론]` Nothing here calls for a new packet, a rule change,
an owner decision, or a re-run of the 26 rule mutations; TASK-006 should be reopened, not
replaced.

---

## Required follow-up

- **New or revised packet:** revise TASK-006 rather than open a new one. Three items:
  (a) **F1, blocking** — either narrow the claim in `handler.py`'s module docstring,
  `_coverage`'s docstring, and the handoff's consequence 3, **or** make `_check_blog` /
  `_check_trend` return the rules they reached so `_coverage` can raise on a declared rule that
  reached neither a verdict nor an abstention; if the second, add the mirror of m9 (a phantom
  rule with no branch) as the control, since that mutation is green today.
  (b) **F2** — weaken or repair the `BOUNDED` constant's comment.
  (c) **F3** — fix `addon.toml`'s dangling cross-reference to a heading `handler.py` does not
  contain.
- **Open Question or Decision Packet update:** the handoff's two questions are real and belong
  at the P1 Entry Gate, not in this add-on: whether `POC-CONTRACT-0.1`'s Invariant 9 means
  across-process determinism (this add-on now holds the strong reading; nothing says every
  normalizer must), and whether `output_contract_version` can mean anything while no artefact
  defines a body shape and no validator checks one — this task changed a stored body's shape
  incompatibly and nothing in the repository noticed. Add `source_item_key`'s unboundedness
  (F4) to the same question about where bounding and strict JSON belong.
- **Project State or contract update:** none from this review. `docs/project-state.md` was not
  touched and hypothesis 6's disposition is the orchestrator's.

## Where this file belongs

Beside the experiment it attacks: `experiments/integrated-p0/`. Link it from
`docs/agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md`'s `Review` section —
which this attacker did not edit, per the role contract.
