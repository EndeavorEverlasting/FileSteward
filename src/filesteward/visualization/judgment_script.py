"""Projection of the repository-owned script; never a second workflow owner."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from filesteward.models import CleanupDisposition
from filesteward.ownership.actions import OwnershipEvidence, admit_cleanup_disposition, plan_owner_actions
from filesteward.ownership.reducer import reduce_path_ownership

from filesteward.visualization.decision_flow import DecisionFlowState
from filesteward.visualization.literal import escape_text


def load_scene_script() -> dict[str, dict]:
    path = Path(__file__).resolve().parents[3] / "harness/contracts/judgment-scene-workflow.v1.json"
    # The harness is the authoring authority. Installed distributions carry an
    # exact, tested mirror so report rendering does not depend on a checkout.
    # An unreadable or malformed canonical file must still fail closed.
    text = path.read_text(encoding="utf-8") if path.is_file() else (
        resources.files("filesteward").joinpath(
            "contracts", "judgment-scene-workflow.v1.json"
        ).read_text(encoding="utf-8")
    )
    document = json.loads(text)
    scenes = {scene["scene_id"]: scene for scene in document["scenes"]}
    for scene in scenes.values():
        for target in scene["transitions"].values():
            if target not in scenes:
                raise ValueError(f"BLOCKED_JUDGMENT_GAP: {target}")
    return scenes


def project_script(flow: DecisionFlowState | None, *, completed: bool = False, incident: bool = False, resolved: bool = False) -> dict:
    """Resolve tutorial stage to its authored scene without promoting evidence."""
    stage = flow.scene.value if flow else "MAP"
    mapping = {
        "MAP": "ATLAS_HOME", "FOCUS": "TARGET_FOCUS", "GATE": "EVIDENCE_GATE",
        "APPROVAL": "AUTHORIZATION_GATE", "STAGED": "AUTHORIZATION_GATE",
        "RESULT": "VERIFY_RETURN", "CLOSED": "VERIFY_RETURN",
    }
    if incident:
        scene_id = "INCIDENT_RECOVERY"
    elif stage in {"RESULT", "CLOSED"}:
        scene_id = "VERIFY_RETURN"
    elif flow is not None and flow.script_scene_id is not None:
        scene_id = flow.script_scene_id
    elif stage == "RESOLVE":
        gate = flow.active_gate_id if flow else None
        scene_id = {
            "contract": "RECOVERABILITY_RESOLVE", "protection": "CONSEQUENCE_RESOLVE",
            "observation": "ATTRIBUTION_RESOLVE", "disposition": "ATTRIBUTION_RESOLVE",
        }.get(gate, "EVIDENCE_GATE")
    else:
        scene_id = mapping.get(stage)
    if scene_id is None:
        raise ValueError(f"BLOCKED_JUDGMENT_GAP: tutorial {stage}")
    scene = load_scene_script()[scene_id]
    return {
        "scene_id": scene_id, "headline": scene["render_script"].get("headline", scene["purpose"]),
        "purpose": scene["purpose"], "primary_impact": scene["primary_impact"],
        "success_evidence": scene["success_evidence"],
        "continuations": scene["transitions"],
        "evidence_status": "Decision recorded" if completed else (
            "Current normalized evidence was resolved by the ownership planner" if resolved else
            "Persisted evidence; current technical resolution is incomplete"
        ),
    }


def render_script_index() -> str:
    scenes = load_scene_script()
    rows = []
    for scene in scenes.values():
        headline = escape_text(scene["render_script"].get("headline", scene["purpose"]))
        purpose = escape_text(scene["purpose"])
        impact = escape_text(scene["primary_impact"].capitalize())
        rows.append(f'<li data-script-scene="{scene["scene_id"]}"><strong>{headline}</strong><span>{impact}: {purpose}</span></li>')
    payload = json.dumps(scenes, ensure_ascii=True).replace("<", "\\u003c")
    return (
        '<details class="scene-script-index"><summary>Your decision journey</summary>'
        '<p>Each chapter has a consequence. This script describes the journey; it does not certify that a probe or action ran.</p>'
        '<ol>' + "".join(rows) + '</ol>'
        '<p>Recurring cleanup settings require a canonical preference and authorization contract. No cleanup schedule is registered.</p></details>'
        '<script type="application/json" id="judgment-scene-script">' + payload + '</script>'
    )


def resolve_scene_evidence(path: str, disposition: CleanupDisposition, evidence: OwnershipEvidence) -> dict:
    """Project the current owning reducers; never classify or grant authority here.

    Resolver observations are data inputs. The complete/fresh gate and exact
    regeneration proof remain owned by ownership.actions, not by this viewer.
    Read-only automatic chapters remain inspectable after advancing to value.
    """
    plan = plan_owner_actions(path, evidence)
    effective = admit_cleanup_disposition(disposition, plan)
    edges = evidence.graph.edges_for_path(path)
    fresh = evidence.fresh()
    owners = sorted({edge.owner_display_name or edge.owner_id for edge in edges})
    sources = sorted({edge.evidence_source for edge in edges if edge.evidence_source})
    # Optional collector coverage reports technical facts, never scene policy.
    coverage = [{"domain": item.domain, "complete": item.complete,
                 "provenance": item.provenance, "gaps": list(item.gaps)}
                for item in getattr(evidence, "coverage", ())]
    unresolved_domains = [item["domain"].replace("_", " ") for item in coverage
                          if not item["complete"]]
    qualified = bool(edges) and all(
        edge.owner_kind in {"APPLICATION", "REPOSITORY"} and edge.lifecycle_hint for edge in edges
    )
    badge = reduce_path_ownership(path, evidence.graph).user_facing_badge if qualified else (
        "Shared dependency" if len(plan.owner_ids) > 1 else
        "Regenerable cache" if plan.raw_delete_eligible else "Unknown ownership"
    )
    proof = next((proof for proof in evidence.proofs if proof.valid_for(path, plan.owner_ids)), None)
    trace = [{
        "scene_id": "ATTRIBUTION_RESOLVE", "status": "RESOLVED" if fresh else "BLOCKED",
        "finding": ", ".join(owners) if owners else "No matching owner established",
        "evidence_sources": sources,
    }]
    if edges:
        trace.append({
            "scene_id": "CONSEQUENCE_RESOLVE", "status": "RESOLVED" if fresh else "STALE",
            "finding": badge, "reason_codes": list(plan.reason_codes),
        })
    if fresh and effective is not CleanupDisposition.PROTECTED:
        trace.append({
            "scene_id": "RECOVERABILITY_RESOLVE", "status": "RESOLVED" if proof else "NOT_PROVEN",
            "finding": proof.recipe if proof else "No exact adapter-backed recovery proof is available",
        })
    complete = evidence.adapters_complete is True
    scene_id = "VALUE_DECISION" if fresh else (
        "EVIDENCE_GATE" if complete else "ATTRIBUTION_RESOLVE"
    )
    missing_fact = None if fresh and plan.owner_ids else (
        "Current ownership evidence is stale or future-dated" if complete and not fresh else
        "The admitted ownership adapters have not completed" if not complete else
        "All admitted adapters completed, but no matching owner was established"
    )
    if unresolved_domains and not complete:
        missing_fact = "Current ownership checks remain incomplete: " + ", ".join(unresolved_domains)
        trace[0]["finding"] += ". Unresolved checks: " + "; ".join(
            item["domain"].replace("_", " ") + " (" + ", ".join(item["gaps"]) + ")"
            for item in coverage if not item["complete"]
        )
    actions = ["KEEP", "REVIEW_LATER"]
    if "APP_BROKEN_REQUIRED" in plan.consequence_classes:
        actions = ["REVIEW_LATER"]
    raw_eligible = effective is CleanupDisposition.RECLAIM_PROVEN and plan.raw_delete_eligible and fresh
    if raw_eligible:
        actions.insert(1, "RECLAIM_GENERATED_OUTPUT")
    # These are planner capabilities, not callable executors. Never render them
    # as inviting actions until their semantic execution owner is connected.
    unavailable = [action.value for action in plan.actions if action.value not in {
        "KEEP", "INVESTIGATE_ORPHAN", "RAW_DELETE_REGENERABLE_ARTIFACT"
    }]
    return {
        "scene_id": scene_id, "effective_disposition": effective.value,
        "ownership_badge": badge, "owners": owners, "reason_codes": list(plan.reason_codes),
        "semantic_actions": [action.value for action in plan.actions],
        "unavailable_semantic_actions": unavailable, "value_actions": actions,
        "raw_delete_eligible": raw_eligible, "adapters_complete": complete, "fresh": fresh,
        "observed_at_unix": evidence.observed_at_unix,
        "graph_revision_id": plan.graph_revision_id, "evidence_digest": plan.evidence_digest,
        "regeneration_digest": plan.regeneration_digest,
        "recovery_mechanism": proof.recipe if proof else None,
        "missing_fact": missing_fact,
        "safe_probes_attempted": sorted(set(sources) | {item["provenance"] for item in coverage if item["provenance"]}),
        "probe_coverage": coverage,
        "why_it_matters": "Unresolved ownership or recovery cannot authorize a destructive action",
        "trace": trace,
    }
