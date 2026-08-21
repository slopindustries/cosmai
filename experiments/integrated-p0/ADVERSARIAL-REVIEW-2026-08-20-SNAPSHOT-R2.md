# ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2 — attack report on TASK-005

- Packet: [`TASK-005-snapshot-evolution-that-discriminates.md`](../../docs/agent-workflow/task-packets/TASK-005-snapshot-evolution-that-discriminates.md)
- Worker revision: `fb107da` ("Answer the charter's fifth question, after an attack said the first
  answer did not"), read at working tree `07c599b` with a clean tree for every file under review —
  `tests/test_snapshot_survives_migration.py` md5 `90979604dd3f7e5ef595e1b4b1036685`,
  `domain/migrations/0005_raw_item_payload_digest.sql` md5 `8305880a2aa85d17f3622db22dc06f83`
- Prior attack this one follows: [`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md`](ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md) (TASK-003, `FAIL`, F1/F2/F3)
- Attacker: `adversarial-reviewer`, separate session from the worker and from the previous attacker
- Date: 2026-08-20
- Result: `PASS` — on the six named criteria and the attacks performed. Two **Major** defects in
  the *record* are open, and one of them falsifies a claim carried in the commit message.

**The experiment now discriminates, and it discriminates for a real reason.** The previous
attack's own acceptance test — mutant M4, the queried design installed in
`domain.store.READ_SNAPSHOT_ITEMS` — was left green by TASK-003's file and is **killed** by this
one, in the class the report required to go red. Four independent mutations of `store.py`'s seal
and read are killed, each of them by the discrimination class's positive control, so the
discrimination is not decorative. F1 and F3 reproduce exactly as recorded.

**What is wrong is narrower than the record says it is.** Two things:

1. The `[가설]` that no legitimate schema migration of `raw_item` discriminates is **false**, and
   I falsified it by measurement with a one-statement migration that changes no value in any
   column (F-A).
2. `queried_reader` is not the alternative OQ-004 names, and against the alternative it *does*
   name, the headline discrimination — step 3, "the failure mode that would not announce
   itself" — **does not discriminate at all**. Only the purge does (F-B).

## Environment and what I changed

`[측정]` `./scripts/with-database.sh .venv/bin/python -c "print('script ok')"` fails here exactly
as both the worker and the previous attacker recorded: `pg_ctl: another server might be running;
trying to start server anyway` / `pg_ctl: could not start server`, against a cluster that answers
on its socket. No sandbox override was used and none was needed. Every command below ran with the
three variables that script exports — `COSMA_DB_HOST=<repo>/var/postgres`,
`COSMA_DB_NAME=cosma_p0`, `COSMA_DB_USER=$(id -un)` — against **PostgreSQL 18.4**.

`[확인 사실]` The cluster was created with `initdb --locale=C`: every database in it reports
`datcollate = C`, `datlocprovider = c`. That is load-bearing for F-A and F-D, and ICU collations
are present (`pg_collation` carries `und-x-icu` and its neighbours), so the migration in F-A is
one this cluster can actually apply.

`[확인 사실]` **I mutated files and restored them, and I created two probe modules and deleted
them.** Stated rather than hidden, as `ATTACKER.md` requires and as the previous attacker did.
Eleven mutants were applied with `Bash` and reverted from copies taken before the first change.
After the last run:

```text
90979604dd3f7e5ef595e1b4b1036685  experiments/integrated-p0/tests/test_snapshot_survives_migration.py
8305880a2aa85d17f3622db22dc06f83  experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql
a5df85d3bd87a0da7dfd5741083ad77b  experiments/integrated-p0/domain/store.py
12ca751e5cbd795d616ee86b777d2f50  experiments/integrated-p0/addon_host/capabilities.py
```

— identical to the pre-attack copies of all four, and `git status --short -- experiments/ docs/
contracts/` is empty. `tests/test_zzz_attacker_probe_r2.py` and
`tests/test_zzz_attacker_probe2_r2.py` were created, run, and deleted. **Nothing was repaired.**

`[측정]` One environmental collision is worth recording because it appears in output below and is
not the worker's: the cluster carries a leftover database `cosma_p0_test_main_8_17` from another
session, and one run reported `psycopg.errors.DuplicateDatabase: database
"cosma_p0_test_main_8_17" already exists` at fixture setup. It is a shared-cluster race, not a
finding.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| The file passes, 12 tests | `pytest -q -p no:cacheprovider tests/test_snapshot_survives_migration.py` | `12 passed in 1.66s` | **reproduced** |
| The file plus the migration guard | `… test_snapshot_survives_migration.py test_migrations.py` | `20 passed in 2.75s` | **reproduced exactly** |
| ruff clean | `ruff check tests/test_snapshot_survives_migration.py` | `All checks passed!` | reproduced |
| mypy clean | `mypy tests/test_snapshot_survives_migration.py` | `Success: no issues found in 1 source file` | reproduced |
| **F1 corrected** — control 2 is `5 failed, 7 passed` | moved the `update snapshot_item …` into the `evolution` fixture immediately after `applied = apply_migrations(handle, directory=DOMAIN_MIGRATIONS)`, per the docstring's own procedure | `5 failed, 7 passed in 1.72s`, and **the five failing tests are the five the docstring names, in that order** | **reproduced exactly.** The three-way disagreement is settled: `2 failed, 7 passed` was the 9-test file's stale record, `3 failed, 6 passed` was F1 measured against that 9-test file, and `5 failed, 7 passed` is what *this* 12-test file produces. The docstring records it correctly and explains both earlier numbers. |
| **F3 closed** — `stored` is asserted, not assumed | changed the single word `stored` → `virtual` in `0005`, ran the file | `1 failed, 11 passed in 1.67s`; `AssertionError: assert 305437 != 305437` on `test_the_migration_rewrote_every_raw_row_that_predates_it` | **reproduced**, same shape as the docstring's `assert 246363 != 246363` |
| Under the shipped migration `relfilenode` moves | inverted the assertion to `==` with the migration as shipped | `AssertionError: assert 308628 == 308517` | **reproduced.** The absolute numbers differ from the docstring's `253091 → 253202` because the database is fresh per run; the **delta is +111 in both**, which is what corroborates the docstring as a real measurement rather than a copied one (F-E) |
| The discrimination control, fixture-level | `sealed_read = domain.read_snapshot_items` → `sealed_read = queried_reader(handle)` | `3 failed, 9 passed in 1.84s`; first failure is `TestASealedSnapshotSurvivesRawStoreEvolution::test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step` | **reproduced exactly**, including which three |
| The docstring's `[확인 사실]` that this substitution differs from M4 (`snapshot_tampering` still calls the real reader, so it fails under M4 and not here) | compared the two runs below | true: under the fixture substitution `test_the_sealed_snapshot_still_verifies` **passes**; under the real M4 it **fails** | **holds** |
| No regression | not run whole (see Limits). `tests/environment/` → `81 passed`; the file under test plus `test_capabilities`, `test_normalizer_capability`, `test_normalized_results` → `113 passed in 10.50s` | no regression in the subsets run | partially reproduced |

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| **M4 proper** — the queried design installed in `domain.store.READ_SNAPSHOT_ITEMS`, the mutant the packet's AC 1 exists to kill | mutant | the hypothesis class must go red, not only the tamper control | `5 failed, 7 passed`, **including** `TestASealedSnapshotSurvivesRawStoreEvolution::test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step`. TASK-003's file left all five of that class green. | — | **killed**, below |
| **F-A** the `[가설]` "no legitimate schema migration of `raw_item` discriminates" | `assumption` / `evaluation` | the `[가설]`'s own falsification condition: exhibit one | one `ALTER` that changes no value in any column reorders every member the queried design replays | **Major** | below |
| **F-B** `queried_reader` is not the alternative OQ-004 names | `evaluation` / `specification` | the alternative measured should be the repository's, and the strongest form of it | against a reference-preserving reader, steps 1–3 **all agree** with the sealed design; only the purge separates them | **Major** | below |
| **F-C** the "purge of Raw" purges `raw_item` only, and DP-005 does not say what the test says it says | `evaluation` | a claim about DP-005's disposition must be DP-005's claim | `raw_envelope` is untouched by the purge (`3` rows / `39` bytes before and after); DP-005 assigns the disposition to the *database*, with the operator deleting it | **Moderate** | below |
| **F-D** DP-019 D5's ordering is collation-dependent and the collation is recorded nowhere | `specification` (new, pre-existing, outside the packet) | a snapshot's identity should not depend on unrecorded environment | two clusters with different collations seal different manifests from identical Raw | **Major**, out of packet scope | below |
| **F-E** the `relfilenode` numbers in the docstring cannot be re-derived | `evaluation` | a `[측정]` should be reproducible | `308517 → 308628` here, not `253091 → 253202`; the delta agrees | **Minor** | above |
| **F-F** the prior report's F4 and F6 still stand, as the worker said | `implementation` (pre-existing) | — | reversing member order in `_NormalizeRun.execute` leaves `112 passed` of 113 green | **Major**, out of packet scope | below |
| **F-G** AC 5 could not be verified in this session | `evaluation` | no regression from the stated baseline | full suite not run by instruction; the packet's `1291 passed, 14 skipped` baseline is also stale against the orchestrator's current `1351 / 14` | **Minor** | Limits |
| S-a `SELECT_SNAPSHOT_MEMBERS` duplicate tiebreak `emitted_at desc, id desc` → `asc, id asc` | mutant | should be caught | `4 failed, 8 passed`, incl. the discrimination class's positive control | — | killed |
| S-b `READ_SNAPSHOT_ITEMS` `order by ordinal` → `order by ordinal desc` | mutant | should be caught | `5 failed, 7 passed` | — | killed |
| S-c `seal_snapshot_from_raw` seals `payload[:4]` | mutant | should be caught | `4 failed, 8 passed` | — | killed |
| S-d `SELECT_SNAPSHOT_MEMBERS` outer `order by item_key` → `desc` | mutant | should be caught | `4 failed, 8 passed` | — | killed |
| S-e `queried_reader` returns `[]` unconditionally — the degenerate alternative | mutant | the absence assertion `after_the_purge.queried == ()` must not be satisfiable by a reader that never worked | `3 failed, 9 passed`, incl. `test_the_queried_reader_reproduces_the_sealed_reading_before_anything_moves` | — | killed |
| S-f the later collection withheld from the fixture | mutant | the discrimination must not be assertable without the evolution | `2 failed, 10 passed` | — | killed |
| Self-comparison in the new four-step timeline | `evaluation` | a byte comparison must not compare a read to itself | it does not: every step is compared against `evolution.at_seal.sealed` **and** against the module-level literal `SEALED_MEMBERS`; `QUERIED_AFTER_LATER_OBSERVATIONS` is the same control on the other side | — | held |
| Fixture pre-applies `0005` before sealing | `assumption` | the seal must precede the evolution | `applied_after_sealing == (MIGRATION_UNDER_TEST,)` is an assertion over what the applier reports it applied, and `staged_without` withholds the file; killed mutants S-a…S-d confirm the fixture is live | — | held |
| Allowed-file compliance | scope | three named files only | `git show --stat fb107da` → the packet, `0005`, and the test file. Nothing else. | — | held |

---

### M4 proper — the acceptance test of the previous attack report, and it dies here

`[측정]` The previous report's F2 was that installing the queried design in
`domain.store.READ_SNAPSHOT_ITEMS` left **every** test of
`TestASealedSnapshotSurvivesRawStoreEvolution` green. Its required follow-up said, in as many
words, *"Mutant M4 in this report is the acceptance test: it must go red in
`TestASealedSnapshotSurvivesRawStoreEvolution`, not only in the tamper control."*

I applied M4 to `domain/store.py` — the same replacement text, verbatim from that report — and ran
the file:

```sh
# domain/store.py: READ_SNAPSHOT_ITEMS replaced by the read-time re-query of raw_item
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py
# 5 failed, 7 passed in 1.69s
#   TestASealedSnapshotSurvivesRawStoreEvolution::test_the_sealed_snapshot_still_verifies
#   TestASealedSnapshotSurvivesRawStoreEvolution::test_the_normalizer_reads_byte_for_byte_what_was_sealed_at_every_step   <- the one required
#   TestTheExperimentTellsTheTwoDesignsApart::test_later_raw_observations_change_what_the_queried_design_replays
#   TestTheExperimentTellsTheTwoDesignsApart::test_purging_the_raw_rows_leaves_the_queried_design_with_nothing
#   TestTheScenarioCanFail::test_both_halves_go_red_when_a_sealed_payload_is_altered
```

`[확인 사실]` This is the packet's acceptance criterion 1 met against the **real** mutant and not
only against the fixture-level substitution the worker recorded. The two differ, and the
difference is in the worker's favour: under the real M4 the tamper control and
`test_the_sealed_snapshot_still_verifies` fail too, because `snapshot_tampering` reads through the
same mutated statement. The class docstring says exactly that and it is right.

`[추론]` **The discrimination is not decorative.** Four mutations of the sealed design's seal and
read (S-a…S-d) are each killed, and in **every one of the four**
`TestTheExperimentTellsTheTwoDesignsApart::test_the_queried_reader_reproduces_the_sealed_reading_before_anything_moves`
is among the failures. That is the property the parent attack line asked about: the sealed design
cannot be broken while the discrimination class stays green, because the class's first test is a
comparison against both the other design *and* a literal written before the run.

---

### F-A — Major. The `[가설]` is false, and a one-statement migration falsifies it

**Claimed.** `test_an_added_column_does_not_tell_the_two_designs_apart`, in its own docstring:

> `[가설]` No schema migration this repository can legitimately apply to `raw_item` tells the two
> designs apart. It is falsified by exhibiting one.

The same claim is the second paragraph of the commit message for `fb107da` and is the reason the
migration axis was abandoned in favour of row changes. Its stated taxonomy: a migration can *add a
column* (cannot reach a three-field projection), *tighten a constraint* (cannot change a value), or
*rewrite values* (which `0002_domain.sql` records this store as not doing).

**Why it is false.** The taxonomy is missing a category: **a migration can change how the
selection's `ORDER BY` and `DISTINCT ON` resolve without changing any value.** `item_key` ordering
is what DP-019 D5 fixes the member order by, and ordering over `text` is a function of the
column's collation, not of its bytes.

`[측정]` Probe module, run 2026-08-20 against PostgreSQL 18.4, deleted afterwards. The item keys
are the two shapes this repository actually produces — `collector.naver.blog` uses
`item_key=entry["link"]`, a URL; the two trend collectors use `f"{title}|{point['period']}"`:

```text
[at seal]
  sealed==queried: True
  order          : ['blog.naver.com/A', 'blog.naver.com/a', 'item-2', 'item_1']

# the candidate 0006, one statement:
#   alter table raw_item alter column item_key type text collate "und-x-icu"

[after the collation migration]
  every raw value unchanged : True          <- item_key, payload, content_type, payload_sha256
  sealed unmoved            : True
  sealed==queried           : False
  sealed  order : ['blog.naver.com/A', 'blog.naver.com/a', 'item-2', 'item_1']
  queried order : ['blog.naver.com/a', 'blog.naver.com/A', 'item_1', 'item-2']
  tampering                 : ()
  payload per ordinal, sealed  : [(0,'…/A','payload-A'), (1,'…/a','payload-a'), (2,'item-2','payload-hyphen'), (3,'item_1','payload-underscore')]
  payload per ordinal, queried : [(0,'…/a','payload-a'), (1,'…/A','payload-A'), (2,'item_1','payload-underscore'), (3,'item-2','payload-hyphen')]
```

**Every ordinal's payload changes under the queried design and none changes under the sealed one.**
`snapshot_tampering` still returns `()`.

**Why it is legitimate, on this repository's own terms.** Each of the reasons the worker used to
reject the payload-rewrite and canonicalization candidates is checked and holds here:

- **It rewrites no value.** Measured above: `raw_item`'s four columns compare equal row for row
  before and after. `AGENTS.md`'s losslessness requirement for Raw payloads is untouched, and
  `0002_domain.sql`'s "append-only is held by the application having no statement that rewrites
  Raw" is untouched in exactly the sense the shipped `0005` leaves it untouched — `0005` rewrites
  the heap too (that is what its own `relfilenode` assertion proves) and writes back identical
  values.
- **It drops and renames nothing.** `INSERT_ITEM` and `SELECT_SNAPSHOT_MEMBERS` compile and run
  unchanged, which is the property the worker used to exclude a drop or rename as "not an
  evolution of the Raw store alone".
- **It has a motive other than its test.** Byte order over URLs and Korean titles is not the order
  a reader would call "ordered by `item_key`" (`item-2` before `item_1`; `/A` before `/a`).
  Migrating a key column to a linguistic collation is an ordinary thing to want, and DP-019's own
  falsification table already names locale dependence as a hazard for D4.

`[추론]` A second instance of the same missing category, weaker because it does touch a value:
`alter table raw_item alter column emitted_at type timestamptz(0)`, or any precision reduction.
`[측정]` In the probe the four rows carry four distinct `emitted_at` values and **one** distinct
day, so a truncating migration collapses the duplicate tiebreak `order by item_key, emitted_at
desc, id desc` onto `id desc` — a random `uuid4`. The queried design would then resolve a
duplicate key to a row the seal did not choose. Not measured end to end; recorded as inference, not
as a result.

**What this does and does not break.** It does **not** refute the hypothesis — the sealed snapshot
was unmoved and still verified, which is one more piece of evidence *for* it, and it does not
touch acceptance criteria 1 or 2. What it breaks is the recorded reasoning: the migration axis was
abandoned on a claim that is false, and that claim is in the commit message, in the migration
comment, and in the test docstring. The `[가설]` label with its falsification condition is the
label working as intended, and this is the condition being met.

**Reproduction.** Seal a snapshot over keys that differ between `C` and a linguistic collation,
then:

```sql
alter table raw_item alter column item_key type text collate "und-x-icu";
```

and read both designs. On a cluster created by `scripts/with-database.sh` (`initdb --locale=C`),
`select array_agg(item_key order by item_key collate "C")` and the same with `collate
"und-x-icu"` already disagree on `('item-2','item_1')` and on `('blog.naver.com/A',
'blog.naver.com/a')`.

---

### F-B — Major. `queried_reader` is not the alternative OQ-004 names, and against the one it does name, step 3 does not discriminate

**Claimed.** The module docstring, lines 11–13:

> the attacker replaced `domain.store.READ_SNAPSHOT_ITEMS` with a read-time re-query of
> `raw_item` — **the design OQ-004 lists as the alternative,** *"preserve only references to
> append-only Raw observations"* —

and again at `QUERIED_SNAPSHOT_ITEMS`: *"OQ-004 lists it as an alternative, so it is the
repository's own and not a straw one."*

**Why it is false as stated.** `[확인 사실]` OQ-004's Alternatives section lists three, and the
first is verbatim *"Preserve only references to append-only Raw observations."* `queried_reader`
preserves **no** references. It stores nothing at seal time and re-runs DP-019 D5's selection from
scratch against whatever rows exist when the normalizer reads. Those are two different designs, and
the difference is precisely the axis step 3 tests: a reference-preserving snapshot has already
fixed *which rows* it meant, so appending rows cannot move it.

`[측정]` I implemented the reference design as a third reader — ordinals and `raw_item.id` recorded
at seal time, payload and content type fetched from Raw at read time — and drove it along the
worker's own four-step timeline. Probe module, deleted afterwards:

```text
[1 at seal]                          sealed==queried: True    sealed==referenced: True  (len 3)
[2 after the additive migration]     sealed==queried: True    sealed==referenced: True  (len 3)
[3 after later Raw observations]     sealed==queried: False   sealed==referenced: True  (len 3)
[4 after the raw_item purge]         sealed==queried: False   sealed==referenced: False (len 0)
```

`[측정]` **Step 3 does not discriminate against OQ-004's first listed alternative.** The
reference-preserving reader replays the sealed bytes byte for byte after the later collection,
because `raw_item` is append-only and the rows it named are untouched. Only step 4 separates it
from the sealed snapshot.

**Why this matters more than a citation.** Step 3 is the one the file sells hardest, and rightly
so — *"the failure mode that would not announce itself"*, a key that keeps its name and changes its
bytes with the member count still looking right. That failure mode belongs to the re-query design
only. The claim the experiment can support is narrower than the claim it makes:

- against **a re-query-the-selection snapshot**: the additive migration does not discriminate,
  later observations do, the purge does, and (F-A) a collation migration does;
- against **a reference-preserving snapshot**: only the purge discriminates.

`[확인 사실]` The worker's handoff discloses the shape of this risk honestly — *"If the real
alternative would have differed (a recorded row-id list rather than a re-run selection, say), what
is measured is my reading of it"* — and names the seal-time agreement as the only thing keeping it
honest. That disclosure is why this is a Major and not a Blocking finding: the limitation is
stated. What is not defensible is the test file asserting OQ-004's words about a reader that does
not implement them, in prose a gate reader will take as `[확인 사실]`.

`[추론]` Two further consequences worth carrying, neither measured: a reference design would
plausibly hold a **foreign key** to `raw_item`, in which case step 4's `delete from raw_item` is
not "the queried design has no input at all" but *"the purge is refused"* — a different and
sharper result, and one that bears on DP-005's disposition. And a reference design that stored the
id set without the ordinals would be discriminated against by F-A's collation migration, since it
would re-sort at read time.

**Reproduction.** Record `(ordinal, raw_item.id)` from
`SELECT_SNAPSHOT_MEMBERS`'s selection at seal time; at read time
`select item_key, payload, content_type from raw_item where id = %(id)s` per reference, in the
recorded order. Drive the existing `evolution` timeline with it.

---

### F-C — Moderate. The purge does not purge Raw, and DP-005 does not say what the test says it says

**Claimed.** `test_purging_the_raw_rows_leaves_the_queried_design_with_nothing`, and the handoff's
"newly discovered questions" as its sharpest new finding:

> DP-005 gives Raw the `DELETE_AFTER_EVIDENCE_CAPTURE` disposition, and `0002_domain.sql` declined
> a DELETE trigger on the Raw tables *for that reason* … `[추론]` a purge that reaches Raw does
> **not** reach the copy inside `snapshot_item`, so an erasure obligation is not discharged by
> deleting Raw alone.

**What is true.** `[측정]` The measurable core holds and I reproduced it: after `delete from
raw_item where source_id = 'demo'` removes all six rows, `snapshot_item` still holds three rows,
`snapshot_tampering` returns `()`, and the sealed design still replays `SEALED_MEMBERS` byte for
byte. A sealed snapshot is a second copy of the Raw payload that no deletion of `raw_item` reaches.
That is a real and worthwhile observation for OQ-004.

**Why it is overstated, in two ways.**

`[측정]` **First: the test's purge is not a purge of Raw.** `raw_envelope` is untouched by it —
measured `(3 rows, 39 bytes of body)` immediately before the delete and `(3, 39)` immediately
after. `project-state.md` §4's Raw is the *envelope* as much as the item; `0002_domain.sql` calls
`raw_envelope` "the lossless original" and `raw_item` "what the add-on extracted from an
envelope". In this fixture the envelope body is `b'{"items": []}'` so the item payloads are not
inside it, but in every real collection in this repository the item payloads are carved **out of**
that body. `[추론]` So in production the bytes survive a `raw_item` purge in `raw_envelope.body`
as well as in `snapshot_item`, and the sealed snapshot is the second of *three* copies, not the
second of two. The finding is real; the mechanism the docstring names is not the one that would
matter.

`[확인 사실]` **Second: DP-005 does not assign the disposition to `raw_item` rows.** DP-005 defines
`DELETE_AFTER_EVIDENCE_CAPTURE` as *"runtime Raw data, restricted downloads, temporary databases,
caches, or protected logs **removed after required metadata, hashes, and retention evidence are
recorded**"* — a disposition whose whole design is that digests outlive the payload.
`P0-ARTIFACT-DISPOSITION.md` assigns it to two things: *"NAVER captures in the local database"* and
*"Local PostgreSQL databases used by the suite"*, both with deletion responsibility **Operator**
and the rationale *"the rows themselves are the operator's to delete"*. The unit is the database,
not a table. So "deleting Raw does not discharge `DELETE_AFTER_EVIDENCE_CAPTURE`" argues against a
mechanism DP-005 never proposed; discharging it by dropping the database removes `snapshot_item`
with everything else.

**What survives the correction.** The genuine question — *if an erasure obligation ever requires
removing one source's Raw while keeping its snapshots, the snapshot is a copy nothing in this
schema reaches* — is real, is new, and belongs to OQ-004 and to `data-handling.md`. It is a
narrower and better-founded claim than "the sharpest new thing this packet found", and it needs
`raw_envelope` named beside `snapshot_item`.

---

### F-D — Major, new, outside this packet. DP-019 D5's member order depends on a collation nobody recorded

`[확인 사실]` This falls out of F-A and is larger than it. `snapshot.selection` stores the selection
as prose — `"every raw_item of one source, ordered by item_key"`, `"latest emitted_at wins"` — and
`0002_domain.sql` says so deliberately ("Prose, not a query"). But *"ordered by `item_key`"* is not
a complete specification of an order over `text`: it is complete only together with a collation,
which is a property of the cluster and is recorded nowhere in the snapshot, the selection, or
DP-019.

`[측정]` This cluster is `C` (`initdb --locale=C`, every `pg_database` row `datcollate = C`). Under
`und-x-icu` the same four keys seal in a different order, so **the same Raw produces a different
manifest digest**, hence a different snapshot identity, on a cluster that differs only in locale.

`[추론]` That bears directly on two accepted records:

- **OQ-004 H2** — *"Snapshot identity can remain independent of the storage backend"*, falsified by
  *"moving the exact bytes and manifest to another tested backend changes the logical snapshot
  identity"*. A backend with a different collation changes the *selection result*, and therefore
  the manifest, before identity is even discussed.
- **DP-019's falsification table for D4** — *"a rule whose output depends on locale, platform, or
  dictionary version"* is already named there as what would falsify determinism. `canonical_body`
  was written with exactly that care (`ensure_ascii=False`, "a later change of that setting would
  look like a normalizer that stopped being deterministic"). The same care was not taken for the
  order the snapshot fixes.

`[측정]` The sealed design is what *protects* against this: the collation migration left the sealed
snapshot unmoved. So this is evidence for hypothesis 4 and against the completeness of D5's
selection record. It is outside the packet's allowed files and needs its own packet or an OQ-004
update.

---

### F-F — Major, out of packet scope. The host path is still unguarded, exactly as the worker said

`[측정]` I re-measured the previous report's F4 because it bounds what "discriminates" is allowed
to mean here. `addon_host/capabilities.py`, `_NormalizeRun.execute`, `for row in members` →
`for row in reversed(members)`:

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_snapshot_survives_migration.py tests/test_capabilities.py \
  tests/test_normalizer_capability.py tests/test_normalized_results.py
# unmutated: 113 passed in 10.50s
# mutated:   112 passed, 1 error in 10.19s
```

`[확인 사실]` The one error is the shared-cluster collision named in the Environment section
(`DuplicateDatabase: cosma_p0_test_main_8_17 already exists`, at fixture setup of an outbound-guard
test), reproduced on a second mutated run and unrelated to the mutation. So the mutant is caught by
**nothing**, as the worker's own Limitations section states in the strongest available terms: *"If
the discrimination is ever to mean 'a normalizer received the sealed bytes', it has to be measured
on that path, and it is not."* That declaration is accurate and it is why this is recorded rather
than counted against the packet.

`[확인 사실]` The prior F6 also stands and is still dormant: `staged_without` copies every `*.sql`
except `0005`, no `0006` exists, and the worker declined to repair it as out of scope. F-A, if
acted on, is what would create the `0006` that wakes it.

## Scope and decision-boundary review

- **Allowed-file compliance:** clean. `git show --stat fb107da` is three files — the packet, `0005`,
  and the test module — with 1017 insertions and 6 deletions, the deletions all in the packet.
  `domain/store.py`, `addon_api/`, `addon_host/`, the add-ons, `platform_core/`,
  `docs/project-state.md`, `docs/architecture-synthesis/**` and `contracts/**` are untouched,
  verified by `git show --stat` and by md5 against pre-attack copies after my own mutations were
  reverted. `[확인 사실]` `0005` and the test module were untracked before `fb107da`, so "the DDL is
  byte-identical, comment only" cannot be checked against git history; the DDL matches what the
  previous attack report quoted (`'hex')) stored;`) and the previous report records the pre-change
  md5 (`6e664802872bf619706fff81276f31a5`) for anyone who wants to close that loop.
- **Accepted-decision compliance:** DP-019 D5's selection is exercised rather than stepped around —
  `queried_reader` reproduces `SELECT_SNAPSHOT_MEMBERS` statement for statement (same `distinct on
  (item_key)`, same `order by item_key, emitted_at desc, id desc`, same outer `order by item_key`),
  which is what makes it a faithful reconstruction *of the seal-time selection* even though it is
  the wrong one of OQ-004's alternatives (F-B). DP-005's disposition is cited beyond what it says
  (F-C). `PoC Contract 0.1` §4 is asserted through `DomainStore` only, not through the host path
  (F-F).
- **Unanswered consequential direction:** three carried forward, none resolved here — the alternative
  design's identity (F-B), the collation the selection does not record (F-D), and the two TASK-003
  items the worker restated: nothing checks `raw_item.payload_sha256` against
  `snapshot_item.payload_sha256` at sealing time, and `SELECT_SNAPSHOT_MEMBERS` breaks an
  equal-`emitted_at` tie on a random `uuid4`. F-A's second instance (`emitted_at` precision) is a
  live route into that second one.
- **Prohibited material exposure:** none. No credentials, no private data, no transcripts. Every
  payload in the scenario and in both probes is synthetic; the probe modules were deleted.

## What I tried and could not break

Stated plainly, because it is the larger part of the result.

- **The discrimination itself.** Attacked hardest, from both sides. The real M4 dies in the class
  the previous report named. Four mutations of the sealed design's seal and read (S-a…S-d) all die,
  and all four take the discrimination class's positive control with them, so the class cannot go
  green over a broken seal. A degenerate `queried_reader` returning `[]` dies (S-e), which is what
  makes `assert after_the_purge.queried == ()` an absence assertion with a positive control rather
  than the failure class this repository names first. Withholding the later collection dies (S-f).
- **The ordering and the seal-before-evolution precondition.** Unchanged from TASK-003 and still
  holds; the mutants above are the evidence that the fixture is live rather than the assertion
  that says so.
- **F1 and F3.** Both closed, both re-derived by running the procedures rather than by reading the
  docstrings, and control 2's five failures are the five named — the third of which the docstring
  proves by arithmetic it prints.
- **The hypothesis.** No evidence against it, and F-A adds a little for it: under a collation
  migration that reorders every member the queried design replays, the sealed snapshot was unmoved
  and still verified.

## Limits of this attack

- `[측정]` **The full suite was not run**, by instruction: the cluster is shared with other sessions
  and a full run collides on the template (the leftover `cosma_p0_test_main_8_17` and the
  `DuplicateDatabase` error above are what that collision looks like). AC 5 is therefore **not
  verified by me**. `[추론]` Its risk surface is small — the change is one test module plus a
  comment in a SQL file — and the subsets I ran (`20`, `81`, `113` passed) show no regression. The
  packet's `1291 passed, 14 skipped` baseline is in any case stale: the orchestrator's current
  clean baseline is `1351 / 14`.
- The reference-preserving reader in F-B is *my* reconstruction of OQ-004's first alternative, and
  the same objection the worker raised against its own `queried_reader` applies to mine. What F-B
  proves is not "the reference design is correct" but "the two candidate alternatives disagree
  about step 3", which is enough to make the file's attribution wrong.
- F-A's collation migration was measured against `queried_reader` and the sealed design over four
  keys in a probe, not as a `0006` in the migration directory. I have no Edit or Write and did not
  add one.
- Timings and one error are not clean; another session held the cluster throughout.

## Conclusion

`PASS`, on the packet's six named criteria and the attacks above, with two Major record defects
that must be corrected before a gate cites this experiment.

**The experiment discriminates, and for a real reason.** The test that the previous attack report
nominated as its acceptance criterion — the queried design installed in `store.py` itself — now
fails in the class it had to fail in, and it takes four other tests with it. The discrimination
cannot be green over a broken sealed design: every mutation I made to the seal or the read was
caught by the discrimination class's own positive control. That is the difference between a
measurement and a sentence in a review, and it is the thing TASK-005 was asked for.

Criterion by criterion: **1** met, and met against the real mutant rather than the fixture
substitution. **2** met — the sealed snapshot verified and replayed byte-identically at all four
steps, and under F-A's fifth evolution as well. **3** met exactly: `5 failed, 7 passed`, the five
named, the third explained by arithmetic the docstring prints, and both earlier numbers accounted
for. **4** met: `relfilenode` is asserted, and `virtual` turns the file red. **6** met, and met
well — the worker's Limitations section names the host path, the reconstruction risk, and the
untested `snapshot_item` axis before I did, and F-B and F-F are both findings its own disclosure
pointed at. **5** not verified in this session; see Limits.

What is defective is the reasoning the record carries around that result:

1. **F-A.** The `[가설]` that no legitimate schema migration of `raw_item` can discriminate is
   false. `alter table raw_item alter column item_key type text collate "und-x-icu"` changes no
   value in any column, drops and renames nothing, has a motive of its own, and reorders every
   member the queried design replays while the sealed snapshot does not move. The claim is in the
   commit message and in the migration comment, and the migration axis was abandoned on it. `[추론]`
   The taxonomy behind it is missing a category — *change how the selection resolves without
   changing a value* — and that category is where the interesting migrations live.
2. **F-B.** The alternative the file measures is not the alternative OQ-004 names, and the
   substitution matters: against a reference-preserving snapshot, step 3 — the discrimination the
   file sells hardest — does not discriminate at all. Only the purge does.

`[추론]` So the answer to the P0 Charter's fifth Architecture Question has moved from *evidence for
the mildest case, from an experiment that cannot distinguish the two designs* to *evidence that
sealing protects replay against three row-level evolutions and one schema evolution, measured
against one of the two designs the project named as the alternative.* That is a real advance and it
is not the advance the record claims. `project-state.md` §5 can be narrowed — "Raw-store evolution
was never exercised" is no longer true — but it should be narrowed to what F-A and F-B leave
standing, and by someone other than the worker or me.

Per `ATTACKER.md`, this `PASS` covers the named criteria and the attacks performed. It is not a
statement that the sealing mechanism is right, and F-D and F-F bound it: the collation the
selection does not record, and the host path where a normalizer actually receives the members, are
both outside what any test here checks.

## Required follow-up

- **New or revised packet — three:**
  1. **Correct the `[가설]` and record its falsification** (F-A), in
     `test_an_added_column_does_not_tell_the_two_designs_apart`, in
     `0005_raw_item_payload_digest.sql`'s comment, and in whatever the gate cites from `fb107da`'s
     message. The honest replacement is narrower and truer: *an additive column cannot discriminate,
     and a migration that changes how the selection resolves — collation, precision — can, without
     rewriting a value.* Optionally as a `0006` and a thirteenth test; `staged_without` will need
     the F6 repair the same day, because it applies "everything except `0005`" and would run `0006`
     first.
  2. **Fix the alternative's attribution, and measure the reference design** (F-B). Either implement
     OQ-004's "preserve only references" as a second reader in the same fixture — three designs on
     one timeline, which is a stronger experiment than two — or restrict the docstrings to the
     design that is actually driven and stop quoting OQ-004's sentence for it. The measurement is in
     this report and can be lifted.
  3. **Guard the host projection** (F-F). Unchanged from the previous report's third
     recommendation, and now the largest single gap between what is asserted and what a normalizer
     receives. Needs a packet whose allowed files include `addon_host/`.
- **Open Question or Decision Packet update:**
  - **OQ-004** gains three: the erasure question F-C leaves standing, stated over `snapshot_item`
    **and** `raw_envelope` rather than over "Raw"; the measured answer to *what counts as a
    Raw-store evolution for this hypothesis* (row changes, **and** collation- or
    precision-changing migrations); and F-B's finding that its own first listed alternative is
    separated from a sealed snapshot only by a purge.
  - **DP-019 D5 / OQ-004 H2** gain F-D: *"ordered by `item_key`"* does not fix an order without a
    collation, the collation is recorded in neither `snapshot.selection` nor the decision, and
    DP-019's own D4 falsification row already names locale dependence as the hazard.
  - The two TASK-003 items stand: the unchecked digest agreement at sealing time, and the `uuid4`
    tiebreak — into which F-A's `emitted_at`-precision variant is a live route.
- **Project State or contract update:** §5's "Raw-store evolution was never exercised" may be
  narrowed, to *"exercised for an additive migration (does not discriminate), for later Raw
  observations and a purge (discriminate against a re-query snapshot), and for a purge alone
  (discriminates against a reference-preserving snapshot); the sealed snapshot survived every
  one"* — after F-A and F-B are corrected, and not by the worker whose work is the evidence.
- **Packet hygiene:** AC 5's baseline (`1291 passed, 14 skipped`) is stale against the current
  `1351 / 14`, and a criterion that requires the full suite cannot be met by a session sharing this
  cluster. Name the scoped set that stands in for it, as this report and the previous one both had
  to do by hand.

## Where this file belongs

Beside the experiment it attacks, which is where it is. Link it from
`docs/agent-workflow/task-packets/TASK-005-snapshot-evolution-that-discriminates.md` §Review —
`tests/environment/test_agent_packet_record.py` requires a resolvable link once the packet is
marked `ACCEPTED`.
