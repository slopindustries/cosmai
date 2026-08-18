"""``addon.toml``: what an add-on declares about itself, and how it is read.

The manifest is the whole of an add-on's metadata. There is no install table
(DP-008 D8): what is in the directory is what is installed, and the source row
holds the operator's approved configuration. A second store would be a second
truth that can drift from the first.

Two error hierarchies meet here and they are kept apart on purpose.
:class:`ManifestError` means the package is malformed and is raised while
loading, before any job runs. :mod:`addon_api.errors` covers failures an add-on
raises while running. Conflating them would let a packaging mistake look like a
transient source problem and be retried.

The version-range parser handles ``>=``, ``>``, ``<=``, ``<``, and ``==`` over a
``MAJOR.MINOR`` contract version, joined by commas. That is deliberately less
than PEP 440. A full implementation, or a dependency providing one, would be an
abstraction reducing no named uncertainty — AGENTS.md's test — and the contract
version is a two-number sequence this project controls end to end.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NamedTuple, Self, get_args

#: The contract this package implements. Raised when a change would break an
#: add-on written against the previous value; see DP-008 D3.
CONTRACT_VERSION = "1.0"

Kind = Literal["collector", "importer", "normalizer"]
KINDS: tuple[Kind, ...] = get_args(Kind)

FieldType = Literal["string", "integer", "boolean"]
FIELD_TYPES: tuple[FieldType, ...] = get_args(FieldType)

MANIFEST_FILENAME = "addon.toml"

_ADDON_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_ENTRY = re.compile(r"^(?P<module>[A-Za-z_][A-Za-z0-9_]*)\:(?P<attr>[A-Za-z_][A-Za-z0-9_]*)$")
_COMPARATOR = re.compile(r"^(?P<op>>=|<=|==|>|<)\s*(?P<version>\d+\.\d+)$")


class ManifestError(Exception):
    """The add-on package is malformed. Raised at load time, never at job time."""


class ConfigValidationError(Exception):
    """Stored configuration does not satisfy the add-on's declared schema.

    Carries the offending field names so an operator surface can mark them
    individually instead of rejecting the whole form with one message.
    """

    def __init__(self, summary: str, fields: Sequence[str]) -> None:
        super().__init__(summary)
        self.summary = summary
        self.fields = tuple(fields)


class ContractVersion(NamedTuple):
    """``MAJOR.MINOR``. Ordered, so a range check is a tuple comparison."""

    major: int
    minor: int

    @classmethod
    def parse(cls, text: str) -> Self:
        match = re.fullmatch(r"(\d+)\.(\d+)", text.strip())
        if match is None:
            raise ManifestError(f"contract version must be MAJOR.MINOR, got {text!r}")
        return cls(int(match.group(1)), int(match.group(2)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


@dataclass(frozen=True)
class VersionRange:
    """A comma-joined comparator list, evaluated as a conjunction."""

    text: str
    comparators: tuple[tuple[str, ContractVersion], ...]

    @classmethod
    def parse(cls, text: str) -> Self:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if not parts:
            raise ManifestError("requires_contract must not be empty")
        comparators: list[tuple[str, ContractVersion]] = []
        for part in parts:
            match = _COMPARATOR.fullmatch(part)
            if match is None:
                raise ManifestError(
                    f"requires_contract clause {part!r} is not a comparator over MAJOR.MINOR; "
                    "use >=, >, <=, <, or =="
                )
            comparators.append((match.group("op"), ContractVersion.parse(match.group("version"))))
        return cls(text=text, comparators=tuple(comparators))

    def matches(self, version: ContractVersion) -> bool:
        for op, bound in self.comparators:
            match op:
                case ">=":
                    ok = version >= bound
                case ">":
                    ok = version > bound
                case "<=":
                    ok = version <= bound
                case "<":
                    ok = version < bound
                case _:
                    ok = version == bound
            if not ok:
                return False
        return True


@dataclass(frozen=True)
class ConfigField:
    """One value an operator supplies for a source.

    ``secret`` is the whole of DP-008 D6's mechanism. A field marked secret is
    written to the repository-external secret store and never to the source row's
    configuration; the host refuses to store its value, so an add-on cannot
    receive it even by mistake.
    """

    name: str
    type: FieldType = "string"
    required: bool = True
    secret: bool = False
    label: str = ""
    help: str = ""

    @classmethod
    def from_toml(cls, data: Mapping[str, Any], where: str) -> Self:
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestError(f"{where}: a config field needs a non-empty name")
        field_type = data.get("type", "string")
        if field_type not in FIELD_TYPES:
            raise ManifestError(
                f"{where}: field {name!r} has type {field_type!r}; "
                f"expected one of {', '.join(FIELD_TYPES)}"
            )
        secret = bool(data.get("secret", False))
        if secret and field_type != "string":
            raise ManifestError(f"{where}: secret field {name!r} must be a string")
        return cls(
            name=name,
            type=field_type,
            required=bool(data.get("required", True)),
            secret=secret,
            label=str(data.get("label", "")),
            help=str(data.get("help", "")),
        )


@dataclass(frozen=True)
class Declarations:
    """What the add-on says it needs. Not what it gets.

    The operator approves these into the source row's outbound profile before
    they become permission. An add-on cannot widen its own allowlist, so this
    block is a request the host reads when presenting a source for approval.
    """

    hosts: tuple[str, ...] = ()
    endpoints: tuple[str, ...] = ()
    streams: tuple[str, ...] = ()
    needs_credential: bool = False

    @classmethod
    def from_toml(cls, data: Mapping[str, Any], where: str) -> Self:
        def string_list(key: str) -> tuple[str, ...]:
            raw = data.get(key, [])
            if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
                raise ManifestError(f"{where}: [declares].{key} must be a list of strings")
            return tuple(raw)

        return cls(
            hosts=string_list("hosts"),
            endpoints=string_list("endpoints"),
            streams=string_list("streams"),
            needs_credential=bool(data.get("needs_credential", False)),
        )


@dataclass(frozen=True)
class AddonManifest:
    """A parsed, validated ``addon.toml``."""

    addon_id: str
    addon_version: str
    kind: Kind
    entry: str
    requires_contract: VersionRange
    config_schema_version: str
    config_schema: tuple[ConfigField, ...] = ()
    declares: Declarations = field(default_factory=Declarations)
    output_contract_version: str | None = None

    @property
    def entry_module(self) -> str:
        match = _ENTRY.fullmatch(self.entry)
        assert match is not None  # validated during parsing
        return match.group("module")

    @property
    def entry_attribute(self) -> str:
        match = _ENTRY.fullmatch(self.entry)
        assert match is not None
        return match.group("attr")

    def secret_fields(self) -> tuple[ConfigField, ...]:
        return tuple(item for item in self.config_schema if item.secret)

    def supports(self, contract: str = CONTRACT_VERSION) -> bool:
        return self.requires_contract.matches(ContractVersion.parse(contract))

    @classmethod
    def parse(cls, text: str, where: str = MANIFEST_FILENAME) -> Self:
        try:
            document = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            raise ManifestError(f"{where}: not valid TOML: {error}") from error
        return cls.from_document(document, where)

    @classmethod
    def load(cls, path: Path) -> Self:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ManifestError(f"{path}: cannot be read: {error}") from error
        return cls.parse(text, where=str(path))

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> Self:
        addon = document.get("addon")
        if not isinstance(addon, Mapping):
            raise ManifestError(f"{where}: missing the [addon] table")

        def required_string(key: str) -> str:
            value = addon.get(key)
            if not isinstance(value, str) or not value:
                raise ManifestError(f"{where}: [addon].{key} is required and must be a string")
            return value

        addon_id = required_string("id")
        if _ADDON_ID.fullmatch(addon_id) is None:
            raise ManifestError(
                f"{where}: [addon].id {addon_id!r} must be lowercase, "
                "starting with a letter, separated by '.', '_', or '-'"
            )

        kind = addon.get("kind")
        if kind not in KINDS:
            raise ManifestError(
                f"{where}: [addon].kind is {kind!r}; expected one of {', '.join(KINDS)}"
            )

        entry = required_string("entry")
        if _ENTRY.fullmatch(entry) is None:
            raise ManifestError(f"{where}: [addon].entry {entry!r} must read as 'module:callable'")

        config = document.get("config")
        if config is not None and not isinstance(config, Mapping):
            raise ManifestError(f"{where}: [config] must be a table")
        config_map: Mapping[str, Any] = config if isinstance(config, Mapping) else {}
        schema_version = config_map.get("schema_version", "1")
        if not isinstance(schema_version, str) or not schema_version:
            raise ManifestError(f"{where}: [config].schema_version must be a non-empty string")

        raw_fields = config_map.get("field", [])
        if not isinstance(raw_fields, list):
            raise ManifestError(f"{where}: [[config.field]] must be a list of tables")
        parsed_fields: list[ConfigField] = []
        for item in raw_fields:
            if not isinstance(item, Mapping):
                raise ManifestError(
                    f"{where}: [[config.field]] entries must be tables, got {type(item).__name__}"
                )
            parsed_fields.append(ConfigField.from_toml(item, where))
        fields = tuple(parsed_fields)
        names = [item.name for item in fields]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ManifestError(f"{where}: duplicate config field names: {', '.join(duplicates)}")

        declares_raw = document.get("declares", {})
        if not isinstance(declares_raw, Mapping):
            raise ManifestError(f"{where}: [declares] must be a table")
        declares = Declarations.from_toml(declares_raw, where)

        output_version = addon.get("output_contract_version")
        if output_version is not None and not isinstance(output_version, str):
            raise ManifestError(f"{where}: [addon].output_contract_version must be a string")

        manifest = cls(
            addon_id=addon_id,
            addon_version=required_string("version"),
            kind=kind,
            entry=entry,
            requires_contract=VersionRange.parse(required_string("requires_contract")),
            config_schema_version=schema_version,
            config_schema=fields,
            declares=declares,
            output_contract_version=output_version,
        )
        _check_kind_consistency(manifest, where)
        return manifest


def _check_kind_consistency(manifest: AddonManifest, where: str) -> None:
    """Refuse declarations a kind's capabilities cannot honour.

    A normalizer that declares a host has misunderstood what it will be given,
    and finding that out at load time is better than finding it out when an add-on
    reaches for a ``fetch`` its context does not carry.
    """
    if manifest.kind == "normalizer":
        if manifest.declares.hosts or manifest.declares.endpoints:
            raise ManifestError(
                f"{where}: a normalizer receives no network capability, "
                "so [declares].hosts and [declares].endpoints must be empty"
            )
        if manifest.declares.needs_credential:
            raise ManifestError(
                f"{where}: a normalizer receives no credential; its input is a sealed snapshot"
            )
        if manifest.declares.streams:
            raise ManifestError(
                f"{where}: a normalizer holds no cursor, so [declares].streams must be empty"
            )
        if manifest.output_contract_version is None:
            raise ManifestError(
                f"{where}: a normalizer must declare [addon].output_contract_version"
            )
    else:
        if manifest.output_contract_version is not None:
            raise ManifestError(
                f"{where}: only a normalizer declares an output contract version"
            )
    if manifest.kind == "importer" and manifest.declares.hosts:
        raise ManifestError(
            f"{where}: an importer receives no network capability, "
            "so [declares].hosts must be empty"
        )


def validate_config(
    schema: Sequence[ConfigField], values: Mapping[str, Any]
) -> dict[str, Any]:
    """Check stored configuration against a declared schema and return it coerced.

    Two separate refusals, and the second is the load-bearing one:

    - a required field missing, an unknown field present, or a value of the wrong
      type is a configuration error the operator can fix;
    - a **secret** field appearing here at all is refused regardless of its value.
      Stored configuration is the source row, and a secret in the source row is
      exactly what ``p0-security.md`` forbids. A caller that reaches this with a
      token in hand has already made the mistake; refusing here means it does not
      also get persisted.
    """
    declared = {item.name: item for item in schema}
    problems: list[str] = []
    offending: list[str] = []

    for name in values:
        if name not in declared:
            problems.append(f"{name!r} is not declared by this add-on")
            offending.append(name)
        elif declared[name].secret:
            problems.append(f"{name!r} is a secret field and must not be stored as configuration")
            offending.append(name)

    coerced: dict[str, Any] = {}
    for name, spec in declared.items():
        if spec.secret:
            continue
        if name not in values:
            if spec.required:
                problems.append(f"{name!r} is required")
                offending.append(name)
            continue
        value = values[name]
        match spec.type:
            case "integer":
                ok = isinstance(value, int) and not isinstance(value, bool)
            case "boolean":
                ok = isinstance(value, bool)
            case _:
                ok = isinstance(value, str)
        if not ok:
            problems.append(f"{name!r} must be a {spec.type}")
            offending.append(name)
        else:
            coerced[name] = value

    if problems:
        raise ConfigValidationError("; ".join(problems), sorted(set(offending)))
    return coerced
