"""Exact source/scene coverage and non-authorizing dependency measurements."""
from copy import deepcopy
import json
from pathlib import Path
import time
import subprocess

import pytest
from filesteward.models import CleanupDisposition
from filesteward.ownership.actions import OwnershipEvidence, dependency_summary, plan_owner_actions
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.visualization.judgment_script import resolve_scene_evidence

ROOT = Path(__file__).resolve().parents[1]


def load_map():
    return json.loads((ROOT / "harness/contracts/feature-map.v1.json").read_text(encoding="utf-8"))



EXPECTED_SOURCE_ROOTS = {"src", "scripts", "packaging", ".github/workflows", ".agents/skills", ".cursor/rules"}
EXPECTED_EXPLICIT_FILES = {
    "FileSteward-source.cmd", "pyproject.toml", "AGENTS.md", "README.md",
    "docs/assets/favicon.svg", "docs/assets/launch.css", "docs/index.html",
    "docs/program/storage-reclaim-visualization-prototype.html",
}
EXPECTED_CONTRACT_ROOTS = {"harness/contracts", "harness/evals"}
EXPECTED_TEST_ROOTS = {"tests"}
SOURCE_SUFFIXES = (".py", ".ps1", ".cmd", ".sh", ".html", ".css", ".svg",
                   ".js", ".jsx", ".ts", ".tsx", ".mdc", ".toml", ".yml", ".yaml")


def validate_map(mapping, source_paths, all_files=None):
    # A manifest cannot hide new files by removing a watched root or source type.
    assert set(mapping["scope"]["roots"]) == EXPECTED_SOURCE_ROOTS
    assert set(mapping["scope"]["root_files"]) == EXPECTED_EXPLICIT_FILES
    assert set(mapping["scope"]["contract_roots"]) == EXPECTED_CONTRACT_ROOTS
    assert set(mapping["scope"]["test_roots"]) == EXPECTED_TEST_ROOTS
    features = mapping["features"]
    ids = [feature["id"] for feature in features]
    assert len(ids) == len(set(ids))
    mapped = [p for feature in features for p in feature["source_paths"]]
    assert len(mapped) == len(set(mapped)), "duplicate source ownership"
    assert set(mapped) == source_paths, (source_paths - set(mapped), set(mapped) - source_paths)
    workflow = json.loads((ROOT / mapping["workflow_ref"]).read_text(encoding="utf-8"))
    composition = json.loads((ROOT / mapping["composition_ref"]).read_text(encoding="utf-8"))
    order = workflow["scene_order"]
    assert [s["scene_id"] for s in mapping["scenes"]] == order
    assert [s["scene_id"] for s in composition["scenes"]] == order
    for feature in features:
        assert feature["source_paths"] and feature["tests"]
        assert set(feature["scene_ids"]) <= set(order)
        assert all((ROOT / test).is_file() for test in feature["tests"])
    # Feature ownership covers the executable system *and* its policy/proof sources.
    contracted = [p for f in features for p in f.get("contract_paths", [])]
    assert len(contracted) == len(set(contracted)), "duplicate contract ownership"
    assert set(contracted) == inventory_scoped(mapping["scope"]["contract_roots"])
    test_sources = {p for f in features for p in f["tests"]}
    assert test_sources == inventory_scoped(mapping["scope"]["test_roots"], suffix=".py")
    tracked = inventory_scoped(["."]) if all_files is None else set(all_files)
    unowned = {p for p in tracked if p.endswith(SOURCE_SUFFIXES)} - (
        set(mapped) | set(contracted) | test_sources
    )
    assert not unowned, "new executable or presentation source outside mapped scope: " + repr(sorted(unowned))
    for scene in mapping["scenes"]:
        expected = {f["id"] for f in features if scene["scene_id"] in f["scene_ids"]}
        assert expected and set(scene["feature_ids"]) == expected


def inventory_scoped(scope, *, suffix=None):
    # Include unignored new sources as well as tracked files; never scan host data.
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *scope],
        cwd=ROOT,
    )
    result = set(raw.decode("utf-8").split("\0")) - {""}
    if suffix is not None:
        result = {path for path in result if path.endswith(suffix)}
    assert all((ROOT / path).is_file() for path in result), "tracked source missing"
    return result


