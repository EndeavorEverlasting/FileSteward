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
