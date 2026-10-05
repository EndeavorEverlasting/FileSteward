"""F0 thin report-shell emitter.

F2 expands this into production html.py. This seam proves:
  model + tokens + literal escaping + selection hooks -> offline HTML string

It does not implement treemap geometry (F3), evidence inference (F1), or
atomic publication (F4). It never emits apply/quarantine/delete controls.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    TreemapRect,
)
from filesteward.visualization.cinematic import (
    render_atlas_runtime_json,
    render_cinematic_css,
    render_cinematic_script,
    render_focus_chamber,
    render_focus_templates,
    render_sector_bank,
    render_sector_overview,
    render_substrate_svg,
)
from filesteward.visualization.decision_chamber import (
    render_decision_chamber_css,
    render_decision_chamber_markup,
    render_decision_chamber_script,
)
from filesteward.visualization.experience import (
    render_cinematic_experience_css,
    render_cinematic_experience_markup,
    render_cinematic_experience_script,
)
from filesteward.visualization.css import render_token_css
from filesteward.visualization.decision_flow import open_decision_session
from filesteward.visualization.interaction import (
    StatusOrbKind,
    cue_for_map_node,
    cue_for_navigation,
    cue_for_status_orb,
    html_data_attrs,
)
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.scene_surface import (
    classification_legend,
    evidence_gap_mode_brief,
    footer_ticker_items,
    metric_scene_entries,
    operator_next_actions,
    pane_scene_entries,
    scenery_subtitle,
)
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
            f'<span class="nav-meta">'
            f'<span class="evidence-state-action state state-{escape_attr(tone)}" '
            f'role="button" tabindex="0" data-open-decision="true" '
            f'data-state-label="{escape_attr(_state_label(node.disposition))}" '
            f'aria-label="Open decision gate for {escape_attr(_state_label(node.disposition))}">'
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
        cue = cue_for_map_node(node, selected=is_selected)
        parts.append(
            f'<button type="button" class="map-node{selected}{density} state-edge-{escape_attr(tone)}" '
            f'data-node-id="{escape_attr(node.node_id)}" '
            f'data-rect-x="{rect.x}" data-rect-y="{rect.y}" '
            f'data-rect-w="{rect.width}" data-rect-h="{rect.height}" '
            f'style="left:{rect.x}%;top:{rect.y}%;width:{rect.width}%;height:{rect.height}%;" '
            f'{html_data_attrs(cue)} '
            f'aria-label="{escape_attr(aria)}"{current}>'
            f'<span class="map-label">{escape_text(node.display_name)}</span>'
            f'<span class="map-size">{escape_text(_fmt_bytes(node.logical_size_bytes))}</span>'
            f'<span class="map-state state state-{escape_attr(tone)}" '
            f'data-open-decision="true" data-state-label="{escape_attr(_state_label(node.disposition))}">'
            f'{escape_text(_state_label(node.disposition))}</span>'
            f"</button>"
        )
    return "\n".join(parts)


def _nav_button(
    element_id: str,
    action: str,
    label: str,
    *,
    aria: str | None = None,
) -> str:
    cue = cue_for_navigation(action)
    aria_attr = f' aria-label="{escape_attr(aria or label)}"'
    return (
        f'<button type="button" id="{escape_attr(element_id)}" '
        f'{html_data_attrs(cue)}{aria_attr}>{label}</button>'
    )


def _render_brand_home(title: str) -> str:
    """Brand/title Home affordance — same camera authority as Atlas Home.

    Terminal user value: return to Atlas camera HOME / overview.
    ENTRYPOINT: brand control. No intermediate panel. No second router.
    """

    cue = cue_for_navigation("brand_home")
    aria = f"{title} — return to Atlas home"
    return (
        f'<h1 class="brand-title">'
        f'<button type="button" id="brand-home" class="brand-home" '
        f'data-atlas-action="home" {html_data_attrs(cue)} '
        f'aria-label="{escape_attr(aria)}">'
        f"{escape_text(title)}"
        f"</button></h1>"
    )


def _render_status_orbs(node: Optional[PresentationNode]) -> str:
    if node is None:
        return (
            '<div class="atlas-status-orbs" id="atlas-status-orbs" '
            'aria-label="Status nodes" hidden></div>'
        )
    flow = open_decision_session(node)
    orbs: list[str] = []
    specs = (
        (StatusOrbKind.PROTECTED, "PROTECTED", "Protection status"),
        (StatusOrbKind.UNAPPROVED, "UNAPPROVED", "Authorization status"),
        (StatusOrbKind.EVIDENCE_GAP, "? items", "Evidence completeness"),
    )
    for kind, visible, aria in specs:
        cue = cue_for_status_orb(kind, node, flow)
        active = cue.availability.value in {"OPERABLE", "BLOCKED"}
        orbs.append(
            f'<button type="button" class="status-orb quality-{escape_attr(cue.quality_tone.value.lower())}" '
            f'data-orb-kind="{escape_attr(kind.value)}" '
            f'data-open-decision="true" '
            f'{html_data_attrs(cue)} '
            f'aria-label="{escape_attr(aria + ": " + cue.label)}" '
            f'data-orb-active="{str(active).lower()}">'
            f'<span class="status-orb-core" aria-hidden="true"></span>'
            f'<span class="status-orb-label">{escape_text(visible)}</span>'
            f"</button>"
        )
    return (
        '<div class="atlas-status-orbs" id="atlas-status-orbs" '
        'aria-label="Status nodes">'
        f'{"".join(orbs)}'
        '<svg class="status-tether" id="status-tether" aria-hidden="true" hidden></svg>'
        "</div>"
    )


def _render_action_trace() -> str:
    return """
