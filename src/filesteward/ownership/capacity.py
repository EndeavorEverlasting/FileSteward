"""Deterministic capacity prioritization, separate from mutation authority."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

CapacityReader = Callable[[Path], tuple[int, int]]


def read_capacity(path: Path) -> tuple[int, int]:
    usage = shutil.disk_usage(path)
    return int(usage.total), int(usage.free)


def capacity_stop_reason(path: Path, reader: CapacityReader) -> tuple[str, str]:
    try:
        total, free = reader(path)
        strategy = plan_capacity_strategy((), total_bytes=total, free_bytes=free)
    except Exception as exc:
        return "CAPACITY_UNKNOWN", f"current capacity measurement unavailable ({type(exc).__name__})"
    if strategy.status == "HEALTHY":
        return "CAPACITY_HEALTHY", "current measured capacity reached the 20% healthy target"
    return "", "current capacity remains below the healthy target"

from dataclasses import dataclass
from typing import Iterable

from filesteward.models import CleanupDisposition
from filesteward.ownership._windows_paths import normalize_path_key, path_intersects
from filesteward.ownership.actions import ActionKind, ActionPlan


@dataclass(frozen=True)
class CapacityCandidate:
    candidate_id: str
    plan: ActionPlan
    action: ActionKind
    projected_reclaim_bytes: int | None = None
    reclaim_basis: str = "unknown"
    friction: int = 0
    reclaim_group_id: str = ""


@dataclass(frozen=True)
class CapacityStrategy:
    status: str
    target_free_bytes: int
    shortfall_bytes: int
    candidates: tuple[CapacityCandidate, ...]
    projected_free_bytes: int
    projection_basis: str = "estimate"


_TIERS = {
    ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT: 0,
    ActionKind.CLEAN_CACHE: 1,
    ActionKind.CLEAN_GENERATED_OUTPUT: 2,
    ActionKind.UNINSTALL_APPLICATION: 3,
    ActionKind.ARCHIVE_OR_REMOVE_REPOSITORY: 4,
}


def _legal(candidate: CapacityCandidate) -> bool:
    plan = candidate.plan
    if (plan.disposition not in {CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.HUMAN_REVIEW}
            or candidate.action not in plan.actions or candidate.action not in _TIERS
            or not candidate.candidate_id or not normalize_path_key(plan.path)
            or not plan.owner_ids or not plan.graph_revision_id or not plan.evidence_digest):
        return False
    if candidate.action is ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT:
        return plan.raw_delete_eligible and bool(plan.regeneration_digest)
    if candidate.action in {ActionKind.CLEAN_CACHE, ActionKind.CLEAN_GENERATED_OUTPUT}:
        return bool(plan.regeneration_digest)
    # Value decisions remain choices; they never authorize automatic deletion.
    return True


def _projection(candidate: CapacityCandidate) -> int:
    amount = candidate.projected_reclaim_bytes
    if (type(amount) is not int or amount < 0 or candidate.reclaim_basis == "unknown"
            or not candidate.reclaim_basis.strip()):
        return 0
    return amount


def _container(candidate: CapacityCandidate) -> bool:
    return candidate.projected_reclaim_bytes == 0 and candidate.reclaim_basis == "container-row"


def plan_capacity_strategy(
    candidates: Iterable[CapacityCandidate], *, total_bytes: int, free_bytes: int,
) -> CapacityStrategy:
    """Rank admitted owner actions and stop at a measured/projected healthy target.

    Measurement is supplied by the caller; this pure planner never observes a
    drive. Projections are estimates, never verified reclaim or authorization.
    Overlapping paths and supplied allocation groups count only once.
    """
    if (type(total_bytes) is not int or type(free_bytes) is not int
            or total_bytes <= 0 or free_bytes < 0 or free_bytes > total_bytes):
        raise ValueError("capacity requires 0 <= free_bytes <= positive total_bytes")
    target = (total_bytes + 4) // 5
    shortfall = max(0, target - free_bytes)
    status = "HEALTHY" if not shortfall else ("CRITICAL" if free_bytes * 10 < total_bytes else "LOW")
    if not shortfall:
        return CapacityStrategy(status, target, 0, (), free_bytes)
    legal = sorted((c for c in candidates if _legal(c)), key=lambda c: (
        _TIERS[c.action], -_projection(c), max(0, c.friction),
        normalize_path_key(c.plan.path), c.candidate_id, c.action.value,
    ))
    selected: list[CapacityCandidate] = []
    groups: set[str] = set()
    ids: set[str] = set()
    projected = free_bytes
    for candidate in legal:
        if projected >= target:
            break
        if (candidate.candidate_id in ids
                or (candidate.reclaim_group_id and candidate.reclaim_group_id in groups)
                or any(path_intersects(candidate.plan.path, c.plan.path)
                       and not _container(candidate) and not _container(c) for c in selected)):
            continue
        selected.append(candidate)
        ids.add(candidate.candidate_id)
        if candidate.reclaim_group_id:
            groups.add(candidate.reclaim_group_id)
        projected = min(total_bytes, projected + _projection(candidate))
    return CapacityStrategy(status, target, shortfall, tuple(selected), projected)
