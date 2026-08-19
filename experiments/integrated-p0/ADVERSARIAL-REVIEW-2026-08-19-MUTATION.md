# Adversarial review — mutation sweep of the whole tree, 2026-08-19

- Reviewer: an independent agent with no write tools, working from a copy. It authored none
  of the code it reviewed.
- Baseline: the working tree as of **2026-08-19 ~08:40 KST**, snapshotted to a pristine
  reference. Baseline suite: **1072 passed, 14 skipped**.
- Coverage: **208 distinct mutations across 34 files — 69 GREEN, 131 RED, 8 ambiguous.**
- Method: each mutation applied to a disk copy, the whole suite run with no path argument,
  the file restored from a content snapshot.
- Outcome: **1 blocking, 6 major, 4 moderate, and a set of minor notes.** Its direct
  predecessor is `ADVERSARIAL-REVIEW-2026-08-18.md` F6 — "seven rules whose removal the suite
  does not catch" — which this extends by two orders of magnitude.

## Why this exists, and what it is not

`[결정]` Committed **before repair**, for the reason
[ADVERSARIAL-REVIEW-2026-08-18.md](ADVERSARIAL-REVIEW-2026-08-18.md) gives. This is the
second of two independent reviews run on 2026-08-19; the other,
[ADVERSARIAL-REVIEW-2026-08-19.md](ADVERSARIAL-REVIEW-2026-08-19.md), attacked the DP-018 and
DP-020 security boundary. `[확인 사실]` The reviewer verified **zero overlap** between their
headline findings.

`[결정]` The reviewer is an agent, not a second person, and shares a class of blind spot with
the author. What it is not is the author: it found a blocking precondition nobody had
performed, and seven of its findings are in tests the author wrote while believing them
sound.

## Verification by the author

`[측정]` Two findings were reproduced independently before this document was written:

| Finding | How it was confirmed | Note |
|---|---|---|
| B1 | `.claude/settings.json` read directly: `"autoAllowBashIfSandboxed": true`, `"allowedDomains": ["*"]`, no `deniedDomains`. `p0-security.md:101` requires the narrowing at P0-B entry. | Confirmed exactly |
| B2 | Removed `"secret"` from `REDACTED_KEYS` and ran the suite: **1126 → 1118 passed**. Eight cases vanished. | **Partially** — one test in the current tree *does* fail, unlike the reviewer's baseline where it was fully green. The parametrization collapse is real; the total silence is not, in this tree |

`[측정]` Everything else rests on the reviewer's measurements, quoted with the numbers it
reported.

## Four caveats the reviewer raised, which shape everything below

1. `[확인 사실]` **The reviewed code is uncommitted** — 26 modified tracked files, 54
   untracked, on `dev` at `c0a266d`. The reviewer's first harness used `git checkout` to
   revert and destroyed the work under review; it switched to content snapshots. Anyone
   re-running mutation work here **must not use `git checkout`**.
2. `[측정]` **Two noise sources, measured rather than assumed.**
   `test_a_store_inside_the_repository_is_refused` failed in **all 208** runs — the
   reviewer's copies symlink `var` to tmpfs and `secret_store_path` resolves symlinks.
   `test_job_007_case_b_*` failed in 5–13 runs of unrelated mutations. Only these two were
   classified as noise, after counting frequency across every run.
3. `[측정]` **The tree moved under the reviewer.** DP-022, the structural-fixture tool, the
   evidence directory and the parallel review all landed mid-run, and
   `outbound.py`/`transport.py`/`capabilities.py` changed. It re-verified at 09:44 that every
   guard it mutated was byte-identical in the live tree. `_check_every_status_was_decided` is
   newer than that check and its results predate it.
4. `[확인 사실]` `CAP-reqbytes` GREEN is the parallel review's M7; the reviewer claims no
   credit for it.

---

## B1 — SEC-006's mandatory P0-B precondition was never performed. **Blocking.**

**Claimed.** `docs/conventions/p0-security.md` requires, in bold, that the agent sandbox's
`allowedDomains` be narrowed from P0-A's `["*"]` to the registered source hosts **before the
first source probe makes a real outbound request**, with `deniedDomains` added and
`autoAllowBashIfSandboxed` re-examined. It is listed as `SEC-006` under Minimum acceptance
evidence.

