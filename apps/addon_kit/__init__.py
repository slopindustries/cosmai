"""`addon_kit new <addon_id> --kind <kind> [--into DIR]`: the add-on generator.

DP-008 D4 fixes one package format shared by every add-on regardless of kind.
This package is that format's generator: it renders `addon_kit/template/` into a
new directory, substituting the kind-specific manifest declarations, handler
signature, and capability example the requested kind is granted. See
`generator`'s module docstring for the placeholder-token convention.

Imports only `addon_api`, per DP-008 D1 and
`tests/environment/test_addon_layer_direction.py`.
"""

from __future__ import annotations

from addon_kit.generator import (
    ADDON_VERSION,
    DEFAULT_ADDONS_ROOT,
    TEMPLATE_DIR,
    AddonKitError,
    new_addon,
    render_handler,
    render_manifest,
    render_readme,
)

__all__ = [
    "ADDON_VERSION",
    "DEFAULT_ADDONS_ROOT",
    "TEMPLATE_DIR",
    "AddonKitError",
    "new_addon",
    "render_handler",
    "render_manifest",
    "render_readme",
]
