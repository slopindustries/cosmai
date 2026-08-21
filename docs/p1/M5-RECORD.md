# M5-RECORD — the dashboard, batch by batch

- Milestone: M5 (`apps/dashboard/`, Lane B).
- Branch: `p1/m5-dashboard`.
- Consumed by: M7's full adversarial review, per the batch plan
  (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §M5).

This record grows one section per batch. All six DP-033 D1 screens now have a complete UI, and as
of batch 5-final every wired call is real and live-verified against M2's domain API and M6's
scheduler/export routes (merged from `dev`) — the only remaining gap is M3's `addon:*` worker,
which is out of Lane B's scope entirely (collect/import stay disabled with a note, per the batch
5-final dispatch).

## Batch 5a — scaffold, jobs monitor, health/metrics

- Date: 2026-08-21.

`[결정]` Scope for this batch, per the dispatch brief: a Vite + React + TypeScript scaffold with
MUI v6, React Router v7, and TanStack Query v5 (DP-033 D4); a routing skeleton naming all six
DP-033 D1 screens (collector-domain, data browser, downloads, normalization management, jobs
monitoring, health/metrics); two of those six fully implemented — jobs monitoring and
health/metrics — against the M1 operator API (`apps/platform_core/api/app.py`); the other four as
labeled placeholder pages that name what lands in 5c/5d and why they are not built yet.

`[확인 사실]` This is a new build against `apps/platform_core/api/app.py`'s response shapes, not a
copy-adapt of `experiments/integrated-p0/dashboard/`. The P0-A dashboard (three screens, no
router, no query cache, no component library — DP-006 D6) was read as a reference for API
consumption shapes (`src/api.ts`) and for what the job screens showed (`src/view.tsx`), per the
task brief; nothing from that tree is imported, matching AGENTS.md's "P0 code must not become a
runtime or package dependency of P1" and `test_apps_never_imports_experiments`
(`[정정, 2026-08-21, m7-fixwave, M-R9]` a function inside
`tests/environment/test_p1_isolation.py`, not its own file — that guard is Python-only —
`.py` files under `apps/` — and does not scan TypeScript, but no
TypeScript import path names `experiments` either).

### What was built

- `apps/dashboard/src/api/types.ts`: TypeScript types for every M1 API response shape (`Job`,
  `JobPage`, `Attempt`, `AttemptPage`, `RetryOutcome`, `HealthResponse`, `MetricsResponse`),
  derived by reading `job_view`, `attempt_view`, `health`, `read_metrics` in `app.py`, plus
  `MetricsReading`/`DurationReading` in `apps/platform_core/obs/metrics.py` and
  `PlatformError.operator_view()` in `apps/platform_core/errors.py` for the unhealthy-health shape.
- `apps/dashboard/src/api/client.ts`: typed `fetch` wrappers (`listJobs`, `readJob`,
  `readAttempts`, `requestRetry`, `readHealth`, `readMetrics`). `apiBase()` defaults to
  `http://127.0.0.1:8000` and refuses a `VITE_API_BASE` naming a non-loopback host, carrying
  forward the loopback-only rule `experiments/integrated-p0/dashboard/src/api.ts` applies, for
  the same SEC-002 reason. `[정정, 2026-08-21, m7-fixwave, M-R9]` Not "and `vite.config.ts`
  both apply" — `[측정]` `apps/dashboard/vite.config.ts` in this tree has no loopback check
  at all (only `react()`/`vitest` setup); that rule exists only in P0's
  `experiments/integrated-p0/dashboard/vite.config.ts`, never carried into P1's. The real
  check this tree has, `apiBase()` in `client.ts:37-48`, had no test asserting it refuses a
  non-loopback `VITE_API_BASE` before this fix wave's B12/M-X2 work touched this file; still
  none exists dedicated to that refusal specifically.
- `apps/dashboard/src/api/queries.ts`: TanStack Query hooks over the client
  (`useJobsQuery`, `useJobQuery`, `useAttemptsQuery`, `useRetryMutation`, `useHealthQuery`,
  `useMetricsQuery`). The retry mutation invalidates the job, its attempts, and every jobs-list
  page on success.
- `apps/dashboard/src/routes/AppLayout.tsx`: an MUI `AppBar`/`Tabs` shell over an `<Outlet />`,
  naming the six DP-033 D1 screens in the order the decision lists them.
- `apps/dashboard/src/App.tsx`: `QueryClientProvider` + MUI `ThemeProvider` + `BrowserRouter`
  wiring all six routes; `/` and unmatched paths redirect to `/jobs`.
- `apps/dashboard/src/screens/JobsListScreen.tsx` (jobs monitor, list half): state filter chips
  (`any` + the four `jobs.state` values), a `limit` selector (25/50/100/200), `offset`-based
  previous/next pagination, and a table that navigates to `/jobs/:jobId` on row click.
- `apps/dashboard/src/screens/JobDetailScreen.tsx` (jobs monitor, detail half): job fields
  (handler, terminal reason, correlation id, timestamps, attempt budget), the payload panel, a
  retry button wired to `POST /jobs/{id}/retry` with its accepted/refused/missing outcome shown in
  full, and the attempts table with `error_class`, `error_class_retryable`, and the three-state
  protected-detail cell (`none` / `present, withheld` / rendered, only after
  `?debug=protected` is explicitly requested).
