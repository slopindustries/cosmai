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
entry rather than an edit. Two of the entries are security guards rather than
type checks:

* ``_loopback_host`` (SEC-002) refuses a non-loopback bind address instead of
  merely defaulting to loopback. The charter's exit criterion says "by default";
  P0-A goes further because there is no P0-A reason to expose an unauthenticated
  operator surface beyond the host, and a default is a thing that gets overridden
  by accident. Relaxing this later is a one-line change with a recorded reason;
  discovering it was already relaxed is not recoverable.
* ``secret_store_location_problem`` (SEC-001) refuses a secret store that
  resolves to somewhere inside the repository working tree. It is the
  application-startup half of the obligation ``docs/conventions/secret-setup.md``
  records; the test-session half lives in ``tests/conftest.py`` and calls this
  same function, so the two cannot drift.

Nothing in this module opens a connection, and nothing in it opens the secret
store. SEC-003 requires cases a–e to fail before the database is touched, and the
cheapest way to guarantee that is for the configuration layer to have no database
code in it at all. SEC-001 requires the location guard to decide without reading
the store's **contents**, because reading a credential in order to validate where
it lives would be the leak the rule exists to prevent.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from platform_core.errors import ConfigurationInvalidError
from platform_core.obs.logging import DEFAULT_LEVEL, LOG_SUFFIX, require_known_level
from platform_core.obs.redaction import REDACTION_MARKER, is_redacted_key

PREFIX: Final = "COSMA_"

#: The path of the secret store, exported by ``scripts/with-secret-source.sh``.
#: This stage reads its **location** and never its contents, which is why it is
#: not a ``Setting`` and produces no configuration field.
SECRET_STORE_VARIABLE: Final = "COSMA_SECRET_SOURCE"

#: Where an operator is sent when the location guard refuses a store.
SECRET_SETUP_POINTER: Final = "docs/conventions/secret-setup.md"

#: The repository working tree this checkout lives in. ``config.py`` sits at
#: ``experiments/integrated-p0/platform_core/config.py``, three directories below
#: the root. ``tests/conftest.py`` computes the same root from its own location
#: and a test asserts the two agree, because a guard measuring the wrong tree
#: would pass everything.
WORKING_TREE_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: Variables this stage recognises but does not turn into a configuration field.
#: Naming them keeps ``scripts/with-secret-source.sh`` out of the
#: unknown-variable report.
RECOGNIZED_UNUSED: Final[frozenset[str]] = frozenset({SECRET_STORE_VARIABLE})

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
    poll_ms: int
    api_host: str
    api_port: int
    log_level: str
    #: Where both entrypoints write their structured log, or ``None`` for standard
    #: error. ``None`` is the ordinary case; a path is what makes the events of
    #: several processes reachable from one place (OPS-003).
    log_file: Path | None = None
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


def _log_file(value: str) -> Path | None:
    """Where the structured log is written, or ``None`` for standard error.

    OPS-003 requires the events of several processes to be reachable through one
    correlation identifier, and its preconditions leave the transport an
    implementation choice. This is that choice: every process writes JSON Lines
    into one file, and the operator API filters it. The alternative — a table —
    would put telemetry inside the schema CONTRACT-JOB@0.1 fixes, so it would need
    a migration and a contract amendment to reach the same result.

    The file is **not** where the request says it is. A request names a correlation
    identifier and nothing else; the path is operator configuration, resolved once
    at startup, so no query can turn into a read of an arbitrary file.

    Two refusals rather than corrections, for the reasons ``_loopback_host`` gives:
    a suffix other than ``.jsonl`` would be silently dropped by the repository's
    ``*.log`` rule and lost as gate evidence, and a directory that does not exist
    would fail at the first event rather than at startup.
    """
    if not value:
        return None
    path = Path(value).expanduser()
    if path.suffix != LOG_SUFFIX:
        raise _Rejected(
            f"must name a file ending in {LOG_SUFFIX}, because the repository ignores "
            "*.log and gate evidence has to stay reviewable"
        )
    if not path.parent.is_dir():
        raise _Rejected(
            f"must name a file in an existing directory, but {path.parent} is not one"
        )
    return path


def _loopback_host(value: str) -> str:
    """Accept a loopback IP address and refuse anything else (SEC-002).

    Refusal rather than correction is the whole point. ``0.0.0.0`` quietly
    rewritten to ``127.0.0.1`` would hide a mistake the operator needs to see, and
    a surface that starts anyway teaches nobody that the setting was wrong.

    Only literal addresses are accepted. A name would have to be resolved before
    its reachability were known, the answer can change between the check and the
    bind, and ``localhost`` in particular resolves to whatever the host's name
    service says it does. Requiring an address keeps "this bind is loopback" a
    property that can be decided here.
    """
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise _Rejected(
            "must be a literal loopback IP address such as "
            f"{DEFAULT_API_HOST} or ::1, and a host name is not accepted"
        ) from None
    if not address.is_loopback:
        raise _Rejected(
            "must be a loopback address; P0-A refuses any other bind, "
            "including the wildcard address, and does not fall back to loopback"
        )
    # Returned exactly as stated. Canonicalising an accepted value would be a
    # second, quieter kind of correction.
    return value