**Why it is false.** `[확인 사실]` `.claude/settings.json` still holds
`"autoAllowBashIfSandboxed": true` and `"allowedDomains": ["*"]`, with no `deniedDomains`.
`README.md` records three collectors that **have** run against the real NAVER API Hub with
credentials.

`[추론]` The second enforcement point the document calls *"application 검증에 결함이 있어도
샌드박스가 egress를 막는다"* is fully open, at exactly the stage it was written to cover. The
reviewer did not change it, and neither has the author: it is a configuration decision for
the operator, and a review has no authority over one.

## B2 — SEC-004's evidence chain is parametrized from the constant it pins. **Major.**

`[측정]` Four test-side derivations, all generated from the production constant:
`test_redaction.py:45`, `test_api.py:94`, `test_dashboard.py:134`, `test_dashboard.py:151` —
each a comprehension over `sorted(REDACTED_KEYS)`.

**Removing a member removes its own test cases.** `[측정]` Dropping `"secret"`: the suite
reports **eight fewer tests**, silently. Seven of the eight members survive only incidentally,
because other tests hard-code those names; `"secret"` appears in `test_redaction.py` only
inside `test_the_input_is_not_mutated`, which passes either way.

`test_every_contract_key_is_masked` is named for a set fixed by `CONTRACT-JOB@0.1` and is
structurally incapable of noticing a key leaving it.

`[추론]` The project already applies the right pattern elsewhere — `test_db.py` hard-codes
`STATES`/`OUTCOMES` as literals and `test_errors.py` hard-codes `CONTRACT_ROWS`. The redaction
key set is the outlier, in the one place SEC-004 depends on. `test_dashboard.py` even records
that its marker *values* are deliberately not shared; the care over values makes the shared
key set more striking, not less.

## B3 — every `DEFAULT_LIMITS` value is unpinned, and the test named for them is a self-comparison. **Major.**

`[측정]` All eight went **GREEN**: `connect_timeout_s` 5s→3600s, `read_timeout_s` 30s→3600s,
`max_response_bytes` 8 MiB→8 GiB, `max_redirects` 3→100, `max_pages` 20→10⁹, `max_records`
5000→10⁹, `max_request_seconds` 60s→86400s, `max_request_bytes` 64 KiB→64 MiB.

The docstring says: *"Small on purpose: a source that needs more says so, and an unstated
limit that happens to be generous is how a bound stops bounding anything."*

**Why nothing catches it.** `test_outbound_policy.py:368` asserts
`profile.limits["max_response_bytes"] == DEFAULT_LIMITS["max_response_bytes"]`. `[추론]` The
test named for *"the documented defaults"* compares the value against itself. It proves the
fallback *mechanism*; no number appears anywhere in it. Every enforcement test uses a fixture
profile stating its own limits, so the values governing a source that states none are held by
nothing — including `ADVERSARIAL-REVIEW-2026-08-18.md` F5's 60-second budget, the repair for
the 38-day occupancy.

## B4 — the API's redaction layer cannot mask anything, and no test says so. **Moderate.**

`[측정]` Both `attempt_view`'s `redact(fields)` → `dict(fields)` and the protected view's
`redact(detail)` → `detail` are **GREEN**. Measured directly:

```
redact({'error_summary': 'the handler failed: token=super-secret-42', ...})
  -> unchanged
redact_text('the handler failed: token=super-secret-42')
  -> 'the handler failed: token=[REDACTED]'
```

`redact` masks by **key name only** and never applies `redact_text` to string values. No
`job_attempt` column name is in `REDACTED_KEYS`, so `attempt_view`'s call is a no-op on every
row it will ever see; `error_detail` was already masked by `ProtectedDetail.__init__` and
`summary` by `redact_text`.

`[추론]` Not a live leak — a control with no independent evidence, in the module whose
docstring presents it as the API's half of SEC-004's boundary, and the layer that would have
to catch anything the writer missed. It composes badly with the parallel review's F3, which is
the same gap one layer in.

## B5 — the N5 shape recurs five more times. **Major.**

`DEBT-REVIEW-2026-08-19.md` N5 asked whether a duplicated guard is duplicated in its tests.
`[측정]` Measured, per clause:

