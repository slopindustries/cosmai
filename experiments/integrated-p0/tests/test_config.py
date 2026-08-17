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

**Coverage gap.** The scenario's Action says to start the worker and API
entrypoints. Neither exists yet; they arrive with T1.3 and T5. These tests
exercise the validation boundary those entrypoints will call, and the subprocess
case observes a real non-zero exit from a process that loads the configuration —
but not from the entrypoints themselves. The scenario is therefore not fully
executed by a green run of this file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from platform_core.config import (
    DEFAULT_API_HOST,
    KNOWN_NAMES,
    RECOGNIZED_UNUSED,
    PlatformConfig,
    load_config,
    unrecognized_variables,
)
from platform_core.errors import ConfigurationInvalidError, ErrorClass

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "experiments" / "integrated-p0"

EX_CONFIG = 78

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


@pytest.fixture
def baseline(tmp_path: Path) -> dict[str, str]:
    """A valid environment, mutated one variable at a time by each case."""
    socket_directory = tmp_path / "postgres"
    socket_directory.mkdir()
    return {
        "COSMA_DB_HOST": str(socket_directory),
        "COSMA_DB_NAME": "cosma_p0",
        "COSMA_DB_USER": "tester",
    }


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
            "COSMA_API_HOST": "0.0.0.0",
            "COSMA_API_PORT": "9001",
            "COSMA_LOG_LEVEL": "debug",
        }
    )
    assert (config.lease_seconds, config.retry_base_ms, config.retry_max_ms) == (5, 10, 20)
    assert (config.api_host, config.api_port, config.log_level) == ("0.0.0.0", 9001, "DEBUG")


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
