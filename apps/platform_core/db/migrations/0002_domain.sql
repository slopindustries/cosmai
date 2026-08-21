-- 0002 — the domain tables: registered sources, cursors, Raw, snapshots,
-- normalized results, and (new in P1) a schedule.
--
-- Copy-adapted and consolidated from four P0 migrations under
-- `experiments/integrated-p0/domain/migrations/`: `0002_domain.sql` (source,
-- source_cursor, raw_envelope, raw_item, snapshot, snapshot_item),
-- `0003_normalized_result.sql` (normalized_result), `0004_input_profile.sql`
-- (`source.input_profile` and its two CHECKs — folded directly into the
-- `create table source` below rather than a later `alter table`, since there
-- is no P1 database that predates this file), and `0005_raw_item_payload_digest.sql`
-- (`raw_item.payload_sha256`, likewise folded into `raw_item`'s own
-- definition).
--
-- P0 kept these as four separate files under `domain/migrations/`, a
-- directory distinct from `platform_core/db/migrations/`, because
-- `experiments/integrated-p0/tests/test_p0a_boundary_guard.py` scanned
-- `platform_core/` for domain vocabulary **including its .sql files** and a
-- migration creating `source` or `raw_item` there would have failed P0-A's
-- own build. That guard's `SCAN_ROOT` is `experiments/integrated-p0/platform_core`
-- (see `tests/environment/test_p0a_boundary_guard.py`), which does not reach
-- `apps/platform_core` at all — so P1 has no equivalent constraint, and one
-- file in this directory, applied after `0001_platform_core.sql`, is the
-- simpler shape: one `apply_migrations` call over one directory, no second
-- applier and no second `MIGRATIONS_DIRECTORY` to keep in sync.
--
-- DP-032 D1/D3, unchanged from `0001_platform_core.sql`'s own header: every
-- object below is qualified to schema `cosmai`, because the migrator role's
-- `search_path` is `pg_catalog` alone (`apps/db/provision.sql`) — an
-- unqualified reference does not resolve by accident, it simply fails.
-- Every timestamp is `timestamptz`; every enumerated column is `text` with a
-- CHECK; every constraint is named after the invariant it holds. All three
-- conventions are carried forward from P0 unchanged.
--
-- **DP-029's three P1 fixes, folded in here rather than left for a later
-- migration** (see `docs/decisions/DP-029-p1-snapshot-identity.md`, D1-D3):
--
--   * D1 — materialization. Already P0's shape (`snapshot_item` copies member
--     bytes rather than referencing `raw_item`); nothing to add here, the
--     store (`apps/domain/store.py`) is where D1 is actually held.
--   * D2 — `raw_item.seq bigint generated always as identity`. P0's same-key
--     tie-break used `emitted_at` (a transaction timestamp, not a per-row
--     order) falling back to `id desc` on a `uuid4`; DP-029's evidence
--     (12 forced-tie re-seals, 2 of 3 keys selecting the older payload) is
--     why this column exists and why the store's snapshot-selection query
--     orders by it instead. `generated always as identity` rather than a
--     sequence default: it is monotonic by construction, gap-tolerant on
--     rollback the same way a `serial` is, and cannot be supplied or
--     overridden by an INSERT the way a default expression technically can.
--   * D3 — the manifest ordering fix (UTF-8 bytewise on `item_key`,
--     independent of collation) is a query-time/app-time concern, not a
--     schema one; nothing here encodes it. It lives in
--     `apps/domain/store.py`'s manifest-building code, commented at the call
--     site per the task brief.
--
-- **New in P1, not in any P0 migration**: the `schedule` table
-- (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §M2, spec §5.5/§4.2).
-- M6 builds the scheduler process that polls it; this migration only lays
-- the table so M2's schema is the one M6 builds against, and creating it a
-- second time from a different lane would be the coordination problem
-- `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md`'s lane
-- structure exists to avoid.
--
-- What is NOT here, and why — carried forward from P0's `0002_domain.sql`
-- unchanged:
--
--   * **No install table.** DP-008 D8: the add-on directory is the installed
--     set; this schema records what add-ons *did*, never which ones exist.
--   * **No UPDATE/DELETE trigger on the Raw tables.** Raw is
--     "logically append-only" by the application never issuing a statement
--     that rewrites it, not by a trigger — DP-005's disposition rule
--     (`DELETE_AFTER_EVIDENCE_CAPTURE`) would have to be worked around a
--     trigger that forbade deletion.
--   * **No answer to the rest of OQ-004.** Selection semantics beyond what
--     DP-029 fixed (D1-D3), and backend-independent snapshot identity beyond
--     that, remain that question's — see DP-029 D4 and `SR-003`.