- `apps/dashboard/src/screens/HealthScreen.tsx`: `/health` status (reachable/unreachable, database
  name, `jobs_by_state`, or the unhealthy error class/summary), `/metrics` counters (claim
  conflicts, suppressed duplicate effects, abandoned attempts, rejected completions, per-state
  transitions), and a labeled scheduler placeholder box (`data-testid="scheduler-placeholder"`)
  noting the scheduler is M6, not this batch.
- `apps/dashboard/src/screens/{CollectorDomainScreen,DataBrowserScreen,DownloadScreen,
  NormalizeManagementScreen}.tsx`: placeholder pages (via a shared `PlaceholderScreen` component),
  each naming which later batch builds it and against which API.

### Deviation from the P0 reference, recorded rather than silently omitted

`[결정]` P0-A's SSR text renderers (`experiments/integrated-p0/dashboard/src/detail-text.tsx`,
`domain-text.tsx`, `screen-text.ts`, and their `npm run text`/`npm run domain` scripts) are
**deliberately not reproduced**. Those existed so a pytest assertion could search rendered screen
text without driving a browser (SEC-004 Action step 3). This batch replaces that seam with
`vitest` + `@testing-library/react` component tests instead — `screen.getByText`/`getByTestId`
assertions against a jsdom-rendered tree serve the same "screen text is checkable by a test on
every run" purpose the SSR renderers served, without a second Vite SSR build target. Per the
dispatch brief, this is the only B-scope omission from the P0 reference in this batch.

### Verification

`[측정]` `npm run build` (`tsc -b && vite build`), 2026-08-21: clean, no TypeScript errors.
Produces a single ~521 kB (160 kB gzipped) JS bundle; Vite's chunk-size-warning notes this is
larger than its default 500 kB threshold — expected for a first MUI+Router+Query bundle with no
code-splitting yet, not a build failure, and not addressed in this batch.

`[측정]` `npm test` (`vitest run`), 2026-08-21: **10 passed, 0 failed**, across
`JobsListScreen.test.tsx` (3 tests), `JobDetailScreen.test.tsx` (4 tests), `HealthScreen.test.tsx`
(3 tests). Hand-rolled `fetch` mocks (`vi.stubGlobal`), not msw — the API surface under test is a
handful of GET/POST paths and a hand mock keeps the request the test made (method, URL, query
string) directly inspectable from the mock's own call log.

Coverage against the brief's required assertions:
- retry button fires a `POST` to `/jobs/{id}/retry` — `JobDetailScreen.test.tsx` "fires a POST to
  the retry endpoint when the retry button is clicked".
- state filter changes the query — `JobsListScreen.test.tsx` "changing the state filter re-queries
  the API with the new state" and its inverse, "returning to 'any' drops the state filter".
- error-class rendering — `JobDetailScreen.test.tsx` "renders the attempt's error class".
- redacted protected field NOT displayed without the toggle — `JobDetailScreen.test.tsx`
  "withholds the protected error detail until the toggle is used" (asserts the protected token is
  absent from the DOM and that no request so far carried `debug=protected`), paired with "reveals
  the protected error detail only after the toggle is clicked" as the positive case.

`[측정]` `npm run lint` (`oxlint`), 2026-08-21: clean, no findings.

No Python gates were run for this batch (no Python files touched); `tests/environment` was not
re-run as part of this batch's own verification, per the dispatch brief's scope.

### Tooling versions actually installed

`[측정]` `node --version` → `v24.19.0`; `npm --version` → `11.17.0`. `package.json` pins
(installed, not merely requested): `vite@8.2.2`, `@vitejs/plugin-react@6`, `react@19.2.8`,
`react-router-dom@7.18.2`, `@tanstack/react-query@5.101.4`, `@mui/material@6.5.0`,
`@emotion/react@11.14.0`, `@emotion/styled@11.14.1`, `vitest@4.1.11` (not the `^2` first
attempted — vitest 2.x's bundled Vite typings conflict with the installed Vite 8, producing a
`tsc -b` type error in `vite.config.ts`; vitest 4.1.11 resolves it), `@testing-library/react@16`,
`@testing-library/jest-dom@6`, `@testing-library/user-event@14`, `jsdom@25`.

`npm install` needed `dangerouslyDisableSandbox` — the sandboxed filesystem refused writes to the
npm cache (`EROFS` under `/home/user1/.npm/_cacache`), matching the sandbox note in the M2–M7
batch plan §공통 제약 (uv cache writes are unsandboxed for the same reason; npm's cache is the
same class of write).

## Batch 5b/5c — credential entry, collector-domain screen, data browser (frontend halves, mocked)

- Date: 2026-08-21.

`[결정]` Controller ruling (batch dispatch, 2026-08-21): the backend half of the credential
endpoint moved to Lane A — the domain API (M2) owns every `/sources/...` route, including
`POST /sources/{id}/credentials`. This batch builds the **frontend halves** of 5b and 5c against
mocks; real wiring to Lane A's and M2's actual routes is batch 5d's job, after M2/M6 merge into
dev.

### What was built

