"""Metadata-only discovery of intentional learning-workspace protection roots.

A learning workspace can be valuable user work without a .git directory.
Discovery inspects immediate directory-entry names and types only; it never
reads lesson content, traverses links/reparse points, or authorizes cleanup.

The same discovery is used by scan-time classification and fresh
execute-time protection rediscovery.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from filesteward.inventory import windows
from filesteward.protect.git import is_git_repository

__all__ = ["learning_workspace_stage", "iter_workspace_protection_roots"]

# A MISSION is an intentional curriculum signal, but not sufficient alone.
# Emerging classrooms deserve protection while the remaining files are built.
_MISSION = "mission.md"
_CURRICULUM_FILES = frozenset(
    {"method.md", "guidance.md", "start-here.md", "notes.md"}
)
_CLASSROOM_DIRS = frozenset(
    {"lessons", "learning-records", "upstreams"}
)


def learning_workspace_stage(
    file_names: set[str] | frozenset[str],
    directory_names: set[str] | frozenset[str],
) -> Optional[str]:
    """Classify *entry names*, not teaching content or folder location.

    Confirmed: MISSION plus at least two other curriculum documents, or a
    supporting document and a classroom structure directory.
    Emerging: MISSION plus one supporting document or classroom directory.
    The minimal signal errs toward preserving work under construction.
    """

    files = {name.casefold() for name in file_names}
    folders = {name.casefold() for name in directory_names}
    if _MISSION not in files:
        return None
    supporting = files & _CURRICULUM_FILES
    structural = folders & _CLASSROOM_DIRS
    if len(supporting) >= 2 or (supporting and structural):
        return "confirmed"
    if supporting or structural:
        return "emerging"
    return None


def _close(iterator: Any) -> None:
    close = getattr(iterator, "close", None)
    if callable(close):
        close()


def iter_workspace_protection_roots(
    root: Any,
    *,
    scandir: Callable[[str], Any] = os.scandir,
    stat: Callable[..., Any] = os.stat,
) -> Iterator[tuple[Path, str]]:
    """Discover Git and learning roots with one streaming, no-follow walk.

    A found root excludes its whole subtree from further protection discovery.
    The inventory can still observe its children; only automatic actions are
    excluded. Siblings, including other non-learning folders, remain evaluable.

    Unreadable directories are left to inventory's UNKNOWN completeness gate.
    """

    stack = [os.path.abspath(os.fspath(root))]
    while stack:
        current = stack.pop()
        git_root = is_git_repository(current)
        files: set[str] = set()
        directories: set[str] = set()
        children: list[str] = []
        try:
            iterator = scandir(current)
        except OSError:
            if git_root:
                yield Path(current), "git-repository"
            continue

        try:
            for entry in iterator:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        files.add(entry.name.casefold())
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    try:
                        observed = entry.stat(follow_symlinks=False)
                    except (AttributeError, TypeError, OSError):
                        observed = stat(os.fspath(entry.path), follow_symlinks=False)
                    if windows.is_reparse_point(observed):
                        continue
                    directories.add(entry.name.casefold())
                    if not git_root:
                        children.append(os.fspath(entry.path))
                except OSError:
                    # Never infer that a failed stat is an absent subtree.
                    # Inventory independently records inaccessible entries.
                    continue
        except OSError:
            # The partial read cannot prove a new learning root. Git markers
            # still warrant protection even if directory enumeration fails.
            if git_root:
                yield Path(current), "git-repository"
            continue
        finally:
            _close(iterator)

        stage = learning_workspace_stage(files, directories)
        if git_root and stage:
            yield Path(current), f"git-repository+learning-workspace:{stage}"
        elif git_root:
            yield Path(current), "git-repository"
        elif stage:
            yield Path(current), f"learning-workspace:{stage}"
        else:
            stack.extend(children)
