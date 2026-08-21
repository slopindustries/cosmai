#!/usr/bin/env bash
#
# Type-check and lint every add-on under apps/addons/, one at a time.
#
#   ./scripts/check-addons.sh              # (run from apps/)
#   ./scripts/check-addons.sh addons/collector.naver.blog
#
# Mirrors the repository root's `scripts/check-addons.sh`, which checks
# `experiments/integrated-p0/addons/` with the root `.venv`. This is the same script
# adapted to this tree's own layout: `apps/addons/` and `apps/.venv`. One at a time is
# not a workaround. Add-ons are deliberately independent roots loaded by path rather
# than imported by name (DP-008 D2), and every add-on's entry file is conventionally
# `handler.py`, so two of them genuinely collide in mypy's single module namespace:
# `mypy addons` reports "Duplicate module named handler" the moment a second add-on
# exists — which `collector.naver.blog` and `normalizer.naver.blog` landing together
# made true immediately rather than hypothetically.
#
# The alternatives were considered and rejected, for the same reasons the root script's
# own comment gives. `--exclude` hides one add-on, which is worse than not checking. An
# `__init__.py` per add-on would make them packages, and add-on ids contain dots and
# hyphens that are not valid identifiers. Checking each root on its own is what the
# layout actually means.
#
# See docs/conventions/addon-authoring.md and this file's own pyproject.toml comment.

set -euo pipefail

apps_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
addons_root="$apps_root/addons"
venv="$apps_root/.venv/bin"

if [ ! -x "$venv/mypy" ]; then
    echo "check-addons: $venv/mypy is missing; run 'uv sync' first" >&2
    exit 1
fi

if [ "$#" -gt 0 ]; then
    targets=("$@")
else
    targets=()
    if [ -d "$addons_root" ]; then
        for candidate in "$addons_root"/*/; do
            [ -f "$candidate/addon.toml" ] || continue
            targets+=("$candidate")
        done
    fi
fi

if [ "${#targets[@]}" -eq 0 ]; then
    # Not an error. DP-008 D8 makes the directory the installed set, so "no add-on
    # is installed" is a state rather than a fault.
    echo "check-addons: no add-on found under $addons_root"
    exit 0
fi

failed=0
for target in "${targets[@]}"; do
    name="$(basename "${target%/}")"
    printf '%-32s' "$name"
    # Files are named explicitly rather than the directory being handed to mypy.
    # pyproject.toml excludes `addons/` from the tree-wide run so that two add-ons
    # both defining `handler` do not collide there, and a directory argument obeys
    # that exclusion — which would leave these checked nowhere at all. A check that
    # silently stops checking is worse than no check. An explicit file path is not
    # filtered by `exclude`, so this keeps working.
    #
    # `--no-incremental` keeps two add-ons that both define `handler` out of one
    # cache entry.
    mapfile -t sources < <(find "$target" -name '*.py' -type f | sort)
    if [ "${#sources[@]}" -eq 0 ]; then
        echo "no Python file"
        failed=1
        continue
    fi
    if "$venv/ruff" check "$target" >/dev/null 2>&1 \
        && "$venv/mypy" --strict --no-incremental "${sources[@]}" >/dev/null 2>&1; then
        echo "ok"
    else
        echo "FAILED"
        "$venv/ruff" check "$target" || true
        "$venv/mypy" --strict --no-incremental "${sources[@]}" || true
        failed=1
    fi
done

exit "$failed"
