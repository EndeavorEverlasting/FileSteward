"""F5 adversarial safety corpus for workstation performance profiles.

Mechanical floor: profiles and projections stay observation-only. Capacity
CRITICAL/BELOW_TARGET never promote reclaim. Fixtures are synthetic only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from filesteward.profiles import (
    ProfileError,
    SCHEMA,
    capture,
    compare_latest,
    load_latest,
    main as profile_main,
    observe,
)
from filesteward.profiles.windows import resolve_declared_volumes_media_type
from filesteward.visualization.performance import (
    ProjectionError,
    project_history,
    render_plain_text,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPO_ROOT / "harness" / "evals" / "workstation-performance-safety.v1.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

FORBIDDEN_AUTHORITY_KEYS = set(CORPUS["forbidden_authority_keys"])
FORBIDDEN_SCHEDULER_TOKENS = {t.casefold() for t in CORPUS["forbidden_scheduler_tokens"]}
ALLOWED_PROFILE_CLI = set(CORPUS["allowed_profile_cli_commands"])

# Synthetic aliases only — never real workstation names from live captures.
SYN_ALIAS = "SynthHost"
SYN_BINDING = "test\0synth-host"


def _usage(total: int, free: int) -> SimpleNamespace:
    return SimpleNamespace(total=total, used=total - free, free=free)


def _psutil_ok() -> SimpleNamespace:
    return SimpleNamespace(
        cpu_percent=lambda interval: 11.0,
        virtual_memory=lambda: SimpleNamespace(total=4096, available=2048),
    )


def _observer_from_status(volume: Path, free: int, total: int = 100):
    """Build an observe-compatible result via real observe() with injectables."""

    def run(volumes, *, sample_seconds=0):
        return observe(
            volumes,
            sample_seconds=sample_seconds,
            disk_usage=lambda _: _usage(total, free),
            psutil_module=_psutil_ok(),
            windows_media_probe=lambda _l: {"ok": False, "reason": "synthetic_no_cim"},
        )

    return run


def _assert_no_authority_payload(obj: object, *, path: str = "$") -> None:
    """Refuse any deletion-manifest / approval authority keys recursively."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_cf = str(key).casefold()
            assert key not in FORBIDDEN_AUTHORITY_KEYS, f"forbidden key at {path}.{key}"
            assert key_cf not in {
                "approved_for_action",
                "deletion_manifest_id",
                "operator_approval_artifact",
            }, f"forbidden authority key at {path}.{key}"
            if key_cf in {"authorization_state"}:
                assert value in (None, "OBSERVATION_ONLY"), (
                    f"non-observation authorization at {path}.{key}={value!r}"
                )
            if key_cf == "profile_provides_delete_authority":
                assert value is False
            if key_cf == "action_authorization":
                assert value == "NONE"
            if key_cf in {"reclaim_or_action_state", "reclaim_authority"}:
                assert value is None
            _assert_no_authority_payload(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_authority_payload(item, path=f"{path}[{i}]")


def _assert_observation_only_snapshot(snap: dict) -> None:
    assert snap["schema_version"] == SCHEMA
    assert snap["authorization_state"] == "OBSERVATION_ONLY"
    assert snap["profile_provides_delete_authority"] is False
    for row in snap.get("observation", {}).get("volumes", []):
        assert row["action_authorization"] == "NONE"
    _assert_no_authority_payload(snap)


# ---------------------------------------------------------------------------
# Harness corpus wiring
# ---------------------------------------------------------------------------


def test_safety_corpus_contract_present():
    assert CORPUS["schema_version"] == "filesteward.workstation-performance-safety/v1"
    assert len(CORPUS["expected_global_invariants"]) >= 8
    ids = {c["id"] for c in CORPUS["cases"]}
    required = {
        "CAP-HEALTHY",
        "CAP-LOW",
        "CAP-CRITICAL",
        "MEDIA-SSD",
        "MEDIA-HDD",
        "MEDIA-AMBIGUOUS",
        "CIM-PERMISSIONS",
        "HOST-RENAME",
        "SNAPSHOT-CORRUPT",
        "CAPTURE-LOCK",
        "SCHEDULER-STUB",
        "PARTIAL-FAILURE",
        "REPARSE-REDIRECT",
        "PROTECTED-UNDER-CRITICAL",
        "FIXTURE-PRIVACY",
    }
    assert required <= ids
    assert ALLOWED_PROFILE_CLI == {"capture", "show", "compare"}
    assert "scan" in FORBIDDEN_SCHEDULER_TOKENS
    assert "delete" in FORBIDDEN_SCHEDULER_TOKENS


# ---------------------------------------------------------------------------
# Capacity visibility — never reclaim promotion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "free,status,case_id",
    [
        (25, "AT_OR_ABOVE_TARGET", "CAP-HEALTHY"),
        (15, "BELOW_TARGET", "CAP-LOW"),
        (5, "CRITICAL", "CAP-CRITICAL"),
    ],
)
def test_capacity_statuses_remain_visibility_only(tmp_path, free, status, case_id):
    assert any(c["id"] == case_id for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    data = observe(
        [str(volume)],
        sample_seconds=0,
        disk_usage=lambda _: _usage(100, free),
        psutil_module=_psutil_ok(),
        windows_media_probe=lambda _l: {"ok": False, "reason": "synthetic"},
    )
    row = data["volumes"][0]
    assert row["capacity_status"] == status
    assert row["action_authorization"] == "NONE"
    assert row["free_pct"] == float(free)

    root = tmp_path / "profiles"
    snap_path = capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, free),
        machine_binding=SYN_BINDING,
    )
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    _assert_observation_only_snapshot(snap)
    latest = load_latest(SYN_ALIAS, profiles_root=root)
    _assert_observation_only_snapshot(latest)

    # Second snapshot enables projection under CRITICAL/BELOW without promotion.
    capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, max(1, free - 1)),
        machine_binding=SYN_BINDING,
    )
    projection = project_history(SYN_ALIAS, profiles_root=root)
    assert projection["authorization_state"] == "OBSERVATION_ONLY"
    assert projection["profile_provides_delete_authority"] is False
    assert projection["decision_support"]["delete_authority"] is False
    assert projection["decision_support"]["capacity_statuses_are_actionable"] is False
    for prow in projection["volumes"]:
        assert prow["capacity_status_role"] == "VISIBILITY_ONLY"
        assert prow["reclaim_or_action_state"] is None
        assert prow["action_authorization"] == "NONE"
    text = render_plain_text(projection)
    assert "RECLAIM" not in text
    assert "APPROVED" not in text
    _assert_no_authority_payload(projection)


