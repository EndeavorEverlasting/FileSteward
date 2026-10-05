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
    assert_no_permanent_delete_actions,
    classification_legend,
    metric_scene_entries,
    operator_next_actions,
    scenery_subtitle,
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


def test_reclaim_unapproved_offers_stage_removal_not_permanent_delete() -> None:
    node = _node(disposition=CleanupDisposition.RECLAIM_PROVEN)
    flow = open_decision_session(node)
    actions = operator_next_actions(flow)
    assert_no_permanent_delete_actions(actions)
    labels = {action.label for action in actions}
    assert "STAGE REMOVAL PATH" in labels
    assert "KEEP" in labels
    assert any(action.intent is DecisionIntent.APPROVE_QUARANTINE for action in actions)
    assert all("PERMANENT" not in action.label.upper() for action in actions)
    assert any("NO BYTES REMOVED" in action.explanation for action in actions)


def test_protected_failure_stack_explains_lock() -> None:
    node = _node(disposition=CleanupDisposition.PROTECTED)
    actions = operator_next_actions(open_decision_session(node))
    assert len(actions) == 1
    assert actions[0].action_id == "why_locked"
    assert actions[0].intent is None


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
    assert "STAGE REMOVAL PATH" in body
    assert 'data-scene-entry="metric_observed_storage"' in body
    assert 'id="scenery-subtitle"' in body
    assert "delete intent opens approval" in body.lower() or "STAGE REMOVAL" in body
    assert "Delete</button>" not in body
    assert "Permanently delete</button>" not in body
    flow = open_decision_session(reclaim)
    assert "APPROVAL" in scenery_subtitle(flow, reclaim.disposition)
