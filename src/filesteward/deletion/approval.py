"""D3 delete-specific irreversible approval (NOT quarantine approval).

Schema: ``filesteward.delete-approval/v1``.

Authority for permanent deletion comes ONLY from a validated
``DeleteApprovalRecord``. The delete-manifest's ``intended_action=QUARANTINE``
is evidence of the default staging lane and is never treated as delete
authorization. Quarantine approvals (``filesteward.approval/v1`` +
``QUARANTINE``) are rejected by this validator.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from filesteward.deletion.manifest import DELETE_MANIFEST_SCHEMA, sha256_file
from filesteward.models import AuthorizationState, CleanupDisposition

__all__ = [
    "DELETE_APPROVAL_FILENAME",
    "DELETE_APPROVAL_SCHEMA",
    "DELETE_ACTION",
    "DeleteApprovalRecord",
    "build_delete_approval",
    "canonical_item_set_hash",
    "load_delete_approval",
    "preflight_identity_digest",
    "request_permanent_delete_set",
    "validate_delete_approval",
    "write_delete_approval",
]

DELETE_APPROVAL_SCHEMA = "filesteward.delete-approval/v1"
DELETE_APPROVAL_FILENAME = "delete-approval.json"
DELETE_ACTION = "DELETE_PERMANENTLY"

# Quarantine approval schema/action — rejected by delete-approval validator.
_QUARANTINE_APPROVAL_SCHEMA = "filesteward.approval/v1"
_QUARANTINE_ACTION = "QUARANTINE"

_BLOCKED_DISPOSITIONS = frozenset(
    {
        CleanupDisposition.HUMAN_REVIEW.value,
        CleanupDisposition.UNKNOWN.value,
        CleanupDisposition.PROTECTED.value,
        CleanupDisposition.KEEP_PROVEN.value,
    }
)

PathLike = Union[str, Path]
JsonLike = Union[Mapping[str, Any], PathLike]


def _load_json(source: JsonLike) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(os.fspath(source))
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: root must be a JSON object")
    return data


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def canonical_item_set_hash(item_ids: Sequence[str]) -> str:
    """SHA-256 of the canonical JSON array of sorted unique item_ids."""

    ordered = sorted(str(item_id) for item_id in item_ids)
    return _sha256_bytes(_canonical_json_bytes(ordered))


def preflight_identity_digest(preflight: Mapping[str, Any] | bytes | PathLike) -> str:
    """Digest bound into delete approval.

    Prefer the exact on-disk bytes of ``delete-preflight.json`` when a path
    is supplied. For in-memory mappings, digest the canonical JSON encoding
    of the preflight object (sort_keys, compact separators).
    """

    if isinstance(preflight, (bytes, bytearray)):
        return _sha256_bytes(bytes(preflight))
    if isinstance(preflight, Mapping):
        return _sha256_bytes(_canonical_json_bytes(dict(preflight)))
    path = Path(os.fspath(preflight))
    return sha256_file(path)


def _manifest_digest(manifest: Mapping[str, Any] | PathLike) -> str:
    if isinstance(manifest, Mapping):
        return _sha256_bytes(_canonical_json_bytes(dict(manifest)))
    return sha256_file(Path(os.fspath(manifest)))


def _items_by_id(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = manifest.get("items")
    if not isinstance(items, list):
        return {}
    out: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("item_id") or "")
        if item_id:
            out[item_id] = item
    return out


def _resolve_projected_reclaim(item: Mapping[str, Any], *, item_id: str) -> int:
    """Return bindable projected reclaim for an approved item.

    Directory container rows often omit projected reclaim (bytes live on
    child FILE rows). Treat DIRECTORY null as 0. For FILE rows, fall back to
    allocated then logical size when the plan left projected empty.
    """

    projected = item.get("projected_reclaim_bytes")
    if projected is not None:
        return int(projected)
    item_type = str(item.get("item_type") or "").upper()
    if item_type == "DIRECTORY":
        return 0
    for key in ("allocated_size_bytes", "logical_size_bytes"):
        value = item.get(key)
        if value is not None:
            return int(value)
    raise ValueError(
        f"item {item_id}: projected_reclaim_bytes missing; cannot bind approval"
    )


def _projected_for_ids(
    manifest: Mapping[str, Any],
    approved_item_ids: Sequence[str],
) -> int:
    by_id = _items_by_id(manifest)
    total = 0
    for item_id in approved_item_ids:
        item = by_id[item_id]
        total += _resolve_projected_reclaim(item, item_id=item_id)
    return total


def request_permanent_delete_set(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Copy delete-manifest items into a request view — does NOT authorize.

    The delete-manifest default ``intended_action=QUARANTINE`` is preserved on
    source items; this helper only projects a candidate permanent-delete set
    for operator review. Authority remains exclusive to DeleteApprovalRecord.
    """

    items = list(manifest.get("items") or [])
    return {
        "schema_version": "filesteward.delete-request/v1",
        "source_manifest_schema": manifest.get("schema_version"),
        "run_id": manifest.get("run_id"),
        "requested_action": DELETE_ACTION,
        "authorization_state": AuthorizationState.UNAPPROVED.value,
        "item_count": len(items),
        "item_ids": sorted(str(i.get("item_id") or "") for i in items if i.get("item_id")),
        "note": (
            "Request projection only. Permanent delete authority requires a "
            "validated filesteward.delete-approval/v1 record."
        ),
        "items": items,
    }


