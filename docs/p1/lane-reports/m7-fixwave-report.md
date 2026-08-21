# M7 fix-wave report — repairs against REVIEW-M2-M7.md

- Branch: `p1/m7-closure`.
- Reviewer document answered: `docs/agent-workflow/reviews/REVIEW-M2-M7.md` (verdict FAIL, 12
  blocking, ~40 minor).
- Fix-loop law honored: every count, quote, and command below was re-derived from the
  post-edit tree by actually running it, not transcribed from the review.
- Commits (this branch, in order): `07dafb6` (defects), `de7cc53` (dashboard), `34fb260`
  (records). This file and the copy of the sixteen lane reports into `docs/p1/lane-reports/`
  land in a fourth commit alongside it (evidence-promotion).

## Gates, re-derived at HEAD

| Gate | Command | Result |
|---|---|---|
| Root guard | `.venv/bin/python -m pytest tests/environment -q` | **87 passed** |
| apps full suite | `COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime ../scripts/with-secret-source.sh uv run python -m pytest -q` | **1124 passed, 1 skipped** |
| mypy | `cd apps && uv run mypy --strict .` | clean, 104 source files |
| ruff (apps) | `cd apps && uv run ruff check .` | clean |
| ruff (root) | `.venv/bin/ruff check .` | 2 pre-existing `E501` in `experiments/integrated-p0/tests/test_outbound_policy.py`, last touched 2026-08-20 (before this fix wave), zero diff against `experiments/` from this branch — P0 tree is read-only per AGENTS.md, not fixed |
| check-addons.sh | `apps/scripts/check-addons.sh` | all 8 add-ons `ok`, exit 0 |
| dashboard build | `cd apps/dashboard && npm run build` | `tsc -b && vite build` clean, 964 modules |
| dashboard tests | `npx vitest run` | **47 passed** |

`dist/` deleted after each build (housekeeping item, confirmed gitignored, untracked before
and after).

## Per-finding account

### Blocking

- **B1 — fixed.** All four handlers (`normalizer.naver.blog`, `normalizer.naver.trend`,
  `normalizer.obf.product`, `importer.local.jsonl`) now catch `(ValueError, RecursionError)`
  instead of `(json.JSONDecodeError, UnicodeDecodeError)` — `ValueError` already covers both
  original classes since `JSONDecodeError`/`UnicodeDecodeError` are `ValueError` subclasses,
  plus the two the review's payloads exercise. Fixture tests added to each of the four test
  files using the review's exact payloads (`{"id":"b","v":` + `9`*5000 + `}`;
  `[`*100000+`]`*100000). All 8 new tests pass; full apps suite unaffected (1124 passed).
- **B2 — fixed.** `platform_core.api.app.create_app` now registers an
  `@app.exception_handler(RequestValidationError)` that strips `input` from every error dict
  FastAPI's default handler would otherwise include, registered platform-wide so every route
  (present and future) inherits it. Test added to `test_domain_api.py` using the review's
  exact probe (a bare JSON string `"MY-SECRET-42"` POSTed to the credentials route) — 422,
  secret absent from the response body, `input` absent from every error entry.
- **B3 — fixed.** `_raw_jsonl_line` now re-serializes a payload that parses as JSON via
  `json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))` instead of splicing the raw
  bytes in verbatim. Test added with the review's own pretty-printed payload
  (`{\n  "title": "hello"\n}`); the whole export parses line-by-line, one line per item.
- **B4 — fixed (record only, no code change, per ruling).** M4-RECORD's "refused at `resolve`"
  claim corrected to what the code does — `resolve` performs no address check, only a
  configuration check on `allow_loopback`; depth is 1, at the transport
  (`_refuse_http_off_loopback`), quoted verbatim from `transport.py`'s own docstring.
- **B5 — fixed.** Added `test_an_encoded_separator_inside_the_approved_prefix_is_still_refused`
  (payload `/v1/items/x%2f..%2f..%2fadmin`, inside the approved prefix by ordinary
  `str.split("/")`). Verified RED/GREEN by hand: with `_ENCODED_SLASH` detection temporarily
  removed from `comparable_segments`, the payload is wrongly **accepted**
  (`PreparedRequest`, not `Refusal`) — 1 failed, 1 passed. Restored: 111 passed (whole file).
