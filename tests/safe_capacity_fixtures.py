"""Exact synthetic generated-owner evidence for deletion lifecycle fixtures."""
from dataclasses import asdict
import time
from filesteward.ownership.actions import OwnershipEvidence, RegenerationProof, plan_owner_actions, unresolved_ownership
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.deletion.ownership import bind_ownership


def generated_evidence(path: str):
    owner = "synthetic-generator"
    graph = build_ownership_graph(extra_edges=(OwnershipEdge(
        "GENERATED_FROM", path, "GENERATED_OUTPUT", owner, "Synthetic generator",
        "fixture-recreation", "strong", "REGENERABLE_ARTIFACT"),))
    proof = RegenerationProof(path, owner, "Recreate synthetic fixture bytes from test source", "a" * 64, True)
    return OwnershipEvidence(graph, True, time.time(), (proof,))


def ownership_binding(path: str):
    evidence = generated_evidence(path)
    return bind_ownership(plan_owner_actions(path, evidence), evidence.observed_at_unix)


def action_record(path: str, item_id: str):
    evidence = generated_evidence(path)
    return {"item_id": item_id, **asdict(plan_owner_actions(path, evidence)),
            "adapters_complete": True, "observed_at_unix": evidence.observed_at_unix}


def resolver_for(items):
    paths = {str(item["ownership"]["path"]) for item in items if "ownership" in item}
    return lambda path: generated_evidence(path) if path in paths else unresolved_ownership(path)


def bind_source_artifacts(manifest, directory):
    """Persist exact synthetic source packets once; never repair existing drift."""
    import hashlib
    import json
    directory.mkdir(parents=True, exist_ok=True)
    packets = {
        "owner-action-plan": {"schema_version": "filesteward.owner-action-plan/v1",
                              "items": [action_record(item["path"], item["item_id"]) for item in manifest["items"]]},
        "capacity-strategy": {"schema_version": "filesteward.capacity-strategy/v1", "status": "LOW", "total_bytes": 10000, "free_bytes": 1000, "target_free_bytes": 2000,
                              "candidates": [{"candidate_id": item["item_id"], "action": "RAW_DELETE_REGENERABLE_ARTIFACT"} for item in manifest["items"]]},
    }
    for name, packet in packets.items():
        field = "source_" + name.replace("-", "_") + "_sha256"
        if field in manifest:
            continue
        path = directory / (name + ".json")
        path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
        manifest[field] = hashlib.sha256(path.read_bytes()).hexdigest()
