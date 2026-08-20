# ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM — Attack report

- Packet: [TASK-009](../../docs/agent-workflow/task-packets/TASK-009-coverage-claim-and-marker-collision.md)
  (`Status: WORKER_DONE`)
- Prior report this packet answers: [ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2](ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md), F1–F4
- Subject: `experiments/integrated-p0/addons/normalizer.rule.baseline/{handler.py,addon.toml}`,
  plus the correction block added to `TASK-006`'s Worker handoff consequence 3
- Attacker: `adversarial-reviewer`, 2026-08-20, uncommitted working tree on `dev` at `70fa293`
- Result: **`FAIL`**, narrowly — see the one blocking finding

## Conclusion

`[측정]` **Everything the packet actually wrote is true, and I verified both halves of it by
experiment rather than by reading.** The new module-docstring paragraph's claims hold: the
declared-but-never-reached rule is emitted `clean: true` with no `AddonOutputInvalid` (probe A);
an undeclared rule name raises whether it fired (B1) or abstained (B2); a rule in both lists
raises (C). The diff is genuinely inert — AST with docstrings stripped is *identical*, every
function's bytecode is identical after normalising line numbers, every module constant compares
equal, and 4 000 differential comparisons of the pre-edit and post-edit modules diverged 0 times.
The `BOUNDED` comment now states the forgeability plainly and the forgery reproduces
byte-identically. `addon.toml`'s cross-reference resolves.

`[측정]` **What fails is one sentence the packet's own Included list left out.** R2's F1 named
*three* false places: the module docstring, **`_coverage`'s own docstring**, and TASK-006's
consequence 3. TASK-009's Included list silently substituted "the comment above `RULES_BY_KIND`"
for the second of those. So `handler.py:379–388` still reads:

> Which of this kind's rules reached a verdict, refusing anything that does not add up. […]
> so the **two ways** the bookkeeping can lie are refused here rather than emitted

`[추론]` Both clauses are the defect this packet exists to remove, in the function the packet is
about, with no pointer to the correction 270 lines above it. A reader who opens `_coverage` —
the most likely reader — still gets the false completeness claim. This is `AGENTS.md`'s *"Do not
describe a convention as a control"* surviving in the one place it matters most.

`[추론]` Rework is one docstring and one test docstring, not a re-plumbing: much smaller than
R2's. Nothing in the work already done needs to be undone.

## Findings

| # | Claim attacked | Why it fails | Severity | Reproduction |
|---|---|---|---|---|
| **A1** | Criterion 1: *"No sentence anywhere in the allowed files claims `_coverage` catches a rule that reaches no verdict"* | `_coverage`'s own docstring (`handler.py:379`, `:382`) still claims it refuses *"anything that does not add up"* and that *"the two ways the bookkeeping can lie"* — exactly two — are refused. A body in which a declared rule never ran does not add up and is not refused (probe A). R2's F1 quoted this sentence by name; TASK-009's Included list omitted it. | **Blocking** | `grep -n "ways the bookkeeping\|does not add up" handler.py` + probe A |
| **A2** | Handoff: *"`grep -n "abstention branch"` [in the test file] returned nothing, so no test docstring repeated the F1 claim"* | The check searched for the *wording*, not the *claim*. `test_normalizer_rule_baseline.py:568` still says the coverage test proves every applicable rule is accounted for *"never both and never neither"*. "Never neither" is precisely what is not enforced: with the phantom rule present in both the module's set and the test's hand-written set, that assertion passes while the rule never ran. | Moderate | probe A + `sed -n 566,573p` of the test file |
| **A3** | The new docstring's two `[측정]` labels | `evidence-labels.md` §`[측정]` requires input, procedure, environment and time, and its boundary rule sends a fact readable from an artifact to `[확인 사실]`. "`rules_evaluated` is computed by subtraction" is read from line 404 → `[확인 사실]`. *"Today's ten rules always reach one branch or the other on **every input** this module classifies"* is universally quantified over inputs and no measurement is recorded for it anywhere in the handoff; the checkable statement behind it is structural (`_check_blog`/`_check_trend` are straight-line, no early return) → `[확인 사실]`/`[추론]`. | Minor | `docs/conventions/evidence-labels.md:48–71,146–171` |
| **A4** | Criterion 1's verification command itself | `grep -rn "abstention branch"` returns nothing partly because the phrase *survives* at `handler.py:119–120` split across a line break (`abstention\nbranch`) — where it is used correctly. The empty output is therefore not evidence of absence; `grep -rn "abstention"` is the check that would have shown it. | Minor / method | `grep -rn "abstention" .../normalizer.rule.baseline` |
| — | Everything else attacked | held — see "Attacks that held" | — | — |

`[추론]` A1 is blocking under the packet's own criterion 1 read literally, and under the
instruction that a sentence claiming a catch that does not happen is blocking. It is *not* a
regression: the sentence predates TASK-009 and was already reported. What makes it blocking here
is that TASK-009's single deliverable was that this add-on's prose stops overstating this exact
guarantee, and the file now contains both the corrected statement and the uncorrected one.

## Environment

```text
repo      /home/user1/github_prj/Main/cosmai, branch dev, HEAD 70fa293, work uncommitted
python    .venv/bin/python (CPython 3.13, per __pycache__/handler.cpython-313.pyc)
probes    written outside the working tree, under $TMPDIR/probes/, run with `python -B`
mutation  none. No repository file was modified at any point; every mutation below is an
          in-memory rebind on a freshly path-loaded module, so the (mtime, size) bytecode
          cache that gave TASK-004's reviewer two false SURVIVED verdicts cannot apply.
```

`[측정]` Restoration proof: `git diff --stat` over the add-on directory shows only the two
files the worker changed, at the same line counts as before this review; the only file this
review created is this report.

## Both halves of the new `_coverage` description, by experiment

`[측정]` `$TMPDIR/probes/probe_coverage.py` loads the pristine `handler.py` by path (the way
`addon_host` does), rebinds `BLOG_RULES`/`RULES_BY_KIND` *in memory only*, and drives `run()`.

**A — the case the docstring says is NOT caught.** An eleventh blog rule declared in the set
with neither a fire nor an abstention append:

```python
m.BLOG_RULES = m.BLOG_RULES + ("blog.phantom_no_abstention_branch",)
m.RULES_BY_KIND = {"document": m.BLOG_RULES, "trend_point": m.TREND_RULES}
```

