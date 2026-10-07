"""Executable ownership portion of the P82 adversarial oracle."""
import json
import time
from pathlib import Path

import pytest

from filesteward.models import CleanupDisposition as D
from filesteward.ownership.actions import (
    ActionKind as A, OwnershipEvidence, RegenerationProof,
    admit_cleanup_disposition, plan_owner_actions,
)
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph

CORPUS = json.loads((Path(__file__).parents[1] / "harness/evals/storage-reclamation-p82-corpus.v1.json").read_text())
PATH = "C:/fixture/bytes"


def evidence(path=PATH, kind="GENERATED_OUTPUT", edge="GENERATED_FROM",
             lifecycle="REGENERABLE_ARTIFACT", *, complete=True, proof=True, extra=()):
    graph = build_ownership_graph(extra_edges=(OwnershipEdge(
        edge, path, kind, "fixture-owner", "Fixture owner", "synthetic-adapter", "strong", lifecycle,
    ), *extra))
    return OwnershipEvidence(graph, complete, time.time(),
        (RegenerationProof(path, "fixture-owner", "fixture-tool rebuild", "a" * 64, True),) if proof else ())


APPLICATIONS = {
    "APP-SQUIRREL-LIVE": ("INSTALLED_AT", "APP_ACTIVE_REQUIRED"),
    "APP-BROKEN-REGISTRATION": ("UNINSTALLS_THROUGH", "APP_BROKEN_REQUIRED"),
    "APP-CACHE-IN-INSTALL": ("INSTALLED_AT", "APP_ACTIVE_REQUIRED"),
    "APP-RUNNING": ("PROCESS_USES", "APP_ACTIVE_REQUIRED"),
    "APP-SERVICE": ("SERVICE_REFERENCES", "APP_ACTIVE_REQUIRED"),
    "APP-TASK": ("TASK_REFERENCES", "APP_ACTIVE_REQUIRED"),
    "APP-MSIX": ("PACKAGE_OWNS", "APP_ACTIVE_REQUIRED"),
}
REPOS = {
    "REPO-CLEAN-PUSHED": "REPO_STABLE", "REPO-DIRTY": "REPO_ACTIVE",
    "REPO-STAGED": "REPO_ACTIVE", "REPO-UNTRACKED": "REPO_ACTIVE",
    "REPO-LOCAL-BRANCH": "REPO_ACTIVE", "REPO-WORKTREE": "REPO_ACTIVE",
    "REPO-NESTED": "REPO_ACTIVE", "REPO-GENERATED": "REPO_GENERATED_OUTPUT",
    "REPO-NETWORK-DOWN": "REPO_ACTIVE", "REPO-ENTIRE-ABSENT": "REPO_STABLE",
}
OWNERSHIP_IDS = set(APPLICATIONS) | set(REPOS) | {
    "MSI-INSTALLER-CACHE", "WIX-BURN-CACHE", "APP-CACHE-REGENERABLE",
    "APP-PORTABLE", "APP-SHARED", "UNKNOWN-DIR",
}


@pytest.mark.parametrize("case", [c for c in CORPUS["cases"] if c["id"] in OWNERSHIP_IDS], ids=lambda c: c["id"])
def test_p82_owner_correct_action(case):
    case_id = case["id"]
    path = PATH
    if case_id in APPLICATIONS:
        edge, lifecycle = APPLICATIONS[case_id]
        observed = evidence(kind="APPLICATION", edge=edge, lifecycle=lifecycle)
    elif case_id in REPOS:
        observed = evidence(kind="REPOSITORY", edge="REPO_CONTAINS", lifecycle=REPOS[case_id])
    elif case_id == "APP-CACHE-REGENERABLE":
        observed = evidence(kind="APPLICATION", lifecycle="APP_CACHE_REGENERABLE")
    elif case_id in {"APP-PORTABLE", "UNKNOWN-DIR"}:
        observed = OwnershipEvidence(build_ownership_graph(), True, time.time())
    elif case_id == "APP-SHARED":
        observed = evidence(extra=(OwnershipEdge("SERVICEABILITY_REQUIRES", PATH, "APPLICATION",
                            "app", "App", "registration", "strong", "APP_BROKEN_REQUIRED"),))
    else:
        path = "C:/Windows/Installer/item.msi" if case_id == "MSI-INSTALLER-CACHE" else "C:/ProgramData/Package Cache/item"
        observed = evidence(path=path)
    plan = plan_owner_actions(path, observed)
    assert not plan.raw_delete_eligible
    assert admit_cleanup_disposition(D.RECLAIM_PROVEN, plan) is not D.RECLAIM_PROVEN
    if case_id in APPLICATIONS or case_id in {"MSI-INSTALLER-CACHE", "WIX-BURN-CACHE", "APP-SHARED"}:
        assert plan.disposition is D.PROTECTED
    if case_id == "APP-CACHE-REGENERABLE":
        assert plan.actions == (A.CLEAN_CACHE,)
    if case_id == "REPO-GENERATED":
        assert plan.actions == (A.CLEAN_GENERATED_OUTPUT,)
    if case_id in {"APP-PORTABLE", "UNKNOWN-DIR"}:
        assert plan.actions == (A.INVESTIGATE_ORPHAN,)


