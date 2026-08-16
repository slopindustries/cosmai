"""Session-wide guards and markers for the CosmaSignal test suite.

The secret-store location guard below is the test-session half of the obligation
recorded in ``docs/conventions/secret-setup.md``. The application-startup half
waits for P0 application code.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

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
    """Refuse to run when the configured secret store sits inside the working tree."""
    configured = os.environ.get("COSMA_SECRET_SOURCE")
    if not configured:
        return
    try:
        resolved = Path(configured).expanduser().resolve()
    except OSError:
        return
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise pytest.UsageError(
            f"COSMA_SECRET_SOURCE points inside the repository working tree: {resolved}. "
            "Credentials must live outside it. See docs/conventions/secret-setup.md."
        )