- `apps/dashboard/src/api/types.ts`: added `CredentialWriteRequest`, `CredentialWriteRefusal`
  (mirrors `PlatformError.operator_view()`'s `error_class`/`error_summary` shape, the one
  platform-error convention already used by `HealthUnhealthy`), `RawItem`, `RawItemPage` — the
  latter two matching `GET /sources/{id}/raw/items?offset&limit` as fixed by
  `docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §신규 API (`item_key`, `seq`, `emitted_at`,
  `content_type`, `payload`).
- `apps/dashboard/src/api/client.ts`: added `credentialRefName(sourceId, purpose)` (derives
  `COSMA_SRC_<SOURCE_ID>_<PURPOSE>` per DP-034 D1/`secret-setup.md`, sanitizing both parts to
  `[A-Z0-9_]` — a source id like `naver-blog-main` becomes `NAVER_BLOG_MAIN`, since `-` is not a
  valid env-var-name character), `writeCredential(sourceId, purpose, value)` (real `POST`
  wrapper expecting `204`, parses an `error_class`/`error_summary` body into a
  `CredentialWriteFailure` on refusal, throws `ApiFailure` otherwise, and never returns the
  submitted value), and `readRawItems(sourceId, offset, limit)` (real `GET` wrapper for the raw
  item page). Both are genuine client functions written against the plan's fixed shapes, not
  stand-ins — only the server behind them doesn't exist yet.
- `apps/dashboard/src/api/queries.ts`: added `useRawItemsQuery` and
  `useCredentialWriteMutation` (no query-key invalidation on success — there is no read query for
  a credential's configured status to invalidate yet; that status is mocked from source detail
  until batch 5d).
- `apps/dashboard/src/screens/collector/CredentialForm.tsx`: the DP-034 D1 credential field.
  Two inputs (`purpose`, `value` — `value` is `type="password"`), one `Save` button. On submit:
  the `value` state is cleared **before** the request is even sent (a local `const` carries the
  actual value into the request; component state never holds it past that point, success or
  failure alike), then `POST`s via `useCredentialWriteMutation`. Shows the derived ref name
  (`credentialRefName`) and a "configured"/"not configured" `Chip`, computed against a
  `configuredPurposes` prop the parent screen currently mocks from "source detail". A refusal
  renders `error_class: error_summary` in an `Alert`; the submitted value is never part of that
  render.
- `apps/dashboard/src/screens/collector/ConfigSchemaForm.tsx`: renders a form from a
  manifest-shaped config schema (`{name, type: "string"|"integer", required, label, help?}` —
  the same shape as an add-on's `[[config.field]]` table, read from
  `experiments/integrated-p0/addons/collector.naver.blog/addon.toml` and
  `.../collector.naver.shoppinginsight/addon.toml`). Client-side validation blocks submission
  when a required field is empty or a declared-integer field isn't a whole number, shown as MUI
  `helperText`. The `<form>` carries `noValidate` — see Deviation/bug note below.
- `apps/dashboard/src/screens/CollectorDomainScreen.tsx`: rewritten from a placeholder into the
  full layout — a domain selector (mock `MOCK_SOURCES`, 2 entries), a status header (enabled,
  last success, next run), the config form, the credential section, a job-history table (reuses
  `useJobsQuery` from batch 5a, filtered client-side by `job.handler`), and a schedule
  placeholder box. The source list/detail is mock data, clearly scoped in the file's own header
  comment; the job-history read and the credential write are real.
- `apps/dashboard/src/screens/DataBrowserScreen.tsx`: rewritten from a placeholder into the full
  layout — a source selector (mock options), a paginated raw-item table
  (`useRawItemsQuery`, offset/limit, previous/next), and a payload detail pane. Row click selects
  an item; the detail pane and the table's preview column both render `item.payload` as a plain
  JSX text child.

### DP-033 D2 control: payload plain-text rendering

`[측정]` `src/screens/__tests__/DataBrowserScreen.test.tsx` "DP-033 D2: a payload containing
markup renders as literal plain text, never as parsed HTML" mocks a raw item whose payload is the
literal string `<script>alert(1)</script><b>x</b>`, selects it, and asserts:
`payloadElement.textContent === rawString` (nothing stripped or transformed), and
`payloadElement.querySelector("script")` / `.querySelector("b")` are both `null` with
`payloadElement.children.length === 0` (nothing was parsed into DOM elements — the tag characters
are inert text). The mechanism is React's own default escaping of JSX text children (`{selectedItem.payload}`
with no `dangerouslySetInnerHTML` anywhere in the render path); the test exists to make that
mechanism a checked assertion rather than an implicit property of the code, per DP-033 D2's own
"asserts: a payload containing `<script>` renders as text" requirement.

### Deviation / bug found and fixed during this batch

`[측정]` `ConfigSchemaForm`'s first version omitted `noValidate` on its `<form>`. MUI's
`required` prop on a `TextField` sets the underlying `<input required>` attribute; a native
`<form>` runs the browser's (and jsdom's) own HTML5 constraint validation on submit and silently
cancels the `submit` event — without ever invoking React's `onSubmit` handler — when a required
input is empty. This made the component's own validation and error message unreachable exactly
in the case the test needed to exercise (submit with the required field empty): the native
validation intercepted the click before `handleSubmit` ever ran. Found by the "blocks submission"
test failing with no error text in the rendered DOM at all (not a wrong message — no message).
Fixed by adding `noValidate` to the form element, which was correct given batch 5a's `JobsListScreen`/
`JobDetailScreen` already establish MUI `helperText`/`Alert` as this dashboard's error-display
convention rather than native browser validation UI. Not a P0-reference deviation (P0-A built no
config-schema renderer to compare against) — recorded here because AGENTS.md's classify-before-patching
rule for a failing test applies to a component test the same way it applies to a gate: this was an
implementation defect in the new code, not a wrong test or a wrong requirement, and the fix is the
kind future config-schema-rendering work in this codebase should know about.

### What remains unwired (mock-first, real wiring is batch 5d)

- `POST /sources/{id}/credentials` — client function is real (`writeCredential`), no backend
  serves it; Lane A owns it now, per the controller ruling.
- `GET /sources/{id}/raw/items?offset&limit` — client function is real (`readRawItems`), no
  backend serves it; M2 domain API.
- `GET /sources` (or equivalent source list/detail) — does not exist as a client function at all
  yet; `CollectorDomainScreen` and `DataBrowserScreen` both use local, hardcoded mock arrays
  (`MOCK_SOURCES`, `MOCK_SOURCE_OPTIONS`) for which domains/sources exist, their status
  (enabled/last success/next run), their config schema, and which credential purposes are already
  configured. No route shape for this exists in the plan yet — inventing one would have been
  guessing at Lane A's design, so this batch mocked the data instead of the client call.
- Persisting `ConfigSchemaForm`'s submitted values to `source.config` — the form's `onSubmit`
  prop is wired to a no-op in `CollectorDomainScreen`; only the form's own client-side validation
  is exercised/tested this batch.
- Schedule display — still the same placeholder box carried from batch 5a (M6 scope, unchanged).

### Verification

`[측정]` `npm run build` (`tsc -b && vite build`), 2026-08-21: clean, no TypeScript errors.
Bundle ~530 kB / 162 kB gzip (up from batch 5a's ~521 kB / 160 kB — two new screens' worth of MUI
form/table usage; still one chunk, same over-500kB warning as batch 5a, still not addressed).

`[측정]` `npm test` (`vitest run`), 2026-08-21: **21 passed, 0 failed** (11 new tests added to
batch 5a's 10), across 7 test files:
`ConfigSchemaForm.test.tsx` (3), `CredentialForm.test.tsx` (4), `CollectorDomainScreen.test.tsx`
(1 smoke test), `DataBrowserScreen.test.tsx` (3, including the DP-033 D2 control above), plus
batch 5a's three unchanged files (10).

`[측정]` `npm run lint` (`oxlint`), 2026-08-21: clean, no findings.

No Python gates were run for this batch (no Python files touched).

## Batch 5d — normalization management + downloads (UI complete, mock-first)

- Date: 2026-08-21.

`[결정]` Coordinator dispatch (2026-08-21, "Lane B batch 3"): build the remaining two DP-033 D1
screens — normalization management (spec §6, PoC Contract §8) and downloads (DP-033 D3) — UI
mock-first, completing all six screens. Real wiring to M2's/M6's actual routes moves to a later
"batch 5-final" (integration wiring + a live pass against the real backend), which is not part of
this batch.

### What was built

- `apps/dashboard/src/mocks/sources.ts`: extracted the `{sourceId, label}` mock source list
  shared by every screen that needs a source selector (`DataBrowserScreen`, and now
  `NormalizeManagementScreen`, `DownloadScreen`) — batch 5b/5c had it duplicated once
  (`DataBrowserScreen`'s own copy); this batch would have made it three, so it moved to a
  shared module instead. `CollectorDomainScreen`'s richer per-source mock (status, config
  schema, credential purposes) is unchanged and uses the same two source ids for consistency.
- `apps/dashboard/src/screens/NormalizeManagementScreen.tsx`: no longer a placeholder. Three
  panes over a source-scoped set of sealed snapshots: (a) a snapshots table — `snapshot_id`
  (short), `item_count`, a manifest-digest prefix (`manifest_sha256.slice(0,12)`), `sealed_at`,
  and **`verifies` as its own table column** (PoC Contract §8: "A snapshot's verification state
  is its own column, never folded into a status word" — mirrors `experiments/integrated-p0/dashboard/src/domain-view.tsx`'s
  `SnapshotTable`, read as reference, new implementation), plus a `Seal snapshot` button in this
  pane's own header; (b) a create-run pane — visible once a snapshot row is selected, a
  normalizer-addon+version selector (mocked list) and a `Create run` button, **structurally
  separate** from the seal button (PoC Contract §8: "Sealing and normalizing are separate
  deliberate acts and must not be combined into one control" — enforced here by the two buttons
  living in two different `Paper`/`data-testid` sections, not by any shared handler that could
  later be merged); (c) a results pane — for the selected snapshot, one card per
  `(addon_id, addon_version, output_contract_version)` group, rendered side by side in a
  horizontal flex row (PoC Contract §5: "Versions coexist... two sets of rows, both readable"),
  each card showing a run summary (`N records, M errors` — DP-030 D2: "the run summary
  aggregates the error-record count") and a per-record table whose `error` column shows a
  `normalize_error: <field>` `Chip` only when that record's mocked `notes.normalize_error` is
  non-null.
- `apps/dashboard/src/screens/download/buildExportUrl.ts`: the actual deliverable for the
  download screen — a pure `buildExportUrl(base, filters)` function against the shape the M2–M7
  batch plan's §신규 API fixes (`GET /export/raw?source_id&from&to&key_prefix&format=jsonl|csv`,
  `GET /export/results?...&format=csv`). An empty `from`/`to`/`keyPrefix` is omitted from the
  query string entirely rather than sent empty. `kind: "results"` always forces `format=csv` in
  the built URL regardless of the requested format, because the plan gives `/export/results` no
  JSONL option ("정규화 결과는 CSV 평탄화"). Pulled into its own module (not
  `DownloadScreen.tsx`) after `oxlint`'s `react(only-export-components)` flagged a component file
  also exporting plain functions/types — see Verification.
- `apps/dashboard/src/screens/DownloadScreen.tsx`: no longer a placeholder. A raw/normalized-results
  radio toggle, a source selector (shared mock list), from/to date fields, an `item_key` prefix
  field, and a JSONL/CSV format radio (JSONL disabled and forced off when "normalized results" is
  selected, matching `buildExportUrl`'s own forcing rule so the UI never shows a state the built
  URL contradicts). Renders the built URL as text, a `Download` link (`<a href>`) carrying that
  same URL, and a copyable `curl -o export.download '<url>'` line. **No network call is made by
  this screen at all** — per the dispatch brief, correct URL construction is the whole
  deliverable; M6 serves the actual route.

### What remains unwired (enumerated, mocked vs. real-but-unwired vs. no-network-by-design)

Real client functions, written against a shape the plan already fixes, with no live backend yet
(batch 5b/5c, unchanged by this batch):
- `POST /sources/{id}/credentials` (`writeCredential`, DP-034 D1) — Lane A's route.
- `GET /sources/{id}/raw/items?offset&limit` (`readRawItems`) — M2's route.

Local mock data, because no route shape for these exists anywhere in the plan yet:
- `GET /sources` (or equivalent source list/detail) — `CollectorDomainScreen`'s `MOCK_SOURCES`
  and the shared `mocks/sources.ts` `MOCK_SOURCE_OPTIONS`, used by `DataBrowserScreen`,
  `NormalizeManagementScreen`, and `DownloadScreen`.
- `GET /snapshots?source_id=...` — `NormalizeManagementScreen`'s `INITIAL_SNAPSHOTS`.
- A normalizer-addon+version list for the create-run selector — `MOCK_NORMALIZERS`.
- `GET /snapshots/{id}/results` — `NormalizeManagementScreen`'s `MOCK_RESULTS`.
- Sealing (`POST /sources/{id}/snapshots` in the P0 reference's `api.ts` shape) — this batch's
  `mockSealSnapshot` appends a locally-generated row to component state; no request is sent.
  P0's reference shape exists (`experiments/integrated-p0/dashboard/src/api.ts`'s
  `sealSnapshot`), but nothing in this batch's brief or the plan re-fixed it for P1, so — unlike
  the credential/raw-item calls — this was left mocked rather than written as a real,
  unwired client function against a guessed shape.
- Creating a normalize run (`POST /snapshots/{id}/normalize` in the P0 reference's shape) — same
  reasoning; `onCreateRun` shows a mocked notice and touches no network.
- Persisting `ConfigSchemaForm`'s submitted config values — unchanged from batch 5b/5c, still a
  no-op `onSubmit`.

No network call by design (the deliverable is the URL, not a fetch):
- `GET /export/raw` / `GET /export/results` — `DownloadScreen` never calls `fetch`; it renders
  the URL and a curl line for the operator to use directly. Wiring here means confirming the
  built URL actually downloads once M6 serves the route — not adding a fetch call.

Batch 5-final (not part of this batch) replaces every "real-but-unwired" and "mock" entry above
with the real call, once M2 and M6 land in dev; the "no network call by design" entries stay as
they are — a live pass there means testing the link, not adding a request.

### Verification

`[측정]` `npm run build` (`tsc -b && vite build`), 2026-08-21: clean, no TypeScript errors.
Bundle ~548 kB / 166 kB gzip (up from batch 5b/5c's ~530 kB / 162 kB — two more full screens'
worth of MUI table/form usage); still one chunk, still over Vite's 500 kB warning threshold,
still unaddressed (noted in every batch so far; not treated as a build failure).

`[측정]` `npm test` (`vitest run`), 2026-08-21: **34 passed, 0 failed** (13 new tests added to
the running total of 21), across 9 test files. New: `NormalizeManagementScreen.test.tsx` (4:
seal/normalize distinct-button-and-section check, sealing creates a separate row without
touching the run pane, two result versions render side by side, the error badge appears only on
the flagged record with the run summary counting it) and `DownloadScreen.test.tsx` (9: 4 direct
unit tests of `buildExportUrl` — param mapping, empty-range omission, format toggling, the
results-forces-csv rule — plus 5 integration tests against the rendered screen covering the same
properties through the UI, and one asserting the download link and curl line carry the same
URL).

`[측정]` `npm run lint` (`oxlint`), 2026-08-21: **found one warning on the first pass** —
`DownloadScreen.tsx:46:17: react(only-export-components)` (a component file also exporting
`buildExportUrl`/`curlLine`/types breaks Fast Refresh). Fixed by moving those exports to
`screens/download/buildExportUrl.ts`, a non-component module, and re-running: clean, no findings,
exit code 0 both before and after the fix (the warning did not fail the gate, but "lint clean" per
the dispatch brief's own gate means no findings, not just a zero exit code).

No Python gates were run for this batch (no Python files touched).

## Batch 5-final — real wiring against M2/M6, live integration smoke

- Date: 2026-08-21.

`[결정]` Coordinator dispatch: `git merge dev` (M2's domain API, M6's scheduler and export
streaming, both real and merged) into `p1/m5-dashboard`; reconcile the client layer against the
real route shapes in `apps/domain/api.py`/`apps/domain/export.py`; update component-test mocks to
mirror the real response shapes; run a live integration smoke against the actual stack; leave
collect/import (M3-pending) disabled with a visible note.

### Merge

`git merge dev --no-ff` inside the worktree: no conflicts (disjoint paths — Lane A/C added
`apps/domain/`, `apps/scheduler/`, `apps/tests/test_domain_*.py`/`test_export.py`/
`test_scheduler.py`/`test_credentials.py`, migration `0002_domain.sql`; Lane B had touched none of
those). Brought in `apps/domain/api.py`, `apps/domain/export.py`, `apps/domain/store.py`,
`apps/scheduler/`, and `docs/p1/M2-RECORD.md`/`M6-RECORD.md`.

### Reconciliation: what was read, and every mismatch found (record any mismatch found — matching the backend, per the dispatch)

Read directly (not the plan's prose summary) before writing any client code: `apps/domain/api.py`
in full (every route's actual signature and view function), `apps/domain/export.py` in full
(`stream_raw`/`stream_results`, the format branch, the query text), and the relevant slices of
`apps/domain/store.py` (`SourceRow`, `RawItemRow`, `record_envelope`/`record_items`,
`raw_summary`, `read_schedule`/`upsert_schedule`, `seal_snapshot_from_raw`, `read_results`).

1. **`GET /sources/{id}/raw/items` has no `matched` field.** `platform_core.api.app`'s `GET
   /jobs` returns `{..., returned, matched, jobs}`; `apps/domain/api.py`'s `read_raw_items`
   returns `{..., returned, items}` — `returned` only. Batch 5b/5c's `RawItemPage` type and
   `DataBrowserScreen`'s pagination both assumed `matched` existed (copied the jobs-page shape
   without checking the raw-items route had the same one). Fixed: `matched` removed from the
   type; `DataBrowserScreen`'s "Next" button now disables on `returned < limit` — the only signal
   available without a total count.
2. **`GET /export/results` accepts `jsonl` or `csv`, not CSV-only.**
   (`[정정, 2026-08-21, m7-fixwave, M-R9]` was written "GET/POST" — `[측정]`
   `apps/domain/api.py` binds `/export/results` with `@app.get(...)` only, no `POST`
   route exists at that path.) The plan's own prose
   ("정규화 결과는 CSV 평탄화") and batch 5d's `buildExportUrl` both read `/export/results` as
   CSV-only and forced `format=csv` whenever "normalized results" was selected. Reading
   `apps/domain/api.py`'s `export_results` and `apps/domain/export.py`'s `stream_results`
   directly shows the real signature is identical to `export_raw`'s —
   `format: Annotated[Literal["jsonl", "csv"], _FORMAT_QUERY] = "jsonl"`, no kind-specific
   restriction anywhere. Fixed: `buildExportUrl` no longer forces a format by kind; `DownloadScreen`
   no longer disables the JSONL radio for normalized results. Verified live (below): both
   `/export/raw` and `/export/results` served `jsonl` and `csv` identically.
3. **`POST /snapshots/{id}/normalize` takes a normalizer *source id*, not an addon/version pair.**
   Batch 5d's create-run picker offered a mocked `{addon_id, version}` pair with no backing route
   for that shape. The real route (`start_normalization`) takes `{source_id}` in the body — a
   registered source of `kind == "normalizer"` — because a normalizer is itself a registered
   source row with its own `addon_id`/`addon_version` already fixed at registration; the route
   even 409s if the named source isn't `kind == "normalizer"`. Fixed:
   `NormalizeManagementScreen`'s picker now lists registered `kind === "normalizer"` sources by
   `source_id`.
4. **The credential write route is genuinely write-only — there is no "configured" status to
   query, ever.** Batch 5b/5c's `CredentialForm` took a `configuredPurposes` prop and rendered
   "configured"/"not configured" against it, implying a server-known, queryable truth. DP-034 D1's
   own text (confirmed by reading `apps/domain/api.py`'s `write_source_credential` and
   `platform_core/secrets.py`'s `write_credential`) is explicit that the route never reads a value
   back and no route anywhere reports whether a purpose is configured — `source_view`'s
   `credential_ref` is a single, source-level ref name, not a per-purpose configured/unconfigured
   map. `configuredPurposes` wasn't standing in for a route that hadn't landed; it was mocking
   information the real system cannot provide at all. Fixed: the prop is removed; the badge now
   reads "written this session" / "not written this session" (this component's own local state),
   never a claim about server state the component cannot see.

### M3-pending: collect/import (left disabled, per the dispatch)

`apps/domain/api.py`'s own docstring states `POST /sources/{id}/collect` and `.../import` were
**never built** — both would create a job for handler `addon:<addon_id>`, and nothing in this
tree registers a handler for that prefix until M3's `addon_host` lands, so such a job would sit
`PENDING` forever. `CollectorDomainScreen` now shows a disabled "Collect now" button
(`data-testid="collect-now-button"`) with a visible note
(`data-testid="collect-disabled-note"`, text: *"Collection dispatch arrives with the add-on host
(M3). apps/domain/api.py builds no /collect route yet..."*) rather than omitting the action or
calling a route that does not exist. `POST /snapshots/{id}/normalize` **is** wired for real (the
batch brief's own scope), even though it shares the same eventual-dispatch gap — a created
normalize job also stays `PENDING` until M3; the UI's success message says so explicitly
("It stays PENDING until M3 registers a worker for it").

### Wiring table

| Endpoint | Screen(s) | Status |
|---|---|---|
| `GET /sources` | Collectors, Data Browser, Normalization, Downloads | real, live-verified |
| `GET /sources/{id}` | (client function; not directly consumed by a screen yet — `useSourceQuery` exists for batch 5c's later use) | real, live-verified |
| `GET /sources/{id}/raw` | Collectors (status header: item count, last retrieved) | real, live-verified |
| `GET /sources/{id}/raw/items` | Data Browser | real, live-verified |
| `GET /sources/{id}/schedule` | Collectors | real, live-verified |
| `PUT /sources/{id}/schedule` | Collectors | real, live-verified |
| `POST /sources/{id}/credentials` | Collectors (`CredentialForm`) | real, live-verified (success + 422 validation refusal) |
| `POST /sources/{id}/snapshots` (seal) | Normalization | real, live-verified |
| `GET /snapshots?source_id=` | Normalization | real, live-verified |
| `POST /snapshots/{id}/normalize` | Normalization | real, live-verified (job created; stays `PENDING`, M3) |
| `GET /snapshots/{id}/results` | Normalization | real, live-verified (empty result set — no worker has run yet, expected) |
| `GET /export/raw` | Downloads (URL only, no fetch) | real, live-verified via curl (jsonl + csv) |
| `GET /export/results` | Downloads (URL only, no fetch) | real, live-verified via curl (jsonl + csv; the format-forcing mismatch above was caught here) |
| `POST /sources/{id}/collect`, `POST /sources/{id}/import` | Collectors ("Collect now") | does not exist (M3); disabled with a note, per the dispatch |
| `GET /jobs`, `/jobs/{id}`, `/jobs/{id}/attempts`, `POST /jobs/{id}/retry`, `/health`, `/metrics` | Jobs monitor, Health | unchanged from batch 5a — `platform_core.api.app`, real since M1 |

### Live integration smoke

`[측정]` Full sequence, 2026-08-21, unsandboxed for DB/env/loopback per the dispatch:

1. **Python gates (no Python changed this batch):** `cd apps && uv run mypy --strict .` — clean,
   57 source files. `uv run ruff check .` — clean.
2. **`apps` pytest suite**, `COSMA_TEST_DB=cosmai_test_2`, port `5434`: **605 passed, 2 failed.**
   The 2 failures (`test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`, both of its
   tests) are a **pre-existing defect exposed by running from inside a worktree, not a
   regression from this batch or from the M2/M6 merge** — diagnosed directly: the class's
   `SKIPPED_PARTS = (..., ".worktrees")` is checked against each file's *absolute* `path.parts`,
   and `REPO_ROOT` (`Path(__file__).resolve().parents[2]`) for this lane is itself
   `.../cosmai/.worktrees/m5` — so `.worktrees` appears in literally every scanned file's `parts`,
   the `not any(part in SKIPPED_PARTS ...)` guard is false for everything, and the scan silently
   returns zero files (confirmed with a throwaway diagnostic script: plain `os.walk`/`rglob` over
   the same root, run both standalone and inside a bare pytest file with the real `conftest.py`
   loaded, correctly found 45,000+ files with zero errors — the defect is specific to this one
   test class's own `SKIPPED_PARTS` entry, not the environment, pytest, or any Python this batch
   touched). Not fixed here: out of Lane B's scope (no Python changes this batch), and the class
   belongs to Lane A's outbound-guard test suite. Recorded per AGENTS.md's classify-before-patching
   rule rather than silently rerun until green.
3. **Schema reset + migration**, migrator path (mirroring `apps/tests/conftest.py`'s
   `_reset_schema` + `apply_migrations`, per the dispatch's own pointer): `drop schema if exists
   cosmai cascade; create schema cosmai` plus the same five grant statements
   `apps/db/provision_db.sql`/`conftest.py` use, then `apply_migrations` — applied
   `0001_platform_core`, `0002_domain` cleanly against `cosmai_test_2` on `127.0.0.1:5434`.
4. **Seed**: one throwaway script (`platform_core.db.connection.connect(role="runtime")` +
   `domain.store.DomainStore`/`platform_core.jobs.store.JobStore`) registered `smoke-collector`
   (kind `collector`, addon `collector.naver.blog`) and `smoke-normalizer` (kind `normalizer`,
   addon `normalizer.naver.blog`), then wrote 3 Raw items for `smoke-collector` through a real
   job+attempt (`raw_envelope.job_id`/`attempt_id` are `NOT NULL` foreign keys — seeding needs a
   real claimed attempt, not a bare insert). One seeded item's payload deliberately contains
   `<script>alert(1)</script>`, carrying DP-033 D2's plain-text control through to a real stored
   row rather than only a mocked one.
5. **API boot**: `python -m` equivalent script composing `platform_core.api.app.create_app(config,
   logger, extend=domain.api.extend_with_domain(config, logger))` — the same `extend` seam
   `platform_core.api.__main__.serve()` exposes, since no standalone `apps/domain/__main__.py`
   entrypoint exists yet (that composition decision is M3's, per `apps/domain/api.py`'s own
   docstring: "M3 must decide whether to import `extend_with_domain` from here... or move this
   module's routes into `addon_host.api` outright"). Bound `127.0.0.1:8100`
   (`COSMA_API_PORT=8100`), DB `cosmai_test_2` on `127.0.0.1:5434`.
6. **curl verification**, every route in the wiring table above, response shapes compared field
   by field against the TypeScript types: `GET /health` → `200`; `GET /sources` → both seeded
   sources, matching `Source` exactly; `GET /sources/{id}/raw` → `{item_count: 3, ...}`; `GET
   .../raw/items` → 3 items in `seq` order, `<script>` payload intact and unescaped in the JSON
   string (correct — escaping is the dashboard's rendering job, not the API's); `PUT`/`GET
   .../schedule` round-tripped `{interval_seconds: 3600, enabled: true}`; `POST
   .../snapshots` sealed a 3-item snapshot, `verifies: true`; `GET /snapshots?source_id=` listed
   it; `POST /snapshots/{id}/normalize` with `{source_id: "smoke-normalizer"}` returned `201`
   `{job_id, snapshot_id}`; `GET .../results` returned `{results: []}` (correct — no worker has
   run the job, M3); `POST .../credentials` returned `204` on a valid write and `422` `{detail:
   ...}` on an empty purpose (the plain FastAPI `HTTPException` shape, not the
   `CredentialWriteRefusal` shape — both are handled by `writeCredential`'s fallback, per its own
   code); `GET /export/raw` and `GET /export/results`, both `format=jsonl` and `format=csv`,
   streamed correctly with `content-type: application/x-ndjson`/`text/csv` and a
   `content-disposition: attachment` header on a `GET` (a `curl -I` HEAD request showed a
   misleading `content-type: application/json` — an artifact of HEAD against a
   `StreamingResponse`, not a real defect; confirmed by comparing against the real `GET` headers
   with `curl -D -`).
7. **Client-module round-trip** (vitest, no mocked `fetch`, real network to `127.0.0.1:8100`, via
   `VITE_API_BASE`): a throwaway `src/__live_smoke__.test.ts` imported `api/client.ts`'s real
   functions directly — `listSources`, `readSource`, `readRawSummary`, `readRawItems`,
   `readSchedule`, `listSnapshots`, `sealSnapshot`, `createNormalizeRun`, `writeCredential` — **9
   tests, all passing**, including one asserting `"matched" in page === false` on the raw-items
   page (the mismatch fix, checked against the live response, not a mock) and one confirming
   `sealSnapshot("smoke-normalizer")` (wrong kind) comes back as `DomainRefused` rather than
   throwing. Deleted before this batch's commits — never part of the committed suite, since
   `npm test`'s normal run has no live server to hit.
8. **Dev-server sanity check**: `vite` dev server booted against `VITE_API_BASE=http://127.0.0.1:8100`
   on port `5180`; root document served `200`.
