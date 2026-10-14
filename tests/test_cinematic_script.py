"""Retained positive/negative controls for the reconciled cinematic lineage."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from filesteward.models import CleanupDisposition
from filesteward.review_bridge import ReviewBridge, DecisionRequest, DecisionBridgeIntent
from filesteward.visualization.decision_flow import DecisionScene, open_decision_session
from filesteward.visualization.decision_chamber import render_decision_chamber_script
from filesteward.visualization.judgment_script import load_scene_script, project_script, render_script_index
from test_decision_ux_continuity import _unknown_node, _reclaim_node


def test_script_covers_every_authoritative_scene_without_inventing_targets():
    scenes = load_scene_script()
    assert len(scenes) == 11
    rendered = render_script_index()
    for scene_id, scene in scenes.items():
        assert f'data-script-scene="{scene_id}"' in rendered
        assert scene["primary_impact"]
        assert scene["success_evidence"]
        assert set(scene["transitions"].values()) <= scenes.keys()


def test_script_projection_keeps_safety_facts_out_of_operator_preferences():
    flow = open_decision_session(_unknown_node("unknown"))
    assert project_script(flow)["scene_id"] == "ATTRIBUTION_RESOLVE"
    assert project_script(replace(flow, scene=DecisionScene.RESULT))["scene_id"] == "VERIFY_RETURN"
    assert project_script(None)["scene_id"] == "ATLAS_HOME"


def test_no_live_owner_adapter_means_no_inviting_delete_affordance(tmp_path):
    eligible = _reclaim_node("eligible")
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", _nodes={"eligible": eligible})
    payload = bridge.state_payload("eligible")
    assert "DELETE_PERMANENTLY" not in payload["allowed_intents"]
    assert "adapters" in payload["delete_unavailable_reason"]
    # Value choices remain available; absence of an adapter is not permission.
    assert "KEEP" in payload["allowed_intents"]


def test_positive_keep_readback_advances_and_survives_matching_reload(tmp_path):
    first, second = _unknown_node("a"), _unknown_node("b")
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", _nodes={"a": first, "b": second})
    state = bridge.record_decision(DecisionRequest("run", "a", DecisionBridgeIntent.KEEP))
    assert state["selected_node_id"] == "b"
    reloaded = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", _nodes={"a": first, "b": second})
    reloaded._load_persisted()
    assert reloaded.state_payload("a")["selected_node_id"] == "b"
    stale = ReviewBridge(tmp_path, "run", "b" * 64, "token", "", _nodes={"a": first, "b": second})
    stale._load_persisted()
    assert stale.state_payload("a")["selected_node_id"] == "a"


def test_client_no_longer_fabricates_offline_approval_and_receipts_are_visible():
    script = render_decision_chamber_script()
    assert "confirm_staging_offline" not in script
    assert "No approval was created" in script
    assert "scene === 'RESULT'" in script
    assert "payload.deletion_receipt" in script
    assert "'attempted','succeeded','failed','skipped'" in script
    assert "const safeFetch" in script
    assert "if (!response.ok) return" not in script


def test_human_review_ui_never_asks_operator_to_assert_regenerability(tmp_path):
    node = _unknown_node("review")
    node.disposition = CleanupDisposition.HUMAN_REVIEW
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", _nodes={"review": node})
    assert "DECLARE_REGENERABLE_CONTRACT" not in bridge.state_payload("review")["allowed_intents"]


def test_receipt_completes_every_succeeded_item_and_passes_same_owner_to_both_gates(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import filesteward.review_bridge as bridge_module
    from safe_capacity_fixtures import generated_evidence

    nodes = {key: _reclaim_node(key) for key in ("a", "b", "c")}
    scan = tmp_path / "scan"
    scan.mkdir()
    resolver = generated_evidence
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", scan_root=scan,
                          ownership_resolver=resolver, _nodes=nodes)
    seen = []
    monkeypatch.setattr(bridge_module, "scan_root_allowed_for_execute", lambda _: None)
    monkeypatch.setattr(bridge_module, "emit_delete_manifest", lambda _: None)
    monkeypatch.setattr(bridge_module, "load_run_protection_context", lambda _: ((), ()))
    def preflight(*args, **kwargs):
        seen.append(kwargs["ownership_resolver"])
        return SimpleNamespace(overall="PASS")
    def execute(**kwargs):
        seen.append(kwargs["ownership_resolver"])
        return SimpleNamespace(overall="PARTIAL")
    monkeypatch.setattr(bridge_module, "run_preflight", preflight)
    monkeypatch.setattr(bridge_module, "execute_permanent_delete", execute)
    monkeypatch.setattr(bridge_module, "write_preflight_receipt", lambda *args: None)
    monkeypatch.setattr(bridge_module, "build_delete_approval", lambda **kwargs: {})
    monkeypatch.setattr(bridge_module, "write_delete_approval", lambda *args: None)
    monkeypatch.setattr(bridge_module.shutil, "copy2", lambda *args: None)
    monkeypatch.setattr(bridge_module, "load_delete_receipt", lambda _: {
        "overall": "PARTIAL", "items": [
            {"item_id": "a", "status": "SUCCEEDED"},
            {"item_id": "b", "status": "SUCCEEDED"},
            {"item_id": "c", "status": "FAILED"},
        ]})
    for item_id in nodes:
        bridge.record_decision(DecisionRequest("run", item_id, DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT))
    payload = bridge.execute_permanent_delete_ui("run", ["a", "b", "c"], scan, "DELETE_PERMANENTLY")
    assert seen == [resolver, resolver]
    assert payload["execution_state"] == "blocked"
    assert payload["deletion_receipt"]["succeeded"] == 2
    assert payload["deletion_receipt"]["failed"] == 1
    assert bridge._is_completed_item("a") and bridge._is_completed_item("b")
    assert not bridge._is_completed_item("c")
    assert payload["script_scene"]["scene_id"] == "INCIDENT_RECOVERY"
    assert payload["selected_node_id"] == "a"
    assert payload["node"]["path"] == nodes["a"].path
    assert payload["next_item_id"] == "c"
    assert payload["allowed_intents"] == []
