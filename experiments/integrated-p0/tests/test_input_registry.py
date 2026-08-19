"""DP-024 — an importer names an input and the operator's profile says what that is.

The property under test is the one that makes every other rule checkable: **the add-on
supplies a name, never a path.** Each case below is an attempt to turn a name into a read
the operator did not approve.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from domain.inputs import (
    InputProfile,
    InputRefusal,
    InputRefusalReason,
    PreparedInput,
    open_stream,
    read_input_profile,
    resolve_input,
)

MEGABYTE = 1024 * 1024


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    root = tmp_path / "datasets"
    (root / "2026-08").mkdir(parents=True)
    (root / "2026-08" / "posts.jsonl").write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")
    return root


@pytest.fixture
def profile(dataset: Path) -> InputProfile:
    return InputProfile(root=dataset, inputs={"rows": "2026-08/posts.jsonl"})


class TestAnApprovedNameResolves:
    def test_a_declared_name_becomes_the_file_the_operator_approved(
        self, profile: InputProfile, dataset: Path
    ) -> None:
        prepared = resolve_input("rows", profile)

        assert isinstance(prepared, PreparedInput)
        assert prepared.path == dataset / "2026-08" / "posts.jsonl"

    def test_the_stream_yields_the_bytes(self, profile: InputProfile) -> None:
        prepared = resolve_input("rows", profile)
        assert isinstance(prepared, PreparedInput)

        assert b"".join(open_stream(prepared, max_bytes=MEGABYTE)) == b'{"id": 1}\n{"id": 2}\n'


class TestANameNobodyApprovedIsRefused:
    def test_a_source_with_no_profile_is_refused(self) -> None:
        refusal = resolve_input("rows", None)

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.SOURCE_HAS_NO_PROFILE

    def test_a_name_the_profile_does_not_hold_is_refused(self, profile: InputProfile) -> None:
        refusal = resolve_input("secrets", profile)

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.INPUT_NOT_DECLARED

    def test_a_name_that_resolves_to_nothing_is_refused(self, dataset: Path) -> None:
        refusal = resolve_input("rows", InputProfile(dataset, {"rows": "2026-08/absent.jsonl"}))

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.INPUT_DOES_NOT_EXIST

    def test_a_name_that_resolves_to_a_directory_is_refused(self, dataset: Path) -> None:
        refusal = resolve_input("rows", InputProfile(dataset, {"rows": "2026-08"}))

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.INPUT_IS_NOT_A_FILE

    def test_a_root_that_is_not_a_directory_is_refused(self, dataset: Path) -> None:
        refusal = resolve_input(
            "rows", InputProfile(dataset / "2026-08" / "posts.jsonl", {"rows": "x"})
        )

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.ROOT_IS_NOT_A_DIRECTORY


class TestNothingEscapesTheRoot:
    """`[측정]` DP-024 D3. The outbound guard's equivalent was wrong once — F4 found the
    redirect path range bypassable by dot segments because it compared strings. These
    compare resolved paths."""

    def test_a_dot_segment_member_is_refused(self, dataset: Path, tmp_path: Path) -> None:
        (tmp_path / "outside.txt").write_text("not yours", encoding="utf-8")

        refusal = resolve_input("rows", InputProfile(dataset, {"rows": "../outside.txt"}))

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.MEMBER_ESCAPES_ROOT

    def test_an_absolute_member_is_refused(self, dataset: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("not yours", encoding="utf-8")

        refusal = resolve_input("rows", InputProfile(dataset, {"rows": str(outside)}))

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.MEMBER_ESCAPES_ROOT

    def test_a_symlink_pointing_outside_is_refused(self, dataset: Path, tmp_path: Path) -> None:
        """The one a string comparison cannot see: every segment looks contained."""
        outside = tmp_path / "outside.txt"
        outside.write_text("not yours", encoding="utf-8")
        (dataset / "looks-fine.jsonl").symlink_to(outside)

        refusal = resolve_input("rows", InputProfile(dataset, {"rows": "looks-fine.jsonl"}))

        assert isinstance(refusal, InputRefusal)
        assert refusal.reason is InputRefusalReason.MEMBER_ESCAPES_ROOT

    def test_a_symlink_staying_inside_is_allowed(self, dataset: Path) -> None:
        """The control. A rule that refused every symlink would pass the case above by
        refusing everything."""
        (dataset / "alias.jsonl").symlink_to(dataset / "2026-08" / "posts.jsonl")

        prepared = resolve_input("rows", InputProfile(dataset, {"rows": "alias.jsonl"}))

        assert isinstance(prepared, PreparedInput)


class TestReadingIsBounded:
    def test_a_file_over_the_limit_is_refused_before_it_is_read(self, dataset: Path) -> None:
        (dataset / "big.jsonl").write_bytes(b"x" * 4096)
        prepared = resolve_input("rows", InputProfile(dataset, {"rows": "big.jsonl"}))
        assert isinstance(prepared, PreparedInput)

        with pytest.raises(Exception) as raised:
            list(open_stream(prepared, max_bytes=1024))

        assert InputRefusalReason.INPUT_TOO_LARGE.value in str(raised.value)

    def test_a_file_at_the_limit_is_read(self, dataset: Path) -> None:
        (dataset / "exact.jsonl").write_bytes(b"x" * 1024)
        prepared = resolve_input("rows", InputProfile(dataset, {"rows": "exact.jsonl"}))
        assert isinstance(prepared, PreparedInput)

        assert len(b"".join(open_stream(prepared, max_bytes=1024))) == 1024


class TestTheStoredProfileIsRead:
    def test_a_stored_profile_becomes_one(self, tmp_path: Path) -> None:
        stored = {"root": str(tmp_path), "inputs": {"rows": "a.jsonl"}}

        profile = read_input_profile(stored)

        assert profile == InputProfile(root=tmp_path, inputs={"rows": "a.jsonl"})

    def test_no_stored_profile_is_no_profile(self) -> None:
        assert read_input_profile(None) is None
