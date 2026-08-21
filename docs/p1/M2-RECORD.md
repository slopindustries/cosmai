# M2-RECORD — what M2 built, what deviates, and what M3 owns next

- Milestone: M2 (`domain` — Raw persistence, outbound guard, snapshots, normalize/results,
  the domain API surface, and the credential-write path).
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m2`, branch `p1/m2-domain`.
- Batches and commits: 2a `dbb7146` ("Parallelize the lane test databases and lay the domain
  schema with its P1 identity fixes"), 2b `cfa88c6` ("Rebuild the domain store: sealed bytes,
  sequence-decided ties, byte-ordered manifests, rows that fail alone"), 2c `0a2c20f`
  ("Rebuild the outbound guard and credential attachment, structure unchanged (SR-001)"), 2d
  (this record's own commit).
- Date: 2026-08-21.
- Consumed by: M3's `addon_host` batches and the M7 closure review, per this plan's own
  §공통 제약 ("편차는 침묵하지 않고 각 레인 기록에 등재 — M7 리뷰가 대조한다").

## (a) Provisioning addendum

Batch 2a's own dated section is the record: `apps/db/provision.md`, "2026-08-21 — lane test
databases (`cosmai_test_2`/`_3`/`_4`)". Summary: three databases provisioned against the
**existing** `cosmai_owner`/`cosmai_migrator`/`cosmai_runtime` roles (no new role, no new
password — `~/.config/cosmai/env` untouched), each running `apps/db/provision_db.sql`'s Part B
verbatim plus the five Part C session-default statements. `apps/tests/conftest.py`'s
`TEST_DATABASE` now reads `COSMA_TEST_DB` (default `cosmai_test`), so a lane selects its
database by environment variable rather than by editing the fixture. Lane assignment: Lane A
(M2/M3/M4) = `cosmai_test`, Lane B (M5) = `cosmai_test_2`, Lane C (M6) = `cosmai_test_3`, M4's
per-add-on worktrees share `cosmai_test_4`, run sequentially.

## (b) Deviations ledger

### The three mandated deviations (batch 2b, DP-029/DP-030)

| # | What P0 did | What P1 does | Basis | Regression test |
|---|---|---|---|---|
| 1 | `SELECT_SNAPSHOT_MEMBERS` broke a same-`item_key` tie with `emitted_at desc, id desc` — a transaction timestamp plus a `uuid4` fallback. | Orders by `raw_item.seq desc` (`generated always as identity`) — the highest sequence number wins, independent of transaction grouping. | DP-029 D2 | `test_normalized_results.py::TestASameKeyTieIsBrokenBySequenceNotArrival` — two rows, same key, written inside one transaction (`emitted_at` provably equal, asserted), re-sealed 12 times, always selects the higher-`seq` row. Falsification confirmed by reverting the query to `emitted_at desc, seq` and watching the test fail on re-seal 0. |
| 2 | The outer `order by item_key` used whatever collation the connected cluster/column carried. | `order by convert_to(item_key, 'UTF8')` — `bytea` comparison is always unsigned-byte order, independent of collation. | DP-029 D3 | `TestManifestOrderIsUtf8BytewiseRegardlessOfCollation` — keys `é`/`a`/`B`, compared against a **live** `order by item_key collate "und-x-icu"` query on the same cluster (verified to actually diverge: ICU gives `a, B, é`; this store gives `B, a, é`), plus a manifest-digest-stability-across-reseals check. |
| 3 | `canonical_body` used `json.dumps(..., allow_nan=True)` and no guard against a lone UTF-16 surrogate; either failure mode raised out of `record_results` and aborted the whole run. | `canonical_body` now passes `allow_nan=False`; `record_results` routes both failure modes through `_safe_canonical_body`, which narrows to the first offending top-level field, replaces it with `null`, and writes `notes.normalize_error {field, reason}`. `record_results` now returns `RecordResultsSummary(written, error_records)` instead of `None`. | DP-030 D2; repairs `P1-INHERITED-DEFECTS.md` §1 | `TestPerRecordFaultTolerance` — 1 bad row (`P1-INHERITED-DEFECTS.md` §1's own lone-surrogate example) + 2 good rows → 3 stored results, exactly 1 flagged, no exception; a separate NaN case confirms it takes the same path; a clean-batch positive control confirms nothing is flagged when nothing is wrong. Falsification confirmed by reverting `record_results` to call `canonical_body` directly and watching both new-case tests fail with the pre-fix exceptions. |

### The M1 over-redaction exception (batch 2c, per the plan's §M2/2c paragraph)

`credential_ref` casefolds to `credentialref`, which **contains** `credential` — so M1's
`platform_core.obs.redaction.is_redacted_key` (substring containment against
`REDACTED_KEYS`) masked it, even though DP-018 D1 fixes a `credential_ref` as a secret-store
key **name**, never a value, and safe for an operator to see (the whole reason it is shown at
all — an operator needs the name to know which key to populate). `EXEMPT_KEYS` in
`apps/platform_core/obs/redaction.py` is an **exact**, casefolded match on `credential_ref`
only — not a second containment rule, so nothing else in `REDACTED_KEYS` loses coverage
(checked explicitly: `api_credential_and_secret` still masks). Regression tests:
`apps/tests/test_obs.py::TestTheCredentialRefExemption` (unit level) and
`apps/tests/test_domain_api.py::TestWritingACredential::test_the_credential_ref_itself_is_visible_in_the_log`
(end to end — the ref appears in the structured log stream after a credential write, the value
never does).

### Other deviations and additions flagged during this milestone

- **`domain.secrets` is not a separate module.** P0 had `experiments/integrated-p0/domain/secrets.py`
  distinct from `platform_core/secrets.py`. P1's `platform_core.secrets` already centralizes
  `resolve_credential` for both `COSMA_DB_*` and `COSMA_SRC_*` ref families (M1, DP-032 D4), so
  `apps/domain/outbound.py` imports it directly rather than duplicating a second copy. No new
  behavior; one fewer file than P0 had.
- **`write_credential` (DP-034 D1/D2) is new — P0 never built the write path DP-008 D6
  proposed.** Added to `apps/platform_core/secrets.py` alongside `resolve_credential`, reusing
  `secret_store_path()`'s location/permission guard so a write refuses under exactly the same
  conditions a read already does (unset, missing, inside the repository, wrong mode), rather
  than inventing a second, divergent location-resolution path. Writes are atomic
  (temp-file-plus-`os.replace`) and preserve the store's existing file mode.
  **`[등록, 2026-08-21, m7-fixwave, M-S3]`** `apps/platform_core/obs/redaction.py`'s
  `REDACTED_KEYS` does not include the credential route's own body field name
  (`value`) — `redact({"value": "THE-SECRET"})` is unmasked. `POST
  /sources/{id}/credentials` never routes that field through `redact` at all
  (`write_credential`'s value is a local variable for the call's duration, never
  logged, never returned — see `apps/domain/api.py`'s own docstring), so the
  route's write-only property holds by the code's own discipline, not by the
  redaction contract. B2's fix wave gave the *response* path a second,
  independent backstop — the platform-wide `RequestValidationError` handler that
  strips FastAPI's own `input` echo — which now also stands behind this route,
  but the redaction contract itself still does not know `value` is sensitive.
  Registered per M-S3, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`; no code
  change accompanies this note.
