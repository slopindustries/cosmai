# ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT — attack report on TASK-003

- Packet: [`TASK-003-snapshot-survives-raw-store-evolution.md`](../../docs/agent-workflow/task-packets/TASK-003-snapshot-survives-raw-store-evolution.md)
- Worker revision: working tree at `f85287c` plus two untracked files —
  `domain/migrations/0005_raw_item_payload_digest.sql` (md5 `6e664802872bf619706fff81276f31a5`)
  and `tests/test_snapshot_survives_migration.py` (md5 `4c4dc9f386009eeeab31e587a4679ae1`)
- Attacker: `adversarial-reviewer`, separate session from the worker
- Date: 2026-08-20
- Result: `FAIL`

**The hypothesis was not refuted.** The narrow fact the worker reports is true and I
reproduced it independently: after a migration that really rewrites `raw_item`, the manifest
verifies and `read_snapshot_items` returns the sealed members byte for byte in the sealed
order. What fails is the *measurement* of that fact. One recorded control output cannot be
produced by the file in the tree (F1), and the evolution chosen cannot tell the snapshot
design under test apart from the design it was chosen over (F2) — so the scenario is green
for a reason weaker than the one it claims.

## Environment and what I changed

`[측정]` `./scripts/with-database.sh` fails here exactly as the worker recorded:
`pg_ctl: another server might be running; trying to start server anyway` / `could not start
server`, against a cluster that answers on its socket. No sandbox override was used. Every
command below ran with `COSMA_DB_HOST=<repo>/var/postgres`, `COSMA_DB_NAME=cosma_p0`,
`COSMA_DB_USER=$(id -un)` set by hand, against PostgreSQL 18.4 — the same cluster the script
would have exported.

`[확인 사실]` **I mutated files and restored them.** This report states it rather than hiding
it, as `ATTACKER.md` requires. Five production/test mutants (M1–M5) and two control
re-derivations were applied with `Bash` and reverted from copies taken before the first
change. Final `md5sum` matches the pre-attack copy for all four files touched
(`test_snapshot_survives_migration.py`, `0005_raw_item_payload_digest.sql`,
`domain/store.py`, `addon_host/capabilities.py`). A temporary probe module
`tests/test_zzz_attacker_probe.py` was created and deleted; `git status` shows only the two
files under review as untracked. Nothing was repaired.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| The two named files pass | `pytest -q -p no:cacheprovider tests/test_snapshot_survives_migration.py tests/test_migrations.py` | `17 passed in 3.48s` | reproduced |
| ruff clean | `ruff check tests/test_snapshot_survives_migration.py` | `All checks passed!` | reproduced |
| mypy clean | `mypy tests/test_snapshot_survives_migration.py` | `Success: no issues found in 1 source file` | reproduced |
| Sealing precedes the evolution | independent probe module (below) | at seal time `raw_item` columns are `emitted_at, envelope_id, payload, notes, id, source_id, item_key, content_type` — no `payload_sha256`; the post-seal applier call returned `('0005_raw_item_payload_digest',)` | **holds, and holds as a measurement rather than only as an assertion** |
| The migration rewrites the table | same probe, `pg_class.relfilenode` around the applier call | `200234` → `200345`; `pg_attribute.attgenerated = 's'` | **holds** |
| Control 1: `1 failed, 8 passed` | replaced the two assertions in `test_the_normalizer_reads_byte_for_byte_what_was_sealed` with `assert evolution.referenced_after == evolution.referenced_before`, changed nothing else | `1 failed, 8 passed in 1.24s`; the failing test is the named one; the diff carries `'payload_sha256': 'a9f6cbe0f3ae90fd7391c65bc4865460a65e78d6ad346d07f79a6715b46ab9e9'` — the same value the docstring quotes | **reproduced exactly** |
| Control 2: `2 failed, 7 passed` | moved `update snapshot_item set payload = 'tampered' … ordinal = 1` into the `evolution` fixture immediately after `apply_migrations`, per the docstring | **`3 failed, 6 passed in 1.14s`** | **not reproduced — F1** |
| No regression | not run whole; ran `test_domain_store`, `test_migrations`, `test_snapshot_survives_migration`, `test_importer_local_jsonl`, `test_normalized_results`, `test_normalizer_capability`, `tests/environment` → `202 passed`; and `test_capabilities`, `test_addon_host`, `test_normalizer_naver_blog`, `test_normalizer_naver_trend`, `test_normalized_results` → `173 passed` | no regression in the subsets run; the full suite was **not** run (see Limits) | partially reproduced |

