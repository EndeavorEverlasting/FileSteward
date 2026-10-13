"""Synthetic workstation profile contract and privacy tests."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from filesteward.profiles import (
    ProfileError, SCHEMA, _key, capture, compare_latest, load_latest, observe,
)

def test_host_key_rejects_alias_traversal():
    for value in ("", "../other", "C:\\", ".hidden", "host name", "a/b"):
        with pytest.raises(ProfileError):
            _key(value)

@pytest.mark.parametrize("free,status", [
    (9, "CRITICAL"), (10, "BELOW_TARGET"), (19, "BELOW_TARGET"),
    (20, "AT_OR_ABOVE_TARGET"),
])
def test_healthy_capacity_boundaries(tmp_path, free, status):
    data = observe([str(tmp_path)], sample_seconds=0,
                   disk_usage=lambda _: SimpleNamespace(total=100, used=100-free, free=free),
                   psutil_module=SimpleNamespace(
                       cpu_percent=lambda interval: 12.5,
                       virtual_memory=lambda: SimpleNamespace(total=1024, available=512)))
    assert data["volumes"][0]["capacity_status"] == status
    assert data["volumes"][0]["action_authorization"] == "NONE"
    assert data["metrics"]["memory_total_bytes"] == 1024

def test_capture_append_only_and_binding_rejects_other_host(tmp_path):
    root = tmp_path / "private"
    data = tmp_path / "volume"
    data.mkdir()
    def fake_observer(volumes, *, sample_seconds):
        assert volumes == [str(data)]
        return {"volumes": [], "metrics": {}, "missing_metrics": []}
    first = capture("PTop", [str(data)], profiles_root=root,
                    observer=fake_observer, machine_binding="windows\0ptop")
    before = first.read_bytes()
    second = capture("PTop", [str(data)], profiles_root=root,
                     observer=fake_observer, machine_binding="windows\0ptop")
    assert first != second
    assert first.read_bytes() == before
    assert load_latest("PTop", profiles_root=root)["snapshot_id"] == second.stem
    assert json.loads(first.read_text())["schema_version"] == SCHEMA
    assert load_latest("PTop", profiles_root=root)["authorization_state"] == "OBSERVATION_ONLY"
    assert load_latest("PTop", profiles_root=root)["profile_provides_delete_authority"] is False
    with pytest.raises(ProfileError, match="HOST_BINDING_MISMATCH"):
        capture("PTop", [str(data)], profiles_root=root,
                observer=fake_observer, machine_binding="windows\0other")
    assert len(list((root / "PTop" / "snapshots").glob("*.json"))) == 2

def test_missing_psutil_is_not_fake_zero(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)
    data = observe([str(tmp_path)], sample_seconds=0)
    assert data["metrics"]["cpu_utilization_pct"] is None
    assert data["metrics"]["memory_total_bytes"] is None
    assert any("psutil unavailable" in reason for reason in data["missing_metrics"])

def test_no_file_mutation_or_recursion(tmp_path):
    protected = tmp_path / "app"
    protected.mkdir()
    sentinel = protected / "Update.exe"
    sentinel.write_bytes(b"irreplaceable")
    before = sentinel.read_bytes()
    observe([str(tmp_path)], sample_seconds=0, psutil_module=SimpleNamespace(
        cpu_percent=lambda interval: 0,
        virtual_memory=lambda: SimpleNamespace(total=2048, available=2000)))
    assert sentinel.read_bytes() == before

def test_profile_symlink_refused(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "PTop").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("OS disallows test symlink")
    with pytest.raises(ProfileError, match="symlink"):
        capture("PTop", [str(tmp_path)], profiles_root=root)

def test_unsafe_sample_length_refused(tmp_path):
    with pytest.raises(ProfileError):
        observe([str(tmp_path)], sample_seconds=30)


def test_compare_capacity_trend_only_same_host_same_root(tmp_path):
    root = tmp_path / "history"
    volume = tmp_path / "C"
    volume.mkdir()
    observations = iter([
        {"volumes": [{"declared_root": str(volume), "free_pct": 21.5, "capacity_status": "AT_OR_ABOVE_TARGET"}],
         "metrics": {}, "missing_metrics": []},
        {"volumes": [{"declared_root": str(volume), "free_pct": 18.0, "capacity_status": "BELOW_TARGET"}],
         "metrics": {}, "missing_metrics": []},
    ])
    def synthetic(v, *, sample_seconds):
        return next(observations)
    with pytest.raises(ProfileError, match="two snapshots"):
        capture("test", [str(volume)], profiles_root=root,
                observer=synthetic, machine_binding="linux\0test")
        compare_latest("test", profiles_root=root)
    capture("test", [str(volume)], profiles_root=root,
            observer=synthetic, machine_binding="linux\0test")
    comparison = compare_latest("test", profiles_root=root)
    assert comparison["volumes"][0]["change_free_percentage_points"] == -3.5
    assert comparison["volumes"][0]["current_capacity_status"] == "BELOW_TARGET"
    assert comparison["causal_attribution"] == "NOT_ESTABLISHED"
    assert comparison["authorization_state"] == "OBSERVATION_ONLY"


def test_overlapping_capture_fails_closed_without_mutation(tmp_path):
    base = tmp_path / "profiles"
    directory = base / "PTop"
    directory.mkdir(parents=True)
    lock = directory / ".capture.lock"
    lock.write_text("held", encoding="utf-8")
    with pytest.raises(ProfileError, match="CAPTURE_BUSY"):
        capture("PTop", [str(tmp_path)], profiles_root=base,
                machine_binding="win\0ptop")
    assert lock.read_text(encoding="utf-8") == "held"
    assert not (directory / "identity.json").exists()
    assert not (directory / "snapshots").exists()
