"""Cinematic storage-atlas presentation helpers.

Presentation-only overview/focus state for the offline report.
Never classifies evidence, grants authorization, or mutates receipt data.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

from filesteward.visualization.camera import DIRECT_TARGET_MIN_PX
from filesteward.visualization.contracts import PresentationNode, TreemapRect
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.signals import project_decision_signals
from filesteward.visualization.tokens import disposition_css_stem

__all__ = [
    "BANK_LIMIT",
    "OVERVIEW_LIMIT",
    "render_atlas_runtime_json",
    "render_cinematic_css",
    "render_cinematic_script",
    "render_decision_signal_rail",
    "render_focus_chamber",
    "render_focus_templates",
    "render_sector_bank",
    "render_sector_overview",
    "render_substrate_svg",
]

OVERVIEW_LIMIT = 12
BANK_LIMIT = 36


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
    largest = max((node.logical_size_bytes or 0 for node in shown), default=0)
    for rank, node in enumerate(shown, start=1):
        ratio = ((node.logical_size_bytes or 0) / largest) if largest else 0.0
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
            f'<span class="sector-magnitude" style="--sector-ratio:{ratio:.4f}" '
            f'aria-hidden="true"></span>'
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
        '<span class="overview-hint">Click a readable sector to dive · Esc backs one scene · Home returns to Atlas Home</span>'
        "</div>"
        f'<div class="sector-grid">{"".join(cards)}</div>'
        f"{remainder}"
        "</section>"
    )


def render_sector_bank(
    nodes: Sequence[PresentationNode],
    selected_id: Optional[str],
    *,
    start: int = OVERVIEW_LIMIT,
    limit: int = BANK_LIMIT,
) -> str:
    """Second LOD band: more existing evidence groups, still not invented hierarchy."""

    ordered = _sorted_nodes(nodes)
    shown = ordered[start:limit]
    if not shown:
        return ""
    cards: list[str] = []
    largest = max((node.logical_size_bytes or 0 for node in shown), default=0)
    for rank, node in enumerate(shown, start=start + 1):
        ratio = ((node.logical_size_bytes or 0) / largest) if largest else 0.0
        selected = " selected" if node.node_id == selected_id else ""
        current = ' aria-current="true"' if node.node_id == selected_id else ""
        tone = disposition_css_stem(node.disposition)
        aria = (
            f"Storage sector {rank}, {node.display_name}, "
            f"{_fmt_bytes(node.logical_size_bytes)}, {_state_label(node)}"
        )
        cards.append(
            f'<button type="button" class="sector-card sector-standard{selected} '
            f'state-edge-{escape_attr(tone)}" data-node-id="{escape_attr(node.node_id)}" '
            f'data-atlas-action="select" data-sector-rank="{rank}" '
            f'aria-label="{escape_attr(aria)}"{current}>'
            f'<span class="sector-rank">S{rank:02d}</span>'
            f'<span class="sector-name">{escape_text(node.display_name)}</span>'
            f'<span class="sector-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="sector-state state state-{escape_attr(tone)}">'
            f'{escape_text(_state_label(node))}</span>'
            f'<span class="sector-path mono">{escape_text(node.path)}</span>'
            f'<span class="sector-magnitude" style="--sector-ratio:{ratio:.4f}" '
            f'aria-hidden="true"></span>'
            f"</button>"
        )
    return (
        '<section class="sector-bank" id="sector-bank" hidden '
        'aria-label="Expanded storage sectors">'
        f'<div class="sector-grid sector-grid-bank">{"".join(cards)}</div>'
        "</section>"
    )


def render_decision_signal_rail(node: PresentationNode) -> str:
    chips: list[str] = []
    for signal in project_decision_signals(node):
        classes = ["signal-chip", f"signal-{signal.kind.value.lower()}"]
        if signal.is_primary:
            classes.append("signal-primary")
        if signal.pulse:
            classes.append("signal-pulse")
        if signal.hard_stop:
            classes.append("signal-hard-stop")
        chips.append(
            f'<li class="{" ".join(classes)}" data-signal-id="{escape_attr(signal.signal_id)}" '
            f'role="button" tabindex="0" data-open-decision="true" '
            f'aria-label="Open decision gate: {escape_attr(signal.label)}">'
            f'<span class="signal-kind">{escape_text(signal.kind.value)}</span>'
            f'<strong>{escape_text(signal.label)}</strong>'
            f'<span class="signal-copy">{escape_text(signal.accessible_text)}</span>'
            "</li>"
        )
    return (
        '<ul class="decision-signal-rail" aria-label="Decision signals">'
        f"{''.join(chips)}</ul>"
    )


def render_atlas_runtime_json(
    nodes: Sequence[PresentationNode],
    rects: Optional[Sequence[TreemapRect]] = None,
) -> str:
    payload = {
        "directTargetMinPx": DIRECT_TARGET_MIN_PX,
        "preferredTargetPx": 44.0,
        "rects": {
            rect.node_id: {
                "x": rect.x,
                "y": rect.y,
                "width": rect.width,
                "height": rect.height,
            }
            for rect in (rects or ())
        },
        "nodeIds": [node.node_id for node in nodes],
    }
    raw = (
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return f'<script type="application/json" id="atlas-runtime">{raw}</script>'


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
  {render_decision_signal_rail(node)}
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
.workspace{transition:grid-template-columns 520ms cubic-bezier(.16,1,.3,1);}
.workspace[data-scene="overview"]{grid-template-columns:minmax(260px,320px) minmax(0,1fr) 0;}
.workspace[data-scene="overview"] .inspector-pane{opacity:0;visibility:hidden;pointer-events:none;overflow:hidden;border:0;}
.workspace[data-scene="focus"]{grid-template-columns:minmax(240px,300px) minmax(0,1fr) minmax(320px,390px);}
.workspace[data-scene="focus"] .inspector-pane{opacity:1;visibility:visible;pointer-events:auto;transition:opacity 220ms ease-out 180ms;}
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
.sector-magnitude{position:absolute;left:0;right:0;bottom:0;height:3px;background:color-mix(in srgb,var(--fs-border-default) 55%,transparent);}
.sector-magnitude::after{content:"";display:block;height:100%;width:calc(var(--sector-ratio,0) * 100%);background:var(--fs-accent);box-shadow:0 0 12px color-mix(in srgb,var(--fs-accent) 35%,transparent);}
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
@media (max-width:1280px){
  .workspace[data-scene="overview"]{grid-template-columns:minmax(220px,280px) minmax(0,1fr);}
  .workspace[data-scene="overview"] .inspector-pane{display:none;}
  .workspace[data-scene="focus"]{grid-template-columns:minmax(220px,280px) minmax(0,1fr);}
  .workspace[data-scene="focus"] .inspector-pane{grid-column:1/-1;display:block;opacity:1;}
  .storage-stage{min-height:42rem;}
  .sector-grid{grid-template-columns:repeat(4,minmax(0,1fr));}
  .sector-major{grid-column:span 2;}
  .sector-wide,.sector-standard{grid-column:span 2;}
  .focus-chamber{grid-template-columns:1fr;}
  .focus-facts{grid-template-columns:repeat(3,minmax(0,1fr));}
}
@media (max-width:799px){
  .workspace[data-scene="overview"],.workspace[data-scene="focus"]{grid-template-columns:1fr;transition:none;}
  .workspace[data-scene="overview"] .inspector-pane{display:none;}
  .workspace[data-scene="focus"] .inspector-pane{grid-column:auto;display:block;opacity:1;}
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
  .sector-overview,.focus-layer,.sector-card,.scene-back,.atlas-hud,.phone-command-bar,.camera-plane,.signal-pulse{transition:none!important;}
  .storage-stage.diving .storage-substrate path{animation:none!important;}
  .dive-ghost,.signal-pulse{animation:none!important;}
}
@media (forced-colors: active){
  .sector-card,.focus-chamber,.context-map-shell,.signal-chip,.atlas-hud button,.phone-command-bar button{forced-color-adjust:none;background:Canvas;border-color:CanvasText;color:CanvasText;box-shadow:none;}
  .sector-card.selected{outline:3px solid Highlight;outline-offset:-3px;}
  .storage-substrate{display:none;}
  .signal-hard-stop{outline:3px solid CanvasText;}
  .signal-primary{outline:3px solid Highlight;}
}
.workspace{container-type:inline-size;container-name:atlas;min-width:0;}
.map-pane,.navigator-pane,.inspector-pane,.storage-stage,.focus-identity,.focus-path,.sector-name,.sector-path{min-width:0;}
.atlas-hud{position:relative;z-index:4;display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;padding:.55rem .75rem;border-bottom:1px solid var(--fs-border-subtle);background:color-mix(in srgb,var(--fs-bg-surface-1) 88%,#05080c 12%);}
.atlas-hud button,.phone-command-bar button,.atlas-open,.atlas-fit{appearance:none;min-height:44px;min-width:44px;padding:.35rem .7rem;border:1px solid var(--fs-border-default);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-2);color:var(--fs-text-primary);font-weight:750;cursor:pointer;}
.atlas-level{font:750 .72rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-accent);margin-right:.4rem;}
.sector-bank{position:absolute;inset:0;z-index:2;padding:var(--fs-space-4);opacity:0;pointer-events:none;}
.storage-stage[data-camera-level="BANK"] .sector-overview{opacity:.35;transform:scale(.98);}
.storage-stage[data-camera-level="BANK"] .sector-bank{opacity:1;pointer-events:auto;}
.fabric-layer{position:absolute;inset:0;z-index:1;opacity:0;pointer-events:none;padding:var(--fs-space-3);}
.storage-stage[data-camera-level="FABRIC"] .sector-overview,.storage-stage[data-camera-level="CELL"] .sector-overview,.storage-stage[data-camera-level="FABRIC"] .sector-bank,.storage-stage[data-camera-level="CELL"] .sector-bank{opacity:0;pointer-events:none;}
.storage-stage[data-camera-level="FABRIC"] .fabric-layer,.storage-stage[data-camera-level="CELL"] .fabric-layer{opacity:1;pointer-events:auto;}
.camera-plane{width:100%;height:100%;min-height:18rem;transform-origin:0 0;transition:transform 360ms cubic-bezier(.16,1,.3,1);}
.map-node.micro{pointer-events:none;cursor:default;}
.storage-stage[data-camera-level="CELL"] .map-node.selected{pointer-events:auto;cursor:pointer;}
.decision-signal-rail{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:.45rem;list-style:none;margin:0;padding:.4rem 0 0;z-index:1;}
.signal-chip{min-width:0;display:grid;gap:.15rem;padding:.45rem .65rem;border:1px solid var(--fs-border-default);border-radius:4px;background:var(--fs-bg-surface-2);max-width:100%;}
.signal-kind{font:750 .66rem/1 var(--fs-font-mono);letter-spacing:.06em;color:var(--fs-text-muted);}
.signal-copy{font-size:.72rem;color:var(--fs-text-secondary);overflow-wrap:anywhere;}
.signal-passed{box-shadow:inset 3px 0 0 color-mix(in srgb,var(--fs-accent) 55%,transparent);}
.signal-unresolved.signal-pulse{border-color:color-mix(in srgb,var(--fs-state-review-edge) 80%,var(--fs-accent));animation:fs-signal-pulse 1.8s ease-in-out infinite;}
.signal-unknown{border-style:dashed;}
.signal-blocked.signal-hard-stop,.signal-unapproved{border-width:2px;box-shadow:none;background:var(--fs-bg-surface-1);}
@keyframes fs-signal-pulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--fs-state-review-edge) 35%,transparent)}50%{box-shadow:0 0 0 6px color-mix(in srgb,var(--fs-state-review-edge) 8%,transparent)}}
.phone-command-bar{display:none;position:sticky;bottom:0;z-index:12;gap:.35rem;padding:.45rem .45rem calc(.45rem + env(safe-area-inset-bottom,0px));background:var(--fs-bg-shell);border-top:1px solid var(--fs-border-subtle);}
.workspace[data-decision-open="true"] .inspector-pane{opacity:1;visibility:visible;pointer-events:auto;}
@container atlas (max-width:1280px){
  .workspace[data-scene="overview"]{grid-template-columns:minmax(3.5rem,4.5rem) minmax(0,1fr);}
  .workspace[data-scene="overview"] .navigator-pane .nav,.workspace[data-scene="overview"] .filters,.workspace[data-scene="overview"] .search-label{display:none;}
  .workspace[data-scene="overview"] .inspector-pane{display:none;}
  .workspace[data-scene="focus"]{grid-template-columns:minmax(0,1fr);}
  .workspace[data-scene="focus"] .navigator-pane{display:none;}
  .workspace[data-scene="focus"] .inspector-pane{grid-column:1/-1;display:block;max-height:42vh;overflow:auto;}
  .focus-chamber{grid-template-columns:minmax(0,1fr);}
  .focus-identity h3,.focus-path,.selection-name,.selection-path{overflow-wrap:anywhere;white-space:normal;}
}
@media (max-width:799px){
  .phone-command-bar{display:flex;justify-content:space-between;}
  .atlas-hud{display:none;}
  .workspace[data-scene="overview"] .navigator-pane,.workspace[data-scene="focus"] .navigator-pane{position:fixed;inset:auto 0 3.6rem 0;z-index:11;max-height:48vh;overflow:auto;display:none;border-top:1px solid var(--fs-border-subtle);}
  .workspace[data-nav-open="true"] .navigator-pane{display:block;}
  .workspace[data-scene="focus"] .inspector-pane{position:fixed;inset:auto 0 3.6rem 0;z-index:11;max-height:52vh;display:none;background:var(--fs-bg-surface-1);}
  .workspace[data-decision-open="true"] .inspector-pane{display:block;}
}
@media (prefers-reduced-motion: reduce){
  .signal-unresolved.signal-pulse{animation:none;border-width:2px;}
}
"""


