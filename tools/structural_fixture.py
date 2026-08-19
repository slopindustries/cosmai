"""Turn a real captured response into a fixture that is ours to publish (DP-022).

`docs/conventions/data-handling.md` refuses to let redaction create redistribution rights,
in as many words: *"원본의 일부를 잘랐거나 redaction했다는 사실만으로 재배포 권리가 생기지
않는다."* This tool does not redact. It **generates a new document** that reproduces every
structural property observed in a capture and contains none of its content — the executable
form of the sentence *"this endpoint returns `items` as an array of objects each carrying
`link` as a non-empty absolute URL"*, which has always been ours to say.

**What is preserved is exactly what a test can assert on**, and the hard part is that this
is more than "the JSON types". `normalizer.naver.blog` exists to strip `<b>` and decode
`&quot;`; a fixture that replaced `촉촉한 <b>수분크림</b> 후기` with `제품 후기` would destroy
the only property that rule is about, and the test over it would pass while proving nothing.
So a string's **shape class** survives — its markup positions, its entity references, its
date format, its URL depth — and the words between them do not. `shape_of` is the definition
of "shape" this whole packet rests on, and `tests/test_structural_fixtures.py` compares a
capture's shape to its fixture's directly.

**Everything is deterministic** (DP-022 D3). Substitutes are derived from a digest of the
value they replace, so the same capture always yields the same fixture, equal values in
different places get equal substitutes, and one changed character changes the output. A
fixture nobody can re-derive is an assertion nobody can re-check.

This lives in `tools/` rather than under `experiments/integrated-p0/` because the rule
outlives P0, and anything under the experiment root is committed to being thrown away.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final

__all__ = [
    "RULESET_VERSION",
    "derive",
    "manifest_for",
    "shape_of",
]

#: Bumped whenever a substitution rule changes. A manifest names it so that a fixture and
#: the tool that made it cannot silently drift apart — regenerating under a new ruleset is
#: a different artifact, not the same one.
RULESET_VERSION: Final = "1"

#: Markup and entity references, kept in place so a rule that strips them still has
#: something to strip. Only the text *between* them is replaced.
_MARKUP: Final = re.compile(r"(<[^>]*>|&[A-Za-z]+;|&#x?[0-9A-Fa-f]+;)")

_YYYYMMDD: Final = re.compile(r"^\d{8}$")
_ISO_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RFC_DATE: Final = re.compile(r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} ")
_URL: Final = re.compile(r"^[a-z][a-z0-9+.-]*://")

#: The alphabet substituted text is drawn from. Hangul syllables, because every source
#: selected so far returns Korean and a fixture in Latin letters would not exercise the
#: same encoding path — `ensure_ascii`, byte length, and normalization all behave
#: differently, and `domain.store.canonical_body` has a rule about exactly that.
_SYLLABLES: Final = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"

_LATIN: Final = "abcdefghijklmnopqrstuvwxyz"


def shape_of(value: Any) -> Any:
    """Everything about `value` that a test could assert on, with the content removed.

    This is the definition the packet rests on. Two documents with equal shapes are
    interchangeable to every assertion in this repository; two with unequal shapes are not.

    Deliberately **not** ignored, because something depends on each:

    - `int` versus `float` — `[측정]` the real DataLab response carried `ratio: 100` and
      `ratio: 96.10965` in one body, and the normalizer accepts both;
    - `null` versus `""` versus an absent key — three different claims about a source;
    - array length — a collector's item count comes from it;
    - a string's markup and entity structure — two normalizer rules read it;
    - a string's date format class — the parser refuses anything but `yyyymmdd`;
    - whether a string is a URL and how deep its path is — `link` is an item's identity.
    """
    if isinstance(value, dict):
        return {"": "object", **{key: shape_of(item) for key, item in value.items()}}
    if isinstance(value, list):
        return ["array", *[shape_of(item) for item in value]]
    if isinstance(value, bool):
        return "bool"
    if value is None:
        return "null"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return _string_shape(value)
    return f"other:{type(value).__name__}"


def derive(raw: bytes) -> bytes:
    """A structural fixture for this capture. Deterministic, and content-free."""
    document = json.loads(raw)
    replaced = _replace(document)
    return json.dumps(replaced, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")


def manifest_for(
    raw: bytes,
    endpoint: str,
    captured_at: str,
    represents: list[str],
    does_not_represent: list[str],
) -> dict[str, Any]:
    """What ties a synthetic document back to a real event (DP-022 D4, D5).

    The original's digest is the load-bearing field: without it a structural fixture is
    indistinguishable from something invented, and inventing one is what it replaces.

    `does_not_represent` is required rather than optional. `data-handling.md`'s promotion
    rule asks for "sample이 대표하는 behavior와 대표하지 못하는 범위", and one capture is one
    moment of one query — it cannot show a `429`, an empty result set it did not contain, or
    a field the API omits only sometimes.

    Nothing here quotes the capture. A manifest that described the content by example would
    put the content back.
    """
    return {
        "ruleset_version": RULESET_VERSION,
        "endpoint": endpoint,
        "captured_at": captured_at,
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "original_bytes": len(raw),
        "fixture_sha256": hashlib.sha256(derive(raw)).hexdigest(),
        "represents": list(represents),
        "does_not_represent": list(does_not_represent),
        "derivation": (
            "Structurally derived under DP-022: every key, nesting level, array length, "
            "JSON type, markup position, entity reference, date format, and URL depth is "
            "the capture's; every string's text, every identifier, and every numeric "
            "magnitude is generated. No content of the original is present."
        ),
    }


# --------------------------------------------------------------------------- #
# Substitution
# --------------------------------------------------------------------------- #


def _replace(value: Any) -> Any:
    if isinstance(value, dict):
        # Key order is the capture's, because a reader comparing a fixture to the vendor's
        # documentation reads them in order.
        return {key: _replace(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item) for item in value]
    if isinstance(value, bool) or value is None:
        # A boolean and a null are already content-free: they carry a claim about the
        # source's behaviour and nothing about anybody's data.
        return value
    if isinstance(value, int):
        return _an_int(value)
    if isinstance(value, float):
        return _a_float(value)
    if isinstance(value, str):
        return _a_string(value)
    return value


def _seed(value: object) -> int:
    """A stable number derived from the value being replaced.

    Keyed on the value rather than on position, so equal inputs get equal substitutes —
    two items sharing a `postdate` still share one in the fixture, which is a property a
    test could assert on.
    """
    material = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _an_int(value: int) -> int:
    """An integer of the same magnitude class, and never the original.

    The magnitude class survives because a reader needs to know that `total` is a large
    count and `display` is a small one; the value does not, because it is an observation
    about the provider's index rather than about their API's shape.
    """
    digits = len(str(abs(value)))
    if digits <= 1:
        return value if value in (0, 1) else _spread(value, 0, 9)
    low = 10 ** (digits - 1)
    return _spread(value, low, low * 10 - 1)


def _a_float(value: float) -> float:
    """A float in the same range, with the same decimal precision.

    Precision survives because a consumer that rounds or formats reads it; the value does
    not. Kept a `float` even when it lands on a whole number, so `shape_of` still separates
    it from an `int`.
    """
    text = repr(value)
    places = len(text.split(".")[1]) if "." in text and "e" not in text else 5
    magnitude = max(abs(value), 1.0)
    scaled = _spread(value, 0, 10**6) / 10**6 * magnitude
    return round(scaled, min(places, 10)) + 0.0


def _spread(value: object, low: int, high: int) -> int:
    return low + _seed(value) % (high - low + 1)


def _a_string(value: str) -> str:
    """A string of the same shape class, with the words replaced.

    The order of these cases is the rule: the most *structural* reading wins. A URL is
    replaced as a URL rather than as prose, because something downstream parses it; a date
    is replaced as a date for the same reason. Only what nothing parses becomes text.
    """
    if value == "":
        return ""
    if _URL.match(value):
        return _a_url(value)
    if _YYYYMMDD.match(value):
        return (
            f"{_spread(value, 2000, 2099)}"
            f"{_spread(value + 'm', 1, 12):02d}{_spread(value + 'd', 1, 28):02d}"
        )
    if _ISO_DATE.match(value):
        return (
            f"{_spread(value, 2000, 2099)}-"
            f"{_spread(value + 'm', 1, 12):02d}-{_spread(value + 'd', 1, 28):02d}"
        )
    if _RFC_DATE.match(value):
        # A header-style date. The format is what `lastBuildDate` is read for, if anything
        # ever reads it; the instant is not ours to republish.
        return "Mon, 01 Jan 2001 00:00:00 +0900"
    return _text_like(value)


def _a_url(value: str) -> str:
    """Same scheme, same path depth, `example.com`, generated segments.

    Path depth survives because it is what distinguishes a URL addressing a post from one
    addressing a blog, and a collector keys its items on the former.
    """
    scheme, _, rest = value.partition("://")
    segments = rest.split("/")
    replaced = [
        _word(f"{value}/{index}", _LATIN, 6 + index)
        for index in range(1, len(segments))
    ]
    return f"{scheme}://example.com" + "".join(f"/{part}" for part in replaced)


def _text_like(value: str) -> str:
    """Prose with its markup left standing.

    `_MARKUP` splits on tags and entity references and `re.split` keeps the separators, so
    the odd positions are markup — copied through untouched — and the even positions are
    text, replaced with syllables of the same length. That is why a fixture derived from a
    title carrying `<b>` still carries it, and why one derived from a plain description
    does not acquire any.
    """
    parts = _MARKUP.split(value)
    out: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1 or part == "":
            out.append(part)
            continue
        out.append(_word(f"{value}#{index}", _SYLLABLES, len(part)))
    return "".join(out)


def _word(material: str, alphabet: str, length: int) -> str:
    """`length` characters drawn deterministically from `alphabet`.

    Length is preserved because a byte-length or a truncation boundary is a property a
    consumer can meet, and a fixture whose fields are all four characters long would never
    reach one.
    """
    if length <= 0:
        return ""
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    while len(digest) < length:
        digest += hashlib.sha256(digest).digest()
    return "".join(alphabet[byte % len(alphabet)] for byte in digest[:length])


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def _string_shape(value: str) -> str:
    """A string's shape class: what survives derivation, described.

    Two strings share a class when every assertion in this repository would treat them
    alike. The markup skeleton is part of the class rather than a footnote to it — that is
    the whole reason this tool is more than a type dump.
    """
    if value == "":
        return "str:empty"
    if _URL.match(value):
        return f"str:url:{value.count('/')}"
    if _YYYYMMDD.match(value):
        return "str:date:yyyymmdd"
    if _ISO_DATE.match(value):
        return "str:date:iso"
    if _RFC_DATE.match(value):
        return "str:date:rfc"
    parts = _MARKUP.split(value)
    skeleton = "".join(
        part if index % 2 == 1 else f"[{len(part)}]" for index, part in enumerate(parts)
    )
    return f"str:text:{skeleton}"
