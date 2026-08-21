# Lane A — M2 batches 2a/2b report (test-DB parallelization, domain schema, domain store core)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m2`, branch `p1/m2-domain`
- Commits:
  - `dbb7146` — "Parallelize the lane test databases and lay the domain schema with its P1
    identity fixes" (batch 2a)
  - `cfa88c6` — "Rebuild the domain store: sealed bytes, sequence-decided ties, byte-ordered
    manifests, rows that fail alone" (batch 2b)
- Verification summary: `cd apps && uv run mypy --strict . && uv run ruff check .` both clean
  (44 source files); `uv run python -m pytest -q` (unsandboxed, `COSMA_DB_HOST=127.0.0.1
  COSMA_DB_PORT=5433 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime
  COSMA_SECRET_SOURCE=~/.config/cosmai/env`) — **400 passed**, 0 failed, both with and without
  `COSMA_TEST_DB` set. Each of the three mandatory regression tests (DP-029 D2, DP-029 D3,
  DP-030 D2) was independently confirmed discriminating: I reverted the corresponding fix in
  `apps/domain/store.py` in place, re-ran only that test class, watched it fail with the
  expected P0-style error, then restored the file (`git diff` clean afterward) before
  committing.

## Batch 2a

- Provisioned `cosmai_test_2`/`_3`/`_4` on the shared server (`docker exec tubedepth-postgres`,
  `dangerouslyDisableSandbox` for the `docker exec`/TCP steps per the M1 global constraints):
  `CREATE DATABASE ... OWNER cosmai_owner`, `apps/db/provision_db.sql` (Part B) run against
  each, then the five Part C `ALTER ROLE ... IN DATABASE` session-default statements per
  database. No new role, no new password — `~/.config/cosmai/env` untouched, as instructed.
  Recorded in a dated section appended to `apps/db/provision.md`, including the negative
  verification (`SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail` → permission denied)
  and the lane-assignment note (Lane A = `cosmai_test`, B = `_2`, C = `_3`, M4 add-ons share
  `_4`).
- `apps/tests/conftest.py`: `TEST_DATABASE = os.environ.get("COSMA_TEST_DB", "cosmai_test")`.
  Everything else in that fixture (grant re-issue, the `test_migrate.py`-first ordering hook)
  is untouched.
- `apps/platform_core/db/migrations/0002_domain.sql`: P0's `0002_domain.sql` +
  `0003_normalized_result.sql` + `0004_input_profile.sql` + `0005_raw_item_payload_digest.sql`
  consolidated into one `cosmai.`-qualified, timestamptz file (P0 split them across two
  migration directories only because its own P0-A boundary guard scanned
  `experiments/integrated-p0/platform_core/` for domain vocabulary — a scope that does not
  reach `apps/platform_core`, confirmed by reading that guard's `SCAN_ROOT` before writing the
  file). Added `raw_item.seq bigint generated always as identity` (DP-029 D2) and a new
  `schedule` table (`source_id` PK/FK, `interval_seconds`, `enabled`, `next_run_at`,
  `last_run_at`, plus an `interval_seconds > 0` CHECK — a documented addition beyond the
  brief's literal column list, in house style with the file's other named-invariant
  constraints). Every P0 CHECK constraint carried forward verbatim.

## Batch 2b

- `apps/domain/store.py` + `apps/domain/__init__.py`: copy-adapted from
  `experiments/integrated-p0/domain/store.py`, schema-qualified to `cosmai.<table>` (DP-032
  D1/D3, the same adaptation `platform_core.jobs.store` already makes). No `domain/migrate.py`
  — the migration now lives beside `platform_core`'s own, so `apply_migrations` alone covers
  both.
