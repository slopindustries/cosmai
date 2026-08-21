# TASK-006 — Make the rule baseline's claims true, since its rules already are

- Status: `WORKER_DONE`
- Phase: P0-B, B3 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

Close the four claims [TASK-004](TASK-004-rule-baseline-normalizer.md)'s attack report
returned `FAIL` on, without touching the ten rules, which survived everything thrown at them.

`[측정]` [`ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE.md):
**26 targeted mutations against the ten rules, all 26 killed.** The reviewer could not make a
rule fire on a clean record, fail to fire on a dirty one, misclassify an item, lose an item,
mis-order results, or diverge `skipped` from its named reasons — and found no vacuous
non-firing test. `[결정]` So this packet changes no rule and adds no rule. It makes the
things said *about* the rules checkable.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 6
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md), [DP-021](../../decisions/DP-021-schema-0-2-trend-points.md), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md), [DP-027](../../decisions/DP-027-dataset-standard-and-share-alike.md)
- Contracts: [`CONTRACT-ADDON@1.3`](../../../contracts/experimental/CONTRACT-ADDON-1.3.md)
- Open Questions: [OQ-013](../../open-questions/OQ-013-addon-responsibility-boundary.md)
- Owner decisions required: `none` — the owner decided on 2026-08-20 that hypothesis 6 closes on fixture evidence with the reason recorded, and that no rule is added to make one fire on real data
- Required evidence or environment: **none.** `[측정]` The scoped run needs no database and passes without `scripts/with-database.sh`. Do not start the full suite; the orchestrator runs it.

## Scope

### Included

**F2 — the only finding that makes the stored artefact say something untrue. Fix first.**
`[측정]` A trend point without `startDate` is emitted as `{"clean": true, "findings": []}`
with `skipped: 0`, while `trend.period_outside_window` never ran. Same shape for a blog
document without `bloggerlink` and `blog.link_equals_bloggerlink`. A record a rule never
evaluated must not be recorded as clean. Decide and implement one of:
- the record carries which rules were **evaluated** (or which were not, and why), or
- an unevaluated rule makes the record abstain rather than pass.
Whichever is chosen, `clean: true` must mean *every applicable rule ran and none fired*, and
a test must fail if it ever means less.

**F1 — a finding's `field`, `expected`, and `found` are asserted by nothing.** `[측정]`
Replacing `_finding`'s return with `{"rule": rule, "field": "", "expected": "", "found":
None}` leaves 57 passed, because every assertion reads only `finding["rule"]`. The packet
that commissioned this add-on asked for *"which rule, which field, what was expected, what
was there"* — three quarters of that is currently unheld.

**F3 — the determinism control does not cover the claim.** `[측정]` `canonical_body` sorts
keys and both `run()` calls share one process, so a set-derived string produces **4 distinct
digests across 6 `PYTHONHASHSEED` values while the test reports `2 passed`**. The shipped code
is genuinely seed-stable; the control is what is missing. Add one that would catch it.

**F5 — a `# type: ignore[union-attr]` masks a real crash.** `[측정]` Removing the
`bloggerlink_ok` guard leaves mypy at `Success` and 57 passed, and a real-shaped item then
dies with `AttributeError` inside the run. Either narrow the ignore to the expression that
needs it, or restructure so none is needed.

**F6 — the outcome summary is unasserted**, including a `clean`/`with_findings` swap.

**F11 — `found` echoes untrusted input verbatim.** 200 KB in, 200 KB in the body; and
`ratio: NaN` makes `canonical_body` emit non-strict JSON. Bound what `found` carries and
decide what a non-finite number becomes.

**F9 — the manifest asserts a distinction nothing makes.** `[측정]` `streams = []` is
byte-identical in effect to omitting `[declares]`, so the comment's *"that is not an
omission"* claims a mechanism that does not exist. Correct the comment; the question it
raised is answered.

**F4 — record, do not repair.** `[측정]` Five of the ten rules cannot fire on anything either
NAVER collector produces: `collector.naver.blog` raises `AddonPermanent` on a missing `link`,
and the trend collectors set `dimension` from a module constant and refuse a non-numeric
`ratio` and an empty `title`. `[결정]` The owner decided hypothesis 6 closes on fixture
evidence. Record in the module docstring **why that is not a defect**: those five rules are a
second line for cases the collector already refuses, so their silence on real data is the
first line working, and the rule baseline is what would catch them if it stopped.

### Excluded

- **Any change to the ten rules' logic, and any new rule.** They survived 26 mutations. A
  rule added so that something fires on real data optimises for the appearance of evidence,
  and the owner declined it.
- `addon_api`, `addon_host`, `domain/`, `platform_core/`, and every other add-on.
- Anything under `docs/` or `contracts/` except this packet's Worker handoff.
- F7, F12, F13 and the out-of-scope findings — the orchestrator records those for the gate.

### Allowed files

- `experiments/integrated-p0/addons/normalizer.rule.baseline/**`
- `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py`

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- everything outside `Allowed files`, in particular `docs/project-state.md`,
  `docs/architecture-synthesis/**`, and `contracts/**`

## Acceptance criteria

1. `clean: true` cannot be recorded for a record with an unevaluated applicable rule, and a
   test fails if it is.
2. `field`, `expected`, and `found` are each asserted for at least one firing of every rule
   that sets them, and blanking `_finding`'s return goes red.
3. A determinism control exists that goes red for a hash-order-dependent value. State how you
   verified it goes red.
4. Removing the `bloggerlink_ok` guard goes red, or the guard is gone and no ignore replaces it.
5. `NormalizeOutcome`'s counts are asserted, and a `clean`/`with_findings` swap goes red.
6. `found` is bounded, and a non-finite `ratio` produces strict JSON.
7. The module docstring records F4's reason as above, and the manifest's `streams` comment no
   longer claims a distinction that does not exist.
8. The ten rules are unchanged. `git diff` on their bodies is empty except where F1/F2 require
   a finding to carry more.

## Verification

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
  tests/environment/test_addon_layer_direction.py

.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py
.venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py
```

`[확인 사실]` A path-based loader caches bytecode by `(mtime, size)`, which gave the reviewer
**two false `SURVIVED` verdicts**. If you mutate to check a control goes red, confirm the
mutation actually loaded — change the byte length, or clear `__pycache__`.

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if closing F2 requires a shape `CONTRACT-ADDON@1.3` cannot express — that is a
  contract finding and worth more than a workaround.

## Worker handoff

- **Changed files:**
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py`
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/addon.toml`
  - `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py`
  - this packet's `Status` and this section. Nothing else was written.

### F2 — the shape chosen, and the one rejected

`[결정]` **The record carries its coverage.** Each body now holds `rules_evaluated` and
`rules_not_evaluated`, and `clean` is `True` only when `findings` is empty *and*
`rules_not_evaluated` is empty. An unevaluated rule is neither a finding nor a pass: it is a
third entry shape, `{"rule", "field", "reason"}`, with fixed prose for the reason and never
the offending value.

`[결정]` **The abstain-the-record option was rejected.** A trend point without `startDate` is
not defective — DP-021 D2 does not require the field — and five of its six rules did reach a
verdict. Turning that into an item-level abstention would drop those five verdicts and put
the record in `skipped`, which is reserved for *"cannot be judged at all"*. It would also
make a legitimate record indistinguishable from an unparseable one in `skip_reasons`, which
is the same class of untrue claim F2 reported, pointed the other way.

Three consequences, stated because they are the cost of the choice:

1. `clean: false` now covers two states. They are told apart by `findings`: empty with a
   non-empty `rules_not_evaluated` means *not fully checked*, not *wrong*. No third body
   field was added for it, because the pair already decides it.
2. `NormalizeOutcome.notes` gains `not_fully_checked`, so the summary's three buckets sum to
   `results_emitted` — asserted, since two buckets that no longer add up would hide exactly
   the records this finding is about.
3. `_coverage()` raises `AddonOutputInvalid` rather than emit a body whose evaluated and
   abstained rules do not cover `RULES_BY_KIND[kind]` exactly. The way `clean` quietly
   starts meaning less again is a rule added without its abstention branch, and that now
   fails the run instead of shrinking the claim.

   `[측정]` **Correction, 2026-08-20 (TASK-009).** The paragraph above is wrong about what
   `_coverage` catches. It refuses a rule name outside the kind's declared set and a rule
   that both fired and abstained — the two directions its own test drives — but a rule
   declared in `RULES_BY_KIND` that reaches no verdict and appends no abstention is silently
   subtracted into `rules_evaluated`, and the record is still emitted `clean: true`.
   Coverage is computed by subtraction from the declared set, not by observing that a rule
   ran, so it does not and cannot catch that third case. See `handler.py`'s module docstring,
   "What `_coverage` actually checks, and the gap it does not close", for the corrected
   claim.

`[결정]` `rule_report_version` and `[addon].output_contract_version` both stay `"0.1"`
although the body shape changed. No `normalized_result` row has ever been written for this
add-on, so nothing exists to misread, and whether a report-shape change owes a version bump
is precisely the question F7 left open — no artefact defines this `"0.1"` and no validator
checks a body against it. Answering it by bumping a string here would decide a specification
question by implementation. Recorded in the module docstring as well.

### Commands and results

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
  tests/environment/test_addon_layer_direction.py
→ 103 passed in 0.82s            (baseline before this task: 62 passed)

.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py
→ All checks passed!

.venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py
→ Success: no issues found in 2 source files

./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.rule.baseline
→ normalizer.rule.baseline  ok
```

`[측정]` No database was used and none was needed. The full suite was **not** run by the
worker; the orchestrator ran it and reports `1393 passed, 14 skipped`.

### Every new control, watched going red

`[확인 사실]` **How the bytecode cache was defeated, since it produced two false `SURVIVED`
verdicts in the previous review.** A harness (in the session scratchpad, outside the
repository) rebuilt each mutant from a byte-exact pristine copy and **asserted that the
mutation changed the source file's byte length** — the loader validates its `.pyc` by
`(mtime, size)`, so a differing size invalidates the cache no matter what the clock did.
The harness then ran pytest **without** `-B`, deliberately letting the `.pyc` be rewritten,
and read the 4-byte source-size field out of the `.pyc` header afterwards. In the eleven
runs it drove, it equalled the mutant's size — direct evidence that the run compiled the
mutated source rather than a cached older one. F3-b (marked `—` below) was applied by a
separate inline script which asserted the length change but did not read the header back;
its invalidation rests on the size assertion alone. Each mutation was restored from the pristine
copy immediately; `diff` against it is empty and `git status --short` shows only the three
files above.

| # | Mutation | Source bytes | `.pyc` after the run | Suite |
|---|---|---|---|---|
| F2a | `clean = not findings and not not_evaluated` → `clean = not findings` | 32319 → 32334 | 32334 | **2 failed**, 96 passed |
| F2b | the window rule's abstention append → `pass` (silent again) | 32319 → 32245 | 32245 | **3 failed**, 95 passed |
| F1 | `_finding` returns `{"rule": rule, "field": "", "expected": "", "found": None}` | 32319 → 32306 | 32306 | **15 failed**, 83 passed |
| F3-a | `', '.join(TREND_DIMENSIONS)` → `', '.join(set(TREND_DIMENSIONS))` | 32319 → 32346 | 32346 | **2 failed**, 96 passed |
| F3-b | `_coverage`'s return → `list({rule for rule in applicable …})` | 32319 → 32353 | — | **1 failed**, 97 passed |
| F5 | `if not link_text or not bloggerlink_text:` → `if not link_text:` | 32319 → 32349 | 32349 | **2 failed**, 96 passed |
| F6a | `kind_counts[kind] += 1` → `pass` | 32319 → 32340 | 32340 | **1 failed**, 97 passed |
| F6b | the clean and with-findings counters swapped | 32319 → 32359 | 32359 | **1 failed**, 97 passed |
| F6c | each result's `notes` → `{}` | 32319 → 32189 | 32189 | **2 failed**, 96 passed |
| F6d | `rule_report_version` dropped from the body | 32319 → 32295 | 32295 | **1 failed**, 97 passed |
| F11 | `found` echoes verbatim (`_bound_found` bypassed) | 32319 → 32349 | 32349 | **3 failed**, 95 passed |
| guard | `_coverage`'s `raise` disabled | 32319 → 32342 | 32342 | **1 failed**, 97 passed |

`[측정]` **Twelve mutations applied, twelve killed.** Every one was watched failing; none is
an inferred pass.

`[측정]` **F3-b is the one that matters most for the determinism claim.** It makes
`rules_evaluated`'s *order* hash-dependent without touching any string a test spells out,
and **only** `test_the_digests_are_the_same_under_different_hash_seeds` catches it — the
other 97 tests pass. That is the class TASK-004's review showed the old same-process digest
test could not see. `[측정]` F3-a was additionally run with the pytest process pinned to
`PYTHONHASHSEED=0`, `1`, and `2`: the seed control fails under all three, so it does not
depend on the runner's own seed.

`[측정]` The new determinism control spawns six interpreters (`PYTHONHASHSEED` 0–5) over a
snapshot that reaches every rule's `expected` string and every abstention reason, and
asserts one digest set. It costs about 0.7 s of the scoped run's 0.82 s.

### Verified versus reasoned about

- **Verified by a mutation that was watched going red:** F1, F2 (both halves), F3, F5, F6
  (all four counters and both note lists), F11 (bound and strict JSON), and the
  `_coverage` guard.
- **Verified by assertion rather than by mutation:** F9's comment correction — a comment
  cannot be mutated into a test. What *is* asserted is `manifest.declares.streams == ()`,
  which no test covered before; the claim the comment now makes (empty and omitted are the
  same value to the loader) is the previous reviewer's measurement, reproduced here only as
  far as this manifest's own parsed value.
- **Not verified, and stated as unverified:** F4's docstring reasoning is prose about
  reachability. Nothing runs this add-on against captured data, so the claim that the five
  unreachable rules are a second line rather than dead weight is `[추론]`, not `[측정]`.
- **Not verified against a live database:** F11's `NaN` path. The add-on now guarantees the
  body is JSON that `json.dumps(..., allow_nan=False)` accepts, asserted with a
  `parse_constant` hook plus a positive control showing the hook catches a `NaN` body. That
  `jsonb` would have rejected the old literal is still `[추론]` — no cluster was touched.
- **`AddonOutputInvalid`'s path through the host is untested here.** `_coverage` raises it,
  and the test asserts the raise; what `addon_host` does with it is that layer's, and this
  packet does not touch it.

### Evidence locations

- Tests: `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` — new classes
  `TestAFindingNamesTheParticulars` (F1), `TestCleanMeansEveryApplicableRuleRan` (F2),
  `TestWhatAFindingEchoes` (F11), new tests in `TestOutcomeCounts` (F6),
  `TestItIsDeterministic::test_the_digests_are_the_same_under_different_hash_seeds` (F3),
  `TestBlogRules::test_a_blog_record_without_bloggerlink_is_judged_rather_than_crashing` (F5).
- Reasoning: `handler.py`'s module docstring (F2's shape and F4's reason) and
  `_coverage` / `_bound_found`'s docstrings; `addon.toml`'s `[declares]` comment (F9).
- The mutation harness is scratchpad-only and deliberately not added to the repository.

### Limitations and remaining risks

- `[측정]` **The ten rules are unchanged in what they decide.** `_check_blog` and
  `_check_trend` were restructured to return `(findings, not_evaluated)`, and each guard
  that was already there became an explicit `if …: abstain / elif …: fire`. Every firing
  condition is equivalent to the one that survived 26 mutations, and all 57 original tests
  still pass unmodified. That is an argument from reading plus a green suite, not a proof.
- The `expected` strings are now asserted verbatim in ten tests, so editing that prose
  fails the suite. Deliberate — it is what makes blanking `_finding` go red — but it is
  friction a later author will meet.
- `_bound_found` runs `json.dumps` per finding. Irrelevant at P0 volumes; noted because it
  is per-finding rather than per-record.
- A bounded value changes type when a list is truncated (list → a one-key marker object).
  Unambiguous, since the marker replaces the whole value rather than sitting beside it, but
  a reader parsing `found` positionally would notice.

### Newly discovered questions or blockers

- **Nothing was blocked, and `CONTRACT-ADDON@1.3` expressed the F2 shape without strain.**
  `NormalizedResult.body` is a free-form `Mapping[str, Any]` the contract does not
  constrain, so `rules_evaluated` / `rules_not_evaluated` needed no contract change.
- `[추론]` **That freedom is itself the finding.** The contract fixes `body`'s *type* and
  nothing about its *shape*, and `output_contract_version` names a shape no artefact
  defines and no validator checks. So this task changed a stored body's shape
  incompatibly, and no mechanism anywhere in the repository noticed or could have. That is
  F7 restated from the other side, and it now has a concrete instance rather than a
  hypothetical one.
- `[추론]` **Invariant 9 says "byte-identical canonical output" without naming a process.**
  The reading this add-on now holds itself to is the stronger one — identical across
  interpreters and hash seeds. Whether every normalizer is held to that, or only to
  same-process stability, is not stated anywhere, and the two differ by exactly the defect
  class F3 named.
- `[확인 사실]` **Neither the contract nor `domain.store.canonical_body` bounds a body or
  requires strict JSON.** `canonical_body` calls `json.dumps` with default `allow_nan=True`,
  so a non-finite float in any add-on's body reaches the store as a bare `NaN` literal. The
  bound and the strictness are enforced inside this add-on because that was the only place
  this packet was allowed to touch; both belong lower down if the property is meant to hold
  for every add-on.
- **One test was added that this packet did not name.**
  `test_missing_field_fires_when_a_required_field_is_only_whitespace` closes F10, which is
  in neither the Included nor the Excluded list. It is test-only, it covers a branch the F1
  work already needed a firing of, and dropping `or not value.strip()` previously left the
  suite green. Disclosed rather than folded in silently.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-RULE-BASELINE-R2.md)
