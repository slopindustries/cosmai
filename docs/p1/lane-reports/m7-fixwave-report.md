# M7 fix-wave report — repairs against REVIEW-M2-M7.md

- Branch: `p1/m7-closure`.
- Reviewer document answered: `docs/agent-workflow/reviews/REVIEW-M2-M7.md` (verdict FAIL, 12
  blocking, ~40 minor).
- Fix-loop law honored: every count, quote, and command below was re-derived from the
  post-edit tree by actually running it, not transcribed from the review.
- Commits (this branch, in order): `07dafb6` (defects), `de7cc53` (dashboard), `34fb260`
  (records), `29b8f84` (evidence-promotion — this file plus the 16 copied lane reports;
  `git ls-files docs/p1/lane-reports | wc -l` → **17**, this file itself the 17th).
  Round 2 lands in one further commit, appended below.

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
  input) — `capabilities.py`'s importer-side `_check_no_refusal_was_swallowed` (`:1159`,
  called `:969` — both re-derived post-M-P1's insertion into the same file; the pre-M-P1
  line numbers were `:1139`/`:949`) had no test anywhere before this. Fixed the mistitled "Refusal-swallowing"
  banner above `TestANonSuccessStatusCannotBeIgnored` (that class is invariant 5, not
  invariant 4) and corrected M3-RECORD's matching claim. 27 tests pass in the file.
- **B7 — fixed (record only), corrected again in round 2 (N3).** M4-RECORD's "41
  collector + 27 normalizer (68 addon-specific)" was wrong component-by-component —
  re-derived at `e87a00e`: 37 collector + 25 normalizer = 62, not 68, matching the
  lane's own report's "862 collected" figure. **"860 passed, 2 failed" was already
  correct and never needed correcting** (862 = 860 + 2) — round 1's fix wrongly called
  it self-contradictory by comparing 68 against 860 while dropping the "2 failed" the
  original sentence also stated; round 2 rewrote the correction to say exactly that.
  Re-derived again at this fix wave's own post-edit tree: 37 + 27 = 64 addon-specific,
  since B1 added two tests to the normalizer file.
- **B8 — fixed, per controller ruling.** The 16 lane/batch reports under
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

## Round 2 — repairs against the re-review of round 1's own diff

Re-verification confirmed B1–B12 by execution. Round 1's own fix diff introduced seven new
findings (N1–N8, one item split into two sub-findings by the re-reviewer). All fixed in one
commit. Every number below was re-derived from the tree after this round's own last edit, not
carried over from round 1's report or the re-review's own numbers.

