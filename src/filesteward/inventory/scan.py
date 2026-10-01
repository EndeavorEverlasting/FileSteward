"""Streaming inventory with fail-closed completeness semantics.

Contract (P04 sections 7/11-14, LOCAL-AGENT-PROTECTIONS section 8):

* never follows symlinks or reparse points into their targets;
* never opens file content (so placeholders are never hydrated);
* unreadable nodes become explicit ``ScanCompleteness.INCOMPLETE``
  evidence — absence is never inferred from a failed read;
* the walk is a generator: bounded memory, one open scandir frame per
  directory of depth, never a materialized ``InventoryItem[]``.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional, Sequence

from filesteward.inventory import windows
from filesteward.models import EntryType, InventoryItem, ScanCompleteness

__all__ = ["ScanDeps", "iter_inventory", "stable_item_id"]


@dataclass(frozen=True)
class ScanDeps:
    """Indirection seam for deterministic tests.

    Only directory enumeration is injectable. There is deliberately no
    content-read capability in this seam.
    """

    scandir: Callable[[str], Any] = os.scandir


def stable_item_id(relative_key: str) -> str:
    """Deterministic per-run item id derived from the root-relative key."""

    return hashlib.sha256(relative_key.encode("utf-8")).hexdigest()[:16]


def _relative_key(path: str, root: str) -> str:
    rel = os.path.relpath(path, root)
    if rel == os.curdir:
        return "."
    return rel.replace(os.sep, "/")


def _close(iterator: Any) -> None:
    closer = getattr(iterator, "close", None)
    if callable(closer):
        closer()


@dataclass
class _Frame:
    path: str
    entry_type: EntryType = EntryType.OTHER
    iterator: Any = None
    state: str = "pending"  # pending -> iterating -> done


def _make_item(
    path: str,
    root: str,
    *,
    entry_type: EntryType,
    st: Any = None,
    symlink: bool = False,
    error: Optional[BaseException] = None,
) -> InventoryItem:
    key = _relative_key(path, root)
    complete = error is None
    logical: Optional[int] = None
    allocated: Optional[int] = None
    modified: Optional[float] = None
    links: Optional[int] = None
    reparse = False
    placeholder = False
    if st is not None:
        logical = int(getattr(st, "st_size", 0) or 0)
        blocks = getattr(st, "st_blocks", None)
        if isinstance(blocks, int) and blocks > 0:
            allocated = blocks * 512
        mtime = getattr(st, "st_mtime", None)
        modified = float(mtime) if mtime is not None else None
        nlink = getattr(st, "st_nlink", None)
        links = int(nlink) if isinstance(nlink, int) and nlink > 0 else None
        if links is None:
            # On Windows, DirEntry.stat(follow_symlinks=False) is built
            # from WIN32_FIND_DATA, which carries no link count, and the
            # API reports st_nlink=0. Zero links is not a real filesystem
            # value, so re-observe it with a no-follow os.stat; when that
            # also fails, record unknown — never a false zero.
            try:
                alt = os.stat(path, follow_symlinks=False)
                alt_nlink = getattr(alt, "st_nlink", None)
                if isinstance(alt_nlink, int) and alt_nlink > 0:
                    links = alt_nlink
            except OSError:
                links = None
        reparse = windows.is_reparse_point(st) or symlink
        placeholder = windows.is_cloud_placeholder(st)
    return InventoryItem(
        item_id=stable_item_id(key),
        path=path,
        entry_type=entry_type,
        logical_size_bytes=logical,
        allocated_size_bytes=allocated,
        modified_at=modified,
        link_count=links,
        scan_completeness=(
            ScanCompleteness.COMPLETE
            if complete
            else ScanCompleteness.INCOMPLETE
        ),
        scan_error=None if complete else f"{type(error).__name__}: {error}",
        is_symlink=symlink,
        is_reparse_point=reparse,
        is_cloud_placeholder=placeholder,
    )


def iter_inventory(
    root: str,
    *,
    deps: Optional[ScanDeps] = None,
    exclude_roots: Optional[Sequence[str]] = None,
) -> Iterator[InventoryItem]:
    """Yield an inventory of ``root`` without following links.

    Order is depth-first, children before parents (post-order), so a
    directory's completeness is known only after its enumeration
    finished. ``root`` is always yielded, even when it cannot be read.

    ``exclude_roots`` are absolute (or abspath-normalized) directory
    prefixes that must not be inventoried or descended into. Used to keep
    the scanner from observing its own runtime output when an ancestor
    volume is scanned.
    """

    deps = deps or ScanDeps()
    root_str = os.fspath(root)
    root_abs = os.path.abspath(root_str)
    excluded = tuple(
        os.path.normcase(os.path.abspath(os.fspath(path)))
        for path in (exclude_roots or ())
    )

    def _is_excluded(path: str) -> bool:
        candidate = os.path.normcase(os.path.abspath(path))
        for prefix in excluded:
            if candidate == prefix:
                return True
            if candidate.startswith(prefix + os.sep):
                return True
        return False

    stack: list[_Frame] = [_Frame(root_abs)]

    while stack:
        frame = stack[-1]

        if frame.state == "pending":
            if frame.path != root_abs and _is_excluded(frame.path):
                # Excluded subtree: do not yield or descend.
                stack.pop()
                continue
            try:
                frame.iterator = deps.scandir(frame.path)
            except OSError as exc:
                yield _make_item(
                    frame.path,
                    root_abs,
                    entry_type=frame.entry_type,
                    error=exc,
                )
                stack.pop()
                continue
            frame.state = "iterating"

        try:
            entry = next(frame.iterator)
        except StopIteration:
            _close(frame.iterator)
            yield _make_item(frame.path, root_abs, entry_type=EntryType.DIRECTORY)
            stack.pop()
            continue
        except OSError as exc:
            _close(frame.iterator)
            yield _make_item(
                frame.path, root_abs, entry_type=EntryType.DIRECTORY, error=exc
            )
            stack.pop()
            continue

        entry_path = os.fspath(entry.path)
        if _is_excluded(entry_path):
            continue

        try:
            symlink = bool(entry.is_symlink())
        except OSError as exc:
            yield _make_item(
                entry_path, root_abs, entry_type=EntryType.OTHER, error=exc
            )
            continue

        try:
            st = entry.stat(follow_symlinks=False)
        except OSError as exc:
            yield _make_item(
                entry_path, root_abs, entry_type=EntryType.OTHER, error=exc
            )
            continue

        if symlink:
            yield _make_item(
                entry_path,
                root_abs,
                entry_type=EntryType.SYMLINK,
                st=st,
                symlink=True,
            )
            continue

        if windows.is_reparse_point(st):
            # Junctions, mount points, cloud reparse entries: recorded,
            # never followed.
            yield _make_item(
                entry_path,
                root_abs,
                entry_type=EntryType.REPARSE_POINT,
                st=st,
            )
            continue

        try:
            is_dir = bool(entry.is_dir(follow_symlinks=False))
            is_file = bool(entry.is_file(follow_symlinks=False))
        except OSError as exc:
            # Race / permission change after stat: record incomplete
            # evidence for this entry; do not abort the walk.
            yield _make_item(
                entry_path,
                root_abs,
                entry_type=EntryType.OTHER,
                st=st,
                error=exc,
            )
            continue
        if is_dir:
            stack.append(_Frame(entry_path, entry_type=EntryType.DIRECTORY))
        elif is_file:
            yield _make_item(
                entry_path, root_abs, entry_type=EntryType.FILE, st=st
            )
        else:
            yield _make_item(
                entry_path, root_abs, entry_type=EntryType.OTHER, st=st
            )
