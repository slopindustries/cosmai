"""The outbound policy, rule by rule.

`p0-security.md` §Outbound lists six obligations and DP-008 D4 puts every one of them on
the platform. Each has a test here that shows it **refusing**, and — where the assertion
is an absence — a positive control showing the same code path accepting. A rule that
never accepted anything would pass every refusal test while blocking all real work, and
a rule that never refused would pass nothing at all yet look identical in a summary line.

None of these open a socket. That is the point of separating policy from transport: a
security test that needs a server standing up is a security test that eventually gets
skipped.
"""

from __future__ import annotations

import pytest
from domain.outbound import (
    ALLOWED_SCHEMES,
    DEFAULT_LIMITS,
    OutboundProfile,
    PreparedRequest,
    Refusal,
    RefusalReason,
    check_redirect,
    check_resolved_addresses,
    resolve,
    strip_protected_headers,
)


def a_profile(**overrides: object) -> OutboundProfile:
    values: dict[str, object] = {
        "hosts": ("api.example.com",),
        "endpoints": {"items": "/v1/items", "reviews": "/v1/reviews"},
        "port": 443,
    }
    values.update(overrides)
    return OutboundProfile(**values)  # type: ignore[arg-type]


class TestEndpointResolution:
    def test_an_approved_endpoint_becomes_a_url_the_add_on_never_composed(self) -> None:
        """The whole of "임의 URL이 아니라 등록된 source_id를 선택한다".

        The add-on supplies `"items"`. There is no input to `resolve` that could have
        become an arbitrary URL, because the name must already be in the profile.
        """
        request = resolve("items", a_profile(), {"q": "kimchi"})
        assert isinstance(request, PreparedRequest)
        assert request.url == "https://api.example.com:443/v1/items?q=kimchi"
        assert request.host == "api.example.com"

    def test_an_undeclared_endpoint_is_refused_and_says_what_is_approved(self) -> None:
        refusal = resolve("secrets", a_profile())
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.ENDPOINT_NOT_DECLARED
        assert "items, reviews" in refusal.summary

    def test_a_url_offered_as_an_endpoint_name_is_just_an_unknown_name(self) -> None:
        """The attack this design forecloses rather than filters.

        A name is looked up in a mapping. `https://evil.test/` is not a key, so it is
        refused by the same rule that refuses a typo — there is no parsing step to slip
        past.
        """
        refusal = resolve("https://evil.test/steal", a_profile())
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.ENDPOINT_NOT_DECLARED

    def test_a_path_traversal_in_an_approved_path_cannot_leave_the_host(self) -> None:
        profile = a_profile(endpoints={"items": "/v1/../../etc/passwd"})
        request = resolve("items", profile)
        assert isinstance(request, PreparedRequest)
        assert request.url.startswith("https://api.example.com:443/")

    def test_a_source_with_no_profile_cannot_fetch_at_all(self) -> None:
        """A normalizer source is required to have none, so this is an ordinary state."""
        refusal = resolve("items", None)
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.SOURCE_HAS_NO_PROFILE

    def test_a_profile_approving_no_host_cannot_fetch(self) -> None:
        refusal = resolve("items", a_profile(hosts=()))
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.HOST_NOT_ALLOWED

    def test_only_https_is_ever_produced(self) -> None:
        """`p0-security.md` says HTTPS. There is no code path here that emits another."""
        assert frozenset({"https"}) == ALLOWED_SCHEMES
        request = resolve("items", a_profile())
        assert isinstance(request, PreparedRequest)
        assert request.url.startswith("https://")


