"""Database access for the P1 platform core.

Copy-adapted from ``experiments/integrated-p0/platform_core/db/``. Three
modules, deliberately nothing else:

* ``connection`` — a thin wrapper over ``psycopg.connect``. DP-032 D1/D3/D4
  move the cluster P0-A had (repository-local, passwordless, Unix-socket-only)
  onto a dedicated database on a shared server, reached over loopback TCP with
  a password resolved through ``platform_core.secrets``. A connection needs a
  host, a port, a database name, a role, and a credential ref — the runtime
  role for ordinary use, the migrator role (which ``SET ROLE``s itself to the
  schema owner) for DDL.
* ``migrate`` — the numbered plain-SQL applier DP-006 D4 chose over Alembic,
  kept by DP-032 D3 for the same reason: P1 is reconstructing already-tested
  transaction-boundary code, and an ORM would mean re-validating it rather than
  reusing it. Its version table and every DDL statement are schema-qualified to
  ``cosmai`` (DP-032 D1) — P1's database has other schemas' worth of headroom in
  it (``public``, stripped of ``CREATE``) but owns exactly one, and everything
  the applier touches says so explicitly.
* ``migrations/`` — the SQL itself, the authoritative schema named by
  CONTRACT-JOB@0.1, carried forward with every object schema-qualified.

DP-032 D3 keeps psycopg 3 in view rather than behind an object mapper, for the
same reason DP-006 D5 did: the statements that matter to a reviewer are the
claim query, the lease predicate, and the idempotent insert. There is still no
pool here — Task 3-4 build no worker or API process yet to hold one, and a
pool's checkout/lifetime/recycling semantics are exactly the concern DP-032 D1
defers to whichever later task builds the process that needs one.
"""
