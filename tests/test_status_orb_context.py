"""Selection changes project the existing grammar into the persistent HUD."""

from dataclasses import replace

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright.sync_playwright

from filesteward.models import CleanupDisposition, ScanCompleteness
from filesteward.visualization.shell import _render_status_orbs, _selection_script
from tests.test_visualization_interaction import _node


def test_status_orbs_follow_selection_and_clear_without_client_classification() -> None:
    protected = replace(_node(disposition=CleanupDisposition.PROTECTED), node_id="protected")
    gap = replace(
        _node(disposition=CleanupDisposition.UNKNOWN, completeness=ScanCompleteness.INCOMPLETE,
              item_count=None), node_id="gap",
    )
    templates = "".join(
        f'<template data-status-orbs-for="{node.node_id}">{_render_status_orbs(node)}</template>'
        for node in (protected, gap)
    )
    with sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(channel="msedge", headless=True)
        except playwright.Error as error:
            pytest.skip(f"Installed Edge browser unavailable: {error}")
        try:
            page = browser.new_page()
            page.set_content(_render_status_orbs(None) + templates + _selection_script())
            assert page.locator("#atlas-status-orbs").is_hidden()
            page.evaluate("FileStewardSelection.activate('protected')")
            protection = page.locator('[data-orb-kind="PROTECTED"]')
            assert protection.get_attribute("data-actionability") == "OPERABLE"
            assert "Protection blocks reclaim" in protection.get_attribute("data-cue-explain")
            assert page.locator('[data-orb-kind="EVIDENCE_GAP"]').get_attribute("data-actionability") == "INFORMATIONAL"
            page.evaluate("FileStewardSelection.activate('gap')")
            assert protection.get_attribute("data-actionability") == "INFORMATIONAL"
            assert "No PROTECTED overlap" in protection.get_attribute("data-cue-explain")
            evidence = page.locator('[data-orb-kind="EVIDENCE_GAP"]')
            assert evidence.get_attribute("data-actionability") == "OPERABLE"
            assert "Evidence gap" in evidence.get_attribute("data-cue-explain")
            assert page.locator("#atlas-status-orbs").get_attribute("data-context-node-id") == "gap"
            page.evaluate("document.dispatchEvent(new CustomEvent('filesteward:selection-cleared'))")
            assert page.locator("#atlas-status-orbs").is_hidden()
            assert page.locator(".status-orb").count() == 0
        finally:
            browser.close()
