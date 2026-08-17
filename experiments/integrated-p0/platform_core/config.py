"""Platform configuration: load it, validate it, or refuse to start.

SEC-003 is the acceptance scenario. Its rule comes out of
``docs/conventions/secret-setup.md``: a process that cannot resolve its
configuration exits with a non-retryable configuration failure and never
continues on an empty value or a fallback. A platform that silently substitutes a
default is one whose later security evidence means nothing, because nobody can
tell afterwards which configuration actually ran.

Two consequences shape this module.

* **A default is a documented value for an absent setting, never a repair for a
  rejected one.** ``COSMA_LEASE_SECONDS=0`` is an error, not a reason to use 30.
* **The report names settings, not the environment.** ``secret-setup.md`` lists
  dumping the environment on a configuration error as its own leak channel, so
  the message carries setting names and reasons, and includes an offending value
  only when the setting's name is not itself a candidate secret — the same
  key-name test SEC-004 uses everywhere else.

An unknown ``COSMA_``-prefixed variable is reported and is not fatal (SEC-003
case f). Rejecting it would make the platform fail on unrelated environment
noise; ignoring it silently would hide a typo in a real setting name, which
presents in exactly this way.

``SETTINGS`` and ``CROSS_CHECKS`` are tables so that a later validator is an
entry rather than an edit. T4.1 adds the secret-store location guard as one more
cross-check; it is deliberately absent here, because SEC-001 does not exist yet.

Nothing in this module opens a connection. SEC-003 requires cases a–e to fail
before the database is touched, and the cheapest way to guarantee that is for the
configuration layer to have no database code in it at all.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from platform_core.errors import ConfigurationInvalidError
from platform_core.obs.logging import DEFAULT_LEVEL, require_known_level
from platform_core.obs.redaction import REDACTION_MARKER, is_redacted_key

PREFIX: Final = "COSMA_"

#: Variables the project defines but this stage does not consume. Naming them
#: keeps ``scripts/with-secret-source.sh`` out of the unknown-variable report; the
#: guard that actually reads this one arrives with T4.1.
RECOGNIZED_UNUSED: Final[frozenset[str]] = frozenset({"COSMA_SECRET_SOURCE"})

DEFAULT_API_HOST: Final = "127.0.0.1"


class _Rejected(Exception):
    """Internal: a parser's reason for refusing a value."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Setting:
    """One environment variable and how it becomes a configuration field."""

    name: str
    attribute: str
    parse: Callable[[str], Any]
    default: str | None = None

    @property
    def required(self) -> bool:
        return self.default is None


@dataclass(frozen=True)
class PlatformConfig:
    """Validated platform configuration. Every field is present and checked."""

    db_host: Path
    db_name: str
    db_user: str
    lease_seconds: int
    retry_base_ms: int
    retry_max_ms: int
    api_host: str
    api_port: int
    log_level: str
    unrecognized_variables: tuple[str, ...] = ()

    def warnings(self) -> tuple[str, ...]:
        """Non-fatal findings an entrypoint should log at startup (SEC-003 case f)."""
        return tuple(
            f"unknown {PREFIX}-prefixed variable is ignored: {name}"
            for name in self.unrecognized_variables
        )


def _text(value: str) -> str:
    return value


