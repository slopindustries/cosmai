-- Part A (cluster level, run as `psql -U fleet -d postgres`) + Part C (role-level session
-- defaults, also cluster level). No password value is ever written to this file — the
-- caller supplies `mig_pw` and `run_pw` as psql variables. See apps/db/provision.md for the
-- exact invocation and apps/db/provision_db.sql for Part B (database-level grants, run once
-- per database against `cosmai` and `cosmai_test`).

\set ON_ERROR_STOP on

-- Part A: roles and databases.
CREATE ROLE cosmai_owner NOLOGIN;
CREATE ROLE cosmai_migrator LOGIN NOINHERIT CONNECTION LIMIT 2 PASSWORD :'mig_pw';
CREATE ROLE cosmai_runtime  LOGIN NOINHERIT CONNECTION LIMIT 12 PASSWORD :'run_pw';
GRANT cosmai_owner TO cosmai_migrator;
CREATE DATABASE cosmai OWNER cosmai_owner;
CREATE DATABASE cosmai_test OWNER cosmai_owner;

-- Part C: role-level session defaults, set per (role, database) pair. Cluster-level, so
-- these are set here rather than in Part B's database-level script.
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE cosmai SET search_path = pg_catalog;
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET statement_timeout = '30s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET lock_timeout = '5s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET idle_in_transaction_session_timeout = '15s';

ALTER ROLE cosmai_runtime IN DATABASE cosmai_test SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE cosmai_test SET search_path = pg_catalog;
ALTER ROLE cosmai_runtime IN DATABASE cosmai_test SET statement_timeout = '30s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai_test SET lock_timeout = '5s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai_test SET idle_in_transaction_session_timeout = '15s';
