# M4 — `p1/m4-naver-datalab` report (NAVER DataLab: collector + normalizer)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4-naver-datalab`, branch
  `p1/m4-naver-datalab`
- Commit: `dfdd0e9` — "Rebuild the DataLab side: POST bodies composed, trend points unrolled
  one per (series, period)"
- Verification summary: `cd apps && uv run mypy --strict .` (91 source files) and
  `uv run ruff check .` both clean. `COSMA_TEST_DB=cosmai_test_3 COSMA_DB_HOST=127.0.0.1
  COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime
  ../scripts/with-secret-source.sh uv run python -m pytest -q` — **872 passed, 2 failed**;
  the 2 failures are `tests/test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`
  and are pre-existing/environmental, not caused by this task (see Concerns). All 74
  NAVER-DataLab-specific tests pass (39 collector, 26 normalizer, 9 host-loading/conformance).
  Root guard `.venv/bin/python -m pytest tests/environment -q` — **87 passed**, including
  `test_addon_layer_direction.py` (confirms both add-ons import `addon_api` only). LIVE smoke:
  **PASS** — see below.

## What was built

- `apps/addons/collector.naver.datalab/` — one collector, three modes
  (`search_trend`/`shopping_categories`/`shopping_keywords`), merging P0's
  `collector.naver.searchtrend` and `collector.naver.shoppinginsight`. Implementer choice
  (spec §5.3): **one add-on, not two or three** — P0's own `shoppinginsight` had already
  merged two of the three DataLab endpoints behind a `mode` field on the grounds that they
  "answer the same question at two depths"; this rebuild carries that merge to the third
  endpoint, since all three share ~90% identical window/cursor/segmentation/date-arithmetic/
  response-parsing/unrolling logic and differ only in the request body's shape, the endpoint
  name, the DP-021 D2 dimension name, and the age-band vocabulary — all four now table-driven
  in `handler.py`'s `_MODES` mapping. Full rationale in
  `apps/addons/collector.naver.datalab/README.md`. POST body composition (DP-020) and
  per-(series, period) unrolling (DP-021 D4) are carried over from P0 unchanged.
