"""`addon_kit`'s own tests: does a generated skeleton satisfy the contract it targets.

Copy-adapted from ``experiments/integrated-p0/tests/test_addon_kit.py`` (M3 batch 3a).
The only change is ``TestDefaultOutputDirectory``'s expectation of where
``DEFAULT_ADDONS_ROOT`` sits: P0's tree put ``addon_kit/`` inside
``experiments/integrated-p0/``, so the default pointed at
``.../integrated-p0/addons``; this tree puts ``addon_kit/`` directly under
``apps/``, so the default points at ``apps/addons`` instead — the same one
directory below ``addon_kit/`` that P0's own comment describes, at this tree's
own root. Nothing else about the assertion changes.

This stops at the contract level, on purpose. The real acceptance test for a
template — a generated add-on passing the conformance suite untouched — cannot be
written yet: that suite is M3 batch 3c's, and depends on ``addon_host``, which is
still in flight in this batch. What is checked here is everything that does not
need a host: the manifest parses and its declarations satisfy DP-008 D4's
per-kind rules, the entry attribute the manifest names actually exists and is
callable, a bad id is refused before anything is written, and an existing directory
is never overwritten.

Every generated file lands under `tmp_path`. `addon_kit` must never write into the
repository's own `addons/` tree — that tree is not this test's to populate, and it
does not exist until M4 selects a real source.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

from addon_api import KINDS, AddonManifest, FetchResponse, Kind, ManifestError, OpenedInput
from addon_kit import DEFAULT_ADDONS_ROOT, AddonKitError, new_addon


def _load_handler(path: Path, module_name: str = "generated_handler") -> ModuleType:
    """Import a generated `handler.py` by path, independent of `addon_id`.

    A plain `import` would need the module on `sys.path` under its own name; a
    generated add-on lives under `tmp_path` and is never meant to be importable
    that way, so this loads it the same way `addon_host` would — by file path.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEachKindGeneratesAConformingManifest:
    @pytest.mark.parametrize("kind", KINDS)
    def test_the_manifest_parses_and_names_a_real_entry(self, tmp_path: Path, kind: Kind) -> None:
        target = new_addon(f"demo.{kind}", kind, tmp_path / kind)
        manifest = AddonManifest.load(target / "addon.toml")

        assert manifest.addon_id == f"demo.{kind}"
        assert manifest.kind == kind
        assert manifest.entry_module == "handler"
        assert manifest.entry_attribute == "run"

        module = _load_handler(target / "handler.py", f"generated_{kind}")
        entry = getattr(module, manifest.entry_attribute)
        assert callable(entry)

        # Positive control: the attribute check is not vacuously true for any name.
        assert not hasattr(module, "not_a_real_entry_point")

    def test_a_collector_declares_the_network_capabilities_its_context_grants(
        self, tmp_path: Path
    ) -> None:
        target = new_addon("demo.collector", "collector", tmp_path / "collector")
        manifest = AddonManifest.load(target / "addon.toml")
        assert manifest.declares.hosts == ("api.example.com",)
        assert manifest.declares.needs_credential is True
        assert manifest.output_contract_version is None

    def test_an_importer_declares_no_host_but_may_declare_a_stream(self, tmp_path: Path) -> None:
        target = new_addon("demo.importer", "importer", tmp_path / "importer")
        manifest = AddonManifest.load(target / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.streams == ("items",)
        assert manifest.output_contract_version is None

    def test_a_normalizer_declares_no_network_credential_or_cursor(self, tmp_path: Path) -> None:
        target = new_addon("demo.normalizer", "normalizer", tmp_path / "normalizer")
        manifest = AddonManifest.load(target / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
        assert manifest.declares.streams == ()
        assert manifest.declares.needs_credential is False
        assert manifest.output_contract_version == "0.1"

        # Positive control: a normalizer declaring what it must not is refused by
        # the contract, so the emptiness above is a real constraint and not an
        # artefact of nothing having been checked.
        with pytest.raises(ManifestError, match="no network capability"):
            AddonManifest.parse(
                (target / "addon.toml").read_text(encoding="utf-8")
                + '\n[declares]\nhosts = ["example.com"]\n'
            )


def _never_fetch(
    endpoint_ref: str,
    params: Mapping[str, str] | None = None,
    body: bytes | None = None,
) -> FetchResponse:
    """A `Fetch` that fails if it is ever called. Written as a function rather than a
    lambda because DP-020 gave the contract an optional third argument, and a lambda that
    took two would type-check as something the contract no longer describes."""
    pytest.fail("fetch must not run: config was invalid")


class TestEntryPointSignaturesMatchTheContext:
    """The generated `run` accepts the context object its own kind is handed.

    Exercised by actually calling it with a stand-in context built from
    `addon_api`'s own types, rather than only inspecting the signature — a
    skeleton that type-checks but raises on the first line it runs would still
    fail a human filling it in, and this is the one check available before the
    conformance suite exists.
    """

    def test_a_collector_reads_config_and_raises_on_a_missing_field(
        self, tmp_path: Path
    ) -> None:
        from addon_api import AddonConfigInvalid, CollectContext, Limits

        target = new_addon("demo.collector", "collector", tmp_path / "collector")
        module = _load_handler(target / "handler.py", "generated_collector")

        context = CollectContext(
            source_id="src-1",
            config={},
            cursor=None,
            limits=Limits(10.0, 10.0, 1_000_000, 5, 10, 1000),
            fetch=_never_fetch,
            accept_status=lambda response, reason: pytest.fail("accept_status must not run"),
            emit_raw=lambda items: pytest.fail("emit_raw must not run"),
            advance_cursor=lambda stream, cursor: pytest.fail("advance_cursor must not run"),
            log=lambda event, fields: None,
        )
        with pytest.raises(AddonConfigInvalid):
            module.run(context)

    def test_an_importer_reads_config_and_raises_on_a_missing_field(self, tmp_path: Path) -> None:
        from addon_api import AddonConfigInvalid, ImportContext, Limits

        target = new_addon("demo.importer", "importer", tmp_path / "importer")
        module = _load_handler(target / "handler.py", "generated_importer")

        context = ImportContext(
            source_id="src-1",
            config={},
            cursor=None,
            limits=Limits(10.0, 10.0, 1_000_000, 5, 10, 1000),
            open_input=lambda ref: OpenedInput(ref, "e-1", b""),
            emit_raw=lambda items: pytest.fail("emit_raw must not run"),
            advance_cursor=lambda stream, cursor: pytest.fail("advance_cursor must not run"),
            log=lambda event, fields: None,
        )
        with pytest.raises(AddonConfigInvalid):
            module.run(context)

    def test_a_normalizer_runs_end_to_end_over_a_synthetic_snapshot(self, tmp_path: Path) -> None:
        from addon_api import NormalizeContext, NormalizedResult, NormalizeOutcome, SnapshotItem

        target = new_addon("demo.normalizer", "normalizer", tmp_path / "normalizer")
        module = _load_handler(target / "handler.py", "generated_normalizer")

        emitted: list[NormalizedResult] = []
        items = [
            SnapshotItem(item_key="a", payload=b'{"x": 1}', content_type="application/json"),
            SnapshotItem(item_key="b", payload=b"not json", content_type="application/json"),
        ]
        context = NormalizeContext(
            run_id="run-1",
            snapshot_id="snap-1",
            config={"strict": False},
            read_snapshot=lambda: iter(items),
            emit_result=emitted.extend,
            log=lambda event, fields: None,
        )
        outcome = module.run(context)
        assert isinstance(outcome, NormalizeOutcome)
        assert outcome.results_emitted == 1
        assert outcome.skipped == 1
        assert len(emitted) == 1


class TestIdValidationReusesTheContractsOwnRule:
    """`addon_kit` does not re-implement `[addon].id`'s regex (task requirement).

    `new_addon` renders a manifest and parses it back through
    `AddonManifest.parse`; a bad id is refused there, as `ManifestError`, not by a
    second check this package would have to keep in sync.
    """

    def test_a_bad_id_is_refused_before_anything_is_written(self, tmp_path: Path) -> None:
        target = tmp_path / "bad"
        with pytest.raises(ManifestError, match=r"\[addon\].id"):
            new_addon("Not-A-Valid-Id", "collector", target)
        assert not target.exists()

    def test_a_good_id_is_accepted_for_contrast(self, tmp_path: Path) -> None:
        """Positive control for the refusal above: a valid id is not also refused."""
        target = new_addon("good.id", "collector", tmp_path / "good")
        assert target.exists()
        assert (target / "addon.toml").exists()


class TestOverwriteProtection:
    def test_an_existing_directory_is_refused_and_left_untouched(self, tmp_path: Path) -> None:
        target = tmp_path / "demo"
        new_addon("demo.first", "collector", target)
        before = (target / "addon.toml").read_text(encoding="utf-8")

        # A second call of a *different* kind into the same directory: if the
        # refusal below did not actually stop the write, this would change the
        # file's `kind` field, so the unchanged assertion is a real check and not
        # one that would pass either way (the required positive control).
        with pytest.raises(AddonKitError, match="already exists"):
            new_addon("demo.second", "normalizer", target)

        after = (target / "addon.toml").read_text(encoding="utf-8")
        assert after == before
        assert 'kind = "collector"' in after

    def test_a_directory_that_does_not_exist_yet_is_not_refused(self, tmp_path: Path) -> None:
        """Positive control: the refusal is about existence, not about `new_addon` itself."""
        target = new_addon("demo.fresh", "collector", tmp_path / "fresh")
        assert target.exists()


class TestDefaultOutputDirectory:
    def test_the_default_root_is_this_tree_s_addons_directory(self) -> None:
        """A pure path computation — never exercised against the filesystem here.

        `addon_kit` must not write into the repository's own `addons/` tree as a
        side effect of being tested (task requirement), so this checks the
        computed default path rather than calling `new_addon` or `main` without
        `--into`. P0 put `addon_kit/` inside `experiments/integrated-p0/`, so its
        default parent read `"integrated-p0"`; this tree puts `addon_kit/`
        directly under `apps/`, so the default parent is `"apps"` instead — the
        same one-directory-below-`addon_kit/` shape, at this tree's own root.
        """
        assert DEFAULT_ADDONS_ROOT.name == "addons"
        assert DEFAULT_ADDONS_ROOT.parent.name == "apps"

    def test_the_cli_honours_an_explicit_into_argument(self, tmp_path: Path) -> None:
        from addon_kit.__main__ import main

        target = tmp_path / "cli-generated"
        exit_code = main(["new", "demo.cli", "--kind", "collector", "--into", str(target)])
        assert exit_code == 0
        assert (target / "addon.toml").exists()

    def test_the_cli_reports_a_bad_id_with_a_non_zero_exit(self, tmp_path: Path) -> None:
        from addon_kit.__main__ import main

        target = tmp_path / "cli-bad"
        exit_code = main(["new", "Not Valid", "--kind", "collector", "--into", str(target)])
        assert exit_code == 1
        assert not target.exists()
