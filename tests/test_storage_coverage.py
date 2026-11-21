"""Storage coverage stays independent of map projection and action authority."""

from __future__ import annotations

import csv
import json
import shutil

import pytest

from filesteward.manifest import write_inventory, write_run_metadata
from filesteward.policy import paths
from filesteward.review_bridge import serve_review
from filesteward.visualization.coverage_view import render_storage_coverage
from filesteward.visualization.model import build_presentation_model
from filesteward.visualization.storage_coverage import summarize_inventory
from test_visualization_model import _write_buckets, _write_valid_run


def test_sector_coverage_counts_only_measured_regular_files() -> None:
    def file(path, disposition, size, **flags):
        return dict(path=path, disposition=disposition, logical_size_bytes=size,
                    entry_type="FILE") | flags

    coverage = summarize_inventory(iter([
        file(r"C:\Scan\Work\keep", "KEEP_PROVEN", "40"),
        file(r"c:\scan\work\check", "HUMAN_REVIEW", "10"),
        file(r"C:\Scan\Work\unread", "UNKNOWN", ""),
        file(r"C:\Scan\Cache\regenerable", "RECLAIM_PROVEN", "20"),
        file(r"C:\Scan\Cache\cloud", "UNKNOWN", "9000", is_cloud_placeholder="True"),
        file(r"C:\Scan\Cache\linked", "UNKNOWN", "9000", is_reparse_point="True"),
        file(r"C:\Scan\Cache", "RECLAIM_PROVEN", "9000", entry_type="DIRECTORY"),
        file(r"C:\Scan\root-item", "PROTECTED", "25"),
        file(r"C:\Other\unmapped", "UNKNOWN", "5"),
    ]), r"C:\Scan")

    assert coverage.total.files == 6
    assert coverage.total.unmeasured == 1
    assert coverage.total.total_bytes == 100
    assert coverage.total.classified_bytes == 85
    sectors = dict(coverage.sectors)
    assert set(sectors) == {"Work\\", "Cache\\", "Files in scan root", "Sector unavailable"}
    assert sectors["Work\\"].classified_bytes == 40
    assert sectors["Work\\"].total_bytes == 50
    assert sectors["Work\\"].unmeasured == 1
    assert sectors["Sector unavailable"].classified_bytes == 0
    html = render_storage_coverage(coverage)
    assert '--coverage-share:85.000000%' in html
    assert 'title="100 bytes"' in html
    assert "Sector unavailable" in html


def _write_file_inventory(run):
    _write_valid_run(run)
    inventory_path = run / "inventory.csv"
    with inventory_path.open(newline="", encoding="utf-8") as stream:
        inventory = list(csv.DictReader(stream))
    for row in inventory:
        row["entry_type"] = "FILE"
    write_inventory(inventory_path, inventory)
    metadata_path = run / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    write_run_metadata(metadata_path, metadata | {"root": "C:\\"})
    return inventory


def test_large_map_buckets_do_not_change_the_coverage_denominator(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    inventory = _write_file_inventory(run)
    full = build_presentation_model(run)
    _write_buckets(run, [{
        "prefix": r"C:\ExampleRestricted",
        "depth": 1,
        "item_count": 5001,
        "logical_bytes_known": 1234,
        "unknown_size_count": 0,
        "contract_hint_tags": "",
    }])
    monkeypatch.setattr("filesteward.visualization.model._ROW_EXPAND_LIMIT", 1)
    grouped = build_presentation_model(run)

    assert len(grouped.nodes) == 1 < len(full.nodes)
    assert grouped.storage_coverage == full.storage_coverage
    assert grouped.storage_coverage.total.files == len(inventory)
    assert grouped.storage_coverage.total.total_bytes == sum(
        int(row["logical_size_bytes"]) for row in inventory
    )
    html = render_storage_coverage(grouped.storage_coverage)
    assert "Immediate folders under the scan root" in html


def test_sector_names_are_rendered_as_literal_text() -> None:
    coverage = summarize_inventory(iter([{
        "path": "/scan/<img onerror=alert(1)>/note",
        "entry_type": "FILE",
        "disposition": "UNKNOWN",
        "logical_size_bytes": "1",
    }]), "/scan")
    html = render_storage_coverage(coverage)
    assert "&lt;img onerror=alert(1)&gt;/" in html
    assert "<img onerror" not in html


def test_missing_measurements_do_not_create_a_pie() -> None:
    coverage = summarize_inventory([], None)
    html = render_storage_coverage(coverage)
    assert "No regular file measurements" in html
    assert 'class="coverage-pie"' not in html


def test_coverage_shows_saved_choices_without_reclassifying_scan(tmp_path, monkeypatch) -> None:
    api = pytest.importorskip("playwright.sync_api")
    runtime = tmp_path / "runtime"
    run = runtime / "runs" / "synthetic"
    _write_file_inventory(run)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    service = serve_review(run, open_browser=False, observation_only=True)
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
                coverage = page.locator("#storage-coverage")
                summary = coverage.get_by_text("Storage coverage by sector", exact=True)
                counts = coverage.locator("#coverage-decision-counts")
                summary.press("Enter")
                api.expect(counts).to_contain_text("No Keep, Review later, or removal decisions recorded yet.")
                pie = coverage.locator(".coverage-pie")
                api.expect(pie).to_be_visible()
                scan_totals = coverage.locator(".coverage-key").inner_text()
                row = coverage.get_by_role("row").filter(has_text="Users")
                row.get_by_text("Breakdown").click()
                api.expect(row.get_by_text("Needs review", exact=False)).to_be_visible()
                summary.click()

                page.locator('.nav-row[data-node-id="review-1"]').click()
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                with page.expect_response("**/api/v1/decision") as response:
                    page.locator('#decision-chamber [data-next-action="keep"]').click()
                assert response.value.ok
                summary.click()
                api.expect(counts).to_have_text("Keep 1")
                assert coverage.locator(".coverage-key").inner_text() == scan_totals
                assert (run / "decision-chamber-state.json").is_file()
                assert not (run / "delete-approval.json").exists()

                page.reload(wait_until="networkidle")
                summary.click()
                api.expect(counts).to_have_text("Keep 1")
                page.set_viewport_size({"width": 390, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                assert not errors
            finally:
                browser.close()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=5)
