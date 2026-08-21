# M4x — platform-gaps fix report

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4x`, branch
  `p1/m4-platform-gaps`, cut from `dev` after `p1/m4-tubedepth` merged (`a87ff08`).
- Commits:
  - `f36e63b` — "Grant loopback HTTP by an explicit per-source flag, and path
    parameters by a declared regex" — `apps/domain/outbound.py`,
    `apps/domain/transport.py`, `apps/tests/test_outbound_policy.py`,
    `apps/tests/test_outbound_transport.py`.
  - `6c0ae21` — "Update the tubedepth adapter's README to the real mechanisms it
    named" — `apps/addons/collector.tubedepth.rest/README.md` (no `handler.py`
    change needed; its `context.fetch` call was already written to the intended
    shape).
  - `942d786` — "Open the two doors the adapters need: loopback HTTP by flag, paths
    by validated template" — `docs/p1/M4-RECORD.md` (new, platform-gaps section).

## Verification (one-line each)

- Gap 1 (loopback HTTP by flag) and Gap 2 (path templates): both implemented in
  `domain/outbound.py`/`domain/transport.py`, each validated at the profile layer
  and again at the transport/containment layer (belt-and-suspenders), with new
  unit tests (`TestScheme`, `TestPathTemplates`, `TestPathTemplateDeclaration`,
  `TestPlainHttpForLoopback`) — all pass, no socket needed for the policy half, a
  real plain-HTTP loopback server for the transport half.
- `mypy --strict .` and `ruff check .`: clean on the whole `apps/` tree.
- Full `apps` suite: 1003 passed, 2 pre-existing failures unrelated to this diff
  (`TestLoopbackIsOnlyReachableByFlag`'s `.worktrees` path-collision, first
  recorded by `m4-tubedepth-report.md`, reproduced identically before this task's
  diff — confirmed by re-running the same two cases against `a87ff08` directly).
- Conformance: `TestConformance::test_the_add_on_is_conformant` for
  `collector.tubedepth.rest` still passes (`tests/test_addon_collector_tubedepth.py`,
  20/20 passed) — CONFORMANT, unchanged.
- Root guard: `.venv/bin/python -m pytest tests/environment -q` — 87 passed (root
  `.venv` did not exist in this worktree; `uv sync` at the worktree root created
  it, same one-time step the tubedepth lane's own report names).
- **Tubedepth live smoke: SUCCEEDED.** One bounded `collect()` through the real
  host worker (`platform_core.worker.Worker` via
  `addon_host.worker.capability_registry`, real `SocketTransport`, real
  `X-API-Key` credential resolved from `~/.config/cosmai/env`, a real source row
  registered in `cosmai_test_5` and fully cleaned up afterward — nothing left in
  the database). Bounded to a real ~3-minute slice of the live feed via the
  add-on's own watermark (the target's full retention window is far larger than
  one job's `max_pages` budget affords in a single pass, which the platform's
  own pre-existing page-limit guard confirmed independently — see Concerns).
  **Counts:** 5 `artifacts_list` pages, 224 `artifact_payload` dereferences (every
  one a real plain-HTTP request to `127.0.0.1:8080` admitted by `allow_loopback`,
  with `{digest}` validated against `^[0-9a-f]{64}$` and substituted by
  `domain.outbound.resolve`), 229 `raw_envelope` rows, 224 `raw_item` rows,
  watermark advanced `03:09:25.090879Z` → `03:12:25.090879Z`, and (called
  directly, the way an operator action would, since sealing is not part of a
  collect job — DP-019 D6) `domain.store.seal_snapshot_from_raw` sealed a
  224-item snapshot. Full detail: `docs/p1/M4-RECORD.md` and this addon's
  README.md, "M4x — the two platform gaps this add-on named, closed".

## Concerns

- **The live tubedepth instance moved version again**, `1.0.3` (the earlier
  finder's measurement) → `1.1.0` (this task's smoke), per `/healthz`. The
  artifacts-feed surface this adapter depends on is unchanged between them, same
  conclusion the earlier `1.0.0`→`1.0.3` move reached. Recorded in the README and
  `M4-RECORD.md` rather than silently absorbed.
- **A first full-backfill attempt (no watermark) hit the platform's own
  pre-existing `max_pages` guard**, not either gap: with `max_pages=60` the job
  failed `PLATFORM_PERMANENT`/`PAGE_LIMIT_EXCEEDED` ("asked for a 61st fetch"),
  proving both mechanisms were already making real successful HTTP-over-loopback
  and path-template-substituted requests before an unrelated, correctly-working
  control stopped it. The retention window holds far more than one job's budget
  affords in a single from-scratch pass; a live `source` row would set
  `max_pages` accordingly or rely on its own watermark narrowing every run after
  the first, which is what the successful smoke run demonstrates.
- **The smoke script seeded its own `since` watermark** (via a real, throwaway
  first job attempt whose `id` satisfies `source_cursor.updated_by_attempt`'s
  FK, then a directly-inserted `source_cursor` row) rather than letting a
  from-scratch backfill run to completion, because a full backfill would need
  far more than 60 requests/minute's worth of time to finish in one job attempt.
  This is a smoke-script accommodation for demonstrating the *steady-state*
  incremental behavior a real scheduled source would actually exercise on every
  run after its first — not a platform or add-on change, and not something a
  real operator-registered source needs to do (its own first run's `max_pages`
  is an operator-set budget, and every run after it reads a real watermark
  automatically).
- **Deviations recorded explicitly in `docs/p1/M4-RECORD.md`, per the task
  packet's own instruction:** `scheme` is profile-wide, not per-endpoint; HTTP
  never leaves loopback (checked twice, independently); a redirect off a
  loopback-HTTP or a templated endpoint is refused outright rather than
  re-validated (`ALLOWED_SCHEMES`/`check_redirect` untouched); path-template
  validation is exactly as strong as the profile's own declared regex plus the
  pre-existing segment containment, no stronger — a permissive regex is not
  independently caught by anything beyond dot-segment/encoded-separator
  detection.
- **Trend-radar has merged into `dev`** (`db9780f`, after this branch was cut).
  Per the task brief, left untouched — its own re-verification is M7's, not
  this task's, and `dev` was not merged into this branch.
- Nothing else outstanding; the worktree's git status is clean and all three
  commits are on `p1/m4-platform-gaps`, not pushed or merged.