def render_cinematic_script() -> str:
    return r"""
<script>
(() => {
  const stage = document.getElementById('storage-stage');
  const workspace = document.getElementById('workspace');
  const focusHost = document.getElementById('focus-host');
  const back = document.getElementById('scene-back');
  if (!stage || !workspace || !focusHost || !back) return;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let focusedId = null;
  let cameraLevel = 'HOME';
  const history = [];
  const runtimeEl = document.getElementById('atlas-runtime');
  const runtime = runtimeEl ? JSON.parse(runtimeEl.textContent || '{}') : {};
  const plane = document.getElementById('camera-plane');
  const levelLabel = document.getElementById('atlas-level');
  const homeBtn = document.getElementById('atlas-home');
  const searchBtn = document.getElementById('atlas-search');
  const zoomInBtn = document.getElementById('atlas-zoom-in');
  const zoomOutBtn = document.getElementById('atlas-zoom-out');
  const fitBtn = document.getElementById('atlas-fit');
  const openBtn = document.getElementById('atlas-open');
  const decisionBtn = document.getElementById('atlas-decision');
  const bank = document.getElementById('sector-bank');

  const byAttr = (selector, attr, value) =>
    Array.from(document.querySelectorAll(selector)).find(
      (el) => el.getAttribute(attr) === value
    );

  const focusTemplate = (id) => byAttr('[data-focus-for]', 'data-focus-for', id);
  const overviewSector = (id) => byAttr('.sector-card', 'data-node-id', id);
  const selectedId = () => {
    const row = document.querySelector('.nav-row.selected, .sector-card.selected');
    return row ? row.getAttribute('data-node-id') : focusedId;
  };

  const setLevel = (level, scene) => {
    cameraLevel = level;
    stage.dataset.cameraLevel = level;
    workspace.dataset.cameraLevel = level;
    if (scene === 'overview') workspace.dataset.scene = 'overview';
    else workspace.dataset.scene = 'focus';
    stage.dataset.scene = workspace.dataset.scene;
    if (levelLabel) levelLabel.textContent = 'CAMERA ' + level;
    if (bank) bank.hidden = level !== 'BANK';
    back.hidden = level === 'HOME';
  };

  const activateNode = (id) => {
    const row = byAttr('.nav-row', 'data-node-id', id);
    if (row) row.click();
  };

  const atlas = {
    select(id) {
      if (!id) return;
      activateNode(id);
      if (cameraLevel === 'CHAMBER') syncFocus(id);
    },
    zoom_in() {
      if (cameraLevel === 'HOME') setLevel('BANK', 'overview');
      else if (cameraLevel === 'BANK') setLevel('FABRIC', 'overview');
      else if (cameraLevel === 'FABRIC') atlas.fit_selected();
      else if (cameraLevel === 'CELL') atlas.open_selected();
    },
    zoom_out() { atlas.back(); },
    fit_selected() {
      const id = selectedId();
      if (!id) return;
      const rect = (runtime.rects || {})[id];
      history.push(cameraLevel);
      setLevel('CELL', 'overview');
      if (plane && rect) {
        const scale = Math.min(8, Math.max(1.15, 70 / Math.max(rect.width, rect.height)));
        const tx = 50 - (rect.x + rect.width / 2) * scale;
        const ty = 50 - (rect.y + rect.height / 2) * scale;
        plane.style.transform = 'translate(' + tx + '%, ' + ty + '%) scale(' + scale + ')';
      }
      activateNode(id);
    },
    open_selected(source) {
      const id = selectedId();
      if (!id) return;
      enterFocus(id, source);
    },
    back() {
      if (cameraLevel === 'CHAMBER') {
        exitFocus();
        return;
      }
      if (cameraLevel === 'CELL') {
        if (plane) plane.style.transform = 'none';
        setLevel('FABRIC', 'overview');
        return;
      }
      if (cameraLevel === 'FABRIC') setLevel('BANK', 'overview');
      else if (cameraLevel === 'BANK') setLevel('HOME', 'overview');
    },
    home() {
      if (plane) plane.style.transform = 'none';
      history.length = 0;
      const keep = selectedId();
      setLevel('HOME', 'overview');
      focusedId = keep;
      if (keep) activateNode(keep);
      stage.classList.remove('returning-home');
      void stage.offsetWidth;
      stage.classList.add('returning-home');
      pulseSubstrate();
      window.setTimeout(() => stage.classList.remove('returning-home'), 820);
    },
    search() {
      const field = document.getElementById('storage-search');
      workspace.dataset.navOpen = 'true';
      if (field) field.focus();
    },
    toggle_decision() {
      const open = workspace.dataset.decisionOpen === 'true';
      workspace.dataset.decisionOpen = open ? 'false' : 'true';
      if (!open) setLevel(cameraLevel === 'HOME' ? 'CELL' : cameraLevel, cameraLevel === 'HOME' ? 'overview' : stage.dataset.scene);
      const inspector = document.getElementById('inspector-body');
      if (!open && inspector) inspector.focus();
    }
  };
  window.FileStewardAtlas = atlas;

  const syncFocus = (id) => {
    const template = focusTemplate(id);
    if (!template) return;
    focusHost.innerHTML = template.innerHTML;
    focusedId = id;
  };

  const pulseSubstrate = () => {
    stage.classList.remove('diving');
    void stage.offsetWidth;
    stage.classList.add('diving');
    window.setTimeout(() => stage.classList.remove('diving'), 680);
  };

  const animateGhost = (from, to) => {
    if (reduced.matches || !from || !to || !document.body.animate) return;
    const ghost = document.createElement('div');
    ghost.className = 'dive-ghost';
    document.body.appendChild(ghost);
    Object.assign(ghost.style, {
      left: from.left + 'px',
      top: from.top + 'px',
      width: Math.max(1, from.width) + 'px',
      height: Math.max(1, from.height) + 'px',
    });
    const animation = ghost.animate(
      [
        {
          left: from.left + 'px',
          top: from.top + 'px',
          width: Math.max(1, from.width) + 'px',
          height: Math.max(1, from.height) + 'px',
          opacity: 0.96,
          transform: 'perspective(900px) rotateX(0deg) scale(1)',
        },
        {
          offset: 0.58,
          opacity: 0.7,
          transform: 'perspective(900px) rotateX(-2deg) scale(1.012)',
        },
        {
          left: to.left + 'px',
          top: to.top + 'px',
          width: Math.max(1, to.width) + 'px',
          height: Math.max(1, to.height) + 'px',
          opacity: 0.08,
          transform: 'perspective(900px) rotateX(0deg) scale(1)',
        },
      ],
      { duration: 560, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'forwards' }
    );
    animation.finished.finally(() => ghost.remove());
  };


  const enterFocus = (id, source) => {
    const template = focusTemplate(id);
    if (!template) return;
    syncFocus(id);
    const origin = source || overviewSector(id) || stage;
    const from = origin.getBoundingClientRect();
    stage.dataset.scene = 'focus';
    workspace.dataset.scene = 'focus';
    history.push(cameraLevel);
    setLevel('CHAMBER', 'focus');
    back.hidden = false;
    pulseSubstrate();
    window.requestAnimationFrame(() => {
      animateGhost(from, focusHost.getBoundingClientRect());
    });
  };

  const exitFocus = () => {
    if (stage.dataset.scene !== 'focus') return;
    const destination = focusedId ? overviewSector(focusedId) : null;
    const from = focusHost.getBoundingClientRect();
    const prev = history.pop() || 'HOME';
    const scene = prev === 'CHAMBER' ? 'focus' : 'overview';
    stage.dataset.scene = scene;
    workspace.dataset.scene = scene;
    setLevel(prev === 'CHAMBER' ? 'HOME' : prev, scene);
    back.hidden = prev === 'HOME';
    pulseSubstrate();
    window.requestAnimationFrame(() => {
      const target = destination || stage;
      animateGhost(from, target.getBoundingClientRect());
    });
    if (destination) {
      window.setTimeout(() => destination.focus(), reduced.matches ? 0 : 560);
    }
  };

  document.querySelectorAll('.sector-card').forEach((sector) => {
    sector.addEventListener('click', (event) => {
      if (!event.isTrusted) return;
      enterFocus(sector.getAttribute('data-node-id'), sector);
    });
    sector.addEventListener('keydown', (event) => {
      if (!event.isTrusted || (event.key !== 'Enter' && event.key !== ' ')) return;
      enterFocus(sector.getAttribute('data-node-id'), sector);
    });
  });

  document.querySelectorAll('.nav-row').forEach((row) => {
    row.addEventListener('keydown', (event) => {
      if (!event.isTrusted || (event.key !== 'Enter' && event.key !== ' ')) return;
      event.preventDefault();
      atlas.select(row.getAttribute('data-node-id'));
      atlas.fit_selected();
    });
  });

  document.querySelectorAll('.map-node.micro').forEach((node) => {
    node.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
    }, true);
  });

  document.addEventListener('filesteward:selection', (event) => {
    const id = event.detail && event.detail.id;
    if (!id) return;
    if (stage.dataset.scene === 'focus') syncFocus(id);
  });

  back.addEventListener('click', () => atlas.back());
  if (homeBtn) homeBtn.addEventListener('click', () => atlas.home());
  if (searchBtn) searchBtn.addEventListener('click', () => atlas.search());
  if (zoomInBtn) zoomInBtn.addEventListener('click', () => atlas.zoom_in());
  if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => atlas.zoom_out());
  if (fitBtn) fitBtn.addEventListener('click', () => atlas.fit_selected());
  if (openBtn) openBtn.addEventListener('click', () => atlas.open_selected(openBtn));
  if (decisionBtn) decisionBtn.addEventListener('click', () => atlas.toggle_decision());
  document.querySelectorAll('[data-atlas-action]').forEach((el) => {
    el.addEventListener('click', () => {
      const action = el.getAttribute('data-atlas-action');
      if (action && typeof atlas[action] === 'function') atlas[action]();
    });
  });
  document.addEventListener('keydown', (event) => {
    const typing = event.target && (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.isContentEditable);
    if (event.key === 'Escape') {
      event.preventDefault();
      atlas.back();
      return;
    }
    if (typing) return;
    if (event.key === 'Home') { event.preventDefault(); atlas.home(); }
    else if (event.key === '+' || event.key === '=') { event.preventDefault(); atlas.zoom_in(); }
    else if (event.key === '-' || event.key === '_') { event.preventDefault(); atlas.zoom_out(); }
    else if (event.key === '/') { event.preventDefault(); atlas.search(); }
    else if (event.key === 'd' || event.key === 'D') { event.preventDefault(); atlas.toggle_decision(); }
  });
  setLevel('HOME', 'overview');
})();
</script>
"""
