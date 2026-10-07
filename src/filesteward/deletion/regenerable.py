"""Explicit regenerable-cache roots eligible for permanent-delete execute.

Personal / semantic home trees stay refused. Only named regenerable cache
prefixes (plus the process temp root) may use size+mtime identity sealing
instead of full-file SHA-256 at preflight.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Sequence

from filesteward.policy.paths import is_lexically_within, normalize_declared_path

__all__ = [
    "allows_size_mtime_identity_seal",
    "is_under_protected_package_cache",
    "is_under_regenerable_cache_allowlist",
    "regenerable_cache_allowlist_roots",
]


def regenerable_cache_allowlist_roots() -> list[Path]:
    """Return normalized absolute allowlisted regenerable-cache roots.

    Roots that do not exist yet are still listed so execute admission can
    match a freshly created contract path. Callers must still refuse any
    scan root that is merely an ancestor of these prefixes.
    """

    local = os.environ.get("LOCALAPPDATA", "").strip()
    roots: list[Path] = []
    if local:
        local_root = Path(local)
        roots.extend(
            [
                local_root / "npm-cache",
                local_root / "ms-playwright",
                local_root / "CrashDumps",
                local_root / "pip" / "Cache",
                local_root
                / "Google"
                / "Chrome"
                / "User Data"
                / "Default"
                / "Cache",
                local_root
                / "Google"
                / "Chrome"
                / "User Data"
                / "Default"
                / "Code Cache",
            ]
        )
    return [normalize_declared_path(p) for p in roots]


def _protected_package_cache_root() -> Path:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData").strip()
    return normalize_declared_path(Path(program_data) / "Package Cache")


def _realpath(path: Path) -> Path:
    try:
        return normalize_declared_path(Path(os.path.realpath(os.fspath(path))))
    except OSError:
        return normalize_declared_path(path)


def is_under_protected_package_cache(path: Path) -> bool:
    """True when path is the protected ProgramData Package Cache or below it."""

    candidate = _realpath(path)
    protected_root = _realpath(_protected_package_cache_root())
    return candidate == protected_root or is_lexically_within(candidate, protected_root)


def is_under_regenerable_cache_allowlist(
    path: Path,
    *,
    allowlist: Optional[Sequence[Path]] = None,
) -> bool:
    """True when ``path`` realpath equals or is lexically within an allowlisted root."""

    candidate = _realpath(path)
    roots: Iterable[Path] = (
        allowlist if allowlist is not None else regenerable_cache_allowlist_roots()
    )
    for root in roots:
        root_real = _realpath(root)
        if candidate == root_real or is_lexically_within(candidate, root_real):
            return True
    return False


def allows_size_mtime_identity_seal(
    scan_root: Path,
    *,
    allowlist: Optional[Sequence[Path]] = None,
) -> bool:
    """True when preflight may seal with size+mtime only (no full-file hash).

    Applies to the process temp root and the explicit regenerable-cache
    allowlist. Arbitrary personal roots remain on the full SHA-256 seal path.
    """

    root = normalize_declared_path(scan_root)
    root_real = _realpath(root)
    if is_under_protected_package_cache(root_real):
        return False
    temp_root = normalize_declared_path(tempfile.gettempdir())
    temp_real = _realpath(temp_root)
    if root_real == temp_real or is_lexically_within(root_real, temp_real):
        return True
    return is_under_regenerable_cache_allowlist(root_real, allowlist=allowlist)
