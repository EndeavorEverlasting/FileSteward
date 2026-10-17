"""Safety-contract tests for the opt-in Windows Downloads review scheduler.

These tests do not register or run a Windows task and do not read private files.
The PowerShell parser test is conditional on pwsh being present. Live Windows
registration and end-to-end scanning require separate operator-host proof.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/windows/downloads-hourly-review.ps1"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_preview_is_default_and_register_requires_explicit_authorization() -> None:
    content = _script()
    assert "[string]$Mode = 'Preview'" in content
    assert "if ($Mode -in @('Disable', 'Unregister', 'Register') -and -not $Authorize)" in content
    assert "if (Get-ExistingTask $name)" in content
    assert "refusing to overwrite or replace" in content


def test_uses_current_user_task_not_system_or_saved_password() -> None:
    content = _script()
    assert "-LogonType Interactive -RunLevel Limited" in content
    assert "WindowsIdentity]::GetCurrent()" in content
    assert "Assert-OwnedTask $task" in content
    assert "Description $OwnerMarker" in content
    assert "FileSteward.downloads-hourly-review/v1" in content


def test_hourly_schedule_guards_overlap_and_is_read_only() -> None:
    content = _script()
    assert "-RepetitionInterval (New-TimeSpan -Hours 1)" in content
    assert "-MultipleInstances IgnoreNew" in content
    assert "WaitOne(0)" in content
    assert "filesteward.cli scan" in content
    assert "filesteward.cli validate" in content
    assert "VERIFIED_READ_ONLY_REVIEW" in content
    assert "WindowsApps Store launcher is not a verified Python interpreter." in content
    assert "requires an operational Python 3.12+" in content
    for forbidden in (
        "Remove-Item", "Clear-RecycleBin", "Move-Item", "delete-execute",
        "delete-approve", "Start-Process -Verb RunAs", "Stop-Process",
    ):
        assert forbidden not in content, forbidden


def test_root_and_private_artifacts_are_bounded() -> None:
    content = _script()
    assert "Only the current Windows user Downloads folder" in content
    assert "[IO.FileAttributes]::ReparsePoint" in content
    assert "scripts\\windows\\downloads-hourly-review.ps1" in content
    assert "'var\\runs'" in content
    assert "Unable to" not in content  # keep refusal behavior visible, no permissive fallback


def test_powershell_parser_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell unavailable: parser proof requires operator Windows host")
    statement = (
        "$tokens=$null; $errors=$null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        "$args[0], [ref]$tokens, [ref]$errors); "
        "if($errors.Count){$errors | Out-String | Write-Error; exit 1}"
    )
    proc = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", statement, str(SCRIPT)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
