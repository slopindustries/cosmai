"""Credential hygiene: the scan, and the load-time refusal it now drives.

Copy-adapted from ``experiments/integrated-p0/tests/test_addon_credential_hygiene.py``
(M3 batch 3c), split into two halves. `TestTheScanItself` carries over P0's own unit
tests of the AST walk (`executable_names`/`hygiene_violations`) — the positive control
that the scan finds a credential that is there, and the pinned false-positive P0's own
scan was built to avoid (a documentation URL in a docstring). `TestTheHostRefusesAtLoadTime`
is new: P0 never wired this scan into anything but a pytest run, and this batch promotes
it to a load-time refusal (`addon_host.loading`'s own docstring and
`addon_host.hygiene`'s explain why). It uses a synthetic add-on under `tmp_path`, the
same way `test_addon_host.py` tests every other load-time refusal, rather than P0's
filesystem-discovery-of-installed-add-ons approach — no real add-on exists in this tree
yet (M4), so there is nothing yet for that discovery mechanism to find.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from addon_host.errors import AddonRefusedError
from addon_host.hygiene import executable_names, hygiene_violations, scan_source_file
from addon_host.loading import MODULE_PREFIX, load_addons

MANIFEST_TEMPLATE = """
[addon]
id = "{addon_id}"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[declares]
hosts = ["api.example.com"]
endpoints = ["items"]
"""

CLEAN_SOURCE = '''
"""Docs: https://example.invalid/reference"""

from addon_api import CollectOutcome


def run(context):
    context.fetch("items", {})
    return CollectOutcome(items_emitted=0)
'''

#: Plants a header name a real request would carry — the thing DP-008 D4 forbids an
#: add-on's *code* from naming, whatever its docstring may cite.
OFFENDING_SOURCE = '''
def run(context):
    return context.fetch("items", {}, headers={"X-NCP-APIGW-API-KEY": "secret"})
'''

#: Marks that its module body ran, so a refused add-on's absence can be checked the same
#: way `test_addon_host.py`'s own version-gate test checks it.
MARKING_OFFENDING_SOURCE = '''
from pathlib import Path

Path(__file__).with_name("imported").write_text("yes", encoding="utf-8")


def run(context):
    return context.fetch("items", {}, headers={"X-NCP-APIGW-API-KEY": "secret"})
'''


def install(root: Path, addon_id: str, source: str) -> Path:
    package = root / addon_id
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(
        MANIFEST_TEMPLATE.format(addon_id=addon_id), encoding="utf-8"
    )
    (package / "handler.py").write_text(source, encoding="utf-8")
    return package


@pytest.fixture(autouse=True)
def unload_addon_modules() -> Iterator[None]:
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith(MODULE_PREFIX):
            del sys.modules[name]


class TestTheScanItself:
    def test_the_scan_finds_a_credential_that_is_there(self) -> None:
        planted = (
            '"""Docs: https://example.invalid/reference"""\n'
            "def run(context):\n"
            '    return context.fetch("blog", headers={"X-NCP-APIGW-API-KEY": "secret"})\n'
        )
        names = executable_names(planted)
        assert any("x-ncp-apigw" in name for name in names), "the scan read no header name"

    def test_the_scan_does_not_fire_on_a_documentation_url_in_a_docstring(self) -> None:
        documented = (
            '"""Reference: https://api.example.invalid/guide"""\n'
            "def run(context):\n"
            "    return None\n"
        )
        assert not [name for name in executable_names(documented) if "https://" in name]

    def test_explaining_why_a_credential_was_rejected_is_not_holding_one(self) -> None:
        """`credential` itself is not forbidden. P0's own scan matched it in three
        add-ons' error messages explaining *why* a request was refused."""
        source = (
            "def run(context):\n"
            "    raise Exception('the source rejected the configured credential (401)')\n"
        )
        assert hygiene_violations(source) == {}

    def test_a_clean_source_has_no_violations(self, tmp_path: Path) -> None:
        path = tmp_path / "handler.py"
        path.write_text(CLEAN_SOURCE, encoding="utf-8")
        assert scan_source_file(path) == {}

    def test_an_offending_source_names_the_rule_that_fired(self, tmp_path: Path) -> None:
        path = tmp_path / "handler.py"
        path.write_text(OFFENDING_SOURCE, encoding="utf-8")
        violations = scan_source_file(path)
        assert "x-ncp-apigw" in violations
        assert any("x-ncp-apigw-api-key" in name for name in violations["x-ncp-apigw"])


class TestTheHostRefusesAtLoadTime:
    def test_an_offending_add_on_is_refused_and_never_imported(self, tmp_path: Path) -> None:
        package = install(tmp_path, "collector.offender", MARKING_OFFENDING_SOURCE)

        with pytest.raises(AddonRefusedError) as caught:
            load_addons(tmp_path)

        assert "collector.offender" in caught.value.summary
        assert "x-ncp-apigw" in caught.value.summary
        assert not caught.value.retryable
        # The version gate's own guarantee, carried over: a refused add-on's module
        # must not have run, or "refused before a job exists" would still have run
        # arbitrary code.
        assert not (package / "imported").exists()

    def test_a_clean_add_on_loads_normally(self, tmp_path: Path) -> None:
        """The positive control. Without it the refusal above could pass against a
        scan that refuses every add-on regardless of its content."""
        install(tmp_path, "collector.clean", CLEAN_SOURCE)

        addons = load_addons(tmp_path)

        assert len(addons) == 1
        assert addons[0].manifest.addon_id == "collector.clean"

    def test_the_refusal_names_every_rule_that_fired(self, tmp_path: Path) -> None:
        multiply_offending = (
            "def run(context):\n"
            '    headers = {"X-NCP-APIGW-API-KEY": "a", "Authorization": "b"}\n'
            "    return context.fetch(\"items\", {}, headers=headers)\n"
        )
        install(tmp_path, "collector.doubly-offending", multiply_offending)

        with pytest.raises(AddonRefusedError) as caught:
            load_addons(tmp_path)

        detail = caught.value.detail.for_protected_debug()
        assert set(detail["violations"]) >= {"x-ncp-apigw", "authorization"}
