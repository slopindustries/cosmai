"""Domain persistence for DP-008: registered sources, cursors, Raw, and snapshots.

Copy-adapted from ``experiments/integrated-p0/domain/__init__.py``. P0's package
also exported ``apply_domain_migrations``/``MIGRATIONS_DIRECTORY`` from its own
``domain/migrate.py``, needed there because ``tests/test_p0a_boundary_guard.py``
forced domain vocabulary out of ``platform_core/db/migrations/``. That guard's
scan root is ``experiments/integrated-p0/platform_core`` and does not reach
``apps/platform_core`` (see ``apps/platform_core/db/migrations/0002_domain.sql``'s
own header), so P1 has one migrations directory and one applier
(``platform_core.db.migrate.apply_migrations``) for both the platform and domain
tables — there is no ``domain.migrate`` module here to export.

``domain`` depends on ``platform_core`` and on nothing else local. In particular
it does **not** import ``addon_api``: Raw persistence should not change when the
add-on contract version changes, so ``addon_host`` (M3) translates between the
two at the boundary instead.
"""

from __future__ import annotations

from domain.store import (
    CURSOR_STREAM_DEFAULT,
    DomainStore,
    NormalizedResultRow,
    RawItemRow,
    SnapshotMember,
    SourceRow,
    canonical_body,
    digest_of,
)

__all__ = [
    "CURSOR_STREAM_DEFAULT",
    "DomainStore",
    "NormalizedResultRow",
    "RawItemRow",
    "SnapshotMember",
    "SourceRow",
    "canonical_body",
    "digest_of",
]
