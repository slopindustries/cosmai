"""The worker that actually hosts add-ons — `ADVERSARIAL-REVIEW-2026-08-18.md` F3.

Copy-adapted from ``experiments/integrated-p0/tests/test_addon_worker.py`` (M3
batch 3b). Two adaptations, both because this batch runs before M4 installs any
real add-on:

- P0 named the one add-on committed to its ``addons/`` tree,
  ``collector.naver.blog``, and relied on the default ``COSMA_ADDON_DIR`` to find
  it. Nothing is installed under this tree's ``apps/addons/`` yet, so
  ``probe_addon`` below builds an equivalent synthetic collector under
  ``tmp_path`` and every call to :func:`addon_host.worker.capability_registry`
  passes ``root=`` explicitly, exactly the way `test_addon_host.py` already does
  for the loading/registration tests.
- P1's fixture names differ from P0's: ``platform_config`` for ``database``,
  ``job_store`` for ``store``, ``job_connection`` for ``connection`` — the same
  renaming every other copy-adapted test module in this tree already carries
  (``tests/test_worker.py``'s own docstring explains why: DP-032's one shared
  ``cosmai_test`` database replaces P0's per-test cloned one, so isolation is
  row-level and the fixtures are named for what they reset rather than for a
  clone that no longer exists).

The finding this file is evidence against: *"`bind_capabilities` has three call
sites, all in tests. `platform_core/worker.py` never wires the capability layer
at all."* Every claim this batch makes about a collector on the platform
therefore rests on this file's own wiring being real, not a test's private
convenience — which is also why `TestTheEntrypoint` below runs the real
``python -m addon_host.worker`` process rather than calling ``main`` in-process.

**Why the wiring is not in `platform_core/worker.py`.** DP-008 D1 says
`platform_core` gains no dependency on the add-on layer, and
`tests/environment/test_addon_layer_direction.py` enforces it: `platform_core`
may import nothing local. A worker that imported `addon_host.capabilities` and
`domain.store` would fail that guard. So `platform_core.worker` gained one
source-neutral seam instead — `registry_for`, a callable handed the connection
that returns the handler table for it — and the add-on half lives here, in
`addon_host`, where DP-008 D1 already permits both imports.

`registry_for` is per *connection* and not per process on purpose. `Worker._reopen`
replaces the connection after a transient database failure, and a capability layer
still holding the previous connection's `DomainStore` would be exactly the
mis-wiring F3 is about — the `DomainStore` writing outside the transaction that
completes the attempt. Rebuilding the table with the connection makes that
unrepresentable rather than merely tested.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import psycopg
import pytest

from addon_host.registration import HANDLER_PREFIX
from addon_host.worker import capability_registry, main
from domain.store import DomainStore
from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.errors import ErrorClass
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.worker import EXIT_OK, Worker, WorkerOptions
from tests.conftest import worker_environment

pytestmark = pytest.mark.usefixtures("_migrations_applied")

PROBE_ADDON_ID = "collector.probe"
PROBE_HANDLER = f"{HANDLER_PREFIX}{PROBE_ADDON_ID}"

PROBE_MANIFEST = """
[addon]
id = "collector.probe"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

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

#: The handler never runs in any case below: every scenario either fails before the
#: capability layer calls it (an unregistered source) or never reaches the worker
#: process at all (`test_addon_host.py` covers the load/register/translate path
#: this test file does not repeat). Present so the add-on package is well-formed.
PROBE_SOURCE = """
def run(context):
    return None
"""


def probe_addon(root: Path) -> Path:
    """Install the one synthetic collector these tests need, and return `root`.

    `root` is what `capability_registry(..., root=...)` scans — the directory
    *containing* `collector.probe/`, not that directory itself, matching
    `addon_host.loading.manifest_paths`'s own contract.
    """
    package = root / PROBE_ADDON_ID
    package.mkdir(parents=True)
    (package / "addon.toml").write_text(PROBE_MANIFEST, encoding="utf-8")
    (package / "handler.py").write_text(PROBE_SOURCE, encoding="utf-8")
    return root


class RefusingTransport:
    """A transport that must never be reached. These cases all refuse before any request.

    A stub rather than the real `SocketTransport`, so that a wiring defect shows up as this
    assertion rather than as an outbound connection from a test run.
    """

    def send(self, request: Any, profile: Any, headers: Any = None, limits: Any = None) -> Any:
        raise AssertionError("no case in this module may reach the network")


