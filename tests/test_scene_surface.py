"""Executable call stacks for U1 scenery comprehension surfaces."""

from __future__ import annotations

from dataclasses import replace

from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
    TreemapRect,
)
from filesteward.visualization.decision_flow import (
    DecisionIntent,
    open_decision_session,
)
from filesteward.visualization.scene_surface import (
    assert_noneligible_cannot_delete,
    classification_legend,
    evidence_gap_mode_brief,
    footer_ticker_items,
    metric_scene_entries,
    operator_next_actions,
    pane_scene_entries,
    path_step_previews,
    scenery_subtitle,
)
from filesteward.visualization.cinematic import render_cinematic_script
from filesteward.visualization.experience import (
    render_cinematic_experience_css,
    render_cinematic_experience_markup,
    render_cinematic_experience_script,
)
from filesteward.visualization.shell import render_report_shell


def _node(
    *,
    disposition: CleanupDisposition,
    authorization: AuthorizationState = AuthorizationState.UNAPPROVED,
    unresolved: bool = False,
) -> PresentationNode:
    return PresentationNode(
        node_id="n1",
        parent_id=None,
        display_name="sample",
        path=r"C:\synthetic\sample",
        entry_type="DIRECTORY",
        logical_size_bytes=1_000_000,
        allocated_size_bytes=1_000_000,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=disposition,
        authorization_state=authorization,
        scan_completeness=ScanCompleteness.COMPLETE,
        protection_relation=(
            "SELF" if disposition is CleanupDisposition.PROTECTED else "UNRELATED"
        ),
        reason="synthetic",
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="synthetic",
        next_gate="observation",
        trace_evidence_source="fixture",
        item_count=1,
        gate_steps=(
            GateStep(
                gate_id="observation",
                name="Observation complete",
                status=GateStepStatus.WAITING if unresolved else GateStepStatus.PASS,
                explanation="synthetic",
                is_first_unresolved=unresolved,
            ),
        ),
    )


def test_metric_entries_match_acceptance_contract_surfaces() -> None:
    entries = metric_scene_entries(
        observed_storage="1 GiB",
        free_space="8 GiB",
        projected_reclaim="0 bytes",
        projected_reclaim_quality=None,
        target_free_space="not established",
        authorization="UNAPPROVED",
    )
    ids = {entry.surface_id for entry in entries}
    assert ids == {
        "metric_observed_storage",
        "metric_baseline_free_space",
        "metric_projected_reclaim",
        "metric_target_free_space",
        "metric_authorization_state",
    }
    assert all(entry.required_action.startswith("OPEN_") for entry in entries)


def test_classification_legend_is_not_color_only() -> None:
    legend = classification_legend()
    assert len(legend) >= 5
    assert {entry.state_id for entry in legend} >= {
        "PROTECTED_BLOCKED",
        "RECLAIM_CANDIDATE",
        "KEEP_ESSENTIAL",
        "AMBIGUOUS_HUMAN_REVIEW",
        "AUTHORIZATION_LOCKED",
    }
    assert all(entry.meaning and entry.label for entry in legend)


def test_reclaim_unapproved_offers_stage_removal_and_permanent_delete() -> None:
    node = _node(disposition=CleanupDisposition.RECLAIM_PROVEN)
    flow = open_decision_session(node)
    actions = operator_next_actions(flow)
    labels = {action.label for action in actions}
    assert "STAGE REMOVAL PATH" in labels
    assert "KEEP" in labels
    assert "DELETE PERMANENTLY" in labels
    assert "STAGE REMOVAL PATH — LOCKED" not in labels
    assert any(action.intent is DecisionIntent.APPROVE_QUARANTINE for action in actions)
    assert any(action.intent is DecisionIntent.DELETE_PERMANENTLY for action in actions)
    assert any(action.action_id == "delete_permanently" for action in actions)
    assert any("NO BYTES REMOVED" in action.explanation for action in actions)


