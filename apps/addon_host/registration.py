"""Putting a loaded add-on into the handler table the platform already dispatches on.

Copy-adapted verbatim from ``experiments/integrated-p0/addon_host/registration.py``
(M3 batch 3b). ``platform_core.jobs.registry.HandlerRegistry`` is unchanged from
M1, so the seam this module plugs into is exactly the one P0 built against.

DP-008 D2 ends with "add-ons register into the existing ``HandlerRegistry`` at
process start", and that sentence is the reason this layer is small.
``platform_core.jobs.registry`` is unchanged: a name in a job row, a callable in
this process, an unregistered name failing as ``HANDLER_UNKNOWN`` on first claim
without retry. The add-on layer supplies callables to a table that already exists
rather than a second dispatch mechanism beside it.

Two things happen at the moment of registration.

**A name is chosen.** It is ``addon:<addon_id>``, namespaced. Neither DP-008 nor
``addon_api`` fixes the spelling, and the namespace is this work package's choice
for one reason that is not cosmetic: ``HandlerRegistry.register`` refuses to
rebind a name, so an add-on whose id happened to be ``succeed`` would otherwise
collide with a platform handler and take a whole process down at start. Recorded
in the B0.1 handoff as a decision the record should confirm.

**Failures are translated.** Every call into add-on code is wrapped by
``addon_host.errors.translated_failures``, so what leaves a handler is always a
``PlatformError`` whose class decides retryability. That wrapper is the only
reason an add-on can be forbidden from importing ``platform_core.errors``.

What is **not** here is the capability layer. Turning a ``JobContext`` into the
``CollectContext``, ``ImportContext``, or ``NormalizeContext`` the add-on's kind
expects needs the source row, the stored configuration, and the cursor that
DP-008 D5 gives ``domain``, and ``domain`` is B0.2. :data:`Invoke` is that seam.
Until it is filled, :func:`capabilities_not_bound` makes an add-on job fail
permanently and say exactly which layer is missing — a stated failure rather than
a handler that appears to work.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Protocol

from addon_api import CONTRACT_VERSION, AddonManifest
from addon_host.errors import AddonRefusedError, translated_failures
from addon_host.loading import LoadedAddon, load_addons
from addon_host.settings import addon_root
from platform_core.errors import PlatformPermanentError
from platform_core.jobs.registry import Handler, HandlerRegistry, JobContext

__all__ = [
    "HANDLER_PREFIX",
    "Invoke",
    "capabilities_not_bound",
    "handler_name",
    "install_addons",
    "make_handler",
    "register_addons",
]

#: What every add-on's handler name begins with, so the add-on namespace and the
#: platform's own handler names cannot collide.
HANDLER_PREFIX: Final = "addon:"


class Invoke(Protocol):
    """Build the context this add-on's kind expects, and call its entry point.

    The seam B0.3 fills. It is stated as a protocol rather than left implicit
    because it is the whole of what ``addon_host`` still owes: everything on either
    side of it — discovery, the version gate, registration, error translation — is
    finished, and what remains needs ``domain``.
    """

    def __call__(self, addon: LoadedAddon, context: JobContext) -> None: ...


def handler_name(manifest: AddonManifest) -> str:
    """The ``job.handler`` value that runs this add-on.

    Derived from ``addon_id`` alone, which is what DP-008 D5 puts on the source
    row, so the platform can name the handler for a source without consulting
    anything else. The kind is not part of the name: an add-on has exactly one, so
    including it would add a second place for the same fact to be recorded.
    """
    return f"{HANDLER_PREFIX}{manifest.addon_id}"


def capabilities_not_bound(addon: LoadedAddon, context: JobContext) -> None:
    """Refuse the job, naming the layer that is missing.

    B0.1 builds discovery, loading, the version gate, registration, and error
    translation. It deliberately builds no capability, because every capability
    DP-008 D4 grants reads or writes something ``domain`` owns. A default that
    silently did nothing and reported success would make an unfinished host look
    like a working one.
    """
    raise PlatformPermanentError(
        f"add-on {addon.identity} is installed and registered, but this host has no "
        f"capability layer bound for kind {addon.manifest.kind!r}; B0.3 supplies it",
        {
            "addon_id": addon.manifest.addon_id,
            "addon_version": addon.manifest.addon_version,
            "kind": addon.manifest.kind,
            "job_id": str(context.job_id),
        },
    )


def make_handler(addon: LoadedAddon, invoke: Invoke = capabilities_not_bound) -> Handler:
    """Wrap one add-on as a platform handler.

    The wrapper is two lines and both are load-bearing: ``invoke`` is the only path
    into add-on code, and ``translated_failures`` is the only path out of it.
    """

    def handler(context: JobContext) -> None:
        with translated_failures(addon.manifest):
            invoke(addon, context)

    return handler


def register_addons(
    registry: HandlerRegistry,
    addons: Iterable[LoadedAddon],
    invoke: Invoke = capabilities_not_bound,
) -> tuple[str, ...]:
    """Bind every add-on's handler name, and return the names in bound order.

    Two failure shapes meet here and only one of them is the registry's.

    A name already bound by something *outside* this call — a platform handler, or
    a previous ``install_addons`` over the same root — raises ``ValueError`` out of
    ``HandlerRegistry.register``, which is that module's contract and not ours to
    restate.

    Two add-ons in one installed set declaring the same ``[addon].id`` is different:
    it is a defect in the directory, discovered at process start, and it would
    otherwise surface as the same bare ``ValueError`` — not a ``PlatformError``, so
    an entrypoint catching ``PlatformError`` would let it through as a traceback.
    It is refused before anything is bound, naming both directories, so an operator
    is told which two to look at rather than which one lost.
    """
    ordered = tuple(addons)
    _require_distinct_ids(ordered)
    names: list[str] = []
    for addon in ordered:
        name = handler_name(addon.manifest)
        registry.register(name, make_handler(addon, invoke))
        names.append(name)
    return tuple(names)


def _require_distinct_ids(addons: tuple[LoadedAddon, ...]) -> None:
    """Refuse an installed set in which two directories claim one identity.

    ``addon_id`` is the identity DP-008 D8 records in Raw provenance and result
    lineage, so two add-ons sharing one would make that record ambiguous after the
    fact — which is worse than refusing to start.
    """
    seen: dict[str, LoadedAddon] = {}
    for addon in addons:
        addon_id = addon.manifest.addon_id
        first = seen.get(addon_id)
        if first is None:
            seen[addon_id] = addon
            continue
        raise AddonRefusedError(
            f"add-on id {addon_id!r} is declared by two directories, "
            f"{first.directory} and {addon.directory}; an installed set cannot "
            "contain one identity twice",
            {
                "addon_id": addon_id,
                "directories": [str(first.directory), str(addon.directory)],
                "versions": [first.manifest.addon_version, addon.manifest.addon_version],
            },
        )


def install_addons(
    registry: HandlerRegistry,
    root: Path | None = None,
    contract: str = CONTRACT_VERSION,
    invoke: Invoke = capabilities_not_bound,
    environment: Mapping[str, str] | None = None,
) -> tuple[LoadedAddon, ...]:
    """Everything a process does at start: resolve the root, load, register.

    One call so that the sequence lives in one place rather than in each
    entrypoint, and so that a process cannot register add-ons it never gated.
    """
    addons = load_addons(addon_root(environment) if root is None else root, contract)
    register_addons(registry, addons, invoke)
    return addons
