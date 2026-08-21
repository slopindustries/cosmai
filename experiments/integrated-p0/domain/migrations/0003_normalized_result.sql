-- 0003 — where a normalized result goes (DP-019 D3, D4).
--
-- `0002_domain.sql` says in its own "What is NOT here" section that it creates no
-- normalized-result table, and `addon_host.capabilities._UNBOUND_KINDS` refuses every
-- normalizer for exactly that reason, in those words. This is that table.
--
-- Three properties of `docs/project-state.md` §4 are held here rather than in code:
--
--   * **Versioned results coexist.** There is no UPDATE path and no "current" flag. Two
--     normalizer versions over one snapshot are two sets of rows, both readable, which is
--     what makes the version axis DP-008 D9 named into something comparable rather than
--     something asserted.
--   * **A rerun is a duplicate, not a version.** The unique index below is what stops an
--     at-least-once retry from silently doubling every result. It is the normalizer's
--     equivalent of `platform_effect`'s primary key, and it is the reason a normalize job
--     needs no separate idempotency token.
--   * **Lineage is not optional.** `source_item_key` is `not null` and the snapshot is a
--     foreign key, so a result can always be traced back to the sealed bytes it came from.
--     The P0 Charter's exit criteria ask for that link by name.
--
-- What is deliberately NOT here:
--
--   * **No schema for `body`.** `NormalizedResult.body` is a mapping and Schema 0.1 is
--     DP-019 D1's, checked by the host against the add-on's declared output contract. A
--     column per field would make every schema revision a migration, and OQ-003 is explicit
--     that 0.x is expected to move.
--   * **No index on anything inside `body`.** Nothing queries it yet. An index chosen
--     before a query exists is a guess about a decision OQ-002 has not made.

create table normalized_result (
  id                       uuid        primary key,

  -- The sealed input. A result with no snapshot could not be reproduced, and
  -- reproducibility is the whole reason a snapshot is materialized rather than queried.
  snapshot_id              uuid        not null references snapshot (id),

  -- Denormalised from the snapshot so that "every result of this source" needs no join,
  -- the same trade `raw_item.source_id` already makes.
  source_id                text        not null references source (source_id),

  -- Which normalizer produced this, and under which of the two version axes that can move
  -- independently (DP-008 D9). `addon_version` moves when the code changes;
  -- `output_contract_version` moves when the *meaning* does, and a reader comparing two
  -- result sets needs to know which of the two happened.
  addon_id                 text        not null,
  addon_version            text        not null,
  output_contract_version  text        not null,

  -- The lineage link. `raw_item.item_key` is not unique within a source, so this names a
  -- key and not a row: the snapshot is what fixes which bytes that key meant.
  source_item_key          text        not null,

  body                     jsonb       not null,

  -- Over the canonical serialization of `body`, computed by the store rather than supplied
  -- by the add-on. DP-019 D4: determinism is a property of what was stored, and an add-on
  -- that computed its own digest could report one that does not match what it wrote.
  body_sha256              text        not null,

  notes                    jsonb       not null default '{}'::jsonb,
  created_at               timestamptz not null default now(),

  constraint normalized_result_digest_is_a_sha256
    check (body_sha256 ~ '^[0-9a-f]{64}$')
);

-- The rerun guard. One (snapshot, normalizer, version, contract, item) produces one row;
-- a second attempt at the same tuple is a duplicate the platform refuses rather than a
-- version it stores. Versions coexist because the tuple *includes* both version columns.
create unique index normalized_result_one_per_run_and_item
  on normalized_result (snapshot_id, addon_id, addon_version, output_contract_version,
                        source_item_key);

create index normalized_result_by_source on normalized_result (source_id, created_at);
create index normalized_result_by_snapshot on normalized_result (snapshot_id);