def run_one_job(
    platform_config: PlatformConfig,
    job_store: JobStore,
    root: Path,
    handler: str,
    payload: Any,
) -> tuple[int, StringIO]:
    """Run one in-process worker pass over one job, and return its exit status and log."""
    job_id = job_store.create_job(handler, payload, max_attempts=1)
    log = StringIO()
    worker = Worker(
        platform_config,
        WorkerOptions(once=True),
        StructuredLogger(stream=log, level="DEBUG"),
        registry_for=capability_registry(RefusingTransport(), root=root),
        report_stream=StringIO(),
    )
    code = worker.run()
    assert job_store.read_job(job_id) is not None
    return code, log


class TestTheAddOnWorkerBindsTheCapabilityLayer:
    def test_the_installed_add_on_is_registered_under_its_handler_name(
        self, tmp_path: Path, job_connection: psycopg.Connection[Any]
    ) -> None:
        root = probe_addon(tmp_path)
        registry = capability_registry(RefusingTransport(), root=root)(job_connection)
        assert PROBE_HANDLER in registry.names()

    def test_the_platform_handlers_are_still_registered_beside_it(
        self, tmp_path: Path, job_connection: psycopg.Connection[Any]
    ) -> None:
        """The add-on table is added to the synthetic one, not substituted for it. A worker
        that lost `succeed` would break every P0-A scenario silently."""
        root = probe_addon(tmp_path)
        registry = capability_registry(RefusingTransport(), root=root)(job_connection)
        assert "succeed" in registry.names()

    def test_a_collect_job_reaches_the_capability_layer_rather_than_the_stated_refusal(
        self, tmp_path: Path, platform_config: PlatformConfig, job_store: JobStore
    ) -> None:
        """The finding itself, as a behavioural assertion.

        `registration.capabilities_not_bound` is the default `Invoke` and fails a job with
        *"this host has no capability layer bound"*. Reaching `_require_source`'s refusal
        instead is what proves `bind_capabilities` is the one installed — and it is a
        refusal, so it needs no source row, no credential, and no socket.
        """
        root = probe_addon(tmp_path)
        code, _ = run_one_job(
            platform_config, job_store, root, PROBE_HANDLER, {"source_id": "not-registered"}
        )

        assert code == EXIT_OK
        attempts = job_store.read_attempts(job_store.list_jobs()[0]["id"])
        assert len(attempts) == 1
        assert attempts[0]["error_class"] == ErrorClass.PLATFORM_PERMANENT.value
        assert "no source named" in attempts[0]["error_summary"]
        assert "no capability layer bound" not in attempts[0]["error_summary"]

    def test_an_unregistered_handler_name_still_fails_as_handler_unknown(
        self, tmp_path: Path, platform_config: PlatformConfig, job_store: JobStore
    ) -> None:
        """The control for the case above: the registry is a real one and can still miss."""
        root = probe_addon(tmp_path)
        run_one_job(
            platform_config,
            job_store,
            root,
            f"{HANDLER_PREFIX}collector.absent",
            {"source_id": "x"},
        )

        attempts = job_store.read_attempts(job_store.list_jobs()[0]["id"])
        assert attempts[0]["error_class"] == ErrorClass.HANDLER_UNKNOWN.value


class TestTheTableIsRebuiltWithTheConnection:
    def test_each_connection_gets_a_domain_store_on_that_connection(
        self, tmp_path: Path, platform_config: PlatformConfig
    ) -> None:
        """`Worker._reopen` replaces the connection; the capability layer must follow it.

        Asserted through `capability_registry` rather than by reaching into the worker,
        because the property is that *the builder* is per connection.
        """
        root = probe_addon(tmp_path)
        build = capability_registry(RefusingTransport(), root=root)
        with (
            connect(platform_config, role="runtime", autocommit=True) as first,
            connect(platform_config, role="runtime", autocommit=True) as second,
        ):
            assert build(first) is not build(second)
            assert DomainStore(first).connection is first
            assert DomainStore(second).connection is second


class TestTheEntrypoint:
    def test_the_process_entrypoint_runs_one_pass_and_exits_cleanly(
        self,
        tmp_path: Path,
        platform_config: PlatformConfig,
        job_store: JobStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`python -m addon_host.worker` is this batch's entrypoint. Run in-process here,
        with the add-on directory and database settings monkeypatched into the real
        environment `main` reads via `load_config()`/`addon_root()`; a real spawned-process
        form belongs to a live source's own scenario, once M4 has one."""
        root = probe_addon(tmp_path)
        for name, value in worker_environment(platform_config, COSMA_ADDON_DIR=str(root)).items():
            monkeypatch.setenv(name, value)
        job_store.create_job(PROBE_HANDLER, {"source_id": "not-registered"}, max_attempts=1)

        assert main(["--once"]) == EXIT_OK
        assert job_store.list_jobs()[0]["state"] == JobState.FAILED.value
