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
