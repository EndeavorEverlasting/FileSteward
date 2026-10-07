"""Object-bound Windows deletion; unsupported protocols never use path deletion.

CreateFileW sharing pins ancestors and the target through validation. Deletion
uses the validated handle, not a second pathname lookup. API contract:
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
"""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator

from filesteward.inventory import windows

SUPPORTED = os.name == "nt"


class AtomicDeleteUnavailable(OSError):
    """No proven object-bound deletion protocol exists on this platform."""


@contextmanager
def bound_delete_target(path: Path) -> Iterator["WindowsDeleteTarget"]:
    if not SUPPORTED:
        raise AtomicDeleteUnavailable("object-bound permanent deletion requires the Windows handle adapter")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                             ctypes.c_void_p, wintypes.DWORD]
    api.SetFileInformationByHandle.restype = wintypes.BOOL

    def open_fd(target: Path, access: int, sharing: int) -> int:
        # OPEN_EXISTING; OPEN_REPARSE_POINT | BACKUP_SEMANTICS. No hydration
        # or write is requested. Preflight already excludes cloud placeholders.
        handle = api.CreateFileW(str(target), access, sharing, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            api.CloseHandle(handle)
            raise

    with ExitStack() as stack:
        # FILE_READ_ATTRIBUTES, share READ|WRITE but never DELETE: ancestor
        # names cannot be renamed/replaced while the target is being checked.
        for parent in reversed(path.absolute().parents):
            fd = open_fd(parent, 0x80, 3)
            stack.callback(os.close, fd)
            opened, named = os.fstat(fd), os.lstat(parent)
            if not opened.st_ino or not named.st_ino:
                raise AtomicDeleteUnavailable("ancestor file object identity unavailable")
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino) or not stat.S_ISDIR(opened.st_mode) or windows.is_reparse_point(named):
                raise OSError("refuse unbound or reparse ancestor")
        # GENERIC_READ|DELETE, share READ only. Sharing/access failures are
        # terminal refusal; there is deliberately no os.unlink/rmdir fallback.
        fd = open_fd(path, 0x80010000, 1)
        stack.callback(os.close, fd)
        if not os.fstat(fd).st_ino:
            raise AtomicDeleteUnavailable("target file object identity unavailable")
        yield WindowsDeleteTarget(fd, api, msvcrt, ctypes)


class WindowsDeleteTarget:
    def __init__(self, fd, api, msvcrt, ctypes):
        self.fd, self.api, self.msvcrt, self.ctypes = fd, api, msvcrt, ctypes

    def delete(self) -> None:
        # FILE_DISPOSITION_INFO is a one-byte BOOLEAN, not a Win32 BOOL.
        disposition = self.ctypes.c_ubyte(1)
        if not self.api.SetFileInformationByHandle(self.msvcrt.get_osfhandle(self.fd), 4,
                                                  self.ctypes.byref(disposition), 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
