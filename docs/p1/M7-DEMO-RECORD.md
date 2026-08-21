# M7-DEMO-RECORD — the real end-to-end demo, on the production `cosmai` database

- Milestone: M7 (`p1/m7-closure`), Commit 2 of the sweep-and-demo task packet.
- Date: 2026-08-21.
- Database: `cosmai` (production, `shared-postgres:5434`) — **not** `cosmai_test`. This
  is the point: every job below ran through the real platform, against the database
  the operator will actually inspect, not a test fixture that gets reset.
- Scope: five sources registered and exercised (trend-radar via the scheduler,
  tubedepth, NAVER blog, NAVER DataLab, a local JSONL importer), one schedule cycle
  observed firing for real, one seal→normalize→results pipeline run twice (NAVER
  blog and the importer/product pair), raw and results downloads verified in both
  JSONL and CSV, all six dashboard screens' API calls verified against the live
  database.
- Everything below is `[측정]` unless labeled otherwise. Job ids, item counts, and
  HTTP status codes are recorded; payload contents beyond counts/keys are not, and no
  credential value appears anywhere in this file or in any script that produced it.

## 0. Setup scripts (not committed)

Three throwaway Python scripts and one small fixture, under `/tmp/claude-1000/m7-demo/`
(outside the repository working tree, per this task's instruction and
`docs/conventions/data-handling.md`): `migrate_cosmai.py` (apply migrations to
`cosmai`), `register_sources.py` (register the seven `cosmai.source` rows below via
`DomainStore.register_source` — five collectors/importer plus two normalizer sources,
since `POST /snapshots/{id}/normalize` names a *registered normalizer source*, not a
bare add-on id), `products.jsonl` (a 3-row fixture for `importer.local.jsonl`, one row
deliberately near-empty to exercise the DP-030 D2 fallback path), and one small
ad-hoc UPDATE script used twice mid-run to raise `tubedepth`'s outbound-profile page
budget (§5's finding explains why). None of these were committed; none contain a
credential value — every credential is referenced by `ref` name only
(`COSMA_SRC_NAVER_BLOG_CLIENT_ID`/`_CLIENT_SECRET`, `COSMA_SRC_TUBEDEPTH_API_KEY`),
resolved at the worker boundary from `~/.config/cosmai/env` exactly as
`platform_core.secrets.resolve_credential` does for any other job.

## 1. Migration

`[측정]` `platform_core.db.migrate.apply_migrations` against `cosmai` via a
`role="migrator"` connection: `applied=['0001_platform_core', '0002_domain']`.
**PASS.**

## 2. Boot

Three processes, all unsandboxed (loopback TCP to `:5434`, and the API/worker/
scheduler each bind their own loopback port), all logging structured JSON to a file
under `/tmp/claude-1000/m7-demo/`:

| Process | Command | Port / role |
|---|---|---|
| API + domain | `COSMA_API_HOST=127.0.0.1 COSMA_API_PORT=8100 uv run python -m addon_host` | `127.0.0.1:8100` — the platform surface plus `domain.api.extend_with_domain` |
| Addon-host worker | `COSMA_ADDON_DIR=<abs path>/apps/addons uv run python -m addon_host.worker` | no port; claims jobs, hosts all 8 add-ons |
| Scheduler | `uv run python -m scheduler` | no port; polls `cosmai.schedule` |

**`[정정, 2026-08-21, M-X2 fix wave]`** `COSMA_API_PORT=8100` above was set explicitly and
without a stated reason at the time this record was written — `platform_core.config`'s own
`COSMA_API_PORT` default was `8000`, which collides with trend-radar's live dashboard
(DP-031 D3: `http://127.0.0.1:8000/api/v1`, also reached during this same demo, `:70`
below). Loud 404s rather than silent wrong data, but unregistered until B6 (M-X2,
`docs/agent-workflow/reviews/REVIEW-M2-M7.md`) found it. `platform_core.config`'s
`COSMA_API_PORT` default (and the dashboard client's matching `DEFAULT_API_BASE`) are now
`8100`, so this demo's command line is what a fresh checkout does with no environment set,
not an unexplained override.

`[측정]` A relative `COSMA_ADDON_DIR=apps/addons` resolves against the process's own
cwd (`apps/`), giving `apps/apps/addons` — nonexistent. First worker start refused
with `CONFIGURATION_INVALID` (`addon_host.worker.refused`, exit `78`), exactly the
"a refusal is fatal, no default substituted" behavior SEC-003 asks for. Restarted with
an absolute path; the default (unset `COSMA_ADDON_DIR`) would also have resolved
correctly, since `addon_host.settings.DEFAULT_ADDON_DIR` is computed from the module's
own file location, not the process cwd — this is a note for the next operator running
these commands by hand, not a code defect.

`[측정]` Worker startup log named all 8 add-ons as claimed handlers:
`addon:collector.naver.blog`, `addon:collector.naver.datalab`,
`addon:collector.trendradar.rest`, `addon:collector.tubedepth.rest`,
`addon:importer.local.jsonl`, `addon:normalizer.naver.blog`,
`addon:normalizer.naver.trend`, `addon:normalizer.obf.product` — plus the platform's
own synthetic handlers. **PASS.**

Live-target reachability confirmed before registering anything:
`curl http://127.0.0.1:8000/api/v1/health` → `200` (trend-radar);
`curl http://127.0.0.1:8080/healthz` → `200` (tubedepth).

## 3. Source registration

Seven `cosmai.source` rows, registered directly via `DomainStore.register_source`
(the same write path an operator-facing registration screen would eventually call;
no such screen exists yet — DP-033's six dashboard screens do not include one, per
`docs/p1/M5-RECORD.md`):

| `source_id` | `addon_id` | kind | outbound/input |
|---|---|---|---|
| `trendradar` | `collector.trendradar.rest` | collector | loopback `:8000`, `scheme:"http"`, `allow_loopback:true` (M4x's gap-1 mechanism) |
| `tubedepth` | `collector.tubedepth.rest` | collector | loopback `:8080`, `scheme:"http"`, `X-API-Key` credential part, `{digest}` path template (M4x's gap-2 mechanism) — the exact profile shape from the add-on's own README |
| `naver.blog` | `collector.naver.blog` | collector | `naverapihub.apigw.ntruss.com`, two NCP header credential parts |
| `naver.datalab` | `collector.naver.datalab` | collector | same host, three POST endpoints, same credential parts (reused — `[확인 사실]` from `m4-naver-datalab-report.md`: the NCP APIGW key pair is account-level) |
| `naver.blog.normalize` | `normalizer.naver.blog` | normalizer | none (DP-008 D4) |
| `importer.local` | `importer.local.jsonl` | importer | `input_profile` naming the 3-row fixture |
| `obf.product.normalize` | `normalizer.obf.product` | normalizer | none |

All seven inserted without error. **PASS.**

## 4. Schedule → scheduler-created collect job (trend-radar)

`PUT /sources/trendradar/schedule {"interval_seconds": 10, "enabled": true}` → `200`.

`[측정]` The scheduler (already running, polling every `COSMA_POLL_MS=200ms`) picked
up the due row on its own and created a collect job **without any further request from
this session** — the thing this step exists to demonstrate:

```
scheduler.job_created  source_id=trendradar  handler=addon:collector.trendradar.rest  job_id=3f610ae2…
```

The worker claimed and ran it: `addon.collect.run_complete` `items_emitted=900,
pages_fetched=20, tables_processed=["rank_snapshot"], more_available=true` →
`job.transition … SUCCEEDED`. **`[정정, 2026-08-21, m7-fixwave, B9]`** The two
sentences that followed this one previously narrated only a second firing; the
scheduler actually fired a **third** time before the schedule was disabled (10s
interval, `COSMA_POLL_MS=200ms` — three firings inside one 10-second window is the
poll interval doing exactly what it is for). `[측정]` re-derived from
`scheduler.log`/`worker.log` at `/tmp/claude-1000/m7-demo/`, still present on disk:
three distinct `scheduler.job_created` events (`job_id`s `3f610ae2…`, `81960e7b…`,
`7d66a053…`), three `addon.collect.run_complete`/`SUCCEEDED` completions —
`items_emitted` **900, 900, 892** in firing order (2692 total). Schedule then set to
`enabled:false` to stop further firing.

**This collect itself is notable independent of the scheduler mechanism**: `[확인
사실]` `m4-trendradar-report.md` recorded trend-radar's live collect as blocked
outright (`SSLError`, plain-HTTP target against an HTTPS-only transport) — the exact
gap M4x's Gap 1 (this file's own §Gap 1, carried from `docs/p1/M4-RECORD.md`) closed.
This is the first live, end-to-end trend-radar collect this project has completed.
**PASS**, and evidence that M4x's fix generalizes past the one tubedepth re-run its
own report measured.

## 5. Direct collect jobs

`POST /sources/tubedepth/collect`, `POST /sources/naver.blog/collect`,
`POST /sources/naver.datalab/collect`, `POST /sources/importer.local/import` —
all `201`.

**naver.blog: SUCCEEDED, but not "1 page" as intended.** `[측정]` This add-on's
`addon.toml` has no `max_pages`-shaped config field — the page budget lives on the
*profile*'s `limits.max_pages` (the same mechanism `m4-naver-blog-report.md`'s live
smoke set to `1` explicitly), which this session did not override, so it defaulted to
`DEFAULT_LIMITS["max_pages"] = 20`. Result: `items_emitted=200, pages_fetched=20,
stopped_reason="max_pages"` — a clean, graceful stop at the budget, not a failure.
**Recorded as a deviation from the task's literal "(1 page)" rather than silently
matched**: the collector's own internal budget tracking stopped it correctly: this is
more data than intended, not a control failure. **`[정정, 2026-08-21, m7-fixwave,
B11]`** Named plainly, not only as a page-count deviation: 20 pages against an
intended 1 is **~20× the intended quota pulled from a live third party** (NAVER's
API Hub) **under a real credential**, not a synthetic or sandboxed target. The
result was benign here (a public search endpoint, no rate-limit or ToS breach
observed), but the same unbounded-default shape against a stricter or metered
upstream would not be — `limits.max_pages` defaulting to 20 rather than requiring
an explicit value is a real operational risk this demo surfaced and did not
previously say out loud.

**naver.datalab: SUCCEEDED as intended.** One `search_trend` window
(2026-08-14..2026-08-20): `addon.collect.window_complete mode=search_trend, points=7`
→ `SUCCEEDED`. 1 envelope, 7 raw items.

**importer.local: SUCCEEDED.** `addon.import.finished emitted=3, lines=3,
malformed_json=0, not_an_object=0, missing_key_field=0` → `SUCCEEDED`. 1 envelope,
3 raw items (one deliberately near-empty row, to exercise the normalizer's fallback
path downstream).

**tubedepth: FAILED, every attempt — a genuine finding, not a platform bug.**
`[측정]` First attempt at the default `limits.max_pages=20` (the README's own example
profile has no override) refused: `"this source grants 20 pages per run and the
collector asked for 21"` — `PLATFORM_PERMANENT` (`job_id=989b2034…`). Raised to `300`
(the M4x live smoke's own scale: 5 list pages + 224 dereferences ≈ 229 requests):
refused again, `"grants 300 … asked for 301"` (`caa3b54d…`). Raised to `2000`: refused
again, `"grants 2000 … asked for 2001"` (`ca905843…`). **`[정정, 2026-08-21,
m7-fixwave, B9]` A fourth attempt at `500`, omitted from the narration below, was also
refused on the same budget check**: `"grants 500 … asked for 501"` — `PLATFORM_PERMANENT`
(`job_id=f8720ced…`, `[측정]` re-derived from `worker.log` at
`/tmp/claude-1000/m7-demo/`, still present on disk; this is the sixth of the six
`FAILED` jobs §10's own tally already counts, the one no sentence in this section had
named). Restricted `config.kinds` to `"video.metadata"` alone and raised to `8000`:
this time the platform's own page-budget check was satisfied, but three attempts each
ended `RETRYABLE_FAILURE`/`PLATFORM_TRANSIENT` ("the request to 'artifact_payload'/
'artifacts_list' did not complete") before exhausting `max_attempts=3` →
`PLATFORM_PERMANENT`. A final attempt at a small, fast `page_limit=10`/
`limits.max_pages=60` refused immediately on the budget again (`"grants 60 … asked
for 61"`).

`[추론]` Two independent things are true at once. First, `[측정]` the live
tubedepth instance's `video.metadata` backlog is now far larger than the 224 total
items `m4-tubedepth-report.md`/`m4x-platform-gaps-report.md` measured a few hours
earlier in the same day — `GET /v1/artifacts?limit=1` returns entries with
`fetched_at` timestamps seconds old, i.e. the service is a live, continuously
ingesting scraper, not a fixed dataset, and a *fresh* source (no prior watermark) asks
for everything since the beginning. Second, `[확인 사실]` `collector.tubedepth.rest`'s
own pagination loop has no internal budget-awareness the way `collector.naver.blog`
and `collector.trendradar.rest` demonstrably have (both of those stopped gracefully
at their granted budget with `stopped_reason`/`more_available` fields; tubedepth
always asks for exactly one page past whatever it is granted, and never stops on its
own). Together: on this specific database (empty of any prior tubedepth watermark),
no operator-chosen finite page budget converges before either the grant is exceeded
or the sustained request volume trips a transport-level transient failure against the
live target. **This is a named limitation, not routed around**: fixing it would mean
teaching `collector.tubedepth.rest` its own budget-aware stopping behavior (the shape
`collector.naver.blog`/`collector.trendradar.rest` already have) — an add-on-layer
code change, not a ≤20-line platform fix, and out of this closure task's scope to
implement. `tubedepth`'s **raw item count in `cosmai` is 0** as a result; every other
source succeeded. The M4x gap-1/gap-2 mechanisms themselves are not in question here —
§Gap 1/§Gap 2's own evidence (a smaller backlog, measured the same day) already proved
they work; what this run adds is that the live target's backlog has since outgrown
what any one bounded run of this specific collector can absorb from a cold start.

## 6. Seal → normalize → results (twice)

**NAVER blog.** `POST /sources/naver.blog/snapshots` → `201`, `item_count=197`
(200 raw items, 3 collapsed by `item_key` under DP-029 D2's "highest `seq` wins" rule),
`verifies:true, problems:[]`. `POST /snapshots/{id}/normalize {"source_id":
"naver.blog.normalize"}` → `201`. Worker: `addon.normalize.complete results_emitted=197,
error_records=0` → `SUCCEEDED`. `GET /snapshots/{id}/results` returned 197 real
normalized blog documents (title/author/excerpt/url, in Korean, real content from the
live API Hub call).

**importer.local → obf.product.** `POST /sources/importer.local/snapshots` → `201`,
`item_count=3, verifies:true`. `POST /snapshots/{id}/normalize {"source_id":
"obf.product.normalize"}` → `201`. Worker: `addon.normalize.complete
results_emitted=3, skipped=0` → `SUCCEEDED`. All three rows present in
`GET /snapshots/{id}/results`, including the deliberately near-empty third row
(empty `product_name`, empty `brands_tags`, `last_modified_t: 0`) — it normalized to
a valid record with empty/zero-derived fields rather than being skipped or crashing,
consistent with `m4-importer-obf-report.md`'s own note that this add-on's field
helpers are already total over any JSON-decoded shape (so the DP-030 D2 fallback path
itself was not newly exercised here — `notes` was `{}` on every row, not a bug).

Both: **PASS.**

## 7. Browse via API (raw items pagination)

`GET /sources/naver.blog/raw/items?offset=0&limit=2` → `200`, 2 real items, payload
plain-text-decoded JSON strings (never rendered/interpreted), `seq`/`item_key`/
`emitted_at` present per DP-033 D2. **PASS.**

## 8. Download via `/export/raw` and `/export/results`

All against `naver.blog` (the source with both raw and normalized data):

| Call | HTTP | Result |
|---|---|---|
| `GET /export/raw?source_id=naver.blog&format=jsonl` | 200 | 200 lines, first line parses as JSON |
| `GET /export/raw?source_id=naver.blog&format=csv` | 200 | 201 lines (200 + header), 5 columns: `item_key, seq, emitted_at, content_type, payload` |
| `GET /export/results?source_id=naver.blog&format=csv` | 200 | 198 lines (197 + header), 11 columns incl. `body_sha256`, `notes`, `body` (`[정정, 2026-08-21, m7-fixwave, M-R10]` was "10 columns" — `RESULT_HEADER` in `apps/domain/export.py` has 11) |
| `GET /export/raw?source_id=naver.blog&format=jsonl&from_=…&to=…` (range filter) | 200 | **`[정정, 2026-08-21, m7-fixwave, B10]` vacuous, not a real range-filter check.** The wire parameter name is `from`, not `from_` (`apps/domain/api.py`'s `_FROM_QUERY: Any = Query(alias="from")`) — FastAPI ignores an unknown query parameter, so `from_=…` bound to nothing and the filter never ran. The 200-of-200 result this row reported is exactly what "no filter applied" also produces, so it cannot distinguish the two. The underlying code is fine — `buildExportUrl.ts` sends `from`, and `test_export.py::TestRawExportScopeFilters` covers the real parameter with a real assertion — only this row's own probe used the wrong name and its PASS should have read BLOCKED-VACUOUS, not PASS |

`csv.reader` parsed every file without error; every JSONL line parsed as JSON.
Content non-empty in all four calls. **PASS**, except the range-filter row above,
which this fix wave downgrades to vacuous rather than counting it as verified.

## 9. Dashboard

`cd apps/dashboard && npm install && VITE_API_BASE=http://127.0.0.1:8100 npm run build`
— `tsc -b && vite build`, 964 modules, `dist/index.html` + one JS bundle (588 KB,
179 KB gzipped — over vite's 500 KB chunk-size advisory, not investigated further,
out of scope for a closure demo). `npx`-free `python3 -m http.server 5173` served
`dist/` on `127.0.0.1:5173`, reachable (`200`).

Per-screen API calls (from `apps/dashboard/src/api/{client,queries}.ts`), each
verified with `curl` against the running API — a browser was not used, per this
task's own allowance:

| Screen | Endpoint(s) | Result |
|---|---|---|
| Health | `GET /health` | `{"status":"ok","database":"reachable","database_name":"cosmai","jobs_by_state":{"PENDING":0,"RUNNING":0,"SUCCEEDED":8,"FAILED":6}}` |
| Jobs | `GET /jobs?limit=3` | real job rows, `matched:14` |
| Collectors | `GET /sources`, `GET /sources/{id}/raw`, `GET /sources/{id}/schedule` | all 7 sources, real raw summaries, trend-radar's now-disabled schedule |
| Data Browser | `GET /sources/{id}/raw/items` | real paginated raw items (§7) |
| Normalization | `GET /snapshots?source_id={id}` | both sealed snapshots, real `manifest_sha256` |
| Downloads | `GET /sources` (to populate the source picker) + `/export/*` links | §8 |

All six: **PASS** (API side; the dashboard's own rendering of this data was not
visually inspected in a browser).

## 10. Shutdown

All three processes stopped with `SIGTERM`: API `api.stopped stop_reason="a stop was
requested by SIGTERM"`; worker `worker.stopped … jobs_executed=16 … exit_code=0`;
scheduler `scheduler.stopped … jobs_created=3 … exit_code=0`. The dashboard's static
file server stopped the same way. Ports verified closed afterward:
`curl --max-time 2 http://127.0.0.1:8100/` and `:5173/` both refuse the connection;
`ss -ltnp` shows no listener on either port.

`cosmai` was **left populated** — this is the demo state the owner may inspect, per
this task's instruction. It carries: 7 sources, 14 jobs (8 `SUCCEEDED`, 6 `FAILED` —
all 6 failures are the tubedepth attempts in §5, named there), 2 sealed snapshots, 200
`normalizer.naver.blog`-eligible raw items (197 after dedup), 3 importer raw items, 7
DataLab raw items, 2692 trend-radar raw items, 197 normalized blog results
(`[정정, 2026-08-21, m7-fixwave, M-R10]` was 200 — contradicts §6/§8's own 197, the
post-dedup count `worker.log` confirms), 3 normalized product results.

## What was NOT demonstrated — named honestly

- **tubedepth live collection did not succeed in this run** (§5). Every attempt
  failed, for the structural reason recorded there: the live backlog has outgrown
  what a fresh, budget-bounded collect can absorb, and this add-on's pagination has
  no graceful stop the way the other two REST collectors do. `tubedepth`'s raw item
  count in `cosmai` is 0.
- **naver.blog was not bounded to "1 page" as the task instruction named** (§5) — it
  ran at the platform's default 20-page budget instead, because this add-on has no
  config-level page cap and the profile's own `limits.max_pages` was not overridden
  before the first attempt. It succeeded regardless (more data collected, not less),
  so this is recorded as a deviation from the literal instruction rather than a
  failure.
- **The dashboard's rendering was verified via its own API calls (curl), not by
  opening it in an actual browser** — per this task's explicit allowance ("a browser
  is not required").
- **No credential value, database password, or raw payload beyond counts/keys is
  recorded anywhere in this file**, per the task's instruction and
  `docs/conventions/data-handling.md`.
- **`docker exec`/loopback TCP/`uv sync`/`npm install` steps all ran unsandboxed**,
  per the standing global-constraints note this batch inherited from M1; nothing else
  needed it.

## Concerns worth carrying forward

- `collector.tubedepth.rest` should gain its own budget-aware stopping behavior
  (mirroring `collector.naver.blog`'s `stopped_reason: "max_pages"` /
  `collector.trendradar.rest`'s `more_available` fields) before it is relied on for
  another live demo against a growing target — otherwise every fresh registration
  against this specific live instance will fail the same way.
- The registration step used direct `DomainStore.register_source` calls rather than
  an operator-facing HTTP surface, because no such surface exists yet (`docs/p1/
  M5-RECORD.md` does not name a "register a new source" screen among the six DP-033
  screens). Worth a decision if P1's next milestone wants an operator to be able to
  do this without a script.
