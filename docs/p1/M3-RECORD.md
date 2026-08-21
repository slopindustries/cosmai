# M3-RECORD — the add-on layer: contract, kit, host, conformance suite, and hygiene

- Milestone: M3 (`addon_api`, `addon_kit`, `addon_host` — the three-layer add-on
  architecture DP-008 specifies, rebuilt against `CONTRACT-ADDON-1.3.md`).
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m3`, branch
  `p1/m3-addon-layer`.
- Batches and commits: 3a `cf9a670` ("Rebuild the add-on contract and the author's
  kit against CONTRACT-ADDON-1.3"), 3b `b3304fe` ("Rebuild the host: discovery,
  the version gate, and capabilities that end in one transaction") + `3dee7a2`
  (follow-up within 3b's own scope, atomicity/durable-scope tests), 3c (this
  record's own commit — conformance suite, deferred capability coverage,
  credential-hygiene promotion, layer guard extension).
- Date: 2026-08-21.
- Consumed by: M4's per-add-on worktrees (`addon_api`/`addon_kit`/`addon_host` are
  the layer every real add-on is written and hosted against) and the M7 closure
  review, per the batch plan's own §공통 제약.

## (a) Scope

- **`apps/addon_api/`** — the contract both sides depend on (manifest parsing, the
  four version axes, kind-specific `Declarations`/context/entry signatures,
  serializable boundary types). Copy-adapted verbatim; imports nothing local.
- **`apps/addon_kit/`** — the author's tools: `new` (the scaffolder) and `run` (the
  offline harness), plus `conformance` (new — see §(b)).
- **`apps/addon_host/`** — discovery, the version gate, registration into
  `HandlerRegistry` as `addon:<id>`, error translation, `capabilities.py`'s
  fetch/open_input/read_snapshot/emit_raw/advance_cursor binding, the worker's
  `RegistryFor` wiring, `addon_host.api`/`__main__` composing the domain surface
  with the `/collect`/`/import` routes M2 deferred, and (new in 3c) a load-time
  credential-hygiene refusal.
- **`apps/domain/inputs.py`** — DP-024's local input registry, needed by the
  importer capability and never built by M2 (see §(b)).
- **`tests/environment/test_p1_isolation.py`** (root guard) — extended with the
  `apps/` layer's own dependency-direction check (see §(b)).

## (b) Deviations ledger

### `domain/inputs.py` was added outside the literal task-packet scope (batch 3b)

M2 never built DP-024's local input registry — `docs/p1/M2-RECORD.md` does not
mention it at all, which is an omission rather than a stated deferral. The 3b task
packet asked for `capabilities.py`'s `open_input` binding, which cannot exist
without it. Copy-adapted verbatim from `experiments/integrated-p0/domain/inputs.py`
(no P1-specific change needed — it touches no database, no credential, and no
network). Flagged at the time in the batch's own report
(`laneA-3ab-report.md`) and repeated here.

### `apps/domain/api.py` reuse decision (M2-RECORD's open item, closed in batch 3b)

M2-RECORD named the choice and left it to M3: reuse `domain.api.extend_with_domain`
from `addon_host`, or relocate its routes into `addon_host.api` outright.
**Reused.** `addon_host.api.extend_with_domain` imports and calls
`domain.api.extend_with_domain`, then adds the two routes M2 deferred
(`POST /sources/{id}/collect`, `POST /sources/{id}/import`) on the same app.
Recorded in both modules' docstrings. `domain.api.HANDLER_PREFIX` remains a
mirrored constant (not imported from `addon_host.registration.HANDLER_PREFIX`) —
a drift between the two would surface only as a job nothing claims, not as a
test failure; no test asserts the two strings stay equal.

### The deep capability-behavior suite was narrowed twice, on purpose, and named both times

P0's `test_capabilities.py` is 1750+ lines. Batch 3b's task packet named
"capability binding, buffered-emit transactionality" and got exactly
`TestACollectionIsAtomicThroughAnAddOn` + `TestTheDurableScopeRequirementIsChecked`
(5 tests) plus their scaffolding. Batch 3c's task packet then named the three
behaviors deferred from 3b explicitly — refusal-swallowing, limits enforcement,
credential attachment — and those were added (15 tests: `TestThePageLimitIsEnforced`,
`TestTheRecordLimitIsEnforced`, `TestTheRequestBodyLimitIsEnforced`,
`TestANonSuccessStatusCannotBeIgnored`, `TestTheCredentialReachesTheRequestAndNothingElse`,
`TestACredentialPartMustNameAProtectedHeader`, `TestASecondRunResumesFromTheFirstsCursor`).

**Still not carried, and why:** the redirect-budget class
(`TestTheRequestBudgetSpansTheRedirectChain` — a deadline-sharing structural
assertion; `test_outbound_transport.py` already covers the wall-clock half over a
real socket), the miscount/wrong-return-type/orphaned-item/wrong-stream/null-cursor
output-shape refusals (`TestOutputIsChecked` — five cases, each a `AddonOutputInvalid`
variant; none is a *new* behavior class, and the task packets named three specific
behaviors, not "the rest of the file"), and the full status/body-refusal matrix
(only one core case plus its positive control was ported per behavior, per both
task packets' own "one strong test per behavior" instruction — P0's file carries
2-4 variants of most of these). If M7's closure review judges this gap material,
`experiments/integrated-p0/tests/test_capabilities.py` is the source to return to;
nothing about the narrowing was structural (the `run_collect`/`ScriptedTransport`
scaffolding in `apps/tests/test_addon_capabilities.py` already generalizes to
carry more of it).

### A real defect found and fixed while writing the credential-attachment tests

`CREDENTIAL_MANIFEST` (the synthetic add-on `TestTheCredentialReachesTheRequestAndNothingElse`
installs) initially declared no `streams`, so the ordinary `COLLECTOR` handler's
`context.advance_cursor("items", ...)` call named a stream `_require_single_stream`
had bound to `"default"` instead — `AddonOutputInvalid: this run reads and writes
the 'default' cursor stream; 'items' was not declared (OQ-010)`. Two tests
(`test_the_platform_attaches_the_credential_to_the_request`,
`test_the_value_is_in_no_recorded_envelope`) passed anyway on the first run,
because `outcome.accepted` is true for an *accepted, failed* completion (the fence
recorded a `PLATFORM_PERMANENT` terminal state normally) — not only for a
*succeeded* one — and the assertions those two tests made (headers sent; a row
existed) either happened before the failure (`fetch` runs before
`advance_cursor`) or coincidentally matched an empty result. `[측정]` Caught by
adding `manifest.declares.streams = ["items"]` to the fixture and re-running;
both tests' assertions were then tightened to `outcome.state is
JobState.SUCCEEDED` rather than `outcome.accepted`, which is the correct
distinction (`RunOutcome.accepted` means "the fence recorded a completion
normally," not "the job succeeded" — `platform_core/jobs/runner.py`'s own
`RunOutcome`/`Completion` docstrings state this and this batch's tests initially
read past it). No production code changed; the defect was in the new test
fixture, not in `addon_host.capabilities`.

### `TestACredentialPartMustNameAProtectedHeader` is new coverage, not a copy-adapt

DP-018 D3's rule ("a credential may only fill a header that is stripped out of
recorded Raw") is enforced in `domain/outbound.py`'s `_read_credentials`
(`M2 batch 2c, copy-adapted verbatim from P0`), but — as far as this tree's copy of
the P0 test suite shows — P0 never actually tested it: neither
`experiments/integrated-p0/tests/test_capabilities.py` nor any `test_outbound_*.py`
file greps for "not a protected header". Added as new coverage (2 tests, against
`domain.outbound.OutboundProfile.from_row` directly) because the 3c task packet
named "a part with a non-protected header refused" as one of the three credential-
attachment behaviors to carry, and there was nothing to carry — only to write.

### The conformance suite does not exist in P0 and was built new

The 3c task packet asked to copy-adapt P0's conformance suite. `[확인 사실]`
`experiments/integrated-p0/EXP-002-addon-layer.md` names it explicitly as work
"deliberately deferred: without the capability layer it could [not be built]",
`EXP-003-capability-layer.md` still lists it among what remains after the
capability layer landed, and `docs/decisions/DP-008-addon-architecture.md` counts
it among the architecture's costs. Nothing in `experiments/integrated-p0/`
implements it as a runnable tool — grepping the tree for `conformance` finds only
the test-double add-on (`addons/normalizer.conformance/`) and prose. What P0 built
instead, and what `CONTRACT-ADDON-1.3.md`'s own "Acceptance criteria" section names
as the add-on layer's real evidence, is a pytest suite needing a database, a
worker, and (for three of four files) a real installed add-on — not something an
author runs against a work-in-progress add-on before either exists.

`apps/addon_kit/conformance.py` is therefore new, not copy-adapted, built from
what the contract and the harness already promise: manifest validity and
contract-range conformance (restating `addon_host.loading`'s own version gate,
without a host); kind-capability conformance (one `addon_kit.harness.run_addon`
call — the harness already builds the right context type, validates configuration
as the host does, and cross-checks emitted counts); the cursor resume scenario
(collector/importer with a declared stream — a second harness run seeded with the
first run's own advanced cursor, using the same fixtures). Wired into
`python -m addon_kit run <dir> --conformance`.

**Determinism is deliberately not checked**, per the 3c task packet's own
instruction to "carry only what P1's decisions keep."
[DP-030](../decisions/DP-030-p1-normalization-scope.md) D1 excludes byte-identical
normalization from the P1 contract requirement; P0's own conformance evidence for
`normalizer.conformance` asserted exactly that (two runs, one snapshot,
byte-identical output), and carrying it into a generic suite would re-impose the
obligation D1 struck down. What D1 does **not** touch — `NormalizeContext` still
offers no clock and no random source, unchanged in contract 1.3 — needed no new
check to "carry": it is a fact about the contract's own types, already true of
every add-on that parses, and asserting it again per add-on would be checking the
parser rather than the add-on. `TestDeterminismIsDeliberatelyNotChecked` in
`apps/tests/test_addon_conformance.py` pins the absence as a positive assertion
(a non-deterministic normalizer still passes) rather than leaving it implicit.

### The credential-hygiene scanner was promoted from a test to a load-time host refusal

The 3c task packet asked for this explicitly ("make it a host-side check that runs
at discovery"). P0's `test_addon_credential_hygiene.py` scanned installed add-ons
after the fact, in a pytest run an operator might never execute against a
production install — and that test's own docstring records that this exact gap
bit it once already (`collector.naver.blog` scanned by nothing until discovery
switched from a name list to the filesystem). `apps/addon_host/hygiene.py` carries
the same AST-based scan (`executable_names`, the same docstring-stripping and
`FORBIDDEN` list, unchanged) but `addon_host/loading.py`'s `_import_by_path` now
calls it on the raw source text **before** importing the module, raising
`AddonRefusedError` — the same refusal class and the same "before the import"
ordering guarantee the version gate already has — when a violation is found. An
operator installing a credential-hygiene-violating add-on now gets one clear,
non-retryable refusal at process start rather than a job that ran and possibly
leaked. `apps/tests/test_addon_hygiene.py` (8 tests) covers both the scan itself
(unit-level, copy-adapted from P0's positive/negative controls) and the new
load-time refusal (a synthetic offending add-on under `tmp_path`, since no real
add-on exists in this tree yet).

Not carried: P0's `test_addon_duplicated_helpers.py` (scans installed add-ons'
`handler.py` for identically-duplicated helper functions like `_day_after`) —
this is evidence about a specific pair of real add-ons that do not exist in this
tree yet (M4), not a host-enforceable rule; flagged for M4/M7 to weigh rather than
built against nothing.

### The layer guard extension covers `apps/`, not just `experiments/integrated-p0/`

`tests/environment/test_p1_isolation.py` previously proved one thing — nothing
under `apps/` imports `experiments`. It now also proves DP-008 D1's direction
*inside* `apps/`: `addon_api` imports nothing local; `addon_kit` and (once M4
installs one) `apps/addons/*` import only `addon_api`; `addon_host` imports
`platform_core`, `domain`, `addon_api` and nothing else; `platform_core` imports
none of `domain`/`addon_*`; add-ons are loaded by path and never imported by name.
Same AST approach as `test_addon_layer_direction.py` (which proves the identical
claim inside `experiments/integrated-p0/`) and the existing experiments-import
guard in the same file; the existing checks and their scaffolding
(`python_files`, `collect_violations`, `test_apps_never_imports_experiments`) are
unchanged. 5 new tests; root guard total 82 → 87.

### `apps/tests/test_addon_host_api.py` is new, not copy-adapted from P0

P0 tested `/collect`/`/import` inline inside its one large `test_domain_api.py`.
Batch 3b wrote a separate, smaller file (11 tests: route creation and its payload
shape, the kind/enabled guards, proof the composed app still serves every
`domain.api` route unchanged, one end-to-end job-creation-to-worker-execution
check) rather than extending `apps/tests/test_domain_api.py` (M2's file, which
tests `domain.api.extend_with_domain` directly and is not this batch's to modify)
or reproducing P0's monolith.

### OQ-013 clause C — carried open, as the plan requires

[`P1-RECONSTRUCTION-PLAN.md`](../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md)'s
M3 row states this explicitly: "OQ-013 clause C is carried open here, not
resolved." Clause C (`docs/open-questions/OQ-013-addon-responsibility-boundary.md`,
"Interim position") is the `accept_status` mechanism — requiring an add-on to
*report* a judgment no layer can check, rather than moving the judgment to the
platform. It landed in the contract at version 1.2 and is unchanged in 1.3; this
milestone reconstructed it exactly as written (`CollectContext.accept_status`,
`_check_every_status_was_decided` in `addon_host.capabilities`,
`TestANonSuccessStatusCannotBeIgnored` in batch 3c's own test additions) and did
not extend, narrow, or otherwise resolve the open question further. No new
decision was made about it in this milestone.

## (c) Scenario / test table

| Surface | Test file | Count | DB required |
|---|---|---|---|
| Manifest, version ranges, config validation | `apps/tests/test_addon_api_contract.py` | 40 | no* |
| `addon_kit new`/generated-skeleton conformance | `apps/tests/test_addon_kit.py` | 16 | no* |
| `addon_kit run` harness + `normalizer.conformance` fixture | `apps/tests/test_addon_harness.py` | 29 | no* |
| Discovery, version gate, registration, error translation, `COSMA_ADDON_DIR` | `apps/tests/test_addon_host.py` | 46 | no* |
| The worker's capability-layer wiring (`RegistryFor`), the process entrypoint | `apps/tests/test_addon_worker.py` | 6 | yes |
| `addon_host.api`: `/collect`, `/import`, the composed domain surface | `apps/tests/test_addon_host_api.py` | 11 | yes |
| Atomicity/durable-scope (3b) + limits/refusal-swallowing/credential attachment/cursor resume (3c) | `apps/tests/test_addon_capabilities.py` | 20 | yes |
| Credential-hygiene scan + load-time refusal | `apps/tests/test_addon_hygiene.py` | 8 | no* |
| The conformance suite (`addon_kit.conformance`) + CLI wiring | `apps/tests/test_addon_conformance.py` | 17 | no* |
| Root guard: apps/ layer direction (new) | `tests/environment/test_p1_isolation.py` | 5 (of 87 total) | no |

*Every module still needs a live server for `conftest.py`'s session-scoped
`_reset_schema` autouse fixture to collect at all — "no DB required" means the
module's own assertions do not touch it, the same caveat `docs/p1/M2-RECORD.md`
records for its own table.

Full apps-suite total at the end of batch 3c: **772 passed** (579 at the end of M2
+ 85 batch 3a + 68 batch 3b, including the atomicity follow-up commit + 40 batch
3c net-new tests = 772); `mypy --strict` clean (82 source files), `ruff check`
clean. Root guard: **87 passed** (82 + 5 new layer-direction tests).

## (d) Files touched, by batch

- **3a**: `apps/addon_api/{__init__,context,errors,manifest,results}.py` (new),
  `apps/addon_kit/{__init__,__main__,generator,harness}.py` (new),
  `apps/addon_kit/template/*.tmpl` (new), `apps/tests/test_addon_api_contract.py`
  (new), `apps/tests/test_addon_kit.py` (new), `apps/tests/test_addon_harness.py`
  (new), `apps/tests/fixtures/normalizer.conformance/{addon.toml,handler.py}` (new).
- **3b**: `apps/addon_host/{__init__,settings,errors,loading,registration,
  capabilities,worker,api,__main__}.py` (new), `apps/domain/inputs.py` (new),
  `apps/domain/api.py` (docstring: reuse decision recorded),
  `apps/platform_core/config.py` (`ADDON_DIR_VARIABLE` restored),
  `apps/tests/test_addon_host.py` (new), `apps/tests/test_addon_worker.py` (new),
  `apps/tests/test_addon_host_api.py` (new), `apps/tests/test_addon_capabilities.py`
  (new — atomicity/durable-scope classes only at this point).
- **3c**: `apps/addon_kit/conformance.py` (new), `apps/addon_kit/__main__.py`
  (`--conformance` flag), `apps/addon_host/hygiene.py` (new),
  `apps/addon_host/loading.py` (`_require_credential_hygiene`, wired into
  `_import_by_path`), `apps/tests/test_addon_capabilities.py` (extended — limits,
  refusal-swallowing, credential attachment, cursor resume), `apps/tests/
  test_addon_hygiene.py` (new), `apps/tests/test_addon_conformance.py` (new),
  `tests/environment/test_p1_isolation.py` (apps/ layer-direction extension),
  `docs/p1/M3-RECORD.md` (this file).
