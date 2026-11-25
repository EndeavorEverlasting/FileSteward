"""Exact source/scene coverage and non-authorizing dependency measurements."""
from copy import deepcopy
import json
from pathlib import Path
import time
import subprocess

import pytest
from filesteward.models import CleanupDisposition
from filesteward.ownership.actions import OwnershipEvidence, dependency_summary, plan_owner_actions
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.visualization.judgment_script import resolve_scene_evidence

ROOT = Path(__file__).resolve().parents[1]


def load_map():
    return json.loads((ROOT / "harness/contracts/feature-map.v1.json").read_text(encoding="utf-8"))


def validate_map(mapping, source_paths):
    features = mapping["features"]
    ids = [feature["id"] for feature in features]
    assert len(ids) == len(set(ids))
    mapped = [p for feature in features for p in feature["source_paths"]]
    assert len(mapped) == len(set(mapped)), "duplicate source ownership"
    assert set(mapped) == source_paths, (source_paths - set(mapped), set(mapped) - source_paths)
    workflow = json.loads((ROOT / mapping["workflow_ref"]).read_text(encoding="utf-8"))
    composition = json.loads((ROOT / mapping["composition_ref"]).read_text(encoding="utf-8"))
    order = workflow["scene_order"]
    assert [s["scene_id"] for s in mapping["scenes"]] == order
    assert [s["scene_id"] for s in composition["scenes"]] == order
    for feature in features:
        assert feature["source_paths"] and feature["tests"]
        assert set(feature["scene_ids"]) <= set(order)
        assert all((ROOT / test).is_file() for test in feature["tests"])
    # Feature ownership covers the executable system *and* its policy/proof sources.
    contracted = [p for f in features for p in f.get("contract_paths", [])]
    assert len(contracted) == len(set(contracted)), "duplicate contract ownership"
    assert set(contracted) == inventory_scoped(mapping["scope"]["contract_roots"])
    test_sources = {p for f in features for p in f["tests"]}
    assert test_sources == inventory_scoped(mapping["scope"]["test_roots"], suffix=".py")
    for scene in mapping["scenes"]:
        expected = {f["id"] for f in features if scene["scene_id"] in f["scene_ids"]}
        assert expected and set(scene["feature_ids"]) == expected


def inventory_scoped(scope, *, suffix=None):
    # Include unignored new sources as well as tracked files; never scan host data.
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *scope],
        cwd=ROOT,
    )
    result = set(raw.decode("utf-8").split("\0")) - {""}
    if suffix is not None:
        result = {path for path in result if path.endswith(suffix)}
    assert all((ROOT / path).is_file() for path in result), "tracked source missing"
    return result


def inventory(mapping):
    scope = mapping["scope"]["roots"] + mapping["scope"]["root_files"]
    return inventory_scoped(scope)


def test_exact_source_and_scene_map():
    mapping = load_map()
    actual = inventory(mapping)
    validate_map(mapping, actual)
    with pytest.raises(AssertionError):
        validate_map(mapping, actual | {"src/filesteward/unmapped.py"})
    bad = deepcopy(mapping)
    bad["scenes"].pop()
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    bad["features"][0]["source_paths"].append(bad["features"][1]["source_paths"][0])
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    bad["features"][-1]["contract_paths"].remove("harness/contracts/feature-map.v1.json")
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    for feature in bad["features"]:
        if "tests/test_antivirus_detector.py" in feature["tests"]:
            feature["tests"].remove("tests/test_antivirus_detector.py")
    with pytest.raises(AssertionError):
        validate_map(bad, actual)


def test_app_dependency_veto_with_incomplete_discovery():
    path = r"C:\\Demo\\component.dll"
    edge = OwnershipEdge("RUNTIME_REQUIRES", path, "APPLICATION", "demo", "Demo",
                         "synthetic runtime reference", "strong", "APP_ACTIVE_REQUIRED")
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=(edge,)), False, time.time())
    plan = plan_owner_actions(path, evidence)
    summary = dependency_summary(path, evidence, plan)
    assert plan.disposition is CleanupDisposition.PROTECTED
    assert summary["application_owner_count"] == 1
    assert summary["protective_edge_count"] == 1
    assert summary["raw_delete_disqualified"]
    assert not summary["current_evidence_complete"]
    projected = resolve_scene_evidence(path, CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert projected["effective_disposition"] == "PROTECTED"
    assert projected["dependency_summary"]["raw_delete_disqualified"]
    assert not projected["raw_delete_eligible"]


def test_no_edges_is_not_disposability():
    path = r"C:\\Demo\\unknown.bin"
    evidence = OwnershipEvidence(build_ownership_graph(), False, time.time())
    summary = dependency_summary(path, evidence, plan_owner_actions(path, evidence))
    assert summary["protective_edge_count"] == 0
    assert summary["raw_delete_disqualified"]
    assert not summary["current_evidence_complete"]

def test_service_reference_is_positive_only_and_path_scoped(tmp_path):
    from filesteward.ownership import current

    service = tmp_path / "service.exe"
    sibling = tmp_path / "unrelated.bin"
    service.write_bytes(b"fixture")
    sibling.write_bytes(b"fixture")
    references = (("demo", "ImagePath", str(service)),)
    result = current._service_projection(tmp_path, tmp_path, references)
    assert not result.complete
    assert len(result.edges) == 1
    assert result.edges[0].storage_path == str(service)
    assert result.edges[0].edge_type == "SERVICE_REFERENCES"
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=result.edges), False, time.time())
    assert plan_owner_actions(str(service), evidence).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(sibling), evidence).disposition is CleanupDisposition.UNKNOWN
    view = resolve_scene_evidence(str(service), CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert view["ownership_badge"] == "Required by service"
    assert view["effective_disposition"] == CleanupDisposition.PROTECTED.value
    assert view["dependency_summary"]["protective_edge_count"] == 1
    assert view["dependency_summary"]["raw_delete_disqualified"] is True
    assert view["raw_delete_eligible"] is False
    assert "Required by service" in view["trace"][1]["finding"]
    assert not current._service_projection(tmp_path, sibling, references).edges
    assert not current._service_projection(tmp_path, tmp_path, ()).complete


def test_known_required_service_does_not_appear_unknown_when_other_domains_fail():
    path = r"C:\\Services\\daemon.exe"
    edge = OwnershipEdge("SERVICE_REFERENCES", path, "SERVICE", "service:daemon",
                         "daemon", "windows_service_registry", "strong", "")
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=(edge,)), False, time.time())
    view = resolve_scene_evidence(path, CleanupDisposition.UNKNOWN, evidence)
    assert view["ownership_badge"] == "Required by service"
    assert view["effective_disposition"] == "PROTECTED"
    assert view["scene_id"] == "ATTRIBUTION_RESOLVE"
    assert view["raw_delete_eligible"] is False


def test_chamber_renders_dependency_metrics_without_mutation():
    source = (ROOT / "src/filesteward/visualization/decision_chamber.py").read_text(encoding="utf-8")
    assert "evidence.dependency_summary" in source
    assert "unresolved discovery domains" in source
    assert "facts.appendChild(metrics)" in source
    assert "Safe raw deletion has not been established." in source
