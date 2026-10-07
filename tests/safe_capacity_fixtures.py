"""Exact synthetic generated-owner evidence for deletion lifecycle fixtures."""
from dataclasses import asdict
import time
from filesteward.ownership.actions import OwnershipEvidence, RegenerationProof, plan_owner_actions, unresolved_ownership
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.deletion.ownership import bind_ownership


def low_capacity(path):
    """Explicit synthetic measurement; production uses current disk usage."""
    return 10000, 1000


def bind_synthetic_discovery(manifest, path):
    """Replace only the old fixture sentinel, never missing/custom/drift data."""
    import csv
    import hashlib
    from pathlib import Path
    if path is None:
        return
    path = Path(path)
    sentinel = b"cleanup-plan-v1\n"
    digest = hashlib.sha256(sentinel).hexdigest()
    if not path.is_file() or path.read_bytes() != sentinel or manifest.get("source_cleanup_plan_sha256") != digest:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item_id", "path", "disposition"])
        writer.writeheader()
        writer.writerows({field: item.get(field, "") for field in writer.fieldnames} for item in manifest["items"])
    current = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["source_cleanup_plan_sha256"] = current
    for item in manifest["items"]:
        if item.get("source_cleanup_plan_sha256") == digest:
            item["source_cleanup_plan_sha256"] = current


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
    from filesteward.ownership.capacity import CapacityCandidate, plan_capacity_strategy
    from filesteward.ownership.actions import ActionKind
    directory.mkdir(parents=True, exist_ok=True)
    candidates = []
    for item in manifest["items"]:
        observed = generated_evidence(item["path"])
        container = item.get("item_type") == "DIRECTORY"
        candidates.append(CapacityCandidate(str(item["item_id"]), plan_owner_actions(item["path"], observed),
            ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT,
            0 if container else item.get("projected_reclaim_bytes"),
            "container-row" if container else item.get("reclaim_basis", "synthetic estimate")))
    total = max(10000, (sum(c.projected_reclaim_bytes or 0 for c in candidates) + 1000) * 10)
    free = total // 10
    capacity = {"schema_version": "filesteward.capacity-strategy/v1", "total_bytes": total, "free_bytes": free,
                **asdict(plan_capacity_strategy(candidates, total_bytes=total, free_bytes=free))}
    packets = {
        "owner-action-plan": {"schema_version": "filesteward.owner-action-plan/v1",
                              "items": [action_record(item["path"], item["item_id"]) for item in manifest["items"]]},
        "capacity-strategy": capacity,
    }
    for name, packet in packets.items():
        field = "source_" + name.replace("-", "_") + "_sha256"
        if field in manifest:
            continue
        path = directory / (name + ".json")
        path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
        manifest[field] = hashlib.sha256(path.read_bytes()).hexdigest()