- **B6 — fixed.** Ported P0's `TestARefusalCannotBeSwallowed` for the collector path
  (`SWALLOWING` add-on, positive control on a granted endpoint) into
  `apps/tests/test_addon_capabilities.py`, and added a new pair for the importer path P0
  never had (`SWALLOWING_IMPORT`, `run_import` harness, positive control on an approved
  input) — `capabilities.py`'s importer-side `_check_no_refusal_was_swallowed` (`:1139`,
  called `:949`) had no test anywhere before this. Fixed the mistitled "Refusal-swallowing"
  banner above `TestANonSuccessStatusCannotBeIgnored` (that class is invariant 5, not
  invariant 4) and corrected M3-RECORD's matching claim. 27 tests pass in the file.
- **B7 — fixed (record only).** M4-RECORD's naver.blog counts corrected: re-derived at
  `e87a00e` (37 collector + 25 normalizer = 62, not 68; lane suite 862, not 860) and again at
  this fix wave's own tree (37 + 27 = 64, since B1 added two tests to the normalizer file).
- **B8 — fixed, per controller ruling.** All 16 lane/batch reports under
  `.superpowers/sdd/2026-08-21-m2-m7-batch/` (every `*.md` except `progress.md`) scanned for
  secret shapes (`[0-9a-f]{40,}`, `PASSWORD`, `ytd_`, `COSMA_[A-Z_]+=` key-value pairs) —
  zero hits requiring redaction (the one `ytd_...` mention is already truncated with an
  ellipsis and the report states it was never printed). Copied (not moved) into
  `docs/p1/lane-reports/`. M4-RECORD's evidence pointers updated to the committed paths.
- **B9 — fixed (record only), re-derived from the retained logs, not the review.**
  `/tmp/claude-1000/m7-demo/scheduler.log` and `worker.log` were still present on disk;
  `grep -c scheduler.job_created scheduler.log` → 3 (job_ids `3f610ae2…`, `81960e7b…`,
  `7d66a053…`); three `addon.collect.run_complete` completions, `items_emitted` 900, 900, 892
  in firing order. `grep -n FAILED worker.log` for `collector.tubedepth.rest` → 6 distinct
  job ids (`989b2034…` 20→21, `caa3b54d…` 300→301, `ca905843…` 2000→2001, `f8720ced…`
  500→501 — the one missing from the original narration, `257a1ca1…` the three-attempt
  transient exhaustion, `10a4f4f6…` 60→61). §4 and §5 of M7-DEMO-RECORD corrected in place
  with dated notes; §10's own tallies (jobs_created=3, 2692, 8 SUCCEEDED/6 FAILED) were
  already correct and are now actually explained by the corrected narration.
- **B10 — fixed (record only).** M7-DEMO-RECORD's range-filter row downgraded from PASS to
  vacuous: the probe used `from_=` where `apps/domain/api.py`'s `_FROM_QUERY` binds `from`,
  so the parameter never reached the server and the 200-of-200 result is what "no filter"
  also produces. The code and its real test (`TestRawExportScopeFilters`) are fine; only the
  demo record's own probe was wrong.
- **B11 — fixed (record only).** Added the sentence naming naver.blog's live collect as
  ~20x the intended quota against a live third party under a real credential, to
  M7-DEMO-RECORD's own §5 paragraph about the deviation.
- **B12 — fixed.** `startCollection`/`startImport` added to `apps/dashboard/src/api/client.ts`
  (+ `JobEnqueued` type, `useStartCollectionMutation`/`useStartImportMutation` hooks).
  `CollectorDomainScreen.tsx`'s "Collect now" button now fires the real
  `POST /sources/{id}/collect` and renders the 201/refusal result instead of being
  permanently disabled with a note claiming the route did not exist. `domain/api.py`'s stale
  M3-pending paragraph and `HANDLER_PREFIX` comment (M-P4) corrected to describe the route's
  actual home in `addon_host/api.py`. vitest added: fires the POST, asserts method, renders
  the 201 result (job id, source id). No dedicated screen exists for importer sources in this
  tree (only "collectors" is routed) — `startImport`/`useStartImportMutation` exist and are
  usable, but nothing in the UI currently calls `startImport`; inventing a new
  ImporterDomainScreen was judged out of this fix wave's scope (B12 was about the existing
  screen's false claim, not about building new UI).

### Minor — Security-adjacent

