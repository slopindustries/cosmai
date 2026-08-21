# M4 — collector.naver.blog + normalizer.naver.blog report

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4-naver-blog`, branch `p1/m4-naver-blog`
- Commit: `e87a00e` — "Rebuild the NAVER blog pair: collect what the profile grants, normalize what survives alone" —
  `apps/addons/collector.naver.blog/{addon.toml,handler.py,README.md}` (copy-adapted, logic
  unchanged from P0); `apps/addons/normalizer.naver.blog/{addon.toml,handler.py}` (copy-adapted,
  DP-030 D2 per-record fallback replacing P0's skip-and-count); `apps/tests/test_collector_naver_blog.py`
  (P0's fixture cases ported + conformance + real-directory discovery, 41 tests);
  `apps/tests/test_normalizer_naver_blog.py` (P0's cases ported, `TestWhatItRefusesToNormalize`
  replaced by `TestPerRecordFallback`, + conformance + real-directory discovery, 27 tests);
  `apps/pyproject.toml` (`[tool.mypy] exclude = ["^addons/"]`, new — two add-ons both landing
  at once collide in mypy's module namespace immediately, not hypothetically); `apps/scripts/check-addons.sh`
  (new, mirrors the root's own per-addon checker).

## Verification

- `cd apps && uv run mypy --strict .` — clean, 90 source files (`addons/` excluded).
- `cd apps && ./scripts/check-addons.sh` — `collector.naver.blog ok`, `normalizer.naver.blog ok`.
- `cd apps && uv run ruff check .` — clean.
- `apps/tests/test_collector_naver_blog.py` + `test_normalizer_naver_blog.py` +
  `test_addon_conformance.py` — **79 passed**.
- `apps/tests/test_addon_host.py` — **46 passed** (host-loading/version-gate baseline unaffected).
- Full `apps` suite, unsandboxed, real DB (`COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434
  COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime ../scripts/with-secret-source.sh
  uv run python -m pytest -q`) — **860 passed, 2 failed** (both pre-existing, out of scope —
  see Concerns).
- Root guard: `.venv/bin/python -m pytest tests/environment -q` — **87 passed**.
- **LIVE smoke (unsandboxed), through the real host worker, one real NAVER API Hub call**:
  registered `naver-blog-live-smoke` with the P0-shaped `outbound_profile` (host
  `naverapihub.apigw.ntruss.com`, endpoint `blog` → `/search/v1/blog`, `max_pages=1`,
  credential parts `COSMA_SRC_NAVER_BLOG_CLIENT_ID`/`COSMA_SRC_NAVER_BLOG_CLIENT_SECRET` —
  both already present in `~/.config/cosmai/env`, confirmed present without reading their
  values), ran one collect job through `JobRunner`+`addon_host`+`domain.transport.SocketTransport`
  against `cosmai_test`, then sealed and normalized the result. **SUCCEEDED**: collect job
  `SUCCEEDED`, 1 raw envelope, 10 raw items; normalize job `SUCCEEDED`, 10 normalized results,
  0 carrying `normalize_error`. Query `수분크림`, `sort=date`, `display=10` — the same
  parameters P0's own `test_naver_real_data.py` used. Smoke script was a throwaway (not
  committed); source rows it wrote live only in `cosmai_test`, which the test session's own
  `_reset_schema` fixture wipes on the next `pytest` run.

## Concerns

- **`apps/pyproject.toml`'s `addons/` mypy exclude and `apps/scripts/check-addons.sh` are new,
  shared infrastructure, not scoped to this one add-on pair.** Landing `collector.naver.blog`
  and `normalizer.naver.blog` together in one worktree is what first makes "two add-ons both
  define `handler.py`" true here — the same collision every other M4 lane with 2+ add-ons will
  independently hit and (per the sibling reports already in this directory) has already hit and
  fixed the same way. These will need reconciling — they should be identical or near-identical —
  when M7 merges every M4 lane's `apps/addons/*` into one tree.
- **Task-brief vs. plan test-DB mismatch.** My task brief named `COSMA_TEST_DB=cosmai_test`;
  `docs/superpowers/plans/2026-08-21-m2-m7-batch.md`'s own §공통 제약 assigns the M4 worktrees
  `cosmai_test_4` (shared, sequential) specifically to avoid schema-reset races with Lane A/other
  concurrent runs (OQ-006). I followed the task brief as given rather than silently switching
  databases; every gate above ran cleanly on `cosmai_test` with no observed collision, but if
  another M4 lane's pytest session resets `cosmai_test`'s schema concurrently with this one, the
  race OQ-006 already names is exactly what would surface. Flagging rather than resolving, since
  which database this lane should use is not mine to redecide from inside a task packet.
- **Two pre-existing, out-of-scope test failures**, identical to what sibling M4 lanes
  independently found and reported: `tests/test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`
  computes `REPO_ROOT = Path(__file__).resolve().parents[2]`, which lands on the worktree's own
  root when run from `.worktrees/<name>/apps/`, then skips every file whose `path.parts` contains
  `.worktrees` — which is every file, since the worktree's own absolute path contains that
  segment. Confirmed structural via `git stash -u` (fails identically with none of this task's
  changes present) and not caused by this diff, which never touches `domain/outbound.py` or that
  test file; not repaired here.
- **DP-030 D2 design choice, stated explicitly for review.** Two distinct failure shapes: a
  payload that is not valid JSON/not an object nulls every derived field (nothing to preserve);
  a payload that parses but lacks a usable `link` keeps every field it *could* derive
  (`title`/`excerpt`/`published_at`/`author`) and nulls only `external_id`/`url`. Both are one
  `NormalizedResult` with one `notes.normalize_error {field, reason}` entry, never a skip, and
  `NormalizeOutcome.notes["error_records"]` is the run-summary aggregate D2's text asks for
  (`skipped` is always `0` for this add-on now). This is a local schema-population choice, not a
  contract deviation — no doc pins the exact shape of a fallback record beyond "nulls +
  `normalize_error`, run continues."
