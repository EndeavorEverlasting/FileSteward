"""P13 regression: Memory Atlas must visibly behave like a cinematic decision instrument."""

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


def _model() -> PresentationModel:
    node = PresentationNode(
        node_id="review",
        parent_id=None,
        display_name="Ambiguous Cache",
        path=r"C:\synthetic\cache",
        entry_type="DIRECTORY",
        logical_size_bytes=8_000_000_000,
        allocated_size_bytes=8_000_000_000,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=CleanupDisposition.HUMAN_REVIEW,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=ScanCompleteness.INCOMPLETE,
        protection_relation="UNRELATED",
        reason="synthetic",
        contract_summary=None,
        contract_hint_tags=(),
        risk_if_acted_on="synthetic risk",
        next_gate="Observation complete",
        trace_evidence_source="fixture",
        item_count=10,
        gate_steps=(
            GateStep(
                gate_id="observation",
                name="Observation complete",
                status=GateStepStatus.WAITING,
                explanation="Scan evidence is incomplete.",
                is_first_unresolved=True,
            ),
        ),
    )
    return PresentationModel(
        run_id="synthetic-v3-experience",
        nodes=(node,),
        metrics=ShellMetrics(
            observed_storage_label="8 GiB",
            free_space_label="32 GiB",
            projected_reclaim_label="0 bytes",
            projected_reclaim_quality=None,
            target_free_space_label="not established",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="review",
    )


def test_decision_tree_is_the_tutorial_not_a_separate_tour() -> None:
    html = render_report_shell(_model())
    assert 'id="decision-compass"' in html
    for step in ("MAP", "FOCUS", "GATE", "RESOLVE", "APPROVAL", "STAGED"):
        assert f'data-guide-step="{step}"' in html
    assert "Open the first unresolved gate" in html
    assert "NO BYTES REMOVED" in html
    assert "Start tutorial" not in html
    assert "product tour" not in html.lower()


def test_home_is_persistent_named_and_teaches_the_hotkey() -> None:
    html = render_report_shell(_model())
    # Floating ATLAS HOME beacon removed — it occluded atlas scenery.
    # Brand title + HUD Atlas Home remain the persistent Home affordances.
    assert "atlas-home-beacon" not in html
    assert 'id="brand-home"' in html
    assert 'id="atlas-home"' in html
    assert 'aria-label="Return to Atlas home"' in html
    assert "<kbd>Home</kbd>" in html
    assert "Esc" in html and "BACK" in html
    assert "returning-home" in html


def test_contextual_reticle_replaces_standard_cursor_inside_atlas_only() -> None:
    html = render_report_shell(_model())
    assert 'id="atlas-reticle"' in html
    assert 'data-cursor-mode="explore"' in html
    assert "pointermove" in html
    assert "cueFrom" in html
    assert "cursor:none!important" in html
    assert "(pointer:fine)" in html
    assert "(prefers-reduced-motion:no-preference)" in html


def test_semantic_glow_and_scan_are_actual_animation_contracts() -> None:
    html = render_report_shell(_model())
    assert "@keyframes fs-signal-breathe" in html
    assert "@keyframes fs-signal-ring" in html
    assert "@keyframes fs-scan-sweep" in html
    assert ".signal-primary" in html
    assert ".signal-hard-stop" in html


def test_cell_and_chamber_materially_recompose_the_workspace() -> None:
    html = render_report_shell(_model()).replace(" ", "")
    assert '.workspace[data-camera-level="CELL"]' in html
    assert '.workspace[data-camera-level="CHAMBER"]' in html
    assert "grid-template-columns:0minmax(0,1fr)0" in html
    assert '[data-decision-open="true"]' in html
