<!-- Transcribed verbatim by the orchestrator from the adversarial reviewer's final message; the reviewer cannot write files. Disposition addendum follows repairs. -->

# REVIEW-M2-M7 — adversarial review of the P1 batch build (`0b01d09..HEAD`, 58 commits, 168 files, ~37,000 insertions)

- **Target:** branch `p1/m7-closure`, everything after M1 merged — M2 domain, M3 addon layer, M4's 8 add-ons + platform mechanisms, M5 dashboard, M6 scheduler/export, M7 sweep+demo.
- **Reviewed artifacts:** `docs/p1/M2-RECORD.md` … `M6-RECORD.md`, `M7-DEMO-RECORD.md`; DP-029…DP-034; `docs/superpowers/plans/2026-08-21-m2-m7-batch.md`; `apps/domain/{outbound,transport,export,api,store}.py`; `apps/addon_host/capabilities.py`; `apps/addons/*` (8); `apps/scheduler/`; `apps/dashboard/src/`; `tests/environment/`.
- **Attacker:** orchestrating reviewer plus six `adversarial-reviewer` subagents (no `Write`/`Edit`). Every finding a subagent returned that is rated BLOCKING below was **independently re-reproduced by the orchestrator** before adoption; one subagent BLOCKING was demoted on re-verification (see §Demoted). Repo untouched — all mutation and probe work under `$TMPDIR`.
- **Date:** 2026-08-21. Tree at `ad067f7`.

## Verdict: **FAIL** — 12 blocking, ~40 minor. Two blocking findings are real runtime defects; the rest are false claims in the decision record.

`[추론]` The pattern is the one this project already names. **The mechanisms are, with two exceptions, very well built and very well tested** — I fired 23 mutations at the outbound policy and 22 died. **The failures are concentrated in the layer that describes the work**, and specifically at the *compression seams*: the M4 consolidation of five lane reports, and the M7 demo record. Where a number passed through one agent's summary into another's, it is wrong about a third of the time.

