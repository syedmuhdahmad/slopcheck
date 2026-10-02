from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from slopfence import __version__, reporters
from slopfence import diff as diffmod
from slopfence.config import ConfigError, load_config
from slopfence.engine import run
from slopfence.models import RULES
from slopfence.registry import OfflineRegistry, PyPIRegistry

EXIT_OK, EXIT_FINDINGS, EXIT_ERROR = 0, 1, 2


def _rule_list(value: str) -> list[str]:
    rules = [r.strip().upper() for r in value.split(",") if r.strip()]
    unknown = [r for r in rules if r not in RULES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown rule(s): {', '.join(unknown)}")
    return rules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slopfence",
        description="Find the junk AI coding assistants leave behind.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path(".")], help="files or directories"
    )
    parser.add_argument(
        "--diff", metavar="REF", help="only report issues on lines changed since REF"
    )
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    parser.add_argument("-o", "--output", type=Path, help="write the report to a file")
    parser.add_argument("--offline", action="store_true", help="skip PyPI lookups (SLOP001)")
    parser.add_argument(
        "--select", type=_rule_list, help="comma-separated rules to run (overrides config)"
    )
    parser.add_argument(
        "--ignore", type=_rule_list, help="comma-separated rules to skip (overrides config)"
    )
    parser.add_argument(
        "--exclude",
        type=lambda v: [p.strip() for p in v.split(",") if p.strip()],
        help="comma-separated paths or globs to skip (overrides config)",
    )
    parser.add_argument("--exit-zero", action="store_true", help="exit 0 even if issues are found")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--list-rules", action="store_true", help="list rules and exit")
    parser.add_argument("--version", action="version", version=f"slopfence {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        for rule in RULES.values():
            print(f"{rule.id}  {rule.severity.value:<6}  {rule.name}: {rule.summary}")
        return EXIT_OK

    for path in args.paths:
        if not path.exists():
            print(f"slopfence: error: {path} does not exist", file=sys.stderr)
            return EXIT_ERROR

    start = args.paths[0].resolve()
    start_dir = start if start.is_dir() else start.parent
    root = diffmod.repo_root(start_dir)
    if root is None:
        cwd = Path.cwd().resolve()
        root = cwd if start_dir == cwd or cwd in start_dir.parents else start_dir

    try:
        config = load_config(root)
    except ConfigError as err:
        print(f"slopfence: error: {err}", file=sys.stderr)
        return EXIT_ERROR
    # Command-line options replace the matching config values.
    select = args.select if args.select is not None else config.select
    ignore = args.ignore if args.ignore is not None else config.ignore
    exclude = args.exclude if args.exclude is not None else config.exclude

    changed = None
    if args.diff:
        try:
            changed = diffmod.changed_lines(root, args.diff)
        except diffmod.DiffError as err:
            print(f"slopfence: error: --diff {args.diff}: {err}", file=sys.stderr)
            return EXIT_ERROR

    registry = OfflineRegistry() if args.offline else PyPIRegistry()
    result = run(
        args.paths,
        root,
        registry,
        select=select,
        ignore=ignore,
        changed=changed,
        exclude=exclude,
    )
    if isinstance(registry, PyPIRegistry):
        registry.save()

    if args.format == "json":
        report = reporters.as_json(result)
    elif args.format == "sarif":
        report = reporters.sarif(result)
    else:
        color = (
            not args.no_color
            and args.output is None
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        report = reporters.text(result, color=color)

    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)

    if result.findings and not args.exit_zero:
        return EXIT_FINDINGS
    return EXIT_OK
