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


def render_cinematic_css() -> str:
    return r"""
/* P95 + Impeccable cinematic Memory Atlas: presentation only. */
.map-pane{position:relative;}
.storage-stage{position:relative;min-height:clamp(34rem,72vh,54rem);overflow:hidden;isolation:isolate;background:radial-gradient(110% 80% at 50% -10%,color-mix(in srgb,var(--fs-accent) 13%,transparent),transparent 58%),linear-gradient(180deg,color-mix(in srgb,var(--fs-bg-surface-2) 88%,#101c28 12%),var(--fs-bg-canvas));}
.storage-stage::before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.36;background-image:linear-gradient(color-mix(in srgb,var(--fs-border-subtle) 42%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--fs-border-subtle) 42%,transparent) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,black,transparent 88%);}
.storage-substrate{position:absolute;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.18;}
.storage-substrate path{fill:none;stroke:var(--fs-accent);stroke-width:1.25;vector-effect:non-scaling-stroke;stroke-dasharray:6 12;}
.storage-substrate circle{fill:var(--fs-accent);}
.storage-stage.diving .storage-substrate path{animation:fs-substrate-charge 620ms cubic-bezier(.16,1,.3,1) both;}
@keyframes fs-substrate-charge{0%{stroke-dashoffset:160;opacity:.08}45%{opacity:.58}100%{stroke-dashoffset:0;opacity:.18}}
.sector-overview,.focus-layer{position:absolute;inset:0;z-index:2;}
.sector-overview{display:grid;grid-template-rows:auto 1fr auto;gap:var(--fs-space-3);padding:var(--fs-space-4);opacity:1;transform:none;transition:opacity 220ms ease-out,transform 520ms cubic-bezier(.16,1,.3,1),filter 360ms ease-out;}
.overview-copy{display:flex;align-items:end;justify-content:space-between;gap:var(--fs-space-4);padding:.15rem .2rem;}
.overview-copy>div{display:grid;gap:.2rem;}
.overview-copy strong{font-size:clamp(1.05rem,1.6vw,1.45rem);letter-spacing:-.02em;}
.overview-copy span{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.overview-hint{font-weight:700;text-align:right;}
.sector-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));grid-auto-rows:minmax(5.4rem,1fr);grid-auto-flow:dense;gap:6px;min-height:0;}
.sector-card{appearance:none;position:relative;overflow:hidden;display:grid;grid-template-columns:auto 1fr auto;grid-template-rows:auto 1fr auto;gap:.35rem .65rem;align-items:start;text-align:left;color:var(--fs-text-primary);background:linear-gradient(145deg,color-mix(in srgb,var(--fs-bg-surface-3) 92%,#8ba3b7 8%),color-mix(in srgb,var(--fs-bg-surface-2) 97%,#08111a 3%));border:1px solid color-mix(in srgb,var(--fs-border-default) 82%,var(--fs-accent) 18%);border-radius:5px;padding:.85rem;cursor:pointer;box-shadow:inset 0 1px 0 color-mix(in srgb,white 6%,transparent),0 12px 28px rgba(0,0,0,.14);transition:transform 260ms cubic-bezier(.16,1,.3,1),border-color 180ms ease-out,box-shadow 260ms ease-out,background 260ms ease-out;}
.sector-card::before,.focus-chamber::before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,transparent 0 8%,color-mix(in srgb,var(--fs-accent) 12%,transparent) 8% 8.3%,transparent 8.3% 91.7%,color-mix(in srgb,var(--fs-accent) 12%,transparent) 91.7% 92%,transparent 92%),linear-gradient(0deg,transparent 0 13%,color-mix(in srgb,var(--fs-border-default) 42%,transparent) 13% 13.4%,transparent 13.4% 86.6%,color-mix(in srgb,var(--fs-border-default) 42%,transparent) 86.6% 87%,transparent 87%);}
.sector-card:hover,.sector-card:focus-visible{transform:translateY(-2px);border-color:var(--fs-accent);box-shadow:inset 0 1px 0 color-mix(in srgb,white 8%,transparent),0 18px 34px rgba(0,0,0,.22);}
.sector-card.selected{border-color:var(--fs-accent);box-shadow:inset 0 0 0 2px var(--fs-accent),0 20px 42px color-mix(in srgb,var(--fs-accent) 18%,transparent);}
.sector-major{grid-column:span 3;grid-row:span 2;}
.sector-wide{grid-column:span 3;}
.sector-standard{grid-column:span 2;}
.sector-rank{font:700 .72rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);z-index:1;}
.sector-name{font-size:clamp(.95rem,1.25vw,1.22rem);font-weight:780;letter-spacing:-.015em;z-index:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sector-size{font-size:clamp(1rem,1.4vw,1.35rem);font-variant-numeric:tabular-nums;font-weight:820;z-index:1;}
.sector-state{grid-column:1/2;font-size:.72rem;font-weight:750;z-index:1;}
.sector-path{grid-column:2/4;font-size:.72rem;z-index:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:normal;color:var(--fs-text-muted);}
.overview-remainder{display:flex;align-items:center;justify-content:space-between;gap:var(--fs-space-3);padding:.65rem .85rem;border-top:1px solid var(--fs-border-subtle);color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.overview-remainder strong{color:var(--fs-text-primary);}
.focus-layer{opacity:0;pointer-events:none;transform:scale(.965);filter:blur(6px);transition:opacity 220ms ease-out,transform 520ms cubic-bezier(.16,1,.3,1),filter 360ms ease-out;padding:var(--fs-space-4);display:grid;grid-template-rows:auto 1fr minmax(7.5rem,10rem);gap:var(--fs-space-3);}
.storage-stage[data-scene="focus"] .sector-overview{opacity:0;pointer-events:none;transform:scale(1.045);filter:blur(7px);}
.storage-stage[data-scene="focus"] .focus-layer{opacity:1;pointer-events:auto;transform:none;filter:none;}
.scene-toolbar{display:flex;align-items:center;justify-content:space-between;gap:var(--fs-space-3);}
.scene-toolbar .selection-summary{flex:1;min-height:0;border:0;border-bottom:1px solid var(--fs-border-subtle);background:transparent;padding:.55rem 0;}
.scene-back{appearance:none;border:1px solid var(--fs-border-default);background:var(--fs-bg-surface-2);color:var(--fs-text-primary);border-radius:var(--fs-radius-sm);padding:.4rem .7rem;font-weight:750;cursor:pointer;white-space:nowrap;}
.focus-host{min-height:0;display:grid;place-items:stretch;}

.focus-chamber{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.55fr) minmax(15rem,.75fr);grid-template-rows:auto 1fr auto;gap:var(--fs-space-4);padding:clamp(1.4rem,3vw,2.6rem);border:1px solid color-mix(in srgb,var(--fs-accent) 52%,var(--fs-border-default));border-radius:6px;background:radial-gradient(90% 120% at 78% 18%,color-mix(in srgb,var(--fs-accent) 11%,transparent),transparent 58%),linear-gradient(135deg,color-mix(in srgb,var(--fs-bg-surface-3) 94%,#688099 6%),color-mix(in srgb,var(--fs-bg-surface-1) 96%,#050a0f 4%));box-shadow:inset 0 1px 0 color-mix(in srgb,white 7%,transparent),0 26px 65px rgba(0,0,0,.24);transform:perspective(1100px) rotateX(.6deg);transform-origin:center center;}
.focus-coordinate{grid-column:1/-1;display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--fs-border-subtle);padding-bottom:.65rem;font:700 .75rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);z-index:1;}
.focus-coordinate strong{font-size:1rem;color:var(--fs-accent);}
.focus-identity{align-self:center;z-index:1;min-width:0;}
.focus-identity h3{margin:0 0 .45rem;font-size:clamp(2rem,4.2vw,4.8rem);line-height:.94;letter-spacing:-.045em;overflow-wrap:anywhere;}
.focus-size{display:block;font-size:clamp(1.45rem,2.3vw,2.5rem);font-variant-numeric:tabular-nums;margin-bottom:1rem;}
.focus-path{font-size:clamp(.72rem,.92vw,.9rem);word-break:break-all;color:var(--fs-text-secondary);}
.focus-facts{align-self:center;display:grid;gap:.65rem;z-index:1;padding:1rem;border-block:1px solid var(--fs-border-subtle);}
.focus-facts span{display:flex;justify-content:space-between;gap:1rem;font-weight:700;}
.focus-gate{grid-column:1/-1;display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--fs-space-3);align-items:start;border-top:1px solid var(--fs-border-subtle);padding-top:.85rem;z-index:1;}
.focus-gate span{font:800 .72rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);}
.focus-gate strong{font-size:clamp(1rem,1.4vw,1.25rem);}
.focus-caption{position:absolute;right:1rem;bottom:.55rem;color:var(--fs-text-muted);font-size:.68rem;z-index:1;}
.context-map-shell{position:relative;overflow:hidden;border:1px solid var(--fs-border-subtle);border-radius:5px;background:var(--fs-bg-surface-2);}
.context-map-label{position:absolute;left:.65rem;top:.45rem;z-index:8;font:750 .66rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);}
.context-map-shell .map-wrap{position:absolute;inset:0;min-height:0;height:auto;padding:1.4rem .35rem .35rem;background:transparent;}
.context-map-shell .map-label,.context-map-shell .map-size,.context-map-shell .map-state{display:none;}
.context-map-shell .map-node{border-radius:1px;padding:0;}
.context-map-shell .map-node.selected{outline-width:3px;box-shadow:0 0 0 2px var(--fs-bg-canvas),0 0 0 4px var(--fs-accent);}
.dive-ghost{position:fixed;z-index:9999;margin:0;pointer-events:none;border:2px solid var(--fs-accent);border-radius:5px;background:linear-gradient(145deg,var(--fs-bg-surface-3),var(--fs-bg-surface-1));box-shadow:0 24px 70px rgba(0,0,0,.35);will-change:left,top,width,height,opacity,transform;}
@media (max-width:1179px){
  .storage-stage{min-height:42rem;}
  .sector-grid{grid-template-columns:repeat(4,minmax(0,1fr));}
  .sector-major{grid-column:span 2;}
  .sector-wide,.sector-standard{grid-column:span 2;}
  .focus-chamber{grid-template-columns:1fr;}
  .focus-facts{grid-template-columns:repeat(3,minmax(0,1fr));}
}
@media (max-width:799px){
  .storage-stage{min-height:48rem;}
  .sector-overview,.focus-layer{padding:var(--fs-space-3);}
  .sector-grid{grid-template-columns:1fr 1fr;}
  .sector-major,.sector-wide,.sector-standard{grid-column:span 1;grid-row:span 1;}
  .sector-major{grid-column:1/-1;}
  .overview-copy,.overview-remainder{align-items:start;flex-direction:column;}
  .overview-hint{text-align:left;}
  .focus-layer{grid-template-rows:auto 1fr 7rem;}
  .focus-identity h3{font-size:clamp(1.8rem,10vw,3rem);}
  .focus-facts{grid-template-columns:1fr;}
}
@media (prefers-reduced-motion: reduce){
  .sector-overview,.focus-layer,.sector-card,.scene-back{transition:none!important;}
  .storage-stage.diving .storage-substrate path{animation:none!important;}
  .dive-ghost{display:none!important;}
}
@media (forced-colors: active){
  .sector-card,.focus-chamber,.context-map-shell{forced-color-adjust:none;background:Canvas;border-color:CanvasText;color:CanvasText;box-shadow:none;}
  .sector-card.selected{outline:3px solid Highlight;outline-offset:-3px;}
  .storage-substrate{display:none;}
}
"""
