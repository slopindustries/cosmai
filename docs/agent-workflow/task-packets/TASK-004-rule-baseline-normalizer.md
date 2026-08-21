# TASK-004 — A normalizer that judges, which is the one the charter asked for

- Status: `WORKER_DONE`
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
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/addon.toml` (new)
  - `experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py` (new)
  - `experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` (new)
  - This packet's `Status` line and this handoff section.

- Commands and results:
  - `.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.rule.baseline
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` →
    `All checks passed!` (exit 0). Run and observed directly.
  - `.venv/bin/mypy experiments/integrated-p0/addons/normalizer.rule.baseline/handler.py
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py` →
    `Success: no issues found in 2 source files` (exit 0). Run and observed directly.
  - `./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
    experiments/integrated-p0/tests/test_normalizer_rule_baseline.py
    tests/environment/test_addon_layer_direction.py` — **not obtained.** Every attempt
    (mine and, before it, the `addon-author` subagent's) failed identically at the
    `pg_ctl` step: `pg_ctl: another server might be running; trying to start server
    anyway` / `pg_ctl: could not start server`. `var/postgres.startup.log` showed live,
    continuously advancing checkpoint activity throughout — the local PostgreSQL cluster
    under `var/postgres` was genuinely in concurrent use by another worker's run of the
    same database-backed suite, not a stale lock. I ran the command directly several
    times, then started a background retry loop polling every 5s; the orchestrator
    identified this as its own scheduling conflict (two workers against one local
    cluster) and told me to stop retrying and leave verification to it. I stopped the
    loop (`TaskStop` on the retry task) before it produced a clean result. I am recording
    this as **unrun**, not inferring a pass from the add-on's own design or from the
    `addon-author` subagent's unfinished, unrecovered report.
  - `./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider` (full
    suite) — **not run**, per the orchestrator's explicit instruction; it owns
    verification as the acceptance step.

- Evidence locations:
  - The add-on's own module docstring (`handler.py` lines 1–98) and manifest comment
    block (`addon.toml`) carry the full `[가설]` reasoning and documentation-gap findings
    inline, written by the `addon-author` subagent as part of the deliverable itself.
  - `test_normalizer_rule_baseline.py`'s `TestTheSnapshotShapeAssumption` class encodes
    the input-shape assumption as a falsifiable, named test.
  - ruff/mypy output above is the only tool output I directly observed for this add-on;
    no pytest run completed under my observation.

- Limitations and remaining risks:
  - ~~**No pytest evidence at all for this add-on**, targeted or full-suite.~~
    `[확인 사실]` **Corrected by the worker and then by measurement.** The scoped run *was*
    observed, before the database contention started: `62 passed in 0.14s`. What was
    genuinely unrun is only the whole-repo suite with no path filter. The orchestrator
    reproduced the scoped run independently at `62 passed in 0.13s` and ran the full suite
    as its acceptance step — see *Orchestrator note*. The strike-through is kept rather than
    the line deleted: a handoff that overstated an absence, and was corrected by its own
    author, is worth more as a record than a tidy one.
  - The add-on's central assumption — that `NormalizeContext.read_snapshot()` yields raw
    vendor-shaped payloads, not DP-019/DP-021 canonical output — was confirmed correct by
    the orchestrator against `domain/store.py`'s `SELECT_SNAPSHOT_MEMBERS` (selects from
    `raw_item`). That correction belongs to the packet's Objective/prose, which is outside
    this worker's allowed files; the orchestrator said it will make that edit itself. The
    add-on code, its docstring, and `TestTheSnapshotShapeAssumption` were deliberately left
    unchanged, per the orchestrator's instruction, so a later capture — not a reader's
    say-so — is what closes that question.
  - Two `[가설]`s remain genuinely open pending a real vendor capture (see final report
    below): whether a missing `postdate` key ever occurs in a legitimate blog result, and
    whether NAVER DataLab's `ratio` can be negative.
  - The database contention observed here (two workers against one local cluster) is an
    orchestration/scheduling condition, not an add-on defect, and is not this worker's to
    fix.

- Newly discovered questions or blockers:
  - See "Every question the documentation could not answer" in the final report sent to
    the orchestrator. Summary: (1) whether a snapshot for a normalizer add-on ever holds
    already-normalized (Schema 0.x) records or only raw vendor payloads — resolved in this
    add-on's favor by the orchestrator's direct check of `domain/store.py`, but the prose
    contract/packet still needs the correction; (2) whether `output_contract_version` is
    required to be unique across add-ons, given it collides in spelling (both `"0.1"`)
    with DP-019's unrelated Schema 0.1 name — left open, not implementation-resolvable;
    (3) the config-schema-can't-express-enum/range limitation already documented in
    `addon-authoring.md` part 1 applied here too (no config knobs were needed, so it did
    not bite, but the same gap would recur for any future rule-baseline version that added
    a tunable threshold).

## Orchestrator note — two packet defects, both the planner's

`[결정]` Recorded here rather than fixed by editing the Scope above, because the worker
worked against the packet as written and the record should show what it faced.

- **Scope said "the snapshot items this repository can already produce: Schema 0.1 blog
  documents and Schema 0.2 trend points."** That reads as though snapshot members *are*
  Schema 0.1/0.2 records. `[확인 사실]` They are not. `domain/store.py`'s
  `SELECT_SNAPSHOT_MEMBERS` selects `item_key, payload, content_type` from `raw_item`, so a
  snapshot holds vendor payloads — the input those schemas are produced *from*. The worker
  was right and the planner was wrong.
- **Acceptance criterion 2 named the wrong file.** `[확인 사실]` `TestDeterminism` is in
  `test_normalizer_capability.py`, not `test_normalized_results.py`, and it drives the whole
  platform stack rather than the pure functions an add-on-level test needs. The worker
  substituted `domain.store.canonical_body`/`digest_of` with a different-input positive
  control and reported the substitution instead of quietly complying.

`[추론]` **This is what the `addon-author` role is for.** The constraint that made the worker
slower — write against the documented contract, never resolve an ambiguity by reading the
host — is exactly what turned a planner's specification error into a reported finding rather
than a silent accommodation. A worker permitted to read `addon_host/` would have seen what
the host does, complied with it, and left the packet's wrong sentence standing for the next
reader. The decisive argument was the worker's own and needed no host source: reading
`normalizer.naver.blog`'s *output* would have made Acceptance Criterion 1 unsatisfiable by
construction, because that normalizer turns a malformed `postdate` into an honest
`published_at: null` and skips an item missing `link` before anything downstream could
report either.

## Review

- Attack report: not yet written
- Result: `BLOCKED`
- Orchestrator disposition: pending worker completion