- **N1 (blocking) — fixed.** `apps/domain/export.py`'s `_raw_jsonl_line` (the function B3
  edited) carried the exact guard-tuple defect class B1 fixed elsewhere:
  `except (json.JSONDecodeError, UnicodeDecodeError)` misses a bare `ValueError` (the
  4300+-digit-integer payload) and `RecursionError` (the deeply-nested payload), so
  `/export/raw?format=jsonl` would raise mid-stream instead of taking the escaped-string
  fallback. Widened to `(ValueError, RecursionError, UnicodeDecodeError)`. Two pure-function
  tests added directly against `_raw_jsonl_line` (no fixture, no database) with the review's
  own two payloads — each now emits exactly one parseable JSONL line via the fallback.
  `[측정]` `tests/test_export.py -k SurvivesSpecValidJson`: 2 passed, both with
  `COSMA_DB_PORT` pointed at a dead port (0.15s, no connection attempted) and against the
  live database (part of the file's own 23-passed run, up from 21 in round 1).
- **N2 (blocking) — fixed, two parts.** `_DB_TOUCHING_FIXTURES` in `apps/tests/conftest.py`
  checked only `job_connection`/`_migrations_applied`; `migrator_connection` and
  `runtime_connection` also call `connect()` independently and were missing, so a test
  requesting either alone (`test_migrate.py`, `test_db_connection.py`) would have been
  wrongly read as DB-free. Both added to the set. The comment's "pinning" claim was also
  false — the test it named checks only that *this one file* (`test_outbound_policy.py`)
  is DB-free, not that the detection set is complete over `conftest.py`'s real fixture
  graph. Fixed by renaming that test to say only what it checks
  (`test_this_file_itself_requests_no_db_touching_fixture`) and adding a second test that
  actually introspects `conftest.py`'s AST — every `@pytest.fixture`-decorated function
  whose body calls `connect(...)` must be in `_DB_TOUCHING_FIXTURES`
  (`test_every_db_touching_conftest_fixture_is_in_the_detection_set`, with a positive
  control that the scan finds something at all). `test_migrate.py`'s "starts from empty"
  precondition, which used to silently hold or not depending on whatever schema state a
  prior session left behind when this file ran standalone, is now enforced automatically —
  every test in it already requests `migrator_connection`, now in the detection set, so
  `_reset_schema` runs before it regardless. `test_db_connection.py`'s own docstring claim
  ("a live server is still required to run pytest at all here") is now false and was
  corrected — none of its tests request a DB-touching fixture, so it now runs standalone
  with no connection at all. `[측정]`, all four re-derived against the post-edit tree: live
  run, `test_migrate.py` alone — 5 passed (schema genuinely reset). Dead-port run
  (`COSMA_DB_PORT=1`), `test_migrate.py` alone — 5 errors after ~130s
  (`psycopg`'s own connect timeout), `platform_core.errors.ConfigurationInvalidError:
  cannot reach the platform database` — a clear, terminating failure, not a silent pass and
  not an infinite hang. Dead-port run, `test_db_connection.py` alone — 6 passed in 0.01s, no
  connection. Dead-port run, `test_outbound_policy.py` — 115 passed (114 + the new
  introspection test).
- **N3 (blocking, record) — fixed.** Round 1's own "correction" to M4-RECORD's naver.blog
  test-count sentence was itself wrong: the original lane report
  (`docs/p1/lane-reports/m4-naver-blog-report.md:26`) genuinely says "**860 passed, 2
  failed**" — 862 collected = 860 + 2, internally consistent — and round 1 called this
  self-contradictory by comparing it against 68 while dropping the "2 failed" the original
  sentence also stated. Only "41 collector + 27 normalizer (68 addon-specific)" was ever
  wrong (real count 37 + 25 = 62). Rewritten to say exactly that, and to note the DataLab
  row at M4-RECORD's M-R1 correction was already handled the right way (total right,
  component breakdown wrong) and needed no further change for consistency — confirmed by
  re-reading it: it already says "872 passed, 2 failed" and needed no correction.
- **N4 (blocking, record) — fixed.** `docs/project-state.md`'s pointer to the fix-wave
  report cited the gitignored `.superpowers/sdd/...` path; repointed to the tracked
  `docs/p1/lane-reports/m7-fixwave-report.md`. `[측정]` `grep -rln '\.superpowers/sdd'
  docs/` → 5 files: `project-state.md` (fixed, above), `agent-workflow/reviews/REVIEW-M1.md`
  and `REVIEW-M2-M7.md` (immutable adversarial-review transcripts — both files' own header
  notes say they are transcribed verbatim from the reviewer, who cannot write files;
  editing their citations would misrepresent what was found at review time, so left
  untouched), `p1/M4-RECORD.md` (already dual-references the tracked
  `docs/p1/lane-reports/` path as primary, with the `.superpowers/sdd/` path only
  parenthetical provenance — "committed copy of ..." — not a broken pointer), and this
  file itself (describes the scan's source location, not a follow-this-link citation).
  One genuinely stale pointer found and fixed; four correctly left as-is.
- **N5 — fixed, re-verified last as instructed.** M-P1's insertion into
  `apps/addon_host/capabilities.py` shifted every line at or after it by exactly +20.
  `[측정]`, re-derived at the final post-round-2 tree: `_check_no_refusal_was_swallowed`
  (collector) at `:868` (was `:848`), called at `:397` (was `:377`); the importer copy at
  `:1159` (was `:1139`), called at `:969` (was `:949`); the "weaker than
  `_check_no_refusal_was_swallowed` beside it" docstring at `:807` (was `:787`). All five
  citations corrected in `apps/tests/test_addon_capabilities.py` (two sites),
  `docs/p1/M3-RECORD.md` (one site), and this report (one site, kept as a historical note
  naming both the old and new numbers rather than silently replaced). `grep`
  for the four old numbers across `apps/`, `docs/`, and `tests/` (excluding the immutable
  review transcripts) after this round's own edits: zero remaining stale hits.
- **N6 — fixed.** `TestAStaleConfigSchemaVersionIsRefused`'s docstring in
  `test_addon_capabilities.py` claimed, present tense, that the add-on READMEs "state" the
  `NEEDS_MIGRATION` sentence — true when M-P1 was written, false now that round 1's own
  README fix (same fix wave) replaced that sentence with the real `CONFIGURATION_INVALID`
  mechanism. Corrected to past tense and to name the real mechanism.
- **N7 — fixed.** `git ls-files docs/p1/lane-reports | wc -l` → **17** (16 lane/batch
  reports plus this report itself). The report's own "sixteen"/"All 16" wording was already
  correct for the lane-report count specifically, but ambiguous next to a reader running
  that exact command and seeing 17 — reworded to state both numbers and which is which.
  Also fixed the B7 bullet's summary, which still carried round 1's now-superseded (N3)
  explanation.
- **N8 — fixed.** The B2 handler's docstring (`platform_core/api/app.py`) claimed "only the
  raw value that was wrong is withheld," overclaiming: Pydantic v2's `ctx` field is not
  stripped by this handler and is not always empty of the input — `[측정]` a `uuid_parsing`
  error's `ctx["error"]` contains a fragment of the offending value (reproduced:
  `"invalid character: found `n` at 1"` for input `"not-a-uuid-at-all-XYZZY"`). This route's
  own failure class (`dict_type`) carries no `ctx` at all — `[측정]` reproduced with
  `pydantic.TypeAdapter(dict[str, Any]).validate_python("MY-SECRET-42")` → no `ctx` key —
  so the credentials route withholds completely, but the docstring no longer claims that of
  every route this platform-wide handler covers.

### Round-2 gates, re-derived at the final tree

| Gate | Command | Result |
|---|---|---|
| Root guard | `.venv/bin/python -m pytest tests/environment -q` | **87 passed** (unchanged) |
| apps full suite | `COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime ../scripts/with-secret-source.sh uv run python -m pytest -q` | **1127 passed, 1 skipped** (up from 1124: N1's 2 tests + N2's 1 introspection test) |
| mypy | `cd apps && uv run mypy --strict .` | clean, 104 source files |
| ruff | `cd apps && uv run ruff check .` | clean |
| DB-free: outbound | dead port (`COSMA_DB_PORT=1`), `.venv/bin/python3 -m pytest tests/test_outbound_policy.py -q` | **115 passed** |
| DB-free: obf | dead port, `-k` excluding `TestCoexistenceOverOneLineage` | **51 passed** |
| DB-free: new export tests | dead port, `-k SurvivesSpecValidJson` | **2 passed** |
| dashboard vitest | `npx vitest run` (unchanged this round — no dashboard file touched) | **47 passed** |

Not fully repaired: nothing on N1–N8 was left unaddressed.