| Guard, per copy | Collector | Normalizer |
|---|---|---|
| `_require_source` — `enabled` | ambiguous | **GREEN** |
| `_require_source` — `kind` | **GREEN** | **GREEN** |
| `_require_source` — `addon_id` | **GREEN** | ambiguous |
| `_check_outcome` — return type | **GREEN** | **GREEN** |
| `_check_outcome` — emitted count | RED | RED |
| `_require_completion_transaction` | RED | RED (repaired 08-19) |
| `_require_config` — schema validation | RED (control) | **ambiguous, likely GREEN** |

`[확인 사실]` The two `_require_source` bodies are textually identical for those three
clauses, and `test_normalizer_capability.py` contains no configuration-schema test at all.

Two more instances outside `capabilities.py`:

- `[측정]` `_MONTH_LENGTH` is duplicated between the two DataLab collectors. Making February
  accept 31 days is **GREEN** in `shoppinginsight` and probably green in `searchtrend` —
  **both copies untested**. The reviewer measured the duplication independently at **70%** of
  the smaller distinct code-line set, corroborating N1's 72%.
- `[측정]` `TestNeitherAddOnEverSeesACredential` is parametrized over the two DataLab
  collectors only. `collector.naver.blog` also declares `needs_credential = true` and **is
  scanned by nothing**: planting `"X-NCP-APIGW-API-KEY"` and a literal URL in its handler is
  **GREEN**, while the identical plant in `searchtrend` is **RED**.

## B6 — `job.claim_conflict` violates I5 and reports conflicts that did not happen. **Major.**

`CONTRACT-JOB-0.1.md`: *"**I5 — Correlation is total.** Every log line, attempt row, and API
response concerning a job carries its `correlation_id`."*

`[확인 사실]` `platform_core/jobs/store.py:912-919` is called from `claim_next` before any
correlation scope is entered, so the line **always** carries `correlation_id: null`.

`[측정]` Worse, it is a TOCTOU race: `CLAIM_NEXT` and `CLAIMABLE_EXISTS` are separate
statements with separate `now()`. 400 trials, one job scheduled 1.2 ms into the future,
nothing else running: **3 false conflicts**. Nothing was held elsewhere.

`[측정]` This makes `test_job_002_shares_one_correlation_id_across_both_attempts` **flaky: 2
failures in 30 unmutated runs** of the pristine tree.

`[추론]` `test_ops.py` states *"No claim conflict can occur in a single-worker run"*, which is
false in general; OPS-004 is safe only because no job in it is scheduled into the future.
`EXP-001` already records `claim_conflicts` as *"not a usable contention measure"* — this adds
false positives to insensitivity.

## B7 — absence assertions that would pass against a system producing nothing. **Major.**

`EXP-003`: *"an absence assertion with no positive control passes equally well against a guard
that checks nothing."* `[측정]` The credential-absence pair is exactly where it fails, and
`test_capabilities.py` claims in its own text that *"every assertion here is paired with the
one that makes it mean something."*

- **`test_the_value_is_in_no_log_line`** — `[측정]` the stream contains **1150 bytes, events
  `['job.transition']` only, zero `addon.*` events**. `run_collect` binds no logger, so
  `_CollectRun._log` returns immediately. The capability layer could log the credential in
  plaintext on every fetch and this test would pass.
- **`test_the_value_is_in_no_recorded_field`** — `[확인 사실]` `request_summary` is
  `{"url", "host"}` and never holds a header; the `ScriptedTransport` never calls
  `strip_protected_headers`. The assertion cannot fail whatever `PROTECTED_HEADERS` contains.
- **`test_a_get_endpoint_still_sends_no_body`** — `seen_bodies.append` exists only in
  `do_POST`. `[측정]` Making every GET carry a body is **GREEN**.
- **`test_no_recorded_response_header_reaches_the_operator_unstripped`** — asserts against
  `/sources/{id}/raw`, whose `raw_summary` returns four scalars and no header under any
  circumstance.
- **The dashboard normalize pair.** The case docstringed *"The positive control. A screen that
  disabled everything would pass above."* splits markup on `<tr` and takes the first row
  containing the normalizer's name — but `SourceTable` renders before `SnapshotTable`, so it
  inspects the normalizer's **source** row, which contains no button at all. `[측정]` Making
  every normalize button `disabled` is **GREEN**, and so is leaving a disabled source's
  buttons live.
- **`TestDeterminism::test_two_runs_of_one_version_over_one_snapshot_agree`** — `[측정]` with
  `record_results` made a no-op this test **passes** (`[] == []`) while its sibling fails. The
  named test proves nothing alone; the class as a whole does catch it.