def test_exact_regenerable_artifact_positive_control():
    plan = plan_owner_actions(PATH, evidence())
    assert plan.raw_delete_eligible
    assert admit_cleanup_disposition(D.HUMAN_REVIEW, plan) is D.HUMAN_REVIEW
    assert admit_cleanup_disposition(D.PROTECTED, plan) is D.PROTECTED


@pytest.mark.parametrize("change", ["incomplete", "stale", "future", "missing-proof", "different-path", "empty-recipe", "different-owner"])
def test_regeneration_and_freshness_required(change):
    from dataclasses import replace
    observed = evidence()
    if change == "incomplete":
        observed = replace(observed, adapters_complete=False)
    elif change == "stale":
        observed = replace(observed, observed_at_unix=time.time() - 301)
    elif change == "future":
        observed = replace(observed, observed_at_unix=time.time() + 100)
    elif change == "missing-proof":
        observed = replace(observed, proofs=())
    else:
        fields = {"different-path": {"path": PATH + "/child"}, "empty-recipe": {"recipe": ""},
                  "different-owner": {"owner_id": "other"}}[change]
        observed = replace(observed, proofs=(replace(observed.proofs[0], **fields),))
    assert not plan_owner_actions(PATH, observed).raw_delete_eligible


def test_unrecognized_domain_edge_fails_closed_without_reducer_crash():
    assert not plan_owner_actions(PATH, evidence(kind="SERVICE", edge="SERVICE_REFERENCES", lifecycle="")).raw_delete_eligible


def test_descendant_or_ancestor_dependency_blocks_whole_action():
    for anchor in ("C:/fixture", PATH + "/service.exe"):
        observed = evidence(extra=(OwnershipEdge("SERVICE_REFERENCES", anchor, "SERVICE", "svc", "Service", "services", "strong"),))
        assert plan_owner_actions(PATH, observed).disposition is D.PROTECTED


def test_same_revision_changed_recipe_changes_full_digest():
    from dataclasses import replace
    before = evidence()
    after = replace(before, proofs=(replace(before.proofs[0], recipe="different rebuild"),))
    assert before.graph.revision == after.graph.revision
    assert before.digest != after.digest


def test_cleanup_run_wires_ownership_and_persists_semantic_plan(tmp_path, monkeypatch):
    import csv
    from filesteward.classify import CacheContract
    from filesteward.run import CleanupRun
    from filesteward.policy import paths
    root = tmp_path / "fixture"
    root.mkdir()
    target = root / "artifact"
    target.write_bytes(b"generated bytes")
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    monkeypatch.setattr("filesteward.run.runtime_root", lambda: runtime)
    contract = CacheContract("fixture", str(root), "synthetic regeneration")
    def read_plan(run):
        with (run / "cleanup-plan.csv").open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    missing = runtime / "runs" / "missing"
    CleanupRun(root, missing, contracts=(contract,)).execute()
    assert read_plan(missing) == []
    owner = runtime / "runs" / "owner"
    CleanupRun(root, owner, contracts=(contract,), ownership_resolver=lambda p: evidence(path=p)).execute()
    assert str(target) in {r["path"] for r in read_plan(owner)}
    protected = runtime / "runs" / "protected"
    CleanupRun(root, protected, contracts=(contract,), ownership_resolver=lambda p: evidence(
        path=p, kind="APPLICATION", edge="INSTALLED_AT", lifecycle="APP_ACTIVE_REQUIRED")).execute()
    assert read_plan(protected) == []
    persisted = json.loads((protected / "owner-action-plan.json").read_text())
    assert all(r["actions"] == ["KEEP", "REPAIR_APPLICATION", "UNINSTALL_APPLICATION"] for r in persisted["items"])
    assert target.read_bytes() == b"generated bytes"
