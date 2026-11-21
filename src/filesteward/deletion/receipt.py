"""D5 permanent-delete execution receipt.

Writes ``delete-execution-receipt.json`` under the run directory. Receipts
survive interruption well enough to prevent blind re-unlink of items already
recorded as SUCCEEDED.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from filesteward.deletion.approval import DELETE_ACTION, DELETE_APPROVAL_FILENAME, DELETE_APPROVAL_SCHEMA
from filesteward.deletion.manifest import DELETE_MANIFEST_FILENAME, DELETE_MANIFEST_SCHEMA
from filesteward.models import AuthorizationState

__all__ = [
    "DELETE_RECEIPT_FILENAME",
    "DELETE_RECEIPT_SCHEMA",
    "completed_delete_paths",
    "load_delete_receipt",
    "write_delete_receipt",
]

DELETE_RECEIPT_SCHEMA = "filesteward.delete-execution-receipt/v1"
DELETE_RECEIPT_FILENAME = "delete-execution-receipt.json"

PathLike = Union[str, Path]


def write_delete_receipt(path: PathLike, receipt: Mapping[str, Any]) -> Path:
    """Atomically write the execution receipt."""

    out = Path(os.fspath(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(receipt)
    payload.setdefault("schema_version", DELETE_RECEIPT_SCHEMA)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{out.name}.",
        suffix=".tmp",
        dir=str(out.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, out)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return out


def load_delete_receipt(path: PathLike) -> Optional[dict[str, Any]]:
    """Load an existing receipt, or return None if missing."""

    target = Path(os.fspath(path))
    if not target.is_file():
        return None
    with target.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("delete-execution-receipt root must be a JSON object")
    return data


def completed_delete_paths(
    run_dir: Path, *, run_id: str, cleanup_plan_sha256: str,
) -> dict[str, str]:
    """Read completed paths from a receipt bound to the served plan and approval."""
    receipt_path = run_dir / DELETE_RECEIPT_FILENAME
    manifest_path = run_dir / DELETE_MANIFEST_FILENAME
    approval_path = run_dir / DELETE_APPROVAL_FILENAME
    try:
        receipt = load_delete_receipt(receipt_path)
        if (not receipt or receipt.get("schema_version") != DELETE_RECEIPT_SCHEMA
                or receipt.get("mode") != DELETE_ACTION or receipt.get("run_id") != run_id
                or receipt.get("overall") not in ("SUCCEEDED", "PARTIAL")
                or not isinstance(receipt.get("items"), list)):
            return {}
        manifest_bytes = manifest_path.read_bytes()
        approval_bytes = approval_path.read_bytes()
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        if (receipt.get("delete_manifest_sha256") != manifest_sha
                or receipt.get("delete_approval_sha256") != hashlib.sha256(approval_bytes).hexdigest()):
            return {}
        manifest = json.loads(manifest_bytes)
        approval = json.loads(approval_bytes)
    except (OSError, ValueError):
        return {}
    if (not isinstance(manifest, dict) or not isinstance(approval, dict)
            or manifest.get("schema_version") != DELETE_MANIFEST_SCHEMA
            or manifest.get("run_id") != run_id
            or manifest.get("source_cleanup_plan_sha256") != cleanup_plan_sha256
            or approval.get("schema_version") != DELETE_APPROVAL_SCHEMA
            or approval.get("authorization_state") != AuthorizationState.APPROVED_FOR_ACTION.value
            or approval.get("run_id") != run_id
            or approval.get("action") != DELETE_ACTION
            or approval.get("delete_manifest_sha256") != manifest_sha
            or not isinstance(approval.get("approved_item_ids"), list)
            or not isinstance(manifest.get("items"), list)):
        return {}
    approved = {item_id for item_id in approval["approved_item_ids"] if isinstance(item_id, str)}
    paths = {
        row["item_id"]: row.get("path") for row in manifest["items"]
        if isinstance(row, dict) and isinstance(row.get("item_id"), str)
    }
    completed: dict[str, str] = {}
    for row in receipt["items"]:
        if not isinstance(row, dict) or row.get("status") != "SUCCEEDED":
            continue
        item_id, path = row.get("item_id"), row.get("path")
        if (isinstance(item_id, str) and item_id in approved
                and isinstance(path, str) and path == paths.get(item_id)):
            completed[item_id] = path
    return completed
