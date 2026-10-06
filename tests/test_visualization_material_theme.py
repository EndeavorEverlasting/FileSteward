from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "docs" / "program" / "storage-reclaim-visual-system.tokens.json"


def _tokens() -> dict:
    return json.loads(TOKENS.read_text(encoding="utf-8"))


def test_material_palette_is_canonical_and_reference_bound() -> None:
    tokens = _tokens()
    ref = tokens["material_reference_palette"]
    assert ref["family"] == "warm-material"
    assert "AYOCIN" in ref["reference"]
    assert "navy" in ref["forbidden_dominant"]
    assert "cyan" in ref["forbidden_dominant"]


def test_dark_atlas_palette_is_espresso_walnut_copper_not_blue() -> None:
    dark = _tokens()["themes"]["dark"]
    assert dark["bg-canvas"] == "#15120F"
    assert dark["bg-shell"] == "#1C1814"
    assert dark["bg-selected"] == "#4A3528"
    assert dark["accent"] == "#D7AA82"
    assert dark["focus"] == "#E7C49F"
    assert dark["state-keep"] == "#A9AD7B"
    old_blue_values = {
        "#0F1318", "#141920", "#23384E", "#83C5F7", "#8BCBFF", "#82B9EE",
    }
    assert not old_blue_values.intersection(dark.values())


def test_light_palette_uses_ivory_walnut_and_moss() -> None:
    light = _tokens()["themes"]["light"]
    assert light["bg-canvas"] == "#F3EDE3"
    assert light["bg-shell"] == "#FBF7F0"
    assert light["accent"] == "#8D5F3F"
    assert light["state-keep"] == "#626B43"
    assert light["state-reclaim"] == "#4F713E"


def test_palette_invariants_forbid_dominant_blue_cyan_and_direct_delete() -> None:
    invariants = set(_tokens()["invariants"])
    assert "dominant_atlas_palette_is_warm_material_not_blue_cyan" in invariants
    assert "delete_intent_stages_quarantine_before_any_permanent_deletion" in invariants
    assert "no_mutation_without_exact_operator_approval_receipt" in invariants
