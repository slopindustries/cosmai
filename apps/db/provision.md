# cosmai database provisioning — execution record

Ran against the shared server: docker container `tubedepth-postgres` (postgres:18-alpine),
mapped `127.0.0.1:5433`, superuser role `fleet` (`docker exec` needs no password —
container-internal trust). Verified live first with `docker ps`.

## Procedure

```bash
MIG_PW=$(openssl rand -hex 24); RUN_PW=$(openssl rand -hex 24)
docker exec -i tubedepth-postgres psql -U fleet -d postgres \
  -v mig_pw="$MIG_PW" -v run_pw="$RUN_PW" < apps/db/provision.sql        # Part A + Part C
docker exec -i tubedepth-postgres psql -U fleet -d cosmai      < apps/db/provision_db.sql  # Part B
docker exec -i tubedepth-postgres psql -U fleet -d cosmai_test < apps/db/provision_db.sql
printf 'COSMA_DB_MIGRATOR=%s\nCOSMA_DB_RUNTIME=%s\n' "$MIG_PW" "$RUN_PW" >> ~/.config/cosmai/env
chmod 600 ~/.config/cosmai/env
unset MIG_PW RUN_PW
```

Part B was split into its own file (`apps/db/provision_db.sql`), run once per database, per
the controller's Ruling 2. No password value was printed to stdout at any step.

## Negative verification (Step 4)

```bash
docker exec tubedepth-postgres psql -U fleet -d cosmai -c \
  "SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail(id int);"
# -> ERROR: permission denied for schema cosmai   (confirmed)

docker exec tubedepth-postgres psql -U fleet -d postgres -c \
  "SELECT rolname, rolconnlimit FROM pg_roles WHERE rolname LIKE 'cosmai%';"
# -> cosmai_migrator 2 / cosmai_owner -1 / cosmai_runtime 12   (confirmed)
```

## Host-path verification (Step 5)

Ran the TCP+password connection test from `apps/` (`uv run python - <<'EOF' ...`), connecting
as `cosmai_runtime` with `host=127.0.0.1 port=5433`, reading the password from
`~/.config/cosmai/env`. Result matched the expected value exactly:
`('cosmai, pg_catalog',) ('30s',)`.

## One-shot retry actually taken

The first provisioning attempt (fresh `MIG_PW`/`RUN_PW`, Part A+C and Part B both applied
successfully) failed at the secret-file step: the `~/.config/cosmai/env` append ran under the
default sandboxed Bash tool, which — for this path — writes to a shadow/overlay copy rather
than the real file (the same sandbox profile denies direct *reads* of this path, which is why
an early existence check falsely reported the file as absent). The generated passwords were
then discarded from scratch storage before the mistake was caught, leaving roles provisioned
with unrecoverable passwords. Per the global-constraints one-shot rollback rule, rolled back
with:

```sql
DROP DATABASE IF EXISTS cosmai;
DROP DATABASE IF EXISTS cosmai_test;
DROP ROLE IF EXISTS cosmai_runtime;
DROP ROLE IF EXISTS cosmai_migrator;
DROP ROLE IF EXISTS cosmai_owner;
```

then re-ran the full procedure above with fresh passwords and `dangerouslyDisableSandbox` for
the secret-file write specifically, confirming after the append that both keys were present
exactly once with the expected value length before proceeding to Steps 4–5. Every password
value used in either attempt was generated fresh with `openssl rand -hex 24`; the first
attempt's values were never persisted anywhere and are unrecoverable, which is why the
corresponding roles were dropped rather than reused.

## Result

- Databases: `cosmai`, `cosmai_test` — owner `cosmai_owner`.
- Roles: `cosmai_owner` (NOLOGIN), `cosmai_migrator` (LOGIN, limit 2), `cosmai_runtime`
  (LOGIN, limit 12).
- Schema `cosmai` in each database; `public` has `CREATE` revoked from `PUBLIC`.
- `~/.config/cosmai/env` (mode 600) holds `COSMA_DB_MIGRATOR` and `COSMA_DB_RUNTIME` alongside
  the pre-existing NAVER/YouTube keys, untouched.

## Caveat: `DROP SCHEMA ... CASCADE` + recreate voids the default-privilege grants below

Part B's `ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai ...` grants (the
`cosmai_runtime` SELECT/INSERT/UPDATE/DELETE binding) are keyed to schema `cosmai`'s **OID**, not
its name. If any future procedure runs `DROP SCHEMA cosmai CASCADE; CREATE SCHEMA cosmai;` — as
opposed to migrating the existing schema in place — the new schema gets a new OID and the old
binding does not carry over: every table created after that point is owned by `cosmai_owner` with
**no** grant to `cosmai_runtime` at all, and the failure is silent (an empty result set, not a
permission error). This was found and fixed in M1 Task 4 (`apps/tests/conftest.py`'s
`_reset_schema` reissues this file's Part B grant statements immediately after `create schema`,
over the migrator connection) — see [M1-RECORD §c deviation 5](../../docs/p1/M1-RECORD.md) for
the full account. Any script that drops and recreates schema `cosmai` — including a future
re-provisioning run — must reissue Part B's grants immediately afterward, in the same session, or
verify `cosmai_runtime` can actually `SELECT` from a freshly created table before trusting the
grant is in effect.

