"""Projection of the repository-owned script; never a second workflow owner."""
from __future__ import annotations

import json
from pathlib import Path

from filesteward.visualization.decision_flow import DecisionFlowState
from filesteward.visualization.literal import escape_text


def load_scene_script() -> dict[str, dict]:
    path = Path(__file__).resolve().parents[3] / "harness/contracts/judgment-scene-workflow.v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    scenes = {scene["scene_id"]: scene for scene in document["scenes"]}
    for scene in scenes.values():
        for target in scene["transitions"].values():
            if target not in scenes:
                raise ValueError(f"BLOCKED_JUDGMENT_GAP: {target}")
    return scenes


def project_script(flow: DecisionFlowState | None, *, completed: bool = False, incident: bool = False) -> dict:
    """Resolve tutorial stage to its authored scene without promoting evidence."""
    stage = flow.scene.value if flow else "MAP"
    mapping = {
        "MAP": "ATLAS_HOME", "FOCUS": "TARGET_FOCUS", "GATE": "EVIDENCE_GATE",
        "APPROVAL": "AUTHORIZATION_GATE", "STAGED": "AUTHORIZATION_GATE",
        "RESULT": "VERIFY_RETURN", "CLOSED": "VERIFY_RETURN",
    }
    if incident:
        scene_id = "INCIDENT_RECOVERY"
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
        "evidence_status": "Decision recorded" if completed else "Persisted evidence; technical resolution is not yet live-proven",
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
