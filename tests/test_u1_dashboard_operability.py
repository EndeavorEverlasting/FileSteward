"""U1 legend/dashboard/chamber operability — acceptance markers.

Prototype measurement for:
  legend cinematic filter navigation;
  metric dashboards beyond ceremonial OPEN_* panels;
  cartouche negative-space docking;
  draggable Decision Chamber.
"""

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
from filesteward.visualization.decision_chamber import (
    render_decision_chamber_css,
    render_decision_chamber_markup,
    render_decision_chamber_script,
)
from filesteward.visualization.experience import (
    render_cinematic_experience_script,
)
from filesteward.visualization.html import render_report_html
from filesteward.visualization.scene_surface import (
    classification_legend,
    metric_scene_entries,
)
from filesteward.visualization.shell import render_report_shell


def _node(
    *,
    node_id: str,
    disposition: CleanupDisposition,
    name: str | None = None,
) -> PresentationNode:
    return PresentationNode(
        node_id=node_id,
        parent_id=None,
        display_name=name or node_id,
        path=rf"C:\synthetic\{node_id}",
        entry_type="DIRECTORY",
        logical_size_bytes=1_000_000,
        allocated_size_bytes=1_000_000,
        projected_reclaim_bytes=(
            500_000 if disposition is CleanupDisposition.RECLAIM_PROVEN else None
        ),
        reclaim_basis=(
            "synthetic" if disposition is CleanupDisposition.RECLAIM_PROVEN else None
        ),
        projection_quality=(
            "ESTIMATE" if disposition is CleanupDisposition.RECLAIM_PROVEN else None
        ),
        disposition=disposition,
        authorization_state=AuthorizationState.UNAPPROVED,
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
                status=GateStepStatus.PASS,
                explanation="synthetic",
                is_first_unresolved=False,
            ),
        ),
    )


