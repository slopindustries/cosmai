# TASK-009 — Say what `_coverage` actually checks, and stop claiming a marker cannot be forged

- Status: `ACCEPTED`
- Phase: P0-B, charter closure
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`
- Attacker: `adversarial-reviewer`
- Orchestrator: project owner's session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

`normalizer.rule.baseline@0.1` describes two protections it does not have. Both descriptions
become what the code measurably does, and neither rule's logic changes.

`[측정]` This packet exists because
[ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md)
returned `FAIL` on [TASK-006](TASK-006-rule-baseline-claims-repair.md) — **not** on the four
claims that packet repaired, all of which held under 11 mutations, six-interpreter
`PYTHONHASHSEED` determinism controls, and 16,000 differential comparisons, but on a fifth
claim TASK-006 wrote on the way past.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5 hypothesis 6
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md),
  [DP-021](../../decisions/DP-021-schema-0-2-trend-points.md),
  [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`CONTRACT-ADDON@1.3`](../../../contracts/experimental/CONTRACT-ADDON-1.3.md)
- Open Questions: [OQ-013](../../open-questions/OQ-013-addon-responsibility-boundary.md) —
  *"what holds a judgment no other layer can check"* is the question F1 lands in
- Owner decisions required: `none`. `AGENTS.md` already fixes the direction:
  *"Do not describe a convention as a control."*
- Required evidence or environment: the R2 attack report above, in full. Read F1, F2, F3, and
  F4 before writing anything.

## The two findings, as measured

`[측정]` **F1 — `_coverage` is computed by subtraction, so it cannot catch the thing three
comments say it catches.** `return [rule for rule in applicable if rule not in unevaluated]`
means a rule declared in `RULES_BY_KIND` that reaches no verdict and appends no abstention
lands in `rules_evaluated` anyway, and the record is emitted `clean: true` with no
`AddonOutputInvalid`. The existing test drives only the opposite direction — a verdict from
*outside* the declared set. `[측정]` The attacker also measured the counterweight: the test
file's hand-written `RULES_BY_KIND` **does** catch a module-only edit, so what exists is
protection against forgetting the *list*, not against forgetting the *abstention branch*.

`[측정]` **F2 — the `BOUNDED` marker is forgeable.** Its comment claims an untrusted key
spelled the same way "cannot be mistaken for this marker". A source `ratio` of
`{"<bounded by the rule baseline>": "a dict too large to echo, bounded away in full"}`
produces a `found` **byte-identical** to a genuine over-size bound.

## Scope

### Included

- **F1, in all three places the claim appears**: `handler.py`'s module docstring (around the
  paragraph ending *"a rule added without its abstention branch"*), the comment above
  `RULES_BY_KIND` (*"so a rule added without an abstention branch fails the run instead"*),
  and TASK-006's Worker handoff consequence 3.

`[확인 사실]` **Round 2, 2026-08-20 — the list above is the planner's, and it was wrong.**
R2 F1 named the module docstring, **`_coverage`'s own docstring**, and TASK-006 consequence
3. This packet silently substituted "the comment above `RULES_BY_KIND`" for the second, so
the first worker corrected three places faithfully and left the one R2 actually pointed at
untouched. `ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md` A1 measured it. The rework
below is the planner's error to repair, not the worker's. Each becomes what `_coverage` measurably
  does: it rejects a body whose evaluated rules are not a subset of the kind's declared set,
  which catches a verdict from an undeclared rule and a stale `RULES_BY_KIND`, and **does
  not** catch a declared rule that silently reaches no verdict.
- **The unenforced property, named rather than dropped.** Say plainly, with `[측정]`, that
  a rule added without an abstention branch is emitted `clean: true` today, and that the
  only thing standing between that and a wrong record is review. That sentence is the
  finding's permanent form.
- **F2**: the `BOUNDED` comment states that the marker is a *report* for a human reader and
  not a parseable channel, and that a source key spelled identically produces identical
  bytes. Measured, not hedged.
- **F3**: `addon.toml` cross-references a `handler.py` docstring heading — *"Question:
  `output_contract_version` collides in spelling with an unrelated schema"* — that does not
  exist. Point it at a heading that does, or drop the quoted title and keep the reference
  general. `grep -c` is the check.
- **F4, recorded and not fixed.** `source_item_key` is unbounded while `found` is bounded.
  State it in the handoff as out of scope with its reason; it lives outside this packet's
  allowed files.

### Included, round 2

`[측정]` All four items come from `ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md`. Read it
before starting. Nothing executable changes in this round either.

- **A1 (blocking) — `_coverage`'s own docstring, `handler.py:378–384`.** Two clauses are
  false and neither carries a pointer to the correction 270 lines above:
  *"Which of this kind's rules reached a verdict"* — the return is `applicable − unevaluated`,
  so a rule that reached no verdict is in it — and *"the two ways the bookkeeping can lie are
  refused here"* — there are three, and the third is not refused. Make both say what the
  function does, and reference the module docstring's `[측정]` so a reader who opens the
  function alone is not left with the belief R2 already falsified.
- **A2 (moderate) — two claims in `test_normalizer_rule_baseline.py`.** `:568` says every
  applicable rule is accounted for *"never both and never neither"*, and the class docstring
  at `:549` says *"reached a verdict"*. `[측정]` "Never neither" is the property that is not
  enforced: a phantom rule added to both the module's set and the test's hand-written set —
  the ordinary thing a rule author does — leaves both assertions passing while the rule never
  ran. Correct the two docstrings. **No assertion changes**, for the reason round 1 held: the
  ten rules survived 26 + 11 mutations and 16,000 + 4,000 differential comparisons.
- **A3 (minor) — two labels.** *"`rules_evaluated` is computed by subtraction"* is
  `[확인 사실]` (readable in the source), not `[측정]`. The claim that today's ten rules always
  reach one branch or the other **for every input** is a universal over inputs and cannot be a
  measurement; state it as `[추론]` with its structural reason — `_check_blog` and
  `_check_trend` have no early return — or record the input, procedure, and environment that
  would make it one.
- **A4 (minor) — this packet's own verification command.** `grep -rn "abstention branch"`
  returning nothing is not evidence of absence: the phrase survives at `handler.py:119–120`
  split across a line break, where its use is correct. Replace it with
  `grep -rn "abstention"`, which has a positive control.

### Included, round 3

`[측정]` One sentence, from `ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md`'s Round 2 B1.
Rounds 1 and 2 are closed — A1–A4 all verified shut, the phantom-rule case built and measured,
inertness confirmed on both files. This round is a half-sentence and nothing else.

- **B1 (blocking) — `handler.py:118–120` gives a false reason for a true conclusion.** The
  paragraph added in round 2 says today's ten rules always reach one branch because
  *"each of the ten checkers they call always either appends a finding or an abstention before
  either function returns"*. `[측정]` That is false, and the attacker measured it on the
  module's own fixtures: on a clean record `_check_blog` and `_check_trend` both return
  `findings=0 abstentions=0` — every declared rule appends **nothing**. Across 125
  `(link, bloggerlink, postdate)` combinations, all 125 have at least one declared rule
  appending to neither list. **A rule that passes appends nothing; that is the design, and it
  is why subtraction is correct in the first place.**

  `[추론]` It is blocking rather than cosmetic because of where it sits: the paragraph exists
  to let a reader tell *"in `rules_evaluated` because it passed"* from *"in `rules_evaluated`
  because it never ran"*, and this sentence names the append as the signal that separates
  them — which is precisely the thing that does not. An over-reassurance inside the paragraph
  written to remove an over-reassurance.

  The property that actually holds: every checker's **condition is evaluated** on every record
  the module classifies, so every rule is decided; a rule that passes records nothing, and a
  rule that abstains says so. Write that. No executable change, as in both prior rounds.

- **B2 (minor) — two new `[측정]` labels in the test file**, on claims that are readings of
  the source or inferences from it rather than observations. Round 2 applied A3's principle to
  the handler and unevenly to the tests. Same fix, same rule in `evidence-labels.md`.

### Excluded

- **Any change to the ten rules' logic, and any new rule.** They are unchanged in what they
  decide across 26 mutations, 11 more, and 16,000 differential comparisons. Touching them
  now spends the strongest evidence this repository has, to fix a defect that is not in them.
- **Making `_coverage` observed rather than subtracted.** That is the other repair for F1 —
  registering each rule's outcome explicitly so an unevaluated rule is detectable — and it
  is deliberately not taken here: it re-plumbs the evaluation path of an add-on whose current
  behavior is the measured evidence, four working days before the freeze, to enforce a
  property P1 will rebuild anyway. `[결정]` P0 states the gap; P1 may build the control.
  If you believe the correction cannot be written honestly without it, **stop and say so**.
- Any change to `NormalizeOutcome`'s counters, the bucket assertions, the determinism
  controls, or the `PYTHONHASHSEED` test. They passed the attack and are not in scope.
- `addon_api`, `addon_host`, `platform_core`, `domain/`, contracts, Decision Packets,
  `project-state.md`, and every other add-on. **`normalizer.obf.product/` and
  `test_normalizer_obf_product.py` are being written by another session right now** — do not
  read or touch them.
- Editing the `Review` section of TASK-006 or of this packet. The orchestrator owns both.

### Allowed files

- `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py`
- `experiments/integrated-p0/addons/normalizer.rule.baseline/addon.toml`
- `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` — only if a test's
  *docstring* repeats the F1 claim. No assertion changes.
- `docs/agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md` — consequence 3
  of its Worker handoff only, marked as a correction with its date, not silently rewritten
- this packet's `Status` line and `Worker handoff` section

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- every other add-on, `addon_api`, `addon_host`, `platform_core`, `domain/`
- `contracts/**`, `docs/decisions/**`, `docs/project-state.md`
- the R2 attack report itself — it is the attacker's record and is not edited by a worker

## Acceptance criteria

1. No sentence anywhere in the allowed files claims `_coverage` catches a rule that reaches
   no verdict. `grep -rn "abstention branch"` over the add-on returns only corrected text.
2. What `_coverage` does catch is stated, and the gap it does not catch is stated with
   `[측정]`, in the module docstring where a reader of the add-on will meet it.
3. The `BOUNDED` comment no longer claims non-forgeability, and states the collision.
4. The `addon.toml` cross-reference resolves: the quoted heading exists in `handler.py`, or
   the quotation is gone. Show the `grep -c` output both ways.
5. `git diff` over `handler.py` touches comments, docstrings, and nothing executable. Prove
   it: the scoped suite's pass count is unchanged, and so is the module's behavior under the
   `PYTHONHASHSEED` control.
6. TASK-006's consequence 3 is corrected in place with the correction visible as a
   correction — this repository's own habit, and the reason its records can be read twice.
7. `ruff` and `mypy` clean; `./scripts/check-addons.sh` still reports the add-on `ok`.

## Verification

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
  tests/environment/test_addon_layer_direction.py \
  tests/environment/test_agent_packet_record.py

./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline
.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline
.venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py

# Criterion 1 and 4, as commands rather than as claims.
grep -rn "abstention" experiments/integrated-p0/addons/normalizer.rule.baseline
grep -c "output_contract_version collides in spelling" \
  experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop if the honest correction cannot be written without changing executable code.** Say
  what the sentence would have to claim and why the code does not support it. A correction
  that quietly becomes a repair is how the defect this packet fixes was introduced.

## Worker handoff

- **Changed files:**
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py` — three prose
    edits only: the module docstring's `_coverage` paragraph (replaced with "What
    `_coverage` actually checks, and the gap it does not close"), the comment above
    `BLOG_RULES`/`RULES_BY_KIND`, and the comment above `BOUNDED`. No executable line
    changed — see the `git diff` in Commands and results.
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/addon.toml` — the
    `output_contract_version` comment's quoted cross-reference now names the heading that
    actually exists in `handler.py` ("Another documentation gap, unrelated to input
    shape") instead of one that does not.
  - `docs/agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md` — consequence
    3 of its Worker handoff, corrected in place with a dated `[측정]` correction block
    appended below the original text (original left unedited, per this packet's "not
    silently rewritten" instruction).
  - This packet's `Status` and `Worker handoff`.
  - `test_normalizer_rule_baseline.py` was **not** touched:
    `grep -n "abstention branch" experiments/integrated-p0/tests/test_normalizer_rule_baseline.py`
    returned nothing, so no test docstring repeated the F1 claim.

- **What changed, in one sentence each:**
  - F1: the module docstring and the `RULES_BY_KIND` comment no longer claim `_coverage`
    fails the run when a declared rule reaches no verdict; both now state what it does
    catch (a stray rule name, a rule both fired and abstained) and name the uncaught case
    (a declared rule that reaches neither branch is subtracted into `rules_evaluated` and
    the record can still be `clean: true`) as `[측정]`, with review named as the only thing
    currently standing between that gap and a wrong record.
  - F2: the `BOUNDED` comment no longer claims a same-spelled source key "cannot be
    mistaken for" the marker; it now states the collision is byte-identical and that the
    field is a diagnostic for a human reader, not a channel a caller should trust.
  - F3: `addon.toml`'s quoted heading now exists in `handler.py`.
  - F4: not touched — see Limitations below; TASK-009's own scope already recorded it as
    out of scope with its reason.
  - The ten rules' logic (`_check_blog`, `_check_trend`, and all rule bodies) is byte-for-byte
    unchanged; `_coverage`, `_bound_found`, `_bounded`, `_bounded_text`, and `run`'s
    executable code are unchanged.

- **Commands and results:**
  ```text
  export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

  .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
    tests/environment/test_addon_layer_direction.py \
    tests/environment/test_agent_packet_record.py
  → 149 passed in 0.83s

  ./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline
  → normalizer.rule.baseline        ok

  .venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline
  → All checks passed!

  .venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → Success: no issues found in 1 source file

  grep -rn "abstention" experiments/integrated-p0/addons/normalizer.rule.baseline
  → (no output — the phrase no longer appears anywhere in the add-on)

  grep -c "output_contract_version collides in spelling" \
    experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → 0

  grep -c "Another documentation gap, unrelated to input shape" \
    experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → 1   (the heading addon.toml now quotes does exist)
  ```
  `[측정]` `git diff -- .../handler.py` (reproduced in full in this session's transcript)
  touches only the module docstring and two `#:` comments; every line of executable code,
  including `_coverage`'s body, is byte-identical to the pre-edit file. Since the executable
  code did not change, the module's behavior under the six-interpreter `PYTHONHASHSEED`
  determinism control cannot have changed either — that control was not re-run because
  nothing it exercises was touched; the scoped suite (which includes it) passing at the same
  count (149, matching R2's 103 plus 46 from `test_agent_packet_record.py`) is the evidence
  for that claim in this handoff.

- **Evidence locations:**
  - The corrected prose: `handler.py`'s module docstring paragraph beginning "What
    `_coverage` actually checks, and the gap it does not close"; the comment above
    `BLOG_RULES`; the comment above `BOUNDED`.
  - `addon.toml`'s `output_contract_version` comment.
  - `docs/agent-workflow/task-packets/TASK-006-rule-baseline-claims-repair.md`, Worker
    handoff, F2 consequence 3 (correction block appended 2026-08-20).
  - This packet's diff is the whole of what changed; no other file was written.

- **Limitations and remaining risks:**
  - `[측정]` The correction states the gap `_coverage` does not close; it does not close it.
    `_coverage` still cannot detect a declared rule that reaches no verdict and appends
    nothing. That is the packet's Excluded item — making `_coverage` observed rather than
    subtracted is deliberately not done here — so this remains true after this packet as it
    was before it. What changed is only that the module now says so.
  - F4 (`source_item_key` unbounded while `found` is bounded) is recorded in the R2 report
    and in TASK-009's own Excluded section, not touched here — it lives outside
    `normalizer.rule.baseline`'s allowed files (it is a `NormalizedResult`/`domain.store`
    question) and this packet's scope does not reach it.
  - The `BOUNDED`-collision (F2) is now stated but not fixed; a source `ratio` shaped exactly
    like the marker still produces an indistinguishable `found`. The R2 report names two
    possible real fixes (escape a source key equal to `BOUNDED`, or move the marker to a
    sibling field); neither is in this packet's Included scope, which asked only for the
    comment to state the collision.

- **Newly discovered questions or blockers:** none. No unanswered consequential direction
  was met; the correction was writable without touching executable code, so the stopping
  condition about a correction quietly becoming a repair did not trigger.

### Round 2 (2026-08-20, closing `ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md`)

- **Changed files:**
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py` — two more prose
    edits, both docstrings, no executable line touched:
    - `_coverage`'s own docstring (A1, blocking). It still claimed *"the two ways the
      bookkeeping can lie are refused here"* and *"refusing anything that does not add up"*
      — the sentence R2's F1 named and this packet's round-1 Included list mistakenly
      substituted "the comment above `RULES_BY_KIND`" for. Now it names the two refusals it
      actually implements, states the third case it does **not** refuse (a declared rule
      that reaches no verdict, left in `rules_evaluated` by subtraction), and points at the
      module docstring's "What `_coverage` actually checks" paragraph, the way the
      `RULES_BY_KIND` comment already did.
    - The two `[측정]` labels the round-1 paragraph used (A3, minor): *"`rules_evaluated` is
      computed by subtraction"* is readable directly from `_coverage`'s body, so it is now
      `[확인 사실]`; *"today's ten rules always reach one branch or the other on every
      input"* is a universal claim over inputs with no per-input measurement behind it, so
      it is now `[추론]`, with the structural reason stated (`_check_blog`/`_check_trend`
      are straight-line, no early return, so each of the ten checkers they call always
      appends a finding or an abstention before either function returns).
    - A third `[측정]` I added while writing `_coverage`'s corrected docstring (not one of
      the four findings, but the same defect class) was labelled `[확인 사실]` for the same
      reason before this handoff was written, not after review.
  - `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` — two docstring edits
    (A2, moderate), no assertion touched:
    - `TestCleanMeansEveryApplicableRuleRan`'s class docstring (`:549`) kept its original
      *"every rule applicable to this record kind reached a verdict"* sentence (that is the
      property `clean` is *meant* to have, not a claim about what the test below proves) and
      gained a `[측정]` paragraph stating what the test actually checks: that
      `rules_evaluated`/`rules_not_evaluated` are disjoint and their union equals the kind's
      declared set — neither of which can observe whether a rule in `rules_evaluated` ran.
    - `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly`'s docstring (`:568`)
      no longer says *"never both and never neither"*; it says what the two assertions check
      (disjointness, union-equals-declared-set) and states plainly that "never neither" is
      not proven.
  - This packet's `Status` (unchanged at `WORKER_DONE`) and `Worker handoff` (this section).
  - No other file touched. `docs/agent-workflow/task-packets/TASK-006-…md` consequence 3 was
    not re-edited — round 2's Included list did not name it, and the round-1 correction block
    already stands.

- **What changed, in one sentence each:**
  - A1: `_coverage`'s own docstring no longer claims to refuse a declared rule that reaches
    no verdict; it names the two cases it does refuse and the one it does not, and points at
    the module docstring's fuller correction.
  - A2: the two test docstrings now describe what the disjointness/union-equality assertions
    check, not the unproven "every rule reached a verdict" reading.
  - A3: the round-1 paragraph's two `[측정]` labels are corrected to `[확인 사실]` (readable
    from source) and `[추론]` (a universal claim over inputs, with its structural reason
    stated) per `docs/conventions/evidence-labels.md`.
  - A4: this packet's own verification block (below) now runs `grep -rn "abstention"`
    instead of `grep -rn "abstention branch"` — the wrapped-phrase command that produced a
    false-negative-shaped "nothing" in round 1 even though `handler.py:119–120` (now
    `:122–123`) correctly uses the phrase split across a line wrap.
  - Nothing executable changed: `_coverage`'s body, the ten rules, `_bound_found`,
    `_bounded`, `_bounded_text`, and `run` are byte-for-byte unchanged from before this round
    and from before round 1.

- **Commands and results:**
  ```text
  export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

  .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
    tests/environment/test_addon_layer_direction.py \
    tests/environment/test_agent_packet_record.py
  → 149 passed in 0.85s

  ./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline
  → normalizer.rule.baseline        ok

  .venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline
  → All checks passed!

  .venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → Success: no issues found in 1 source file

  grep -rn "abstention" experiments/integrated-p0/addons/normalizer.rule.baseline
  → 16 lines, every occurrence a correct use of the word (verified by reading each)

  grep -rn "abstention branch" experiments/integrated-p0/addons/normalizer.rule.baseline
  → (no output) — the exact phrase no longer appears; it survives only split across a line
    wrap at handler.py:122–123, which is correct usage, not a leftover claim

  grep -c "output_contract_version collides in spelling" \
    experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → 0
  ```
  `[측정]` AST comparison against `git show HEAD:.../handler.py` with all docstrings
  (function, class, and module) stripped to the empty string before comparing: `ast.dump()`
  of the two trees is identical. Since the module docstring, the `RULES_BY_KIND`/`BLOG_RULES`
  comment, the `BOUNDED` comment, and `_coverage`'s docstring are the only places this round
  or round 1 touched, and comments are not part of the AST at all while docstrings were
  stripped before comparing, this is stronger evidence than a line-count diff that no
  executable code changed. `git diff --stat` for the round shows only the two allowed files
  (`handler.py`, `test_normalizer_rule_baseline.py`), 56 and 12 lines changed respectively,
  matching the scope of the prose edits made.

- **Evidence locations:**
  - `_coverage`'s corrected docstring: `handler.py`, the function immediately following
    `_abstention`.
  - The two corrected `[측정]`/`[확인 사실]`/`[추론]` labels: the module docstring paragraph
    beginning "What `_coverage` actually checks".
  - The two corrected test docstrings: `test_normalizer_rule_baseline.py`,
    `TestCleanMeansEveryApplicableRuleRan` and
    `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly`.
  - This packet's verification block, updated to `grep -rn "abstention"`.

- **Limitations and remaining risks (round 2, in addition to round 1's):**
  - `[측정]` The gap A1 now states in `_coverage`'s own docstring is the same gap the module
    docstring already stated after round 1: `_coverage` still cannot detect a declared rule
    that reaches no verdict. Nothing in round 2 closes it; the packet's Excluded item
    (observed rather than subtracted coverage) is unchanged and still deliberately not taken.
  - A2's test-docstring corrections do not add a test that would catch "never neither" —
    round 2's Included list explicitly forbids an assertion change, for the reason round 1
    held (the ten rules' 26+11 mutations and 16,000+4,000 differential comparisons). Writing
    a test that actually proves "never neither" would need `_coverage` to observe rather than
    subtract, which is the same excluded repair.
  - A2's report on the original round-1 handoff ("no test docstring repeated the F1 claim")
    was itself the mistake the attacker's A2 named: it searched for the wording "abstention
    branch," not the claim. That search method is not reused in this round's own handoff —
    the claims above are checked by reading, not by grepping for a phrase.

- **Newly discovered questions or blockers:** none. Every A1–A4 correction was writable as
  prose against existing code; none required touching `_coverage`'s body, the ten rules, or
  any assertion. The stopping condition about a correction quietly becoming a repair did not
  trigger in this round either.

### Round 3 (2026-08-20, closing `ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md`'s Round 2)

- **Scope.** Half a sentence, per the Included list: B1 (blocking) and B2 (minor). Rounds 1
  and 2 are closed — A1–A4 all verified shut by the attacker, the phantom-rule case built and
  measured, inertness confirmed on both files across two rounds. Nothing from rounds 1–2 was
  touched again.

- **Changed files:**
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py` — one paragraph,
    `handler.py:116–127` (the module docstring's `_coverage` correction paragraph), prose
    only, no executable line touched.
  - `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` — two docstring
    edits (B2), no assertion touched: `TestCleanMeansEveryApplicableRuleRan`'s class
    docstring (`:554–558`) and `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly`'s
    docstring (`:576–578`).
  - This packet's `Status` (now `WORKER_DONE`) and `Worker handoff` (this section).
  - No other file touched.

- **What changed, in one sentence each:**
  - B1: the module docstring's `[추론]` paragraph no longer claims "each of the ten checkers
    they call always either appends a finding or an abstention before either function
    returns" — the attacker measured that false on the module's own clean fixtures
    (`_check_blog`/`_check_trend` both return `findings=0 abstentions=0`, and 125
    `(link, bloggerlink, postdate)` combinations all had at least one declared rule
    appending to neither list). It now states the property that actually holds: every
    checker's condition is evaluated on every record (structural, from the "no early
    return" fact), so every rule is *decided*; a rule whose condition does not hold is
    decided as passing and records nothing, a rule whose condition does hold appends a
    finding or an abstention — and a name in `rules_evaluated` because it passed is
    byte-identical to one there because it never ran.
  - B2: the two `[측정]` labels the round-2 worker introduced in the test file are
    re-typed per `docs/conventions/evidence-labels.md`. `TestCleanMeansEveryApplicableRuleRan`'s
    class docstring split one sentence carrying two roles into `[확인 사실]` (readable
    directly off the two `assert` lines) and `[추론]` (that neither assertion can observe
    whether a rule ran); `test_the_two_coverage_lists_cover_the_kinds_rule_set_exactly`'s
    docstring changed `[측정]` to `[추론]` for the "does not prove 'never neither'" claim,
    which has no stated input/procedure/environment/time and is an inference about the
    test's reach, with a pointer to this report's phantom-rule construction added.
  - Nothing executable changed: `_coverage`'s body, the ten rules, `_bound_found`,
    `_bounded`, `_bounded_text`, and `run` are byte-for-byte unchanged from before round 1.

- **Self-check against the same trap (why this round's new sentence does not repeat B1's
  mistake):** `[측정]` Every clause the new paragraph asserts was checked against what the
  attacker actually measured before being written, not just read against the code: "every
  checker's condition is evaluated on every record" restates the attacker's own accepted
  structural reason (`grep` finds exactly one `return` in each of `_check_blog` and
  `_check_trend`, unchanged by this round); "a rule whose condition does not hold is decided
  as passing and records nothing" restates the attacker's own probe result
  (`findings=0 abstentions=0` on the clean fixtures, all 125 combinations); "a rule whose
  condition does hold either appends a finding or an abstention" is the *only* half phrased
  as "always appends," and it is scoped to the case where the condition *does* hold — the
  case the attacker never disputed — rather than asserted of all ten rules unconditionally,
  which is exactly the scope B1 said was missing. No new universal claim was introduced that
  is not either (a) the attacker's own structural reason, (b) the attacker's own measured
  result, or (c) a conditional ("if X then Y") that does not require every rule to reach a
  particular branch on every input. The paragraph was re-read once more after writing,
  specifically hunting for an unscoped "always" or "cannot" outside those three sources, and
  found none.
- **Self-check on B2's own labels:** `[확인 사실]`/`[추론]` were assigned by the same
  §"확인 사실과 측정의 경계" test the packet named — "직접 확인 가능한 속성을 보고하는가"
  → `[확인 사실]`; "다른 evidence에서 의미를 도출한 문장인가" → `[추론]` — and neither new
  label claims a measured procedure with input/environment/time, so neither is `[측정]`.

- **Commands and results:**
  ```text
  export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

  .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
    tests/environment/test_addon_layer_direction.py \
    tests/environment/test_agent_packet_record.py
  → 149 passed in 0.90s

  ./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline
  → normalizer.rule.baseline        ok

  .venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline
  → All checks passed!

  .venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → Success: no issues found in 1 source file

  grep -rn "abstention" experiments/integrated-p0/addons/normalizer.rule.baseline
  → 16 lines, every occurrence a correct use of the word (read individually)

  grep -c "output_contract_version collides in spelling" \
    experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
  → 0
  ```
  `[측정]` `ast.dump()` of `git show HEAD:<path>` compared against the working file, with
  every module/class/function docstring blanked to `""` before comparison: identical for
  both `handler.py` and `test_normalizer_rule_baseline.py`. Since comments are not part of
  the AST and every docstring was blanked before comparing, this shows every remaining
  executable construct — including each `assert` in the test file — is unchanged from
  `HEAD` (`70fa293`), across all three rounds.

- **Evidence locations:**
  - The corrected paragraph: `handler.py:116–127`, the module docstring, immediately after
    "What `_coverage` actually checks, and the gap it does not close."
  - The two re-typed test docstrings: `test_normalizer_rule_baseline.py:554–558` and
    `:574–578`.
  - This packet's verification block, above.

- **Limitations and remaining risks (round 3, in addition to rounds 1–2's):**
  - The gap `_coverage` does not close is unchanged by this round: it still cannot detect a
    declared rule that reaches no verdict and appends nothing. Round 3 only replaced a false
    reason for why that gap does not matter *today* with a true one; it does not narrow the
    gap. The Excluded item (observed rather than subtracted coverage) is still deliberately
    not taken.
  - The corrected paragraph is still prose asked to carry a guarantee the code does not
    enforce — the same structural situation that produced B1. It is a smaller, more
    conditional claim than round 2's, but a fourth round is not something this handoff can
    rule out; it can only report that the specific self-check above was performed.

- **Newly discovered questions or blockers:** none. The correction was writable as prose
  against existing code, touching neither `_coverage`'s body, the ten rules, nor any
  assertion. The stopping condition about a correction quietly becoming a repair did not
  trigger.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-COVERAGE-CLAIM.md)
- Result: `PASS`
- Orchestrator disposition, round 3: `ACCEPTED`. `[측정]` Every clause of the replacement
  paragraph was attacked separately rather than read. "No early return" is true by AST — one
  `Return` in each checker, no `Break`/`Continue`/`Raise`/`While`/`Try`/`With`, and
  `_check_trend`'s single `For` iterates a literal 4-tuple. "Every checker's condition is
  evaluated on every record" held under a `sys.settrace` line trace over **12,870 records**
  — 1,350 blog and 11,520 trend combinations including `None`, `True`, `nan`, `10**400`, a
  dict-valued field, and `"20260230"` — with every guard line executed and nothing raised.
  The byte-identical claim was verified **by construction**: an in-memory copy of the module
  with `blog.invalid_postdate`'s block deleted but the rule still declared emits a body
  byte-identical to the intact module's on a clean record, and on `postdate: "20260230"`
  emits that same clean body with the rule listed in `rules_evaluated`.

  `[추론]` The paragraph is now structurally incapable of the failure rounds 2 and 3 died on,
  because its conclusion is **negative** — that a passed rule and a never-run rule are
  indistinguishable in the emitted body. A sentence that claims no mechanism cannot
  over-claim one.

  `[확인 사실]` One wording item, C1, is recorded and deliberately not escalated by the
  attacker: for the five rules with an abstention path, "condition" is true of the guard chain
  and false of the rule's own violation test. Both readings reach the same conclusion, the
  next clause forces the true one, and **the phrase was the one the attacker itself prescribed
  in round 2** — the worker used it as given. Fix only if that paragraph is edited again.
- Orchestrator disposition, round 2: `REWORK` again — `FAIL` on **B1, a sentence written in
  round 2**, not on any of A1–A4, which the same attacker verified closed. `[측정]` A2 is now
  measured rather than described: the phantom rule was added to the module's set and to a copy
  of the test's, and `clean: True` with both assertions passing was observed. `[확인 사실]` The
  orchestrator independently confirmed round 2's inertness by docstring-stripped AST on both
  changed files before the re-attack was dispatched.

  `[추론]` Three rounds on one paragraph is worth stating plainly rather than burying: each
  round's `FAIL` was on a sentence the previous round introduced, which is what happens when
  prose is asked to carry a guarantee the code does not. `[결정]` The paragraph stays prose and
  the gap stays unenforced — round 1's Excluded section records why, and the alternative repair
  is P1's.
- Orchestrator disposition, round 1: `REWORK`, and the defect was the planner's. `[측정]` The worker
  corrected every place this packet named and its diff is inert — confirmed four ways:
  docstring-stripped AST identical, per-function bytecode identical after line-number
  normalisation, every module constant equal, and 4,000 differential comparisons with zero
  divergence, plus 98 passed across six `PYTHONHASHSEED` values. What failed is that the
  packet's Included list named the wrong second location. Round 2 above repairs it.

`[확인 사실]` The attacker also verified **both halves** of the new description by experiment,
including a case R2 itself did not run — an undeclared rule that *abstains*, not only one that
fires, also raises. And it caught a trap worth recording: `TREND_MARKER_KEYS`'s `repr` differs
between runs because it is a `frozenset`, while `==` is `True`. A reviewer comparing reprs
would have reported a false divergence.