<div class="atlas-action-trace" id="atlas-action-trace" aria-label="Camera orientation and recent commands">
  <div class="trace-current">
    <span class="trace-kicker">CAMERA</span>
    <strong id="atlas-camera-current" aria-current="true">HOME</strong>
  </div>
  <ol class="trace-history" id="atlas-command-history">
    <li data-recency="IDLE"><span>ATLAS HOME</span></li>
  </ol>
</div>
"""


def _render_metric_scene_cards(model: PresentationModel) -> str:
    entries = metric_scene_entries(
        observed_storage=model.metrics.observed_storage_label,
        free_space=model.metrics.free_space_label,
        projected_reclaim=model.metrics.projected_reclaim_label,
        projected_reclaim_quality=model.metrics.projected_reclaim_quality,
        target_free_space=model.metrics.target_free_space_label,
        authorization=model.metrics.authorization_label,
    )
    cards: list[str] = []
    for entry in entries:
        auth_attr = ' class="auth"' if entry.surface_id == "metric_authorization_state" else ""
        cards.append(
            f'<button type="button" class="metric metric-scene" '
            f'id="{escape_attr(entry.surface_id)}" '
            f'data-scene-entry="{escape_attr(entry.surface_id)}" '
            f'data-scene="{escape_attr(entry.scene)}" '
            f'data-scene-action="{escape_attr(entry.required_action)}" '
            f'data-cue-explain="{escape_attr(entry.explanation)}" '
            f'aria-label="{escape_attr(entry.label + ": " + entry.value + ". " + entry.explanation)}">'
            f"<b{auth_attr}>{escape_text(entry.value)}</b>"
            f"<span>{escape_text(entry.label)}</span>"
            f"</button>"
        )
    return "\n    ".join(cards)


def _render_mode_brief(node: Optional[PresentationNode]) -> str:
    if node is None:
        return '<aside class="mode-brief" id="mode-brief" hidden></aside>'
    flow = open_decision_session(node)
    gap_cue = cue_for_status_orb(StatusOrbKind.EVIDENCE_GAP, node, flow)
    show_gap = (
        node.item_count is None
        or node.scan_completeness is ScanCompleteness.INCOMPLETE
        or (
            gap_cue.verb.value in {"RESCAN", "EXPLAIN"}
            and "Evidence gap" in gap_cue.explanation
        )
    )
    if not show_gap:
        return '<aside class="mode-brief" id="mode-brief" hidden></aside>'
    brief = evidence_gap_mode_brief()

    def _list(title: str, rows: tuple[str, ...]) -> str:
        items = "".join(f"<li>{escape_text(row)}</li>" for row in rows)
        return f"<div><h3>{escape_text(title)}</h3><ul>{items}</ul></div>"

    return (
        f'<aside class="mode-brief" id="mode-brief" data-mode="{escape_attr(brief.mode_id)}" '
        f'aria-label="{escape_attr(brief.title)}">'
        f"<strong>{escape_text(brief.title)}</strong>"
        '<div class="mode-brief-grid">'
        f"{_list('Rules', brief.rules)}"
        f"{_list('Assumptions', brief.assumptions)}"
        f"{_list('Choices', brief.choices)}"
        "</div></aside>"
    )


def _render_classification_legend(node: Optional[PresentationNode] = None) -> str:
    items: list[str] = []
    for entry in classification_legend():
        items.append(
            f'<li class="class-legend-item quality-{escape_attr(entry.quality_tone.value.lower())}" '
            f'tabindex="0" '
            f'data-legend-state="{escape_attr(entry.state_id)}" '
            f'data-cue-label="{escape_attr(entry.label)}" '
            f'data-cue-explain="{escape_attr(entry.meaning + " " + entry.operable_hint)}" '
            f'data-cursor-mode="explore" data-actionability="INFORMATIONAL">'
            f'<span class="class-legend-swatch" aria-hidden="true"></span>'
            f'<span class="class-legend-label">{escape_text(entry.label)}</span>'
            f'<span class="class-legend-meaning">{escape_text(entry.meaning)}</span>'
            f"</li>"
        )
    return (
        '<section class="atlas-classification-legend" id="atlas-classification-legend" '
        'aria-label="Classification legend">'
        '<div class="class-legend-head">'
        "<strong>LEGEND</strong>"
        "<span>Classification ≠ authority · color is not the only signal</span>"
        "</div>"
        f'<ul class="class-legend-list">{"".join(items)}</ul>'
        '<p class="class-legend-hotkeys"><kbd>D</kbd> Decision · <kbd>Home</kbd> Atlas Home · '
        "<kbd>Esc</kbd> Back · brand title = Home</p>"
        f"{_render_mode_brief(node)}"
        "</section>"
    )


def _render_pane_head(surface_id: str) -> str:
    entry = next(item for item in pane_scene_entries() if item.surface_id == surface_id)
    return (
        '<div class="pane-head">'
        f'<button type="button" class="pane-scene-btn" id="{escape_attr(entry.surface_id)}" '
        f'data-scene-entry="{escape_attr(entry.surface_id)}" '
        f'data-scene="{escape_attr(entry.scene)}" '
        f'data-scene-action="{escape_attr(entry.required_action)}" '
        f'data-cue-label="{escape_attr(entry.label.upper())}" '
        f'data-cue-explain="{escape_attr(entry.explanation)}" '
        f'data-cursor-mode="explore" data-actionability="OPERABLE" '
        f'aria-label="{escape_attr(entry.label + ". " + entry.explanation)}">'
        f"{escape_text(entry.label)}"
        "</button></div>"
    )


def _render_footer_ticker(
    *,
    authorization: str,
    disposition_label: str | None,
    scene_hint: str,
) -> str:
    items = footer_ticker_items(
        authorization=authorization,
        disposition_label=disposition_label,
        scene_hint=scene_hint,
    )
    # Duplicate for seamless loop.
    doubled = list(items) + list(items)
    spans = "".join(f"<span>{escape_text(item)}</span>" for item in doubled)
    return (
        '<footer class="footer footer-ticker" tabindex="0" '
        'aria-label="Status ticker">'
        f'<div class="footer-ticker-track">{spans}</div>'
        "</footer>"
    )


def _render_operator_next_actions(node: Optional[PresentationNode]) -> str:
    if node is None:
        return (
            '<section class="atlas-next-actions" id="atlas-next-actions" '
            'aria-label="Next legal actions" hidden></section>'
        )
    flow = open_decision_session(node)
    actions = operator_next_actions(flow)
    buttons: list[str] = []
    for action in actions:
        intent_attr = (
            f' data-decision-intent="{escape_attr(action.intent.value)}"'
            if action.intent is not None
            else ""
        )
        open_attr = ' data-open-approval="true"' if action.opens_approval else ""
        buttons.append(
            f'<button type="button" class="next-action" '
            f'data-next-action="{escape_attr(action.action_id)}" '
            f'data-consequence="{escape_attr(action.consequence)}" '
            f'data-cue-explain="{escape_attr(action.explanation)}"'
            f"{intent_attr}{open_attr} "
            f'aria-label="{escape_attr(action.label + ". " + action.explanation)}">'
            f"<strong>{escape_text(action.label)}</strong>"
            f"<span>{escape_text(action.explanation)}</span>"
            f"</button>"
        )
    return (
        '<section class="atlas-next-actions" id="atlas-next-actions" '
        'aria-label="Next legal actions">'
        '<div class="next-actions-head">'
        "<strong>NEXT ACTIONS</strong>"
        "<span>How to classify or stage removal for the selected evidence</span>"
        "</div>"
        f'<div class="next-actions-row" role="group">{"".join(buttons)}</div>'
        "</section>"
    )


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
  <button type="button" class="evidence-state-action state state-{escape_attr(tone)}"
          data-open-decision="true"
          data-state-label="{escape_attr(_state_label(node.disposition))}"
          aria-label="Open decision gate for {escape_attr(_state_label(node.disposition))}">
    <span class="state-marker" aria-hidden="true">[{escape_text(_state_label(node.disposition))}]</span>
    {escape_text(_state_label(node.disposition))}
  </button>
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
    <dt>Disposition</dt><dd><button type="button" class="evidence-state-action state state-{escape_attr(tone)}" data-open-decision="true" data-state-label="{escape_attr(_state_label(node.disposition))}" aria-label="Open decision gate for {escape_attr(_state_label(node.disposition))}"><span class="state-marker" aria-hidden="true">[{escape_text(_state_label(node.disposition))}]</span> {escape_text(_state_label(node.disposition))}</button></dd>
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
html,body{color-scheme:dark;scrollbar-color:color-mix(in srgb,var(--fs-accent) 55%,var(--fs-bg-surface-3)) var(--fs-bg-shell);scrollbar-width:thin;}
html::-webkit-scrollbar,body::-webkit-scrollbar,.app::-webkit-scrollbar,.inspector::-webkit-scrollbar,.nav::-webkit-scrollbar,.atlas-scene-panel::-webkit-scrollbar{width:10px;height:10px;}
html::-webkit-scrollbar-track,body::-webkit-scrollbar-track,.app::-webkit-scrollbar-track,.inspector::-webkit-scrollbar-track,.nav::-webkit-scrollbar-track{background:var(--fs-bg-shell);}
html::-webkit-scrollbar-thumb,body::-webkit-scrollbar-thumb,.app::-webkit-scrollbar-thumb,.inspector::-webkit-scrollbar-thumb,.nav::-webkit-scrollbar-thumb{background:linear-gradient(180deg,color-mix(in srgb,var(--fs-accent) 70%,var(--fs-bg-surface-2)),color-mix(in srgb,var(--fs-bg-surface-3) 70%,var(--fs-accent)));border:2px solid var(--fs-bg-shell);border-radius:999px;}
html::-webkit-scrollbar-thumb:hover,body::-webkit-scrollbar-thumb:hover,.app::-webkit-scrollbar-thumb:hover{background:var(--fs-accent);}
.skip-link{position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;}
.skip-link:focus{position:static;width:auto;height:auto;display:inline-block;margin:var(--fs-space-2);padding:var(--fs-space-2) var(--fs-space-3);background:var(--fs-bg-surface-1);color:var(--fs-text-primary);border:2px solid var(--fs-focus);z-index:10;}
.app{min-height:100vh;display:grid;grid-template-rows:auto auto 1fr auto;overflow-x:auto;}
.shell{background:var(--fs-bg-shell);border-bottom:1px solid var(--fs-border-subtle);padding:var(--fs-space-4) var(--fs-space-5);}
.shell .brand-title{margin:0;font-size:var(--fs-type-title-lg-size);line-height:var(--fs-type-title-lg-line);font-weight:var(--fs-type-title-lg-weight);}
.shell .brand-home{appearance:none;border:0;background:transparent;color:inherit;font:inherit;font-size:inherit;line-height:inherit;font-weight:inherit;padding:0;margin:0;cursor:pointer;text-align:left;}
.shell .brand-home:hover{color:var(--fs-accent);}
.shell .brand-home:focus-visible{outline:2px solid var(--fs-focus);outline-offset:3px;border-radius:2px;}
@media (prefers-reduced-motion:reduce){.shell .brand-home{transition:none;}}
@media (forced-colors:active){.shell .brand-home{forced-color-adjust:auto;outline:1px solid ButtonText;}}
.shell .sub{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--fs-space-2);padding:var(--fs-space-3) var(--fs-space-5);background:var(--fs-bg-surface-2);border-bottom:1px solid var(--fs-border-subtle);}
.metric{appearance:none;display:block;width:100%;text-align:left;cursor:pointer;background:var(--fs-bg-surface-1);border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);padding:var(--fs-space-3);min-width:0;color:inherit;font:inherit;}
.metric:hover{border-color:var(--fs-accent);background:var(--fs-bg-hover);}
.metric:focus-visible{outline:2px solid var(--fs-focus);outline-offset:2px;}
.metric[aria-pressed="true"]{border-color:var(--fs-accent);box-shadow:inset 0 0 0 1px var(--fs-accent);}
.metric b{display:block;font-variant-numeric:tabular-nums;font-size:var(--fs-type-title-size);overflow-wrap:anywhere;}
.metric span{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.atlas-classification-legend{margin:.55rem 0 0;padding:.65rem .75rem;border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);background:color-mix(in srgb, var(--fs-bg-surface-1) 88%, transparent);}
.class-legend-head{display:flex;justify-content:space-between;gap:.75rem;flex-wrap:wrap;margin-bottom:.45rem;}
.class-legend-head strong{font:800 .72rem/1 var(--fs-font-mono);letter-spacing:.08em;}
.class-legend-head span,.class-legend-hotkeys{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.class-legend-list{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.45rem;}
.class-legend-item{display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;column-gap:.4rem;row-gap:.15rem;padding:.35rem .4rem;border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-2);min-width:0;}
.class-legend-swatch{width:.7rem;height:.7rem;border-radius:999px;margin-top:.2rem;grid-row:1 / span 2;background:var(--fs-text-muted);box-shadow:0 0 0 1px var(--fs-border-default);}
.class-legend-item.quality-blocked .class-legend-swatch{background:var(--fs-danger, #b56b5c);}
.class-legend-item.quality-reclaim_candidate .class-legend-swatch{background:var(--fs-accent);}
.class-legend-item.quality-essential .class-legend-swatch{background:var(--fs-success, #86A76A);}
.class-legend-item.quality-ambiguous .class-legend-swatch{background:var(--fs-warning, #D7AA82);}
.class-legend-label{font:750 .68rem/1.2 var(--fs-font-mono);letter-spacing:.04em;}
.class-legend-meaning{grid-column:2;color:var(--fs-text-secondary);font-size:.68rem;line-height:1.3;}
.atlas-next-actions{margin:.55rem 0 0;padding:.65rem .75rem;border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);background:color-mix(in srgb, var(--fs-bg-shell) 92%, var(--fs-accent) 8%);}
.next-actions-head{display:flex;justify-content:space-between;gap:.75rem;flex-wrap:wrap;margin-bottom:.45rem;}
.next-actions-head strong{font:800 .72rem/1 var(--fs-font-mono);letter-spacing:.08em;}
.next-actions-head span{color:var(--fs-text-muted);font-size:var(--fs-type-small-size);}
.next-actions-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.45rem;}
.next-action{appearance:none;border:1px solid var(--fs-border-default);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-1);color:inherit;text-align:left;padding:.55rem .65rem;cursor:pointer;min-height:44px;}
.next-action:hover,.next-action:focus-visible{border-color:var(--fs-accent);outline:2px solid var(--fs-focus);outline-offset:1px;}
.next-action strong{display:block;font:800 .74rem/1.2 var(--fs-font-mono);letter-spacing:.05em;margin-bottom:.25rem;}
.next-action span{display:block;color:var(--fs-text-secondary);font-size:.72rem;line-height:1.35;}
.atlas-scene-panel{margin:.55rem 0 0;padding:.7rem .8rem;border:1px solid var(--fs-accent);border-radius:var(--fs-radius-md);background:var(--fs-bg-surface-1);}
.atlas-scene-panel[hidden]{display:none!important;}
.atlas-scene-panel strong{display:block;font:800 .78rem/1.2 var(--fs-font-mono);letter-spacing:.06em;margin-bottom:.3rem;}
@media (max-width:1100px){.class-legend-list{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media (max-width:720px){.class-legend-list{grid-template-columns:1fr;}}
.workspace{display:grid;grid-template-columns:minmax(260px,320px) minmax(480px,1fr) minmax(320px,400px);min-height:0;min-width:0;}
.pane{background:var(--fs-bg-surface-1);border-right:1px solid var(--fs-border-subtle);min-width:0;}
.pane:last-child{border-right:0;}
.pane-head{min-height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 var(--fs-space-3);border-bottom:1px solid var(--fs-border-subtle);flex-wrap:wrap;gap:var(--fs-space-2);}
.pane-head h2,.pane-scene-btn{margin:0;font-size:var(--fs-type-small-strong-size);font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--fs-text-secondary);}
.pane-scene-btn{appearance:none;border:1px solid transparent;background:transparent;padding:.35rem .45rem;border-radius:var(--fs-radius-sm);cursor:pointer;color:inherit;}
.pane-scene-btn:hover,.pane-scene-btn:focus-visible{border-color:var(--fs-accent);color:var(--fs-text-primary);outline:2px solid var(--fs-focus);outline-offset:1px;}
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
.footer{padding:0;border-top:1px solid var(--fs-border-subtle);color:var(--fs-text-muted);font-size:var(--fs-type-small-size);overflow:hidden;background:var(--fs-bg-shell);}
.footer-ticker{display:flex;align-items:center;min-height:2.4rem;mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent);}
.footer-ticker-track{display:flex;gap:2.5rem;white-space:nowrap;width:max-content;padding:.65rem var(--fs-space-5);animation:fs-ticker 42s linear infinite;}
.footer-ticker:hover .footer-ticker-track,.footer-ticker:focus-within .footer-ticker-track{animation-play-state:paused;}
.footer-ticker-track span{display:inline-flex;align-items:center;gap:.45rem;}
.footer-ticker-track span::before{content:"";width:.35rem;height:.35rem;border-radius:999px;background:var(--fs-accent);box-shadow:0 0 8px color-mix(in srgb,var(--fs-accent) 55%,transparent);}
@keyframes fs-ticker{from{transform:translateX(0);}to{transform:translateX(-50%);}}
@media (prefers-reduced-motion:reduce){.footer-ticker-track{animation:none;flex-wrap:wrap;width:auto;white-space:normal;}}
.mode-brief{margin:.45rem 0 0;padding:.55rem .7rem;border:1px solid color-mix(in srgb,var(--fs-warning,#D7AA82) 55%,var(--fs-border-subtle));border-radius:var(--fs-radius-md);background:color-mix(in srgb,var(--fs-bg-surface-1) 90%,var(--fs-warning,#D7AA82) 10%);}
.mode-brief[hidden]{display:none!important;}
.mode-brief strong{display:block;font:800 .72rem/1.2 var(--fs-font-mono);letter-spacing:.06em;margin-bottom:.35rem;}
.mode-brief-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;}
.mode-brief-grid h3{margin:0 0 .2rem;font:750 .66rem/1 var(--fs-font-mono);letter-spacing:.05em;color:var(--fs-text-secondary);}
.mode-brief-grid ul{margin:0;padding-left:1rem;color:var(--fs-text-secondary);font-size:.7rem;line-height:1.35;}
@media (max-width:900px){.mode-brief-grid{grid-template-columns:1fr;}}
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
  .status-orb,.atlas-action-trace{forced-color-adjust:none;border-color:CanvasText;background:Canvas;color:CanvasText;box-shadow:none;}
  .status-orb[data-actionability="OPERABLE"] .status-orb-core,
  .status-orb[data-actionability="BLOCKED"] .status-orb-core{outline:2px solid Highlight;}
}
/* V4-D interaction grammar: quality polarity + status orbs + camera memory */
.atlas-action-trace{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem;min-height:40px;padding:.25rem .45rem;border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-2);}
.atlas-action-trace .trace-kicker{font:800 .62rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);}
.atlas-action-trace #atlas-camera-current{font:800 .85rem/1.1 var(--fs-font-mono);color:var(--fs-accent);text-shadow:0 0 12px color-mix(in srgb,var(--fs-accent) 45%,transparent);}
.trace-history{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.35rem;}
.trace-history li{font:700 .68rem/1.2 var(--fs-font-mono);padding:.2rem .4rem;border-radius:3px;border:1px solid var(--fs-border-subtle);opacity:.55;}
.trace-history li[data-recency="LAST"]{opacity:1;border-color:color-mix(in srgb,var(--fs-accent) 55%,var(--fs-border-default));box-shadow:0 0 10px color-mix(in srgb,var(--fs-accent) 28%,transparent);}
.trace-history li[data-recency="RECENT"]{opacity:.78;border-color:color-mix(in srgb,var(--fs-accent) 30%,var(--fs-border-default));}
.atlas-hud .atlas-status-orbs{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin-left:.25rem;}
.status-orb{appearance:none;display:inline-flex;align-items:center;gap:.45rem;min-height:40px;min-width:40px;padding:.35rem .65rem;border-radius:999px;border:1px solid var(--fs-border-default);background:var(--fs-bg-surface-2);color:var(--fs-text-primary);font:800 .68rem/1 var(--fs-font-mono);letter-spacing:.04em;cursor:pointer;pointer-events:auto;}
.status-orb-core{width:12px;height:12px;border-radius:50%;background:currentColor;box-shadow:0 0 0 2px color-mix(in srgb,currentColor 25%,transparent);}
.status-orb.quality-blocked{color:var(--fs-state-protected-edge);border-color:color-mix(in srgb,var(--fs-state-protected-edge) 55%,var(--fs-border-default));}
.status-orb.quality-essential{color:var(--fs-state-keep-edge);border-color:color-mix(in srgb,var(--fs-state-keep-edge) 55%,var(--fs-border-default));}
.status-orb.quality-reclaim_candidate{color:var(--fs-state-reclaim-edge);border-color:color-mix(in srgb,var(--fs-state-reclaim-edge) 55%,var(--fs-border-default));}
.status-orb.quality-ambiguous{color:var(--fs-state-review-edge);border-color:color-mix(in srgb,var(--fs-state-review-edge) 55%,var(--fs-border-default));}
.status-orb[data-actionability="OPERABLE"] .status-orb-core,
.status-orb[data-actionability="BLOCKED"] .status-orb-core{
  animation:fs-orb-pulse 1500ms ease-in-out infinite;
  box-shadow:0 0 0 2px color-mix(in srgb,currentColor 30%,transparent),0 0 16px color-mix(in srgb,currentColor 55%,transparent);
}
.status-orb[data-actionability="BLOCKED"]{cursor:help;}
.status-orb[data-actionability="INFORMATIONAL"]{opacity:.55;}
@keyframes fs-orb-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
.map-node[data-quality-tone="BLOCKED"],.map-node[data-quality-tone="ESSENTIAL"],
.map-node[data-quality-tone="RECLAIM_CANDIDATE"],.map-node[data-quality-tone="AMBIGUOUS"]{
  box-shadow:inset -2px -2px 0 currentColor;
}
.map-node[data-quality-tone="BLOCKED"]{color:var(--fs-state-protected-edge);}
.map-node[data-quality-tone="ESSENTIAL"]{color:var(--fs-state-keep-edge);}
.map-node[data-quality-tone="RECLAIM_CANDIDATE"]{color:var(--fs-state-reclaim-edge);}
.map-node[data-quality-tone="AMBIGUOUS"]{color:var(--fs-state-review-edge);}
.map-node[data-actionability="OPERABLE"]:focus-visible,
.status-orb:focus-visible{outline:3px solid var(--fs-focus);outline-offset:2px;}
.atlas-hud button[data-recency="LAST"]{box-shadow:0 0 0 1px color-mix(in srgb,var(--fs-accent) 50%,transparent),0 0 14px color-mix(in srgb,var(--fs-accent) 30%,transparent);}
.atlas-hud button[data-recency="RECENT"]{box-shadow:0 0 10px color-mix(in srgb,var(--fs-accent) 16%,transparent);}
@media (prefers-reduced-motion:reduce){
  .status-orb[data-actionability="OPERABLE"] .status-orb-core,
  .status-orb[data-actionability="BLOCKED"] .status-orb-core{animation:none;}
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
      if (on) {
        el.setAttribute('data-selected', 'true');
        el.setAttribute('aria-selected', 'true');
        el.setAttribute('aria-current', 'true');
      } else {
        el.removeAttribute('data-selected');
        el.removeAttribute('aria-selected');
        el.removeAttribute('aria-current');
      }
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
      else if (event.key === 'End') { event.preventDefault(); moveNav(0, 'end'); }
    });
  });

  const scenePanel = document.getElementById('atlas-scene-panel');
  const sceneTitle = document.getElementById('atlas-scene-panel-title');
  const sceneBody = document.getElementById('atlas-scene-panel-body');
  const openScene = (scene, explain, action) => {
    if (!scenePanel) return;
    if (sceneTitle) sceneTitle.textContent = scene || 'SCENE';
    if (sceneBody) sceneBody.textContent = (action ? action + ' — ' : '') + (explain || '');
    scenePanel.hidden = false;
  };
  document.querySelectorAll('[data-scene-entry]').forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll('[data-scene-entry]').forEach((other) => {
        other.setAttribute('aria-pressed', other === el ? 'true' : 'false');
      });
      const scene = el.getAttribute('data-scene');
      const action = el.getAttribute('data-scene-action');
      openScene(scene, el.getAttribute('data-cue-explain'), action);
      const atlas = window.FileStewardAtlas;
      const workspace = document.getElementById('workspace');
      if (action === 'OPEN_NAVIGATOR_SCENE' && atlas && typeof atlas.search === 'function') {
        if (workspace) workspace.dataset.navOpen = 'true';
        atlas.search();
      } else if (action === 'OPEN_ATLAS_SCENE' && atlas && typeof atlas.home === 'function') {
        atlas.home();
        const stage = document.getElementById('storage-stage');
        if (stage) stage.focus();
      } else if (action === 'OPEN_INSPECTOR_SCENE') {
        if (atlas && typeof atlas.toggle_decision === 'function'
            && workspace && workspace.dataset.decisionOpen !== 'true') {
          atlas.toggle_decision();
        }
        const inspector = document.getElementById('inspector-body');
        if (inspector) inspector.focus();
      }
    });
  });
  document.querySelectorAll('.next-action').forEach((el) => {
    el.addEventListener('click', () => {
      const explain = el.getAttribute('data-cue-explain') || '';
      const label = (el.querySelector('strong') && el.querySelector('strong').textContent) || 'NEXT';
      openScene(label, explain, el.getAttribute('data-consequence'));
      if (el.getAttribute('data-open-approval') === 'true' || el.getAttribute('data-decision-intent')) {
        const atlas = window.FileStewardAtlas;
        if (atlas && typeof atlas.toggle_decision === 'function') atlas.toggle_decision();
        const decisionBtn = document.getElementById('atlas-decision');
        if (decisionBtn) decisionBtn.focus();
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
    selected_flow = open_decision_session(selected) if selected is not None else None
    dynamic_sub = (
        scenery_subtitle(selected_flow, selected.disposition)
        if selected is not None and selected_flow is not None
        else "Read-only decision surface · magnitude ≠ authority · synthetic/runtime evidence only"
    )

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
{render_cinematic_experience_css()}
{render_decision_chamber_css()}
</style>
</head>
<body>
<a class="skip-link" href="#storage-stage">Skip to storage atlas</a>
<a class="skip-link" href="#inspector-body">Skip to decision inspector</a>
<div class="app" data-run-id="{escape_attr(model.run_id)}">
  <header class="shell">
    {_render_brand_home(title)}
    <div class="sub" id="scenery-subtitle">{escape_text(dynamic_sub)} · run <span class="mono">{escape_text(model.run_id)}</span></div>
    {_render_classification_legend(selected)}
    {_render_operator_next_actions(selected)}
    <aside class="atlas-scene-panel" id="atlas-scene-panel" hidden aria-live="polite">
      <strong id="atlas-scene-panel-title">SCENE</strong>
      <span id="atlas-scene-panel-body">Activate a metric or legend cue to open its scenery explanation.</span>
    </aside>
  </header>
  <section class="metrics" aria-label="Run metrics">
    {_render_metric_scene_cards(model)}
  </section>
  <main class="workspace" id="workspace" data-scene="overview" data-camera-level="HOME">
    <section class="pane navigator-pane" aria-label="Storage navigator">
      {_render_pane_head("pane_navigator")}
      <nav class="nav" aria-label="Storage items">{_render_navigator(model.nodes, current_id)}</nav>
    </section>
    <section class="pane map-pane" aria-label="Storage map">
      {_render_pane_head("pane_atlas")}
      <div class="atlas-hud" role="toolbar" aria-label="Atlas camera">
        <span class="atlas-level" id="atlas-level">CAMERA HOME</span>
        {_render_action_trace()}
        {_nav_button("atlas-home", "home", "⌂ Atlas Home <kbd>Home</kbd>", aria="Return to Atlas home")}
        {_nav_button("atlas-zoom-out", "zoom_out", "Zoom -", aria="Zoom out")}
        {_nav_button("atlas-zoom-in", "zoom_in", "Zoom +", aria="Zoom in")}
        {_nav_button("atlas-search", "search", "Search")}
        {_nav_button("atlas-fit", "fit_selected", "Fit selected")}
        {_nav_button("atlas-open", "open", "Open")}
        {_nav_button("atlas-decision", "decision", "Decision")}
        {_render_status_orbs(selected)}
      </div>
      <div class="storage-stage" id="storage-stage" data-scene="overview" data-camera-level="HOME" tabindex="-1">
        {render_substrate_svg()}
        {render_cinematic_experience_markup()}
        {render_decision_chamber_markup()}
        {render_sector_overview(model.nodes, current_id)}
        {render_sector_bank(model.nodes, current_id)}
        <section class="fabric-layer" aria-label="Evidence fabric">
          <div class="camera-plane" id="camera-plane">
            <div class="map-wrap selection-active" role="group" aria-label="Storage treemap">{_render_map_slots(model.nodes, rects, current_id)}</div>
          </div>
        </section>
        <section class="focus-layer" aria-label="Focused storage sector">
          <div class="scene-toolbar">
            <button type="button" class="scene-back" id="scene-back" hidden>← Sector overview</button>
            <div class="selection-summary" id="selection-summary" aria-live="polite">{_render_selection_summary(selected)}</div>
          </div>
          <div class="focus-host" id="focus-host">{render_focus_chamber(selected, model.nodes)}</div>
          <div class="context-map-shell">
            <span class="context-map-label">FULL-RUN CONTEXT · {len(model.nodes):,} EVIDENCE GROUPS</span>
            <div class="map-wrap selection-active" role="group" aria-label="Chamber context treemap">{_render_map_slots(model.nodes, rects, current_id)}</div>
          </div>
        </section>
      </div>
      <div class="phone-command-bar" role="toolbar" aria-label="Phone atlas commands">
        <button type="button" data-atlas-action="home" aria-label="Return to Atlas home">⌂ Home</button>
        <button type="button" data-atlas-action="search">Search</button>
        <button type="button" data-atlas-action="zoom_out" aria-label="Zoom out">Zoom -</button>
        <button type="button" data-atlas-action="zoom_in" aria-label="Zoom in">Zoom +</button>
        <button type="button" data-atlas-action="toggle_decision">Decision</button>
      </div>
    </section>
    <section class="pane inspector-pane" aria-label="Decision inspector">
      {_render_pane_head("pane_inspector")}
      <div class="inspector" id="inspector-body" tabindex="-1">{_render_inspector(selected)}</div>
    </section>
  </main>
  {_render_footer_ticker(
      authorization=model.metrics.authorization_label,
      disposition_label=_state_label(selected.disposition) if selected is not None else None,
      scene_hint=selected_flow.scene.value if selected_flow is not None else "MAP",
  )}
</div>
{"".join(inspector_templates)}
{"".join(selection_templates)}
{render_focus_templates(model.nodes)}
{render_atlas_runtime_json(model.nodes, rects)}
{_selection_script()}
{render_cinematic_script()}
{render_cinematic_experience_script()}
{render_decision_chamber_script()}
</body>
</html>
"""
    lowered = html.lower()
    for marker in _FORBIDDEN_CONTROL_MARKERS:
        # Allow explanatory prose that says controls do not exist; block actionable UI verbs as controls.
        if f">{marker.lower()}</button>" in lowered or f'value="{marker.lower()}"' in lowered:
            raise RuntimeError(f"forbidden control marker leaked into shell: {marker}")
    return html
