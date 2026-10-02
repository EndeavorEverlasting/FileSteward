"""F0 thin report-shell emitter.

F2 expands this into production html.py. This seam proves:
  model + tokens + literal escaping + selection hooks -> offline HTML string

It does not implement treemap geometry (F3), evidence inference (F1), or
atomic publication (F4). It never emits apply/quarantine/delete controls.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    TreemapRect,
)
from filesteward.visualization.css import render_token_css
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.selection import SelectionController
from filesteward.visualization.tokens import disposition_css_stem

__all__ = ["render_report_shell"]

_FORBIDDEN_CONTROL_MARKERS = (
    "Apply",
    "Quarantine",
    "Delete",
    "Permanently delete",
)


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


def _state_label(disposition: CleanupDisposition) -> str:
    return disposition.value.replace("_", " ")


def _auth_label(auth: AuthorizationState) -> str:
    return auth.value.replace("_", " ")


def _gate_class(status: GateStepStatus, first: bool) -> str:
    base = {
        GateStepStatus.PASS: "pass",
        GateStepStatus.FAIL: "fail",
        GateStepStatus.BLOCK: "block",
        GateStepStatus.WAITING: "waiting",
        GateStepStatus.UNKNOWN: "unknown",
        GateStepStatus.NOT_APPLICABLE: "na",
    }[status]
    return f"step {base}{' unresolved' if first else ''}"


def _render_navigator(nodes: Sequence[PresentationNode], selected_id: Optional[str]) -> str:
    rows = []
    for node in sorted(
        nodes,
        key=lambda n: (n.logical_size_bytes is None, -(n.logical_size_bytes or 0)),
    ):
        selected = " selected" if node.node_id == selected_id else ""
        tone = disposition_css_stem(node.disposition)
        meta_bits = [
            escape_text(_state_label(node.disposition)),
            (
                f"{node.item_count:,} items"
                if node.item_count is not None
                else "item count unknown"
            ),
        ]
        if node.contract_hint_tags:
            meta_bits.append("hints: " + ", ".join(escape_text(t) for t in node.contract_hint_tags))
        aria = (
            f"{node.display_name}, {_fmt_bytes(node.logical_size_bytes)}, "
            f"{_state_label(node.disposition)}, {_auth_label(node.authorization_state)}"
        )
        rows.append(
            f'<button type="button" class="nav-row{selected}" data-node-id="{escape_attr(node.node_id)}" '
            f'aria-label="{escape_attr(aria)}">'
            f'<span class="nav-name">{escape_text(node.display_name)}</span>'
            f'<span class="nav-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="nav-meta"><span class="state state-{escape_attr(tone)}">'
            f'{escape_text(_state_label(node.disposition))}</span> · '
            f'{escape_text(" · ".join(meta_bits[1:]))}</span>'
            f"</button>"
        )
    return "\n".join(rows)


def _render_map_slots(
    nodes: Sequence[PresentationNode],
    rects: Optional[Sequence[TreemapRect]],
    selected_id: Optional[str],
) -> str:
    if not rects:
        # F0/F2 shell provides the map container; F3 fills geometry later.
        return (
            '<div class="map-placeholder" role="img" '
            'aria-label="Treemap geometry owned by F3; shell container only">'
            "Map container ready — treemap rectangles supplied by F3."
            "</div>"
        )
    parts = []
    by_id = {n.node_id: n for n in nodes}
    for rect in rects:
        node = by_id[rect.node_id]
        selected = " selected" if node.node_id == selected_id else ""
        tone = disposition_css_stem(node.disposition)
        aria = (
            f"{node.display_name}, {_fmt_bytes(node.logical_size_bytes)}, "
            f"{_state_label(node.disposition)}, {_auth_label(node.authorization_state)}"
        )
        parts.append(
            f'<button type="button" class="map-node{selected} state-edge-{escape_attr(tone)}" '
            f'data-node-id="{escape_attr(node.node_id)}" '
            f'style="left:{rect.x}%;top:{rect.y}%;width:{rect.width}%;height:{rect.height}%;" '
            f'aria-label="{escape_attr(aria)}">'
            f'<span class="map-label">{escape_text(node.display_name)}</span>'
            f"</button>"
        )
    return "\n".join(parts)


def _render_gate_steps(steps: Iterable[GateStep]) -> str:
    rows = []
    for step in steps:
        rows.append(
            f'<li class="{_gate_class(step.status, step.is_first_unresolved)}">'
            f'<div class="gate-name">{escape_text(step.name)}</div>'
            f'<div class="gate-status">{escape_text(step.status.value)}</div>'
            f'<div class="gate-expl">{escape_text(step.explanation)}</div>'
            f"</li>"
        )
    if not rows:
        return (
            '<p class="empty">Decision detail unavailable. '
            "State: UNKNOWN / NOT PERSISTED</p>"
        )
    return f'<ol class="trace">{"".join(rows)}</ol>'


def _render_inspector(node: Optional[PresentationNode]) -> str:
    if node is None:
        return '<p class="empty">No items match these filters.</p>'
    tone = disposition_css_stem(node.disposition)
    reclaim = _fmt_bytes(node.projected_reclaim_bytes)
    quality = node.projection_quality or "not-applicable"
    return f"""
