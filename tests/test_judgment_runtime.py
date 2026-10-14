"""Real owning reducers drive scripted scenes; synthetic data carries no authority."""
from dataclasses import replace
import time

import pytest

from filesteward.models import CleanupDisposition
from filesteward.ownership.actions import OwnershipEvidence, unresolved_ownership
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.review_bridge import DecisionBridgeIntent, DecisionRequest, ReviewBridge
from filesteward.visualization.judgment_script import resolve_scene_evidence
from safe_capacity_fixtures import generated_evidence
from test_decision_ux_continuity import _reclaim_node, _unknown_node


def evidence_for(*edges, complete=True, observed=None):
    return OwnershipEvidence(build_ownership_graph(extra_edges=edges), complete,
                             time.time() if observed is None else observed)


def edge(kind, owner, lifecycle, edge_type="REPO_CONTAINS"):
    return OwnershipEdge(edge_type, r"C:\synthetic\target", kind, owner, owner,
                         "synthetic-normalized-adapter", "strong", lifecycle)


def test_incomplete_empty_graph_stops_at_attribution_without_reclaim():
    view = resolve_scene_evidence(r"C:\synthetic\target", CleanupDisposition.RECLAIM_PROVEN,
                                  unresolved_ownership(r"C:\synthetic\target"))
    assert view["scene_id"] == "ATTRIBUTION_RESOLVE"
    assert view["effective_disposition"] == "UNKNOWN"
    assert view["raw_delete_eligible"] is False
    assert view["missing_fact"] and view["why_it_matters"]


def test_exhausted_empty_graph_reaches_only_safe_value_choices():
    view = resolve_scene_evidence(r"C:\synthetic\target", CleanupDisposition.UNKNOWN, evidence_for())
    assert view["scene_id"] == "VALUE_DECISION"
    assert view["value_actions"] == ["KEEP", "REVIEW_LATER"]
    assert "no matching owner" in view["missing_fact"].lower()


@pytest.mark.parametrize("age", [301, -10])
def test_stale_or_future_capture_returns_to_evidence_gate(age):
    evidence = replace(generated_evidence(r"C:\synthetic\target"), observed_at_unix=time.time() - age)
    view = resolve_scene_evidence(r"C:\synthetic\target", CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert view["scene_id"] == "EVIDENCE_GATE"
    assert not view["raw_delete_eligible"]


def test_app_dependency_wins_over_a_legacy_repo_and_preserves_both_owners():
    evidence = evidence_for(edge("APPLICATION", "app", "APP_ACTIVE_REQUIRED", "INSTALLED_AT"),
                            edge("REPOSITORY", "repo", "REPO_LEGACY_CANDIDATE"))
    view = resolve_scene_evidence(r"C:\synthetic\target", CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert view["effective_disposition"] == "PROTECTED"
    assert view["owners"] == ["app", "repo"]
    assert "Required by app" == view["ownership_badge"]
    assert not view["raw_delete_eligible"]
    assert "CONSEQUENCE_RESOLVE" in [row["scene_id"] for row in view["trace"]]


def test_current_generated_evidence_visits_value_before_authorization(tmp_path):
    node = _reclaim_node("generated")
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", scan_root=tmp_path,
                          ownership_resolver=generated_evidence, _nodes={node.node_id: node})
    before = bridge.state_payload(node.node_id)
    assert before["script_scene"]["scene_id"] == "VALUE_DECISION"
    assert "DELETE_PERMANENTLY" not in before["allowed_intents"]
    assert "RECLAIM_GENERATED_OUTPUT" in before["allowed_intents"]
    assert [row["scene_id"] for row in before["scene_evidence"]["trace"]] == [
        "ATTRIBUTION_RESOLVE", "CONSEQUENCE_RESOLVE", "RECOVERABILITY_RESOLVE"]
    after = bridge.record_decision(DecisionRequest("run", node.node_id, DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT))
    assert after["script_scene"]["scene_id"] == "AUTHORIZATION_GATE"
    assert after["authorization_state"] == "UNAPPROVED"
    assert "DELETE_PERMANENTLY" in after["allowed_intents"]
    assert not (tmp_path / "delete-approval.json").exists()
    # A newly protective edge invalidates the persisted intent.
    bridge.ownership_resolver = lambda path: evidence_for(edge("APPLICATION", "app", "APP_ACTIVE_REQUIRED", "INSTALLED_AT"))
    drift = bridge.state_payload(node.node_id)
    assert "DELETE_PERMANENTLY" not in drift["allowed_intents"]
    assert drift["script_scene"]["scene_id"] == "VALUE_DECISION"


def test_fresh_evidence_never_promotes_unknown_inventory(tmp_path):
    node = _unknown_node("unknown")
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", scan_root=tmp_path,
                          ownership_resolver=generated_evidence, _nodes={node.node_id: node})
    state = bridge.state_payload(node.node_id)
    assert state["evidence_disposition"] == "UNKNOWN"
    assert "RECLAIM_GENERATED_OUTPUT" not in state["allowed_intents"]


