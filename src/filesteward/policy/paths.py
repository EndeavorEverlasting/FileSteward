"""Deterministic runtime-path policy for generated output.

Contract: repository/worktree/runtime/entry-point path resolution belongs
exclusively to ``docs/agent/CANONICAL-PATHS.md``. This module encodes the
machine-checkable portion of that contract:

* all generated runtime output lives beneath the repository's ignored
  ``var/`` tree — never an arbitrary user path, never a forbidden root;
* path resolution fails closed when the canonical checkout marker cannot
  be proved.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

__all__ = [
    "FORBIDDEN_ROOT_NAMES",
    "RUN_ID_PATTERN",
    "is_under_forbidden_root",
    "repository_root",
    "run_dir",
    "runtime_root",
]

PathLike = Union[str, "Path"]

#: Forbidden roots per docs/agent/CANONICAL-PATHS.md section 6.
FORBIDDEN_ROOT_NAMES = frozenset(
    {"Desktop", "Documents", "OneDrive", "Backups"}
)

#: Run identifiers are single path components; no separators, no traversal.
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _parts_lower(path: Path) -> list[str]:
    return [part.lower() for part in path.parts]


def is_under_forbidden_root(path: PathLike) -> bool:
    """True when any component of ``path`` is a forbidden root name.

    Case-insensitive, matching Windows folder semantics.
    """

    forbidden = {name.lower() for name in FORBIDDEN_ROOT_NAMES}
    return any(part in forbidden for part in _parts_lower(Path(path)))


def repository_root() -> Path:
    """Resolve the repository checkout this package was imported from.

    ``src/filesteward/policy/paths.py`` -> repository root. Resolution is
    proved by the tracked packaging marker; without it the caller gets a
    fail-closed error instead of a plausible-looking substitute path.
    """

    root = Path(__file__).resolve().parents[3]
    marker = root / "pyproject.toml"
    if not marker.is_file():
        raise RuntimeError(
            "canonical checkout marker not found at "
            f"{root}; refusing to resolve runtime paths outside the "
            "repository (see docs/agent/CANONICAL-PATHS.md)"
        )
    return root


def runtime_root() -> Path:
    """Ignored runtime root: ``<repository>/var``.

    Raises ``RuntimeError`` if the resolved root would sit beneath a
    forbidden root (Desktop/Documents/OneDrive/Backups).
    """

    root = repository_root() / "var"
    if is_under_forbidden_root(root):
        raise RuntimeError(
            f"runtime root {root} resolves beneath a forbidden root; STOP"
        )
    return root


def run_dir(run_id: str) -> Path:
    """Per-run runtime directory: ``<repository>/var/runs/<run_id>/``.

    Real inventories, hashes, queues, manifests, and receipts belong here
    and stay ignored. ``run_id`` must be a single safe path component.
    """

    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise ValueError(
            f"invalid run_id {run_id!r}: must match {RUN_ID_PATTERN.pattern}"
        )
    if run_id in {".", ".."}:
        raise ValueError(f"invalid run_id {run_id!r}")
    return runtime_root() / "runs" / run_id
