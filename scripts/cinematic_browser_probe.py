#!/usr/bin/env python3
"""Repeatable synthetic-only Chromium proof; never scans or deletes workstation data.

Requires installed Playwright and Chromium. Uses the retained model fixture as
the evidence oracle. Output belongs only in ignored var/runs runtime storage.
This is bounded browser proof, not deletion or all-scene workflow certification.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def snapshot(page):
    return page.evaluate("""() => ({
      workspace: {...document.getElementById('workspace')?.dataset},
      chamber: {hidden: document.getElementById('decision-chamber')?.hidden,
        scene: document.getElementById('chamber-scene-label')?.textContent,
        brief: document.getElementById('chamber-brief')?.textContent},
      filter: window.FileStewardFilters?.getFilter(),
      search: document.getElementById('storage-search')?.value,
      selected: document.querySelector('.nav-row.selected')?.dataset.nodeId,
      visibleRows: [...document.querySelectorAll('.nav-row')].filter(e => !e.hidden).map(e => e.dataset.nodeId),
      overflow: Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth,
      actions: [...document.querySelectorAll('#chamber-actions button,#chamber-next-actions-row button')]
        .map(e=>({text:e.textContent.trim(),disabled:e.disabled,...e.dataset}))
    })""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--channel", choices=["chromium", "msedge", "chrome"], default="msedge")
    parser.add_argument("--output", type=Path, default=ROOT / "var/runs/cinematic-browser-20261013")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be an alphanumeric runtime filename component")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "var/runs").resolve()):
        parser.error("output must remain under this worktree's ignored var/runs")
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("visual_fixture", ROOT / "tests/test_visualization_model.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    run = fixture._write_valid_run(output / args.label / "synthetic-run")
    from filesteward.review_bridge import serve_review
    from playwright.sync_api import sync_playwright
    service = serve_review(run, open_browser=False)
    results = {"proof_scope": "synthetic loopback browser only; no real scan/delete/schedule",
               "not_proved": ["real deletion", "all canonical scenes end-to-end", "maintenance persistence"],
               "label": args.label, "cases": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel=args.channel)
            for name, width, height, media in [
                ("desktop", 1440, 900, {}), ("narrow", 390, 844, {}),
                ("reduced-motion", 1440, 900, {"reduced_motion": "reduce"}),
                ("forced-colors", 1440, 900, {"forced_colors": "active"})]:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                case = {"mode": name, "errors": [], "steps": [], "screenshots": []}
                page.on("pageerror", lambda error, case=case: case["errors"].append(str(error)))
                page.on("console", lambda msg, case=case: case["errors"].append(msg.text) if msg.type == "error" else None)
                page.emulate_media(**media)
                page.goto(service.url, wait_until="networkidle")
                page.wait_for_timeout(300)
                case["initial"] = snapshot(page)
                def capture(suffix):
                    path = output / f"{args.label}-{name}-{suffix}.png"
                    page.screenshot(path=str(path), full_page=True)
                    case["screenshots"].append(str(path))
                def step(label, callback):
                    try:
                        callback()
                        page.wait_for_timeout(250)
                        case["steps"].append({"action": label, "state": snapshot(page)})
                    except Exception as exc:
                        case["steps"].append({"action": label, "failure": str(exc)})
                capture("home")
                # Reach every currently rendered scene entry independently.
                entries = page.locator("[data-scene-entry]").evaluate_all("els=>els.map(e=>e.id).filter(Boolean)")
                for entry in entries:
                    step("home-before:" + entry, lambda: page.locator("#brand-home").click(timeout=3000))
                    if entry == "pane_inspector":
                        step("focus-for-inspector", lambda: page.locator('.sector-card[data-node-id="review-1"]').click(timeout=3000))
                        step("decision-for-inspector", lambda: page.locator('.phone-command-bar [data-atlas-action="toggle_decision"]' if width < 800 else '#atlas-decision').click(timeout=3000))
                    step("scene-entry:" + entry, lambda entry=entry: page.locator("#" + entry).click(timeout=3000))
                step("home-keyboard", lambda: (page.locator("#brand-home").focus(), page.keyboard.press("Enter")))
                # Composition is tested through normal controls, never DOM state assignment.
                search = page.locator("#storage-search")
                step("search-pointer", lambda: search.fill("Cache", timeout=3000))
                step("filter-pointer", lambda: page.locator('.filter-chip[data-filter="HUMAN_REVIEW"]').click(timeout=3000))
                case["composed_before"] = snapshot(page)
                step("home-pointer", lambda: page.locator("#brand-home").click(timeout=3000))
                case["composed_after"] = snapshot(page)
                case["composition_preserved"] = all(case["composed_before"].get(k) == case["composed_after"].get(k) for k in ["filter", "search", "selected"])
                step("search-clear", lambda: search.fill("", timeout=3000))
                step("all-filter-keyboard", lambda: (page.locator('.filter-chip[data-filter="ALL"]').focus(), page.keyboard.press("Enter")))
                for node in ["prot-1", "unknown-1", "reclaim-1"]:
                    step("select:" + node, lambda node=node: page.locator('.nav-row[data-node-id="' + node + '"]').click(timeout=3000))
                    capture(node)
                case["final"] = snapshot(page)
                step("decision-home", lambda: page.locator('#brand-home').click(timeout=3000))
                step("decision-select-unknown", lambda: page.locator('.nav-row[data-node-id="unknown-1"]').click(timeout=3000))
                step("open-resolve", lambda: page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click(timeout=3000))
                step("keep-readback", lambda: page.locator('#chamber-next-actions-row [data-next-action="keep"]').click(timeout=3000))
                case["decision_after"] = snapshot(page)
                capture("decision-readback")
                # Both markers and authoritative runtime must advance together.
                chamber_state = page.evaluate("() => window.__filestewardDecisionChamber")
                case["decision_advanced"] = chamber_state.get("selectedNodeId") != "unknown-1"
                case["selection_agrees"] = case["decision_after"]["selected"] == chamber_state.get("selectedNodeId")
                context.close()
                results["cases"].append(case)
            browser.close()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=5)
        path = output / f"{args.label}-results.json"
        path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(path)
    failures = sum(len(c["errors"]) + sum("failure" in s for s in c["steps"]) + (not c["composition_preserved"]) + (not c.get("decision_advanced")) + (not c.get("selection_agrees")) + (c["initial"]["overflow"] > 1) for c in results["cases"])
    print(json.dumps({"failures": failures, "cases": len(results["cases"])}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
