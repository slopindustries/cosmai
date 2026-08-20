# TASK-011 — Make the dataset record say what it measured, and give one number a guard

- Status: `ACCEPTED`
- Phase: P0-B, charter closure
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`
- Attacker: `adversarial-reviewer`
- Orchestrator: project owner's session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

`evidence/obf-dataset/README.md` is the file a P1 Entry Gate reader opens first for the
charter's dataset half. It is accurate about what ran and silent about what that does not
establish. Both are fixed, and the one number in it that nothing watches gets a test.

## Authority and dependencies

- Attack report, which is the whole input:
  [`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md)
  — F1, F3, F4, F5, F6, F7, F8. Read all seven before starting.
- Accepted decisions: [DP-028](../../decisions/DP-028-schema-0-3-product-records.md) **D6**,
  which is the line F4 says is missing; [DP-027](../../decisions/DP-027-dataset-standard-and-share-alike.md)
  D2, which measured the zeroes D6 refers to
- Prior packets, both `ACCEPTED`: [TASK-007](TASK-007-obf-dataset-end-to-end.md),
  [TASK-010](TASK-010-obf-real-snapshot-normalized.md)
- Owner decisions required: `none`
- Required evidence or environment: network and the local cluster for the F1 test only

## Scope

### Included

- **F4 (the one that matters) — the record does not carry DP-028 D6's line.** D6 reads: *no
  gate claim may read "the dataset half is closed" as "the dataset is useful for the product
  question"*. `[측정]` The attacker grepped the record for `Korean|NO-GO|sunscreen|toner|does
  not establish` and found one line, in a subordinate clause immediately softened. Add a
  section — **"What this does not establish"** — carrying: DP-027 D2's zero Korean sunscreen
  and zero Korean toner rows; that ingredient completeness is 26.5% database-wide with no
  threshold in this repository to judge it against; that "closed" means the path works, not
  that this dataset answers the product question; and that DP-026 moved that question to P1.
- **F1 — the field-presence table has no positive control.** `[측정]` Changing
  `handler.py`'s `"display_name": _display_name(row.get("product_name"))` to
  `... or "FABRICATED"` makes `display_name` 121/121 and the documented command still reports
  `123 passed`; the only guard is `assert not all(count == len(results))`, which stays green
  while any other field is sparse. Add an assertion in `test_obf_real_data.py` that pins each
  field's count **per field** against the payload — computed from the input file at run time,
  not hard-coded, so a later delta does not make it a false failure. Prove it goes red: apply
  the `or "FABRICATED"` mutation, show the new assertion fails, restore, and state the digest
  before and after.
- **F3 — "Fetched" is the wrong timestamp.** `[확인 사실]` The recorded value is
  `raw_envelope.retrieved_at`, which `capabilities.py:548` sets when the **local file** is
  read, not when HTTPS delivered it. Either record the real acquisition time from
  `FetchedDelta.fetched_at` beside it, or relabel the column so it says what it is. Do not
  silently keep a fetch-time label on a file-read time.
- **F5 — "a day earlier" is wrong.** `SRC-003` recorded delta A's digest the **same day**, at
  08:30:48. Correct it.
- **F6 — a docstring contradicts the record and the record is right.** The test module's
  docstring says a second fetch cannot reproduce the same bytes; three retrievals (08:30,
  15:36, 16:16) returned identical bytes, which is what an archived export does. Correct the
  docstring, not the record.
- **F7 — the TASK-010 section names no database.** Every other section does. Add it.
- **F8 — an unattributed section.** `experiments/integrated-p0/tests/README.md` gained a
  section on the `tests`-path requirement for `--run-network` that is in no packet's allowed
  files. `[확인 사실]` The orchestrator wrote it, on 2026-08-20, after it cost two workers
  time. Add that attribution line so the file does not carry anonymous provenance.

### Excluded

- **F2, the `emitted_at` tie-break.** Recorded in
  [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md) by the orchestrator. It is a
  contract question for P1, not a repair. Do not change snapshot member selection.
- **Any change to `normalizer.obf.product`, `importer.local.jsonl`, or any other add-on.**
  F1 is a *test* gap. The mutation you apply to prove the new assertion goes red must be
  restored, and the add-on's committed state must be byte-identical when you finish.
- Any change to `domain/`, `addon_api`, `addon_host`, `platform_core`, migrations, contracts,
  Decision Packets, or `docs/project-state.md`.
- Re-running the whole TASK-007/TASK-010 evidence chain. Its numbers were independently
  reproduced by the attacker; do not re-derive what is already twice-measured.
- **`normalizer.rule.baseline` and its tests** — a separate review is active there.

### Allowed files

- `experiments/integrated-p0/evidence/obf-dataset/README.md`
- `experiments/integrated-p0/tests/test_obf_real_data.py`
- `experiments/integrated-p0/tests/README.md` — the F8 attribution line only
- this packet's `Status` line and `Worker handoff` section

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `experiments/integrated-p0/addons/**`, `domain/`, `addon_api`, `addon_host`, `platform_core`
- `contracts/**`, `docs/decisions/**`, `docs/project-state.md`
- any Open Beauty Facts payload inside the repository working tree

## Acceptance criteria

1. The record carries a "What this does not establish" section with DP-027 D2's two zeroes,
   the 26.5% with its missing threshold, and DP-026's assignment of the product question to
   P1. A reader who opens only this file cannot mistake "closed" for "useful".
2. Each field's count is asserted individually against the payload, computed at run time.
   The `or "FABRICATED"` mutation makes it fail — shown, with digests before and after
   restoration.
3. The fetch-time column either carries the real acquisition time or no longer claims to.
4. F5, F6, F7, F8 are corrected, each visible as a correction where it replaces a prior claim.
5. `git status --short` shows only the allowed files; the add-on tree is byte-identical to its
   pre-mutation state; no OBF payload in the working tree.
6. `ruff`, `mypy`, and the real-data test pass.

## Verification

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

# `tests` is load-bearing — `--run-network` is defined by `tests/conftest.py`.
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests experiments/integrated-p0/tests/test_obf_real_data.py --run-network

.venv/bin/ruff check experiments/integrated-p0/tests/test_obf_real_data.py
.venv/bin/mypy experiments/integrated-p0/tests/test_obf_real_data.py
git diff --stat -- experiments/integrated-p0/addons/   # must be empty

grep -n "does not establish" experiments/integrated-p0/evidence/obf-dataset/README.md
```

`[측정]` Reading `httpx`'s certifi bundle is blocked by this session's sandbox; three prior
sessions recorded the same `PermissionError`. State it if you disable the sandbox.

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop if the new per-field assertion cannot be written without hard-coding today's
  counts.** A test that pins 27/121 as a literal will fail on the next delta for the wrong
  reason, and a gate reader cannot tell that from a real regression. Say so rather than
  shipping it.
- **Stop if correcting F3 would require changing what the platform records.** Relabelling is
  in scope; changing `capabilities.py` is not.

## Worker handoff

- Changed files:
  - `experiments/integrated-p0/evidence/obf-dataset/README.md` — added "What this does not
    establish" (F4); relabeled the "Fetched" row and added a clarifying note (F3); corrected
    "a day earlier" to "the same day, ~7 hours earlier" in both places it appeared (F5);
    named F7's traceability gap honestly rather than inventing a database name (see
    Limitations).
  - `experiments/integrated-p0/tests/test_obf_real_data.py` — added a per-field positive
    control to `test_field_presence_over_real_rows_is_recorded_not_smoothed`, computed at
    run time from `deltas`'s own bytes (F1); corrected the `deltas` fixture's docstring to
    match the record instead of contradicting it (F6).
  - `experiments/integrated-p0/tests/README.md` — added the F8 attribution line (orchestrator,
    2026-08-20) to the pre-existing `--run-network`/`tests`-path section.
  - This packet's `Status` and `Worker handoff`.
- Commands and results:
  - `.venv/bin/ruff check experiments/integrated-p0/tests/test_obf_real_data.py` →
    `All checks passed!`
  - `.venv/bin/mypy experiments/integrated-p0/tests/test_obf_real_data.py` →
    `Success: no issues found in 1 source file`
  - `export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"`
    then `.venv/bin/python -m pytest -q -p no:cacheprovider tests
    experiments/integrated-p0/tests/test_obf_real_data.py --run-network` → `123 passed, 1
    warning in 7.07s` (sandbox disabled for this command; certifi `PermissionError` recurred
    when tried inside the sandbox first, matching the packet's own note and three prior
    sessions).
  - F1 mutation proof: `handler.py` before `sha256:71156e6f…6a33f`. Applied
    `"display_name": _display_name(row.get("product_name")) or "FABRICATED"`. Re-ran the new
    assertion alone (`-k field_presence`, sandbox disabled): `AssertionError:
    per-field presence diverged … emitted {'display_name': 121, …}, source computes
    {'display_name': 27, …}` — `1 failed`. Restored the line verbatim; `sha256:71156e6f…6a33f`
    again — byte-identical, confirmed by digest match, not by inspection alone.
  - `git status --short` / `git diff --stat -- experiments/integrated-p0/addons/` — the
    `normalizer.obf.product` directory is untracked (as TASK-007/TASK-010 left it) and shows
    no `git diff` output; `normalizer.rule.baseline`'s tracked changes are the concurrent
    attacker's, untouched by this task.
  - `grep -n "does not establish" experiments/integrated-p0/evidence/obf-dataset/README.md`
    → line 19, `## What this does not establish`.
  - No OBF payload in the working tree: `var/samples/obf/*` all `git check-ignore` to
    `/var/`.
- Evidence locations: all commands above were run from the repository root; digests and the
  new assertion's failure/pass output are reproduced verbatim in this section rather than
  summarized.
- Limitations and remaining risks:
  - **F7** could not be satisfied as literally stated ("add" a database name) without either
    fabricating one or re-running the normalizer scenario outside this packet's stated
    evidence scope (`Required evidence: network and the local cluster for the F1 test
    only`; `Excluded: Re-running the whole TASK-007/TASK-010 evidence chain`). The original
    worker's kept database for TASK-010's snapshot `1ce74fc5…` was already dropped before
    this task, and no db name for that specific run survives anywhere in the record or the
    attack report (the attacker's own `_8`–`_11` databases are from an independent later run
    with different snapshot ids, not this one). I recorded the gap explicitly instead of
    inventing a plausible-looking identifier — a decision, not a silent read of the packet.
    If the orchestrator wants an actual database name on this line, that requires a new,
    explicitly authorized re-run of `TestTheNormalizerRunsOnTheRealSnapshot` with
    `--keep-database`.
  - F4's threshold-free 26.5% and the zero Korean rows are restated from `DP-027` D2 and
    `DP-028` D6 verbatim; no new measurement was taken for them.
- Newly discovered questions or blockers: none beyond the F7 limitation above.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-OBF-RECORD-REPAIRS.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-RECORD-REPAIRS.md)
- Result: `PASS`
- Orchestrator disposition: `ACCEPTED`. Findings B, C, D, and E are recorded and routed to the
  P1 Entry Gate as stated limitations rather than to a fourth round.

`[측정]` **F1's control is genuine and stronger than the packet asked for.** The attacker
rebuilt the presence computation offline and went red on **four mutations this packet never
named** — a different field, an off-by-one down, an off-by-one up, and a single skipped row —
while the old `not all(...)` guard stayed green for every one. The two sides do not share a
wrong origin: the computed side is an independent reimplementation sharing only the delta file.

`[측정]` **F7's deviation was verified, not merely accepted.** The database name is gone from
the cluster, gone from `var/postgres.startup.log` (`log_statement` off; its 27 dated
test-database lines end at 14:23 while TASK-010 ran ~18:06–18:09), and in no document. `[결정]`
The worker was right to record the gap instead of naming one, and this disposition says so
explicitly because the opposite call — a plausible identifier for a run that could not have
produced it — is the failure `naver-real-data/README.md` already carries a missing digest for.

`[결정]` **Four findings go to the gate rather than to a fourth round:**

- **B (Medium) — the control pins presence, not value.** `observed_at` replaced by a constant
  epoch on all 121 rows, `brands` replaced by `["xx:FABRICATED"]` (which also passes the
  `xx:`-prefix test), and `language` rewritten all stay green. So the record's *content*
  claims rest on one manual reading. `[추론]` Closing this means asserting values against the
  source per row, which is a larger test than the record it guards; P1 inherits it.
- **C (Low) — "computed at run time" is not "delta-proof."** `_observed_at(1e300)` abstains
  while the test's expectation counts it present, and `expected` counts file rows while
  `presence` counts snapshot members, which the seal dedupes. Either shape in a future delta
  makes it red for a non-defect.
- **D (Low) — one softener survives**, in the paragraph immediately above the disclaimer and
  in `test_obf_real_data.py`'s module docstring. The disclaimer itself is correct, complete
  against DP-027 D2 / DP-028 D6 / DP-026 D1, and placed ahead of every evidence table; the
  attacker could not construct the "dataset is useful" misreading from a full read.
- **E (informational) — criterion 5 was unverifiable as written.** `git status` cannot
  attribute changes in a tree three sessions are writing. `[결정]` A digest check is what a
  future packet should ask for; the attacker used the `handler.py` digest recorded in an
  *earlier* report, which the worker did not write, and that is the pattern worth keeping.

`[확인 사실]` **One command returned `BLOCKED` and the attacker did not work around it.** The
sandbox denies reading certifi's bundle, so the network run could not be reproduced; the
attacker recorded `--collect-only` matching the handoff's denominator of 123 and explicitly
claimed no reproduction of the pass. That is the correct answer under `AGENTS.md` and is
recorded rather than smoothed.