class TestParameterAllowlist:
    def test_an_unapproved_parameter_is_refused_by_name(self) -> None:
        profile = a_profile(allowed_parameters=("q", "start"))
        refusal = resolve("items", profile, {"q": "a", "callback": "x"})
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.PARAMETER_NOT_ALLOWED
        assert "callback" in refusal.summary

    def test_the_refusal_names_the_parameter_but_never_quotes_its_value(self) -> None:
        """A query value is the part an add-on controls, so it is the part a log must not
        hold."""
        profile = a_profile(allowed_parameters=("q",))
        refusal = resolve("items", profile, {"leak": "s3cret-looking-value"})
        assert isinstance(refusal, Refusal)
        assert "s3cret-looking-value" not in refusal.summary
        assert "s3cret-looking-value" not in str(refusal.detail)

    def test_approved_parameters_pass(self) -> None:
        """The positive control: the allowlist accepts as well as refusing."""
        profile = a_profile(allowed_parameters=("q", "start"))
        request = resolve("items", profile, {"q": "a", "start": "1"})
        assert isinstance(request, PreparedRequest)

    def test_no_allowlist_means_no_parameter_check(self) -> None:
        request = resolve("items", a_profile(), {"anything": "goes"})
        assert isinstance(request, PreparedRequest)


class TestRedirectRevalidation:
    def test_a_redirect_within_policy_is_accepted(self) -> None:
        """The positive control for every refusal below."""
        result = check_redirect("https://api.example.com/v1/items?page=2", a_profile(), hops=1)
        assert isinstance(result, PreparedRequest)

    def test_a_redirect_to_another_host_is_refused(self) -> None:
        result = check_redirect("https://evil.test/v1/items", a_profile(), hops=1)
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.HOST_NOT_ALLOWED

    def test_a_redirect_downgrading_to_http_is_refused(self) -> None:
        result = check_redirect("http://api.example.com/v1/items", a_profile(), hops=1)
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.SCHEME_NOT_ALLOWED

    def test_a_redirect_to_another_port_is_refused(self) -> None:
        result = check_redirect("https://api.example.com:8443/v1/items", a_profile(), hops=1)
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.PORT_NOT_ALLOWED

    def test_a_redirect_out_of_the_approved_path_range_is_refused(self) -> None:
        result = check_redirect("https://api.example.com/admin/keys", a_profile(), hops=1)
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.PATH_NOT_ALLOWED

    def test_too_many_hops_is_refused_before_the_destination_is_considered(self) -> None:
        """Otherwise a chain of individually-legal hops has no end."""
        result = check_redirect("https://api.example.com/v1/items", a_profile(), hops=99)
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.TOO_MANY_REDIRECTS

    @pytest.mark.parametrize("location", ["/v1/items", "//evil.test/v1/items", ""])
    def test_a_relative_or_protocol_relative_redirect_is_refused(self, location: str) -> None:
        """`//evil.test/...` is the one worth naming: it looks relative and is not."""
        result = check_redirect(location, a_profile(), hops=1)
        assert isinstance(result, Refusal)


class TestResolvedAddressRange:
    def test_a_public_address_passes(self) -> None:
        """The positive control. Every assertion below is an absence without it."""
        assert check_resolved_addresses("api.example.com", ["93.184.216.34"], a_profile()) is None

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",       # loopback
            "10.0.0.5",        # private
            "192.168.1.1",     # private
            "172.16.0.1",      # private
            "169.254.169.254", # link-local — the cloud metadata endpoint
            "224.0.0.1",       # multicast
            "0.0.0.0",         # unspecified
            "::1",             # loopback, v6
            "fe80::1",         # link-local, v6
            "fc00::1",         # unique local, v6
        ],
    )
    def test_a_blocked_range_is_refused(self, address: str) -> None:
        refusal = check_resolved_addresses("api.example.com", [address], a_profile())
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.ADDRESS_RANGE_BLOCKED

    def test_every_address_must_pass_not_merely_the_first(self) -> None:
        """A name resolving to one public and one loopback address is refused.

        Taking the first — or any — would make the outcome depend on resolver ordering,
        which is not something a security rule may depend on.
        """
        refusal = check_resolved_addresses(
            "api.example.com", ["93.184.216.34", "127.0.0.1"], a_profile()
        )
        assert isinstance(refusal, Refusal)

    def test_something_that_is_not_an_address_is_refused_rather_than_raising(self) -> None:
        refusal = check_resolved_addresses("api.example.com", ["not-an-ip"], a_profile())
        assert isinstance(refusal, Refusal)


