"""The host's own tests: discovery, the version gate, registration, translation.

Copy-adapted from ``experiments/integrated-p0/tests/test_addon_host.py`` (M3
batch 3b). No database is needed here — discovery, the version gate,
registration, and error translation are all local, synchronous operations, the
same as P0. The only change is ``EXPERIMENT_ROOT``'s replacement,
``ADDONS_ROOT`` below, which points at this tree's own ``apps/addons`` default
rather than P0's ``experiments/integrated-p0/addons``.

Every add-on here is built in ``tmp_path``. Nothing in this file touches the real
``addons/`` directory, because a fixture that had to be installed to be tested
would be an add-on the platform ships, and DP-008 D8 makes the directory the
installed set rather than a fixture tray.

The refusals carry most of the weight, and for the reason DP-008 D3 gives: each
version axis has a stated failure in a stated place. A contract mismatch that
reached job time would be indistinguishable from a source being unavailable, and
the operator would retry it.

Where a test asserts something is **absent** — no add-on discovered, no module
executed, no message in a summary — it is paired with a control proving the same
assertion can fail. An absence assertion alone would pass over a host that never
looked.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from addon_api import (
    CONTRACT_VERSION,
    AddonConfigInvalid,
    AddonError,
    AddonManifest,
    AddonOutputInvalid,
    AddonPermanent,
    AddonTransient,
    ManifestError,
)
from addon_host import (
    ADDON_DIR_VARIABLE,
    DEFAULT_ADDON_DIR,
    HANDLER_PREFIX,
    AddonRefusedError,
    LoadedAddon,
    addon_root,
    handler_name,
    install_addons,
    load_addons,
    make_handler,
    manifest_paths,
    module_name_for,
    translate,
    translated_failures,
)
from addon_host.loading import MODULE_PREFIX
from platform_core.errors import (
    ConfigurationInvalidError,
    ErrorClass,
    HandlerUnknownError,
    PlatformError,
    PlatformPermanentError,
    PlatformTransientError,
)
from platform_core.handlers.synthetic import synthetic_registry
from platform_core.jobs.registry import HandlerRegistry, JobContext
from platform_core.obs.redaction import REDACTION_MARKER

#: ``apps/``, where ``addons/`` sits by default in this tree.
ADDONS_ROOT = Path(__file__).resolve().parents[1]

MAX_ATTEMPTS = 3

MANIFEST_TEMPLATE = """
[addon]
id = "{addon_id}"
version = "{version}"
kind = "collector"
entry = "{entry}"
requires_contract = "{requires}"

[config]
schema_version = "1"

[[config.field]]
name = "base_path"
type = "string"
required = true

[declares]
hosts = ["api.example.com"]
endpoints = ["/v1/items"]
streams = ["items"]
"""

#: The smallest thing that satisfies the entry check. It takes whatever it is
#: given: batch 3b builds the capability layer, but this test file stays about
#: discovery, the gate, registration, and translation — not about a capability.
ENTRY_SOURCE = """
def run(context):
    return None
"""

#: Records that its module body ran. The version gate's evidence depends on this
#: file *not* appearing.
MARKING_SOURCE = """
from pathlib import Path

Path(__file__).with_name("imported").write_text("yes", encoding="utf-8")


def run(context):
    return None
"""

RAISING_ENTRY_SOURCE = """
from addon_api import AddonTransient


def run(context):
    raise AddonTransient("the synthetic add-on refused this attempt")
