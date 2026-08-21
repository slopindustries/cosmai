# Lane A — M3 batch 3c report (conformance suite, deferred capability coverage, credential-hygiene refusal, layer guard)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m3`, branch `p1/m3-addon-layer`
- Commits:
  - `e2b6438` — "Build the conformance suite, close the deferred capability coverage,
    and promote credential hygiene to a load-time refusal" — `apps/addon_kit/conformance.py`
    (new), `--conformance` wired into `addon_kit run`; `apps/addon_host/hygiene.py`
    (new) wired into `addon_host/loading.py`'s `_import_by_path` as a load-time
    `AddonRefusedError`; `apps/tests/test_addon_capabilities.py` extended with the
    three behaviors deferred from batch 3b (refusal-swallowing, limits enforcement,
    credential attachment) plus the cursor resume scenario and new
    non-protected-header-refused coverage; `tests/environment/test_p1_isolation.py`
    extended with the `apps/` layer's own DP-008 D1 direction guard;
    `docs/p1/M3-RECORD.md` (scope, deviations, test table, OQ-013 clause C note).
- Verification summary: `mypy --strict .` and `ruff check .` clean across `apps/`
  (82 source files); full apps pytest suite — **772 passed**, 0 failed, unsandboxed
  against `cosmai_test` on `shared-postgres` (port 5434); root guard
  `tests/environment` — **87 passed** (82 + 5 new apps-layer-direction tests). One
  transient run mid-batch failed ~245 tests with `relation "cosmai.platform_effect"
  does not exist` (a concurrent schema reset, consistent with another lane sharing
  the database); an immediate re-run passed clean and was not reproduced.

## Concerns

- **P0 has no conformance suite to copy-adapt — this is a finding, not an
  implementation shortcut.** `experiments/integrated-p0/EXP-002-addon-layer.md`
  names it "deliberately deferred: without the capability layer it could [not be
  built]" and `EXP-003-capability-layer.md` still lists it among what remains after
  the capability layer landed; nothing in the P0 tree implements it as a runnable
  tool. `apps/addon_kit/conformance.py` is therefore new code, not a copy-adapt,
  built from what `addon_api`/`addon_kit.harness` already promise (manifest
  validity, the contract-range gate, one harness run for kind-capability
  conformance, a second harness run seeded with the first's own cursor for the
  resume scenario). Full reasoning and the "what P0 built instead" citation trail
  are in the module's own docstring and `docs/p1/M3-RECORD.md` §(b).
- **Determinism is deliberately not checked in the conformance suite**, per
  DP-030 D1 (byte-identical normalization excluded from the P1 contract
  requirement). A non-deterministic normalizer passes conformance; this is pinned
  as a positive test (`TestDeterminismIsDeliberatelyNotChecked`) rather than left
  as a silent gap.
- **The deep capability-behavior suite (P0's `test_capabilities.py`, ~1750 lines)
  is still narrowed, deliberately, for the second batch running.** Batch 3b took
  atomicity/durable-scope; this batch took the three behaviors its own task packet
  named (refusal-swallowing, limits, credential attachment) plus the cursor resume
  scenario — one strong test per behavior plus this codebase's own positive-control
  convention, not P0's full 2-4-variant-per-case coverage. Not carried: the
  redirect-budget deadline-sharing class (covered indirectly by
  `test_outbound_transport.py`'s wall-clock version), and P0's five-case
  output-shape refusal matrix (`TestOutputIsChecked` — miscounted output, wrong
  return type, orphaned item, wrong stream, null cursor). Named explicitly in
  `docs/p1/M3-RECORD.md` §(b) for M7's closure review to weigh.
- **A real test-fixture bug was found and fixed while writing the credential-
  attachment tests, not a platform bug.** A synthetic add-on manifest omitted
  `streams = ["items"]`, so `advance_cursor("items", ...)` hit
  `AddonOutputInvalid` (OQ-010's stream-binding check) — and two tests passed
  anyway because `RunOutcome.accepted` means "the fence recorded a completion
  normally," not "the job succeeded," and both tests' assertions happened to hold
  regardless. Fixed the manifest and tightened both assertions to
  `outcome.state is JobState.SUCCEEDED`. Full account in `docs/p1/M3-RECORD.md` §(b).
- **`TestACredentialPartMustNameAProtectedHeader` is new coverage.** DP-018 D3's
  "credential may only fill a protected header" rule is enforced in
  `domain/outbound.py` (M2, copy-adapted from P0 verbatim) but — as far as this
  tree's copy of P0's test suite shows — P0 never tested it. Added 2 tests against
  `domain.outbound.OutboundProfile.from_row` directly.
- **P0's `test_addon_duplicated_helpers.py` was not ported.** It scans installed
  add-ons for identically-duplicated helper functions (e.g. `_day_after`) across
  real collectors that do not exist in this tree yet (M4). Flagged for M4/M7.
- **The credential-hygiene scanner is now a load-time host refusal, not only a
  test.** This was the task packet's own explicit ask, but it is a real behavior
  change worth naming plainly: an add-on whose executable code names a credential-
  shaped header, key, or URL is now refused by `addon_host.loading` before its
  module is ever imported (`AddonRefusedError`, the same class and "before the
  import" ordering the version gate already has). This is new host behavior, not
  present anywhere in P0.