- **`apps/domain/api.py`'s placement is provisional.** P0 put the domain API extension in
  `addon_host/api.py`, the one layer allowed to import `domain` + `platform_core` +
  `addon_api` together. Nothing M2 built needs `addon_api` at all (no route dispatches to an
  add-on's own code), so this batch placed it at `domain.api` instead — a direction
  `tests/environment/test_addon_layer_direction.py` already permits. **M3 must decide**
  whether to import `extend_with_domain` from here and wrap it with the addon-dispatched
  routes, or move this module's routes into `addon_host.api` outright and retire this one.
  Either is a small change; the module's own docstring says so and repeats it here so it is
  not missed.
- **`RecordResultsSummary`** (return type of `DomainStore.record_results`, batch 2b) and the
  **`interval_seconds > 0` CHECK** on the `schedule` table (batch 2a) are both additions
  beyond the literal task brief text — neither is a contract deviation; both are documented at
  their definition site.
- **`apps/tests/conftest.py::worker_environment` strips `COSMA_TEST_DB`** from a spawned
  process's environment (batch 2a). It is `COSMA_`-prefixed but not a `platform_core.config`
  setting, so leaving it in a spawned worker/API process's environment tripped that process's
  own "unknown `COSMA_`-prefixed variable" warning — found because it broke
  `test_sec_003_case_f_the_api_entrypoint_reports_an_unknown_variable_and_runs`, which counts
  exactly one such warning.
- **`DomainStore.list_items`** (batch 2d, new) is the paginated raw-item read path
  (`LIST_ITEMS`, ordered by `seq` — the same identity column DP-029 D2 added — rather than
  `emitted_at`, for the same reason: stable paging while a collection is still appending
  rows). Not a deviation from anything P0 had; P0 never built this route at all (see §신규
  API below).

## (c) Scenario / test table

| Surface | Test file | Count | DB required |
|---|---|---|---|
| Test-DB parallelization + migration | `apps/tests/test_migrate.py` | 5 | yes |
| Domain store core (sources, cursors, Raw, snapshots, atomicity, CHECKs) | `apps/tests/test_domain_store.py` | 47 | yes |
| Normalized results, snapshot sealing, the 3 mandated regressions | `apps/tests/test_normalized_results.py` | 25 | yes |
| Outbound policy (pure functions, no socket) | `apps/tests/test_outbound_policy.py` | 90 | no* |
| Outbound transport (real TLS stub, bounded failures, loopback-flag repo scan) | `apps/tests/test_outbound_transport.py` | 23 | no* |
| Credential parts/attachment (`domain.outbound`-specific half only) | `apps/tests/test_credentials.py` | 7 | no* |
| Redaction, incl. the `credential_ref` exemption | `apps/tests/test_obs.py` | 108 | no* |
| `platform_core.secrets`, incl. `write_credential` | `apps/tests/test_secrets.py` | 35 | no* |
| Domain API (sources, raw, raw/items, snapshots, seal, normalize-creation, results, credential write) | `apps/tests/test_domain_api.py` | 42 | yes |

*Every module in this suite still needs a live server for `conftest.py`'s session-scoped
`_reset_schema` autouse fixture to collect at all (documented in `conftest.py`'s own
docstring, carried from M1) — "no DB required" above means the module's own assertions do
not touch it, not that the run can skip `COSMA_DB_*`/`COSMA_SECRET_SOURCE`.

Full-suite total at the end of batch 2d: **579 passed**, `mypy --strict` clean (51 source
files), `ruff check` clean.

## (d) M3-deferred route list

`apps/domain/api.py` does **not** implement:

- `POST /sources/{source_id}/collect`
- `POST /sources/{source_id}/import`

Both would create a job whose `handler` names `f"addon:{addon_id}"` — a dispatch convention
that lives in `addon_host.registration` (P0) and has no P1 implementation yet. Creating such a
job today would insert a row nothing can ever claim (no worker registers a handler for the
`addon:` prefix until M3), which is a route that looks like it works and does not — so it is
omitted rather than built to look complete.

`POST /snapshots/{snapshot_id}/normalize` **is** implemented, per this batch's explicit brief,
even though the job it creates shares the identical eventual-dispatch dependency: it stays
`PENDING` until M3 registers an `addon:*` handler. This is a deliberate scope choice from the
batch brief (which named "normalize-run creation" among the routes to reproduce while naming
only collect/import as needing the addon host) rather than a technical distinction this
implementer can independently justify — flagged here explicitly so M3/M7 can weigh whether the
inconsistency should be resolved by also deferring normalize, or by building collect/import
now that the pattern exists. `apps/domain/api.py`'s own module docstring and
`start_normalization`'s docstring both name the gap at the point a reader would hit it.

`HANDLER_PREFIX = "addon:"` is mirrored (not imported — `addon_host` does not exist) as a
module-level constant in `apps/domain/api.py`. **M3 must keep it in sync with its own**
`addon_host.registration.HANDLER_PREFIX`, or supersede this module outright.

## (e) The not-adapted P0 migration-replay test

`experiments/integrated-p0/tests/test_snapshot_survives_migration.py` was **not**
copy-adapted (batch 2b). It depends on two things P1 deliberately does not have: a per-test
`CREATE DATABASE ... TEMPLATE`-cloned isolation model (DP-032 replaces this with one shared
`cosmai_test` database and row-level reset), and two separate migration directories staged
independently so a snapshot could be sealed *before* one specific migration file was applied
(this batch consolidated all of `0002`–`0005` into one `0002_domain.sql`, so there is no
later domain migration to withhold and apply after the fact). Reproducing its exact mechanism
would mean building a template-clone fixture DP-032 deliberately declined.

DP-029 D1 (materialization) — the property that file's `TestASealedSnapshotSurvivesRawStoreEvolution`
class measured — is preserved verbatim in `apps/domain/store.py`'s implementation (`seal_snapshot`
copies member bytes into `snapshot_item` at seal time; nothing reads back from `raw_item`) and is
exercised by the ordinary snapshot tests in `test_domain_store.py`/`test_normalized_results.py`:
read-back-in-fixed-order, tamper detection via recomputed digests, and manifest-digest stability
across reseals. What is **not** re-run here is the specific purge/later-collection/collation-migration
timeline P0 measured against a live schema evolution. This is recorded as a gap for M7 to weigh,
not resolved by this batch.

