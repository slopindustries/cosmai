"""Domain persistence for DP-008: registered sources, cursors, Raw, and snapshots.

``domain`` depends on ``platform_core`` and on nothing else local. In particular it
does **not** import ``addon_api``, and that is a judgement rather than a necessity:
Raw persistence should not change when the add-on contract version changes, so
``addon_host`` translates between the two at the boundary instead.
``tests/environment/test_addon_layer_direction.py`` enforces it. If B0.3 finds the
translation is pure ceremony, that is evidence about the contract and belongs in the
record — not a reason to widen the rule quietly.

What this package answers is the gap DP-008 was written to close. ``source_id`` and
"registered source" were named in three documents and defined in none, and a
collector's position — cursor, watermark, rate window — appeared nowhere except as an
illustration of how to label a claim. With the collector as platform code, "which
source" came from the code and "where did I stop" from the job payload; neither
survives an operator-installed component.
"""

from __future__ import annotations

from domain.migrate import MIGRATIONS_DIRECTORY, apply_domain_migrations
from domain.store import (
    CURSOR_STREAM_DEFAULT,
    DomainStore,
    RawItemRow,
    SnapshotMember,
    SourceRow,
    digest_of,
)

__all__ = [
    "CURSOR_STREAM_DEFAULT",
    "MIGRATIONS_DIRECTORY",
    "DomainStore",
    "RawItemRow",
    "SnapshotMember",
    "SourceRow",
    "apply_domain_migrations",
    "digest_of",
]
