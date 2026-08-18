"""Apply the domain migrations, reusing the platform's applier.

The applier already takes a directory, so two migration directories work without
anything being added to ``platform_core``:

    apply_migrations(connection)          # platform tables, 0001
    apply_domain_migrations(connection)   # domain tables, 0002

They are separate directories for a reason that is checked rather than preferred:
``tests/environment/test_p0a_boundary_guard.py`` scans ``platform_core/`` for domain
vocabulary **including its ``.sql`` files**, so a migration creating ``source`` or
``raw_item`` under ``platform_core/db/migrations/`` fails the build. The guard
decided the layout.

Version stems must stay unique across both directories, because
``schema_migrations.version`` is a primary key over the filename stem. ``0002_domain``
cannot collide with ``0001_platform_core``, and the numbering is global for that
reason rather than restarting per directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import psycopg
from platform_core.db.migrate import apply_migrations
from platform_core.obs.logging import StructuredLogger

MIGRATIONS_DIRECTORY: Final[Path] = Path(__file__).resolve().parent / "migrations"


def apply_domain_migrations(
    connection: psycopg.Connection[Any], logger: StructuredLogger | None = None
) -> tuple[str, ...]:
    """Apply every unapplied domain migration. Returns the versions applied.

    Requires an autocommit connection, for the reason ``platform_core.db.migrate``
    states: inside an implicit transaction ``connection.transaction()`` opens a
    savepoint rather than a transaction, so the per-file boundary would silently not
    be there. That check lives in the applier and is not repeated here.
    """
    return apply_migrations(connection, logger, MIGRATIONS_DIRECTORY)