def test_critical_never_overrides_protected_boundary(tmp_path):
    """Capacity pressure must not emit reclaim/delete authority (ownership boundary)."""
    assert any(c["id"] == "PROTECTED-UNDER-CRITICAL" for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    # Synthetic "protected" sentinel — profile must not mutate or authorize reclaim.
    protected = volume / "Update.exe"
    protected.write_bytes(b"synthetic-app-serviceability")
    before = protected.read_bytes()

    data = observe(
        [str(volume)],
        sample_seconds=0,
        disk_usage=lambda _: _usage(100, 3),
        psutil_module=_psutil_ok(),
    )
    assert data["volumes"][0]["capacity_status"] == "CRITICAL"
    assert data["volumes"][0]["action_authorization"] == "NONE"
    assert protected.read_bytes() == before

    root = tmp_path / "profiles"
    capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, 3),
        machine_binding=SYN_BINDING,
    )
    snap = load_latest(SYN_ALIAS, profiles_root=root)
    _assert_observation_only_snapshot(snap)
    blob = json.dumps(snap)
    for token in ("RECLAIM_PROVEN", "APPROVED_FOR_ACTION", "deletion_manifest"):
        assert token not in blob
    assert protected.read_bytes() == before


# ---------------------------------------------------------------------------
# Media / CIM fail-closed
# ---------------------------------------------------------------------------