The probe module, deleted after the run, applied every domain migration except `0005` from a
staged copy, collected one item, read `information_schema.columns` and `pg_class.relfilenode`
**before** sealing, sealed, applied `0005`, and read them again.

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| F1 Control 2's recorded output is not reproducible | `evaluation` | AC 4: record the failure that was observed | `3 failed, 6 passed`, not `2 failed, 7 passed` | **Major** | below |
| F2 The evolution does not break the naive design | `evaluation` / `specification` | Scope: a migration "chosen so that a naive snapshot implementation would break" | mutant M4 (a queried snapshot) leaves all five hypothesis tests green | **Major** | below |
| F3 The "physical rewrite" claim is not measured | `evaluation` | the test docstring asserts PostgreSQL rewrote the table | `stored` → `virtual` leaves all 9 tests green | **Moderate** | below |
| F4 "In the sealed order" is unguarded on the real host path | `implementation` (pre-existing) | a normalizer receives members in the sealed order | mutant M5 reverses that order; 9 + 173 tests all pass | **Major**, out of packet scope | below |
| F5 AC 5 is unsatisfiable as worded | `specification` | `test_migrations.py`'s guard covers the new migration | it applies `platform_core/db/migrations/` only | **Minor** | inspection |
| F6 `staged_without` misorders any future `0006` | `implementation` | the staged directory is the history before the evolution | it is the history *minus* `0005`, so a later file would be applied before an earlier one | **Minor** | inspection |
| M1 read order reversed in `READ_SNAPSHOT_ITEMS` | mutant | should be caught | `2 failed` — caught | — | killed |
| M2 duplicate tiebreak inverted in `SELECT_SNAPSHOT_MEMBERS` | mutant | should be caught | `1 failed` — caught | — | killed |
| M3 `snapshot_tampering` returns `()` unconditionally | mutant | should be caught | `1 failed` — caught by the tamper control | — | killed |
| Self-comparison | `evaluation` | the byte comparison must not compare a read to itself | it does not: `evolution.sealed` is captured before the applier call and is *also* compared against the literal `SEALED_MEMBERS` | — | held |
| Fixture pre-applies `0005` | `assumption` | `empty_database` must carry no migration | it clones with `template=None`, and does not depend on `migrated_template` | — | held |

---

### F1 — Major. The recorded output of control 2 cannot have come from this file.

**Claimed.** `test_both_halves_go_red_when_a_sealed_payload_is_altered` records, as a
`[측정]` in its own docstring, that moving its `update` into the `evolution` fixture
immediately after `apply_migrations` produced `2 failed, 7 passed`.

**Why it is false.** I followed that procedure exactly. It produces `3 failed, 6 passed`.
The third failure is `test_each_member_still_matches_the_digest_it_was_sealed_with`, and it
is not incidental — it is forced by a number the docstring itself quotes:

```
sha256(b'\x00\x01\x02 the second reading') = ca7fe1bf75c972778e65d4d1986d176a5833112a811430bf9d3d4f2a0a9a83e1
sha256(b'tampered')                        = d121be3103007b41edf96f8262925f8c7d61894afe9a041843b631f69445bc57
```

The docstring says "the stored `payload_sha256` is unchanged in that diff — `ca7fe1bf...` on
both sides". If the stored digest is `ca7fe1bf…` while the payload is `b'tampered'`, then
`digest_of(member.payload) == member.payload_sha256` — the single assertion of
`test_each_member_still_matches_the_digest_it_was_sealed_with` — must fail. A run of that
procedure in which it did not fail is a run against a file that did not yet contain that
test. The recorded measurement is from an earlier revision, carried forward unchanged.

This is the class `AGENTS.md` and this repository's own review history name first: evidence
named for a revision that could not have produced it. AC 4 asks for the *observed* failure;
what is recorded is an observation of something else.

**It is a defect in the record, not in the control.** The control is real and is *stronger*
than advertised: three assertions go red, not two, and the extra one is the per-member digest
check. Both quoted tracebacks match what I saw.

**Reproduction.**

```sh
# in tests/test_snapshot_survives_migration.py, in the `evolution` fixture,
# immediately after `applied = apply_migrations(handle, directory=DOMAIN_MIGRATIONS)`:
#     handle.execute(
#         "update snapshot_item set payload = %s where snapshot_id = %s and ordinal = 1",
#         (b"tampered", snapshot_id),
#     )
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py
# 3 failed, 6 passed in 1.14s
#   test_the_sealed_snapshot_still_verifies
#   test_the_normalizer_reads_byte_for_byte_what_was_sealed
#   test_each_member_still_matches_the_digest_it_was_sealed_with   <- unrecorded
```

