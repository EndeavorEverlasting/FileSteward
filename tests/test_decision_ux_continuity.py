from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from filesteward.deletion import DELETE_ACTION, DELETE_APPROVAL_SCHEMA, DELETE_MANIFEST_SCHEMA
from filesteward.deletion.execute import ExecutionResult, ItemExecutionResult
from filesteward.deletion.receipt import DELETE_RECEIPT_SCHEMA
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


def test_failed_decision_persistence_does_not_publish_intent(tmp_path, monkeypatch) -> None:
    node = _unknown_node("unknown-a")
    bridge = ReviewBridge(
        run_dir=tmp_path,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        _nodes={node.node_id: node},
    )

    def fail_write(*args):
        raise OSError("synthetic write failure")

    request = DecisionRequest(bridge.run_id, node.node_id, DecisionBridgeIntent.KEEP)
    with monkeypatch.context() as patch:
        patch.setattr("filesteward.review_bridge._atomic_write_json", fail_write)
        with pytest.raises(OSError, match="synthetic write failure"):
            bridge.record_decision(request)

    before_retry = bridge.state_payload(node.node_id)
    assert before_retry["classification_views"]["operator_intents"] == {}
    assert before_retry["scene_revision"] == 0
    assert "KEEP" in before_retry["allowed_intents"]
    result = bridge.record_decision(request)
    assert result["classification_views"]["operator_intents"] == {"KEEP": 1}
    assert result["scene_revision"] == 1
    assert bridge.decision_state_path().is_file()


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


@pytest.mark.parametrize("successful", [False, True])
def test_delete_readback_survives_secondary_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, successful: bool
) -> None:
    import filesteward.review_bridge as bridge_mod
    from safe_capacity_fixtures import generated_evidence

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    node = _reclaim_node("reclaim-a")
    next_node = _reclaim_node("reclaim-b")
    bridge = ReviewBridge(
        run_dir=run_dir,
        run_id="continuity-run",
        cleanup_plan_sha256="a" * 64,
        session_token="token",
        report_html="",
        scan_root=tmp_path / "scan",
        ownership_resolver=generated_evidence,
        _nodes={node.node_id: node, next_node.node_id: next_node},
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
        overall="SUCCEEDED" if successful else "PARTIAL",
        run_dir=run_dir,
        receipt_path=run_dir / "delete-execution-receipt.json",
        items=[
            ItemExecutionResult(
                item_id="reclaim-a",
                path=node.path,
                status="SUCCEEDED" if successful else "FAILED",
                reason_class="DELETED" if successful else "IO",
                detail="deleted" if successful else "locked",
            )
        ],
    )
    def execute_fixture(**kwargs):
        manifest_path = kwargs["manifest"]
        manifest_path.write_text(json.dumps({
            "schema_version": DELETE_MANIFEST_SCHEMA,
            "run_id": bridge.run_id,
            "source_cleanup_plan_sha256": bridge.cleanup_plan_sha256,
            "items": [{"item_id": node.node_id, "path": node.path}],
        }), encoding="utf-8")
        manifest_digest = bridge_mod.sha256_file(manifest_path)
        approval_path = kwargs["approval"]
        approval_path.write_text(json.dumps({
            "schema_version": DELETE_APPROVAL_SCHEMA,
            "run_id": bridge.run_id,
            "action": DELETE_ACTION,
            "authorization_state": AuthorizationState.APPROVED_FOR_ACTION.value,
            "delete_manifest_sha256": manifest_digest,
            "approved_item_ids": [node.node_id],
        }), encoding="utf-8")
        result.receipt_path.write_text(json.dumps({
            "schema_version": DELETE_RECEIPT_SCHEMA,
            "mode": DELETE_ACTION,
            "run_id": bridge.run_id,
            "overall": result.overall,
            "delete_manifest_sha256": manifest_digest,
            "delete_approval_sha256": bridge_mod.sha256_file(approval_path),
            "items": [result.items[0].to_dict()],
        }), encoding="utf-8")
        return result

    monkeypatch.setattr(bridge_mod, "execute_permanent_delete", execute_fixture)
    for item in (node, next_node):
        bridge.record_decision(DecisionRequest(
            "continuity-run", item.node_id, DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT,
        ))

    def fail_index_write():
        raise OSError("comparison fixture has no space for the decision index")

    monkeypatch.setattr(bridge, "_persist_decisions", fail_index_write)
    payload = bridge.execute_permanent_delete_ui(
        "continuity-run",
        [node.node_id],
        scan_root=tmp_path / "scan",
        irreversible_confirmation="DELETE_PERMANENTLY",
    )
    receipt = payload["deletion_receipt"]
    expected_state = ExecutionState.COMPLETE if successful else ExecutionState.BLOCKED
    assert payload["execution_state"] == expected_state.value
    assert receipt["succeeded"] == int(successful)
    assert receipt["failed"] == int(not successful)
    assert bridge._execution_by_item[node.node_id] is expected_state

    def reopen():
        instance = ReviewBridge(
            run_dir=run_dir, run_id=bridge.run_id,
            cleanup_plan_sha256=bridge.cleanup_plan_sha256,
            session_token="new-session", report_html="",
            scan_root=bridge.scan_root, ownership_resolver=generated_evidence,
            _nodes={item.node_id: _reclaim_node(item.node_id) for item in (node, next_node)},
        )
        instance._load_persisted()
        return instance

    reopened = reopen()
    intents = reopened.state_payload()["classification_views"]["operator_intents"]
    assert reopened._is_completed_item(node.node_id) is successful
    assert intents.get("DELETE_PERMANENTLY", 0) == int(successful)

    if successful:
        original = result.receipt_path.read_bytes()
        monkeypatch.setattr(reopened, "_persist_decisions", fail_index_write)
        with pytest.raises(OSError, match="no space"):
            reopened.execute_permanent_delete_ui(
                bridge.run_id, [next_node.node_id], scan_root=bridge.scan_root,
                irreversible_confirmation=DELETE_ACTION,
            )
        assert result.receipt_path.read_bytes() == original

        # A mismatched receipt row cannot restore a completion on restart.
        bad_receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
        bad_receipt["items"][0]["path"] = str(tmp_path / "other-target")
        result.receipt_path.write_text(json.dumps(bad_receipt), encoding="utf-8")
        assert not reopen()._is_completed_item(node.node_id)


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


def test_declare_regenerable_refuses_operator_technical_judgment(tmp_path: Path) -> None:
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
    with pytest.raises(ValueError, match="not allowed"):
        bridge.record_decision(
            DecisionRequest(
                run_id="continuity-run",
                item_id="review-a",
                intent=DecisionBridgeIntent.DECLARE_REGENERABLE_CONTRACT,
            )
        )
    artifact = tmp_path / OPERATOR_CONTRACT_FILENAME
    assert not artifact.exists()
    assert bridge.state_payload("review-a")["evidence_disposition"] == "HUMAN_REVIEW"
