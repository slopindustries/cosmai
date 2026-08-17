"""The error table of CONTRACT-JOB@0.1, expressed as types.

Two properties of the contract are load-bearing and are therefore encoded rather
than left to the call site:

* **Retryability belongs to the error class.** JOB-004's intent is that a
  permanent failure is not retried because the failure said so, not because some
  ``except`` clause happened to be written that way. ``ErrorClass.retryable`` is
  the only answer to that question in the platform.
* **Debug detail is protected by construction.** The contract says
  ``error_detail`` is never in an API response by default and reaches logs only
  at debug level. A plain ``dict`` attribute would satisfy that only for as long
  as everyone remembered; ``ProtectedDetail`` cannot be printed, formatted, or
  serialized into an operator-visible string by accident, and it is redacted the
  moment it is built.

Protected is not the same as unredacted. SEC-004 is explicit that the redaction
boundary still holds inside the protected representation, so the masking happens
at construction and there is no way back to the original values.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from typing import Any, ClassVar, Final, final

from platform_core.obs.redaction import redact_mapping, redact_text


class ErrorClass(StrEnum):
    """Every error class in the CONTRACT-JOB@0.1 error table."""

    PLATFORM_TRANSIENT = "PLATFORM_TRANSIENT"
    PLATFORM_PERMANENT = "PLATFORM_PERMANENT"
    HANDLER_UNKNOWN = "HANDLER_UNKNOWN"
    LEASE_ABANDONED = "LEASE_ABANDONED"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"

    @property
    def retryable(self) -> bool:
        """Whether the contract permits an automatic further attempt."""
        return self in _RETRYABLE_CLASSES


_RETRYABLE_CLASSES: Final[frozenset[ErrorClass]] = frozenset(
    {ErrorClass.PLATFORM_TRANSIENT, ErrorClass.LEASE_ABANDONED}
)

_WITHHELD: Final = "<withheld>"


@final
class ProtectedDetail:
    """Debug detail that is redacted on the way in and never rendered by default.

    ``str`` and ``repr`` report the field count and nothing else, so an f-string,
    a traceback, or ``json.dumps(..., default=str)`` cannot leak it. Reading the
    values is an explicit act with a name that says what it is for.
    """

    __slots__ = ("_fields",)

    def __init__(self, fields: Mapping[str, Any] | None = None) -> None:
        self._fields = redact_mapping(fields)

    def for_protected_debug(self) -> dict[str, Any]:
        """Return the redacted fields, for the protected-debug path only."""
        return deepcopy(self._fields)

    def field_names(self) -> tuple[str, ...]:
        """Names only. Safe to show an operator; says what was captured."""
        return tuple(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def __bool__(self) -> bool:
        return bool(self._fields)

    def __repr__(self) -> str:
        return f"ProtectedDetail({len(self._fields)} field(s), {_WITHHELD})"

    def __str__(self) -> str:
        return repr(self)


class PlatformError(Exception):
    """Base type for every failure the platform classifies.

    Subclasses bind one ``ErrorClass``. The class is always set, so — as the
    contract puts it — an unstructured exception message is never the only
    external error contract.
    """

    error_class: ClassVar[ErrorClass]

    def __init__(self, summary: str, detail: Mapping[str, Any] | None = None) -> None:
        self.summary = redact_text(summary)
        self.detail = ProtectedDetail(detail)
        super().__init__(self.summary)

    @property
    def retryable(self) -> bool:
        return self.error_class.retryable

    def operator_view(self) -> dict[str, Any]:
        """The default, operator-visible representation. Carries no detail."""
        return {
            "error_class": self.error_class.value,
            "error_summary": self.summary,
            "retryable": self.retryable,
        }

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(error_class={self.error_class.value!r}, "
            f"summary={self.summary!r}, detail={_WITHHELD})"
        )


class PlatformTransientError(PlatformError):
    """Retryable platform failure. Rescheduled with backoff until the budget ends."""

    error_class = ErrorClass.PLATFORM_TRANSIENT


class PlatformPermanentError(PlatformError):
    """Non-retryable platform failure. The job goes terminal on this attempt."""

    error_class = ErrorClass.PLATFORM_PERMANENT


class HandlerUnknownError(PlatformError):
    """The named handler is not registered. Not retried; register it, then retry."""

    error_class = ErrorClass.HANDLER_UNKNOWN


class LeaseAbandonedError(PlatformError):
    """A lease expired while running. Recovery is automatic; the attempt is closed."""

    error_class = ErrorClass.LEASE_ABANDONED


class ConfigurationInvalidError(PlatformError):
    """Invalid platform configuration, or a job rejected at creation.

    Not retryable by design: SEC-003 requires a supervisor restart to fail
    identically rather than eventually succeed.
    """

    error_class = ErrorClass.CONFIGURATION_INVALID


ERROR_TYPES: Final[Mapping[ErrorClass, type[PlatformError]]] = {
    ErrorClass.PLATFORM_TRANSIENT: PlatformTransientError,
    ErrorClass.PLATFORM_PERMANENT: PlatformPermanentError,
    ErrorClass.HANDLER_UNKNOWN: HandlerUnknownError,
    ErrorClass.LEASE_ABANDONED: LeaseAbandonedError,
    ErrorClass.CONFIGURATION_INVALID: ConfigurationInvalidError,
}