---

### F2 — Major. The evolution does not tell the two snapshot designs apart.

**Claimed.** The packet's Scope requires a migration "chosen so that a naive snapshot
implementation would break and this one is claimed not to". The migration's own comment says
the change "is the change that tells the two snapshot designs apart", and control 1 is
offered as the case where the property does not hold.

**Why it is unproven.** I replaced `domain.store.READ_SNAPSHOT_ITEMS` with a read-time
re-query of `raw_item` — DP-019 D5's selection run at read time, `snapshot_item` never
touched. That *is* the naive design: a snapshot that fixed which rows it meant and read them
when the normalizer ran. **All five tests of
`TestASealedSnapshotSurvivesRawStoreEvolution` passed**, including
`test_the_normalizer_reads_byte_for_byte_what_was_sealed`.

```sh
# mutant M4, in domain/store.py:
# READ_SNAPSHOT_ITEMS = """
# select row_number() over (order by l.item_key) - 1 as ordinal,
#        l.item_key, l.payload, l.content_type,
#        encode(sha256(l.payload), 'hex') as payload_sha256
# from (
#     select distinct on (item_key) item_key, payload, content_type, emitted_at, id
#     from raw_item
#     where source_id = (select source_id from snapshot where id = %(snapshot_id)s)
#     order by item_key, emitted_at desc, id desc
# ) l
# order by l.item_key
# """
.venv/bin/python -m pytest -q -p no:cacheprovider \
  "experiments/integrated-p0/tests/test_snapshot_survives_migration.py::TestASealedSnapshotSurvivesRawStoreEvolution"
# 5 passed in 0.66s
```

The reason is structural, not accidental. `addon_api.results.SnapshotItem` carries exactly
`item_key`, `payload`, `content_type` — `[확인 사실]`,
`experiments/integrated-p0/addon_api/results.py:115`. No design in this repository, naive or
otherwise, hands a normalizer a whole `raw_item` row. An *additive* column therefore cannot
reach a normalizer under either design, so byte-identity of the normalizer input is preserved
by both, and the scenario's green says nothing about which one is in place.

Control 1 does not close this. Its `referenced()` helper compares `to_jsonb(latest)` — every
column of the row, including `id`, `notes`, `envelope_id`, `emitted_at`. That is not the
queried design; it is a strictly wider projection than any design here would use, chosen so
that an added column shows up. The difference control 1 observes is a difference in the
helper, not a difference the contract would ever see.

M4 *is* caught — but only by `test_both_halves_go_red_when_a_sealed_payload_is_altered`, in
the other class, and it catches it because tampering with `snapshot_item` becomes invisible,
which is a statement about tamper detection and not about Raw-store evolution.

`[추론]` So what the scenario measures is: *this particular additive migration does not
disturb the sealed bytes.* What the charter question asks is: *does sealing protect
reproducibility from Raw-store evolution* — which needs an evolution that would move the
input of a snapshot that had not sealed the bytes. On the three fields the contract defines,
an added column is not one. The worker's own Limitations section is close to this ("it says
nothing about a migration that drops or renames a column `store.py` reads, deletes Raw rows,
or changes `snapshot_item`") but stops short: those are not merely further cases, they are the
only cases that would discriminate.

---

### F3 — Moderate. The test does not measure the rewrite it claims to.

**Claimed.** `test_the_evolution_really_changed_the_raw_table` — "This one is `stored`, so
PostgreSQL rewrote the table and every `raw_item` written before it now carries a digest
computed after it."

**Why it is unproven.** I changed one word in the migration, `stored` → `virtual`, and ran
the file.

```sh
# 0005_raw_item_payload_digest.sql: "'hex')) stored;" -> "'hex')) virtual;"
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py
# 9 passed in 1.08s
```

`[측정]` Under `virtual`: `pg_attribute.attgenerated = 'v'`, `pg_class.relfilenode` unchanged
across the applier call (`203042` → `203042`) — **no rewrite at all** — and
`information_schema.columns` returns a byte-identical row: `('text', 'NO', 'ALWAYS',
"encode(sha256(payload), 'hex'::text)")`. The test's assertion
`columns["payload_sha256"] == ("text", "NO", "ALWAYS")` cannot distinguish the two, and PG 18
makes `VIRTUAL` the default for `generated always as (…)` with no keyword, so this is a live
distinction and not a hypothetical.

