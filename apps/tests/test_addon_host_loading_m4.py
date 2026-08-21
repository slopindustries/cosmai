"""The host discovers and registers this batch's two installed add-ons.

`tests/test_addon_host.py` (M3) proves discovery, the version gate, registration, and error
translation generically, against add-ons built in `tmp_path` — DP-008 D8's own reason: a
fixture that had to be installed to be tested would be an add-on the platform ships. This
file is the complementary evidence M4 needs: that the platform's actual, installed
`apps/addons/` directory — the one this batch ships — loads and registers cleanly through
that same host machinery, with nothing synthetic standing in for either add-on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from addon_api import CONTRACT_VERSION
from addon_host.loading import load_addons
from addon_host.registration import register_addons
from domain import DomainStore
from platform_core.jobs.registry import HandlerRegistry

ADDONS_ROOT = Path(__file__).resolve().parents[1] / "addons"


class _NoTransport:
    """An importer or normalizer must never reach this. DP-024 D6 / DP-008 D4."""

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("nothing in this file should ever open a request")


def test_both_addons_are_discovered() -> None:
    loaded = load_addons(ADDONS_ROOT, CONTRACT_VERSION)
    ids = {addon.manifest.addon_id for addon in loaded}
    assert {"importer.local.jsonl", "normalizer.obf.product"} <= ids


def test_the_importer_manifest_loads_with_the_expected_kind_and_declares() -> None:
    loaded = load_addons(ADDONS_ROOT, CONTRACT_VERSION)
    importer = next(a for a in loaded if a.manifest.addon_id == "importer.local.jsonl")
    assert importer.manifest.kind == "importer"
    assert importer.manifest.declares.inputs == ("rows",)
    assert importer.manifest.declares.streams == ("rows",)


def test_the_normalizer_manifest_loads_with_the_expected_kind_and_output_contract() -> None:
    loaded = load_addons(ADDONS_ROOT, CONTRACT_VERSION)
    normalizer = next(a for a in loaded if a.manifest.addon_id == "normalizer.obf.product")
    assert normalizer.manifest.kind == "normalizer"
    assert normalizer.manifest.output_contract_version == "0.3"
    assert normalizer.manifest.declares.streams == ()


def test_both_addons_register_a_handler_without_a_database(
    domain_store: DomainStore,
) -> None:
    """Registration itself needs no database beyond `domain_store`'s own connection — this
    only proves the handler table gains both entries, not that a job against either
    succeeds; `test_importer_local_jsonl.py` and `test_normalizer_obf_product.py` carry
    that evidence."""
    from addon_host.capabilities import bind_capabilities

    registry = HandlerRegistry()
    register_addons(
        registry,
        load_addons(ADDONS_ROOT, CONTRACT_VERSION),
        bind_capabilities(domain_store, _NoTransport()),
    )

    assert "addon:importer.local.jsonl" in registry
    assert "addon:normalizer.obf.product" in registry
