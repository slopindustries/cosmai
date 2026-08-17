"""SEC-001 — the platform refuses a secret-store path inside the working tree.

The scenario's case table drives this file, and its two easily-lost properties get
a test each rather than being folded into the table:

* **Case e** points the variable at a path that is outside the tree and whose
  target is inside it. A guard comparing the string it was given passes that case
  and lets a credential file under version control through, which is the whole
  failure the rule exists to prevent. The test asserts the naive comparison would
  have succeeded, so a regression to it fails here rather than silently.
* **Case b** points the variable at a file nothing can read. Startup must still
  succeed, because the guard's answer depends on location alone. A guard that
  opened the store to check it would fail this case, and opening a credential to
  validate where it lives is the leak the rule prevents.

Nothing here creates a file that outlives the test. The two cases that need a real
path inside the working tree create one under a ``.tmp-`` name — ``.gitignore``
excludes that prefix — and remove it in a fixture teardown. The guard never opens
the file, so most cases do not need it to exist at all; the ones that do exist
prove the refusal is not merely an "absent path" answer wearing a different hat.
"""

from __future__ import annotations

import importlib.util
import stat
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from platform_core.config import (
    SECRET_SETUP_POINTER,
    SECRET_STORE_VARIABLE,
    WORKING_TREE_ROOT,
    PlatformConfig,
    load_config,
    secret_store_location_problem,
)
from platform_core.errors import ConfigurationInvalidError, ErrorClass

from tests.conftest import (
    ENTRYPOINTS,
    EX_CONFIG,
    REQUEST_TIMEOUT_SECONDS,
    SECRET_MARKER,
    log_events,
    run_worker,
    running_api,
    start_entrypoint,
)

#: Refused because the whole tree is refused. Nothing is written to it.
INSIDE_TREE_NAMES = (
    ".tmp-sec-001-store",
    "experiments/integrated-p0/.tmp-sec-001-store",
    "tests/fixtures/local/.tmp-sec-001-store",
)

READ_ONLY_OWNER = stat.S_IRUSR | stat.S_IWUSR

UNREADABLE = 0o000


@pytest.fixture
def store_outside_the_tree(tmp_path: Path) -> Path:
    """A synthetic store file outside the working tree, mode 600. Holds no credential."""
    path = tmp_path / "env"
    path.write_text("COSMA_SRC_EXAMPLE_TOKEN=not-a-real-value\n", encoding="utf-8")
    path.chmod(READ_ONLY_OWNER)
    return path


@pytest.fixture
def store_inside_the_tree() -> Iterator[Path]:
    """A real file inside the working tree, removed however the test ends.

    Created so that case c is a refusal of a store that exists, not an accidental
    refusal of a path that does not. ``.tmp-`` is already in ``.gitignore``, so a
    test that dies between creation and teardown cannot leave a tracked file.
    """
    path = WORKING_TREE_ROOT / ".tmp-sec-001-store"
    path.write_text("COSMA_SRC_EXAMPLE_TOKEN=not-a-real-value\n", encoding="utf-8")
    path.chmod(READ_ONLY_OWNER)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
        assert not path.exists(), "the working tree must be left as it was found"


def refusal(environment: Mapping[str, str]) -> ConfigurationInvalidError:
    with pytest.raises(ConfigurationInvalidError) as raised:
        load_config(environment)
    return raised.value


# --- the case table ---------------------------------------------------------


def test_sec_001_case_a_an_unset_store_is_not_a_configuration_error(
    baseline: dict[str, str],
) -> None:
    """P0-A resolves no credential, so requiring the variable would invent a rule.

    OQ-007 assigns credential resolution to P0-B. Until it is decided, a run
    without a store is a run that has nothing to resolve, not a misconfigured one.
    """
    assert SECRET_STORE_VARIABLE not in baseline
    config = load_config(baseline)
    assert isinstance(config, PlatformConfig)
    assert secret_store_location_problem({}, baseline) is None


