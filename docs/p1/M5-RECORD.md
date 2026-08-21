# M5-RECORD — the dashboard, batch by batch

- Milestone: M5 (`apps/dashboard/`, Lane B).
- Branch: `p1/m5-dashboard`.
- Consumed by: M7's full adversarial review, per the batch plan
  (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §M5).

This record grows one section per batch. Batch 5b (credential write path), 5c (collector-domain +
data browser), and 5d (normalization management + downloads + schedule UI) are not yet started;
their sections are added when those batches land.

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
