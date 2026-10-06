"""D4B permanent delete executor + D5 receipt emission + D6 reclaim verify.

Requires a validated DeleteApprovalRecord (DELETE_PERMANENTLY) and a fresh
PASS preflight before any unlink. Operates only on approved enumerated
paths under scan_root. Never follows symlink/junction/reparse.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from filesteward.deletion.approval import (
    DELETE_ACTION,
    DELETE_APPROVAL_FILENAME,
    DeleteApprovalRecord,
    load_delete_approval,
    validate_delete_approval,
)
from filesteward.deletion.manifest import DELETE_MANIFEST_FILENAME, sha256_file
from filesteward.deletion.preflight import (
    identity_drift_against_lstat,
    merge_execute_protection_context,
    reparse_or_path_escape,
    run_preflight,
    write_preflight_receipt,
)
from filesteward.deletion.receipt import (
    DELETE_RECEIPT_FILENAME,
    DELETE_RECEIPT_SCHEMA,
    load_delete_receipt,
    write_delete_receipt,
)
from filesteward.deletion.reclaim import ReclaimVerification, verify_reclaim
from filesteward.inventory import windows
from filesteward.policy.paths import is_lexically_within, normalize_declared_path
from filesteward.protect import ProtectionIndex, ProtectionRelation

__all__ = [
    "ExecutionResult",
    "ItemExecutionResult",
    "execute_permanent_delete",
    "scan_root_allowed_for_execute",
]

PathLike = Union[str, Path]
JsonLike = Union[Mapping[str, Any], PathLike, DeleteApprovalRecord]


def scan_root_allowed_for_execute(scan_root: PathLike) -> Optional[str]:
    """Return refusal reason, or None if execute may proceed.

    Temp membership uses **only** ``realpath`` containment under
    ``tempfile.gettempdir()`` (and equality). Lexical-only membership is
    refused so a junction/symlink under Temp that resolves into the home
    directory cannot be admitted. Home refusal also consults ``root_real``.
    A path component containing ``pytest`` is not enough:
    ``Path.home()/pytest-victim`` must remain refused.
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
    under_temp = root_real == temp_real or is_lexically_within(root_real, temp_real)
    if under_temp:
        return None
    home = normalize_declared_path(Path.home())
    try:
        home_real = normalize_declared_path(Path(os.path.realpath(os.fspath(home))))
    except OSError:
        home_real = home
    under_home = (
        root == home
        or root_real == home
        or root_real == home_real
        or is_lexically_within(root, home)
        or is_lexically_within(root_real, home)
        or is_lexically_within(root_real, home_real)
    )
    if under_home:
        return (
            f"refusing live personal home root {root}; operator live-specimen "
            "gate is outside this CLI default path (use synthetic temp fixtures)"
        )
    # Non-home roots still require --i-understand-irreversible (caller).
    return None


@dataclass
class ItemExecutionResult:
    item_id: str
    path: str
    status: str  # SUCCEEDED | FAILED | SKIPPED | PENDING
    reason_class: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "item_id": self.item_id,
            "path": self.path,
            "status": self.status,
            "reason_class": self.reason_class,
            "detail": self.detail,
        }


@dataclass
class ExecutionResult:
    overall: str
    run_dir: Path
    receipt_path: Path
    mode: str = DELETE_ACTION
    items: list[ItemExecutionResult] = field(default_factory=list)
    free_bytes_before: Optional[int] = None
    free_bytes_after: Optional[int] = None
    reclaim: Optional[ReclaimVerification] = None
    started_at_unix: float = 0.0
    ended_at_unix: float = 0.0
    approval_errors: tuple[str, ...] = ()
    preflight_overall: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "mode": self.mode,
            "run_dir": str(self.run_dir),
            "receipt_path": str(self.receipt_path),
            "free_bytes_before": self.free_bytes_before,
            "free_bytes_after": self.free_bytes_after,
            "started_at_unix": self.started_at_unix,
            "ended_at_unix": self.ended_at_unix,
            "preflight_overall": self.preflight_overall,
            "approval_errors": list(self.approval_errors),
            "items": [item.to_dict() for item in self.items],
            "reclaim": None if self.reclaim is None else self.reclaim.to_dict(),
        }


