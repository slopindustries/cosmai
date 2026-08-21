"""Finding add-ons on disk and turning each one into a callable, or refusing it.

Copy-adapted verbatim from ``experiments/integrated-p0/addon_host/loading.py``
(M3 batch 3b). Discovery, the version gate, and load-by-path are all
source-independent, so nothing here changes with P1's placement.

DP-008 D2 fixes the mechanism: scan a root directory for ``addons/*/addon.toml``
and load the declared module through ``importlib.util.spec_from_file_location``,
**by path and never by module name**. A static ``import addons.something`` would
mean the platform knows an add-on exists, which is the coupling the add-on layer
removes, and ``tests/environment/test_addon_layer_direction.py`` fails the build
for it. Nothing in this module names an add-on.

Everything that can be refused is refused here, before a job exists:

* a malformed manifest, a missing entry module, or an entry attribute that is
  absent or not callable raises ``ManifestError`` — ``addon_api``'s own class,
  because what is wrong is the package;
* an add-on whose ``requires_contract`` excludes this host's ``CONTRACT_VERSION``
  raises :class:`~addon_host.errors.AddonRefusedError`, naming the add-on and both
  versions (D3);
* an add-on whose module raises while being imported is refused the same way,
  with the exception's type recorded.

**The version gate runs before the import.** An add-on written for another
contract version must not have its module body executed on the way to being
refused, or "refused at process start" would still have run arbitrary code. That
ordering is the substance of the gate rather than a detail of it.

An add-on that is simply **not installed** needs nothing from this module.
``platform_core.jobs.registry`` already contracts that an unregistered handler
name fails as ``HANDLER_UNKNOWN`` on first claim without retry, and P0-A tested
it, so the absent case is covered by not being built.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from addon_api import CONTRACT_VERSION, AddonManifest, ManifestError
from addon_api.manifest import MANIFEST_FILENAME
from addon_host.errors import AddonRefusedError

__all__ = [
    "LoadedAddon",
    "load_addon",
    "load_addons",
    "manifest_paths",
    "module_name_for",
]

#: A directory whose name starts with one of these is not an add-on. It keeps
#: ``__pycache__`` and editor droppings out of the installed set. The add-on
#: template is deliberately *not* what this guards: it lives at
#: ``addon_kit/template/``, outside discovery entirely, so a template cannot be
#: loaded as an add-on nobody installed even if this rule were removed.
IGNORED_PREFIXES: Final[tuple[str, ...]] = ("_", ".")

#: Namespace for the ``sys.modules`` key a loaded add-on is filed under. Derived
#: from the add-on's own identity so that two add-ons cannot land on one key, and
#: prefixed so that an add-on module can never occupy the name of a real
#: distribution and be found by a later ``import``.
MODULE_PREFIX: Final = "cosma_addon_"


@dataclass(frozen=True)
class LoadedAddon:
    """One add-on that passed every load-time check, and the callable it declared."""

    manifest: AddonManifest
    directory: Path
    manifest_path: Path
    module: ModuleType
    #: The attribute ``[addon].entry`` named. Its real signature is decided by
    #: ``manifest.kind`` — ``addon_api.context`` states one alias per kind — and
    #: load time can only establish that it is callable. Whichever context it is
    #: given is B0.3's to build, and needs ``domain``.
    entry: Callable[..., Any]

    @property
    def identity(self) -> str:
        """``addon_id@addon_version``, as Raw provenance and results record it (D8)."""
        return f"{self.manifest.addon_id}@{self.manifest.addon_version}"


def manifest_paths(root: Path) -> tuple[Path, ...]:
    """Every ``<root>/*/addon.toml`` there is, in a stable order.

    An absent root, an empty root, and a directory holding no manifest all yield
    nothing rather than an error. DP-008 D8 makes the directory the installed set,
    so "no add-on is installed" is a state and not a fault; a host with none must
    start, because the platform's own synthetic handlers do not depend on any.
    """
    if not root.is_dir():
        return ()
    found: list[Path] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith(IGNORED_PREFIXES):
            continue
        manifest = entry / MANIFEST_FILENAME
        if manifest.is_file():
            found.append(manifest)
    return tuple(found)


def module_name_for(manifest: AddonManifest) -> str:
    """The ``sys.modules`` key for this add-on's entry module.

    Not the add-on's own module name and not importable as one: the name exists so
    that tracebacks, ``dataclasses``, and anything else consulting
    ``sys.modules`` find the module they are executing, which is what the standard
    load-by-path recipe registers it for.
    """
    stem = "".join(character if character.isalnum() else "_" for character in manifest.addon_id)
    return f"{MODULE_PREFIX}{stem}_{manifest.entry_module}"


def load_addon(manifest_path: Path, contract: str = CONTRACT_VERSION) -> LoadedAddon:
    """Read one ``addon.toml``, gate it, import its module, and check its entry."""
    manifest = AddonManifest.load(manifest_path)
    directory = manifest_path.parent
    _require_supported_contract(manifest, manifest_path, contract)
    module = _import_by_path(manifest, directory, manifest_path)
    try:
        entry = _require_entry(manifest, module, manifest_path)
    except ManifestError:
        # A refused add-on leaves nothing of itself behind, the same way one whose
        # module failed to execute does not. The module ran; the package is still
        # refused, so its ``sys.modules`` entry is not something a later import
        # should be able to find.
        sys.modules.pop(module_name_for(manifest), None)
        raise
    return LoadedAddon(
        manifest=manifest,
        directory=directory,
        manifest_path=manifest_path,
        module=module,
        entry=entry,
    )


def load_addons(root: Path, contract: str = CONTRACT_VERSION) -> tuple[LoadedAddon, ...]:
    """Load every add-on under ``root``, or refuse at the first one that fails.

    Unlike ``platform_core.config.load_config``, which collects every problem
    before raising, this stops at the first refusal. The reason is that loading is
    not independent: importing a module runs its code, and continuing past a
    refused add-on in order to collect a second opinion would run add-on code the
    host has already decided not to run.
    """
    return tuple(load_addon(path, contract) for path in manifest_paths(root))


def _require_supported_contract(
    manifest: AddonManifest, manifest_path: Path, contract: str
) -> None:
    """Refuse an add-on written against a contract version this host is not (D3)."""
    if manifest.supports(contract):
        return
    raise AddonRefusedError(
        f"add-on {manifest.addon_id}@{manifest.addon_version} at {manifest_path} requires "
        f"add-on contract {manifest.requires_contract.text!r}, but this host implements "
        f"{contract}; install a version of the add-on that accepts {contract}, or upgrade "
        "the host",
        {
            "addon_id": manifest.addon_id,
            "addon_version": manifest.addon_version,
            "requires_contract": manifest.requires_contract.text,
            "host_contract_version": contract,
            "manifest": str(manifest_path),
        },
    )


def _import_by_path(manifest: AddonManifest, directory: Path, where: Path) -> ModuleType:
    """Execute the add-on's entry module, located by path rather than by name.

    One file, ``<directory>/<entry_module>.py``. A package form was left out
    because the manifest's ``entry`` grammar admits a single identifier, so an
    add-on cannot name a submodule and nothing in the contract needs one; adding
    ``__init__.py`` handling would be an abstraction reducing no named
    uncertainty. Recorded in the B0.1 handoff as a limitation on add-on authors.
    """
    path = directory / f"{manifest.entry_module}.py"
    if not path.is_file():
        raise ManifestError(
            f"{where}: [addon].entry names module {manifest.entry_module!r}, "
            f"but {path.name} is not a file in {directory}"
        )
    name = module_name_for(manifest)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ManifestError(f"{where}: {path} cannot be loaded as a Python module")
    module = importlib.util.module_from_spec(spec)
    # Registered before execution, as the load-by-path recipe requires, so the
    # module can be found while its own body is still running.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        # A half-executed module must not stay visible to a later import.
        sys.modules.pop(name, None)
        raise AddonRefusedError(
            f"add-on {manifest.addon_id}@{manifest.addon_version} at {directory} raised "
            f"{type(error).__name__} while its entry module was being imported",
            {
                "addon_id": manifest.addon_id,
                "addon_version": manifest.addon_version,
                "module": str(path),
                "exception_type": type(error).__name__,
                "exception_message": str(error),
            },
        ) from error
    return module


def _require_entry(
    manifest: AddonManifest, module: ModuleType, where: Path
) -> Callable[..., Any]:
    """Refuse a manifest pointing at an entry the module does not provide.

    A missing or non-callable entry is a malformed package, not a runtime failure:
    the manifest promised something the code does not have, and the only moment
    that can be discovered cheaply is now. Finding out at job time would spend an
    attempt on a packaging mistake.
    """
    attribute = manifest.entry_attribute
    if not hasattr(module, attribute):
        raise ManifestError(
            f"{where}: [addon].entry names {manifest.entry!r}, but "
            f"{manifest.entry_module}.py defines no {attribute!r}"
        )
    # Typed as ``object`` so that ``callable`` is what narrows it: an unannotated
    # ``getattr`` is ``Any``, and ``Any`` would satisfy the return type without the
    # check having proved anything.
    entry: object = getattr(module, attribute)
    if not callable(entry):
        raise ManifestError(
            f"{where}: [addon].entry names {manifest.entry!r}, but {attribute!r} is a "
            f"{type(entry).__name__} rather than something callable"
        )
    return entry
