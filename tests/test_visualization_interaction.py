"""Atlas Interaction Grammar projection — presentation-only seams."""

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
    DecisionFlowState,
    DecisionIntent,
    DecisionScene,
    open_decision_session,
)
from filesteward.visualization.interaction import (
    Availability,
    Consequence,
    InteractionVerb,
    QualityTone,
    Recency,
    StatusOrbKind,
    TargetKind,
    cue_for_camera_command,
    cue_for_intent,
    cue_for_map_node,
    cue_for_navigation,
    cue_for_status_orb,
    html_data_attrs,
)
from filesteward.visualization.shell import render_report_shell


def _node(
    *,
    disposition: CleanupDisposition,
    authorization: AuthorizationState = AuthorizationState.UNAPPROVED,
    completeness: ScanCompleteness = ScanCompleteness.COMPLETE,
    item_count: int | None = 3,
    gate_status: GateStepStatus = GateStepStatus.PASS,
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
        scan_completeness=completeness,
        protection_relation="SELF" if disposition is CleanupDisposition.PROTECTED else "UNRELATED",
        reason="synthetic",
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="synthetic",
        next_gate="observation",
        trace_evidence_source="fixture",
        item_count=item_count,
        gate_steps=(
            GateStep(
                gate_id="observation",
                name="Observation complete",
                status=gate_status,
                explanation="synthetic",
                is_first_unresolved=unresolved,
            ),
        ),
    )


def test_map_node_cues_distinguish_explore_focus_and_protected() -> None:
    reclaim = _node(disposition=CleanupDisposition.RECLAIM_PROVEN)
    protected = _node(disposition=CleanupDisposition.PROTECTED)

    explore = cue_for_map_node(reclaim, selected=False)
    focus = cue_for_map_node(reclaim, selected=True)
    block = cue_for_map_node(protected, selected=False)

    assert explore.verb is InteractionVerb.EXPLORE
    assert explore.quality_tone is QualityTone.RECLAIM_CANDIDATE
    assert focus.verb is InteractionVerb.FOCUS
    assert block.verb is InteractionVerb.INSPECT_BLOCK
    assert block.quality_tone is QualityTone.BLOCKED
    assert "title=" not in html_data_attrs(explore)


def test_navigation_cues_are_deterministic() -> None:
    assert cue_for_navigation("zoom_in").label == "DIVE IN · Zoom +"
    assert cue_for_navigation("zoom_out").verb is InteractionVerb.PULL_BACK
    assert cue_for_navigation("fit_selected").verb is InteractionVerb.FRAME
    assert cue_for_navigation("search").verb is InteractionVerb.LOCATE
    assert cue_for_navigation("decision").verb is InteractionVerb.RESOLVE
    assert cue_for_navigation("home").consequence is Consequence.READ_ONLY
    brand = cue_for_navigation("brand_home")
    assert brand.verb is InteractionVerb.RETURN
    assert brand.consequence is Consequence.READ_ONLY
    assert brand.label == cue_for_navigation("home").label


def test_brand_title_is_truthful_home_affordance() -> None:
    reclaim = replace(
        _node(disposition=CleanupDisposition.RECLAIM_PROVEN),
        node_id="reclaim",
        display_name="reclaim",
        path=r"C:\synthetic\reclaim",
    )
    model = PresentationModel(
        run_id="synthetic-brand-home",
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
        title="FileSteward Storage Decision Map",
    )
    body = html.split("<body>", 1)[1]

    assert 'id="brand-home"' in body
    assert 'data-atlas-action="home"' in body
    assert "brand-home" in body
    assert 'data-action="RETURN"' in body
    assert "return to Atlas home" in body
    assert 'id="atlas-home"' in body
    # Negative: inert plain title heading without Home action is gone.
    assert "<h1>FileSteward Storage Decision Map</h1>" not in body
    assert 'data-atlas-action="delete"' not in body.lower()
    assert "PERMANENT_DELETE" not in body
    assert "title=" not in body
    assert "returning-home" in body