class DeleteApprovalRecord(dict):
    """Mapping-shaped delete approval record (JSON-serializable)."""

    @property
    def schema_version(self) -> str:
        return str(self.get("schema_version") or "")

    @property
    def run_id(self) -> str:
        return str(self.get("run_id") or "")

    @property
    def approved_item_ids(self) -> list[str]:
        raw = self.get("approved_item_ids") or []
        return [str(x) for x in raw]


def build_delete_approval(
    *,
    manifest: Mapping[str, Any] | PathLike,
    preflight: Mapping[str, Any] | PathLike | bytes,
    approved_item_ids: Sequence[str],
    irreversible_confirmation: str,
    delete_manifest_sha256: Optional[str] = None,
    preflight_sha256: Optional[str] = None,
    projected_reclaim_bytes: Optional[int] = None,
    created_at_unix: Optional[float] = None,
    run_id: Optional[str] = None,
) -> DeleteApprovalRecord:
    """Build a DELETE_PERMANENTLY approval bound to manifest + PASS preflight.

    ``projected_reclaim_bytes`` defaults to the sum of
    ``projected_reclaim_bytes`` for the approved item ids from the manifest.
    ``approved_item_ids`` are sorted into canonical order for ``item_set_hash``.
    """

    manifest_data = _load_json(manifest) if not isinstance(manifest, Mapping) else dict(manifest)
    if isinstance(preflight, (bytes, bytearray)):
        preflight_data = json.loads(bytes(preflight).decode("utf-8"))
        if not isinstance(preflight_data, dict):
            raise ValueError("preflight bytes must decode to a JSON object")
        pf_digest = preflight_sha256 or preflight_identity_digest(bytes(preflight))
    elif isinstance(preflight, Mapping):
        preflight_data = dict(preflight)
        pf_digest = preflight_sha256 or preflight_identity_digest(preflight_data)
    else:
        pf_path = Path(os.fspath(preflight))
        preflight_data = _load_json(pf_path)
        pf_digest = preflight_sha256 or preflight_identity_digest(pf_path)

    if not irreversible_confirmation or not str(irreversible_confirmation).strip():
        raise ValueError("irreversible_confirmation must be a non-empty token")

    ids = [str(x) for x in approved_item_ids]
    if not ids:
        raise ValueError("approved_item_ids must be non-empty")
    if len(set(ids)) != len(ids):
        raise ValueError("approved_item_ids must be unique")
    ordered = sorted(ids)

    if delete_manifest_sha256 is not None:
        manifest_digest = str(delete_manifest_sha256).lower()
    elif isinstance(manifest, Mapping):
        manifest_digest = _manifest_digest(manifest_data)
    else:
        manifest_digest = sha256_file(Path(os.fspath(manifest)))

    if projected_reclaim_bytes is None:
        projected = _projected_for_ids(manifest_data, ordered)
    else:
        projected = int(projected_reclaim_bytes)
    if projected < 0:
        raise ValueError("projected_reclaim_bytes must be >= 0")

    bound_run_id = run_id if run_id is not None else str(manifest_data.get("run_id") or "")
    if not bound_run_id:
        raise ValueError("run_id missing from manifest and builder args")

    record = DeleteApprovalRecord(
        {
            "schema_version": DELETE_APPROVAL_SCHEMA,
            "run_id": bound_run_id,
            "delete_manifest_sha256": str(manifest_digest).lower(),
            "preflight_sha256": str(pf_digest).lower(),
            "preflight_overall": str(preflight_data.get("overall") or ""),
            "approved_item_ids": ordered,
            "item_set_hash": canonical_item_set_hash(ordered),
            "item_count": len(ordered),
            "action": DELETE_ACTION,
            "projected_reclaim_bytes": projected,
            "irreversible_confirmation": str(irreversible_confirmation).strip(),
            "authorization_state": AuthorizationState.APPROVED_FOR_ACTION.value,
            "created_at_unix": float(
                created_at_unix if created_at_unix is not None else time.time()
            ),
        }
    )
    # Validate against the same sources used for digest binding (Path bytes vs
    # mapping canonical digest) so pretty-printed files do not false-drift.
    manifest_for_validate: Any = (
        manifest if isinstance(manifest, (str, Path)) else manifest_data
    )
    if isinstance(preflight, (bytes, bytearray)):
        preflight_for_validate: Any = bytes(preflight)
    elif isinstance(preflight, (str, Path)):
        preflight_for_validate = Path(os.fspath(preflight))
    else:
        preflight_for_validate = preflight_data
    errors = validate_delete_approval(
        record, manifest_for_validate, preflight_for_validate
    )
    if errors:
        raise ValueError("; ".join(errors))
    return record


