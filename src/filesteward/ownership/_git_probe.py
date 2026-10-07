"""Injectable Git probes for repository attribution (synthetic-test friendly)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

__all__ = [
    "GitCommand",
    "GitProbeResult",
    "default_git_command",
    "probe_git_repository",
]


GitCommand = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class GitProbeResult:
    """Normalized Git adapter outputs for one repository root."""

    root: str
    is_repository: bool
    clean_working_tree: bool
    has_staged: bool
    has_untracked: bool
    has_unpushed_or_unique_branch: bool
    remote_recoverable: bool
    is_current_worktree: bool
    branch: Optional[str]
    remotes: tuple[str, ...]
    detached: bool
    probe_errors: tuple[str, ...]


def default_git_command(
    args: Sequence[str],
    *,
    cwd: str,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Run a real ``git`` subprocess. Prefer injecting a fake in tests."""

    exe = shutil.which("git")
    if exe is None:
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=127,
            stdout="",
            stderr="git executable not available",
        )
    merged = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    if env:
        merged.update(env)
    return subprocess.run(
        [exe, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def _ok(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0


def _parse_porcelain(stdout: str) -> tuple[bool, bool, bool]:
    """Return ``(clean, has_staged, has_untracked)`` from ``git status --porcelain``."""

    has_staged = False
    has_untracked = False
    any_entry = False
    for raw in stdout.splitlines():
        line = raw.rstrip("\n")
        if not line:
            continue
        any_entry = True
        if line.startswith("??") or line.startswith("!!"):
            has_untracked = True
            continue
        x = line[0] if len(line) >= 1 else " "
        if x not in (" ", "?"):
            has_staged = True
    return (not any_entry, has_staged, has_untracked)


def probe_git_repository(
    root: Any,
    *,
    run_git: GitCommand = default_git_command,
    treat_as_current_worktree: Optional[bool] = None,
) -> GitProbeResult:
    """Collect dirty/remote/worktree/push evidence for ``root``.

    Fail-closed on probe gaps that affect uniqueness or recoverability:
    unresolved ahead/behind or missing remotes never claim recoverability.
    """

    path = os.path.abspath(os.fspath(root))
    errors: list[str] = []

    inside = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    if not _ok(inside) or inside.stdout.strip().lower() != "true":
        return GitProbeResult(
            root=path,
            is_repository=False,
            clean_working_tree=False,
            has_staged=False,
            has_untracked=False,
            has_unpushed_or_unique_branch=True,
            remote_recoverable=False,
            is_current_worktree=False,
            branch=None,
            remotes=(),
            detached=False,
            probe_errors=("not_a_git_work_tree",),
        )

    status = run_git(["status", "--porcelain"], cwd=path)
    if not _ok(status):
        errors.append("status_failed")
        clean, has_staged, has_untracked = False, True, True
    else:
        clean, has_staged, has_untracked = _parse_porcelain(status.stdout)

    branch_result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    detached = False
    branch: Optional[str] = None
    if _ok(branch_result):
        name = branch_result.stdout.strip()
        if name == "HEAD":
            detached = True
            branch = None
        else:
            branch = name or None
    else:
        errors.append("branch_failed")

    remote_result = run_git(["remote"], cwd=path)
    remotes: tuple[str, ...] = ()
    if _ok(remote_result):
        remotes = tuple(
            line.strip() for line in remote_result.stdout.splitlines() if line.strip()
        )
    else:
        errors.append("remote_failed")

    remote_recoverable = False
    if remotes:
        for remote in remotes:
            url = run_git(["remote", "get-url", remote], cwd=path)
            if _ok(url) and url.stdout.strip():
                remote_recoverable = True
                break
        if not remote_recoverable:
            errors.append("remote_url_unproven")

    has_unpushed = False
    if branch and remotes:
        upstream = run_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=path,
        )
        if _ok(upstream) and upstream.stdout.strip():
            counts = run_git(
                ["rev-list", "--left-right", "--count", "@{u}...HEAD"],
                cwd=path,
            )
            if _ok(counts):
                parts = counts.stdout.strip().split()
                if len(parts) >= 2:
                    try:
                        ahead = int(parts[1])
                    except ValueError:
                        errors.append("ahead_parse_failed")
                        has_unpushed = True
                    else:
                        has_unpushed = ahead > 0
                else:
                    errors.append("ahead_count_unparsed")
                    has_unpushed = True
            else:
                errors.append("ahead_probe_failed")
                has_unpushed = True
        else:
            has_unpushed = True
            errors.append("no_upstream")
    elif branch and not remotes:
        has_unpushed = True
    elif detached:
        has_unpushed = True

    if treat_as_current_worktree is not None:
        is_current = treat_as_current_worktree
    else:
        # Listed worktrees are normal. Only locked (or explicit override /
        # Entire current-worktree evidence) raise the ACTIVE current floor.
        is_current = _worktree_is_locked(path, run_git=run_git, errors=errors)

    return GitProbeResult(
        root=path,
        is_repository=True,
        clean_working_tree=clean,
        has_staged=has_staged,
        has_untracked=has_untracked,
        has_unpushed_or_unique_branch=has_unpushed,
        remote_recoverable=remote_recoverable,
        is_current_worktree=is_current,
        branch=branch,
        remotes=remotes,
        detached=detached,
        probe_errors=tuple(errors),
    )


def _worktree_is_locked(
    path: str,
    *,
    run_git: GitCommand,
    errors: list[str],
) -> bool:
    """True when this root's worktree entry is locked (fail closed on list failure)."""

    listed = run_git(["worktree", "list", "--porcelain"], cwd=path)
    if not _ok(listed):
        errors.append("worktree_list_failed")
        return True
    norm = os.path.normcase(os.path.abspath(path))
    current: Optional[str] = None
    locked = False
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            if current is not None and current == norm and locked:
                return True
            current = os.path.normcase(
                os.path.abspath(line[len("worktree ") :].strip())
            )
            locked = False
        elif line.strip() == "locked" or line.startswith("locked "):
            locked = True
    return bool(current == norm and locked)
