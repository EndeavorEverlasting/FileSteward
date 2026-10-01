"""``filesteward`` console entry point.

Command vocabulary is owned by ``plans/active/C-DRIVE-CLEANUP-P04.md``
section 10: ``scan`` / ``validate`` / ``apply``. This module must not
invent a competing command system, and it contains no cleanup judgment.

Lane wiring status is explicit: until the owning lane registers the real
implementation, invocations exit with ``EXIT_LANE_UNAVAILABLE`` rather
than pretending to have produced evidence. ``apply`` is a refusal seam
for this sprint — it never mutates anything.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

import filesteward

__all__ = ["EXIT_LANE_UNAVAILABLE", "EXIT_OK", "build_parser", "main"]

EXIT_OK = 0
EXIT_LANE_UNAVAILABLE = 3

_LANE_STATUS = {
    "scan": "inventory scanning is wired by lane L1/L3",
    "validate": "artifact validation is wired by lane L3",
    "apply": "apply is a refusal seam; real apply is outside this sprint",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filesteward",
        description=(
            "Read-only file triage and cleanup analysis. "
            "Ambiguity is reported for operator review, never resolved."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"filesteward {filesteward.__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan", help="read-only inventory of an approved root"
    )
    scan.add_argument("root", help="root directory to inventory (read-only)")
    scan.add_argument(
        "--run-dir",
        required=True,
        dest="run_dir",
        help="runtime output directory (beneath the ignored var/ tree)",
    )

    validate = subparsers.add_parser(
        "validate", help="validate generated artifacts against their schema"
    )
    validate.add_argument("target", help="run directory or manifest path")

    apply_parser = subparsers.add_parser(
        "apply",
        help="refusal seam; actions require a separate operator approval artifact",
    )
    apply_parser.add_argument("target", help="manifest path")
    apply_parser.add_argument(
        "--execute",
        action="store_true",
        help="never honored in this sprint; apply always refuses",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    status = _LANE_STATUS[args.command]
    print(
        f"filesteward {filesteward.__version__}: "
        f"'{args.command}' is not available yet — {status}. "
        "No filesystem state was read or changed.",
        file=sys.stderr,
    )
    return EXIT_LANE_UNAVAILABLE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