```text
raised AddonOutputInvalid: False
clean            = True
rules_evaluated  = ['blog.missing_link', 'blog.missing_content', 'blog.invalid_postdate',
                    'blog.link_equals_bloggerlink', 'blog.phantom_no_abstention_branch']
not_evaluated    = []
outcome.notes[clean] = 1
```

→ the docstring's *"It does **not** raise, and cannot by construction"* is **accurate**, and
R2's F1 reproduces exactly as recorded.

**B1 — an undeclared rule name that FIRED.** `RULES_BY_KIND["document"]` shrunk by
`blog.missing_link`, record with `link` removed:

```text
raised AddonOutputInvalid: True -> a record's rule coverage does not match its kind's rule set…
```

**B2 — an undeclared rule name that ABSTAINED.** `RULES_BY_KIND["trend_point"]` shrunk by
`trend.unknown_dimension`, record with `dimension: null` (drives the abstention branch):

```text
raised AddonOutputInvalid: True -> …so `clean` would not mean that every applicable rule ran
```

→ the docstring's *"when a rule name outside this kind's set **fired or abstained**"* is
accurate in **both** directions. R2 only drove the fired direction; the abstained half is
verified here for the first time.

**C — one rule in both lists.** `_coverage("document", [finding(missing_link)],
[abstention(missing_link)])`, a rule that *is* declared so `stray` is necessarily empty:

```text
raised AddonOutputInvalid: True
```

→ the docstring's second claimed catch holds, and is reached through `contradictory` rather
than `stray`.

**D — is C reachable from today's checkers?** 100 `(link, postdate)` value combinations through
`_check_blog`: **0** cases where a rule appears in both lists. Consistent with `_coverage`'s
*"Neither is reachable from today's ten rules"*.

`[결정]` Verdict on the packet's central deliverable: the new module-docstring paragraph and the
new `RULES_BY_KIND` comment are **accurate in every clause I could test**, including the negative
clause. That is the half of this review that the worker earned.

## Criterion 5 — is the diff really inert?

`[측정]` Three independent checks, `$TMPDIR/probes/inert.py` and `inert2.py`, comparing
`git show HEAD:…/handler.py` against the working file:

```text
AST with all docstrings stripped, ast.unparse-compared      → IDENTICAL
per-function dis() with line numbers normalised, plus
  co_consts (non-code) and __doc__, over every module name  → 0 entries differ
every module-level constant compared by value               → all equal
  RULE_REPORT_VERSION '0.1' · BLOG_RULES · TREND_RULES · RULES_BY_KIND · BLOG_MARKER_KEYS
  TREND_MARKER_KEYS · FOUND_MAX_TEXT 200 · FOUND_MAX_ITEMS 8 · FOUND_MAX_DEPTH 2
  FOUND_MAX_BYTES 4096 · BOUNDED '<bounded by the rule baseline>'
module __doc__ differs                                       → True (the intended change)
```

`[측정]` The one thing that first *looked* like a difference was `TREND_MARKER_KEYS`'s `repr`
(`frozenset` iteration order) — two processes, two hash seeds, same set; `==` is `True`. Reported
here because a reviewer comparing `repr`s alone would have raised a false finding.

`[측정]` Differential fuzz, `$TMPDIR/probes/diffl.py`: 4 000 records (seed 20260820) over
blog- and trend-shaped key sets drawn from 21 adversarial values (`NaN`, `inf`, `True`, 300-char
strings, nested dicts, a forged `BOUNDED` object, out-of-range ratios, calendar-invalid dates,
absent keys), each driven through **both** modules and compared on the full emitted body plus
`outcome.notes`:

```text
differential comparisons: 4000, divergences: 0
```

`[결정]` So the worker's reasoning — unchanged executable code cannot change behavior, therefore
the `PYTHONHASHSEED` control need not be re-run — **is sound, and its premise is now
independently established rather than accepted.** `[측정]` I re-ran the control anyway because it
costs under a second: `PYTHONHASHSEED` ∈ {0, 1, 7, 12345, 999983, random} → `98 passed` in all
six. Criterion 5 is met. `[추론]` A comment edit that changed a default, a constant or a literal
used in logic is the thing this section was hunting; there is none.

## Reproduced worker evidence

| Handoff claim | Command | Observed | Verdict |
|---|---|---|---|
| `149 passed in 0.83s` | the packet's `Verification` block verbatim | `149 passed in 0.86s` | matches |
| `149 = R2's 103 + 46` | per-file runs | `98` + `5` + `46` = `149`; R2 recorded `103` for the first two | arithmetic correct |
| `check-addons.sh` → `ok` | as written | `normalizer.rule.baseline        ok` | matches |
| `ruff` clean | as written | `All checks passed!` | matches |
| `mypy` clean | as written | `Success: no issues found in 1 source file` | matches |
| `grep -rn "abstention branch"` → nothing | as written | nothing | matches, **but see A4** |
| `grep -c "output_contract_version collides in spelling"` → `0` | as written | `0` | matches |
| `grep -c "Another documentation gap, unrelated to input shape"` → `1` | as written | `1` | matches |

## F3 — does the cross-reference resolve now?

`[측정]` Both directions, as criterion 4 asks:

```text
grep -c "output_contract_version collides in spelling" handler.py   → 0   (the dangling title)
grep -c "Another documentation gap, unrelated to input shape" handler.py → 1  (handler.py:88)
grep -n "Another documentation gap" addon.toml                      → 21: # "…".
```

`[확인 사실]` `handler.py:88` opens *"**Another documentation gap, unrelated to input shape.**
`[addon].output_contract_version` here is `"0.1"`…"* — the paragraph `addon.toml`'s comment is
pointing at, and the one that carries the reasoning. F3 is closed. `[추론]` The quoted heading is
now a prefix of a bolded sentence rather than a heading in its own right, so the reference is
`grep`-checkable, which is what made F3 findable in the first place.

## F2 — is the forgeability now stated plainly, and does it still reproduce?

`[확인 사실]` The new comment (`handler.py:224–232`) says the marker *"does not distinguish the
two: a source value that is itself `{BOUNDED: "..."}` with the exact marker text produces a
`found` byte-identical to a genuine bound"*, and that the field is *"a diagnostic for a human
reader, not a parseable channel a caller should trust"*. No hedge, no "cannot be mistaken".

`[측정]` `$TMPDIR/probes/probe_forge.py`, exactly R2's F2 construction — a genuine bound from an
8-key dict with 600-character keys, against a source `ratio` that *is* the marker object:

```text
genuine found: {"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}
forged  found: {"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}
BYTE-IDENTICAL: True
forged truncation form: {"<bounded by the rule baseline>": {"kept": "<dict omitted below depth 2>", "keys_omitted": 99}}
```

