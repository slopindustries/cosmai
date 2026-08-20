# M1-RECORD — what M1 built, what was measured, and where it deviates from the contract's P0-A wording

- Milestone: M1 (`platform_core`, plus DB provisioning and migration on the shared PostgreSQL
  server — [DP-032](../decisions/DP-032-p1-database-placement.md)).
- Branch: `p1/m1-platform-core`. Tasks 1–10 commits: `fca5e6c`, `336484e`, `f6ca812`, `506d808`,
  `9f73785`, `a4511c7`, `a2757c0`, `3e42f60`, `4a20336` (Task 1's `cc02fb5` predates the DB work).
- Date: 2026-08-21.
- Consumed by: M2 planning and the T12 adversarial review, per the Task 11 brief.

## (a) Provisioning evidence

`[확인 사실]` Server identity, confirmed with `docker ps` before provisioning
(`apps/db/provision.md`): docker container `tubedepth-postgres`, image `postgres:18-alpine`
(PostgreSQL 18.6), reachable at `127.0.0.1:5433`. Administrative operations ran as the container's
`fleet` superuser over `docker exec` (container-internal trust, no password); application roles
connect over authenticated loopback TCP.

`[측정]` Negative verification (Task 2, `apps/db/provision.md` Step 4), run against the live
server on 2026-08-21:

```
SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail(id int);
-> ERROR: permission denied for schema cosmai
```

`[측정]` Role connection limits, queried the same session:

```
SELECT rolname, rolconnlimit FROM pg_roles WHERE rolname LIKE 'cosmai%';
-> cosmai_migrator 2 / cosmai_owner -1 / cosmai_runtime 12
```

`cosmai_owner` is `NOLOGIN` — its `-1` (unlimited) is not an operational connection budget, since
nothing can open a session as that role directly; it is only reached via the migrator's
`SET ROLE`.

`[측정]` Host-path TCP+password verification (Task 2, `apps/db/provision.md` Step 5), run from
`apps/` as `cosmai_runtime` with `host=127.0.0.1 port=5433`, credential read from
`~/.config/cosmai/env`:

```
('cosmai, pg_catalog',) ('30s',)
```

— the first tuple is the connected role's effective `search_path` (`cosmai, pg_catalog`, see §d);
the second is its effective `statement_timeout` (`30s`), matching the global-constraints fixed
budget value. No password value appears in this record, in `apps/db/provision.md`, or in any
commit; `~/.config/cosmai/env` stays outside the repository and is mode 600.

`[확인 사실]` Provisioned objects (`apps/db/provision.md` Result): databases `cosmai` and
`cosmai_test`, both owned by `cosmai_owner`; roles `cosmai_owner` (NOLOGIN),
`cosmai_migrator` (LOGIN, limit 2), `cosmai_runtime` (LOGIN, limit 12); schema `cosmai` in each
database; `CREATE` revoked from `PUBLIC` on `public`.

`[확인 사실]` The first provisioning attempt was rolled back and redone (Task 1-2 report,
"One-shot retry actually exercised"): a sandbox shadow-copy of `~/.config/cosmai/env` swallowed
the first attempt's generated passwords before they were durably recorded, so the global
constraints' one-shot rollback (`DROP DATABASE cosmai; DROP DATABASE cosmai_test; DROP ROLE
cosmai_runtime; DROP ROLE cosmai_migrator; DROP ROLE cosmai_owner;`) was actually exercised, not
just documented as a contingency. No password value from either attempt was ever printed, logged,
or committed; verified by grepping the committed diff for `password|pw=|secret` (matched only
variable names and prose).

## (b) Scenario result table

`[측정]` Reproduced 2026-08-21 (Task 9, commit `3e42f60`) against `apps/`, no P0 import path in
any new file. Suite total after Task 9: 318/318; after Task 10 (adds one measurement test):
**319/319**. `mypy --strict` and `ruff check` clean on the whole `apps/` tree at both points.

| Scenario | Tests | Contract clause | Result |
|---|---|---|---|
| JOB-001 (successful execution) | 4 | I1, I2, I4, I5 | pass |
| JOB-002 (retryable failure then success) | 4 | I4, I5 | pass |
| JOB-003 (retry exhaustion) | 4 | I4 | pass |
| JOB-004 (permanent failure, no budget spent) | 4 | state-transition rows 3/6 | pass |
| JOB-005 (interruption before/after effect, cases A+B) | 2 | I1, I3; OQ-006 H1 | pass |
| JOB-006 (expired-lease reclaim, fenced worker) | 1 | I2; OQ-006 H2 | pass |
| JOB-007 case A (1 job, 4 workers, 5 reps) | 5 | I2; OQ-006 H2 | pass |
| JOB-007 case B (200 jobs, 4 workers, 5 reps) | 5 | I2; OQ-006 H2 | pass |
| JOB-008 case A (safe-retry refusal + sequential replay) | 2 | I1; see caveat below | pass |
| JOB-008 case B (20 colliding jobs, 5 reps) | 5 | I1 | pass |
| JOB-008 case C (20 distinct keys, control, 5 reps) | 5 | I1 (control) | pass |
| **Total** | **41** | — | **41/41** |

`[확인 사실]` JOB-008 case A's scenario document asks for an operator safe retry of a `SUCCEEDED`
job, which CONTRACT-JOB@0.1's transition table permits only from `FAILED`. This is a restated P0
deviation, not a new one: P0's `test_job_concurrency.py` already recorded the same conflict and
substituted a sequential-replay test for that half of the case; the same substitution was
copy-adapted here unchanged (Task 9 report).

`[측정]` Task 10 carried-measurement 1 — JOB-007 case B (200 jobs × 4 workers), 10 independent
`pytest` process repetitions, 2026-08-21: **0/10 failures**, wall-clock 14s, claim distribution
49–51 of 200 per worker in every run, `claim_conflicts` 0–2/run, no suppressions or rejections.

`[측정]` Task 10 carried-measurement 2 — F16 (the correlation-id test,
`test_job_002_shares_one_correlation_id_and_counts_both_transitions`) under `pytest -n 4`, 20
repetitions, 2026-08-21: **0/20 failures**, wall-clock 16s. `[확인 사실]` Caveat recorded
identically in `docs/open-questions/OQ-006-job-concurrency.md`: selecting one test by node id
under `-n 4` hands it to exactly one of the four xdist worker processes; the other three never
run a test and never trigger the session-scoped schema-reset fixture. This 0/20 result does not
establish that P1's test isolation holds under genuine parallel execution — it establishes only
that the named test does not fail on its own under `-n 4` process-startup overhead. See deviation
7 below for the adjacent whole-suite finding this caveat connects to.

## (c) Contract deviation ledger

Each item below was verified against the actual tree or the cited report before being written
here — quoted, not recalled.

**1. CONTRACT-JOB-0.1 §Provenance and security's "no TCP listener" line is P0-A environment
prose, not a P1 constraint; P1's database sits on real loopback TCP by design.**
`[확인 사실]` The contract's exact text (`contracts/experimental/CONTRACT-JOB-0.1.md:190`, under
"Outbound or source policy constraints"): "The database is reachable only over a local Unix
socket and has no TCP listener at all. Operator surfaces bind to loopback, and a non-loopback
bind is refused as `CONFIGURATION_INVALID`..." `[결정]` DP-032 D1/D4 deliberately places P1's
database on the shared server's real TCP listener at `127.0.0.1:5433`, reached with a password
(`COSMA_DB_*`), because DP-006 D2's Unix-socket-only cluster was itself scoped to P0-A and named
as producing "no evidence about authenticated database access" — a gap D4 exists to close. The
TCP listener in question is `tubedepth-postgres`'s own, not one P1 opens; P1 never binds a
database listener itself. Two P0-A SEC-002 tests asserting no-TCP
(`test_sec_002_no_postgresql_tcp_listener_exists_on_this_host`,
`test_sec_002_the_database_session_is_not_a_tcp_connection`) were deliberately dropped rather
than ported or inverted, since DP-032 makes both assertions false by design (Task 7-8 report,
deviation 1). The operator-API side of SEC-002 — the API's own loopback bind, refused
`CONFIGURATION_INVALID` on a non-loopback config — is retained unchanged and still passes.
**What this deviation does not cover:** any exposure of the database beyond `127.0.0.1` (a
non-loopback bind, a container port mapped to a routable interface, a future multi-host
deployment) is a new decision this record does not authorize or evaluate — DP-032's own Remaining
uncertainty names the server's `max_connections`/extension state as unconfirmed beyond what M1
touched, and nothing in M1 inspected or constrained network exposure beyond the loopback address
actually used.

**2. The transient SQLSTATE branch (classes `08`/`53`/`57`) remains unexercised in M1, exactly
the status the contract itself already records for P0-A.** `[확인 사실]` The contract's own text
(`contracts/experimental/CONTRACT-JOB-0.1.md:178`): "The transient branch is unexercised in
P0-A: no scenario kills a connection mid-statement, so classes `08`, `53`, and `57` have never
been reached. The branch is written and reviewable but carries no measurement..." `[확인 사실]`
Task 5-6's `db/connection.py` reimplements `classify()`/`TRANSIENT_SQLSTATE_CLASSES` against
this rule, including wrapping the migrator's post-connect `SET ROLE cosmai_owner` statement in
the same `try` the connect call uses, and explicitly records: "The transient branch (SQLSTATE
`08`/`53`/`57`) remains unexercised: no test here or in `test_jobs_store.py`/
`test_jobs_runner.py` kills a connection mid-statement, consistent with the contract's own
recorded status for P0-A. Not claimed as tested." No M1 task changed this status. No execution
claim is made for this branch anywhere in M1.

**3. Over-redaction side effect: `credential_ref` is now masked by the substring rule, where P0
treated ref names as safe to show.** `[확인 사실]` The contract's redaction rule
(`contracts/experimental/CONTRACT-JOB-0.1.md:184`): "any mapping key matching, case-insensitively,
`password`, `token`, `secret`, `authorization`, `cookie`, `api_key`, `apikey`, or `credential` is
replaced with a redaction marker," and (`:186`) "Matching is containment, not equality." Task 6's
reconciliation wired `config.py`'s exceptions through the real `platform_core.errors`/
`platform_core.obs.redaction` modules, and `platform_core.secrets.CredentialNotResolved` puts
`{"credential_ref": ref}` into its protected detail. The key `credential_ref` contains the
substring `credential`, so `is_redacted_key` now masks the ref *name* — not a secret value — in
the protected-debug view (Task 5-6 report, deviations 2 and the reconciliation section). This is
a real, observable narrowing from "detail exposes ref names" to "detail exposes that a ref name
was captured." No test currently asserts the raw value survives, so nothing broke, and the
direction is safe (over-redaction, not under-redaction) — but it matters for M2/M5 surfaces that
may want to show an operator *which* credential reference failed to resolve, not just that one
did. Flagged, not fixed, in M1.

**4. Several P0 interfaces changed shape crossing into P1, beyond a name change:**
- `apply_migrations` now returns `list[str]` (the Task 4 brief's literal signature), not P0's
  `tuple[str, ...]`, and drops P0's optional `logger` parameter (no `StructuredLogger` existed
  yet at Task 4; Task 3-4 report, deviation 2). This is the one place the "P0's actual name wins"
  ruling (controller Ruling 3) was not applied, because the brief was explicit and unambiguous
  about the return shape and Task 5+ consumes it directly.
- `db/connection.py`'s `describe()` gained a required `role` argument in this milestone
  (DP-032 D1 splits `runtime` from `migrator` identities where P0 had one connection shape;
  Task 7-8 report, deviation 3) — `worker.py`'s one call site is `describe(self._config,
  "runtime")`.
- `connect()` exists with no `connected()` context-manager wrapper — P0-A's `api/app.py` used
  `with connected(config, autocommit=True) as handle:` throughout; P1 verified empirically that
  an ordinary `psycopg.Connection`'s own `with`-exit already commits-or-rolls-back then closes,
  so every call site became `with connect(config, ...)` with identical behavior (Task 7-8 report,
  deviation 2). Not a contract deviation — `connected()` was never part of CONTRACT-JOB@0.1 — but
  a shape change from the P0 source the briefs said to copy-adapt.
- `COSMA_ADDON_DIR`/`ADDON_DIR_VARIABLE` was dropped from `RECOGNIZED_UNUSED` rather than carried
  forward: P0 recognized it because `addon_host.settings` reads it (DP-008 D1); P1 builds no
  add-on host in M1, so there is nothing yet for the variable to serve. Deferred to the milestone
  that builds the add-on layer (M3), not restored here (Task 3-4 report, deviation 5).

**5. Operational finding: `DROP SCHEMA cosmai CASCADE; CREATE SCHEMA cosmai;` silently voids
`ALTER DEFAULT PRIVILEGES` grants, because the binding is keyed to the schema's OID, not its
name.** `[측정]` Discovered while sanity-checking Task 4 outside the test harness: a fresh
`connect(role="runtime")` against a freshly migrated `cosmai_test` saw zero tables in
`information_schema.tables`, even though the superuser (`fleet`, via `psql`) showed all four
tables present and owned by `cosmai_owner`. `[확인 사실]` Root cause: `apps/db/provision_db.sql`
binds `cosmai_runtime`'s default SELECT/INSERT/UPDATE/DELETE grant via `ALTER DEFAULT PRIVILEGES
FOR ROLE cosmai_owner IN SCHEMA cosmai`, and PostgreSQL keys that binding to the schema's OID.
A literal `DROP SCHEMA cosmai CASCADE; CREATE SCHEMA cosmai;` — the brief's own conftest
instruction, read literally — destroys the old OID and allocates a new one the
provisioning-time binding does not cover; every table created after that reset would be owned by
`cosmai_owner` with **no** grant to `cosmai_runtime` at all: a silent, not-loud failure (empty
result set, no permission error). `[결정]` Fixed by having `apps/tests/conftest.py`'s
`_reset_schema` reissue `apps/db/provision_db.sql`'s Part B grants (`revoke all ... from public`,
`grant usage on schema ... to cosmai_runtime`, both `alter default privileges` statements)
immediately after `create schema`, over the same migrator connection — re-verified manually and
via the full test suite (Task 3-4 report, "A real bug found and fixed before committing"). The
same caveat has been added to `apps/db/provision.md` in this commit (see below) for any future
re-provisioning script that drops and recreates the schema rather than migrating it in place.

**6. The M1 test suite is an invariant-mapped curated subset of P0's job-core tests, not a
line-for-line port; Task 5's commit alone is not independently checkout-buildable.**
`[확인 사실]` P0's four job-core test files total 2793 lines and exercise infrastructure M1's
Task 6 file list does not build (`platform_core.handlers`, `platform_core.worker`,
`platform_core.api`, real multi-process concurrency). Task 6's `test_jobs_store.py` (34 tests)
and `test_jobs_runner.py` (14 tests) are copy-adapted in spirit, mapped explicitly to
CONTRACT-JOB@0.1's I1–I5 and the state-transition table rather than ported line-for-line — the
Task 5-6 report's "Tests" paragraph names exactly what is and is not covered. `[확인 사실]`
Separately: `obs/logging.py` imports `platform_core.errors.ConfigurationInvalidError` and
`obs/metrics.py` imports `platform_core.jobs.state.JOB_STATES`, so Task 5's own package
physically needed `errors.py` and `jobs/state.py` (nominally Task 6 files) to exist before its
tests could import. Both files sat untracked in the working tree from the point Task 5's tests
were verified until the Task 6 commit staged them — every quality-gate run happened against the
complete working tree, never against an isolated checkout, but `git checkout 506d808` alone is
missing `errors.py`/`jobs/state.py` (Task 5-6 report, "Bootstrapping order" and deviation 3). The
branch tip (`9f73785` and later) is checkout-buildable; the intermediate Task 5 commit by itself
is not.

**7. Whole-suite `-n 4` collapses (~300/318 errors); a session-scoped schema reset races per
xdist worker against one shared database.** `[측정]` Reproduced twice (Task 10): 19 passed / 299
errors, then 19 passed / 300 errors, of 318–319 collected — the same suite is 318/318 (later
319/319) run serially. `[추론]` Root cause inferred, not confirmed with a debugger:
`apps/tests/conftest.py`'s `_reset_schema` is `scope="session", autouse=True` and issues
`drop schema cosmai cascade` / `create schema cosmai` against DP-032's one fixed `cosmai_test`
database; under `pytest-xdist`, "session" scope is per-worker-*process*, so `-n 4` starts four
independent sessions, each running its own `_reset_schema` once, racing the same DROP/CREATE pair
against the same physical schema with no coordination between them. P0 avoided this by building
one private database per xdist worker, keyed off `PYTEST_XDIST_WORKER`; P1 has no per-worker
database to key off under DP-032's one-shared-database placement. `[결정]` No fix attempted in
M1 — out of Task 10's measurement-only boundary. Recorded in
`docs/open-questions/OQ-006-job-concurrency.md`'s "M1 Task 10 remeasurement — 2026-08-21" section
as decision-needed. **The single-process suite (`uv run python -m pytest -q`, no `-n` flag) is
the only supported mode for M1**; `-n 4` or any parallel worker count greater than 1 against the
shared `cosmai_test` database is a known, reproducible hazard, not a flake, until this is
resolved by either scoping/locking `_reset_schema` differently or provisioning per-worker
databases.

## (d) `search_path` strategy

`[확인 사실]` `apps/db/provision.sql` sets a role-level default, not a per-session or
per-statement one:

```sql
ALTER ROLE cosmai_runtime  IN DATABASE cosmai      SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE cosmai      SET search_path = pg_catalog;
ALTER ROLE cosmai_runtime  IN DATABASE cosmai_test SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE cosmai_test SET search_path = pg_catalog;
```

`cosmai_runtime` gets `cosmai, pg_catalog` as its default — every unqualified table name it uses
resolves inside the one schema it may touch. `cosmai_migrator` deliberately gets only
`pg_catalog` — no application schema at all — and every DDL statement in
`db/migrations/0001_platform_core.sql` and `jobs/store.py`'s SQL is written schema-qualified to
`cosmai.` regardless (Task 4 and Task 6 reports). The host-path verification in §a above confirms
the runtime role's effective `search_path` is `cosmai, pg_catalog` on a live connection.

`[결정]` This pairing — a role-level default for the role that only ever touches its own schema,
plus explicit qualification everywhere for the role that briefly elevates to `cosmai_owner` — is
the chosen strategy, not the only one PostgreSQL supports (a fully explicit `SET search_path`
per session, or qualifying every statement for both roles, were both available). `[추론]` The
risk `search_path` trust normally guards against — an object placed earlier in the path that
shadows the intended one, letting an unqualified reference silently resolve to an attacker- or
another-tenant's object — depends on another schema or role being reachable on the same path.
DP-032 D1 gives `cosmai` a dedicated database with `public` emptied of application objects and
`CREATE` revoked from `PUBLIC`; no other service's schema exists in `cosmai`/`cosmai_test` at
all, and no cross-database name resolution exists in PostgreSQL without an extension (DP-032
Evidence, H3). The structural precondition for a `search_path`-shadowing attack — a second,
reachable candidate object — is therefore absent in this placement, which is why a role-level
default for `cosmai_runtime` was judged an acceptable convenience rather than a residual risk,
while `cosmai_migrator`'s DDL path (the one role capable of creating objects) still qualifies
everything explicitly as the stricter belt-and-suspenders choice, consistent with the
operating-rules document's rule 0 reasoning DP-032 D1 carries forward ("rule 0's reason is about
`USAGE`/`CREATE` grants and `search_path` trust").

## Gates (end of M1, Task 11)

`[측정]` 2026-08-21, re-run once after this record (no code change in this task):
- Root guard: `.venv/bin/python -m pytest tests/environment -q` — **81 passed**.
- `cd apps && uv run python -m pytest -q` (unsandboxed, real DB on loopback TCP) —
  **319 passed**.
