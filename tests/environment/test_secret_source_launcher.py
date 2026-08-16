"""Replayable checks for ``scripts/with-secret-source.sh``.

These lock the invariant that the launcher validates the store location and
exports only its path — never a credential value. See
``docs/conventions/secret-setup.md``.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "with-secret-source.sh"

EX_CONFIG = 78
TOKEN_KEY = "COSMA_SRC_EXAMPLE_TOKEN"
TOKEN_VALUE = "test-value-must-not-leak"


def write_store(path: Path, mode: int = 0o600) -> Path:
    path.write_text(f"{TOKEN_KEY}={TOKEN_VALUE}\n", encoding="utf-8")
    path.chmod(mode)
    return path


def run_launcher(store: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(LAUNCHER), *argv],
        cwd=REPO_ROOT,
        env={**os.environ, "COSMA_SECRET_SOURCE": str(store)},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def valid_store(tmp_path: Path) -> Path:
    return write_store(tmp_path / "env")


def test_missing_store_is_a_configuration_failure(tmp_path: Path) -> None:
    result = run_launcher(tmp_path / "absent", ["true"])
    assert result.returncode == EX_CONFIG
    assert "not found" in result.stderr


def test_store_inside_the_working_tree_is_rejected() -> None:
    fd, name = tempfile.mkstemp(dir=REPO_ROOT, prefix=".tmp-store-")
    os.close(fd)
    inside = Path(name)
    try:
        write_store(inside)
        result = run_launcher(inside, ["true"])
    finally:
        inside.unlink(missing_ok=True)
    assert result.returncode == EX_CONFIG
    assert "inside the repository working tree" in result.stderr


def test_group_readable_store_is_rejected(tmp_path: Path) -> None:
    store = write_store(tmp_path / "env", mode=0o644)
    result = run_launcher(store, ["true"])
    assert result.returncode == EX_CONFIG
    assert "600" in result.stderr


def test_valid_store_exports_its_path(valid_store: Path) -> None:
    result = run_launcher(valid_store, ["sh", "-c", 'printf %s "$COSMA_SECRET_SOURCE"'])
    assert result.returncode == 0
    assert Path(result.stdout) == valid_store.resolve()


def test_credential_value_never_reaches_the_child_environment(valid_store: Path) -> None:
    result = run_launcher(valid_store, ["env"])
    assert result.returncode == 0
    assert TOKEN_KEY not in result.stdout
    assert TOKEN_VALUE not in result.stdout
