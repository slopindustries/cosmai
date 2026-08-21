"""Apply numbered plain-SQL migrations in filename order (DP-006 D4, kept by DP-032 D3).

Copy-adapted from ``experiments/integrated-p0/platform_core/db/migrate.py``. The
applier is unchanged in shape: it records each applied version, skips versions
already there, and wraps each file in its own transaction so a half-applied
file leaves no recorded version behind. The autocommit check is unchanged for
the same reason P0 had it — in psycopg 3, ``connection.transaction()`` opens a
real transaction only when none is already running; inside an implicit one it
opens a savepoint instead, which releases without committing, and the per-file
commit boundary this module exists to provide would silently not be there.

**What DP-032 changes.** P0's version table (and every bootstrapped or applied
statement) lived in the connected database's default search path. DP-032 D1
gives P1 exactly one schema, ``cosmai``, inside its own dedicated database, and
D3 requires every DDL statement — including the applier's own bootstrap — to be
schema-qualified rather than relying on ``search_path``. That matters here
specifically: ``apps/db/provision.sql`` sets the migrator role's
``search_path`` to ``pg_catalog`` alone (unlike the runtime role's
``cosmai, pg_catalog``), so an unqualified ``schema_migrations`` reference from
a migrator connection would not resolve to ``cosmai.schema_migrations`` even by
accident — it would simply fail, which is the intended fail-safe, but
schema-qualifying every statement is what actually makes the applier correct
rather than merely lucky.

**Who may call this.** ``apply_migrations`` only checks that its connection is
autocommit; it does not itself verify the connection's role. The privilege that
makes its DDL succeed comes from ``platform_core.db.connection.connect(role="migrator")``,
which opens as ``cosmai_migrator`` and issues ``SET ROLE cosmai_owner`` before
returning — a connection this module receives already elevated, not one it
elevates itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg

from platform_core.config import ConfigurationInvalidError

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"

SUFFIX = ".sql"

#: DP-032 D1: P1's one schema inside its own dedicated database.
SCHEMA = "cosmai"

VERSION_TABLE = f"""
create table if not exists {SCHEMA}.schema_migrations (
    version    text        primary key,
    applied_at timestamptz not null default now()
)
"""


def migration_files(directory: Path = MIGRATIONS_DIRECTORY) -> tuple[Path, ...]:
    """Every migration, in the filename order that is also the apply order."""
    return tuple(sorted(directory.glob(f"*{SUFFIX}")))


def applied_versions(connection: psycopg.Connection[Any]) -> frozenset[str]:
    """Versions already recorded. Creates the bookkeeping table if it is absent."""
    connection.execute(VERSION_TABLE)
    rows = connection.execute(f"select version from {SCHEMA}.schema_migrations").fetchall()
    return frozenset(str(row[0]) for row in rows)


def apply_migrations(
    connection: psycopg.Connection[Any],
    directory: Path = MIGRATIONS_DIRECTORY,
) -> list[str]:
    """Apply every unapplied migration. Returns the versions applied by this call.

    ``connection`` must already be autocommit — see the module docstring — and
    is expected to be a migrator connection already ``SET ROLE``'d to
    ``cosmai_owner`` (``platform_core.db.connection.connect(role="migrator")``).
    """
    if not connection.autocommit:
        raise ConfigurationInvalidError(
            "migrations need an autocommit connection so that each file commits "
            "in a transaction of its own; see platform_core.db.migrate"
        )
    already = applied_versions(connection)
    applied: list[str] = []
    for path in migration_files(directory):
        version = path.stem
        if version in already:
            continue
        with connection.transaction():
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute(
                f"insert into {SCHEMA}.schema_migrations (version) values (%s)", (version,)
            )
        applied.append(version)
    return applied
