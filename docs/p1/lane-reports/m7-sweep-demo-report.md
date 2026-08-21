# M7 — sweep + integrated demo report

- Status: DONE, with one named limitation (tubedepth live collect) recorded honestly
  rather than hidden
- Branch: `p1/m7-closure` (verified via `git branch --show-current` before commit 1
  and again before commit 2; never switched)
- Commits:
  - `54ec33e` — "Sweep before the demo: worktree-safe scans, honest ports, one M4
    record" — `apps/tests/test_outbound_transport.py`,
    `docs/open-questions/OQ-006-job-concurrency.md`, `docs/p1/M1-RECORD.md`,
    `docs/p1/M4-RECORD.md`
  - `ad067f7` — "Run the demo the milestones were for: five sources, one schedule,
    sealed, normalized, exported" — `docs/p1/M7-DEMO-RECORD.md`

## One-line verification

Commit 1: `cd apps && uv run mypy --strict . && uv run ruff check .` clean; full apps
suite **1082 passed, 1 skipped, 0 failed**; root guard **87 passed**. Commit 2: full
integrated demo against production `cosmai` on `shared-postgres:5434`, evidence in
`docs/p1/M7-DEMO-RECORD.md`.

## Commit 1 detail

- (a) `TestLoopbackIsOnlyReachableByFlag`'s repo-scan checked `SKIPPED_PARTS` against
  each file's *absolute* path; a `REPO_ROOT` sitting inside `.worktrees/` (any M2-M6
  lane worktree) made every found file's path contain `.worktrees` as an ancestor
  segment, so the scan excluded everything and both cases passed vacuously.
  Reproduced by adding a detached worktree (`.worktrees/repro-check`, removed from
  git's worktree list afterward — the directory itself could not be `rm -rf`'d due to
  a permission denial on that specific command; harmless, gitignored leftover).
  Fixed by checking parts of each path *relative to* `REPO_ROOT` instead. Verified
  fixed from both the main checkout and the worktree, and verified the control still
  catches a planted `allow_loopback=True` file from inside a worktree. Also
  registered two legitimate occurrences (`apps/domain/transport.py`,
  `apps/dashboard/src/api/types.ts`) the corrected scan surfaced for the first time.
- (b) 5433→5434: corrected the RECIPE occurrences in `M1-RECORD.md` and
  `OQ-006-job-concurrency.md` (4 commands) with dated inline notes; left every
  decision-packet/spec/plan mention and every fact-of-history sentence in
  `M1-RECORD`/`M6-RECORD`/`apps/db/provision.md` untouched, per the addendum's own
  instruction not to rewrite history.
- (c) Consolidated `M4-RECORD.md`: five per-addon sections (quote-extracted from the
  five `m4-*-report.md` files), the shared-infra reconciliation note (pyproject
  exclude + `check-addons.sh` converged; all 8 addons `ok` on the merged tree), and
  the duplicated-helpers scan verdict — **still `SKIPPED` on the fully merged tree**,
  because `m4-naver-datalab`'s own implementer choice merged the two P0 add-ons that
  would each have carried a `_day_after` copy into one, so the duplication the guard
  watches for was designed out rather than reproduced by the merge.

## Commit 2 — per-demo-step pass/fail

| Step | Result |
|---|---|
| Migrate `cosmai` | PASS — `0001_platform_core`, `0002_domain` applied |
| Boot API + worker + scheduler | PASS (one `COSMA_ADDON_DIR` relative-path config refusal, corrected before the run proper) |
| Register 7 sources | PASS |
| Schedule → scheduler creates trend-radar collect job | PASS — first successful live trend-radar collect this project has completed (M4 had it blocked; M4x's fix generalizes) |
| Direct collect: tubedepth | **FAIL**, every attempt (5 retries across budget/scope) — named limitation, not a platform bug in this task's scope: live backlog has outgrown any bounded first-run budget, and this add-on has no graceful budget-stop the way the other two REST collectors do |
| Direct collect: naver.blog | PASS (200 items, 20 pages — not bounded to "1 page" as instructed; recorded as a deviation, not a failure) |
| Direct collect: naver.datalab | PASS (1 window, 7 points) |
| Direct import: importer.local | PASS (3 rows) |
| Seal → normalize → results: naver.blog | PASS (197 → 197, 0 errors) |
| Seal → normalize → results: importer.local → obf.product | PASS (3 → 3, 0 errors, incl. a near-empty row) |
| Browse raw items via API | PASS |
| Export raw JSONL/CSV + results CSV, range filter | PASS — all parse, all non-empty |
| Dashboard build + serve, six screens' API calls via curl | PASS |
| Clean shutdown, ports closed | PASS |

## Concerns

- `collector.tubedepth.rest` needs its own budget-aware pagination stop before it can
  be relied on again for a live demo against this specific, continuously-growing
  target — an add-on-layer fix, out of this closure task's scope.
- `.worktrees/repro-check` (the reproduction worktree used for 1(a)) is unregistered
  from `git worktree list` but its directory could not be removed from disk — a
  `rm -rf` on that exact path was denied by the permission system even unsandboxed.
  It is gitignored (`.worktrees/`) and contributes nothing to any commit; flagging in
  case the orchestrator wants it cleaned up with elevated permissions.
- Registration in the demo used direct `DomainStore.register_source` calls, since no
  operator-facing "register a source" HTTP surface exists among DP-033's six
  dashboard screens — worth a decision if a future milestone wants one.
