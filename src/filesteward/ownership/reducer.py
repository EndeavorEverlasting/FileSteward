"""Most-protective-edge-wins ownership reducer (J4).

Consumes the cross-domain graph and produces user-facing classification
plus CleanupDisposition floors. Never authorizes mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from filesteward.models import CleanupDisposition
from filesteward.ownership.graph import OwnershipGraph
from filesteward.ownership.repository import RepoLifecycleClass
from filesteward.ownership.windows_app import AppLifecycleClass

__all__ = [
    "PathOwnershipJudgment",
    "USER_FACING_BADGES",
    "reduce_path_ownership",
]


USER_FACING_BADGES = (
    "Broken app dependency",
    "Required by app",
    "Part of active repo",
    "Shared dependency",
    "Stable repo",
    "Legacy repo candidate",
    "Regenerable cache",
    "User data",
    "Unknown ownership",
)


@dataclass(frozen=True)
class PathOwnershipJudgment:
    path: str
    user_facing_badge: str
    disposition: CleanupDisposition
    safety_floor: str
    owners: tuple[str, ...]
    depends_on_reasons: tuple[str, ...]
    lifecycle_labels: tuple[str, ...]
    semantic_actions: tuple[str, ...]
    graph_revision_id: str
    simultaneous_owners: bool
    unknown: bool


_BADGE_RANK = {
    "Broken app dependency": 900,
    "Required by app": 800,
    "Part of active repo": 700,
    "Shared dependency": 650,
    "Stable repo": 500,
    "Legacy repo candidate": 400,
    "Regenerable cache": 300,
    "User data": 250,
    "Unknown ownership": 100,
}

_DISPOSITION_RANK = {
    CleanupDisposition.PROTECTED: 400,
    CleanupDisposition.KEEP_PROVEN: 350,
    CleanupDisposition.HUMAN_REVIEW: 300,
    CleanupDisposition.UNKNOWN: 200,
    CleanupDisposition.RECLAIM_PROVEN: 100,
}


def _most_protective_disposition(
    candidates: Sequence[CleanupDisposition],
) -> CleanupDisposition:
    if not candidates:
        return CleanupDisposition.UNKNOWN
    return max(candidates, key=lambda d: _DISPOSITION_RANK[d])


def _app_badge_and_disposition(
    lifecycle: str,
) -> tuple[str, CleanupDisposition, str, tuple[str, ...]]:
    if lifecycle == AppLifecycleClass.BROKEN_REQUIRED.value:
        return (
            "Broken app dependency",
            CleanupDisposition.PROTECTED,
            "PROTECTED",
            ("REPAIR_APPLICATION", "UNINSTALL_APPLICATION"),
        )
    if lifecycle == AppLifecycleClass.ACTIVE_REQUIRED.value:
        return (
            "Required by app",
            CleanupDisposition.PROTECTED,
            "PROTECTED",
            ("REPAIR_APPLICATION", "UNINSTALL_APPLICATION"),
        )
    if lifecycle == AppLifecycleClass.CACHE_REGENERABLE.value:
        return (
            "Regenerable cache",
            CleanupDisposition.HUMAN_REVIEW,
            "SEMANTIC_CLEAN_ACTION_ONLY",
            ("CLEAN_CACHE",),
        )
    if lifecycle == AppLifecycleClass.ORPHAN_CANDIDATE.value:
        return (
            "Unknown ownership",
            CleanupDisposition.HUMAN_REVIEW,
            "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION",
            (),
        )
    return ("Unknown ownership", CleanupDisposition.UNKNOWN, "UNKNOWN", ())


def _repo_badge_and_disposition(
    lifecycle: str,
) -> tuple[str, CleanupDisposition, str, tuple[str, ...]]:
    if lifecycle == RepoLifecycleClass.REPO_ACTIVE.value:
        return (
            "Part of active repo",
            CleanupDisposition.PROTECTED,
            "PROTECTED_OR_KEEP",
            (),
        )
    if lifecycle == RepoLifecycleClass.REPO_STABLE.value:
        return (
            "Stable repo",
            CleanupDisposition.HUMAN_REVIEW,
            "OPERATOR_VALUE_DECISION",
            (),
        )
    if lifecycle == RepoLifecycleClass.REPO_LEGACY_CANDIDATE.value:
        return (
            "Legacy repo candidate",
            CleanupDisposition.HUMAN_REVIEW,
            "OPERATOR_VALUE_DECISION",
            (),
        )
    if lifecycle == RepoLifecycleClass.REPO_GENERATED_OUTPUT.value:
        return (
            "Regenerable cache",
            CleanupDisposition.HUMAN_REVIEW,
            "RECLAIM_ONLY_AFTER_REGENERATION_PROOF",
            (),
        )
    return ("Unknown ownership", CleanupDisposition.UNKNOWN, "UNKNOWN", ())


def reduce_path_ownership(
    path: str,
    graph: OwnershipGraph,
    *,
    adapters_exhausted: bool = False,
) -> PathOwnershipJudgment:
    """Reduce all matching edges; most protective current dependency wins."""

    matching = graph.edges_for_path(path)
    badges: list[str] = []
    dispositions: list[CleanupDisposition] = []
    floors: list[str] = []
    owners: list[str] = []
    reasons: list[str] = []
    lifecycles: list[str] = []
    actions: list[str] = []

    app_hits = [
        e for e in matching if e.owner_kind == "APPLICATION" and e.lifecycle_hint
    ]
    repo_hits = [
        e for e in matching if e.owner_kind == "REPOSITORY" and e.lifecycle_hint
    ]

    for edge in app_hits:
        badge, disp, floor, acts = _app_badge_and_disposition(edge.lifecycle_hint)
        badges.append(badge)
        dispositions.append(disp)
        floors.append(floor)
        owners.append(edge.owner_display_name or edge.owner_id)
        lifecycles.append(edge.lifecycle_hint)
        actions.extend(acts)
        reasons.append(
            f"{edge.owner_display_name or edge.owner_id} ({edge.edge_type})"
        )

    for edge in repo_hits:
        badge, disp, floor, acts = _repo_badge_and_disposition(edge.lifecycle_hint)
        badges.append(badge)
        dispositions.append(disp)
        floors.append(floor)
        owners.append(edge.owner_display_name or edge.owner_id)
        lifecycles.append(edge.lifecycle_hint)
        actions.extend(acts)
        reasons.append(
            f"repository {edge.owner_display_name or edge.owner_id} "
            f"({edge.lifecycle_hint})"
        )

    # Shared when both app and repo (or multiple distinct owners) bind the path.
    distinct_owners = tuple(dict.fromkeys(owners))
    simultaneous = len(distinct_owners) > 1 or (
        bool(app_hits) and bool(repo_hits)
    )
    if simultaneous and "Shared dependency" not in badges:
        # Shared is an explanatory badge; protective app/repo badges still win rank.
        badges.append("Shared dependency")
        reasons.append(
            "Multiple owners currently depend on these bytes; "
            "most protective dependency wins."
        )

    if not matching:
        unknown = True
        badge = "Unknown ownership"
        if adapters_exhausted:
            disp = CleanupDisposition.HUMAN_REVIEW
            floor = "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION"
            reasons = (
                "Safe attribution adapters found no owner; "
                "absence of ownership is not disposability.",
            )
        else:
            disp = CleanupDisposition.UNKNOWN
            floor = "UNKNOWN"
            reasons = ("Ownership has not been fully resolved for this path.",)
        return PathOwnershipJudgment(
            path=path,
            user_facing_badge=badge,
            disposition=disp,
            safety_floor=floor,
            owners=(),
            depends_on_reasons=reasons,
            lifecycle_labels=(),
            semantic_actions=(),
            graph_revision_id=graph.revision.revision_id,
            simultaneous_owners=False,
            unknown=unknown,
        )

    badge = max(badges, key=lambda b: _BADGE_RANK.get(b, 0))
    # Prefer Broken/Required/Active over Shared when both present.
    if badge == "Shared dependency" and any(
        b in badges
        for b in (
            "Broken app dependency",
            "Required by app",
            "Part of active repo",
        )
    ):
        badge = max(
            (
                b
                for b in badges
                if b
                in (
                    "Broken app dependency",
                    "Required by app",
                    "Part of active repo",
                    "Shared dependency",
                )
            ),
            key=lambda b: _BADGE_RANK.get(b, 0),
        )

    disposition = _most_protective_disposition(dispositions)
    # Never allow RECLAIM_PROVEN from this reducer — reclaim requires regeneration proof elsewhere.
    if disposition is CleanupDisposition.RECLAIM_PROVEN:
        disposition = CleanupDisposition.HUMAN_REVIEW

    floor = floors[0] if floors else "UNKNOWN"
    # Prefer the floor belonging to the winning badge's domain.
    for edge in list(app_hits) + list(repo_hits):
        b, d, f, _a = (
            _app_badge_and_disposition(edge.lifecycle_hint)
            if edge.owner_kind == "APPLICATION"
            else _repo_badge_and_disposition(edge.lifecycle_hint)
        )
        if b == badge:
            floor = f
            break

    return PathOwnershipJudgment(
        path=path,
        user_facing_badge=badge,
        disposition=disposition,
        safety_floor=floor,
        owners=distinct_owners,
        depends_on_reasons=tuple(dict.fromkeys(reasons)),
        lifecycle_labels=tuple(dict.fromkeys(lifecycles)),
        semantic_actions=tuple(dict.fromkeys(actions)),
        graph_revision_id=graph.revision.revision_id,
        simultaneous_owners=simultaneous,
        unknown=False,
    )