@pytest.mark.parametrize("given", ["", "   "])
def test_sec_001_an_empty_store_setting_is_treated_as_unset(
    baseline: dict[str, str], given: str
) -> None:
    """A blank value states no location, and there is no location to refuse.

    Deliberately unlike the settings this stage consumes, where an empty value is a
    statement and is rejected. Nothing is being configured here: the guard has an
    opinion about paths, and a blank string is not one.
    """
    assert load_config({**baseline, SECRET_STORE_VARIABLE: given}).api_host


def test_sec_001_case_b_a_store_outside_the_working_tree_is_accepted(
    baseline: dict[str, str], store_outside_the_tree: Path
) -> None:
    config = load_config({**baseline, SECRET_STORE_VARIABLE: str(store_outside_the_tree)})
    assert isinstance(config, PlatformConfig)


def test_sec_001_case_b_an_unreadable_store_outside_the_tree_still_starts(
    baseline: dict[str, str], store_outside_the_tree: Path
) -> None:
    """The evidence that the guard never opens the store.

    A guard that read the file to validate it would fail here, and it is exactly
    the guard that would leak a credential into a validation error message.
    """
    store_outside_the_tree.chmod(UNREADABLE)
    try:
        with pytest.raises(PermissionError):
            store_outside_the_tree.read_text(encoding="utf-8")
        config = load_config({**baseline, SECRET_STORE_VARIABLE: str(store_outside_the_tree)})
        assert isinstance(config, PlatformConfig)
    finally:
        store_outside_the_tree.chmod(READ_ONLY_OWNER)


def test_sec_001_case_c_a_store_that_exists_in_the_repository_root_is_refused(
    baseline: dict[str, str], store_inside_the_tree: Path
) -> None:
    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(store_inside_the_tree)})
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID
    assert not error.retryable
    assert SECRET_STORE_VARIABLE in error.summary


@pytest.mark.parametrize("relative", INSIDE_TREE_NAMES)
def test_sec_001_cases_c_and_d_any_path_inside_the_tree_is_refused(
    baseline: dict[str, str], relative: str
) -> None:
    """Case c and case d, at the root and nested. No file is created.

    The guard decides on location, so a path that does not exist yet is refused on
    the same grounds — which is the useful direction: the refusal happens before
    anybody has put a credential there.
    """
    candidate = WORKING_TREE_ROOT / relative
    assert not candidate.exists(), "this test must not depend on a file existing"
    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(candidate)})
    assert str(candidate) in error.summary
    assert not candidate.exists(), "the guard created nothing"


def test_sec_001_case_e_a_link_from_outside_the_tree_into_it_is_refused(
    baseline: dict[str, str], tmp_path: Path, store_inside_the_tree: Path
) -> None:
    """The case a naive check fails, with the naive check's answer asserted too."""
    link = tmp_path / "env"
    link.symlink_to(store_inside_the_tree)

    # The control: by every test that does not resolve, this path is outside.
    assert not str(link).startswith(str(WORKING_TREE_ROOT))
    assert WORKING_TREE_ROOT not in link.parents

    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(link)})
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID
    assert str(store_inside_the_tree) in error.summary, "the resolved target is named"


def test_sec_001_case_e_a_link_that_resolves_outside_the_tree_is_accepted(
    baseline: dict[str, str], tmp_path: Path, store_outside_the_tree: Path
) -> None:
    """The other half of case e: resolving is not an excuse to refuse links."""
    link = tmp_path / "link-to-env"
    link.symlink_to(store_outside_the_tree)
    assert isinstance(load_config({**baseline, SECRET_STORE_VARIABLE: str(link)}), PlatformConfig)


def test_sec_001_case_f_the_repository_root_itself_is_refused(baseline: dict[str, str]) -> None:
    """A directory, not a file, and the boundary value of the comparison."""
    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(WORKING_TREE_ROOT)})
    assert str(WORKING_TREE_ROOT) in error.summary


