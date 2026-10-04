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


def render_focus_chamber(
    node: Optional[PresentationNode],
    nodes: Sequence[PresentationNode],
) -> str:
    if node is None:
        return '<div class="focus-empty">No sector selected.</div>'
    rank = _rank_for(node, nodes)
    tone = disposition_css_stem(node.disposition)
    item_count = f"{node.item_count:,}" if node.item_count is not None else "?"
    return f"""
<article class="focus-chamber state-edge-{escape_attr(tone)}"
         data-focus-node="{escape_attr(node.node_id)}">
  <div class="focus-coordinate">
    <span>STORAGE SECTOR</span>
    <strong>S{rank:03d}</strong>
  </div>
  <div class="focus-identity">
    <h3>{escape_text(node.display_name)}</h3>
    <strong class="focus-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</strong>
    <p class="focus-path mono">{escape_text(node.path)}</p>
  </div>
  <div class="focus-facts">
    <span class="state state-{escape_attr(tone)}">{escape_text(_state_label(node))}</span>
    <span>{escape_text(node.authorization_state.value.replace("_", " "))}</span>
    <span>{escape_text(item_count)} items</span>
  </div>
  <div class="focus-gate">
    <span>NEXT GATE</span>
    <strong>{escape_text(node.next_gate)}</strong>
  </div>
  <div class="focus-caption">
    Read-only evidence chamber · size is magnitude, never permission
  </div>
</article>
"""


def render_focus_templates(nodes: Sequence[PresentationNode]) -> str:
    return "".join(
        f'<template data-focus-for="{escape_attr(node.node_id)}">'
        f"{render_focus_chamber(node, nodes)}"
        "</template>"
        for node in nodes
    )


def render_substrate_svg() -> str:
    """Decorative hardware/substrate trace field. It carries no data meaning."""

    return """
<svg class="storage-substrate" viewBox="0 0 1200 700"
     preserveAspectRatio="none" aria-hidden="true">
  <g class="substrate-gridlines">
    <path d="M40 90H310L360 140H690L740 90H1160"/>
    <path d="M0 250H220L280 310H520L590 240H930L1010 320H1200"/>
    <path d="M70 610H330L400 540H760L830 610H1130"/>
    <path d="M180 0V100L240 160V410L180 470V700"/>
    <path d="M1010 0V130L950 190V490L1010 550V700"/>
    <path d="M570 0V90L620 140V560L570 610V700"/>
  </g>
  <g class="substrate-nodes">
    <circle cx="360" cy="140" r="4"/><circle cx="740" cy="90" r="4"/>
    <circle cx="280" cy="310" r="4"/><circle cx="590" cy="240" r="4"/>
    <circle cx="1010" cy="320" r="4"/><circle cx="400" cy="540" r="4"/>
    <circle cx="830" cy="610" r="4"/><circle cx="620" cy="140" r="4"/>
  </g>
</svg>
"""