SETTINGS: Final[Sequence[Setting]] = (
    # The socket directory of the local cluster (DP-006 D2). It carries no
    # password, so it is local configuration rather than a credential.
    Setting("COSMA_DB_HOST", "db_host", _directory),
    Setting("COSMA_DB_NAME", "db_name", _text),
    Setting("COSMA_DB_USER", "db_user", _text),
    Setting("COSMA_LEASE_SECONDS", "lease_seconds", _positive_int, default="30"),
    Setting("COSMA_RETRY_BASE_MS", "retry_base_ms", _positive_int, default="100"),
    Setting("COSMA_RETRY_MAX_MS", "retry_max_ms", _positive_int, default="30000"),
    # How long a worker waits before asking an empty queue again. It is a pause
    # between claims, not a deadline on anything, so lowering it in a test only
    # makes the loop turn faster.
    Setting("COSMA_POLL_MS", "poll_ms", _positive_int, default="200"),
    # Loopback, and only loopback (SEC-002). The default applies when the variable
    # is absent; a stated non-loopback address is refused rather than replaced.
    Setting("COSMA_API_HOST", "api_host", _loopback_host, default=DEFAULT_API_HOST),
    Setting("COSMA_API_PORT", "api_port", _port, default="8000"),
    Setting("COSMA_LOG_LEVEL", "log_level", _level, default=DEFAULT_LEVEL),
    # Absent means standard error, which is what every process does unless an
    # operator asks for one shared file. The default is the empty string rather
    # than ``None`` because ``None`` is how this table spells "required"; a
    # *stated* empty value is still refused above, as every other setting's is.
    Setting("COSMA_LOG_FILE", "log_file", _log_file, default=""),
)

KNOWN_NAMES: Final[frozenset[str]] = frozenset(setting.name for setting in SETTINGS)

Problem = tuple[str, str]
"""(setting name, why it was rejected)."""

CrossCheck = Callable[[Mapping[str, Any], Mapping[str, str]], Problem | None]
"""(parsed values, the environment they came from) -> a problem, or ``None``.

The environment is passed as well as the parsed values because not every rule is
about a setting this stage consumes. SEC-001's guard is about the **location** of
``COSMA_SECRET_SOURCE``, whose contents P0-A never reads and which therefore never
becomes a configuration field; a check given only ``values`` could not see it.
"""


def _backoff_window_is_ordered(
    values: Mapping[str, Any], environment: Mapping[str, str]
) -> Problem | None:
    base = values.get("retry_base_ms")
    maximum = values.get("retry_max_ms")
    if base is None or maximum is None:
        return None
    if maximum < base:
        return ("COSMA_RETRY_MAX_MS", f"must be at least COSMA_RETRY_BASE_MS ({base})")
    return None


def secret_store_location_problem(
    values: Mapping[str, Any], environment: Mapping[str, str]
) -> Problem | None:
    """Refuse a secret store whose resolved path lies inside the working tree.

    The application-startup half of the guard ``docs/conventions/secret-setup.md``
    names: *"Store 경로가 repository working tree 아래면 기동 시점에 즉시
    실패시킨다."* Until this existed, any run that bypassed
    ``scripts/with-secret-source.sh`` — an IDE run configuration, a bare
    ``python -m``, a container entrypoint — had no guard at all.

    Three properties are the substance of SEC-001 and are easy to lose.

    * **The comparison is between resolved paths.** A path outside the tree whose
      target is a symbolic link into it is the case a naive check waves through,
      and it is the case that actually puts a credential file under version
      control. ``tests/conftest.py`` calls this function so the session guard and
      the startup guard cannot disagree about that.
    * **The store is never opened.** Location is the entire question. Reading a
      credential to decide where it lives would be the leak the rule exists to
      prevent, so this touches the filesystem only through ``resolve``, and
      SEC-001 case b proves it by pointing the variable at an unreadable file and
      requiring startup to succeed anyway.
    * **An unset variable is not a problem.** P0-A resolves no credential; OQ-007
      assigns resolution to P0-B. Requiring the variable now would invent an
      obligation the stage boundary does not have.

    Permissions are deliberately not re-checked here. ``with-secret-source.sh``
    checks them, and the store's mode is a fact about a file this stage never
    opens; SEC-001 records the gap rather than closing it, because P0-B's resolver
    is where a permission check has something to protect.
    """
    stated = environment.get(SECRET_STORE_VARIABLE, "").strip()
    if not stated:
        return None
    try:
        resolved = Path(stated).expanduser().resolve()
    except OSError:
        # `resolve` is non-strict, so a merely absent path resolves fine and is
        # still compared. Reaching here means the filesystem refused to answer,
        # which names no location inside the tree.
        return None
    if resolved != WORKING_TREE_ROOT and WORKING_TREE_ROOT not in resolved.parents:
        return None
    # The rejected path and the root are printed: neither is a credential value,
    # and an operator who cannot see which path was refused cannot move it. The
    # store's contents are never read, so nothing else about it can be shown.
    return (
        SECRET_STORE_VARIABLE,
        "must name a path outside the repository working tree, but "
        f"{resolved} resolves inside {WORKING_TREE_ROOT} — "
        f"move the store outside the repository; see {SECRET_SETUP_POINTER}",
    )


CROSS_CHECKS: Final[Sequence[CrossCheck]] = (
    _backoff_window_is_ordered,
    secret_store_location_problem,
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
        problem = check(values, env)
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