def test_provenance_change_invalidates_value_intent_even_if_graph_revision_same(tmp_path):
    node = _reclaim_node("generated")
    first = generated_evidence(node.path)
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", scan_root=tmp_path,
                          ownership_resolver=lambda path: first, _nodes={node.node_id: node})
    bridge.record_decision(DecisionRequest("run", node.node_id, DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT))
    changed_graph = build_ownership_graph(extra_edges=tuple(replace(e, detail="changed provenance") for e in first.graph.edges))
    second = replace(first, graph=changed_graph)
    assert first.graph.revision.revision_id == second.graph.revision.revision_id
    assert first.digest != second.digest
    bridge.ownership_resolver = lambda path: second
    state = bridge.state_payload(node.node_id)
    assert state["script_scene"]["scene_id"] == "VALUE_DECISION"
    assert "DELETE_PERMANENTLY" not in state["allowed_intents"]


def test_evidence_drift_reopens_keep_and_rejects_stale_delete_before_artifacts(tmp_path, monkeypatch):
    import filesteward.review_bridge as module
    node = _reclaim_node("generated")
    first = generated_evidence(node.path)
    bridge = ReviewBridge(tmp_path, "run", "a" * 64, "token", "", scan_root=tmp_path,
                          ownership_resolver=lambda path: first, _nodes={node.node_id: node})
    bridge.record_decision(DecisionRequest("run", node.node_id, DecisionBridgeIntent.KEEP))
    assert bridge._is_completed_item(node.node_id)
    second = replace(first, graph=build_ownership_graph(extra_edges=tuple(
        replace(e, detail="changed provenance") for e in first.graph.edges)))
    bridge.ownership_resolver = lambda path: second
    assert not bridge._is_completed_item(node.node_id)
    bridge.record_decision(DecisionRequest("run", node.node_id, DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT))
    assert bridge.state_payload(node.node_id)["script_scene"]["scene_id"] == "AUTHORIZATION_GATE"
    bridge.ownership_resolver = lambda path: first
    monkeypatch.setattr(module, "scan_root_allowed_for_execute", lambda path: None)
    def unexpected(*args):
        pytest.fail("stale authorization must be rejected before package creation")
    monkeypatch.setattr(module, "emit_delete_manifest", unexpected)
    with pytest.raises(ValueError, match="current value intent"):
        bridge.execute_permanent_delete_ui("run", [node.node_id], tmp_path, "DELETE_PERMANENTLY")


def test_staging_preserves_prior_still_valid_approval_after_reload(tmp_path):
    import json
    from filesteward.approval import ApprovalAction
    from filesteward.review_bridge import ApprovalRequest
    nodes = {key: _reclaim_node(key) for key in ("a", "b")}
    rows = [{"item_id":key,"disposition":"RECLAIM_PROVEN","proposed_action":"quarantine"} for key in nodes]
    bridge = ReviewBridge(tmp_path,"run","a"*64,"token","",scan_root=tmp_path,
                          ownership_resolver=generated_evidence,_nodes=nodes,_plan_rows=rows)
    for key in nodes:
        bridge.record_decision(DecisionRequest("run",key,DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT))
        bridge.record_approval(ApprovalRequest("run",key,"a"*64,ApprovalAction.QUARANTINE,True))
    assert json.loads(bridge.approval_record_path().read_text())["approved_item_ids"] == ["a","b"]
    reloaded = ReviewBridge(tmp_path,"run","a"*64,"token","",scan_root=tmp_path,
                            ownership_resolver=generated_evidence,_nodes=nodes,_plan_rows=rows)
    reloaded._load_persisted()
    assert set(reloaded._approvals) == {"a","b"}
    assert all(reloaded.state_payload(key)["open_decision_scene"] == "STAGED" for key in nodes)


def test_approval_reload_rejects_wrong_run_even_with_matching_plan(tmp_path):
    import json
    from filesteward.approval import ApprovalRecord
    bridge = ReviewBridge(tmp_path,"current","a"*64,"token","",_nodes={"a":_reclaim_node("a")})
    bridge.approval_record_path().write_text(json.dumps(ApprovalRecord("other","a"*64,("a",)).as_mapping()))
    bridge._load_persisted()
    assert not bridge._approvals
    assert bridge.state_payload("a")["authorization_state"] == "UNAPPROVED"
