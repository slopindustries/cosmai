# REVIEW-M1 — adversarial review of `p1/m1-platform-core` (`dev..HEAD`, 11 commits, 53 files)

Reviewer: attacker role (subagent `adversarial-reviewer`, read-only; nothing repaired; transcribed by the orchestrator). Date 2026-08-21. Tree at `6d7dcf5`.

## Verdict: **FAIL** — 3 blocking findings, 11 minor. One gate could not be verified at all (§Unverifiable).

The job core itself is clean — attacked hardest and it held. The blocking findings are in the **evidence layer**: a test named for a property it does not assert, a contract citation in `M1-RECORD` that resolves to the wrong rows, and a behavioral consequence of DP-032 that the deviation ledger does not register.

- Disposition: REWORK before merge. Repairs and the re-verification are recorded in this file's addendum after the fact.

## What held (negative results — these are real results)

`[측정]` **Semantic parity of the job core is exact.** `diff -u` of each P1 file against its P0 original:

| File | Divergence |
|---|---|
| `jobs/state.py` | docstring only |
| `jobs/registry.py` | **byte-identical** |
| `jobs/runner.py` | one blank line removed at `:181` |
| `errors.py` | **byte-identical** |
| `jobs/store.py` | schema qualification (`cosmai.`) and one `coalesce(...)` reflow. No CTE, predicate, lock mode, or assignment changed. |

The claim statement, `_FENCE`, lease-expiry handling, and `APPLY_EFFECT` are unmodified. `obs/*` differ only in a docstring word. `handlers/synthetic.py`, `worker.py`, `api/app.py` differ only where M1-RECORD §c registers. **No unregistered semantic drift in the job core.**

`[측정]` **Isolation holds.** `grep -rn "experiments" apps/ --include='*.py'` → 33 hits, all docstring prose, zero imports. All 11 commits touch zero files under `experiments/`.

`[측정]` **All of §a's provisioning claims reproduce exactly** against the live server: DDL denial, limits 2/-1/12, ownership, role settings (search_path, three timeouts), and deviation 5's OID fix currently in effect (live ACLs + `pg_default_acl` rows).

`[측정]` **I1's absence assertions are not vacuous** (JOB-008 case B: 19 suppressions from 19 distinct job_ids; case C positive control: 20 effects, zero suppressions). No mutation defeating I1, I2, or the fence was constructed that left the suite green.

`[측정]` **The `cosmai_test` guard holds against subprocesses** — `worker_environment()` overrides `COSMA_DB_NAME` with the test config's name; every spawn routes through it; production `cosmai` holds no tables (confirmed live).

`[측정]` **No credential leaked** — zero `\b[0-9a-f]{48}\b` matches in the full range incl. `uv.lock`; zero `PASSWORD '...'` literals; two amended-away commits checked separately (message-only amends).