-- ---------------------------------------------------------------------------
-- source — a registered source, and the operator's approved configuration for it.
-- ---------------------------------------------------------------------------

create table cosmai.source (
  source_id             text        primary key,

  addon_id              text        not null,
  addon_version         text        not null,
  kind                  text        not null,

  config                jsonb       not null default '{}'::jsonb,
  config_schema_version text        not null,

  credential_ref        text,

  -- Platform-owned outbound grant (collector). DP-008 D4: an add-on declares,
  -- an operator grants — this column is the grant.
  outbound_profile      jsonb,

  -- Platform-owned local-input grant (importer). DP-024; mirrors
  -- `outbound_profile`'s shape for the same reason: the add-on names an
  -- input, the operator's profile says which file. Folded in here directly
  -- rather than added by a later `alter table`, unlike P0's `0004_input_profile.sql`
  -- (see this file's header).
  input_profile         jsonb,

  data_class            text        not null default 'local',
  enabled               boolean     not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),

  constraint source_kind_is_known
    check (kind in ('collector', 'importer', 'normalizer')),

  constraint source_data_class_is_known
    check (data_class in ('public', 'local', 'private')),

  -- DP-008 D6: `secret-setup.md`'s COSMA_SRC_<SOURCE_ID>_<PURPOSE> naming
  -- convention, turned into a constraint. A shape check, not a secrecy
  -- mechanism — a value that merely looked like a key name would still pass.
  constraint source_credential_ref_is_a_key_name
    check (credential_ref is null or credential_ref ~ '^COSMA_SRC_[A-Z0-9_]+$'),

  -- DP-008 D4's asymmetry, held where a *grant* (not just a manifest
  -- declaration) could break it: a normalizer reaches nothing outside its
  -- sealed snapshot.
  constraint source_normalizer_reaches_nothing_outside_its_snapshot
    check (
      kind <> 'normalizer'
      or (outbound_profile is null and credential_ref is null)
    ),

  -- DP-024 D6 as SQL. Each kind has exactly one input surface: a collector
  -- fetches, an importer reads a local file, a normalizer reads a sealed
  -- snapshot.
  constraint source_only_an_importer_reads_a_local_input
    check (kind = 'importer' or input_profile is null),

  -- An importer receives no network capability, so an outbound grant on one
  -- would be a grant nothing can spend. `credential_ref` is deliberately
  -- *not* forbidden here — the platform may need one to open a protected
  -- input (`addon_api.manifest`'s own rule).
  constraint source_an_importer_is_granted_no_outbound_profile
    check (kind <> 'importer' or outbound_profile is null)
);

create index source_by_addon on cosmai.source (addon_id);

-- ---------------------------------------------------------------------------
-- source_cursor — where a collector or importer stopped.
-- ---------------------------------------------------------------------------

create table cosmai.source_cursor (
  source_id  text        not null references cosmai.source (source_id),

  -- An add-on names its own streams; the platform does not interpret the name.
  stream     text        not null,

  -- Opaque to the platform. Giving this a schema would put source-specific
  -- pagination semantics in the platform, which is the coupling the add-on
  -- layer removes.
  cursor     jsonb       not null,

  -- Which attempt advanced it — the audit half of the atomicity requirement:
  -- the cursor's value and the attempt that produced it are written in one
  -- transaction, so a cursor can always be traced to the Raw it accompanies.
  updated_by_attempt uuid not null references cosmai.job_attempt (id),
  updated_at timestamptz not null default now(),

  primary key (source_id, stream)
);

-- ---------------------------------------------------------------------------
-- raw_envelope — the lossless original, recorded before an add-on interprets it.
-- ---------------------------------------------------------------------------

create table cosmai.raw_envelope (
  id             uuid        primary key,
  source_id      text        not null references cosmai.source (source_id),
  job_id         uuid        not null references cosmai.job (id),
  attempt_id     uuid        not null references cosmai.job_attempt (id),

  -- Provenance (DP-008 D8), recorded per envelope rather than read from
  -- `source`: `source.addon_version` moves when an add-on is upgraded, and
  -- this must keep saying what actually produced these bytes.
  addon_id       text        not null,
  addon_version  text        not null,

  -- For a collector: the endpoint name the add-on asked for. Null for an
  -- importer, which asked for a registered input instead.
  endpoint_ref   text,
  input_ref      text,

  -- No Authorization, Cookie, or provider-protected header reaches this
  -- table: p0-security.md requires them stripped before the platform's
  -- `fetch`/`open_input` ever calls the store.
  request_summary   jsonb,
  status            integer,
  response_headers  jsonb,

  body           bytea       not null,
  body_sha256    text        not null,
  content_type   text,
  retrieved_at   timestamptz not null default now(),

  constraint raw_envelope_digest_is_a_sha256
    check (body_sha256 ~ '^[0-9a-f]{64}$'),

  -- Exactly one origin: a collector names an endpoint, an importer names an
  -- input. Both or neither would leave provenance ambiguous or untraceable.
  constraint raw_envelope_names_one_origin
    check ((endpoint_ref is null) <> (input_ref is null))
);

