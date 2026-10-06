"""``filesteward`` console entry point.

Command vocabulary is owned by the active plan: ``scan`` / ``validate`` /
``plan`` / ``visualize`` / ``delete-manifest`` / ``delete-preflight`` /
``delete-approve`` / ``delete-execute`` / ``apply``. This module must not
invent a competing command system, and it contains no cleanup judgment:
it only parses arguments, invokes owned run/delete seams, and maps
outcomes to exit codes.
``apply`` is a refusal seam — it never mutates anything. ``plan`` is
read-only receipt triage (path-prefix buckets); it never nominates
reclaim or grants approval. ``visualize`` is read-only report publication
from validated artifacts; it never mutates source inventory.
``delete-manifest`` emits an UNAPPROVED exact delete set; it never deletes.
``delete-preflight`` is read-only observation. ``delete-approve`` writes a
delete-specific irreversible approval artifact. ``delete-execute`` may
permanently delete only after approval + fresh PASS preflight and only
when explicitly flagged; it never defaults to live personal roots.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

import filesteward
from filesteward.classify import CacheContract
from filesteward.deletion import (
    DELETE_APPROVAL_FILENAME,
    DELETE_MANIFEST_FILENAME,
    build_delete_approval,
    emit_delete_manifest,
    execute_permanent_delete,
    run_preflight,
    write_delete_approval,
    write_preflight_receipt,
)
from filesteward.manifest import triage_run_dir, validate_run
from filesteward.policy.paths import (
    is_lexically_within,
    normalize_declared_path,
    prove_run_dir_under_runtime,
    resolve_run_dir_argument,
)
from filesteward.run import CleanupRun, RunResult
from filesteward.visualization.report import visualize_run_dir

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

    visualize = subparsers.add_parser(
        "visualize",
        help=(
            "read-only offline HTML decision map for a validated run; "
            "publishes under the run directory without mutating source artifacts"
        ),
    )
    visualize.add_argument(
        "target",
        help="run directory beneath the canonical ignored var/runs/ tree",
    )

    delete_manifest = subparsers.add_parser(
        "delete-manifest",
        help=(
            "emit an exact UNAPPROVED delete-manifest from RECLAIM_PROVEN "
            "cleanup-plan rows; writes operator surface; mutates no scanned targets"
        ),
    )
    delete_manifest.add_argument(
        "target",
        help="run directory beneath the canonical ignored var/runs/ tree",
    )

    delete_preflight = subparsers.add_parser(
        "delete-preflight",
        help=(
            "run fail-closed no-mutation delete preflight against "
            "delete-manifest.json; writes delete-preflight.json"
        ),
    )
    delete_preflight.add_argument(
        "target",
        help="run directory beneath the canonical ignored var/runs/ tree",
    )
    delete_preflight.add_argument(
        "--scan-root",
        required=True,
        dest="scan_root",
        help="approved scan root; paths escaping this root fail closed",
    )

    delete_approve = subparsers.add_parser(
        "delete-approve",
        help=(
            "write filesteward.delete-approval/v1 for DELETE_PERMANENTLY "
            "bound to delete-manifest.json + PASS delete-preflight.json"
        ),
    )
    delete_approve.add_argument(
        "target",
        help="run directory beneath the canonical ignored var/runs/ tree",
    )
    delete_approve.add_argument(
        "--irreversible-confirmation",
        required=True,
        dest="irreversible_confirmation",
        help="non-empty operator confirmation token for irreversible delete",
    )
    delete_approve.add_argument(
        "--item-id",
        action="append",
        default=[],
        dest="item_ids",
        metavar="ITEM_ID",
        help=(
            "approved item id (repeatable); default = all delete-manifest items"
        ),
    )

    delete_execute = subparsers.add_parser(
        "delete-execute",
        help=(
            "permanently delete approved items after fresh PASS preflight; "
            "requires --i-understand-irreversible and --scan-root; "
            "refuses live personal home roots"
        ),
    )
    delete_execute.add_argument(
        "target",
        help="run directory beneath the canonical ignored var/runs/ tree",
    )
    delete_execute.add_argument(
        "--scan-root",
        required=True,
        dest="scan_root",
        help="scan root bounding deletable paths (required; no default)",
    )
    delete_execute.add_argument(
        "--i-understand-irreversible",
        action="store_true",
        dest="i_understand_irreversible",
        help="required acknowledgment that permanent delete is irreversible",
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


def _run_visualize(args: argparse.Namespace) -> int:
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        result = visualize_run_dir(target)
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError) as exc:
        print(f"filesteward visualize: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print(
        f"filesteward visualize: {result.node_count} nodes -> {result.report_path}"
    )
    print(
        "Report is read-only UNAPPROVED evidence for operator review; "
        "this command produced no contract, no approval, no apply, and no deletion."
    )
    return EXIT_OK


def _run_delete_manifest(args: argparse.Namespace) -> int:
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        result = emit_delete_manifest(target)
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError) as exc:
        print(f"filesteward delete-manifest: {exc}", file=sys.stderr)
        return EXIT_INVALID

    totals = result.totals
    print(
        f"filesteward delete-manifest: item_count={result.item_count} "
        f"authorization={result.authorization_state} "
        f"intended_action={result.intended_action}"
    )
    print(
        "totals: "
        f"logical={totals.get('logical_size_bytes')} "
        f"allocated={totals.get('allocated_size_bytes')} "
        f"projected_reclaim={totals.get('projected_reclaim_bytes')} "
        f"quality={totals.get('projection_quality')}"
    )
    print(f"manifest: {result.manifest_path}")
    print(f"surface: {result.html_path}")
    print(f"surface_text: {result.text_path}")
    print(
        "Delete set is UNAPPROVED evidence only; nothing was mutated, "
        "no deletion occurred, and permanent deletion is not claimed."
    )
    return EXIT_OK


def _load_run_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def _run_delete_preflight(args: argparse.Namespace) -> int:
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        manifest_path = target / DELETE_MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise ValueError(f"missing {DELETE_MANIFEST_FILENAME}")
        scan_root = normalize_declared_path(args.scan_root)
        plan_path = target / "cleanup-plan.csv"
        result = run_preflight(
            manifest_path,
            scan_root=scan_root,
            cleanup_plan_path=plan_path if plan_path.is_file() else None,
        )
        out = write_preflight_receipt(target / "delete-preflight.json", result)
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError) as exc:
        print(f"filesteward delete-preflight: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print(
        f"filesteward delete-preflight: overall={result.overall} "
        f"mutated_filesystem={result.mutated_filesystem} "
        f"items={len(result.items)}"
    )
    print(f"receipt: {out}")
    if result.overall != "PASS":
        print(
            "Preflight FAIL: no mutation occurred; delete-approve/execute blocked.",
            file=sys.stderr,
        )
        return EXIT_INVALID
    print("Preflight PASS: observation only; nothing was mutated.")
    return EXIT_OK


def _run_delete_approve(args: argparse.Namespace) -> int:
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        manifest_path = target / DELETE_MANIFEST_FILENAME
        preflight_path = target / "delete-preflight.json"
        if not manifest_path.is_file():
            raise ValueError(f"missing {DELETE_MANIFEST_FILENAME}")
        if not preflight_path.is_file():
            raise ValueError("missing delete-preflight.json (run delete-preflight first)")
        preflight = _load_run_json(preflight_path)
        if str(preflight.get("overall") or "") != "PASS":
            raise ValueError(
                f"delete-preflight overall must be PASS, got {preflight.get('overall')!r}"
            )
        manifest = _load_run_json(manifest_path)
        item_ids = list(args.item_ids) if args.item_ids else [
            str(item.get("item_id"))
            for item in manifest.get("items") or []
            if isinstance(item, dict) and item.get("item_id")
        ]
        record = build_delete_approval(
            manifest=manifest_path,
            preflight=preflight_path,
            approved_item_ids=item_ids,
            irreversible_confirmation=args.irreversible_confirmation,
        )
        # Freeze approval-time preflight identity for execute replay.
        approved_pf = target / "delete-preflight.approved.json"
        shutil.copyfile(preflight_path, approved_pf)
        out = write_delete_approval(target / DELETE_APPROVAL_FILENAME, record)
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError) as exc:
        print(f"filesteward delete-approve: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print(
        f"filesteward delete-approve: action={record['action']} "
        f"item_count={record['item_count']} "
        f"projected_reclaim_bytes={record['projected_reclaim_bytes']}"
    )
    print(f"approval: {out}")
    print(
        "Delete approval written. Permanent delete still requires "
        "delete-execute with --i-understand-irreversible."
    )
    return EXIT_OK


def _scan_root_allowed_for_execute(scan_root: Path) -> Optional[str]:
    """Return refusal reason, or None if execute may proceed.

    Synthetic temp / pytest roots are the supported seam. Live personal
    profile trees (under ``Path.home()`` but outside the process temp root)
    stay behind an explicit operator live-specimen gate.
    """

    root = normalize_declared_path(scan_root)
    temp_root = normalize_declared_path(tempfile.gettempdir())
    try:
        root_real = normalize_declared_path(Path(os.path.realpath(os.fspath(root))))
        temp_real = normalize_declared_path(
            Path(os.path.realpath(os.fspath(temp_root)))
        )
    except OSError:
        root_real = root
        temp_real = temp_root
    under_temp = (
        root == temp_root
        or root_real == temp_real
        or is_lexically_within(root, temp_root)
        or is_lexically_within(root_real, temp_real)
    )
    # Pytest tmp_path often uses the long profile path while gettempdir()
    # returns an 8.3 short path on Windows; admit pytest fixture trees.
    parts_casefold = [part.casefold() for part in root.parts]
    under_pytest_tmp = any(
        part.startswith("pytest-") or part == "pytest" for part in parts_casefold
    )
    if under_temp or under_pytest_tmp:
        return None
    home = normalize_declared_path(Path.home())
    under_home = root == home or is_lexically_within(root, home)
    if under_home:
        return (
            f"refusing live personal home root {root}; operator live-specimen "
            "gate is outside this CLI default path (use synthetic temp fixtures)"
        )
    # Non-home roots still require --i-understand-irreversible (caller).
    return None


def _run_delete_execute(args: argparse.Namespace) -> int:
    if not args.i_understand_irreversible:
        print(
            "filesteward delete-execute: refusing — "
            "--i-understand-irreversible is required; nothing was deleted.",
            file=sys.stderr,
        )
        return EXIT_INVALID
    try:
        target = prove_run_dir_under_runtime(resolve_run_dir_argument(args.target))
        scan_root = normalize_declared_path(args.scan_root)
        refusal = _scan_root_allowed_for_execute(scan_root)
        if refusal:
            raise ValueError(refusal)
        manifest_path = target / DELETE_MANIFEST_FILENAME
        approval_path = target / DELETE_APPROVAL_FILENAME
        if not manifest_path.is_file():
            raise ValueError(f"missing {DELETE_MANIFEST_FILENAME}")
        if not approval_path.is_file():
            raise ValueError(f"missing {DELETE_APPROVAL_FILENAME}")
        approved_pf = target / "delete-preflight.approved.json"
        preflight_arg = approved_pf if approved_pf.is_file() else None
        result = execute_permanent_delete(
            run_dir=target,
            manifest=manifest_path,
            approval=approval_path,
            preflight=preflight_arg,
            scan_root=scan_root,
        )
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError) as exc:
        print(f"filesteward delete-execute: {exc}", file=sys.stderr)
        return EXIT_INVALID

    reclaim_state = result.reclaim.state if result.reclaim is not None else "n/a"
    print(
        f"filesteward delete-execute: overall={result.overall} "
        f"items={len(result.items)} reclaim={reclaim_state}"
    )
    print(f"receipt: {result.receipt_path}")
    if result.approval_errors:
        for err in result.approval_errors:
            print(f"  - {err}", file=sys.stderr)
    if result.overall == "FAILED":
        return EXIT_INVALID
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
    if args.command == "visualize":
        return _run_visualize(args)
    if args.command == "delete-manifest":
        return _run_delete_manifest(args)
    if args.command == "delete-preflight":
        return _run_delete_preflight(args)
    if args.command == "delete-approve":
        return _run_delete_approve(args)
    if args.command == "delete-execute":
        return _run_delete_execute(args)

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
