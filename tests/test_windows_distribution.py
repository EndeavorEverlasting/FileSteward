from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("windows_distribution", ROOT / "scripts/build_windows_distribution.py")
assert SPEC and SPEC.loader
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


def test_output_admission_preserves_existing_proof_and_rejects_escape(tmp_path: Path) -> None:
    candidate = distribution.admit_output(tmp_path, "proof-1")
    candidate.mkdir(parents=True)
    proof = candidate / "proof.txt"
    proof.write_text("retained", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        distribution.admit_output(tmp_path, "proof-1")
    assert proof.read_text(encoding="utf-8") == "retained"
    for label in ("../outside", "C:/outside", ".", "new/sub", ""):
        with pytest.raises(ValueError):
            distribution.admit_output(tmp_path, label)


def test_public_build_refuses_dirty_source_before_creating_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(distribution.sys, "platform", "win32")
    monkeypatch.setattr(distribution.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(distribution, "git", lambda *args, **kwargs: " M src/filesteward/launch.py")
    with pytest.raises(ValueError, match="clean source HEAD"):
        distribution.build("must-not-exist", root=tmp_path)
    assert not (tmp_path / "var").exists()


def test_frozen_entry_reports_startup_failure_and_returns_nonzero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    spec = importlib.util.spec_from_file_location("windows_entry", ROOT / "packaging/windows/entrypoint.py")
    assert spec and spec.loader
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    fake_launch = types.ModuleType("filesteward.launch")

    def refused(argv):
        raise ValueError("Application root marker was refused")

    fake_launch.main = refused
    monkeypatch.setitem(sys.modules, "filesteward.launch", fake_launch)
    assert entry.main([]) == 2
    assert "Application root marker was refused" in capsys.readouterr().err
    if os.name != "nt":
        return  # The console refusal above is portable; MessageBox is native.
    import ctypes

    dialogs = []
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(entry.logging, "exception", lambda *args: None)
    monkeypatch.setattr(ctypes.windll, "user32", types.SimpleNamespace(
        MessageBoxW=lambda owner, text, title, flags: dialogs.append((text, title))
    ))
    assert entry.main([]) == 2
    assert dialogs == [("Application root marker was refused", "FileSteward could not start")]


def test_bootstrap_binds_exact_version_digest_and_preserves_existing_files() -> None:
    template = (ROOT / "packaging/windows/FileSteward.cmd.in").read_text(encoding="utf-8")
    bootstrap = distribution.render_bootstrap(template, "0.16.0", "a" * 64)
    assert "@VERSION@" not in bootstrap and "@EXE_SHA256@" not in bootstrap
    assert "/releases/download/v0.16.0/FileSteward.exe" in bootstrap
    assert "/latest/" not in bootstrap and "EncodedCommand" not in bootstrap
    assert "$expectedHash = '" + "a" * 64 + "'" in bootstrap
    assert "[IO.FileMode]::CreateNew" in bootstrap
    assert "Existing FileSteward.exe does not match" in bootstrap
    assert "[IO.File]::Move($temporary, $target)" in bootstrap
    assert "Remove-Item -LiteralPath $temporary" in bootstrap
    assert "-Recurse" not in bootstrap and "-Force -" not in bootstrap
    assert "[Environment+SpecialFolder]::LocalApplicationData" in bootstrap
    assert "filesteward.application-root/v1" in bootstrap
    assert "windows-localappdata/v1" in bootstrap
    assert "ReparsePoint" in bootstrap


@pytest.mark.skipif(os.name != "nt", reason="native Windows PowerShell parser")
def test_bootstrap_payload_is_valid_windows_powershell(tmp_path: Path) -> None:
    bootstrap = distribution.render_bootstrap(
        (ROOT / "packaging/windows/FileSteward.cmd.in").read_text(encoding="utf-8"), "0.16.0", "a" * 64
    )
    payload = tmp_path / "payload.ps1"
    payload.write_text(bootstrap.rsplit("# POWERSHELL_PAYLOAD", 1)[1], encoding="utf-8")
    # Parse without evaluating downloads, filesystem mutations, or launching anything.
    command = "$tokens=$null;$errors=$null;[Management.Automation.Language.Parser]::ParseFile($env:FILESTEWARD_PARSE_PATH,[ref]$tokens,[ref]$errors)|Out-Null;if($errors.Count){$errors|Out-String|Write-Error;exit 1}"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], env={**os.environ, "FILESTEWARD_PARSE_PATH": str(payload)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_bootstrap_rejects_nonliteral_identity_inputs() -> None:
    for version, digest in (("0.16.0';throw", "a" * 64), ("0.16.0", "not-a-hash")):
        with pytest.raises(ValueError):
            distribution.render_bootstrap("@VERSION@ @EXE_SHA256@", version, digest)


@pytest.mark.skipif(os.name != "nt", reason="native Windows PowerShell bootstrap proof")
def test_bootstrap_synthetic_download_hash_reuse_and_bad_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.exe"
    source.write_bytes(b"synthetic executable transport fixture")
    local_data = tmp_path / "local-data"
    local_data.mkdir()
    bootstrap = distribution.render_bootstrap(
        (ROOT / "packaging/windows/FileSteward.cmd.in").read_text(encoding="utf-8"),
        "0.16.0", distribution.sha256(source),
    )
    payload = bootstrap.rsplit("# POWERSHELL_PAYLOAD", 1)[1]
    payload = payload.replace(
        "$localData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)",
        "$localData = $env:FILESTEWARD_TEST_LOCAL_DATA",
    )
    payload = payload.replace("$client.DownloadFile($downloadUrl, $temporary)",
                              "[IO.File]::Copy($env:FILESTEWARD_TEST_SOURCE, $temporary)")
    # Substitute only Known Folder, transport, and process launch boundaries.
    # Root admission, marker, version path, checksum, and no-overwrite logic run unchanged.
    adapters = """
function Start-Process { param([string]$FilePath, [string]$WorkingDirectory, [string]$WindowStyle)
  [IO.File]::WriteAllText($env:FILESTEWARD_TEST_LAUNCH, $FilePath)
}
"""
    script = tmp_path / "bootstrap-proof.ps1"
    script.write_text(adapters + payload, encoding="utf-8")
    launched = tmp_path / "launched.txt"
    environment = {**os.environ, "FILESTEWARD_TEST_LOCAL_DATA": str(local_data),
                   "FILESTEWARD_TEST_SOURCE": str(source), "FILESTEWARD_TEST_LAUNCH": str(launched)}

    def run() -> subprocess.CompletedProcess:
        return subprocess.run(["powershell.exe", "-NoProfile", "-File", str(script)], env=environment,
                              capture_output=True, text=True, timeout=15)

    assert run().returncode == 0
    target = local_data / "FileSteward/app/v0.16.0/FileSteward.exe"
    assert target.read_bytes() == source.read_bytes()
    assert Path(launched.read_text(encoding="utf-8")) == target
    source.unlink()  # Reuse must succeed without invoking the synthetic download adapter.
    assert run().returncode == 0
    target.write_bytes(b"unrelated or damaged file")
    launched.unlink()
    result = run()
    assert result.returncode != 0
    assert "It was not replaced" in result.stderr
    assert target.read_bytes() == b"unrelated or damaged file"
    assert not launched.exists()
    unrelated_data = tmp_path / "unrelated-local-data"
    unrelated_root = unrelated_data / "FileSteward"
    unrelated_root.mkdir(parents=True)
    sentinel = unrelated_root / "personal.txt"
    sentinel.write_bytes(b"preserve me")
    environment["FILESTEWARD_TEST_LOCAL_DATA"] = str(unrelated_data)
    result = run()
    assert result.returncode != 0 and "unmarked" in result.stderr
    assert list(unrelated_root.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"preserve me"
    failed_data = tmp_path / "failed-hash-local-data"
    failed_data.mkdir()
    environment["FILESTEWARD_TEST_LOCAL_DATA"] = str(failed_data)
    source.write_bytes(b"wrong downloaded bytes")
    result = run()
    assert result.returncode != 0 and "checksum failed" in result.stderr
    failed_directory = failed_data / "FileSteward/app/v0.16.0"
    assert not list(failed_directory.iterdir())
    assert not launched.exists()
