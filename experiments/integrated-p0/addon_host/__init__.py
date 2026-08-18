"""The host side of the add-on contract: find add-ons, load them, refuse bad ones.

DP-008 D2 puts discovery in a directory scan rather than in an import, and the
difference is the point of the layer. A static ``import addons.something`` would
mean the platform knows an add-on exists, which is exactly the coupling the add-on
layer removes; ``tests/environment/test_addon_layer_direction.py`` fails the build
if any package names ``addons``. So this package reaches an add-on only through
``importlib.util.spec_from_file_location`` and a path, and names none of them.

The dependency direction DP-008 D1 fixes is what this package is for.
``addon_host`` may import ``platform_core``, ``addon_api``, and ``domain``; an
add-on may import ``addon_api`` and nothing else local. Everything that would
otherwise force an add-on to reach into the platform is done here instead — most
visibly the error translation in :mod:`addon_host.errors`, without which the
add-on error taxonomy would be a second spelling of the platform's rather than a
boundary.

Three refusals happen before any job runs, and none of them is a surprise at job
time:

* a manifest that is malformed, names a module that is not there, or names an
  entry attribute that is missing or not callable — ``ManifestError``, because what
  is wrong is the package;
* an add-on whose ``requires_contract`` excludes this host's ``CONTRACT_VERSION`` —
  :class:`~addon_host.errors.AddonRefusedError` at process start, naming the add-on
  and both versions, with the add-on's module never executed (D3);
* an add-on whose module raises while being imported — refused the same way, with
  the exception's type recorded.

An add-on that is **not installed** needed nothing built for it.
``platform_core.jobs.registry`` contracts that an unregistered handler name fails
as ``HANDLER_UNKNOWN`` on first claim without retry and P0-A tested it, so the
absent case is discharged by leaving it alone.

**What B0.1 stops short of.** No capability is implemented. Building a
``CollectContext``, ``ImportContext``, or ``NormalizeContext`` requires the source
row, the stored configuration, and the cursor that DP-008 D5 assigns to ``domain``,
and ``domain`` is B0.2's. The seam is :class:`addon_host.registration.Invoke`; the
default fills it with a permanent failure that names the missing layer, so an
unfinished host cannot be mistaken for a working one.
"""

from __future__ import annotations

from addon_host.errors import (
    TRANSLATIONS,
    UNEXPECTED_TRANSLATION,
    AddonRefusedError,
    translate,
    translated_failures,
)
from addon_host.loading import (
    IGNORED_PREFIXES,
    LoadedAddon,
    load_addon,
    load_addons,
    manifest_paths,
    module_name_for,
)
from addon_host.registration import (
    HANDLER_PREFIX,
    Invoke,
    capabilities_not_bound,
    handler_name,
    install_addons,
    make_handler,
    register_addons,
)
from addon_host.settings import ADDON_DIR_VARIABLE, DEFAULT_ADDON_DIR, addon_root

__all__ = [
    "ADDON_DIR_VARIABLE",
    "DEFAULT_ADDON_DIR",
    "HANDLER_PREFIX",
    "IGNORED_PREFIXES",
    "TRANSLATIONS",
    "UNEXPECTED_TRANSLATION",
    "AddonRefusedError",
    "Invoke",
    "LoadedAddon",
    "addon_root",
    "capabilities_not_bound",
    "handler_name",
    "install_addons",
    "load_addon",
    "load_addons",
    "make_handler",
    "manifest_paths",
    "module_name_for",
    "register_addons",
    "translate",
    "translated_failures",
]
