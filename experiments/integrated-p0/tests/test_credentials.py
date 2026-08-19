"""Credential parts, their resolution, and their attachment — DP-018, resolving OQ-009.

Nothing in this repository attached a credential to anything before 2026-08-18. The first
real collector, `collector.naver.blog`, needs two header values and said so in its own
module docstring because the contract had no vocabulary for it.

Three properties are what these tests exist for, and each has its own class.

**A value never leaves the store except into one request.** `secret-setup.md` invariant 2:
the store is not spread into the process environment, so nothing a child process inherits
can carry a credential. Asserted by reading `os.environ` after a resolution.

**A credential header is a protected header, by construction.** DP-018 D3. `PROTECTED_HEADERS`
is what keeps a credential out of `raw_envelope.response_headers`; a profile free to name a
header outside that set could attach on the way out and record on the way back. The refusal
is tested, and so is the positive control that an approved header is accepted.

**A missing credential fails as configuration, never as an anonymous request.** `secret-setup.md`
invariant 4. The falsification target is a source answering an unauthenticated request with
`200` and an error body, which a collector would then store as Raw.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from domain.outbound import (
    PROTECTED_HEADERS,
    CredentialPart,
    OutboundProfile,
    credential_headers,
)
from domain.secrets import (
    CredentialNotResolved,
    SecretValue,
    resolve_credential,
    secret_store_path,
)

REF = "COSMA_SRC_PROBE_TOKEN"

VALUE = "the-actual-secret-42"


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A secret store outside the repository, at the permissions the launcher enforces."""
    path = tmp_path / "env"
    path.write_text(f"{REF}={VALUE}\n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv("COSMA_SECRET_SOURCE", str(path))
    return path


class TestResolvingOneRef:
    def test_a_declared_key_resolves_to_its_value(self, store: Path) -> None:
        assert resolve_credential(REF).reveal() == VALUE

    def test_the_value_is_not_in_the_process_environment(self, store: Path) -> None:
        """`secret-setup.md` invariant 2, asserted rather than asserted about.

        The store holds the value; the environment holds only the store's path. A child
        process — a frontend build, a subprocess in a traceback handler — inherits the
        second and never the first.
        """
        resolve_credential(REF)

        assert VALUE not in os.environ.values()
        assert REF not in os.environ

    def test_an_absent_key_is_a_configuration_failure_not_an_empty_value(
        self, store: Path
    ) -> None:
        with pytest.raises(CredentialNotResolved) as raised:
            resolve_credential("COSMA_SRC_PROBE_ABSENT")
        assert "COSMA_SRC_PROBE_ABSENT" in raised.value.summary

    def test_an_absent_store_is_a_configuration_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COSMA_SECRET_SOURCE", str(tmp_path / "nothing"))
        with pytest.raises(CredentialNotResolved):
            resolve_credential(REF)

    def test_an_unset_store_location_is_a_configuration_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Not a fallback to `os.environ`. A worker started without the launcher must
        fail, not quietly resolve credentials from wherever it can find them."""
        monkeypatch.delenv("COSMA_SECRET_SOURCE", raising=False)
        monkeypatch.setenv(REF, VALUE)

        with pytest.raises(CredentialNotResolved):
            resolve_credential(REF)

    def test_a_store_inside_the_repository_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """`scripts/with-secret-source.sh` checks this, and `secret-setup.md` records that
        the check reaches no execution path that skips the launcher. This is that path."""
        inside = Path(__file__).resolve().parents[3] / "var" / "leaked-env"
        inside.parent.mkdir(parents=True, exist_ok=True)
        inside.write_text(f"{REF}={VALUE}\n", encoding="utf-8")
        inside.chmod(0o600)
        monkeypatch.setenv("COSMA_SECRET_SOURCE", str(inside))
        try:
            with pytest.raises(CredentialNotResolved) as raised:
                resolve_credential(REF)
            assert "working tree" in raised.value.summary
        finally:
            inside.unlink()

    def test_a_world_readable_store_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "loose"
        path.write_text(f"{REF}={VALUE}\n", encoding="utf-8")
        path.chmod(0o644)
        monkeypatch.setenv("COSMA_SECRET_SOURCE", str(path))

        with pytest.raises(CredentialNotResolved):
            resolve_credential(REF)


class TestTheValueResistsBeingPrinted:
    """The remaining leak paths `secret-setup.md` names are traceback and string formatting.

    A `str`/`repr` that reports nothing is not secrecy — `reveal()` is one call away — it is
    the difference between a value that leaks when someone is careless and one that leaks
    only when someone means it.
    """

    def test_repr_and_str_withhold_the_value(self) -> None:
        secret = SecretValue(VALUE)
        assert VALUE not in repr(secret)
        assert VALUE not in str(secret)
        assert VALUE not in f"{secret}"

    def test_it_does_not_survive_an_exception_message(self) -> None:
        secret = SecretValue(VALUE)
        try:
            raise RuntimeError(f"failed with {secret}")
        except RuntimeError as error:
            assert VALUE not in str(error)

    def test_reveal_returns_it_because_something_has_to(self) -> None:
        """The positive control. A wrapper that withheld the value from everyone would
        pass every assertion above and attach nothing to any request."""
        assert SecretValue(VALUE).reveal() == VALUE


class TestOnlyAProtectedHeaderMayCarryACredential:
    """DP-018 D3."""

    def test_a_profile_naming_an_unprotected_header_is_refused_at_read_time(self) -> None:
        with pytest.raises(ValueError, match="protected"):
            OutboundProfile.from_row(
                {
                    "hosts": ["api.example.com"],
                    "endpoints": {"items": "/v1/items"},
                    "credentials": [{"header": "X-Debug-Token", "ref": REF}],
                }
            )

    def test_a_profile_naming_a_protected_header_is_read(self) -> None:
        """The positive control for the refusal above."""
        profile = OutboundProfile.from_row(
            {
                "hosts": ["api.example.com"],
                "endpoints": {"items": "/v1/items"},
                "credentials": [{"header": "X-NCP-APIGW-API-KEY", "ref": REF}],
            }
        )
        assert profile is not None
        assert profile.credentials == (CredentialPart("X-NCP-APIGW-API-KEY", REF),)

    def test_every_naver_header_the_add_on_needs_is_protected(self) -> None:
        """The two names `collector.naver.blog` documents, checked against the list that
        strips them out of Raw. If these ever diverge, a real credential is recorded."""
        assert "x-ncp-apigw-api-key" in PROTECTED_HEADERS
        assert "x-ncp-apigw-api-key-id" in PROTECTED_HEADERS

    def test_a_ref_that_is_not_a_key_name_is_refused(self) -> None:
        """The `source_credential_ref_is_a_key_name` constraint exists on the column and
        not on this array. Same rule, stated where the array is read."""
        with pytest.raises(ValueError, match="key name"):
            OutboundProfile.from_row(
                {
                    "hosts": ["api.example.com"],
                    "endpoints": {"items": "/v1/items"},
                    "credentials": [{"header": "Authorization", "ref": "sk-live-actual"}],
                }
            )


class TestBuildingTheHeadersForARequest:
    def test_each_part_becomes_its_header(self, store: Path) -> None:
        profile = OutboundProfile(
            hosts=("api.example.com",),
            endpoints={"items": "/v1/items"},
            credentials=(CredentialPart("Authorization", REF),),
        )
        assert credential_headers(profile) == {"Authorization": VALUE}

    def test_a_profile_with_no_credential_needs_no_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Most sources have none, and they must not be made to depend on a store."""
        monkeypatch.delenv("COSMA_SECRET_SOURCE", raising=False)
        profile = OutboundProfile(hosts=("api.example.com",), endpoints={"items": "/v1/items"})

        assert credential_headers(profile) == {}

    def test_an_unresolvable_part_raises_rather_than_sending_an_anonymous_request(
        self, store: Path
    ) -> None:
        """`secret-setup.md` invariant 4, and the reason it exists: a source may answer an
        unauthenticated request with `200` and an error body, which a collector would then
        store as Raw and a normalizer would then read as data."""
        profile = OutboundProfile(
            hosts=("api.example.com",),
            endpoints={"items": "/v1/items"},
            credentials=(CredentialPart("Authorization", "COSMA_SRC_PROBE_MISSING"),),
        )
        with pytest.raises(CredentialNotResolved):
            credential_headers(profile)


class TestTheStorePathItself:
    def test_it_comes_from_the_launcher_variable(
        self, store: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert secret_store_path() == store

    def test_the_parser_ignores_comments_and_blank_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`config/env.example` is written in this shape, and an operator copying from it
        will bring the comments along."""
        path = tmp_path / "env"
        path.write_text(f"# a comment\n\n{REF}={VALUE}\n", encoding="utf-8")
        path.chmod(0o600)
        monkeypatch.setenv("COSMA_SECRET_SOURCE", str(path))

        assert resolve_credential(REF).reveal() == VALUE

    def test_a_value_containing_an_equals_sign_survives(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Base64 and connection strings both carry them, and splitting on every `=`
        would truncate a credential into something that fails authentication obscurely."""
        path = tmp_path / "env"
        path.write_text(f"{REF}=abc==def\n", encoding="utf-8")
        path.chmod(0o600)
        monkeypatch.setenv("COSMA_SECRET_SOURCE", str(path))

        assert resolve_credential(REF).reveal() == "abc==def"
