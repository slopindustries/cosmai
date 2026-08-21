#!/usr/bin/env bash
#
# Type-check and lint every add-on under apps/addons/, one at a time.
#
#   apps/scripts/check-addons.sh
#   apps/scripts/check-addons.sh addons/collector.trendradar.rest
#
# Mirrors the repository root's own `scripts/check-addons.sh` for the same reason:
# add-ons are independent roots loaded by path rather than imported by name
# (DP-008 D2), every add-on's entry file is conventionally `handler.py`, and
# `apps/pyproject.toml` excludes `addons/` from the tree-wide `mypy --strict .` run
# because two add-ons collide in mypy's single module namespace the moment both
# exist ("Duplicate module named handler") — first hit here when
# `addons/collector.trendradar.rest/handler.py` collided with
# `tests/fixtures/normalizer.conformance/handler.py`. See
# `docs/conventions/addon-authoring.md` for the full reasoning; this script is the
# `apps/` counterpart the exclude leaves nothing else to check add-ons with.
#
# Run from anywhere; paths below are resolved relative to this script's own
# location, not the caller's working directory.

set -euo pipefail

apps_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
addons_root="$apps_root/addons"
venv="$apps_root/.venv/bin"

if [ ! -x "$venv/mypy" ]; then
    echo "check-addons: $venv/mypy is missing; run 'cd apps && uv sync' first" >&2
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
    # Not an error. DP-008 D8 makes the directory the installed set, so "no
    # add-on is installed" is a state rather than a fault.
    echo "check-addons: no add-on found under $addons_root"
    exit 0
fi

failed=0
for target in "${targets[@]}"; do
    name="$(basename "${target%/}")"
    printf '%-32s' "$name"
    # Files are named explicitly, not the directory, for the same reason the root
    # script gives: a directory argument would obey pyproject.toml's `addons/`
    # exclude and leave this checking nothing at all.
    mapfile -t sources < <(find "$target" -name '*.py' -type f | sort)
    if [ "${#sources[@]}" -eq 0 ]; then
        echo "no Python file"
        failed=1
        continue
    fi
    if "$venv/ruff" check "$target" >/dev/null 2>&1 \
        && "$venv/mypy" --no-incremental --strict "${sources[@]}" >/dev/null 2>&1; then
        echo "ok"
    else
        echo "FAILED"
        "$venv/ruff" check "$target" || true
        "$venv/mypy" --no-incremental --strict "${sources[@]}" || true
        failed=1
    fi
done

exit "$failed"