def test_camera_current_state_is_not_historical_command() -> None:
    current = cue_for_camera_command("zoom_in", recency=Recency.LAST, is_current_state=True)
    last = cue_for_camera_command("zoom_in", recency=Recency.LAST, is_current_state=False)
    assert current.recency is Recency.CURRENT
    assert "Current camera orientation" in current.explanation
    assert last.recency is Recency.LAST


def test_unapproved_orb_approves_only_when_decision_flow_allows() -> None:
    reclaim = _node(disposition=CleanupDisposition.RECLAIM_PROVEN)
    protected = _node(disposition=CleanupDisposition.PROTECTED)
    reclaim_flow = open_decision_session(reclaim)
    protected_flow = open_decision_session(protected)

    approve = cue_for_status_orb(StatusOrbKind.UNAPPROVED, reclaim, reclaim_flow)
    locked = cue_for_status_orb(StatusOrbKind.UNAPPROVED, protected, protected_flow)

    assert approve.verb is InteractionVerb.APPROVE
    assert approve.availability is Availability.OPERABLE
    assert approve.consequence is Consequence.WRITE_APPROVAL
    assert locked.verb is InteractionVerb.WHY_LOCKED
    assert locked.availability is Availability.BLOCKED


def test_evidence_gap_orb_is_not_cleanup_disposition_unknown() -> None:
    gap = _node(
        disposition=CleanupDisposition.HUMAN_REVIEW,
        completeness=ScanCompleteness.INCOMPLETE,
        item_count=None,
        gate_status=GateStepStatus.WAITING,
        unresolved=True,
    )
    flow = open_decision_session(gap)
    cue = cue_for_status_orb(StatusOrbKind.EVIDENCE_GAP, gap, flow)
    assert cue.verb in {InteractionVerb.EXPLAIN, InteractionVerb.RESCAN}
    assert "CleanupDisposition.UNKNOWN" in cue.explanation
    assert cue.target_kind is TargetKind.STATUS


def test_intent_cue_never_invents_illegal_actions() -> None:
    node = _node(disposition=CleanupDisposition.PROTECTED)
    flow = DecisionFlowState(
        selected_node_id=node.node_id,
        scene=DecisionScene.CLOSED,
        disposition=CleanupDisposition.PROTECTED,
        authorization_state=AuthorizationState.UNAPPROVED,
    )
    cue = cue_for_intent(DecisionIntent.APPROVE_QUARANTINE, flow)
    assert cue.verb is InteractionVerb.LOCKED
    assert cue.availability is Availability.UNAVAILABLE


def test_shell_emits_interaction_attrs_and_no_native_map_title() -> None:
    protected = replace(
        _node(disposition=CleanupDisposition.PROTECTED),
        node_id="protected",
        display_name="protected",
        path=r"C:\synthetic\protected",
    )
    reclaim = replace(
        _node(disposition=CleanupDisposition.RECLAIM_PROVEN),
        node_id="reclaim",
        display_name="reclaim",
        path=r"C:\synthetic\reclaim",
    )
    model = PresentationModel(
        run_id="synthetic-interaction",
        nodes=(protected, reclaim),
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
        rects=(
            TreemapRect(node_id="protected", x=0, y=0, width=40, height=50),
            TreemapRect(node_id="reclaim", x=40, y=0, width=60, height=50),
        ),
    )

    # Page <title> remains; Atlas interaction nodes must not emit native title=
    body = html.split("<body>", 1)[1]
    assert "title=" not in body
    assert 'data-target-kind="EVIDENCE"' in body
    assert 'data-action="INSPECT_BLOCK"' in body
    assert 'data-quality-tone="BLOCKED"' in body
    assert 'data-quality-tone="RECLAIM_CANDIDATE"' in body
    assert 'id="atlas-status-orbs"' in body
    assert 'id="atlas-action-trace"' in body
    assert 'id="atlas-cartouche"' in body
    assert 'data-orb-kind="PROTECTED"' in body
    assert 'data-orb-kind="UNAPPROVED"' in body
    assert 'data-orb-kind="EVIDENCE_GAP"' in body
    assert "cueFrom" in body
    assert "data-actionability" in body
    assert "atlas-cartouche" in body
    assert 'data-action="DIVE_IN"' in body
    assert 'data-action="PULL_BACK"' in body
    assert 'aria-current="true"' in body  # camera CURRENT state carrier
