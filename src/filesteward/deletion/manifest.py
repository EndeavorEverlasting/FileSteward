"""Build the exact UNAPPROVED delete-manifest from RECLAIM_PROVEN plan rows.

Authority artifact: ``delete-manifest.json``. Authorization remains
``UNAPPROVED``; default intended action is ``QUARANTINE`` with
``REVERSIBLE_QUARANTINE``. This module never mutates scanned targets.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from filesteward.classify import is_managed
from filesteward.manifest import validate_run
from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    EntryType,
    InventoryItem,
    ScanCompleteness,
)
from filesteward.policy.paths import prove_run_dir_under_runtime
from filesteward.deletion.ownership import binding_from_action_record, action_plan_from_record
from filesteward.ownership.actions import ActionKind
from filesteward.ownership.capacity import CapacityCandidate, plan_capacity_strategy

__all__ = [
    "DELETE_MANIFEST_FILENAME",
    "DELETE_MANIFEST_SCHEMA",
    "DeleteManifestResult",
    "build_delete_manifest",
    "emit_delete_manifest",
    "sha256_file",
]

DELETE_MANIFEST_SCHEMA = "filesteward.delete-manifest/v1"
DELETE_MANIFEST_FILENAME = "delete-manifest.json"

INTENDED_ACTION = "QUARANTINE"
REVERSIBILITY = "REVERSIBLE_QUARANTINE"

_UNTOUCHED_NOTE = (
    "HUMAN_REVIEW, UNKNOWN, PROTECTED, and KEEP_PROVEN rows are excluded "
    "from this delete set."
)

_IDENTITY_COLUMNS = (
    "path",
    "logical_size_bytes",
    "allocated_size_bytes",
)

_VALID_ITEM_TYPES = frozenset(member.value for member in EntryType)

_PLAN_QUALITY_TO_TOTAL = {
    "allocated-evidence": "allocated-evidence",
    "estimate-logical": "estimate-logical",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DeleteManifestResult:
    """Outcome of emitting a local/private delete-manifest + surface."""

    run_dir: Path
    manifest_path: Path
    html_path: Path
    text_path: Path
    run_id: str
    item_count: int
    authorization_state: str
    intended_action: str
    totals: Mapping[str, Any]
    untouched: Mapping[str, Any]
    source_cleanup_plan_sha256: str
    manifest: Mapping[str, Any]


def _opt_int(text: str) -> Optional[int]:
    if text == "":
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"non-integer optional int field: {text!r}") from exc


def _parse_bool(text: str, *, field: str, item_id: str) -> bool:
    value = text.strip().casefold()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"item {item_id}: inventory {field} must be true/false, got {text!r}"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sum_bytes(values: Sequence[Optional[int]]) -> Optional[int]:
    """Sum bytes honestly: empty -> 0; any unknown -> None; else exact sum."""

    if not values:
        return 0
    if any(value is None for value in values):
        return None
    return sum(int(value) for value in values)


def _aggregate_projection_quality(qualities: Sequence[str]) -> str:
    if not qualities:
        return "unknown"
    mapped: set[str] = set()
    for quality in qualities:
        mapped.add(_PLAN_QUALITY_TO_TOTAL.get(quality, "unknown"))
    if mapped == {"allocated-evidence"}:
        return "allocated-evidence"
    if mapped == {"estimate-logical"}:
        return "estimate-logical"
    if "unknown" in mapped and len(mapped) == 1:
        return "unknown"
    return "mixed"


def _managed_for_path(path: str, managed_paths: Sequence[str]) -> bool:
    if not managed_paths:
        return False
    # Minimal InventoryItem solely for the declared-prefix managed check.
    probe = InventoryItem(
        item_id="managed-probe",
        path=path,
        entry_type=EntryType.OTHER,
        scan_completeness=ScanCompleteness.COMPLETE,
    )
    return is_managed(probe, managed_paths)


def _bind_item(
    plan_row: Mapping[str, str],
    inventory_row: Mapping[str, str],
    *,
    run_id: str,
    plan_sha: str,
    managed_paths: Sequence[str],
) -> dict[str, Any]:
    item_id = plan_row.get("item_id", "")
    if not item_id:
        raise ValueError("cleanup-plan row missing item_id")

    disposition = plan_row.get("disposition", "")
    if disposition != CleanupDisposition.RECLAIM_PROVEN.value:
        raise ValueError(
            f"item {item_id}: disposition {disposition!r} is not RECLAIM_PROVEN"
        )

    for column in _IDENTITY_COLUMNS:
        plan_value = plan_row.get(column, "")
        inv_value = inventory_row.get(column, "")
        if plan_value != inv_value:
            raise ValueError(
                f"item {item_id}: identity field {column} cannot be bound "
                f"(plan={plan_value!r}, inventory={inv_value!r})"
            )

    path = plan_row.get("path", "")
    if not path:
        raise ValueError(f"item {item_id}: empty path cannot be bound")

    entry_type = inventory_row.get("entry_type", "")
    if entry_type not in _VALID_ITEM_TYPES:
        raise ValueError(
            f"item {item_id}: inventory entry_type {entry_type!r} is not bindable"
        )

    inv_disposition = inventory_row.get("disposition", "")
    if inv_disposition != CleanupDisposition.RECLAIM_PROVEN.value:
        raise ValueError(
            f"item {item_id}: inventory disposition {inv_disposition!r} "
            "is not RECLAIM_PROVEN"
        )

    logical = _opt_int(plan_row.get("logical_size_bytes", ""))
    allocated = _opt_int(plan_row.get("allocated_size_bytes", ""))
    projected = _opt_int(plan_row.get("projected_reclaim_bytes", ""))
    # Directory containers often omit projected reclaim (bytes are on files).
    # Bind 0 so approval can include empty-dir rows without failing closed.
    if projected is None:
        if entry_type == "DIRECTORY":
            projected = 0
        elif allocated is not None:
            projected = allocated
        elif logical is not None:
            projected = logical
    link_count = _opt_int(inventory_row.get("link_count", ""))
    modified_at = inventory_row.get("modified_at", "") or None
    projection_quality = plan_row.get("projection_quality", "") or "unknown"

    return {
        "item_id": item_id,
        "path": path,
        "item_type": entry_type,
        "disposition": CleanupDisposition.RECLAIM_PROVEN.value,
        "evidence": plan_row.get("evidence", ""),
        "contract_source": plan_row.get("confidence_basis", ""),
        "logical_size_bytes": logical,
        "allocated_size_bytes": allocated,
        "projected_reclaim_bytes": projected,
        "reclaim_basis": plan_row.get("reclaim_basis", ""),
        "projection_quality": projection_quality,
        "protection_check": plan_row.get("protection_check", ""),
        "is_managed": _managed_for_path(path, managed_paths),
        "is_cloud_placeholder": _parse_bool(
            inventory_row.get("is_cloud_placeholder", "false"),
            field="is_cloud_placeholder",
            item_id=item_id,
        ),
        "is_symlink": _parse_bool(
            inventory_row.get("is_symlink", "false"),
            field="is_symlink",
            item_id=item_id,
        ),
        "is_reparse_point": _parse_bool(
            inventory_row.get("is_reparse_point", "false"),
            field="is_reparse_point",
            item_id=item_id,
        ),
        "link_count": link_count,
        "modified_at": modified_at,
        "source_run_id": run_id,
        "source_cleanup_plan_sha256": plan_sha,
        "identity": {
            "path": path,
            "item_type": entry_type,
            "logical_size_bytes": logical,
            "allocated_size_bytes": allocated,
            "modified_at": modified_at,
            "link_count": link_count,
        },
        "intended_action": INTENDED_ACTION,
        "reversibility": REVERSIBILITY,
    }


def _untouched_counts(
    inventory: Sequence[Mapping[str, str]],
    review: Sequence[Mapping[str, str]],
    exclusions: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    human_review_count = sum(
        1
        for row in review
        if row.get("disposition") == CleanupDisposition.HUMAN_REVIEW.value
    )
    unknown_count = sum(
        1
        for row in review
        if row.get("disposition") == CleanupDisposition.UNKNOWN.value
    )
    # Inventory disposition is authoritative for KEEP_PROVEN; protected rows
    # are counted from the exclusions queue (one row per protected item).
    keep_proven_count = sum(
        1
        for row in inventory
        if row.get("disposition") == CleanupDisposition.KEEP_PROVEN.value
    )
    protected_count = len(exclusions)
    return {
        "human_review_count": human_review_count,
        "protected_count": protected_count,
        "unknown_count": unknown_count,
        "keep_proven_count": keep_proven_count,
        "note": _UNTOUCHED_NOTE,
    }


def build_delete_manifest(run_dir: Path) -> dict[str, Any]:
    """Construct the delete-manifest mapping from a validated run directory.

    Fail closed when a plan row is not ``RECLAIM_PROVEN``, missing from
    inventory, or cannot bind identity. Does not follow links and does not
    mutate any scanned target.
    """

    target = Path(run_dir)
    plan_path = target / "cleanup-plan.csv"
    inventory_path = target / "inventory.csv"
    review_path = target / "human-review.csv"
    exclusions_path = target / "protected-exclusions.csv"
    run_meta_path = target / "run.json"

    for required in (
        plan_path,
        inventory_path,
        review_path,
        exclusions_path,
        run_meta_path,
    ):
        if not required.is_file():
            raise ValueError(f"missing required artifact: {required.name}")

    metadata = json.loads(run_meta_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("run.json is empty or not an object")
    run_id = str(metadata.get("run_id") or "")
    if not run_id:
        raise ValueError("run.json missing run_id")

    managed_raw = metadata.get("managed_paths") or []
    if not isinstance(managed_raw, list):
        raise ValueError("run.json managed_paths must be a list when present")
    managed_paths = tuple(str(path) for path in managed_raw)

    plan_sha = sha256_file(plan_path)
    plan_rows = _read_csv(plan_path)
    discovered_plan_count = len(plan_rows)
    discovered_rows = list(plan_rows)
    capacity_path = target / "capacity-strategy.json"
    if plan_rows:
        if not capacity_path.is_file():
            raise ValueError("CAPACITY_STRATEGY_MISSING: rank legal actions before binding deletion")
        capacity = json.loads(capacity_path.read_text(encoding="utf-8"))
        if capacity.get("schema_version") != "filesteward.capacity-strategy/v1":
            raise ValueError("CAPACITY_STRATEGY_INVALID: unsupported schema")
        if capacity.get("status") not in {"HEALTHY", "LOW", "CRITICAL", "UNKNOWN"}:
            raise ValueError("CAPACITY_STRATEGY_INVALID: unsupported capacity state")
        selected = {str(c["candidate_id"]) for c in capacity.get("candidates", [])
                    if c.get("action") == "RAW_DELETE_REGENERABLE_ARTIFACT"}
        if capacity.get("status") in {"HEALTHY", "UNKNOWN"}:
            selected = set()
        plan_rows = [row for row in plan_rows if row.get("item_id") in selected]
    inventory_rows = _read_csv(inventory_path)
    review_rows = _read_csv(review_path)
    exclusion_rows = _read_csv(exclusions_path)

    inventory_by_id = {row["item_id"]: row for row in inventory_rows if row.get("item_id")}
    if len(inventory_by_id) != len(inventory_rows):
        raise ValueError("inventory.csv contains duplicate or empty item_id values")

    items: list[dict[str, Any]] = []
    ownership_path = target / "owner-action-plan.json"
    ownership_rows = {}
    if discovered_rows:
        if not ownership_path.is_file():
            raise ValueError("OWNERSHIP_UNKNOWN: owner-action-plan.json missing")
        ownership_data = json.loads(ownership_path.read_text(encoding="utf-8"))
        if ownership_data.get("schema_version") != "filesteward.owner-action-plan/v1":
            raise ValueError("OWNERSHIP_UNKNOWN: owner-action schema mismatch")
        for row in ownership_data.get("items", []):
            if not isinstance(row, dict) or not row.get("item_id") or row["item_id"] in ownership_rows:
                raise ValueError("OWNERSHIP_UNKNOWN: duplicate or malformed ownership row")
            ownership_rows[row["item_id"]] = row
        capacity_candidates = []
        for row in discovered_rows:
            record = ownership_rows.get(row["item_id"])
            if record is None:
                raise ValueError("OWNERSHIP_UNKNOWN: discovery row lacks ownership")
            plan = action_plan_from_record(record)
            capacity_candidates.append(CapacityCandidate(row["item_id"], plan,
                ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT,
                0 if row["projection_quality"] == "container-row" else _opt_int(row["projected_reclaim_bytes"]),
                "container-row" if row["projection_quality"] == "container-row" else row["reclaim_basis"]))
        if capacity.get("status") != "UNKNOWN":
            canonical = plan_capacity_strategy(capacity_candidates, total_bytes=capacity.get("total_bytes"),
                                               free_bytes=capacity.get("free_bytes"))
            if capacity.get("status") != canonical.status or capacity.get("target_free_bytes") != canonical.target_free_bytes:
                raise ValueError("CAPACITY_STRATEGY_INVALID: measurement/state mismatch")
            canonical_ids = {c.candidate_id for c in canonical.candidates}
            if selected != canonical_ids:
                raise ValueError("CAPACITY_STRATEGY_INVALID: ranked raw-delete set changed")
    for plan_row in plan_rows:
        item_id = plan_row.get("item_id", "")
        if not item_id:
            raise ValueError("cleanup-plan.csv contains a row with empty item_id")
        inventory_row = inventory_by_id.get(item_id)
        if inventory_row is None:
            raise ValueError(
                f"item {item_id}: missing from inventory.csv (fail closed)"
            )
        items.append(
            _bind_item(
                plan_row,
                inventory_row,
                run_id=run_id,
                plan_sha=plan_sha,
                managed_paths=managed_paths,
            )
        )
        action_row = ownership_rows.get(item_id)
        if action_row is None or action_row.get("path") != items[-1]["path"]:
            raise ValueError(f"OWNERSHIP_UNKNOWN: missing exact ownership for {item_id}")
        items[-1]["ownership"] = binding_from_action_record(action_row)

    logical_values = [item["logical_size_bytes"] for item in items]
    allocated_values = [item["allocated_size_bytes"] for item in items]
    projected_values = [item["projected_reclaim_bytes"] for item in items]
    qualities = [str(item["projection_quality"]) for item in items]

    return {
        "schema_version": DELETE_MANIFEST_SCHEMA,
        "run_id": run_id,
        "source_cleanup_plan_sha256": plan_sha,
        "source_owner_action_plan_sha256": sha256_file(ownership_path) if ownership_path.is_file() else "",
        "source_capacity_strategy_sha256": sha256_file(capacity_path) if capacity_path.is_file() else "",
        "capacity_deferred_item_count": discovered_plan_count - len(items),
        "authorization_state": AuthorizationState.UNAPPROVED.value,
        "intended_action": INTENDED_ACTION,
        "item_count": len(items),
        "totals": {
            "logical_size_bytes": _sum_bytes(logical_values),
            "allocated_size_bytes": _sum_bytes(allocated_values),
            "projected_reclaim_bytes": _sum_bytes(projected_values),
            "projection_quality": _aggregate_projection_quality(qualities),
        },
        "untouched": _untouched_counts(inventory_rows, review_rows, exclusion_rows),
        "items": items,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def emit_delete_manifest(run_dir: Path) -> DeleteManifestResult:
    """Validate a run, emit delete-manifest.json + operator surface, mutate nothing else."""

    from filesteward.deletion.surface import write_delete_set_surface

    target = prove_run_dir_under_runtime(run_dir)
    errors = validate_run(target)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(
            f"run failed FileSteward validation ({len(errors)} problem(s)): {joined}"
        )

    manifest = build_delete_manifest(target)
    manifest_path = target / DELETE_MANIFEST_FILENAME
    _atomic_write_json(manifest_path, manifest)
    html_path, text_path = write_delete_set_surface(target, manifest)

    return DeleteManifestResult(
        run_dir=target,
        manifest_path=manifest_path,
        html_path=html_path,
        text_path=text_path,
        run_id=str(manifest["run_id"]),
        item_count=int(manifest["item_count"]),
        authorization_state=str(manifest["authorization_state"]),
        intended_action=str(manifest["intended_action"]),
        totals=dict(manifest["totals"]),
        untouched=dict(manifest["untouched"]),
        source_cleanup_plan_sha256=str(manifest["source_cleanup_plan_sha256"]),
        manifest=manifest,
    )
