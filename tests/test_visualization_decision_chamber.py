"""V4-C Decision Chamber wiring regressions."""

from __future__ import annotations

from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
)
from filesteward.visualization.shell import render_report_shell


def _node(
    node_id: str,
    disposition: CleanupDisposition,
    *,
    gate_id: str = "observation",
) -> PresentationNode:
    return PresentationNode(
        node_id=node_id,
        parent_id=None,
        display_name=node_id,
        path=rf"C:\synthetic\{node_id}",
        entry_type="DIRECTORY",
        logical_size_bytes=1_000_000,
        allocated_size_bytes=1_000_000,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=disposition,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=ScanCompleteness.INCOMPLETE,
        protection_relation="UNRELATED",
        reason="synthetic",
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="synthetic",
        next_gate=gate_id,
        trace_evidence_source="fixture",
        item_count=1,
        gate_steps=(
            GateStep(
                gate_id=gate_id,
                name=gate_id,
                status=GateStepStatus.WAITING,
                explanation="synthetic unresolved",
                is_first_unresolved=True,
            ),
        ),
    )


def _model() -> PresentationModel:
    nodes = (
        _node("unknown", CleanupDisposition.UNKNOWN),
        _node("review", CleanupDisposition.HUMAN_REVIEW, gate_id="contract"),
        _node("reclaim", CleanupDisposition.RECLAIM_PROVEN, gate_id="disposition"),
        _node("keep", CleanupDisposition.KEEP_PROVEN, gate_id="disposition"),
    )
    return PresentationModel(
        run_id="synthetic-v4c",
        nodes=nodes,
        metrics=ShellMetrics(
            observed_storage_label="1 GiB",
            free_space_label="8 GiB",
            projected_reclaim_label="0 bytes",
            projected_reclaim_quality=None,
            target_free_space_label="not established",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="unknown",
    )


def test_unknown_status_is_operable_and_opens_gate_scene() -> None:
    html = render_report_shell(_model())
    assert 'data-open-decision="true"' in html
    assert "openDecisionScene" in html
    assert "selectedNodeId" in html
    assert "activeGateId" in html
    assert "localOpenGate" in html or "open_decision_session" in html
    assert "GATE" in html
    assert "chamber-brief" in html
    assert "confirm_staging_offline" in html
    assert "sceneBrief" in html
    assert "filesteward:atlas-home" in html
    assert "requestedScene" in html
    assert "approval_locked_no_reclaim_authority" in html
    assert "GATE — inspect the first unresolved evidence gate" in html
    assert "RESOLVE — only decision_flow.allowed_intents()" in html
    assert "APPROVAL — authorize exact quarantine scope" in html
    assert "chamber-next-actions" in html
    assert "stage_removal_locked" in html
    assert "sceneForDispositionLabel" in html
    assert "STAGE REMOVAL LOCKED" in html
    assert "APPROVE_QUARANTINE" in html  # present in script path for reclaim only
    assert "NO BYTES REMOVED" in html


def test_orientation_markers_are_distinct() -> None:
    html = render_report_shell(_model())
    assert 'data-selected="true"' in html or "setAttribute('data-selected'" in html
    assert "aria-selected" in html
    assert 'aria-current="step"' in html
    assert "data-last-completed" in html
    assert "data-active" in html


def test_no_direct_permanent_delete_control() -> None:
    html = render_report_shell(_model()).lower()
    assert "permanently delete</button>" not in html
    assert "delete</button>" not in html
    assert "/api/v1/delete" not in html
    assert "confirm staging" in html


def test_staged_copy_and_warm_palette_contract_remain_present() -> None:
    html = render_report_shell(_model())
    assert "STAGED — QUARANTINE REQUIRED — NO BYTES REMOVED" in html
    assert "#15120F" in html or "--fs-bg-canvas" in html
    assert "decision-chamber" in html
    assert "quarantine-rail" in html


def test_fetch_state_does_not_force_staged_over_server_approval() -> None:
    html = render_report_shell(_model())
    assert "sceneCompatibleWithServer" in html
    assert "Never force STAGED when server is on APPROVAL" in html
    # Blind overwrite of openDecisionScene from requestedScene is gone.
    assert "absorbState(await response.json());\n    if (requestedScene) {\n      state.openDecisionScene = requestedScene;" not in html
    assert "sceneCompatibleWithServer(requestedScene, payload)" in html
    assert "runtime.scanRoot" in html or "bridge.scanRoot" in html
    assert "delete_permanently_missing_scan_root" in html