def validate_delete_approval(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any] | PathLike,
    preflight: Mapping[str, Any] | PathLike | bytes,
) -> tuple[str, ...]:
    """Return validation errors (empty tuple means OK). Fail closed."""

    errors: list[str] = []
    try:
        manifest_data = (
            dict(manifest) if isinstance(manifest, Mapping) else _load_json(manifest)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return (f"cannot load delete-manifest: {exc}",)

    if isinstance(preflight, (bytes, bytearray)):
        try:
            preflight_data = json.loads(bytes(preflight).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return (f"cannot decode preflight bytes: {exc}",)
        if not isinstance(preflight_data, dict):
            return ("preflight bytes must decode to a JSON object",)
        expected_pf_digest = preflight_identity_digest(bytes(preflight))
    elif isinstance(preflight, Mapping):
        preflight_data = dict(preflight)
        expected_pf_digest = preflight_identity_digest(preflight_data)
    else:
        try:
            pf_path = Path(os.fspath(preflight))
            preflight_data = _load_json(pf_path)
            expected_pf_digest = preflight_identity_digest(pf_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return (f"cannot load preflight: {exc}",)

    schema = str(record.get("schema_version") or "")
    action = str(record.get("action") or "")

    # Reject quarantine approval schema/action outright.
    if schema == _QUARANTINE_APPROVAL_SCHEMA or action == _QUARANTINE_ACTION:
        errors.append(
            "quarantine approval (filesteward.approval/v1 / QUARANTINE) "
            "cannot authorize DELETE_PERMANENTLY"
        )
        return tuple(errors)

    if schema != DELETE_APPROVAL_SCHEMA:
        errors.append(
            f"schema_version must be {DELETE_APPROVAL_SCHEMA!r}, got {schema!r}"
        )

    if action != DELETE_ACTION:
        errors.append(f"action must be {DELETE_ACTION!r}, got {action!r}")

    auth = str(record.get("authorization_state") or "")
    if auth != AuthorizationState.APPROVED_FOR_ACTION.value:
        errors.append(
            f"authorization_state must be APPROVED_FOR_ACTION, got {auth!r}"
        )

    confirmation = record.get("irreversible_confirmation")
    if not isinstance(confirmation, str) or not confirmation.strip():
        errors.append("irreversible_confirmation must be a non-empty string token")

    created = record.get("created_at_unix")
    if not isinstance(created, (int, float)):
        errors.append("created_at_unix must be a number")

    run_id = str(record.get("run_id") or "")
    manifest_run = str(manifest_data.get("run_id") or "")
    if not run_id:
        errors.append("run_id missing")
    elif run_id != manifest_run:
        errors.append(f"run_id mismatch: approval={run_id!r} manifest={manifest_run!r}")

    manifest_schema = str(manifest_data.get("schema_version") or "")
    if manifest_schema != DELETE_MANIFEST_SCHEMA:
        errors.append(
            f"manifest schema_version must be {DELETE_MANIFEST_SCHEMA!r}, "
            f"got {manifest_schema!r}"
        )

    # Digest binding: prefer on-disk bytes when Path supplied.
    if isinstance(manifest, (str, Path)):
        actual_manifest_digest = sha256_file(Path(os.fspath(manifest)))
    else:
        actual_manifest_digest = _manifest_digest(manifest_data)
    declared_manifest = str(record.get("delete_manifest_sha256") or "").lower()
    if not declared_manifest or len(declared_manifest) != 64:
        errors.append("delete_manifest_sha256 must be a 64-hex digest")
    elif declared_manifest != actual_manifest_digest.lower():
        errors.append(
            "delete_manifest_sha256 drift: "
            f"approval={declared_manifest} observed={actual_manifest_digest}"
        )

    declared_pf = str(record.get("preflight_sha256") or "").lower()
    if not declared_pf or len(declared_pf) != 64:
        errors.append("preflight_sha256 must be a 64-hex digest")
    elif declared_pf != expected_pf_digest.lower():
        errors.append(
            "preflight_sha256 drift: "
            f"approval={declared_pf} observed={expected_pf_digest}"
        )

    pf_overall = str(preflight_data.get("overall") or "")
    record_overall = str(record.get("preflight_overall") or "")
    if pf_overall != "PASS":
        errors.append(f"preflight overall must be PASS, got {pf_overall!r}")
    if record_overall != "PASS":
        errors.append(
            f"approval preflight_overall must be PASS, got {record_overall!r}"
        )
    if record_overall and pf_overall and record_overall != pf_overall:
        errors.append(
            f"preflight_overall mismatch: approval={record_overall!r} "
            f"preflight={pf_overall!r}"
        )

    raw_ids = record.get("approved_item_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        errors.append("approved_item_ids must be a non-empty list")
        return tuple(errors)

    ids = [str(x) for x in raw_ids]
    if any(not x for x in ids):
        errors.append("approved_item_ids contains empty id")
    if len(ids) != len(set(ids)):
        errors.append("approved_item_ids contains duplicates")
    if ids != sorted(ids):
        errors.append("approved_item_ids must be sorted in canonical order")

    item_count = record.get("item_count")
    if not isinstance(item_count, int) or item_count != len(ids):
        errors.append(
            f"item_count must equal len(approved_item_ids) "
            f"({len(ids)}), got {item_count!r}"
        )

    declared_set_hash = str(record.get("item_set_hash") or "").lower()
    expected_set_hash = canonical_item_set_hash(ids)
    if declared_set_hash != expected_set_hash:
        errors.append(
            "item_set_hash mismatch: "
            f"approval={declared_set_hash} expected={expected_set_hash}"
        )

    by_id = _items_by_id(manifest_data)
    projected_sum = 0
    for item_id in ids:
        item = by_id.get(item_id)
        if item is None:
            errors.append(f"approved item_id unknown in manifest: {item_id}")
            continue
        disposition = str(item.get("disposition") or "")
        if disposition in _BLOCKED_DISPOSITIONS:
            errors.append(
                f"item {item_id}: disposition {disposition} cannot be approved "
                "for permanent delete"
            )
        elif disposition != CleanupDisposition.RECLAIM_PROVEN.value:
            errors.append(
                f"item {item_id}: disposition must be RECLAIM_PROVEN, got {disposition!r}"
            )
        try:
            projected_sum += _resolve_projected_reclaim(item, item_id=item_id)
        except ValueError as exc:
            errors.append(str(exc))
        except TypeError:
            errors.append(f"item {item_id}: projected_reclaim_bytes not int-like")

    declared_projected = record.get("projected_reclaim_bytes")
    if not isinstance(declared_projected, int) or declared_projected < 0:
        errors.append("projected_reclaim_bytes must be an int >= 0")
    elif not any(e.startswith("approved item_id unknown") for e in errors):
        if declared_projected != projected_sum:
            errors.append(
                "projected_reclaim_bytes mismatch: "
                f"approval={declared_projected} sum(approved items)={projected_sum}"
            )

    return tuple(errors)


def write_delete_approval(path: PathLike, record: Mapping[str, Any]) -> Path:
    """Atomically write delete-approval.json."""

    out = Path(os.fspath(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(record), indent=2, sort_keys=True) + "\n"
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


def load_delete_approval(path: PathLike) -> DeleteApprovalRecord:
    """Load a delete-approval JSON file into a DeleteApprovalRecord."""

    data = _load_json(path)
    return DeleteApprovalRecord(data)