def test_unknown_surfaces_locked_stage_removal_blocker() -> None:
    node = _node(disposition=CleanupDisposition.UNKNOWN, unresolved=True)
    flow = open_decision_session(node)
    actions = operator_next_actions(flow)
    assert_noneligible_cannot_delete(actions, flow)
    by_id = {action.action_id: action for action in actions}
    assert "stage_removal_locked" in by_id
    assert "RESCAN" in {a.label for a in actions}
    assert "UNKNOWN" in by_id["stage_removal_locked"].explanation.upper()
    assert by_id["stage_removal_locked"].consequence == "READ_ONLY"


def test_protected_failure_stack_explains_lock() -> None:
    node = _node(disposition=CleanupDisposition.PROTECTED)
    actions = operator_next_actions(open_decision_session(node))
    assert len(actions) == 1
    assert actions[0].action_id == "why_locked"
    assert actions[0].intent is None


def test_path_step_previews_are_distinct_and_non_destructive() -> None:
    steps = path_step_previews()
    assert [step.step_id for step in steps] == [
        "MAP",
        "FOCUS",
        "GATE",
        "RESOLVE",
        "APPROVAL",
        "STAGED",
    ]
    labels = {step.cue_label for step in steps}
    assert len(labels) == 6
    assert any("NO BYTES REMOVED" in step.explanation for step in steps)
    assert all("PERMANENT DELETE" not in step.cue_label.upper() for step in steps)


def test_experience_markup_emits_path_step_cues() -> None:
    html = render_cinematic_experience_markup()
    assert 'data-guide-step="APPROVAL"' in html
    assert 'data-cue-label="PREVIEW GATE"' in html
    assert 'data-cursor-mode="approve"' in html
    assert 'data-cue-label="PREVIEW MAP"' in html
    assert 'data-cue-label="PREVIEW STAGED"' in html
    assert html.count("data-cue-label=") == 6
    assert 'data-drag-handle="true"' in html
    assert 'data-portal="body"' in html
    assert "atlas-home-beacon" not in html


def test_experience_script_portals_cursor_and_enacts_path() -> None:
    script = render_cinematic_experience_script()
    css = render_cinematic_experience_css()
    assert "document.body.appendChild" in script
    assert "enactPathStep" in script
    assert "filesteward:path-step" in script
    assert "filesteward:atlas-home" in script
    assert "resetHighlights" in script
    assert "atlas-range-marquee" in script
    assert "selectstart" in script
    assert "fs.decisionPath.pos" in script
    assert "2147483000" in css
    assert "returning-home" in css
    assert "html,body,.app,.app *" in css
    assert "user-select:none" in css.replace(" ", "")
    assert "document.addEventListener('selectstart'" in script
    cinematic = render_cinematic_script()
    assert "document.dispatchEvent(new CustomEvent('filesteward:atlas-home'))" in cinematic
    assert "el.classList.remove('selected')" in cinematic
    assert "placeCartoucheAway" in script
    assert "cartoucheObstacles" in script
    shell_html = render_report_shell(
        PresentationModel(
            run_id="u1-legend-glow",
            nodes=(_node(disposition=CleanupDisposition.UNKNOWN, unresolved=True),),
            metrics=ShellMetrics(
                observed_storage_label="1 GiB",
                free_space_label="8 GiB",
                projected_reclaim_label="0 bytes",
                projected_reclaim_quality=None,
                target_free_space_label="not established",
                authorization_label="UNAPPROVED",
            ),
            default_selected_id="n1",
        )
    )
    assert ".class-legend-item.is-active" in shell_html
    assert "classList.toggle('is-active'" in shell_html


