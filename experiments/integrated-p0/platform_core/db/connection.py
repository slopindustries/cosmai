"""Open a psycopg 3 connection to the local cluster described by ``PlatformConfig``.

DP-006 D2 fixes the shape this module has to serve: a repository-local cluster
with ``listen_addresses = ''``, reachable only through a Unix socket, with no
password anywhere. ``db_host`` is therefore a directory rather than a hostname —
libpq treats a ``host`` value beginning with ``/`` as a socket directory — and
there is no credential to resolve, which is precisely why P0-A can stay inside
the boundary ``docs/conventions/secret-setup.md`` draws around P0-B.

Two things are deliberately absent.

* **No pool.** P0-A runs a few processes on one host. A pool would add checkout,
  lifetime, and recycling semantics on top of the transaction boundaries the
  experiment is trying to observe directly, and it reduces no named uncertainty.
* **No abstraction over psycopg.** DP-006 D5 wants the claim statement, the lease
  predicate, and the idempotent insert legible to a gate reviewer. A wrapper type
  would be one more thing to read before reaching them.

What this module does add is classification. A failure to connect arrives as a
driver exception, and the platform's external error contract is the error table
of CONTRACT-JOB@0.1, so the exception is mapped onto that table at the boundary
rather than propagated unclassified into code that would then have to guess.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Final

import psycopg
from psycopg.conninfo import make_conninfo

from platform_core.config import PlatformConfig
from platform_core.errors import ConfigurationInvalidError, PlatformError, PlatformTransientError

#: SQLSTATE classes where waiting is a sensible response: connection exceptions
#: (08), insufficient resources such as too many connections (53), and operator
#: intervention such as a cluster still starting up or shutting down (57).
#: Everything else at connect time — a database that does not exist, a role that
#: does not, a directory holding no socket — is a statement about how the process
#: was configured, and the contract's answer to that is to refuse to start.
TRANSIENT_SQLSTATE_CLASSES: Final[frozenset[str]] = frozenset({"08", "53", "57"})


def connection_parameters(config: PlatformConfig, database: str | None = None) -> dict[str, str]:
    """The libpq keywords for this configuration. No password appears here."""
    return {
        "host": str(config.db_host),
        "dbname": config.db_name if database is None else database,
        "user": config.db_user,
    }


def describe(config: PlatformConfig, database: str | None = None) -> str:
    """A short, non-secret description of what a connection was aiming at."""
    parameters = connection_parameters(config, database)
    return f"database {parameters['dbname']!r} on socket directory {parameters['host']!r}"


def classify(error: psycopg.Error, target: str) -> PlatformError:
    """Map a driver failure onto the CONTRACT-JOB@0.1 error table."""
    sqlstate = error.sqlstate or ""
    summary = f"cannot reach the platform {target}: {error}"
    detail: dict[str, Any] = {"sqlstate": sqlstate or None, "target": target}
    if sqlstate[:2] in TRANSIENT_SQLSTATE_CLASSES:
        return PlatformTransientError(summary, detail)
    return ConfigurationInvalidError(summary, detail)


def connect(
    config: PlatformConfig,
    database: str | None = None,
    autocommit: bool = False,
) -> psycopg.Connection[Any]:
    """Open one connection, or raise the classified platform error.

    ``autocommit`` is an argument rather than a default because two callers need
    it for reasons the database gives them no choice about: the migration applier,
    which needs a real transaction per file, and ``CREATE DATABASE``, which cannot
    run inside a transaction block at all.
    """
    try:
        conninfo = make_conninfo(**connection_parameters(config, database))
        return psycopg.connect(conninfo, autocommit=autocommit)
    except psycopg.Error as error:
        raise classify(error, describe(config, database)) from error


@contextmanager
def connected(
    config: PlatformConfig,
    database: str | None = None,
    autocommit: bool = False,
) -> Iterator[psycopg.Connection[Any]]:
    """A connection that is closed on the way out, however the block ends.

    It does not commit for you. ``with psycopg.connect(...)`` commits on a clean
    exit; here the transaction boundary is one of the things P0-A is trying to
    observe, so leaving the block without committing rolls back and says so.
    """
    handle = connect(config, database, autocommit)
    try:
        yield handle
    finally:
        handle.close()