## M1 — the guards about guards. **Moderate.**

`[측정]` Every intended control fired — `allow_loopback` in an add-on, add-on importing
`platform_core`, `platform_core` importing `domain`, `addon_api` importing `platform_core`,
domain vocabulary in `platform_core` Python and SQL, a credential literal in `searchtrend`, a
collector skipping config validation: **all RED**.

And the gaps, which confirm `ADVERSARIAL-REVIEW-2026-08-18.md` **F9 by measurement** rather
than by construction — the scan is `EXPERIMENT_ROOT.rglob("*.py")`:

| `allow_loopback` planted in | Result |
|---|---|
| `domain/migrations/0002_domain.sql` — F9's predicted P0-B shape | ambiguous, likely GREEN |
| `addons/collector.naver.blog/addon.toml` | **GREEN** |
| `experiments/integrated-p0/README.md` | **GREEN** |
| repo-root `tests/environment/` | **GREEN** |

`[측정]` Domain vocabulary in `dashboard/src/api.ts` is **GREEN** — the P0-A guard's own
documented coverage limit, now measured rather than assumed.

`[측정]` The credential scan's docstring-stripping is likely unpinned: its positive control
re-parses a **fresh, unstripped** tree, so it controls "literals are readable", not the
stripping step the real scan performs.

## M2 — the suite can be silently reduced to 33 tests. **Moderate.**

`[측정]` Narrowing `pyproject.toml`'s `testpaths` from
`["tests", "experiments/integrated-p0/tests"]` to `["tests"]` drops **1039 of 1072 tests** and
the suite reports **`33 passed`** — green, no error, no warning.

`[추론]` `tests/environment/test_module_layout.py` asserts `pythonpath` names the experiment
root. There is no sibling for `testpaths`, which is the setting deciding whether any of the
guards run at all.

## M3 — database CHECKs that nothing exercises. **Moderate.**

`[측정]` GREEN: `snapshot_manifest_digest_is_a_sha256`,
`snapshot_item_digest_is_a_sha256`, `snapshot_item_ordinal_is_zero_based`,
`snapshot_item_count_is_not_negative`, `raw_envelope_digest_is_a_sha256`,
`normalized_result_digest_is_a_sha256`, `job_attempt_number_is_one_based`.

`[추론]` The digest and ordinal constraints on the snapshot tables — the ones OQ-003's
determinism claim leans on — are held by the schema and asserted by nobody.

## M4 — add-on validation limits. **Moderate.**

`[측정]` GREEN: `searchtrend` `MAX_KEYWORDS` 20→2000 and its `DEVICES`/`GENDERS`/`AGE_BANDS`
widened; `shoppinginsight` `MAX_KEYWORDS` 5→500 and February accepting 31 days;
`collector.naver.blog` accepting an undefined sort; `normalizer.naver.blog`'s `_POSTDATE`
losing its `$` anchor; `normalizer.naver.trend`'s `DIMENSIONS` dropping two of three.

`[추론]` `DIMENSIONS` is the one worth acting on: DP-021 admits three, the ShoppingInsight
collector emits all three, and `test_normalizer_naver_trend.py` only ever uses
`search_keyword`. The group and category count limits *are* tested in both add-ons; the
keyword count limits are tested in neither.

## M5 — documentation stating controls that do not exist. **Major.**

`[확인 사실]` Each verified against the code:

| Claim | Reality |
|---|---|
| `addon_host/__init__.py` — *"No capability is implemented."* | `capabilities.py` is 986 lines implementing collector and normalizer capabilities |
| `addon_host/settings.py` — *"`platform_core` … is not modified by this work, so the P0-A gate's evidence stands unchanged"* | `git diff --shortstat f83fe3c -- platform_core` = **7 files changed, +193 −12** |
| `addon_host/worker.py` — *"a source needing one is refused by the outbound guard rather than served by a guess made here"* | `capabilities.py` calls `credential_headers(profile)` and attaches them |
| `capabilities.py` — *"The outbound obligations stay on the platform — four of the six"* | contradicted by the paragraph below it and by `_limits_of` |
| `EXP-003` Result — *"findings are unrepaired… F1, F2, F3 blocking"*, *"Only `collector` is bound"* | all three repaired; two normalizers run end to end. `README.md` sends readers here *"before building on the capability layer"* |
| `evidence/…/README.md` — three files changed under `platform_core`/`dashboard` since `f83fe3c` | six, including `jobs/runner.py` (+64) |
| `docs/conventions/addon-authoring.md` — gives `context.fetch(endpoint_ref, params)` | DP-020 added a third `body` argument. The guide contains **zero** occurrences of `body` or `POST`, and **cannot produce two of the three committed collectors**. `AGENTS.md` sends add-on authors here |
| `docs/decisions/README.md` "Active decisions" | lists 8; **DP-018, 012, 013, 014, 015 are all `ACCEPTED_FOR_POC` and absent**, while `AGENTS.md` says to treat those as constraints |
| `p0-security.md` SEC-001…006 vs `tests/acceptance/SEC-001…004` | two numbering schemes; **none of the four overlapping ids agree** |
| `AGENTS.md` — *"Store unstable contracts only under `contracts/experimental/`"* | the add-on contract has **no document there** |

