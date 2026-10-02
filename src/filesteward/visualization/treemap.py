"""Deterministic squarified treemap layout (Bruls et al.).

F3 owns geometry only. Size comes from structured presentation fields;
this module never invents bytes or evidence.
"""

from __future__ import annotations

from typing import Optional, Protocol, Sequence

from filesteward.visualization.contracts import PresentationNode, TreemapRect

__all__ = ["layout_treemap"]


class _Sized(Protocol):
    node_id: str
    logical_size_bytes: Optional[int]
    allocated_size_bytes: Optional[int]


def _size_of(node: _Sized, size_attr: str) -> Optional[int]:
    value = getattr(node, size_attr, None)
    if value is None:
        return None
    return int(value)


def _worst(row: Sequence[tuple[str, float]], length: float) -> float:
    if not row or length <= 0:
        return float("inf")
    sizes = [size for _, size in row]
    total = sum(sizes)
    if total <= 0:
        return float("inf")
    max_s = max(sizes)
    min_s = min(sizes)
    s2 = total * total
    return max((length * length * max_s) / s2, s2 / (length * length * min_s))


def _layout_row(
    row: Sequence[tuple[str, float]],
    x: float,
    y: float,
    width: float,
    height: float,
    horizontal: bool,
) -> list[TreemapRect]:
    total = sum(size for _, size in row)
    if total <= 0:
        return []
    rects: list[TreemapRect] = []
    offset = 0.0
    if horizontal:
        for node_id, size in row:
            span = width * (size / total)
            rects.append(
                TreemapRect(
                    node_id=node_id,
                    x=x + offset,
                    y=y,
                    width=span,
                    height=height,
                )
            )
            offset += span
    else:
        for node_id, size in row:
            span = height * (size / total)
            rects.append(
                TreemapRect(
                    node_id=node_id,
                    x=x,
                    y=y + offset,
                    width=width,
                    height=span,
                )
            )
            offset += span
    return rects


def _squarify(
    items: Sequence[tuple[str, float]],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[TreemapRect]:
    if not items:
        return []
    if len(items) == 1:
        node_id, _ = items[0]
        return [
            TreemapRect(node_id=node_id, x=x, y=y, width=width, height=height)
        ]

    total = sum(size for _, size in items)
    if total <= 0 or width <= 0 or height <= 0:
        return []

    horizontal = width >= height
    length = height if horizontal else width
    row: list[tuple[str, float]] = []
    remaining = list(items)
    rects: list[TreemapRect] = []

    while remaining:
        node = remaining[0]
        trial = row + [node]
        if row and _worst(trial, length) > _worst(row, length):
            row_total = sum(size for _, size in row)
            fraction = row_total / total
            if horizontal:
                row_height = height * fraction
                rects.extend(_layout_row(row, x, y, width, row_height, True))
                y += row_height
                height -= row_height
            else:
                row_width = width * fraction
                rects.extend(_layout_row(row, x, y, row_width, height, False))
                x += row_width
                width -= row_width
            total -= row_total
            row = []
            horizontal = width >= height
            length = height if horizontal else width
            continue
        row = trial
        remaining = remaining[1:]

    if row:
        rects.extend(_layout_row(row, x, y, width, height, horizontal))
    return rects


def layout_treemap(
    nodes: Sequence[PresentationNode] | Sequence[_Sized],
    *,
    width: float = 100.0,
    height: float = 100.0,
    size_attr: str = "logical_size_bytes",
) -> tuple[TreemapRect, ...]:
    """Return deterministic rectangles covering ``width`` x ``height``.

    Nodes with missing or non-positive ``size_attr`` are omitted from the
    area layout (they remain available via the navigator). Equal sizes are
    ordered by ``node_id`` for stable ties.
    """

    if width < 0 or height < 0:
        raise ValueError("treemap width/height must be non-negative")
    if not nodes:
        return ()

    sized: list[tuple[str, float]] = []
    for node in nodes:
        raw = _size_of(node, size_attr)
        if raw is None or raw <= 0:
            continue
        sized.append((node.node_id, float(raw)))

    sized.sort(key=lambda item: (-item[1], item[0]))
    return tuple(_squarify(sized, 0.0, 0.0, width, height))
