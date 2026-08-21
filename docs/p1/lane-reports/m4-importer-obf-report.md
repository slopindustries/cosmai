# M4 — importer.local.jsonl + normalizer.obf.product report

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4-importer-obf`, branch `p1/m4-importer-obf`
- Commit:
  - `1748019` — "Rebuild the importer and the product normalizer: rows abstain, never abort" —
    `apps/addons/importer.local.jsonl/{addon.toml,handler.py}` and
    `apps/addons/normalizer.obf.product/{addon.toml,handler.py}` (copy-adapted verbatim from
    P0, plus DP-030 D2's `_build_body` per-field fallback in the normalizer); six new test
    files (`test_importer_local_jsonl.py`, `test_normalizer_obf_product.py`,
    `test_addon_conformance_m4.py`, `test_addon_host_loading_m4.py`,
    `test_addon_duplicated_helpers.py`, `test_importer_obf_end_to_end.py`); `apps/pyproject.toml`
    (`[tool.mypy] exclude = ["^addons/"]`, new) and `apps/scripts/check-addons.sh` (new),
    mirroring the repository root's own documented per-addon check model since this is the
    first M4 lane to populate `apps/addons/`.
- Verification: `cd apps && uv run mypy --strict .` clean (94 source files); `uv run ruff check .`
  clean; `apps/scripts/check-addons.sh` — both add-ons `ok` individually; full `apps` pytest
  suite unsandboxed against `cosmai_test_6` on `shared-postgres:5434` —
  **880 passed, 6 skipped, 2 failed** (both pre-existing and out of scope, see Concerns);
  root guard `.venv/bin/python -m pytest tests/environment -q` — **87 passed**.

## Concerns

- **Two pre-existing, out-of-scope test failures block a fully clean full-suite run, and are
  not caused by this task.** `tests/test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`
  (both its cases) computes `REPO_ROOT = Path(__file__).resolve().parents[2]`, which resolves
  to the *worktree's own root* when run from inside `.worktrees/<name>/apps/`. Its
  `SKIPPED_PARTS` exclusion list includes `.worktrees` to keep the scan from double-counting
  sibling lane worktrees — but the worktree's own absolute path necessarily contains
  `.worktrees` as a path segment of itself, so `not any(part in SKIPPED_PARTS for part in
  path.parts)` is `False` for every file the scan finds, and both tests fail with an empty
  result. `[측정]` Reproduced identically, byte-for-byte, in an untouched sibling worktree
  (`m4-naver-blog`, verified against its own `cosmai_test` database) that this task never
  touched — confirming the failure is structural to running any M4 lane worktree at all, not
  caused by anything in this task's diff (nothing here touches `domain/outbound.py` or
  `test_outbound_transport.py`). Left unfixed: the file belongs to a different area (M2's
  outbound guard), fixing it was not part of this task's packet, and AGENTS.md's
  "does not broaden scope" rule for a bounded task applies. Flagged here as a deviation per
  the global constraints ("계약과 다른 동작을 만들게 되면... '편차' 항목으로 기록") for M7 or
  whoever owns `test_outbound_transport.py` to repair — likely by deriving `REPO_ROOT`
  differently (e.g. from a `git rev-parse --show-toplevel`-style resolution, or by excluding
  `.worktrees` only when it is *not* the worktree's own second path segment) rather than by
  assuming the running tree is never itself inside `.worktrees`.
- **DP-030 D2's normalizer-level fallback could not be exercised through the ordinary JSON
  pipeline, and the test file says so.** Every field this add-on reads comes from
  `json.loads`, so a row can only ever carry JSON's own types, and Python's `str()` never
  raises on any of them — the four field helpers were already total over every JSON-decoded
  shape before this task started. `TestPerRecordFallback` in `test_normalizer_obf_product.py`
  exercises `_build_body`'s fallback honestly by substituting a sentinel-triggered stand-in for
  `_brands` via `monkeypatch`-style module attribute replacement, rather than by constructing
  a snapshot payload that cannot actually exist. The module docstring records this reasoning
  directly.
- **F3 from `P1-INHERITED-DEFECTS.md` §3 is recorded as left, not repaired.**
  `TestCoexistenceOverOneLineage`'s "no row updated in place" clause is unfalsifiable through
  `DomainStore`, because `record_results` has no UPDATE path at all — a real repair needs a
  store-level UPDATE method nothing else in this codebase has a reason to add. The class
  docstring states this plainly rather than leaving the weak assertion unremarked.
- **`test_addon_duplicated_helpers.py`'s subject (`_day_after`) does not exist in this
  worktree.** Neither `importer.local.jsonl` nor `normalizer.obf.product` declares it — that
  helper belongs to the NAVER DataLab collectors, built in sibling M4 worktrees this one
  cannot see. Ported anyway, pointed at `apps/addons/` directly, with the "found in more than
  one add-on" guard skipping (not failing) when fewer than two implementations exist in this
  worktree's own tree; it re-activates automatically once M7 merges every M4 lane's add-ons
  into one `apps/addons/`.
- **`apps/pyproject.toml`'s `addons/` mypy exclude and `apps/scripts/check-addons.sh` are new,
  shared infrastructure, not scoped to this pair.** This is the first M4 task to populate
  `apps/addons/`, so it is the first to hit mypy's "Duplicate module named handler" collision
  every `handler.py`-named entry file produces the moment a second add-on exists
  (`docs/conventions/addon-authoring.md` documents the same collision and resolution at the P0
  root). Added the exclude plus the per-addon check script rather than working around it
  locally, since another M4 lane's own `apps/addons/<id>/` will hit the same collision the
  moment it lands beside this one.
