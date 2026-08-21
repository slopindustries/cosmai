"""Resolving one credential, at the point of use, from the store the launcher validated.

Copy-adapted from ``experiments/integrated-p0/domain/secrets.py``. The shape is
unchanged: a location guard (``secret_store_path``), a line-scan resolver
(``resolve_credential``), and a wrapper (``SecretValue``) whose ``repr``/``str``
never show the value. There is still no cache — each call re-reads the store,
which is the cheapest way to guarantee a rotated credential is picked up on the
next use rather than held stale for a process's lifetime.

**What DP-032 changes.** P0's ``resolve_credential`` accepted any ``ref`` and
looked it up; the naming discipline (``COSMA_SRC_<SOURCE_ID>_<PURPOSE>``) was
enforced elsewhere, in ``domain/outbound.py``, at the point an outbound profile
was read. P1 has no outbound-profile layer yet, and DP-032 D4 adds a second ref
family (``COSMA_DB_*``) alongside the source one, so the naming check is
centralized here instead: ``resolve_credential`` refuses a ``ref`` that does not
match ``CREDENTIAL_REF_PATTERN`` before it ever reads the store, the same way
``platform_core.config``'s ``_credential_ref`` parser refuses a malformed
``COSMA_DB_PASSWORD_REF`` before a connection is ever attempted.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Final

from platform_core.config import (
    CREDENTIAL_REF_PATTERN,
    SECRET_STORE_VARIABLE,
    ConfigurationInvalidError,
)

__all__ = [
    "CREDENTIAL_REF_PATTERN",
    "CredentialNotResolved",
    "SecretValue",
    "resolve_credential",
    "secret_store_path",
    "write_credential",
]

#: The repository working tree. ``secrets.py`` sits at
#: ``apps/platform_core/secrets.py``, two directories below the root — one
#: shallower than P0's ``experiments/integrated-p0/domain/secrets.py``. A store
#: inside it would be one ``git add -A`` from being committed.
_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: What ``scripts/with-secret-source.sh`` requires. Repeated here because
#: ``secret-setup.md`` records the gap in its own words: this check does not
#: apply to an execution path that bypasses the launcher, and a worker started
#: by a supervisor, a test, or an operator who forgot takes exactly such a path.
_PERMITTED_MODES: Final[frozenset[int]] = frozenset({0o600, 0o400})

_WITHHELD: Final = "<withheld>"


class CredentialNotResolved(ConfigurationInvalidError):
    """A credential was required and could not be produced."""


class SecretValue:
    """One resolved credential value, wrapped so that printing it says nothing."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the value. The one place it becomes an ordinary string."""
        return self._value

    def __repr__(self) -> str:
        return f"SecretValue({_WITHHELD})"

    def __str__(self) -> str:
        return repr(self)


def secret_store_path() -> Path:
    """Where the store is, or a refusal."""
    stated = os.environ.get(SECRET_STORE_VARIABLE)
    if not stated:
        raise CredentialNotResolved(
            f"{SECRET_STORE_VARIABLE} is not set, so no credential can be resolved; run the "
            "command through scripts/with-secret-source.sh",
            {"setting": SECRET_STORE_VARIABLE},
        )
    path = Path(stated).expanduser()
    if not path.is_file():
        raise CredentialNotResolved(
            f"the secret store named by {SECRET_STORE_VARIABLE} is not a file",
            {"setting": SECRET_STORE_VARIABLE},
        )
    resolved = path.resolve()
    if resolved == _REPOSITORY_ROOT or _REPOSITORY_ROOT in resolved.parents:
        raise CredentialNotResolved(
            "the secret store is inside the repository working tree; move it outside "
            "before resolving any credential",
            {"setting": SECRET_STORE_VARIABLE},
        )
    mode = stat.S_IMODE(resolved.stat().st_mode)
    if mode not in _PERMITTED_MODES:
        raise CredentialNotResolved(
            f"the secret store must be mode 600 or 400, and is {mode:o}",
            {"setting": SECRET_STORE_VARIABLE, "mode": f"{mode:o}"},
        )
    return resolved


def resolve_credential(ref: str) -> SecretValue:
    """The value stored under ``ref``.

    ``ref`` must be a secret-store key name — ``COSMA_SRC_*`` or ``COSMA_DB_*``
    (DP-032 D4) — never a value. A ref outside that shape is refused before the
    store is even located, so a real token pasted into a ``db_password_ref``-like
    field by mistake is refused rather than "not found".
    """
    if not CREDENTIAL_REF_PATTERN.match(ref):
        raise CredentialNotResolved(
            f"{ref!r} is not a secret-store key name; it must match "
            f"{CREDENTIAL_REF_PATTERN.pattern} and is never a value",
            {"credential_ref": ref},
        )
    store = secret_store_path()
    for line in store.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == ref:
            return SecretValue(value.strip())
    raise CredentialNotResolved(
        f"the secret store holds no key named {ref!r}",
        {"credential_ref": ref},
    )


def write_credential(ref: str, value: str) -> None:
    """Write ``ref=value`` to the secret store, replacing any existing line for ``ref``.

    M2 batch 2d / DP-034 D1-D2: the dashboard's credential-entry write path. This is
    the one relaxation DP-034 D2 names — a *second* point of use for invariant 2,
    the API process rather than the worker — bounded to exactly this call: ``value``
    is a local variable for the duration of one write, never returned, never logged,
    never included in any exception this function raises (only ``ref``, a key name,
    ever is), and never held past this function's return.

    Writes to the same location ``resolve_credential`` reads (``secret_store_path()``),
    so a value written here is immediately resolvable — and, per DP-034 D1, a store
    that cannot be located, is not a file, is inside the repository, or carries the
    wrong permissions refuses exactly as it already does for a *read*
    (``CredentialNotResolved``, ``CONFIGURATION_INVALID``), never falling back to
    creating one at a guessed location.

    ``ref`` must already be a secret-store key name — the caller derives and
    validates it before calling this, the same division of labor
    ``domain.outbound._read_credentials`` already holds between a profile's shape and
    the store that resolves it.
    """
    if not CREDENTIAL_REF_PATTERN.match(ref):
        raise CredentialNotResolved(
            f"{ref!r} is not a secret-store key name; it must match "
            f"{CREDENTIAL_REF_PATTERN.pattern} and is never a value",
            {"credential_ref": ref},
        )
    path = secret_store_path()
    mode = stat.S_IMODE(path.stat().st_mode)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    replaced = False
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() == ref:
                rewritten.append(f"{ref}={value}\n")
                replaced = True
                continue
        rewritten.append(line)
    if not replaced:
        if rewritten and not rewritten[-1].endswith("\n"):
            rewritten[-1] = f"{rewritten[-1]}\n"
        rewritten.append(f"{ref}={value}\n")

    # Written to a temporary file in the same directory and renamed into place, so a
    # reader (a worker resolving a credential mid-write) never observes a partially
    # written store — `os.replace` is atomic on the same filesystem. The mode is
    # copied from the file being replaced rather than left to the process umask,
    # which is what "mode preserved" means here: a store that was 600 stays 600.
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text("".join(rewritten), encoding="utf-8")
    tmp.chmod(mode)
    os.replace(tmp, path)