## 2026-08-21 — lane test databases (`cosmai_test_2`/`_3`/`_4`)

M2 batch 2a (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §공통 제약): each M2–M7
lane gets its own test database on the same shared server, so parallel `pytest` runs across
worktrees do not race on one schema reset (OQ-006). `cosmai_test` (Lane A) already existed;
this section provisions three more against the roles and passwords already created above —
**no new role, no new password, `~/.config/cosmai/env` untouched.**

Part A (roles, `cosmai`, `cosmai_test`) is not repeated: `cosmai_owner`/`cosmai_migrator`/
`cosmai_runtime` already exist cluster-wide, and `CONNECTION LIMIT` on a role is cluster-wide
too, not per-database, so adding databases does not touch the budget recorded above
(migrator 2 / runtime 12 / sum 16).

```bash
for db in cosmai_test_2 cosmai_test_3 cosmai_test_4; do
  docker exec tubedepth-postgres psql -U fleet -d postgres -c "CREATE DATABASE $db OWNER cosmai_owner;"
done

for db in cosmai_test_2 cosmai_test_3 cosmai_test_4; do
  docker exec -i tubedepth-postgres psql -U fleet -d "$db" < apps/db/provision_db.sql   # Part B, reused verbatim
done

# Part C (role-level session defaults), one block per new database — the same five
# statements provision.sql's Part A+C ran for `cosmai`/`cosmai_test` above.
for db in cosmai_test_2 cosmai_test_3 cosmai_test_4; do
  docker exec tubedepth-postgres psql -U fleet -d postgres -c "
ALTER ROLE cosmai_runtime IN DATABASE $db SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE $db SET search_path = pg_catalog;
ALTER ROLE cosmai_runtime IN DATABASE $db SET statement_timeout = '30s';
ALTER ROLE cosmai_runtime IN DATABASE $db SET lock_timeout = '5s';
ALTER ROLE cosmai_runtime IN DATABASE $db SET idle_in_transaction_session_timeout = '15s';
"
done
```

Negative verification (Step 4's pattern, run once against `cosmai_test_2` as a representative —
Part B is the same statements applied to every database in the loop above):

```bash
docker exec tubedepth-postgres psql -U fleet -d cosmai_test_2 -c \
  "SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail(id int);"
# -> ERROR: permission denied for schema cosmai   (confirmed)
```

`\l` confirms all five databases (`cosmai`, `cosmai_test`, `cosmai_test_2`, `cosmai_test_3`,
`cosmai_test_4`) owned by `cosmai_owner`; `pg_roles` confirms the role/connection-limit set is
unchanged (`cosmai_migrator` 2, `cosmai_runtime` 12, `cosmai_owner` -1). No password value was
generated, printed, or written at any step in this section. `dangerouslyDisableSandbox` was used
for every `docker exec`/TCP step per the M1 global constraints' sandbox note; nothing else needed
it.

**Lane assignment** (`docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §공통 제약): Lane A
(M2/M3/M4) = `cosmai_test`, Lane B (M5) = `cosmai_test_2`, Lane C (M6) = `cosmai_test_3`, M4's
per-add-on worktrees share `cosmai_test_4` and run their add-on tests sequentially against it.
`apps/tests/conftest.py`'s `TEST_DATABASE` now reads `COSMA_TEST_DB` (default `cosmai_test`), so
a lane selects its database by setting that environment variable rather than by editing the
fixture.

## 2026-08-21 addendum — the shared server was replaced mid-M3/M6

`[확인 사실]` The docker container `tubedepth-postgres` (127.0.0.1:5433) was removed outside this
project's control and replaced by `shared-postgres` (postgres:18, **127.0.0.1:5434**, admin role
`platform`, part of a new `shared-db` compose that also containerizes trend-radar). The old
volume's cosmai databases did not survive.

`[측정]` Re-provisioned on `shared-postgres` with the same one-shot procedure (parts A+B+C via
`docker exec -i shared-postgres psql -U platform ...`), all five databases (`cosmai`,
`cosmai_test`, `cosmai_test_2/3/4`), fresh passwords rotated into `~/.config/cosmai/env`
(values never printed). Verified: role limits 12/2/-1, runtime DDL denied
(`permission denied for schema cosmai`), TCP connect from the apps venv on :5434 with
`search_path = cosmai, pg_catalog` and `statement_timeout 30s`.

Every recipe in this repo that says `COSMA_DB_PORT=5433` should be read as `5434` from this
date; per-document corrections land with the M7 sweep rather than by rewriting history here.
