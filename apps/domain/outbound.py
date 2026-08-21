"""The outbound policy. Every obligation in `p0-security.md` §Outbound lives here.

Copy-adapted from ``experiments/integrated-p0/domain/outbound.py`` (M2 batch 2c). The only
change is where credential resolution comes from: ``platform_core.secrets`` rather than a
domain-local ``secrets.py`` — P1 already centralizes ``resolve_credential`` there (DP-032
D4's ``COSMA_DB_*``/``COSMA_SRC_*`` ref families share one resolver and one ref-shape
check), so this module reuses it instead of duplicating a second copy. Every rule, refusal,
limit, and the credential-attachment logic (DP-018) are otherwise verbatim.

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
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final
from urllib.parse import quote, urlencode, urlsplit

from platform_core.secrets import resolve_credential

__all__ = [
    "DEFAULT_LIMITS",
    "PROTECTED_HEADERS",
    "CredentialPart",
    "credential_headers",
    "OutboundProfile",
    "PreparedRequest",
    "Refusal",
    "RefusalReason",
    "check_resolved_addresses",
    "comparable_segments",
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
    #: The two limits `ADVERSARIAL-REVIEW-2026-08-18.md` F1 found enforced nowhere. They
    #: are refusals rather than a quiet stop for the reason every other member here is one:
    #: an add-on that ran past its grant has not collected less, it has been refused, and a
    #: run that reported success at the limit would be indistinguishable from one that
    #: reached the end of the data.
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    RECORD_LIMIT_EXCEEDED = "RECORD_LIMIT_EXCEEDED"
    #: DP-020. The method is the operator's grant and the body is bounded by the platform,
    #: so both can be refused for the same reason every other member here exists: an add-on
    #: reached past what the source row approved.
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"


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
    #: DP-020 D1. From the profile, never from the add-on.
    method: str = "GET"
    #: DP-020 D2. From the add-on, exactly as `params` always has been. `None` for a `GET`.
    body: bytes | None = None


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
    # DP-024. Bounds one local input an importer opens, and has nothing to do with the
    # network — it lives here because `Limits` is one object an add-on reads, not because
    # a dataset is a request.
    "max_input_bytes": 64 * 1024 * 1024,
    # The whole of one `fetch`, redirect hops and connection attempts included.
    # `ADVERSARIAL-REVIEW-2026-08-18.md` F5 is why it exists: the socket timeouts above
    # bound one `recv` each, so a server sending one byte per (timeout − ε) trips none of
    # them, and occupancy came out linear in `max_response_bytes` — the reviewer's
    # arithmetic put `DEFAULT_LIMITS` at about 38 days. This is the bound that does not
    # move with what it bounds.
    #
    # 60 seconds is chosen rather than derived. One honest hop against a slow but working
    # source costs `connect_timeout_s + read_timeout_s` = 35s, so this leaves room for a
    # redirect and no more; summing the per-hop limits over `max_redirects + 1` would give
    # 140s, which is the arithmetic of the worst case rather than a bound anyone wants. A
    # source that genuinely needs longer states it, and states it where an operator can
    # see what it is buying.
    "max_request_seconds": 60.0,
    # DP-020 D3. A body is the add-on's (D2), so it is the add-on's to get wrong, and a
    # limit written into a contract with no counter behind it is what
    # `ADVERSARIAL-REVIEW-2026-08-18.md` F1 was about. 64 KiB is far above the largest
    # documented DataLab body — five keyword groups of twenty keywords — and far below
    # anything that would make one request expensive to hold in memory.
    "max_request_bytes": 64 * 1024,
}

#: DP-020 D1. `GET` reads and `POST` reads-expressed-as-a-body; nothing that writes. A
#: write to a source is a different safety question and `p0-security.md` has not been asked
#: it, so the others are refused by name rather than passed through.
ALLOWED_METHODS: Final[frozenset[str]] = frozenset({"GET", "POST"})

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


#: The shape `secret-setup.md` fixes for a secret-store key, and the same pattern the
#: `source_credential_ref_is_a_key_name` CHECK holds on the column. Repeated here because
#: DP-018 puts refs in a jsonb array that a column constraint cannot see inside.
_KEY_NAME: Final = re.compile(r"^COSMA_SRC_[A-Z0-9_]+$")


@dataclass(frozen=True)
class CredentialPart:
    """One part of a source's credential: a key name, and the header it fills.

    [DP-018](../../../docs/decisions/DP-018-credential-parts-and-attachment.md) D1. A part
    exists at all because the first real source needs two of them: DP-008 left
    `needs_credential` as one boolean and `source.credential_ref` as one column, and Naver
    API Hub wants `X-NCP-APIGW-API-KEY-ID` and `X-NCP-APIGW-API-KEY` together.

    `ref` is a **key name** and never a value. The whole of what may appear in a log line,
    a dashboard, or this dataclass's `repr` is the name.
    """

    header: str
    ref: str


def _as_bytes(body: object) -> bytes | None:
    """The body as the bytes that will actually be sent, or `None` if that is unknowable.

    `[측정]` **This exists because `len(body)` was the wrong quantity.**
    `ADVERSARIAL-REVIEW-2026-08-19.md` F1: `len` is a byte count only for `bytes`, and
    `http.client` accepts far more than that — any bytes-like via the buffer protocol, and
    any iterable of bytes, which it streams `Transfer-Encoding: chunked`. A one-element
    `list[bytes]` therefore measured **1** against a 64 KiB grant and put 1 MiB on the wire.
    DP-020 D3 claims the platform bounds the body; a bound that trusts the add-on's static
    typing to keep the shape simple is not the platform bounding anything.

    `bytes` remains the declared type and mypy still refuses the alternatives. This is what
    happens when one reaches here anyway — and the finding is the argument for having it:
    a `bytearray` is the natural way to assemble a body incrementally, and a helper
    annotated `-> bytes` that returns one satisfies the checker and not the runtime.

    **An unmeasurable body is refused rather than sent.** A generator cannot be sized without
    consuming it, and consuming it here would leave the caller an exhausted iterator — so the
    honest answer is that this guard cannot bound it, and DP-020 D3 says an unbounded body
    does not go out. `None` is that answer.
    """
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray | memoryview):
        # Bytes-like: `http.client` sends these through the buffer protocol, and their
        # length is already a byte count. Copied to `bytes` so that what was measured is
        # what is sent — a `bytearray` the add-on still holds could change afterwards.
        return bytes(body)
    # An iterable of chunks, which `http.client` streams. Materialised here because a
    # sequence can be measured without being consumed; a generator cannot, and falls through
    # to the refusal below.
    if isinstance(body, list | tuple) and all(
        isinstance(chunk, bytes | bytearray | memoryview) for chunk in body
    ):
        return b"".join(bytes(chunk) for chunk in body)
    return None


def _read_endpoints(endpoints: Mapping[str, Any]) -> dict[str, Any]:
    """Read both endpoint shapes, refusing a method the platform does not grant.

    DP-020 D1. A `ValueError` and not a `Refusal`, like every other malformed-row check
    here: the row should never have been written, which is a different thing from a request
    being denied. Refusing at read time also means an operator learns at registration rather
    than on the first fetch of an endpoint they may not use for weeks.
    """
    read: dict[str, Any] = {}
    for name, entry in endpoints.items():
        if isinstance(entry, Mapping):
            method = str(entry.get("method", "GET")).upper()
            if method not in ALLOWED_METHODS:
                raise ValueError(
                    f"outbound_profile.endpoints[{name!r}] asks for method {method!r}; this "
                    f"platform grants only {', '.join(sorted(ALLOWED_METHODS))} (DP-020 D1)"
                )
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                raise ValueError(
                    f"outbound_profile.endpoints[{name!r}] declares no path. An absent path "
                    "used to default to the empty string, which every path is inside — one "
                    "such endpoint granted the whole host as the redirect range for all the "
                    "others. State the path, or remove the endpoint."
                )
            read[str(name)] = {"path": path, "method": method}
        else:
            read[str(name)] = str(entry)
    return read


def _read_credentials(profile: Mapping[str, Any]) -> tuple[CredentialPart, ...]:
    """Read the `credentials` array, refusing a part the platform cannot honour safely.

    Both refusals are `ValueError` rather than `Refusal`, because this is a row that should
    never have been written — the shape `from_row` already uses for a malformed `endpoints`
    value, and a different thing from a request being denied.

    **The header must be protected.** DP-018 D3, and the load-bearing half of the packet.
    `strip_protected_headers` is what keeps a credential out of
    `raw_envelope.response_headers`, and it works from a fixed list. A profile free to name
    any header could name one that is attached on the way out and recorded on the way back —
    a credential in Raw with every individual rule still satisfied. Tying attachment to that
    list makes "attached" and "stripped" one set by construction instead of by two people
    remembering.

    **The ref must be a key name.** The column's CHECK cannot see inside a jsonb array, so
    the same rule is stated where the array is read, and a real token pasted into a profile
    is refused rather than sent.
    """
    stated = profile.get("credentials")
    if not stated:
        return ()
    parts: list[CredentialPart] = []
    for entry in stated:
        header = str(entry["header"])
        ref = str(entry["ref"])
        if header.lower() not in PROTECTED_HEADERS:
            raise ValueError(
                f"outbound_profile.credentials names {header!r}, which is not a protected "
                "header; a credential may only fill a header that is stripped out of "
                f"recorded Raw (DP-018 D3). Protected: {', '.join(sorted(PROTECTED_HEADERS))}"
            )
        if not _KEY_NAME.match(ref):
            raise ValueError(
                "outbound_profile.credentials carries a ref that is not a secret-store key "
                "name; it must match COSMA_SRC_<SOURCE_ID>_<PURPOSE> and is never a value"
            )
        parts.append(CredentialPart(header=header, ref=ref))
    return tuple(parts)


def credential_headers(profile: OutboundProfile) -> dict[str, str]:
    """Resolve this source's credential into the headers one request will carry.

    Per request and never cached — `domain.secrets.resolve_credential` says why. A profile
    with no credential resolves nothing and therefore needs no secret store at all, which
    matters because most sources have none and none of them should be made to depend on a
    store existing.

    Raises rather than returning what it could resolve. `secret-setup.md` invariant 4: a
    partially-authenticated request is one a source may answer with `200` and an error body,
    which a collector would store as Raw and a normalizer would later read as data.
    """
    return {part.header: resolve_credential(part.ref).reveal() for part in profile.credentials}


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
    #: What this source authenticates with, and where each part goes (DP-018 D2). On the
    #: *profile* rather than in the add-on's manifest: an add-on naming its own header would
    #: be describing the wire format of a request DP-008 D4 forbids it to compose, which is
    #: one fact in two places that can disagree. The manifest's `needs_credential` is the
    #: request; this is the grant, exactly as it already is for hosts and endpoints.
    credentials: tuple[CredentialPart, ...] = ()

    def path_of(self, endpoint_ref: str) -> str | None:
        """The approved path for this name, whichever shape the row used.

        DP-020 D1 lets an entry be a bare string — the `GET` form every profile written
        before it uses — or an object carrying a method. Read here rather than normalised at
        construction so that a profile built directly in a test and one read from a row take
        the same path through this code.
        """
        entry = self.endpoints.get(endpoint_ref)
        if entry is None:
            return None
        if isinstance(entry, Mapping):
            return str(entry.get("path", ""))
        return str(entry)

    def method_of(self, endpoint_ref: str) -> str:
        """The method the operator granted for this name. `GET` unless the row says otherwise."""
        entry = self.endpoints.get(endpoint_ref)
        if isinstance(entry, Mapping):
            return str(entry.get("method", "GET")).upper()
        return "GET"

    def approved_paths(self) -> tuple[str, ...]:
        """Every approved path, for the redirect range. Both entry shapes, one tuple."""
        return tuple(
            path for name in self.endpoints if (path := self.path_of(name)) is not None
        )

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
        endpoints = _read_endpoints(endpoints)
        limits = dict(DEFAULT_LIMITS)
        limits.update(profile.get("limits") or {})
        allowed = profile.get("allowed_parameters")
        return cls(
            hosts=tuple(profile.get("hosts") or ()),
            endpoints=endpoints,
            port=int(profile.get("port", 443)),
            limits=limits,
            allowed_parameters=None if allowed is None else tuple(str(a) for a in allowed),
            allow_loopback=bool(profile.get("allow_loopback", False)),
            credentials=_read_credentials(profile),
        )


def resolve(
    endpoint_ref: str,
    profile: OutboundProfile | None,
    params: Mapping[str, str] | None = None,
    body: bytes | None = None,
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

    path = profile.path_of(endpoint_ref)
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

    if comparable_segments(path) is None:
        # A stored path that cannot be compared segment by segment would grant a range
        # `check_redirect` is unable to describe, so every redirect for this source would
        # be refused and nothing would say why. Refusing on the first fetch puts the
        # failure where an operator can act on it — see F4 in the review.
        return Refusal(
            RefusalReason.PATH_NOT_ALLOWED,
            f"the approved path for {endpoint_ref!r} carries a dot segment or an encoded "
            "separator, so the range it grants cannot be decided",
            {"endpoint_ref": endpoint_ref},
        )

    method = profile.method_of(endpoint_ref)
    if method not in ALLOWED_METHODS:
        return Refusal(
            RefusalReason.METHOD_NOT_ALLOWED,
            f"the profile grants method {method!r} for {endpoint_ref!r}, which this platform "
            f"does not send; granted methods are {', '.join(sorted(ALLOWED_METHODS))}",
            {"endpoint_ref": endpoint_ref, "method": method},
        )
    # DP-020 D4, both directions. A `GET` carrying a body is legal HTTP that many servers
    # ignore — a request the operator approved and the add-on did not get — and a `POST`
    # with none is an add-on that forgot the question it came to ask.
    if method == "GET" and body is not None:
        return Refusal(
            RefusalReason.METHOD_NOT_ALLOWED,
            f"{endpoint_ref!r} is approved for GET and a body was supplied; a body is only "
            "sent to an endpoint the profile grants POST",
            {"endpoint_ref": endpoint_ref, "method": method},
        )
    if method == "POST" and body is None:
        return Refusal(
            RefusalReason.METHOD_NOT_ALLOWED,
            f"{endpoint_ref!r} is approved for POST and no body was supplied",
            {"endpoint_ref": endpoint_ref, "method": method},
        )
    if body is not None:
        limit = int(profile.limits.get("max_request_bytes", DEFAULT_LIMITS["max_request_bytes"]))
        measured = _as_bytes(body)
        if measured is None or len(measured) > limit:
            # The body is the add-on's and could carry anything, so the refusal counts it and
            # never quotes it — the rule `Refusal` already applies to a query.
            size = -1 if measured is None else len(measured)
            return Refusal(
                RefusalReason.REQUEST_TOO_LARGE,
                f"the request body for {endpoint_ref!r} is {size} bytes and this source "
                f"grants {limit}"
                if measured is not None
                else f"the request body for {endpoint_ref!r} is not bytes this guard can "
                "measure, and an unmeasured body is not a bounded one",
                {"endpoint_ref": endpoint_ref, "limit": limit, "size": size},
            )
        # The measured bytes are what goes downstream, so the thing counted and the thing
        # sent cannot differ. `_hop` writes `request.body` and re-measures nothing.
        body = measured

    url = f"https://{host}:{profile.port}{quote(path, safe='/')}"
    # A `POST` asks its question in the body, so nothing goes in the URL as well: two places
    # for one fact is two places that can disagree, and only one of them is what was sent.
    if params and method == "GET":
        url = f"{url}?{urlencode(dict(params))}"
    return PreparedRequest(
        url=url,
        host=host,
        port=profile.port,
        endpoint_ref=endpoint_ref,
        method=method,
        body=body,
    )


def check_redirect(
    location: str, profile: OutboundProfile, hops: int
) -> PreparedRequest | Refusal:
    """Revalidate a redirect destination under the same policy as the original request.

    `p0-security.md`: "HTTP redirect가 발생하면 destination을 같은 정책으로 다시
    검증한다." Same policy means the same function decides — a second, looser check
    written for redirects would be the hole.

    `[측정]` The function was the same and the *comparison* was not. Until 2026-08-18 the
    path test was `parts.path.startswith(approved)` on the raw path, and
    `ADVERSARIAL-REVIEW-2026-08-18.md` F4 walked out of the approved range twice over —
    once with dot segments the far end resolves and this function did not, once with a
    string prefix that is not a path prefix. `comparable_segments` is the repair, and its
    docstring carries the reasoning for refusing rather than normalizing.
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
    # A redirect is followed as a `GET` whatever the original method was: `303` says so,
    # and for `307`/`308` re-sending a body to a destination the add-on never named is a
    # request nobody approved. Refusing to carry it is the conservative half.
    if not _is_within_approved_range(parts.path, profile):
        return Refusal(
            RefusalReason.PATH_NOT_ALLOWED,
            "a redirect left the source's approved path range",
            {"path": parts.path},
        )
    return PreparedRequest(
        url=location, host=parts.hostname, port=port, endpoint_ref="(redirect)"
    )


