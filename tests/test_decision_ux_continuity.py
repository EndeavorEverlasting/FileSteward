from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.review_bridge import (
    DecisionBridgeIntent,
    DecisionRequest,
    ReviewBridge,
)
from filesteward.visualization.decision_flow import DecisionIntent, open_decision_session
from filesteward.visualization.interaction import cue_for_map_node, cue_for_navigation
from filesteward.visualization.scene_surface import operator_next_actions


def _unknown_node(node_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        node_id=node_id,
        disposition=CleanupDisposition.UNKNOWN,
        authorization_state=AuthorizationState.UNAPPROVED,
        gate_steps=(
            SimpleNamespace(
                gate_id="observation",
                status="WAITING",
                is_first_unresolved=True,
            ),
        ),
        path=rf"C:\synthetic\{node_id}",
        display_name=node_id,
        reclaim_basis=None,
    )


def test_keep_advances_to_a_different_unknown_item(tmp_path: Path) -> None:
    first = _unknown_node("unknown-a")
    second = _unknown_node("unknown-b")
    bridge = ReviewBridge(
        run_dir=tmp_path,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        _nodes={first.node_id: first, second.node_id: second},
    )
    before = bridge.state_payload("unknown-a")
    assert before["open_decision_scene"] in {"GATE", "RESOLVE"}
    after = bridge.record_decision(
        DecisionRequest(
            run_id="continuity-run",
            item_id="unknown-a",
            intent=DecisionBridgeIntent.KEEP,
        )
    )
    assert after["current_item_id"] == "unknown-a"
    assert after["selected_node_id"] == "unknown-b"
    assert after["next_item_id"] == "unknown-b"
    assert after["open_decision_scene"] in {"GATE", "RESOLVE"}
    assert after["selected_node_id"] != "unknown-a"
    replay = bridge.state_payload("unknown-a")
    assert replay["selected_node_id"] == "unknown-b"


def test_cue_bind_fields_are_complete() -> None:
    node = _unknown_node("unknown-a")
    cue = cue_for_map_node(node, selected=False)
    for field in (
        "source_scene",
        "destination_scene",
        "impact_kind",
        "continuation",
        "context_fingerprint",
    ):
        assert getattr(cue, field)
    nav = cue_for_navigation("decision")
    for field in (
        "source_scene",
        "destination_scene",
        "impact_kind",
        "continuation",
        "context_fingerprint",
    ):
        assert getattr(nav, field)


def test_delete_permanently_not_allowed_for_unknown(tmp_path: Path) -> None:
    node = _unknown_node("unknown-a")
    flow = open_decision_session(node)
    actions = operator_next_actions(flow)
    assert all(action.intent is not DecisionIntent.DELETE_PERMANENTLY for action in actions)
    assert all(action.action_id != "delete_permanently" for action in actions)
    bridge = ReviewBridge(
        run_dir=tmp_path,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        _nodes={node.node_id: node},
    )
    with pytest.raises(ValueError, match="RECLAIM_PROVEN"):
        bridge.execute_permanent_delete_ui(
            "continuity-run",
            [node.node_id],
            scan_root=r"C:\synthetic",
            irreversible_confirmation="DELETE_PERMANENTLY",
        )
