"""P82 dependency and race falsification through actual preflight/executor."""
from dataclasses import replace
import json
import os
from pathlib import Path
import time

import pytest

from filesteward.deletion.preflight import run_preflight
from filesteward.deletion.execute import execute_permanent_delete
from filesteward.deletion.ownership import revalidate_ownership
from filesteward.ownership.actions import OwnershipEvidence
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from safe_capacity_fixtures import generated_evidence, resolver_for
from test_delete_execute import _file_item, _manifest, _prepare_run

CORPUS = json.loads((Path(__file__).parents[1] / "harness/evals/storage-reclamation-p82-corpus.v1.json").read_text())
K3_IDS = {"FS-REPARSE", "FS-HARDLINK", "RACE-TARGET-DRIFT", "RACE-OWNER-DRIFT", "RACE-APP-UPDATE"}


def protective(path, edge="INSTALLED_AT", kind="APPLICATION", lifecycle="APP_ACTIVE_REQUIRED"):
    return OwnershipEvidence(build_ownership_graph(extra_edges=(OwnershipEdge(
        edge, path, kind, "app", "App", "fresh-adapter", "strong", lifecycle),)), True, time.time())


@pytest.mark.parametrize("case", [c for c in CORPUS["cases"] if c["id"] in K3_IDS], ids=lambda c: c["id"])
def test_p82_filesystem_and_race_oracle(case, tmp_path):
    path = tmp_path / "artifact"
    path.write_bytes(b"synthetic bytes")
    item = _file_item(path, item_id="artifact")
    manifest = _manifest([item])
    resolver = resolver_for([item])
    case_id = case["id"]
    if case_id == "FS-REPARSE":
        item["is_reparse_point"] = True
        expected = "REPARSE_OR_SYMLINK"
    elif case_id == "FS-HARDLINK":
        os.link(path, tmp_path / "other-link")
        expected = "HARDLINK_AMBIGUITY"
    elif case_id == "RACE-TARGET-DRIFT":
        path.write_bytes(b"changed target identity and length")
        expected = "IDENTITY_DRIFT"
    else:
        before = generated_evidence(str(path))
        edge = replace(before.graph.edges[0], detail="owner registration/update revision changed")
        after = replace(before, graph=build_ownership_graph(extra_edges=(edge,)))
        assert before.graph.revision.revision_id == after.graph.revision.revision_id
        resolver = lambda p: after
        expected = "OWNERSHIP_REVISION_DRIFT"
    result = run_preflight(manifest, scan_root=tmp_path, ownership_resolver=resolver)
    assert result.overall == "FAIL"
    assert result.items[0].reason_class == expected
    assert path.exists()


@pytest.mark.parametrize("kind,edge,lifecycle,reason", [
    ("APPLICATION", "INSTALLED_AT", "APP_ACTIVE_REQUIRED", "APP_DEPENDENCY_PRESENT"),
    ("APPLICATION", "SERVICEABILITY_REQUIRES", "APP_BROKEN_REQUIRED", "SERVICEABILITY_DEPENDENCY_PRESENT"),
    ("REPOSITORY", "REPO_CONTAINS", "REPO_ACTIVE", "REPOSITORY_UNIQUE_WORK_PRESENT"),
    ("SERVICE", "SERVICE_REFERENCES", "", "PROTECTIVE_DEPENDENCY_PRESENT"),
])
def test_new_dependency_blocks_preflight(tmp_path, kind, edge, lifecycle, reason):
    target = tmp_path / "artifact"
    target.write_bytes(b"bytes")
    item = _file_item(target, item_id="artifact")
    result = run_preflight(_manifest([item]), scan_root=tmp_path,
                           ownership_resolver=lambda p: protective(p, edge, kind, lifecycle))
    assert result.overall == "FAIL"
    assert result.items[0].reason_class == reason
    assert target.read_bytes() == b"bytes"


