"""The socket half of the outbound guard: one hop, bounded, connected where it was checked.

`domain.outbound` is deliberately decidable without a socket — every rule there is a
function of a URL, a profile, and a list of addresses. This module is what is left over:
a name to resolve, a connection to make, bytes to read, and a clock to run out. It is
separate for the reason `outbound` states, which is that a policy testable only against a
live network is a policy nobody re-tests.

Three properties are this module's and not `outbound`'s.

**It connects to the address it checked.** `getaddrinfo` runs once, every address it
returned is put through :func:`~domain.outbound.check_resolved_addresses`, and the socket
is opened to one of *those* addresses with the approved hostname carried separately for
TLS and for `Host`. Checking a name and then connecting by name is a rebinding hole: the
second lookup can answer differently from the first, and nothing in a passing test would
show it.

**It follows no redirect.** One call is one hop. A `3xx` comes back with its `Location`
unfollowed, because revalidating a redirect is `outbound.check_redirect`'s and a transport
that quietly followed one would be a second, looser policy nobody wrote down.

**It stops.** The read deadline is a socket timeout and the size limit is enforced while
reading rather than after, so `SEC-004`'s "oversized/slow response는 bounded failure로
종료되고 worker를 무기한 점유하지 않는다" holds against a server that never stops sending
as well as one that never starts.

The TLS context is a constructor argument whose default is `ssl.create_default_context()`.
That is how a test reaches a stub with its own certificate authority without any source
row, profile field, or environment variable being able to widen the policy — a
*per-process* trust anchor rather than a *per-source* one. `tests/test_outbound_transport.py`
holds the positive control: the same stub under the default context fails to verify.
"""

from __future__ import annotations

import http.client
import socket
import ssl
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from domain.outbound import (
    DEFAULT_LIMITS,
    OutboundProfile,
    PreparedRequest,
    Refusal,
    RefusalReason,
    check_resolved_addresses,
    strip_protected_headers,
)

__all__ = [
    "SocketTransport",
    "Transport",
    "TransportLimits",
    "TransportResponse",
    "TransportUnavailable",
    "resolve_addresses",
]


