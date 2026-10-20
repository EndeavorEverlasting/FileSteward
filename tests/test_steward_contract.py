"""Contract-only regressions for the uninstalled FileSteward hourly steward."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "harness" / "contracts"

def read(name):
    return json.loads((FILES / name).read_text(encoding="utf-8"))

def test_agent_lane_mapping_covers_every_generated_ticket():
    program = read("steward-program.v1.json")
    mapping = read("steward-adapter-map.v1.json")
    routing = read("steward-routing.v1.json")
    allowed = {lane["lane"] for lane in routing["lanes"]}
    assert set(mapping["ticket_to_lane"]) == set(program["agent_catalog"]) - {"AUDIT_MAINTENANCE"}
    assert all(set(m["consumer"]).issubset(allowed) for m in mapping["ticket_to_lane"].values())

def test_scheduler_is_hourly_readonly_and_opt_in():
    program = read("steward-program.v1.json")
    script = (ROOT / "scripts/windows/steward-hourly.ps1").read_text(encoding="utf-8")
    assert program["scheduler"]["frequency"] == "HOURLY"
    assert program["scheduler"]["disabled_until_opt_in"] is True
    assert program["scheduler"]["model_invocation_default"] == "NEVER_FROM_TIMER"
    assert "filesteward.cli scan" in script
    assert "filesteward.cli validate" in script
    assert "filesteward.steward" in script
    assert "SHGetKnownFolderPath" in script
    assert "EXPLICIT_AUTHORIZE_REQUIRED" in script
    assert "LEGACY_HOURLY_TASK_PRESENT" in script

def test_source_and_value_are_not_action_permission():
    program = read("steward-program.v1.json")
    assert program["scope"]["source_mutation"] is False
    assert "NO_SCHEDULER_SELF_APPROVAL" in program["invariants"]
    assert "MOST_PROTECTIVE_OWNER_EDGE_WINS" in program["invariants"]
    assert program["scheduler"]["max_agent_tickets_per_hour"] == 40
    assert program["scheduler"]["max_items_per_hour"] == 250
    assert read("steward-routing.v1.json")["routing_policy"]["default"] == "OUTBOX_ONLY"