def inventory(mapping):
    scope = mapping["scope"]["roots"] + mapping["scope"]["root_files"]
    return inventory_scoped(scope)


def test_exact_source_and_scene_map():
    mapping = load_map()
    actual = inventory(mapping)
    validate_map(mapping, actual)
    with pytest.raises(AssertionError):
        validate_map(mapping, actual | {"src/filesteward/unmapped.py"})
    bad = deepcopy(mapping)
    bad["scenes"].pop()
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    bad["features"][0]["source_paths"].append(bad["features"][1]["source_paths"][0])
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    bad["features"][-1]["contract_paths"].remove("harness/contracts/feature-map.v1.json")
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    for feature in bad["features"]:
        if "tests/test_antivirus_detector.py" in feature["tests"]:
            feature["tests"].remove("tests/test_antivirus_detector.py")
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    bad = deepcopy(mapping)
    bad["scope"]["roots"].remove("scripts")
    with pytest.raises(AssertionError):
        validate_map(bad, actual)
    with pytest.raises(AssertionError):
        validate_map(mapping, actual, all_files=inventory_scoped(["."]) | {"new-area/agent.py"})


def test_app_dependency_veto_with_incomplete_discovery():
    path = r"C:\\Demo\\component.dll"
    edge = OwnershipEdge("RUNTIME_REQUIRES", path, "APPLICATION", "demo", "Demo",
                         "synthetic runtime reference", "strong", "APP_ACTIVE_REQUIRED")
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=(edge,)), False, time.time())
    plan = plan_owner_actions(path, evidence)
    summary = dependency_summary(path, evidence, plan)
    assert plan.disposition is CleanupDisposition.PROTECTED
    assert summary["application_owner_count"] == 1
    assert summary["protective_edge_count"] == 1
    assert summary["raw_delete_disqualified"]
    assert not summary["current_evidence_complete"]
    projected = resolve_scene_evidence(path, CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert projected["effective_disposition"] == "PROTECTED"
    assert projected["dependency_summary"]["raw_delete_disqualified"]
    assert not projected["raw_delete_eligible"]


def test_no_edges_is_not_disposability():
    path = r"C:\\Demo\\unknown.bin"
    evidence = OwnershipEvidence(build_ownership_graph(), False, time.time())
    summary = dependency_summary(path, evidence, plan_owner_actions(path, evidence))
    assert summary["protective_edge_count"] == 0
    assert summary["raw_delete_disqualified"]
    assert not summary["current_evidence_complete"]

def test_service_reference_is_positive_only_and_path_scoped(tmp_path):
    from filesteward.ownership import current

    service = tmp_path / "service.exe"
    sibling = tmp_path / "unrelated.bin"
    service.write_bytes(b"fixture")
    sibling.write_bytes(b"fixture")
    references = (("demo", "ImagePath", str(service)),)
    result = current._service_projection(tmp_path, tmp_path, references)
    assert not result.complete
    assert len(result.edges) == 1
    assert result.edges[0].storage_path == str(service)
    assert result.edges[0].edge_type == "SERVICE_REFERENCES"
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=result.edges), False, time.time())
    assert plan_owner_actions(str(service), evidence).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(sibling), evidence).disposition is CleanupDisposition.UNKNOWN
    view = resolve_scene_evidence(str(service), CleanupDisposition.RECLAIM_PROVEN, evidence)
    assert view["ownership_badge"] == "Required by service"
    assert view["effective_disposition"] == CleanupDisposition.PROTECTED.value
    assert view["dependency_summary"]["protective_edge_count"] == 1
    assert view["dependency_summary"]["raw_delete_disqualified"] is True
    assert view["raw_delete_eligible"] is False
    assert "Required by service" in view["trace"][1]["finding"]
    assert not current._service_projection(tmp_path, sibling, references).edges
    assert not current._service_projection(tmp_path, tmp_path, ()).complete


def test_known_required_service_does_not_appear_unknown_when_other_domains_fail():
    path = r"C:\\Services\\daemon.exe"
    edge = OwnershipEdge("SERVICE_REFERENCES", path, "SERVICE", "service:daemon",
                         "daemon", "windows_service_registry", "strong", "")
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=(edge,)), False, time.time())
    view = resolve_scene_evidence(path, CleanupDisposition.UNKNOWN, evidence)
    assert view["ownership_badge"] == "Required by service"
    assert view["effective_disposition"] == "PROTECTED"
    assert view["scene_id"] == "ATTRIBUTION_RESOLVE"
    assert view["raw_delete_eligible"] is False