def test_media_ssd_and_hdd_never_grant_action(tmp_path, monkeypatch):
    volume = tmp_path / "vol"
    volume.mkdir()
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C"
    )
    for code, label, case_id in ((4, "SSD", "MEDIA-SSD"), (3, "HDD", "MEDIA-HDD")):
        assert any(c["id"] == case_id for c in CORPUS["cases"])
        data = observe(
            [str(volume)],
            sample_seconds=0,
            disk_usage=lambda _: _usage(100, 40),
            psutil_module=None,
            windows_media_probe=lambda _l, c=code: {"ok": True, "media_type_code": c},
        )
        assert data["metrics"]["media_type"] == label
        assert data["volumes"][0]["action_authorization"] == "NONE"
        _assert_no_authority_payload(data)


def test_ambiguous_media_stays_null(tmp_path, monkeypatch):
    assert any(c["id"] == "MEDIA-AMBIGUOUS" for c in CORPUS["cases"])
    answers = {"C": 4, "D": 3}
    media, reason = resolve_declared_volumes_media_type(
        [r"C:\a", r"D:\b"],
        probe=lambda letter: {"ok": True, "media_type_code": answers[letter]},
        platform_name="win32",
    )
    assert media is None
    assert "ambiguous" in reason

    volume = tmp_path / "vol"
    volume.mkdir()
    # observe() maps one declared root; inject disagreeing probe via resolve path
    # by stubbing letter then failing probe — media stays null, never zero.
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C"
    )
    data = observe(
        [str(volume)],
        sample_seconds=0,
        disk_usage=lambda _: _usage(100, 40),
        psutil_module=None,
        windows_media_probe=lambda _l: {"ok": False, "reason": "ambiguous_or_missing_physical"},
    )
    assert data["metrics"]["media_type"] is None
    assert data["metrics"]["device_wear_pct"] is None
    assert data["metrics"]["temperature_c"] is None
    assert data["metrics"]["volume_latency_ms"] is None
    assert any("ambiguous" in r or "media_type" in r for r in data["missing_metrics"])


def test_missing_cim_permissions_do_not_fabricate_zero(tmp_path, monkeypatch):
    assert any(c["id"] == "CIM-PERMISSIONS" for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    monkeypatch.setattr(
        "filesteward.profiles.windows.drive_letter_for_root", lambda _root: "C"
    )
    # Force unavailable collectors: observe(None) would re-import installed psutil.
    denied = SimpleNamespace(
        cpu_percent=lambda interval: (_ for _ in ()).throw(OSError("denied")),
        virtual_memory=lambda: (_ for _ in ()).throw(OSError("denied")),
    )
    data = observe(
        [str(volume)],
        sample_seconds=0,
        disk_usage=lambda _: _usage(100, 40),
        psutil_module=denied,
        windows_media_probe=lambda _l: {
            "ok": False,
            "reason": "cim_access_denied_or_unavailable",
        },
    )
    # Explicit: unavailable metrics stay null — never fabricated as zero.
    for key in (
        "cpu_utilization_pct",
        "memory_total_bytes",
        "memory_available_bytes",
        "volume_latency_ms",
        "device_wear_pct",
        "temperature_c",
        "media_type",
    ):
        assert data["metrics"][key] is None
    assert any("cim_access_denied" in r for r in data["missing_metrics"])


def test_unknown_metrics_stay_null_not_zero(tmp_path, monkeypatch):
    # Match F1 floor: block psutil import so missing stays null (not zero).
    monkeypatch.setitem(sys.modules, "psutil", None)
    data = observe(
        [str(tmp_path)],
        sample_seconds=0,
        disk_usage=lambda _: _usage(100, 50),
    )
    assert data["metrics"]["cpu_utilization_pct"] is None
    assert data["metrics"]["memory_total_bytes"] is None
    assert data["metrics"]["volume_latency_ms"] is None
    assert data["metrics"]["device_wear_pct"] is None
    assert data["metrics"]["temperature_c"] is None
    assert 0 not in (
        data["metrics"]["cpu_utilization_pct"],
        data["metrics"]["memory_total_bytes"],
        data["metrics"]["volume_latency_ms"],
        data["metrics"]["device_wear_pct"],
        data["metrics"]["temperature_c"],
    )
    assert any("psutil unavailable" in reason for reason in data["missing_metrics"])


# ---------------------------------------------------------------------------
# Host binding / corruption / lock / partial failure
# ---------------------------------------------------------------------------


def test_host_rename_alias_collision_refuses(tmp_path):
    assert any(c["id"] == "HOST-RENAME" for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    root = tmp_path / "profiles"
    first = capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, 30),
        machine_binding="windows\0original-host",
    )
    before = list((root / SYN_ALIAS / "snapshots").glob("*.json"))
    assert len(before) == 1
    with pytest.raises(ProfileError, match="HOST_BINDING_MISMATCH"):
        capture(
            SYN_ALIAS,
            [str(volume)],
            profiles_root=root,
            observer=_observer_from_status(volume, 5),
            machine_binding="windows\0renamed-host",
        )
    after = list((root / SYN_ALIAS / "snapshots").glob("*.json"))
    assert after == before
    assert first.read_bytes() == after[0].read_bytes()
    latest = load_latest(SYN_ALIAS, profiles_root=root)
    assert latest["authorization_state"] == "OBSERVATION_ONLY"