**The claim itself is true.** With `stored`, I measured `relfilenode` moving `200234` →
`200345`. The migration file is correct. What is decorative is the test that says it checks
it. `pg_attribute.attgenerated = 's'` and a `relfilenode` comparison would make it real.

---

### F4 — Major, and outside this packet's allowed files. "In the sealed order" is unguarded
on the path a normalizer actually takes.

The worker declares the projection risk: "if that projection changes in `capabilities.py`,
this test will not notice." I measured how large that hole is.

```sh
# mutant M5, addon_host/capabilities.py, _NormalizeRun.execute:
#   "for row in members" -> "for row in reversed(members)"
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py
# 9 passed
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_capabilities.py tests/test_addon_host.py tests/test_normalizer_naver_blog.py \
  tests/test_normalizer_naver_trend.py tests/test_normalized_results.py
# 173 passed          (identical to the unmutated baseline: 173 passed)
```

`[측정]` Reversing the order in which a normalizer receives the sealed members is caught by
**nothing** — not by the new scenario, not by the 173 host and normalizer tests. The claim
under attack includes "member for member and *in the sealed order*"; that half is proven for
`DomainStore.read_snapshot_items` and unproven for what an add-on receives.

`[확인 사실]` Pre-existing, not introduced by TASK-003, and `addon_host/` is on the packet's
Excluded list — the worker could not have fixed it. It is recorded here because it bounds what
this packet is allowed to conclude, and because it deserves a packet of its own.

---

### F5 — Minor. Acceptance criterion 5 asks for something that cannot be done.

`[확인 사실]` `test_migrations.py` calls `apply_migrations(handle)` with no `directory`, i.e.
`platform_core/db/migrations/`, in every test but the three that build a synthetic directory
under `tmp_path`. Its idempotency guard, `test_applying_the_shipped_migration_twice_is_safe`,
covers `0001_platform_core` and nothing under `domain/migrations/`. AC 5 is therefore
unsatisfiable without editing a file the packet forbids. The worker stopped, said so, and
substituted `TestTheEvolutionIsSafeToApplyTwice`, which asserts the same property over the
domain directory **and** adds the positive control the platform guard lacks — re-executing
the file itself raises `DuplicateColumn`, so the second pass is the applier skipping rather
than the file being harmless. That is the right call and the right disclosure; the defect is
in the packet's wording.

### F6 — Minor. The staging fixture is a trap for the next migration.

`staged_without` copies every `*.sql` except `0005`. A future `0006` would land in the staged
directory and be applied *before* `0005`, out of filename order. It would fail loudly rather
than silently, so this is a maintenance hazard and not an evidence defect — but the fixture's
name says "before the evolution" and what it builds is "everything except the evolution",
which are the same thing only for as long as `0005` is the last file.

## What I tried and could not break

Stated plainly, because a list of failures to falsify is a result.

- **The ordering.** Attacked first and hardest, since it is where the worker itself said the
  test was most likely to be wrong. It holds, and it holds as a measurement: at seal time
  `raw_item` has no `payload_sha256` column at all, and the applier's post-seal return is
  exactly `('0005_raw_item_payload_digest',)`. `empty_database` clones with `template=None`
  and does not depend on `migrated_template`, so no fixture pre-applies the migration.
- **Self-comparison.** `evolution.sealed` is read before the applier call, and the same
  members are independently compared against the module-level literal `SEALED_MEMBERS`, which
  is a genuine positive control: a degenerate read returning `[]` would satisfy
  `now == evolution.sealed` and fail the literal comparison. This is not the B3 defect.
- **Mutants M1, M2, M3** — reversed member read order, inverted duplicate-key tiebreak,
  `snapshot_tampering` returning `()` unconditionally — were all killed, with the failure
  landing on the test whose name describes the property.
- **Regression.** `202 passed` and `173 passed` across the database-backed suites that do not
  spawn subprocesses. The sandbox's `certifi` denial accounts for the subprocess block, as the
  worker described; I confirmed the mechanism and did not work around it.

## Scope and decision-boundary review

- **Allowed-file compliance:** clean. `git status` shows exactly the two permitted untracked
  files. `domain/store.py`, `addon_api/`, `addon_host/`, the add-ons, `docs/project-state.md`,
  `docs/architecture-synthesis/**` and `contracts/**` are untouched — verified by `git status`
  and by md5 against pre-attack copies after my own mutations were reverted.
- **Accepted-decision compliance:** DP-019 D5's selection is exercised rather than stepped
  around — a duplicate key is inside what gets sealed. `PoC Contract 0.1` §4 (verify before a
  byte is seen) is asserted, though only through `DomainStore` and not through the host path
  that implements it (F4).
