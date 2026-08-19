"""Checks on how P0 code is reached, and on it staying unreachable any other way.

``platform_core`` is importable only because ``[tool.pytest.ini_options] pythonpath``
adds ``experiments/integrated-p0``; the directory name's hyphen makes it a
non-package. DP-003 keeps the repository root itself free of an importable
product package (``[tool.uv] package = false``) so that, under DP-001, no P1
runtime or package dependency can form against P0 code. Both halves are asserted
here because either one silently breaking would be discovered late.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = REPO_ROOT / "experiments" / "integrated-p0"


def read_pyproject() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_platform_core_is_importable() -> None:
    import platform_core

    assert platform_core.__doc__


def test_platform_core_resolves_inside_the_integrated_experiment() -> None:
    import platform_core

    assert platform_core.__file__ is not None
    location = Path(platform_core.__file__).resolve()
    assert location.parent == EXPERIMENT_ROOT / "platform_core", location


def test_pytest_path_names_the_experiment_root() -> None:
    options = read_pyproject()["tool"]["pytest"]["ini_options"]
    assert "experiments/integrated-p0" in options["pythonpath"]


def test_pytest_collects_both_test_roots() -> None:
    """`testpaths` decides whether any guard in this directory runs at all.

    `[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` M2: narrowing `testpaths` to
    `["tests"]` drops **1039 of 1072** tests and the suite reports `33 passed` — green, no
    error, no warning. The sibling above pins `pythonpath` and nothing pinned this, which
    made the more consequential of the two settings the unguarded one.
    """
    options = read_pyproject()["tool"]["pytest"]["ini_options"]
    testpaths = options["testpaths"]

    assert "tests" in testpaths, testpaths
    assert "experiments/integrated-p0/tests" in testpaths, testpaths


def test_both_test_roots_actually_hold_tests() -> None:
    """The control on the case above.

    `testpaths` naming a directory that no longer holds tests would pass the assertion and
    still collect nothing — the same silent green by a different route.
    """
    options = read_pyproject()["tool"]["pytest"]["ini_options"]
    root = Path(__file__).resolve().parents[2]

    for named in options["testpaths"]:
        found = sorted((root / named).rglob("test_*.py"))
        assert len(found) >= 5, f"{named} holds {len(found)} test files"


def test_repository_declares_no_importable_package() -> None:
    """DP-003 regression guard: nothing here may be installed as a product package."""
    assert read_pyproject()["tool"]["uv"]["package"] is False