<section class="card selected-item">
  <h3>{escape_text(node.display_name)}</h3>
  <p class="path mono">{escape_text(node.path)}</p>
  <dl class="kv">
    <dt>Logical size</dt><dd>{escape_text(_fmt_bytes(node.logical_size_bytes))}</dd>
    <dt>Allocated size</dt><dd>{escape_text(_fmt_bytes(node.allocated_size_bytes))}</dd>
    <dt>Projected reclaim</dt><dd>{escape_text(reclaim)}</dd>
    <dt>Projection quality</dt><dd>{escape_text(quality)}</dd>
    <dt>Disposition</dt><dd class="state state-{escape_attr(tone)}">{escape_text(_state_label(node.disposition))}</dd>
    <dt>Authorization</dt><dd class="auth">{escape_text(_auth_label(node.authorization_state))}</dd>
    <dt>Evidence source</dt><dd>{escape_text(node.trace_evidence_source)}</dd>
  </dl>
</section>
<section class="card evidence">
  <h3>Evidence</h3>
  <p>{escape_text(node.reason)}</p>
</section>
<section class="card decision-trace">
  <h3>Decision trace</h3>
  {_render_gate_steps(node.gate_steps)}
</section>
<section class="card risk">
  <h3>Risk</h3>
  <p>{escape_text(node.risk_if_acted_on)}</p>
</section>
<section class="card next-action">
  <h3>Next valid action</h3>
  <p>{escape_text(node.next_gate)}</p>
</section>
<section class="card authorization">
  <h3>Authorization</h3>
  <p class="auth">{escape_text(_auth_label(node.authorization_state))}</p>
  <p class="note">RECLAIM PROVEN evidence is not approval. No apply control exists in this report.</p>
</section>
"""


def _shell_behavior_css() -> str:
    return """
