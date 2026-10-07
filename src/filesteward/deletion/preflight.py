"""Fail-closed, no-mutation delete-manifest preflight engine.

Observes targets via ``lstat`` / directory enumeration only. Never unlinks,
renames, recycles, or quarantines. Authorization fields on the manifest are
ignored as mutation permission: ``UNAPPROVED`` is expected, and even
``DELETE_PERMANENTLY`` remains a dry-run here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
from filesteward.ownership.actions import OwnershipResolver, unresolved_ownership
from filesteward.deletion.ownership import revalidate_ownership, validate_source_membership
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

from filesteward.deletion.regenerable import allows_size_mtime_identity_seal
from filesteward.inventory import windows
from filesteward.policy.paths import (
    is_lexically_within,
    is_symlink_or_reparse,
    normalize_declared_path,
)
from filesteward.protect import ProtectedRoot, ProtectionIndex, ProtectionRelation

__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "PREFLIGHT_SCHEMA_VERSION",
    "ItemVerdict",
    "PreflightResult",
    "ReasonClass",
    "discover_scan_protection_roots",
    "identity_drift_against_lstat",
    "load_run_protection_context",
    "merge_execute_protection_context",
    "reparse_or_path_escape",
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
    CAPACITY_ACTION_NOT_ADMITTED = "CAPACITY_ACTION_NOT_ADMITTED"
    SOURCE_ACTION_INVALID = "SOURCE_ACTION_INVALID"
    PROTECTIVE_DEPENDENCY_PRESENT = "PROTECTIVE_DEPENDENCY_PRESENT"
    OWNERSHIP_REVISION_DRIFT = "OWNERSHIP_REVISION_DRIFT"
    OWNERSHIP_UNKNOWN = "OWNERSHIP_UNKNOWN"
    OWNERSHIP_EVIDENCE_STALE = "OWNERSHIP_EVIDENCE_STALE"
    APP_DEPENDENCY_PRESENT = "APP_DEPENDENCY_PRESENT"
    SERVICEABILITY_DEPENDENCY_PRESENT = "SERVICEABILITY_DEPENDENCY_PRESENT"
    REPOSITORY_UNIQUE_WORK_PRESENT = "REPOSITORY_UNIQUE_WORK_PRESENT"
    REGENERATION_PROOF_MISSING = "REGENERATION_PROOF_MISSING"
    SEMANTIC_ACTION_REQUIRED = "SEMANTIC_ACTION_REQUIRED"

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
    CLEANUP_PLAN_MISSING = "CLEANUP_PLAN_MISSING"


@dataclass(frozen=True)
class ItemVerdict:
    item_id: str
    verdict: str
    reason_class: str
    detail: str
    projected_reclaim_bytes: Optional[int] = None
    content_sha256: Optional[str] = None
    ownership: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "item_id": self.item_id,
            "verdict": self.verdict,
            "reason_class": self.reason_class,
            "detail": self.detail,
        }
        if self.content_sha256:
            payload["content_sha256"] = self.content_sha256
        if self.ownership is not None:
            payload["ownership"] = dict(self.ownership)
        return payload


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
    content_sha256: Optional[str] = None,
) -> ItemVerdict:
    return ItemVerdict(
        item_id=item_id,
        verdict="PASS",
        reason_class=ReasonClass.OK,
        detail=detail,
        projected_reclaim_bytes=projected_reclaim_bytes,
        content_sha256=content_sha256,
    )


def _is_sha256_hex(token: str) -> bool:
    return len(token) == 64 and all(c in "0123456789abcdef" for c in token)


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


def _exclusions_explicit_root_column(
    fieldnames: Sequence[Optional[str]],
) -> Optional[str]:
    """Return the CSV header name for an explicit protection-root column.

    The exclusion item ``path`` column is never a root column: ANCESTOR rows
    record the scan root (or other ancestor) as ``path``, which must not be
    promoted into ``ProtectedRoot``. Only an explicit root column is consulted.
    """

    names = [name for name in fieldnames if isinstance(name, str) and name]
    by_fold = {name.casefold(): name for name in names}
    for candidate in ("protected_root", "root"):
        if candidate in by_fold:
            return by_fold[candidate]
    return None


def load_run_protection_context(
    run_dir: PathLike,
) -> tuple[tuple[ProtectedRoot, ...], tuple[Path, ...]]:
    """Rebuild protection roots and managed prefixes from run artifacts.

    Sources (union, fail-closed):
    - ``run.json`` ``protected_roots`` / ``managed_paths`` (canonical roots)
    - ``protected-exclusions.csv`` only when an explicit root column exists
      (``protected_root`` or ``root``); the exclusion ``path`` column is never
      treated as a protection root. ANCESTOR exclusion rows never contribute
      roots.

    An empty root list with a valid exclusions CSV is allowed when ``run.json``
    supplies roots or when execute-time rediscovery fills the gap.

    Unreadable or malformed ``run.json`` / ``protected-exclusions.csv`` raise
    ``ValueError`` (fail closed). Partial CSV loads are never returned.
    """

    target = Path(os.fspath(run_dir))
    roots: list[ProtectedRoot] = []
    managed: list[Path] = []
    seen_roots: set[str] = set()

    def _add_root(path_value: Any, source: str) -> None:
        if not path_value:
            return
        normalized = normalize_declared_path(path_value)
        key = str(normalized).casefold()
        if key in seen_roots:
            return
        seen_roots.add(key)
        roots.append(ProtectedRoot(path=str(normalized), source=source))

    meta_path = target / "run.json"
    if meta_path.is_file():
        try:
            with meta_path.open("r", encoding="utf-8") as handle:
                metadata = json.load(handle)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"unreadable or malformed run.json at {meta_path}: {exc}"
            ) from exc
        if not isinstance(metadata, dict):
            raise ValueError(f"run.json at {meta_path} must be a JSON object")
        for entry in metadata.get("protected_roots") or []:
            if isinstance(entry, Mapping):
                _add_root(entry.get("path"), str(entry.get("source") or "run.json"))
            else:
                _add_root(entry, "run.json")
        for raw in metadata.get("managed_paths") or []:
            if raw:
                managed.append(normalize_declared_path(raw))

    exclusions_path = target / "protected-exclusions.csv"
    if exclusions_path.is_file():
        try:
            with exclusions_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    raise ValueError("protected-exclusions.csv missing header row")
                fieldnames = tuple(reader.fieldnames)
                rows = list(reader)
        except (OSError, csv.Error, UnicodeError, ValueError) as exc:
            raise ValueError(
                f"unreadable or malformed protected-exclusions.csv at "
                f"{exclusions_path}: {exc}"
            ) from exc
        root_column = _exclusions_explicit_root_column(fieldnames)
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(
                    f"malformed protected-exclusions.csv row at {exclusions_path}"
                )
            # Exclusion item paths (including ANCESTOR scan-root rows) are
            # never protection roots. Only an explicit root column may add
            # roots, and ANCESTOR rows are skipped even then.
            relationship = str(row.get("relationship") or "").strip().upper()
            if relationship == "ANCESTOR":
                continue
            if root_column is None:
                continue
            source = str(row.get("protection_source") or "protected-exclusions")
            _add_root(row.get(root_column), source)

    return tuple(roots), tuple(managed)


def discover_scan_protection_roots(
    scan_root: PathLike,
) -> tuple[ProtectedRoot, ...]:
    """Rediscover git/worktree protection roots under ``scan_root``.

    Fail closed when discovery itself raises. An empty discovery result
    (no git roots under the scan) is allowed and returns ``()``.
    """

    root = normalize_declared_path(scan_root)
    try:
        return ProtectionIndex.from_git_discovery(root).roots
    except OSError as exc:
        raise ValueError(
            f"protection rediscovery unavailable for scan_root {root}: {exc}"
        ) from exc


def merge_execute_protection_context(
    run_dir: PathLike,
    scan_root: PathLike,
) -> tuple[tuple[ProtectedRoot, ...], tuple[Path, ...]]:
    """Union run-artifact protection with fresh scan rediscovery."""

    artifact_roots, managed = load_run_protection_context(run_dir)
    discovered = discover_scan_protection_roots(scan_root)
    seen: set[str] = set()
    merged: list[ProtectedRoot] = []
    for root in (*artifact_roots, *discovered):
        key = str(normalize_declared_path(root.path)).casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(root)
    return tuple(merged), managed


def reparse_or_path_escape(
    path: PathLike,
    scan_root: Optional[PathLike],
) -> Optional[tuple[str, str]]:
    """Return ``(reason_class, detail)`` when path escapes via reparse/symlink.

    Checks:
    1. lexical containment under ``scan_root`` (when provided);
    2. any intermediate component from ``path`` up through ``scan_root`` is a
       symlink/junction/reparse (including ``scan_root`` itself);
    3. ``realpath(path)`` remains lexically within ``realpath(scan_root)``.
    """

    target = normalize_declared_path(path)
    if scan_root is None:
        # Still refuse reparse at the leaf and ancestors that exist.
        cursor: Optional[Path] = target
        while cursor is not None:
            if cursor.exists() and is_symlink_or_reparse(cursor):
                return (
                    ReasonClass.REPARSE_OR_SYMLINK,
                    f"symlink/junction/reparse at {cursor}",
                )
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        return None

    root = normalize_declared_path(scan_root)
    if not is_lexically_within(target, root):
        return (
            ReasonClass.PATH_ESCAPE,
            f"path escapes approved scan_root {root}",
        )

    cursor = target
    while True:
        if cursor.exists() and is_symlink_or_reparse(cursor):
            return (
                ReasonClass.REPARSE_OR_SYMLINK,
                f"symlink/junction/reparse on path component {cursor}",
            )
        if cursor == root:
            break
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent

    try:
        real_target = normalize_declared_path(
            Path(os.path.realpath(os.fspath(target)))
        )
        real_root = normalize_declared_path(Path(os.path.realpath(os.fspath(root))))
    except OSError as exc:
        return (
            ReasonClass.PATH_ESCAPE,
            f"cannot resolve realpath for containment: {exc}",
        )
    # Containment must use realpath(scan_root), not the lexical scan_root alone.
    if real_target != real_root and not is_lexically_within(real_target, real_root):
        return (
            ReasonClass.PATH_ESCAPE,
            (
                f"realpath {real_target} escapes realpath(scan_root) "
                f"{real_root}"
            ),
        )
    return None


def _declared_content_digest(item: Mapping[str, Any]) -> Optional[str]:
    identity = _identity_map(item)
    raw = (
        identity.get("content_sha256")
        or item.get("content_sha256")
        or identity.get("identity_token")
        or item.get("identity_token")
    )
    if raw is None:
        return None
    token = str(raw).strip()
    return token or None


def identity_drift_against_lstat(
    item: Mapping[str, Any],
    path: PathLike,
    st: os.stat_result,
    *,
    observed_content_sha256: Optional[str] = None,
) -> Optional[str]:
    """Return IDENTITY_DRIFT detail when live ``lstat`` disagrees with item.

    Floor: path + logical size + mtime (+ allocated when both known).
    Stronger: when ``content_sha256`` / ``identity_token`` is present, verify
    file content digest. Non-empty but invalid (not 64 hex) tokens FAIL;
    they are never ignored. ``observed_content_sha256`` may supply a digest
    already computed from an open fd (TOCTOU-safe unlink path).
    """

    normalized = normalize_declared_path(path)
    identity = _identity_map(item)
    declared_type = str(
        item.get("item_type") or identity.get("item_type") or ""
    ).upper()
    expected_path = identity.get("path", item.get("path"))
    if expected_path and normalize_declared_path(expected_path) != normalized:
        return "identity.path does not match item path"

    is_file = declared_type == "FILE" or (
        not declared_type and stat.S_ISREG(st.st_mode)
    )
    if not is_file:
        return None

    expected_logical = identity.get("logical_size_bytes", item.get("logical_size_bytes"))
    expected_mtime = identity.get("modified_at", item.get("modified_at"))
    observed_logical = int(getattr(st, "st_size", 0) or 0)
    if expected_logical is not None and int(expected_logical) != observed_logical:
        return (
            f"logical size drift: expected {expected_logical}, "
            f"observed {observed_logical}"
        )
    observed_mtime = float(st.st_mtime)
    if expected_mtime is not None and not _mtime_matches(expected_mtime, observed_mtime):
        return f"mtime drift: expected {expected_mtime}, observed {observed_mtime}"

    expected_alloc = identity.get(
        "allocated_size_bytes", item.get("allocated_size_bytes")
    )
    observed_alloc = _allocated_bytes(st)
    if (
        expected_alloc is not None
        and observed_alloc is not None
        and int(expected_alloc) != observed_alloc
    ):
        return (
            f"allocated size drift: expected {expected_alloc}, "
            f"observed {observed_alloc}"
        )

    expected_hash = _declared_content_digest(item)
    if expected_hash is not None:
        token = expected_hash.lower()
        if not _is_sha256_hex(token):
            return (
                f"invalid content digest token (want 64 hex): {expected_hash!r}"
            )
        if observed_content_sha256 is not None:
            actual = observed_content_sha256.lower()
        else:
            try:
                actual = _sha256_file(normalized)
            except OSError as exc:
                return f"cannot hash target for identity: {exc}"
        if actual.lower() != token:
            return (
                f"content digest drift: expected {token}, observed {actual.lower()}"
            )
    return None


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

    escape = reparse_or_path_escape(path, scan_root)
    if escape is not None:
        reason, detail = escape
        return _fail(item_id, reason, detail)

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

    # Identity: size/mtime floor; content digest required for regular files.
    drift = identity_drift_against_lstat(item, path, st)
    if drift is not None:
        return _fail(item_id, ReasonClass.IDENTITY_DRIFT, drift)

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
    # Default: seal observed content digest so approval-bound preflight and
    # fresh execute preflight can refuse equal-size+mtime rewrites.
    # Regenerable-cache / temp contract roots skip full-file hashing and seal
    # with size+mtime only (open→fstat→unlink TOCTOU remains at execute).
    declared_digest = _declared_content_digest(item)
    sealed_digest: Optional[str] = None
    if declared_digest is not None:
        sealed_digest = declared_digest.lower()
    elif scan_root is None or not allows_size_mtime_identity_seal(scan_root):
        try:
            sealed_digest = _sha256_file(path)
        except OSError as exc:
            return _fail(
                item_id,
                ReasonClass.IDENTITY_DRIFT,
                f"cannot hash target for identity seal: {exc}",
            )

    projected: Optional[int] = None
    observed_alloc = _allocated_bytes(st)
    observed_logical = int(getattr(st, "st_size", 0) or 0)
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

    return _pass(
        item_id,
        projected_reclaim_bytes=projected,
        content_sha256=sealed_digest,
    )


def run_preflight(
    manifest: ManifestLike,
    *,
    scan_root: Optional[PathLike] = None,
    cleanup_plan_path: Optional[PathLike] = None,
    protection_roots: Iterable[Any] = (),
    managed_paths: Iterable[PathLike] = (),
    ownership_resolver: OwnershipResolver = unresolved_ownership,
    source_artifact_dir: Optional[PathLike] = None,
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
    source_errors: list[ItemVerdict] = []
    source_dir = Path(os.fspath(source_artifact_dir)) if source_artifact_dir is not None else (
        Path(os.fspath(cleanup_plan_path)).parent if cleanup_plan_path is not None else (
            Path(os.fspath(manifest)).parent if isinstance(manifest, (str, Path)) else None))

    owner_digest = str(data.get("source_owner_action_plan_sha256") or "")
    if items_raw and not _is_sha256_hex(owner_digest):
        source_errors.append(_fail("", ReasonClass.OWNERSHIP_REVISION_DRIFT, "valid source ownership digest required"))
    if owner_digest:
        owner_path = source_dir / "owner-action-plan.json" if source_dir else None
        try:
            if owner_path is None or _sha256_file(owner_path) != owner_digest:
                source_errors.append(_fail("", ReasonClass.OWNERSHIP_REVISION_DRIFT, "source owner-action artifact missing or changed"))
        except OSError:
            source_errors.append(_fail("", ReasonClass.OWNERSHIP_REVISION_DRIFT, "source owner-action artifact unreadable"))
    capacity_digest = str(data.get("source_capacity_strategy_sha256") or "")
    if items_raw and not _is_sha256_hex(capacity_digest):
        source_errors.append(_fail("", ReasonClass.DIGEST_DRIFT, "valid source capacity digest required"))
    if capacity_digest:
        capacity_path = source_dir / "capacity-strategy.json" if source_dir else None
        try:
            if capacity_path is None or _sha256_file(capacity_path) != capacity_digest:
                source_errors.append(_fail("", ReasonClass.DIGEST_DRIFT, "source capacity strategy missing or changed"))
        except OSError:
            source_errors.append(_fail("", ReasonClass.DIGEST_DRIFT, "source capacity strategy unreadable"))

    expected_digest = str(data.get("source_cleanup_plan_sha256") or "").strip()
    plan_path = (
        Path(os.fspath(cleanup_plan_path)) if cleanup_plan_path is not None else None
    )
    plan_exists = plan_path is not None and plan_path.is_file()
    item_declares_plan_digest = any(
        isinstance(raw, Mapping)
        and str(raw.get("source_cleanup_plan_sha256") or "").strip()
        for raw in items_raw
    )
    # Empty top-level digest fails closed when a cleanup plan exists on disk
    # or when any item declares a plan digest (align item-level with top-level).
    if not expected_digest and (plan_exists or item_declares_plan_digest):
        verdicts.append(
            _fail(
                "",
                ReasonClass.DIGEST_DRIFT,
                (
                    "source_cleanup_plan_sha256 is empty but cleanup-plan.csv "
                    "exists or item-level plan digests are present"
                ),
            )
        )
    elif expected_digest:
        # Non-empty digest requires an on-disk cleanup plan; missing is FAIL.
        if cleanup_plan_path is None:
            verdicts.append(
                _fail(
                    "",
                    ReasonClass.CLEANUP_PLAN_MISSING,
                    (
                        "manifest declares source_cleanup_plan_sha256 but "
                        "cleanup-plan.csv path was not provided"
                    ),
                )
            )
        else:
            assert plan_path is not None
            if not plan_path.is_file():
                verdicts.append(
                    _fail(
                        "",
                        ReasonClass.CLEANUP_PLAN_MISSING,
                        f"cleanup plan missing at {plan_path}",
                    )
                )
            else:
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
                    actual_digest.lower() != expected_digest.lower()
                ):
                    verdicts.append(
                        _fail(
                            "",
                            ReasonClass.DIGEST_DRIFT,
                            (
                                "cleanup-plan digest drift: "
                                f"manifest={expected_digest} "
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
        verdict = _check_item(
                raw,
                scan_root=root_path,
                protection=protection,
                managed_paths=managed,
                all_items_by_path=by_path,
            )
        if verdict.verdict == "PASS":
            reason, detail, current_ownership = revalidate_ownership(raw, ownership_resolver)
            if reason:
                verdict = _fail(str(raw.get("item_id") or ""), reason, detail)
            else:
                verdict = replace(verdict, ownership=current_ownership)
        verdicts.append(verdict)

    if items_raw and not source_errors and source_dir is not None:
        try:
            owner_source = json.loads((source_dir / "owner-action-plan.json").read_text(encoding="utf-8"))
            capacity_source = json.loads((source_dir / "capacity-strategy.json").read_text(encoding="utf-8"))
            source_errors.extend(_fail("", reason, detail) for reason, detail in
                                 validate_source_membership(items_raw, owner_source, capacity_source))
        except (OSError, ValueError, UnicodeError):
            source_errors.append(_fail("", "SOURCE_ACTION_INVALID", "source action artifact cannot be decoded"))
    verdicts.extend(source_errors)
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
