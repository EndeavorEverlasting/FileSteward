"""J4 ownership graph assembly tests."""

from __future__ import annotations

from filesteward.ownership.graph import build_ownership_graph
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


def _app(path: str) -> AppOwnershipRecord:
    return AppOwnershipRecord(
        app_id="demo",
        display_name="Demo App",
        lifecycle_class=AppLifecycleClass.ACTIVE_REQUIRED,
        user_facing_badge="Required by app",
        consequence_classes=("APP_SERVICEABILITY_DEPENDENCY",),
        semantic_actions=("UNINSTALL_APPLICATION",),
        edges=(
            AppOwnershipEdge(
                edge_type="INSTALLED_AT",
                storage_path=path,
                owner_id="demo",
                owner_display_name="Demo App",
                evidence_source="uninstall_registration",
                confidence="strong",
            ),
        ),
        reasons=("registered install",),
        probes_attempted=("uninstall_registration",),
        safety_floor="PROTECTED",
    )


def _repo(root: str, lifecycle: RepoLifecycleClass) -> RepositoryAttribution:
    evidence = RepositoryEvidence(
        root=root,
        clean_working_tree=lifecycle is not RepoLifecycleClass.REPO_ACTIVE,
        has_staged=False,
        has_untracked=lifecycle is RepoLifecycleClass.REPO_ACTIVE,
        has_unpushed_or_unique_branch=False,
        remote_recoverable=True,
        is_current_worktree=False,
    )
    return RepositoryAttribution(
        root=root,
        lifecycle_class=lifecycle,
        safety_floor="PROTECTED_OR_KEEP"
        if lifecycle is RepoLifecycleClass.REPO_ACTIVE
        else "OPERATOR_VALUE_DECISION",
        reasons=("synthetic",),
        evidence=evidence,
    )


def test_graph_revision_stable_for_same_inputs():
    path = r"C:\Apps\Demo"
    g1 = build_ownership_graph(app_records=[_app(path)])
    g2 = build_ownership_graph(app_records=[_app(path)])
    assert g1.revision.revision_id == g2.revision.revision_id
    assert g1.revision.edge_count == 1


def test_graph_preserves_simultaneous_app_and_repo_edges():
    shared = r"C:\Shared\Tool"
    graph = build_ownership_graph(
        app_records=[_app(shared)],
        repo_records=[_repo(shared, RepoLifecycleClass.REPO_ACTIVE)],
    )
    kinds = {e.owner_kind for e in graph.edges_for_path(shared)}
    assert kinds == {"APPLICATION", "REPOSITORY"}
    assert graph.revision.app_record_count == 1
    assert graph.revision.repo_record_count == 1
