"""Open a psycopg 3 connection to the shared PostgreSQL server (DP-032 D1/D3/D4).

Copy-adapted from ``experiments/integrated-p0/platform_core/db/connection.py``.
DP-006 D2 fixed a repository-local cluster reachable only through a Unix socket
with no password; DP-032 replaces that placement with a dedicated database
(``cosmai``) on a shared server, reached over loopback TCP with a password. What
carries forward unchanged is the shape of the module: no pool (a handful of
processes on one host, and DP-032 does not change that count), no abstraction
over psycopg (DP-006 D5 / DP-032 D3 — the statements a gate reviewer needs to
read stay legible).

Two roles, one function. ``role="runtime"`` connects as ``config.db_user`` with
the credential named by ``config.db_password_ref`` (default
``COSMA_DB_RUNTIME``) — the operator-configured identity for ordinary DML.
``role="migrator"`` connects as the fixed identity ``cosmai_migrator`` with the
fixed ref ``COSMA_DB_MIGRATOR`` (``apps/db/provision.sql``: a deploy-time
connection is never the thing an operator points at a different identity by
setting ``COSMA_DB_USER``), then immediately issues ``SET ROLE cosmai_owner`` —
``cosmai_migrator`` is a member of ``cosmai_owner`` but ``NOINHERIT``, so the
grant does nothing until this statement runs, which is exactly the point: a
migrator connection that merely opened would still be unable to run DDL by
accident.

The password exists only as ``psycopg.connect``'s own keyword argument —
``resolve_credential(...).reveal()`` is passed inline and never assigned to a
local name, so there is nothing here for a traceback or a debugger to hold past
the one call that needs it.
"""

from __future__ import annotations

from typing import Any, Final

import psycopg

from platform_core.config import PlatformConfig
from platform_core.secrets import resolve_credential

#: DP-032 D1: the migrator's identity is fixed, not read from ``PlatformConfig``.
MIGRATOR_USER: Final = "cosmai_migrator"

#: DP-032 D4: the migrator's own key, distinct from the runtime credential a
#: ``PlatformConfig`` names through ``db_password_ref``.
MIGRATOR_CREDENTIAL_REF: Final = "COSMA_DB_MIGRATOR"

#: The role the migrator ``SET ROLE``s itself to immediately after connecting.
OWNER_ROLE: Final = "cosmai_owner"

_ROLES: Final[frozenset[str]] = frozenset({"runtime", "migrator"})


def connect(
    config: PlatformConfig,
    *,
    role: str = "runtime",
    autocommit: bool = False,
) -> psycopg.Connection[Any]:
    """Open one connection over loopback TCP, or let the driver's own error propagate.

    ``role="migrator"`` is always autocommit regardless of the ``autocommit``
    argument: ``SET ROLE`` (without ``LOCAL``) is transactional, so a role that
    took effect inside a transaction reverts on that transaction's rollback —
    and ``platform_core.db.migrate.apply_migrations`` wraps each migration file
    in a transaction of its own, which would otherwise silently drop the
    migrator's elevated role after the first file's commit ended the
    transaction the ``SET ROLE`` itself ran in. ``role="runtime"`` honours the
    caller's ``autocommit`` unchanged.
    """
    if role not in _ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {sorted(_ROLES)}")
    if role == "migrator":
        user = MIGRATOR_USER
        password_ref = MIGRATOR_CREDENTIAL_REF
        effective_autocommit = True
    else:
        user = config.db_user
        password_ref = config.db_password_ref
        effective_autocommit = autocommit

    connection = psycopg.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=user,
        password=resolve_credential(password_ref).reveal(),
        autocommit=effective_autocommit,
    )
    if role == "migrator":
        connection.execute(f"set role {OWNER_ROLE}")
    return connection
