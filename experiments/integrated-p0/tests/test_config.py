"""SEC-003 — invalid platform configuration fails loudly and is not retryable.

The scenario's case table drives this file one test per row, and its intent is
what the assertions protect: a process given invalid configuration must refuse to
start, **name** what is wrong, and not substitute a default. The last clause is
the one that decays quietly, so several tests assert not merely that loading
failed but that no fallback value was produced.

Two constraints from the scenario are checked separately, because a green result
on the case table would not imply them:

* the failure precedes any database work;
* the report never dumps the environment, which
  ``docs/conventions/secret-setup.md`` names as its own leak channel.

Every test here is named ``test_sec_003_*`` so that the scenario's own
Verification command — ``pytest experiments/integrated-p0/tests -k sec_003`` —
selects them.

Both entrypoints now exist, and the scenario's Action — "start the worker
entrypoint and then the API entrypoint" — is executed at the end of this file
against ``python -m platform_core.worker`` and ``python -m platform_core.api``
themselves, not only against ``load_config``. The unit-level cases stay because
they say which setting was refused and why, which an exit status cannot.

SEC-002's configuration half lives here too, for the same reason it is one
function call away from SEC-003's: a non-loopback bind is a rejected setting, and
the guard that rejects it is a parser in the same table. The parts of SEC-002 that
need a bound socket are in ``test_api.py``.
"""

from __future__ import annotations

import ipaddress
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from platform_core.config import (
    ADDON_DIR_VARIABLE,
    DEFAULT_API_HOST,
    KNOWN_NAMES,
    RECOGNIZED_UNUSED,
    PlatformConfig,
    load_config,
    unrecognized_variables,
)
from platform_core.errors import ConfigurationInvalidError, ErrorClass

from tests.conftest import (
    ENTRYPOINTS,
    EX_CONFIG,
    EXPERIMENT_ROOT,
    REPO_ROOT,
    SECRET_MARKER,
    log_events,
    start_entrypoint,
    start_worker,
    wait_for_worker,
)

IPV6_LOOPBACK = "::1"

UNRELATED_NAME = "COSMA_TYPO_LEASE_SECONDS"
UNRELATED_VALUE = "45"
FOREIGN_NAME = "SOME_UNRELATED_VARIABLE"
FOREIGN_VALUE = "value-that-must-not-be-dumped"

# Exercised as a subprocess so the exit status, not just the exception, is observed.
PROBE = """
import sys

from platform_core.config import load_config
from platform_core.errors import ConfigurationInvalidError

try:
    load_config()
except ConfigurationInvalidError as error:
    sys.stderr.write(error.error_class.value + "\\n")
    sys.stderr.write(error.summary + "\\n")
    sys.stdout.write("db-driver-loaded=" + str("psycopg" in sys.modules) + "\\n")
    raise SystemExit(78)
raise SystemExit(0)
"""


def rejection(environment: Mapping[str, str]) -> ConfigurationInvalidError:
    """Load, expect refusal, and hand back the error for inspection."""
    with pytest.raises(ConfigurationInvalidError) as raised:
        load_config(environment)
    return raised.value


def reported_text(error: ConfigurationInvalidError) -> str:
    """Everything an operator or a log could see, protected detail included."""
    return " ".join(
        [
            str(error),
            repr(error),
            str(error.operator_view()),
            str(error.detail.for_protected_debug()),
        ]
    )


def test_sec_003_a_valid_baseline_loads_with_documented_defaults(baseline: dict[str, str]) -> None:
    config = load_config(baseline)
    assert config.db_host == Path(baseline["COSMA_DB_HOST"])
    assert config.db_name == "cosma_p0"
    assert config.db_user == "tester"
    assert config.lease_seconds == 30
    assert config.retry_base_ms == 100
    assert config.retry_max_ms == 30000
    assert config.api_host == DEFAULT_API_HOST == "127.0.0.1"
    assert config.api_port == 8000
    assert config.log_level == "INFO"
    assert config.unrecognized_variables == ()
    assert config.warnings() == ()


