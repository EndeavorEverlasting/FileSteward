"""F0 presentation and shell contracts consumed by F1/F2/F3.

These shapes freeze the seam. F1 fills PresentationNode from validated
artifacts without prose parsing. F2 renders. F3 lays out rectangles.
Nothing here mutates evidence or authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness

__all__ = [
    "GateStep",
    "GateStepStatus",
    "PresentationModel",
    "PresentationNode",
    "ShellMetrics",
    "TreemapRect",
    "ViewportMode",
]


class ViewportMode(str, Enum):
    """Responsive shell mode. Display only."""

    WIDE = "wide"
    STANDARD = "standard"
    MEDIUM = "medium"
    NARROW = "narrow"


class GateStepStatus(str, Enum):
    """Decision-trace step presentation status."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"
    WAITING = "WAITING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class GateStep:
    """One structured decision-trace row. Must come from persisted fields."""

    gate_id: str
    name: str
    status: GateStepStatus
    explanation: str
    is_first_unresolved: bool = False

    def __post_init__(self) -> None:
        if not self.gate_id:
            raise ValueError("gate_id must be non-empty")
        if not self.name:
            raise ValueError("gate name must be non-empty")


@dataclass(frozen=True)
class PresentationNode:
    """Immutable display facts for one storage group or item.

    F1 constructs these. Viewers must not reclassify or invent gate facts.
    """

    node_id: str
    parent_id: Optional[str]
    display_name: str
    path: str
    entry_type: str
    logical_size_bytes: Optional[int]
    allocated_size_bytes: Optional[int]
    projected_reclaim_bytes: Optional[int]
    reclaim_basis: Optional[str]
    projection_quality: Optional[str]
    disposition: CleanupDisposition
    authorization_state: AuthorizationState
    scan_completeness: ScanCompleteness
    protection_relation: str
    reason: str
    contract_summary: Optional[str]
    contract_hint_tags: tuple[str, ...]
    risk_if_acted_on: str
    next_gate: str
    trace_evidence_source: str
    item_count: Optional[int] = None
    gate_steps: tuple[GateStep, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("node_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if not self.path:
            raise ValueError("path must be non-empty")
        for name in (
            "logical_size_bytes",
            "allocated_size_bytes",
            "projected_reclaim_bytes",
            "item_count",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0 when present")


@dataclass(frozen=True)
class TreemapRect:
    """Geometry produced by F3. F0/F2 consume coordinates only."""

    node_id: str
    x: float
    y: float
    width: float
    height: float
    depth: int = 0

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("node_id must be non-empty")
        if self.width < 0 or self.height < 0:
            raise ValueError("treemap dimensions must be non-negative")


@dataclass(frozen=True)
class ShellMetrics:
    """Footer/metrics strip facts. Projection quality stays visible."""

    observed_storage_label: str
    free_space_label: str
    projected_reclaim_label: str
    projected_reclaim_quality: Optional[str]
    target_free_space_label: str
    authorization_label: str


@dataclass(frozen=True)
class PresentationModel:
    """Immutable presentation graph for one validated run."""

    run_id: str
    nodes: tuple[PresentationNode, ...]
    metrics: ShellMetrics
    root_ids: tuple[str, ...] = ()
    default_selected_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.nodes:
            raise ValueError("presentation model has no nodes")
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("presentation node_id values must be unique")
        if self.default_selected_id is not None and self.default_selected_id not in ids:
            raise ValueError("default_selected_id must reference a node")
        object.__setattr__(
            self,
            "root_ids",
            self.root_ids
            or tuple(n.node_id for n in self.nodes if n.parent_id is None),
        )

    def by_id(self) -> dict[str, PresentationNode]:
        return {node.node_id: node for node in self.nodes}
