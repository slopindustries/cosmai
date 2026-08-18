"""The handler table: a name in a job row, a callable in this process.

``job.handler`` is text the platform stores without interpreting. Turning it into
something executable is the one place the platform decides what a job means, and
the contract fixes what happens when it cannot: a name that is not registered
fails the job as ``HANDLER_UNKNOWN`` on its first claim and is not retried.

The context a handler receives is deliberately thin. It carries the job's
identity, its opaque payload, the attempt it is running as, and the one durable
effect P0-A permits — and nothing that would let a handler reach the job tables
directly. A handler that could write its own state would make the state machine
untestable, which is the whole point of running synthetic handlers at all.

``apply_effect`` arrives as a callable rather than a store reference so this
module stays free of database code: ``runner`` binds it to the store it is using.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from platform_core.errors import HandlerUnknownError


@dataclass(frozen=True)
class JobContext:
    """What a handler is given. Everything here is platform state, never domain state."""

    job_id: UUID
    payload: Any
    attempt_no: int
    attempt_count: int
    max_attempts: int
    correlation_id: str
    worker_id: str
    apply_effect: Callable[[str, Any], bool]

    def payload_field(self, name: str, fallback: Any = None) -> Any:
        """Read one key from the payload, tolerating a payload that is not a mapping.

        The platform does not interpret a payload; a synthetic handler does, and
        JSON ``null`` is a legal payload, so "the payload has no fields" has to be
        an ordinary answer rather than an exception.
        """
        if isinstance(self.payload, Mapping):
            return self.payload.get(name, fallback)
        return fallback


Handler = Callable[[JobContext], None]
"""A handler succeeds by returning, and fails by raising a ``PlatformError``."""


class HandlerRegistry:
    """Name to callable. Empty by default; a process registers what it will run."""

    def __init__(self, handlers: Mapping[str, Handler] | None = None) -> None:
        self._handlers: dict[str, Handler] = dict(handlers or {})

    def register(self, name: str, handler: Handler) -> None:
        """Bind ``name``. Rebinding is refused: two meanings for one name is a defect."""
        if name in self._handlers:
            raise ValueError(f"handler {name!r} is already registered")
        self._handlers[name] = handler

    def resolve(self, name: str) -> Handler:
        """Return the handler, or raise the contract's ``HANDLER_UNKNOWN``.

        The summary names the missing handler and lists what is registered. Both
        are configuration, not payload, so neither can carry an input value.
        """
        try:
            return self._handlers[name]
        except KeyError:
            known = ", ".join(sorted(self._handlers)) or "none"
            raise HandlerUnknownError(
                f"no handler named {name!r} is registered; registered handlers are {known}",
                {"requested": name, "registered": sorted(self._handlers)},
            ) from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def __contains__(self, name: object) -> bool:
        return name in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._handlers))


#: The payload key a synthetic handler reads to choose its effect key. JOB-008
#: needs two different jobs to be able to produce the same key, so the key cannot
#: be derived from job identity alone.
EFFECT_KEY_FIELD: Final = "effect_key"


def effect_key_for(context: JobContext) -> str:
    """The effect key this attempt will use.

    Independent of the attempt number by construction — that independence is the
    entire idempotency mechanism under I1. A payload may state a key so that two
    jobs can collide on purpose; otherwise the job's own identity is the key, so
    that a retried job reproduces it.
    """
    stated = context.payload_field(EFFECT_KEY_FIELD)
    if isinstance(stated, str) and stated:
        return stated
    return f"job/{context.job_id}"
