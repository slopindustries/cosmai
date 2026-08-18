"""The outbound policy. Every obligation in `p0-security.md` §Outbound lives here.

`[결정]` DP-008 D4 puts all of them on the platform rather than on the add-on, and this
module is what "on the platform" means. An add-on names an endpoint; everything between
that name and a response is decided here.

**Policy is separated from transport on purpose.** `resolve` takes an endpoint name, a
source's approved profile, and parameters, and returns either a `PreparedRequest` or a
`Refusal` — without opening a socket, resolving a name, or reading a clock. Three things
follow:

* Every refusal is testable without a network. A test that must stand up a server to
  learn whether a host is allowed will eventually be skipped, and a security control
  nobody runs is not a control.
* The reason for a refusal is a value, not a log line, so an operator can be shown which
  rule refused rather than that something failed.
* The transport half stays small enough to read, which matters because it is the half
  that can leak.

The one place policy cannot be pure is DNS: whether a hostname resolves inside a blocked
range is only knowable by asking. `check_resolved_addresses` therefore takes the
addresses as an argument rather than looking them up, so the rule is testable and the
lookup is the caller's.

**Loopback and the test stub.** The address rule blocks loopback, which is also where a
local stub server lives, so a source profile may carry `allow_loopback`. It is a real
hole and it is guarded two ways: a test asserts no committed source sets it, and a
second asserts that with the flag off a loopback address is actually refused. The second
is not optional — an absence assertion with no positive control passes just as well
against a rule that checks nothing.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final
from urllib.parse import quote, urlencode, urlsplit

__all__ = [
    "DEFAULT_LIMITS",
    "OutboundProfile",
    "PreparedRequest",
    "Refusal",
    "RefusalReason",
    "check_resolved_addresses",
    "resolve",
    "strip_protected_headers",
]


class RefusalReason(StrEnum):
    """Why a request was refused, as a value an operator surface can render.

    One member per rule in `p0-security.md` §Outbound, so that "which rule refused this"
    has an answer rather than a stack trace.
    """

    SOURCE_HAS_NO_PROFILE = "SOURCE_HAS_NO_PROFILE"
    ENDPOINT_NOT_DECLARED = "ENDPOINT_NOT_DECLARED"
    SCHEME_NOT_ALLOWED = "SCHEME_NOT_ALLOWED"
    HOST_NOT_ALLOWED = "HOST_NOT_ALLOWED"
    PORT_NOT_ALLOWED = "PORT_NOT_ALLOWED"
    PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
    ADDRESS_RANGE_BLOCKED = "ADDRESS_RANGE_BLOCKED"
    TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    PARAMETER_NOT_ALLOWED = "PARAMETER_NOT_ALLOWED"


@dataclass(frozen=True)
class Refusal:
    """A refused request. Carries the rule and enough detail to act on it.

    `summary` is written for an operator, and deliberately never quotes a parameter
    value: a query string is the one part of a request an add-on controls, so it is the
    one part that could carry something a log should not hold.
    """

    reason: RefusalReason
    summary: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedRequest:
    """A request the policy has approved. Not yet sent.

    `host` is kept beside the URL so the caller can resolve exactly the name the policy
    approved. Re-parsing the URL to find it would leave room for the two to disagree.
    """

    url: str
    host: str
    port: int
    endpoint_ref: str


#: `p0-security.md` requires per-source limits; these are the values used when a profile
#: states none. Small on purpose: a source that needs more says so, and an unstated limit
#: that happens to be generous is how a bound stops bounding anything.
DEFAULT_LIMITS: Final[Mapping[str, Any]] = {
    "connect_timeout_s": 5.0,
    "read_timeout_s": 30.0,
    "max_response_bytes": 8 * 1024 * 1024,
    "max_redirects": 3,
    "max_pages": 20,
    "max_records": 5000,
}

#: Stripped from anything recorded. `p0-security.md` names the first two; the rest are
#: the shapes a provider credential takes in practice. Matched case-insensitively.
PROTECTED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-api-key",
        "x-ncp-apigw-api-key",
        "x-ncp-apigw-api-key-id",
    }
)

#: Only HTTPS. `p0-security.md` says "허용 HTTPS scheme"; http is not a narrower case of
#: that, it is a different one, and permitting it would make every other rule here
#: conditional on a transport nobody chose.
ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"https"})


@dataclass(frozen=True)
class OutboundProfile:
    """A source's approved outbound policy, as the `source` row stores it.

    Built from the operator-approved row and never from the add-on's manifest. The
    manifest's `[declares]` block is a request; this is the grant (DP-008 D4).
    """

    hosts: tuple[str, ...]
    endpoints: Mapping[str, str]
    port: int = 443
    limits: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    allowed_parameters: tuple[str, ...] | None = None
    allow_loopback: bool = False

    @classmethod
    def from_row(cls, profile: Mapping[str, Any] | None) -> OutboundProfile | None:
        """Read a `source.outbound_profile` jsonb value, or `None` if the source has none.

        A source with no profile is not an error here — a normalizer source is required
        to have none — but it cannot fetch, and `resolve` says so by name.
        """
        if not profile:
            return None
        endpoints = profile.get("endpoints") or {}
        if not isinstance(endpoints, Mapping):
            raise ValueError("outbound_profile.endpoints must be an object of name -> path")
        limits = dict(DEFAULT_LIMITS)
        limits.update(profile.get("limits") or {})
        allowed = profile.get("allowed_parameters")
        return cls(
            hosts=tuple(profile.get("hosts") or ()),
            endpoints={str(k): str(v) for k, v in endpoints.items()},
            port=int(profile.get("port", 443)),
            limits=limits,
            allowed_parameters=None if allowed is None else tuple(str(a) for a in allowed),
            allow_loopback=bool(profile.get("allow_loopback", False)),
        )


def resolve(
    endpoint_ref: str,
    profile: OutboundProfile | None,
    params: Mapping[str, str] | None = None,
) -> PreparedRequest | Refusal:
    """Turn an add-on's endpoint name into an approved request, or refuse it by rule.

    This is the whole of `p0-security.md`'s "임의 URL이 아니라 등록된 source_id를
    선택한다": the add-on supplies a name that must already be in the profile, so there
    is no input to this function that could become an arbitrary URL. A name the profile
    does not carry is refused before anything else is considered.
    """
    if profile is None:
        return Refusal(
            RefusalReason.SOURCE_HAS_NO_PROFILE,
            f"the source has no approved outbound profile, so {endpoint_ref!r} cannot be requested",
            {"endpoint_ref": endpoint_ref},
        )

    path = profile.endpoints.get(endpoint_ref)
    if path is None:
        known = ", ".join(sorted(profile.endpoints)) or "none"
        return Refusal(
            RefusalReason.ENDPOINT_NOT_DECLARED,
            f"{endpoint_ref!r} is not an approved endpoint; approved endpoints are {known}",
            {"endpoint_ref": endpoint_ref, "approved": sorted(profile.endpoints)},
        )

    if not profile.hosts:
        return Refusal(
            RefusalReason.HOST_NOT_ALLOWED,
            f"the source's profile approves no host, so {endpoint_ref!r} cannot be requested",
            {"endpoint_ref": endpoint_ref},
        )
    host = profile.hosts[0]

    if profile.allowed_parameters is not None and params:
        unexpected = sorted(set(params) - set(profile.allowed_parameters))
        if unexpected:
            # Names only. A value is the part an add-on controls.
            return Refusal(
                RefusalReason.PARAMETER_NOT_ALLOWED,
                f"parameters not approved for {endpoint_ref!r}: {', '.join(unexpected)}",
                {"endpoint_ref": endpoint_ref, "unexpected": unexpected},
            )

    if not path.startswith("/"):
        return Refusal(
            RefusalReason.PATH_NOT_ALLOWED,
            f"the approved path for {endpoint_ref!r} is not absolute",
            {"endpoint_ref": endpoint_ref},
        )

    url = f"https://{host}:{profile.port}{quote(path, safe='/')}"
    if params:
        url = f"{url}?{urlencode(dict(params))}"
    return PreparedRequest(url=url, host=host, port=profile.port, endpoint_ref=endpoint_ref)


def check_redirect(
    location: str, profile: OutboundProfile, hops: int
) -> PreparedRequest | Refusal:
    """Revalidate a redirect destination under the same policy as the original request.

    `p0-security.md`: "HTTP redirect가 발생하면 destination을 같은 정책으로 다시
    검증한다." Same policy means the same function decides — a second, looser check
    written for redirects would be the hole.
    """
    if hops > int(profile.limits.get("max_redirects", DEFAULT_LIMITS["max_redirects"])):
        return Refusal(
            RefusalReason.TOO_MANY_REDIRECTS,
            f"the request exceeded {profile.limits.get('max_redirects')} redirects",
            {"hops": hops},
        )

    parts = urlsplit(location)
    if parts.scheme not in ALLOWED_SCHEMES:
        return Refusal(
            RefusalReason.SCHEME_NOT_ALLOWED,
            f"a redirect to scheme {parts.scheme or '(relative)'!r} is not allowed",
            {"scheme": parts.scheme},
        )
    if parts.hostname is None or parts.hostname not in profile.hosts:
        return Refusal(
            RefusalReason.HOST_NOT_ALLOWED,
            f"a redirect to host {parts.hostname!r} is not approved for this source",
            {"host": parts.hostname, "approved": list(profile.hosts)},
        )
    port = parts.port or 443
    if port != profile.port:
        return Refusal(
            RefusalReason.PORT_NOT_ALLOWED,
            f"a redirect to port {port} is not approved for this source",
            {"port": port, "approved": profile.port},
        )
    if not any(parts.path.startswith(p) for p in profile.endpoints.values()):
        return Refusal(
            RefusalReason.PATH_NOT_ALLOWED,
            "a redirect left the source's approved path range",
            {"path": parts.path},
        )
    return PreparedRequest(
        url=location, host=parts.hostname, port=port, endpoint_ref="(redirect)"
    )


def check_resolved_addresses(
    host: str, addresses: Sequence[str], profile: OutboundProfile
) -> Refusal | None:
    """Refuse a hostname that resolves into a range `p0-security.md` blocks.

    Takes the addresses rather than resolving them, so the rule is testable without a
    resolver and without a network. The lookup belongs to the caller, which is also the
    only party that can do it at the right moment — a name checked once and connected to
    later is a rebinding hole, so the caller must connect to the address it checked.

    **Every address must pass.** A name resolving to one public and one loopback address
    is refused: taking the first, or any, would make the outcome depend on resolver
    ordering.
    """
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return Refusal(
                RefusalReason.ADDRESS_RANGE_BLOCKED,
                f"{host!r} resolved to something that is not an IP address",
                {"host": host},
            )
        if address.is_loopback and profile.allow_loopback:
            continue
        if (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return Refusal(
                RefusalReason.ADDRESS_RANGE_BLOCKED,
                f"{host!r} resolved into a blocked address range",
                {"host": host, "address": str(address)},
            )
    return None


def strip_protected_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Remove credential-bearing headers from anything about to be recorded.

    `p0-security.md`: "Network error와 HTTP response를 기록할 때 Authorization, Cookie와
    provider-protected header를 제거한다." Applied on the way *out* of the transport, so
    that what an add-on receives and what the Raw envelope stores have already lost them
    — rather than being trusted to lose them later.
    """
    return {k: v for k, v in headers.items() if k.lower() not in PROTECTED_HEADERS}
