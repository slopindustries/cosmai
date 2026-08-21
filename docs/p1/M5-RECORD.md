# M5-RECORD — the dashboard, batch by batch

- Milestone: M5 (`apps/dashboard/`, Lane B).
- Branch: `p1/m5-dashboard`.
- Consumed by: M7's full adversarial review, per the batch plan
  (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §M5).

This record grows one section per batch. Batch 5d (normalization management, downloads, schedule
UI, and real wiring of everything batches 5b/5c mocked) is not yet started; its section is added
when that batch lands.

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
runtime or package dependency of P1" and `tests/environment/test_apps_never_imports_experiments.py`
(that guard is Python-only — `.py` files under `apps/` — and does not scan TypeScript, but no
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
  forward the loopback-only rule `experiments/integrated-p0/dashboard/src/api.ts` and
  `vite.config.ts` both apply, for the same SEC-002 reason.
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
