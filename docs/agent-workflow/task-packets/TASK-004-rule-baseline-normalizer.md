# TASK-004 — A normalizer that judges, which is the one the charter asked for

- Status: `READY`
- Phase: P0-B, B3 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `addon-author`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

`normalizer.rule.baseline@0.1` — one add-on that applies deterministic rules to a sealed
snapshot and **reports what is wrong with the data**, so that the charter's required flow
item 7 and hypothesis 6 have a subject.

`[확인 사실]` `p0-charter.md`'s required flow item 7 asks for *"one selected REST collector,
one selected dataset importer, and one deterministic `rule-baseline@0.1` normalizer **as
add-ons**"*. `[측정]` It does not exist. `project-state.md` §5 records the hypothesis it
serves — *"A rule baseline can expose schema and quality problems before ML or LLM providers
are introduced"* — as **"Not tested in P0. No quality baseline was built; the normalizers
extract, they do not judge."** `addons/normalizer.conformance/handler.py`'s own docstring
says `rule-baseline@0.1` is not it.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 6
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) (Schema 0.1, `normalized_result`, determinism enforced), [DP-021](../../decisions/DP-021-schema-0-2-trend-points.md) (Schema 0.2 as a discriminated union on `record_type`), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md) (DP-011's product scope is P1's, not this packet's)
- Contracts: [`CONTRACT-ADDON@1.3`](../../../contracts/experimental/CONTRACT-ADDON-1.3.md), [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4
- Open Questions: [OQ-013](../../open-questions/OQ-013-addon-responsibility-boundary.md) — a judgment no other layer can check is exactly what this add-on makes
- Owner decisions required: `none`
- Required evidence or environment: the local PostgreSQL cluster; `addon_kit` for authoring and conformance

## Scope

### Included

- `experiments/integrated-p0/addons/normalizer.rule.baseline/` — manifest, handler, and
  whatever the authoring guide requires.
- Deterministic rules over the snapshot items this repository can already produce: Schema
  0.1 blog documents and Schema 0.2 trend points. Each rule states, in the code, **what a
  violation means and why a rule rather than a model can decide it**.
- A result body that carries the finding — which rule, which field, what was expected, what
  was there — rather than a score. `[결정]` A number without the rule that produced it is
  the thing a rule baseline exists to avoid.
- **Abstention.** An item a rule cannot decide is `skipped`, counted, and named. Guessing is
  the failure mode; `NormalizeOutcome` already carries `skipped` for it.
- Tests: determinism (same snapshot and version → byte-identical results), each rule firing,
  each rule **not** firing on a clean item, and abstention.

### Excluded

- Anything from DP-011's product scope: no evidence card, no product/ingredient/topic
  identity, no trend classification, no sunscreen or toner semantics. DP-026 moved all of it
  to P1 and a rule baseline is not a smuggling route for it.
- Any change to `addon_api`, `addon_host`, `domain/`, or `platform_core/`. If the contract
  cannot express what this add-on needs, **stop and report that** — a documented gap is this
  packet's most valuable possible output.
- Any new migration. `normalized_result` already holds `body` and `notes`.
- Any change under `docs/`, `contracts/`, except this packet's Worker handoff.

### Allowed files

- `experiments/integrated-p0/addons/normalizer.rule.baseline/**`
- `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` (new)

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- everything outside `Allowed files`, and in particular `docs/project-state.md`,
  `docs/architecture-synthesis/**`, and `contracts/**` — a worker does not write the claim
  its own work is the evidence for
- any project module other than `addon_api`. An add-on imports `addon_api` and nothing else,
  and `tests/environment/test_addon_layer_direction.py` will name the violation.

## Acceptance criteria

1. The add-on **judges**. For a snapshot item that is structurally intact but wrong — a
   missing required field, an out-of-range value, a value inconsistent with another field in
   the same record — it emits a finding naming the rule. An add-on that only reshapes fields
   has not met this packet.
2. Determinism is proved, not claimed: the same snapshot at the same add-on version produces
   byte-identical `body` values across two runs. Reuse the pattern in
   `tests/test_normalized_results.py::TestDeterminism`.
3. Every rule has **both** tests — one where it fires and one where it does not. A rule that
   fires on everything and a rule that fires on nothing are the same defect from opposite
   sides, and this repository has found both.
4. Abstention is exercised: an item the rules cannot decide is skipped, counted in
   `NormalizeOutcome.skipped`, and identified in `notes` — never silently dropped and never
   guessed.
5. `output_contract_version` is declared and matches what the body actually conforms to.
6. The conformance path in `addon_kit` passes for this add-on.
7. The full suite does not regress from **1291 passed, 14 skipped**.

## Verification

```sh
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_rule_baseline.py \
  tests/environment/test_addon_layer_direction.py

./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if the documented contract does not say what you need to know.** You are
  writing against `CONTRACT-ADDON@1.3` and `addon-authoring.md` on purpose. Where they are
  silent or wrong, that gap is the deliverable — record the question rather than inferring
  the answer from the host's source.

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