"""

#: A manifest whose add-on is a perfectly good package for a different host.
MANIFEST = AddonManifest.parse(
    MANIFEST_TEMPLATE.format(
        addon_id="collector.demo", version="0.1.0", entry="handler:run", requires=">=1.0,<2.0"
    )
)


def install_addon(
    root: Path,
    directory: str = "collector.demo",
    addon_id: str = "collector.demo",
    version: str = "0.1.0",
    requires: str = ">=1.0,<2.0",
    entry: str = "handler:run",
    manifest: str | None = None,
    module: str | None = "handler.py",
    source: str = ENTRY_SOURCE,
) -> Path:
    """Build one add-on package under ``root`` and return its directory."""
    package = root / directory
    package.mkdir(parents=True)
    text = (
        MANIFEST_TEMPLATE.format(
            addon_id=addon_id, version=version, entry=entry, requires=requires
        )
        if manifest is None
        else manifest
    )
    (package / "addon.toml").write_text(text, encoding="utf-8")
    if module is not None:
        (package / module).write_text(source, encoding="utf-8")
    return package


def _no_effect(key: str, value: Any) -> bool:
    raise AssertionError("no test in this module applies a durable effect")


def job_context() -> JobContext:
    """A context shaped like a worker's, carrying nothing an add-on could use yet."""
    return JobContext(
        job_id=uuid4(),
        attempt_id=uuid4(),
        payload=None,
        attempt_no=1,
        attempt_count=1,
        max_attempts=MAX_ATTEMPTS,
        correlation_id="correlation-under-test",
        worker_id="worker-under-test",
        apply_effect=_no_effect,
    )


def call_entry(addon: LoadedAddon, context: JobContext) -> None:
    """Stand-in for the real capability layer (``addon_host.capabilities``).

    It calls the entry point with the ``JobContext`` rather than the kind's own
    context, so this file's tests exercise the load/register/translate path
    without needing a database — the capability layer itself is
    ``test_addon_worker.py``'s and the domain-store suite's to exercise.
    """
    addon.entry(context)


@pytest.fixture(autouse=True)
def unload_addon_modules() -> Iterator[None]:
    """Leave ``sys.modules`` as it was found.

    Loading an add-on files its module under a namespaced key on purpose, so one
    test's fixture add-on would otherwise still be visible to the next.
    """
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith(MODULE_PREFIX):
            del sys.modules[name]


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def test_a_valid_add_on_is_discovered_loaded_and_registered(tmp_path: Path) -> None:
    package = install_addon(tmp_path)
    registry = HandlerRegistry()

    addons = install_addons(registry, root=tmp_path)

    assert len(addons) == 1
    loaded = addons[0]
    assert loaded.manifest.addon_id == "collector.demo"
    assert loaded.identity == "collector.demo@0.1.0"
    assert loaded.directory == package
    assert loaded.manifest_path == package / "addon.toml"
    assert callable(loaded.entry)
    assert registry.names() == ("addon:collector.demo",)


def test_an_absent_root_directory_yields_no_add_ons(tmp_path: Path) -> None:
    absent = tmp_path / "nowhere"
    assert manifest_paths(absent) == ()

    # The control: the same call over a root that does have an add-on finds it, so
    # the empty answer above is an answer rather than a scan that never ran.
    install_addon(tmp_path)
    assert len(manifest_paths(tmp_path)) == 1


def test_an_empty_root_directory_yields_no_add_ons(tmp_path: Path) -> None:
    empty = tmp_path / "addons"
    empty.mkdir()
    assert manifest_paths(empty) == ()

    install_addon(empty)
    assert len(manifest_paths(empty)) == 1


def test_a_directory_holding_no_manifest_is_not_an_add_on(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "handler.py").write_text(ENTRY_SOURCE, encoding="utf-8")
    assert manifest_paths(tmp_path) == ()

    install_addon(tmp_path)
    assert [path.parent.name for path in manifest_paths(tmp_path)] == ["collector.demo"]


def test_a_template_directory_is_not_installed(tmp_path: Path) -> None:
    """``addon_kit`` puts a template at ``addons/_template/``; a template is not installed."""
    install_addon(tmp_path, directory="_template", addon_id="collector.template")
    assert manifest_paths(tmp_path) == ()

    # The control: the identical package under a name without the prefix is found.
    install_addon(tmp_path, directory="collector.template", addon_id="collector.template")
    assert [path.parent.name for path in manifest_paths(tmp_path)] == ["collector.template"]


def test_a_host_with_no_add_on_directory_still_starts(tmp_path: Path) -> None:
    registry = synthetic_registry()
    before = registry.names()

    assert install_addons(registry, root=tmp_path / "nowhere") == ()
    assert registry.names() == before


def test_discovery_order_is_stable(tmp_path: Path) -> None:
    for name in ("collector.c", "collector.a", "collector.b"):
        install_addon(tmp_path, directory=name, addon_id=name)
    assert [path.parent.name for path in manifest_paths(tmp_path)] == [
        "collector.a",
        "collector.b",
        "collector.c",
    ]


