"""Database access for the disposable P0-A platform core.

Three modules, and deliberately nothing else:

* ``connection`` — a thin wrapper over ``psycopg.connect``. DP-006 D2 makes the
  cluster passwordless and reachable only through a Unix socket, so a connection
  needs a directory, a database name, and a user, and nothing that could be a
  credential.
* ``migrate`` — the numbered plain-SQL applier DP-006 D4 chose over Alembic.
* ``migrations/`` — the SQL itself, which is the authoritative schema named by
  CONTRACT-JOB@0.1.

DP-006 D5 keeps psycopg 3 in view rather than behind an object mapper, because
the statements that matter to the gate reviewer are the claim query, the lease
predicate, and the idempotent insert. There is no pool here either: P0-A runs a
handful of processes on one host, so a pool would add lifetime semantics without
reducing any named uncertainty.
"""