## Minor

- `[측정]` GREEN: no-SQLSTATE-transient, any `module:attr` entry point, API page and event
  caps raised a thousandfold, `_WITHHELD` changed, redaction cycle handling, three
  `results.py` type checks, and source config served unredacted by the API.
- `[측정]` The `Host` header line is **GREEN and benign** — `http.client` supplies the same
  value. Recorded precisely because it reads as load-bearing;
  `ADVERSARIAL-REVIEW-2026-08-18.md` F6 said the same and it still holds.
- `[측정]` **JOB-007 is load-sensitive.** Its 30-second settle budget for 200 jobs × 4
  processes times out under CPU contention: three standalone runs under load gave 1, 3 and 1
  failures; unloaded it passes.
- `[추론]` `addon_kit/harness.py` says *"**Four** things the platform does are absent by
  construction"*. At least two more are: its `advance_cursor` accepts a `None` value and any
  stream name, both of which the platform refuses.
- `[추론]` `test_credentials.py` hard-codes a path under `var/`. Any checkout where `var` is a
  symlink or a mount fails it for reasons unrelated to the guard — which contaminated all 208
  of the reviewer's runs.

## What the reviewer could not break

- `[측정]` The in-repo secret-store guard **holds**; its apparent GREEN was the reviewer's own
  `var` symlink. Re-run against a real `var` directory it is RED.
- `[측정]` Reverting F2's `_settle` repair produced **91 failures and 111 errors**. That repair
  is thoroughly tested.
- `[측정]` DP-019 D4's determinism is genuinely pinned: a constant digest, an unsorted
  canonical form, and an ASCII-escaping one are all RED.
- `[측정]` **`ADVERSARIAL-REVIEW-2026-08-18.md` F6 items 3 and 5 are repaired** —
  `PROTECTED_HEADERS` is now pinned by `test_credentials.py` and by being a precondition of
  `CredentialPart`, and `_UNBOUND_KINDS`/`importer` is covered.
- `[측정]` F6's other five are **still open**: `resolve`'s absolute-path check,
  `_advance_cursor`'s null-cursor check, `is_reserved`, `_check_outcome`'s `isinstance` (both
  copies), and `_hop`'s `Host` header.
- `[확인 사실]` **No dead guards** — every `_require_*` / `_check_*` has a non-test call site.
- Config, manifest, loading and registration guards are solid: cross-checks, the contract
  gate, distinct add-on ids, add-on id validation, and the three config refusals are all RED.
- `[측정]` `ruff` clean, `mypy --strict` clean over 92 files, the committed evidence SHA-256s
  all verify, all 16 acceptance scenarios have executable counterparts, and there are no
  orphan test files.

## Still ambiguous — 8 of 208