create index raw_envelope_by_source on cosmai.raw_envelope (source_id, retrieved_at);
create index raw_envelope_by_attempt on cosmai.raw_envelope (attempt_id);

-- ---------------------------------------------------------------------------
-- raw_item — what the add-on extracted from an envelope.
-- ---------------------------------------------------------------------------

create table cosmai.raw_item (
  id           uuid        primary key,
  envelope_id  uuid        not null references cosmai.raw_envelope (id),

  -- Denormalised from the envelope so "every item of this source" needs no join.
  source_id    text        not null references cosmai.source (source_id),

  -- Identity **within one source**, chosen by the add-on. Deliberately not
  -- unique: duplicate and changed-content policy is still an open P0-B
  -- contract question, and a unique index here would answer it silently.
  item_key     text        not null,

  payload      bytea       not null,
  content_type text        not null,
  notes        jsonb       not null default '{}'::jsonb,
  emitted_at   timestamptz not null default now(),

  -- DP-029 D2: the same-`item_key` tie-break. `emitted_at` is a
  -- **transaction** timestamp — "the later import wins" held only per
  -- import, not per row, and P0's `id desc` fallback (a `uuid4`) selected
  -- the *older* payload in 2 of 3 keys across 12 forced-tie re-seals
  -- (`docs/decisions/DP-029-p1-snapshot-identity.md` D2 evidence). An
  -- explicit, monotonically increasing per-row sequence is what the
  -- snapshot-selection query (`apps/domain/store.py`) now orders by
  -- instead. `generated always as identity` rather than a nullable/default
  -- column: it cannot be supplied or overridden by an INSERT, so a caller
  -- cannot accidentally defeat the ordering by supplying its own value.
  seq          bigint      generated always as identity,

  -- DP-005/0005_raw_item_payload_digest.sql: the digest `raw_envelope` and
  -- `snapshot_item` already carry, closing the one link in that chain whose
  -- integrity was nowhere written down. Generated rather than supplied, for
  -- the same reason `normalized_result.body_sha256` is computed by the store:
  -- a digest written by whoever writes the row can disagree with the bytes
  -- beside it. `stored` (not `virtual`, PostgreSQL 18's default when neither
  -- is named) so the digest is written to disk with the row it describes.
  payload_sha256 text      not null
    generated always as (encode(sha256(payload), 'hex')) stored,

  constraint raw_item_digest_is_a_sha256
    check (payload_sha256 ~ '^[0-9a-f]{64}$')
);

