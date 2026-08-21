# Lane A — M3 batches 3a/3b report (addon_api + addon_kit, addon_host)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m3`, branch `p1/m3-addon-layer`
- Commits:
  - `cf9a670` — batch 3a: "Rebuild the add-on contract and the author's kit against
    CONTRACT-ADDON-1.3" — `apps/addon_api/` (verbatim copy-adapt, `CONTRACT_VERSION = "1.3"`),
    `apps/addon_kit/` (`new` scaffolder + `run` harness, `DEFAULT_ADDONS_ROOT` retargeted to
    `apps/addons`), P0's contract/kit/harness test suites (85 tests), a `normalizer.conformance`
    fixture add-on moved to `apps/tests/fixtures/` (not `apps/addons/`, which this tree reserves
    for real M4 add-ons).
  - `b3304fe` — batch 3b: "Rebuild the host: discovery, the version gate, and capabilities that
    end in one transaction" — `apps/addon_host/` (loading, the version gate, registration, error
    translation, `capabilities.py`'s fetch/open_input/read_snapshot/emit_raw/advance_cursor
    binding, the worker's `RegistryFor` wiring, `addon_host.api`/`__main__` composing the domain
    surface with the deferred `/collect`/`/import` routes); `apps/domain/inputs.py` (new — DP-024
    local input registry M2 never built, needed for the importer capability); `COSMA_ADDON_DIR`
    restored to `platform_core/config.py`; P0's host/worker test suites adapted (63 tests, no
    real add-on installed anywhere in this tree yet).
  - `3dee7a2` — follow-up within 3b's scope: "Prove the capability layer's writes end in the
    fence's own transaction" — the atomicity/durable-scope evidence the task packet named
    explicitly (`TestACollectionIsAtomicThroughAnAddOn`, `TestTheDurableScopeRequirementIsChecked`,
    5 tests), copy-adapted from P0's 1750-line `test_capabilities.py` and narrowed to just those
    two classes plus their scaffolding.
- Verification summary: `mypy --strict .` and `ruff check .` clean across `apps/` (78 source
  files); full apps pytest suite — **732 passed**, 0 failed, unsandboxed against `cosmai_test`
  on the new `shared-postgres` server (port 5434, per the mid-session infrastructure swap); root
  guard `tests/environment` — **82 passed**. One transient run mid-way through batch 3b failed
  ~161 tests with `cannot reach the platform database` (connection-limit or lock contention, not
  reproduced); an immediate re-run passed clean, consistent with the coordinator's note about a
  controller gate run briefly sharing the database.

## Concerns

- **`domain/inputs.py` was not in the batch brief and was added anyway.** M2 never built DP-024's
  local input registry (M2-RECORD doesn't mention it at all — an omission, not a stated
  deferral), but `addon_host.capabilities`'s importer path (`open_input`) needs it and the task
  packet explicitly asked for `open_input` to be wired. Copy-adapted verbatim from P0's
  `domain/inputs.py`; flagging because it's a file outside the literal "addon_host" batch scope.
- **`domain/api.py` reuse decision (M2-RECORD's open item).** Reused rather than relocated:
  `addon_host.api.extend_with_domain` imports `domain.api.extend_with_domain` and composes it
  with the two deferred routes, rather than moving 400+ lines of tested routes into `addon_host`.
  Recorded in both modules' docstrings. `HANDLER_PREFIX` is still mirrored (not imported) in
  `domain/api.py`'s own module — `addon_host.registration.HANDLER_PREFIX` is the source of truth
  and the two are asserted equal nowhere explicit; a future drift would only surface as a job
  nothing claims.
- **The deep capability-behavior suite (P0's `test_capabilities.py`, ~1750 lines) was narrowed,
  not skipped, and the cut line is a judgment call.** The task packet named "capability binding,
  buffered-emit transactionality" specifically; I copy-adapted the two atomicity/durable-scope
  classes those words most directly describe and left refusal-cannot-be-swallowed, the
  page/record limits, the redirect budget, and credential attachment out — real capability-layer
  behavior, exercised only indirectly (through `domain.outbound`/`domain.transport`'s own direct
  test suites) rather than through `addon_host.capabilities` itself. Flagging for batch 3c
  (conformance suite) to weigh explicitly rather than treat as already covered.
- **`P0's `test_addon_credential_hygiene.py`/`test_addon_duplicated_helpers.py` were not
  copy-adapted.** Both scan `addons/*/handler.py` on disk and assert `len(...) >= 2` or `>= 6`
  installed add-ons — they test nothing until M4 installs real ones, and I judged them squarely
  M3 batch 3c's ("conformance suite") to bring over alongside the layer-direction guard extension.
- **No real add-on exists anywhere in this tree.** Every test in both batches builds its own
  synthetic add-on under `tmp_path` (or `apps/tests/fixtures/`) rather than depending on
  `apps/addons/collector.naver.blog` the way P0's originals did — expected and by design (M4
  hasn't run), named here so the pattern is visible across both batches at once.
- `apps/tests/test_addon_host_api.py` is new (not a P0 file) — P0 tested `/collect`/`/import`
  inline inside its giant `test_domain_api.py`; I judged a focused new file better proportioned
  to what M3 actually added (11 tests: route creation, kind/enabled guards, proof the composed
  app still serves every `domain.api` route, and one end-to-end job-creation-to-worker-execution
  check).
