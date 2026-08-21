"""The data that crosses the add-on boundary, and its JSON form.

Every type here carries an explicit ``to_json``/``from_json`` pair rather than
relying on ``dataclasses.asdict``. Two reasons, and both are about keeping
DP-008's subprocess option open:

- ``payload`` is ``bytes``, which JSON has no representation for. Base64 is a
  decision, and a decision belongs in the contract rather than in whichever
  caller happens to serialize first.
- An explicit pair is testable. ``tests/environment/test_addon_contract_is_serializable.py``
  round-trips every type in ``addon_api.SERIALIZABLE`` and separately asserts that
  registry covers every boundary dataclass in the package, so "the contract stays
  serializable" is a test rather than an intention.

The capabilities in :mod:`addon_api.context` are callables and are not
serializable — under subprocess isolation they become the request/response
surface. What has to survive that change is the data they carry, which is
everything in this module.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, Self, runtime_checkable


@runtime_checkable
class BoundaryData(Protocol):
    """What every boundary data type provides, stated so the registry can be typed.

    Written as a Protocol rather than a base class on purpose: inheritance would
    put a shared parent in the contract, and an add-on author would then have one
    more thing to know about. Structural typing gets the same guarantee for free
    and keeps each type readable on its own.
    """

    def to_json(self) -> dict[str, Any]: ...

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self: ...


def _decode_payload(value: object, where: str) -> bytes:
    if not isinstance(value, str):
        raise TypeError(f"{where}: payload must be a base64 string, got {type(value).__name__}")
    return base64.b64decode(value, validate=True)


def _require_str(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{where}: expected a string, got {type(value).__name__}")
    return value


def _require_int(value: object, where: str) -> int:
    # bool is an int in Python and would silently pass; a count of `True` is a defect.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{where}: expected an integer, got {type(value).__name__}")
    return value


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{where}: expected an object, got {type(value).__name__}")
    return {_require_str(key, where): item for key, item in value.items()}


@dataclass(frozen=True)
class RawItem:
    """One observation an add-on carved out of what it was given.

    ``payload`` is the add-on's extraction and ``envelope_ref`` points at the
    lossless artifact it came from — the response or file the platform recorded
    before the add-on saw it. Keeping both is what lets a later reader check the
    extraction rather than trust it.

    ``item_key`` is identity *within one source*. The platform does not interpret
    it and does not require it to be unique on its own; what duplicate and
    changed-content policy it feeds is a P0-B contract question, not a property
    fixed here.
    """

    item_key: str
    payload: bytes
    content_type: str
    envelope_ref: str | None = None
    notes: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "payload": base64.b64encode(self.payload).decode("ascii"),
            "content_type": self.content_type,
            "envelope_ref": self.envelope_ref,
            "notes": dict(self.notes),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        envelope = data.get("envelope_ref")
        return cls(
            item_key=_require_str(data["item_key"], "RawItem.item_key"),
            payload=_decode_payload(data["payload"], "RawItem"),
            content_type=_require_str(data["content_type"], "RawItem.content_type"),
            envelope_ref=(
                None if envelope is None else _require_str(envelope, "RawItem.envelope_ref")
            ),
            notes=_require_mapping(data.get("notes", {}), "RawItem.notes"),
        )


@dataclass(frozen=True)
class SnapshotItem:
    """One item read out of a sealed snapshot.

    The platform verifies the snapshot's hashes before a normalizer sees a byte,
    so an add-on receiving this can treat the bytes as already checked. It cannot
    treat them as *valid* — hash verification says the input is what was sealed,
    not that it parses.
    """

    item_key: str
    payload: bytes
    content_type: str

    def to_json(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "payload": base64.b64encode(self.payload).decode("ascii"),
            "content_type": self.content_type,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            item_key=_require_str(data["item_key"], "SnapshotItem.item_key"),
            payload=_decode_payload(data["payload"], "SnapshotItem"),
            content_type=_require_str(data["content_type"], "SnapshotItem.content_type"),
        )


@dataclass(frozen=True)
class NormalizedResult:
    """One normalized record, and the Raw item it was derived from.

    ``source_item_key`` is the lineage link the charter's exit criteria ask for.
    ``body`` is validated against the add-on's declared output contract by the
    host, not here — this package fixes the shape, and Schema 0.x is OQ-003's to
    fix.
    """

    source_item_key: str
    body: Mapping[str, Any]
    notes: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "source_item_key": self.source_item_key,
            "body": dict(self.body),
            "notes": dict(self.notes),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            source_item_key=_require_str(
                data["source_item_key"], "NormalizedResult.source_item_key"
            ),
            body=_require_mapping(data["body"], "NormalizedResult.body"),
            notes=_require_mapping(data.get("notes", {}), "NormalizedResult.notes"),
        )


@dataclass(frozen=True)
class CollectOutcome:
    """What a collector or importer reports when it returns.

    ``items_emitted`` is reported even though the host counted the ``emit_raw``
    calls itself. The host compares the two and a mismatch fails the attempt: an
    add-on that miscounts its own work is the cheapest possible signal that it is
    doing something other than what it thinks.

    ``more_available`` is a statement, not a request. Collection never triggers
    its own continuation — ``project-state.md`` §4 keeps that with the operator or
    a schedule — so this only tells the operator there is more to ask for.
    """

    items_emitted: int
    more_available: bool = False
    notes: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "items_emitted": self.items_emitted,
            "more_available": self.more_available,
            "notes": dict(self.notes),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        more = data.get("more_available", False)
        if not isinstance(more, bool):
            raise TypeError("CollectOutcome.more_available: expected a boolean")
        return cls(
            items_emitted=_require_int(data["items_emitted"], "CollectOutcome.items_emitted"),
            more_available=more,
            notes=_require_mapping(data.get("notes", {}), "CollectOutcome.notes"),
        )


@dataclass(frozen=True)
class NormalizeOutcome:
    """What a normalizer reports when it returns.

    ``skipped`` is separate from ``results_emitted`` because "this snapshot item
    produced nothing" and "this snapshot item was never looked at" are different
    claims, and only the first one is a normalizer doing its job.
    """

    results_emitted: int
    skipped: int = 0
    notes: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "results_emitted": self.results_emitted,
            "skipped": self.skipped,
            "notes": dict(self.notes),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            results_emitted=_require_int(
                data["results_emitted"], "NormalizeOutcome.results_emitted"
            ),
            skipped=_require_int(data.get("skipped", 0), "NormalizeOutcome.skipped"),
            notes=_require_mapping(data.get("notes", {}), "NormalizeOutcome.notes"),
        )
