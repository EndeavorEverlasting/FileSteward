"""Deterministic runtime-path policy for generated output.

Contract: repository/worktree/runtime/entry-point path resolution belongs
exclusively to ``docs/agent/CANONICAL-PATHS.md``. This module encodes the
machine-checkable portion of that contract:

* all generated runtime output lives beneath the repository's ignored
  ``var/`` tree — never an arbitrary user path, never a forbidden root;
* path resolution fails closed when the canonical checkout marker cannot
  be proved;
* operator-declared paths normalize to absolute form before comparison;
* run-dir admission resists symlink/junction escape.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Union

from filesteward.inventory import windows

__all__ = [
    "FORBIDDEN_ROOT_NAMES",
    "RUN_ID_PATTERN",
    "admit_canonical_runtime_output",
    "is_lexically_within",
    "is_symlink_or_reparse",
    "is_under_forbidden_root",
    "normalize_declared_path",
    "prove_run_dir_under_runtime",
    "repository_root",
    "resolve_run_dir_argument",
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


def normalize_declared_path(path: PathLike) -> Path:
    """Absolute-normalize an operator-declared path; collapse ``..``.

    Uses ``os.path.abspath`` so parent segments collapse without following
    the final path through a symlink/junction target.
    """

    return Path(os.path.abspath(os.fspath(path)))


def resolve_run_dir_argument(path: PathLike) -> Path:
    """Resolve a CLI ``--run-dir`` against the repository when relative.

    Relative paths are joined to ``repository_root()`` so invocation CWD
    cannot silently relocate runtime output. Absolute paths normalize in
    place (``..`` collapsed).
    """

    candidate = Path(os.fspath(path))
    if not candidate.is_absolute():
        candidate = repository_root() / candidate
    return normalize_declared_path(candidate)


def is_lexically_within(child: PathLike, parent: PathLike) -> bool:
    """True when ``child`` equals ``parent`` or is a lexical descendant."""

    child_path = normalize_declared_path(child)
    parent_path = normalize_declared_path(parent)
    return child_path == parent_path or parent_path in child_path.parents


def is_symlink_or_reparse(path: PathLike) -> bool:
    """True when the path itself is a symlink or Windows reparse point."""

    target = Path(os.fspath(path))
    try:
        if target.is_symlink():
            return True
    except OSError:
        return True
    try:
        st = os.lstat(os.fspath(target))
    except OSError:
        return False
    return windows.is_reparse_point(st)


def _linked_component_escape(
    path: Path, *, required_ancestor: Path
) -> Optional[str]:
    """Return an error if any existing component is a link escape.

    Walks from ``required_ancestor`` down to ``path``. A symlink/reparse
    component whose resolved identity leaves ``required_ancestor`` is
    refused. Missing leaf components are allowed (mkdir later).
    """

    ancestor = normalize_declared_path(required_ancestor)
    current = normalize_declared_path(path)
    if not is_lexically_within(current, ancestor):
        return (
            f"{current} is not lexically beneath required ancestor {ancestor}"
        )

    relative = current.relative_to(ancestor)
    cursor = ancestor
    for part in relative.parts:
        cursor = cursor / part
        if not cursor.exists():
            break
        if is_symlink_or_reparse(cursor):
            try:
                real = Path(os.path.realpath(os.fspath(cursor)))
            except OSError as exc:
                return (
                    f"cannot establish safe identity for linked path "
                    f"{cursor}: {exc}"
                )
            if not is_lexically_within(real, ancestor):
                return (
                    f"linked path {cursor} resolves to {real}, outside "
                    f"required ancestor {ancestor}"
                )
    return None


def prove_run_dir_under_runtime(run_dir_path: PathLike) -> Path:
    """Prove ``run_dir`` is a safe directory beneath canonical ``var/runs``.

    Fail-closed against symlink/junction escape and against paths that are
    not under ``runtime_root()/runs``.
    """

    runtime = normalize_declared_path(runtime_root())
    runs_root = normalize_declared_path(runtime / "runs")
    candidate = normalize_declared_path(run_dir_path)

    if candidate == runtime or not is_lexically_within(candidate, runs_root):
        raise ValueError(
            f"run-dir must live beneath the ignored runtime tree "
            f"{runs_root}; got {candidate}"
        )

    for probe in (runtime, runs_root):
        if probe.exists() and is_symlink_or_reparse(probe):
            raise ValueError(
                f"runtime path component {probe} is a symlink/reparse; "
                "refusing linked runtime root"
            )

    escape = _linked_component_escape(candidate, required_ancestor=runtime)
    if escape:
        raise ValueError(f"run-dir rejected: {escape}")

    if candidate.exists():
        if is_symlink_or_reparse(candidate):
            raise ValueError(
                f"run-dir {candidate} is a symlink/reparse; refusing linked "
                "runtime output directory"
            )
        if not candidate.is_dir():
            raise ValueError(f"run-dir is not a directory: {candidate}")
        try:
            real = Path(os.path.realpath(os.fspath(candidate)))
        except OSError as exc:
            raise ValueError(
                f"cannot establish safe identity for run-dir {candidate}: "
                f"{exc}"
            ) from exc
        if not is_lexically_within(real, runtime):
            raise ValueError(
                f"run-dir {candidate} resolves to {real}, outside runtime "
                f"tree {runtime}"
            )
    return candidate


def admit_canonical_runtime_output(
    run_dir_path: PathLike, scan_root: PathLike
) -> Path:
    """Admit a canonical runtime run-dir that lexically sits under scan root.

    Explicit runtime-output rule (not a general containment exemption):

    * realpath/lexical proof via ``prove_run_dir_under_runtime``;
    * path must be inside ``runtime_root()/runs/``;
    * no symlink/reparse escape on runtime or run-dir components;
    * caller must exclude ``runtime_root()`` from inventory before walk.

    Every other run directory inside the scan namespace remains rejected.
    """

    candidate = prove_run_dir_under_runtime(run_dir_path)
    root = normalize_declared_path(scan_root)
    if not is_lexically_within(candidate, root):
        raise ValueError(
            "canonical runtime-output admission requires the run-dir to "
            f"sit under the scan root; {candidate} is outside {root}"
        )
    return candidate