def test_corrupted_latest_snapshot_refused(tmp_path):
    assert any(c["id"] == "SNAPSHOT-CORRUPT" for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    root = tmp_path / "profiles"
    capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, 40),
        machine_binding=SYN_BINDING,
    )
    latest = root / SYN_ALIAS / "latest.json"
    latest.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_latest(SYN_ALIAS, profiles_root=root)
    with pytest.raises(ProjectionError):
        project_history(SYN_ALIAS, profiles_root=root)

    # Schema-valid JSON but wrong schema / authority markers.
    latest.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA,
                "alias": SYN_ALIAS,
                "authorization_state": "APPROVED_FOR_ACTION",
                "profile_provides_delete_authority": True,
                "observation": {"volumes": []},
            }
        ),
        encoding="utf-8",
    )
    # load_latest only checks schema+alias; projection must refuse unsafe markers.
    loaded = load_latest(SYN_ALIAS, profiles_root=root)
    assert loaded["profile_provides_delete_authority"] is True  # adversarial fixture
    with pytest.raises(ProjectionError, match="unsafe snapshot authority|observation-only"):
        project_history(SYN_ALIAS, profiles_root=root)


def test_compare_refuses_snapshot_claiming_delete_authority(tmp_path):
    volume = tmp_path / "vol"
    volume.mkdir()
    root = tmp_path / "profiles"
    observations = iter(
        [
            {
                "volumes": [
                    {
                        "declared_root": str(volume),
                        "free_pct": 30.0,
                        "capacity_status": "AT_OR_ABOVE_TARGET",
                        "action_authorization": "NONE",
                    }
                ],
                "metrics": {},
                "missing_metrics": [],
            },
            {
                "volumes": [
                    {
                        "declared_root": str(volume),
                        "free_pct": 8.0,
                        "capacity_status": "CRITICAL",
                        "action_authorization": "NONE",
                    }
                ],
                "metrics": {},
                "missing_metrics": [],
            },
        ]
    )

    def synthetic(volumes, *, sample_seconds):
        return next(observations)

    capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=synthetic,
        machine_binding=SYN_BINDING,
    )
    second = capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=synthetic,
        machine_binding=SYN_BINDING,
    )
    # Tamper second snapshot to claim delete authority.
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["profile_provides_delete_authority"] = True
    second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProfileError, match="unsafe snapshot authority"):
        compare_latest(SYN_ALIAS, profiles_root=root)


def test_concurrent_capture_lock_refuses_without_mutation(tmp_path):
    assert any(c["id"] == "CAPTURE-LOCK" for c in CORPUS["cases"])
    base = tmp_path / "profiles"
    directory = base / SYN_ALIAS
    directory.mkdir(parents=True)
    lock = directory / ".capture.lock"
    lock.write_text("held-by-synthetic-owner", encoding="utf-8")
    with pytest.raises(ProfileError, match="CAPTURE_BUSY"):
        capture(
            SYN_ALIAS,
            [str(tmp_path)],
            profiles_root=base,
            observer=_observer_from_status(tmp_path, 20),
            machine_binding=SYN_BINDING,
        )
    assert lock.read_text(encoding="utf-8") == "held-by-synthetic-owner"
    assert not (directory / "identity.json").exists()
    assert not (directory / "snapshots").exists()
    assert not (directory / "latest.json").exists()


