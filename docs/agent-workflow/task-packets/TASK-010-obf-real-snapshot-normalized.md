# TASK-010 — A real Open Beauty Facts row through the normalizer, which is what "end to end" meant

- Status: `ACCEPTED`
- Phase: P0-B, charter closure
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`
- Attacker: `adversarial-reviewer`
- Orchestrator: project owner's session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

The sealed snapshot [TASK-007](TASK-007-obf-dataset-end-to-end.md) produced from real Open
Beauty Facts bytes is normalized by `normalizer.obf.product@0.1` through the installed host,
producing `normalized_result` rows at `output_contract_version 0.3` — so that the charter's
*"one REST source and one dataset complete the end-to-end flow"* has a dataset half that
reaches the end of the flow rather than stopping at the snapshot.

## Why this packet exists

`[확인 사실]` TASK-007 and TASK-008 each did what they were asked and together leave a gap
neither was asked to close. The attack report on TASK-008 states it in one sentence:

> TASK-007's completed capture mentions neither `obf.product` nor `0.3`, so no real Open
> Beauty Facts row has ever passed through it: every `product` record that has ever existed
> came from `a_row()` in the test file the handler's own author wrote.

`[추론]` That is a planning defect, not a worker's. The orchestrator split acquisition from
normalization to keep two packets bounded and never wrote the third that joins them. This is
that packet.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §1, §5 hypotheses 3 and 5
- Accepted decisions: [DP-028](../../decisions/DP-028-schema-0-3-product-records.md) (the
  record type and its four body fields), [DP-027](../../decisions/DP-027-dataset-standard-and-share-alike.md)
  (source, `local`, publish nothing), [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md)
  D3/D5/D6, [DP-024](../../decisions/DP-024-local-input-registry.md),
  [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4, §5
- Prior evidence, all of which you must read: TASK-007's capture record
  [`evidence/obf-dataset/README.md`](../../../experiments/integrated-p0/evidence/obf-dataset/README.md);
  the attack report [`ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md);
  TASK-008's `Review` section, where F1 is already resolved by measurement
- Open Questions: [OQ-001](../../open-questions/OQ-001-source-capability.md) dataset half,
  [OQ-003](../../open-questions/OQ-003-normalization-protocol.md)
- Owner decisions required: **one, and it does not block you.** Whether `brands` carries the
  language prefix (`xx:Hismile`) or the bare name (`Hismile`) is a schema question. Record
  what the run produces; do not decide it. See *Stopping conditions*.
- Required evidence or environment: network access to `static.openbeautyfacts.org`; the local
  PostgreSQL cluster. `[측정]` The two delta files TASK-007 used are still under
  `var/samples/obf/` — prefer re-retrieving rather than trusting them, and say which you did.

## Scope

### Included

- **Normalize the real snapshot.** Extend `experiments/integrated-p0/tests/test_obf_real_data.py`
  with a scenario that seals a snapshot over the real import (as TASK-007's own scenarios
  already do) and then runs the installed `normalizer.obf.product@0.1` through `JobRunner`
  and the host's normalize route — the same path `test_naver_real_data.py` uses for
  `normalizer.naver.blog`. Not a hand-built `NormalizeContext`: the point is the host path,
  which the attacker recorded as unmeasured.
- **Record what the real rows produce**, as counts and as measured field presence:
  `results_emitted`, `skipped`, and how many records carry each of `display_name`,
  `brands`, `observed_at`, and `has_ingredients = true`. `[측정]` `SRC-003` predicts sparsity
  — `product_name` was present in 19 of 36 rows — so a run where every field is populated is
  evidence something is wrong, not evidence of success.
- **The `brands_tags` measurement, in the record.** `[측정]` The orchestrator measured 247
  real rows across TASK-007's two deltas: `brands_tags` is present on 26 of 121 in delta A,
  is a `list` in every case, and **every one of the 70 values across both deltas carries an
  `xx:` language prefix**; 9 rows carry more than one tag. Confirm or contradict this from
  your own run and record which happened.