`[측정]` **Gates runnable by the reviewer:** root guard 81 passed; apps collection 319 tests; ruff clean; mypy --strict clean (39 files). **Budget arithmetic closes** (12+2+2=16; the "slack: 2" naming is F9's subject). **Scenario table counts verified: all eleven rows correct, total 41.**

## Blocking findings

### F1 — BLOCKING. Transition row 8's only test asserts neither half of its required side effect

`apps/tests/test_jobs_store.py:197-212` — named/documented as the reclaim-into-exhausted-budget transition (contract row 8: prior attempt closed `ABANDONED`, `terminal_reason = LEASE_ABANDONED`, **no new attempt opened**), but its assertions (`second is None`, state, terminal_reason, lease_owner, in-process `abandoned_attempts` counter) never read `job_attempt` rows or an `outcome`. `[측정]` A store mutation (drawing the `opened` CTE from `candidate` instead of `started`) inserts a spurious open attempt on every exhausted reclaim and the whole suite stays green — a genuine I2/I3 violation the suite is blind to. No acceptance scenario reaches row 8 (`LEASE_ABANDONED` as terminal_reason occurs exactly once, in this test). Minimal repair: assert `len(attempts_of(...)) == 1`, `outcome == "ABANDONED"`, `finished_at is not None`.

### F2 — BLOCKING. `M1-RECORD` §b cites contract rows JOB-004 does not exercise

`docs/p1/M1-RECORD.md:75` — cell "state-transition rows 3/6" sits in a column headed **Contract clause**, but contract rows 3/6 are the reclaim path and the retryable-exhaustion path; JOB-004 exercises **row 7** (permanent failure, one attempt). The 3/6 numbers are correct only against the *scenario document's own* table (`tests/acceptance/JOB-004-...md:34-39`) — the defect is the transplant into a contract-headed column. Over-claims coverage in exactly the region F1 shows is thinnest.

### F3 — BLOCKING. DP-032's new `lock_timeout` makes a transient condition classify as a non-retryable worker death; unregistered

`provision.sql` sets `lock_timeout='5s'` (P0 set none — the SQLSTATE was unreachable); `_FENCE` ends `for update of j` (blocking); `55P03` ∉ transient classes so `classify()` → `ConfigurationInvalidError`, retryable=False; `worker.py:330-332` then **dies**. `[측정]` Measured statically: `55P03 → ConfigurationInvalidError False`, `25P03 → ConfigurationInvalidError False`, `57014 → PlatformTransientError True` — the three new session defaults do not behave alike. A lock wait >5s on the job row (API retry racing a fenced completion is the concrete path) terminates the worker with the class the contract reserves for "no number of retries fixes it". Needs a decision: widen the transient set or register as accepted-and-unmeasured. `[가설]` Actual firing not reproduced (no DB access for the reviewer).

## Minor findings

- **F4** `M1-RECORD.md:236` — "P0's four job-core test files total 2793 lines" is wrong; measured **2658** (961+864+500+333). §c's own preamble claims quote-not-recall.
- **F5** §c deviation 4 — "identical behavior" for `connected()`→`connect()` is false in the non-autocommit case: P0's `connected()` deliberately rolled back on exit; `psycopg.Connection.__exit__` commits. All api call sites are autocommit (no-op), but `conftest.py:146`'s `runtime_connection` is non-autocommit; `test_migrate.py:78-80` even carries a compensating rollback. A safety property recorded as preserved was dropped.
- **F6** `conftest.py:160-163` claims "Nothing here is autouse … runnable without a live server" while `:91`'s `_reset_schema` is session-scoped autouse; `[측정]` running the three "server-free" modules against a dead port yields 173 errors.
- **F7** `apps/README.md:4-7` describes a convention as a control — no root guard scans `apps/` (`grep -rn "apps" tests/environment/*.py` → zero); the 81-test guard would stay green if `from experiments...` were added under `apps/`. Isolation is currently true; the control is missing.
- **F8** M1-RECORD's Gates command, run as written, produces 319 errors (required `COSMA_DB_*` env unset); the only complete recipe lives inside OQ-006 and additionally needs `with-secret-source.sh`. OQ-006's recipes also set `COSMA_DB_NAME=cosmai` (production) — harmless only because conftest forces `cosmai_test`.
- **F9** `service-db.json` silently revises DP-032 D2's budget split (migrator 2/reserve 2/"slack" 2 vs draft migration 1/headroom 5) — pre-authorized by D2 but registered nowhere; "slack" is a one-off token. D2's handoff asked M1 to confirm the budget against the real server before fixing `CONNECTION LIMIT`; the confirmation was skipped. `[측정]` Reviewer supplies it: `max_connections=100`, 17 active — 16 fits comfortably.
- **F10** Root `.gitignore`'s private-data patterns are root-anchored; `apps/tests/fixtures/private/…` etc. are **committable**. No leak occurred; the preventive control has a hole.
- **F11** Two off-by-one counts around the grant reissue: conftest says "four statements" (five); §c deviation 5 says "both alter default privileges statements" (three). Substance verified correct live.
- **F12** I3 ("no stranded state") asserted nowhere — two instances tested, no invariant-level check.
- **F13** I4's inequality never asserted; backoff untested past attempt 1 (a constant-50ms backoff would pass the suite).
- **F14** `POST /jobs/{job_id}/retry` has zero test coverage — the operator-facing half of transition row 9; correlation_id checked only on two GET routes.
- Methodological note: §a's secret-scan citation (`password|pw=|secret` grep) would not catch a bare 48-hex value; the claim survives the stronger shape scan, which the record should cite instead.

## Unverifiable — named, not counted as passes

1. `cd apps && uv run pytest` **319 passed** — reviewer's constraints forbade unsandboxed execution; collection/ruff/mypy/root-guard verified instead. BLOCKED, not confirmed.
2. All Task 10 measurement figures (JOB-007 0/10; F16 0/20; `-n 4` collapse) — same blocker; the `-n 4` hazard IS recorded in OQ-006 correctly.
3. F3's actual firing (no >5s lock wait produced).
4. Whether `.superpowers/sdd/` (untracked, self-ignored) counts as a prohibited "session snapshot" under AGENTS.md — owner's call.

## Recommended disposition

**REWORK.** F1/F2 mechanical before merge; F3 needs a decision; F4–F11 record/control corrections; F12–F14 named as gaps rather than fixed in M1. Everything the record claims about the job core's fidelity to P0 is true, verified line by line. The failures are in the layer that describes the work, not the work.

---

## Disposition addendum (orchestrator, 2026-08-21, post-repair)

| Round | Commit | Scope | Independent re-verification |
|---|---|---|---|
| 1 | `b581820` | F1–F14 per controller rulings (55P03→transient; convention→control guard; budget registered) | all fourteen ADDRESSED; F1's durable-row gap closed regardless of which assertion catches which mutation; two new blocking doc defects (stale 319 count under a fresh `[측정]`; "no database required" contradicted by the same wave's own F6 text) |
| 2 | `6732fc8` | D1–D3, D5–D7 (text-level; D4 parked — the plan file is point-in-time, the manifest is authoritative) | orchestrator reproduced each edit directly: quoted output matches an actually-run command, guard-limit sentences present, root guard 82 |

`tests/environment`: 82 passed (81 + `test_p1_isolation.py`, the F7 convention promoted to a control). The apps suite: 328 passed per the fixer at rounds 1–2; the re-reviewer could independently verify collection (328), mypy (40 files), ruff, and every static claim, but not the live-DB run — recorded as their named gap, discharged by the fixer's runs and the orchestrator's earlier direct runs.