html,body{margin:0;background:var(--fs-bg-canvas);color:var(--fs-text-primary);font-family:var(--fs-font-sans);}
.app{min-height:100vh;display:grid;grid-template-rows:auto auto 1fr auto;}
.shell{background:var(--fs-bg-shell);border-bottom:1px solid var(--fs-border-subtle);padding:var(--fs-space-4) var(--fs-space-5);}
.shell h1{margin:0;font-size:var(--fs-type-title-lg-size);line-height:var(--fs-type-title-lg-line);font-weight:var(--fs-type-title-lg-weight);}
.shell .sub{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--fs-space-2);padding:var(--fs-space-3) var(--fs-space-5);background:var(--fs-bg-surface-2);border-bottom:1px solid var(--fs-border-subtle);}
.metric{background:var(--fs-bg-surface-1);border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);padding:var(--fs-space-3);}
.metric b{display:block;font-variant-numeric:tabular-nums;font-size:var(--fs-type-title-size);}
.metric span{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.workspace{display:grid;grid-template-columns:minmax(260px,320px) minmax(480px,1fr) minmax(320px,400px);min-height:0;}
.pane{background:var(--fs-bg-surface-1);border-right:1px solid var(--fs-border-subtle);min-width:0;}
.pane:last-child{border-right:0;}
.pane-head{height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 var(--fs-space-3);border-bottom:1px solid var(--fs-border-subtle);}
.pane-head h2{margin:0;font-size:var(--fs-type-small-strong-size);font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--fs-text-secondary);}
.nav{display:flex;flex-direction:column;}
.nav-row{appearance:none;border:0;border-bottom:1px solid var(--fs-border-subtle);background:transparent;color:inherit;text-align:left;display:grid;grid-template-columns:1fr auto;gap:var(--fs-space-1) var(--fs-space-2);padding:var(--fs-space-3);min-height:44px;cursor:pointer;}
.nav-row:hover{background:var(--fs-bg-hover);}
.nav-row.selected{background:var(--fs-bg-selected);box-shadow:inset 2px 0 0 var(--fs-accent);}
.nav-name{font-size:var(--fs-type-body-size);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.nav-size{font-variant-numeric:tabular-nums;font-weight:600;}
.nav-meta{grid-column:1/-1;font-size:var(--fs-type-small-size);color:var(--fs-text-muted);}
.map-wrap{position:relative;min-height:420px;padding:var(--fs-space-2);background:var(--fs-bg-surface-2);}
.map-placeholder,.map-node{border:1px solid var(--fs-border-default);border-radius:var(--fs-radius-treemap);background:var(--fs-bg-surface-3);color:var(--fs-text-primary);}
.map-placeholder{display:grid;place-items:center;height:100%;padding:var(--fs-space-4);color:var(--fs-text-secondary);}
.map-node{position:absolute;overflow:hidden;cursor:pointer;}
.map-node.selected{outline:3px solid var(--fs-accent);outline-offset:-3px;}
.state-edge-state-review{box-shadow:inset -2px -2px 0 var(--fs-state-review-edge);}
.state-edge-state-unknown{box-shadow:inset -2px -2px 0 var(--fs-state-unknown-edge);}
.state-edge-state-protected{box-shadow:inset -2px -2px 0 var(--fs-state-protected-edge);}
.state-edge-state-keep{box-shadow:inset -2px -2px 0 var(--fs-state-keep-edge);}
.state-edge-state-reclaim{box-shadow:inset -2px -2px 0 var(--fs-state-reclaim-edge);}
.inspector{padding:var(--fs-space-4);overflow:auto;}
.card{background:var(--fs-bg-surface-2);border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);padding:var(--fs-space-4);margin-bottom:var(--fs-space-3);}
.card h3{margin:0 0 var(--fs-space-2);font-size:var(--fs-type-title-size);}
.path,.mono{font-family:var(--fs-font-mono);font-size:var(--fs-type-small-size);word-break:break-all;color:var(--fs-text-secondary);}
.kv{display:grid;grid-template-columns:140px 1fr;gap:var(--fs-space-2);margin:0;}
.kv dt{color:var(--fs-text-muted);}
.trace{list-style:none;margin:0;padding:0;display:grid;gap:var(--fs-space-2);}
.step{border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-sm);padding:var(--fs-space-3);background:var(--fs-bg-surface-1);}
.step.pass{opacity:.72;}
.step.unresolved{border-color:var(--fs-state-review-edge);border-width:2px;font-weight:600;}
.state-state-review{color:var(--fs-state-review);}
.state-state-unknown{color:var(--fs-state-unknown);}
.state-state-protected{color:var(--fs-state-protected);}
.state-state-keep{color:var(--fs-state-keep);}
.state-state-reclaim{color:var(--fs-state-reclaim);}
.auth{font-weight:600;color:var(--fs-text-secondary);}
.note{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.footer{padding:var(--fs-space-3) var(--fs-space-5);border-top:1px solid var(--fs-border-subtle);color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
:focus-visible{outline:3px solid var(--fs-focus);outline-offset:2px;}
@media (max-width:1179px){
  .workspace{grid-template-columns:minmax(220px,280px) minmax(0,1fr);}
  .pane.inspector-pane{grid-column:1/-1;border-top:1px solid var(--fs-border-subtle);}
  .metrics{grid-template-columns:repeat(2,minmax(0,1fr));}
}
@media (max-width:799px){
  .workspace{grid-template-columns:1fr;}
  .metrics{grid-template-columns:1fr;}
}
"""


def _selection_script() -> str:
    return """
<script>
(() => {
  const activate = (id) => {
    document.querySelectorAll('[data-node-id]').forEach((el) => {
      el.classList.toggle('selected', el.getAttribute('data-node-id') === id);
    });
    const inspector = document.getElementById('inspector-body');
    const source = document.querySelector(`[data-inspector-for="${CSS.escape(id)}"]`);
    if (inspector && source) inspector.innerHTML = source.innerHTML;
  };
  document.querySelectorAll('[data-node-id]').forEach((el) => {
    el.addEventListener('click', () => activate(el.getAttribute('data-node-id')));
    el.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activate(el.getAttribute('data-node-id'));
      }
    });
  });
})();
</script>
"""


def render_report_shell(
    model: PresentationModel,
    rects: Optional[Sequence[TreemapRect]] = None,
    *,
    title: str = "FileSteward Storage Decision Map",
    selected_id: Optional[str] = None,
) -> str:
    """Compose the offline report shell string.

    Call stack:
      render_report_shell
        -> SelectionController (stable selected_id)
        -> render_token_css
        -> literal escape of receipt strings
        -> navigator + map container + inspector HTML
        -> return complete HTML document string
    """

    if not model.nodes:
        raise ValueError("presentation model has no nodes")

    controller = SelectionController(model)
    if selected_id is not None:
        controller.select(selected_id)
    current_id = controller.state.selected_id
    selected = controller.selected_node()

    # Pre-render per-node inspector bodies for JS swap without reclassification.
    inspector_templates = []
    for node in model.nodes:
        inspector_templates.append(
            f'<template data-inspector-for="{escape_attr(node.node_id)}">'
            f"{_render_inspector(node)}"
            f"</template>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape_text(title)}</title>
<style>
{render_token_css()}
{_shell_behavior_css()}
</style>
</head>
<body>
<div class="app" data-run-id="{escape_attr(model.run_id)}">
  <header class="shell">
    <h1>{escape_text(title)}</h1>
    <div class="sub">Read-only decision surface · magnitude ≠ authority · synthetic/runtime evidence only</div>
  </header>
  <section class="metrics" aria-label="Run metrics">
    <div class="metric"><b>{escape_text(model.metrics.observed_storage_label)}</b><span>Observed storage</span></div>
    <div class="metric"><b>{escape_text(model.metrics.free_space_label)}</b><span>Free space</span></div>
    <div class="metric"><b>{escape_text(model.metrics.projected_reclaim_label)}</b><span>Projected reclaim{" · " + escape_text(model.metrics.projected_reclaim_quality) if model.metrics.projected_reclaim_quality else ""}</span></div>
    <div class="metric"><b>{escape_text(model.metrics.target_free_space_label)}</b><span>Target free space</span></div>
    <div class="metric"><b class="auth">{escape_text(model.metrics.authorization_label)}</b><span>Authorization state</span></div>
  </section>
  <main class="workspace">
    <section class="pane navigator-pane" aria-label="Storage navigator">
      <div class="pane-head"><h2>Storage navigator</h2></div>
      <div class="nav" role="list">{_render_navigator(model.nodes, current_id)}</div>
    </section>
    <section class="pane map-pane" aria-label="Storage map">
      <div class="pane-head"><h2>Storage map</h2></div>
      <div class="map-wrap">{_render_map_slots(model.nodes, rects, current_id)}</div>
    </section>
    <section class="pane inspector-pane" aria-label="Decision inspector">
      <div class="pane-head"><h2>Decision inspector</h2></div>
      <div class="inspector" id="inspector-body">{_render_inspector(selected)}</div>
    </section>
  </main>
  <footer class="footer">Area communicates size. Labels and edges communicate evidence. Authorization remains separate. No destructive control exists.</footer>
</div>
{"".join(inspector_templates)}
{_selection_script()}
</body>
</html>
"""
    lowered = html.lower()
    for marker in _FORBIDDEN_CONTROL_MARKERS:
        # Allow explanatory prose that says controls do not exist; block actionable UI verbs as controls.
        if f">{marker.lower()}</button>" in lowered or f'value="{marker.lower()}"' in lowered:
            raise RuntimeError(f"forbidden control marker leaked into shell: {marker}")
    return html
