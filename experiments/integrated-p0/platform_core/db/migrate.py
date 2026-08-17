"""Apply numbered plain-SQL migrations in filename order (DP-006 D4).

The applier is small on purpose. It records each applied version in
``schema_migrations``, skips versions already there, and wraps each file in its
own transaction so that a half-applied file leaves no recorded version behind. A
migration and the row that says it ran commit together or not at all; anything
weaker produces a database whose recorded state is a claim rather than a fact.

**The connection must be in autocommit mode**, and this is checked rather than
assumed. In psycopg 3, ``connection.transaction()`` opens a real transaction only
when none is already running; inside an implicit one it opens a savepoint
instead, which releases without committing. A migration applied that way is
durable only when something else later commits, so the per-file boundary this
module exists to provide would silently not be there.

``schema_migrations`` is created here rather than in ``0001``. The applier must
read that table to decide whether ``0001`` has run, so the table has to exist
first; ``create table if not exists`` is the bootstrap, and it is the one
statement in the system that is allowed to be conditional.

Idempotence is what makes the test-isolation template safe to build under
parallel test workers: several may run this against one database, and every one
after the first applies nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg

from platform_core.errors import ConfigurationInvalidError
from platform_core.obs.logging import StructuredLogger

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"

SUFFIX = ".sql"

VERSION_TABLE = """
create table if not exists schema_migrations (
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
    rows = connection.execute("select version from schema_migrations").fetchall()
    return frozenset(str(row[0]) for row in rows)


def apply_migrations(
    connection: psycopg.Connection[Any],
    logger: StructuredLogger | None = None,
    directory: Path = MIGRATIONS_DIRECTORY,
) -> tuple[str, ...]:
    """Apply every unapplied migration. Returns the versions applied by this call."""
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
            connection.execute("insert into schema_migrations (version) values (%s)", (version,))
        applied.append(version)
        if logger is not None:
            logger.info("db.migration_applied", version=version)
    if logger is not None:
        logger.info("db.migrations_settled", applied=applied, skipped=sorted(already))
    return tuple(applied)
