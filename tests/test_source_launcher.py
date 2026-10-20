"""Exercise the Windows source launcher's update boundary on synthetic Git repos."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = (ROOT / "FileSteward-source.cmd").read_text().rsplit("# POWERSHELL_PAYLOAD", 1)[1]
FUNCTIONS = PAYLOAD.rsplit("\nStart-SourceFileSteward", 1)[0]
POWERSHELL = shutil.which("powershell.exe")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "profile" / "dev" / "FileSteward"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Synthetic launcher test")
    git(repo, "config", "user.email", "synthetic@example.invalid")
    (repo / "tracked.txt").write_text("first\n")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "synthetic baseline")
    git(repo, "remote", "add", "origin", "https://github.com/EndeavorEverlasting/FileSteward.git")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def run_functions(tmp_path, suffix):
    if not POWERSHELL:
        pytest.skip("Windows PowerShell is required for CMD payload execution")
    script = tmp_path / "launcher-proof.ps1"
    script.write_text(FUNCTIONS + "\n" + suffix, encoding="utf-8")
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-Command",
         "& ([ScriptBlock]::Create([IO.File]::ReadAllText($env:FS_TEST_SCRIPT)))"],
        env={**os.environ, "FS_TEST_SCRIPT": str(script)},
        text=True, capture_output=True, timeout=30,
    )


def update(tmp_path, repo):
    # Fetch alone is stubbed; every identity/status/ancestry/ff check uses real Git.
    # The test remote ref is populated in the synthetic repository above.
    return run_functions(tmp_path, r"""
$originalGit = ${function:Invoke-SourceGit}
function Invoke-SourceGit([string]$repo, [string[]]$arguments) {
  if ($arguments[0] -eq 'fetch') { Write-Host 'SYNTHETIC_FETCH'; return }
  & $originalGit $repo $arguments
}
Update-SourceCheckout '""" + str(repo).replace("'", "''") + "'\n")


def test_updates_clean_checkout_by_fast_forward(tmp_path, checkout):
    previous = git(checkout, "rev-parse", "HEAD")
    (checkout / "tracked.txt").write_text("second\n")
    git(checkout, "commit", "-am", "synthetic update")
    expected = git(checkout, "rev-parse", "HEAD")
    git(checkout, "update-ref", "refs/remotes/origin/main", expected)
    git(checkout, "update-ref", "refs/heads/main", previous)
    git(checkout, "restore", "--source", previous, "--staged", "--worktree", "tracked.txt")
    result = update(tmp_path, checkout)
    assert result.returncode == 0, result.stderr
    assert git(checkout, "rev-parse", "HEAD") == expected
    assert (checkout / "tracked.txt").read_text() == "second\n"


@pytest.mark.parametrize("case, expected", [
    ("modified", "local changes"),
    ("untracked", "local changes"),
    ("branch", "Switch the canonical checkout to main"),
    ("ahead", "unpublished commits"),
    ("remote", "Origin does not match"),
    ("nested", "must itself be the FileSteward checkout"),
])
def test_refuses_unsafe_update_and_preserves_head(tmp_path, checkout, case, expected):
    target = checkout
    if case == "modified":
        (checkout / "tracked.txt").write_text("operator edits\n")
    elif case == "untracked":
        (checkout / "unique.txt").write_text("operator work\n")
    elif case == "branch":
        git(checkout, "checkout", "-b", "codex/unfinished")
    elif case == "ahead":
        (checkout / "tracked.txt").write_text("unpublished\n")
        git(checkout, "commit", "-am", "unpublished work")
    elif case == "remote":
        git(checkout, "remote", "set-url", "origin", "https://example.invalid/other.git")
    elif case == "nested":
        target = checkout / "nested"
        target.mkdir()
    head = git(checkout, "rev-parse", "HEAD")
    before = git(checkout, "status", "--porcelain")
    result = update(tmp_path, target)
    assert result.returncode != 0
    assert expected in result.stderr
    assert git(checkout, "rev-parse", "HEAD") == head
    assert git(checkout, "status", "--porcelain") == before


def test_rejects_forbidden_source_root(tmp_path):
    forbidden = tmp_path / "OneDrive" / "dev" / "FileSteward"
    result = run_functions(tmp_path, "Assert-SourcePath '" + str(forbidden) + "'")
    assert result.returncode != 0
    assert "forbidden root" in result.stderr


def test_git_failure_is_not_silently_successful(tmp_path):
    result = run_functions(tmp_path, """
function git { $global:LASTEXITCODE = 9 }
Invoke-SourceGit '.' @('fetch', 'origin', 'main')
""")
    assert result.returncode != 0
    assert "Git failed (9)" in result.stderr


def test_running_source_app_blocks_update(tmp_path, checkout):
    launch_dir = checkout / "var" / "launch"
    launch_dir.mkdir(parents=True)
    lock = launch_dir / "instance.lock"
    lock.write_bytes(b"0")
    result = run_functions(tmp_path, """
$held = [IO.File]::Open('""" + str(lock) + """', 'Open', 'ReadWrite', 'None')
try { Update-SourceCheckout '""" + str(checkout) + """' } finally { $held.Dispose() }
""")
    assert result.returncode != 0
    assert "Close the running FileSteward source app" in result.stderr


def test_cmd_uses_existing_canonical_launch_and_distinct_release_route():
    assert "'dev\\FileSteward'" in PAYLOAD
    assert "@('merge', '--ff-only', 'origin/main')" in PAYLOAD
    assert "& $entry launch" in PAYLOAD
    assert "-I -m pip install --editable $repo" in PAYLOAD
    assert "Start-Process" not in PAYLOAD
    assert "releases/download/v@VERSION@/FileSteward.exe" in (
        ROOT / "packaging/windows/FileSteward.cmd.in"
    ).read_text()
