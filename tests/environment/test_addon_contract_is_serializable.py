"""Guard: everything the add-on boundary carries as data survives JSON.

DP-008 chose in-process add-ons and rejected subprocess isolation on cost, not on
merit — and recorded that the option stays open only if the contract is written in
serializable shapes, so that moving later is a change to ``addon_host`` rather
than a rewrite of the contract every add-on was written against.

That is a promise about future work, which is the kind that quietly stops being
true. So it is tested twice:

- every type in ``addon_api.SERIALIZABLE`` round-trips through real JSON;
- the registry itself covers every boundary dataclass in the package, so adding
  one without a JSON form fails here instead of being discovered at the moment
  someone tries to collect the promise.

The contexts are excluded by name because they carry callables. Under subprocess
isolation those become the request surface; what has to cross a pipe is the data
they pass, which is exactly what the registry lists.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import addon_api
from addon_api import (
    CollectOutcome,
    FetchResponse,
    Limits,
    NormalizedResult,
    NormalizeOutcome,
    RawItem,
    SnapshotItem,
)
from addon_api import context as context_module
from addon_api import results as results_module

#: One populated instance per boundary type. Every optional field is set to a
#: non-default value: a round-trip that only ever sees defaults would pass while
#: dropping a field on the floor.
SAMPLES: dict[type, Any] = {
    RawItem: RawItem(
        item_key="item-1",
        payload=b"\x00\x01\xfe\xff not ascii",
        content_type="application/json",
        envelope_ref="envelope-7",
        notes={"page": 3},
    ),
    SnapshotItem: SnapshotItem(
        item_key="item-1",
        payload=b"\x00sealed",
        content_type="application/json",
    ),
    NormalizedResult: NormalizedResult(
        source_item_key="item-1",
        body={"name": "value", "count": 2},
        notes={"rule": "baseline"},
    ),
    CollectOutcome: CollectOutcome(items_emitted=5, more_available=True, notes={"pages": 2}),
    NormalizeOutcome: NormalizeOutcome(results_emitted=4, skipped=1, notes={"ambiguous": 1}),
    Limits: Limits(
        connect_timeout_s=2.5,
        read_timeout_s=10.0,
        max_response_bytes=1_048_576,
        max_redirects=3,
        max_pages=10,
        max_records=1000,
    ),
    FetchResponse: FetchResponse(
        endpoint_ref="items",
        status=200,
        headers={"content-type": "application/json"},
        body=b"\x00\x01binary",
        envelope_ref="envelope-7",
        retrieved_at="2026-08-18T00:00:00Z",
    ),
}


def boundary_dataclasses() -> set[type]:
    """Every dataclass defined in the two boundary modules, minus the contexts."""
    found: set[type] = set()
    for module in (context_module, results_module):
        for name in dir(module):
            if name.startswith("_"):
                continue
            candidate = getattr(module, name)
            if not isinstance(candidate, type) or not dataclasses.is_dataclass(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue  # re-exported from the other module; counted once
            if name.endswith("Context"):
                continue
            found.add(candidate)
    return found


def test_every_boundary_type_round_trips_through_real_json() -> None:
    for boundary_type in addon_api.SERIALIZABLE:
        original = SAMPLES[boundary_type]
        encoded = json.dumps(original.to_json())
        restored = boundary_type.from_json(json.loads(encoded))
        assert restored == original, boundary_type.__name__


def test_the_registry_covers_every_boundary_dataclass() -> None:
    """Adding a type without a JSON form must fail here, not later."""
    registered = set(addon_api.SERIALIZABLE)
    declared = boundary_dataclasses()
    missing = declared - registered
    assert not missing, f"not in addon_api.SERIALIZABLE: {sorted(t.__name__ for t in missing)}"
    stale = registered - declared
    assert not stale, f"listed but not a boundary dataclass: {sorted(t.__name__ for t in stale)}"


def test_every_registered_type_has_a_populated_sample() -> None:
    missing = set(addon_api.SERIALIZABLE) - set(SAMPLES)
    assert not missing, f"no sample instance: {sorted(t.__name__ for t in missing)}"


def test_binary_payloads_survive_rather_than_being_assumed_textual() -> None:
    """The reason the contract carries an explicit JSON form at all.

    ``dataclasses.asdict`` would produce ``bytes``, which ``json.dumps`` refuses.
    The failure would surface only once a real source returned something that is
    not valid UTF-8 — so the sample payloads above are deliberately not text.
    """
    item = SAMPLES[RawItem]
    assert b"\xfe\xff" in item.payload
    restored = RawItem.from_json(json.loads(json.dumps(item.to_json())))
    assert restored.payload == item.payload


def test_a_context_is_not_serializable_and_is_not_claimed_to_be() -> None:
    """The exclusion is deliberate, so it is asserted rather than left implicit."""
    for name in ("CollectContext", "ImportContext", "NormalizeContext"):
        context_type = getattr(addon_api, name)
        assert context_type not in addon_api.SERIALIZABLE
        assert not hasattr(context_type, "to_json"), name
