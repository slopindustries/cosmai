# TASK-003 — Prove, or refute, that a sealed snapshot survives Raw-store evolution

- Status: `REWORK`
- Phase: P0-B, B4 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

A migration that really changes the Raw store after a snapshot is sealed, and a scenario
that says whether the snapshot still replays the same normalizer input — with a control
proving the scenario would have failed had it not.

`[확인 사실]` `p0-charter.md`'s fifth Architecture Question is *"Does the sealed snapshot
protect reproducibility from Raw-store evolution?"* `project-state.md` §5 already records
the answer as half-measured: *"Tampering is detected and named. **Raw-store evolution was
never exercised** — no migration changed the Raw tables after a snapshot was sealed — so the
half the hypothesis is actually about has no evidence."* The gate cannot answer this
question from what exists.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 4
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) D5 (what a snapshot selects), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4 — a normalizer receives a sealed snapshot verified before it sees a byte
- Open Questions: [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md)
- Owner decisions required: `none`
- Required evidence or environment: the local PostgreSQL cluster via `scripts/with-database.sh`

## Scope

### Included

- One migration under `experiments/integrated-p0/domain/migrations/` that makes a **real**
  change to a Raw table — a column added, a column widened, or a constraint changed — chosen
  so that a naive snapshot implementation would break and this one is claimed not to.
- A scenario test: seal a snapshot, apply the migration, then verify the snapshot still
  verifies **and** that reading it yields byte-identical normalizer input.
- **A control that fails.** The scenario must be shown to be capable of failing: a mutation,
  a deliberately broken variant, or a second assertion over a case where the property does
  not hold. State in the test what was observed failing and how.
- The migration must be idempotent, like its siblings — `test_migrations.py` already asserts
  that applying the shipped migration twice is safe.

### Excluded

- Any change to `addon_api`, `addon_host`, or the add-ons.
- Any change to how a snapshot is sealed, unless the scenario refutes the hypothesis — in
  which case **stop and report the refutation**, do not repair it.
- Anything under `docs/` except the worker handoff in this packet.

### Allowed files

