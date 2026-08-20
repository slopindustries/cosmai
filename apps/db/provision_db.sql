-- Part B (database level). Run once against each of `cosmai` and `cosmai_test`:
--   docker exec -i tubedepth-postgres psql -U fleet -d cosmai      < apps/db/provision_db.sql
--   docker exec -i tubedepth-postgres psql -U fleet -d cosmai_test < apps/db/provision_db.sql
-- No password value is used or written here.

\set ON_ERROR_STOP on

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SET ROLE cosmai_owner;
CREATE SCHEMA cosmai;
RESET ROLE;
REVOKE ALL ON SCHEMA cosmai FROM PUBLIC;
GRANT USAGE ON SCHEMA cosmai TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  GRANT USAGE, SELECT ON SEQUENCES TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
