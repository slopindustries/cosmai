"""Resolving one credential, at the point of use, from the store the launcher validated."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Final

from platform_core.config import SECRET_STORE_VARIABLE
from platform_core.errors import ConfigurationInvalidError

__all__ = [
    "CredentialNotResolved",
    "SecretValue",
    "resolve_credential",
    "secret_store_path",
]

#: The repository working tree. A store inside it would be one `git add -A` from being
#: committed, which is `secret-setup.md` invariant 1 and the only one of the four that
#: cannot be undone afterwards.
_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: What `scripts/with-secret-source.sh` requires. Repeated here because `secret-setup.md`
#: records the gap in its own words — "이 검사는 런처를 거치지 않는 실행 경로에는 적용되지
#: 않는다" — and a worker started by a supervisor, a test, or an operator who forgot takes
#: exactly such a path.
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
    """The value stored under `ref`."""
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