def _directory(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.exists():
        raise _Rejected("must name an existing directory, but the path does not exist")
    if not path.is_dir():
        raise _Rejected("must name a directory, but the path is not one")
    return path


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise _Rejected("must be an integer") from None
    if number <= 0:
        raise _Rejected("must be greater than zero")
    return number


def _port(value: str) -> int:
    number = _positive_int(value)
    if number > 65535:
        raise _Rejected("must be a port number between 1 and 65535")
    return number


def _level(value: str) -> str:
    try:
        return require_known_level(value)
    except ConfigurationInvalidError as error:
        raise _Rejected(error.summary) from None


SETTINGS: Final[Sequence[Setting]] = (
    # The socket directory of the local cluster (DP-006 D2). It carries no
    # password, so it is local configuration rather than a credential.
    Setting("COSMA_DB_HOST", "db_host", _directory),
    Setting("COSMA_DB_NAME", "db_name", _text),
    Setting("COSMA_DB_USER", "db_user", _text),
    Setting("COSMA_LEASE_SECONDS", "lease_seconds", _positive_int, default="30"),
    Setting("COSMA_RETRY_BASE_MS", "retry_base_ms", _positive_int, default="100"),
    Setting("COSMA_RETRY_MAX_MS", "retry_max_ms", _positive_int, default="30000"),
    # Loopback by default: the charter requires operator surfaces to bind locally
    # unless a deployment deliberately says otherwise.
    Setting("COSMA_API_HOST", "api_host", _text, default=DEFAULT_API_HOST),
    Setting("COSMA_API_PORT", "api_port", _port, default="8000"),
    Setting("COSMA_LOG_LEVEL", "log_level", _level, default=DEFAULT_LEVEL),
)

KNOWN_NAMES: Final[frozenset[str]] = frozenset(setting.name for setting in SETTINGS)

Problem = tuple[str, str]
"""(setting name, why it was rejected)."""


def _backoff_window_is_ordered(values: Mapping[str, Any]) -> Problem | None:
    base = values.get("retry_base_ms")
    maximum = values.get("retry_max_ms")
    if base is None or maximum is None:
        return None
    if maximum < base:
        return ("COSMA_RETRY_MAX_MS", f"must be at least COSMA_RETRY_BASE_MS ({base})")
    return None


CROSS_CHECKS: Final[Sequence[Callable[[Mapping[str, Any]], Problem | None]]] = (
    _backoff_window_is_ordered,
)


def unrecognized_variables(environment: Mapping[str, str]) -> tuple[str, ...]:
    """The ``COSMA_``-prefixed names this stage does not know about."""
    return tuple(
        sorted(
            name
            for name in environment
            if name.startswith(PREFIX)
            and name not in KNOWN_NAMES
            and name not in RECOGNIZED_UNUSED
        )
    )


def load_config(environment: Mapping[str, str] | None = None) -> PlatformConfig:
    """Build a validated configuration, or raise ``ConfigurationInvalidError``.

    Every problem is collected before raising, so one restart shows an operator
    everything that is wrong rather than one item at a time.
    """
    env = os.environ if environment is None else environment
    problems: list[Problem] = []
    values: dict[str, Any] = {}

    for setting in SETTINGS:
        stated = env.get(setting.name)
        if stated is None:
            if setting.required:
                problems.append((setting.name, "is required but is not set"))
                continue
            # A default stands in for an absent variable. It never repairs a
            # stated one, blank or otherwise.
            given = setting.default
            assert given is not None
        else:
            given = stated.strip()
            if not given:
                # An empty value is a statement, not an absence. Falling back here
                # is the silent substitution secret-setup.md forbids.
                problems.append((setting.name, "is set but empty; it must state a value"))
                continue
        try:
            values[setting.attribute] = setting.parse(given)
        except _Rejected as rejected:
            problems.append((setting.name, _reason_for(setting.name, given, rejected.reason)))

    for check in CROSS_CHECKS:
        problem = check(values)
        if problem is not None:
            problems.append(problem)

    if problems:
        raise ConfigurationInvalidError(_summary_of(problems), _detail_of(problems))

    values["unrecognized_variables"] = unrecognized_variables(env)
    return PlatformConfig(**values)


def _reason_for(name: str, given: str, reason: str) -> str:
    """Attach the offending value, unless the setting's name reads as a secret."""
    shown = REDACTION_MARKER if is_redacted_key(name) else repr(given)
    return f"{reason}, but was {shown}"


def _summary_of(problems: Iterable[Problem]) -> str:
    listed = "; ".join(f"{name} {reason}" for name, reason in problems)
    return f"invalid platform configuration: {listed}"


def _detail_of(problems: Iterable[Problem]) -> dict[str, Any]:
    return {"rejected": [{"setting": name, "reason": reason} for name, reason in problems]}
