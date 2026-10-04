"""Cinematic storage-atlas presentation helpers.

Presentation-only overview/focus state for the offline report.
Never classifies evidence, grants authorization, or mutates receipt data.
"""

from __future__ import annotations

from typing import Optional, Sequence

from filesteward.visualization.contracts import PresentationNode
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.tokens import disposition_css_stem

__all__ = [
    "OVERVIEW_LIMIT",
    "render_cinematic_css",
    "render_cinematic_script",
    "render_focus_chamber",
    "render_focus_templates",
    "render_sector_overview",
    "render_substrate_svg",
]

OVERVIEW_LIMIT = 12


def _fmt_bytes(value: Optional[int]) -> str:
    if value is None:
        return "not established"
    gib = value / (1024**3)
    if gib >= 10:
        return f"{gib:.1f} GiB"
    if gib >= 1:
        return f"{gib:.2f} GiB"
    mib = value / (1024**2)
    return f"{mib:.1f} MiB"


def _state_label(node: PresentationNode) -> str:
    return node.disposition.value.replace("_", " ")


def _sorted_nodes(nodes: Sequence[PresentationNode]) -> list[PresentationNode]:
    return sorted(
        nodes,
        key=lambda n: (
            n.logical_size_bytes is None,
            -(n.logical_size_bytes or 0),
            n.path.casefold(),
        ),
    )


def _sector_class(rank: int) -> str:
    if rank == 1:
        return " sector-major"
    if rank in (2, 3):
        return " sector-wide"
    return " sector-standard"


def render_sector_overview(
    nodes: Sequence[PresentationNode],
    selected_id: Optional[str],
    *,
    limit: int = OVERVIEW_LIMIT,
) -> str:
    """Render a bounded, readable first-frame overview from existing evidence."""

    ordered = _sorted_nodes(nodes)
    shown = ordered[:limit]
    omitted = ordered[limit:]
    known_omitted = sum(node.logical_size_bytes or 0 for node in omitted)

    cards: list[str] = []
    for rank, node in enumerate(shown, start=1):
        selected = " selected" if node.node_id == selected_id else ""
        current = ' aria-current="true"' if node.node_id == selected_id else ""
        tone = disposition_css_stem(node.disposition)
        aria = (
            f"Storage sector {rank}, {node.display_name}, "
            f"{_fmt_bytes(node.logical_size_bytes)}, {_state_label(node)}"
        )
        cards.append(
            f'<button type="button" class="sector-card{_sector_class(rank)}{selected} '
            f'state-edge-{escape_attr(tone)}" data-node-id="{escape_attr(node.node_id)}" '
            f'data-focus-on-select="true" data-sector-rank="{rank}" '
            f'aria-label="{escape_attr(aria)}"{current}>'
            f'<span class="sector-rank">S{rank:02d}</span>'
            f'<span class="sector-name">{escape_text(node.display_name)}</span>'
            f'<span class="sector-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="sector-state state state-{escape_attr(tone)}">'
            f'{escape_text(_state_label(node))}</span>'
            f'<span class="sector-path mono">{escape_text(node.path)}</span>'
            f"</button>"
        )

    remainder = ""
    if omitted:
        remainder = (
            '<div class="overview-remainder" role="note">'
            f"<strong>{len(omitted):,} smaller sectors</strong>"
            f"<span>{escape_text(_fmt_bytes(known_omitted))} known logical size "
            "collapsed from the first frame · use search or the navigator to dive directly</span>"
            "</div>"
        )

    return (
        '<section class="sector-overview" id="sector-overview" '
        'aria-label="Dominant storage sectors">'
        '<div class="overview-copy">'
        '<div><strong>Dominant sectors</strong>'
        f'<span>Top {len(shown)} of {len(ordered):,} evidence groups · '
        "readable overview, not action authority</span></div>"
        '<span class="overview-hint">Click a sector to dive · Esc returns</span>'
        "</div>"
        f'<div class="sector-grid">{"".join(cards)}</div>'
        f"{remainder}"
        "</section>"
    )


def _rank_for(node: PresentationNode, nodes: Sequence[PresentationNode]) -> int:
    for rank, candidate in enumerate(_sorted_nodes(nodes), start=1):
        if candidate.node_id == node.node_id:
            return rank
    return 0
