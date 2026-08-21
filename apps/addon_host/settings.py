"""Where the add-on directory is, and what happens when the setting is wrong.

Copy-adapted from ``experiments/integrated-p0/addon_host/settings.py`` (M3 batch
3b). The only change is the default root's location: P0 sat one directory below
``experiments/integrated-p0/`` (which also holds ``platform_core`` and
``addon_api``), so its default pointed at ``.../integrated-p0/addons``; this
module sits one directory below ``apps/`` for the same reason, so the default
points at ``apps/addons`` — the plan's own default (``docs/superpowers/plans/
2026-08-21-m2-m7-batch.md`` §M3: "``COSMA_ADDON_DIR``, default ``apps/addons/``").
``ADDON_DIR_VARIABLE`` was restored to ``platform_core.config`` in this same
batch (M1 deferred it; see that module's own comment).

``COSMA_ADDON_DIR`` is DP-008 D2's one deployment knob. The root defaults to the
in-repository ``addons/`` tree and can be moved without a code change, which is
what keeps the rejected candidate 2 — out-of-repository add-ons — reachable later
as a deployment change rather than a contract rewrite.

It lives here rather than in ``platform_core.config.SETTINGS`` because DP-008 D1 says
``platform_core`` gains no new dependency on the add-on layer. One consequence is
visible and is not hidden: ``platform_core.config.unrecognized_variables`` does not
turn this name into a configuration field, so a process that sets it also reports it —
except that ``RECOGNIZED_UNUSED`` names it explicitly, so the report does not call it
"ignored" (which would be false).

The refusal rules follow ``platform_core.config``'s, for its reasons: a default
stands in for an **absent** variable and never repairs a **stated** one, so an
empty value or a path that is not a directory is refused rather than replaced by
the default. An absent variable whose default directory does not exist is not an
error at all — DP-008 D8 makes the directory the installed set, and "nothing is
installed" is an ordinary state rather than a misconfiguration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from platform_core.config import ADDON_DIR_VARIABLE
from platform_core.errors import ConfigurationInvalidError

#: DP-008 D2's deployment knob. Re-exported rather than re-declared: the name has
#: to be spelled in ``platform_core.config`` regardless, because that module's
#: unknown-variable report would otherwise call it ignored, and two spellings of one
#: setting name is exactly the drift that report exists to catch. This module still
#: owns what the value *means* — resolution, refusal, and the default — which is
#: what DP-008 D1 keeps in the add-on layer.
__all__ = ["ADDON_DIR_VARIABLE", "DEFAULT_ADDON_DIR", "addon_root"]

#: ``apps/addons``. This file sits one directory below the ``apps/`` root, which
#: is also where ``platform_core`` and ``addon_api`` live.
DEFAULT_ADDON_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "addons"


def addon_root(environment: Mapping[str, str] | None = None) -> Path:
    """The directory to scan for add-ons, or a configuration refusal.

    The directory is not required to exist when it comes from the default: the
    in-repository ``addons/`` tree is created by the first add-on, and a host with
    none installed must still start.
    """
    env = os.environ if environment is None else environment
    stated = env.get(ADDON_DIR_VARIABLE)
    if stated is None:
        return DEFAULT_ADDON_DIR
    value = stated.strip()
    if not value:
        raise _refused("is set but empty; it must state a value")
    path = Path(value).expanduser()
    if not path.is_dir():
        # Refused rather than replaced by the default. An operator who moved the
        # add-on directory and mistyped the path would otherwise get a host that
        # starts with no add-ons installed and no indication why.
        raise _refused(f"must name an existing directory, but was {value!r}")
    return path


def _refused(reason: str) -> ConfigurationInvalidError:
    """A refusal shaped like ``platform_core.config``'s, so both read alike."""
    detail: dict[str, Any] = {
        "rejected": [{"setting": ADDON_DIR_VARIABLE, "reason": reason}]
    }
    return ConfigurationInvalidError(
        f"invalid platform configuration: {ADDON_DIR_VARIABLE} {reason}", detail
    )
