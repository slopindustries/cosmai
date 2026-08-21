"""SEC-001's secret-reader half, for ``platform_core.secrets``, copy-adapted.

Narrower than P0's ``tests/test_secret_store_guard.py``: no entrypoints exist
yet in this milestone, so the process-level cases (spawn a worker, spawn the
API, watch it refuse) do not apply here. What carries forward is the resolver
behaviour itself: the store's location and permission guard, ``SecretValue``
never printing its value, and the two things DP-032 D4 adds — a ``ref`` must
match ``CREDENTIAL_REF_PATTERN`` (``COSMA_SRC_*`` or ``COSMA_DB_*``) before the
store is even opened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_core.config import SECRET_STORE_VARIABLE, WORKING_TREE_ROOT, ConfigurationInvalidError
from platform_core.secrets import (
    CREDENTIAL_REF_PATTERN,
    CredentialNotResolved,
    SecretValue,
    resolve_credential,
)

SECRET_MARKER = "marker-must-not-leak-42"


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A valid store outside the working tree, mode 600, pointed at by the env."""
    path = tmp_path / "env"
    path.write_text(
        "\n".join(
            [
                "# a comment line, and a blank one below",
                "",
                f"COSMA_DB_RUNTIME={SECRET_MARKER}",
                "COSMA_SRC_NAVER_BLOG_TOKEN=another-value",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(path))
    return path


# --- SecretValue never reveals its own value ----------------------------------


def test_secret_value_repr_and_str_are_withheld() -> None:
    value = SecretValue(SECRET_MARKER)
    assert repr(value) == "SecretValue(<withheld>)"
    assert str(value) == "SecretValue(<withheld>)"
    assert SECRET_MARKER not in repr(value)
    assert SECRET_MARKER not in str(value)


def test_secret_value_reveal_returns_the_value() -> None:
    value = SecretValue(SECRET_MARKER)
    assert value.reveal() == SECRET_MARKER


# --- resolving a value ---------------------------------------------------------


def test_resolve_credential_returns_the_stored_value(store: Path) -> None:
    resolved = resolve_credential("COSMA_DB_RUNTIME")
    assert isinstance(resolved, SecretValue)
    assert resolved.reveal() == SECRET_MARKER


def test_resolve_credential_reads_the_store_fresh_each_call(store: Path) -> None:
    """No cache: a rotated value is visible on the very next call."""
    resolve_credential("COSMA_DB_RUNTIME")
    store.write_text("COSMA_DB_RUNTIME=rotated-value\n", encoding="utf-8")
    store.chmod(0o600)
    assert resolve_credential("COSMA_DB_RUNTIME").reveal() == "rotated-value"


def test_resolve_credential_refuses_a_key_the_store_does_not_hold(store: Path) -> None:
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential("COSMA_DB_MIGRATOR")
    assert "COSMA_DB_MIGRATOR" in str(raised.value.summary)
    assert isinstance(raised.value, ConfigurationInvalidError)
    assert not raised.value.retryable


# --- DP-032 D4: the ref pattern check -----------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "not-a-ref-at-all",
        "COSMA_API_TOKEN",
        "cosma_db_runtime",
        "",
        SECRET_MARKER,
    ],
)
def test_resolve_credential_refuses_a_ref_that_is_not_a_key_name(store: Path, ref: str) -> None:
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential(ref)
    assert CREDENTIAL_REF_PATTERN.pattern in raised.value.summary
    # The ref itself is a name, not a value, and is safe to show.
    assert ref in raised.value.summary or ref == ""


@pytest.mark.parametrize("ref", ["COSMA_DB_RUNTIME", "COSMA_SRC_NAVER_BLOG_TOKEN"])
def test_resolve_credential_accepts_both_key_families(store: Path, ref: str) -> None:
    resolved = resolve_credential(ref)
    assert isinstance(resolved, SecretValue)


# --- the location and permission guard ----------------------------------------


def test_secret_store_variable_unset_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET_STORE_VARIABLE, raising=False)
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential("COSMA_DB_RUNTIME")
    assert SECRET_STORE_VARIABLE in raised.value.summary


def test_a_store_inside_the_working_tree_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    inside = WORKING_TREE_ROOT / ".tmp-task3-secrets-store"
    inside.write_text(f"COSMA_DB_RUNTIME={SECRET_MARKER}\n", encoding="utf-8")
    inside.chmod(0o600)
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(inside))
    try:
        with pytest.raises(CredentialNotResolved) as raised:
            resolve_credential("COSMA_DB_RUNTIME")
        assert "inside the repository working tree" in raised.value.summary
    finally:
        inside.unlink(missing_ok=True)


def test_a_store_that_is_not_a_file_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(tmp_path))
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential("COSMA_DB_RUNTIME")
    assert "not a file" in raised.value.summary


@pytest.mark.parametrize("mode", [0o644, 0o664, 0o777, 0o640])
def test_a_secret_file_with_a_permissive_mode_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    """The brief's named case: mode 644 (and other non-600/400 modes) refuse."""
    path = tmp_path / "env"
    path.write_text(f"COSMA_DB_RUNTIME={SECRET_MARKER}\n", encoding="utf-8")
    path.chmod(mode)
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(path))
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential("COSMA_DB_RUNTIME")
    assert "mode 600 or 400" in raised.value.summary
    assert f"{mode:o}" in raised.value.summary


@pytest.mark.parametrize("mode", [0o600, 0o400])
def test_a_secret_file_with_a_permitted_mode_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    path = tmp_path / "env"
    path.write_text(f"COSMA_DB_RUNTIME={SECRET_MARKER}\n", encoding="utf-8")
    path.chmod(mode)
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(path))
    assert resolve_credential("COSMA_DB_RUNTIME").reveal() == SECRET_MARKER


def test_the_error_never_prints_the_secret_value(store: Path) -> None:
    """secret-setup.md: an environment or store dump is its own leak channel."""
    with pytest.raises(CredentialNotResolved) as raised:
        resolve_credential("COSMA_DB_NONEXISTENT")
    error = raised.value
    text = " ".join(
        [
            str(error),
            repr(error),
            str(error.operator_view()),
            str(error.detail.for_protected_debug()),
        ]
    )
    assert SECRET_MARKER not in text
