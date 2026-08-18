"""`python -m addon_kit new <addon_id> --kind <kind> [--into DIR]`.

Kept separate from `generator.py` so the generator is importable — and testable —
without going through `argparse` and process exit codes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from addon_api import KINDS, Kind, ManifestError

from addon_kit.generator import DEFAULT_ADDONS_ROOT, AddonKitError, new_addon


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="addon_kit")
    subcommands = parser.add_subparsers(dest="command", required=True)

    new_command = subcommands.add_parser("new", help="generate a new add-on skeleton")
    new_command.add_argument("addon_id", help="the [addon].id this add-on will declare")
    new_command.add_argument("--kind", required=True, choices=KINDS)
    new_command.add_argument(
        "--into",
        type=Path,
        default=None,
        help="output directory; defaults to experiments/integrated-p0/addons/<addon_id>",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    kind: Kind = args.kind
    into: Path = args.into if args.into is not None else DEFAULT_ADDONS_ROOT / args.addon_id
    try:
        target = new_addon(args.addon_id, kind, into)
    except (AddonKitError, ManifestError) as error:
        print(f"addon_kit: {error}", file=sys.stderr)
        return 1
    print(f"addon_kit: wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
