"""Exact source/scene coverage and non-authorizing dependency measurements."""
from copy import deepcopy
import json
from pathlib import Path
import time

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
    for scene in mapping["scenes"]:
        expected = {f["id"] for f in features if scene["scene_id"] in f["scene_ids"]}
        assert expected and set(scene["feature_ids"]) == expected


def inventory(mapping):
    result = set(mapping["scope"]["root_files"])
    for prefix in mapping["scope"]["roots"]:
        for path in (ROOT / prefix).rglob("*"):
            relative = path.relative_to(ROOT)
            if path.is_file() and not any(part.startswith(".") or part == "__pycache__"
                                          for part in relative.parts[1:]) and path.suffix not in {".pyc", ".pyo"}:
                result.add(relative.as_posix())
    return result


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
