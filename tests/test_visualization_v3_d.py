from filesteward.visualization.cinematic import (
    BANK_LIMIT,
    OVERVIEW_LIMIT,
    render_atlas_runtime_json,
    render_decision_signal_rail,
)
from filesteward.visualization.html import render_report_html
from filesteward.visualization.shell import render_report_shell

from test_visualization_f5 import _model


def test_v3_shell_exposes_camera_and_cross_input_actions() -> None:
    html = render_report_html(_model())
    assert 'data-camera-level="HOME"' in html
    assert "atlas.select" in html
    assert "atlas.zoom_in" in html
    assert "atlas.zoom_out" in html
    assert "atlas.fit_selected" in html
    assert "atlas.open_selected" in html
    assert "atlas.back" in html
    assert "atlas.home" in html
    assert "atlas.search" in html
    assert "atlas.toggle_decision" in html
    assert 'id="atlas-home"' in html
    assert 'class="phone-command-bar"' in html
    assert "@container atlas" in html
    assert "min-width:0" in html
    assert "directTargetMinPx" in html
    assert OVERVIEW_LIMIT == 12
    assert BANK_LIMIT == 36


def test_v3_decision_signals_are_projected_with_text() -> None:
    html = render_report_shell(_model())
    assert "decision-signal-rail" in html
    assert "signal-pulse" in html
    assert "UNRESOLVED" in html
    assert "UNAPPROVED" in html
    rail = render_decision_signal_rail(_model().nodes[0])
    assert "First unresolved decision" in rail
    assert "signal-kind" in rail


def test_v3_runtime_payload_is_literal_safe() -> None:
    blob = render_atlas_runtime_json(_model().nodes)
    assert 'id="atlas-runtime"' in blob
    assert "<script>alert" not in blob
