# TASK-005 — Make the snapshot evolution experiment discriminate, which TASK-003's did not

- Status: `WORKER_DONE`
- Phase: P0-B, B4 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

An evolution of the Raw store that **breaks the design a snapshot was chosen over**, and
leaves the sealed snapshot intact — so that passing the scenario means something a
re-query-at-read-time implementation could not also pass.

`[확인 사실]` [TASK-003](TASK-003-snapshot-survives-raw-store-evolution.md) is `REWORK`. Its
attack report,
[`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md),
returned `FAIL` on three findings this packet closes. The hypothesis was **not** refuted;
the measurement of it was.

`[측정]` F2, the one that matters: the attacker replaced `READ_SNAPSHOT_ITEMS` with a
read-time re-query of `raw_item` — the queried design `0003_normalized_result.sql` names as
the alternative — and **every test of `TestASealedSnapshotSurvivesRawStoreEvolution` passed
anyway.** The reason is structural: `addon_api.results.SnapshotItem` carries exactly
`item_key`, `payload`, `content_type`, so an *added column* cannot reach a normalizer under
either design. The experiment measured an evolution no design is sensitive to.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 4
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) D5, [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4
- Open Questions: [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md)
- Owner decisions required: `none` — the owner chose "rework into a discriminating experiment" on 2026-08-20
- Required evidence or environment: the local PostgreSQL cluster. **Connect with `psql -h "$COSMA_DB_HOST"`** — this machine also runs a system PostgreSQL on `/run/postgresql`, and an unqualified `psql` reaches that one and fails with `role "user1" does not exist`.

## Scope

### Included

- Keep `0005_raw_item_payload_digest.sql` and the existing scenario. They are correct as far
  as they go and the ordering held under independent attack. This packet **adds
  discrimination**, it does not start over.
- A second evolution that touches an axis a normalizer actually receives — `item_key`,
  `payload`, or `content_type` — or that removes Raw rows a snapshot named. Candidates the
  worker should weigh and choose between, recording why:
  - a migration that rewrites `raw_item.payload` for existing rows (a re-encoding, a
    normalization of stored bytes);
  - a migration or data change that **deletes** `raw_item` rows a sealed snapshot named;
  - a change to what `raw_item` rows exist for a source, so the queried design would return
    a different set.
- **The discrimination test itself.** Prove, as a permanent test, that the queried design
  fails where the sealed design passes. The attacker did this by hand by swapping
  `READ_SNAPSHOT_ITEMS`; make it a fixture-level alternative implementation the test can
  drive, so the discrimination is measured on every run rather than once by an attacker.
- **F1** — correct control 2's recorded output. Following its own docstring produces
  `3 failed, 6 passed`, not the recorded `2 failed, 7 passed`; the unrecorded third failure
  is `test_each_member_still_matches_the_digest_it_was_sealed_with`, forced by the digests
  the docstring itself prints. Record what the file actually produces.
- **F3** — make the physical-rewrite claim a measurement. `stored` → `virtual` leaves all
  nine tests green, and `VIRTUAL` is PostgreSQL 18's default, so the claim currently rests on
  one word nothing checks. Assert `relfilenode` moves, or drop the claim.

### Excluded

- Any change to how a snapshot is sealed or read. If the discriminating evolution **refutes**
  the hypothesis, stop and report the refutation. Do not repair `store.py` to make a test
  pass.
- F4 — that reversing member order in `addon_host/capabilities.py::_NormalizeRun.execute` is
  caught by nothing. Real, and outside this packet. It is recorded for the gate separately.
- `addon_api`, `addon_host`, the add-ons, `platform_core/`.

### Allowed files

- `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql`
- `experiments/integrated-p0/domain/migrations/0006_*.sql` (new, if the chosen evolution needs one)
- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py`

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `docs/project-state.md`, `docs/architecture-synthesis/**`, `contracts/**`,
  `experiments/integrated-p0/domain/store.py`

## Acceptance criteria

1. **A permanent test shows the queried design failing where the sealed design passes.** An
   alternative read implementation is driven by the test itself. If both designs pass every
   evolution the suite exercises, the experiment still does not discriminate and this packet
   is not met.
2. The sealed snapshot still verifies and still replays byte-identical members across the
   new evolution — or the refutation is reported with evidence.
3. Control 2's docstring records the output the file actually produces, verified by running
   it. `[결정]` Evidence named for a revision that cannot have produced it is the defect
   class this repository has already recorded; a corrected record is worth more than a
   flattering one.
4. The `stored` claim is asserted against `pg_class.relfilenode`, or removed. A claim no test
   holds does not go to a gate.
5. The whole suite does not regress from **1291 passed, 14 skipped**.
6. State plainly what remains unmeasured. TASK-003's handoff did this well; keep that.

## Verification

```sh
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py

./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if no evolution this repository can legitimately perform discriminates
  between the two designs.** That is itself an answer to the charter's fifth Architecture
  Question, and a more interesting one than a green test.

## Worker handoff

**The experiment now discriminates, and the hypothesis still holds.** A permanent test
drives the queried design as a drop-in for the sealed one and reads both at four moments on
one timeline. Under the additive migration the two are **indistinguishable** — F2, kept as a
measurement instead of a sentence in a review. Under two changes to which `raw_item` rows
exist, the queried design replays different bytes and then nothing at all, while the sealed
snapshot verifies and replays byte-identically at every step. `store.py` was not touched and
did not need to be.

### The evolution chosen, and why it is not a migration

`[추론]` **No schema migration of `raw_item` that this repository can legitimately apply
discriminates.** Recorded in the scenario as a `[가설]`, because that is what it is.
`SnapshotItem` carries three fields; a migration can add a column (cannot reach
them), tighten a constraint (cannot change a value), or rewrite values — and
`0002_domain.sql` records this store as having no statement that rewrites Raw. Dropping or
renaming `item_key`, `payload`, or `content_type` *would* discriminate, and breaks
`domain.store.INSERT_ITEM` and `SELECT_SNAPSHOT_MEMBERS` in the same statement, so it is not
an evolution of the Raw store alone. Its falsification condition is to exhibit one.

`[확인 사실]` The hypothesis is not only about migrations, and neither is the packet.
`project-state.md` §5 says *"despite later Raw-store **changes or** migration"*, and OQ-004's
own **minimum experiment** asks for the case that was never run: *"add later Raw observations
and simulate a changed Raw-store projection; replay only from the snapshot."* So the two
discriminating evolutions are changes to the rows:

1. **Later Raw observations.** A third collection supersedes `item-002` — a key the snapshot
   sealed — and adds `item-004`, which it never saw. DP-019 D5 selects "latest per key", so
   the queried design now resolves the same snapshot id to bytes that did not exist when it
   was sealed. This is the ordinary operation of a collector, not a fault, which is what
   makes it the case a snapshot has to survive; and it is the failure mode that would not
   announce itself, since the key and the member count look right.
2. **The disposition purge.** Every `raw_item` row of the source is deleted.
   `0002_domain.sql` declined a DELETE trigger on Raw **for exactly this reason** — DP-005
   gives Raw the `DELETE_AFTER_EVIDENCE_CAPTURE` disposition and a trigger would have to be
   worked around to honour it — so this is an operation the schema deliberately left
   available, not vandalism invented for a test. The queried design then has no input at all.

Weighed and rejected, with the reason rather than the assumption: a migration that
re-encodes `raw_item.payload`, and one that canonicalizes `item_key` or `content_type`. Both
discriminate, and both are statements that rewrite Raw — the property `0002_domain.sql`
records as held by the application having no such statement, and the losslessness `AGENTS.md`
requires of Raw payloads. Making one would have bought discrimination by contradicting an
accepted property, which is a worse trade than the one taken. TASK-003 set the same
candidates aside as untestable; the reason it gave for deletion — that it "contradicts
`0002_domain.sql`'s recorded append-only property" — is the one claim of the three that is
**wrong**: `0002` says the opposite in as many words.

### Changed files

- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py` — rewritten. 12 tests
  in four classes (was 9 in three). New: `queried_reader`, the alternative design as a
  reader with `DomainStore.read_snapshot_items`'s signature; a four-step timeline in the
  `evolution` fixture; and `TestTheExperimentTellsTheTwoDesignsApart`. The old control 1,
  which compared `to_jsonb(*)` of the whole Raw row, is folded into
  `test_an_added_column_does_not_tell_the_two_designs_apart` and demoted to what it is — a
  projection no design reads, kept to show *why* the migration cannot discriminate.
- `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql` — comment
  only; the DDL is byte-identical. The paragraph claiming this was "the change that tells
  the two snapshot designs apart" is replaced by the correction and by what does separate
  them. The `stored` paragraph now says the word is checked and where.

Nothing else was touched. `store.py`, `addon_api`, `addon_host`, the add-ons,
`platform_core/`, `docs/project-state.md`, `docs/architecture-synthesis/**` and
`contracts/**` are unchanged. No `0006` was written: the chosen evolutions need none, which
also means the whole suite carries no new migration.

### Commands and results

`./scripts/with-database.sh` still cannot start here — `pg_ctl: another server might be
running; trying to start server anyway` / `could not start server`, against a cluster that
answers on its socket. Reported, not worked around; no sandbox override was used. Every
command below ran with the three variables that script exports — `COSMA_DB_HOST=<repo>/var/postgres`,
`COSMA_DB_NAME=cosma_p0`, `COSMA_DB_USER=$(id -un)` — against PostgreSQL 18.4.

```text
$ .venv/bin/python -m ruff check experiments/integrated-p0/tests/test_snapshot_survives_migration.py
All checks passed!

$ .venv/bin/python -m mypy experiments/integrated-p0/tests/test_snapshot_survives_migration.py
Success: no issues found in 1 source file

$ .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_snapshot_survives_migration.py \
    experiments/integrated-p0/tests/test_migrations.py
20 passed in 3.51s

$ .venv/bin/python -m pytest -q -p no:cacheprovider          # whole suite
6 failed, 1173 passed, 13 skipped, 1 warning, 117 errors in 401.86s (0:06:41)
```

`[측정]` **No regression.** TASK-003 measured `6 failed, 1170 passed, 13 skipped, 116 errors`
in this same sandbox, and `1170 + 6 + 116 + 13 = 1305 = 1291 + 14`, this packet's baseline.
Mine differs by `+3 passed` — exactly the three tests added, 9 → 12 — with the same six
failures and the same 13 skips. `[확인 사실]` The 117th error is not mine:
`psycopg.errors.InvalidCatalogName: template database "cosma_p0_template" does not exist` at
`shared_database` setup, i.e. another session dropping the shared template mid-run.
`test_job_concurrency.py` on its own: `27 passed in 18.21s`. The 116 constant errors are the
sandbox's `certifi` denial, as the packet describes.

### The controls, all three re-derived by running them

1. **The discrimination control — the attack report's own acceptance test.** M4 edited
   `domain.store.READ_SNAPSHOT_ITEMS`, which this packet forbids, so it was run where a
   worker may: the fixture's `sealed_read = domain.read_snapshot_items` became
   `sealed_read = queried_reader(handle)`. `3 failed, 9 passed in 1.72s`, and the first
   failure is
   `TestASealedSnapshotSurvivesRawStoreEvolution::test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step`
   — the class the attack report required to go red and which stayed green under TASK-003's
   evolution. Recorded in the class docstring, including how the substitution differs from
   M4.
2. **F1 — control 2's recorded output, corrected by running its own procedure.**
   `5 failed, 7 passed in 1.74s`, with all five named in the docstring. Not the `2 failed,
   7 passed` TASK-003 recorded and not the `3 failed, 6 passed` F1 measured against the
   nine-test file: this file has twelve tests and two of the new ones are in the
   discrimination class, which the mutation also reaches.
3. **F3 — the rewrite claim, now a measurement.** `pg_class.relfilenode` is read on either
   side of the applier call and asserted to move, with `pg_attribute.attgenerated = 's'`
   beside it. Under the shipped migration it moves `253091 → 253202`; with the single word
   `stored` changed to `virtual`, `AssertionError: assert 246363 != 246363` and
   `1 failed, 11 passed in 1.74s`. The claim is asserted, so it was not dropped.

### Evidence locations

- The scenario, the alternative design, and all three controls:
  `experiments/integrated-p0/tests/test_snapshot_survives_migration.py`
- The corrected migration comment:
  `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql`
- Observed control output: in the docstrings of
  `TestTheExperimentTellsTheTwoDesignsApart` (class),
  `TestTheScenarioCanFail.test_both_halves_go_red_when_a_sealed_payload_is_altered`, and
  `TestASealedSnapshotSurvivesRawStoreEvolution::test_the_migration_rewrote_every_raw_row_that_predates_it`

### Limitations and remaining risks

- **What is still unmeasured, first: the host path.** F4 is untouched and outside this
  packet. `addon_host.capabilities._NormalizeRun.execute` is where a `SnapshotItem` is
  actually built, and reversing the member order there is caught by nothing. Everything
  above is asserted through `DomainStore` and a projection written in the test to match what
  that method builds. **If the discrimination is ever to mean "a normalizer received the
  sealed bytes", it has to be measured on that path, and it is not.**
- **The alternative design is the test's, not the platform's.** `queried_reader` is a
  faithful drop-in — its positive control shows it reproducing the sealed reading exactly
  before anything moves — but it is a reconstruction of a design this repository never
  implemented. If the real alternative would have differed (a recorded row-id list rather
  than a re-run selection, say), what is measured is my reading of it. The seal-time
  agreement is the only thing keeping that honest.
- **One evolution class remains untested: a change to `snapshot_item` itself.** A migration
  of the sealed table is a different hypothesis, and nothing here says anything about it.
- **`staged_without` is still "everything except `0005`" rather than "everything before
  it"** (attack report F6). Left alone deliberately: no `0006` was written, so it is dormant,
  and it fails loudly rather than silently when one lands. Repairing it is scope this packet
  did not name.
- **Timings are not clean.** Another session held the cluster throughout — it is the one that
  produced the 117th error, and its own untracked files appeared in the tree during the
  whole-suite run. The suite numbers above were taken before those files existed.
- The whole-suite comparison is against TASK-003's measurement in this same sandbox, not
  against a clean 1291/14 run, which this session cannot produce.

### Newly discovered questions or blockers

- **A purge does not reach a sealed snapshot, and that is the cost of the benefit.**
  `test_purging_the_raw_rows_leaves_the_queried_design_with_nothing` measures Raw being
  emptied while `snapshot_item` still holds the bytes and still verifies. For DP-005's
  `DELETE_AFTER_EVIDENCE_CAPTURE`, and for any erasure obligation, deleting Raw is therefore
  **not** sufficient — the copy survives in every sealed snapshot that named the row. This
  belongs to OQ-004 and is the sharpest new thing this packet found.
- **What counts as a Raw-store evolution for this hypothesis** — the question F2 exposed —
  now has a measured answer for `raw_item`: only a change to which rows exist. OQ-004 should
  carry it, and `project-state.md` §5's "Raw-store evolution was never exercised" can be
  narrowed, but by someone other than the worker whose work is the evidence.
- TASK-003's two open items stand unchanged: nothing checks `raw_item.payload_sha256`
  against `snapshot_item.payload_sha256` at sealing time, and `SELECT_SNAPSHOT_MEMBERS`
  breaks an equal-`emitted_at` tie on a random `uuid4`. The fixture asserts the three
  `emitted_at` values are distinct rather than relying on it.

## Review

- Attack report: not yet written
- Result: `BLOCKED`
- Orchestrator disposition: pending worker completion
