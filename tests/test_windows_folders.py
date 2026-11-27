"""Deterministic native adapter tests; never inspect workstation Downloads."""
import ctypes
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from filesteward import windows_folders as folders


def output(argument, value, kind=ctypes.c_void_p):
    ctypes.cast(argument, ctypes.POINTER(kind))[0] = kind(value)


def known_folder(monkeypatch, text, hresult=0, allocate=True):
    held = ctypes.create_unicode_buffer(text)
    freed, calls = [], []
    def discover(guid, flags, token, pointer):
        calls.append((bytes(ctypes.cast(guid, ctypes.POINTER(folders._GUID)).contents), flags, token))
        if allocate:
            output(pointer, ctypes.addressof(held))
        return hresult
    api = (SimpleNamespace(SHGetKnownFolderPath=discover),
           SimpleNamespace(CoTaskMemFree=lambda pointer: freed.append(pointer.value)), None)
    monkeypatch.setattr(folders, "_api", lambda: api)
    return held, freed, calls


def test_known_folder_uses_downloads_guid_and_relocated_os_result(monkeypatch):
    held, freed, calls = known_folder(monkeypatch, "Z:/Relocated/SyntheticInbox")
    assert folders.windows_downloads_known_folder() == Path("Z:/Relocated/SyntheticInbox")
    assert calls == [(bytes(folders._guid(folders.DOWNLOADS_FOLDER_ID)), 0, None)]
    assert freed == [ctypes.addressof(held)]


@pytest.mark.parametrize("text,hresult,allocate", [
    ("Z:/Synthetic", 0x80070002, True), ("", 0, False), ("relative", 0, True), ("", 0, True),
])
def test_known_folder_errors_never_guess_and_always_free(monkeypatch, text, hresult, allocate):
    held, freed, calls = known_folder(monkeypatch, text, hresult, allocate)
    with pytest.raises(RuntimeError):
        folders.windows_downloads_known_folder()
    assert freed == ([ctypes.addressof(held)] if allocate else [])


@pytest.fixture
def dialog(monkeypatch):
    log = []
    state = dict(show=0, create=0, initialize=0, result=0, display=0,
                 path="Z:/Synthetic/Selected", interactive=True, null_item=False)
    buffers = []
    def initialize(*args):
        log.append(("initialize", threading.get_ident(), args))
        return state["initialize"]
    def create(clsid, outer, context, iid, pointer):
        log.append(("create",))
        output(pointer, 101)
        return state["create"]
    ole = SimpleNamespace(CoInitializeEx=initialize, CoCreateInstance=create,
        CoUninitialize=lambda: log.append(("uninitialize",)),
        CoTaskMemFree=lambda pointer: log.append(("free", pointer.value)))
    monkeypatch.setattr(folders, "_api", lambda: (None, ole, None))
    monkeypatch.setattr(folders, "_interactive", lambda user: state["interactive"])
    def call(pointer, index, result_type, argument_types=()):
        def invoke(this, *args):
            log.append(("method", pointer.value, index))
            if index == 10:
                output(args[0], 0x1000, ctypes.c_uint32)
            if index == 9:
                state["options"] = args[0]
            if index == 3:
                return state["show"]
            if index == 20:
                if not state["null_item"]:
                    output(args[0], 202)
                return state["result"]
            if index == 5:
                held = ctypes.create_unicode_buffer(state["path"])
                buffers.append(held)
                output(args[1], ctypes.addressof(held))
                return state["display"]
            return 0
        return invoke
    monkeypatch.setattr(folders, "_call", call)
    return state, log


def released(log):
    return [row[1] for row in log if row[0] == "method" and row[2] == 2]


def test_picker_selects_on_distinct_sta_and_releases(dialog):
    state, log = dialog
    assert folders.pick_windows_folder() == Path(state["path"])
    initialize = next(row for row in log if row[0] == "initialize")
    assert initialize[1] != threading.get_ident() and initialize[2] == (None, 6)
    assert state["options"] & folders._PICKER_FLAGS == folders._PICKER_FLAGS
    assert released(log) == [202, 101]
    assert sum(row[0] == "free" for row in log) == 1
    assert log[-1] == ("uninitialize",)


def test_picker_cancel_is_none_and_releases(dialog):
    state, log = dialog
    state["show"] = folders._CANCELLED
    assert folders.pick_windows_folder() is None
    assert released(log) == [101]
    assert not any(row[0] == "free" for row in log)
    assert log[-1] == ("uninitialize",)


@pytest.mark.parametrize("failure", ["initialize", "create", "show", "result", "display"])
def test_picker_native_failure_has_bounded_cleanup(dialog, failure):
    state, log = dialog
    state[failure] = 0x80004005
    with pytest.raises(RuntimeError, match="PICKER_UNAVAILABLE"):
        folders.pick_windows_folder()
    if failure == "initialize":
        assert not released(log) and not any(row[0] == "uninitialize" for row in log)
    else:
        assert 101 in released(log) and log[-1] == ("uninitialize",)
    if failure in {"result", "display"}:
        assert 202 in released(log)
    if failure == "display":
        assert any(row[0] == "free" for row in log)


@pytest.mark.parametrize("invalid", ["relative", "", "Z:/Synthetic/../Escape"])
def test_picker_invalid_path_releases(dialog, invalid):
    state, log = dialog
    state["path"] = invalid
    with pytest.raises(RuntimeError, match="absolute normalized"):
        folders.pick_windows_folder()
    assert released(log) == [202, 101] and log[-1] == ("uninitialize",)


def test_picker_noninteractive_fails_before_com(dialog):
    state, log = dialog
    state["interactive"] = False
    with pytest.raises(RuntimeError, match="NO_INTERACTIVE_DESKTOP"):
        folders.pick_windows_folder()
    assert not log


def test_picker_missing_result_interface_is_explicit(dialog):
    state, log = dialog
    state["null_item"] = True
    with pytest.raises(RuntimeError, match="no folder interface"):
        folders.pick_windows_folder()
    assert released(log) == [101]


def test_interactive_station_flags_are_required():
    closed = []
    def query(station, kind, flags, size, length):
        if kind == 1:
            ctypes.cast(flags, ctypes.POINTER(ctypes.c_uint32))[2] = 1
        else:
            flags.value = "SyntheticDesktop"
        return 1
    user = SimpleNamespace(GetProcessWindowStation=lambda: 1, GetUserObjectInformationW=query,
        OpenInputDesktop=lambda *args: 2, GetThreadDesktop=lambda thread: 3, CloseDesktop=lambda handle: closed.append(handle))
    assert folders._interactive(user)
    assert closed == [2]
    user.OpenInputDesktop = lambda *args: 0
    assert not folders._interactive(user)
    user.GetProcessWindowStation = lambda: 0
    assert not folders._interactive(user)


def test_non_windows_has_no_fallback(monkeypatch):
    monkeypatch.setattr(folders, "os", SimpleNamespace(name="posix"))
    with pytest.raises(RuntimeError, match="require Windows"):
        folders.windows_downloads_known_folder()
    with pytest.raises(RuntimeError, match="requires Windows"):
        folders.pick_windows_folder()
