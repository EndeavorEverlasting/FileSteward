"""F3 deterministic treemap geometry proofs."""

from __future__ import annotations

import pytest

from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    ScanCompleteness,
)
from filesteward.visualization.contracts import PresentationNode
from filesteward.visualization.treemap import layout_treemap


def _node(node_id: str, logical: int | None) -> PresentationNode:
    return PresentationNode(
        node_id=node_id,
        parent_id=None,
        display_name=node_id,
        path=f"C:\\synthetic\\{node_id}",
        entry_type="DIRECTORY",
        logical_size_bytes=logical,
        allocated_size_bytes=logical,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=CleanupDisposition.HUMAN_REVIEW,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=ScanCompleteness.COMPLETE,
        protection_relation="UNRELATED",
        reason="fixture",
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="n/a",
        next_gate="n/a",
        trace_evidence_source="fixture",
    )


def _area(rect) -> float:
    return rect.width * rect.height


def test_determinism_and_tiebreak() -> None:
    nodes = (
        _node("b", 50),
        _node("a", 50),
        _node("c", 100),
    )
    first = layout_treemap(nodes)
    second = layout_treemap(nodes)
    assert first == second
    assert [r.node_id for r in first][0] == "c"
    # Equal 50s ordered by node_id: a before b in sort key (-size, id)
    ids = [r.node_id for r in first]
    assert ids.index("a") < ids.index("b")


def test_no_negative_or_overlap_and_covers() -> None:
    nodes = tuple(_node(f"n{i}", size) for i, size in enumerate((40, 30, 20, 10), start=1))
    rects = layout_treemap(nodes, width=100, height=100)
    assert rects
    for rect in rects:
        assert rect.width >= 0
        assert rect.height >= 0
    # Pairwise interior overlap check (edges may touch).
    for i, a in enumerate(rects):
        for b in rects[i + 1 :]:
            ax2, ay2 = a.x + a.width, a.y + a.height
            bx2, by2 = b.x + b.width, b.y + b.height
            overlap_x = min(ax2, bx2) - max(a.x, b.x)
            overlap_y = min(ay2, by2) - max(a.y, b.y)
            assert overlap_x <= 1e-9 or overlap_y <= 1e-9
    total = sum(_area(r) for r in rects)
    assert abs(total - 10_000.0) < 1e-6


def test_zero_and_none_sizes_omitted() -> None:
    nodes = (
        _node("keep", 100),
        _node("zero", 0),
        _node("missing", None),
    )
    rects = layout_treemap(nodes)
    assert [r.node_id for r in rects] == ["keep"]


def test_empty_input() -> None:
    assert layout_treemap(()) == ()


def test_layout_is_scale_invariant_for_realistic_byte_weights() -> None:
    small = tuple(
        _node(node_id, size)
        for node_id, size in (("a", 40), ("b", 30), ("c", 20), ("d", 10))
    )
    large = tuple(
        _node(node_id, size * 1_000_000_000)
        for node_id, size in (("a", 40), ("b", 30), ("c", 20), ("d", 10))
    )
    small_rects = layout_treemap(small, width=100, height=100)
    large_rects = layout_treemap(large, width=100, height=100)
    assert [r.node_id for r in small_rects] == [r.node_id for r in large_rects]
    for left, right in zip(small_rects, large_rects):
        assert left.x == pytest.approx(right.x)
        assert left.y == pytest.approx(right.y)
        assert left.width == pytest.approx(right.width)
        assert left.height == pytest.approx(right.height)
