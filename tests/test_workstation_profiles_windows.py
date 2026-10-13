"""F2 Windows physical-to-volume media mapping (synthetic / fail-closed)."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from filesteward.profiles import observe
from filesteward.profiles.windows import (
    drive_letter_for_root,
    normalize_media_type,
    resolve_declared_volumes_media_type,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (3, "HDD"),
        (4, "SSD"),
        (5, "SCM"),
        (0, None),
        (99, None),
        ("SSD", "SSD"),
        ("hdd", "HDD"),
        ("Unspecified", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_normalize_media_type_fail_closed(raw, expected):
    assert normalize_media_type(raw) == expected


def test_drive_letter_for_windows_root():
    assert drive_letter_for_root(r"C:\Users\example") == "C"
    assert drive_letter_for_root(r"d:/data") == "D"
    assert drive_letter_for_root(r"\\server\share") is None


def test_resolve_sets_ssd_when_probe_unambiguous():
    def probe(letter: str):
        assert letter == "C"
        return {"ok": True, "media_type_code": 4}

    media, reason = resolve_declared_volumes_media_type(
        [r"C:\Vol"], probe=probe, platform_name="win32")
    assert media == "SSD"
    assert reason == ""


def test_resolve_fails_closed_when_cim_unavailable():
    def probe(_letter: str):
        return {"ok": False, "reason": "ambiguous_or_missing_physical"}

    media, reason = resolve_declared_volumes_media_type(
        [r"C:\Vol"], probe=probe, platform_name="win32")
    assert media is None
    assert reason == "media_type: ambiguous_or_missing_physical"


def test_resolve_fails_closed_on_unspecified_media_type():
    media, reason = resolve_declared_volumes_media_type(
        [r"C:\Vol"],
        probe=lambda _l: {"ok": True, "media_type_code": 0},
        platform_name="win32",
    )
    assert media is None
    assert "unspecified" in reason


def test_resolve_fails_closed_when_volumes_disagree():
    answers = {"C": 4, "D": 3}

    def probe(letter: str):
        return {"ok": True, "media_type_code": answers[letter]}

    media, reason = resolve_declared_volumes_media_type(
        [r"C:\a", r"D:\b"], probe=probe, platform_name="win32")
    assert media is None
    assert "ambiguous" in reason


def test_resolve_skips_live_cim_on_non_windows_without_probe():
    media, reason = resolve_declared_volumes_media_type(
        [r"C:\Vol"], probe=None, platform_name="linux")
    assert media is None
    assert reason == "media_type: no trusted physical mapping"


def test_observe_wires_stubbed_ssd_without_live_cim(tmp_path, monkeypatch):
    # Synthetic letter so the stub path does not require a live Windows drive.
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C")
    data = observe(
        [str(tmp_path)],
        sample_seconds=0,
        disk_usage=lambda _: SimpleNamespace(total=100, used=50, free=50),
        psutil_module=None,
        windows_media_probe=lambda letter: {"ok": True, "media_type_code": 4},
    )
    assert data["metrics"]["media_type"] == "SSD"
    assert not any(r.startswith("media_type:") for r in data["missing_metrics"])
    assert data["volumes"][0]["action_authorization"] == "NONE"


def test_observe_keeps_null_media_when_probe_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C")
    data = observe(
        [str(tmp_path)],
        sample_seconds=0,
        disk_usage=lambda _: SimpleNamespace(total=100, used=40, free=60),
        psutil_module=None,
        windows_media_probe=lambda _l: {"ok": False, "reason": "cim_probe_nonzero_exit"},
    )
    assert data["metrics"]["media_type"] is None
    assert any("cim_probe_nonzero_exit" in r for r in data["missing_metrics"])


def test_observe_probe_exception_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C")

    def boom(_letter: str):
        raise RuntimeError("no cim")

    data = observe(
        [str(tmp_path)],
        sample_seconds=0,
        disk_usage=lambda _: SimpleNamespace(total=100, used=40, free=60),
        psutil_module=None,
        windows_media_probe=boom,
    )
    assert data["metrics"]["media_type"] is None
    assert any("cim probe error" in r for r in data["missing_metrics"])


@pytest.mark.skipif(sys.platform != "win32", reason="live letter fixture is Windows-only")
def test_observe_default_probe_path_does_not_fabricate_without_evidence(tmp_path):
    """Without injection, media_type stays null or a trusted label — never invented codes."""
    data = observe(
        [str(tmp_path)],
        sample_seconds=0,
        disk_usage=lambda _: SimpleNamespace(total=100, used=40, free=60),
        psutil_module=None,
    )
    media = data["metrics"]["media_type"]
    assert media in (None, "HDD", "SSD", "SCM")
    if media is None:
        assert any(r.startswith("media_type:") for r in data["missing_metrics"])
    else:
        assert not any(r.startswith("media_type:") for r in data["missing_metrics"])
