"""The error taxonomy an add-on raises.

An add-on cannot import ``platform_core.errors``: that is the dependency this
package exists to break. So the contract carries its own taxonomy and
``addon_host`` translates it at the boundary. Without that translation the
decoupling would be nominal — an add-on importing the platform's error classes
is an add-on that imports the platform.

The translation is deliberately narrow. An add-on says what kind of failure it
hit; it does not choose a retry schedule, a terminal state, or an error code the
operator sees. Those stay with the platform, which is the only party that knows
the attempt budget.

``detail`` is for diagnosis and the platform treats it as protected: it is
redacted before it reaches a log and is withheld from the default API
representation. That is a safety net and not a licence — an add-on must not put
a credential in ``summary`` or ``detail``, because the add-on never receives one
in the first place (DP-008 D4).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AddonError(Exception):
    """Base class for every failure an add-on may raise deliberately.

    An add-on that raises anything else is not thereby broken — the host treats an
    unexpected exception as a permanent failure and records the type — but it has
    given up its say in how the failure is classified.
    """

    def __init__(self, summary: str, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(summary)
        self.summary = summary
        self.detail: Mapping[str, Any] | None = detail


class AddonTransient(AddonError):
    """The same call could succeed later: a rate limit, a timeout, a 5xx.

    The platform decides whether an attempt remains. An add-on raising this on a
    failure that will never clear only spends the attempt budget before reaching
    the same terminal state.
    """


class AddonPermanent(AddonError):
    """Retrying will not help: an unparseable record, a 4xx that is not authentication."""


class AddonConfigInvalid(AddonError):
    """The stored configuration for this source is wrong, and no retry can fix it.

    A 401 or 403 belongs here rather than in :class:`AddonPermanent`. The
    credential is part of the source's configuration, the operator is the only
    party who can correct it, and ``p0-security.md`` already requires an
    unresolvable credential to end as a non-retryable configuration failure.
    """


class AddonOutputInvalid(AddonError):
    """A produced result does not satisfy the declared output contract.

    Normally raised by the host during output validation rather than by an add-on.
    It is declared here so that an add-on validating its own output raises the
    same class the host would, instead of inventing a second spelling for it.
    """
