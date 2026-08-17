"""The operator API process entrypoint: ``python -m platform_core.api`` (DP-006 D1).

Four decisions are worth reading before the code.

**Configuration is resolved before anything else, and a refusal is fatal.** The
same rule the worker follows, for the same reason: SEC-003 requires a process given
invalid configuration to exit non-zero without substituting a default. Because
``load_config`` also carries SEC-001's secret-store location guard and SEC-002's
loopback guard, this one call is what makes the API the *second* entrypoint both
scenarios ask for — neither guard is written twice.

**The socket is bound here, not by uvicorn.** SEC-002 wants the address the process
actually bound to, and its telemetry section is explicit that a claim in a document
is not evidence. A server handed a host and a port can only be asked what it was
told; a socket can be asked what it got. So this module binds, reads
``getsockname()`` back off the socket, logs *that*, and hands the listening socket
to uvicorn.

**A bind failure and a bad configuration are different exits.** ``EX_CONFIG`` means
the environment was wrong and a restart will fail identically. A port already in
use is a transient condition, so it exits ``1`` — the same split
``platform_core.worker`` makes, and the numbers are asserted equal in
``tests/test_api.py`` rather than assumed.

**uvicorn's own logging is switched off.** Standard error is the platform's JSON
Lines stream, and SEC-004 has to be able to grep it. Interleaving a second log
format into it would make every line a reader has to classify before parsing.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
from collections.abc import Sequence
from types import FrameType
from typing import Final

import uvicorn

from platform_core.api.app import create_app
from platform_core.config import PlatformConfig, load_config
from platform_core.errors import PlatformError
from platform_core.obs.logging import StructuredLogger

EXIT_OK: Final = 0

#: The process could not run, but the configuration was not what was wrong: a port
#: already in use, a socket the kernel refused. A supervisor may retry this.
EXIT_UNAVAILABLE: Final = 1

#: ``EX_CONFIG`` from ``sysexits.h``. The same status ``platform_core.worker`` and
#: ``scripts/with-database.sh`` use for the same condition.
EXIT_CONFIGURATION_INVALID: Final = 78

#: How many pending connections the kernel may queue. P0-A has one operator.
BACKLOG: Final = 16

#: The signals that ask for a clean stop. The same pair ``platform_core.worker``
#: honours, so a supervisor stops both processes the same way.
STOP_SIGNALS: Final[tuple[signal.Signals, ...]] = (signal.SIGTERM, signal.SIGINT)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Read the command line. There is nothing on it, and that is the point.

    Every setting comes from the environment, so there is no second place a bind
    address could be stated — which is what keeps SEC-002's guard the only path to
    one. The parser exists so that ``--help`` works and a mistaken argument is
    reported instead of ignored.
    """
    parser = argparse.ArgumentParser(
        prog="python -m platform_core.api",
        description=(
            "Run the P0-A operator API. Every setting is read from the "
            "environment; see config/env.example."
        ),
    )
    return parser.parse_args(argv)


def listening_socket(host: str, port: int) -> socket.socket:
    """Bind and listen, returning the socket so its real address can be read.

    The family is chosen from the address rather than left to ``getaddrinfo``,
    because the configuration guard has already established that this is a literal
    loopback address and resolving it again would introduce the ambiguity the guard
    exists to remove.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    handle = socket.socket(family, socket.SOCK_STREAM)
    # No SO_REUSEADDR. On a single-host P0 the useful behavior is that a second
    # API on the same port fails loudly rather than shadowing the first.
    try:
        handle.bind((host, port))
        handle.listen(BACKLOG)
    except OSError:
        handle.close()
        raise
    return handle


def serve(config: PlatformConfig, logger: StructuredLogger, listener: socket.socket) -> int:
    """Serve on an already-bound socket until a stop signal, then report the exit.

    A stop handler is installed **around** uvicorn's. uvicorn captures the stop
    signals, shuts down gracefully, restores whatever handler it found, and then
    re-raises the signal so that the process ends the way the sender expected —
    which by default means dying of ``SIGTERM`` with no shutdown event written and a
    status of 143. Leaving a handler underneath it turns that re-raise into a note:
    the shutdown is still graceful, and the process then exits ``0`` having recorded
    that it stopped and why.

    The window before uvicorn installs its own handlers is not covered. A signal
    arriving there is noted and not acted on, so the server would keep running; it
    is the same shape of gap ``platform_core.worker`` has between process start and
    its own handler installation, and it is bounded by the socket already being
    bound before this is called.
    """
    bound = listener.getsockname()
    host, port = str(bound[0]), int(bound[1])
    logger.info(
        "api.started",
        host=host,
        port=port,
        pid=os.getpid(),
        log_level=config.log_level,
    )
    noted: list[str] = []

    def note_stop(number: int, frame: FrameType | None) -> None:
        noted.append(signal.Signals(number).name)

    restore = [(number, signal.getsignal(number)) for number in STOP_SIGNALS]
    for number in STOP_SIGNALS:
        signal.signal(number, note_stop)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(config, logger),
            # Host and port are left at their defaults and are unused: the
            # already-bound socket is what gets served.
            log_config=None,
            access_log=False,
        )
    )
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        for number, previous in restore:
            signal.signal(number, previous)
    logger.info(
        "api.stopped",
        host=host,
        port=port,
        pid=os.getpid(),
        stop_reason=f"a stop was requested by {noted[0]}" if noted else "the server returned",
    )
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve configuration, bind, and serve. Returns the process exit status."""
    parse_arguments(argv)
    try:
        config = load_config()
    except PlatformError as invalid:
        # No configuration means no log level, so this is the one event written by
        # a logger the configuration did not choose. It names settings and reasons;
        # secret-setup.md forbids dumping the environment instead.
        StructuredLogger().error(
            "api.configuration_invalid",
            error_class=invalid.error_class.value,
            error_summary=invalid.summary,
        )
        return EXIT_CONFIGURATION_INVALID
    logger = StructuredLogger(level=config.log_level)
    for warning in config.warnings():
        logger.warning("api.configuration_warning", detail=warning)
    try:
        listener = listening_socket(config.api_host, config.api_port)
    except OSError as refused:
        logger.error(
            "api.bind_refused",
            host=config.api_host,
            port=config.api_port,
            error_summary=str(refused),
        )
        return EXIT_UNAVAILABLE
    return serve(config, logger, listener)


if __name__ == "__main__":  # pragma: no cover - exercised as a process, not imported
    sys.exit(main())
