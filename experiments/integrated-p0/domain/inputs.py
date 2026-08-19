"""The registry of approved local inputs — DP-024.

`domain.outbound` is this module's sibling and its shape is deliberately copied. An
importer names an **input**, exactly as a collector names an endpoint; the operator's
approved profile says what that name is; and the add-on never composes, sees, or holds a
path. Everything below is the filesystem half of DP-008 D4.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class InputRefusalReason(StrEnum):
    """Why an input was refused, as a value an operator surface can render."""

    SOURCE_HAS_NO_PROFILE = "SOURCE_HAS_NO_PROFILE"
    INPUT_NOT_DECLARED = "INPUT_NOT_DECLARED"
    MEMBER_ESCAPES_ROOT = "MEMBER_ESCAPES_ROOT"
    ROOT_IS_NOT_A_DIRECTORY = "ROOT_IS_NOT_A_DIRECTORY"
    INPUT_DOES_NOT_EXIST = "INPUT_DOES_NOT_EXIST"
    INPUT_IS_NOT_A_FILE = "INPUT_IS_NOT_A_FILE"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"


@dataclass(frozen=True)
class InputRefusal:
    """A refused input. Carries the rule and enough detail to act on it."""

    reason: InputRefusalReason
    summary: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InputProfile:
    """What an operator approved this source may read."""

    root: Path
    inputs: Mapping[str, str]


@dataclass(frozen=True)
class PreparedInput:
    """An input the policy has approved. Not yet opened."""

    input_ref: str
    path: Path


class InputRefused(Exception):
    """Raised when a read is refused after the input was already approved.

    `resolve_input` returns a refusal because refusing is one of its two ordinary
    answers. `open_stream` raises, because by then the add-on is iterating and there is
    no return value left to inspect — the same split `domain.transport` makes.
    """

    def __init__(self, refusal: InputRefusal) -> None:
        super().__init__(f"{refusal.reason.value}: {refusal.summary}")
        self.refusal = refusal


def read_input_profile(stored: Any) -> InputProfile | None:
    """Turn the stored `source.input_profile` column into a profile, or None."""
    if not isinstance(stored, Mapping):
        return None
    root = stored.get("root")
    if not isinstance(root, str) or not root:
        return None
    inputs = stored.get("inputs")
    if not isinstance(inputs, Mapping):
        return None
    return InputProfile(
        root=Path(root),
        inputs={str(name): str(member) for name, member in inputs.items()},
    )


def resolve_input(input_ref: str, profile: InputProfile | None) -> PreparedInput | InputRefusal:
    """Turn an add-on's input name into an approved file, or refuse it by rule.

    The order of the checks is the order the rules apply in, and containment is checked
    **before** existence: a member that escapes the root is refused for escaping, not for
    being absent, because the two need different operator action.
    """
    if profile is None:
        return InputRefusal(
            InputRefusalReason.SOURCE_HAS_NO_PROFILE,
            "this source has no approved input profile, so it reads nothing",
        )
    member = profile.inputs.get(input_ref)
    if member is None:
        return InputRefusal(
            InputRefusalReason.INPUT_NOT_DECLARED,
            f"input {input_ref!r} is not in this source's approved profile",
            {"input_ref": input_ref, "approved": sorted(profile.inputs)},
        )

    root = profile.root.resolve()
    if not root.is_dir():
        return InputRefusal(
            InputRefusalReason.ROOT_IS_NOT_A_DIRECTORY,
            "the approved input root is not a directory",
            {"input_ref": input_ref},
        )

    # `resolve()` follows symlinks and collapses `..`, so an absolute member, a dot
    # segment, and a symlink out of the tree all arrive here as the path they really
    # name. `is_relative_to` then compares resolved *parts*, not string prefixes —
    # `/data/beauty-private` is not inside `/data/beauty`. `ADVERSARIAL-REVIEW-2026-08-19.md`
    # F4 is what this sentence is paying for: the outbound guard compared strings and a
    # dot segment walked out of its approved path range.
    candidate = (root / member).resolve()
    if not candidate.is_relative_to(root):
        return InputRefusal(
            InputRefusalReason.MEMBER_ESCAPES_ROOT,
            f"input {input_ref!r} resolves outside the approved root",
            {"input_ref": input_ref},
        )
    if not candidate.exists():
        return InputRefusal(
            InputRefusalReason.INPUT_DOES_NOT_EXIST,
            f"input {input_ref!r} names a file that is not there",
            {"input_ref": input_ref},
        )
    if not candidate.is_file():
        return InputRefusal(
            InputRefusalReason.INPUT_IS_NOT_A_FILE,
            f"input {input_ref!r} is not a regular file",
            {"input_ref": input_ref},
        )
    return PreparedInput(input_ref=input_ref, path=candidate)


def open_stream(
    prepared: PreparedInput, max_bytes: int, chunk_size: int = 64 * 1024
) -> Iterator[bytes]:
    """Yield the input's bytes in chunks, refusing anything over `max_bytes`.

    The size is checked **before** the first chunk rather than counted while reading:
    the size is knowable here, and a bound that only fires partway through has already
    spent what it was meant to save.
    """
    size = prepared.path.stat().st_size
    if size > max_bytes:
        raise InputRefused(
            InputRefusal(
                InputRefusalReason.INPUT_TOO_LARGE,
                f"input {prepared.input_ref!r} is {size} bytes and the limit is {max_bytes}",
                {"input_ref": prepared.input_ref, "size": size, "limit": max_bytes},
            )
        )
    return _chunks(prepared.path, chunk_size)


def _chunks(path: Path, chunk_size: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                return
            yield chunk