def test_a_loaded_module_is_filed_under_a_namespaced_key(tmp_path: Path) -> None:
    install_addon(tmp_path)
    addons = load_addons(tmp_path)

    name = module_name_for(addons[0].manifest)
    assert name == "cosma_addon_collector_demo_handler"
    assert sys.modules[name] is addons[0].module
    # The add-on did not claim a plain importable name, which is what would make a
    # later `import handler` reach it. The assertion above is the control: the
    # module is present, under a key nothing else can ask for.
    assert "handler" not in sys.modules


# --------------------------------------------------------------------------- #
# The version gate (DP-008 D3)
# --------------------------------------------------------------------------- #


def test_an_add_on_requiring_another_contract_version_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, requires=">=2.0")

    with pytest.raises(AddonRefusedError) as caught:
        load_addons(tmp_path)

    summary = caught.value.summary
    assert "collector.demo@0.1.0" in summary
    assert ">=2.0" in summary, "the add-on's own requirement is not named"
    assert CONTRACT_VERSION in summary, "the host's contract version is not named"
    assert caught.value.error_class is ErrorClass.CONFIGURATION_INVALID
    assert not caught.value.retryable


def test_a_refused_add_on_never_has_its_module_executed(tmp_path: Path) -> None:
    refused_root = tmp_path / "refused"
    package = install_addon(refused_root, requires="<1.0", source=MARKING_SOURCE)

    with pytest.raises(AddonRefusedError):
        load_addons(refused_root)
    assert not (package / "imported").exists()

    # The control: the identical module under a satisfiable range does run, so the
    # absence above is the gate's doing and not a module that marks nothing. It goes
    # in a root of its own, because a refusal stops the scan it happens in.
    allowed_root = tmp_path / "allowed"
    other = install_addon(allowed_root, source=MARKING_SOURCE)
    load_addons(allowed_root)
    assert (other / "imported").exists()


def test_the_gate_is_evaluated_against_the_contract_version_it_is_given(
    tmp_path: Path,
) -> None:
    """The host's own version is the default, not the only answerable question.

    A parametrized contract makes the gate testable in both directions without
    editing ``addon_api``, which this batch may not do.
    """
    install_addon(tmp_path, requires=">=2.0,<3.0")

    assert len(load_addons(tmp_path, contract="2.1")) == 1
    with pytest.raises(AddonRefusedError):
        load_addons(tmp_path, contract="3.0")


def test_the_gate_refuses_before_the_registry_is_touched(tmp_path: Path) -> None:
    install_addon(tmp_path, directory="collector.a", addon_id="collector.a")
    install_addon(tmp_path, directory="collector.b", addon_id="collector.b", requires=">=9.0")
    registry = HandlerRegistry()

    with pytest.raises(AddonRefusedError):
        install_addons(registry, root=tmp_path)

    # Discovery is ordered, so `collector.a` loaded before `collector.b` was
    # refused. Nothing is registered, because registration follows a complete load.
    assert registry.names() == ()


# --------------------------------------------------------------------------- #
# Malformed packages
# --------------------------------------------------------------------------- #


def test_a_manifest_that_is_not_valid_toml_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, manifest="[addon\nid = 'collector.demo'\n")

    with pytest.raises(ManifestError, match="not valid TOML"):
        load_addons(tmp_path)


def test_a_manifest_missing_the_addon_table_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, manifest="[config]\nschema_version = '1'\n")

    with pytest.raises(ManifestError, match=r"missing the \[addon\] table"):
        load_addons(tmp_path)


def test_a_manifest_naming_a_module_that_is_not_there_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, entry="collect:run", module="handler.py")

    with pytest.raises(ManifestError) as caught:
        load_addons(tmp_path)
    assert "collect" in str(caught.value)


def test_a_manifest_naming_a_missing_entry_attribute_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, entry="handler:collect")

    with pytest.raises(ManifestError) as caught:
        load_addons(tmp_path)
    assert "'collect'" in str(caught.value)
    # A refused add-on leaves nothing of itself behind, even though its module ran.
    assert module_name_for(MANIFEST) not in sys.modules