#: Percent-encodings of `.` and `/`. A path is compared as text here and resolved by the
#: far end after decoding, so a comparison that ignored these would be comparing something
#: other than what the server will act on — which is exactly how `%2e%2e` walks out of an
#: approved range while a scan for `..` sees nothing.
_ENCODED_DOT: Final[tuple[str, ...]] = ("%2e", "%2E")
_ENCODED_SLASH: Final[tuple[str, ...]] = ("%2f", "%2F")


def comparable_segments(path: str) -> tuple[str, ...] | None:
    """The path's segments, or `None` if what the far end will resolve is not knowable.

    `ADVERSARIAL-REVIEW-2026-08-18.md` F4. The approved range used to be tested with
    `path.startswith(approved)` on the raw path, and `domain.transport` sends the URL
    verbatim. Two things got through, and the reviewer carried the first of them end to end
    over TLS into a body it had written as `{"secret": "THIS-PATH-WAS-NEVER-APPROVED"}`:

    * `/v1/items/../../admin/keys` — the far end removes dot segments as RFC 3986 §5.2.4
      requires, so the path this function reads is not the path the server acts on.
    * `/v1/items2/secret` — a string prefix, not a path prefix. `/v1/items2` is beside
      `/v1/items`, not under it.

    So: **refuse rather than normalize.** Resolving `..` here would mean predicting which
    of several defensible decodings the far end performs — nginx, Apache, and a bare
    application server do not agree about `%2f`, and being wrong in the permissive
    direction is the hole. A `Location` carrying a dot segment is unusual server behaviour;
    a redirect refused for it costs one collection, and the alternative costs the range.
    """
    if not path:
        # `()` here would be a prefix of every path, so an endpoint that reached
        # `approved_paths()` without one granted the entire host to every other endpoint's
        # redirects. `None` routes it to the same `continue` an uncomparable path takes:
        # one bad endpoint narrows nothing and widens nothing.
        return None
    lowered = path
    for encoded in _ENCODED_SLASH:
        if encoded in lowered:
            return None
    for encoded in _ENCODED_DOT:
        lowered = lowered.replace(encoded, ".")
    segments = tuple(lowered.split("/"))
    if any(segment in (".", "..") for segment in segments):
        return None
    # A trailing slash makes `/v1/items/` and `/v1/items` the same resource to every server
    # that matters, and an empty final segment would otherwise make them different ranges.
    if len(segments) > 1 and segments[-1] == "":
        segments = segments[:-1]
    return segments


def _is_within_approved_range(path: str, profile: OutboundProfile) -> bool:
    """Whether `path` is one of the approved paths or under one, compared by segment."""
    candidate = comparable_segments(path)
    if candidate is None:
        return False
    for approved in profile.approved_paths():
        granted = comparable_segments(approved)
        if granted is None:
            # `resolve` refuses such a source on its first fetch. Skipped rather than
            # treated as granting everything, so a defect in one endpoint cannot widen
            # the range the others grant.
            continue
        if candidate[: len(granted)] == granted:
            return True
    return False


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