**`[등록, 2026-08-21, m7-fixwave, M-R15]`** M7 never weighed this gap — no M6-RECORD,
M7-DEMO-RECORD, or closure review before this fix wave mentions it. Weighed now: the
gap is not closable by a later milestone's *testing*, because this batch's own
migration consolidation removed the structural precondition P0's scenario needed — "no
later domain migration to withhold and apply after the fact" (above) is still true of
the merged M2–M7 tree; `apps/platform_core/db/migrations/` holds one domain migration,
not a sequence a test could apply partway through. Closing this gap for real would mean
either reintroducing a multi-step domain migration sequence for no reason but testability,
or accepting that DP-029 D1's materialization property is exercised at the ordinary-case
level this record already names (`test_domain_store.py`/`test_normalized_results.py`)
and not against a live schema-evolution timeline. This record's disposition, made
explicit rather than left implicit: the gap is registered as permanently out of scope
under the current migration shape, not pending on a future milestone.

## (f) Files touched, by batch

- **2a**: `apps/db/provision.md` (append), `apps/tests/conftest.py`,
  `apps/platform_core/db/migrations/0002_domain.sql` (new), `apps/tests/test_migrate.py`.
- **2b**: `apps/domain/__init__.py` (new), `apps/domain/store.py` (new),
  `apps/tests/conftest.py`, `apps/tests/test_domain_store.py` (new),
  `apps/tests/test_normalized_results.py` (new).
- **2c**: `apps/domain/outbound.py` (new), `apps/domain/transport.py` (new),
  `apps/tests/test_outbound_policy.py` (new), `apps/tests/test_outbound_transport.py` (new),
  `apps/tests/test_credentials.py` (new), `apps/platform_core/obs/redaction.py`,
  `apps/tests/test_obs.py`.
- **2d**: `apps/domain/store.py` (`list_items`/`LIST_ITEMS`), `apps/domain/api.py` (new),
  `apps/platform_core/secrets.py` (`write_credential`), `apps/tests/test_domain_api.py` (new),
  `apps/tests/test_secrets.py`, `apps/tests/test_outbound_transport.py` (permitted-path set
  update for `apps/domain/api.py`'s own `allow_loopback` mention), `docs/p1/M2-RECORD.md`
  (this file).