Two findings are different in kind and are the ones I would not merge past: **B1** (a data-quality event still ends the whole run — the exact defect DP-030 D2 was written to close) and **B2** (the credential value is echoed to the caller, meeting DP-034 H1's own falsification condition).

---

## Gates (orchestrator, run directly)

| Gate | Command | Result |
|---|---|---|
| Root guard | `.venv/bin/python -m pytest tests/environment -q` | **87 passed** ✓ expected |
| apps collection | `apps/.venv/bin/python -m pytest --collect-only -q` | **1083 collected, 0 collection errors** (= 1082 passed + 1 skip) ✓ |
| mypy | `apps/.venv/bin/python -m mypy --strict .` | clean, **101 source files** — *excludes `^addons/`*, see M-C1 |
| ruff | `ruff check .` | **All checks passed** |
| per-addon | `apps/scripts/check-addons.sh` | **all 8 `ok`**, exit 0 |
| merge discipline | all 11 merges in range | **2 parents each — no squash, no rebase.** AGENTS.md held |
| secrets | shape scans over `git log -p 0b01d09..HEAD` | **clean.** Every 32+ hex is a SHA/digest fixture; zero `PASSWORD '...'`; the tubedepth key did not land |

`ruff format --check` reports 53 files unformatted — **not a finding**, `ruff format` is nowhere declared as a gate.

---

## BLOCKING

### B1 — DP-030 D2 is defeated by *valid JSON*. One bad record still ends the run, in all three normalizers and the importer.
`apps/addons/normalizer.naver.blog/handler.py:212`, `normalizer.naver.trend/handler.py:137`, `normalizer.obf.product/handler.py:160`, `importer.local.jsonl/handler.py:94` — all four carry the identical guard:
```python
    except (json.JSONDecodeError, UnicodeDecodeError):
```
**Claim:** DP-030 D2 — *"a single malformed row must not end the run"*; commit `1748019` is titled *"rows abstain, never abort"*.

**Evidence `[측정]`** — `json.loads` raises two exception classes on spec-valid JSON, neither caught (`JSONDecodeError` is a `ValueError` subclass, but these are a *bare* `ValueError` and a `RecursionError`, so the narrow tuple misses both):
```
b'{"id":"b","v":' + b'9'*5000 + b'}'  -> ValueError: Exceeds the limit (4300 digits) for integer string conversion
b'['*100000 + b']'*100000             -> RecursionError
```
The subagent ran this end-to-end at the add-on boundary against unmutated handlers: **`RUN ABORTED, 0 of 3 emitted`** for all three normalizers, and for the importer `4300+ digit number -> ABORTED, 0 raw items` beside its own working positive control (`ordinary malformed line -> SURVIVED emitted=2, malformed_json=1`).

`[추론]` Reachability is highest for `importer.local.jsonl`, whose stated purpose is malformed operator-supplied local rows; an unbounded integer needs no attacker. `domain.store._safe_canonical_body` does not help — it guards serialization of an *emitted* body, and nothing is emitted. This reproduces `P1-INHERITED-DEFECTS.md` §1 ("converts a data-quality event into an availability event") under a different exception class. **No test covers it**: every D2 fixture uses the one malformed shape the guard does catch.

### B2 — `POST /sources/{id}/credentials` echoes the credential value in a 422 body.
`apps/domain/api.py:337` (`body: dict[str, Any] = _REQUIRED_BODY`), claim at `:341-344`: *"Write-only, **by construction rather than by convention**: … never included in the response."* DP-034 H1's falsification condition is *"Any … response body … found to contain a plaintext credential value."*

**Evidence `[측정]`** — no `RequestValidationError` handler is registered anywhere (`grep -rn "add_exception_handler\|exception_handler\|RequestValidationError" --include='*.py' .` → **empty**), so FastAPI's default handler answers and Pydantic v2 puts the body in `input`. Reproduced by the orchestrator against the identical binding:
```
dict (normal)  -> 204  secret-in-response=False
JSON string    -> 422  secret-in-response=True
   {"detail":[{"type":"dict_type","loc":["body"],"msg":"Input should be a valid dictionary","input":"MY-SECRET-42"}]}
JSON array     -> 422  secret-in-response=True
```
Honest scoping: echoed only to the caller who sent it — not a cross-tenant leak. Blocking because *"by construction"* is false, the packet's own falsification condition is met, and 422 bodies are exactly what lands in proxy logs and error sinks. Existing tests exercise only the route's *own* 422s, never one FastAPI raises first.

### B3 — `/export/raw?format=jsonl` emits invalid JSONL for any pretty-printed JSON payload.
`apps/domain/export.py:183-192`. `json.loads()` accepts embedded newlines, so such payloads take the verbatim-splice branch and the newline lands inside the "line".

**Evidence `[측정]`** — reproduced by the orchestrator, pure function, no DB:
```
payload b'{\n  "title": "hello"\n}'  ->  ONE item emitted as THREE physical lines
  line0: JSONDecodeError   line1: JSONDecodeError   line2: JSONDecodeError
```
The whole export is unparseable from that item on. `raw_item.payload` is `bytea` holding arbitrary add-on bytes, and AGENTS.md's lossless-Raw rule makes storing an upstream body verbatim the *intended* path — reachable, not theoretical. `apps/tests/test_export.py:100-127` uses only compact single-line JSON. Unregistered in M6's deviation ledger.

### B4 — `M4-RECORD.md:230-234` claims a security control that does not exist; depth-in-defense is claimed at 2 and delivered at 1.
**Claim (verbatim):** *"a public or private-range host with `scheme: "http"` is **refused at `resolve`** (no `allow_loopback` needed to be missing) and, if it somehow reached the transport anyway, refused again there."*

**Evidence `[측정]`** — found independently by the orchestrator and one subagent:
```python
OutboundProfile.from_row({"hosts":["evil.example.com"], "endpoints":{"e":"/v1/items"},
                          "scheme":"http", "allow_loopback":True})
resolve("e", p)  ->  PreparedRequest(url='http://evil.example.com:443/v1/items')   # NOT a Refusal
```
`apps/domain/outbound.py:586` tests only `scheme == "http" and not profile.allow_loopback`; `resolve` performs no DNS and no address check at all. **Not a live egress hole** — `transport.py:218` `_refuse_http_off_loopback` does hold (`['93.184.216.34']`→`SCHEME_NOT_ALLOWED`, `['127.0.0.1']`→proceed, order-independent), and `transport.py:224-230`'s own docstring says the opposite of the record. Blocking as a **false claim about a security control** in the merged decision record.

### B5 — `%2f` containment: the only test that names it passes for a different reason, and the control is unasserted.
`apps/domain/outbound.py:790` `_ENCODED_SLASH`; test `apps/tests/test_outbound_policy.py:254-261`.

**Evidence `[측정]`** — 23 mutations against the outbound policy, run over all 347 DB-free tests, with a working self-check (`resolve` always refuses → 45 failed). **22 killed; exactly one survived:** removing the encoded-slash refusal leaves **347 passed, 6 skipped** — identical to baseline. Proof it is a real escape, not just an untested line:
```
                                                     REAL           MUTANT
/v1/items%2f..%2fadmin/keys      (the test's payload) PATH_NOT_ALLOWED  PATH_NOT_ALLOWED
/v1/items/x%2f..%2f..%2fadmin    (inside the prefix)  PATH_NOT_ALLOWED  *** ACCEPTED ***
```
The test's payload is outside the approved prefix either way, so its assertion cannot distinguish "refused for the encoded separator" from "refused for being out of range". The payload that actually exercises the control is covered nowhere (`grep -rn "%2f" tests/` → that one test only). Same structure as REVIEW-M1's F1, on a control whose own docstring cites a prior adversarial review.

### B6 — M3 claims refusal-swallowing coverage was added; nothing in the tree exercises it.
`docs/p1/M3-RECORD.md:65-70` and the module docstring at `apps/tests/test_addon_capabilities.py:12-17`.

**Evidence `[확인 사실]`, re-verified by the orchestrator** — contract 1.3 invariants 4 and 5 are different rules. Invariant 4 lives only at `apps/addon_host/capabilities.py:848` (collector, called `:377`) and `:1139` (importer, called `:949`). The 15 tests credit `TestANonSuccessStatusCannotBeIgnored`, which is **invariant 5**; the section banner at `:611` is itself mistitled. P0 had the real test (`experiments/integrated-p0/tests/test_capabilities.py:519 TestARefusalCannotBeSwallowed`, with a positive control); P1 has no equivalent, and it is **not** in M3's "Still not carried, and why" list (`:72-85`). The implementation's own docstring (`capabilities.py:787`) says the status check is *"weaker than `_check_no_refusal_was_swallowed` beside it"* — the stronger control is the untested one. Deleting lines 377 and 949 would leave the suite green.

### B7 — M4-RECORD's naver.blog test counts are wrong, and the sentence refutes itself.
`docs/p1/M4-RECORD.md:31-32` claims *"41 collector + 27 normalizer (68 addon-specific), full `apps` suite 860 passed"*.
**Evidence `[측정]`** (orchestrator, at HEAD; files unchanged since `e87a00e`): `test_collector_naver_blog.py` → **37**, `test_normalizer_naver_blog.py` → **25**, total **62**. The lane suite collected **862** = 800 baseline + 62. Had it been 68 the suite would read 868/866, not the 860 the same sentence states. Error originates in the lane report and was copied without re-derivation.

### B8 — The record's declared primary evidence is untracked and gitignored.
`docs/p1/M4-RECORD.md:5-7,16,21` — *"those five reports are the **primary evidence**"*, *"Controlling evidence: `.superpowers/sdd/…`"*, cited under `[확인 사실]` in `M7-DEMO-RECORD.md:85,111,161,198`.
**Evidence `[측정]`:** `git ls-files .superpowers | wc -l` → **0**; `git check-ignore -v` → `.superpowers/sdd/.gitignore:1:*`. All 16 lane reports. Every live measurement in M4 — 224 dereferences, the key-minting, both `curl` verifications, the 10 blog items — terminates in a machine-local file. AGENTS.md defines `[확인 사실]` as *독립적으로 검증할 수 있는 상태*; a gitignored file is not that from a clone. **Needs an owner decision, not a fix** — promoting them may collide with AGENTS.md's transcript-retention rule, which is exactly the consequential ambiguity AGENTS.md says not to resolve silently.

### B9 — `M7-DEMO-RECORD` §4 records two scheduler firings; its own §10 requires three. §5 omits a sixth failed job.
Found independently by two subagents, from the demo's own retained run logs at `/tmp/claude-1000/m7-demo/`.
- `[측정]` `grep -c scheduler.job_created scheduler.log` → **3** distinct job_ids; `worker.log` holds three trendradar completions: **900, 900, 892**. §4 (`:104-108`) narrates two. The record's own `:252` quotes `jobs_created=3` and `:261` states 2692 = 900+900+892. An undisclosed third firing is 900 more items pulled from a live target.
- `[측정]` Six tubedepth jobs reached FAILED; §5 (`:143-155`) narrates five. The missing one is `f8720ced`, `grants 500 pages … asked for 501`. So `:258`'s *"all 6 failures are the tubedepth attempts in §5, named there"* does not reconcile.
- The ledger's **"13/14 PASS"** appears nowhere in the record (`grep -n "13/14"` → no match) and is not derivable from it. Measured outcome: **8 SUCCEEDED / 6 FAILED of 14 jobs.**

### B10 — `M7-DEMO-RECORD:219`'s range-filter PASS is vacuous.
**Claim:** `GET /export/raw?…&from_=…&to=…` (range filter) | 200 | *"the filter accepted the parameters and streamed without error"*.
**Evidence `[측정]`** (orchestrator): the wire name is `from`, not `from_` — `apps/domain/api.py:115` `_FROM_QUERY: Any = Query(alias="from")`, applied at `:294,:317`. FastAPI ignores unknown query parameters, so `from_=` binds nothing and the filter never ran; that fully explains the 200-of-200 result the record attributes to the window. The code is fine (`buildExportUrl.ts:50` sends `from`; `test_export.py::TestRawExportScopeFilters` covers it). The **gate's demo record presents a vacuous check as a PASS.**

### B11 — M3-RECORD's `[측정]` that "P0 never tested the protected-header rule" is false, and the "new coverage" duplicates a test already in P1.
`docs/p1/M3-RECORD.md:110-120` (*"there was nothing to carry — only to write"*, `:120`), carried under a `[측정]` label into `apps/tests/test_addon_capabilities.py:859-861`.
**Evidence `[확인 사실]`, re-verified by the orchestrator** — byte-comparable classes exist in both trees:
`experiments/integrated-p0/tests/test_credentials.py:154 class TestOnlyAProtectedHeaderMayCarryACredential` (with its positive control at `:167`), and **M2 batch 2c already copy-adapted it** to `apps/tests/test_credentials.py:55` — same class name, same test names. The record's grep was scoped to `test_capabilities.py`/`test_outbound_*.py`, silently excluding the one P0 file named for the subject. No runtime defect; blocking as a false `[측정]` in both a milestone record and a test docstring.

### B12 — The shipped dashboard tells the operator that collect/import do not exist. They do.
`apps/dashboard/src/screens/CollectorDomainScreen.tsx:85` renders: *"Collection dispatch arrives with the add-on host (M3). apps/domain/api.py builds no /collect route yet — creating one now would enqueue a job nothing can ever claim."*
**Evidence `[확인 사실]`:** M3 merged after M5 (`f96b60e` precedes `55e8c68`). At HEAD `apps/addon_host/api.py:110` and `:128` serve `POST /sources/{id}/collect` and `/import` (201), and `M7-DEMO-RECORD:120-122` records four such calls all returning 201. `apps/dashboard/src/api/client.ts:122-127` deliberately has no `startCollection`, so DP-033 D1's collector-domain screen cannot trigger a collection at all. The ledger's parked note said "disabled **until M4 addons merge**" — all eight merged. Nothing registers this as a remaining gap.

---

## Demoted on re-verification (recorded so it is not re-filed)

`[측정]` One subagent rated as BLOCKING that `tests/environment/test_addon_layer_direction.py:45` is hard-scoped to `EXPERIMENT_ROOT` and therefore covers **0 of 8** P1 add-ons — the "guard scanning the wrong tree" shape. That half is true. But the **rule is enforced**, by the guard M3 added. The orchestrator planted `from platform_core.jobs import registry` into a `$TMPDIR` copy of `apps/addons/collector.naver.blog/handler.py` and ran the whole root guard:
```
FAILED tests/environment/test_p1_isolation.py::test_the_apps_layer_points_one_way
E  apps/addons/collector.naver.blog/handler.py:289: imports 'platform_core' — addons may import only addon_api, addons
```
So the correct finding is narrower and **MINOR**: `AGENTS.md:15` and `M4-RECORD:57` cite the wrong test file for the P1 tree. Both guards were separately positive-controlled and both name the offending file and line.

---

## MINOR findings

**Security-adjacent**

| # | Where | Issue |
|---|---|---|
| M-S1 | `apps/platform_core/secrets.py:193-196` | `write_credential`'s temp file is created at **0644** (`[측정]` umask 0o22) holding the plaintext credential, and chmod'ed only after. Claim at `M2-RECORD:63-64` is true of the final file only. `test_secrets.py:223` asserts only the post-rename mode |
| M-S2 | `apps/domain/outbound.py:213` | `"x-api-key"` added for tubedepth but never asserted. `[측정]` deleting the line leaves 169 tests identical to baseline. `test_credentials.py:80-84` established the convention for the previous source and was not extended |
| M-S3 | `apps/platform_core/obs/redaction.py:53-64` | `value` is **not** a redacted key, and the credential route's body field is named `value`. `[측정]` `redact({"value":"THE-SECRET"})` → unmasked. The route is safe by discipline, not by the redaction contract; `test_domain_api.py:826` would stay green with redaction disabled |
| M-S4 | `apps/domain/export.py:195-208` | CSV formula injection: `=cmd\|'/c calc'!A1`, `@SUM(...)`, `+1+1` land **unquoted**. RFC4180 round-trip (the control M6 cites) holds and is the wrong control for this threat. Unregistered. The same untrusted content DP-033 D2 forces to plain text on the dashboard path is interpreted on the export path |
| M-S5 | `apps/dashboard/src/screens/DataBrowserScreen.tsx:143` | DP-033 D2's guard covers the detail pane but **not** the table preview cell, though `M5-RECORD:184` claims both. `[측정]` mutating the preview to `dangerouslySetInnerHTML` leaves all 4 tests green (probe confirmed a real `<b>` element rendered) |
| M-S6 | `apps/domain/api.py:566`, `export.py:251,260` | Normalized bodies are key-redacted on every egress path while the `body_sha256` beside them digests the **unredacted** body — the exported digest cannot verify against the exported body. Both code sites document it; no record or DP does |

**Controls described as controls that are conventions**

| # | Where | Issue |
|---|---|---|
| M-C1 | `apps/pyproject.toml:38` | `mypy --strict .` excludes `^addons/`, so the "101 source files" gate covers **0 of 8** add-ons. `check-addons.sh` compensates correctly (verified: all 8 `ok`, and a subagent positive-controlled it to `FAILED`) but **nothing invokes it** — no test, no CI. Honest in pyproject; a convention, not a control |
| M-C2 | `AGENTS.md:15`, `M4-RECORD:57` | Name `test_addon_layer_direction.py` as enforcing the add-on rule for this project; it scans only `experiments/integrated-p0/`. The rule *is* enforced, by `test_p1_isolation.py` (see §Demoted) |
| M-C3 | `tests/environment/test_p1_isolation.py:133-135,154,235-241` | `LOCAL_PACKAGES` omits `scheduler` — `apps/scheduler/` is outside the layer guard entirely and could import `addons` by name unnoticed. The guard-on-the-guard asserts 3 of 6 packages (not `addons`, the one the READMEs lean on). `:154`'s "`apps/addons/` holds nothing yet (M4)" is stale — it holds eight |
| M-C4 | `apps/tests/test_addon_duplicated_helpers.py:94-109` | `pytest.skip` sits above the assertion, so `assert len(DAY_AFTER) >= 2` is unreachable and a wrong `ADDONS` path would look identical. `M4-RECORD:180-186` discloses the skip honestly; `:193-195`'s "remains correct and ready" has nothing behind it |
| M-C5 | `apps/scheduler/store.py:22-27`, `__main__.py:306-308` | Multi-process safety stated in the voice of `[확인 사실]`; all 8 scheduler tests are sequential `--once` runs. M6-RECORD is honest; the docstrings are not |

**Present tense for things not built**

| # | Where | Issue |
|---|---|---|
| M-P1 | `apps/addons/collector.naver.blog/README.md:31-33`, `apps/addon_kit/template/README.md.tmpl:23-25` | *"A source configured under an older schema is marked `NEEDS_MIGRATION` and refuses to run."* `[측정]` `NEEDS_MIGRATION` appears in **exactly those two markdown files and zero code files**. `config_schema_version` is parsed, stored and echoed, but never compared, no state set, no refusal. It propagates to every generated add-on via `generator.py:348,381`. *(This is the one MINOR I would consider promoting — it is AGENTS.md's named rule violated verbatim, and it ships to all future add-ons.)* |
| M-P2 | `apps/dashboard/src/screens/HealthScreen.tsx:103` | *"No scheduler process exists yet."* M6 landed `apps/scheduler/`. DP-033 D1's "plus scheduler status" is unimplemented; no scheduler endpoint exists |
| M-P3 | `apps/addon_kit/template/README.md.tmpl:54` | Tells every generated add-on the conformance suite *"does not exist yet"*. It does — `addon_kit/conformance.py`, wired at `__main__.py:76` |
| M-P4 | `apps/domain/api.py:22-31,78-79` | Still says `addon_host` *"does not exist in this tree yet"* and *"M3 must keep this string in sync"*. False at HEAD; this is the paragraph B12's UI note quotes |

**Record/evidence defects** (all `[측정]`-re-derived unless noted)

| # | Where | Issue |
|---|---|---|
| M-R1 | `M4-RECORD:55` | DataLab breakdown "39 collector, 26 normalizer, 9 host-loading/conformance" — actual **35 / 33 / 6**. Total 74 is right; every component wrong. The "9" is `test_addon_conformance_m4`(5)+`test_addon_host_loading_m4`(4), both written by the *importer-obf* lane. Textbook compression seam |
| M-R2 | `M4-RECORD:305` | The newest apps-suite `[측정]` in all of `docs/` reports 2 failures that **the same commit fixed**. `54ec33e`'s own message records 1082/0. `grep -rn '1082' docs/` → nothing. A reader of `docs/p1/` concludes the tree is red |
| M-R3 | `apps/tests/test_outbound_transport.py:598-599` | `[측정]` claims the pre-fix cases *"passed vacuously"*. Replay shows both **failed at their positive controls** — the controls are what stopped the vacuity from being silent. Mislabels the signature defect in the one place it did not occur |
| M-R4 | `M4-RECORD:108` | Quotes `COSMA_DB_NAME=cosmai_test_5`; `conftest.py:60-66` reads **`COSMA_TEST_DB`**. The lane report carried both; the consolidation kept the inert half |
| M-R5 | `M4-RECORD:104-105` | "every timestamp this add-on constructs" — tubedepth imports no `datetime`/`time` and constructs none; it round-trips the provider's. Conclusion unaffected |
| M-R6 | `M4-RECORD:35-39,58-65` | NAVER live-smoke `[측정]`s carry no capture time, API version, sample hash, or usage basis — all required by AGENTS.md §Evidence. The tubedepth block at `:311-313` is the counter-example done right |
| M-R7 | `M4-RECORD:128-148` | The importer-obf sentinel/unreachable-branch disclosure is genuinely thorough — **in the test file** (`test_normalizer_obf_product.py:534-551`). M4-RECORD does not mention it at all |
| M-R8 | `M5-RECORD:556-557` | "the same 37 from batch 5d" — 5d was **34**, and they are not the same tests: 9 added, 6 removed. Six assertions were deleted and the phrasing hides it |
| M-R9 | `M5-RECORD:30`, `:44-45`, `:397`, `:553` | Cites nonexistent `test_apps_never_imports_experiments.py` (it is a *function* in `test_p1_isolation.py:111`); credits `vite.config.ts` with a loopback rule only P0 has (and the real check at `client.ts:37-48` has **no test**); writes `GET/POST /export/results` (GET only); says 549 kB where `:341` says 548 (actual 548.40) |
| M-R10 | `M7-DEMO-RECORD:262`, `:218` | "200 normalized blog results" contradicts §6/§8's **197** (`worker.log` confirms 197); "10 columns" vs `RESULT_HEADER`'s **11** |
| M-R11 | `M7-DEMO-RECORD:124-132` | The naver.blog 200-items deviation is stated, but never names that it consumed ~20× the intended quota against a live third party under a real credential |
| M-R12 | `apps/tests/concurrency/run_measurements.sh:23`, `test_db_connection.py:32` | Still `5433`. `provision.md:165` said *"every recipe"*; `54ec33e`'s message claims it corrected "the two documents the addendum named" — `[확인 사실]` the addendum names no documents. The scoping justification is invented |
| M-R13 | `DP-032:256-258` | Present tense: *"The server **is** docker container `tubedepth-postgres` … `127.0.0.1:5433`"*, with no dated correction, while `project-state.md:187-194` points there as the current decision |
| M-R14 | `docs/project-state.md` | **Untouched in the entire range.** The batch plan `:83` requires the M7 update; it still reads Version 0.9, "Next gate: P1 charter gate", and knows nothing of M1–M7 — while AGENTS.md tells every agent to read it first |
| M-R15 | `M2-RECORD:141-158`, `M3-RECORD:72-86` | Two items explicitly handed to M7 ("recorded as a gap for M7 to weigh"; "if M7's closure review judges this gap material") are unacknowledged by any M7 document. B6 is the second one, and it *is* material |

**Contract/consistency**

| # | Where | Issue |
|---|---|---|
| M-X1 | `apps/domain/export.py:91-102,270` vs `DP-033:193-197` | D3 says *"Normalized results export as flattened CSV"*; the build ships metadata columns plus one `json.dumps` blob — the Raw-CSV shape D3 distinguishes it from. M6's deviation ledger registers the neighbouring format-set difference but not this one |
| M-X2 | `apps/platform_core/config.py:319`, `client.ts:33` | Platform API port and dashboard API base both default to **`:8000`**, which DP-031 D3 fixes for trend-radar. The demo silently ran on 8100 with no stated reason. Loud 404s, not silent wrong data — but unregistered |
| M-X3 | `client.ts:143-146` vs `api.py:131-146` | Two different `credential_ref` rules, with a comment claiming they are the same. `[측정]` agree on all five real source ids; diverge on consecutive/edge separators (`a..b` → `A_B` vs `A__B`; `.lead` → `LEAD` vs `_LEAD`). Showing the operator which key to populate is the ref's whole purpose. No test asserts agreement |
| M-X4 | `api.py:83`, `registration.py:62`, `scheduler/__main__.py:103` (+ `SOURCE_ID_FIELD` ×4) | `HANDLER_PREFIX` has **three** copies, `SOURCE_ID_FIELD` four; three records each reason about "two". `[측정]` no test asserts any two are equal — every test derives from one of them |
| M-X5 | `DP-033:66` H5 | Framed entirely on `effect_key` idempotency; the built suppression (`scheduler/store.py:72-80`) is unrelated to `effect_key` (`jobs/store.py:376-379`, which fences *effects of* a running job). `grep -rn effect_key docs/p1/` → nothing. H5 is never evaluated. Separately, `DP-033:283-290` asked M6 to record whether the OQ-008 case arises; `M6-RECORD:107-110` holds the answer without connecting it |
| M-X6 | `DP-034` D1 | Still says the screen shows *"whether it is currently set"*; `e2afd95` correctly removed that. `M5-RECORD:414-424` reconciles it well — only the packet text was left |
| M-X7 | `collector.tubedepth.rest/README.md:127,136,142,186`; `apps/dashboard/README.md` | The tubedepth README documents a `tests/` layout under the add-on that does not exist (real files are `apps/tests/…`; `test_handler_fixtures.py` exists nowhere). The dashboard README is the unmodified Vite scaffold — 32 new lines saying nothing true about cosmai |
| M-X8 | `apps/tests/conftest.py:96`; `test_normalizer_obf_product.py:55` | The session-scoped autouse `_reset_schema` gates **every** test on a live DB, including `test_outbound_policy.py`, whose own docstring says *"No fixture, no database … a security test that needs a server standing up is a security test that eventually gets skipped."* `[측정]` those 110 pass standalone in 0.14s; module-scoped `usefixtures` similarly gates 49 DB-free obf tests. conftest is *honest* about this (REVIEW-M1 F6 was addressed) — but the practical effect is that the outbound security suite is unrunnable by an independent reviewer whenever the server is down, which is the state I found it in |

---

## What HELD — attacked hard, did not break

- `[측정]` **The outbound policy is the best-tested code in the batch.** 23 mutations × 347 DB-free tests, self-check validated: **22 killed**. Scheme allowlist, http-requires-loopback, post-substitution containment, path-param regex, missing-param, dot-segments, header stripping, protected-header-for-credentials, key-name refs, redirect scheme/host/port/range/hops, body limits, empty-path, absolute-path — all load-bearing. Only B5 survived.
- `[측정]` **The transport-time DNS recheck is real.** `send` resolves once, checks, and `_connect` dials from that same list — no second lookup, no rebinding window. `_refuse_http_off_loopback` requires *every* address to be loopback and is order-independent (`['127.0.0.1','93.184.216.34']` → refused either ordering). `SocketTransport` is the only production transport (`addon_host/worker.py:120`).
- `[측정]` **Path-template containment holds for the shipped profile.** tubedepth's real `^[0-9a-f]{64}$` refuses all 19 traversal payloads I threw at it. Under a deliberately permissive `.*`, `quote()`'s `%`-re-encoding neutralizes multi-encoding (`%252e…` → inert) and `comparable_segments` catches `..`/`%2e`/`%2f`. `M4-RECORD:270-292` **registers the residual limitation honestly and accurately** — including the exact `foo/bar` case I measured. (`....//admin` and `..;/admin` also survive a permissive regex; the record's carve-out says "no dots", so these sit just outside its wording. Named, not filed.)
- `[측정]` **DP-033 D2's detail-pane control is genuine.** Mutated to `dangerouslySetInnerHTML` → **RED** with the exact expected diff. It asserts `textContent` equality plus `querySelector("script"/"b") === null` — the strong form.
- `[측정]` **DP-030 D2's add-on-side abstain-and-count is real in all three normalizers** — 3/3 mutants killed each (re-raise, drop-without-count, emit-without-count), with genuine N=3/K=1 positive controls and zero-controls. B1 is a gap in the *guard's exception tuple*, not in the abstain machinery.
- `[측정]` **Redaction, header stripping, and credential containment hold.** Emptying `REDACTED_KEYS` → 6 tests red. `strip_protected_headers` → identity → 5 red. An add-on **cannot set any header** — the `Fetch` protocol takes only `(endpoint_ref, params, body)`. Auth headers travel to redirect hops but `check_redirect` refuses any host outside `profile.hosts`. tubedepth holds no key; only stripped `response_headers` are persisted. `test_addon_capabilities.py:826-850` carries an explicit anti-vacuity control: `assert "url" in row[0], "nothing was recorded, so the absence proves nothing"`.
- `[측정]` **Both isolation guards are real controls.** Planted violations in `$TMPDIR` copies; each named file, line, and rule. Root guard 87.
- `[측정]` **The worktree-scan fix is a narrowing, not a hole.** The `.worktrees` exclusion now matches `path.relative_to(REPO_ROOT).parts`. Against a synthetic tree all 8 plausible locations for a real `allow_loopback` are caught; against the real tree the scan finds exactly 13 files and `permitted` has exactly 13 entries — equality, no slack.
- `[측정]` **Scheduler suppression is DB-backed, not in-process** — schedule-row lock + `next_run_at` re-check + a SQL `select exists`, all in one transaction. Tests assert real row counts with a terminal-job positive control. M6-RECORD describes the mechanism the code actually uses.
- `[측정]` **Every number in M2-RECORD and M3-RECORD re-derives exactly** (18 per-file counts, batch arithmetic 579+85+68+40=772, root guard 82→87, mypy 51/82 files). **Every M5 vitest count and bundle size re-derives to two decimals** across all four batches. **All five M4 lane suite totals reproduce** as `800 + addon-specific + 2`.
- `[확인 사실]` **Contract 1.3 is implemented faithfully.** Clause-by-clause diff of the `addon_api` surface: the per-kind context table matches member for member including the absences; `addon_api` is byte-identical to P0 but one docstring. The single clause implemented differently — invariant 9, determinism — is deliberately unchecked per DP-030 D1 and honestly registered, with `TestDeterminismIsDeliberatelyNotChecked` pinning the absence as a positive assertion.
- `[측정]` **Every route in the plan's §신규 API exists on all three sides** (backend decorator, dashboard client, correct parameter names). No three-way mismatch. P0's 10 `extend_with_domain` routes are all reproduced plus five new ones.
- `[측정]` **`check-addons.sh` is a non-vacuous gate.** A subagent confirmed the naive `mypy --strict addons/<id>/` reports "no .py files" (the vacuous pass the exclude would have caused); the script passes explicit file paths instead, and a planted type error yields `FAILED`.
- `[측정]` **The sweep dropped no content** (`54ec33e --numstat`: +10/−3, +7/−3, +187/−8; every removal is a 5433→5434 replacement or a preamble replaced by a longer one). **All 94 test identifiers cited across the six records resolve.** **Merge discipline held** — 11 merges, 2 parents each.

---

## BLOCKED — could not verify; named, not counted as passes

1. **The full `apps` suite.** `127.0.0.1:5434` → `ConnectionRefusedError` (server down — *not* a sandbox denial; the sandbox permitted the connect). All 1083 numbers are static collection counts. The 1082/1-skip pass result rests on the M7 agent's run and the ledger.
2. **Every live number** — trend-radar `:8000`, tubedepth `:8080`, API `:8100` all refused. Not re-derivable: 224 dereferences, the 10 blog raw items, both DataLab passes, the tubedepth key-minting and its two `curl` checks, instance versions 1.0.3/1.1.0. The 224 figure is internally consistent across three documents, but that is three copies of one unrepeatable observation.
3. **B9's job tally** was derived by subagents from `/tmp/claude-1000/m7-demo/*.log` — real primary evidence, but transient and outside the repo. I did not re-run those greps myself.
4. **All DB-backed tests**, including every test of B2's route, the capability-layer credential-envelope test, and the M2 identity regressions (seq-tie, ICU collation, row-level fault tolerance). Read and judged strong; not executed.
5. **B1 through the full host/worker path** — demonstrated at the add-on boundary and traced through `translated_failures`; no real normalize job was run.
6. **`~/.config/cosmai/env`** is on the sandbox read-deny list. I neither read it nor used `dangerouslyDisableSandbox` at any point.

---

## What was NOT covered

- **`apps/dashboard/src/` beyond DP-033 D2, the API client, and `buildExportUrl`** — no systematic review of the six screens' state handling, routing, or accessibility.
- **`apps/platform_core/jobs/`** — reviewed at M1 and re-read only where M6's scheduler touches it. No fresh attack on the claim statement, fence, or lease logic.
- **The M2 domain store's snapshot-identity internals (DP-029)** — cross-read for consistency and the tests read, but no mutation testing (DB-gated).
- **`apps/addon_host/capabilities.py` as a whole** (~1200 lines) — attacked only at the credential, header, and refusal-swallowing surfaces.
- **Six of the eight add-ons' collection logic** — pagination, cursor advance, and watermark handling were read where a record made a claim, not audited.
- **`experiments/` (P0)** — touched only to check what M2/M3 claimed to carry.
- **Performance, concurrency under real load, and migration replay.**
- **Line-by-line review of ~37k insertions** — this was risk-prioritized, and the priorities were the brief's seven axes.

---

## Recommended disposition

**REWORK before main + v0.1.0.**

- **Fix first (real defects):** B1 (widen the exception tuple to `ValueError`/`RecursionError` in all four add-ons, and add a fixture that reaches it), B2 (register a `RequestValidationError` handler that does not echo `input` — this is a platform-wide fix, not a route fix), B3 (reject or re-serialize a payload containing a newline).
- **Needs an owner decision, not a fix:** B8 (`.superpowers/sdd/` evidence — promote into the tree, or stop citing it as `[확인 사실]` controlling evidence; AGENTS.md's transcript rule may bear on it). Also M-X2's port default and B5's disposition if you would rather register the residual than test it.
- **Record corrections, mechanical:** B4, B7, B9, B10, B11, M-R1…M-R15. These are the compression seams; the M4-RECORD consolidation and the M7 demo record are where they cluster, and both were written by an agent summarizing another agent.
- **Test-quality debt, cheap now and expensive later:** B5, B6, M-S2, M-S5, M-C1…M-C4.
- **B12 and M-P1…M-P4** are operator- and author-facing false statements shipped in the product and in the add-on template. M-P1 is the one MINOR I would consider promoting to blocking: it violates AGENTS.md's "do not describe a convention as a control" verbatim and propagates to every future add-on.

**Housekeeping:** a review subagent's `npm run build` left `apps/dashboard/dist/` on disk. It is gitignored (`apps/dashboard/.gitignore:11`) so the tracked tree is clean — `git status --porcelain -uno` is empty — but it should be deleted. Neither I nor any subagent modified a tracked file at any point; all mutation work was under `$TMPDIR`.

---

## Disposition addendum (orchestrator, 2026-08-21, post-repair)

| Round | Commits | Scope | Independent re-verification |
|---|---|---|---|
| 1 | `07dafb6` `de7cc53` `34fb260` `29b8f84` | B1–B12 + every M-# per controller rulings (B8 promoted to `docs/p1/lane-reports/` after a secret-shape scan; M-P1 implemented as a real refusal; M-X2 port → 8100; B12 collect wired) | B1–B12 confirmed **by execution** (B1 four real/mutant pairs; B2 live probe; B5 RED/GREEN re-run by the reviewer). Four new findings: N1 (the B1 tuple gap surviving in `export.py`), N2 (DB-detection flag incomplete + a convention described as a control), N3 (a correction that was itself false), N4 (a gitignored path cited from a new section), N5–N8 minor |
| 2 | `020924a` | N1–N8 | Orchestrator reproduced directly: the widened tuple at `export.py:202`, the corrected M4-RECORD wording, 17 tracked lane reports, all remaining `.superpowers` mentions verified as historical/provenance text rather than evidence pointers, root guard 87 |

Final state: root guard **87**, apps suite **1127 passed / 1 skipped** (live DB), mypy --strict clean, ruff clean, `check-addons.sh` 8/8, dashboard build + **47** vitest. Residuals accepted with rulings: importer UI screen absent (client+hook tested; screen is follow-on work), one immutable commit message, two P0-tree E501s (read-only tree).
