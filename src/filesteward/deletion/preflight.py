"""Fail-closed, no-mutation delete-manifest preflight engine.

Observes targets via ``lstat`` / directory enumeration only. Never unlinks,
renames, recycles, or quarantines. Authorization fields on the manifest are
ignored as mutation permission: ``UNAPPROVED`` is expected, and even
``DELETE_PERMANENTLY`` remains a dry-run here.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

from filesteward.inventory import windows
from filesteward.policy.paths import (
    is_lexically_within,
    normalize_declared_path,
)
from filesteward.protect import ProtectedRoot, ProtectionIndex, ProtectionRelation

__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "PREFLIGHT_SCHEMA_VERSION",
    "ItemVerdict",
    "PreflightResult",
    "ReasonClass",
    "run_preflight",
    "write_preflight_receipt",
]

MANIFEST_SCHEMA_VERSION = "filesteward.delete-manifest/v1"
PREFLIGHT_SCHEMA_VERSION = "filesteward.delete-preflight/v1"

PathLike = Union[str, Path]
ManifestLike = Union[Mapping[str, Any], PathLike]

# Windows attribute bits used for unsupported-semantics detection.
_FILE_ATTRIBUTE_READONLY = 0x1
_FILE_ATTRIBUTE_SPARSE_FILE = 0x200
_FILE_ATTRIBUTE_COMPRESSED = 0x800
_WIN_MAX_PATH = 260


class ReasonClass:
    """Stable fail-closed reason classes for delete-preflight receipts."""

    OK = "OK"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DIGEST_DRIFT = "DIGEST_DRIFT"
    PATH_ESCAPE = "PATH_ESCAPE"
    IDENTITY_MISSING = "IDENTITY_MISSING"
    IDENTITY_DRIFT = "IDENTITY_DRIFT"
    ITEM_TYPE_MISMATCH = "ITEM_TYPE_MISMATCH"
    REPARSE_OR_SYMLINK = "REPARSE_OR_SYMLINK"
    PROTECTION_HIT = "PROTECTION_HIT"
    MANAGED_PATH = "MANAGED_PATH"
    CLOUD_PLACEHOLDER = "CLOUD_PLACEHOLDER"
    PROVIDER_UNCERTAINTY = "PROVIDER_UNCERTAINTY"
    DIRECTORY_CHILD_DRIFT = "DIRECTORY_CHILD_DRIFT"
    HARDLINK_AMBIGUITY = "HARDLINK_AMBIGUITY"
    LOCKED_OR_DENIED = "LOCKED_OR_DENIED"
    UNSUPPORTED_SEMANTICS = "UNSUPPORTED_SEMANTICS"
    MANIFEST_INVALID = "MANIFEST_INVALID"


@dataclass(frozen=True)
class ItemVerdict:
    item_id: str
    verdict: str
    reason_class: str
    detail: str
    projected_reclaim_bytes: Optional[int] = None

    def to_dict(self) -> dict[str, str]:
        return {
            "item_id": self.item_id,
            "verdict": self.verdict,
            "reason_class": self.reason_class,
            "detail": self.detail,
        }


@dataclass
class PreflightResult:
    overall: str
    mutated_filesystem: bool = False
    baseline_free_bytes: Optional[int] = None
    recalculated_projected_reclaim_bytes: Optional[int] = None
    items: list[ItemVerdict] = field(default_factory=list)
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION
    schema_version: str = PREFLIGHT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_schema_version": self.manifest_schema_version,
            "overall": self.overall,
            "mutated_filesystem": False,
            "baseline_free_bytes": self.baseline_free_bytes,
            "recalculated_projected_reclaim_bytes": (
                self.recalculated_projected_reclaim_bytes
            ),
            "items": [item.to_dict() for item in self.items],
        }


def _fail(
    item_id: str,
    reason_class: str,
    detail: str,
) -> ItemVerdict:
    return ItemVerdict(
        item_id=item_id,
        verdict="FAIL",
        reason_class=reason_class,
        detail=detail,
        projected_reclaim_bytes=None,
    )


def _pass(
    item_id: str,
    detail: str = "identity matches; reclaim exclusive",
    *,
    projected_reclaim_bytes: Optional[int] = None,
) -> ItemVerdict:
    return ItemVerdict(
        item_id=item_id,
        verdict="PASS",
        reason_class=ReasonClass.OK,
        detail=detail,
        projected_reclaim_bytes=projected_reclaim_bytes,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(manifest: ManifestLike) -> dict[str, Any]:
    if isinstance(manifest, Mapping):
        return dict(manifest)
    path = Path(os.fspath(manifest))
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("delete-manifest root must be a JSON object")
    return data


def _iso_or_float_mtime(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            # Accept ISO-8601 without requiring datetime dependency quirks:
            # identity policy compares numeric epoch when possible; string
            # mismatch against observed float is handled by the caller.
            return None
    return None


def _mtime_matches(expected: Any, observed: float, *, tolerance: float = 1.0) -> bool:
    """Material mtime match: numeric epoch within tolerance, else exact string."""

    if expected is None:
        return False
    if isinstance(expected, (int, float)):
        return abs(float(expected) - observed) <= tolerance
    if isinstance(expected, str):
        text = expected.strip()
        try:
            return abs(float(text) - observed) <= tolerance
        except ValueError:
            return False
    return False


def _observed_item_type(path: Path, st: os.stat_result) -> str:
    mode = st.st_mode
    if path.is_symlink() or windows.is_reparse_point(st):
        # Callers treat reparse separately; type string still reports surface.
        if stat.S_ISDIR(mode):
            return "DIRECTORY"
        if stat.S_ISREG(mode):
            return "FILE"
        return "OTHER"
    if stat.S_ISDIR(mode):
        return "DIRECTORY"
    if stat.S_ISREG(mode):
        return "FILE"
    return "OTHER"


def _link_count(path: Path, st: os.stat_result) -> Optional[int]:
    nlink = getattr(st, "st_nlink", None)
    if isinstance(nlink, int) and nlink > 0:
        return nlink
    # Windows DirEntry/lstat may report 0; re-observe with os.stat no-follow.
    try:
        alt = os.stat(os.fspath(path), follow_symlinks=False)
        alt_nlink = getattr(alt, "st_nlink", None)
        if isinstance(alt_nlink, int) and alt_nlink > 0:
            return alt_nlink
    except OSError:
        return None
    return None


def _allocated_bytes(st: os.stat_result) -> Optional[int]:
    blocks = getattr(st, "st_blocks", None)
    if isinstance(blocks, int) and blocks > 0:
        return blocks * 512
    return None


def _path_too_long(path: Path) -> bool:
    raw = os.fspath(path)
    if raw.startswith("\\\\?\\"):
        return False
    return len(raw) >= _WIN_MAX_PATH


def _enumerate_descendants(root: Path) -> tuple[Optional[set[str]], Optional[str]]:
    """No-follow walk of descendants. Returns (paths, error_detail)."""

    observed: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(os.fspath(current)) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    observed.add(str(normalize_declared_path(child)))
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_symlink = entry.is_symlink()
                    except OSError as exc:
                        return None, f"cannot enumerate {child}: {exc}"
                    reparse = False
                    try:
                        st = entry.stat(follow_symlinks=False)
                        reparse = windows.is_reparse_point(st)
                    except OSError:
                        # Still recorded as observed; type unknown.
                        pass
                    if is_dir and not is_symlink and not reparse:
                        stack.append(child)
        except OSError as exc:
            return None, f"cannot scandir {current}: {exc}"
    return observed, None


def _baseline_free_bytes(paths: Sequence[Path]) -> Optional[int]:
    for path in paths:
        probe = path if path.exists() else path.parent
        try:
            usage = shutil.disk_usage(os.fspath(probe if probe.exists() else path.anchor or probe))
            return int(usage.free)
        except OSError:
            continue
    return None


def _identity_map(item: Mapping[str, Any]) -> Mapping[str, Any]:
    identity = item.get("identity")
    if isinstance(identity, Mapping):
        return identity
    return item


def _build_protection_index(
    protection_roots: Iterable[Any],
) -> ProtectionIndex:
    roots: list[ProtectedRoot] = []
    for root in protection_roots:
        if isinstance(root, ProtectedRoot):
            roots.append(root)
        else:
            roots.append(
                ProtectedRoot(path=os.fspath(root), source="preflight-protection")
            )
    return ProtectionIndex(roots)


def _is_managed(path: Path, managed_paths: Sequence[Path]) -> bool:
    for managed in managed_paths:
        if path == managed or is_lexically_within(path, managed):
            return True
    return False


def _approved_descendants(
    directory: Path,
    all_paths: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    dir_key = str(normalize_declared_path(directory))
    approved: set[str] = set()
    for key in all_paths:
        if key == dir_key:
            continue
        if is_lexically_within(key, dir_key):
            approved.add(key)
    return approved


def _check_item(
    item: Mapping[str, Any],
    *,
    scan_root: Optional[Path],
    protection: ProtectionIndex,
    managed_paths: Sequence[Path],
    all_items_by_path: Mapping[str, Mapping[str, Any]],
) -> ItemVerdict:
    item_id = str(item.get("item_id") or "")
    raw_path = item.get("path")
    if not raw_path:
        return _fail(item_id, ReasonClass.MANIFEST_INVALID, "item path missing")

    path = normalize_declared_path(raw_path)
    identity = _identity_map(item)
    declared_type = str(
        item.get("item_type") or identity.get("item_type") or ""
    ).upper()

    if scan_root is not None and not is_lexically_within(path, scan_root):
        return _fail(
            item_id,
            ReasonClass.PATH_ESCAPE,
            f"path escapes approved scan_root {scan_root}",
        )

    if _path_too_long(path):
        return _fail(
            item_id,
            ReasonClass.UNSUPPORTED_SEMANTICS,
            "path length exceeds Windows MAX_PATH without extended prefix",
        )

    # Rebuild protection; do not trust stale protection_check flags.
    relation = protection.relation(path)
    if relation in (ProtectionRelation.SELF, ProtectionRelation.DESCENDANT):
        return _fail(
            item_id,
            ReasonClass.PROTECTION_HIT,
            f"protection index hit ({relation.value})",
        )
    if relation is ProtectionRelation.ANCESTOR:
        return _fail(
            item_id,
            ReasonClass.PROTECTION_HIT,
            "directory is an ancestor of a protected root; action prohibited",
        )

    if item.get("is_managed") is True or _is_managed(path, managed_paths):
        return _fail(
            item_id,
            ReasonClass.MANAGED_PATH,
            "path is managed; mutation blocked",
        )

    if item.get("is_cloud_placeholder") is True:
        return _fail(
            item_id,
            ReasonClass.CLOUD_PLACEHOLDER,
            "manifest marks cloud placeholder; provider uncertainty",
        )

    try:
        st = os.lstat(os.fspath(path))
    except FileNotFoundError:
        return _fail(
            item_id,
            ReasonClass.IDENTITY_MISSING,
            "target path missing at preflight",
        )
    except PermissionError as exc:
        return _fail(
            item_id,
            ReasonClass.LOCKED_OR_DENIED,
            f"permission denied: {exc}",
        )
    except OSError as exc:
        # Sharing violations / cannot lstat => FAIL, never skip-as-absent.
        return _fail(
            item_id,
            ReasonClass.LOCKED_OR_DENIED,
            f"cannot lstat target: {type(exc).__name__}: {exc}",
        )

    try:
        symlink = path.is_symlink()
    except OSError as exc:
        return _fail(
            item_id,
            ReasonClass.LOCKED_OR_DENIED,
            f"cannot inspect symlink state: {exc}",
        )

    reparse = windows.is_reparse_point(st) or symlink
    if reparse or item.get("is_symlink") or item.get("is_reparse_point"):
        return _fail(
            item_id,
            ReasonClass.REPARSE_OR_SYMLINK,
            "symlink/junction/reparse at target; no-follow fail-closed",
        )

    if windows.is_cloud_placeholder(st):
        return _fail(
            item_id,
            ReasonClass.CLOUD_PLACEHOLDER,
            "Windows cloud-placeholder attributes detected",
        )

    attrs = windows.file_attributes(st)
    if attrs & (_FILE_ATTRIBUTE_SPARSE_FILE | _FILE_ATTRIBUTE_COMPRESSED):
        observed_alloc = _allocated_bytes(st)
        if observed_alloc is None:
            return _fail(
                item_id,
                ReasonClass.UNSUPPORTED_SEMANTICS,
                "sparse/compressed file without proveable allocated reclaim",
            )

    if attrs & _FILE_ATTRIBUTE_READONLY:
        return _fail(
            item_id,
            ReasonClass.UNSUPPORTED_SEMANTICS,
            "readonly attribute set; readonly is not delete",
        )

    observed_type = _observed_item_type(path, st)
    if declared_type and observed_type != declared_type:
        return _fail(
            item_id,
            ReasonClass.ITEM_TYPE_MISMATCH,
            f"item_type mismatch: declared {declared_type}, observed {observed_type}",
        )

    # Identity: material size/mtime must match declared identity facts.
    expected_logical = identity.get("logical_size_bytes", item.get("logical_size_bytes"))
    expected_mtime = identity.get("modified_at", item.get("modified_at"))
    expected_path = identity.get("path", item.get("path"))
    if expected_path and normalize_declared_path(expected_path) != path:
        return _fail(
            item_id,
            ReasonClass.IDENTITY_DRIFT,
            "identity.path does not match item path",
        )

    observed_logical = int(getattr(st, "st_size", 0) or 0)
    if declared_type == "FILE" or (
        not declared_type and stat.S_ISREG(st.st_mode)
    ):
        if expected_logical is not None and int(expected_logical) != observed_logical:
            return _fail(
                item_id,
                ReasonClass.IDENTITY_DRIFT,
                f"logical size drift: expected {expected_logical}, observed {observed_logical}",
            )
        observed_mtime = float(st.st_mtime)
        if expected_mtime is not None and not _mtime_matches(expected_mtime, observed_mtime):
            return _fail(
                item_id,
                ReasonClass.IDENTITY_DRIFT,
                f"mtime drift: expected {expected_mtime}, observed {observed_mtime}",
            )
        expected_alloc = identity.get(
            "allocated_size_bytes", item.get("allocated_size_bytes")
        )
        observed_alloc = _allocated_bytes(st)
        if (
            expected_alloc is not None
            and observed_alloc is not None
            and int(expected_alloc) != observed_alloc
        ):
            return _fail(
                item_id,
                ReasonClass.IDENTITY_DRIFT,
                f"allocated size drift: expected {expected_alloc}, observed {observed_alloc}",
            )

    expected_links = identity.get("link_count", item.get("link_count"))
    links = _link_count(path, st)
    if declared_type == "FILE" or stat.S_ISREG(st.st_mode):
        if links is None:
            return _fail(
                item_id,
                ReasonClass.HARDLINK_AMBIGUITY,
                "link_count unknown; exclusive reclaim not proven",
            )
        if links > 1 or (
            expected_links is not None and int(expected_links) > 1
        ):
            return _fail(
                item_id,
                ReasonClass.HARDLINK_AMBIGUITY,
                f"hardlink ambiguity (link_count={links}); exclusive reclaim not proven",
            )
        if expected_links is not None and int(expected_links) != links:
            return _fail(
                item_id,
                ReasonClass.IDENTITY_DRIFT,
                f"link_count drift: expected {expected_links}, observed {links}",
            )

    if declared_type == "DIRECTORY" or (
        not declared_type and stat.S_ISDIR(st.st_mode)
    ):
        approved = _approved_descendants(path, all_items_by_path)
        observed, enum_error = _enumerate_descendants(path)
        if enum_error:
            return _fail(
                item_id,
                ReasonClass.LOCKED_OR_DENIED,
                enum_error,
            )
        assert observed is not None
        if observed != approved:
            extra = sorted(observed - approved)
            missing = sorted(approved - observed)
            return _fail(
                item_id,
                ReasonClass.DIRECTORY_CHILD_DRIFT,
                (
                    "directory child set drift; "
                    f"extra={extra[:5]}; missing={missing[:5]}"
                ),
            )
        return _pass(
            item_id,
            "directory identity matches; child set exact",
            projected_reclaim_bytes=0,
        )

    # Proven exclusive reclaim for a single-link regular file.
    projected: Optional[int] = None
    observed_alloc = _allocated_bytes(st)
    if observed_alloc is not None:
        projected = observed_alloc
    else:
        declared_projected = item.get("projected_reclaim_bytes")
        declared_alloc = item.get("allocated_size_bytes")
        if declared_alloc is not None:
            projected = int(declared_alloc)
        elif declared_projected is not None:
            projected = int(declared_projected)
        else:
            projected = observed_logical

    return _pass(item_id, projected_reclaim_bytes=projected)


def run_preflight(
    manifest: ManifestLike,
    *,
    scan_root: Optional[PathLike] = None,
    cleanup_plan_path: Optional[PathLike] = None,
    protection_roots: Iterable[Any] = (),
    managed_paths: Iterable[PathLike] = (),
) -> PreflightResult:
    """Validate a delete-manifest against live, read-only filesystem state.

    Never mutates targets. Does not honor ``authorization_state`` as
    permission to mutate.
    """

    try:
        data = _load_manifest(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return PreflightResult(
            overall="FAIL",
            mutated_filesystem=False,
            items=[
                _fail(
                    "",
                    ReasonClass.MANIFEST_INVALID,
                    f"cannot load delete-manifest: {exc}",
                )
            ],
        )

    schema = str(data.get("schema_version") or "")
    if schema != MANIFEST_SCHEMA_VERSION:
        return PreflightResult(
            overall="FAIL",
            mutated_filesystem=False,
            manifest_schema_version=schema or MANIFEST_SCHEMA_VERSION,
            items=[
                _fail(
                    "",
                    ReasonClass.SCHEMA_MISMATCH,
                    f"expected {MANIFEST_SCHEMA_VERSION}, got {schema!r}",
                )
            ],
        )

    # Authorization is informational only — never a mutation gate here.
    _ = data.get("authorization_state")
    _ = data.get("intended_action")

    items_raw = data.get("items")
    if not isinstance(items_raw, list):
        return PreflightResult(
            overall="FAIL",
            mutated_filesystem=False,
            items=[
                _fail(
                    "",
                    ReasonClass.MANIFEST_INVALID,
                    "manifest items must be a list",
                )
            ],
        )

    root_path = (
        normalize_declared_path(scan_root) if scan_root is not None else None
    )
    managed = tuple(
        normalize_declared_path(path) for path in managed_paths
    )
    protection = _build_protection_index(protection_roots)

    verdicts: list[ItemVerdict] = []

    expected_digest = str(data.get("source_cleanup_plan_sha256") or "")
    if cleanup_plan_path is not None:
        plan_path = Path(os.fspath(cleanup_plan_path))
        try:
            actual_digest = _sha256_file(plan_path)
        except OSError as exc:
            verdicts.append(
                _fail(
                    "",
                    ReasonClass.DIGEST_DRIFT,
                    f"cannot read cleanup plan for digest: {exc}",
                )
            )
            actual_digest = None
        if actual_digest is not None and (
            not expected_digest or actual_digest.lower() != expected_digest.lower()
        ):
            # Digest drift fails the whole run; still attach a synthetic item.
            verdicts.append(
                _fail(
                    "",
                    ReasonClass.DIGEST_DRIFT,
                    (
                        "cleanup-plan digest drift: "
                        f"manifest={expected_digest or '<missing>'} "
                        f"observed={actual_digest}"
                    ),
                )
            )

    # Index paths for directory child-set checks.
    by_path: dict[str, Mapping[str, Any]] = {}
    for raw in items_raw:
        if not isinstance(raw, Mapping):
            verdicts.append(
                _fail("", ReasonClass.MANIFEST_INVALID, "item is not an object")
            )
            continue
        path_value = raw.get("path")
        if path_value:
            by_path[str(normalize_declared_path(path_value))] = raw

    probe_paths: list[Path] = []
    if root_path is not None:
        probe_paths.append(root_path)
    for key in by_path:
        probe_paths.append(Path(key))
        if len(probe_paths) > 8:
            break

    baseline = _baseline_free_bytes(probe_paths)

    # If digest already failed, still evaluate items so receipts show detail,
    # but overall remains FAIL.
    for raw in items_raw:
        if not isinstance(raw, Mapping):
            continue
        # Per-item digest echo (optional consistency with top-level digest).
        item_digest = raw.get("source_cleanup_plan_sha256")
        if (
            expected_digest
            and item_digest
            and str(item_digest).lower() != expected_digest.lower()
        ):
            verdicts.append(
                _fail(
                    str(raw.get("item_id") or ""),
                    ReasonClass.DIGEST_DRIFT,
                    "item source_cleanup_plan_sha256 mismatches manifest digest",
                )
            )
            continue
        verdicts.append(
            _check_item(
                raw,
                scan_root=root_path,
                protection=protection,
                managed_paths=managed,
                all_items_by_path=by_path,
            )
        )

    any_fail = any(v.verdict == "FAIL" for v in verdicts)
    reclaim_total = 0
    reclaim_known = False
    for verdict in verdicts:
        if verdict.verdict == "PASS" and verdict.projected_reclaim_bytes is not None:
            reclaim_total += int(verdict.projected_reclaim_bytes)
            reclaim_known = True

    return PreflightResult(
        overall="FAIL" if any_fail else "PASS",
        mutated_filesystem=False,
        baseline_free_bytes=baseline,
        recalculated_projected_reclaim_bytes=(
            reclaim_total if reclaim_known else None
        ),
        items=verdicts,
        manifest_schema_version=schema,
    )


def write_preflight_receipt(
    path: PathLike,
    result: PreflightResult,
) -> Path:
    """Write ``delete-preflight.json``. Always records mutated_filesystem=false."""

    out = Path(os.fspath(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload["mutated_filesystem"] = False
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return out
