"""The single redaction point for the P0-A platform core.

CONTRACT-JOB@0.1 ("Provenance and security") fixes the key set and states that a
matching key's value is replaced by a marker in structured logs, error summaries,
and API responses. SEC-004 fixes the shape of the replacement: the **key name
survives**, because knowing that a token was present is diagnostic while its
value is not.

Every masking decision in the platform is made here. A logger, an error type, and
an HTTP response that each carried their own copy of this rule would eventually
disagree, and the one that disagreed would be the leak.

Two deliberate widenings of the literal contract text, both of which mask more
than the contract requires and never less:

* Keys are casefolded (lowercased, non-alphanumerics removed) and matched by
  containment, so ``DB_PASSWORD``, ``X-Api-Key`` and ``refreshToken`` are covered.
  A strict equality reading would let all three through.
* ``redact_text`` masks ``key=value`` and ``key: value`` pairs inside a plain
  string, so that an error summary — which the contract says is redacted, but
  which is text rather than a mapping — has some boundary rather than none. This
  is best effort by construction: a bare value in prose has no key to match on.

Known limit, recorded in SEC-004: matching is key-name based, so a value placed
under an innocuous key is not detected. In text, a value is also only masked when
a key introduces it — a bare value in prose has nothing to match on, and a value
that continues past whitespace keeps only its first word masked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence, Set
from typing import Any, Final

#: The key set fixed by CONTRACT-JOB@0.1, matched case-insensitively.
REDACTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "token",
        "secret",
        "authorization",
        "cookie",
        "api_key",
        "apikey",
        "credential",
    }
)

#: What replaces a masked value. Distinctive enough to grep evidence for.
REDACTION_MARKER: Final = "[REDACTED]"

#: What replaces a container already being visited, so a cycle cannot recurse.
CYCLE_MARKER: Final = "[CYCLE]"

_NON_ALPHANUMERIC: Final = re.compile(r"[^a-z0-9]+")

_KEY_AFFIX: Final = r"[A-Za-z0-9_.\-]*"

# Authentication scheme words sit between the separator and the value. They are
# not the secret, and keeping them tells an operator what kind of value was here.
_SCHEMES: Final = r"(?:Bearer|Basic|Token|Digest|Negotiate)[ \t]+"


def _casefold_key(key: str) -> str:
    return _NON_ALPHANUMERIC.sub("", key.lower())


_CASEFOLDED_KEYS: Final[frozenset[str]] = frozenset(_casefold_key(key) for key in REDACTED_KEYS)


def _term_pattern(key: str) -> str:
    """Allow the same separators ``_casefold_key`` erases: ``api_key``, ``API KEY``."""
    parts = re.split(r"[_\-\s]+", key)
    return r"[\s_.\-]*".join(re.escape(part) for part in parts)


_TERMS: Final = "|".join(
    sorted((_term_pattern(key) for key in REDACTED_KEYS), key=len, reverse=True)
)

# ``key = value``, ``key: value``, ``"key": "value"``.
#
# The key group matches **only** a sensitive key. An earlier version accepted any
# identifier and left the sensitivity test to the replacement callback, which let
# a harmless leading pair — ``rejected: api_key=...`` — match first, swallow the
# real pair inside its value, and pass the whole thing through unmasked. Narrowing
# the key means a non-sensitive pair never starts a match at all.
#
# The affixes on either side of the term keep this consistent with
# ``is_redacted_key``, which matches by containment: ``db_password`` and
# ``refreshToken`` are one rule in both the mapping walk and here.
_ASSIGNMENT: Final = re.compile(
    rf"""(?P<key>{_KEY_AFFIX}(?:{_TERMS}){_KEY_AFFIX})"""
    r"""(?P<closing>["']?)"""
    r"""(?P<separator>[ \t]*[=:][ \t]*)"""
    rf"""(?P<scheme>{_SCHEMES})?"""
    r"""(?P<value>"[^"]*"|'[^']*'|[^\s,;)\]}]+)""",
    re.IGNORECASE,
)


def is_redacted_key(key: object) -> bool:
    """Return whether a mapping key's value must be masked."""
    if not isinstance(key, str):
        return False
    folded = _casefold_key(key)
    return any(term in folded for term in _CASEFOLDED_KEYS)


def redact(value: object) -> Any:
    """Return ``value`` with every sensitive mapping value replaced by a marker.

    Mappings and sequences are walked recursively. Strings and bytes are treated
    as leaves rather than sequences of characters. A container reached twice on
    one path — a cycle — yields ``CYCLE_MARKER`` instead of recursing. The input
    is never mutated.
    """
    return _redact(value, frozenset())


def redact_mapping(fields: Mapping[Any, Any] | None) -> dict[str, Any]:
    """Redact a mapping and coerce its keys to strings, ready for JSON."""
    if not fields:
        return {}
    return {
        str(key): (REDACTION_MARKER if is_redacted_key(key) else _redact(item, frozenset()))
        for key, item in fields.items()
    }


def redact_text(text: str) -> str:
    """Mask ``key=value`` pairs in free text whose key is sensitive.

    Best effort, and only a second line of defence: the operator-visible summary
    is expected to name a failure class, not to quote a payload.
    """

    def replace(match: re.Match[str]) -> str:
        # Defensive duplication: the pattern already admits only sensitive keys,
        # so this can fire only if the two rules ever drift apart.
        if not is_redacted_key(match.group("key")):
            return match.group(0)
        return (
            f"{match.group('key')}{match.group('closing')}{match.group('separator')}"
            f"{match.group('scheme') or ''}{REDACTION_MARKER}"
        )

    return _ASSIGNMENT.sub(replace, text)


def _redact(value: object, visiting: frozenset[int]) -> Any:
    if isinstance(value, str | bytes | bytearray):
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in visiting:
            return CYCLE_MARKER
        nested = visiting | {identity}
        return {
            key: (REDACTION_MARKER if is_redacted_key(key) else _redact(item, nested))
            for key, item in value.items()
        }
    if isinstance(value, Sequence | Set):
        identity = id(value)
        if identity in visiting:
            return CYCLE_MARKER
        nested = visiting | {identity}
        return [_redact(item, nested) for item in value]
    return value