- Result: `FAIL`
- Orchestrator disposition: `REWORK`, narrowly. `[측정]` The four claims this packet was
  written to repair **hold under attack** — 11 mutations killed, determinism measured as the
  strong cross-process reading under six `PYTHONHASHSEED` values, both bucket-counter swaps
  red, and the ten rules unchanged across 16,000 differential comparisons against `07c599b`.
  What failed is a **fifth** claim the packet made on the way past: three places say
  `_coverage` is what forces a rule added without an abstention branch to fail the run, and
  F1 measured that it is not — coverage is computed by subtraction, so such a rule lands in
  `rules_evaluated` and the record is emitted `clean: true`. `AGENTS.md`'s *"Do not describe
  a convention as a control"* is the rule that breaks, which makes this a record defect of
  the class this repository treats as blocking rather than a cosmetic one.
  Repair is [TASK-009](TASK-009-coverage-claim-and-marker-collision.md); F4 is recorded
  there as out-of-scope rather than carried silently.

  `[확인 사실]` **Closed 2026-08-20 under [TASK-009](TASK-009-coverage-claim-and-marker-collision.md),
  which this packet's `Result` deliberately does not restate.** That packet took three rounds
  — each round's `FAIL` landed on a sentence the previous round had introduced — and was
  accepted `PASS` on the third. This packet's own `FAIL` stands as the record of what was
  found here; a repair accepted elsewhere does not retroactively make this review a pass.
