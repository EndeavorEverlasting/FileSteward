"""Composition is complete and references policy without copying its transitions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "harness/contracts/scene-composition.v1.json"


def load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def resolve(reference):
    filename, _, pointer = reference.partition("#")
    value = json.loads((ROOT / filename).read_text(encoding="utf-8"))
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def validate(contract):
    workflow = resolve(contract["workflow_ref"])
    assert contract["authority"] == "presentation_composition_only_not_second_state_machine"
    expected = workflow["scene_order"]
    assert [s["scene_id"] for s in contract["scenes"]] == expected
    components = {c["id"] for c in contract["components"]}
    assert components == {
        "world", "subject", "related_subjects", "gate_evidence", "chamber",
        "path_guide", "context_reticle", "chrome", "input_mode",
    }
    assert all(c["owner"] and c["responsibility"] for c in contract["components"])
    markup = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "src/filesteward/visualization").glob("*.py")
    )
    for i, scene in enumerate(contract["scenes"]):
        prefix = f"{contract['workflow_ref']}#/scenes/{i}"
        assert scene["script_ref"] == prefix
        assert resolve(scene["script_ref"])["scene_id"] == scene["scene_id"]
        for field, suffix in {
            "entry_ref": "entry_when", "transitions_ref": "transitions",
            "evidence_ref": "render_script/must_show", "success_ref": "success_evidence",
        }.items():
            assert scene[field] == f"{prefix}/{suffix}"
            assert resolve(scene[field])
        assert set(resolve(scene["transitions_ref"]).values()) <= set(expected)
        assert "transitions" not in scene  # no shadow policy table
        assert set(scene["required_components"]) == components
        assert scene["dominant_component"] in components
        assert scene["same_subject_selector"] == "[data-node-id]"
        assert scene["continuation_owner"] == "canonical_script_after_authoritative_readback"
        assert scene["related_region_selectors"]
        for selector in scene["related_region_selectors"]:
            attribute = "id" if selector.startswith("#") else "class"
            assert f'{attribute}="{selector[1:]}"' in markup, selector
    binding = contract["context_binding"]
    assert resolve(binding["authority_inputs_ref"]) == resolve(contract["action_ref"])["architecture"]["canonical_inputs"]
    assert resolve(binding["invalidation_inputs_ref"]) == resolve(contract["action_ref"])["architecture"]["invalidation_inputs"]
    assert binding["missing_mapping"] == "BLOCKED_JUDGMENT_GAP"
    placement = contract["context_placement"]
    assert placement["max_anchor_gap_css_px"] == 48
    assert placement["pointer_events"] == "none"
    assert placement["unknown_action"] == "no_operable_custom_action_cursor"
    assert placement["failure_order"] == [
        "compact_label_and_retry_local_candidates",
        "hide_transient_panel_preserve_persistent_evidence",
    ]
    assert {"hovered_target_rect", "visible_same_subject_rects", "visible_scene_related_evidence_rects", "visible_active_controls"} <= set(placement["obstacles"])
    assert {"cover_hovered_target", "cover_related_evidence", "park_on_opposite_viewport_edge", "clamp_after_collision_check", "suppress_persistent_evidence"} <= set(placement["forbidden_fallbacks"])


def test_complete_canonical_scene_composition():
    validate(load())


def validate_runtime_regions(contract, source):
    obstacle_source = source.split("const cartoucheObstacles = (host) => {", 1)[1].split(
        "if (host)", 1
    )[0]
    chamber_markup = (ROOT / "src/filesteward/visualization/decision_chamber.py").read_text(encoding="utf-8")
    # The exact same action container has both attributes. A class exclusion
    # protects the id binding without requiring a redundant selector.
    assert 'class="chamber-actions" id="chamber-actions"' in chamber_markup
    equivalent = {"#chamber-actions": ".chamber-actions"}
    for scene in contract["scenes"]:
        for selector in scene["related_region_selectors"]:
            alias = equivalent.get(selector)
            assert repr(selector) in obstacle_source or (
                alias is not None and repr(alias) in obstacle_source
            ), selector


def test_runtime_excludes_every_declared_related_region():
    source = (ROOT / "src/filesteward/visualization/experience.py").read_text(encoding="utf-8")
    validate_runtime_regions(load(), source)


def test_runtime_missing_related_region_is_rejected():
    source = (ROOT / "src/filesteward/visualization/experience.py").read_text(encoding="utf-8")
    # Positive control first prevents a pre-existing failure from satisfying
    # the negative fixture for the wrong reason.
    validate_runtime_regions(load(), source)
    source = source.replace("'#chamber-result'", "'#unrelated-result'")
    with pytest.raises(AssertionError):
        validate_runtime_regions(load(), source)


@pytest.mark.parametrize("mutation", ["omit_scene", "redirect_transition", "omit_related_evidence", "distant_panel", "occluding_fallback"])
def test_composition_rejects_regression(mutation):
    contract = deepcopy(load())
    if mutation == "omit_scene":
        contract["scenes"].pop(3)
    elif mutation == "redirect_transition":
        contract["scenes"][0]["transitions_ref"] = contract["scenes"][1]["transitions_ref"]
    elif mutation == "omit_related_evidence":
        contract["context_placement"]["obstacles"].remove("visible_scene_related_evidence_rects")
    elif mutation == "distant_panel":
        contract["context_placement"]["max_anchor_gap_css_px"] = 10000
    else:
        contract["context_placement"]["failure_order"][-1] = "cover_hovered_target"
    with pytest.raises(AssertionError):
        validate(contract)
