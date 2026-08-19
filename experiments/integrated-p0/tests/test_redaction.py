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

#: The key set `CONTRACT-JOB@0.1` fixes, **written out as literals**.
#:
#: `[측정]` This existed as `sorted(REDACTED_KEYS)` until 2026-08-19, and
#: `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B2 measured what that meant: removing a member
#: from the production constant removed **its own test cases**, and the suite reported eight
#: fewer tests with no failure and no warning. Four sites across three modules were
#: parametrized that way — every one of SEC-004's evidence chain.
#:
#: `[추론]` The pattern this replaces is the one the repository already uses everywhere else:
#: `test_db.py` hard-codes `STATES` and `OUTCOMES`, `test_errors.py` hard-codes
#: `CONTRACT_ROWS`. A test derived from the thing it is meant to pin cannot notice the thing
#: changing. This set is the contract's, not the code's, and it belongs in the test as text.
CONTRACT_REDACTED_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)


def test_the_redacted_key_set_is_exactly_what_the_contract_fixes() -> None:
    """The pin itself. Adding or removing a key must be a decision someone records here.

    A key *added* to the production set without appearing here is as much a change to
    `CONTRACT-JOB@0.1`'s masking surface as one removed, so this is an equality and not a
    subset.
    """
    assert sorted(REDACTED_KEYS) == sorted(CONTRACT_REDACTED_KEYS)

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


@pytest.mark.parametrize("key", sorted(CONTRACT_REDACTED_KEYS))
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


class TestASensitivePairInsideAValueIsMasked:
    """`[측정]` Two independent reviews found the same gap one layer apart.

    `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B4 measured `attempt_view`'s `redact(fields)`
    and the protected view's `redact(detail)` as **GREEN** — deleting either changed nothing,
    because no `job_attempt` column name is in `REDACTED_KEYS` and `redact` matched by key
    name only. `ADVERSARIAL-REVIEW-2026-08-19.md` F3 called the same thing value-level
    redaction.

    `[결정]` Closed by making `redact` apply `redact_text` to string values, which is the
    module's own stated principle — *"both of which mask more than the contract requires and
    never less"* — extended to the one place it was not applied. The key-name limit SEC-004
    records still stands for a bare value with no key introducing it; what changes is that a
    `key=value` pair **inside** a string is now caught wherever the mapping walk reaches.
    """

    def test_a_pair_inside_a_summary_string_is_masked(self) -> None:
        masked = redact({"error_summary": "the handler failed: token=super-secret-42"})

        assert masked["error_summary"] == "the handler failed: token=[REDACTED]"

    def test_the_same_holds_through_redact_mapping(self) -> None:
        masked = redact_mapping({"error_summary": "refused: api_key=abc123"})

        assert masked["error_summary"] == "refused: api_key=[REDACTED]"

    def test_a_pair_nested_in_a_list_is_masked(self) -> None:
        masked = redact({"notes": ["fine", "authorization: Bearer abc123"]})

        assert masked["notes"] == ["fine", "authorization: Bearer [REDACTED]"]

    def test_an_innocent_string_is_left_alone(self) -> None:
        """The control. A rule that rewrote every string would pass all three cases above."""
        original = "the handler failed after 3 attempts: state=RUNNING"

        assert redact({"error_summary": original})["error_summary"] == original

    def test_bytes_are_still_left_alone(self) -> None:
        """Raw payloads pass through this walk and must not be rewritten — a mutated
        payload is a lost original, which is worse than an unmasked one it never held."""
        payload = b"token=not-text-and-not-ours"

        assert redact({"body": payload})["body"] == payload
