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
        brief: document.getElementById('chamber-brief')?.textContent,
        blocksPath: (() => {const a=document.getElementById('decision-chamber'), b=document.getElementById('decision-compass');
          if(!a||!b||a.hidden)return false; const r=a.getBoundingClientRect(),s=b.getBoundingClientRect();
          return s.bottom>0&&s.top<innerHeight&&r.left<s.right&&r.right>s.left&&r.top<s.bottom&&r.bottom>s.top;})()},
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
    parser.add_argument("--full-acceptance", action="store_true", help="include real touch, empty-state restoration and state-read failure controls")
    parser.add_argument("--resolved-fixtures", action="store_true", help="inject retained synthetic ownership evidence; never a live resolver")
    parser.add_argument("--output", type=Path, default=ROOT / "var/runs/cinematic-browser-20261013")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be an alphanumeric runtime filename component")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "var/runs").resolve()):
        parser.error("output must remain under this worktree's ignored var/runs")
    output.mkdir(parents=True, exist_ok=True)
    if (output / args.label).exists():
        parser.error("this label already has preserved evidence; choose a fresh label")
    spec = importlib.util.spec_from_file_location("visual_fixture", ROOT / "tests/test_visualization_model.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    run = fixture._write_valid_run(output / args.label / "synthetic-run")
    from filesteward.review_bridge import serve_review
    from playwright.sync_api import sync_playwright
    options = {}
    if args.resolved_fixtures:
        sys.path.insert(0, str(ROOT / "tests"))
        from safe_capacity_fixtures import generated_evidence
        options["ownership_resolver"] = generated_evidence
    service = serve_review(run, open_browser=False, **options)
    results = {"proof_scope": "synthetic loopback browser only; no real scan/delete/schedule",
               "not_proved": ["real deletion", "all canonical scenes end-to-end", "maintenance persistence"],
               "label": args.label, "normalized_ownership": args.resolved_fixtures, "cases": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel=args.channel)
            modes = [
                ("desktop", 1440, 900, {}), ("narrow", 390, 844, {}),
                ("reduced-motion", 1440, 900, {"reduced_motion": "reduce"}),
                ("forced-colors", 1440, 900, {"forced_colors": "active"})]
            if args.full_acceptance:
                modes.append(("touch", 390, 844, {}))
            for name, width, height, media in modes:
                # A mode must not inherit completed decisions from an earlier
                # mode. Compare the same fresh workload with independent owners.
                service.server.shutdown()
                service.server.server_close()
                service.thread.join(timeout=5)
                mode_run = fixture._write_valid_run(output / args.label / name / "synthetic-run")
                service = serve_review(mode_run, open_browser=False, **options)
                context = browser.new_context(viewport={"width": width, "height": height},
                    has_touch=name == "touch", is_mobile=name == "touch")
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
                if args.full_acceptance and name == "desktop":
                    card = page.locator('.sector-card[data-node-id="review-1"]')
                    card.scroll_into_view_if_needed()
                    rect = card.bounding_box()
                    point = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
                    page.mouse.move(*point)
                    page.wait_for_timeout(100)
                    def reticle_state():
                        return page.evaluate("""() => {const e=document.getElementById('atlas-reticle'), r=e.getBoundingClientRect();
                          return {visible:e.classList.contains('is-visible'),x:r.x+28,y:r.y+28};}""")
                    before_pointer = reticle_state()
                    page.locator('#atlas-decision').focus()
                    page.wait_for_timeout(100)
                    after_pointer = reticle_state()
                    case["pointer_focus_stable"] = not after_pointer["visible"] or (
                        abs(before_pointer["x"] - after_pointer["x"]) <= 2 and abs(before_pointer["y"] - after_pointer["y"]) <= 2)
                    page.locator('.filter-chip[data-filter="ALL"]').click(timeout=3000)
                    case["ordinary_click_no_range"] = page.locator('#atlas-range-marquee').get_attribute('hidden') is not None
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
                if args.full_acceptance:
                    expected_rows = snapshot(page)["visibleRows"]
                    step("search-empty", lambda: search.fill("no-synthetic-row-matches-92741"))
                    case["empty_search"] = not snapshot(page)["visibleRows"]
                    case["empty_explained"] = page.locator('#navigator-empty-state').is_visible() and "No items match" in page.locator('#navigator-empty-state').inner_text()
                    step("search-restore", lambda: search.fill(""))
                    case["empty_restored"] = snapshot(page)["visibleRows"] == expected_rows
                step("all-filter-keyboard", lambda: (page.locator('.filter-chip[data-filter="ALL"]').focus(), page.keyboard.press("Enter")))
                for node in ["prot-1", "unknown-1", "reclaim-1"]:
                    step("select:" + node, lambda node=node: page.locator('.nav-row[data-node-id="' + node + '"]').click(timeout=3000))
                    capture(node)
                case["final"] = snapshot(page)
                if args.resolved_fixtures:
                    step("value-home", lambda: page.locator('#brand-home').click(timeout=3000))
                    step("value-select", lambda: page.locator('.nav-row[data-node-id="reclaim-1"]').click(timeout=3000))
                    step("value-open", lambda: page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click(timeout=3000))
                    case["value_scene"] = page.locator('#decision-chamber').get_attribute('data-script-scene')
                    # A prior mode may already have the same persisted value
                    # intent. It remains unapproved; fresh evidence must agree.
                    if case["value_scene"] == "VALUE_DECISION":
                        step("value-mark", lambda: page.locator('[data-next-action="reclaim_generated_output"]').click(timeout=3000))
                    case["authorization_scene"] = page.locator('#decision-chamber').get_attribute('data-script-scene')
                    case["value_did_not_authorize"] = page.evaluate("() => window.__filestewardDecisionChamber.auth === 'UNAPPROVED'")
                    if name == "touch":
                        before_scroll = page.locator('#decision-chamber').evaluate("el => el.scrollTop")
                        rect = page.locator('#decision-chamber').bounding_box()
                        session = context.new_cdp_session(page)
                        x, y = rect['x'] + rect['width'] * .5, rect['y'] + rect['height'] - 35
                        session.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
                        for index in range(1,11):
                            session.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':x,'y':max(rect['y']+15,y-index*15)}]})
                            page.wait_for_timeout(30)
                        session.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
                        page.wait_for_timeout(150)
                        case['touch_chamber_scroll'] = page.locator('#decision-chamber').evaluate("el => el.scrollTop") > before_scroll
                        session.detach()
                    original_viewport = page.viewport_size
                    page.set_viewport_size({'width':width,'height':height-80})
                    page.wait_for_timeout(100)
                    case['resize_clear'] = not snapshot(page)['chamber']['blocksPath']
                    page.set_viewport_size(original_viewport)
                    page.wait_for_timeout(850)
                    capture("exact-authorization")
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
                if args.full_acceptance:
                    if name == "touch":
                        step("touch-home", lambda: page.locator('#brand-home').tap(timeout=3000))
                        step("touch-filter", lambda: page.locator('.filter-chip[data-filter="UNKNOWN"]').tap(timeout=3000))
                        case["touch_effect"] = snapshot(page)["filter"] == "UNKNOWN"
                        step("touch-all", lambda: page.locator('.filter-chip[data-filter="ALL"]').tap(timeout=3000))
                    # Read failure is intentionally injected; it must be visible
                    # and fail closed, rather than silently inventing local state.
                    step("failure-home", lambda: page.locator('#brand-home').click(timeout=3000))
                    page.route("**/api/v1/state?*", lambda route: route.abort())
                    step("failure-open", lambda: page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click(timeout=3000))
                    case["read_failure_visible"] = page.locator('#chamber-error').is_visible()
                    case["read_failure_closed"] = page.evaluate("() => window.__filestewardDecisionChamber.allowedIntents.length === 0")
                    page.unroute("**/api/v1/state?*")
                    capture("read-failure")
                    # Network-abort console entries are expected only in this
                    # deliberate negative control; JS exceptions still fail.
                    case["expected_abort_messages"] = [e for e in case["errors"] if 'net::ERR_FAILED' in e]
                    case["errors"] = [e for e in case["errors"] if 'net::ERR_FAILED' not in e]
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
    if args.full_acceptance:
        failures += sum(not c.get(check) for c in results["cases"] for check in
                       ["empty_search", "empty_explained", "empty_restored", "read_failure_visible", "read_failure_closed"])
        failures += sum(not c.get(check) for c in results["cases"] if c["mode"] == "touch"
                        for check in ["touch_effect", "touch_chamber_scroll"])
        failures += sum(not c.get("resize_clear") for c in results["cases"] if args.resolved_fixtures)
        failures += sum(not c.get(check) for c in results["cases"] if c["mode"] == "desktop"
                       for check in ["pointer_focus_stable", "ordinary_click_no_range"])
        failures += sum(bool(s.get("state", {}).get("chamber", {}).get("blocksPath")) for c in results["cases"] for s in c["steps"])
    if args.resolved_fixtures:
        failures += sum(c.get("authorization_scene") != "AUTHORIZATION_GATE" or not c.get("value_did_not_authorize") for c in results["cases"])
    print(json.dumps({"failures": failures, "cases": len(results["cases"])}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