def test_sec_001_a_relative_path_is_resolved_before_it_is_compared(
    baseline: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``COSMA_SECRET_SOURCE=env`` from inside the repository is inside the tree."""
    monkeypatch.chdir(WORKING_TREE_ROOT)
    error = refusal({**baseline, SECRET_STORE_VARIABLE: ".tmp-sec-001-relative"})
    assert str(WORKING_TREE_ROOT) in error.summary


# --- what the refusal is allowed to say -------------------------------------


def test_sec_001_the_refusal_names_the_path_the_root_and_the_convention(
    baseline: dict[str, str], store_inside_the_tree: Path
) -> None:
    """The scenario's operator-visible explanation, item by item."""
    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(store_inside_the_tree)})
    assert str(store_inside_the_tree) in error.summary
    assert str(WORKING_TREE_ROOT) in error.summary
    assert SECRET_SETUP_POINTER in error.summary
    assert error.operator_view()["error_class"] == ErrorClass.CONFIGURATION_INVALID


def test_sec_001_the_refusal_does_not_dump_the_environment(
    baseline: dict[str, str], store_inside_the_tree: Path
) -> None:
    """secret-setup.md names an environment dump as a leak channel of its own."""
    error = refusal(
        {
            **baseline,
            SECRET_STORE_VARIABLE: str(store_inside_the_tree),
            "COSMA_API_TOKEN": SECRET_MARKER,
            "SOME_UNRELATED_VARIABLE": SECRET_MARKER,
        }
    )
    reported = " ".join(
        [
            str(error),
            repr(error),
            str(error.operator_view()),
            str(error.detail.for_protected_debug()),
        ]
    )
    assert SECRET_MARKER not in reported
    assert baseline["COSMA_DB_USER"] not in reported


def test_sec_001_the_store_contents_are_never_reported(
    baseline: dict[str, str], store_inside_the_tree: Path
) -> None:
    """A refused store's own text is not read, so it cannot be quoted."""
    store_inside_the_tree.write_text(f"COSMA_SRC_A_TOKEN={SECRET_MARKER}\n", encoding="utf-8")
    error = refusal({**baseline, SECRET_STORE_VARIABLE: str(store_inside_the_tree)})
    assert SECRET_MARKER not in error.summary
    assert SECRET_MARKER not in str(error.detail.for_protected_debug())


# --- both entrypoints, as processes -----------------------------------------


@pytest.mark.parametrize("module", ENTRYPOINTS)
def test_sec_001_each_entrypoint_refuses_a_store_inside_the_working_tree(
    baseline: dict[str, str], store_inside_the_tree: Path, module: str
) -> None:
    """The scenario's Action: start the worker entrypoint, and then the API one.

    Until this existed, the launcher's protection was a convention rather than an
    invariant: a bare ``python -m`` had no guard at all.
    """
    result = start_entrypoint(
        module, {**baseline, SECRET_STORE_VARIABLE: str(store_inside_the_tree)}
    )
    assert result.returncode == EX_CONFIG, result.stderr
    assert "CONFIGURATION_INVALID" in result.stderr
    assert SECRET_STORE_VARIABLE in result.stderr
    assert str(store_inside_the_tree) in result.stderr
    assert SECRET_SETUP_POINTER in result.stderr


@pytest.mark.parametrize("module", ENTRYPOINTS)
def test_sec_001_no_database_connection_is_attempted_when_the_store_is_refused(
    baseline: dict[str, str], store_inside_the_tree: Path, module: str
) -> None:
    """"Refused before any database connection", as an observation on the process.

    The baseline names a socket directory with nothing in it, so a process that
    reached the database would fail with a *connection* error naming that directory
    — a distinct, unmistakable message. Instead the only error the process reports
    is the configuration one, and it names the store. Two things are asserted
    because either alone is weak: that the connection failure is absent, and that
    exactly one error event was written.

    The driver being *imported* is not the question and is not asserted: both
    entrypoints import psycopg at module load, long before ``main`` runs. What
    SEC-001 requires is that no connection is opened, and
    ``test_sec_003_no_database_module_is_loaded_when_configuration_is_refused``
    separately establishes that the configuration layer holds no database code.
    """
    result = start_entrypoint(
        module, {**baseline, SECRET_STORE_VARIABLE: str(store_inside_the_tree)}
    )
    assert result.returncode == EX_CONFIG, result.stderr
    errors = [record for record in log_events(result.stderr) if record["level"] == "ERROR"]
    assert len(errors) == 1, result.stderr
    assert errors[0]["error_class"] == ErrorClass.CONFIGURATION_INVALID
    assert SECRET_STORE_VARIABLE in errors[0]["error_summary"]
    assert "cannot reach the platform" not in result.stderr
    assert baseline["COSMA_DB_HOST"] not in result.stderr