def test_a_manifest_naming_an_entry_that_is_not_callable_is_refused(tmp_path: Path) -> None:
    install_addon(tmp_path, source="run = 3\n")

    with pytest.raises(ManifestError, match="callable"):
        load_addons(tmp_path)


def test_an_entry_module_that_raises_while_importing_is_refused_at_load(
    tmp_path: Path,
) -> None:
    install_addon(tmp_path, source="raise RuntimeError('the add-on is broken')\n")

    with pytest.raises(AddonRefusedError) as caught:
        load_addons(tmp_path)
    assert "RuntimeError" in caught.value.summary
    assert not caught.value.retryable
    # A half-executed module must not stay visible to a later import.
    assert module_name_for(MANIFEST) not in sys.modules


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_a_handler_name_is_namespaced_so_an_add_on_cannot_shadow_the_platform(
    tmp_path: Path,
) -> None:
    """``HandlerRegistry.register`` refuses to rebind a name, so a collision is fatal."""
    registry = synthetic_registry()
    assert "succeed" in registry

    install_addon(tmp_path, directory="succeed", addon_id="succeed")
    install_addons(registry, root=tmp_path)

    assert handler_name(MANIFEST).startswith(HANDLER_PREFIX)
    assert "addon:succeed" in registry
    assert registry.resolve("succeed") is not registry.resolve("addon:succeed")


def test_an_add_on_that_is_not_installed_still_fails_as_handler_unknown(
    tmp_path: Path,
) -> None:
    """Contracted P0-A behaviour, so this batch builds nothing new for the absent case."""
    registry = HandlerRegistry()
    install_addons(registry, root=tmp_path)

    with pytest.raises(HandlerUnknownError) as caught:
        registry.resolve("addon:collector.demo")
    assert caught.value.error_class is ErrorClass.HANDLER_UNKNOWN
    assert not caught.value.retryable

    # The control: the same name resolves once the add-on is in the directory.
    install_addon(tmp_path)
    install_addons(registry, root=tmp_path)
    assert callable(registry.resolve("addon:collector.demo"))


def test_the_capability_seam_is_not_bound_and_says_so(tmp_path: Path) -> None:
    install_addon(tmp_path)
    registry = HandlerRegistry()
    install_addons(registry, root=tmp_path)

    handler = registry.resolve("addon:collector.demo")
    with pytest.raises(PlatformPermanentError) as caught:
        handler(job_context())
    assert "capability layer" in caught.value.summary
    assert "collector" in caught.value.summary
    assert not caught.value.retryable


def test_a_registered_handler_translates_the_add_ons_own_failure(tmp_path: Path) -> None:
    install_addon(tmp_path, source=RAISING_ENTRY_SOURCE)
    registry = HandlerRegistry()
    install_addons(registry, root=tmp_path, invoke=call_entry)

    handler = registry.resolve("addon:collector.demo")
    with pytest.raises(PlatformTransientError) as caught:
        handler(job_context())
    assert caught.value.retryable
    assert "collector.demo@0.1.0" in caught.value.summary


def test_two_directories_claiming_one_addon_id_are_refused_by_name(
    tmp_path: Path,
) -> None:
    """The installed set, not the registry, is what is wrong — so say which two.

    Without this the failure is the bare ``ValueError`` from ``HandlerRegistry``,
    which is not a ``PlatformError``, so an entrypoint catching ``PlatformError``
    would let a packaging mistake through as a traceback. It also names only the
    loser, while an operator needs both directories.
    """
    install_addon(tmp_path, directory="first", addon_id="collector.twin")
    install_addon(tmp_path, directory="second", addon_id="collector.twin")
    registry = HandlerRegistry()

    with pytest.raises(AddonRefusedError) as caught:
        install_addons(registry, root=tmp_path)

    assert isinstance(caught.value, PlatformError)
    assert not caught.value.retryable
    assert "collector.twin" in caught.value.summary
    assert "first" in caught.value.summary and "second" in caught.value.summary
    # Nothing was bound: the refusal precedes registration, so a partly installed
    # process is not a state this can leave behind.
    assert len(registry) == 0


