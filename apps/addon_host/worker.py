"""The worker process that hosts add-ons: ``python -m addon_host.worker``.

Copy-adapted verbatim from ``experiments/integrated-p0/addon_host/worker.py``
(M3 batch 3b). ``platform_core.worker.RegistryFor`` is exactly the seam P0 built
against — M1 carried it forward unchanged — so nothing here needed to move.

``platform_core.worker`` owns the process — configuration, the connection, the loop, the
signals, the shutdown report — and it owns none of this. What it lacks is a handler table
containing add-ons, and it cannot build one: DP-008 D1 forbids ``platform_core`` from
importing anything in the add-on layer, and ``tests/environment/test_addon_layer_direction.py``
fails the build if it tries. So the platform gained one source-neutral seam,
:data:`platform_core.worker.RegistryFor`, and the add-on half is here.

`ADVERSARIAL-REVIEW-2026-08-18.md` F3 is why this module exists rather than being implied.
It measured that ``bind_capabilities`` had three call sites and all three were tests, so
every claim EXP-003 made about a collector on the platform rested on a test's own wiring —
and the wiring was where the requirement that ``DomainStore`` and ``JobStore`` share one
connection was least visible. Two things follow, and both are deliberate:

**The table is rebuilt per connection, not per process.** ``Worker._reopen`` replaces the
connection after a transient database failure. A capability layer still holding the
previous connection's ``DomainStore`` would write outside the transaction that completes
the attempt — H2a's atomicity silently gone, with nothing failing. Building the
``DomainStore`` inside the callback makes that state unreachable rather than merely
untested.

**The transport is per process.** ``SocketTransport`` holds one TLS context and no
connection; DP-008 D4's rule is that an add-on opens no socket, not that the platform opens
a new stack per job. Its trust anchor is therefore fixed once, at process start, where no
source row or add-on manifest can reach it.

What this module deliberately does **not** do is resolve a credential — but not for the
reason it used to give. `[확인 사실]` OQ-009 is `RESOLVED` and DP-018 fixed the mapping: a
credential is a set of named parts, each a secret-store key name filling one protected
header. Resolution happens in :mod:`addon_host.capabilities`, at the point the outbound
request is composed, which is the worker boundary `p0-security.md` names. Nothing is
refused for want of an answer any more, and the sentence claiming so was corrected on
2026-08-19.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import psycopg

from addon_api import CONTRACT_VERSION
from addon_host.capabilities import bind_capabilities
from addon_host.registration import install_addons
from domain.store import DomainStore
from domain.transport import SocketTransport, Transport
from platform_core.config import PlatformConfig, load_config
from platform_core.errors import PlatformError
from platform_core.handlers.synthetic import synthetic_registry
from platform_core.jobs.registry import HandlerRegistry
from platform_core.obs.logging import StructuredLogger
from platform_core.worker import (
    EXIT_CONFIGURATION_INVALID,
    RegistryFor,
    Worker,
    WorkerOptions,
    parse_arguments,
)

__all__ = ["capability_registry", "main"]


def capability_registry(
    transport: Transport,
    logger: StructuredLogger | None = None,
    root: Path | None = None,
    contract: str = CONTRACT_VERSION,
    environment: Mapping[str, str] | None = None,
    base: Callable[[], HandlerRegistry] = synthetic_registry,
) -> RegistryFor:
    """Return the per-connection builder a worker binds its handler table with.

    ``base`` is the platform's own table and the add-ons are added *to* it rather than
    substituted for it: a worker that lost ``succeed`` would break every P0-A scenario
    while looking like a working host. It is a factory rather than a registry because
    ``HandlerRegistry.register`` refuses to rebind a name, so a reopen must start from a
    fresh table rather than from the one the previous connection's add-ons are already in.

    Add-on discovery and the version gate run on every connection as a consequence. That is
    a cost — a reopen re-reads the directory — and it is the honest one: the alternative is
    a table whose handlers outlive the connection they were built for, which is the defect
    this whole module exists to make unrepresentable.
    """

    def build(connection: psycopg.Connection[Any]) -> HandlerRegistry:
        registry = base()
        install_addons(
            registry,
            root=root,
            contract=contract,
            invoke=bind_capabilities(DomainStore(connection), transport, logger),
            environment=environment,
        )
        return registry

    return build


def build_worker(
    config: PlatformConfig,
    options: WorkerOptions,
    logger: StructuredLogger,
    transport: Transport | None = None,
) -> Worker:
    """One add-on-hosting worker, ready to run. Separated from :func:`main` so a test can
    hold the object rather than only the exit status."""
    return Worker(
        config,
        options,
        logger,
        registry_for=capability_registry(
            SocketTransport() if transport is None else transport, logger
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve configuration, then run one add-on-hosting worker.

    Structurally identical to ``platform_core.worker.main`` and deliberately not shared with
    it: the platform entrypoint must keep working with no add-on layer present at all, and
    a common helper would put this module on its import path. `[결정]` The duplication is
    two dozen lines and the coupling it avoids is the one DP-008 D1 names.
    """
    options = parse_arguments(argv)
    try:
        config = load_config()
    except PlatformError as invalid:
        StructuredLogger().error(
            "worker.configuration_invalid",
            error_class=invalid.error_class.value,
            error_summary=invalid.summary,
        )
        return EXIT_CONFIGURATION_INVALID
    logger = StructuredLogger.resolved(config.log_file, config.log_level)
    try:
        for warning in config.warnings():
            logger.warning("worker.configuration_warning", detail=warning)
        # An add-on directory that does not exist, or an installed add-on written against
        # another contract version, refuses inside the first `_open` — `AddonRefusedError`
        # is a `ConfigurationInvalidError`, so `Worker.run` already ends the process with
        # `EXIT_CONFIGURATION_INVALID` and SEC-003's rule holds without a second handler
        # here: a supervisor restart fails identically rather than eventually succeeding.
        return build_worker(config, options, logger).run()
    finally:
        logger.close()


if __name__ == "__main__":  # pragma: no cover - exercised as a process, not imported
    sys.exit(main())
