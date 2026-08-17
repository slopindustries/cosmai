"""SEC-004: the redaction boundary, at the one place that implements it.

The scenario's own reasoning drives the shape of these tests: *"A run in which
nothing leaked is therefore not evidence."* Every masking assertion here is
paired with a detection control — a distinctive marker under an ordinary key that
**must** survive. Without it, "no marker was found" and "nothing was ever
searched" produce the same green result.
"""

from __future__ import annotations

from typing import Any

import pytest
from platform_core.obs.redaction import (
    CYCLE_MARKER,
    REDACTED_KEYS,
    REDACTION_MARKER,
    is_redacted_key,
    redact,
    redact_mapping,
    redact_text,
)

SENSITIVE_MARKER = "marker-must-not-leak-42"
ORDINARY_MARKER = "marker-must-survive-42"
ORDINARY_KEY = "note"


def flatten(value: Any) -> list[str]:
    """Every string anywhere in a redacted structure, keys and values alike."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            found.append(str(key))
            found.extend(flatten(item))
        return found
    if isinstance(value, list):
        return [text for item in value for text in flatten(item)]
    return [str(value)]


@pytest.mark.parametrize("key", sorted(REDACTED_KEYS))
def test_every_contract_key_is_masked(key: str) -> None:
    result = redact({key: SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER})
    assert result[key] == REDACTION_MARKER
    assert result[ORDINARY_KEY] == ORDINARY_MARKER, "detection control failed"


@pytest.mark.parametrize("key", ["TOKEN", "Token", "ApiKey", "API_KEY", "Authorization"])
def test_key_matching_ignores_case_and_separators(key: str) -> None:
    assert is_redacted_key(key)
    assert redact({key: SENSITIVE_MARKER})[key] == REDACTION_MARKER


@pytest.mark.parametrize("key", ["db_password", "X-Api-Key", "refreshToken", "user.credential"])
def test_a_sensitive_key_with_an_affix_is_still_masked(key: str) -> None:
    """Masking more than the contract's literal set is the safe direction."""
    assert redact({key: SENSITIVE_MARKER})[key] == REDACTION_MARKER


@pytest.mark.parametrize("key", ["note", "job_id", "correlation_id", "handler", "attempt_no"])
def test_ordinary_keys_are_untouched(key: str) -> None:
    assert not is_redacted_key(key)
    assert redact({key: ORDINARY_MARKER})[key] == ORDINARY_MARKER


def test_key_names_survive_so_the_masking_is_diagnostic() -> None:
    """SEC-004: knowing a token was present is diagnostic; its value is not."""
    result = redact({"token": SENSITIVE_MARKER})
    assert "token" in result
    assert SENSITIVE_MARKER not in flatten(result)


def test_nested_mappings_and_sequences_are_walked() -> None:
    payload = {
        "outer": {
            "items": [
                {"password": SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER},
                ("api_key", {"cookie": SENSITIVE_MARKER}),
            ]
        },
        ORDINARY_KEY: ORDINARY_MARKER,
    }
    result = redact(payload)
    strings = flatten(result)
    assert SENSITIVE_MARKER not in strings
    assert strings.count(ORDINARY_MARKER) == 2, "detection control failed"
    assert result[ORDINARY_KEY] == ORDINARY_MARKER


def test_the_input_is_not_mutated() -> None:
    payload: dict[str, Any] = {"token": SENSITIVE_MARKER, "nested": {"secret": SENSITIVE_MARKER}}
    redact(payload)
    assert payload["token"] == SENSITIVE_MARKER
    assert payload["nested"]["secret"] == SENSITIVE_MARKER


def test_a_cycle_terminates_instead_of_recursing() -> None:
    payload: dict[str, Any] = {"token": SENSITIVE_MARKER, ORDINARY_KEY: ORDINARY_MARKER}
    payload["self"] = payload
    result = redact(payload)
    assert result["self"] == CYCLE_MARKER
    assert result["token"] == REDACTION_MARKER
    assert result[ORDINARY_KEY] == ORDINARY_MARKER, "detection control failed"


def test_a_repeated_but_acyclic_value_is_kept_twice() -> None:
    """A shared child is not a cycle; treating it as one would hide real fields."""
    shared = {ORDINARY_KEY: ORDINARY_MARKER}
    result = redact({"left": shared, "right": shared})
    assert result["left"] == {ORDINARY_KEY: ORDINARY_MARKER}
    assert result["right"] == {ORDINARY_KEY: ORDINARY_MARKER}


