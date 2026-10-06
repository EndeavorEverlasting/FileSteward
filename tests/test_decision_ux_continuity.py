from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from filesteward.deletion.execute import ExecutionResult, ItemExecutionResult
from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.review_bridge import (
    DecisionBridgeIntent,
    DecisionRequest,
    ReviewBridge,
)
from filesteward.visualization.decision_flow import (
    DecisionIntent,
    ExecutionState,
    open_decision_session,
)
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


def _reclaim_node(node_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        node_id=node_id,
        disposition=CleanupDisposition.RECLAIM_PROVEN,
        authorization_state=AuthorizationState.UNAPPROVED,
        gate_steps=(
            SimpleNamespace(
                gate_id="disposition",
                status="WAITING",
                is_first_unresolved=True,
            ),
        ),
        path=rf"C:\synthetic\{node_id}",
        display_name=node_id,
        reclaim_basis="RECLAIM_PROVEN",
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


def test_bridge_delete_refuses_home_scan_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    # Keep pytest's tmp_path out of the temp-admission allowlist so home
    # refusal is what we exercise.
    fake_temp = tmp_path / "fake-temp-only"
    fake_temp.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    victim = home / "Downloads"
    victim.mkdir()
    node = _reclaim_node("reclaim-a")
    bridge = ReviewBridge(
        run_dir=tmp_path / "run",
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        _nodes={node.node_id: node},
    )
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(ValueError, match="personal home root"):
        bridge.execute_permanent_delete_ui(
            "continuity-run",
            [node.node_id],
            scan_root=victim,
            irreversible_confirmation="DELETE_PERMANENTLY",
        )


def test_bridge_delete_missing_scan_root_fails_closed(tmp_path: Path) -> None:
    node = _reclaim_node("reclaim-a")
    bridge = ReviewBridge(
        run_dir=tmp_path / "run",
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        scan_root=None,
        _nodes={node.node_id: node},
    )
    (tmp_path / "run").mkdir()
    with pytest.raises(ValueError, match="scan_root is required"):
        bridge.execute_permanent_delete_ui(
            "continuity-run",
            [node.node_id],
            scan_root="",
            irreversible_confirmation="DELETE_PERMANENTLY",
        )


def test_partial_delete_does_not_mark_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import filesteward.review_bridge as bridge_mod

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    node = _reclaim_node("reclaim-a")
    bridge = ReviewBridge(
        run_dir=run_dir,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        scan_root=tmp_path / "scan",
        _nodes={node.node_id: node},
    )
    (tmp_path / "scan").mkdir()

    monkeypatch.setattr(bridge_mod, "scan_root_allowed_for_execute", lambda p: None)
    monkeypatch.setattr(bridge_mod, "emit_delete_manifest", lambda d: None)
    monkeypatch.setattr(
        bridge_mod, "load_run_protection_context", lambda d: ((), ())
    )

    class _PF:
        overall = "PASS"

    monkeypatch.setattr(bridge_mod, "run_preflight", lambda *a, **k: _PF())
    monkeypatch.setattr(bridge_mod, "write_preflight_receipt", lambda *a, **k: None)
    monkeypatch.setattr(
        bridge_mod, "build_delete_approval", lambda **k: {"action": "DELETE_PERMANENTLY"}
    )
    monkeypatch.setattr(bridge_mod, "write_delete_approval", lambda *a, **k: None)
    monkeypatch.setattr(bridge_mod.shutil, "copy2", lambda *a, **k: None)

    result = ExecutionResult(
        overall="PARTIAL",
        run_dir=run_dir,
        receipt_path=run_dir / "delete-execution-receipt.json",
        items=[
            ItemExecutionResult(
                item_id="reclaim-a",
                path=str(tmp_path / "scan" / "a"),
                status="FAILED",
                reason_class="IO",
                detail="locked",
            )
        ],
    )
    monkeypatch.setattr(
        bridge_mod, "execute_permanent_delete", lambda **k: result
    )
    monkeypatch.setattr(
        bridge_mod,
        "load_delete_receipt",
        lambda p: {
            "overall": "PARTIAL",
            "items": [result.items[0].to_dict()],
            "reclaim": None,
        },
    )

    payload = bridge.execute_permanent_delete_ui(
        "continuity-run",
        [node.node_id],
        scan_root=tmp_path / "scan",
        irreversible_confirmation="DELETE_PERMANENTLY",
    )
    assert payload["execution_state"] == ExecutionState.BLOCKED.value
    assert payload["execution_state"] != ExecutionState.COMPLETE.value
    assert "partial" in str(payload["last_transition"]).lower()
    assert bridge._execution_by_item[node.node_id] is ExecutionState.BLOCKED


def test_rescan_blocks_without_claiming_success(tmp_path: Path) -> None:
    node = _unknown_node("unknown-a")
    bridge = ReviewBridge(
        run_dir=tmp_path,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        scan_root=None,
        _nodes={node.node_id: node},
    )
    after = bridge.record_decision(
        DecisionRequest(
            run_id="continuity-run",
            item_id="unknown-a",
            intent=DecisionBridgeIntent.RESCAN,
        )
    )
    assert after["execution_state"] == ExecutionState.BLOCKED.value
    assert "missing_scan_root" in str(after["last_transition"])
    assert after["execution_state"] != ExecutionState.COMPLETE.value


def test_declare_regenerable_persists_and_blocks_truthfully(tmp_path: Path) -> None:
    from filesteward.review_bridge import OPERATOR_CONTRACT_FILENAME

    node = SimpleNamespace(
        node_id="review-a",
        disposition=CleanupDisposition.HUMAN_REVIEW,
        authorization_state=AuthorizationState.UNAPPROVED,
        gate_steps=(
            SimpleNamespace(
                gate_id="contract",
                status="WAITING",
                is_first_unresolved=True,
            ),
        ),
        path=r"C:\synthetic\review-a",
        display_name="review-a",
        reclaim_basis=None,
    )
    bridge = ReviewBridge(
        run_dir=tmp_path,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        _nodes={node.node_id: node},
    )
    # Avoid full presentation rebuild against incomplete fixture run_dir.
    bridge._refresh_nodes = MagicMock(return_value=None)  # type: ignore[method-assign]
    after = bridge.record_decision(
        DecisionRequest(
            run_id="continuity-run",
            item_id="review-a",
            intent=DecisionBridgeIntent.DECLARE_REGENERABLE_CONTRACT,
        )
    )
    artifact = tmp_path / OPERATOR_CONTRACT_FILENAME
    assert artifact.is_file()
    assert after["execution_state"] == ExecutionState.BLOCKED.value
    assert "awaiting_scan" in str(after["last_transition"])