def _load_json(source: JsonLike) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(os.fspath(source))
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: root must be a JSON object")
    return data


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _baseline_free(scan_root: Path) -> Optional[int]:
    probe = scan_root if scan_root.exists() else scan_root.parent
    try:
        usage = shutil.disk_usage(
            os.fspath(probe if probe.exists() else scan_root.anchor)
        )
        return int(usage.free)
    except OSError:
        return None


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        st = os.lstat(os.fspath(path))
        return windows.is_reparse_point(st)
    except OSError:
        return False


def _prior_succeeded(
    receipt: Optional[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if not receipt:
        return {}
    out: dict[str, Mapping[str, Any]] = {}
    for item in receipt.get("items") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status")) == "SUCCEEDED":
            item_id = str(item.get("item_id") or "")
            if item_id:
                out[item_id] = item
    return out


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    position = os.lseek(fd, 0, os.SEEK_CUR)
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.lseek(fd, position, os.SEEK_SET)
    return digest.hexdigest()


def _preflight_content_digests(preflight_source: Any) -> dict[str, str]:
    """Map item_id -> content_sha256 sealed in an approval-time preflight."""

    if isinstance(preflight_source, Mapping):
        data = dict(preflight_source)
    elif isinstance(preflight_source, (str, Path)):
        path = Path(os.fspath(preflight_source))
        if not path.is_file():
            return {}
        data = _load_json(path)
    else:
        return {}
    out: dict[str, str] = {}
    for row in data.get("items") or []:
        if not isinstance(row, Mapping):
            continue
        item_id = str(row.get("item_id") or "")
        digest = str(row.get("content_sha256") or "").strip().lower()
        if item_id and len(digest) == 64 and all(
            c in "0123456789abcdef" for c in digest
        ):
            out[item_id] = digest
    return out


def _bind_item_content_digest(
    item: Mapping[str, Any], digest: str
) -> dict[str, Any]:
    bound = dict(item)
    bound["content_sha256"] = digest
    identity = dict(bound.get("identity") or {})
    identity["content_sha256"] = digest
    bound["identity"] = identity
    return bound


class IdentityDriftError(OSError):
    """Raised when open-fd identity validation fails before unlink."""


def _delete_file(path: Path, item: Mapping[str, Any]) -> None:
    """Validate identity on an open fd, then unlink that same path object.

    POSIX: ``os.unlink`` while the fd remains open so a replacement at the
    name cannot become the unlinked inode (classic open→fstat→unlink hold).
    Windows: the CRT ``os.open`` path does not request ``FILE_SHARE_DELETE``,
    so unlink-while-open is unavailable; we fstat/hash via the open handle,
    close, then ``os.unlink`` immediately. Residual TOCTOU on Windows is
    narrower than a separate lstat-then-unlink path lookup, but not zero.
    """

    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(os.fspath(path), flags)
    unlink_after_close = os.name == "nt"
    try:
        st = os.fstat(fd)
        if windows.is_reparse_point(st):
            raise OSError("refuse unlink of reparse/symlink")
        try:
            if path.is_symlink():
                raise OSError("refuse unlink of reparse/symlink")
        except OSError as exc:
            if "refuse unlink" in str(exc):
                raise
            raise OSError(f"cannot inspect symlink state: {exc}") from exc
        if not stat.S_ISREG(st.st_mode):
            raise OSError(f"not a regular file: mode={st.st_mode}")
        observed_hash = _sha256_fd(fd)
        drift = identity_drift_against_lstat(
            item,
            path,
            st,
            observed_content_sha256=observed_hash,
        )
        if drift is not None:
            raise IdentityDriftError(drift)
        # When the item carried no digest, still require the fd hash to match
        # any approval-sealed content_sha256 injected onto the item.
        declared = (
            (item.get("identity") or {}).get("content_sha256")
            if isinstance(item.get("identity"), Mapping)
            else None
        ) or item.get("content_sha256")
        if declared:
            token = str(declared).strip().lower()
            if token and observed_hash.lower() != token:
                raise IdentityDriftError(
                    f"content digest drift: expected {token}, "
                    f"observed {observed_hash.lower()}"
                )
        if not unlink_after_close:
            os.unlink(os.fspath(path))
            return
    finally:
        os.close(fd)
    if unlink_after_close:
        os.unlink(os.fspath(path))


def _delete_directory_if_empty(path: Path) -> None:
    st = os.lstat(os.fspath(path))
    if windows.is_reparse_point(st) or path.is_symlink():
        raise OSError("refuse rmdir of reparse/symlink")
    if not stat.S_ISDIR(st.st_mode):
        raise OSError("not a directory")
    with os.scandir(os.fspath(path)) as entries:
        leftovers = [entry.name for entry in entries]
    if leftovers:
        raise OSError(f"directory not empty: {leftovers[:5]}")
    os.rmdir(os.fspath(path))


def _sort_bottom_up(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    def depth_key(item: Mapping[str, Any]) -> tuple[int, str]:
        path = str(item.get("path") or "")
        normalized = str(normalize_declared_path(path))
        return (-normalized.count("\\") - normalized.count("/"), normalized)

    return sorted(items, key=depth_key)


def _resolve_manifest_source(
    run_dir: Path, manifest: Mapping[str, Any] | PathLike
) -> tuple[dict[str, Any], Any]:
    if isinstance(manifest, (str, Path)):
        path = Path(os.fspath(manifest))
        return _load_json(path), path
    data = dict(manifest)
    on_disk = run_dir / DELETE_MANIFEST_FILENAME
    if on_disk.is_file():
        disk_data = _load_json(on_disk)
        if json.dumps(disk_data, sort_keys=True) == json.dumps(data, sort_keys=True):
            return data, on_disk
    return data, data


def _resolve_approval_source(
    run_dir: Path, approval: Mapping[str, Any] | PathLike | DeleteApprovalRecord
) -> dict[str, Any]:
    if isinstance(approval, (str, Path)):
        return dict(load_delete_approval(approval))
    if isinstance(approval, Mapping):
        return dict(approval)
    path = run_dir / DELETE_APPROVAL_FILENAME
    if path.is_file():
        return dict(load_delete_approval(path))
    raise ValueError("approval must be a mapping, path, or DeleteApprovalRecord")


def _validate_for_execute(
    approval: Mapping[str, Any],
    manifest_source: Any,
    approval_time_preflight: Any,
    fresh_overall: str,
) -> list[str]:
    """Validate approval binding; require fresh PASS; tolerate preflight byte churn.

    Approval is bound to the preflight identity at approve-time. Execute always
    re-runs preflight and requires a fresh PASS. ``preflight_sha256`` drift
    against the fresh file is expected and ignored only when fresh overall is
    PASS and the approval-time preflight validation (or approved snapshot)
    otherwise succeeds.
    """

    errors: list[str] = []
    if fresh_overall != "PASS":
        errors.append(f"fresh preflight overall must be PASS, got {fresh_overall!r}")

    raw = list(
        validate_delete_approval(approval, manifest_source, approval_time_preflight)
    )
    for err in raw:
        if "preflight_sha256 drift" in err and fresh_overall == "PASS":
            continue
        errors.append(err)
    if str(approval.get("action")) != DELETE_ACTION:
        errors.append("approval action must be DELETE_PERMANENTLY")
    return errors


def execute_permanent_delete(
    *,
    run_dir: Path,
    manifest: Mapping[str, Any] | PathLike,
    approval: Mapping[str, Any] | PathLike | DeleteApprovalRecord,
    preflight: Mapping[str, Any] | PathLike | None = None,
    scan_root: Path,
) -> ExecutionResult:
    """Validate approval + fresh PASS preflight, then permanently delete approved paths.

    Never enlarges the approved set on failure. Use synthetic/temp fixtures in
    tests; never default to live operator personal roots.
    """

    started = time.time()
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    scan = normalize_declared_path(scan_root)
    receipt_path = run_path / DELETE_RECEIPT_FILENAME

    manifest_data, manifest_source = _resolve_manifest_source(run_path, manifest)
    approval_data = _resolve_approval_source(run_path, approval)

    # Capture approval-time preflight BEFORE overwriting with a fresh run.
    # Prefer explicit argument, then approved snapshot, then current preflight file.
    approved_snapshot = run_path / "delete-preflight.approved.json"
    current_pf = run_path / "delete-preflight.json"
    if preflight is not None and isinstance(preflight, Mapping):
        approval_time_preflight: Any = dict(preflight)
    elif preflight is not None and isinstance(preflight, (str, Path)):
        approval_time_preflight = Path(os.fspath(preflight))
    elif approved_snapshot.is_file():
        approval_time_preflight = approved_snapshot
    elif current_pf.is_file():
        # Snapshot bytes so fresh preflight rewrite cannot break digest binding.
        if not approved_snapshot.is_file():
            approved_snapshot.write_bytes(current_pf.read_bytes())
        approval_time_preflight = approved_snapshot
    else:
        approval_time_preflight = {
            "schema_version": "filesteward.delete-preflight/v1",
            "overall": str(approval_data.get("preflight_overall") or "PASS"),
            "mutated_filesystem": False,
            "items": [],
        }

    approved_ids = [str(x) for x in approval_data.get("approved_item_ids") or []]
    by_id = {
        str(item.get("item_id")): item
        for item in manifest_data.get("items") or []
        if isinstance(item, Mapping) and item.get("item_id")
    }

    prior = _prior_succeeded(load_delete_receipt(receipt_path))
    items_out: list[ItemExecutionResult] = []
    free_before = _baseline_free(scan)

    # Reconcile prior SUCCEEDED items before fresh preflight so absent paths
    # do not fail-closed the replay as IDENTITY_MISSING.
    pending_ids: list[str] = []
    for item_id in approved_ids:
        item = by_id.get(item_id)
        if item is None:
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path="",
                    status="FAILED",
                    reason_class="UNKNOWN_ITEM",
                    detail="approved item missing from manifest",
                )
            )
            continue
        path = normalize_declared_path(str(item.get("path") or ""))
        if item_id in prior:
            if not path.exists():
                items_out.append(
                    ItemExecutionResult(
                        item_id=item_id,
                        path=str(path),
                        status="SKIPPED",
                        reason_class="PRIOR_SUCCEEDED",
                        detail="prior receipt SUCCEEDED and path already absent",
                    )
                )
            else:
                items_out.append(
                    ItemExecutionResult(
                        item_id=item_id,
                        path=str(path),
                        status="FAILED",
                        reason_class="PRIOR_SUCCEEDED_RESIDUAL",
                        detail="prior receipt SUCCEEDED but path still exists",
                    )
                )
            continue
        pending_ids.append(item_id)

    # Fresh preflight only over still-pending approved items (never enlarge set).
    pending_manifest = dict(manifest_data)
    pending_manifest["items"] = [
        by_id[item_id] for item_id in pending_ids if item_id in by_id
    ]
    pending_manifest["item_count"] = len(pending_manifest["items"])

    cleanup_plan = run_path / "cleanup-plan.csv"
    try:
        protection_roots, managed_paths = merge_execute_protection_context(
            run_path, scan
        )
    except ValueError as exc:
        result = ExecutionResult(
            overall="FAILED",
            run_dir=run_path,
            receipt_path=receipt_path,
            items=items_out,
            free_bytes_before=free_before,
            free_bytes_after=None,
            reclaim=None,
            started_at_unix=started,
            ended_at_unix=time.time(),
            approval_errors=(f"protection rediscovery failed: {exc}",),
            preflight_overall="",
        )
        _write_receipt(result, approval_data, manifest_data, {})
        return result
    protection_index = (
        ProtectionIndex(protection_roots) if protection_roots else None
    )

    # Inject approval-time sealed content digests so fresh preflight and
    # unlink-time identity checks refuse equal-size+mtime rewrites.
    sealed_digests = _preflight_content_digests(approval_time_preflight)
    if sealed_digests:
        rebound: list[Mapping[str, Any]] = []
        for item_id in pending_ids:
            item = by_id.get(item_id)
            if item is None:
                continue
            digest = sealed_digests.get(item_id)
            if digest:
                bound = _bind_item_content_digest(item, digest)
                by_id[item_id] = bound
                rebound.append(bound)
            else:
                rebound.append(item)
        pending_manifest["items"] = rebound

    if pending_ids:
        # Always pass the run-dir cleanup-plan path so a declared digest cannot
        # fail-open when the file is absent.
        fresh = run_preflight(
            pending_manifest,
            scan_root=scan,
            cleanup_plan_path=cleanup_plan,
            protection_roots=protection_roots,
            managed_paths=managed_paths,
        )
    else:
        # Nothing left to mutate; synthesize PASS without observing missing paths.
        from filesteward.deletion.preflight import PreflightResult

        fresh = PreflightResult(overall="PASS", mutated_filesystem=False, items=[])
    write_preflight_receipt(current_pf, fresh)
    preflight_data = fresh.to_dict()

    # Cross-check fresh sealed digests against approval-time seals when the
    # fresh receipt actually recorded per-item digests (skip empty synthetic
    # PASS stubs used only in unit tests).
    if sealed_digests and fresh.overall == "PASS":
        fresh_digests = _preflight_content_digests(preflight_data)
        if fresh_digests:
            for item_id, expected in sealed_digests.items():
                if item_id not in pending_ids:
                    continue
                observed = fresh_digests.get(item_id)
                if observed != expected:
                    errors_early = [
                        (
                            f"content digest drift for {item_id}: "
                            f"approved={expected} fresh={observed!r}"
                        )
                    ]
                    result = ExecutionResult(
                        overall="FAILED",
                        run_dir=run_path,
                        receipt_path=receipt_path,
                        items=items_out,
                        free_bytes_before=free_before,
                        free_bytes_after=None,
                        reclaim=None,
                        started_at_unix=started,
                        ended_at_unix=time.time(),
                        approval_errors=tuple(errors_early),
                        preflight_overall=str(fresh.overall),
                    )
                    _write_receipt(
                        result, approval_data, manifest_data, preflight_data
                    )
                    return result

    errors = _validate_for_execute(
        approval_data,
        manifest_source,
        approval_time_preflight,
        fresh.overall,
    )

    if errors:
        result = ExecutionResult(
            overall="FAILED",
            run_dir=run_path,
            receipt_path=receipt_path,
            items=items_out,
            free_bytes_before=free_before,
            free_bytes_after=None,
            reclaim=None,
            started_at_unix=started,
            ended_at_unix=time.time(),
            approval_errors=tuple(errors),
            preflight_overall=str(fresh.overall),
        )
        _write_receipt(result, approval_data, manifest_data, preflight_data)
        return result

    approved_items: list[Mapping[str, Any]] = [
        by_id[item_id] for item_id in pending_ids if item_id in by_id
    ]

    for item in _sort_bottom_up(approved_items):
        item_id = str(item.get("item_id"))
        raw_path = str(item.get("path") or "")
        path = normalize_declared_path(raw_path)
        item_type = str(item.get("item_type") or "").upper()

        escape = reparse_or_path_escape(path, scan)
        if escape is not None:
            reason, detail = escape
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="FAILED",
                    reason_class=reason,
                    detail=detail,
                )
            )
            continue

        if protection_index is not None:
            relation = protection_index.relation(path)
            if relation in (
                ProtectionRelation.SELF,
                ProtectionRelation.DESCENDANT,
                ProtectionRelation.ANCESTOR,
            ):
                items_out.append(
                    ItemExecutionResult(
                        item_id=item_id,
                        path=str(path),
                        status="FAILED",
                        reason_class="PROTECTION_HIT",
                        detail=f"protection index hit at execute ({relation.value})",
                    )
                )
                continue

        if path.exists() and _is_reparse(path):
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="FAILED",
                    reason_class="REPARSE_OR_SYMLINK",
                    detail="refuse symlink/junction/reparse",
                )
            )
            continue

        try:
            if item_type != "DIRECTORY":
                # open→fstat/hash validate→unlink (same inode/name object).
                _delete_file(path, item)
            else:
                st = os.lstat(os.fspath(path))
                if windows.is_reparse_point(st) or path.is_symlink():
                    raise OSError("reparse detected at unlink time")
                _delete_directory_if_empty(path)
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="SUCCEEDED",
                    reason_class="OK",
                    detail="permanently deleted",
                )
            )
        except FileNotFoundError:
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="FAILED",
                    reason_class="IDENTITY_MISSING",
                    detail="path missing at delete time",
                )
            )
        except IdentityDriftError as exc:
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="FAILED",
                    reason_class="IDENTITY_DRIFT",
                    detail=str(exc),
                )
            )
        except OSError as exc:
            items_out.append(
                ItemExecutionResult(
                    item_id=item_id,
                    path=str(path),
                    status="FAILED",
                    reason_class="DELETE_FAILED",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )

    free_after = _baseline_free(scan)
    residuals: list[str] = []
    for row in items_out:
        if row.path and Path(row.path).exists():
            residuals.append(row.path)

    reclaim = verify_reclaim(
        free_bytes_before=free_before,
        free_bytes_after=free_after,
        item_results=[i.to_dict() for i in items_out],
        residual_paths=residuals,
    )

    any_fail = any(i.status == "FAILED" for i in items_out)
    any_ok = any(i.status == "SUCCEEDED" for i in items_out)
    if any_fail and any_ok:
        overall = "PARTIAL"
    elif any_fail:
        overall = "FAILED"
    elif any_ok or any(i.status == "SKIPPED" for i in items_out):
        overall = "SUCCEEDED"
    else:
        overall = "FAILED"

    result = ExecutionResult(
        overall=overall,
        run_dir=run_path,
        receipt_path=receipt_path,
        items=items_out,
        free_bytes_before=free_before,
        free_bytes_after=free_after,
        reclaim=reclaim,
        started_at_unix=started,
        ended_at_unix=time.time(),
        approval_errors=(),
        preflight_overall=str(fresh.overall),
    )
    _write_receipt(result, approval_data, manifest_data, preflight_data)
    return result


def _write_receipt(
    result: ExecutionResult,
    approval: Mapping[str, Any],
    manifest: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> None:
    run_dir = result.run_dir
    manifest_path = run_dir / DELETE_MANIFEST_FILENAME
    approval_path = run_dir / DELETE_APPROVAL_FILENAME
    preflight_path = run_dir / "delete-preflight.json"

    def _digest(path: Path, fallback: Mapping[str, Any]) -> str:
        if path.is_file():
            return sha256_file(path)
        return _canonical_digest(fallback)

    receipt = {
        "schema_version": DELETE_RECEIPT_SCHEMA,
        "mode": DELETE_ACTION,
        "overall": result.overall,
        "run_id": manifest.get("run_id"),
        "started_at_unix": result.started_at_unix,
        "ended_at_unix": result.ended_at_unix,
        "delete_manifest_sha256": _digest(manifest_path, manifest),
        "delete_approval_sha256": _digest(approval_path, approval),
        "preflight_sha256": _digest(preflight_path, preflight),
        "free_bytes_before": result.free_bytes_before,
        "free_bytes_after": result.free_bytes_after,
        "items": [item.to_dict() for item in result.items],
        "residuals": [
            item.path for item in result.items if item.path and Path(item.path).exists()
        ],
        "reclaim": None if result.reclaim is None else result.reclaim.to_dict(),
        "approval_errors": list(result.approval_errors),
        "preflight_overall": result.preflight_overall,
    }
    write_delete_receipt(result.receipt_path, receipt)