def test_sec_003_stated_values_override_the_defaults(baseline: dict[str, str]) -> None:
    config = load_config(
        {
            **baseline,
            "COSMA_LEASE_SECONDS": "5",
            "COSMA_RETRY_BASE_MS": "10",
            "COSMA_RETRY_MAX_MS": "20",
            "COSMA_API_HOST": IPV6_LOOPBACK,
            "COSMA_API_PORT": "9001",
            "COSMA_LOG_LEVEL": "debug",
        }
    )
    assert (config.lease_seconds, config.retry_base_ms, config.retry_max_ms) == (5, 10, 20)
    assert (config.api_host, config.api_port, config.log_level) == (IPV6_LOOPBACK, 9001, "DEBUG")


# --- SEC-003 case table -----------------------------------------------------


def test_sec_003_case_a_db_host_unset(baseline: dict[str, str]) -> None:
    del baseline["COSMA_DB_HOST"]
    error = rejection(baseline)
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID
    assert not error.retryable
    assert "COSMA_DB_HOST" in error.summary
    assert "is not set" in error.summary


def test_sec_003_case_b_db_name_unset(baseline: dict[str, str]) -> None:
    del baseline["COSMA_DB_NAME"]
    error = rejection(baseline)
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID
    assert "COSMA_DB_NAME" in error.summary


