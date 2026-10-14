"""Installed-browser checks for intermediate layout and filtered Atlas targets."""
import pytest

from filesteward.review_bridge import serve_review
from filesteward.policy.paths import run_dir
from test_visualization_model import _write_valid_run


@pytest.mark.parametrize("width", [900, 1100])
def test_intermediate_atlas_keeps_navigation_and_hides_filtered_cards(width: int):
    playwright = pytest.importorskip("playwright.sync_api")
    output = run_dir("cinematic-layout-regression") / str(width)
    service = serve_review(_write_valid_run(output / "synthetic-run"), open_browser=False)
    try:
        with playwright.sync_playwright() as driver:
            try:
                browser = driver.chromium.launch(channel="msedge", headless=True)
            except playwright.Error as error:
                pytest.skip(f"Installed Edge browser unavailable: {error}")
            try:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(service.url, wait_until="networkidle")
                search = page.locator("#storage-search")
                assert search.is_visible()
                assert page.locator('.filter-chip[data-filter="ALL"]').is_visible()
                page.locator('.sector-card[data-node-id="unknown-1"]').first.click()
                page.wait_for_timeout(650)
                assert search.is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                page.screenshot(path=str(output / "focus.png"), full_page=True)
                page.locator("#brand-home").click()
                search.fill("no-synthetic-target-matches-this-query")
                page.wait_for_timeout(100)
                cards = page.locator(".sector-card")
                assert cards.count() > 0
                assert cards.evaluate_all("els => els.every(e => e.hidden && getComputedStyle(e).display === 'none' && e.getClientRects().length === 0)")
                page.screenshot(path=str(output / "empty-search.png"), full_page=True)
                search.fill("")
                assert page.locator('.sector-card[data-node-id="unknown-1"]').first.is_visible()
                page.locator('.filter-chip[data-filter="PROTECTED"]').click()
                assert cards.evaluate_all("els => els.every(e => e.dataset.nodeId === 'prot-1' ? !e.hidden : e.hidden && getComputedStyle(e).display === 'none')")
                page.screenshot(path=str(output / "protected-filter.png"), full_page=True)
                page.locator('.filter-chip[data-filter="ALL"]').click()
                assert page.locator('.sector-card[data-node-id="unknown-1"]').first.is_visible()
            finally:
                browser.close()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=5)