9. **Cleanup**: API server and dev server processes killed; both ports (`8100`, `5180`) confirmed
   refusing connections (`curl` → `000`) afterward. The seeded rows remain in `cosmai_test_2`
   (a disposable lane test database, not `cosmai` production) — not cleaned up, since nothing in
   this batch's scope required leaving that database empty, and the next `pytest` run against it
   resets the schema anyway (`_reset_schema`, session-scoped autouse).

### What remains unwired (updated from batch 5d)

- `POST /sources/{id}/collect`, `POST /sources/{id}/import` — do not exist in `apps/domain/api.py`
  at all (M3's gap, not this lane's). `CollectorDomainScreen` shows both disabled with a note.
- `POST /snapshots/{id}/normalize` creates a real job that stays `PENDING` until M3 registers an
  `addon:*` worker — the route is fully wired; what's missing is downstream of this lane.
- `ConfigSchemaForm`'s field definitions are still a per-`addon_id` mock
  (`MOCK_CONFIG_SCHEMAS` in `CollectorDomainScreen.tsx`) — no route anywhere exposes an add-on
  manifest's `[[config.field]]` schema; that is M3/`addon_host` territory. Submitting the form is
  still a no-op (no config-write route exists either).
- Everything else named in batch 5b/5c/5d's "what remains unwired" sections is now real: the
  source list/detail, schedule, seal, normalize-run creation, and results routes are all wired
  and live-verified above.

