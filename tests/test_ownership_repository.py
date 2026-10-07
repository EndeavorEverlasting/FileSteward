"""J3 proof: repository attribution lifecycle reducer.

Negative: age-only and Entire-absence-only never yield LEGACY_CANDIDATE.
Positive: dirty => ACTIVE; clean recoverable required_all => LEGACY_CANDIDATE;
clean intentional clone missing a required signal => STABLE.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import pytest

from filesteward.ownership.repository import (
    EntireContextEvidence,
    RepoLifecycleClass,
    RepositoryEvidence,
    attribute_repositories_under,
    classify_repository,
    entire_context_from_status,
    evidence_from_probe,
)
from filesteward.ownership._git_probe import GitProbeResult, probe_git_repository


def _evidence(**overrides: Any) -> RepositoryEvidence:
    base = dict(
        root=r"C:\synthetic\repo",
        clean_working_tree=True,
        has_staged=False,
        has_untracked=False,
        has_unpushed_or_unique_branch=False,
        remote_recoverable=True,
        is_current_worktree=False,
        has_app_toolchain_dependency=False,
        has_cross_repo_dependency=False,
    )
    base.update(overrides)
    return RepositoryEvidence(**base)


# ---------------------------------------------------------------------------
# Negative: forbidden inferences
# ---------------------------------------------------------------------------


class TestForbiddenLegacyInferences:
    def test_age_alone_never_legacy(self) -> None:
        # Old + intentionally present, but missing remote recovery proof.
        result = classify_repository(
            _evidence(remote_recoverable=False, age_days=4000),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_STABLE
        assert result.lifecycle_class is not RepoLifecycleClass.REPO_LEGACY_CANDIDATE
        assert "age_alone_never_legacy" in result.reasons

    def test_inactivity_alone_never_legacy(self) -> None:
        result = classify_repository(
            _evidence(remote_recoverable=False, inactive_days=900),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_STABLE
        assert "inactivity_alone_never_legacy" in result.reasons

    def test_entire_absence_alone_never_legacy(self) -> None:
        # Entire missing is the only "signal"; other required_all not satisfied.
        result = classify_repository(
            _evidence(remote_recoverable=False),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_STABLE
        assert "entire_absence_alone_never_legacy" in result.reasons
        assert result.lifecycle_class is not RepoLifecycleClass.REPO_LEGACY_CANDIDATE

    def test_age_with_otherwise_complete_signals_still_not_age_authority(self) -> None:
        # Age may be recorded on a true LEGACY_CANDIDATE, but must not be the authority.
        result = classify_repository(
            _evidence(age_days=4000),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_LEGACY_CANDIDATE
        assert "age_recorded_but_not_authority" in result.reasons


# ---------------------------------------------------------------------------
# Positive ACTIVE / LEGACY / STABLE
# ---------------------------------------------------------------------------


class TestLifecyclePositive:
    def test_dirty_repo_is_active(self) -> None:
        result = classify_repository(_evidence(clean_working_tree=False))
        assert result.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE
        assert result.safety_floor == "PROTECTED_OR_KEEP"
        assert "dirty_working_tree" in result.reasons

    def test_staged_or_untracked_is_active(self) -> None:
        staged = classify_repository(_evidence(has_staged=True))
        untracked = classify_repository(_evidence(has_untracked=True))
        assert staged.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE
        assert untracked.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE

    def test_ahead_unpushed_is_active(self) -> None:
        result = classify_repository(
            _evidence(has_unpushed_or_unique_branch=True)
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE

    def test_current_worktree_is_active(self) -> None:
        result = classify_repository(_evidence(is_current_worktree=True))
        assert result.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE

    def test_entire_current_activity_is_active(self) -> None:
        result = classify_repository(
            _evidence(),
            entire=EntireContextEvidence(
                available=True, change_impact=True
            ),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE
        assert "entire_change_impact" in result.reasons

    def test_clean_recoverable_required_all_is_legacy_candidate(self) -> None:
        result = classify_repository(
            _evidence(),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_LEGACY_CANDIDATE
        assert result.safety_floor == "OPERATOR_VALUE_DECISION"
        assert "operator_decision_only_not_auto_delete" in result.reasons
        assert result.is_operator_decision_only

    def test_clean_recoverable_with_entire_available_but_idle_may_be_legacy(
        self,
    ) -> None:
        result = classify_repository(
            _evidence(),
            entire=EntireContextEvidence(available=True),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_LEGACY_CANDIDATE

    def test_clean_intentional_clone_missing_remote_stays_stable(self) -> None:
        result = classify_repository(
            _evidence(remote_recoverable=False),
            entire=EntireContextEvidence(available=False),
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_STABLE
        assert "legacy_gap:remote_recovery_proven" in result.reasons

    def test_clean_clone_with_cross_repo_dependency_stays_stable(self) -> None:
        result = classify_repository(
            _evidence(has_cross_repo_dependency=True)
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_STABLE
        assert "legacy_gap:no_cross_repo_dependency" in result.reasons

    def test_generated_output_with_regen_proof(self) -> None:
        result = classify_repository(
            _evidence(is_generated_output=True, regeneration_proven=True)
        )
        assert result.lifecycle_class is RepoLifecycleClass.REPO_GENERATED_OUTPUT
        assert result.safety_floor == "RECLAIM_ONLY_AFTER_REGENERATION_PROOF"


# ---------------------------------------------------------------------------
# Entire helpers
# ---------------------------------------------------------------------------


class TestEntireContext:
    def test_missing_status_is_unavailable(self) -> None:
        assert entire_context_from_status(None).available is False
        assert entire_context_from_status({}).available is False

    def test_disabled_or_error_is_unavailable(self) -> None:
        assert entire_context_from_status({"enabled": False}).available is False
        assert entire_context_from_status({"error": "not set up"}).available is False


# ---------------------------------------------------------------------------
# Injectable git probe + discovery
# ---------------------------------------------------------------------------


def _fake_git(
    responses: Mapping[tuple[str, ...], tuple[int, str]],
) -> Any:
    def run(
        args: Sequence[str],
        *,
        cwd: str,
        env: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(args)
        # Allow prefix matches for remote get-url etc. already exact.
        if key not in responses:
            # Try ignoring cwd-specific noise: exact only.
            return subprocess.CompletedProcess(
                args=list(args), returncode=1, stdout="", stderr=f"unexpected {args}"
            )
        code, out = responses[key]
        return subprocess.CompletedProcess(
            args=list(args), returncode=code, stdout=out, stderr=""
        )

    return run


class TestInjectableProbe:
    def test_probe_dirty_maps_to_active_via_classifier(self) -> None:
        root = r"C:\synthetic\dirty"
        run = _fake_git(
            {
                ("rev-parse", "--is-inside-work-tree"): (0, "true\n"),
                ("status", "--porcelain"): (0, " M tracked.txt\n"),
                ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n"),
                ("remote",): (0, "origin\n"),
                ("remote", "get-url", "origin"): (
                    0,
                    "https://example.invalid/repo.git\n",
                ),
                (
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ): (0, "origin/main\n"),
                ("rev-list", "--left-right", "--count", "@{u}...HEAD"): (
                    0,
                    "0\t0\n",
                ),
                ("worktree", "list", "--porcelain"): (
                    0,
                    f"worktree {root}\nHEAD abc\nbranch refs/heads/main\n",
                ),
            }
        )
        probe = probe_git_repository(
            root, run_git=run, treat_as_current_worktree=False
        )
        assert probe.clean_working_tree is False
        attr = classify_repository(evidence_from_probe(probe))
        assert attr.lifecycle_class is RepoLifecycleClass.REPO_ACTIVE

    def test_probe_clean_recoverable_not_current(self) -> None:
        root = r"C:\synthetic\clean"
        run = _fake_git(
            {
                ("rev-parse", "--is-inside-work-tree"): (0, "true\n"),
                ("status", "--porcelain"): (0, ""),
                ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n"),
                ("remote",): (0, "origin\n"),
                ("remote", "get-url", "origin"): (
                    0,
                    "https://example.invalid/repo.git\n",
                ),
                (
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ): (0, "origin/main\n"),
                ("rev-list", "--left-right", "--count", "@{u}...HEAD"): (
                    0,
                    "0\t0\n",
                ),
                ("worktree", "list", "--porcelain"): (
                    0,
                    f"worktree {root}\nHEAD abc\nbranch refs/heads/main\n",
                ),
            }
        )
        probe = probe_git_repository(
            root, run_git=run, treat_as_current_worktree=False
        )
        assert probe.clean_working_tree is True
        assert probe.remote_recoverable is True
        assert probe.has_unpushed_or_unique_branch is False
        attr = classify_repository(
            evidence_from_probe(probe),
            entire=EntireContextEvidence(available=False),
        )
        assert attr.lifecycle_class is RepoLifecycleClass.REPO_LEGACY_CANDIDATE


class TestDiscoveryIntegration:
    def test_attribute_under_uses_protection_index(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "clone"
        repo.mkdir()
        (repo / ".git").mkdir()

        calls: list[str] = []

        def run(
            args: Sequence[str],
            *,
            cwd: str,
            env: Optional[Mapping[str, str]] = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args[0] if args else "")
            table = {
                ("rev-parse", "--is-inside-work-tree"): (0, "true\n"),
                ("status", "--porcelain"): (0, ""),
                ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n"),
                ("remote",): (0, "origin\n"),
                ("remote", "get-url", "origin"): (
                    0,
                    "https://example.invalid/x.git\n",
                ),
                (
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ): (0, "origin/main\n"),
                ("rev-list", "--left-right", "--count", "@{u}...HEAD"): (
                    0,
                    "0\t0\n",
                ),
                ("worktree", "list", "--porcelain"): (
                    0,
                    f"worktree {repo}\nHEAD abc\nbranch refs/heads/main\n",
                ),
            }
            code, out = table.get(tuple(args), (1, ""))
            return subprocess.CompletedProcess(
                args=list(args), returncode=code, stdout=out, stderr=""
            )

        attrs = attribute_repositories_under(
            tmp_path,
            run_git=run,
            entire_status=lambda: None,
            treat_as_current_worktree=False,
        )
        assert len(attrs) == 1
        assert attrs[0].lifecycle_class is RepoLifecycleClass.REPO_LEGACY_CANDIDATE
        assert "rev-parse" in calls

    def test_entire_status_callable_marks_active(self, tmp_path: Path) -> None:
        repo = tmp_path / "active-clone"
        repo.mkdir()
        (repo / ".git").mkdir()

        def run(
            args: Sequence[str],
            *,
            cwd: str,
            env: Optional[Mapping[str, str]] = None,
        ) -> subprocess.CompletedProcess[str]:
            table = {
                ("rev-parse", "--is-inside-work-tree"): (0, "true\n"),
                ("status", "--porcelain"): (0, ""),
                ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n"),
                ("remote",): (0, "origin\n"),
                ("remote", "get-url", "origin"): (
                    0,
                    "https://example.invalid/x.git\n",
                ),
                (
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ): (0, "origin/main\n"),
                ("rev-list", "--left-right", "--count", "@{u}...HEAD"): (
                    0,
                    "0\t0\n",
                ),
                ("worktree", "list", "--porcelain"): (
                    0,
                    f"worktree {repo}\nHEAD abc\nbranch refs/heads/main\n",
                ),
            }
            code, out = table.get(tuple(args), (1, ""))
            return subprocess.CompletedProcess(
                args=list(args), returncode=code, stdout=out, stderr=""
            )

        attrs = attribute_repositories_under(
            tmp_path,
            run_git=run,
            entire_status=lambda: {
                "enabled": True,
                "change_impact": True,
            },
            treat_as_current_worktree=False,
        )
        assert len(attrs) == 1
        assert attrs[0].lifecycle_class is RepoLifecycleClass.REPO_ACTIVE