def test_failure_after_one_successful_snapshot_preserves_history(tmp_path):
    assert any(c["id"] == "PARTIAL-FAILURE" for c in CORPUS["cases"])
    volume = tmp_path / "vol"
    volume.mkdir()
    root = tmp_path / "profiles"
    first = capture(
        SYN_ALIAS,
        [str(volume)],
        profiles_root=root,
        observer=_observer_from_status(volume, 35),
        machine_binding=SYN_BINDING,
    )
    first_bytes = first.read_bytes()
    first_payload = json.loads(first_bytes)

    def boom(volumes, *, sample_seconds):
        raise ProfileError("synthetic observer failure after first success")

    with pytest.raises(ProfileError, match="synthetic observer failure"):
        capture(
            SYN_ALIAS,
            [str(volume)],
            profiles_root=root,
            observer=boom,
            machine_binding=SYN_BINDING,
        )
    snaps = sorted((root / SYN_ALIAS / "snapshots").glob("*.json"))
    assert len(snaps) == 1
    assert snaps[0].read_bytes() == first_bytes
    latest = load_latest(SYN_ALIAS, profiles_root=root)
    assert latest["snapshot_id"] == first_payload["snapshot_id"]
    _assert_observation_only_snapshot(latest)
    # Lock must not remain held after failure.
    assert not (root / SYN_ALIAS / ".capture.lock").exists()


# ---------------------------------------------------------------------------
# Symlink / junction / reparse
# ---------------------------------------------------------------------------


def test_profile_symlink_redirect_refused(tmp_path):
    assert any(c["id"] == "REPARSE-REDIRECT" for c in CORPUS["cases"])
    root = tmp_path / "private"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / SYN_ALIAS).symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("OS disallows test symlink")
    with pytest.raises(ProfileError, match="symlink/reparse"):
        capture(
            SYN_ALIAS,
            [str(tmp_path)],
            profiles_root=root,
            observer=_observer_from_status(tmp_path, 20),
            machine_binding=SYN_BINDING,
        )
    assert not (outside / "identity.json").exists()
    assert not (outside / "snapshots").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction fixture")
def test_profile_junction_redirect_refused(tmp_path):
    assert any(c["id"] == "REPARSE-REDIRECT" for c in CORPUS["cases"])
    root = tmp_path / "private"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = root / SYN_ALIAS
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not junction.exists():
        pytest.skip(f"junction fixture unavailable: {completed.stderr}")
    with pytest.raises(ProfileError, match="symlink/reparse"):
        capture(
            SYN_ALIAS,
            [str(tmp_path)],
            profiles_root=root,
            observer=_observer_from_status(tmp_path, 20),
            machine_binding=SYN_BINDING,
        )
    assert not (outside / "identity.json").exists()
    assert not (outside / "snapshots").exists()


# ---------------------------------------------------------------------------
# Scheduler / CLI argv contract (F4 may be absent — stub allowlist)
# ---------------------------------------------------------------------------


def _scheduled_command_allowlist(argv: list[str]) -> None:
    """Stub gate for a future scheduled-capture surface.

    Only observation CLI verbs are allowed. Tokens resembling scan/apply/delete
    (or other mutation/approval verbs from the safety corpus) are refused.
    """
    if not argv:
        raise ProfileError("scheduler stub: empty command")
    verb = argv[0].casefold()
    if verb not in ALLOWED_PROFILE_CLI:
        raise ProfileError(f"scheduler stub: command not allowed: {argv[0]}")
    for token in argv[1:]:
        piece = token.lstrip("-").casefold()
        if piece in FORBIDDEN_SCHEDULER_TOKENS:
            raise ProfileError(f"scheduler stub: forbidden token: {token}")
        # Refuse compound flags like --apply-manifest
        for forbidden in FORBIDDEN_SCHEDULER_TOKENS:
            if forbidden in piece:
                raise ProfileError(f"scheduler stub: forbidden token fragment: {token}")