`[추론]` The comment's surviving positive claim — *"it shadows an untrusted key spelled the same
way rather than sitting beside it"* — is also true: `_bound_found` returns `{BOUNDED: …}` as the
whole value, so nothing sits beside it. The comment now separates the property that holds from
the one that does not, which is what the packet asked for. F2's prose half: **PASS**; the
implementation half remains open by decision, recorded in Limitations.

## A1 in full — the sentence the packet's Included list dropped

`[확인 사실]` R2's F1 listed three places. Compare with TASK-009's Included list:

| R2 F1 named | TASK-009 Included | Corrected? |
|---|---|---|
| `handler.py` module docstring | yes | **yes** |
| **`_coverage`'s own docstring** — *"the two ways the bookkeeping can lie are refused here"* | **absent; replaced by "the comment above `RULES_BY_KIND`"** | **no** |
| TASK-006 handoff consequence 3 | yes | **yes** |

`[확인 사실]` Current text, unchanged from `07c599b`:

```python
def _coverage(...) -> list[str]:
    """Which of this kind's rules reached a verdict, refusing anything that does not add up.

    `clean: true` is a claim that `RULES_BY_KIND[kind]` ran in full. That claim is only worth
    the bookkeeping behind it, so the two ways the bookkeeping can lie are refused here
    rather than emitted: …
```

`[추론]` Two false clauses, both of the class this packet exists to remove:

1. *"Which of this kind's rules **reached a verdict**"* — the return value is
   `applicable − unevaluated`, which names rules that may not have reached a verdict at all.
   Probe A is a body where the return value asserts a verdict that never happened.
2. *"the **two** ways the bookkeeping can lie are refused here"* / *"refusing anything that
   does not add up"* — there is a third way, it is not refused, and the module docstring 270
   lines above now says so explicitly. The function's own docstring is where a reader of
   `_coverage` lands, and it carries no pointer to that correction (the `RULES_BY_KIND` comment
   does carry one; this docstring does not).

`[추론]` Failure class: **specification** — the same class as R2's F1, one sentence short of
closed. The repair is prose only and needs no executable change: state that the two refusals are
the two the guard *implements*, not the two that exist, and cross-reference the module
docstring's *"What `_coverage` actually checks"* the way the `RULES_BY_KIND` comment does.

`[추론]` Why this is not a nitpick: the packet's stated objective is *"Both descriptions become
what the code measurably does."* After this packet, `handler.py` contains a correct description
and an incorrect one about the same function, and the incorrect one is closer to the code. A P1
reader trusting the nearer comment inherits exactly the belief R2 falsified.

## A2 — the test docstring the wording-search missed

`[확인 사실]` `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py:566–573`:

```python
def test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly(self, record_builder) -> None:
    """Whatever happens to a record, every applicable rule is accounted for once — as
    evaluated or as not evaluated, never both and never neither."""
    …
    assert evaluated.isdisjoint(unevaluated_rules(body))
    assert evaluated | unevaluated_rules(body) == RULES_BY_KIND[body["record_kind"]]
```

`[추론]` *"never neither"* is the property `_coverage` does not have. What the two assertions
actually check is (a) disjointness, which the `contradictory` guard already raises on, and (b)
that the module's declared set equals the test file's hand-written one — R2 measured that second
one as a genuine control (it kills m9). Neither can detect a declared rule that never ran:
probe A's body satisfies both once the phantom is in the test's list too, which is what adding a
rule ordinarily requires. `[측정]` The class docstring above it (`:549`) states the same reading
— *"`clean` now means every rule applicable to this record kind **reached a verdict**"* — which
is the claim, not the wording, the packet told the worker to look for.

`[추론]` The worker's check (`grep -n "abstention branch"` → nothing → conclude no test docstring
repeats the claim) is the defect class this repository names most often: a search that proves the
*phrase* is absent, reported as evidence that the *claim* is absent. The packet's allowed-files
entry for the test file permits a docstring edit with no assertion change, so this is inside
scope and was reachable.

## A4 — criterion 1's own command is line-wrap sensitive

`[측정]` `grep -rn "abstention branch"` over the add-on returns nothing. But the phrase is still
there, at `handler.py:119–120`, split by the docstring's line wrap:

```text
119: `_coverage` enforces. The only thing standing between a future rule missing its abstention
120: branch and a wrong `clean: true` is review — the same distinction `AGENTS.md` draws between
```

`[확인 사실]` That occurrence is *correct* text — it is the packet's own required sentence naming
the unenforced property. `[추론]` So the criterion passes and the prose is right, but the command
that proves it would have returned `0` whether the phrase was removed, corrected, or merely
re-wrapped. `grep -rn "abstention"` is the check with a positive control behind it; it returns 15
lines and every one of them reads correctly today.

## TASK-006's consequence 3 — does a first-time reader get the true statement?

`[확인 사실]` The diff appends, below the original numbered item and indented inside it, a block
opening **`[측정]` "Correction, 2026-08-20 (TASK-009). The paragraph above is wrong about what
`_coverage` catches."** The original paragraph is byte-unchanged, per the packet's *"not silently
rewritten"* instruction.

`[추론]` Judgment: **acceptable, and the right trade.** A reader arriving at consequence 3 reads
the false paragraph and then, with no intervening content and inside the same list item, the
bolded correction — the correction cannot be missed by anyone reading the item to its end, and
the original's survival is what lets the record be read twice, which is this repository's stated
habit. `[추론]` The one residual risk is extraction rather than reading: the original sentence
still `grep`s as a standalone true-sounding claim (*"that now fails the run instead of shrinking
the claim"*), so a future search that quotes it without its neighbourhood will quote the false
version. A four-word inline marker on the original line (`— corrected below, TASK-009`) would
close that without rewriting anything. Not a finding; recorded as the cheapest available
improvement.

`[확인 사실]` TASK-006's `Review` section is also changed in this working tree (`Result: FAIL`,
disposition `REWORK`, linking R2 and TASK-009). That section is forbidden to the worker and its
content is orchestrator work; TASK-009's handoff does not claim it. `[추론]` Attributed to the
orchestrator, not to this worker. The working tree cannot prove authorship, so it is recorded
rather than asserted.

## Did anything outside the allowed file list change?

`[측정]` `git status --short` shows six modified tracked files. Attribution:

| File | Allowed by TASK-009? | Attribution |
|---|---|---|
| `addons/normalizer.rule.baseline/handler.py` | yes | this worker |
| `addons/normalizer.rule.baseline/addon.toml` | yes | this worker |
| `task-packets/TASK-006-…md` — Worker handoff consequence 3 | yes | this worker |
| `task-packets/TASK-006-…md` — `Review` section | **no** | orchestrator (see above) |
| `contracts/experimental/POC-CONTRACT-0.1.md` | no | `[추론]` the concurrent session: the hunk is DP-028 / `Normalized Schema 0.3` `product` records |
| `docs/project-state.md` | no | `[추론]` same — a DP-028 bullet |
| `experiments/integrated-p0/tests/README.md` | no | `[추론]` same — a note about `--run-network` needing the `tests` path, from the real-data capture |

`[추론]` None of the last three is attributable to this worker, and none touches the add-on. The
worker's *"no other file was written"* is consistent with what the add-on's own history shows;
`test_normalizer_rule_baseline.py` is indeed untouched, which is what A2 is about.

## Attacks that held

`[측정]` Recorded because a short honest list is worth more than a padded one.

- Both claimed catches, in all three directions (`stray` from a fired rule, `stray` from an
  abstained rule, `contradictory`) — all raise.
- The claimed non-catch — reproduces exactly as R2 recorded, `clean: true`, `not_evaluated: []`.
- Diff inertness — three independent methods, plus 4 000 differential comparisons, plus the
  six-seed determinism control re-run. No executable change, no changed constant, no changed
  literal.
- The ten rules — unchanged in what they decide, measured rather than assumed.
- `_check_blog` double-append over 100 field combinations — none, so the `contradictory` branch
  stays unreachable from today's rules as its docstring says.
- F3's cross-reference — resolves, both greps as claimed.
- F2's forgery — reproduces byte-identically, and the comment now says so.
- Suite count, `ruff`, `mypy`, `check-addons.sh` — every number in the handoff reproduced.

## Required follow-up

1. **Blocking (A1).** Correct `_coverage`'s docstring: the two refusals are the two the guard
   implements, not the two that exist; and add the same cross-reference to the module docstring's
   *"What `_coverage` actually checks"* that the `RULES_BY_KIND` comment already carries.
   Prose only — no executable change, so criterion 5 survives it.
2. **Moderate (A2).** Correct
   `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly`'s docstring (*"never
   neither"*) and `TestCleanMeansEveryApplicableRuleRan`'s (*"reached a verdict"*) to say what
   the assertions check: disjointness, and module set == test set. No assertion change, which
   the packet already permits.
3. **Minor (A3).** Re-label the two new `[측정]`s per `evidence-labels.md`, or attach the input,
   procedure and time a `[측정]` requires.
4. **Minor (A4).** When a criterion's proof is a `grep` for absence, grep for the word, not the
   wrapped phrase, and record the positive control.
5. **Unchanged, for the gate.** F1's gap and F2's forgeability are stated, not closed; F4 is
   untouched. All three are correctly recorded as out of scope.

## Where this file belongs

`[확인 사실]` Beside the experiment, per `docs/agent-workflow/reviews/README.md`.

---

# Round 2 — re-attack of A1–A4

- Scope: the round-1 findings only. Round 1's substance is not re-litigated.
- Attacker: `adversarial-reviewer`, 2026-08-20, uncommitted working tree on `dev` at `70fa293`
- Subject: `handler.py` and `test_normalizer_rule_baseline.py`, prose only
- Result: **`FAIL`**, narrowly — **all four of A1–A4 are closed**, and one new sentence
  written this round is false. See B1.

## Round-2 status of each round-1 finding

| # | Round-1 severity | Round-2 status |
|---|---|---|
| **A1** | Blocking | **Closed.** Verified below. |
| **A2** | Moderate | **Closed.** Verified by the phantom-rule construction round 1 only described. |
| **A3** | Minor | **Closed for the two labels named**, plus the worker's voluntary third. Two new `[측정]`s of the same class appear in the test file — recorded as B2, minor. |
| **A4** | Minor / method | **Closed.** The command now has a positive control; the wrapped text is correct and stays. |
| **B1** | — | **New, blocking.** A round-2 sentence in the module docstring is falsified by the module's own clean fixture. |

## A1 — `_coverage`'s own docstring: closed

`[확인 사실]` The summary line is now *"The kind's declared rules minus the ones this record's
checkers abstained on."* `[측정]` That is exactly the body — `applicable = RULES_BY_KIND[kind]`,
`unevaluated = {entry["rule"] for entry in not_evaluated}`,
`return [rule for rule in applicable if rule not in unevaluated]` — with no completeness claim
attached. Both round-1 defects are gone:

1. *"reached a verdict"* → replaced by the subtraction, stated as subtraction.
2. *"the **two** ways the bookkeeping can lie are refused here"* → now *"This refuses two of the
   ways the bookkeeping can lie, **not every way**"*, and the third is named in the same
   docstring: *"a rule declared in `RULES_BY_KIND[kind]` that reaches no verdict at all — it is
   computed by subtraction, so such a rule is simply left in the returned list,
   indistinguishable from one that actually ran."*

`[측정]` The route out of the function exists and resolves: the docstring says *see the module
docstring's "What `_coverage` actually checks"*, and
`grep -c 'What `_coverage` actually checks' handler.py` → **3**. A reader who opens `_coverage`
alone now gets the correction without leaving the docstring, and a pointer if they want the
fuller one.

`[추론]` I looked specifically for round 1's failure mode one level down — a correction that is
itself an overstatement — inside this docstring, and did not find one. Every clause I could
drive is accurate: the two refusals raise (round 1, probes B1/B2/C), the third does not
(probe A, re-run below). The surviving pre-existing clause *"Neither is reachable from today's
ten rules"* now sits under a `[확인 사실]` label while being structural inference rather than a
readable state; that is a label question, folded into B2, not a truth question.

## A2 — the two test docstrings: closed, and the phantom case now measured

`[측정]` `$TMPDIR/probe_phantom.py` — module loaded by path, `BLOG_RULES`/`RULES_BY_KIND`
rebound **in memory only**, plus the phantom added to a copy of the test file's hand-written
`RULES_BY_KIND` exactly as a rule author would:

```text
raised:                        None
clean:                         True
phantom in rules_evaluated:    True
assert evaluated.isdisjoint(unevaluated_rules(body))              → True
assert evaluated | unevaluated_rules(body) == RULES_BY_KIND[kind] → True
```

`[확인 사실]` So both assertions pass on a body in which a declared rule never ran — the
construction round 1 described but did not execute. The docstrings no longer claim otherwise:

- `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly` dropped *"never both and never
  neither"* for *"disjoint and their union is this kind's declared rule set — never both, and
  never outside it"*, then states plainly: *"This does not prove 'never neither'."*
- `TestCleanMeansEveryApplicableRuleRan` keeps *"reached a verdict"* as a statement of what
  `clean` is **meant** to mean — which is correct and is the class's subject — and adds what the
  test below actually proves, with *"Neither assertion can observe whether a rule in
  `rules_evaluated` ran."*

`[추론]` Keeping the aspirational sentence and adding the narrower one is the right trade here for
the same reason TASK-006's consequence 3 kept its original: the record stays readable twice. The
two sentences are now unambiguously about different things (the field's intended meaning vs. the
test's reach), so the round-1 defect — one sentence doing both jobs — is gone.

## B1 (new, blocking) — the round-2 structural claim is false on the module's own happy path

`[확인 사실]` Round 2 rewrote the module docstring's universal claim as `[추론]` and supplied a
structural reason, `handler.py:116–121`:

> `[추론]` Today's ten rules always reach one branch or the other on every input this module
> classifies — not measured against every input, but structural: `_check_blog` and `_check_trend`
> are straight-line functions with no early return, so **each of the ten checkers they call
> always either appends a finding or an abstention before either function returns.**

`[측정]` `$TMPDIR/probe_branch.py`, the module's own clean fixtures (`a_blog_record` /
`a_trend_record` field-for-field), calling the two checkers directly:

```text
_check_blog:  findings=0 abstentions=0
   rules that appended NOTHING: blog.invalid_postdate, blog.link_equals_bloggerlink,
                                blog.missing_content, blog.missing_link
_check_trend: findings=0 abstentions=0
   rules that appended NOTHING: all six trend rules
```

`[측정]` `$TMPDIR/probe_branch2.py`, 125 `(link, bloggerlink, postdate)` combinations over
`{"", "x", the bloggerlink URL, None, "20260230"}`:

```text
blog inputs tried: 125; inputs where >=1 declared rule appended NOTHING: 125
```

`[확인 사실]` A rule that **passes** appends nothing. That is the design — `_check_blog` appends
only inside `if not link_text:`, `if title_blank and description_blank:`, and so on — and it is
why subtraction produces the right answer for a passing rule. So the sentence is false in both
halves: the ten checkers do not always append, and on a clean record no rule reaches "one branch
or the other" in the sense the preceding sentence establishes (fired, or abstained).

