"""`apps/scripts/check-addons.sh` — the per-add-on mypy --strict + ruff gate.

M-C1 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`): `apps/pyproject.toml`'s
`mypy --strict .` excludes `^addons/` (two add-ons both defining `handler.py` collide
in mypy's single module namespace — see the script's own header comment), so the
"101 source files" root gate covers zero of the add-ons. `check-addons.sh` is what
compensates, checking each add-on's files explicitly by path so the exclude cannot
hide it — but nothing before this fix wave ever invoked the script itself. A script
that exists, is honest in `pyproject.toml`'s own comment, and is never run is a
convention, not a control (AGENTS.md: "do not describe a convention as a control").

This test shells out to the real script over the real `apps/addons/` tree, the same
invocation the fix-wave's own closing gates run by hand. No `pytest.skip` if the
script is missing — a missing script is the exact regression this test exists to
catch, so it is asserted present and executable, not silently passed over.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

APPS_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = APPS_ROOT / "scripts" / "check-addons.sh"


def test_the_script_exists_and_is_executable() -> None:
    """Asserted, not skipped-if-absent: a missing or non-executable script is a
    regression this test must fail on, not quietly step around."""
    assert SCRIPT.is_file(), f"{SCRIPT} does not exist"
    assert stat.S_IMODE(SCRIPT.stat().st_mode) & stat.S_IXUSR, f"{SCRIPT} is not executable"


def test_running_it_over_the_real_addons_tree_reports_every_addon_ok() -> None:
    """The real invocation this fix wave's own closing gate runs
    (`apps/scripts/check-addons.sh`, no arguments — every installed add-on). A
    planted type error was independently confirmed (M4/B6 review evidence) to turn
    this `FAILED`; this is the non-mutated, everyday case."""
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=APPS_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, (
        f"check-addons.sh exited {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    addon_dirs = sorted(
        p.parent.name for p in (APPS_ROOT / "addons").glob("*/addon.toml")
    )
    assert addon_dirs, "no add-on is installed under apps/addons — nothing was checked"
    for name in addon_dirs:
        assert f"{name}" in result.stdout, f"{name} is not named in check-addons.sh's output"
    assert "FAILED" not in result.stdout, result.stdout
