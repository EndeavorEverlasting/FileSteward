"""Windows-owned folder discovery and explicit native folder selection.

Neither operation scans a folder or grants review/action authority. The caller
must apply canonical scope admission to every returned path before reviewing it.
"""
from __future__ import annotations

from concurrent.futures import Future
import ctypes
import os
from pathlib import Path
import threading
import uuid


DOWNLOADS_FOLDER_ID = "374DE290-123F-4565-9164-39C4925E467B"
_FILE_OPEN_DIALOG = "DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7"
_I_FILE_OPEN_DIALOG = "D57C7288-D4AD-4768-BE02-9D969532D960"
_I_SHELL_ITEM = "43826D1E-E718-42EE-BC55-A1E261C37BFE"
_CANCELLED = 0x800704C7
_PICKER_FLAGS = 0x20 | 0x40 | 0x800 | 0x8 | 0x02000000


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text: str) -> _GUID:
    return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


def _check(result: int, operation: str) -> None:
    if result & 0x80000000:
        raise RuntimeError(f"{operation} failed (HRESULT 0x{result & 0xffffffff:08x})")


def _absolute(text: str) -> Path:
    path = Path(text)
    if not text or not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("Windows folder API did not return an absolute normalized path")
    return path


def _api():
    if os.name != "nt":
        raise RuntimeError("PICKER_UNAVAILABLE: Windows folder APIs require Windows")
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), ctypes.c_uint32,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    shell.SHCreateItemFromParsingName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p,
        ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    shell.SHCreateItemFromParsingName.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes, ole.CoTaskMemFree.restype = [ctypes.c_void_p], None
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = [ctypes.c_void_p, ctypes.c_uint32], ctypes.c_long
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.c_long
    user.GetProcessWindowStation.argtypes, user.GetProcessWindowStation.restype = [], ctypes.c_void_p
    user.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    user.GetUserObjectInformationW.restype = ctypes.c_int
    user.OpenInputDesktop.argtypes, user.OpenInputDesktop.restype = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32], ctypes.c_void_p
    user.GetThreadDesktop.argtypes, user.GetThreadDesktop.restype = [ctypes.c_uint32], ctypes.c_void_p
    user.CloseDesktop.argtypes, user.CloseDesktop.restype = [ctypes.c_void_p], ctypes.c_int
    return shell, ole, user


def windows_downloads_known_folder() -> Path:
    """Resolve current OS Downloads registration, without guessing or traversal."""
    shell, ole, _ = _api()
    folder, buffer = _guid(DOWNLOADS_FOLDER_ID), ctypes.c_void_p()
    try:
        result = shell.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(buffer))
        _check(result, "Downloads KnownFolder resolution")
        if not buffer.value:
            raise RuntimeError("Downloads KnownFolder resolution returned no path")
        return _absolute(ctypes.wstring_at(buffer.value))
    finally:
        if buffer.value:
            ole.CoTaskMemFree(buffer)


def _interactive(user) -> bool:
    class Flags(ctypes.Structure):
        _fields_ = [("inherit", ctypes.c_int), ("reserved", ctypes.c_int), ("flags", ctypes.c_uint32)]
    station = user.GetProcessWindowStation()
    flags, length = Flags(), ctypes.c_uint32()
    if not (station and user.GetUserObjectInformationW(station, 1, ctypes.byref(flags),
            ctypes.sizeof(flags), ctypes.byref(length)) and flags.flags & 1):
        return False
    desktop = user.OpenInputDesktop(0, False, 1)
    if not desktop:
        return False
    try:
        active, current = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
        own = user.GetThreadDesktop(threading.get_native_id())
        return bool(own and user.GetUserObjectInformationW(desktop, 2, active, ctypes.sizeof(active), ctypes.byref(length))
            and user.GetUserObjectInformationW(own, 2, current, ctypes.sizeof(current), ctypes.byref(length))
            and active.value and active.value == current.value)
    finally:
        user.CloseDesktop(desktop)


def _call(pointer, index: int, result_type, argument_types=()):
    """IUnknown-derived ABI, using stdcall and pointer-width-safe handles."""
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(result_type, ctypes.c_void_p, *argument_types)(vtable[index])


