-- 0005 — `raw_item` gains the digest its neighbours already carry.
--
-- This migration exists to be applied to a database that **already holds sealed
-- snapshots**. The P0 Charter's fifth Architecture Question asks whether the sealed
-- snapshot protects reproducibility from Raw-store evolution, and `docs/project-state.md`
-- §5 records the answer as half-measured in as many words: tampering is detected and
-- named, but no migration had ever changed the Raw tables after a snapshot was sealed, so
-- the half the hypothesis is actually about rested on reading the code rather than on
-- running it. `tests/test_snapshot_survives_migration.py` is the scenario, and this file
-- is the migration in it.
--
-- **Why this change, and not a cosmetic one.**
--
-- `raw_envelope` records `body_sha256` and `snapshot_item` records `payload_sha256`.
-- `raw_item` — the table between them — records neither, so the bytes an add-on extracted
-- are the one link in that chain whose integrity is nowhere written down. Closing that gap
-- is worth doing on its own account, which is what keeps this migration from being a prop
-- built for its test.
--
-- **What this change does NOT do, corrected 2026-08-20.** An earlier revision of this
-- comment claimed it was "the change that tells the two snapshot designs apart".
-- `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md` F2 measured that claim and it is false, and
-- the scenario now measures it on every run
-- (`test_an_added_column_does_not_tell_the_two_designs_apart`).
-- `0003_normalized_result.sql` names the alternative design in as many words —
-- *"reproducibility is the whole reason a snapshot is materialized rather than queried"* —
-- and `addon_api.results.SnapshotItem` carries exactly `item_key`, `payload` and
-- `content_type`. A **column added** to this table reaches neither design's normalizer, so
-- it separates nothing. What separates them is a change to which `raw_item` rows exist: a
-- later collection that supersedes a sealed key, or the purge that `0002_domain.sql`
-- anticipates when it declines a DELETE trigger on Raw. The scenario drives both.
--
-- This migration is therefore the *floor* of the experiment rather than its point — the
-- mildest evolution a Raw table can undergo, kept because a sealed snapshot has to survive
-- it too and because the digest it adds is worth having on its own account.
--
-- **Generated rather than supplied**, for the reason `0003_normalized_result.sql` gives for
-- `body_sha256`: a digest written by whoever writes the row can disagree with the bytes
-- beside it, and a digest that can disagree is not evidence. Generating it also leaves
-- `domain.store.INSERT_ITEM` correct without a code change, so this migration changes the
-- Raw store and nothing else — which is what the scenario needs it to be.
--
-- `stored` rather than `virtual`: the table is rewritten and every `raw_item` row that
-- predates this file is written again. That is what makes this an evolution of the data at
-- rest rather than of the catalogue alone. **The word is load-bearing and is now checked**:
-- PostgreSQL 18 makes `VIRTUAL` the default when `generated always as (…)` names neither,
-- `information_schema` describes the two identically, and until 2026-08-20 nothing here
-- would have noticed the difference. `pg_class.relfilenode` is read on either side of the
-- applier call, so changing this word turns the scenario red.

alter table raw_item
  add column payload_sha256 text not null
    generated always as (encode(sha256(payload), 'hex')) stored;

-- Named and shaped like `raw_envelope_digest_is_a_sha256`, and not redundant with the
-- generation expression above: the expression is what a later migration can change, and
-- this is what such a migration would have to drop deliberately rather than defeat by
-- accident. It is the same argument `0002_domain.sql` makes for stating an invariant as a
-- named constraint instead of trusting the code that writes the column.
alter table raw_item
  add constraint raw_item_digest_is_a_sha256
    check (payload_sha256 ~ '^[0-9a-f]{64}$');
