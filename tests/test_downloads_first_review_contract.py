"""Retained specification guards for the Downloads-first, one-click scope contract.

This file verifies the design artifact, not implementation or live UX. The
behavioral acceptance suite is deliberately RED until the product is built.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "harness/contracts/downloads-first-review.v1.json"


def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_has_canonical_authority_and_no_second_judgment_owner():
    spec = contract()
    assert spec["schema_version"] == "filesteward.downloads-first-review/v1"
    assert "docs/agent/CANONICAL-PATHS.md" in spec["canonical_references"]
    assert "src/filesteward/contracts/runtime-profile.v1.json" in spec["canonical_references"]
    assert "harness/contracts/judgment-scene-workflow.v1.json" in spec["canonical_references"]
    assert spec["operating_modes"]["startup"] == "NO_PERSONAL_SCAN"
    assert spec["operating_modes"]["review"] == "EXPLICIT_SINGLE_SCOPE_METADATA_ONLY"


def test_os_discovery_is_distinct_from_install_storage_and_guessed_paths():
    spec = contract()
    windows = spec["windows"]
    assert windows["downloads_known_folder_guid"] == "374DE290-123F-4565-9164-39C4925E467B"
    assert windows["resolver"] == "SHGetKnownFolderPath(FOLDERID_Downloads)"
    assert windows["installation_profile"] == "windows-localappdata/v1"
    assert {"USERPROFILE/Downloads", "HOME/Downloads", "cwd",
            "executable_directory", "LocalAppData/FileSteward"}.issubset(
                windows["forbidden_fallbacks"])
    assert spec["default_scope"]["root_source"] == "operating_system_known_folder_only"
    assert "forbidden-root" in spec["default_scope"]["eligibility_protection"]
    assert "runtime_root()" in spec["default_scope"]["output_location"]


def test_one_click_action_is_explicit_and_opens_review_without_second_click():
    spec = contract()
    welcome = spec["welcome"]
    assert welcome["primary_label"] == "Review Downloads"
    assert welcome["primary_element_id"] == "review-downloads"
    assert welcome["secondary_label"] == "Browse folders here"
    assert welcome["secondary_element_id"] == "browse-folders"
    assert welcome["native_picker_label"] == "Windows folder picker"
    assert welcome["native_picker_element_id"] == "choose-folder"
    assert contract()["api"]["browser"]["effect"].startswith("directory-only in-app navigation")
    assert "without a second click" in welcome["success_transition"]
    states = {row["id"]: row for row in spec["states"]}
    assert len(states) == 8
    assert states["WELCOME_DISCOVERING"]["effect"].endswith("only")
    assert "one authenticated" in states["REVIEW_READING"]["effect"]
    assert "automatically" in states["REVIEW_READY"]["effect"]
    assert "fail closed" in states["REVIEW_ERROR"]["effect"]


def test_default_admission_uses_authenticated_opaque_single_use_scope():
    spec = contract()
    api = spec["api"]
    assert api["recommend"]["method"] == "GET"
    assert api["recommend"]["path"] == "/api/v1/launch/recommended-scope"
    assert api["recommend"]["effect"] == "DISCOVER_ONLY"
    assert api["recommend"]["token_lifetime_seconds"] <= 600
    assert "single-use" in api["recommend"]["token_storage"]
    assert api["begin"]["method"] == "POST"
    assert api["begin"]["path"] == "/api/v1/launch/current-scan"
    assert api["begin"]["default_body_keys"] == ["scope_token"]
    assert api["begin"]["legacy_body_keys"] == ["scan_root"]
    assert "Host+Origin+session-header" in api["begin"]["auth"]
    assert api["choose"]["effect"].startswith("interactive_native_Windows_folder_picker_only")


def test_regression_categories_are_complete_and_unique():
    ids = contract()["invariant_ids"]
    assert len(ids) == 16
    assert len(set(ids)) == len(ids)
    assert {f"D{n:02d}" for n in range(1, 17)} == {item.split("_")[0] for item in ids}
    required = {"D01_no_scan_on_open_or_discovery", "D02_one_click_begins_and_opens_review",
                "D06_drift_between_display_and_click_refused",
                "D10_sample_import_and_old_captures_remain_observational",
                "D12_runtime_storage_stays_os_owned",
                "D16_after_process_restart_requires_new_click"}
    assert required <= set(ids)