def test_two_directories_with_distinct_ids_both_register(tmp_path: Path) -> None:
    """The positive control for the refusal above.

    Two directories in one root is ordinary. If this failed too, the test above
    would be passing for the wrong reason.
    """
    install_addon(tmp_path, directory="first", addon_id="collector.one")
    install_addon(tmp_path, directory="second", addon_id="collector.two")
    registry = HandlerRegistry()

    install_addons(registry, root=tmp_path)

    assert set(registry.names()) == {"addon:collector.one", "addon:collector.two"}


def test_a_second_add_on_claiming_one_name_is_refused_by_the_registry(
    tmp_path: Path,
) -> None:
    """Two meanings for one name is a defect in the add-on directory as much as in code."""
    install_addon(tmp_path)
    registry = HandlerRegistry()
    install_addons(registry, root=tmp_path)

    with pytest.raises(ValueError, match="already registered"):
        install_addons(registry, root=tmp_path)


# --------------------------------------------------------------------------- #
# Error translation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raised", "expected", "retryable"),
    [
        (AddonTransient("the source rate-limited this attempt"), PlatformTransientError, True),
        (AddonPermanent("the record cannot be parsed"), PlatformPermanentError, False),
        (AddonConfigInvalid("the stored configuration is wrong"), ConfigurationInvalidError, False),
        (AddonOutputInvalid("the result fails the output contract"), PlatformPermanentError, False),
    ],
)
def test_each_contract_error_becomes_its_platform_error(
    raised: AddonError, expected: type[PlatformError], retryable: bool
) -> None:
    translated = translate(raised, MANIFEST)

    assert type(translated) is expected
    assert translated.retryable is retryable
    assert translated.summary == f"collector.demo@0.1.0: {raised.summary}"


def test_a_narrowed_contract_error_keeps_the_classification_it_asked_for() -> None:
    class RateLimited(AddonTransient):
        """An add-on's own subclass, which the host has never heard of."""

    translated = translate(RateLimited("slow down"), MANIFEST)

    assert type(translated) is PlatformTransientError
    assert translated.retryable


def test_an_unexpected_exception_becomes_a_permanent_failure_recording_its_type() -> None:
    translated = translate(ZeroDivisionError("division by zero"), MANIFEST)

    assert type(translated) is PlatformPermanentError
    assert not translated.retryable
    assert "ZeroDivisionError" in translated.summary
    # The message is withheld from the operator-visible summary and kept in
    # protected detail, which is the control: it was recorded, not discarded.
    assert "division by zero" not in translated.summary
    detail = translated.detail.for_protected_debug()
    assert detail["exception_type"] == "ZeroDivisionError"
    assert detail["exception_message"] == "division by zero"


def test_a_bare_contract_error_is_not_a_free_pass() -> None:
    """``AddonError`` itself classifies nothing, so it is treated as unexpected."""
    translated = translate(AddonError("something went wrong"), MANIFEST)

    assert type(translated) is PlatformPermanentError
    assert "AddonError" in translated.summary


def test_a_translated_failure_records_which_add_on_failed() -> None:
    translated = translate(AddonPermanent("no"), MANIFEST)

    detail = translated.detail.for_protected_debug()
    assert detail["addon_id"] == "collector.demo"
    assert detail["addon_version"] == "0.1.0"
    assert detail["kind"] == "collector"


def test_an_add_ons_own_detail_is_carried_and_still_redacted() -> None:
    raised = AddonTransient(
        "the source rate-limited this attempt",
        {"retry_after_s": 30, "api_key": "irrelevant"},
    )

    detail = translate(raised, MANIFEST).detail.for_protected_debug()

    assert detail["addon_detail"]["retry_after_s"] == 30
    assert detail["addon_detail"]["api_key"] == REDACTION_MARKER


def test_an_add_on_cannot_overwrite_the_identity_the_host_recorded() -> None:
    raised = AddonPermanent("no", {"addon_id": "someone.else"})

    detail = translate(raised, MANIFEST).detail.for_protected_debug()

    assert detail["addon_id"] == "collector.demo"
    assert detail["addon_detail"]["addon_id"] == "someone.else"


