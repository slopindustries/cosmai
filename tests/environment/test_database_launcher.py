"""Replayable checks for ``scripts/with-database.sh`` that never start a cluster.

These lock the two invariants that would be expensive to discover later: the
launcher's calling convention, and the shape of the cluster it configures — a
local Unix socket with no TCP listener and no password. ``config/env.example``
classifies a connection string carrying a password as a credential, and
``docs/conventions/secret-setup.md`` defers credential resolution to P0-B, so a
passwordless socket is what lets P0-A have a database at all.

Starting PostgreSQL is deliberately out of scope here. The launcher derives its
data directory from its own location, so these tests run a copy planted in a
temporary directory: no test can reach, create, or stop the checkout's cluster.
Tests that exercise a real cluster arrive with the platform core's database work.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "with-database.sh"

EX_USAGE = 64

_FULL_LINE_COMMENT = re.compile(r"^\s*#.*$", re.MULTILINE)


@pytest.fixture
def isolated_launcher(tmp_path: Path) -> Path:
    """A copy of the launcher whose repository root, and cluster, is ``tmp_path``."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    copy = scripts / LAUNCHER.name
    shutil.copy2(LAUNCHER, copy)
    return copy


def run_launcher(launcher: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    root = launcher.parent.parent
    return subprocess.run(
        [str(launcher), *argv],
        cwd=root,
        env={**os.environ, "HOME": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def executable_lines() -> str:
    """The launcher with full-line comments removed.

    Prose about passwords is how the constraint gets explained; only executable
    lines can actually set one.
    """
    return _FULL_LINE_COMMENT.sub("", LAUNCHER.read_text(encoding="utf-8"))


def test_no_arguments_is_a_usage_failure(isolated_launcher: Path) -> None:
    result = run_launcher(isolated_launcher, [])
    assert result.returncode == EX_USAGE
    assert result.stdout == ""
    assert "usage:" in result.stderr


def test_stopping_an_absent_cluster_succeeds_quietly(isolated_launcher: Path) -> None:
    """``--stop`` names a desired end state, and an absent cluster already meets it."""
    if shutil.which("pg_ctl") is None:
        pytest.skip("pg_ctl is not on PATH; enter the Nix shell or install PostgreSQL 18")
    result = run_launcher(isolated_launcher, ["--stop"])
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert not (isolated_launcher.parent.parent / "var").exists()


def test_cluster_has_no_tcp_listener(executable_lines: str) -> None:
    assert "listen_addresses = ''" in executable_lines
    assert "unix_socket_directories" in executable_lines


def test_launcher_sets_no_password(executable_lines: str) -> None:
    lowered = executable_lines.lower()
    for forbidden in ("password", "--auth=md5", "--auth=scram", "--pwprompt", "--pwfile"):
        assert forbidden not in lowered, forbidden
    assert "--auth=trust" in lowered


def test_launcher_exports_only_non_credential_connection_facts(executable_lines: str) -> None:
    exported = set(re.findall(r"^export (\w+)=", executable_lines, re.MULTILINE))
    assert exported == {"COSMA_DB_HOST", "COSMA_DB_NAME", "COSMA_DB_USER"}
