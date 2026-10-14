"""Installed runtime has explicit identity and OS-owned private placement."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from filesteward import __version__
from filesteward import runtime_profile as profile
from filesteward.policy import paths


@pytest.fixture
def frozen_install(monkeypatch, tmp_path):
    known = tmp_path / "KnownFolderLocal"
    known.mkdir()
    transport = tmp_path / "Desktop" / "FileSteward.exe"
    transport.parent.mkdir()
    transport.write_bytes(b"synthetic executable identity")
    monkeypatch.setattr(profile, "windows_local_app_data", lambda: known)
    monkeypatch.setattr(profile, "_is_frozen", lambda: True)
    monkeypatch.setattr(profile, "_frozen_identity", lambda: None)
    monkeypatch.setattr(profile.sys, "executable", str(transport))
    return known, transport


def marker(root, **changes):
    root.mkdir(exist_ok=True)
    document = {"schema_version": "filesteward.application-root/v1",
                "app_id": "filesteward", "runtime_profile": profile.PROFILE_ID}
    document.update(changes)
    (root / profile.APPLICATION_MARKER).write_text(json.dumps(document), encoding="utf-8")


def test_direct_exe_initializes_os_owned_runtime_without_using_transport(frozen_install):
    known, transport = frozen_install
    with pytest.raises(RuntimeError, match="family root"):
        profile.resolve_installed_runtime()
    result = profile.initialize_installed_runtime()
    assert result.application_root == known / "FileSteward"
    assert result.runtime_root == known / "FileSteward/runtime/var"
    assert result.artifact_origin == transport
    assert (result.runtime_root / "runs").is_dir()
    receipt = json.loads((result.runtime_root / "runtime-readiness.json").read_text())
    assert receipt["startup_authority"] == "PRIVATE_RUNTIME_ONLY"
    assert not receipt["scan_started"] and not receipt["deletion_started"] and not receipt["schedule_registered"]
    assert not (transport.parent / "var").exists()
    assert profile.resolve_installed_runtime() == result
    assert profile.initialize_installed_runtime() == result


def test_shared_family_marker_does_not_lock_future_package_version(frozen_install):
    known, _ = frozen_install
    marker(known / "FileSteward", created_version="0.1.0")
    result = profile.initialize_installed_runtime()
    assert result.package_version == __version__
    assert json.loads((result.application_root / profile.APPLICATION_MARKER).read_text())["created_version"] == "0.1.0"


@pytest.mark.parametrize("changes", [{"app_id": "another-app"}, {"schema_version": "wrong"},
                                    {"runtime_profile": "unknown-profile"}])
def test_existing_marker_mismatch_refuses_without_creating_runtime(frozen_install, changes):
    known, _ = frozen_install
    marker(known / "FileSteward", **changes)
    with pytest.raises(RuntimeError, match="marker identity"):
        profile.initialize_installed_runtime()
    assert not (known / "FileSteward/runtime").exists()


def test_unknown_existing_application_root_is_not_adopted(frozen_install):
    known, _ = frozen_install
    root = known / "FileSteward"
    root.mkdir()
    sentinel = root / "unrelated.txt"
    sentinel.write_text("preserve")
    with pytest.raises(RuntimeError, match="marker"):
        profile.initialize_installed_runtime()
    assert sentinel.read_text() == "preserve"
    assert not (root / profile.APPLICATION_MARKER).exists()


def test_explicit_application_root_cannot_redirect_knownfolder(frozen_install):
    known, _ = frozen_install
    with pytest.raises(RuntimeError, match="KnownFolder family"):
        profile.initialize_installed_runtime(known / "different")
    assert not (known / "different").exists()


def test_cwd_and_environment_variables_cannot_relocate_runtime(frozen_install, monkeypatch, tmp_path):
    known, _ = frozen_install
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    monkeypatch.chdir(foreign)
    monkeypatch.setenv("LOCALAPPDATA", str(foreign))
    monkeypatch.setenv("FILESTEWARD_RUNTIME", str(foreign))
    result = profile.initialize_installed_runtime()
    assert result.runtime_root == known / "FileSteward/runtime/var"
    assert not (foreign / "FileSteward").exists()


def test_failed_knownfolder_admission_has_no_fallback(frozen_install, monkeypatch):
    def fail():
        raise RuntimeError("OS folder unavailable")
    monkeypatch.setattr(profile, "windows_local_app_data", fail)
    with pytest.raises(RuntimeError, match="OS folder unavailable"):
        profile.initialize_installed_runtime()


def test_forbidden_runtime_root_refuses_before_creation(frozen_install, monkeypatch, tmp_path):
    known = tmp_path / "OneDrive" / "Local"
    known.mkdir(parents=True)
    monkeypatch.setattr(profile, "windows_local_app_data", lambda: known)
    with pytest.raises(RuntimeError, match="forbidden"):
        profile.initialize_installed_runtime()
    assert not (known / "FileSteward").exists()


def test_reparse_component_refuses_before_creation(frozen_install, monkeypatch):
    known, _ = frozen_install
    protected_ino = known.stat().st_ino
    monkeypatch.setattr(profile.windows, "is_reparse_point", lambda st: st.st_ino == protected_ino)
    with pytest.raises(RuntimeError, match="symlink/reparse"):
        profile.initialize_installed_runtime()
    assert not (known / "FileSteward").exists()


def test_profile_identity_version_drift_refuses(frozen_install, monkeypatch):
    class BadResource:
        def joinpath(self, *parts):
            return self
        def read_bytes(self):
            return b'{"profile_version":999}'
    monkeypatch.setattr(profile.resources, "files", lambda package: BadResource())
    with pytest.raises(RuntimeError, match="profile identity/version"):
        profile.initialize_installed_runtime()


def test_frozen_build_identity_is_required_and_version_bound(monkeypatch, tmp_path):
    package = tmp_path / "package"
    contract = package / "contracts/build-info.json"
    contract.parent.mkdir(parents=True)
    monkeypatch.setattr(profile.resources, "files", lambda package_name: package)
    with pytest.raises(RuntimeError, match="build identity is unavailable"):
        profile._frozen_identity()
    document = {"schema_version": "filesteward.build-info/v1", "app_id": "filesteward",
                "runtime_profile": profile.PROFILE_ID, "package_version": __version__}
    contract.write_text(json.dumps(document))
    profile._frozen_identity()
    document["package_version"] = "0.0.0"
    contract.write_text(json.dumps(document))
    with pytest.raises(RuntimeError, match="build identity/version"):
        profile._frozen_identity()


def test_wheel_metadata_must_match_actual_import_origin(monkeypatch, tmp_path):
    origin = tmp_path / "installed/filesteward/__init__.py"
    monkeypatch.setattr(profile.metadata, "distribution", lambda name: SimpleNamespace(
        version=__version__, locate_file=lambda relative: origin))
    profile._wheel_identity(origin)
    with pytest.raises(RuntimeError, match="import-origin"):
        profile._wheel_identity(tmp_path / "different/filesteward/__init__.py")
    monkeypatch.setattr(profile.metadata, "distribution", lambda name: SimpleNamespace(
        version="0.0.0", locate_file=lambda relative: origin))
    with pytest.raises(RuntimeError, match="metadata/version"):
        profile._wheel_identity(origin)


def test_installed_wheel_initializes_same_private_profile(frozen_install, monkeypatch, tmp_path):
    known, _ = frozen_install
    origin = tmp_path / "site-packages/filesteward/__init__.py"
    origin.parent.mkdir(parents=True)
    origin.write_text("synthetic installed wheel")
    monkeypatch.setattr(profile, "_is_frozen", lambda: False)
    monkeypatch.setattr(profile, "_package_file", lambda: origin)
    monkeypatch.setattr(profile.metadata, "distribution", lambda name: SimpleNamespace(
        version=__version__, locate_file=lambda relative: origin))
    result = profile.initialize_installed_runtime()
    assert result.mode == "wheel"
    assert result.runtime_root == known / "FileSteward/runtime/var"
    assert result.artifact_origin == origin


def test_artifact_identity_failure_precedes_any_family_creation(frozen_install, monkeypatch):
    known, _ = frozen_install
    def fail():
        raise RuntimeError("immutable frozen build identity/version mismatch")
    monkeypatch.setattr(profile, "_frozen_identity", fail)
    with pytest.raises(RuntimeError, match="build identity/version"):
        profile.initialize_installed_runtime()
    assert not (known / "FileSteward").exists()


def test_packaged_policy_admits_only_private_runtime_runs(frozen_install, monkeypatch):
    known, _ = frozen_install
    result = profile.initialize_installed_runtime()
    def not_checkout():
        raise RuntimeError("not a checkout")
    monkeypatch.setattr(paths, "repository_root", not_checkout)
    assert paths.runtime_root() == result.runtime_root
    assert paths.run_dir("welcome") == result.runtime_root / "runs/welcome"
    assert paths.resolve_run_dir_argument("var/runs/welcome") == result.runtime_root / "runs/welcome"
    assert paths.prove_run_dir_under_runtime(paths.run_dir("welcome")) == paths.run_dir("welcome")
    with pytest.raises(ValueError, match="runtime tree"):
        paths.prove_run_dir_under_runtime(known / "foreign-run")


def test_source_repository_runtime_contract_is_unchanged():
    assert paths.runtime_root() == paths.repository_root() / "var"
    assert paths.resolve_run_dir_argument("var/runs/demo") == paths.repository_root() / "var/runs/demo"


def test_interrupted_marker_write_never_publishes_an_unmarked_family(frozen_install, monkeypatch):
    known, _ = frozen_install
    def interrupted(*args, **kwargs):
        raise OSError("simulated interrupted marker write")
    monkeypatch.setattr(profile.json, "dump", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        profile.initialize_installed_runtime()
    assert not (known / "FileSteward").exists()
    assert not list(known.glob(".filesteward-startup-*"))
