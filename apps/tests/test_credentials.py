"""Credential parts and their attachment — DP-018, resolving OQ-009.

Copy-adapted from `experiments/integrated-p0/tests/test_credentials.py` (M2 batch 2c),
narrowed to what is genuinely `domain.outbound`'s: DP-018 D3's protected-header refusal
and `credential_headers`' attachment/resolution-failure behavior. P0's file also carried
`TestResolvingOneRef`, `TestTheValueResistsBeingPrinted`, and `TestTheStorePathItself` —
`platform_core.secrets` mechanics (the store-location guard, `SecretValue`'s withheld
`repr`, comment/blank-line parsing, an `=`-bearing value surviving) that this tree's own
`apps/tests/test_secrets.py` already covers against the identical, DP-032-centralized
`resolve_credential`. Re-adapting them here would duplicate that coverage rather than add
to it, so only the two classes below — which need `domain.outbound.OutboundProfile`/
`CredentialPart`/`credential_headers`, not the store itself — are carried over.

**A credential header is a protected header, by construction.** DP-018 D3.
`PROTECTED_HEADERS` is what keeps a credential out of `raw_envelope.response_headers`; a
profile free to name a header outside that set could attach on the way out and record on
the way back. The refusal is tested, and so is the positive control that an approved
header is accepted.

**A missing credential fails as configuration, never as an anonymous request.**
`secret-setup.md` invariant 4. The falsification target is a source answering an
unauthenticated request with `200` and an error body, which a collector would then store
as Raw.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.outbound import (
    PROTECTED_HEADERS,
    CredentialPart,
    OutboundProfile,
    credential_headers,
)
from platform_core.secrets import CredentialNotResolved

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

    def test_the_tubedepth_header_is_protected(self) -> None:
        """M-S2 (REVIEW-M2-M7.md): `x-api-key` was added to `PROTECTED_HEADERS` for
        `collector.tubedepth.rest` but never asserted anywhere — `[측정]` deleting the
        line left 169 tests identical to baseline. This is that assertion, the same
        convention `test_every_naver_header_the_add_on_needs_is_protected` establishes
        for the NAVER headers."""
        assert "x-api-key" in PROTECTED_HEADERS

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
