# TASK-006 — Make the rule baseline's claims true, since its rules already are

- Status: `READY`
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

- Changed files:
- Commands and results:
- Evidence locations:
- Limitations and remaining risks:
- Newly discovered questions or blockers:

## Review

- Attack report: not yet written
- Result: `BLOCKED`
- Orchestrator disposition: pending worker completion