class TestLoopbackEscapeHatch:
    """The one deliberate hole, and the two tests that keep it from widening."""

    def test_the_flag_permits_loopback_for_a_local_stub(self) -> None:
        profile = a_profile(allow_loopback=True)
        assert check_resolved_addresses("localhost", ["127.0.0.1"], profile) is None

    def test_with_the_flag_off_the_same_address_is_actually_refused(self) -> None:
        """The positive control the flag exists to require.

        Without this, "no committed source sets the flag" would pass equally well against
        a rule that never checked anything.
        """
        refusal = check_resolved_addresses("localhost", ["127.0.0.1"], a_profile())
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.ADDRESS_RANGE_BLOCKED

    def test_the_flag_does_not_also_unlock_private_or_link_local(self) -> None:
        """It is loopback only. The metadata endpoint stays blocked either way."""
        profile = a_profile(allow_loopback=True)
        for address in ("10.0.0.5", "169.254.169.254", "192.168.1.1"):
            assert isinstance(
                check_resolved_addresses("host", [address], profile), Refusal
            ), address

    def test_the_flag_is_off_unless_a_profile_asks_for_it(self) -> None:
        assert a_profile().allow_loopback is False
        assert OutboundProfile.from_row({"hosts": ["h"], "endpoints": {}}) is not None
        row = OutboundProfile.from_row({"hosts": ["h"], "endpoints": {}})
        assert row is not None and row.allow_loopback is False


class TestProtectedHeaders:
    def test_credential_bearing_headers_are_removed(self) -> None:
        stripped = strip_protected_headers(
            {
                "Authorization": "Bearer s3cret",
                "X-NCP-APIGW-API-KEY": "s3cret",
                "Cookie": "session=s3cret",
                "Content-Type": "application/json",
            }
        )
        assert stripped == {"Content-Type": "application/json"}
        assert "s3cret" not in str(stripped)

    def test_matching_ignores_case(self) -> None:
        assert strip_protected_headers({"AUTHORIZATION": "x", "authorization": "y"}) == {}

    def test_ordinary_headers_survive(self) -> None:
        """The positive control: stripping everything would also pass the tests above."""
        headers = {"Content-Type": "application/json", "ETag": "abc", "Date": "now"}
        assert strip_protected_headers(headers) == headers


class TestProfileFromRow:
    def test_an_absent_profile_reads_as_none_rather_than_an_empty_one(self) -> None:
        """An empty profile would approve nothing and read as a misconfiguration; `None`
        says the source has none, which is what a normalizer source is required to be."""
        assert OutboundProfile.from_row(None) is None
        assert OutboundProfile.from_row({}) is None

    def test_unstated_limits_fall_back_to_the_documented_defaults(self) -> None:
        profile = OutboundProfile.from_row({"hosts": ["h"], "endpoints": {"a": "/a"}})
        assert profile is not None
        assert profile.limits["max_response_bytes"] == DEFAULT_LIMITS["max_response_bytes"]

    def test_a_stated_limit_overrides_only_itself(self) -> None:
        profile = OutboundProfile.from_row(
            {"hosts": ["h"], "endpoints": {"a": "/a"}, "limits": {"max_pages": 2}}
        )
        assert profile is not None
        assert profile.limits["max_pages"] == 2
        assert profile.limits["max_redirects"] == DEFAULT_LIMITS["max_redirects"]

    def test_a_malformed_endpoints_value_is_refused_at_read_time(self) -> None:
        with pytest.raises(ValueError, match="endpoints"):
            OutboundProfile.from_row({"hosts": ["h"], "endpoints": ["/a", "/b"]})
