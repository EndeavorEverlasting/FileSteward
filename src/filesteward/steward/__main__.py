"""CLI for an independently auditable FileSteward stewardship cycle.

Usage: python -m filesteward.steward --scan-run <canonical var/runs/id>
Every output is locally private and UNAPPROVED. Never dispatches an AI model.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filesteward.manifest.artifacts import validate_run
from filesteward.policy.paths import (
    prove_run_dir_under_runtime,
    is_symlink_or_reparse,
    resolve_run_dir_argument,
    runtime_root,
)
from . import build_cycle


def _write(path: Path, value: Any) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        if isinstance(value, list):
            for row in value:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        else:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
    temp.replace(path)


def _load_private_evidence(path: Path | None, *, scan_name: str) -> dict[str, Any]:
    if path is None:
        return {}
    private_base = runtime_root() / "steward"
    for component in (runtime_root(), private_base):
        if component.exists() and is_symlink_or_reparse(component):
            raise ValueError("linked private runtime directory refused")
    base = private_base.resolve()
    resolved = path.resolve(strict=True)
    if base not in resolved.parents or not resolved.is_file():
        raise ValueError("observation file must be beneath FileSteward private var/steward/")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("source_scan") != scan_name:
        raise ValueError("observation source_scan mismatch")
    values = payload.get("items")
    if not isinstance(values, dict):
        raise ValueError("observation items must be an item_id object")
    return values


def execute_readonly_cycle(
    scan_run: Path,
    *,
    observations: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Validate a canonical scan and publish an unapproved private work queue."""
    scan_run = prove_run_dir_under_runtime(resolve_run_dir_argument(scan_run))
    errors = validate_run(scan_run)
    if errors:
        raise ValueError(f"scan validation failed: {len(errors)} error(s): " + "; ".join(errors[:4]))
    inventory = scan_run / "inventory.csv"
    # Bounded memory even when Downloads contains an enormous inventory.
    with inventory.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        total_rows = 0
        for row in reader:
            total_rows += 1
            if len(rows) < 250:
                rows.append(row)
    extra = _load_private_evidence(observations, scan_name=scan_run.name)
    report = build_cycle(rows, extra, scan_id=scan_run.name,
                         now=now or datetime.now(timezone.utc),
                         unobserved_input_count=total_rows - len(rows))
    if report["coverage"]["coverage_state"] != "OBSERVED_INPUT":
        # Persist evidence of the budget limit but never indicate scan completion.
        report["coverage"]["completion_state"] = "INCOMPLETE_NO_CLEANUP_AUTHORITY"
    else:
        report["coverage"]["completion_state"] = "READ_ONLY_REVIEW_PRODUCED"
    private_root = runtime_root() / "steward" / "cycles"
    for component in (runtime_root(), private_root.parent, private_root):
        if component.exists() and is_symlink_or_reparse(component):
            raise ValueError("linked runtime output path refused")
    private_root.mkdir(parents=True, exist_ok=True)
    cycle_path = private_root / (scan_run.name + "-" + uuid.uuid4().hex[:12])
    cycle_path.mkdir(mode=0o700, exist_ok=False)
    _write(cycle_path / "classified.jsonl", report["classified"])
    _write(cycle_path / "unresolved.jsonl", report["unresolved"])
    _write(cycle_path / "work-items.jsonl", report["work_items"])
    _write(cycle_path / "coverage.json", report["coverage"])
    _write(cycle_path / "cycle.json", {
        "schema_version": report["schema_version"],
        "policy_version": report["policy_version"],
        "source_scan": report["source_scan"],
        "observed_at_utc": report["observed_at_utc"],
        "source_mutations": 0,
        "agent_executions": 0,
        "authorization_state": "UNAPPROVED",
        "dispatch_adapter_state": "OUTBOX_ONLY_NO_AGENT_LAUNCHED",
    })
    return cycle_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local read-only steward: evidence -> facets -> unresolved -> typed outbox")
    parser.add_argument("--scan-run", required=True, type=Path)
    parser.add_argument("--observations", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        path = execute_readonly_cycle(args.scan_run, observations=args.observations)
    except (OSError, ValueError, RuntimeError, csv.Error, json.JSONDecodeError) as exc:
        print("STEWARD_REFUSED: " + str(exc), file=sys.stderr)
        return 2
    print("STEWARD_REVIEW_READY: " + str(path))
    print("No agents invoked; no source file or approval modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