@pytest.mark.parametrize("change,reason", [
    ("proof-missing", "REGENERATION_PROOF_MISSING"),
    ("recipe-drift", "OWNERSHIP_REVISION_DRIFT"),
    ("source-drift", "OWNERSHIP_REVISION_DRIFT"),
    ("semantic-action", "SEMANTIC_ACTION_REQUIRED"),
    ("binding-missing", "OWNERSHIP_UNKNOWN"),
    ("expired", "OWNERSHIP_EVIDENCE_STALE"),
    ("future", "OWNERSHIP_EVIDENCE_STALE"),
    ("nan", "OWNERSHIP_EVIDENCE_STALE"),
    ("incomplete", "OWNERSHIP_UNKNOWN"),
    ("resolver-error", "OWNERSHIP_UNKNOWN"),
])
def test_binding_and_regeneration_drift_fail_closed(tmp_path, change, reason):
    target = tmp_path / "artifact"
    target.write_bytes(b"bytes")
    item = _file_item(target, item_id="artifact")
    observed = generated_evidence(str(target))
    if change == "proof-missing":
        observed = replace(observed, proofs=())
    elif change in {"recipe-drift", "source-drift", "semantic-action"}:
        fields = {"recipe-drift": {"recipe": "changed recipe"}, "source-drift": {"source_digest": "b" * 64},
                  "semantic-action": {"raw_delete_allowed": False}}[change]
        observed = replace(observed, proofs=(replace(observed.proofs[0], **fields),))
    elif change == "binding-missing":
        del item["ownership"]
    elif change in {"expired", "future", "nan"}:
        item["ownership"]["observed_at_unix"] = {"expired": time.time() - 301, "future": time.time() + 60, "nan": float("nan")}[change]
    elif change == "incomplete":
        observed = replace(observed, adapters_complete=False)
    def resolve(path):
        if change == "resolver-error":
            raise OSError("synthetic failed adapter")
        return observed
    result = run_preflight(_manifest([item]), scan_root=tmp_path, ownership_resolver=resolve)
    assert result.overall == "FAIL"
    assert result.items[0].reason_class == reason
    assert target.exists()


def test_missing_live_resolver_is_not_legacy_evidence(tmp_path):
    target = tmp_path / "artifact"
    target.write_bytes(b"bytes")
    item = _file_item(target, item_id="artifact")
    result = run_preflight(_manifest([item]), scan_root=tmp_path)
    assert result.overall == "FAIL"
    assert result.items[0].reason_class == "OWNERSHIP_UNKNOWN"


@pytest.mark.parametrize("directory", [False, True])
def test_dependency_rechecked_at_final_mutation_boundary(tmp_path, directory):
    from test_delete_execute import _dir_item
    target = tmp_path / "artifact"
    if directory:
        target.mkdir()
        item = _dir_item(target, item_id="artifact")
    else:
        target.write_bytes(b"bytes")
        item = _file_item(target, item_id="artifact")
    run_dir, manifest, approval = _prepare_run(tmp_path, [item], tmp_path)
    calls = []
    def resolver(path):
        calls.append(path)
        return generated_evidence(path) if len(calls) == 1 else protective(path)
    result = execute_permanent_delete(run_dir=run_dir, manifest=run_dir / "delete-manifest.json",
        approval=approval, preflight=run_dir / "delete-preflight.approved.json",
        scan_root=tmp_path, ownership_resolver=resolver)
    assert result.preflight_overall == "PASS"
    assert result.overall == "FAILED"
    assert len(calls) == 2
    assert result.items[0].reason_class == "APP_DEPENDENCY_PRESENT"
    assert target.exists()


def test_positive_exact_delete_receipt_binds_immediate_ownership(tmp_path):
    target = tmp_path / "artifact"
    target.write_bytes(b"synthetic generated bytes")
    item = _file_item(target, item_id="artifact")
    run_dir, manifest, approval = _prepare_run(tmp_path, [item], tmp_path)
    result = execute_permanent_delete(run_dir=run_dir, manifest=run_dir / "delete-manifest.json",
        approval=approval, preflight=run_dir / "delete-preflight.approved.json",
        scan_root=tmp_path, ownership_resolver=resolver_for([item]))
    assert result.overall == "SUCCEEDED"
    assert not target.exists()
    receipt = json.loads(result.receipt_path.read_text())
    assert receipt["items"][0]["ownership"]["action_kind"] == "RAW_DELETE_REGENERABLE_ARTIFACT"
    assert receipt["items"][0]["ownership"]["evidence_digest"] == item["ownership"]["evidence_digest"]
    assert receipt["items"][0]["ownership"]["owner_ids"] == ["synthetic-generator"]


def test_every_p82_case_has_an_executable_lane_owner():
    from test_safe_capacity_actions import OWNERSHIP_IDS
    assert {c["id"] for c in CORPUS["cases"]} == OWNERSHIP_IDS | K3_IDS