class TransportUnavailable(Exception):
    """The request could not be completed. Not a policy refusal — a failed attempt.

    Kept apart from `Refusal` because they retry differently and an operator acts on
    them differently. A refusal means the request was never allowed and never will be
    until configuration changes; this means the network, the name service, or the far
    end did not cooperate this time.
    """

    def __init__(self, summary: str, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(summary)
        self.summary = summary
        self.detail: Mapping[str, Any] = dict(detail or {})


@dataclass(frozen=True)
class TransportLimits:
    """What bounds this one hop.

    Plain numbers rather than `addon_api.Limits`: `tests/environment/test_addon_layer_direction.py`
    forbids `domain` from importing `addon_api`, and that rule is the reason Raw persistence
    does not move when the add-on contract version does. `addon_host` translates.
    """

    connect_timeout_s: float = float(DEFAULT_LIMITS["connect_timeout_s"])
    read_timeout_s: float = float(DEFAULT_LIMITS["read_timeout_s"])
    max_response_bytes: int = int(DEFAULT_LIMITS["max_response_bytes"])

    @classmethod
    def from_profile(cls, profile: OutboundProfile) -> TransportLimits:
        limits = {**DEFAULT_LIMITS, **profile.limits}
        return cls(
            connect_timeout_s=float(limits["connect_timeout_s"]),
            read_timeout_s=float(limits["read_timeout_s"]),
            max_response_bytes=int(limits["max_response_bytes"]),
        )


@dataclass(frozen=True)
class TransportResponse:
    """One hop's result. Headers already stripped, body already bounded.

    `location` is lifted out of the headers rather than left for the caller to find, so
    that "was this a redirect" is answered the same way every time. It is carried
    unvalidated on purpose: validating it is `outbound.check_redirect`'s, and a transport
    that pre-screened it would be deciding policy.
    """

    status: int
    headers: Mapping[str, str]
    body: bytes
    location: str | None = None
    addresses: tuple[str, ...] = field(default_factory=tuple)


class Transport(Protocol):
    """One hop. Returns a response, refuses by rule, or raises because it could not.

    A protocol because the capability layer must be testable without a network, and
    because the thing being tested there — buffering, atomicity, the count cross-check —
    is not this.
    """

    def send(
        self,
        request: PreparedRequest,
        profile: OutboundProfile,
        headers: Mapping[str, str] | None = None,
        limits: TransportLimits | None = None,
    ) -> TransportResponse | Refusal: ...


def resolve_addresses(host: str, port: int) -> tuple[str, ...]:
    """Every address `host` resolves to right now, as strings.

    Separate from the check so a test can supply addresses the local resolver would
    never return — which is the only way to exercise the blocked ranges without owning
    a domain that points at them.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise TransportUnavailable(
            f"{host!r} could not be resolved", {"host": host}
        ) from error
    return tuple(dict.fromkeys(str(info[4][0]) for info in infos))


#: Read in pieces so the size limit can stop a body mid-flight. Small enough that an
#: 8 MiB limit is not overshot by a meaningful amount, large enough not to syscall per row.
_CHUNK: Final = 64 * 1024


class SocketTransport:
    """The real one. HTTPS only, one hop, and it never looks a name up twice."""

    def __init__(self, context: ssl.SSLContext | None = None) -> None:
        self._context = context or ssl.create_default_context()

    def send(
        self,
        request: PreparedRequest,
        profile: OutboundProfile,
        headers: Mapping[str, str] | None = None,
        limits: TransportLimits | None = None,
    ) -> TransportResponse | Refusal:
        bounds = limits or TransportLimits.from_profile(profile)
        addresses = resolve_addresses(request.host, request.port)
        if not addresses:
            raise TransportUnavailable(
                f"{request.host!r} resolved to no address", {"host": request.host}
            )
        refusal = check_resolved_addresses(request.host, addresses, profile)
        if refusal is not None:
            return refusal
        return self._hop(request, addresses, headers or {}, bounds)

    def _hop(
        self,
        request: PreparedRequest,
        addresses: Sequence[str],
        headers: Mapping[str, str],
        bounds: TransportLimits,
    ) -> TransportResponse | Refusal:
        connection = self._connect(request, addresses, bounds)
        try:
            # `Host` is set from the approved hostname because the socket was opened to
            # an address: without this the request would announce the IP it dialled and
            # a name-based virtual host would answer the wrong site.
            sent = {"Host": request.host, "Accept-Encoding": "identity", **dict(headers)}
            connection.request("GET", _path_of(request.url), headers=sent)
            response = connection.getresponse()
            body, overflowed = _read_bounded(response, bounds.max_response_bytes)
            if overflowed:
                return Refusal(
                    RefusalReason.RESPONSE_TOO_LARGE,
                    f"the response exceeded {bounds.max_response_bytes} bytes and was abandoned",
                    {"endpoint_ref": request.endpoint_ref, "limit": bounds.max_response_bytes},
                )
            return TransportResponse(
                status=response.status,
                headers=strip_protected_headers(dict(response.getheaders())),
                body=body,
                location=response.getheader("Location"),
                addresses=tuple(addresses),
            )
        except (TimeoutError, OSError, http.client.HTTPException) as error:
            raise TransportUnavailable(
                f"the request to {request.endpoint_ref!r} did not complete",
                {"endpoint_ref": request.endpoint_ref, "cause": type(error).__name__},
            ) from error
        finally:
            connection.close()

    def _connect(
        self, request: PreparedRequest, addresses: Sequence[str], bounds: TransportLimits
    ) -> http.client.HTTPSConnection:
        """Open a socket to a checked address, with TLS verified against the approved name.

        The socket is built here and handed to `HTTPSConnection` already wrapped, rather
        than letting it dial: `HTTPSConnection` would use one string for the address, the
        SNI, and the `Host` header, and those are the same value only when no address
        check happened. Assigning `.sock` is what makes it skip its own `connect()`.
        """
        last: Exception | None = None
        for address in addresses:
            raw: socket.socket | None = None
            try:
                raw = socket.create_connection(
                    (address, request.port), timeout=bounds.connect_timeout_s
                )
                secured = self._context.wrap_socket(raw, server_hostname=request.host)
                secured.settimeout(bounds.read_timeout_s)
            except (TimeoutError, OSError, ssl.SSLError) as error:
                last = error
                if raw is not None:
                    raw.close()
                continue
            connection = http.client.HTTPSConnection(
                request.host, request.port, timeout=bounds.read_timeout_s, context=self._context
            )
            connection.sock = secured
            return connection
        raise TransportUnavailable(
            f"no checked address for {request.host!r} accepted a connection",
            {"host": request.host, "addresses": list(addresses),
             "cause": type(last).__name__ if last else None},
        ) from last


def _read_bounded(source: http.client.HTTPResponse, limit: int) -> tuple[bytes, bool]:
    """Read at most `limit` bytes, and say whether there were more.

    One byte past the limit is requested on purpose. Reading exactly `limit` cannot tell a
    body that ended at the limit from one that was cut at it, and "we do not know whether
    this is complete" is not a state Raw may hold — losslessness is the claim Raw makes.
    """
    chunks: list[bytes] = []
    remaining = limit + 1
    while remaining > 0:
        chunk = source.read(min(_CHUNK, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    body = b"".join(chunks)
    if len(body) > limit:
        return b"", True
    return body, False


def _path_of(url: str) -> str:
    """The origin-form request target: everything from the path on.

    Taken from the URL `outbound.resolve` built rather than reassembled, so the bytes that
    were approved are the bytes that are sent.
    """
    without_scheme = url.split("://", 1)[-1]
    slash = without_scheme.find("/")
    return "/" if slash < 0 else without_scheme[slash:]