def test_chamber_renders_dependency_metrics_without_mutation():
    source = (ROOT / "src/filesteward/visualization/decision_chamber.py").read_text(encoding="utf-8")
    assert "evidence.dependency_summary" in source
    assert "unresolved discovery domains" in source
    assert "facts.appendChild(metrics)" in source
    assert "Safe raw deletion has not been established." in source


def test_service_registry_collector_reads_synthetic_positive_references(tmp_path, monkeypatch):
    """Read-only Winreg fixture proves both service executable and ServiceDll."""
    from types import SimpleNamespace
    import sys
    from filesteward.ownership import current

    exe = tmp_path / "service.exe"
    dll = tmp_path / "service.dll"
    exe.write_bytes(b"executable")
    dll.write_bytes(b"library")

    class Key:
        def __init__(self, location):
            self.location = location
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def open_key(parent, name, *args):
        if parent == "HKLM":
            return Key("root")
        if parent.location == "root" and name == "DemoSvc":
            return Key("service")
        if parent.location == "service" and name == "Parameters":
            return Key("parameters")
        raise FileNotFoundError()

    def query_value(key, name):
        if key.location == "service" and name == "ImagePath":
            return ('"' + str(exe) + '" --service', 1)
        if key.location == "parameters" and name == "ServiceDll":
            return (str(dll), 1)
        raise FileNotFoundError()

    fake = SimpleNamespace(
        HKEY_LOCAL_MACHINE="HKLM", KEY_READ=1, REG_SZ=1, REG_EXPAND_SZ=2,
        OpenKey=open_key,
        QueryInfoKey=lambda key: (1, 0, 0),
        EnumKey=lambda key, i: "DemoSvc",
        QueryValueEx=query_value,
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    observations, gaps = current._read_service_registrations()
    assert not gaps
    assert set(observations) == {
        ("DemoSvc", "ImagePath", str(exe)),
        ("DemoSvc", "ServiceDll", str(dll)),
    }
    projected = current._service_projection(tmp_path, tmp_path, observations)
    assert len(projected.edges) == 2
    assert not projected.complete
    evidence = OwnershipEvidence(build_ownership_graph(extra_edges=projected.edges), False, time.time())
    assert plan_owner_actions(str(exe), evidence).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(dll), evidence).disposition is CleanupDisposition.PROTECTED


def test_service_registry_failure_is_explicit_not_evidence_of_absence(monkeypatch):
    import sys
    from types import SimpleNamespace
    from filesteward.ownership import current

    def denied(*args):
        raise PermissionError("synthetic protected message")
    fake = SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", KEY_READ=1, OpenKey=denied)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    observations, gaps = current._read_service_registrations()
    assert observations == ()
    assert gaps == ("SERVICE_REGISTRY_UNREADABLE",)
    assert "synthetic protected message" not in repr((observations, gaps))