def test_healthy_run_has_no_delete_set_pressure(tmp_path, monkeypatch):
    from filesteward.classify import CacheContract
    from filesteward.run import CleanupRun
    from filesteward.policy import paths
    from filesteward.deletion.manifest import build_delete_manifest
    root = tmp_path / "scan"
    root.mkdir()
    (root / "artifact").write_bytes(b"x" * 100)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    monkeypatch.setattr("filesteward.run.runtime_root", lambda: runtime)
    run = runtime / "runs" / "healthy"
    CleanupRun(root, run, contracts=(CacheContract("fixture", str(root), "synthetic"),),
        ownership_resolver=generated_evidence, baseline_free_bytes=200, capacity_total_bytes=1000).execute()
    strategy = json.loads((run / "capacity-strategy.json").read_text())
    assert strategy["status"] == "HEALTHY"
    assert strategy["candidates"] == []
    manifest = build_delete_manifest(run)
    assert manifest["items"] == []
    assert manifest["capacity_deferred_item_count"] > 0
    assert (root / "artifact").exists()


@pytest.mark.parametrize("artifact", ["owner-action-plan.json", "capacity-strategy.json"])
def test_manifest_requires_owner_and_capacity_artifacts(tmp_path, artifact):
    from test_delete_manifest import write_synthetic_run
    from filesteward.deletion.manifest import build_delete_manifest
    write_synthetic_run(tmp_path)
    (tmp_path / artifact).unlink()
    with pytest.raises(ValueError):
        build_delete_manifest(tmp_path)


@pytest.mark.parametrize("artifact", ["owner-action-plan.json", "capacity-strategy.json"])
def test_source_action_artifact_drift_fails_preflight(tmp_path, artifact):
    from test_delete_manifest import write_synthetic_run
    from filesteward.deletion.manifest import build_delete_manifest
    target = tmp_path / "artifact"
    target.write_bytes(b"x" * 100)
    run = tmp_path / "run"
    write_synthetic_run(run, reclaim_path=str(target))
    manifest = build_delete_manifest(run)
    (run / artifact).write_text("{}")
    result = run_preflight(manifest, scan_root=tmp_path, cleanup_plan_path=run / "cleanup-plan.csv",
                           ownership_resolver=resolver_for(manifest["items"]))
    assert result.overall == "FAIL"
    assert any(i.reason_class in {"OWNERSHIP_REVISION_DRIFT", "DIGEST_DRIFT"} for i in result.items)
    assert target.exists()


@pytest.mark.parametrize("status,free,target", [("junk", 1000, 2000), (None, 1000, 2000),
                                               ("LOW", 2000, 2000), ("HEALTHY", 1000, 2000),
                                               ("LOW", 1000, 1001)])
def test_malformed_capacity_cannot_admit_delete_set(tmp_path, status, free, target):
    from test_delete_manifest import write_synthetic_run
    from filesteward.deletion.manifest import build_delete_manifest
    write_synthetic_run(tmp_path)
    source = tmp_path / "capacity-strategy.json"
    capacity = json.loads(source.read_text())
    capacity.update(status=status, free_bytes=free, target_free_bytes=target)
    source.write_text(json.dumps(capacity))
    with pytest.raises(ValueError):
        build_delete_manifest(tmp_path)


@pytest.mark.parametrize("field", ["source_owner_action_plan_sha256", "source_capacity_strategy_sha256"])
@pytest.mark.parametrize("value", [None, "", "not-a-digest"])
def test_missing_source_digest_cannot_bypass_preflight(tmp_path, field, value):
    target = tmp_path / "artifact"
    target.write_bytes(b"bytes")
    item = _file_item(target, item_id="artifact")
    manifest = _manifest([item])
    if value is None:
        manifest.pop(field, None)
    else:
        manifest[field] = value
    result = run_preflight(manifest, scan_root=tmp_path, ownership_resolver=resolver_for([item]))
    assert result.overall == "FAIL"
    assert any("source" in v.detail for v in result.items if v.verdict == "FAIL")
    assert target.exists()


def test_resolver_target_replacement_after_identity_probe_is_blocked(tmp_path):
    target = tmp_path / "artifact"
    target.write_bytes(b"original bytes")
    item = _file_item(target, item_id="artifact")
    run_dir, manifest, approval = _prepare_run(tmp_path, [item], tmp_path)
    calls = []
    def resolver(path):
        calls.append(path)
        if len(calls) == 2:
            # Simulate a competing writer during fresh attribution.
            target.unlink()
            target.write_bytes(b"replaced bytes")
            os.utime(target, (item["modified_at"], item["modified_at"]))
        return generated_evidence(path)
    result = execute_permanent_delete(run_dir=run_dir, manifest=run_dir / "delete-manifest.json",
        approval=approval, preflight=run_dir / "delete-preflight.approved.json",
        scan_root=tmp_path, ownership_resolver=resolver)
    assert result.overall == "FAILED"
    assert result.items[0].reason_class == "IDENTITY_DRIFT"
    assert target.read_bytes() == b"replaced bytes"