Failed only in the two noise tests and need one more quiet run. The reviewer's predictions,
stated so they can be checked: `AD-st-monthlen` (likely GREEN), `H-cfg-normalize` (likely
GREEN — N5's sixth instance), `CAP-src-c-enabled`, `CAP-src-n-addon`, `G-loop-sql`,
`G-normalizer-url`, `OUT-addr-loopback` (likely GREEN but benign — `127.0.0.1` is also
`is_private`), `OUT-lim-reqbytes`.

## Work items

Ranked. Nothing here is done; this list is the handoff.

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | B1 — SEC-006 sandbox precondition unperformed while P0-B makes real requests | **Blocking** | **waived 08-19** — [DP-023](../../docs/decisions/DP-023-sec-006-waived-for-p0.md) |
| 2 | B2 — redaction tests parametrized from `REDACTED_KEYS` | Major | **repaired 08-19** |
| 3 | B3 — `DEFAULT_LIMITS` values unpinned; the test for them is a self-comparison | Major | **repaired 08-19** |
| 4 | B6 — `job.claim_conflict`: null correlation id, false conflicts, a real flake | Major | **repaired 08-19** — see below |
| 5 | B7 — the credential-absence pair, the GET-body control, the dashboard pair | Major | **repaired 08-19** |
| 6 | B5 — five more N5 instances | Major | **repaired 08-19** — see below |
| 7 | M5 — documents stating controls that do not exist; the authoring guide predates DP-020 | Major | **repaired 08-19** — 8 of 10; see below |
| 8 | B4 — API redaction is an untested no-op | Moderate | **repaired 08-19** |
| 9 | M2 — `testpaths` can be narrowed silently | Moderate | **repaired 08-19** |
| 10 | M1, M3, M4 — guard scan roots, snapshot CHECKs, add-on limits | Moderate | **repaired 08-19** |


## Repair record — B6, 2026-08-19

`[측정]` Repaired test-first. Two tests were written and watched to fail before any
production change:

| Test | Failure observed before the fix |
|---|---|
| `test_a_claim_conflict_names_the_job_it_could_not_take` | `assert None == 'corr-held'` — the I5 violation exactly as reported |
| `test_a_claim_that_finds_nothing_decides_the_conflict_from_one_look` | `a claim that found nothing looked at the queue 2 times` |

`[결정]` The conflict probe was folded into `CLAIM_NEXT` as a `conflict` CTE guarded by
`not exists (select 1 from candidate)`, and the statement now returns exactly one row so the
answer arrives with the claim. `CLAIMABLE_EXISTS` has no caller and was deleted.

`[결정]` The line carries the held job's `correlation_id`, read in the same statement. This
satisfies I5 **as written** rather than reinterpreting what *"concerning a job"* means; the
row is readable because the other transaction holds a write lock, which does not block a
read. No contract change was needed and none was made.

`[측정]` Verification:

| Check | Before | After |
|---|---|---|
| `test_job_002`, 30 runs of the tree | 2 failures (reviewer) | **0 failures** |
| Full suite | 1130 passed, 14 skipped | **1132 passed, 14 skipped** |

`[측정]` Mutation verification — each applied alone, then reverted:

| Mutation | Result |
|---|---|
| drop `correlation_id=` from the log call | **1 failed** |
| reintroduce a second statement in the nothing-claimed path | **1 failed** |
| `cf.id is not null as conflict_exists` → `false` | **1 failed** |

`[확인 사실]` `tests/environment/test_p0a_boundary_guard.py` refused the first draft: the new
SQL comment used *"snapshot"* (MVCC) and *"source"* (a one-row relation), and the guard
cannot distinguish those from the domain words. The comment was reworded; the guard was not
widened. `[추론]` Fifth repository guard to fire correctly in this session.

`[추론]` One further finding, not in the review. `JobStore`'s class docstring states *"Every
method is one statement, so an autocommit connection gives one transaction per operation."*
That was **false for `claim_next`** for as long as the second statement existed — the same
prose-claims-what-the-code-does-not-do shape this session has now met nine times. The fix
made the docstring true rather than the docstring being edited to match the code.


## Repair record — B5, 2026-08-19

`[결정]` Repaired under [OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md)'s
clause A: the duplicated code stays and is recorded as measured evidence about the layer
rule; what changes is that **the tests stop naming their subjects and start discovering
them**, so the next add-on is covered without anybody remembering.

| Clause | Repair | Watched failure |
|---|---|---|
| credential-literal scan covered 2 of 3 collectors | `tests/test_addon_credential_hygiene.py` discovers every add-on from `addons/*/addon.toml`, plus a test asserting the discovery still finds them all | planted `X-NCP-APIGW-API-KEY` + a vendor URL in `collector.naver.blog`: old scan **4 passed**, new scan **RED on `collector.naver.blog`** |
| `_MONTH_LENGTH` untested in both copies | `tests/test_addon_duplicated_helpers.py` discovers every add-on defining `_day_after` and runs the calendar cases against each | February set to 31 days: **RED in both copies** |
| `_require_source` — `enabled`, `kind`, `addon_id` on the normalizer side | `TestTheNormalizersOwnSourceRowIsChecked` | each clause disabled alone: **RED** |
| `_require_config` — no normalizer test at all | same class; the guard was present and raises the more precise `CONFIGURATION_INVALID` | schema validation removed: **RED** |
| `_check_outcome` return type — GREEN on **both** sides | the collector side had no test at all; the normalizer's asserted only that the run failed | both guards removed: **2 failed** |

`[측정]` Suite: 1132 → **1153 passed**, 14 skipped. `ruff` and `mypy --strict` clean.

`[측정]` **The first attempt at the `kind` clause reproduced the very defect B5 reports.**
Pointing the run at the ordinary collector row let the `addon_id` clause do the refusing, so
removing the `kind` clause stayed **GREEN**. It was found by mutating the clause rather than
by reading the test, and fixed by registering a row that differs in `kind` *and nothing
else*. `[추론]` A test that exercises a guard is not the same as a test that isolates it, and
only mutation tells them apart.

`[측정]` **`_check_outcome`'s return-type guard was green for a different reason**: removing
it still failed the run, because the next line to touch the result crashes. A test asserting
only *that* the run failed cannot distinguish a checked refusal from a crash. Both sides now
read the summary.

`[추론]` Two distinct causes hide behind one symptom. A duplicated guard can be untested
because **nobody wrote the second test**, or because **the first test never isolated the
clause**, or because **the system fails anyway for an unrelated reason**. All three appeared
here, and only the first is what N5 originally described.


## Repair record — B4, M1, M2, M3, M4, M5, 2026-08-19

`[측정]` Each repaired test-first or mutation-verified. The watched failure is named per row.

| Item | Repair | Watched failure |
|---|---|---|
| **M2** — the suite can be silently reduced | `tests/environment/test_module_layout.py::test_pytest_collects_both_test_roots` pins both roots, plus a control asserting each still holds tests | narrowing `testpaths` to `["tests"]`: **1 failed** where it previously reported a clean green |
| **M1** — the guard scanned only `*.py` under the experiment root | the `allow_loopback` scan now walks the **whole repository** over `.py .ts .tsx .toml .sql .json .yaml .yml .sh`, skipping build output and prose, with a per-suffix control | planting the flag in `collector.naver.blog/addon.toml` → **RED**; in `0002_domain.sql` → **RED**. `[확인 사실]` `dashboard/src/api.ts` and `domain-view.tsx` had carried the name since the domain surface was written and were never scanned; both are now registered. |
| **M3** — seven database CHECKs exercised by nothing | `TestTheShapeChecksTheDatabaseHolds` — eight cases writing a valid row through the ordinary path and then updating one column past the constraint | replacing three CHECK expressions with `check (true)`: **3 failed** |
| **M4** — `DIMENSIONS` admitted three and one was tested | `TestEveryDimensionDP014AdmitsIsNormalized` — one case per dimension, the admitted set pinned as a literal, and a control for a dimension outside it | dropping two of three: **3 failed** (M4 measured this as GREEN) |
| **B4** + review A's **F3** — redaction masked by key name only, so a sensitive pair inside a string value survived | `_redact` now applies `redact_text` to string values; `bytes` still pass through untouched | three cases RED before the change, with an innocent-string control and a bytes control |
| **M5** — 10 documentation claims | 8 corrected: `addon_host/__init__.py`, `settings.py`, `worker.py`, `capabilities.py`, `EXP-003`'s Result, the P0-A evidence README, `addon-authoring.md` (three new sections), `docs/decisions/README.md`, and the `SEC-00N` collision documented at both ends. The add-on contract now exists as [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md). | not test-shaped; each verified against the code it described |

`[추론]` **Two of these were the same defect at different depths.** B4 and review A's F3 were
found independently, one in the API layer and one in the redactor, and neither reviewer saw
the other's. Fixing the redactor closed both — which is the argument for the single-redaction
point the module's docstring already makes, arriving as evidence rather than as design.

`[측정]` **M1's finding was worse than reported.** The review predicted `.toml`, `.sql` and
`.md` as gaps. The scan was also missing two dashboard source files that *already contained
the name* — not planted, present since the domain surface was written. A guard that names
its subjects had been silently not covering two real files for as long as they existed.

`[측정]` Suite: 1153 → **1213 passed**, 14 skipped. `ruff` and `mypy --strict` clean over 92
files.
