"""J4 most-protective-edge-wins reducer tests."""

from __future__ import annotations

from filesteward.models import CleanupDisposition
from filesteward.ownership.graph import build_ownership_graph
from filesteward.ownership.reducer import reduce_path_ownership
from filesteward.ownership.repository import (
    RepoLifecycleClass,
    RepositoryAttribution,
    RepositoryEvidence,
)
from filesteward.ownership.windows_app import (
    AppLifecycleClass,
    AppOwnershipEdge,
    AppOwnershipRecord,
)


def _app_record(
    path: str,
    *,
    lifecycle: AppLifecycleClass,
    name: str = "Demo App",
) -> AppOwnershipRecord:
    return AppOwnershipRecord(
        app_id=name.lower().replace(" ", "-"),
        display_name=name,
        lifecycle_class=lifecycle,
        user_facing_badge="x",
        consequence_classes=(),
        semantic_actions=(
            ("REPAIR_APPLICATION", "UNINSTALL_APPLICATION")
            if lifecycle
            in (
                AppLifecycleClass.ACTIVE_REQUIRED,
                AppLifecycleClass.BROKEN_REQUIRED,
            )
            else (("CLEAN_CACHE",) if lifecycle is AppLifecycleClass.CACHE_REGENERABLE else ())
        ),
        edges=(
            AppOwnershipEdge(
                edge_type="INSTALLED_AT",
                storage_path=path,
                owner_id=name,
                owner_display_name=name,
                evidence_source="test",
                confidence="strong",
            ),
        ),
        reasons=("synthetic app edge",),
        probes_attempted=("test",),
        safety_floor="PROTECTED",
    )


def _repo_record(root: str, lifecycle: RepoLifecycleClass) -> RepositoryAttribution:
    return RepositoryAttribution(
        root=root,
        lifecycle_class=lifecycle,
        safety_floor="PROTECTED_OR_KEEP",
        reasons=("synthetic repo",),
        evidence=RepositoryEvidence(
            root=root,
            clean_working_tree=True,
            has_staged=False,
            has_untracked=False,
            has_unpushed_or_unique_branch=False,
            remote_recoverable=True,
            is_current_worktree=False,
        ),
    )


def test_broken_app_beats_active_repo():
    path = r"C:\Shared\Tool"
    graph = build_ownership_graph(
        app_records=[
            _app_record(path, lifecycle=AppLifecycleClass.BROKEN_REQUIRED, name="Wispr")
        ],
        repo_records=[_repo_record(path, RepoLifecycleClass.REPO_ACTIVE)],
    )
    judgment = reduce_path_ownership(path, graph)
    assert judgment.user_facing_badge == "Broken app dependency"
    assert judgment.disposition is CleanupDisposition.PROTECTED
    assert judgment.simultaneous_owners is True
    assert "Wispr" in judgment.owners


def test_active_app_protects_over_legacy_repo_candidate():
    path = r"C:\Shared\OldClone"
    graph = build_ownership_graph(
        app_records=[
            _app_record(path, lifecycle=AppLifecycleClass.ACTIVE_REQUIRED, name="Tool")
        ],
        repo_records=[
            _repo_record(path, RepoLifecycleClass.REPO_LEGACY_CANDIDATE)
        ],
    )
    judgment = reduce_path_ownership(path, graph)
    assert judgment.user_facing_badge == "Required by app"
    assert judgment.disposition is CleanupDisposition.PROTECTED
    assert judgment.disposition is not CleanupDisposition.RECLAIM_PROVEN


def test_unknown_fails_closed_after_adapter_exhaustion():
    graph = build_ownership_graph()
    judgment = reduce_path_ownership(
        r"C:\Mystery",
        graph,
        adapters_exhausted=True,
    )
    assert judgment.user_facing_badge == "Unknown ownership"
    assert judgment.disposition is CleanupDisposition.HUMAN_REVIEW
    assert judgment.unknown is True
    assert "disposability" in judgment.depends_on_reasons[0]


def test_legacy_repo_candidate_is_operator_decision_not_reclaim():
    path = r"C:\Repos\OldPrototype"
    graph = build_ownership_graph(
        repo_records=[
            _repo_record(path, RepoLifecycleClass.REPO_LEGACY_CANDIDATE)
        ],
    )
    judgment = reduce_path_ownership(path, graph)
    assert judgment.user_facing_badge == "Legacy repo candidate"
    assert judgment.disposition is CleanupDisposition.HUMAN_REVIEW
    assert judgment.disposition is not CleanupDisposition.RECLAIM_PROVEN


def test_reducer_never_emits_reclaim_proven():
    path = r"C:\Cache\Demo"
    graph = build_ownership_graph(
        app_records=[
            _app_record(path, lifecycle=AppLifecycleClass.CACHE_REGENERABLE)
        ],
    )
    judgment = reduce_path_ownership(path, graph)
    assert judgment.disposition is not CleanupDisposition.RECLAIM_PROVEN
    assert judgment.user_facing_badge == "Regenerable cache"
