# M6-RECORD — what M6 built, what deviates, and what M7 owns next

- Milestone: M6 (Lane C — the scheduler process and streaming Raw/results export).
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m6`, branch `p1/m6-ops`,
  cut from `dev` after M2 merged.
- Batches and commits: 6a "A scheduler that wakes sources on time and refuses to pile up
  jobs" (`apps/scheduler/`, `GET|PUT /sources/{id}/schedule`), 6b "Export raw and normalized
  rows as a stream, in the shapes the dashboard already links to" (`apps/domain/export.py`,
  `GET /export/raw`, `GET /export/results`, this record).
- Date: 2026-08-21.
- Consumed by: M5's download/schedule screens (once merged) and the M7 closure review, per
  the plan's §공통 제약 ("편차는 침묵하지 않고 각 레인 기록에 등재 — M7 리뷰가 대조한다").

## (a) Infrastructure change mid-milestone

`[확인 사실]` The shared PostgreSQL container (`tubedepth-postgres`, `127.0.0.1:5433`) was
replaced outside this project's control by `shared-postgres` (`127.0.0.1:5434`) partway
through this milestone. The orchestrator re-provisioned `cosmai`/`cosmai_test`/
`cosmai_test_2/3/4` on the new server and rotated `~/.config/cosmai/env` before this
milestone's gates ran; `apps/db/provision.md`'s own 2026-08-21 addendum (commit `ea7f535`
on `dev`, not merged into this branch) owns the full story. Every command below in this
record and every gate run for this milestone used `COSMA_DB_PORT=5434`. This branch's own
history (commits before this one) still names `5433` in inherited doc text elsewhere in the
tree; that is pre-existing and out of this milestone's scope to correct everywhere.

Verified before any other work in this milestone: a direct connection to `cosmai_test_3` on
`:5434` as `cosmai_runtime`, then the full pre-existing `apps` suite (579 tests, the M2
baseline) green on the new port before any M6 code was written.

## (b) Scope as built

- **`apps/scheduler/`** (new package): `apps/scheduler/store.py` (`SchedulerStore` — a due
  scan, a locked re-check-and-decide, a duplicate check, an advance) and
  `apps/scheduler/__main__.py` (`python -m scheduler` — the process: configuration-first
  startup, cooperative shutdown, a `scheduler.report` JSON object on stdout at exit, the
  same database-failure classification and reopen-on-transient behavior
  `platform_core.worker` uses). One pass: scan due (`enabled` schedule, `enabled` source,
  `next_run_at <= now()`), then per candidate — in one transaction — lock and re-verify,
  skip if a `PENDING`/`RUNNING` job already carries the exact handler and `source_id`,
  otherwise create the collect job (`handler = f"addon:{addon_id}"`, `payload =
  {"source_id": source_id}`, `max_attempts = 3`) and advance `next_run_at`/`last_run_at`
  together with it.
- **`GET|PUT /sources/{id}/schedule`** in `apps/domain/api.py` (extended, not restructured)
  and `apps/domain/store.py` (`read_schedule`/`upsert_schedule` added to `DomainStore`
  alongside its existing CRUD). `PUT` upserts and requires the source be a `collector`.
- **`GET /export/raw` and `GET /export/results`** in `apps/domain/api.py`, backed by the new
  `apps/domain/export.py` — streaming generators over a named (server-side) PostgreSQL
  cursor, `StreamingResponse`, `Content-Disposition: attachment`. Scope filters: `source_id`
  (required), `from`/`to` (bound the row's own timestamp), `key_prefix` (`starts_with`, not
  `LIKE`, so a prefix containing `%`/`_` is not read as a wildcard). Formats: `jsonl`
  (default — Raw's `payload` spliced verbatim when it is already valid JSON, an escaped
  string otherwise; results as one JSON object per line) and `csv` (metadata/envelope
  columns plus one payload/body column, RFC4180-escaped via the streaming `csv.writer`
  idiom).

## (c) Deviations ledger

| # | What the plan's literal text said | What M6 built | Basis / reasoning |
|---|---|---|---|
| 1 | §신규 API shows `GET /export/raw?...&format=jsonl\|csv` but `GET /export/results?...&format=csv` — different format sets per endpoint, read literally. | Both endpoints accept `format=jsonl\|csv`, default `jsonl`. | This milestone's own dispatch brief states the shared param list as `(params source_id, from, to, key_prefix, format=jsonl\|csv)` for the whole batch, not narrowed per endpoint, and DP-033 D3's prose ("JSONL default... plus a CSV option") reads as a general export principle rather than a Raw-only one. The two source documents disagree on this point; the brief's own literal instruction is followed as the more specific, more recent one. `GET /export/results?format=csv` (no `format`, or `format=csv`) still produces exactly the CSV shape D3 names, so nothing the plan's literal query example shows is broken — it is a strict superset (JSONL is additionally available). Flagged here per this milestone's own "flag deviations" instruction rather than left silent. |
| 2 | The brief does not say a schedule may only be written on a `collector` source. | `PUT /sources/{id}/schedule` requires `kind == "collector"` (409 otherwise). | DP-033 D5's own text: "normalization stays operator-triggered, with an optional schedule" — the optional normalization hook is explicitly **not** built by this batch ("정규화는 수동 유지+선택 스케줄 훅만"). A schedule accepted on a normalizer or importer would be a row `apps/scheduler` could build an `addon:<id>` handler string against, but the resulting job would never mean "collect" — the same "a route that looks like it works and does not" reasoning `apps/domain/api.py`'s own docstring already gives for `/collect`/`/import`. |
| 3 | The brief does not specify whether a schedule on a source the operator has since **disabled** should still fire. | `apps/scheduler/store.py`'s `DUE_SOURCE_IDS`/`LOCK_SCHEDULE` both require `src.enabled`, not only `s.enabled`. | A job created against a disabled source is a job nothing can meaningfully process (the same "a route that looks like it works and does not" concern) and there is no operator-facing indication of why it never completes. Reversible: removing `and src.enabled` is a one-line change if a future packet decides otherwise. |
| 4 | The brief does not specify what happens to `next_run_at` when a pass is suppressed as a duplicate. | A suppressed pass leaves `next_run_at`/`last_run_at` untouched — no advance, no record of a run. | The row stays "due" so the next poll retries once the in-flight job clears, rather than silently going quiet for a full interval while nothing actually ran. Tested (`tests/test_scheduler.py::TestDuplicateSuppression::test_once_the_in_flight_job_clears_a_forced_due_pass_creates_one`): closing out the blocking job and re-polling (with `next_run_at` forced back into the past, since a suppressed pass never advanced it) creates exactly one job. |
| 5 | — | `HANDLER_PREFIX`/`SOURCE_ID_FIELD` are re-declared as local constants in `apps/scheduler/__main__.py` rather than imported from `apps/domain/api.py`. | Mirrors `apps/domain/api.py`'s own stated convention for the same constants ("Mirrored here, not imported — `addon_host` does not exist in this tree yet"), extended to a third consumer. No P1-side layering guard forbids the import (`tests/environment/test_addon_layer_direction.py` scans only `experiments/integrated-p0/`), so this is a style choice for keeping a background process from depending on a FastAPI route module, not a constraint violation either way. Both copies must be kept in sync; noted in both modules' docstrings. |

## (d) What was not built

- **The optional normalization schedule hook** DP-033 D5 mentions ("scheduling added only as
  an option on top of" normalization's manual-trigger path) is explicitly out of this
  batch's scope per the batch brief itself and is not built. `PUT /sources/{id}/schedule`
  refuses a normalizer source (deviation 2 above) rather than silently accepting a row that
  would do nothing.
- **`apps/scheduler`'s collect job stays `PENDING` until M3 lands `addon_host`.** Same gap
  `apps/domain/api.py`'s own docstring already records for `POST /snapshots/{id}/normalize`
  — nothing in this tree yet registers a handler for the `addon:*` prefix.
- **The 10,000-row streaming test measures correctness and completion time, not process
  RSS.** `tests/test_export.py::TestLargeExportStreams` confirms every one of 10,000 rows
  arrives in order and uncorrupted, and that the request completes (in this run, well under
  a second server-side). The "bounded memory" claim itself (H3, DP-033) rests on the
  implementation using a named server-side PostgreSQL cursor with `itersize=500` and never
  calling `fetchall()` (`apps/domain/export.py`'s own docstring) — an inspectable code
  property — rather than on a live memory measurement this test suite does not take.

## (e) Test evidence

`[측정]` 2026-08-21, unsandboxed, `COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434
COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime COSMA_TEST_DB=cosmai_test_3
../scripts/with-secret-source.sh uv run python -m pytest -q` (run from `apps/`):

- Baseline (M2 tree, before any M6 change, same port): **579 passed**.
- After 6a+6b: **607 passed** (+28: 8 in `tests/test_domain_api.py::TestScheduleReadAndWrite`,
  8 in `tests/test_scheduler.py`, 12 in `tests/test_export.py`).
- `cd apps && uv run mypy --strict .` — clean, 57 source files.
- `cd apps && uv run ruff check .` — clean.
- Root guard: `.venv/bin/python -m pytest tests/environment -q` (run from the repository
  root against this worktree's `apps/` tree) — **82 passed**, including
  `test_apps_never_imports_experiments` (no new file under `apps/` imports `experiments`)
  and the add-on layer-direction guard (unaffected — it scans only
  `experiments/integrated-p0/`, which this milestone did not touch).

Scenario-level evidence for the batch brief's named test list:

- **due → job created; next_run advance**:
  `test_scheduler.py::TestADueScheduleWakesItsSource::test_a_due_enabled_schedule_creates_a_collect_job_and_advances_next_run_at`.
- **duplicate suppressed while pending/running**:
  `test_scheduler.py::TestDuplicateSuppression::test_a_second_pass_is_suppressed_while_a_job_is_still_in_flight`
  (parametrized over both `PENDING` and `RUNNING`), plus a positive control
  (`test_a_terminal_job_does_not_suppress_the_next_pass`) confirming a `SUCCEEDED` job does
  *not* suppress — the suppression is specifically about in-flight work, not about the
  source having ever run.
- **disabled ignored**: `test_scheduler.py::TestDisabledIsIgnored` — both a disabled
  schedule and a schedule on a disabled source.
- **PUT/GET roundtrip**: `test_domain_api.py::TestScheduleReadAndWrite`, including the
  unconfigured-schedule shape, the 404 on an unregistered source, the 409 on a non-collector,
  and the "editing the interval does not reset `next_run_at`" case this milestone's own
  `UPSERT_SCHEDULE` docstring states as a deliberate choice.
- **range filters honored**: `test_export.py::TestRawExportScopeFilters` (`from`/`to` on
  `emitted_at`, `key_prefix` as a literal prefix, not a `LIKE` wildcard).
- **10,000-row streaming test, bounded memory**: `test_export.py::TestLargeExportStreams` —
  see (d)'s caveat on what "bounded memory" evidence this actually is.
- **CSV escaping, RFC4180 round trip**: `test_export.py::TestRawExportCsv::test_csv_escapes_quotes_and_newlines_and_round_trips`
  — a payload containing embedded quotes, a newline, and a comma, read back through
  Python's `csv.reader` and compared byte-for-byte against the original.
- **empty result → valid empty file**: `test_export.py`'s
  `test_an_empty_source_is_zero_lines_not_an_error` (JSONL, raw),
  `test_an_empty_source_is_a_header_only_file` (CSV, raw), and
  `test_an_empty_source_is_a_header_only_csv_and_zero_jsonl_lines` (results, both formats).

## (f) Manual verification against a real API process

Before the automated suite above existed, both new route groups and the scheduler process
were exercised by hand against `cosmai_test_3` on `:5434`: `PUT`/`GET
/sources/{id}/schedule` round-tripped through a real in-process `TestClient`; `/export/raw`
in both formats correctly spliced a JSON payload verbatim (JSONL) and RFC4180-escaped a
payload containing embedded quotes and a newline (CSV); a missing source 404'd before any
streaming began; `python -m scheduler --once` against a seeded due schedule created exactly
one `addon:collector.smoke` job and advanced `next_run_at`; a second `--once` pass against
the same still-`PENDING` job suppressed the duplicate and logged
`scheduler.duplicate_suppressed`. These runs are not re-included as saved output — the
automated tests above cover the same ground reproducibly — but are recorded here as the
evidence the automated suite was written *against*, not invented after the fact.