- Three mandatory deviations, implemented and each independently falsification-tested (see
  Verification summary above):
  1. **DP-029 D2** — `SELECT_SNAPSHOT_MEMBERS`'s inner `distinct on (item_key) ... order by
     item_key, seq desc` replaces P0's `emitted_at desc, id desc`.
  2. **DP-029 D3** — the outer ordering is `order by convert_to(item_key, 'UTF8')`
     (`bytea` comparison is always unsigned-byte order in PostgreSQL, so this is
     collation-independent by construction); chosen over an app-side byte sort because the
     ordinal has to be assigned before materialization either way and this keeps it one round
     trip.
  3. **DP-030 D2** — `canonical_body` now passes `allow_nan=False` (closing P0's `allow_nan=True`
     gap); `record_results` routes both failure modes (a lone surrogate, a non-finite float)
     through a new `_safe_canonical_body` helper that narrows the failure to the first
     offending top-level field, replaces it with `null`, and writes a
     `notes.normalize_error {field, reason}` entry rather than raising. `record_results` now
     returns a `RecordResultsSummary(written, error_records)` instead of `None`, so a future
     run-summary caller (M3) has the error count without re-reading every row.
- Copy-adapted P0's `test_domain_store.py` (47 tests) and `test_normalized_results.py` (22 P0
  tests), located by grepping `experiments/integrated-p0/tests/` for `domain.store`/
  `DomainStore`/`canonical_body`/`SELECT_SNAPSHOT`. Adapted fixture names to this tree's own
  (`domain`/`store`/`connection` → `domain_store`/`job_store`/`job_connection`, matching
  `apps/tests/conftest.py`'s existing `job_store` convention) and schema-qualified every ad-hoc
  SQL string in the test bodies. No existing assertion changed.
- Added the three regression tests as new classes in `test_normalized_results.py`:
  `TestASameKeyTieIsBrokenBySequenceNotArrival` (two rows, same key, written inside one
  transaction — confirmed by asserting `count(distinct emitted_at) = 1` — re-sealed 12 times,
  always selects the higher-`seq` payload), `TestManifestOrderIsUtf8BytewiseRegardlessOfCollation`
  (keys `é`/`a`/`B`; asserts the store's actual order against a **live** `order by item_key
  collate "und-x-icu"` query on the same cluster, which really does disagree — `a, B, é` vs.
  the store's `B, a, é` — rather than assuming a collation difference; also asserts manifest
  digest stability across reseals), `TestPerRecordFaultTolerance` (1 bad row — the lone-surrogate
  case from `P1-INHERITED-DEFECTS.md` §1 — + 2 good rows → 3 stored results, 1 flagged, plus a
  separate NaN case and a clean-batch positive control).
- `apps/tests/conftest.py` gained `domain_store` and `_reset_domain_tables` fixtures.
  `_reset_domain_tables` depends on `_reset_job_tables` (not just `job_connection`) so the two
  resets nest correctly around the `raw_envelope.job_id`/`attempt_id` foreign keys.
- Also touched, both required to keep the existing gate green rather than scope creep on their
  own: `apps/tests/test_migrate.py` (`EXPECTED_VERSION` → `EXPECTED_VERSIONS`, now asserting
  both migration files and the domain tables' presence) and
  `apps/tests/conftest.py::worker_environment` (strips `COSMA_TEST_DB` from a spawned
  process's environment before adding the process's real `COSMA_DB_*` overrides — otherwise a
  `COSMA_`-prefixed test-harness variable that has nothing to do with the spawned process's own
  configuration trips its unknown-variable warning and broke
  `test_sec_003_case_f_the_api_entrypoint_reports_an_unknown_variable_and_runs`, which counts
  exactly one such warning).

## Concerns / deviations to flag for M7

- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py` was **not**
  copy-adapted. It depends on P0's per-test `CREATE DATABASE ... TEMPLATE`-cloned isolation and
  two separate migration directories (staging "every migration but one" to seal before an
  evolution) — both replaced in P1 by DP-032's one shared `cosmai_test` database and by this
  batch's single consolidated migration file. Reproducing its exact mechanism would mean
  building a template-clone fixture DP-032 deliberately declined. DP-029 D1 (materialization)
  itself is preserved verbatim in `apps/domain/store.py`'s implementation and is exercised by
  the ordinary snapshot tests in `test_domain_store.py`/`test_normalized_results.py`
  (tamper detection, read-back-in-fixed-order, manifest-digest stability), but the specific
  purge/later-collection/collation-migration timeline P0 measured is not re-run here. Flagging
  for M7 rather than silently dropping it.
- `RecordResultsSummary` (return type of `record_results`) and the `interval_seconds > 0` CHECK
  on `schedule` are both additions beyond the literal task brief — neither is a contract
  deviation, both are documented in the code and above.
- Root guard (`tests/environment`, 82 tests at last count) was **not** run from this worktree —
  it has no root `.venv` (confirmed: `apps/pyproject.toml`'s `pythonpath`/`testpaths` reference
  `experiments/integrated-p0`, which is a read-only path shared with the main checkout, and the
  worktree has no `.venv` at its root at all). Per the task brief this is expected and left for
  the M2 merge gate to run from the main checkout.
- Batches 2c (outbound/transport/credential parts) and 2d (domain API + scenario tests,
  `docs/p1/M2-RECORD.md`) are explicitly out of this task's scope and were not started.
