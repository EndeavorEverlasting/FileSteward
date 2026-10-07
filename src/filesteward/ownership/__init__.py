"""Ownership attribution package.

J4 owns the public graph/reducer surface. J2/J3 adapter modules remain
importable for construction of normalized app/repo evidence.
"""

from __future__ import annotations

from filesteward.ownership.graph import (
    OwnershipEdge,
    OwnershipGraph,
    OwnershipGraphRevision,
    build_ownership_graph,
)
from filesteward.ownership.reducer import (
    PathOwnershipJudgment,
    reduce_path_ownership,
)

__all__ = [
    "OwnershipEdge",
    "OwnershipGraph",
    "OwnershipGraphRevision",
    "PathOwnershipJudgment",
    "build_ownership_graph",
    "reduce_path_ownership",
]
