"""Cross-domain ownership evidence graph (J4).

A path may carry simultaneous application, repository, toolchain, and
user-data edges. This module normalizes those edges; it does not delete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from filesteward.ownership.repository import RepositoryAttribution
from filesteward.ownership.windows_app import AppOwnershipRecord, PathAttribution

__all__ = [
    "OwnershipEdge",
    "OwnershipGraph",
    "OwnershipGraphRevision",
    "build_ownership_graph",
]


@dataclass(frozen=True)
class OwnershipEdge:
    edge_type: str
    storage_path: str
    owner_kind: str
    owner_id: str
    owner_display_name: str
    evidence_source: str
    confidence: str
    lifecycle_hint: str = ""
    detail: str = ""


@dataclass(frozen=True)
class OwnershipGraphRevision:
    """Immutable revision identity for deletion/preflight binding (J5)."""

    revision_id: str
    edge_count: int
    app_record_count: int
    repo_record_count: int


@dataclass(frozen=True)
class OwnershipGraph:
    edges: tuple[OwnershipEdge, ...]
    app_records: tuple[AppOwnershipRecord, ...] = ()
    repo_records: tuple[RepositoryAttribution, ...] = ()
    path_attributions: tuple[PathAttribution, ...] = ()
    revision: OwnershipGraphRevision = field(
        default_factory=lambda: OwnershipGraphRevision(
            revision_id="empty",
            edge_count=0,
            app_record_count=0,
            repo_record_count=0,
        )
    )

    def edges_for_path(self, path: str) -> tuple[OwnershipEdge, ...]:
        from filesteward.ownership._windows_paths import path_intersects

        return tuple(e for e in self.edges if path_intersects(path, e.storage_path))


def _revision_id(
    edges: Sequence[OwnershipEdge],
    apps: Sequence[AppOwnershipRecord],
    repos: Sequence[RepositoryAttribution],
) -> str:
    import hashlib

    parts = [
        f"{e.edge_type}|{e.storage_path}|{e.owner_kind}|{e.owner_id}|{e.lifecycle_hint}"
        for e in edges
    ]
    parts.extend(f"app|{r.app_id}|{r.lifecycle_class.value}" for r in apps)
    parts.extend(f"repo|{r.root}|{r.lifecycle_class.value}" for r in repos)
    digest = hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()
    return f"own-graph-{digest[:16]}"


def build_ownership_graph(
    *,
    app_records: Sequence[AppOwnershipRecord] = (),
    repo_records: Sequence[RepositoryAttribution] = (),
    path_attributions: Sequence[PathAttribution] = (),
    extra_edges: Sequence[OwnershipEdge] = (),
) -> OwnershipGraph:
    """Assemble a revisioned graph from J2/J3 normalized records."""

    edges: list[OwnershipEdge] = list(extra_edges)
    for record in app_records:
        for edge in record.edges:
            edges.append(
                OwnershipEdge(
                    edge_type=edge.edge_type,
                    storage_path=edge.storage_path,
                    owner_kind="APPLICATION",
                    owner_id=edge.owner_id,
                    owner_display_name=edge.owner_display_name,
                    evidence_source=edge.evidence_source,
                    confidence=edge.confidence,
                    lifecycle_hint=record.lifecycle_class.value,
                    detail=edge.detail,
                )
            )
    for repo in repo_records:
        edges.append(
            OwnershipEdge(
                edge_type="REPO_CONTAINS",
                storage_path=repo.root,
                owner_kind="REPOSITORY",
                owner_id=repo.root,
                owner_display_name=repo.root,
                evidence_source="git_repository",
                confidence="strong",
                lifecycle_hint=repo.lifecycle_class.value,
                detail=";".join(repo.reasons[:3]),
            )
        )

    revision = OwnershipGraphRevision(
        revision_id=_revision_id(edges, app_records, repo_records),
        edge_count=len(edges),
        app_record_count=len(app_records),
        repo_record_count=len(repo_records),
    )
    return OwnershipGraph(
        edges=tuple(edges),
        app_records=tuple(app_records),
        repo_records=tuple(repo_records),
        path_attributions=tuple(path_attributions),
        revision=revision,
    )
