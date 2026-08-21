"""The operator API process that serves the domain surface too: ``python -m addon_host``.

``platform_core.api`` owns the process — configuration, the bound socket, the signal
handling, the exit statuses — and it owns none of the domain routes, because DP-008 D1
forbids ``platform_core`` from importing anything local and
``tests/environment/test_addon_layer_direction.py`` enforces it. So the platform's
``create_app`` gained one source-neutral seam, ``extend``, and this entrypoint is the
composition: the platform's app, plus :func:`addon_host.api.extend_with_domain`.

`[결정]` A second entrypoint rather than a flag on the first, for the reason
``addon_host.worker`` gives about the worker: ``python -m platform_core.api`` must keep
serving a source-neutral surface with no add-on layer present at all, which is what keeps
the P0-A gate's evidence standing. The duplication is one function and the coupling it
avoids is the one DP-008 D1 names.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from platform_core.api.__main__ import (
    EXIT_CONFIGURATION_INVALID,
    EXIT_UNAVAILABLE,
    listening_socket,
    parse_arguments,
    serve,
)
from platform_core.api.app import create_app
from platform_core.config import load_config
from platform_core.errors import PlatformError
from platform_core.obs.logging import StructuredLogger

from addon_host.api import extend_with_domain


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve configuration, bind, and serve the platform and domain surfaces together."""
    parse_arguments(argv)
    try:
        config = load_config()
    except PlatformError as invalid:
        StructuredLogger().error(
            "api.configuration_invalid",
            error_class=invalid.error_class.value,
            error_summary=invalid.summary,
        )
        return EXIT_CONFIGURATION_INVALID
    logger = StructuredLogger.resolved(config.log_file, config.log_level)
    try:
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
        return serve(
            config,
            logger,
            listener,
            app=create_app(config, logger, extend=extend_with_domain(config, logger)),
        )
    finally:
        logger.close()


if __name__ == "__main__":  # pragma: no cover - exercised as a process, not imported
    sys.exit(main())
