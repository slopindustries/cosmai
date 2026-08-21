"""The add-on author's commands.

    python -m addon_kit new <addon_id> --kind <kind> [--into DIR]
    python -m addon_kit run <directory> [--fixtures DIR] [--config JSON] [--cursor JSON]
    python -m addon_kit run <directory> --conformance [--fixtures DIR] [--config JSON]

Kept separate from `generator.py`, `harness.py`, and `conformance.py` so all three are
importable — and testable — without going through `argparse` and process exit codes.

`run` is the authoring loop and **not** an integration test. `harness.py`'s docstring
lists the four platform behaviours it cannot show you; the short version is that
passing here means the add-on's logic works against the contract's shapes, and says
nothing about whether it works against the platform.

`run --conformance` is the same non-claim, restated for a checklist rather than a
transcript: `addon_kit.conformance`'s own module docstring is explicit about what it
checks (manifest validity, the contract-range gate, kind-capability conformance
through one harness run, and — for a collector or importer — the cursor resume
scenario) and, deliberately, what it does not (byte-identical determinism, dropped
from the P1 contract requirement by DP-030 D1).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from addon_api import KINDS, AddonManifest, Kind, ManifestError
from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.generator import DEFAULT_ADDONS_ROOT, AddonKitError, new_addon
from addon_kit.harness import HarnessError, format_report, load_fixtures, run_addon


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

    run_command = subcommands.add_parser(
        "run", help="run an add-on against captured fixtures; not an integration test"
    )
    run_command.add_argument("directory", type=Path, help="the add-on's directory")
    run_command.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="directory of captured responses named <endpoint>.<n>.<ext>",
    )
    run_command.add_argument(
        "--config", default="{}", help="the source configuration, as JSON"
    )
    run_command.add_argument(
        "--cursor",
        default=None,
        help="the cursor this run starts from, as JSON; omit to start with none",
    )
    run_command.add_argument(
        "--status",
        type=int,
        default=200,
        help="the HTTP status every fixture is served with, for exercising a failure path",
    )
    run_command.add_argument(
        "--conformance",
        action="store_true",
        help=(
            "run addon_kit.conformance's checklist instead of one ordinary pass: "
            "manifest validity, the contract-range gate, kind-capability conformance, "
            "and (collector/importer) the cursor resume scenario. --status and --cursor "
            "are not used in this mode."
        ),
    )
    return parser


def _new(args: argparse.Namespace) -> int:
    kind: Kind = args.kind
    into: Path = args.into if args.into is not None else DEFAULT_ADDONS_ROOT / args.addon_id
    try:
        target = new_addon(args.addon_id, kind, into)
    except (AddonKitError, ManifestError) as error:
        print(f"addon_kit: {error}", file=sys.stderr)
        return 1
    print(f"addon_kit: wrote {target}")
    return 0


def _run_conformance(args: argparse.Namespace) -> int:
    """Exit 0 when every check passed, 1 otherwise. See `addon_kit.conformance`."""
    try:
        fixtures = load_fixtures(args.fixtures) if args.fixtures is not None else {}
        config = json.loads(args.config)
    except HarnessError as error:
        print(f"addon_kit: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"addon_kit: --config must be JSON: {error}", file=sys.stderr)
        return 1

    report = run_conformance(args.directory, fixtures=fixtures, config=config)
    print(format_conformance_report(report))
    return 0 if report.passed else 1


def _run(args: argparse.Namespace) -> int:
    """Exit 0 when the add-on returned, 1 when it failed or could not be run.

    An add-on that *reported* a failure exits non-zero even though the harness worked:
    from an author's seat "my add-on raised AddonPermanent" is a failed run, and the
    transcript above the exit code says which kind of failure it was.
    """
    if args.conformance:
        return _run_conformance(args)
    try:
        manifest = AddonManifest.load(args.directory / "addon.toml")
        fixtures = load_fixtures(args.fixtures) if args.fixtures is not None else {}
        result = run_addon(
            args.directory,
            fixtures=fixtures,
            config=json.loads(args.config),
            cursor=None if args.cursor is None else json.loads(args.cursor),
            status=args.status,
        )
    except (HarnessError, ManifestError) as error:
        print(f"addon_kit: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"addon_kit: --config and --cursor must be JSON: {error}", file=sys.stderr)
        return 1

    print(format_report(result, manifest))
    if result.failed:
        return 1
    if result.emitted_count_disagrees():
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _run(args)
    return _new(args)


if __name__ == "__main__":
    raise SystemExit(main())