def test_sec_003_case_c_db_host_names_a_path_that_does_not_exist(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    baseline["COSMA_DB_HOST"] = str(tmp_path / "absent")
    error = rejection(baseline)
    assert "COSMA_DB_HOST" in error.summary
    assert "does not exist" in error.summary


def test_sec_003_case_c_db_host_naming_a_file_is_also_refused(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    """A socket directory that is a file is the same class of mistake."""
    ordinary_file = tmp_path / "not-a-directory"
    ordinary_file.write_text("", encoding="utf-8")
    baseline["COSMA_DB_HOST"] = str(ordinary_file)
    error = rejection(baseline)
    assert "COSMA_DB_HOST" in error.summary
    assert "not one" in error.summary


@pytest.mark.parametrize("given", ["soon", "30s", "", "  ", "3.5"])
def test_sec_003_case_d_a_numeric_setting_given_a_non_numeric_value(
    baseline: dict[str, str], given: str
) -> None:
    error = rejection({**baseline, "COSMA_LEASE_SECONDS": given})
    assert "COSMA_LEASE_SECONDS" in error.summary
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID


@pytest.mark.parametrize("given", ["0", "-1", "-30"])
def test_sec_003_case_e_a_numeric_setting_given_zero_or_a_negative_value(
    baseline: dict[str, str], given: str
) -> None:
    error = rejection({**baseline, "COSMA_LEASE_SECONDS": given})
    assert "COSMA_LEASE_SECONDS" in error.summary
    assert "greater than zero" in error.summary


def test_sec_003_case_f_an_unknown_prefixed_variable_is_reported_and_not_fatal(
    baseline: dict[str, str],
) -> None:
    """Rejecting it would fail on environment noise; hiding it would hide a typo."""
    config = load_config({**baseline, UNRELATED_NAME: UNRELATED_VALUE})
    assert config.unrecognized_variables == (UNRELATED_NAME,)
    assert config.lease_seconds == 30
    warnings = config.warnings()
    assert len(warnings) == 1
    assert UNRELATED_NAME in warnings[0]


def test_sec_003_case_f_a_variable_outside_the_prefix_is_not_even_reported(
    baseline: dict[str, str],
) -> None:
    config = load_config({**baseline, FOREIGN_NAME: FOREIGN_VALUE})
    assert config.unrecognized_variables == ()


# --- Rules the case table depends on ----------------------------------------


@pytest.mark.parametrize(
    ("name", "given"),
    [
        ("COSMA_LEASE_SECONDS", "0"),
        ("COSMA_RETRY_BASE_MS", "nope"),
        ("COSMA_API_PORT", "70000"),
        ("COSMA_LOG_LEVEL", "LOUD"),
    ],
)
def test_sec_003_no_default_is_substituted_for_a_rejected_value(
    baseline: dict[str, str], name: str, given: str
) -> None:
    """secret-setup.md: never continue on an empty value or a fallback."""
    error = rejection({**baseline, name: given})
    assert name in error.summary


def test_sec_003_every_problem_is_named_in_one_report(baseline: dict[str, str]) -> None:
    del baseline["COSMA_DB_NAME"]
    error = rejection({**baseline, "COSMA_LEASE_SECONDS": "0", "COSMA_API_PORT": "0"})
    for name in ("COSMA_DB_NAME", "COSMA_LEASE_SECONDS", "COSMA_API_PORT"):
        assert name in error.summary
    rejected = error.detail.for_protected_debug()["rejected"]
    assert {item["setting"] for item in rejected} == {
        "COSMA_DB_NAME",
        "COSMA_LEASE_SECONDS",
        "COSMA_API_PORT",
    }


def test_sec_003_a_backoff_window_that_cannot_hold_is_refused(baseline: dict[str, str]) -> None:
    error = rejection({**baseline, "COSMA_RETRY_BASE_MS": "5000", "COSMA_RETRY_MAX_MS": "100"})
    assert "COSMA_RETRY_MAX_MS" in error.summary
    assert "COSMA_RETRY_BASE_MS" in error.summary


def test_sec_003_an_equal_backoff_window_is_allowed(baseline: dict[str, str]) -> None:
    config = load_config({**baseline, "COSMA_RETRY_BASE_MS": "100", "COSMA_RETRY_MAX_MS": "100"})
    assert config.retry_base_ms == config.retry_max_ms == 100


def test_sec_003_the_report_names_settings_but_never_dumps_the_environment(
    baseline: dict[str, str],
) -> None:
    """secret-setup.md names an environment dump as a leak channel of its own."""
    del baseline["COSMA_DB_HOST"]
    error = rejection(
        {
            **baseline,
            FOREIGN_NAME: FOREIGN_VALUE,
            UNRELATED_NAME: UNRELATED_VALUE,
            "COSMA_API_TOKEN": "marker-must-not-leak-42",
        }
    )
    text = reported_text(error)
    assert "COSMA_DB_HOST" in text
    assert FOREIGN_VALUE not in text
    assert FOREIGN_NAME not in text
    assert "marker-must-not-leak-42" not in text
    assert baseline["COSMA_DB_USER"] not in text


def test_sec_003_a_rejected_value_is_shown_unless_its_name_reads_as_a_secret(
    baseline: dict[str, str],
) -> None:
    """SEC-003 defers the decision to SEC-004's key-name rule."""
    error = rejection({**baseline, "COSMA_LEASE_SECONDS": "soon"})
    assert "soon" in error.summary, "detection control failed"


def test_sec_003_the_configuration_error_is_the_contract_class(baseline: dict[str, str]) -> None:
    del baseline["COSMA_DB_USER"]
    error = rejection(baseline)
    assert error.operator_view() == {
        "error_class": "CONFIGURATION_INVALID",
        "error_summary": error.summary,
        "retryable": False,
    }


def test_sec_003_the_known_and_recognized_names_do_not_overlap() -> None:
    assert not KNOWN_NAMES & RECOGNIZED_UNUSED
    assert unrecognized_variables(dict.fromkeys(RECOGNIZED_UNUSED, "x")) == ()
    assert unrecognized_variables(dict.fromkeys(KNOWN_NAMES, "x")) == ()


def test_sec_003_the_add_on_directory_is_not_reported_as_ignored() -> None:
    """``COSMA_ADDON_DIR`` is read by ``addon_host``, so calling it ignored is false.

    The variable is not a ``Setting`` here — DP-008 D1 keeps the add-on layer's
    settings in the add-on layer — but this module still has to know the name,
    because the report's wording is a claim about behaviour and the claim would be
    untrue. A standing false positive is worse than noise: this report exists to
    catch a typo in a real setting name, and an operator who learns to skip it
    loses the one thing it is for.
    """
    assert unrecognized_variables({ADDON_DIR_VARIABLE: "/somewhere"}) == ()


def test_sec_003_a_typo_in_the_add_on_directory_is_still_caught() -> None:
    """The positive control. Without it the assertion above proves nothing.

    If the allowance were a prefix match, or the report had simply stopped working,
    the test above would pass either way. This is the case it must still catch.
    """
    typo = f"{ADDON_DIR_VARIABLE}R"
    assert unrecognized_variables({typo: "/somewhere"}) == (typo,)


def test_sec_003_the_configuration_is_immutable(baseline: dict[str, str]) -> None:
    config = load_config(baseline)
    assert isinstance(config, PlatformConfig)
    with pytest.raises(AttributeError):
        config.lease_seconds = 1  # type: ignore[misc]


def test_sec_003_load_config_reads_the_process_environment_by_default(
    baseline: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith("COSMA_"):
            monkeypatch.delenv(name, raising=False)
    for name, value in baseline.items():
        monkeypatch.setenv(name, value)
    assert load_config().db_name == "cosma_p0"


def test_sec_003_no_database_module_is_loaded_when_configuration_is_refused(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    """SEC-003: cases a–e refuse before a database connection is attempted."""
    del baseline["COSMA_DB_HOST"]
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(probe)],
        cwd=REPO_ROOT,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(EXPERIMENT_ROOT),
            FOREIGN_NAME: FOREIGN_VALUE,
            **baseline,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EX_CONFIG
    assert "CONFIGURATION_INVALID" in result.stderr
    assert "COSMA_DB_HOST" in result.stderr
    assert "db-driver-loaded=False" in result.stdout
    assert FOREIGN_VALUE not in result.stderr + result.stdout


# --- SEC-003's Action: both entrypoints, as processes ------------------------


@pytest.mark.parametrize("module", ENTRYPOINTS)
@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param({"COSMA_DB_HOST": None}, "COSMA_DB_HOST", id="case-a"),
        pytest.param({"COSMA_DB_NAME": None}, "COSMA_DB_NAME", id="case-b"),
        pytest.param(
            {"COSMA_DB_HOST": "/nonexistent-cosma-socket-directory"},
            "does not exist",
            id="case-c",
        ),
        pytest.param({"COSMA_LEASE_SECONDS": "soon"}, "COSMA_LEASE_SECONDS", id="case-d"),
        pytest.param({"COSMA_LEASE_SECONDS": "0"}, "greater than zero", id="case-e"),
    ],
)
def test_sec_003_each_entrypoint_refuses_the_case_table(
    baseline: dict[str, str],
    module: str,
    mutation: dict[str, str | None],
    expected: str,
) -> None:
    """The scenario's Action, executed: cases a–e against each entrypoint.

    The exit status is ``EX_CONFIG`` and not merely non-zero, because a supervisor
    has to be able to tell "this configuration will never work" from "the database
    was not up yet", and only one of those is worth restarting for.
    """
    environment = dict(baseline)
    for name, value in mutation.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    result = start_entrypoint(module, environment)
    assert result.returncode == EX_CONFIG, result.stderr
    assert "CONFIGURATION_INVALID" in result.stderr, result.stderr
    assert expected in result.stderr, result.stderr


def test_sec_003_case_f_the_worker_entrypoint_reports_an_unknown_variable_and_runs(
    database: PlatformConfig,
) -> None:
    """Case f against a real process: reported, and the process reaches its loop.

    A real database is used because "not fatal" is only observable if the process
    has somewhere to get to. The API half of this case is in ``test_api.py``, which
    is where a process that binds a socket is already being started.
    """
    # The two underlying helpers rather than run_worker: its keyword-only timeout
    # and its **overrides cannot be told apart by a type checker at the call site.
    finished = wait_for_worker(
        start_worker(database, "--once", **{UNRELATED_NAME: UNRELATED_VALUE})
    )
    assert finished.returncode == 0, finished.stderr
    recorded = log_events(finished.stderr)
    warnings = [record for record in recorded if record["event"] == "worker.configuration_warning"]
    assert len(warnings) == 1, recorded
    assert UNRELATED_NAME in warnings[0]["detail"]
    assert [record for record in recorded if record["event"] == "worker.started"]
    assert not [record for record in recorded if "configuration_invalid" in record["event"]]


@pytest.mark.parametrize("module", ENTRYPOINTS)
def test_sec_003_neither_entrypoint_prints_the_environment_when_it_refuses(
    baseline: dict[str, str], module: str
) -> None:
    """secret-setup.md names an environment dump as a leak channel of its own."""
    del baseline["COSMA_DB_HOST"]
    result = start_entrypoint(
        module,
        {**baseline, FOREIGN_NAME: FOREIGN_VALUE, "COSMA_API_TOKEN": SECRET_MARKER},
    )
    written = result.stdout + result.stderr
    assert result.returncode == EX_CONFIG
    assert "COSMA_DB_HOST" in written
    assert FOREIGN_NAME not in written
    assert FOREIGN_VALUE not in written
    assert SECRET_MARKER not in written
    assert baseline["COSMA_DB_USER"] not in written


# --- SEC-002, the half that is a configuration decision ---------------------


def test_sec_002_the_default_bind_address_is_loopback(baseline: dict[str, str]) -> None:
    """The charter's "by default" half. The refusal below is the P0-A addition."""
    assert "COSMA_API_HOST" not in baseline
    config = load_config(baseline)
    assert config.api_host == DEFAULT_API_HOST
    assert ipaddress.ip_address(config.api_host).is_loopback


@pytest.mark.parametrize("given", ["127.0.0.1", IPV6_LOOPBACK, "127.0.0.53"])
def test_sec_002_a_loopback_address_is_accepted_exactly_as_stated(
    baseline: dict[str, str], given: str
) -> None:
    config = load_config({**baseline, "COSMA_API_HOST": given})
    assert config.api_host == given
    assert ipaddress.ip_address(config.api_host).is_loopback


@pytest.mark.parametrize(
    "given",
    [
        "0.0.0.0",
        "::",
        "192.168.1.10",
        "10.0.0.5",
        "203.0.113.7",
        "fe80::1",
        "localhost",
        "example.com",
        "",
    ],
)
def test_sec_002_a_non_loopback_bind_address_is_refused(
    baseline: dict[str, str], given: str
) -> None:
    """`CONFIGURATION_INVALID`, not a default. The scenario's step 6 and step 7."""
    error = rejection({**baseline, "COSMA_API_HOST": given})
    assert error.error_class is ErrorClass.CONFIGURATION_INVALID
    assert not error.retryable
    assert "COSMA_API_HOST" in error.summary


def test_sec_002_the_wildcard_address_is_not_silently_corrected(
    baseline: dict[str, str],
) -> None:
    """The one behavior SEC-002 forbids by name.

    Falling back to loopback here would produce a *working* API on a configuration
    the operator got wrong, and the mistake would be discovered the next time
    somebody assumed the setting did something.
    """
    wildcard = "0.0.0.0"
    with pytest.raises(ConfigurationInvalidError) as raised:
        load_config({**baseline, "COSMA_API_HOST": wildcard})
    assert wildcard in raised.value.summary, "the rejected address is named"
    assert "does not fall back" in raised.value.summary
