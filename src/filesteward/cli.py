"""``filesteward`` console entry point.

Command vocabulary is owned by ``plans/active/C-DRIVE-CLEANUP-P04.md``
section 10: ``scan`` / ``validate`` / ``plan`` / ``apply``. This module
must not invent a competing command system, and it contains no cleanup
judgment: it only parses arguments, invokes ``CleanupRun``/
``validate_run``/``triage_run_dir``, and maps outcomes to exit codes.
``apply`` is a refusal seam — it never mutates anything. ``plan`` is
read-only receipt triage (path-prefix buckets); it never nominates
reclaim or grants approval.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Sequence

import filesteward
from filesteward.classify import CacheContract
from filesteward.manifest import triage_run_dir, validate_run
from filesteward.policy.paths import (
    prove_run_dir_under_runtime,
    resolve_run_dir_argument,
)
from filesteward.run import CleanupRun, RunResult

__all__ = [
    "EXIT_INVALID",
    "EXIT_LANE_UNAVAILABLE",
    "EXIT_OK",
    "build_parser",
    "main",
]

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_LANE_UNAVAILABLE = 3

_LANE_STATUS = {
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
    scan.add_argument(
        "--contract",
        action="append",
        default=[],
        metavar="PATH_PREFIX",
        help=(
            "explicit path-prefix contract asserting deterministic "
            "regenerable cache evidence (repeatable)"
        ),
    )
    scan.add_argument(
        "--protect",
        action="append",
        default=[],
        metavar="PATH",
        help="operator-declared protected root to exclude (repeatable)",
    )
    scan.add_argument(
        "--managed",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "path declared system/application-managed: inventoried, but "
            "never an automatic mutation candidate without an explicit "
            "contract (repeatable)"
        ),
    )
    scan.add_argument(
        "--target-free-bytes",
        type=int,
        dest="target_free_bytes",
        default=None,
        help="free-space target for stop-point math (bytes)",
    )
    scan.add_argument(
        "--baseline-free-bytes",
        type=int,
        dest="baseline_free_bytes",
        default=None,
        help="override the measured baseline free space (bytes); tests only",
    )

    validate = subparsers.add_parser(
        "validate", help="validate generated artifacts against their schema"
    )
    validate.add_argument("target", help="run directory or manifest path")

    plan = subparsers.add_parser(
        "plan",
        help=(
            "read-only HUMAN_REVIEW path-prefix triage for an existing run; "
            "writes bucket totals only, never reclaim nominations"
        ),
    )
    plan.add_argument("target", help="run directory containing human-review.csv")
    plan.add_argument(
        "--depth",
        type=int,
        default=2,
        help="path-prefix depth for buckets (default: 2)",
    )
    plan.add_argument(
        "--top",
        type=int,
        default=20,
        help="how many largest buckets to print (default: 20)",
    )

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


def _run_scan(args: argparse.Namespace) -> int:
    contracts = tuple(
        CacheContract(
            contract_id=f"cli-contract-{position}",
            path_prefix=prefix,
            description=(
                "operator-supplied explicit contract via --contract for "
                "this path prefix"
            ),
        )
        for position, prefix in enumerate(args.contract, start=1)
    )
    try:
        result: RunResult = CleanupRun(
            args.root,
            resolve_run_dir_argument(args.run_dir),
            contracts=contracts,
            protected_roots=tuple(args.protect),
            managed_paths=tuple(args.managed),
            target_free_bytes=args.target_free_bytes,
            baseline_free_bytes=args.baseline_free_bytes,
        ).execute()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"filesteward scan: {exc}", file=sys.stderr)
        return EXIT_INVALID

    counts = ", ".join(
        f"{name}={count}"
        for name, count in sorted(result.disposition_counts.items())
    )
    print(f"filesteward scan: {result.inventory_items} items ({counts})")
    print(f"plan rows: {result.plan_rows}")
    print(
        "cumulative projected reclaim: "
        f"{result.cumulative_projected_reclaim_bytes} bytes"
    )
    print(f"artifacts: {result.run_dir}")
    print(
        "All proposed rows are UNAPPROVED evidence; this run produced no "
        "operator approval, no apply, and no deletion."
    )
    return EXIT_OK


def _run_validate(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if target.is_file():
        if target.name != "cleanup-plan.csv":
            print(
                "filesteward validate: expected a run directory or a "
                f"cleanup-plan.csv manifest path; got {target}",
                file=sys.stderr,
            )
            return EXIT_INVALID
        target = target.parent
    if not target.is_dir():
        print(
            f"filesteward validate: run directory not found: {target}",
            file=sys.stderr,
        )
        return EXIT_INVALID
    try:
        errors = validate_run(target)
    except (ValueError, TypeError, OSError, UnicodeError, RuntimeError) as exc:
        print(f"filesteward validate: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if errors:
        print(
            f"filesteward validate: {len(errors)} problem(s) found:",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return EXIT_INVALID
    print(f"filesteward validate: {target} is consistent")
    return EXIT_OK


def _run_plan(args: argparse.Namespace) -> int:
    if args.depth < 1:
        print("filesteward plan: --depth must be >= 1", file=sys.stderr)
        return EXIT_INVALID
    if args.top < 1:
        print("filesteward plan: --top must be >= 1", file=sys.stderr)
        return EXIT_INVALID
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        result = triage_run_dir(target, depth=args.depth)
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        print(f"filesteward plan: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print(
        f"filesteward plan: {result.human_review_rows} review rows -> "
        f"{len(result.buckets)} buckets (depth={result.depth})"
    )
    print(f"artifacts: {result.csv_path}")
    print(f"summary: {result.markdown_path}")
    print(
        "Buckets are UNAPPROVED evidence for operator contract selection; "
        "this command produced no reclaim nomination, no approval, no apply, "
        "and no deletion."
    )
    for row in result.buckets[: args.top]:
        tags = ",".join(row.contract_hint_tags) if row.contract_hint_tags else "-"
        print(
            f"  {row.logical_bytes_known} bytes / {row.item_count} items / "
            f"unknown_size={row.unknown_size_count} / hints={tags} / {row.prefix}"
        )
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "scan":
        return _run_scan(args)
    if args.command == "validate":
        return _run_validate(args)
    if args.command == "plan":
        return _run_plan(args)

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
