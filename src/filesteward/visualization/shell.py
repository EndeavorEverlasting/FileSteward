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
from filesteward.visualization.cinematic import (
    render_cinematic_css,
    render_cinematic_script,
    render_focus_chamber,
    render_focus_templates,
    render_sector_overview,
    render_substrate_svg,
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
        is_selected = node.node_id == selected_id
        selected = " selected" if is_selected else ""
        current = ' aria-current="true"' if is_selected else ""
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
            f'aria-label="{escape_attr(aria)}"{current}>'
            f'<span class="nav-name">{escape_text(node.display_name)}</span>'
            f'<span class="nav-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="nav-meta"><span class="state state-{escape_attr(tone)}" '
            f'data-state-label="{escape_attr(_state_label(node.disposition))}">'
            f'<span class="state-marker" aria-hidden="true">'
            f'[{escape_text(_state_label(node.disposition))}]</span> '
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
        is_selected = node.node_id == selected_id
        selected = " selected" if is_selected else ""
        current = ' aria-current="true"' if is_selected else ""
        tone = disposition_css_stem(node.disposition)
        density = ""
        if rect.width < 6 or rect.height < 4:
            density = " micro"
        elif rect.width < 14 or rect.height < 8:
            density = " compact"
        aria = (
            f"{node.display_name}, {_fmt_bytes(node.logical_size_bytes)}, "
            f"{_state_label(node.disposition)}, {_auth_label(node.authorization_state)}"
        )
        title_text = (
            f"{node.path} · {_fmt_bytes(node.logical_size_bytes)} · "
            f"{_state_label(node.disposition)}"
        )
        parts.append(
            f'<button type="button" class="map-node{selected}{density} state-edge-{escape_attr(tone)}" '
            f'data-node-id="{escape_attr(node.node_id)}" '
            f'style="left:{rect.x}%;top:{rect.y}%;width:{rect.width}%;height:{rect.height}%;" '
            f'title="{escape_attr(title_text)}" '
            f'aria-label="{escape_attr(aria)}"{current}>'
            f'<span class="map-label">{escape_text(node.display_name)}</span>'
            f'<span class="map-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="map-state state state-{escape_attr(tone)}">'
            f'{escape_text(_state_label(node.disposition))}</span>'
            f"</button>"
        )
    return "\n".join(parts)


def _render_selection_summary(node: Optional[PresentationNode]) -> str:
    if node is None:
        return '<span class="selection-empty">No item selected.</span>'
    tone = disposition_css_stem(node.disposition)
    return f"""
<div class="selection-primary">
  <span class="selection-kicker">Selected</span>
  <strong class="selection-name">{escape_text(node.display_name)}</strong>
  <span class="selection-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>
</div>
<div class="selection-secondary">
  <span class="state state-{escape_attr(tone)}" data-state-label="{escape_attr(_state_label(node.disposition))}">
    <span class="state-marker" aria-hidden="true">[{escape_text(_state_label(node.disposition))}]</span>
    {escape_text(_state_label(node.disposition))}
  </span>
  <span class="selection-path mono">{escape_text(node.path)}</span>
</div>
<div class="selection-next">
  <span>Next gate</span>
  <strong>{escape_text(node.next_gate)}</strong>
</div>
"""


def _render_gate_steps(steps: Iterable[GateStep]) -> str:
    step_list = list(steps)
    rows = []
    first_unresolved: Optional[GateStep] = None
    for step in step_list:
        first = step.is_first_unresolved
        if first and first_unresolved is None:
            first_unresolved = step
        current = ' aria-current="step"' if first else ""
        badge = (
            '<div class="gate-first">First unresolved gate</div>' if first else ""
        )
        rows.append(
            f'<li class="{_gate_class(step.status, first)}"{current}>'
            f"{badge}"
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
    # Lead with a dominant callout so assistive tech hears the first unresolved
    # gate before the chronological trace; keep ol.trace in evidence order.
    lead = ""
    if first_unresolved is not None:
        lead = (
            '<p class="gate-lead" role="status">'
            "<strong>First unresolved gate:</strong> "
            f"{escape_text(first_unresolved.name)} — "
            f"{escape_text(first_unresolved.status.value)}. "
            f"{escape_text(first_unresolved.explanation)}"
            "</p>"
        )
    return f'{lead}<ol class="trace">{"".join(rows)}</ol>'


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
    <dt>Disposition</dt><dd class="state state-{escape_attr(tone)}" data-state-label="{escape_attr(_state_label(node.disposition))}"><span class="state-marker" aria-hidden="true">[{escape_text(_state_label(node.disposition))}]</span> {escape_text(_state_label(node.disposition))}</dd>
    <dt>Authorization</dt><dd class="auth">{escape_text(_auth_label(node.authorization_state))}</dd>
    <dt>Evidence source</dt><dd>{escape_text(node.trace_evidence_source)}</dd>
  </dl>
</section>
<section class="card decision-trace">
  <h3>Decision trace</h3>
  {_render_gate_steps(node.gate_steps)}
</section>
<section class="card next-action">
  <h3>Next valid action</h3>
  <p>{escape_text(node.next_gate)}</p>
</section>
<section class="card evidence">
  <h3>Evidence</h3>
  <p>{escape_text(node.reason)}</p>
</section>
<section class="card risk">
  <h3>Risk</h3>
  <p>{escape_text(node.risk_if_acted_on)}</p>
</section>
<section class="card authorization">
  <h3>Authorization</h3>
  <p class="auth">{escape_text(_auth_label(node.authorization_state))}</p>
  <p class="note">RECLAIM PROVEN evidence is not approval. No apply control exists in this report.</p>
</section>
"""


def _shell_behavior_css() -> str:
    return """
html{text-size-adjust:100%;-webkit-text-size-adjust:100%;}
html,body{margin:0;background:var(--fs-bg-canvas);color:var(--fs-text-primary);font-family:var(--fs-font-sans);}
.skip-link{position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;}
.skip-link:focus{position:static;width:auto;height:auto;display:inline-block;margin:var(--fs-space-2);padding:var(--fs-space-2) var(--fs-space-3);background:var(--fs-bg-surface-1);color:var(--fs-text-primary);border:2px solid var(--fs-focus);z-index:10;}
.app{min-height:100vh;display:grid;grid-template-rows:auto auto 1fr auto;overflow-x:auto;}
.shell{background:var(--fs-bg-shell);border-bottom:1px solid var(--fs-border-subtle);padding:var(--fs-space-4) var(--fs-space-5);}
.shell h1{margin:0;font-size:var(--fs-type-title-lg-size);line-height:var(--fs-type-title-lg-line);font-weight:var(--fs-type-title-lg-weight);}
.shell .sub{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--fs-space-2);padding:var(--fs-space-3) var(--fs-space-5);background:var(--fs-bg-surface-2);border-bottom:1px solid var(--fs-border-subtle);}
.metric{background:var(--fs-bg-surface-1);border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);padding:var(--fs-space-3);min-width:0;}
.metric b{display:block;font-variant-numeric:tabular-nums;font-size:var(--fs-type-title-size);overflow-wrap:anywhere;}
.metric span{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.workspace{display:grid;grid-template-columns:minmax(260px,320px) minmax(480px,1fr) minmax(320px,400px);min-height:0;min-width:0;}
.pane{background:var(--fs-bg-surface-1);border-right:1px solid var(--fs-border-subtle);min-width:0;}
.pane:last-child{border-right:0;}
.pane-head{min-height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 var(--fs-space-3);border-bottom:1px solid var(--fs-border-subtle);flex-wrap:wrap;gap:var(--fs-space-2);}
.pane-head h2{margin:0;font-size:var(--fs-type-small-strong-size);font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--fs-text-secondary);}
.nav{display:flex;flex-direction:column;}
.nav-row{appearance:none;border:0;border-bottom:1px solid var(--fs-border-subtle);background:transparent;color:inherit;text-align:left;display:grid;grid-template-columns:1fr auto;gap:var(--fs-space-1) var(--fs-space-2);padding:var(--fs-space-3);min-height:44px;cursor:pointer;position:relative;}
.nav-row[hidden],.map-node[hidden]{display:none!important;}
.nav-row:hover{background:var(--fs-bg-hover);}
.nav-row.selected{background:var(--fs-bg-selected);color:var(--fs-text-primary);box-shadow:inset 4px 0 0 var(--fs-accent),inset 0 0 0 1px var(--fs-accent-300);}
.nav-row.selected .nav-name{font-weight:800;}
.nav-name{font-size:var(--fs-type-body-size);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.nav-size{font-variant-numeric:tabular-nums;font-weight:700;}
.nav-meta{grid-column:1/-1;font-size:var(--fs-type-small-size);color:var(--fs-text-muted);}
.state-marker{font-weight:700;font-family:var(--fs-font-mono);margin-right:0.25em;}
.selection-summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:var(--fs-space-2) var(--fs-space-4);padding:var(--fs-space-3) var(--fs-space-4);background:var(--fs-bg-surface-1);border-bottom:2px solid var(--fs-accent);min-height:5.25rem;}
.selection-primary{display:flex;align-items:baseline;gap:var(--fs-space-2);min-width:0;}
.selection-kicker{font-size:var(--fs-type-small-size);font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--fs-accent);}
.selection-name{font-size:var(--fs-type-title-size);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.selection-size{font-variant-numeric:tabular-nums;font-weight:800;white-space:nowrap;}
.selection-secondary{grid-column:1/-1;display:flex;align-items:center;gap:var(--fs-space-2);min-width:0;}
.selection-path{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:normal;}
.selection-next{grid-column:1/-1;display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--fs-space-2);align-items:start;padding-top:var(--fs-space-1);border-top:1px solid var(--fs-border-subtle);}
.selection-next span{font-size:var(--fs-type-small-size);font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:var(--fs-text-muted);}
.selection-next strong{overflow-wrap:anywhere;}
.selection-empty{color:var(--fs-text-muted);}
.map-wrap{position:relative;min-height:clamp(16rem,42vh,26.25rem);padding:var(--fs-space-2);background:var(--fs-bg-surface-2);}
.map-placeholder,.map-node{border:1px solid var(--fs-border-default);border-radius:var(--fs-radius-treemap);background:var(--fs-bg-surface-3);color:var(--fs-text-primary);}
.map-placeholder{display:grid;place-items:center;height:100%;padding:var(--fs-space-4);color:var(--fs-text-secondary);}
.map-node{position:absolute;overflow:hidden;cursor:pointer;display:flex;flex-direction:column;justify-content:space-between;padding:var(--fs-space-1);transition:opacity 90ms linear,filter 90ms linear,box-shadow 90ms linear;}
.map-wrap.selection-active .map-node:not(.selected){opacity:.68;filter:saturate(.72) brightness(.86);}
.map-wrap.selection-active .map-node:not(.selected):hover,.map-wrap.selection-active .map-node:not(.selected):focus-visible{opacity:1;filter:none;z-index:4;}
.map-node.selected{z-index:6;outline:4px solid var(--fs-accent);outline-offset:-2px;box-shadow:0 0 0 2px var(--fs-bg-canvas),0 0 0 5px var(--fs-accent);filter:brightness(1.14) saturate(1.08);}
.map-node.selected.micro,.map-node.selected.compact{overflow:visible;}
.map-node.selected.micro::after,.map-node.selected.compact::after{content:"";position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border:3px solid var(--fs-focus);border-radius:50%;box-shadow:0 0 0 2px var(--fs-bg-canvas);pointer-events:none;}
.map-label{font-weight:750;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.map-size{font-size:var(--fs-type-small-size);font-variant-numeric:tabular-nums;font-weight:800;}
.map-state{font-size:var(--fs-type-small-size);font-weight:600;}
.map-node.compact .map-state{display:none;}
.map-node.micro .map-label,.map-node.micro .map-size,.map-node.micro .map-state{display:none;}
.state-edge-state-review{box-shadow:inset -2px -2px 0 var(--fs-state-review-edge);}
.state-edge-state-unknown{box-shadow:inset -2px -2px 0 var(--fs-state-unknown-edge);}
.state-edge-state-protected{box-shadow:inset -2px -2px 0 var(--fs-state-protected-edge);}
.state-edge-state-keep{box-shadow:inset -2px -2px 0 var(--fs-state-keep-edge);}
.state-edge-state-reclaim{box-shadow:inset -2px -2px 0 var(--fs-state-reclaim-edge);}
.inspector{padding:var(--fs-space-4);overflow:auto;}
.card{background:var(--fs-bg-surface-2);border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);padding:var(--fs-space-4);margin-bottom:var(--fs-space-3);}
.card h3{margin:0 0 var(--fs-space-2);font-size:var(--fs-type-title-size);}
.selected-item{border-color:var(--fs-accent-300);box-shadow:inset 4px 0 0 var(--fs-accent);}
.decision-trace,.next-action{border-color:var(--fs-state-review-edge);}
.decision-trace h3,.next-action h3{font-weight:800;}
.path,.mono{font-family:var(--fs-font-mono);font-size:var(--fs-type-small-size);word-break:break-all;color:var(--fs-text-secondary);}
.kv{display:grid;grid-template-columns:minmax(8rem,9rem) 1fr;gap:var(--fs-space-2);margin:0;}
.kv dt{color:var(--fs-text-muted);}
.trace{list-style:none;margin:0;padding:0;display:grid;gap:var(--fs-space-2);}
.step{border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-sm);padding:var(--fs-space-3);background:var(--fs-bg-surface-1);}
.step.pass{opacity:.72;}
.step.unresolved{border-color:var(--fs-state-review-edge);border-width:3px;font-weight:700;box-shadow:0 0 0 2px var(--fs-accent-100);background:var(--fs-bg-surface-2);}
.gate-lead{margin:0 0 var(--fs-space-3);padding:var(--fs-space-3);border:3px solid var(--fs-state-review-edge);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-2);font-weight:700;}
.gate-first{color:var(--fs-state-review);font-size:var(--fs-type-small-size);text-transform:uppercase;letter-spacing:.04em;margin-bottom:var(--fs-space-1);}
.state-state-review{color:var(--fs-state-review);}
.state-state-unknown{color:var(--fs-state-unknown);}
.state-state-protected{color:var(--fs-state-protected);}
.state-state-keep{color:var(--fs-state-keep);}
.state-state-reclaim{color:var(--fs-state-reclaim);}
.auth{font-weight:600;color:var(--fs-text-secondary);}
.note{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.footer{padding:var(--fs-space-3) var(--fs-space-5);border-top:1px solid var(--fs-border-subtle);color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
:focus-visible{outline:3px solid var(--fs-focus);outline-offset:2px;}
@media (max-width:1179px),(max-width:1024px){
  .workspace{grid-template-columns:minmax(220px,280px) minmax(0,1fr);}
  .pane.inspector-pane{grid-column:1/-1;border-top:1px solid var(--fs-border-subtle);}
  .metrics{grid-template-columns:repeat(2,minmax(0,1fr));}
}
@media (max-width:1024px){
  .workspace{grid-template-columns:minmax(12rem,16rem) minmax(0,1fr);}
  .map-wrap{min-height:clamp(12rem,36vh,22rem);}
}
@media (max-width:799px){
  .workspace{grid-template-columns:1fr;}
  .metrics{grid-template-columns:1fr;}
  .selection-summary{grid-template-columns:1fr;}
  .selection-primary{flex-wrap:wrap;}
}
@media (forced-colors: active){
  .nav-row.selected,.map-node.selected{outline:3px solid Highlight;outline-offset:-3px;background:Highlight;color:HighlightText;forced-color-adjust:none;}
  .nav-row.selected .nav-meta,.nav-row.selected .state,.nav-row.selected .state-marker,.map-node.selected .map-state,.map-node.selected .map-size{color:HighlightText;}
  .selection-summary{border-bottom:3px solid Highlight;forced-color-adjust:none;}
  .map-node.selected.micro::after,.map-node.selected.compact::after{border-color:Highlight;box-shadow:none;forced-color-adjust:none;}
  .step.unresolved,.gate-lead{border:3px solid Highlight;box-shadow:none;forced-color-adjust:none;}
  .state-marker{forced-color-adjust:none;}
  .state-edge-state-review,.state-edge-state-unknown,.state-edge-state-protected,.state-edge-state-keep,.state-edge-state-reclaim{box-shadow:inset -3px -3px 0 CanvasText;}
}
"""


def _selection_script() -> str:
    return """
<script>
(() => {
  const activate = (id) => {
    document.querySelectorAll('[data-node-id]').forEach((el) => {
      const on = el.getAttribute('data-node-id') === id;
      el.classList.toggle('selected', on);
      if (on) el.setAttribute('aria-current', 'true');
      else el.removeAttribute('aria-current');
    });
    const inspector = document.getElementById('inspector-body');
    const source = document.querySelector(`[data-inspector-for="${CSS.escape(id)}"]`);
    if (inspector && source) inspector.innerHTML = source.innerHTML;
    const summary = document.getElementById('selection-summary');
    const summarySource = Array.from(
      document.querySelectorAll('[data-selection-summary-for]')
    ).find((el) => el.getAttribute('data-selection-summary-for') === id);
    if (summary && summarySource) summary.innerHTML = summarySource.innerHTML;
    const mapWrap = document.querySelector('.map-wrap');
    if (mapWrap) mapWrap.classList.toggle('selection-active', Boolean(id));
    const navRow = Array.from(document.querySelectorAll('.nav-row')).find(
      (el) => el.getAttribute('data-node-id') === id
    );
    if (navRow) navRow.scrollIntoView({ block: 'nearest' });
    document.dispatchEvent(
      new CustomEvent('filesteward:selection', { detail: { id } })
    );
  };
  const visibleNavRows = () => Array.from(document.querySelectorAll('.nav-row:not([hidden])'));
  const moveNav = (delta, edge) => {
    const rows = visibleNavRows();
    if (!rows.length) return;
    if (edge === 'home') { rows[0].focus(); activate(rows[0].getAttribute('data-node-id')); return; }
    if (edge === 'end') { rows[rows.length - 1].focus(); activate(rows[rows.length - 1].getAttribute('data-node-id')); return; }
    const active = document.activeElement;
    let idx = rows.indexOf(active);
    if (idx < 0) {
      const selected = rows.find((r) => r.classList.contains('selected'));
      idx = selected ? rows.indexOf(selected) : 0;
    }
    const next = rows[Math.max(0, Math.min(rows.length - 1, idx + delta))];
    next.focus();
    activate(next.getAttribute('data-node-id'));
  };
  document.querySelectorAll('[data-node-id]').forEach((el) => {
    el.addEventListener('click', () => activate(el.getAttribute('data-node-id')));
    el.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activate(el.getAttribute('data-node-id'));
        return;
      }
      if (!el.classList.contains('nav-row')) return;
      if (event.key === 'ArrowDown') { event.preventDefault(); moveNav(1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); moveNav(-1); }
      else if (event.key === 'Home') { event.preventDefault(); moveNav(0, 'home'); }
      else if (event.key === 'End') { event.preventDefault(); moveNav(0, 'end'); }
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

    # Pre-render per-node inspector and selection-summary bodies for JS swap
    # without reclassification or client-side evidence inference.
    inspector_templates = []
    selection_templates = []
    for node in model.nodes:
        inspector_templates.append(
            f'<template data-inspector-for="{escape_attr(node.node_id)}">'
            f"{_render_inspector(node)}"
            f"</template>"
        )
        selection_templates.append(
            f'<template data-selection-summary-for="{escape_attr(node.node_id)}">'
            f"{_render_selection_summary(node)}"
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
{render_cinematic_css()}
</style>
</head>
<body>
<a class="skip-link" href="#inspector-body">Skip to decision inspector</a>
<div class="app" data-run-id="{escape_attr(model.run_id)}">
  <header class="shell">
    <h1>{escape_text(title)}</h1>
    <div class="sub">Read-only decision surface · magnitude ≠ authority · synthetic/runtime evidence only · run <span class="mono">{escape_text(model.run_id)}</span></div>
  </header>
  <section class="metrics" aria-label="Run metrics">
    <div class="metric"><b>{escape_text(model.metrics.observed_storage_label)}</b><span>Observed storage</span></div>
    <div class="metric"><b>{escape_text(model.metrics.free_space_label)}</b><span>Run baseline free space</span></div>
    <div class="metric"><b>{escape_text(model.metrics.projected_reclaim_label)}</b><span>Projected reclaim{" · " + escape_text(model.metrics.projected_reclaim_quality) if model.metrics.projected_reclaim_quality else ""}</span></div>
    <div class="metric"><b>{escape_text(model.metrics.target_free_space_label)}</b><span>Target free space</span></div>
    <div class="metric"><b class="auth">{escape_text(model.metrics.authorization_label)}</b><span>Authorization state</span></div>
  </section>
  <main class="workspace" id="workspace" data-scene="overview">
    <section class="pane navigator-pane" aria-label="Storage navigator">
      <div class="pane-head"><h2>Storage navigator</h2></div>
      <nav class="nav" aria-label="Storage items">{_render_navigator(model.nodes, current_id)}</nav>
    </section>
    <section class="pane map-pane" aria-label="Storage map">
      <div class="pane-head"><h2>Storage atlas</h2></div>
      <div class="storage-stage" id="storage-stage" data-scene="overview">
        {render_substrate_svg()}
        {render_sector_overview(model.nodes, current_id)}
        <section class="focus-layer" aria-label="Focused storage sector">
          <div class="scene-toolbar">
            <button type="button" class="scene-back" id="scene-back" hidden>← Sector overview</button>
            <div class="selection-summary" id="selection-summary" aria-live="polite">{_render_selection_summary(selected)}</div>
          </div>
          <div class="focus-host" id="focus-host">{render_focus_chamber(selected, model.nodes)}</div>
          <div class="context-map-shell">
            <span class="context-map-label">FULL-RUN CONTEXT · 200 EVIDENCE GROUPS</span>
            <div class="map-wrap selection-active" role="group" aria-label="Storage treemap">{_render_map_slots(model.nodes, rects, current_id)}</div>
          </div>
        </section>
      </div>
    </section>
    <section class="pane inspector-pane" aria-label="Decision inspector">
      <div class="pane-head"><h2>Decision inspector</h2></div>
      <div class="inspector" id="inspector-body" tabindex="-1">{_render_inspector(selected)}</div>
    </section>
  </main>
  <footer class="footer">The overview prioritizes readable dominant sectors; the focus context map preserves full-run magnitude. Evidence and authorization remain separate. No destructive control exists.</footer>
</div>
{"".join(inspector_templates)}
{"".join(selection_templates)}
{render_focus_templates(model.nodes)}
{_selection_script()}
{render_cinematic_script()}
</body>
</html>
"""
    lowered = html.lower()
    for marker in _FORBIDDEN_CONTROL_MARKERS:
        # Allow explanatory prose that says controls do not exist; block actionable UI verbs as controls.
        if f">{marker.lower()}</button>" in lowered or f'value="{marker.lower()}"' in lowered:
            raise RuntimeError(f"forbidden control marker leaked into shell: {marker}")
    return html