- **M-S1 — fixed.** `write_credential`'s temp file is now created via `os.open(tmp,
  O_WRONLY|O_CREAT|O_EXCL, mode)` — created at 0600 directly, never at the process umask and
  chmod'ed after. Test added asserting the exact `mode` argument `os.open` was called with
  for the temp path (spy on the real `os.open`, not a replacement, so the write still
  happens).
- **M-S2 — fixed.** `test_the_tubedepth_header_is_protected` added to `test_credentials.py`,
  asserting `"x-api-key" in PROTECTED_HEADERS` — the same convention the existing NAVER-header
  test already establishes.
- **M-S3 — registered, per ruling.** Note appended to M2-RECORD: the credential route's own
  `value` field is not a `REDACTED_KEYS` entry; the route is write-only by the code's own
  discipline (never logged, never returned), now also backed by B2's platform-wide handler,
  but the redaction contract itself still does not know the field name is sensitive. No code
  change.
- **M-S4 — fixed.** `_csv_cell` helper added to `domain/export.py`, prefixing a literal `'`
  on any string cell starting with `=`, `+`, `-`, or `@`, applied to every untrusted string
  field in both `_raw_csv_rows` and `_result_csv_rows`. Parametrized tests added on both
  export CSVs over all four prefix characters.
- **M-S5 — fixed.** `data-testid="payload-preview"` added to the table cell;
  `DataBrowserScreen.test.tsx` extended with the same three anti-markup assertions
  (`textContent` equality, no `<script>`/`<b>` element, zero DOM children) the detail-pane
  test already made — the code needed no change, since JSX interpolation already escapes it;
  only the test coverage was missing.
- **M-S6 — registered, per ruling.** Note appended to M6-RECORD's deviations ledger: normalized
  bodies are key-redacted on every egress path while `body_sha256` beside them digests the
  unredacted body, so an exported digest cannot verify against the exported body. Not a
  security defect; a verification-utility gap. No code change.

### Minor — Controls described as controls that are conventions

- **M-C1 — fixed.** `apps/tests/test_check_addons_script.py` added: asserts the script exists
  and is executable (no skip-if-missing), then runs it via `subprocess` over the real
  `apps/addons/` tree and asserts every installed add-on is named `ok` in its output.
- **M-C2 — fixed.** `AGENTS.md:15` and `M4-RECORD:57`'s citation of
  `test_addon_layer_direction.py` corrected to `tests/environment/test_p1_isolation.py`.
- **M-C3 — fixed.** `scheduler` added to `LOCAL_PACKAGES` and `ALLOWED_IMPORTS` (allowed:
  `platform_core` only, matching what `apps/scheduler/__main__.py` actually imports) in
  `tests/environment/test_p1_isolation.py`. The guard-on-the-guard
  (`test_the_layer_guard_reads_the_packages_it_claims_to_read`) now iterates every package in
  `ALLOWED_IMPORTS` instead of asserting 3 of 6 by name. The stale "`apps/addons/` holds
  nothing yet (M4)" comment corrected to name the 8 real add-ons and this fix wave.
