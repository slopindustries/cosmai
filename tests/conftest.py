"""Session-wide guards and markers for the Cosmai test suite.

The secret-store location guard below is the test-session half of the obligation
recorded in ``docs/conventions/secret-setup.md``. The application-startup half now
exists too, and this file **calls it** rather than reimplementing it: SEC-001
requires both halves to refuse the same paths, and two copies of a path
comparison are two things that can disagree. The one that disagreed would be the
leak.

The import therefore points at P0-A code. That is a test-session dependency and
not a runtime or package one, so DP-001 is unaffected — but it does mean this
guard leaves with the experiment. When ``experiments/integrated-p0/`` is disposed
of, the location check has to move here or into whatever replaces it; a session
that silently stops guarding is the failure this note exists to prevent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from platform_core.config import (
    SECRET_STORE_VARIABLE,
    WORKING_TREE_ROOT,
    secret_store_location_problem,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# (flag, marker, reason)
_OPT_IN_MARKERS = (
    ("--run-network", "network", "performs an outbound request"),
    ("--run-credential", "requires_credential", "needs a real credential"),
)


def pytest_addoption(parser: pytest.Parser) -> None:
    for flag, marker, reason in _OPT_IN_MARKERS:
        parser.addoption(
            flag,
            action="store_true",
            default=False,
            help=f"run tests marked {marker} ({reason})",
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for flag, marker, reason in _OPT_IN_MARKERS:
        if config.getoption(flag):
            continue
        skip = pytest.mark.skip(reason=f"{reason}; pass {flag} to run")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Refuse to run when the configured secret store sits inside the working tree.

    The decision is the platform's; only the way it is reported differs, because a
    session has no exit status to set and ``UsageError`` is what stops collection
    before any test opens anything.
    """
    # A guard measuring a different tree would pass everything, so the two roots
    # are compared here rather than asserted in a test that might not be selected.
    assert WORKING_TREE_ROOT == REPO_ROOT, (
        f"the platform guard measures {WORKING_TREE_ROOT} while this session is "
        f"rooted at {REPO_ROOT}; one of the two path calculations is wrong"
    )
    problem = secret_store_location_problem({}, os.environ)
    if problem is not None:
        raise pytest.UsageError(f"{SECRET_STORE_VARIABLE} {problem[1]}")
