# Lane C — M6 batches 6a/6b report (scheduler, streaming export)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m6`, branch `p1/m6-ops`
- Commits:
  - `10a3a00` — "A scheduler that wakes sources on time and refuses to pile up jobs" (batch 6a)
  - `f1a0bbc` — "Export raw and normalized rows as a stream, in the shapes the dashboard
    already links to" (batch 6b)
- Verification summary: `cd apps && uv run mypy --strict .` (57 source files) and
  `uv run ruff check .` both clean; `COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434
  COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime COSMA_TEST_DB=cosmai_test_3
  ../scripts/with-secret-source.sh uv run python -m pytest -q` — **607 passed** (579 M2
  baseline + 28: 8 schedule-API, 8 scheduler-process, 12 export); gates re-run and green
  independently at the 6a checkpoint too (595 passed) before that commit. Root guard
  `.venv/bin/python -m pytest tests/environment -q` — **82 passed** at both checkpoints. Full
  detail, deviations ledger, and per-scenario test mapping in `docs/p1/M6-RECORD.md`.

## Concerns

- **Mid-milestone infrastructure swap.** The shared Postgres container moved from
  `127.0.0.1:5433` to `127.0.0.1:5434` (`shared-postgres`) partway through this work, per the
  orchestrator's notice; all commands above and both commits' gates used `:5434`. Noted in
  `docs/p1/M6-RECORD.md` (a); the `apps/db/provision.md` addendum documenting the swap lives
  on `dev` (commit `ea7f535`) and was not merged into this branch, as instructed.
- **Flagged deviation:** both export endpoints accept `format=jsonl|csv` (default `jsonl`);
  the plan's own §신규 API line shows `/export/results` with only `format=csv`. The batch
  brief's own param list states `format=jsonl|csv` for the whole batch without narrowing per
  endpoint, so that instruction was followed — reasoning and the three other flagged
  deviations (schedule restricted to `collector` sources; a schedule on a disabled source is
  ignored; a suppressed scheduler pass does not advance `next_run_at`) are in
  `docs/p1/M6-RECORD.md` (c).
- **Known gap, not a defect:** a scheduler-created `addon:<addon_id>` job stays `PENDING`
  until M3 lands `addon_host` — the same gap `domain.api`'s own docstring already records for
  `POST /snapshots/{id}/normalize`.
- The 10,000-row streaming test verifies correctness and completion, not measured process
  memory; the "bounded memory" claim rests on the named-server-side-cursor implementation
  itself (never `fetchall()`), stated as such rather than smoothed over.