def test_a_platform_error_from_the_host_passes_through_untranslated() -> None:
    with pytest.raises(PlatformTransientError) as caught, translated_failures(MANIFEST):
        raise PlatformTransientError("the host's own lease expired")

    assert caught.value.summary == "the host's own lease expired"
    assert "collector.demo" not in caught.value.summary

    # The control: an add-on's error in the same block does get the prefix.
    with pytest.raises(PlatformTransientError) as second, translated_failures(MANIFEST):
        raise AddonTransient("the source rate-limited this attempt")
    assert second.value.summary.startswith("collector.demo@0.1.0: ")


def test_an_interrupted_process_is_not_an_attempt_failure() -> None:
    """``KeyboardInterrupt`` is the worker being stopped, not the add-on failing."""
    with pytest.raises(KeyboardInterrupt), translated_failures(MANIFEST):
        raise KeyboardInterrupt

    with pytest.raises(SystemExit), translated_failures(MANIFEST):
        raise SystemExit(1)


def test_a_handler_returning_normally_is_a_success(tmp_path: Path) -> None:
    install_addon(tmp_path)
    addons = load_addons(tmp_path)

    handler = make_handler(addons[0], invoke=call_entry)

    assert handler(job_context()) is None


# --------------------------------------------------------------------------- #
# COSMA_ADDON_DIR
# --------------------------------------------------------------------------- #


def test_the_default_root_is_the_in_repository_addons_directory() -> None:
    assert addon_root({}) == DEFAULT_ADDON_DIR
    assert DEFAULT_ADDON_DIR == ADDONS_ROOT / "addons"


def test_a_stated_root_is_used(tmp_path: Path) -> None:
    assert addon_root({ADDON_DIR_VARIABLE: str(tmp_path)}) == tmp_path


def test_a_stated_root_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    absent = tmp_path / "nowhere"

    with pytest.raises(ConfigurationInvalidError) as caught:
        addon_root({ADDON_DIR_VARIABLE: str(absent)})
    assert ADDON_DIR_VARIABLE in caught.value.summary
    assert not caught.value.retryable

    # The control: the default's own directory need not exist, so the refusal above
    # is about a *stated* value rather than about the path being absent.
    assert addon_root({}) == DEFAULT_ADDON_DIR


def test_a_root_stated_as_empty_is_refused() -> None:
    with pytest.raises(ConfigurationInvalidError, match="is set but empty"):
        addon_root({ADDON_DIR_VARIABLE: "   "})


def test_a_file_named_as_the_root_is_refused(tmp_path: Path) -> None:
    stated = tmp_path / "addons.toml"
    stated.write_text("", encoding="utf-8")

    with pytest.raises(ConfigurationInvalidError, match="existing directory"):
        addon_root({ADDON_DIR_VARIABLE: str(stated)})


# --------------------------------------------------------------------------- #
# DP-024 — only an importer opens a local input
# --------------------------------------------------------------------------- #


IMPORTER_MANIFEST = """
[addon]
id = "importer.demo"
version = "0.1.0"
kind = "importer"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[declares]
inputs = ["rows"]
streams = ["rows"]
"""


def test_an_importer_may_declare_the_inputs_it_opens(tmp_path: Path) -> None:
    install_addon(tmp_path, manifest=IMPORTER_MANIFEST)

    loaded = load_addons(tmp_path)

    assert loaded[0].manifest.declares.inputs == ("rows",)


@pytest.mark.parametrize("kind", ["collector", "normalizer"])
def test_any_other_kind_declaring_an_input_is_refused(tmp_path: Path, kind: str) -> None:
    """The mirror of the rule that an importer declares no host. A declaration no
    capability can honour is refused rather than ignored, because an ignored one is
    undiscoverable — no error, no log, no behaviour change."""
    manifest = IMPORTER_MANIFEST.replace('kind = "importer"', f'kind = "{kind}"')
    if kind == "normalizer":
        manifest = manifest.replace(
            'requires_contract = ">=1.0,<2.0"',
            'requires_contract = ">=1.0,<2.0"\noutput_contract_version = "0.1"',
        ).replace('streams = ["rows"]', "streams = []")
    install_addon(tmp_path, manifest=manifest)

    with pytest.raises(ManifestError, match="only an importer opens a local input"):
        load_addons(tmp_path)
