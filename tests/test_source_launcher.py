"""Exercise the Windows source launcher's update boundary on synthetic Git repos."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

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
    (repo / ".git" / "info" / "exclude").write_text("var/\n")
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


def test_failed_dependency_step_releases_application_lock(tmp_path, checkout):
    result = run_functions(tmp_path, r"""
$originalGit = ${function:Invoke-SourceGit}
function Invoke-SourceGit([string]$repo, [string[]]$arguments) {
  if ($arguments[0] -eq 'fetch') { return }
  & $originalGit $repo $arguments
}
Update-SourceCheckout '""" + str(checkout) + "' { throw 'Synthetic dependency failure' }\n")
    assert result.returncode != 0
    assert "Synthetic dependency failure" in result.stderr
    from filesteward.launch import InstanceLock
    lock = InstanceLock(checkout / "var" / "launch" / "instance.lock")
    try:
        assert lock.acquire(), "Failed dependency installation must release the shared application lock"
    finally:
        lock.close()


@pytest.mark.parametrize("existing_lock", [False, True])
def test_update_excludes_native_app_and_other_update_through_all_writes(tmp_path, checkout, existing_lock):
    if not POWERSHELL:
        pytest.skip("Windows PowerShell is required for native locking proof")
    lock_path = checkout / "var" / "launch" / "instance.lock"
    if existing_lock:
        lock_path.parent.mkdir(parents=True)
        lock_path.write_bytes(b"0")
    fetch_ready, fetch_release = tmp_path / "fetch-ready", tmp_path / "fetch-release"
    install_ready, install_release = tmp_path / "install-ready", tmp_path / "install-release"
    script = tmp_path / "paused-update.ps1"
    script.write_text(FUNCTIONS + r"""
$originalGit = ${function:Invoke-SourceGit}
function Wait-ProofRelease([string]$ready, [string]$release) {
  [IO.File]::WriteAllText($ready, 'ready')
  $deadline = [DateTime]::UtcNow.AddSeconds(20)
  while (!(Test-Path -LiteralPath $release)) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Concurrent proof timed out' }
    Start-Sleep -Milliseconds 25
  }
}
function Invoke-SourceGit([string]$repo, [string[]]$arguments) {
  if ($arguments[0] -eq 'fetch') {
    Wait-ProofRelease $env:FS_FETCH_READY $env:FS_FETCH_RELEASE
    return
  }
  & $originalGit $repo $arguments
}
Update-SourceCheckout $env:FS_PROOF_REPO {
  Wait-ProofRelease $env:FS_INSTALL_READY $env:FS_INSTALL_RELEASE
}
""", encoding="utf-8")
    process = subprocess.Popen(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-Command",
         "& ([ScriptBlock]::Create([IO.File]::ReadAllText($env:FS_TEST_SCRIPT)))"],
        env={**os.environ, "FS_TEST_SCRIPT": str(script), "FS_PROOF_REPO": str(checkout),
             "FS_FETCH_READY": str(fetch_ready), "FS_FETCH_RELEASE": str(fetch_release),
             "FS_INSTALL_READY": str(install_ready), "FS_INSTALL_RELEASE": str(install_release)},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    def wait_ready(path):
        deadline = time.monotonic() + 12
        while not path.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.025)
        assert path.exists(), process.communicate(timeout=3)

    def native_lock_probe():
        # Real application InstanceLock in a separate Windows Python process.
        return subprocess.run(
            [sys.executable, "-c", "from pathlib import Path; import sys; "
             "from filesteward.launch import InstanceLock; "
             "lock=InstanceLock(Path(sys.argv[1])); "
             "sys.exit(0 if lock.acquire() else 7)", str(lock_path)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True, timeout=10,
        )

    try:
        wait_ready(fetch_ready)
        assert lock_path.exists(), "Updater must create the lock even before a first app launch"
        assert native_lock_probe().returncode != 0, "Native application entered during Git writes"
        second = update(tmp_path, checkout)
        assert second.returncode != 0
        assert "wait for its update" in second.stderr
        fetch_release.write_text("continue")
        wait_ready(install_ready)
        assert native_lock_probe().returncode != 0, "Native application entered during dependency writes"
        install_release.write_text("continue")
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stdout + stderr
        assert native_lock_probe().returncode == 0, "Completed update did not release application lock"
    finally:
        fetch_release.touch()
        install_release.touch()
        if process.poll() is None:
            process.communicate(timeout=10)


def test_cmd_uses_existing_canonical_launch_and_distinct_release_route():
    assert "'dev\\FileSteward'" in PAYLOAD
    assert "@('merge', '--ff-only', 'origin/main')" in PAYLOAD
    assert "& $entry launch" in PAYLOAD
    assert "-I -m pip install --editable $repo" in PAYLOAD
    assert "Start-Process" not in PAYLOAD
    assert "releases/download/v@VERSION@/FileSteward.exe" in (
        ROOT / "packaging/windows/FileSteward.cmd.in"
    ).read_text()


@pytest.mark.parametrize("payload_exit, expected_exit", [(0, 0), (7, 1)])
def test_cmd_self_replacement_returns_only_to_preparsed_header(tmp_path, payload_exit, expected_exit):
    if os.name != "nt" or not POWERSHELL:
        pytest.skip("Actual cmd.exe and Windows PowerShell are required")
    marker = tmp_path / "unexpected-batch-resumption.txt"
    script = tmp_path / "self-updating-launcher.cmd"
    # Use the real production header. Its simulated payload replaces this same
    # file with hostile trailing batch lines while cmd.exe waits for PowerShell.
    # Resuming by an obsolete file offset would eventually execute those lines.
    header = (ROOT / "FileSteward-source.cmd").read_text().rsplit("# POWERSHELL_PAYLOAD", 1)[0]
    replacement = (f'echo UNEXPECTED>"{marker}"\r\n' * 200).replace("'", "''")
    payload = "\n[IO.File]::WriteAllText($env:FS_SOURCE_BOOTSTRAP, '" + replacement + "')\n"
    payload += f"exit {payload_exit}\n"
    script.write_text(header + "# POWERSHELL_PAYLOAD" + payload, encoding="utf-8", newline="\r\n")
    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(script)],
        cwd=tmp_path, text=True, input="\n", capture_output=True, timeout=15,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    assert script.read_text().startswith("echo UNEXPECTED>"), "Proof must actually rewrite the running CMD"
    assert not marker.exists(), "CMD resumed by a stale offset into the replaced source"
    assert "is not recognized" not in result.stderr