- **M-C4 — fixed, real verdict recorded.** `test_the_arithmetic_was_found_in_more_than_one_add_on`
  restructured: an unconditional `assert len(DAY_AFTER) >= 1` (would catch a broken scan path)
  now precedes the skip, which is reachable and no longer masks a would-be failure. Re-derived
  on the merged 8-add-on tree: `DAY_AFTER` finds exactly one implementation
  (`collector.naver.datalab`) — P0's two DataLab collectors were consolidated into one add-on
  by design (M4's own naver-datalab lane), so the "second copy" this guard predicted never
  arrives structurally, not because of an incomplete merge. Matches M4-RECORD's own
  already-honest measurement of this same fact.
- **M-C5 — fixed.** `scheduler/store.py`'s and `scheduler/__main__.py`'s multi-process-safety
  docstring paragraphs marked `[가설]` with a pointer to M-C5 and the fact that every scheduler
  test to date is a sequential `--once` run — the mechanism (Postgres `for update of s`) is
  correct by construction, but was stated as measured when it has never been tested against
  two concurrent processes.

### Minor — Present tense for things not built

- **M-P1 — fixed, per ruling.** `_resolved_source_row` (shared by collector, importer, and
  normalizer dispatch) now refuses with `ConfigurationInvalidError` when a source's stored
  `config_schema_version` does not match its add-on's manifest, naming both versions. Three
  tests added (older, newer, matching-positive-control). The naver.blog README's and the
  add-on template's "marked `NEEDS_MIGRATION`" sentence corrected to describe the actual
  `CONFIGURATION_INVALID` mechanism.
- **M-P2 — fixed.** HealthScreen's scheduler note corrected: the process exists and runs (M6);
  no route reports its own status.
- **M-P3 — fixed.** The add-on template README's "conformance suite... does not exist yet"
  corrected to describe `addon_kit.conformance` and its real CLI invocation.
- **M-P4 — fixed.** `domain/api.py`'s stale "M3 must keep this string in sync" /
  "`addon_host` does not exist in this tree yet" paragraphs corrected to describe the real,
  merged M3 state — this is the exact text B12's dashboard note had quoted.

### Minor — Record/evidence defects

- **M-R1 — fixed**, combined with B7's edit (M4-RECORD's DataLab breakdown corrected to
  35/33/6, with the misattributed "9" traced to the importer-obf lane's own files).
- **M-R2 — fixed.** M4-RECORD's "1003 passed, 2 pre-existing failures" note now says those two
  failures were fixed by the M7 sweep's own worktree-scan narrowing —
  `TestLoopbackIsOnlyReachableByFlag` re-derived at 3 passed, 0 failed.
- **M-R3 — fixed.** `test_outbound_transport.py`'s docstring corrected: the pre-fix cases did
  not "pass vacuously" — the positive-control assertion (`assert Path(...) in found`) failed
  loudly, which is exactly what a positive control is for. Only the *other* assertion (a
  subset check) would have passed vacuously on its own.
- **M-R4 — fixed**, combined with M-R5's edit. `COSMA_DB_NAME=cosmai_test_5` corrected to name
  `COSMA_TEST_DB`, the variable `apps/tests/conftest.py`'s `TEST_DATABASE` actually reads.
- **M-R5 — fixed.** "every timestamp this add-on constructs" corrected — `[측정]`
  `collector.tubedepth.rest/handler.py` imports neither `datetime` nor `time` and constructs
  no timestamp; it round-trips the provider's own values verbatim.
- **M-R6 — registered.** A note added to the naver.blog LIVE-smoke bullet naming the missing
  capture time/API version/sample hash/usage basis AGENTS.md §Evidence requires — not
  fabricated after the fact, since the values were never captured.
- **M-R7 — fixed.** A bullet added to M4-RECORD's importer/obf-product lane summary naming the
  sentinel/unreachable-branch disclosure `test_normalizer_obf_product.py`'s own docstrings
  already carry, which this record never mentioned.
- **M-R8 — fixed.** M5-RECORD's "the same 37 from batch 5d" corrected — 5d reported 34, not
  37, and the two sets differ by 9 added / 6 removed (net +3), not "the same."
- **M-R9 — fixed (four sub-items).** `test_apps_never_imports_experiments` citation corrected
  to name it as a function inside `test_p1_isolation.py`. The `vite.config.ts`
  loopback-rule credit corrected (P1's `vite.config.ts` has no such rule; only P0's does) —
  and a real test for `client.ts`'s own `apiBase()` refusal was added, since none existed.
  `GET/POST /export/results` corrected to `GET` only. The 549 kB vs. 548 kB bundle-size
  contradiction resolved to 548 (matching the earlier, independently re-derivable figure).
- **M-R10 — fixed**, combined with B9/B10's edits: "200 normalized blog results" corrected to
  197 (matching §6/§8's own figure); "10 columns" corrected to 11 (`RESULT_HEADER`'s real
  length).
- **M-R11 — fixed**, same edit as B11.
- **M-R12 — fixed.** Both stale `5433` occurrences (`run_measurements.sh`,
  `test_db_connection.py`) corrected to `5434`. The sweep commit's own invented scoping
  justification ("the two documents the addendum named") lives in an immutable git commit
  message and cannot be corrected retroactively; not repeated in any doc this fix wave
  touched.
- **M-R13 — fixed.** DP-032's present-tense `tubedepth-postgres`/`:5433` server description
  given a dated correction note naming the live replacement (`shared-postgres`, `:5434`,
  confirmed via `docker ps` this session) and the fact `project-state.md` still pointed at
  the stale description.
- **M-R14 — fixed.** See `docs/project-state.md`'s new "P1 M1–M7 status, 2026-08-21"
  subsection, described above.
- **M-R15 — fixed (both halves).** M3-RECORD's handoff (invariant 4/refusal-swallowing) closed
  by B6's implementation and cross-referenced. M2-RECORD's handoff (the purge/collation-
  migration timeline) explicitly weighed: closing it would require reintroducing a
  multi-step migration sequence this batch's own consolidation removed, so it is registered
  as permanently out of scope under the current migration shape rather than left pending.

### Minor — Contract/consistency

- **M-X1 — registered, per ruling.** A new row added to M6-RECORD's deviations ledger naming
  the flattened-CSV-vs-metadata-plus-blob shape as an explicit deviation from DP-033 D3's
  literal text. No code change.
- **M-X2 — fixed, per ruling.** `platform_core.config`'s `COSMA_API_PORT` default and the
  dashboard's `DEFAULT_API_BASE` both changed from 8000 to 8100 (avoiding the collision with
  trend-radar's live dashboard on 8000, DP-031 D3). `test_config.py` and
  `CredentialForm.test.tsx` updated to match; registered in M7-DEMO-RECORD.
- **M-X3 — fixed.** `client.ts`'s `envSafe` now collapses consecutive separators and strips
  leading/trailing underscores, matching `domain.api.credential_ref_for` exactly. A shared
  vector table (including `"a..b"` and `".lead"`) asserted identically in
  `apps/tests/test_credential_ref_derivation_agrees.py` (pytest) and
  `apps/dashboard/src/api/__tests__/client.test.ts` (vitest).
- **M-X4 — fixed.** `apps/tests/test_mirrored_constants_agree.py` added: asserts every
  `HANDLER_PREFIX` copy (3) and every `SOURCE_ID_FIELD` copy (4) agrees, plus a control that
  the two constant families are not accidentally the same value.
- **M-X5 — fixed, per ruling (append-only).** A "Post-decision corrections" section appended
  to DP-033: H5's falsification condition named the wrong mechanism (`effect_key`, unrelated
  to the scheduler's real `non_terminal_job_exists` lock-based suppression), and the
  OQ-008 answer M6-RECORD already held (a `SUCCEEDED` job does not suppress the next
  scheduled pass, so the re-execution case does arise) is now connected to the question that
  asked for it.
- **M-X6 — fixed, per ruling (append-only).** A "Post-decision corrections" section appended
  to DP-034: D1's stale "whether it is currently set" sentence corrected — M5 already removed
  that display and replaced it with session-local "written this session" state; only the
  packet's own text was left saying the earlier, incorrect thing.
- **M-X7 — fixed.** The tubedepth README's phantom `tests/`-under-the-add-on layout corrected
  to the real paths (`apps/tests/test_addon_collector_tubedepth.py`,
  `apps/tests/fixtures/collector.tubedepth.rest/`). The dashboard README replaced with 14
  true lines describing the real screens, API base, and scripts, in place of the unmodified
  Vite scaffold.
- **M-X8 — fixed.** `pytest_collection_modifyitems` in `apps/tests/conftest.py` now computes
  whether any selected test's fixture closure touches the database
  (`job_connection`/`_migrations_applied`) and stores the result; `_reset_schema` (session
  autouse) skips connecting entirely when it does not. Registered with
  `@pytest.hookimpl(trylast=True)` so it runs after `-k`/`--deselect` filtering, not before
  (an earlier version of this fix computed the flag against the pre-filter item list and was
  wrong for a deselected class — caught and fixed during this same fix wave, not left in).
  `normalizer.obf.product`'s blanket module-level `pytest.mark.usefixtures("_migrations_applied")`
  removed — only `TestCoexistenceOverOneLineage` needed it, and it already gets it
  transitively through `job_connection`. Proven: both `test_outbound_policy.py` (114 tests)
  and `test_normalizer_obf_product.py` minus the one DB-backed class (51 tests) run to
  completion with `COSMA_DB_PORT` pointed at port `1` (nothing listens there), no wrapper,
  no live server.

## What was NOT fully repaired

Nothing on the review's B/M-# list was left unaddressed. Two items were resolved as
registrations rather than code changes, per the controller's own ruling (M-S3, M-S6, M-X1,
M-X5, M-X6) — these are documented above as intentionally record-only. B12's importer-side UI
wiring is client/hook-complete but has no screen to attach to in this tree (see B12's entry
above) — building a new ImporterDomainScreen was judged out of this fix wave's scope.

## Housekeeping

`apps/dashboard/dist/` was present at the start of this fix wave (build output, gitignored,
untracked) and was deleted; it reappeared twice more from this fix wave's own build runs and
was deleted each time.
