"""The CONTRACT-JOB@0.1 error table, checked row by row.

Two obligations are under test. Retryability is a property of the error class,
because JOB-004's intent is that a permanent failure is not retried on the
strength of its own classification rather than on how a ``try`` block happened to
be written. And protected detail stays protected: it must be impossible to reach
through the default string representation of the error.
"""

from __future__ import annotations

import json

import pytest
from platform_core.errors import (
    ERROR_TYPES,
    ConfigurationInvalidError,
    ErrorClass,
    HandlerUnknownError,
    LeaseAbandonedError,
    PlatformError,
    PlatformPermanentError,
    PlatformTransientError,
    ProtectedDetail,
)
from platform_core.obs.redaction import REDACTION_MARKER

SENSITIVE_MARKER = "marker-must-not-leak-42"
ORDINARY_MARKER = "marker-must-survive-42"

# The "Retryable" column of the contract's error table.
CONTRACT_ROWS = (
    (PlatformTransientError, ErrorClass.PLATFORM_TRANSIENT, True),
    (PlatformPermanentError, ErrorClass.PLATFORM_PERMANENT, False),
    (HandlerUnknownError, ErrorClass.HANDLER_UNKNOWN, False),
    (LeaseAbandonedError, ErrorClass.LEASE_ABANDONED, True),
    (ConfigurationInvalidError, ErrorClass.CONFIGURATION_INVALID, False),
)


@pytest.mark.parametrize(("error_type", "error_class", "retryable"), CONTRACT_ROWS)
def test_each_row_of_the_error_table_is_a_type(
    error_type: type[PlatformError], error_class: ErrorClass, retryable: bool
) -> None:
    error = error_type("something went wrong")
    assert error.error_class is error_class
    assert error.retryable is retryable
    assert error_class.retryable is retryable


def test_the_table_is_complete() -> None:
    assert set(ERROR_TYPES) == set(ErrorClass)
    assert len(CONTRACT_ROWS) == len(ErrorClass)


def test_the_class_answers_retryability_not_the_call_site() -> None:
    """JOB-004: the decision travels with the failure."""
    raised: PlatformError = PlatformPermanentError("injected permanent failure")
    assert not raised.retryable
    assert raised.error_class.value == "PLATFORM_PERMANENT"


def test_the_default_string_is_the_summary_alone() -> None:
    error = PlatformPermanentError("injected permanent failure", {"token": SENSITIVE_MARKER})
    assert str(error) == "injected permanent failure"
    assert SENSITIVE_MARKER not in str(error)
    assert SENSITIVE_MARKER not in repr(error)
    assert SENSITIVE_MARKER not in "".join(str(item) for item in error.args)


def test_detail_never_renders_itself() -> None:
    error = PlatformPermanentError("failed", {"note": ORDINARY_MARKER})
    assert ORDINARY_MARKER not in str(error.detail)
    assert ORDINARY_MARKER not in repr(error.detail)
    assert ORDINARY_MARKER not in f"{error.detail}"
    assert ORDINARY_MARKER not in json.dumps({"detail": error.detail}, default=str)


def test_detail_is_reachable_only_through_the_protected_path() -> None:
    error = PlatformPermanentError("failed", {"note": ORDINARY_MARKER})
    assert error.detail.for_protected_debug() == {"note": ORDINARY_MARKER}
    assert error.detail.field_names() == ("note",)
    assert len(error.detail) == 1


def test_protected_does_not_mean_unredacted() -> None:
    """SEC-004: the boundary holds inside the protected representation too."""
    error = PlatformPermanentError(
        "failed",
        {
            "token": SENSITIVE_MARKER,
            "nested": {"cookie": SENSITIVE_MARKER},
            "note": ORDINARY_MARKER,
        },
    )
    revealed = error.detail.for_protected_debug()
    assert revealed["token"] == REDACTION_MARKER
    assert revealed["nested"] == {"cookie": REDACTION_MARKER}
    assert revealed["note"] == ORDINARY_MARKER, "detection control failed"


def test_the_protected_copy_cannot_be_edited_in_place() -> None:
    error = PlatformPermanentError("failed", {"note": ORDINARY_MARKER})
    revealed = error.detail.for_protected_debug()
    revealed["note"] = "changed"
    assert error.detail.for_protected_debug() == {"note": ORDINARY_MARKER}


def test_an_absent_detail_is_empty_not_missing() -> None:
    error = PlatformTransientError("injected retryable failure")
    assert not error.detail
    assert error.detail.for_protected_debug() == {}
    assert isinstance(error.detail, ProtectedDetail)


def test_the_summary_is_masked_where_it_can_be() -> None:
    error = HandlerUnknownError(f"rejected: api_key={SENSITIVE_MARKER}")
    assert SENSITIVE_MARKER not in error.summary
    assert REDACTION_MARKER in error.summary


def test_the_operator_view_carries_no_detail() -> None:
    error = PlatformPermanentError("injected permanent failure", {"token": SENSITIVE_MARKER})
    view = error.operator_view()
    assert view == {
        "error_class": "PLATFORM_PERMANENT",
        "error_summary": "injected permanent failure",
        "retryable": False,
    }
    assert SENSITIVE_MARKER not in json.dumps(view)


def test_a_platform_error_is_catchable_as_one_type() -> None:
    with pytest.raises(PlatformError):
        raise LeaseAbandonedError("lease expired while running")
