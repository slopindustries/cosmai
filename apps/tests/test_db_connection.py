"""``platform_core.db.connection.classify`` — the classification logic needs no database.

Every other test that touches ``db/connection.py`` goes through a real
connection (``conftest.py``'s ``migrator_connection``/``runtime_connection``),
which is the right tool for "does this open a session" but the wrong one for
"does this map a SQLSTATE correctly" — that question needs only a
``psycopg.Error`` with a ``sqlstate`` set, never a socket. REVIEW-M1 F3 found
this branch untested: DP-032's ``provision.sql`` sets ``lock_timeout='5s'``
(P0 set none), which makes SQLSTATE ``55P03`` (lock not available) reachable
for the first time, and `classify` did not know it. This file is the
regression guard for that fix and its explicit boundary — ``25P03`` stays
``CONFIGURATION_INVALID``.

**This is about the logic under test, not this file's own requirements.**
No test *function* below opens a connection or requests a database fixture.
`[정정, 2026-08-21, m7-fixwave round 2, N2/M-X8]` This paragraph used to say a
live server was "still required to run pytest at all here" because
`conftest.py`'s session-scoped, `autouse=True` `_reset_schema` fixture ran
regardless of which test triggered collection first (F6's own finding). That
is no longer true when this file runs alone: `_reset_schema` now skips
connecting when nothing selected touches the database
(`conftest._SESSION_NEEDS_DATABASE`), and this file's own tests do not.
`[측정]` run standalone with `COSMA_DB_PORT` pointed at a dead port: 6 passed
in 0.01s, no connection attempted. Run inside the ordinary full suite
alongside DB-backed modules, the session-level reset still happens once, same
as always — this file just no longer forces it on its own.
"""

from __future__ import annotations

import psycopg
import pytest

from platform_core.db.connection import classify
from platform_core.errors import ConfigurationInvalidError, PlatformTransientError

TARGET = "database 'cosmai_test' on 127.0.0.1:5434 as role 'runtime'"


def _error(sqlstate: str) -> psycopg.Error:
    return psycopg.errors.lookup(sqlstate)("injected for classify()")


@pytest.mark.parametrize(
    ("sqlstate", "retryable"),
    [
        ("55P03", True),  # lock not available — DP-032's new lock_timeout
        ("25P03", False),  # idle-in-transaction timeout — deliberately not reclassified
        ("57014", True),  # statement_timeout — already class 57, unchanged by this fix
        ("28P01", False),  # bad password — a configuration statement, unchanged
    ],
)
def test_classify_maps_the_reviewed_sqlstates(sqlstate: str, retryable: bool) -> None:
    error = classify(_error(sqlstate), TARGET)
    assert error.retryable is retryable, sqlstate
    if retryable:
        assert isinstance(error, PlatformTransientError)
    else:
        assert isinstance(error, ConfigurationInvalidError)


def test_55p03_is_platform_transient_and_25p03_is_not() -> None:
    """The review's own snippet, mirrored directly."""
    assert classify(_error("55P03"), TARGET).retryable is True
    assert classify(_error("25P03"), TARGET).retryable is False


def test_no_sqlstate_at_all_is_configuration_invalid() -> None:
    """A failure to connect at startup: psycopg reports ``sqlstate = None``."""
    error = psycopg.OperationalError("could not connect")
    assert error.sqlstate is None
    classified = classify(error, TARGET)
    assert isinstance(classified, ConfigurationInvalidError)
    assert classified.retryable is False