- `experiments/integrated-p0/domain/migrations/0005_*.sql`
- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py` (new)
- `experiments/integrated-p0/domain/store.py` — **only** if the scenario refutes the claim,
  and only after stopping and reporting

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `docs/project-state.md`, `docs/architecture-synthesis/**`, `contracts/**` — a worker does
  not write the claim its own work is the evidence for

## Acceptance criteria

1. The migration changes a Raw table in a way a reader can see is not cosmetic. Say in the
   migration's own comment why this change is the one that tests the hypothesis.
2. Sealing happens **before** the migration and verification **after**. A test that migrates
   first proves nothing about evolution.
3. The scenario asserts both halves: the manifest still verifies, **and** the bytes a
   normalizer would read are identical to what was sealed. Verification alone is weaker than
   the hypothesis.
4. The control is real and its failure was **observed**, not asserted to be possible. Record
   the failure output in the test's docstring, as this repository's other scenarios do.
5. `test_migrations.py`'s idempotency guard passes for the new migration.
6. If the hypothesis is refuted, the packet result is a **refutation with evidence**, not a
   repair. That is a complete and valuable outcome.

## Verification

```sh
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py \
  experiments/integrated-p0/tests/test_migrations.py

# Then the whole suite, which must not regress from 1282 passed / 14 skipped:
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if the hypothesis is refuted.** Do not change how snapshots are sealed
  in order to make the scenario pass.

## Worker handoff

**The hypothesis held.** A sealed snapshot survived a real Raw-store migration: the
manifest still verified and the bytes a normalizer would read were identical, member for
member, to the ones sealed before the migration existed. No change was made to how a
snapshot is sealed, and none was needed.

### Changed files

- `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql` (new).
  `raw_item` gains `payload_sha256 text not null generated always as
  (encode(sha256(payload), 'hex')) stored`, plus the named CHECK its siblings carry. Two
  reasons, both in the file's own comment: `raw_envelope.body_sha256` and
  `snapshot_item.payload_sha256` exist while the table between them records no integrity
  at all, so the change is worth making on its own account; and `stored` rewrites the
  table, so every `raw_item` row that predates the migration is physically written again
  rather than the catalogue alone being touched. Generated rather than supplied for the
  reason `0003` gives for `body_sha256`, and because it leaves `domain.store.INSERT_ITEM`
  correct without a code change — this migration changes the Raw store and nothing else.
- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py` (new). Nine tests
  in three classes.

Nothing else was touched. `docs/project-state.md`, `docs/architecture-synthesis/**`, and
`contracts/**` are unchanged, as are `store.py`, `addon_api`, `addon_host`, and the add-ons.

### How the ordering is held

The test-isolation template applies every file under `domain/migrations/`, so a snapshot
sealed against the `database` fixture would already have lived through `0005`. The
`evolution` fixture therefore builds on `empty_database`, applies every domain migration
**except** `0005` from a staged copy, seals, and only then points the applier at the real
directory. Acceptance criterion 2 is asserted rather than described: the applier's return
value from that second call must be exactly `("0005_raw_item_payload_digest",)`.

### Commands and results

`./scripts/with-database.sh` could not be used — see *Limitations*. Every command below ran
with the three variables that script exports (`COSMA_DB_HOST=<repo>/var/postgres`,
`COSMA_DB_NAME=cosma_p0`, `COSMA_DB_USER=$(id -un)`) against the same already-running
cluster, PostgreSQL 18.4.

```text
$ .venv/bin/python -m ruff check experiments/integrated-p0/tests/test_snapshot_survives_migration.py
All checks passed!

$ .venv/bin/python -m mypy experiments/integrated-p0/tests/test_snapshot_survives_migration.py
Success: no issues found in 1 source file

$ .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_snapshot_survives_migration.py \
    experiments/integrated-p0/tests/test_migrations.py
17 passed in 2.16s

$ .venv/bin/python -m pytest -q -p no:cacheprovider          # whole suite, with the change
6 failed, 1170 passed, 13 skipped, 1 warning, 116 errors in 367.62s (0:06:07)

$ .venv/bin/python -m pytest -q -p no:cacheprovider          # whole suite, both new files moved out
6 failed, 1161 passed, 13 skipped, 1 warning, 116 errors in 394.03s (0:06:34)
```

`[측정]` The two whole-suite runs differ by exactly `+9 passed` — the nine new tests — with
the same six failures, the same 116 errors, and the same 13 skips. `1161 + 6 + 116 + 13 =
1296 = 1282 + 14`, so the packet's baseline is this environment's baseline plus the 122
cases the sandbox breaks. **No regression.** `[확인 사실]` All 122 fail on
`PermissionError: [Errno 13] Permission denied` at
`ssl.SSLContext.load_verify_locations`; this session's sandbox denies reads of
`.venv/.../certifi/cacert.pem`, and every one of them starts an API or worker subprocess.
They fail identically without the new files present.

`[측정]` `ruff check experiments/integrated-p0/` also reports two pre-existing `E501`s in
`tests/test_outbound_policy.py:704` and `:711`. Not touched — repairing an unrelated defect
found in passing is outside a worker's scope.

### The controls, and what was observed

Both were run and seen red. The failing output is quoted in the docstring of the test that
now holds each case, per acceptance criterion 4.

1. **The property does not hold for the design this one was chosen over.**
   `0003_normalized_result.sql` names that design in as many words — *"reproducibility is
   the whole reason a snapshot is materialized rather than queried"*. The test's
   `referenced()` helper is that alternative: it re-runs DP-019 D5's selection against
   `raw_item` at read time and hands on the row. Replacing the scenario's byte-comparison
   with `assert evolution.referenced_after == evolution.referenced_before`, changing
   nothing else, produced `1 failed, 8 passed`, with the diff showing the same row id and
   the same payload and one extra field, `payload_sha256`. The migration is therefore not
   a no-op with respect to what Raw yields; the sealed snapshot is simply not reading it.
2. **Both halves of the main claim go red when the sealed bytes move.** Moving an `update
   snapshot_item set payload = 'tampered'` into the fixture, immediately after
   `apply_migrations`, produced `2 failed, 7 passed`: `snapshot_tampering` named
   `member 1 ('item-002') no longer matches its digest` together with the manifest
   mismatch, and the replay comparison failed at index 1. The stored `payload_sha256` is
   unchanged on both sides of that diff, which is worth noticing — detection is a
   recomputation, not a comparison of two stored fields.

Both cases are kept permanently in `TestTheScenarioCanFail`, asserted in the direction they
were observed.

### Evidence locations

- The migration: `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql`
- The scenario and both controls: `experiments/integrated-p0/tests/test_snapshot_survives_migration.py`
- The observed failure output: in the docstrings of
  `TestTheScenarioCanFail.test_a_snapshot_that_referenced_raw_would_have_replayed_different_input`
  and `TestTheScenarioCanFail.test_both_halves_go_red_when_a_sealed_payload_is_altered`

### Limitations and remaining risks

- **`./scripts/with-database.sh` did not run in this session.** `pg_ctl status` reports "no
  server running" and then "another server might be running; trying to start server anyway"
  against a cluster that is up and answering on its socket — this sandbox cannot see the
  postmaster's PID, so the script's own start/status logic fails before it exports
  anything. Reported rather than worked around: no sandbox override was used, and the three
  environment variables the script exports were set by hand instead. The cluster, database,
  and socket are the ones the script would have used.
- **Another session held the cluster during these runs.** Databases are per-process, so the
  isolation holds, but the timings above are not clean.
- `test_migrations.py` exercises `platform_core/db/migrations/` only; its idempotency guard
  covers `0001` and nothing under `domain/migrations/`. I could not edit it — it is not in
  the packet's allowed files — so acceptance criterion 5 is met by
  `TestTheEvolutionIsSafeToApplyTwice` in the new file, which asserts the same property
  over the domain directory and adds the positive control `0001`'s guard lacks: re-executing
  the file itself raises `DuplicateColumn`, so the second pass is the *applier* skipping and
  not the file happening to be harmless. **This was a decision the packet did not settle.**
- The scenario exercises **one** kind of evolution: an additive, table-rewriting column on
  `raw_item`. It says nothing about a migration that drops or renames a column `store.py`
  reads, deletes Raw rows, or changes `snapshot_item` itself. The first two could not be
  written without breaking the suite or contradicting `0002_domain.sql`'s recorded
  append-only property; the third is a different hypothesis.
- "The bytes a normalizer would read" is a projection of `read_snapshot_items` written in
  the test to match what `addon_host.capabilities._NormalizeRun.execute` builds. The real
  host path was not driven, because doing so needs a whole job context and would put the
  add-on layer between the claim and the evidence. If that projection changes in
  `capabilities.py`, this test will not notice.

### Newly discovered questions or blockers

- `raw_item` now has a digest and `snapshot_item` computes its own in Python
  (`domain.store.digest_of`) over the same bytes. Nothing checks the two against each other
  at sealing time, and a mismatch would mean the copy is not the original. Cheap to assert;
  whether the platform *should* is a question for OQ-004 rather than for this packet.
- `SELECT_SNAPSHOT_MEMBERS` breaks a duplicate-key tie with `emitted_at desc, id desc`, and
  `id` is a `uuid4`. Two items with the same key written inside one transaction share
  `emitted_at`, so which one gets sealed is decided at random. The fixture asserts the two
  `emitted_at` values differ rather than relying on it, but the underlying nondeterminism is
  real and belongs to the open duplicate-policy question.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md)
- Result: `FAIL`
- Orchestrator disposition: `REWORK` into
  [TASK-005](TASK-005-snapshot-evolution-that-discriminates.md), 2026-08-20. The hypothesis
  was **not** refuted and nothing here is discarded — the migration, the ordering, and both
  controls survived independent attack, and the orchestrator reproduced the suite result
  outside the sandbox at **1291 passed, 14 skipped**, exactly the worker's `+9` with no
  regression. What failed is discrimination: F2 showed the queried design passing every one
  of these tests, so the experiment cannot tell a sealed snapshot from the alternative it was
  chosen over. TASK-005 adds an evolution that separates them, and closes F1 and F3. F4 is
  real, outside this packet's scope, and goes to the gate.
