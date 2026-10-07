"""Actual Windows handle/protocol falsification using temporary bytes only."""

import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from filesteward.deletion import execute, native


def test_unsupported_protocol_never_mutates(tmp_path, monkeypatch):
    target = tmp_path / "bytes"
    target.write_bytes(b"keep")
    monkeypatch.setattr(native, "SUPPORTED", False)
    with pytest.raises(native.AtomicDeleteUnavailable):
        execute._delete_file(target, {"path": str(target)})
    assert target.read_bytes() == b"keep"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle adapter")
@pytest.mark.parametrize("directory", [False, True])
def test_native_target_rename_is_denied_during_final_probe(tmp_path, directory, monkeypatch):
    target = tmp_path / "artifact"
    if directory:
        target.mkdir()
    else:
        target.write_bytes(b"approved")
    replacement = tmp_path / "replacement"
    blocked = []
    def probe():
        with pytest.raises(PermissionError):
            os.rename(target, replacement)
        blocked.append(True)
    # A path-based fallback would violate this oracle even after a good probe.
    def forbidden(*args, **kwargs):
        raise AssertionError("pathname deletion fallback")
    monkeypatch.setattr(os, "unlink", forbidden)
    monkeypatch.setattr(os, "rmdir", forbidden)
    if directory:
        execute._delete_directory_if_empty(target, dependency_check=probe)
    else:
        execute._delete_file(target, {"path": str(target)}, dependency_check=probe)
    assert blocked == [True]
    assert not target.exists()
    assert not replacement.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle adapter")
def test_native_ancestor_rename_is_denied(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "artifact"
    target.write_bytes(b"approved")
    def probe():
        with pytest.raises(PermissionError):
            parent.rename(tmp_path / "moved")
    execute._delete_file(target, {"path": str(target)}, dependency_check=probe)
    assert parent.exists()
    assert not target.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle adapter")
def test_native_write_and_unlink_are_denied_during_final_probe(tmp_path):
    target = tmp_path / "artifact"
    target.write_bytes(b"approved")
    def probe():
        with pytest.raises(PermissionError):
            target.write_bytes(b"replacement")
        with pytest.raises(PermissionError):
            target.unlink()
    execute._delete_file(target, {"path": str(target)}, dependency_check=probe)
    assert not target.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle adapter")
def test_native_sharing_failure_has_no_path_fallback(tmp_path):
    target = tmp_path / "artifact"
    target.write_bytes(b"keep")
    fd = os.open(target, os.O_RDONLY)
    try:
        with pytest.raises(PermissionError):
            execute._delete_file(target, {"path": str(target)})
    finally:
        os.close(fd)
    assert target.read_bytes() == b"keep"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle adapter")
@pytest.mark.parametrize("directory", [False, True])
def test_native_acquisition_replacement_never_deletes_new_object(tmp_path, monkeypatch, directory):
    target = tmp_path / "artifact"
    target.mkdir() if directory else target.write_bytes(b"same bytes")
    original = tmp_path / "original"
    acquire = execute.bound_delete_target
    @contextmanager
    def replacing(path):
        path.rename(original)
        path.mkdir() if directory else path.write_bytes(b"same bytes")
        with acquire(path) as handle:
            yield handle
    monkeypatch.setattr(execute, "bound_delete_target", replacing)
    with pytest.raises(execute.IdentityDriftError):
        if directory:
            execute._delete_directory_if_empty(target)
        else:
            execute._delete_file(target, {"path": str(target)})
    assert target.exists() and original.exists()