def test_shell_uses_scenery_type_classes() -> None:
    reclaim = replace(
        _node(disposition=CleanupDisposition.RECLAIM_PROVEN),
        node_id="reclaim",
        item_count=None,
        scan_completeness=ScanCompleteness.INCOMPLETE,
    )
    html = render_report_shell(
        PresentationModel(
            run_id="u1-type",
            nodes=(reclaim,),
            metrics=ShellMetrics(
                observed_storage_label="1 GiB",
                free_space_label="8 GiB",
                projected_reclaim_label="0 bytes",
                projected_reclaim_quality=None,
                target_free_space_label="not established",
                authorization_label="UNAPPROVED",
            ),
            default_selected_id="reclaim",
        ),
        rects=(TreemapRect(node_id="reclaim", x=0, y=0, width=100, height=100),),
    )
    assert "fs-type-display" in html
    assert "fs-type-meta" in html
    assert '<details class="mode-brief"' in html
    assert "atlas-home-beacon" not in html
    assert "returning-home" in html
    assert "filesteward:path-step" in html
    assert "document.body.appendChild" in html


def test_evidence_gap_mode_brief_teaches_rules() -> None:
    brief = evidence_gap_mode_brief()
    assert brief.mode_id == "EVIDENCE_GAP"
    assert any("not the same as CleanupDisposition.UNKNOWN" in rule for rule in brief.rules)
    assert any("RESCAN" in choice for choice in brief.choices)


def test_pane_and_footer_surfaces_exist() -> None:
    panes = {entry.surface_id for entry in pane_scene_entries()}
    assert panes == {"pane_navigator", "pane_atlas", "pane_inspector"}
    ticker = footer_ticker_items(
        authorization="UNAPPROVED",
        disposition_label="RECLAIM PROVEN",
        scene_hint="APPROVAL",
    )
    assert any("ticker" not in item.lower() for item in ticker)
    assert any("QUARANTINE" in item for item in ticker)


def test_shell_renders_legend_metrics_and_next_actions() -> None:
    reclaim = replace(
        _node(disposition=CleanupDisposition.RECLAIM_PROVEN),
        node_id="reclaim",
        display_name="reclaim",
        path=r"C:\synthetic\reclaim",
    )
    model = PresentationModel(
        run_id="u1-comprehension",
        nodes=(reclaim,),
        metrics=ShellMetrics(
            observed_storage_label="1 GiB",
            free_space_label="8 GiB",
            projected_reclaim_label="0 bytes",
            projected_reclaim_quality=None,
            target_free_space_label="not established",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="reclaim",
    )
    html = render_report_shell(
        model,
        rects=(TreemapRect(node_id="reclaim", x=0, y=0, width=100, height=100),),
    )
    body = html.split("<body>", 1)[1]
    assert 'id="atlas-classification-legend"' in body
    assert "RECLAIM CANDIDATE" in body
    assert 'id="atlas-next-actions"' in body
    assert 'data-dock="header"' in body
    assert "STAGE REMOVAL PATH" in body
    assert "chamber-next-actions" in body
    assert 'data-scene-entry="metric_observed_storage"' in body
    assert 'id="scenery-subtitle"' in body
    assert 'data-product-version="' in body
    assert 'id="product-version"' in body
    assert 'class="pane-scene-btn"' in body
    assert 'data-scene-entry="pane_atlas"' in body
    assert "footer-ticker-track" in body
    assert "scrollbar-color" in html
    assert "delete intent opens approval" in body.lower() or "STAGE REMOVAL" in body
    assert "Delete</button>" not in body
    assert "Permanently delete</button>" not in body
    flow = open_decision_session(reclaim)
    assert "APPROVAL" in scenery_subtitle(flow, reclaim.disposition)

    gap = replace(
        reclaim,
        item_count=None,
        scan_completeness=ScanCompleteness.INCOMPLETE,
    )
    gap_model = PresentationModel(
        run_id="u1-gap-mode",
        nodes=(gap,),
        metrics=model.metrics,
        default_selected_id="reclaim",
    )
    gap_html = render_report_shell(
        gap_model,
        rects=(TreemapRect(node_id="reclaim", x=0, y=0, width=100, height=100),),
    )
    assert 'data-mode="EVIDENCE_GAP"' in gap_html
    assert "? items mode" in gap_html
