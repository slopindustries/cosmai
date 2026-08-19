"""The add-on contract. Both sides import this; neither side imports the other.

``addon_host`` depends on ``platform_core``, ``domain``, and this package.
Add-ons under ``addons/`` depend on this package and nothing else local.
``platform_core`` depends on none of them. That direction is the whole of
DP-008 D1 and ``tests/environment/test_addon_layer_direction.py`` enforces it,
which is what keeps "loosely coupled" a fact rather than an intention.

This package therefore imports nothing from the project. If it ever needs to, the
thing it needs has been put in the wrong place.
"""

from __future__ import annotations

from addon_api.context import (
    CollectContext,
    CollectEntry,
    FetchResponse,
    ImportContext,
    ImportEntry,
    Limits,
    NormalizeContext,
    NormalizeEntry,
    OpenedInput,
)
from addon_api.errors import (
    AddonConfigInvalid,
    AddonError,
    AddonOutputInvalid,
    AddonPermanent,
    AddonTransient,
)
from addon_api.manifest import (
    CONTRACT_VERSION,
    FIELD_TYPES,
    KINDS,
    AddonManifest,
    ConfigField,
    ConfigValidationError,
    ContractVersion,
    Declarations,
    Kind,
    ManifestError,
    VersionRange,
    validate_config,
)
from addon_api.results import (
    BoundaryData,
    CollectOutcome,
    NormalizedResult,
    NormalizeOutcome,
    RawItem,
    SnapshotItem,
)

#: Every type that crosses the boundary as data, as opposed to as a capability.
#:
#: ``tests/environment/test_addon_contract_is_serializable.py`` round-trips each
#: one through JSON and separately asserts this tuple covers every boundary
#: dataclass in the package. Adding a type without a JSON form therefore fails a
#: test rather than quietly closing off the subprocess isolation DP-008 kept
#: reachable. The contexts are excluded because they carry callables; under
#: subprocess isolation those become the request surface and the data they pass
#: is exactly what is listed here.
SERIALIZABLE: tuple[type[BoundaryData], ...] = (
    RawItem,
    SnapshotItem,
    NormalizedResult,
    CollectOutcome,
    NormalizeOutcome,
    Limits,
    FetchResponse,
    OpenedInput,
)

__all__ = [
    "CONTRACT_VERSION",
    "FIELD_TYPES",
    "KINDS",
    "SERIALIZABLE",
    "AddonConfigInvalid",
    "AddonError",
    "AddonManifest",
    "AddonOutputInvalid",
    "AddonPermanent",
    "AddonTransient",
    "BoundaryData",
    "CollectContext",
    "CollectEntry",
    "CollectOutcome",
    "ConfigField",
    "ConfigValidationError",
    "ContractVersion",
    "Declarations",
    "FetchResponse",
    "ImportContext",
    "ImportEntry",
    "OpenedInput",
    "Kind",
    "Limits",
    "ManifestError",
    "NormalizeContext",
    "NormalizeEntry",
    "NormalizeOutcome",
    "NormalizedResult",
    "RawItem",
    "SnapshotItem",
    "VersionRange",
    "validate_config",
]
