"""Browser proof of the exact removal offer and refusal on evidence drift."""

import shutil

import pytest

from filesteward.ownership.actions import unresolved_ownership
from filesteward.policy import paths
from filesteward.review_bridge import serve_review
from safe_capacity_fixtures import generated_evidence
from test_visualization_model import _write_valid_run


def test_review_removal_scope_is_visible_and_drift_refuses_the_exact_click(tmp_path, monkeypatch):
    api = pytest.importorskip("playwright.sync_api")
    runtime = tmp_path / "runtime"
    run = _write_valid_run(runtime / "runs" / "synthetic")
    scan = tmp_path / "scan"
    scan.mkdir()
    sentinel = scan / "unrelated.txt"
    sentinel.write_bytes(b"synthetic bytes")
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    fresh = True
    target = r"C:\ProgramData\ExampleTool\RegenerableCache"

    def current_evidence(path):
        if path == target and fresh:
            return generated_evidence(path)
        return unresolved_ownership(path)

    service = serve_review(
        run, open_browser=False, scan_root=scan, ownership_resolver=current_evidence
    )
    try:
        with api.sync_playwright() as driver:
            chromium = shutil.which("chromium")
            browser = driver.chromium.launch(
                **({"executable_path": chromium} if chromium else {"channel": "msedge"})
            )
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(service.url, wait_until="networkidle")

                chamber = page.locator("#decision-chamber")
                page.locator('.nav-row[data-node-id="reclaim-1"]').click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                api.expect(chamber).to_have_attribute("data-script-scene", "VALUE_DECISION")
                delete = chamber.locator('[data-decision-intent="DELETE_PERMANENTLY"]')
                api.expect(delete).to_have_count(0)
                api.expect(chamber.locator('[data-next-action="keep"]')).to_contain_text("Keep this item")
                api.expect(chamber.locator('[data-next-action="review_later"]')).to_contain_text("Review later")
                removal_options = chamber.get_by_role("button", name="Review removal options", exact=False)
                removal_options.click()

                api.expect(chamber).to_have_attribute("data-script-scene", "AUTHORIZATION_GATE")
                api.expect(chamber.locator("#chamber-delete-scope")).to_be_visible()
                api.expect(chamber.locator("#chamber-delete-path")).to_have_text(target)
                api.expect(chamber.get_by_role("heading", name="Quarantine staging scope")).to_be_visible()
                api.expect(delete).to_have_attribute("aria-describedby", "chamber-delete-scope")
                assert not (run / "delete-approval.json").exists()
                assert not (run / "approval-record.json").exists()

                fresh = False
                with page.expect_response("**/api/v1/delete") as request_result:
                    delete.click()
                response = request_result.value
                assert response.status == 400
                assert response.request.post_data_json["item_id"] == "reclaim-1"
                api.expect(chamber.locator("#chamber-error")).to_contain_text(
                    "current ownership and regeneration evidence do not admit permanent deletion"
                )
                api.expect(delete).to_have_count(0)

                page.locator("#brand-home").click()
                page.locator('.nav-row[data-node-id="unknown-1"]').click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                api.expect(chamber.locator("#chamber-delete-scope")).to_be_hidden()
                api.expect(delete).to_have_count(0)
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