- **F1's record error, corrected.** `test_normalizer_obf_product.py`'s docstring attributes
  the `brands_tags` field name to `SRC-003`. `SRC-003` measured `brands`. Correct the
  attribution to DP-028 D3 and note that the field's presence and list shape are now measured
  from real rows — a correction visible as a correction, this repository's habit.
- **The evidence record**, appended to `evidence/obf-dataset/README.md`: snapshot id,
  manifest digest, normalizer id and version, `output_contract_version`, the counts, and the
  field-presence table. Digests taken **while the rows exist** — TASK-007's record explains
  what happens otherwise.
- **Coexistence on real lineage, if it is free.** If a NAVER snapshot's normalized results
  are already present in the same database, record that `0.1` and `0.3` rows coexist over
  real data. If that requires a second capture, skip it and say so — the structural test in
  `test_normalizer_obf_product.py` already covers the property.

### Excluded

- **Any change to `normalizer.obf.product/handler.py` or `addon.toml`.** The add-on passed an
  independent attack: 24 of 30 mutants died, determinism held across 7 hash seeds. If a real
  row makes it behave wrongly, that is a **finding to report**, not a fix to make. Stop.
- **Any change to the four `product` body fields, or a fifth.** DP-028 D3 fixes them.
- **Deciding the `xx:` prefix question.** Record it; do not strip, map, or normalize it.
- **Repairing F2–F6 of the attack report.** TASK-008's disposition accepted them as recorded.
- The platform surrogate defect (`{"code":"a\ud800"}` → `UnicodeEncodeError` in
  `domain.store.canonical_body`). It predates this work and exposes `normalizer.naver.blog`
  identically. If a real row triggers it, that is a blocking finding and a stop, not a repair.
- `addon_api`, `addon_host`, `platform_core`, `domain/`, migrations, contracts, Decision
  Packets, `project-state.md`, and every other add-on.
- **`normalizer.rule.baseline` and its tests** — TASK-009 is queued against them.

### Allowed files

- `experiments/integrated-p0/tests/test_obf_real_data.py`
- `experiments/integrated-p0/evidence/obf-dataset/README.md`
- `experiments/integrated-p0/tests/test_normalizer_obf_product.py` — the F1 docstring
  attribution only. No assertion changes.
- this packet's `Status` line and `Worker handoff` section

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `experiments/integrated-p0/addons/**` — every add-on, unchanged
- `contracts/**`, `docs/decisions/**`, `docs/project-state.md`
- any Open Beauty Facts payload inside the repository working tree

## Acceptance criteria

1. A `normalized_result` row exists whose `source_item_key` traces to a sealed snapshot item
   carved from real Open Beauty Facts bytes, at `output_contract_version 0.3` with
   `record_type: "product"`, produced through the host path rather than a hand-built context.
2. The counts are recorded and add up: `results_emitted` plus `skipped` equals the snapshot's
   item count.
3. Field presence is recorded per field, and the sparsity is stated rather than smoothed. If
   every record carries every field, say so and treat it as suspicious.
4. `brands_tags`'s presence, list shape, and `xx:` prefix are confirmed or contradicted from
   your own run, and the prefix is recorded as an undecided schema question.
5. `evidence/obf-dataset/README.md` carries the snapshot id, manifest digest, normalizer
   version, contract version, counts, and field table — taken while the rows existed.
6. The F1 attribution is corrected and reads as a correction.
7. `git status --short` shows no OBF payload in the tree and no file outside the allowed list.
8. `ruff`, `mypy`, and the real-data test pass; `check-addons.sh` still reports both
   `importer.local.jsonl` and `normalizer.obf.product` `ok`.

## Verification

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

# `tests` is load-bearing: `--run-network` is defined by `tests/conftest.py`, and pytest
# loads a directory's conftest only when given a path under it. Recorded in
# `experiments/integrated-p0/tests/README.md` after it cost two workers time.
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests experiments/integrated-p0/tests/test_obf_real_data.py --run-network

