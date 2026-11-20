"""Regression guards for the user-owned Windows FileSteward shortcut launcher.

These are source-level contract checks, NOT native Windows shell acceptance.
Native .lnk click and interactive launch still require supported host proof.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "windows" / "Install-FileSteward-Shortcut.ps1"


def test_shortcut_executes_local_app_not_ephemeral_web_address():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "pythonw.exe" in script
    assert "$link.TargetPath = $pythonw" in script
    assert "$link.Arguments = '-m filesteward.cli launch'" in script
    assert "$link.WorkingDirectory = $source" in script
    assert "Start-Process -FilePath $pythonw" in script
    assert "127.0.0.1:50315" not in script
    assert "http://127.0.0.1:" not in script.split("# A .lnk launches pythonw")[0]
    assert "webbrowser.open" not in script  # existing application owns browser opening


def test_shortcut_respects_existing_checkout_and_worktree_canonical_roots():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "'dev', 'FileSteward'" in script
    assert "'dev', 'worktrees', 'FileSteward'" in script
    assert "relativeLane.IndexOf('\\')" in script
    assert "Refusing a linked/reparse path" in script
    assert "Not an existing FileSteward Git checkout/worktree." in script
    assert "py.exe -3 -m venv $venv" in script
    assert "pip install --editable $source" in script
    assert "filesteward.cli import main" in script
    assert "$source.Equals($canonical, $equals)" in script


def test_shortcut_does_not_claim_cleanup_authority_or_overwrite_unknown_link():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "Existing shortcut belongs to a different installation; preserved" in script
    assert "No shortcut was created" in script
    assert "[switch]$StartMenuOnly" in script
    assert "[switch]$NoLaunch" in script
    assert "Shortcut installed:" in script
    assert "FileSteward launch requested." in script
    assert "filesteward scan" not in script
    assert "delete-execute" not in script
    assert "Start-ScheduledTask" not in script
    assert "Register-ScheduledTask" not in script


def test_application_remains_single_instance_and_selects_actual_port():
    launch = (ROOT / "src" / "filesteward" / "launch.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--port", type=int, default=0)' in launch
    assert "if not lock.acquire():" in launch
    assert '"/api/v1/launch/health"' in launch
    assert "webbrowser.open(url)" in launch
    assert "webbrowser.open(session.origin)" in launch


def test_double_click_installer_is_relative_and_not_a_browser_bookmark():
    cmd = (ROOT / "Install-FileSteward-Shortcut.cmd").read_text(encoding="utf-8")
    assert "%~dp0scripts\\windows\\Install-FileSteward-Shortcut.ps1" in cmd
    assert 'powershell.exe -NoLogo -NoProfile -File "%FS_SHORTCUT_INSTALLER%"' in cmd
    assert "pause" in cmd
    assert "http://127.0.0.1" not in cmd
    assert "ExecutionPolicy Bypass" not in cmd