def test_scheduler_stub_refuses_scan_apply_delete():
    assert any(c["id"] == "SCHEDULER-STUB" for c in CORPUS["cases"])
    # Allowed observation surface.
    _scheduled_command_allowlist(["capture", "--host-key", "SynthHost", "--volume", "C:\\"])
    _scheduled_command_allowlist(["show", "--host-key", "SynthHost"])
    _scheduled_command_allowlist(["compare", "--host-key", "SynthHost"])

    for bad in (
        ["scan"],
        ["apply"],
        ["delete"],
        ["capture", "--apply"],
        ["capture", "--delete"],
        ["show", "--approve"],
        ["compare", "--manifest"],
        ["quarantine"],
        ["capture", "--reclaim"],
    ):
        with pytest.raises(ProfileError, match="scheduler stub"):
            _scheduled_command_allowlist(bad)


def test_public_profile_cli_argv_contract_observation_only():
    """Public profile CLI exposes only capture/show/compare — no scan/apply/delete."""
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    # Mirror production surface by invoking profile_main --help paths via parse failures.
    for name in ALLOWED_PROFILE_CLI:
        commands.add_parser(name)
    # Rebuild from real entrypoint: parse known-good and refuse forbidden.
    with pytest.raises(SystemExit):
        # argparse exits on unknown subcommand when using the real main parser path.
        profile_main(["scan"])
    # Real parser only accepts the three observation commands.
    # Capture without required args fails argparse (SystemExit), not scan path.
    with pytest.raises(SystemExit):
        profile_main(["delete", "--all"])
    with pytest.raises(SystemExit):
        profile_main(["apply"])

    # Inspect production parser choices by constructing equivalent and checking help.
    # Source-level: main only registers capture/show/compare.
    import filesteward.profiles as profiles_mod

    source = Path(profiles_mod.__file__).read_text(encoding="utf-8")
    assert 'add_parser("capture")' in source
    assert 'add_parser("show")' in source
    assert 'add_parser("compare")' in source
    for forbidden in ("scan", "apply", "delete", "quarantine", "approve"):
        assert f'add_parser("{forbidden}")' not in source


# ---------------------------------------------------------------------------
# No deletion-manifest generation / privacy / gitignore
# ---------------------------------------------------------------------------


def test_profile_and_projection_never_emit_manifest_authority(tmp_path):
    volume = tmp_path / "vol"
    volume.mkdir()
    root = tmp_path / "profiles"
    for free in (40, 4):
        capture(
            SYN_ALIAS,
            [str(volume)],
            profiles_root=root,
            observer=_observer_from_status(volume, free),
            machine_binding=SYN_BINDING,
        )
    snap = load_latest(SYN_ALIAS, profiles_root=root)
    comparison = compare_latest(SYN_ALIAS, profiles_root=root)
    projection = project_history(SYN_ALIAS, profiles_root=root)
    for payload in (snap, comparison, projection):
        _assert_no_authority_payload(payload)
        flat = json.dumps(payload).casefold()
        assert "deletion_manifest" not in flat
        assert "approved_for_action" not in flat
        assert "operator_approval" not in flat
    assert comparison["authorization_state"] == "OBSERVATION_ONLY"
    assert projection["volumes"][0]["capacity_status"] == "CRITICAL"
    assert projection["volumes"][0]["reclaim_or_action_state"] is None


def test_fixture_privacy_and_var_gitignored():
    assert any(c["id"] == "FIXTURE-PRIVACY" for c in CORPUS["cases"])
    import re

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"(?m)^var/\s*$", gitignore)

    corpus_text = CORPUS_PATH.read_text(encoding="utf-8")
    self_text = Path(__file__).read_text(encoding="utf-8")
    # No live capture digests or operator path leakage in committed safety fixtures.
    assert not re.search(r"\b[a-f0-9]{64}\b", corpus_text)
    assert "CheeksMcClappeth" not in corpus_text
    assert "Admin Box" not in corpus_text
    assert "PTop" not in corpus_text
    assert SYN_ALIAS == "SynthHost"
    assert "SynthHost" in self_text
    # Corpus documents privacy without embedding device serials.
    assert "serial" not in corpus_text.casefold()