- **Unanswered consequential direction:** the worker raised two and did not resolve them,
  correctly — the unchecked `raw_item.payload_sha256` versus `snapshot_item.payload_sha256`
  at sealing time, and `SELECT_SNAPSHOT_MEMBERS`'s random `uuid4` tiebreak on equal
  `emitted_at`. Both belong to OQ-004 and the open duplicate-policy question. F2 adds a third:
  whether an additive migration is an evolution *at all* for the purposes of this hypothesis.
- **Prohibited material exposure:** none. No credentials, no private data, no transcripts. The
  fixtures are three synthetic payloads.

## Conclusion

`FAIL`, and the reason matters more than the verdict.

**The hypothesis is not refuted and I found no evidence against it.** Under a migration that
demonstrably rewrites `raw_item` on disk, the sealed snapshot verified and replayed byte for
byte, and I confirmed the sealing genuinely preceded the migration by reading the table's
column list at seal time rather than by trusting the assertion that says so. Acceptance
criteria 1, 2 and 3 hold, and criterion 2 holds better than the handoff claims.

It fails on two of the packet's own requirements:

1. **AC 4 (Major, F1).** The control's recorded failure is not the failure the file produces.
   `3 failed, 6 passed`, not `2 failed, 7 passed`, and the missing third failure is forced by
   a digest the docstring itself prints. A recorded measurement that the tree cannot reproduce
   is the defect this repository has ruled on before.
2. **Scope (Major, F2).** The migration was required to be one "a naive snapshot implementation
   would break". It is not. Replacing `read_snapshot_items` with a read-time re-query of
   `raw_item` — the queried design `0003_normalized_result.sql` names as the alternative — leaves
   every test of the hypothesis class green. `SnapshotItem` has three fields, so an added
   column cannot reach a normalizer under either design. The scenario measures that this
   migration is harmless; the charter question asks whether sealing is what makes it harmless,
   and the two are not the same statement.

`[추론]` So the answer to the P0 Charter's fifth Architecture Question has moved from *no
evidence* to *evidence for the mildest case, from an experiment that cannot yet distinguish
the two designs*. `project-state.md` §5 should not be rewritten to say the hypothesis holds on
the strength of this. Both defects are in the evidence and are correctable without touching
`store.py`; neither suggests the sealing mechanism is wrong.

Per `ATTACKER.md`, this `PASS`/`FAIL` covers the named criteria and the attacks performed. The
full suite was not run in this session — a constraint of the session, not a judgement — so the
worker's `+9 passed / no regression` is reproduced only over the subsets named above.

## Required follow-up

- **New or revised packet — three:**
  1. *Re-derive and correct control 2's recorded output* in
     `test_both_halves_go_red_when_a_sealed_payload_is_altered`, to `3 failed, 6 passed` with
     the third test named. Smallest possible change; blocking for AC 4.
  2. *A discriminating evolution.* One migration that a queried snapshot would not survive —
     the candidates the worker listed and set aside, with the reasons they were set aside
     tested rather than assumed. Mutant M4 in this report is the acceptance test: it must go
     red in `TestASealedSnapshotSurvivesRawStoreEvolution`, not only in the tamper control.
  3. *Guard the host projection* (F4). `_NormalizeRun.execute` must hand a normalizer the
     sealed members in the sealed order, and something must fail when it does not. Needs a
     packet whose allowed files include `addon_host/`.
- **Open Question or Decision Packet update:** OQ-004 gains the question F2 exposes — what
  counts as a Raw-store evolution *for this hypothesis*, given that `SnapshotItem` projects
  three fields and an additive column can never reach one. Also the worker's two: the
  unchecked digest agreement at sealing time, and the `uuid4` tiebreak.
- **Project State or contract update:** none yet. §5's "Raw-store evolution was never
  exercised" may be narrowed to "exercised for an additive column only, by an experiment that
  does not yet separate the two snapshot designs" — but only after F1 is corrected, and by
  someone other than the worker.
- **Packet hygiene:** AC 5 as worded is unsatisfiable (F5) and should be rewritten to name the
  domain directory, so the next worker does not have to discover it.

## Where this file belongs

Beside the experiment it attacks, which is where it is. Link it from
`docs/agent-workflow/task-packets/TASK-003-snapshot-survives-raw-store-evolution.md` §Review —
`tests/environment/test_agent_packet_record.py` requires a resolvable link once the packet is
marked `ACCEPTED`.
