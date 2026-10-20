"""Synthetic P82 proof floor for hourly FileSteward classification."""
from datetime import datetime, timedelta, timezone
import pytest
from filesteward.steward import build_cycle, classify_item

NOW = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)

def item(name="memo.jpg", days=365, disposition="HUMAN_REVIEW", **kw):
    x = dict(item_id="id-"+name, path="/synthetic/Downloads/"+name,
             disposition=disposition, entry_type="FILE",
             scan_completeness="COMPLETE", is_symlink="False",
             is_reparse_point="False", is_cloud_placeholder="False",
             modified_at=str((NOW-timedelta(days=days)).timestamp()))
    x.update(kw)
    return x

def proof(state, source="WINDOWS_ADAPTER"):
    return dict(state=state, source=source, evidence_ref="synthetic:typed")

def assess(x, e=None):
    return classify_item(x, e or {}, scan_id="fixture", now=NOW)

def test_s01_photo_memorabilia_is_not_assumed_junk():
    c, jobs = assess(item())
    assert c["facets"]["personal_value"] == "POTENTIAL_MEMORABILIA"
    assert c["facets"]["activity"] == "LAST_MODIFIED_OLD"
    assert c["authorizes_move_or_delete"] is False
    assert any(j["lane"] == "AGENT_PERSONAL_VALUE_CONTEXT" for j in jobs)

def test_s02_declared_memorabilia_is_protected():
    c, _ = assess(item(), {"memorabilia": proof("OPERATOR_MARKED_MEMORABILIA", "OPERATOR_DECLARATION")})
    assert c["safety_floor"] == "PROTECTED"

def test_s03_app_dependency_is_protected():
    c, _ = assess(item("cache.bin"), {"ownership": proof("APP_REQUIRED")})
    assert c["safety_floor"] == "PROTECTED"

def test_s04_broken_app_serviceability_is_protected():
    c, _ = assess(item("update.exe"), {"ownership": proof("APP_BROKEN_SERVICEABILITY")})
    assert c["safety_floor"] == "PROTECTED"

def test_s05_old_modification_time_is_not_last_access():
    c, _ = assess(item("memo.docx"))
    assert c["facets"]["activity"] == "LAST_MODIFIED_OLD"
    assert c["last_access_verified"] is False

def test_s06_active_git_reference_is_protected():
    c, _ = assess(item("project.zip"), {"activity": proof("ACTIVE_REFERENCE", "GIT_ADAPTER")})
    assert c["safety_floor"] == "PROTECTED"
    assert c["facets"]["lifecycle"] == "ACTIVE_REQUIRED"

def test_s07_no_reference_does_not_prove_archive():
    c, _ = assess(item("dormant.zip"), {"activity": proof("NO_REFERENCE_FOUND_COMPLETE")})
    assert c["facets"]["lifecycle"] == "DORMANCY_CANDIDATE_REVIEW"
    assert c["authorizes_move_or_delete"] is False

def test_s08_only_operator_can_declare_archive():
    c, _ = assess(item("archive.zip"), {"archival": proof("USER_DECLARED_ARCHIVE", "OPERATOR_DECLARATION")})
    assert c["facets"]["lifecycle"] == "USER_DECLARED_ARCHIVE"
    c, _ = assess(item("archive.zip"), {"archival": proof("USER_DECLARED_ARCHIVE", "MODEL")})
    assert c["facets"]["lifecycle"] != "USER_DECLARED_ARCHIVE"

def test_s09_reparse_is_unknown():
    c, jobs = assess(item("link.zip", is_reparse_point="True"))
    assert c["safety_floor"] == "UNKNOWN"
    assert jobs[0]["lane"] == "ADAPTER_SCAN_COMPLETENESS"

def test_s10_upstream_protection_never_downgrades():
    c, _ = assess(item("data.bin", disposition="PROTECTED"), {
        "ownership": proof("NOT_ATTRIBUTED_AFTER_COMPLETE_ADAPTERS")})
    assert c["safety_floor"] == "PROTECTED"

def test_s11_bounded_queue_not_false_completion():
    rows = [item(f"x-{n}.jpg") for n in range(5)]
    report = build_cycle(rows, {}, scan_id="fixture", now=NOW, max_items=3, max_tickets=2)
    assert report["coverage"]["unobserved_budget_items"] == 2
    assert report["coverage"]["coverage_state"] == "INCOMPLETE_BUDGET"
    assert len(report["work_items"]) == 2
    assert all(t["state"] == "BLOCKED_ADAPTER" and not t["agent_dispatched"] for t in report["work_items"])

def test_s12_incorrect_disposition_and_duplicates_refused():
    with pytest.raises(ValueError, match="invalid input disposition"):
        assess(item("bad.zip", disposition="JUNK"))
    r = item("dupe.zip")
    with pytest.raises(ValueError, match="duplicate inventory"):
        build_cycle([r, r], {}, scan_id="fixture", now=NOW)

def test_result_has_no_permission_to_mutate_or_use_agents():
    x = build_cycle([item()], {}, scan_id="fixture", now=NOW)
    assert x["coverage"]["source_mutations"] == 0
    assert x["coverage"]["agent_executions"] == 0
    assert all(t["source_mutation_authorized"] is False for t in x["work_items"])
