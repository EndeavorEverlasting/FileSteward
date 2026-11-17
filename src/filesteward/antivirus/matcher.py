"""Bounded SHA-256 scan adapted from SysAdminSuite PR #571."""
from __future__ import annotations

import hashlib
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from filesteward.inventory.windows import is_cloud_placeholder, is_reparse_point

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_SCAN_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 10_000
SCAN_SECONDS = 60
BLOCK_BYTES = 1024 * 1024
OPEN_FLAGS = (os.O_RDONLY | getattr(os, "O_BINARY", 0) |
              getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
LOCAL_LINUX_FILESYSTEMS = frozenset({
    "btrfs", "exfat", "ext2", "ext3", "ext4", "f2fs", "ntfs", "ntfs3",
    "overlay", "ramfs", "tmpfs", "vfat", "xfs", "zfs",
})


def excluded(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or is_reparse_point(info) or is_cloud_placeholder(info)


def regular_file(info: os.stat_result) -> bool:
    return stat.S_ISREG(info.st_mode) and not excluded(info) and info.st_nlink == 1


def checked_directory(path: Path) -> os.stat_result:
    if not path.is_absolute() or ".." in path.parts or path.drive.startswith("\\\\"):
        raise ValueError("Select an absolute local directory")
    if os.name == "nt":
        import ctypes

        drive_type = ctypes.windll.kernel32.GetDriveTypeW
        drive_type.argtypes = (ctypes.c_wchar_p,)
        drive_type.restype = ctypes.c_uint
        if drive_type(path.anchor) not in (2, 3, 5, 6):
            raise ValueError("Select a local volume")
    for directory in (*reversed(path.parents), path):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or excluded(info):
            raise ValueError("Select an ordinary directory")
    return info


def linux_mount_id(fd: int) -> str:
    for line in Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines():
        if line.startswith("mnt_id:"):
            return line.split()[1]
    raise ValueError("Mount identity is unavailable")


@contextmanager
def open_directory(path: Path):
    """Pin a Linux directory without following links in any component."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Select an absolute local directory")
    if os.name == "nt":
        yield None, checked_directory(path)
        return
    if path.anchor != "/" or not Path("/proc/self/mountinfo").is_file():
        raise ValueError("Detection supports native Linux and Windows")
    flags = OPEN_FLAGS | os.O_DIRECTORY
    fd = os.open(path.anchor, flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        mount_id = linux_mount_id(fd)
        for line in Path("/proc/self/mountinfo").read_text(errors="replace").splitlines():
            metadata, _, filesystem = line.partition(" - ")
            if metadata.split()[0] == mount_id and filesystem.split()[0] in LOCAL_LINUX_FILESYSTEMS:
                break
        else:
            raise ValueError("Scope is outside supported local filesystems")
        yield fd, os.fstat(fd)
    finally:
        os.close(fd)


def scope_identity(path: Path) -> tuple[int, int]:
    if path == Path(path.anchor):
        raise ValueError("Select a subdirectory for scanning")
    with open_directory(path) as (_, info):
        return identity(info)


def identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def snapshot(info: os.stat_result) -> tuple[int, ...]:
    return (*identity(info), info.st_mode, info.st_nlink, info.st_size, info.st_mtime_ns)


def same_opened_file(before: os.stat_result, opened: os.stat_result) -> bool:
    # Cross-API NTFS ctime can differ even for the same file. Compare ctime
    # again below using two samples from the same open handle.
    return snapshot(before) == snapshot(opened) and (
        os.name == "nt" or before.st_ctime_ns == opened.st_ctime_ns
    )


def same_directory(before: os.stat_result, after: os.stat_result) -> bool:
    return snapshot(before) == snapshot(after) and before.st_ctime_ns == after.st_ctime_ns


def open_readonly(path: Path | str, dir_fd: int | None = None):
    if os.name != "nt":
        return os.fdopen(os.open(path, OPEN_FLAGS, dir_fd=dir_fd), "rb", buffering=0)
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    # GENERIC_READ, share read/write/delete, OPEN_EXISTING,
    # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_OPEN_NO_RECALL.
    handle = create(str(path), 0x80000000, 7, None, 3, 0x00300000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        close(handle)
        raise
    return os.fdopen(descriptor, "rb", buffering=0)


def digest_file(entry: os.DirEntry, before: os.stat_result, scope: Path,
                scope_identity: tuple[int, int], root_fd: int | None,
                root_mount: str | None, deadline: float) -> str:
    if root_fd is None and identity(checked_directory(scope)) != scope_identity:
        raise ValueError("Scan scope changed")
    with open_readonly(entry.name if root_fd is not None else scope / entry.name, root_fd) as stream:
        opened = os.fstat(stream.fileno())
        if root_mount is not None and linux_mount_id(stream.fileno()) != root_mount:
            raise ValueError("File crosses the approved mount")
        if not regular_file(opened) or not same_opened_file(before, opened):
            raise ValueError("File changed before scan")
        if root_fd is None and identity(checked_directory(scope)) != scope_identity:
            raise ValueError("Scan scope changed")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            if time.monotonic() >= deadline:
                raise ValueError("Scan time budget exhausted")
            block = stream.read(min(BLOCK_BYTES, remaining))
            if not block:
                raise ValueError("File changed during scan")
            digest.update(block)
            remaining -= len(block)
        # Size alone is insufficient for pseudo-files and live mutations.
        if stream.read(1):
            raise ValueError("File exceeds its recorded size")
        after = os.fstat(stream.fileno())
        if snapshot(after) != snapshot(opened) or after.st_ctime_ns != opened.st_ctime_ns:
            raise ValueError("File changed during scan")
        located = os.stat(entry.name if root_fd is not None else scope / entry.name,
                          dir_fd=root_fd, follow_symlinks=False)
        if not regular_file(located) or not same_opened_file(located, after):
            raise ValueError("File moved during scan")
        if root_fd is None and identity(checked_directory(scope)) != scope_identity:
            raise ValueError("Scan scope changed")
        return digest.hexdigest()


def scan_directory(
    scope: Path, expected_root: tuple[int, int], signatures: frozenset[str]
) -> tuple[list[tuple[str, str]], bool]:
    """Return observed (filename, digest) matches and whether coverage was complete."""
    findings: list[tuple[str, str]] = []
    complete = True
    spent = 0
    deadline = time.monotonic() + SCAN_SECONDS
    try:
        with open_directory(scope) as (root_fd, scope_info):
            if identity(scope_info) != expected_root:
                return findings, False
            root_mount = linux_mount_id(root_fd) if root_fd is not None else None
            with os.scandir(root_fd if root_fd is not None else scope) as listing:
                for index, entry in enumerate(listing):
                    if index >= MAX_ENTRIES or time.monotonic() >= deadline:
                        complete = False
                        break
                    try:
                        # Windows DirEntry.stat omits device and inode identity.
                        location = entry.name if root_fd is not None else scope / entry.name
                        info = os.stat(location, dir_fd=root_fd, follow_symlinks=False)
                        if excluded(info) or stat.S_ISDIR(info.st_mode):
                            continue
                        if (not regular_file(info) or info.st_dev != scope_info.st_dev or
                                info.st_size > MAX_FILE_BYTES or info.st_size + 1 > MAX_SCAN_BYTES - spent):
                            complete = False
                            continue
                        spent += info.st_size + 1
                        digest = digest_file(entry, info, scope, expected_root, root_fd,
                                             root_mount, deadline)
                        if digest in signatures:
                            findings.append((entry.name, digest))
                    except (OSError, ValueError):
                        complete = False
            with open_directory(scope) as (_, current):
                if identity(current) != expected_root:
                    return [], False
                complete = complete and same_directory(scope_info, current)
    except (OSError, ValueError):
        return [], False
    return findings, complete
