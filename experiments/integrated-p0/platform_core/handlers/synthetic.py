"""The failure injectors the `JOB` scenarios need, and nothing that resembles work.

Each handler is one behavior, chosen so a scenario can name exactly what it is
exercising:

``succeed``            returns, leaving one effect. The base path of JOB-001.
``fail_transient``     raises a retryable failure until a stated attempt passes.
``fail_permanent``     always raises a non-retryable failure.
``halt_before_effect`` kills its own process before the effect is applied.
``halt_after_effect``  kills its own process after the effect is applied.
``stall``              sleeps past the lease so another worker reclaims the job.

The two ``halt`` handlers use ``os._exit``. That is the point: a handler that
raised, or that called ``sys.exit``, would unwind and let cleanup run, and the
interruption being tested is the one where nothing gets to clean up. They are the
only place in the platform allowed to do it, and they are only ever run in a
process a test started.

``halt_before_effect`` and ``halt_after_effect`` differ by one line, and that
line is the experiment: whether the durable effect survives an interruption
placed on either side of it, and whether the retry that follows produces a second
one. Splitting them into two handlers rather than one with a flag keeps the two
cases separately nameable from a scenario document.
"""

from __future__ import annotations

import os
import time
from typing import Any, Final

from platform_core.errors import PlatformPermanentError, PlatformTransientError
from platform_core.jobs.registry import HandlerRegistry, JobContext, effect_key_for

#: Payload key: the last attempt number ``fail_transient`` refuses to survive.
FAIL_UNTIL_ATTEMPT_FIELD: Final = "fail_until_attempt"

#: Payload key: how long ``stall`` sleeps, in seconds.
STALL_SECONDS_FIELD: Final = "stall_seconds"

#: Payload key: the status a ``halt`` handler exits with.
EXIT_CODE_FIELD: Final = "exit_code"

DEFAULT_EXIT_CODE: Final = 70

DEFAULT_STALL_SECONDS: Final = 5.0


def _effect_value(context: JobContext, marker: str) -> dict[str, Any]:
    """The opaque value written into ``platform_effect.payload``.

    It carries a handler name and an attempt number and nothing else. The column
    has no schema on purpose: giving it provenance or identity fields is exactly
    what would turn the effect table into something P0-A may not have.
    """
    return {"applied_by": marker, "attempt_no": context.attempt_no}


def succeed(context: JobContext) -> None:
    """Apply the effect and return. The scenario every other one deviates from."""
    context.apply_effect(effect_key_for(context), _effect_value(context, "succeed"))


def fail_transient(context: JobContext) -> None:
    """Raise a retryable failure through attempt ``fail_until_attempt``, then succeed.

    With no such field the handler never succeeds, which is what a retry-exhaustion
    scenario wants; with ``fail_until_attempt = 1`` the second attempt is the one
    that applies the effect.
    """
    threshold = context.payload_field(FAIL_UNTIL_ATTEMPT_FIELD)
    limit = context.max_attempts if not isinstance(threshold, int) else threshold
    if context.attempt_no <= limit:
        raise PlatformTransientError(
            "the retryable failure injector refused this attempt",
            {"attempt_no": context.attempt_no, "fails_through_attempt": limit},
        )
    context.apply_effect(effect_key_for(context), _effect_value(context, "fail_transient"))


def fail_permanent(context: JobContext) -> None:
    """Always raise a failure the contract forbids retrying."""
    raise PlatformPermanentError(
        "the permanent failure injector refused this attempt",
        {"attempt_no": context.attempt_no},
    )


def halt_before_effect(context: JobContext) -> None:
    """End this process with no effect applied and the attempt left open."""
    _halt(context)


def halt_after_effect(context: JobContext) -> None:
    """Apply the effect, then end this process with the attempt left open."""
    context.apply_effect(effect_key_for(context), _effect_value(context, "halt_after_effect"))
    _halt(context)


def stall(context: JobContext) -> None:
    """Sleep past the lease, then apply the effect and return.

    By the time it wakes, another worker has reclaimed the job and this worker's
    completion will be refused by the fence. The effect it applies on the way out
    is deliberate: the suppressed duplicate is part of what JOB-006 observes.
    """
    stated = context.payload_field(STALL_SECONDS_FIELD)
    seconds = float(stated) if isinstance(stated, int | float) else DEFAULT_STALL_SECONDS
    time.sleep(seconds)
    context.apply_effect(effect_key_for(context), _effect_value(context, "stall"))


def _halt(context: JobContext) -> None:
    """Leave immediately, running no handler, no finally block, and no flush."""
    stated = context.payload_field(EXIT_CODE_FIELD)
    code = stated if isinstance(stated, int) else DEFAULT_EXIT_CODE
    os._exit(code)


#: Every handler in this module, under the name a job row would carry.
SYNTHETIC_HANDLERS: Final[dict[str, Any]] = {
    "succeed": succeed,
    "fail_transient": fail_transient,
    "fail_permanent": fail_permanent,
    "halt_before_effect": halt_before_effect,
    "halt_after_effect": halt_after_effect,
    "stall": stall,
}


def synthetic_registry() -> HandlerRegistry:
    """A registry holding exactly the handlers above. The P0-A worker's whole table."""
    return HandlerRegistry(SYNTHETIC_HANDLERS)
