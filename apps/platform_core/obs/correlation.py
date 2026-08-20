"""The correlation identifier and its ambient context.

CONTRACT-JOB@0.1 invariant I5 is that correlation is total: every log line,
attempt row, and API response about a job carries its ``correlation_id``. An
invariant that has to be threaded through every call signature by hand is one
that fails quietly at the first helper someone forgets to update, so the current
identifier also lives in a ``ContextVar`` that the structured logger reads on its
own.

A ``ContextVar`` is per-thread and per-task, which is what the platform needs:
two workers in one process, or two requests in one event loop, never observe each
other's identifier. A new thread starts with an empty context by design — a
worker thread is expected to enter its own scope rather than inherit one.

This is platform provenance, and only that. Anything to do with where data came
from belongs to P0-B.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Final
from uuid import uuid4

#: The field name used everywhere this identifier is written.
CORRELATION_FIELD: Final = "correlation_id"

_CURRENT: Final[ContextVar[str | None]] = ContextVar("cosma_correlation_id", default=None)


def new_correlation_id() -> str:
    """Mint an identifier for a unit of work that does not have one yet."""
    return str(uuid4())


def current_correlation_id() -> str | None:
    """The identifier in scope, or ``None`` outside any scope."""
    return _CURRENT.get()


def bind_correlation_id(correlation_id: str) -> Token[str | None]:
    """Enter a scope without a ``with`` block. Pair with ``release_correlation_id``."""
    if not correlation_id:
        raise ValueError("correlation_id must be a non-empty string")
    return _CURRENT.set(correlation_id)


def release_correlation_id(token: Token[str | None]) -> None:
    """Restore whatever scope was in effect before the matching bind."""
    _CURRENT.reset(token)


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Run a block under ``correlation_id``, minting one when none is given.

    The previous value is restored on exit, including on an exception, so a
    nested scope cannot outlive its block.
    """
    value = correlation_id if correlation_id else new_correlation_id()
    token = bind_correlation_id(value)
    try:
        yield value
    finally:
        release_correlation_id(token)