def _model() -> PresentationModel:
    nodes = (
        _node(node_id="protected", disposition=CleanupDisposition.PROTECTED),
        _node(node_id="reclaim", disposition=CleanupDisposition.RECLAIM_PROVEN),
        _node(node_id="keep", disposition=CleanupDisposition.KEEP_PROVEN),
        _node(node_id="unknown", disposition=CleanupDisposition.UNKNOWN),
        replace(
            _node(node_id="review", disposition=CleanupDisposition.HUMAN_REVIEW),
            next_gate="judgment",
        ),
    )
    return PresentationModel(
        run_id="u1-dashboard-operability",
        nodes=nodes,
        metrics=ShellMetrics(
            observed_storage_label="1 GiB",
            free_space_label="8 GiB",
            projected_reclaim_label="0.5 MiB",
            projected_reclaim_quality="ESTIMATE",
            target_free_space_label="not established",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="reclaim",
    )


def test_legend_entries_declare_operable_filter_targets() -> None:
    legend = {entry.state_id: entry for entry in classification_legend()}
    assert getattr(legend["PROTECTED_BLOCKED"], "filter_target", None) == "PROTECTED"
    assert getattr(legend["RECLAIM_CANDIDATE"], "filter_target", None) == "RECLAIM_PROVEN"
    assert getattr(legend["KEEP_ESSENTIAL"], "filter_target", None) == "KEEP_PROVEN"
    ambiguous = getattr(legend["AMBIGUOUS_HUMAN_REVIEW"], "filter_target", None)
    assert ambiguous in {"AMBIGUOUS", ("HUMAN_REVIEW", "UNKNOWN")} or (
        isinstance(ambiguous, (tuple, list))
        and set(ambiguous) >= {"HUMAN_REVIEW", "UNKNOWN"}
    )
    auth = legend["AUTHORIZATION_LOCKED"]
    assert getattr(auth, "filter_target", None) in {None, "", "AUTHORIZATION"}
    assert "approval" in auth.meaning.lower() or "authorization" in auth.meaning.lower()


def test_authorization_metric_explains_unapproved_without_opaque_token_primary() -> None:
    entries = {
        entry.surface_id: entry
        for entry in metric_scene_entries(
            observed_storage="1 GiB",
            free_space="8 GiB",
            projected_reclaim="0.5 MiB",
            projected_reclaim_quality="ESTIMATE",
            target_free_space="not established",
            authorization="UNAPPROVED",
        )
    }
    auth = entries["metric_authorization_state"]
    assert "OPEN_AUTHORIZATION_SCENE" not in auth.explanation
    assert "UNAPPROVED" in auth.explanation.upper() or "approval" in auth.explanation.lower()
    assert "disposition" in auth.explanation.lower() or "classification" in auth.explanation.lower()


def test_filter_api_supports_ambiguous_and_programmatic_set() -> None:
    html = render_report_html(
        _model(),
        rects=tuple(
            TreemapRect(node_id=n.node_id, x=i * 20, y=0, width=20, height=100)
            for i, n in enumerate(_model().nodes)
        ),
    )
    assert "FileStewardFilters" in html
    assert "setFilter" in html
    assert "AMBIGUOUS" in html or "HUMAN_REVIEW" in html and "UNKNOWN" in html
    assert "filesteward:set-filter" in html or "FileStewardFilters" in html


def test_shell_wires_legend_and_metric_dashboards() -> None:
    model = _model()
    rects = tuple(
        TreemapRect(node_id=n.node_id, x=i * 20, y=0, width=20, height=100)
        for i, n in enumerate(model.nodes)
    )
    html = render_report_shell(model, rects=rects)
    full = render_report_html(model, rects=rects)
    assert "data-filter-target=" in html
    assert "data-legend-action=" in html
    assert "class-legend-item" in html
    assert 'data-actionability="OPERABLE"' in html
    assert "activateLegendItem" in html
    assert "OPEN_RECLAIM_SCENE" in html
    assert "fit_selected" in html
    assert "toggle_decision" in html
    assert "FileStewardFilters" in full
    assert "filesteward:set-filter" in full
    assert "Authorization is separate" in html or "no operator approval" in html.lower()


def test_cartouche_negative_space_obstacles_include_chrome() -> None:
    script = render_cinematic_experience_script()
    assert "placeCartoucheAway" in script
    for marker in (
        "atlas-classification-legend",
        ".metrics",
        "navigator",
        "atlas-hud",
        "decision-chamber",
        "decision-compass",
    ):
        assert marker in script
    assert "storage-stage" in script or "getBoundingClientRect" in script


def test_decision_chamber_is_draggable_like_decision_path() -> None:
    markup = render_decision_chamber_markup()
    script = render_decision_chamber_script()
    css = render_decision_chamber_css()
    assert "data-drag-handle" in markup
    assert "fs.decisionChamber.pos" in script
    assert "is-dragging" in css or "is-dragging" in script
    assert "pointerdown" in script


def test_live_journey_regressions_from_operator_proof() -> None:
    """Measured failures on 0.12.x live proof must not return."""

    from filesteward.visualization.decision_chamber import render_decision_chamber_script
    from filesteward.visualization.experience import render_cinematic_experience_script
    from filesteward.visualization.shell import render_report_shell

    model = _model()
    rects = tuple(
        TreemapRect(node_id=n.node_id, x=i * 20, y=0, width=20, height=100)
        for i, n in enumerate(model.nodes)
    )
    html = render_report_shell(model, rects=rects)
    # Auth dashboard must leave unrelated filters before hunting reclaim rows.
    assert "setNavigatorFilter('RECLAIM_PROVEN')" in html
    # Legend cinematic stays on Atlas subset — no automatic CHAMBER dive.
    assert "open: false" in html or "open:false" in html.replace(" ", "")
    assert "exitChamberToAtlas" in html
    # Subtitle must track selection, not freeze on the default node.
    assert 'id="scenery-subtitle-text"' in html
    assert "data-subtitle-for=" in html
    assert "subtitleSource.content" in html
    # Metric dashboards must reopen AFTER atlas.home() (home clears the panel).
    marker = "openScene must run after"
    assert marker in html
    home_after = html.find("atlas.home()", html.find(marker))
    open_after = html.find("openScene(", html.find(marker))
    assert home_after >= 0 and open_after >= 0
    assert home_after < open_after
    assert "data-dashboard-open" in html
    # Cartouche clamps to viewport∩stage and hard-prefers chrome-clear docks.
    script = render_cinematic_experience_script()
    assert "window.innerHeight" in script
    assert "intersect" in script or "viewBox" in script
    assert "bestClear" in script or "cursorOverChrome" in script
    # Chamber docks into visible viewport∩stage — not stage-bottom below the fold.
    from filesteward.visualization.decision_chamber import render_decision_chamber_css

    chamber = render_decision_chamber_script()
    assert "dockChamberInView" in chamber
    assert "visibleStageBox" in chamber
    assert "innerHeight" in chamber
    css = render_decision_chamber_css()
    assert "max-height" in css
    assert "overflow-y:auto" in css.replace(" ", "") or "overflow-y: auto" in css
    assert "position:fixed" in css.replace(" ", "") or "position: fixed" in css
    assert "fixed: true" in chamber or 'fixed:true' in chamber.replace(" ", "")
