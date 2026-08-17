"""The ambient correlation scope that invariant I5 leans on.

I5 says correlation is total. The context variable is what makes that achievable
without threading an argument through every helper, so its scoping rules — entry,
restoration, nesting, and isolation between threads — are the thing under test.
"""

from __future__ import annotations

import threading

import pytest
from platform_core.obs.correlation import (
    CORRELATION_FIELD,
    bind_correlation_id,
    correlation_context,
    current_correlation_id,
    new_correlation_id,
    release_correlation_id,
)

GIVEN_ID = "correlation-under-test"
OTHER_ID = "correlation-under-test-2"


def test_the_field_name_matches_the_contract() -> None:
    assert CORRELATION_FIELD == "correlation_id"


def test_minted_identifiers_are_unique() -> None:
    minted = {new_correlation_id() for _ in range(100)}
    assert len(minted) == 100
    assert all(value for value in minted)


def test_there_is_no_identifier_outside_a_scope() -> None:
    assert current_correlation_id() is None


def test_a_scope_mints_an_identifier_when_none_is_given() -> None:
    with correlation_context() as value:
        assert value
        assert current_correlation_id() == value
    assert current_correlation_id() is None


def test_a_scope_honours_an_identifier_it_is_given() -> None:
    with correlation_context(GIVEN_ID) as value:
        assert value == GIVEN_ID
        assert current_correlation_id() == GIVEN_ID


def test_scopes_nest_and_restore() -> None:
    with correlation_context(GIVEN_ID):
        with correlation_context(OTHER_ID):
            assert current_correlation_id() == OTHER_ID
        assert current_correlation_id() == GIVEN_ID
    assert current_correlation_id() is None


def test_a_scope_is_restored_after_an_exception() -> None:
    with pytest.raises(RuntimeError), correlation_context(GIVEN_ID):
        raise RuntimeError("handler failed")
    assert current_correlation_id() is None


def test_bind_and_release_are_the_explicit_form() -> None:
    token = bind_correlation_id(GIVEN_ID)
    try:
        assert current_correlation_id() == GIVEN_ID
    finally:
        release_correlation_id(token)
    assert current_correlation_id() is None


def test_an_empty_identifier_is_refused() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        bind_correlation_id("")


def test_a_thread_does_not_observe_another_scope() -> None:
    """Two workers in one process must never share an identifier by accident."""
    seen: list[str | None] = []

    def observer() -> None:
        seen.append(current_correlation_id())

    with correlation_context(GIVEN_ID):
        thread = threading.Thread(target=observer)
        thread.start()
        thread.join()
        assert current_correlation_id() == GIVEN_ID

    assert seen == [None]