.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_obf_product.py \
  experiments/integrated-p0/tests/test_importer_local_jsonl.py \
  tests/environment/test_addon_layer_direction.py

./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.obf.product
./scripts/check-addons.sh experiments/integrated-p0/addons/importer.local.jsonl
.venv/bin/ruff check experiments/integrated-p0/tests/test_obf_real_data.py
.venv/bin/mypy experiments/integrated-p0/tests/test_obf_real_data.py
```

`[측정]` Reading `httpx`'s certifi bundle is blocked by this session's sandbox
(`.venv/**/certifi/cacert.pem` is on the deny-read list), so network-hitting commands need
the sandbox disabled. TASK-007's worker recorded the same thing. State it if you do it.

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop if the real rows make the add-on behave wrongly.** A real row that produces a wrong
  record is the most valuable thing this packet can find, and repairing it here would destroy
  the independence of the attack the add-on already survived.
- **Stop if a criterion can only be met by deciding the `xx:` prefix.** That is the owner's,
  and a recorded open question is a complete result.
- **Stop if the snapshot holds zero items or the normalizer skips all of them.** Report the
  counts and the reason. An honest zero is a finding; a zero presented as a pass is not.

## Worker handoff

- Changed files:
  - `experiments/integrated-p0/tests/test_obf_real_data.py` — new class
    `TestTheNormalizerRunsOnTheRealSnapshot` (4 tests): runs the installed
    `normalizer.obf.product@0.1` through `JobRunner` and the host's normalize path over the
    real sealed snapshot, the same way `test_naver_real_data.py`'s
    `TestTheNormalizerRunsOnRealData` does for `normalizer.naver.blog`. Two small helpers
    added (`normalize_complete_fields`, `register_normalizer`, `run_normalize`) and one
    module-level constant pair (`NORMALIZE_SOURCE`, `NORMALIZE_ADDON_ID`).
  - `experiments/integrated-p0/tests/test_normalizer_obf_product.py` — module docstring
    only: the F1 attribution corrected from `SRC-003` to `DP-028 D3`, with a visible
    `[결정]` correction paragraph naming the attack report and this packet's own
    confirmation. No assertion changed.
  - `experiments/integrated-p0/evidence/obf-dataset/README.md` — new section "TASK-010 —
    the normalizer half of the flow, run for the first time": snapshot id, manifest digest,
    normalizer id/version, `output_contract_version`, counts, field-presence table, and the
    `brands_tags`/`xx:` measurement.
  - This packet's `Status` and `Worker handoff`.
- Commands and results:
  - `.venv/bin/ruff check experiments/integrated-p0/tests/test_obf_real_data.py
    experiments/integrated-p0/tests/test_normalizer_obf_product.py` → `All checks passed!`
  - `.venv/bin/mypy experiments/integrated-p0/tests/test_obf_real_data.py` → `Success: no
    issues found in 1 source file`
  - `.venv/bin/python -m pytest -q -p no:cacheprovider tests
    experiments/integrated-p0/tests/test_obf_real_data.py --run-network` → **`123 passed,
    1 warning`**. Run with the command sandbox disabled — same reason TASK-007's worker
    recorded: `ssl.create_default_context` needs to read
    `.venv/**/certifi/cacert.pem`, which this session's sandbox denies. Reproduced the
    failure first (`PermissionError` on that path, 12 errors) before disabling it.
  - `.venv/bin/python -m pytest -q -p no:cacheprovider
    experiments/integrated-p0/tests/test_normalizer_obf_product.py
    experiments/integrated-p0/tests/test_importer_local_jsonl.py
    tests/environment/test_addon_layer_direction.py` → `63 passed`
  - `./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.obf.product` →
    `ok`; `./scripts/check-addons.sh experiments/integrated-p0/addons/importer.local.jsonl`
    → `ok`
  - `git status --short` and `git check-ignore -v var/samples/obf/*.json` → no OBF payload
    in the tree (both delta files gitignored under `/var/`); only the four allowed files
    changed (`git status --short -uall -- experiments/integrated-p0/evidence/obf-dataset/`
    shows exactly `README.md`; the other pre-existing modified/untracked paths in a bare
    `git status --short` belong to concurrent TASK-006/007/008/009 work and this session's
    own environment files, none of them touched here).
  - **Measured counts, from the real run** (delta A, same file TASK-007 captured — the
    rolling window had not advanced): `item_count 121`, `results_emitted 121`, `skipped 0`
    (`121 + 0 == 121`). Field presence over the 121 emitted records: `display_name` 27/121,
    `brands` (non-empty) 22/121, `observed_at` 121/121, `has_ingredients=true` 16/121. This
    is the sparse shape SRC-003 predicted, not a suspiciously-full run — recorded per
    criterion 3, and `observed_at` at 100% (universal, unlike the other three) is new
    information this run adds. `brands_tags`: 22 records carried a non-empty list, 25
    individual tag values total, **all 25 carrying the `xx:` prefix** — this **confirms**
    TASK-008's `Review`-section measurement (70/70 prefixed across both deltas) from an
    independent run through the installed host rather than a hand read of the delta file.
- Evidence locations:
  - `experiments/integrated-p0/evidence/obf-dataset/README.md` (new section, this task)
  - `experiments/integrated-p0/tests/test_obf_real_data.py::TestTheNormalizerRunsOnTheRealSnapshot`
- Limitations and remaining risks:
  - **The add-on was not touched, per the packet's exclusion, and did not need to be.** No
    real row made it behave wrongly; every abstention path fired as its own unit tests
    already pin. This is reported as an observation, not a certification that no future
    real row could expose a gap — 121 rows from one delta is one sample.
  - **Coexistence with real NAVER rows over one lineage was not attempted.** It is not free:
    it would need a second real capture (`--run-network --run-credential`, a live API
    quota) landing in the same database as this run, and neither this session nor
    TASK-007's did that. `TestCoexistenceOverOneLineage`'s structural fixtures already
    cover the property, and the packet allows skipping this when not free.
  - **The `xx:` prefix question is recorded, not decided**, exactly as the packet requires.
    Both this run and TASK-008's `Review` section measured it; whether Schema 0.3's
    `brands` should carry the prefix or strip it is the project owner's.
  - **The exact `brands_tags` count (25 individual values / 22 non-empty records) differs
    numerically from TASK-008's `Review` figure (26 rows carrying the field, 70 values
    across both deltas)** — expected and explained in the evidence record: that figure was
    read from the raw payload across both deltas (a field present, possibly as `[]`,
    counts), this one is read from the normalized output of one delta (only a non-empty
    list counts). Both are real measurements; neither contradicts the other.
- Newly discovered questions or blockers: none. The `xx:` prefix is already an open
  question this packet routes to the owner rather than decides (see *Authority and
  dependencies*); nothing new surfaced beyond what TASK-008's `Review` section already
  named.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md)
- Result: `PASS`
- Orchestrator disposition: `ACCEPTED`. Every number in the evidence record was independently
  reproduced — digests, byte counts, 121/126, the 3-code overlap, the 244-member union, all four
  field counts at two layers, and manifest `82c27a07…` across two sessions, two processes, and two
  databases. `[측정]` `observed_at` at 121/121 is real: `last_modified_t` is present as an `int` on
  121/121 of delta A and 126/126 of delta B. `[측정]` The two `brands_tags` counts do not
  contradict — delta A has the key on 26 rows, 4 of them an empty list, and 70 of 70 values across
  both deltas carry the `xx:` prefix. `[측정]` Tamper detection's negative control was measured
  **outside** the test, on sibling databases: one returned `()` clean before mutation, the other
  named two problems after.

  Eight findings are open and none blocks acceptance. Record repairs go to
  [TASK-011](TASK-011-obf-record-repairs.md); F2 goes to
  [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md), where snapshot member selection
  already lives.
