"""F5 accessibility / adversarial polish gates for the offline report."""

from __future__ import annotations

import re

from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    ScanCompleteness,
)
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
    TreemapRect,
)
from filesteward.visualization.css import render_token_css
from filesteward.visualization.html import render_report_html
from filesteward.visualization.shell import render_report_shell


def _node(
    *,
    node_id: str,
    name: str,
    path: str,
    disposition: CleanupDisposition,
    logical: int,
    steps: tuple[GateStep, ...] = (),
) -> PresentationNode:
    return PresentationNode(
        node_id=node_id,
        parent_id=None,
        display_name=name,
        path=path,
        entry_type="DIRECTORY",
        logical_size_bytes=logical,
        allocated_size_bytes=logical,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=disposition,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=ScanCompleteness.COMPLETE,
        protection_relation="UNRELATED",
        reason='synthetic <script>alert("x")</script> & "quoted"',
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="synthetic risk",
        next_gate="operator judgment",
        trace_evidence_source="fixture",
        item_count=3,
        gate_steps=steps,
    )


def _model() -> PresentationModel:
    hostile = r'C:\Users\<profile>\Local\Cache & "tmp" <script>alert(1)</script>'
    steps = (
        GateStep(
            gate_id="protection",
            name="Protected overlap",
            status=GateStepStatus.PASS,
            explanation="None observed",
        ),
        GateStep(
            gate_id="contract",
            name="Contract coverage",
            status=GateStepStatus.FAIL,
            explanation="No durable contract",
            is_first_unresolved=True,
        ),
        GateStep(
            gate_id="approval",
            name="Operator approval",
            status=GateStepStatus.WAITING,
            explanation="Not reached",
        ),
    )
    return PresentationModel(
        run_id="synthetic-f5",
        nodes=(
            _node(
                node_id="review",
                name="Ambiguous Cache",
                path=hostile,
                disposition=CleanupDisposition.HUMAN_REVIEW,
                logical=40_000_000_000,
                steps=steps,
            ),
            _node(
                node_id="reclaim",
                name="Contract Cache",
                path=r"C:\Users\<profile>\Local\ContractCache",
                disposition=CleanupDisposition.RECLAIM_PROVEN,
                logical=10_000_000_000,
            ),
            _node(
                node_id="protected",
                name="Protected Profile",
                path=r"C:\Users\<profile>\Documents",
                disposition=CleanupDisposition.PROTECTED,
                logical=5_000_000_000,
            ),
        ),
        metrics=ShellMetrics(
            observed_storage_label="55 GiB",
            free_space_label="12 GiB",
            projected_reclaim_label="10 GiB",
            projected_reclaim_quality="estimate-logical",
            target_free_space_label="40 GiB",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="review",
    )


def test_keyboard_only_selection_workflow_is_present() -> None:
    html = render_report_html(_model())
    assert "ArrowDown" in html
    assert "ArrowUp" in html
    assert "Home" in html
    assert "End" in html
    assert "event.key === 'Enter'" in html or 'event.key === "Enter"' in html
    assert "ArrowRight" in html
    assert "ArrowLeft" in html
    # Arrowing among filter chips must activate the focused chip.
    assert "activeFilter = next.getAttribute('data-filter')" in html


def test_first_unresolved_gate_leads_dom_order() -> None:
    html = render_report_shell(_model())
    lead = html.index('class="gate-lead"')
    trace = html.index('<ol class="trace">')
    assert lead < trace
    assert "First unresolved gate:" in html[lead:trace]
    # Chronological trace keeps earlier passed gates before later unresolved ones.
    trace_html = html[trace:]
    assert trace_html.index("Protected overlap") < trace_html.index("Contract coverage")
    assert 'aria-current="step"' in html


def test_hidden_filter_targets_force_display_none() -> None:
    html = render_report_shell(_model())
    assert ".nav-row[hidden],.map-node[hidden]{display:none!important;}" in html.replace(
        " ", ""
    ) or "display:none!important" in html


def test_empty_filter_clears_aria_current() -> None:
    html = render_report_html(_model())
    assert "removeAttribute('aria-current')" in html


def test_forced_colors_selected_uses_highlight_text() -> None:
    html = render_report_shell(_model())
    assert "color:HighlightText" in html
    css = render_token_css()
    assert "--fs-text-on-selected: HighlightText" in css


def test_focus_visible_and_skip_link() -> None:
    html = render_report_shell(_model())
    assert ":focus-visible" in html
    assert 'class="skip-link"' in html
    assert 'href="#inspector-body"' in html
    assert 'id="inspector-body"' in html
    assert 'tabindex="-1"' in html


def test_screen_reader_labels_cover_decision_surface() -> None:
    html = render_report_html(_model())
    assert 'aria-label="Evidence filters"' in html
    assert 'aria-label="Search paths and groups"' in html
    assert 'aria-label="Storage navigator"' in html
    assert 'aria-label="Storage map"' in html
    assert 'aria-label="Decision inspector"' in html
    assert 'aria-label="Storage items"' in html
    assert 'aria-label="Storage treemap"' in html
    assert "aria-current=" in html
    assert 'for="storage-search"' in html


def test_intermediate_1024_and_zoom_safe_layout() -> None:
    html = render_report_shell(_model())
    assert "@media (max-width:1024px)" in html
    assert "inspector-pane{grid-column:1/-1" in html.replace(" ", "")
    assert "text-size-adjust:100%" in html
    assert "overflow-x:auto" in html
    assert "min-height:clamp(" in html
    assert "user-scalable=no" not in html
    assert 'name="viewport" content="width=device-width,initial-scale=1"' in html


def test_literal_hostile_text_remains_non_executable() -> None:
    html = render_report_html(_model())
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert 'alert("x")' not in html or "&quot;" in html
    assert html.count("<script>alert(1)</script>") == 0
    assert r"\u003cscript\u003ealert(1)\u003c/script\u003e" in html


def test_state_not_color_only_and_first_unresolved_gate_dominant() -> None:
    html = render_report_shell(_model())
    assert "state-marker" in html
    assert "[HUMAN REVIEW]" in html or "[HUMAN_REVIEW]" in html.replace("_", " ")
    assert "First unresolved gate" in html
    assert 'aria-current="step"' in html
    assert "step fail unresolved" in html or "unresolved" in html
    assert re.search(r"class=\"[^\"]*unresolved[^\"]*\"", html)
    # Disposition text remains beside color classes.
    assert "state state-state-review" in html or 'state-state-review"' in html


def test_live_selection_salience_keeps_micro_bucket_and_next_gate_obvious() -> None:
    model = _model()
    rects = (
        TreemapRect(node_id="review", x=0, y=0, width=95, height=100),
        TreemapRect(node_id="reclaim", x=95, y=0, width=5, height=3),
    )
    html = render_report_shell(model, rects=rects, selected_id="reclaim")

    assert 'id="selection-summary"' in html
    assert 'data-selection-summary-for="reclaim"' in html
    assert "Run baseline free space" in html
    assert 'run <span class="mono">synthetic-f5</span>' in html
    assert 'class="map-node selected micro ' in html
    assert "map-size" in html
    assert ".map-wrap.selection-active .map-node:not(.selected)" in html
    assert ".map-node.selected.micro::after" in html
    assert "scrollIntoView({ block: 'nearest' })" in html
    assert "Next gate" in html

    # Terminal decision context must precede explanatory evidence in the inspector.
    assert html.index('class="card decision-trace"') < html.index(
        'class="card evidence"'
    )
    assert html.index('class="card next-action"') < html.index(
        'class="card evidence"'
    )


def test_forced_colors_and_high_contrast_hooks() -> None:
    css = render_token_css()
    html = render_report_html(_model())
    assert "@media (forced-colors: active)" in css
    assert "@media (prefers-contrast: more)" in css
    assert "--fs-state-review-edge: Highlight" in css
    assert "@media (forced-colors: active)" in html
    assert "forced-color-adjust:none" in html


def test_map_nodes_expose_text_state_and_geometry() -> None:
    model = _model()
    rects = (
        TreemapRect(node_id="review", x=0, y=0, width=60, height=100),
        TreemapRect(node_id="reclaim", x=60, y=0, width=40, height=100),
    )
    html = render_report_shell(model, rects=rects, selected_id="review")
    assert "map-state" in html
    assert 'aria-current="true"' in html
    assert "HUMAN REVIEW" in html
    assert "No apply control exists" in html