def test_a_cyclic_sequence_terminates() -> None:
    items: list[Any] = [ORDINARY_MARKER]
    items.append(items)
    result = redact({"items": items})
    assert result["items"] == [ORDINARY_MARKER, CYCLE_MARKER]


def test_non_string_keys_do_not_break_the_walk() -> None:
    result = redact({1: SENSITIVE_MARKER, None: ORDINARY_MARKER})
    assert result[1] == SENSITIVE_MARKER
    assert result[None] == ORDINARY_MARKER


def test_redact_mapping_coerces_keys_for_json() -> None:
    result = redact_mapping({1: ORDINARY_MARKER, "token": SENSITIVE_MARKER})
    assert result == {"1": ORDINARY_MARKER, "token": REDACTION_MARKER}


def test_redact_mapping_accepts_nothing() -> None:
    assert redact_mapping(None) == {}
    assert redact_mapping({}) == {}


@pytest.mark.parametrize(
    "text",
    [
        f"failed with token={SENSITIVE_MARKER}",
        f'failed with "token": "{SENSITIVE_MARKER}"',
        f"failed with Authorization: {SENSITIVE_MARKER}",
    ],
)
def test_text_assignments_are_masked(text: str) -> None:
    masked = redact_text(text)
    assert SENSITIVE_MARKER not in masked
    assert REDACTION_MARKER in masked
    assert "token" in masked.lower() or "authorization" in masked.lower()


def test_a_harmless_pair_in_front_does_not_shield_a_sensitive_one() -> None:
    """Regression: a leading ``rejected:`` pair used to swallow the real pair.

    The key group accepted any identifier, so the first match consumed
    ``rejected: api_key=<value>`` whole, found ``rejected`` harmless, and returned
    it untouched. The sensitive key was never examined.
    """
    masked = redact_text(f"rejected: api_key={SENSITIVE_MARKER}")
    assert SENSITIVE_MARKER not in masked
    assert masked == f"rejected: api_key={REDACTION_MARKER}"


def test_every_sensitive_pair_in_one_string_is_masked() -> None:
    masked = redact_text(
        f"token={SENSITIVE_MARKER} {ORDINARY_KEY}={ORDINARY_MARKER} "
        f"cookie={SENSITIVE_MARKER} password={SENSITIVE_MARKER}"
    )
    assert SENSITIVE_MARKER not in masked
    assert masked.count(REDACTION_MARKER) == 3
    assert ORDINARY_MARKER in masked, "detection control failed"


@pytest.mark.parametrize(
    "key", ["api_key", "apikey", "api-key", "API KEY", "Api_Key", "X-Api-Key"]
)
def test_every_spelling_of_a_separated_key_is_masked(key: str) -> None:
    masked = redact_text(f"{key}={SENSITIVE_MARKER}")
    assert SENSITIVE_MARKER not in masked
    assert masked == f"{key}={REDACTION_MARKER}"


def test_an_affixed_sensitive_key_is_masked_in_text_as_well() -> None:
    """Deliberately the same containment rule ``is_redacted_key`` applies.

    ``mytoken_count=3`` is masked, because the mapping key ``mytoken_count`` is
    masked too. Diverging here would give the module two notions of a sensitive
    key, and the weaker one would be the leak. Over-masking is the safe direction.
    """
    assert is_redacted_key("mytoken_count")
    assert redact_text("mytoken_count=3") == f"mytoken_count={REDACTION_MARKER}"


def test_an_authentication_scheme_survives_but_its_value_does_not() -> None:
    masked = redact_text(f"authorization: Bearer {SENSITIVE_MARKER}")
    assert SENSITIVE_MARKER not in masked
    assert masked == f"authorization: Bearer {REDACTION_MARKER}"


def test_text_masking_leaves_ordinary_assignments_alone() -> None:
    text = f"handler=succeed attempt_no=2 {ORDINARY_KEY}={ORDINARY_MARKER}"
    assert redact_text(text) == text, "detection control failed"


def test_text_masking_stops_at_the_end_of_the_value() -> None:
    masked = redact_text(f"token={SENSITIVE_MARKER}, {ORDINARY_KEY}={ORDINARY_MARKER}")
    assert ORDINARY_MARKER in masked, "detection control failed"
    assert SENSITIVE_MARKER not in masked
