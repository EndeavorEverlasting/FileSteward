"""Installed reports retain the canonical scene script and terminal routing."""
from importlib import resources
import json
from pathlib import Path

import pytest

from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.visualization import judgment_script, tokens
from filesteward.visualization.decision_flow import DecisionFlowState, DecisionScene


def test_packaged_scene_contract_is_exact_canonical_mirror():
    canonical = Path(__file__).resolve().parents[1] / "harness/contracts/judgment-scene-workflow.v1.json"
    packaged = resources.files("filesteward").joinpath("contracts", canonical.name)
    assert packaged.read_bytes() == canonical.read_bytes(), "Refresh the exact packaged mirror after canonical edits"


def test_packaged_visual_tokens_are_exact_canonical_mirror():
    canonical = Path(__file__).resolve().parents[1] / "docs/program/storage-reclaim-visual-system.tokens.json"
    packaged = resources.files("filesteward").joinpath("contracts", canonical.name)
    assert packaged.read_bytes() == canonical.read_bytes(), "Refresh the exact packaged token mirror after canonical edits"


def test_token_path_prefers_canonical_then_packaged_mirror(monkeypatch, tmp_path):
    monkeypatch.setattr(tokens, "__file__", str(tmp_path / "src/filesteward/visualization/tokens.py"))
    canonical = tmp_path / "docs/program/storage-reclaim-visual-system.tokens.json"
    packaged = tmp_path / "src/filesteward/contracts/storage-reclaim-visual-system.tokens.json"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("packaged", encoding="utf-8")
    assert tokens.token_document_path() == packaged
    canonical.parent.mkdir(parents=True)
    canonical.write_text("canonical", encoding="utf-8")
    assert tokens.token_document_path() == canonical


def test_installed_layout_loads_packaged_contract_without_repository(monkeypatch, tmp_path):
    monkeypatch.setattr(judgment_script, "__file__", str(tmp_path / "site-packages/filesteward/visualization/judgment_script.py"))
    assert not (tmp_path / "harness").exists()
    scenes = judgment_script.load_scene_script()
    assert len(scenes) == 11
    assert scenes["VERIFY_RETURN"]["primary_impact"] == "VERIFY"
    assert "data-script-scene=\"ATLAS_HOME\"" in judgment_script.render_script_index()


def test_present_canonical_contract_does_not_fall_back_when_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr(judgment_script, "__file__", str(tmp_path / "src/filesteward/visualization/judgment_script.py"))
    canonical = tmp_path / "harness/contracts/judgment-scene-workflow.v1.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("invalid canonical JSON", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        judgment_script.load_scene_script()


@pytest.mark.parametrize("stage", [DecisionScene.RESULT, DecisionScene.CLOSED])
def test_terminal_receipt_scene_overrides_prior_authorization_script(stage):
    flow = DecisionFlowState("synthetic", stage, CleanupDisposition.RECLAIM_PROVEN,
                             AuthorizationState.APPLIED, script_scene_id="AUTHORIZATION_GATE")
    assert judgment_script.project_script(flow, completed=True)["scene_id"] == "VERIFY_RETURN"
    assert judgment_script.project_script(flow, incident=True)["scene_id"] == "INCIDENT_RECOVERY"