-- Includes `seq` so the snapshot-selection query's `distinct on (item_key) ...
-- order by item_key, seq desc` can use this index directly instead of an
-- extra sort.
create index raw_item_by_source_key on cosmai.raw_item (source_id, item_key, seq desc);
create index raw_item_by_envelope on cosmai.raw_item (envelope_id);

-- ---------------------------------------------------------------------------
-- snapshot / snapshot_item — a sealed, hash-verifiable normalizer input.
-- ---------------------------------------------------------------------------
--
-- DP-029 D1: **materialized**. Member bytes are copied into `snapshot_item`
-- at seal time rather than referenced from `raw_item` — the only one of the
-- two designs OQ-004's own four-step Raw-store-evolution experiment measured
-- to replay byte-identically after a purge of every `raw_item` row.

create table cosmai.snapshot (
  id                 uuid        primary key,
  source_id          text        not null references cosmai.source (source_id),

  -- Materialized item count and the digest over the manifest of member
  -- digests. Tamper detection compares a recomputed manifest digest against
  -- this value without re-reading every item's own row.
  item_count         integer     not null,
  manifest_sha256    text        not null,

  -- Prose, not a query. What was selected and why, for a human reading a run
  -- afterwards.
  selection          jsonb       not null default '{}'::jsonb,

  -- Sealed means closed to further members. A run may only consume a sealed
  -- snapshot; the partial index below is what makes "sealed" checkable.
  sealed_at          timestamptz,
  created_at         timestamptz not null default now(),

  constraint snapshot_manifest_digest_is_a_sha256
    check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint snapshot_item_count_is_not_negative
    check (item_count >= 0)
);

create index snapshot_sealed on cosmai.snapshot (source_id, sealed_at) where sealed_at is not null;

create table cosmai.snapshot_item (
  snapshot_id  uuid        not null references cosmai.snapshot (id),

  -- Position within the snapshot, fixed at seal time by DP-029 D3's bytewise
  -- manifest ordering (held in `apps/domain/store.py`, not here).
  ordinal      integer     not null,

  item_key     text        not null,
  payload      bytea       not null,
  content_type text        not null,
  payload_sha256 text      not null,

  primary key (snapshot_id, ordinal),

  constraint snapshot_item_digest_is_a_sha256
    check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  constraint snapshot_item_ordinal_is_zero_based
    check (ordinal >= 0)
);

-- One member per key within a snapshot: an input with the same key twice
-- would make a normalizer's output depend on which one it read last.
create unique index snapshot_item_one_per_key on cosmai.snapshot_item (snapshot_id, item_key);

-- ---------------------------------------------------------------------------
-- normalized_result — where a normalized result goes (DP-019 D3, D4; DP-030).
-- ---------------------------------------------------------------------------
--
-- Three properties held here rather than in code, unchanged from P0's
-- `0003_normalized_result.sql`:
--
--   * **Versioned results coexist.** No UPDATE path, no "current" flag — two
--     normalizer versions over one snapshot are two sets of rows, both
--     readable.
--   * **A rerun is a duplicate, not a version.** The unique index below stops
--     an at-least-once retry from doubling every result.
--   * **Lineage is not optional.** `source_item_key` is `not null` and the
--     snapshot is a foreign key, so a result can always be traced to the
--     sealed bytes it came from.
--
-- DP-030 D2 (record-level fault tolerance): a record that fails canonical
-- serialization is still stored here, with the failing field replaced by
-- `null` and a `normalize_error` entry in `notes` — held by
-- `apps/domain/store.py`'s `canonical_body`/`record_results`, not by this
-- table's shape. No column changes for D2; `notes` already carries it.

create table cosmai.normalized_result (
  id                       uuid        primary key,

  snapshot_id              uuid        not null references cosmai.snapshot (id),
  source_id                text        not null references cosmai.source (source_id),

  addon_id                 text        not null,
  addon_version            text        not null,
  output_contract_version  text        not null,

  -- Lineage link. `raw_item.item_key` is not unique within a source, so this
  -- names a key and not a row: the snapshot fixes which bytes that key meant.
  source_item_key          text        not null,

  body                     jsonb       not null,

  -- Over the canonical serialization of `body`, computed by the store rather
  -- than supplied by the add-on.
  body_sha256              text        not null,

  notes                    jsonb       not null default '{}'::jsonb,
  created_at               timestamptz not null default now(),

  constraint normalized_result_digest_is_a_sha256
    check (body_sha256 ~ '^[0-9a-f]{64}$')
);

create unique index normalized_result_one_per_run_and_item
  on cosmai.normalized_result (snapshot_id, addon_id, addon_version, output_contract_version,
                                source_item_key);

create index normalized_result_by_source on cosmai.normalized_result (source_id, created_at);
create index normalized_result_by_snapshot on cosmai.normalized_result (snapshot_id);

-- ---------------------------------------------------------------------------
-- schedule — recurring collection, one row per source (new in P1).
-- ---------------------------------------------------------------------------
--
-- `docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §신규 API and §M2, and
-- `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md` §5.5: M6's
-- scheduler polls this table and creates a collect job for every `enabled`
-- source whose `next_run_at` is due, then advances `next_run_at` and records
-- `last_run_at`. `source_id` is the primary key rather than a surrogate one:
-- a source has at most one schedule, and a second row for the same source
-- would leave "which one does the scheduler honour" unanswered by the schema.
-- No `enabled`-implies-non-null-`next_run_at` constraint: an enabled schedule
-- that has never run yet (`next_run_at` still null) is a legitimate resting
-- state until the scheduler's first pass sets it, and M6 owns that state
-- machine — this table only has to hold it.

create table cosmai.schedule (
  source_id       text        primary key references cosmai.source (source_id),
  interval_seconds integer    not null,
  enabled         boolean     not null default false,
  next_run_at     timestamptz,
  last_run_at     timestamptz,

  constraint schedule_interval_is_positive
    check (interval_seconds > 0)
);
