"""Non-destructive regression checks for the immutable Downloads cleanup policy.

These tests verify the admissible deterministic policy; they do not claim the
auto-quarantine executor, standing authorization or live scheduling exists.
"""
import json
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / "harness/contracts/downloads-recurring-cleanup.v1.json"


def contract():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_does_not_silently_enable_actions():
    c = contract()
    assert c["status"] == "DESIGN_CONTRACT_ONLY_NOT_LIVE_AUTHORITY"
    assert c["scheduler"]["default_mode"] == "REVIEW_ONLY"
    assert c["scheduler"]["agent_calls_per_run"] == 0
    assert c["scheduler"]["cadence_minutes"] == 60
    assert c["actions"]["exact_duplicate_zip_quarantine"]["state"] == "BLOCKED_UNTIL_DELEGATED_AUTHORITY_CONTRACT_APPROVED"
    assert c["authorization"]["default"] == "REVIEW_ONLY"
    assert c["authorization"]["standing_rule_not_currently_supported"] is True
    assert c["authorization"]["blocked_without_approval"] == "REPORT_CANDIDATES_ONLY_DO_NOT_MOVE"


def test_eligibility_requires_hash_stability_owner_proof_and_distinct_authority():
    c = contract()
    technical = "\n".join(c["candidate_eligibility_all"] + c["candidate_evidence_requirements"])
    action = "\n".join(c["action_eligibility_all"])
    for fact in ("SHA256", "two successful scans", "canonical unsuffixed", "application"):
        assert fact.lower() in technical.lower(), fact
    for fact in ("same-volume", "operator-approved standing authorization", "separate validated"):
        assert fact.lower() in action.lower(), fact
    assert "operator-approved" not in technical
    assert c["scope"]["follow_reparse_points"] is False
    assert c["scope"]["traversal"] == "TOP_LEVEL_REGULAR_FILES_ONLY"
    assert c["actions"]["exact_duplicate_zip_quarantine"]["auto_purge"] is False


def test_policy_has_fixed_fail_closed_fixtures_and_all_safe_routes():
    c = contract()
    cases = c["acceptance_cases"]
    ids = [case["id"] for case in cases]
    assert ids == [f"D{x:02d}" for x in range(1, 13)]
    expected = {
        "SKIP_INSTALLER", "SKIP_BUSINESS_DOCUMENT", "SKIP_NOT_EXACT",
        "SKIP_NO_CANONICAL", "SKIP_STALE", "SKIP_PROTECTED",
        "SKIP_REPARSE_OR_UNKNOWN", "REPORT_ONLY_ZERO_MOVES",
        "SKIP_NONZERO_NO_MUTATION", "SKIP_NO_OVERWRITE",
        "REFUSE_RESTORE_COLLISION",
    }
    assert expected.issubset({case["expect"] for case in cases})
    assert c["recovery"]["retention"] == "NO_AUTO_PURGE"
    assert c["recovery"]["restore"].startswith("EXACT_RECEIPT")


def test_no_unbounded_scope_or_hidden_delete_policy():
    c = contract()
    assert c["scope"]["root_source"] == "WINDOWS_SHGETKNOWNFOLDERPATH_FOLDERID_DOWNLOADS"
    assert c["actions"]["review_only"]["mutates_source"] is False
    q = c["actions"]["exact_duplicate_zip_quarantine"]
    assert q["max_items_per_run"] == 20
    assert q["max_total_bytes_per_run"] == 1073741824
    assert q["minimum_file_age_hours"] == 24
    assert q["minimum_scans"] == 2
    assert "NO_AUTO_PURGE" == c["recovery"]["retention"]
