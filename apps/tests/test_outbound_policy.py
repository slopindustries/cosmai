"""The outbound policy, rule by rule.

Copy-adapted from ``experiments/integrated-p0/tests/test_outbound_policy.py`` (M2 batch
2c), verbatim. No fixture, no database, and no P0-specific import: every case here is a
pure function of a URL, a profile, and (for the address rule) a list of strings, so
nothing about this tree's fixture names or schema qualification applies.

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

    def test_a_path_traversal_in_an_approved_path_is_refused_rather_than_sent(self) -> None:
        """`[결정]` Tightened on 2026-08-18 while repairing F4, and the previous property is
        kept below rather than dropped.

        This used to assert only that such a path *cannot leave the host* — the request was
        prepared and sent, on the reasoning that where it lands is the operator's business
        as long as it lands on an approved host. F4 makes that reasoning insufficient in one
        direction that matters: a path carrying a dot segment has no decidable range, so
        `check_redirect` cannot say what a redirect from it may reach. Refusing at `resolve`
        puts the failure on the first fetch, where an operator can read it, rather than on a
        redirect nobody would think to look at.
        """
        profile = a_profile(endpoints={"items": "/v1/../../etc/passwd"})
        refusal = resolve("items", profile)
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.PATH_NOT_ALLOWED

    def test_an_ordinary_approved_path_still_resolves_against_the_approved_host(self) -> None:
        """The property the case above used to carry, kept as its own assertion so that
        tightening one rule did not quietly retire the other."""
        request = resolve("items", a_profile())
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


class TestTheApprovedPathRangeIsComparedBySegment:
    """`ADVERSARIAL-REVIEW-2026-08-18.md` F4.

    `check_redirect`'s docstring says *"same policy means the same function decides — a
    second, looser check written for redirects would be the hole."* The function was the
    same and the comparison was not: `parts.path.startswith(p)` on the raw, un-normalized
    path, against a transport that sends the URL verbatim. `[측정]` The reviewer carried
    `/v1/items/../../admin/keys` end to end over TLS against a stub that normalizes its
    request target the way RFC 3986 §5.2.4 requires — as nginx and Apache do — and reached
    a body it had written as `{"secret": "THIS-PATH-WAS-NEVER-APPROVED"}`.

    Two defects, one comparison. Dot segments mean the path the far end resolves is not
    the path this function read; a string prefix means `/v1/items2` is inside the range
    granted to `/v1/items`. Both are fixed by comparing *segments* of a path that is
    refused outright if it cannot be compared.
    """

    @pytest.mark.parametrize(
        "location",
        [
            "https://api.example.com/v1/items/../../admin/keys",
            "https://api.example.com/v1/items/../../../admin/keys",
            "https://api.example.com/v1/./items/../admin/keys",
            # The same escape spelled so a naive `..` scan misses it. The far end decodes
            # before it normalizes, so this is the same request as the first one.
            "https://api.example.com/v1/items/%2e%2e/%2e%2e/admin/keys",
            "https://api.example.com/v1/items/%2E%2E/admin/keys",
        ],
    )
    def test_a_dot_segment_cannot_walk_out_of_the_approved_range(self, location: str) -> None:
        result = check_redirect(location, a_profile(), hops=1)
        assert isinstance(result, Refusal), location
        assert result.reason is RefusalReason.PATH_NOT_ALLOWED

    @pytest.mark.parametrize(
        "location",
        [
            "https://api.example.com/v1/items2/secret",
            "https://api.example.com/v1/itemsomething",
            "https://api.example.com/v1/reviewsX",
        ],
    )
    def test_a_sibling_whose_name_merely_starts_with_an_approved_one_is_refused(
        self, location: str
    ) -> None:
        """The prefix half. `/v1/items2` is not under `/v1/items`; it is beside it."""
        result = check_redirect(location, a_profile(), hops=1)
        assert isinstance(result, Refusal), location
        assert result.reason is RefusalReason.PATH_NOT_ALLOWED

    @pytest.mark.parametrize(
        "location",
        [
            "https://api.example.com/v1/items",
            "https://api.example.com/v1/items/3",
            "https://api.example.com/v1/items/3/reviews",
            "https://api.example.com/v1/items?page=2",
            "https://api.example.com/v1/items/",
        ],
    )
    def test_what_is_genuinely_inside_the_range_is_still_accepted(self, location: str) -> None:
        """The positive control. A comparison that refused everything would pass both
        assertions above, and a redirect to a sub-resource is ordinary server behaviour."""
        result = check_redirect(location, a_profile(), hops=1)
        assert isinstance(result, PreparedRequest), location

    def test_an_encoded_separator_is_refused_rather_than_guessed_at(self) -> None:
        """`%2f` is a separator to some servers and a literal to others, so what the far
        end will resolve is not knowable here. Refused rather than decided."""
        result = check_redirect(
            "https://api.example.com/v1/items%2f..%2fadmin/keys", a_profile(), hops=1
        )
        assert isinstance(result, Refusal)
        assert result.reason is RefusalReason.PATH_NOT_ALLOWED

    def test_an_approved_path_that_cannot_be_compared_refuses_at_resolve_time(self) -> None:
        """A source whose own approved path carries a dot segment would otherwise fail only
        on a redirect, which is the one place nobody would look. It fails on the first
        fetch instead, where an operator can act on it."""
        profile = a_profile(endpoints={"items": "/v1/../admin/keys"})
        assert isinstance(resolve("items", profile), Refusal)

    def test_a_stored_path_that_is_not_absolute_is_refused(self) -> None:
        """`[측정]` `ADVERSARIAL-REVIEW-2026-08-18.md` F6: removing this check was **GREEN**,
        and still was when re-measured on 2026-08-19.

        A relative stored path would be joined against whatever the URL builder assumed,
        so the request would go somewhere the operator did not write down — the one thing
        the profile exists to prevent. Refused at `resolve`, before any socket."""
        profile = a_profile(endpoints={"items": "v1/items"})

        refusal = resolve("items", profile)

        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.PATH_NOT_ALLOWED
        assert "not absolute" in refusal.summary

    def test_the_same_path_with_a_leading_slash_resolves(self) -> None:
        """The control. A rule refusing every path would pass the case above."""
        profile = a_profile(endpoints={"items": "/v1/items"})

        assert not isinstance(resolve("items", profile), Refusal)


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

    def test_the_reserved_clause_is_subsumed_by_the_private_one(self) -> None:
        """`[측정]` `ADVERSARIAL-REVIEW-2026-08-18.md` F6: removing `address.is_reserved`
        from the range check is **GREEN**, and re-measured on 2026-08-19 it still is.

        `[확인 사실]` The reason is not a missing test. In Python's `ipaddress`, **every**
        address for which `is_reserved` holds also has `is_private` — `240.0.0.0/4`,
        `255.255.255.254`, and `100::/64` all report both. There is no address the reserved
        clause alone refuses, so no test can distinguish a tree with it from one without.

        `[결정]` The clause stays and this test states why it cannot be exercised, rather
        than a case being invented that appears to exercise it. If `ipaddress` ever narrows
        `is_private`, this test fails and the clause becomes load-bearing — which is the
        moment a real case for it exists.
        """
        import ipaddress

        for candidate in ("240.0.0.1", "255.255.255.254", "100::1"):
            address = ipaddress.ip_address(candidate)
            assert address.is_reserved, candidate
            assert address.is_private, (
                f"{candidate} is reserved and no longer private: the `is_reserved` clause "
                "now refuses something nothing else does, and needs a case of its own"
            )

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

    def test_the_documented_defaults_are_these_numbers(self) -> None:
        """`ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B3.

        `[측정]` All eight values were unpinned: `read_timeout_s` 30s → 3600s,
        `max_response_bytes` 8 MiB → 8 GiB, `max_pages` 20 → 10⁹ — every one **GREEN**. The
        test that carried the word "defaults" in its name is directly below and compares the
        value against itself, which proves the fallback *mechanism* and pins no number.

        `DEFAULT_LIMITS`' own docstring says *"Small on purpose: a source that needs more says
        so, and an unstated limit that happens to be generous is how a bound stops bounding
        anything."* These are the numbers that sentence is about, and one of them —
        `max_request_seconds` — is `ADVERSARIAL-REVIEW-2026-08-18.md` F5's repair for a
        38-day occupancy. Written as literals for the reason `CONTRACT_REDACTED_KEYS` is:
        a test derived from the constant it pins cannot notice the constant changing.

        Changing a number here is meant to be a deliberate act with a reason, so this
        asserts the whole mapping rather than a subset — an added key is a new bound nobody
        reviewed.
        """
        assert DEFAULT_LIMITS == {
            "connect_timeout_s": 5.0,
            "read_timeout_s": 30.0,
            "max_response_bytes": 8 * 1024 * 1024,
            "max_redirects": 3,
            "max_pages": 20,
            "max_records": 5000,
        "max_input_bytes": 64 * 1024 * 1024,
            "max_request_seconds": 60.0,
            "max_request_bytes": 64 * 1024,
        }

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


class TestMethodAndBody:
    """DP-020. Two of the three selected Naver endpoints are `POST` with a JSON body, and
    until 2026-08-18 `resolve` built a query string and `transport` sent `"GET"`, hardcoded.

    The split the packet argues for is asserted here rather than described: the **method**
    comes from the operator-approved profile and an add-on cannot choose it, while the
    **body** comes from the add-on exactly as `params` always has.
    """

    def a_post_profile(self, **overrides: object) -> OutboundProfile:
        values: dict[str, object] = {
            "hosts": ("naverapihub.apigw.ntruss.com",),
            "endpoints": {
                "trend": {"path": "/search-trend/v1/search", "method": "POST"},
                "blog": "/search/v1/blog",
            },
        }
        values.update(overrides)
        return OutboundProfile(**values)  # type: ignore[arg-type]

    def test_a_string_endpoint_is_still_a_get(self) -> None:
        """Every profile written before DP-020 keeps working, and says so here."""
        request = resolve("blog", self.a_post_profile(), {"query": "x"})
        assert isinstance(request, PreparedRequest)
        assert request.method == "GET"
        assert request.body is None

    def test_a_declared_post_endpoint_carries_its_body(self) -> None:
        request = resolve("trend", self.a_post_profile(), body=b'{"startDate":"2026-01-01"}')
        assert isinstance(request, PreparedRequest)
        assert request.method == "POST"
        assert request.body == b'{"startDate":"2026-01-01"}'

    def test_the_url_of_a_post_carries_no_query_string(self) -> None:
        """The body is the question, so nothing needs to be in the URL as well. Two places
        for one fact is two places that can disagree."""
        request = resolve("trend", self.a_post_profile(), body=b"{}")
        assert isinstance(request, PreparedRequest)
        assert "?" not in request.url

    def test_a_body_on_a_get_endpoint_is_refused(self) -> None:
        """DP-020 D4. A `GET` with a body is legal HTTP that many servers ignore, which
        makes it a request the operator approved and the add-on did not get."""
        refusal = resolve("blog", self.a_post_profile(), body=b"{}")
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.METHOD_NOT_ALLOWED

    def test_a_post_endpoint_with_no_body_is_refused(self) -> None:
        refusal = resolve("trend", self.a_post_profile())
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.METHOD_NOT_ALLOWED

    def test_a_method_the_platform_does_not_grant_is_refused_by_name(self) -> None:
        """`PUT`, `PATCH`, `DELETE`: a write to a source is a safety question
        `p0-security.md` has not been asked."""
        profile = self.a_post_profile(
            endpoints={"wipe": {"path": "/v1/things", "method": "DELETE"}}
        )
        refusal = resolve("wipe", profile, body=b"{}")
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.METHOD_NOT_ALLOWED

    def test_an_oversized_body_is_refused_before_anything_is_sent(self) -> None:
        """DP-020 D3, and `ADVERSARIAL-REVIEW-2026-08-18.md` F1's lesson applied at the
        moment the limit is written rather than after someone measures that it is not
        enforced."""
        profile = self.a_post_profile(limits={**DEFAULT_LIMITS, "max_request_bytes": 16})
        refusal = resolve("trend", profile, body=b"x" * 17)
        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.REQUEST_TOO_LARGE

    def test_a_body_inside_the_limit_is_not_refused(self) -> None:
        """The control. A check that refused every body would pass the case above."""
        profile = self.a_post_profile(limits={**DEFAULT_LIMITS, "max_request_bytes": 16})
        assert isinstance(resolve("trend", profile, body=b"x" * 16), PreparedRequest)

    def test_the_add_on_cannot_reach_a_second_host_through_the_body(self) -> None:
        """The property DP-008 D4 actually protects, restated for bodies: whatever the body
        says, the destination is still the profile's."""
        request = resolve(
            "trend", self.a_post_profile(), body=b'{"url":"https://evil.test/steal"}'
        )
        assert isinstance(request, PreparedRequest)
        assert request.host == "naverapihub.apigw.ntruss.com"
        assert request.url.startswith("https://naverapihub.apigw.ntruss.com:443/search-trend/")

    def test_a_malformed_endpoint_object_is_refused_at_read_time(self) -> None:
        with pytest.raises(ValueError, match="method"):
            OutboundProfile.from_row(
                {
                    "hosts": ["api.example.com"],
                    "endpoints": {"x": {"path": "/v1/x", "method": "TRACE"}},
                }
            )

    def test_a_profile_row_reads_both_endpoint_shapes(self) -> None:
        profile = OutboundProfile.from_row(
            {
                "hosts": ["api.example.com"],
                "endpoints": {
                    "get": "/v1/get",
                    "post": {"path": "/v1/post", "method": "POST"},
                },
            }
        )
        assert profile is not None
        assert profile.method_of("get") == "GET"
        assert profile.method_of("post") == "POST"

    def test_a_redirect_is_still_checked_against_the_approved_paths(self) -> None:
        """The path range has to keep working now that a path can arrive inside an object."""
        result = check_redirect(
            "https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            self.a_post_profile(),
            hops=1,
        )
        assert isinstance(result, PreparedRequest)


class TestTheBodyBoundCountsBytes:
    """`ADVERSARIAL-REVIEW-2026-08-19.md` F1.

    DP-020 D3 says a body is bounded and the bound is the platform's, and it cites the
    2026-08-18 review's F1 by name — *"a limit that exists in a contract and in no counter
    is not a limit"* — as the reason the counter was written with the decision.

    `[측정]` The counter was written and it counted the wrong quantity. `len(body)` is a byte
    count only when `body` is exactly `bytes`; `http.client` accepts any bytes-like and any
    iterable of bytes, streaming the latter chunked. The independent reviewer sent **1 MiB
    through a 64 KiB grant** as a one-element `list[bytes]`, and the author reproduced it at
    1,562× with a 64-byte grant.

    So the bound is now on the payload, and the type is checked rather than trusted: the
    contract says `bytes`, mypy enforces it for a cleanly-typed add-on, and this is what
    happens when something reaches here anyway.
    """

    def a_post_profile(self, limit: int) -> OutboundProfile:
        read = OutboundProfile.from_row(
            {
                "hosts": ["api.example.com"],
                "endpoints": {"trend": {"path": "/v1/trend", "method": "POST"}},
                "limits": {**DEFAULT_LIMITS, "max_request_bytes": limit},
            }
        )
        assert read is not None
        return read

    def test_a_list_of_chunks_is_measured_by_its_bytes(self) -> None:
        """The reviewer's exact attack. One element, a megabyte of payload."""
        refusal = resolve("trend", self.a_post_profile(64), body=[b"A" * 100_000])  # type: ignore[arg-type]

        assert isinstance(refusal, Refusal)
        assert refusal.reason is RefusalReason.REQUEST_TOO_LARGE

    def test_the_refusal_reports_the_real_size_not_the_element_count(self) -> None:
        """A refusal that said "1 bytes against a grant of 64" would be the same defect
        wearing a refusal's clothes."""
        refusal = resolve("trend", self.a_post_profile(64), body=[b"A" * 100_000])  # type: ignore[arg-type]

        assert isinstance(refusal, Refusal)
        assert refusal.detail["size"] == 100_000

    @pytest.mark.parametrize(
        "body",
        [
            bytearray(b"A" * 100_000),
            memoryview(b"A" * 100_000),
            [b"A" * 50_000, b"B" * 50_000],
            (b"A" * 100_000,),
            iter([b"A" * 100_000]),
        ],
        ids=["bytearray", "memoryview", "list", "tuple", "iterator"],
    )
    def test_every_bytes_like_body_http_client_would_accept_is_measured(
        self, body: object
    ) -> None:
        """`http.client` sends all of these. Each was a way past the old counter."""
        outcome = resolve("trend", self.a_post_profile(64), body=body)  # type: ignore[arg-type]

        assert isinstance(outcome, Refusal), f"{type(body).__name__} was not measured"
        assert outcome.reason is RefusalReason.REQUEST_TOO_LARGE

    def test_a_body_the_platform_cannot_measure_is_refused_rather_than_sent(self) -> None:
        """An arbitrary object is not a body this guard can size, and DP-020 D3 is a bound
        the platform keeps rather than one it hopes about. Refused by the same rule."""
        outcome = resolve("trend", self.a_post_profile(64), body=object())  # type: ignore[arg-type]

        assert isinstance(outcome, Refusal)
        assert outcome.reason is RefusalReason.REQUEST_TOO_LARGE

    def test_a_bytes_body_inside_the_limit_is_still_accepted(self) -> None:
        """The positive control. A guard that refused every body would pass all of the
        above and make the endpoint unusable."""
        assert isinstance(
            resolve("trend", self.a_post_profile(64), body=b"A" * 64), PreparedRequest
        )

    def test_a_bytes_like_body_inside_the_limit_is_accepted_too(self) -> None:
        """The second control, and the one that matters: measuring correctly must not mean
        refusing every shape. A `bytearray` under the grant is a legitimate body."""
        outcome = resolve("trend", self.a_post_profile(64), body=bytearray(b"A" * 64))  # type: ignore[arg-type]

        assert isinstance(outcome, PreparedRequest)

    def test_what_reaches_the_transport_is_bytes_whatever_arrived(self) -> None:
        """Normalising at the boundary is what makes the measurement and the payload the
        same thing downstream — `_hop` writes `request.body` and nothing re-measures it."""
        outcome = resolve("trend", self.a_post_profile(4096), body=bytearray(b"AB"))  # type: ignore[arg-type]

        assert isinstance(outcome, PreparedRequest)
        assert outcome.body == b"AB"
        assert isinstance(outcome.body, bytes)


class TestAnEndpointWithoutAPathCannotWidenTheRange:
    """The F4 class again, through the door DP-020 opened.

    `_read_endpoints` defaults a mapping-form endpoint's missing `path` to `""`.
    `comparable_segments("")` returned `()` rather than `None`, so it was not skipped the
    way an uncomparable path is — and `candidate[:0] == ()` is true for every path. One
    endpoint declared as `{"method": "POST"}` therefore granted the **whole host** as the
    redirect range for every other endpoint, with the source's credential headers still
    attached.

    `[측정]` Reproduced before the repair, with a control: against a profile carrying
    `{"post": {"method": "POST"}, "items": "/v1/items"}`, `check_redirect` accepted
    `https://api.example.com/admin/keys`; against the same profile without the pathless
    endpoint it refused it.

    Two tests, because the two halves fail differently. The first stops the row being
    written. The second is what holds if one is written anyway — the guard's own rule that
    "a defect in one endpoint cannot widen the range the others grant".
    """

    def test_a_mapping_endpoint_without_a_path_is_refused_when_the_row_is_read(self) -> None:
        with pytest.raises(ValueError, match="path"):
            OutboundProfile.from_row(
                {
                    "hosts": ["api.example.com"],
                    "endpoints": {"post": {"method": "POST"}, "items": "/v1/items"},
                }
            )

    def test_an_empty_approved_path_grants_nothing_rather_than_everything(self) -> None:
        widened = a_profile(
            endpoints={"post": {"path": "", "method": "POST"}, "items": "/v1/items"}
        )
        result = check_redirect("https://api.example.com/admin/keys", widened, hops=1)
        assert isinstance(result, Refusal), result
        assert result.reason is RefusalReason.PATH_NOT_ALLOWED

    def test_the_control_the_range_still_grants_what_it_approved(self) -> None:
        """Without this, a guard that refused every redirect would pass the case above."""
        widened = a_profile(
            endpoints={"post": {"path": "", "method": "POST"}, "items": "/v1/items"}
        )
        result = check_redirect("https://api.example.com/v1/items/42", widened, hops=1)
        assert isinstance(result, PreparedRequest), result