`[추론]` Why this is blocking rather than a wording nit. The paragraph's entire job is to let a
reader tell *"in `rules_evaluated` because it passed"* apart from *"in `rules_evaluated` because
it never ran"*. This sentence tells the reader the distinguishing signal is an append. It is not —
the two cases are byte-identical in the emitted body, which is the whole finding. A P1 reader
who builds a check on the stated rule ("a declared rule that appended to neither list is a bug")
flags every clean record, and a reader who trusts the reassurance ("today's ten can't hit the
gap, they always append") is reassured by something untrue. It is the over-reassurance direction,
in the paragraph written to remove an over-reassurance.

`[추론]` Failure class: **specification**, same class as round 1's A1, one level further down
again. The repair is a half-sentence and needs no executable change: the structural property that
actually holds is that `_check_blog` and `_check_trend` are straight-line with no early return, so
**every checker's condition is evaluated** on every record — the rules are all *decided*, and a
decision of "passes" appends nothing by design. That is true, it is the reason subtraction is
sound for today's ten, and it does not require the false append claim.

`[측정]` The "no early return" half is true as written: `grep` over `_check_blog` and
`_check_trend` finds exactly one `return` each, the final `return findings, not_evaluated`.

## A3 — labels: the two named ones are closed; B2 is a minor residual

`[확인 사실]` Both round-1 mislabels are corrected as the packet asked:

| Claim | Round 1 | Round 2 | Correct per `evidence-labels.md` |
|---|---|---|---|
| *"`rules_evaluated` is computed by subtraction"* | `[측정]` | `[확인 사실]` | yes — §경계, a directly checkable property of an existing artifact (`handler.py:404`) |
| *"today's ten rules always reach one branch or the other on every input"* | `[측정]` | `[추론]` | yes as a **type** — a universal over inputs is not an observation. Its content is B1. |

`[확인 사실]` The worker's reported voluntary third is real: `_coverage`'s new docstring paragraph
carries `[확인 사실]`, not `[측정]`, and its content (which two cases the guard refuses) is
readable from the function body. Correct.

`[측정]` **B2, minor.** Two `[측정]` labels were introduced this round in
`test_normalizer_rule_baseline.py` on claims that are not observations from a stated procedure:

- `TestCleanMeansEveryApplicableRuleRan:554` — *"`[측정]` What the test below actually proves is
  narrower … disjoint … union equals this kind's declared rule set … Neither assertion can
  observe whether a rule in `rules_evaluated` ran."* The first half is readable from the two
  `assert` lines → `[확인 사실]`; the second half is inference → `[추론]`. One label over two
  roles is the thing §"하나의 문장에 역할을 섞지 않는다" forbids.
- `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly:573` — *"`[측정]` This does not
  prove 'never neither'."* An inference about the test's reach, with no input, procedure,
  environment or time recorded, which §`[측정]`'s metadata list requires. `[추론]` with a pointer
  to this report's probe would carry it.

`[추론]` Not blocking and not a regression in truth — both sentences are *correct*, they are
typed wrong. Recorded because it is the same principle A3 raised, applied unevenly: the worker
fixed it in `handler.py` and re-introduced it in the file it edited next.

`[추론]` One tension worth the orchestrator's attention rather than the worker's: acceptance
criterion 2 requires the gap to be stated *"with `[측정]`"* in the module docstring, and A3's
instruction moved that paragraph's labels off `[측정]`. The `RULES_BY_KIND` comment still carries
`[측정]` on the gap and its content is genuinely a measured behavior (round 1's probe A), so the
criterion is met somewhere in the add-on. The criterion's wording and the label convention
disagree; the convention should win, and the criterion should be reworded rather than the labels
reverted.

## A4 — the verification command: closed, with the positive control shown

`[측정]`

```text
grep -rn "abstention" .../normalizer.rule.baseline   → 16 lines   (positive control: non-empty)
grep -rn "abstention branch" .../normalizer.rule.baseline → nothing
handler.py:122  missing its abstention
handler.py:123  branch and a wrong `clean: true` is review — the same distinction `AGENTS.md` draws
```

`[확인 사실]` The packet's `Verification` block now runs `grep -rn "abstention"`. `[측정]` I read
all 16 hits; every one is a correct use of the word, and `:122–123` is the packet's own required
sentence naming the unenforced property, split by the docstring's line wrap. It is correct text
and should stay. `[추론]` The command now fails loudly if the corrected prose is deleted, which
the round-1 command did not — A4's method complaint is answered.

`[추론]` Cosmetic only, not a finding: line 122 (*"missing its abstention"*) is a four-word line
because the round-1 insert preserved the old wrap point. Re-wrapping it would also remove the
line-split that made A4 findable, so it is a trade, not a defect.

## Inertness — one check, as asked

`[측정]` `$TMPDIR/inert2.py`, `ast.dump()` of `git show HEAD:<path>` against the working file with
every module, class and function docstring blanked before comparison:

```text
handler.py                       docstring-stripped AST identical: True   (raw source differs)
test_normalizer_rule_baseline.py docstring-stripped AST identical: True   (raw source differs)
```

`[확인 사실]` This **confirms** the orchestrator's claim for both files. `[추론]` Comments are
absent from the AST and docstrings were blanked, so identity here means every remaining
executable construct — including each `assert` in the test file — is unchanged. Round 1's
four-way battery is not rebuilt; it does not need to be.

`[측정]` The handoff's numbers reproduce:

```text
scoped suite (3 files)                    → 149 passed in 0.84s
./scripts/check-addons.sh …rule.baseline  → normalizer.rule.baseline        ok
ruff (handler.py + the test file)         → All checks passed!
mypy handler.py                           → Success: no issues found in 1 source file
git diff --stat                           → addon.toml 2, handler.py 56, test file 12
```

`[추론]` `handler.py`'s 56 is round 1 plus round 2 together, not round 2 alone; the handoff says
"for the round" and means the cumulative working-tree diff. Harmless, but it is the kind of number
a later reader would mis-attribute.

## Allowed-file compliance

`[측정]` `git diff` over the tracked files this packet may touch:

| File | Changed | Round | Allowed? |
|---|---|---|---|
| `addons/normalizer.rule.baseline/handler.py` | yes | 1 + 2 | yes |
| `addons/normalizer.rule.baseline/addon.toml` | yes, 1 line | **round 1 only** — the F3 cross-reference | yes |
| `tests/test_normalizer_rule_baseline.py` | yes, docstrings only | round 2 | yes |
| `task-packets/TASK-006-…md` | yes | **round 1 only** — consequence 3 block; `Review` is the orchestrator's | yes / orchestrator |
| `task-packets/TASK-009-…md` | yes | Status + Worker handoff + Verification | yes |

`[확인 사실]` The worker's round-2 claims check out: `addon.toml` carries only the round-1
one-line change, and TASK-006 contains no round-2 or A1 text (`grep -n "A1\|[Rr]ound 2"` → no
hits). `[추론]` The three other modified tracked files (`POC-CONTRACT-0.1.md`,
`docs/project-state.md`, `tests/README.md`) are the concurrent OBF session's, unchanged in
character from round 1's attribution table. Not this worker's.

## Attacks that held in round 2

`[측정]`

- `_coverage`'s new docstring — every clause driven; no new overstatement found in it.
- The two test docstrings — the phantom construction passes both assertions, and neither
  docstring claims it would not.
- Diff inertness, both files — docstring-stripped ASTs identical to `HEAD`.
- Suite count, `ruff`, `mypy`, `check-addons.sh` — all reproduced.
- Allowed-file discipline — nothing outside the list, and the round-1 files were not re-edited.
- `_check_blog` / `_check_trend` early returns — one `return` each, so the "no early return"
  half of B1's sentence is true. Only the append half is false.

## Required follow-up

1. **Blocking (B1).** Replace the false half of the module docstring's `[추론]`. What is true and
   sufficient: `_check_blog` and `_check_trend` are straight-line with no early return, so every
   checker's condition is evaluated on every record — each of today's ten rules is *decided*, and
   a rule that passes appends nothing by design, which is why subtraction is currently sound.
   Prose only; the AST identity above survives it.
2. **Minor (B2).** Re-type the two new test-file `[측정]`s as `[확인 사실]` / `[추론]`, splitting
   the class docstring's sentence so one paragraph carries one role.
3. **Orchestrator, not worker.** Acceptance criterion 2 pins `[측정]` to a paragraph A3 correctly
   moved off `[측정]`. Reword the criterion.
4. **Unchanged, for the gate.** F1's gap and F2's forgeability remain stated and not closed; F4
   untouched. Correctly out of scope in both rounds.

---

# Round 3 — 2026-08-20 — `PASS`

`[결정]` Result: **`PASS`**. B1 is closed and B2 is closed. Nothing in round 3 is blocking, and
I am not raising a fourth finding on this paragraph. One wording imprecision is recorded below
as **C1 (non-blocking)** because it is worth a reader's attention, not because it falsifies
anything — and because the imprecise phrase is the one *this report* handed the worker in
round 2's follow-up 1, so it is mine before it is theirs.

Subject, in full: one paragraph of `handler.py`'s module docstring (`:116–128`) and two label
groups in `test_normalizer_rule_baseline.py` (`:554–558`, `:574–578`). Rounds 1 and 2 were not
re-attacked; their findings stay closed.

Environment: `.venv` Python 3.13, `HEAD` = `70fa293`, working tree as of this session. Rounds 1
and 2 are uncommitted, so every `git show HEAD:` baseline below is the pre-round-1 file.

## B1 — the replacement paragraph, `handler.py:116–128` — `PASS`

The paragraph asserts five things. Each was attacked separately.

### B1.a — "`_check_blog` and `_check_trend` are straight-line functions with no early return"

`[측정]` True, by AST rather than by reading. Each function contains exactly one `Return`
(`_check_blog:555`, `_check_trend:662`), and neither contains any `Break`, `Continue`, `Raise`,
`While`, `Try`, `With`, or `Assert` node. `_check_trend` does contain one `For` — over a
**literal 4-tuple** `("dimension", "title", "period", "timeUnit")`, so it is unconditional and
fixed-length and cannot skip an iteration. Every rule's `if` is a top-level statement of its
function (blog `:502 :516 :527 :539`; trend `:596 :611 :626 :644`, plus `:590` inside that
loop); none is nested inside another rule's branch. There is no comprehension in either
function.

Reproduce: `ast.parse` the file, walk both `FunctionDef`s, list `Return`/`Break`/`Continue`/
`Raise`/`Try` nodes and the `lineno` of each `If`.

`[추론]` "Straight-line" is loose for a function containing a loop, but the loop is
unconditional, so the conclusion the word is used to support holds.

### B1.b — "every checker's condition is evaluated on every record they see"

`[측정]` Held under a line-level trace. `sys.settrace` was attached, `_check_blog` was driven
over **1,350** records (the cross product of five `link`, five `bloggerlink`, three `title`,
three `description`, six `postdate` values, including `None`, `5`, `"   "`, `{"x": 1}`,
`"20260230"`, `12`) and `_check_trend` over **11,520** (five `dimension`, three `title`, four
`period`, four `timeUnit`, eight `ratio` — including `True`, `float("nan")`, `10**400`,
`"a lot"` — three `startDate`, two `endDate`). For all **12,870** records, every rule's guard
line executed, and **no input raised**. So no enclosing `if`, short-circuit, `try`, or
comprehension skips a rule for any input, and no exception cuts a checker short before a later
rule is reached. Since `_parse` admits only `json.loads` output, the value space probed covers
the JSON types a record can actually carry.

Reproduce: the probe is in this session's scratchpad (`b1_probe.py`); it is 40 lines and is
described completely in the paragraph above.

### B1.c — "a rule whose condition does not hold is decided as passing, and passing records nothing … a rule whose condition does hold appends either a finding or an abstention"

`[확인 사실]` True under the reading the paragraph's own second clause forces: *condition* = the
rule's `if`/`elif` guard chain. Every one of the ten guard chains has the shape "guard(s) hold →
append a finding or an abstention; otherwise append nothing", and **every guard body of both
functions appends** — there is no branch that holds and records nothing. The disjunction "a
finding **or** an abstention" only makes sense under that reading, since a rule's *violation*
test can only ever produce a finding.

See **C1** for what the other reading of "condition" would make of the same sentence.

### B1.d — "a name in `rules_evaluated` because it passed is byte-identical to one there because it never ran"

`[측정]` Verified **by construction**, not by reading. `handler.py` was loaded twice by path. In
the second copy `_check_blog` was rebound in memory to a hand-written variant identical to the
original **except that the whole `blog.invalid_postdate` block is absent** — the "rule declared
but never implemented" case — while `RULES_BY_KIND` still declares the rule. Both copies were
driven through `run()` over the same clean blog record.

```text
evaluated-and-passing : {"clean": true, "findings": [], "record_kind": "document",
                         "rule_report_version": "0.1",
                         "rules_evaluated": ["blog.missing_link", "blog.missing_content",
                                             "blog.invalid_postdate",
                                             "blog.link_equals_bloggerlink"],
                         "rules_not_evaluated": []}
never-ran (block gone): (the same bytes)
body byte-identical    : True
notes identical        : True
```

`[측정]` And the harm the paragraph is describing was produced, not asserted: feeding the
same deleted-rule module a record with `postdate: "20260230"` — the calendar-invalid date the
rule exists to catch — emits a body **byte-identical to the clean one**, `clean: true`,
`findings: []`, with `blog.invalid_postdate` sitting in `rules_evaluated`. The intact module
emits `clean: false` with the finding. In-memory rebinding was used throughout, so round 1's
`__pycache__` `(mtime, size)` trap does not apply.

### B1.e — "`_coverage` … does not raise, and cannot by construction"

`[측정]` The deleted-rule run above raised nothing and returned a full `rules_evaluated`. This
is round 1's clause, re-confirmed as a side effect rather than re-attacked.

### The over-reassurance hunt

`[측정]` I searched the new paragraph for the failure mode that produced rounds 2 and 3: a
sentence that reassures beyond what the code supports. The paragraph contains **no unscoped
"always"**. Its one "cannot" (`_coverage` "does not raise, and cannot by construction") is
backed structurally and was reproduced above. Its universal claim is explicitly de-measured —
*"not measured against every input, but structural"* — which is the correct move under
`evidence-labels.md`, and I then measured it anyway (12,870 records) and it held. The
paragraph's punchline is a **negative** one: that passed and never-ran are indistinguishable,
and that review is the only thing standing between a missing abstention branch and a wrong
`clean: true`. A paragraph whose conclusion is "you cannot tell these apart" is not structurally
capable of the over-reassurance rounds 2 and 3 failed on. The worker's self-check claim in the
handoff — that no new universal was introduced outside the attacker's own structural reason,
the attacker's own measured result, or a conditional — is **accurate as far as I can falsify
it**.

## C1 (non-blocking, wording) — "condition" carries two meanings, and one of them is false

`[측정]` For the five rules with an abstention path, the rule's **own violation test** is *not*
executed on an abstaining input, though the rule still appends an abstention. Traced:

| record | violation test never executed | abstention recorded |
|---|---|---|
| blog, `bloggerlink` absent | `link_text == bloggerlink_text` (`:545`) | `blog.link_equals_bloggerlink` |
| trend, `dimension` blank | `dimension not in TREND_DIMENSIONS` (`:600`) | `trend.unknown_dimension` |
| trend, `timeUnit` blank | `time_unit not in TREND_TIME_UNITS` (`:615`) | `trend.unknown_time_unit` |
| trend, `ratio` not a number | `0 <= ratio <= 100` (`:631`) | `trend.ratio_out_of_range` |
| trend, `period` unparseable | `start <= period <= end` (`:648`) | `trend.period_outside_window` |

`[추론]` So *"every checker's condition is evaluated on every record"* is true if "condition"
means the rule's guard chain (B1.b, B1.c) and false if it means the rule's violation test. The
paragraph's next sentence — "either appends a finding **or an abstention**" — only parses under
the first reading, so the paragraph is internally consistent and a reader who follows it to its
conclusion is not misled: under **either** reading, no rule is silently skipped, every rule is
visibly decided, and the byte-identity conclusion is unchanged.

`[추론]` This is why C1 is not a fourth `FAIL`. Round 2's B1 was blocking because its sentence
was false under *every* reading and because the false clause supported a **reassuring**
conclusion (an append is the signal that separates passed from never-ran). C1's sentence has a
true reading, it is the reading the paragraph supplies, and the conclusion it supports is the
pessimistic one. `[확인 사실]` It is also the exact phrase this report prescribed in round 2's
"Required follow-up 1"; the worker used it as given.

`[결정]` If anyone touches this paragraph again for any other reason, "condition" → "branch"
(or "guard") in that one sentence removes the ambiguity at zero cost. Opening a fourth round
for it alone is not worth the paragraph's remaining stability.

## B2 — the two relabelled claim groups — `PASS`

`[확인 사실]` `TestCleanMeansEveryApplicableRuleRan` (`:554–558`) now reads: `[확인 사실]` for
*"`rules_evaluated` and `rules_not_evaluated` are disjoint, and their union equals this kind's
declared rule set — readable directly off the two `assert` lines below"*, and `[추론]` for
*"neither assertion can observe whether a rule in `rules_evaluated` ran"*. Judged against
`evidence-labels.md` §"판정 순서" and §"`[확인 사실]`과 `[측정]`의 경계`":

- The first is a directly verifiable property of an existing artifact — the two `assert`
  statements are ten lines below the sentence and say exactly that — so rule 5, `[확인 사실]`.
  Correct.
- The second derives meaning from other evidence rather than reporting a readable state, so
  rule 3, `[추론]`. Correct.
- Neither claims an input, procedure, environment, or time, so neither may be `[측정]`. The
  round-2 labels are properly retired.
- §"하나의 문장에 역할을 섞지 않는다" is satisfied: round 2 had one sentence carrying both roles;
  round 3 split it at the role boundary.

`[확인 사실]` `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly` (`:574–578`) is
`[추론]` on *"this does not prove 'never neither'"*, with a pointer to this report's phantom-rule
construction. Correct: it is an inference about the test's reach. It could defensibly have been
`[측정]` (round 2 *did* measure it here), but `[추론]` plus a citation of where the measurement
lives is the more conservative of the two and does not overstate.

`[측정]` The unlabelled universal that opens the same docstring — *"Whatever happens to a record,
`rules_evaluated` and `rules_not_evaluated` are disjoint and their union is this kind's declared
rule set"* — was attacked rather than assumed, because it is the shape round 2's B1 hid in. It
holds: across the same **12,870** records driven through `_coverage`, zero `AddonOutputInvalid`
and zero invariant violations. It is also structural — `_coverage` raises unless the abstained
set is a subset of the declared set, then returns the declared set minus it — so for any body
that is emitted at all, the invariant is exact. No finding.

`[확인 사실]` Not in scope and not a round-3 defect, noted so a later reader does not mistake it
for one: the `[측정]` at the head of the same class docstring (*"TASK-004's review found …"*)
is round-1-and-earlier text, reporting a prior review's finding rather than an observation from
that work. Round 3 did not write it and B2 did not name it.

## Inertness — one check

`[측정]` `ast.dump()` of `git show HEAD:<path>` against the working file, with every module,
class, and function docstring blanked to `""` before comparison:

| file | docstring-stripped AST identical to `70fa293` |
|---|---|
| `addons/normalizer.rule.baseline/handler.py` | **True** |
| `tests/test_normalizer_rule_baseline.py` | **True** |

Both files differ from `HEAD` at the byte level and not at all in executable structure, across
all three rounds. This confirms the orchestrator's independent check and the worker's. Comments
are absent from the AST, so this does not speak to comment changes — which is immaterial, since
no comment in either file participates in behaviour (`ruff` and `mypy` below are clean, so no
`# type: ignore` or `# noqa` was introduced or removed with effect).

`[측정]` The handoff's verification block reproduces exactly, in this working tree:

```text
pytest -q -p no:cacheprovider (three scoped files)  → 149 passed in 0.86s
./scripts/check-addons.sh …/normalizer.rule.baseline → normalizer.rule.baseline  ok
ruff check …/normalizer.rule.baseline                → All checks passed!
mypy …/normalizer.rule.baseline/handler.py           → Success: no issues found in 1 source file
grep -c "Another documentation gap, unrelated to input shape" handler.py → 1
```

## Allowed-file compliance

| file | on the list | round-3 content | verdict |
|---|---|---|---|
| `addons/normalizer.rule.baseline/handler.py` | yes | one docstring paragraph | ok |
| `tests/test_normalizer_rule_baseline.py` | yes | two docstrings, no assertion | ok |
| `addons/normalizer.rule.baseline/addon.toml` | yes | **round 1 only** — the single quoted-heading line | ok |
| `task-packets/TASK-006-…md` | yes | **round 1 only** — the consequence-3 correction block; the `Review` edit is the orchestrator's, as recorded in round 1 | ok |
| `task-packets/TASK-009-…md` | yes | `Status` + Round 3 handoff | ok |

`[측정]` `git diff --stat` also shows `contracts/experimental/POC-CONTRACT-0.1.md`,
`docs/project-state.md`, `docs/open-questions/OQ-004-snapshot-boundary.md`, and
`experiments/integrated-p0/tests/README.md` modified. Grepping their diffs for
`rule.baseline`, `TASK-009`, and `coverage` returns **nothing** — they belong to the concurrent
OBF session, not to this packet. `[추론]` Two of them (`contracts/**`, `project-state.md`) are on
TASK-009's forbidden list; attribution matters here, and the evidence attributes them elsewhere.

## What I tried and could not break

`[측정]`

- Every clause of the replacement paragraph, separately: no early return (AST), condition
  evaluated on every record (12,870-record line trace), guard-holds-implies-append (every guard
  body inspected), byte-identity (built, not read), `_coverage` cannot raise on the gap
  (produced).
- A checker that raises mid-way and skips a later rule: none found across 12,870 inputs
  including `nan`, `10**400`, `True`, a `dict`-valued field, and `None` everywhere.
- A guard that holds and appends nothing: none exists in either function.
- A new unscoped "always"/"cannot" in the round-3 text: none, and the one universal present is
  explicitly de-measured and then measured true.
- The unlabelled universal in the test docstring: held, and is structural.
- Both files' inertness: docstring-stripped ASTs identical to `HEAD`.

## Required follow-up

1. **Nothing blocking.** B1 and B2 are closed. The paragraph now describes what the code does.
2. **C1, at the next edit of that paragraph and not before**: "condition" → "branch"/"guard" in
   one sentence.
3. **Still open from round 2, and still the orchestrator's, not a worker's**: acceptance
   criterion 2 of TASK-009 requires the gap to be stated *"with `[측정]`"*, while A3 correctly
   moved that paragraph off `[측정]` to `[확인 사실]`/`[추론]`. The criterion contradicts the
   accepted correction and should be reworded.
4. **Unchanged, for the gate.** F1's gap (a declared rule reaching no verdict is subtracted into
   `rules_evaluated`, and the record can be `clean: true`), F2's `BOUNDED` forgeability, and F4
   (`source_item_key` unbounded) remain **stated and not closed**. That is the packet's Excluded
   decision, correctly held for three rounds. `[추론]` The add-on's record is now accurate about
   its own guarantees; the guarantees themselves are P1's to build.
