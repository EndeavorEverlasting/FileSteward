"""J3 repository attribution: Git (+ optional Entire) -> lifecycle evidence.

Normalizes repository ownership/lifecycle classes for the cross-domain graph.
Does not authorize deletion. Age, inactivity, or Entire absence alone never
produce ``REPO_LEGACY_CANDIDATE`` or reclaim.

Reuses ``ProtectionIndex.from_git_discovery`` for root discovery.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from filesteward.ownership._git_probe import (
    GitCommand,
    GitProbeResult,
    default_git_command,
    probe_git_repository,
)
from filesteward.protect import ProtectionIndex

__all__ = [
    "EntireContextEvidence",
    "RepoLifecycleClass",
    "RepositoryAttribution",
    "RepositoryEvidence",
    "attribute_repositories_under",
    "classify_repository",
    "entire_context_from_status",
    "evidence_from_probe",
]


class RepoLifecycleClass(str, Enum):
    REPO_ACTIVE = "REPO_ACTIVE"
    REPO_STABLE = "REPO_STABLE"
    REPO_LEGACY_CANDIDATE = "REPO_LEGACY_CANDIDATE"
    REPO_GENERATED_OUTPUT = "REPO_GENERATED_OUTPUT"


_SAFETY_FLOOR = {
    RepoLifecycleClass.REPO_ACTIVE: "PROTECTED_OR_KEEP",
    RepoLifecycleClass.REPO_STABLE: "OPERATOR_VALUE_DECISION",
    RepoLifecycleClass.REPO_LEGACY_CANDIDATE: "OPERATOR_VALUE_DECISION",
    RepoLifecycleClass.REPO_GENERATED_OUTPUT: "RECLAIM_ONLY_AFTER_REGENERATION_PROOF",
}


@dataclass(frozen=True)
class EntireContextEvidence:
    """Entire as context accelerator only — never deletion authority.

    ``available=False`` means Entire was not injectable/usable. That absence
    must never be read as dispensability or legacy proof.
    """

    available: bool = False
    current_worktree: bool = False
    session_activity: bool = False
    change_impact: bool = False

    @property
    def has_current_activity(self) -> bool:
        if not self.available:
            return False
        return (
            self.current_worktree or self.session_activity or self.change_impact
        )


@dataclass(frozen=True)
class RepositoryEvidence:
    """Machine-resolved repository facts used for lifecycle classification.

    ``age_days`` / ``inactive_days`` may be recorded for explainability but are
    forbidden as sole or deciding inputs for ``REPO_LEGACY_CANDIDATE``.
    """

    root: str
    clean_working_tree: bool
    has_staged: bool
    has_untracked: bool
    has_unpushed_or_unique_branch: bool
    remote_recoverable: bool
    is_current_worktree: bool
    has_app_toolchain_dependency: bool = False
    has_cross_repo_dependency: bool = False
    is_generated_output: bool = False
    regeneration_proven: bool = False
    age_days: Optional[int] = None
    inactive_days: Optional[int] = None
    branch: Optional[str] = None
    remotes: tuple[str, ...] = ()
    detached: bool = False
    probe_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepositoryAttribution:
    root: str
    lifecycle_class: RepoLifecycleClass
    safety_floor: str
    reasons: tuple[str, ...]
    evidence: RepositoryEvidence
    entire: EntireContextEvidence = field(default_factory=EntireContextEvidence)

    @property
    def is_operator_decision_only(self) -> bool:
        return self.lifecycle_class in (
            RepoLifecycleClass.REPO_STABLE,
            RepoLifecycleClass.REPO_LEGACY_CANDIDATE,
        )


def entire_context_from_status(
    status: Optional[Mapping[str, Any]],
    *,
    repo_root: Optional[str] = None,
) -> EntireContextEvidence:
    """Map an ``entire status --json``-like mapping into context evidence.

    Missing/empty/disabled status => ``available=False`` (never legacy).
    """

    if not status or not isinstance(status, Mapping):
        return EntireContextEvidence(available=False)
    if status.get("enabled") is False:
        return EntireContextEvidence(available=False)
    if status.get("error"):
        return EntireContextEvidence(available=False)

    current_worktree = bool(status.get("current_worktree") or status.get("is_current_worktree"))
    if repo_root and not current_worktree:
        wt = status.get("worktree") or status.get("working_tree")
        if isinstance(wt, str) and wt:
            current_worktree = os.path.normcase(
                os.path.abspath(wt)
            ) == os.path.normcase(os.path.abspath(repo_root))

    session = bool(
        status.get("session_activity")
        or status.get("active_sessions")
        or status.get("has_session")
    )
    impact = bool(
        status.get("change_impact")
        or status.get("has_change_impact")
        or status.get("impact")
    )
    return EntireContextEvidence(
        available=True,
        current_worktree=current_worktree,
        session_activity=session,
        change_impact=impact,
    )


def evidence_from_probe(
    probe: GitProbeResult,
    *,
    has_app_toolchain_dependency: bool = False,
    has_cross_repo_dependency: bool = False,
    is_generated_output: bool = False,
    regeneration_proven: bool = False,
    age_days: Optional[int] = None,
    inactive_days: Optional[int] = None,
) -> RepositoryEvidence:
    return RepositoryEvidence(
        root=probe.root,
        clean_working_tree=probe.clean_working_tree,
        has_staged=probe.has_staged,
        has_untracked=probe.has_untracked,
        has_unpushed_or_unique_branch=probe.has_unpushed_or_unique_branch,
        remote_recoverable=probe.remote_recoverable,
        is_current_worktree=probe.is_current_worktree,
        has_app_toolchain_dependency=has_app_toolchain_dependency,
        has_cross_repo_dependency=has_cross_repo_dependency,
        is_generated_output=is_generated_output,
        regeneration_proven=regeneration_proven,
        age_days=age_days,
        inactive_days=inactive_days,
        branch=probe.branch,
        remotes=probe.remotes,
        detached=probe.detached,
        probe_errors=probe.probe_errors,
    )


def classify_repository(
    evidence: RepositoryEvidence,
    *,
    entire: Optional[EntireContextEvidence] = None,
) -> RepositoryAttribution:
    """Reduce Git (+ optional Entire/dependency) evidence to a lifecycle class.

    Precedence: generated-output boundary (when proven) -> ACTIVE protective
    floor -> LEGACY_CANDIDATE only when every required_all signal is satisfied
    -> otherwise STABLE. Forbidden inferences (age/inactivity/Entire absence)
    never tip the class toward LEGACY.
    """

    ctx = entire if entire is not None else EntireContextEvidence(available=False)
    reasons: list[str] = []

    if evidence.is_generated_output and evidence.regeneration_proven:
        reasons.append("generated_output_boundary_with_regeneration_proof")
        return RepositoryAttribution(
            root=evidence.root,
            lifecycle_class=RepoLifecycleClass.REPO_GENERATED_OUTPUT,
            safety_floor=_SAFETY_FLOOR[RepoLifecycleClass.REPO_GENERATED_OUTPUT],
            reasons=tuple(reasons),
            evidence=evidence,
            entire=ctx,
        )

    active_reasons = _active_reasons(evidence, ctx)
    if active_reasons:
        return RepositoryAttribution(
            root=evidence.root,
            lifecycle_class=RepoLifecycleClass.REPO_ACTIVE,
            safety_floor=_SAFETY_FLOOR[RepoLifecycleClass.REPO_ACTIVE],
            reasons=tuple(active_reasons),
            evidence=evidence,
            entire=ctx,
        )

    legacy_ok, legacy_gaps = _legacy_required_all(evidence, ctx)
    if legacy_ok:
        reasons.append("all_legacy_required_signals_satisfied")
        reasons.append("operator_decision_only_not_auto_delete")
        # Explicitly record that age/inactivity/Entire-absence were not used.
        if evidence.age_days is not None:
            reasons.append("age_recorded_but_not_authority")
        if evidence.inactive_days is not None:
            reasons.append("inactivity_recorded_but_not_authority")
        if not ctx.available:
            reasons.append("entire_unavailable_not_legacy_authority")
        return RepositoryAttribution(
            root=evidence.root,
            lifecycle_class=RepoLifecycleClass.REPO_LEGACY_CANDIDATE,
            safety_floor=_SAFETY_FLOOR[RepoLifecycleClass.REPO_LEGACY_CANDIDATE],
            reasons=tuple(reasons),
            evidence=evidence,
            entire=ctx,
        )

    reasons.append("intentional_or_incomplete_reproducible_presence")
    reasons.extend(f"legacy_gap:{gap}" for gap in legacy_gaps)
    if evidence.age_days is not None:
        reasons.append("age_alone_never_legacy")
    if evidence.inactive_days is not None:
        reasons.append("inactivity_alone_never_legacy")
    if not ctx.available:
        reasons.append("entire_absence_alone_never_legacy")
    return RepositoryAttribution(
        root=evidence.root,
        lifecycle_class=RepoLifecycleClass.REPO_STABLE,
        safety_floor=_SAFETY_FLOOR[RepoLifecycleClass.REPO_STABLE],
        reasons=tuple(reasons),
        evidence=evidence,
        entire=ctx,
    )


def _active_reasons(
    evidence: RepositoryEvidence, ctx: EntireContextEvidence
) -> list[str]:
    reasons: list[str] = []
    if not evidence.clean_working_tree:
        reasons.append("dirty_working_tree")
    if evidence.has_staged:
        reasons.append("staged_unique_work")
    if evidence.has_untracked:
        reasons.append("untracked_unique_work")
    if evidence.has_unpushed_or_unique_branch:
        reasons.append("ahead_or_unpushed_or_unresolved_uniqueness")
    if evidence.is_current_worktree:
        reasons.append("current_or_attached_worktree")
    if ctx.has_current_activity:
        if ctx.current_worktree:
            reasons.append("entire_current_worktree")
        if ctx.session_activity:
            reasons.append("entire_session_activity")
        if ctx.change_impact:
            reasons.append("entire_change_impact")
    if evidence.has_app_toolchain_dependency:
        reasons.append("application_or_toolchain_dependency")
    return reasons


def _legacy_required_all(
    evidence: RepositoryEvidence, ctx: EntireContextEvidence
) -> tuple[bool, tuple[str, ...]]:
    """Return whether every contract ``required_all`` signal is satisfied."""

    gaps: list[str] = []
    if not evidence.clean_working_tree:
        gaps.append("clean_working_tree")
    if evidence.has_staged:
        gaps.append("no_staged_unique_work")
    if evidence.has_untracked:
        gaps.append("no_untracked_unique_work")
    if evidence.has_unpushed_or_unique_branch:
        gaps.append("no_unpushed_or_unresolved_uniqueness")
    if not evidence.remote_recoverable:
        gaps.append("remote_recovery_proven")
    if evidence.is_current_worktree:
        gaps.append("not_current_worktree")
    if evidence.has_app_toolchain_dependency:
        gaps.append("no_app_toolchain_dependency")
    if evidence.has_cross_repo_dependency:
        gaps.append("no_cross_repo_dependency")
    # When Entire is available, current session/change-impact blocks legacy.
    # When unavailable, this signal is vacuously satisfied — absence is not
    # a positive legacy proof and is never used alone (see classify reasons).
    if ctx.available and ctx.has_current_activity:
        gaps.append("no_entire_current_activity")
    return (not gaps, tuple(gaps))


def attribute_repositories_under(
    root: Any,
    *,
    run_git: GitCommand = default_git_command,
    entire_status: Optional[Callable[[], Optional[Mapping[str, Any]]]] = None,
    scandir: Any = None,
    dependency_flags: Optional[
        Callable[[str], Mapping[str, bool]]
    ] = None,
    treat_as_current_worktree: Optional[bool] = None,
    age_days_for: Optional[Callable[[str], Optional[int]]] = None,
    inactive_days_for: Optional[Callable[[str], Optional[int]]] = None,
) -> tuple[RepositoryAttribution, ...]:
    """Discover git roots under ``root`` and attribute each repository.

    Discovery uses ``ProtectionIndex.from_git_discovery``. Entire status is an
    optional callable; missing Entire never authorizes legacy/reclaim.
    """

    kwargs = {} if scandir is None else {"scandir": scandir}
    index = ProtectionIndex.from_git_discovery(root, **kwargs)

    status_map: Optional[Mapping[str, Any]] = None
    entire_available_probe = False
    if entire_status is not None:
        try:
            status_map = entire_status()
            entire_available_probe = True
        except Exception:
            status_map = None
            entire_available_probe = False

    attributions: list[RepositoryAttribution] = []
    for protected in index:
        probe = probe_git_repository(
            protected.path,
            run_git=run_git,
            treat_as_current_worktree=treat_as_current_worktree,
        )
        if not probe.is_repository:
            continue
        flags = dependency_flags(protected.path) if dependency_flags else {}
        evidence = evidence_from_probe(
            probe,
            has_app_toolchain_dependency=bool(
                flags.get("has_app_toolchain_dependency", False)
            ),
            has_cross_repo_dependency=bool(
                flags.get("has_cross_repo_dependency", False)
            ),
            is_generated_output=bool(flags.get("is_generated_output", False)),
            regeneration_proven=bool(flags.get("regeneration_proven", False)),
            age_days=age_days_for(protected.path) if age_days_for else None,
            inactive_days=(
                inactive_days_for(protected.path) if inactive_days_for else None
            ),
        )
        entire = (
            entire_context_from_status(status_map, repo_root=protected.path)
            if entire_available_probe
            else EntireContextEvidence(available=False)
        )
        attributions.append(classify_repository(evidence, entire=entire))
    return tuple(attributions)