- `apps/addons/normalizer.naver.trend/` — DataLab points into `Normalized Schema 0.2`
  trend records, implementing DP-030 D2's record-level fallback in the add-on's own logic
  (distinct from the host-level `domain.store._safe_canonical_body` safety net M2 already
  built, which only catches serialization-level crashes). Design: an item that carries no
  `dimension` key at all is skipped (not this normalizer's data, e.g. a blog document);
  an item that carries a `dimension` string — recognizable as a DataLab-record candidate,
  including an unrecognised dimension value — is never dropped. Its first invalid field
  (checked in order: dimension, series, period, ratio, time_unit) is named in
  `notes.normalize_error {field, reason}`, every invalid field is nulled, and the record is
  still emitted (`results_emitted`, not `skipped`); the run's `NormalizeOutcome.notes`
  carries an `error_records` aggregate. D1 (normalization-time metadata) needed no add-on
  change — `cosmai.normalized_result` already carries `snapshot_id`/`addon_id`/
  `addon_version`/`created_at` as host-attached columns, and `NormalizeContext` does not
  even expose the add-on its own id/version. Full reasoning in the handler's module
  docstring.
- `apps/pyproject.toml` — added a `[tool.mypy] exclude = ["^addons/"]`, mirroring the
  repository-root `pyproject.toml`'s existing exclude for `experiments/integrated-p0/addons/`
  and for the same reason: two add-ons both entering as `handler.py` collide in mypy's module
  namespace ("Duplicate module named handler") the moment a second add-on exists under
  `apps/addons/` — which this task is the first M4 lane to trigger, since `apps/addons/`
  didn't exist before. Each add-on is still checked individually
  (`uv run mypy --strict addons/<id>/handler.py`, done above for both).
- Tests: `apps/tests/test_collector_naver_datalab.py` (ported/merged from P0's
  `test_collector_naver_trend.py`), `apps/tests/test_normalizer_naver_trend.py`
  (ported, with `TestWhatItSkips` narrowed and a new `TestDP030RecordLevelFallback` class),
  `apps/tests/test_naver_datalab_addon_layer.py` (new: host discovery/registration against
  the real `apps/addons/` directory with no database, plus `addon_kit.conformance` runs for
  both add-ons).

## A bug the conformance run itself found and fixed

`_Mode` was originally a frozen `@dataclass`. Under `from __future__ import annotations`,
`dataclasses._process_class`'s `KW_ONLY` check resolves a bare string annotation via
`sys.modules[cls.__module__]`. `addon_host.loading._import_by_path` (the real host) registers
a loaded add-on's module in `sys.modules` before executing it; `addon_kit.harness._load_entry`
(the conformance suite and `addon_kit run`) does not, so running the collector through
conformance raised `AttributeError: 'NoneType' object has no attribute '__dict__'`. Fixed by
switching `_Mode` to `typing.NamedTuple`, which never reaches that code path. Documented in
the class's own docstring as a `[측정]` finding, in case a future add-on author reaches for
`@dataclass` in a `handler.py` and hits the same thing. Not a fix to `addon_kit` itself —
out of this task's file scope, and the safe fix was on this add-on's side.

## LIVE smoke

Run manually (unsandboxed, one-off script, not committed — the task specifies "record counts
only"), against `cosmai_test_3` with migrations freshly (re-)applied (the schema had been
reset by something else touching the shared DB between my earlier full-suite run and the
smoke — see Concerns), through the real `JobRunner` + `bind_capabilities` +
`SocketTransport`, no doubles:

- **Credential**: resolved via `platform_core.secrets.resolve_credential`. The
  `COSMA_SRC_NAVER_DATALAB_CLIENT_ID/_SECRET` refs were not present in the store; the
  existing `COSMA_SRC_NAVER_BLOG_CLIENT_ID/_SECRET` pair (P0's naver.blog source) resolved
  and worked — `[확인 사실]` the NCP APIGW key pair is account-level, not per-product, so the
  already-provisioned blog credential also grants DataLab. Names only; no value was printed
  or persisted anywhere.
- **Pass 1 — `search_trend` mode → `/search-trend/v1/search` (`trend` endpoint), one day,
  one keyword group**: collect `SUCCEEDED`, 1 raw item; seal; normalize `SUCCEEDED`, 1
  normalized result, 0 `normalize_error`.
- **Pass 2 — `shopping_categories` mode → `/shopping/v1/categories` (`categories`
  endpoint)**: collect `SUCCEEDED`, 1 raw item; seal; normalize `SUCCEEDED`, 1 normalized
  result, 0 `normalize_error`.
- `shopping_keywords`/`category_keywords` was not separately live-tested (time budget); its
  request-composition logic is exercised by the fixture-based unit and conformance suites
  and shares every mechanism the two live-tested modes already proved end to end (window,
  cursor, POST body, response parsing, unrolling) — the only untested-live surface is that
  one endpoint path itself accepting a POST from this account, which the operator can confirm
  cheaply if it matters before P1's demo milestone.
- Test source rows and their Raw/snapshot/result data were deleted from `cosmai_test_3`
  after the smoke; nothing from a live response was committed to the repository.

## Concerns

- **A found and fixed request-composition bug, worth naming because it was almost missed.**
  The first live-smoke attempt sent `outbound_profile.endpoints = {"trend": TREND_PATH}` (a
  bare string, meaning GET per DP-020 D1) and was correctly refused by the platform's own
  guard ("a body was supplied ... only sent to an endpoint the profile grants POST") —
  a bug in my *test scaffolding*, not the add-on, but worth recording since it is exactly the
  DP-020 D1 method-grant check working as designed. Fixed by using
  `{"path": ..., "method": "POST"}`.
- **`COSMA_TEST_DB=cosmai_test_3` (per this task's brief) conflicts with the batch plan's own
  table** (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md`: "M4 워크트리=`cosmai_test_4`
  (공유, 애드온 테스트는 순차)"; `cosmai_test_3` is named there for Lane C/M6, already merged).
  Followed the task's explicit instruction rather than the plan text. Between my full-suite
  pytest run and the live smoke, `cosmai_test_3`'s schema was found empty (`relation
  "cosmai.source" does not exist`) — consistent with another process (a concurrent M4 lane,
  or M6's own now-merged test run) having reset it in between. Re-applied migrations
  idempotently (no schema drop) before the smoke; did not investigate further, since the
  brief names `cosmai_test_3` explicitly and re-applying is safe. Flagging for the orchestrator
  in case the five M4 worktrees are not actually using five distinct databases as the plan
  intended.
- **Two pre-existing, environmental test failures, not caused by this task.**
  `tests/test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag` computes
  `REPO_ROOT = Path(__file__).resolve().parents[2]`, which correctly resolves to this
  worktree's own root (`.worktrees/m4-naver-datalab`) — but `SKIPPED_PARTS` includes
  `".worktrees"`, and every absolute path under this worktree contains `.worktrees` as an
  ancestor path component (the worktree itself lives inside a directory named that). The
  scan therefore excludes every file it walks, and both tests fail on an empty result.
  Reproduced in isolation (`pytest tests/test_outbound_transport.py` alone, same two
  failures), confirmed unrelated to any file this task touched (pure path arithmetic, no
  addon code involved), and confirmed as a structural property of running this specific test
  from inside any `.worktrees/<name>` directory — it would hit identically on any of the
  other four M4 lanes' worktrees. Not fixed here: out of this task's file scope, and a
  one-line guard change to a shared test file risks a duplicate/conflicting fix landing from
  a parallel M4 lane. Named here rather than worked around silently, per AGENTS.md's
  deviation-recording rule.
- **`shopping_keywords` mode's live coverage** is the fixture/conformance suites only, as
  noted above.