def test_sec_001_the_worker_entrypoint_starts_with_an_unreadable_store_outside_the_tree(
    database: PlatformConfig, store_outside_the_tree: Path
) -> None:
    """Case b against a real process: it reaches its loop without opening the store."""
    store_outside_the_tree.chmod(UNREADABLE)
    try:
        finished = run_worker(
            database, "--once", COSMA_SECRET_SOURCE=str(store_outside_the_tree)
        )
    finally:
        store_outside_the_tree.chmod(READ_ONLY_OWNER)
    assert finished.returncode == 0, finished.stderr
    assert [record for record in log_events(finished.stderr) if record["event"] == "worker.started"]


def test_sec_001_the_api_entrypoint_starts_with_an_unreadable_store_outside_the_tree(
    database: PlatformConfig, store_outside_the_tree: Path
) -> None:
    """Case b for the second entrypoint. It serves, and it never read the store."""
    store_outside_the_tree.chmod(UNREADABLE)
    try:
        with running_api(database, COSMA_SECRET_SOURCE=str(store_outside_the_tree)) as api:
            response = httpx.get(f"{api.base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS)
            assert response.status_code == 200, response.text
    finally:
        store_outside_the_tree.chmod(READ_ONLY_OWNER)
    finished = api.collected()
    assert finished.returncode == 0, finished.stderr
    assert [record for record in log_events(finished.stderr) if record["event"] == "api.started"]


# --- the two halves of the guard are one guard -------------------------------


def test_sec_001_the_platform_and_the_test_session_measure_the_same_tree() -> None:
    """A guard measuring the wrong root would pass everything.

    ``WORKING_TREE_ROOT`` is derived from this module's own location here, by a
    different route than ``config.py`` uses, so a moved file changes one and not the
    other.
    """
    assert Path(__file__).resolve().parents[3] == WORKING_TREE_ROOT
    assert (WORKING_TREE_ROOT / "pyproject.toml").is_file()
    assert (WORKING_TREE_ROOT / "AGENTS.md").is_file()


def load_session_conftest() -> ModuleType:
    """Load ``tests/conftest.py`` as a module, by path.

    Loaded from the file rather than fetched out of ``sys.modules``, because whether
    pytest has already imported it depends on which paths this run selected — and
    ``-k sec_001`` against the experiment directory alone does not select it. A hole
    in the scenario's own verification command is not an acceptable price for a
    shorter test.
    """
    location = WORKING_TREE_ROOT / "tests" / "conftest.py"
    specification = importlib.util.spec_from_file_location("cosma_session_conftest", location)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_sec_001_the_test_session_guard_calls_the_platform_guard() -> None:
    """SEC-001 requires both halves to refuse the same paths.

    The strongest available form of that is one implementation, so this asserts the
    session conftest holds a reference to the same function object rather than a
    second copy of the comparison. Two copies of a path comparison are two things
    that can disagree, and the one that disagreed would be the leak.
    """
    session_conftest = load_session_conftest()
    assert session_conftest.secret_store_location_problem is secret_store_location_problem
    assert session_conftest.WORKING_TREE_ROOT == WORKING_TREE_ROOT
    assert session_conftest.REPO_ROOT == WORKING_TREE_ROOT


def test_sec_001_the_test_session_guard_refuses_what_the_platform_refuses(
    store_inside_the_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The behavioural half: the session hook stops a run the platform would refuse.

    Identity of the function is not quite enough on its own — a hook could hold the
    reference and never call it — so the hook is invoked with the environment each
    case sets and its answer is observed.
    """
    session_conftest = load_session_conftest()
    monkeypatch.setenv(SECRET_STORE_VARIABLE, str(store_inside_the_tree))
    with pytest.raises(pytest.UsageError) as raised:
        session_conftest.pytest_sessionstart(None)
    assert str(store_inside_the_tree) in str(raised.value)
    assert SECRET_SETUP_POINTER in str(raised.value)

    monkeypatch.delenv(SECRET_STORE_VARIABLE)
    assert session_conftest.pytest_sessionstart(None) is None