@pytest.mark.parametrize(
    "mode,width,height",
    [("desktop", 1440, 1000), ("narrow", 390, 844), ("reduced", 1440, 1000), ("forced", 1440, 1000)],
)
def test_decision_chamber_browser_service_protection_and_reclaim_control(
    tmp_path, monkeypatch, mode, width, height
):
    """Browser proof: service-required protection blocks delete while positive control stays reachable."""
    import shutil

    api = pytest.importorskip("playwright.sync_api")
    from filesteward.ownership.actions import unresolved_ownership
    from filesteward.ownership.current import CurrentOwnershipEvidence, ProbeCoverage
    from filesteward.policy import paths
    from filesteward.review_bridge import serve_review
    from safe_capacity_fixtures import generated_evidence
    from test_visualization_model import _write_valid_run

    runtime = tmp_path / "runtime"
    run = _write_valid_run(runtime / "runs" / "synthetic")
    scan = tmp_path / "scan"
    scan.mkdir()
    sentinel = scan / "unrelated.txt"
    sentinel.write_bytes(b"synthetic bytes")
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)

    service_target = r"C:\ExampleRestricted"
    reclaim_target = r"C:\ProgramData\ExampleTool\RegenerableCache"

    def current_evidence(path):
        if path == service_target:
            edge = OwnershipEdge(
                "SERVICE_REFERENCES",
                path,
                "SERVICE",
                "service:DemoSvc",
                "DemoSvc",
                "windows_service_registry",
                "strong",
                "",
                "Registered service ImagePath references this path",
            )
            return CurrentOwnershipEvidence(
                build_ownership_graph(extra_edges=(edge,)),
                False,
                time.time(),
                coverage=(
                    ProbeCoverage(
                        "service",
                        False,
                        "windows_service_registry",
                        ("SERVICE_RUNTIME_DEPENDENCY_COMPLETENESS_UNPROVEN",),
                    ),
                ),
            )
        if path == reclaim_target:
            return generated_evidence(path)
        return unresolved_ownership(path)

    service = serve_review(
        run, open_browser=False, scan_root=scan, ownership_resolver=current_evidence
    )
    output = ROOT / "var" / "runs" / "fs80-scene-browser"
    output.mkdir(parents=True, exist_ok=True)
    try:
        with api.sync_playwright() as driver:
            chromium = shutil.which("chromium")
            browser = driver.chromium.launch(
                **({"executable_path": chromium} if chromium else {"channel": "msedge"})
            )
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    reduced_motion="reduce" if mode == "reduced" else "no-preference",
                    forced_colors="active" if mode == "forced" else "none",
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(service.url, wait_until="networkidle")

                chamber = page.locator("#decision-chamber")
                # Protected negative fixture: positive service edge with incomplete discovery.
                unknown_row = page.locator('.nav-row[data-node-id="unknown-1"]')
                if mode == "desktop":
                    unknown_row.focus()
                    unknown_row.press("Enter")
                else:
                    unknown_row.click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                page.wait_for_function(
                    "window.__filestewardDecisionChamber && window.__filestewardDecisionChamber.sceneEvidence"
                )
                evidence = page.evaluate("window.__filestewardDecisionChamber.sceneEvidence")
                assert evidence["ownership_badge"] == "Required by service"
                assert evidence["effective_disposition"] == "PROTECTED"
                assert evidence["raw_delete_eligible"] is False
                assert evidence["dependency_summary"]["protective_edge_count"] == 1
                assert evidence["dependency_summary"]["raw_delete_disqualified"] is True

                page.locator("#chamber-evidence-trace > summary").click()
                facts = chamber.locator("#chamber-evidence-facts")
                api.expect(facts).to_contain_text("Required by service: DemoSvc")
                api.expect(facts).to_contain_text("1 protective dependency edges; 0 dependent applications;")
                api.expect(facts).to_contain_text("Raw deletion excluded by positive dependency evidence.")
                api.expect(chamber.locator('[data-decision-intent="DELETE_PERMANENTLY"]')).to_have_count(0)
                api.expect(chamber.locator("#chamber-delete-scope")).to_be_hidden()
                assert "DELETE PERMANENTLY" not in chamber.inner_text()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                if mode in {"desktop", "narrow"}:
                    page.screenshot(path=str(output / f"{mode}-service-protected.png"), full_page=True)

                # Reclaimable positive control: fresh regenerable evidence stays reachable.
                page.locator("#brand-home").click()
                page.locator('.nav-row[data-node-id="reclaim-1"]').click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                api.expect(chamber).to_have_attribute("data-script-scene", "VALUE_DECISION")
                reclaim_facts = chamber.locator("#chamber-evidence-facts")
                api.expect(reclaim_facts).to_contain_text("0 protective dependency edges;")
                api.expect(reclaim_facts).to_contain_text(
                    "Reclaim candidate only; separate operator approval required."
                )
                chamber.get_by_role("button", name="Review removal options", exact=False).click()
                api.expect(chamber).to_have_attribute("data-script-scene", "AUTHORIZATION_GATE")
                api.expect(chamber.locator("#chamber-delete-scope")).to_be_visible()
                assert not errors
                assert not (run / "delete-approval.json").exists()
                assert not (run / "delete-execution-receipt.json").exists()
                assert sentinel.read_bytes() == b"synthetic bytes"
            finally:
                browser.close()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=5)