def _release(pointer) -> None:
    if pointer.value:
        _call(pointer, 2, ctypes.c_uint32)(pointer)


def _pick_sta(initial_folder: Path | None = None) -> Path | None:
    """Internal STA implementation; optional synthetic start is for native proof."""
    shell, ole, user = _api()
    if not _interactive(user):
        raise RuntimeError("NO_INTERACTIVE_DESKTOP: Folder selection requires an interactive Windows desktop")
    initialized = False
    dialog, item, initial, name = (ctypes.c_void_p() for _ in range(4))
    try:
        _check(ole.CoInitializeEx(None, 2 | 4), "PICKER_UNAVAILABLE: STA initialization")
        initialized = True
        clsid, iid = _guid(_FILE_OPEN_DIALOG), _guid(_I_FILE_OPEN_DIALOG)
        _check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(dialog)),
               "PICKER_UNAVAILABLE: Folder dialog creation")
        if not dialog.value:
            raise RuntimeError("PICKER_UNAVAILABLE: Folder dialog returned no interface")
        options = ctypes.c_uint32()
        _check(_call(dialog, 10, ctypes.c_long, (ctypes.POINTER(ctypes.c_uint32),))(dialog, ctypes.byref(options)),
               "PICKER_UNAVAILABLE: Read folder dialog options")
        _check(_call(dialog, 9, ctypes.c_long, (ctypes.c_uint32,))(dialog, options.value | _PICKER_FLAGS),
               "PICKER_UNAVAILABLE: Configure folder dialog")
        _check(_call(dialog, 17, ctypes.c_long, (ctypes.c_wchar_p,))(dialog, "FileSteward — Choose a folder"),
               "PICKER_UNAVAILABLE: Set folder dialog title")
        if initial_folder is not None:
            start = _absolute(str(initial_folder))
            item_iid = _guid(_I_SHELL_ITEM)
            _check(shell.SHCreateItemFromParsingName(str(start), None, ctypes.byref(item_iid), ctypes.byref(initial)),
                   "PICKER_UNAVAILABLE: Set synthetic initial folder")
            if not initial.value:
                raise RuntimeError("PICKER_UNAVAILABLE: Initial folder returned no interface")
            _check(_call(dialog, 12, ctypes.c_long, (ctypes.c_void_p,))(dialog, initial),
                   "PICKER_UNAVAILABLE: Set synthetic initial folder")
        shown = _call(dialog, 3, ctypes.c_long, (ctypes.c_void_p,))(dialog, None)
        if shown & 0xffffffff == _CANCELLED:
            return None
        _check(shown, "PICKER_UNAVAILABLE: Show folder dialog")
        _check(_call(dialog, 20, ctypes.c_long, (ctypes.POINTER(ctypes.c_void_p),))(dialog, ctypes.byref(item)),
               "PICKER_UNAVAILABLE: Read selected folder")
        if not item.value:
            raise RuntimeError("PICKER_UNAVAILABLE: Selection returned no folder interface")
        _check(_call(item, 5, ctypes.c_long, (ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)))(
            item, 0x80058000, ctypes.byref(name)), "PICKER_UNAVAILABLE: Read filesystem folder path")
        if not name.value:
            raise RuntimeError("PICKER_UNAVAILABLE: Selection returned no filesystem path")
        return _absolute(ctypes.wstring_at(name.value))
    finally:
        if name.value:
            ole.CoTaskMemFree(name)
        _release(item)
        _release(initial)
        _release(dialog)
        if initialized:
            ole.CoUninitialize()


def pick_windows_folder() -> Path | None:
    """Show an actual native directory dialog on a dedicated STA thread.

    Cancellation returns None. Unsupported/noninteractive/native failures raise;
    no environment/path fallback, browser file input, scan or content read occurs.
    The caller must reserve one picker without holding its UI service lock.
    """
    if os.name != "nt":
        raise RuntimeError("PICKER_UNAVAILABLE: Native folder selection requires Windows")
    result: Future = Future()
    def work():
        try:
            result.set_result(_pick_sta())
        except Exception as exc:
            result.set_exception(exc)
    threading.Thread(target=work, name="FileSteward-folder-picker-STA", daemon=True).start()
    return result.result()
