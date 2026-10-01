"""Git repository/worktree discovery for protection.

Fail-closed bias: a directory that merely *claims* to be a repository
(``.git`` present as directory or file) is treated as one. Over-protection
is safe; missed protection is not.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterator

from filesteward.inventory import windows

__all__ = ["GIT_MARKER", "is_git_repository", "iter_git_roots"]

GIT_MARKER = ".git"


def is_git_repository(path: Any) -> bool:
    """True for repositories (``.git`` directory) and linked worktrees
    (``.git`` file)."""

    try:
        return (Path(os.fspath(path)) / GIT_MARKER).exists()
    except OSError:
        return False


def _close(iterator: Any) -> None:
    closer = getattr(iterator, "close", None)
    if callable(closer):
        closer()


def iter_git_roots(
    root: Any,
    *,
    scandir: Callable[[str], Any] = os.scandir,
    stat: Callable[..., Any] = os.stat,
) -> Iterator[Path]:
    """Stream repository/worktree roots beneath ``root``.

    Does not follow symlinks or reparse points. Does not descend into a
    found repository: everything beneath a protected root is already
    covered by descendant containment.
    """

    stack = [os.path.abspath(os.fspath(root))]
    while stack:
        current = stack.pop()
        if is_git_repository(current):
            yield Path(current)
            continue
        try:
            iterator = scandir(current)
        except OSError:
            # Unreadable directory during discovery: its contents are
            # covered by inventory's explicit UNKNOWN evidence instead.
            continue
        try:
            for entry in iterator:
                try:
                    if entry.is_symlink():
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except (AttributeError, TypeError, OSError):
                        st = stat(os.fspath(entry.path), follow_symlinks=False)
                    if windows.is_reparse_point(st):
                        # Junctions/mount points: never traverse.
                        continue
                except OSError:
                    continue
                stack.append(os.fspath(entry.path))
        except OSError:
            continue
        finally:
            _close(iterator)