### Verification

`[측정]` `npm run build` (`tsc -b && vite build`), 2026-08-21: clean, no TypeScript errors. Bundle
~589 kB / 179 kB gzip (up from batch 5d's ~548 kB / 166 kB — `[정정, 2026-08-21,
m7-fixwave, M-R9]` was written 549, contradicting line 349 above's own 548 (actual
548.40, rounds to 548) — the domain type/client surface grew
substantially; still one chunk, still over Vite's 500 kB warning threshold, still unaddressed).

`[측정]` `npm test` (`vitest run`), 2026-08-21: **37 passed, 0 failed**.
`[정정, 2026-08-21, m7-fixwave, M-R8]` Not "the same 37 from batch 5d" — batch 5d
(line 345 above) reported **34**, not 37, and they are not the same tests: this pass
added 9 and removed 6 (net +3). Six assertions were deleted along with the mock-shape
rewrite this paragraph describes, and the earlier phrasing hid that a net gain of 3
included a loss of 6. `CredentialForm.test.tsx`, `DataBrowserScreen.test.tsx`,
`CollectorDomainScreen.test.tsx`, `NormalizeManagementScreen.test.tsx`, and
`DownloadScreen.test.tsx` were all rewritten to mock the real response shapes (derived
from `apps/domain/api.py`'s view functions, not from batch 5b/5c/5d's earlier
guesses) rather than the old mock-source-list shapes.

`[측정]` `npm run lint` (`oxlint`), 2026-08-21: clean, no findings.

Commits are logical: (1) the `dev` merge, (2) the type/client/query reconciliation, (3) the
`CredentialForm` fix (removing `configuredPurposes`), (4) the four screens' real wiring, (5) the
`buildExportUrl` format-forcing fix, (6) the rewritten component tests, (7) this record.
