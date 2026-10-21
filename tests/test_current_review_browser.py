"""Actual welcome-folder action and canonical scene readback on synthetic data."""
from pathlib import Path
import pytest

from filesteward import launch
from filesteward.policy import paths
from filesteward.ownership.current import make_current_resolver, ProbeResult


@pytest.mark.parametrize("mode,width", [("desktop",1440),("narrow",390),("reduced",1440),("forced",1440)])
def test_explicit_folder_enters_current_attribution_scene(tmp_path, monkeypatch, mode, width):
    api = pytest.importorskip("playwright.sync_api")
    output = Path(__file__).resolve().parents[1] / "var/runs/current-review-browser"
    output.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "synthetic-folder"
    root.mkdir()
    (root / "synthetic-note.txt").write_text("Synthetic fixture; metadata only", encoding="utf-8")
    before = (root / "synthetic-note.txt").read_bytes()
    runtime = tmp_path / "private-runtime/var"
    (runtime / "runs").mkdir(parents=True)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    calls = []
    def factory(admitted):
        calls.append(admitted)
        # No actual workstation registry/process/ownership probe is invoked.
        return make_current_resolver(admitted, providers={"service": lambda root, target:
            ProbeResult(False, "synthetic_service_probe", ("SYNTHETIC_COVERAGE_GAP",))})
    session, thread = launch.start_server(runtime, resolver_factory=factory)
    try:
        with api.sync_playwright() as driver:
            browser = driver.chromium.launch(channel="msedge", headless=True)
            try:
                page = browser.new_page(viewport={"width":width,"height":1000},
                    reduced_motion="reduce" if mode=="reduced" else "no-preference",
                    forced_colors="active" if mode=="forced" else "none")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.origin, wait_until="networkidle")
                assert calls == []
                page.locator("#scan-root").fill(str(root))
                # Keyboard submission is the same explicit admission action.
                page.locator("#scan-root").press("Enter")
                page.locator("#open-current").wait_for(state="visible", timeout=15000)
                assert calls == [root]
                result = page.locator("#scan-result").inner_text()
                assert "Ownership: incomplete" in result
                assert "SYNTHETIC_COVERAGE_GAP" in result
                assert "synthetic_service_probe" in result
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                page.screenshot(path=str(output / (mode + "-folder-result.png")), full_page=True)
                page.locator("#open-current").click()
                page.wait_for_url("**/", timeout=15000)
                page.locator("#storage-stage").wait_for(timeout=15000)
                card = page.locator(".sector-card[data-node-id]").first
                card.click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                page.wait_for_function("window.__filestewardDecisionChamber && window.__filestewardDecisionChamber.sceneEvidence")
                evidence = page.evaluate("window.__filestewardDecisionChamber.sceneEvidence")
                assert evidence["raw_delete_eligible"] is False
                assert evidence["scene_id"] == "ATTRIBUTION_RESOLVE"
                api.expect(page.locator("#chamber-evidence-chapters")).to_contain_text("SYNTHETIC_COVERAGE_GAP")
                assert "DELETE PERMANENTLY" not in page.locator("#decision-chamber").inner_text()
                page.screenshot(path=str(output / (mode + "-current-attribution.png")), full_page=True)
                page.locator("#brand-home").click()
                assert not errors
                assert (root / "synthetic-note.txt").read_bytes() == before
            finally:
                browser.close()
    finally:
        session.server.shutdown(); session.server.server_close(); session.close()
        thread.join(timeout=3)
