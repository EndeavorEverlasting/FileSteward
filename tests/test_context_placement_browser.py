"""Installed-browser controls for local, collision-free transient context."""
import math
import pytest
from filesteward.policy.paths import run_dir
from filesteward.review_bridge import serve_review
from test_visualization_model import _write_valid_run


@pytest.fixture
def context_browser():
    api = pytest.importorskip("playwright.sync_api")
    output = run_dir("scene-context-browser-regression")
    service = serve_review(_write_valid_run(output / "synthetic-run"), open_browser=False)
    try:
        with api.sync_playwright() as driver:
            try:
                browser = driver.chromium.launch(channel="msedge", headless=True)
            except api.Error as error:
                pytest.skip(f"Installed Edge unavailable: {error}")
            try:
                yield browser, service.url, output
            finally:
                browser.close()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=5)


def snapshot(page):
    return page.evaluate("""() => {
      const c=document.getElementById('atlas-cartouche');
      const r=c.getBoundingClientRect();
      return {hidden:c.hidden, presentation:c.dataset.presentation,
        rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},
        reticle:document.getElementById('atlas-reticle').classList.contains('is-visible'),
        custom:document.getElementById('storage-stage').classList.contains('has-context-reticle'),
        label:document.getElementById('atlas-reticle-label').textContent,
        described:document.querySelectorAll('[aria-describedby~=atlas-cartouche]').length};
    }""")


def hover_card_edge(page, node="reclaim-1"):
    card = page.locator(f'.sector-card[data-node-id="{node}"]').first
    card.scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    box = card.bounding_box()
    x, y = box["x"] + box["width"] * .02, box["y"] + box["height"] * .98
    page.mouse.move(x, y)
    # Stationary hover must reproject after the authored transform settles.
    # No follow-up pointer event may be needed to restore legal context.
    page.wait_for_timeout(350)
    page.wait_for_timeout(80)
    return card, x, y


@pytest.mark.parametrize("mode,width", [("desktop",1440),("narrow",900),("reduced",1440),("forced",1440)])
def test_context_locality_positive_and_congested_fallback(context_browser,mode,width):
    browser,url,output=context_browser
    page=browser.new_page(viewport={"width":width,"height":1000},
        reduced_motion="reduce" if mode=="reduced" else "no-preference",
        forced_colors="active" if mode=="forced" else "none")
    try:
        page.goto(url,wait_until="networkidle")
        # A real authored card boundary supplies a legal full seat on desktop;
        # narrow composition intentionally may compact or suppress this seat.
        card,x,y=hover_card_edge(page)
        state=snapshot(page)
        if width==1440:
            assert not state["hidden"]
            assert state["presentation"]=="full"
            assert state["described"]==1
        if not state["hidden"]:
            r=state["rect"]
            gap=math.hypot(max(r["left"]-x,x-r["right"],0),max(r["top"]-y,y-r["bottom"],0))
            assert gap<=48
            assert r["left"]>=8 and r["top"]>=8
            assert r["right"]<=width-8 and r["bottom"]<=992
            assert card.evaluate("""e=>{let a=e.getBoundingClientRect(),b=document.getElementById('atlas-cartouche').getBoundingClientRect();return !(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top)}""")
        if not state["hidden"]:
            # A tooltip cannot hide a duplicate same-subject representation,
            # nor any visible operable control/related authored evidence.
            assert page.evaluate("""() => {
                let c=document.getElementById('atlas-cartouche').getBoundingClientRect();
                let targets=document.querySelectorAll('[data-node-id="reclaim-1"],button,a,input,select,summary,[tabindex="0"],.chamber-subject,#chamber-evidence-trace');
                return [...targets].every(e=>{if(!e.getClientRects().length)return true;let r=e.getBoundingClientRect();return !(r.left<c.right&&r.right>c.left&&r.top<c.bottom&&r.bottom>c.top)});
            }""")
        page.screenshot(path=str(output/f"{mode}-local-context.png"))
        # Card center has no local seat outside its subject. Never dock remotely.
        card.hover()
        page.wait_for_timeout(80)
        state=snapshot(page)
        assert state["hidden"]
        assert not state["custom"]
        assert state["described"]==0
        assert not state["reticle"]
        # Physical reticle is always absent in reduced motion/forced colors.
        hover_card_edge(page)
        if mode in ("reduced","forced"):
            assert page.locator('#atlas-reticle').evaluate("e=>getComputedStyle(e).display") == "none"
    finally:
        page.close()


def test_context_dismissal_invalidation_and_unknown_action(context_browser):
    browser,url,output=context_browser
    page=browser.new_page(viewport={"width":1440,"height":1000})
    try:
        page.goto(url,wait_until="networkidle")
        hover_card_edge(page)
        assert not snapshot(page)["hidden"]
        page.keyboard.press("Escape")
        assert snapshot(page)["hidden"] and snapshot(page)["described"]==0
        page.mouse.move(5,5)
        hover_card_edge(page)
        assert not snapshot(page)["hidden"]
        page.evaluate("document.dispatchEvent(new Event('scroll'))")
        assert snapshot(page)["hidden"]
        page.mouse.move(5,5)
        hover_card_edge(page)
        page.set_viewport_size({"width":1400,"height":1000})
        page.wait_for_function("document.getElementById('atlas-cartouche').hidden")
        assert snapshot(page)["hidden"]
        hover_card_edge(page)
        page.evaluate("document.querySelector('#workspace').dataset.scene='test-new-context'")
        page.wait_for_timeout(50)
        assert snapshot(page)["hidden"]
        # An actual empty authored canvas point is not an operable EXPLORE.
        page.mouse.move(1432,990)
        state=snapshot(page)
        assert state["hidden"] and not state["reticle"] and not state["custom"]
        assert state["label"]!="EXPLORE"
    finally:
        page.close()


def test_keyboard_context_does_not_use_old_pointer_or_teleport_reticle(context_browser):
    browser,url,output=context_browser
    page=browser.new_page(viewport={"width":1440,"height":1000})
    try:
        page.goto(url,wait_until="networkidle")
        card,_,_=hover_card_edge(page)
        page.mouse.move(1330,780)
        page.keyboard.press("Tab")
        card.focus()
        page.wait_for_timeout(80)
        state=snapshot(page)
        assert not state["reticle"] and not state["custom"]
        if not state["hidden"]:
            # Locality belongs to focus bounds, not the preceding pointer.
            a=card.bounding_box();r=state["rect"]
            dx=max(a["x"]-r["right"],r["left"]-a["x"]-a["width"],0)
            dy=max(a["y"]-r["bottom"],r["top"]-a["y"]-a["height"],0)
            assert math.hypot(dx,dy)<=48
        page.screenshot(path=str(output/"keyboard-context.png"))
    finally:
        page.close()


def test_home_timeout_cannot_hide_replacement_scene_or_overlap_path(context_browser):
    browser, url, output = context_browser
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(url, wait_until="networkidle")
        page.locator('#brand-home').click()
        page.wait_for_timeout(100)
        page.evaluate("""() => {
          window.__sceneOverlapFrames=[];
          const end=performance.now()+2400;
          const sample=()=>{
            const chamber=document.getElementById('decision-chamber');
            const a=chamber.getBoundingClientRect();
            const b=document.getElementById('decision-compass').getBoundingClientRect();
            window.__sceneOverlapFrames.push(!chamber.hidden&&b.bottom>0&&b.top<innerHeight&&a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top);
            if(performance.now()<end)requestAnimationFrame(sample);
          };requestAnimationFrame(sample);
        }""")
        page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
        assert page.locator('#atlas-scene-panel').is_visible()
        page.wait_for_timeout(1800)
        assert page.locator('#atlas-scene-panel').is_visible()
        assert "RESOLVE" in page.locator('#atlas-scene-panel-title').inner_text()
        page.wait_for_timeout(500)
        frames=page.evaluate('window.__sceneOverlapFrames')
        assert len(frames)>30
        assert not any(frames), "Chamber covered Decision Path during scene continuation"
        page.screenshot(path=str(output/'home-replacement-scene.png'))
    finally:
        page.close()


def test_explicit_range_drag_retains_cue_until_release(context_browser):
    browser, url, output = context_browser
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(350)
        page.locator('#storage-search').fill('no-synthetic-target-matches-this-query')
        page.locator('#storage-stage').scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        # Find a genuine eligible map surface by browser hit testing. Never inject a
        # fake cue/host or drag an authored button to obtain a passing positive.
        points=page.evaluate("""() => {
          const surface=document.getElementById('storage-stage').getBoundingClientRect();
          const chrome='input,textarea,button,a,select,[contenteditable="true"],.decision-compass,.decision-chamber,.atlas-hud,.filters,.navigator-pane,header.shell,.chamber-actions,.next-action';
          const candidates=[];
          for(let y=Math.max(20,surface.top+20);y<Math.min(innerHeight-70,surface.bottom-70);y+=40)
            for(let x=Math.max(20,surface.left+20);x<Math.min(innerWidth-100,surface.right-100);x+=80){
              let e=document.elementFromPoint(x,y);
              if(e&&!e.closest(chrome)&&e.closest('.map-wrap,.map-stage,#storage-stage,.map-node,[data-atlas-surface]'))candidates.push({x,y});
            }
          return candidates;
        }""")
        assert points, "Authored map lacks a reachable non-chrome drag surface"
        positive=None
        for point in points:
            x,y=point['x'],point['y']
            page.mouse.click(x,y)
            assert page.locator('#atlas-range-marquee').is_hidden()
            page.mouse.move(x,y)
            page.mouse.down()
            page.mouse.move(x+12,y+12)
            page.wait_for_timeout(150)
            page.evaluate('() => new Promise(requestAnimationFrame)')
            state=snapshot(page)
            if not state['hidden'] and state['label']=='FRAME RANGE':
                positive=state
                assert page.locator('#atlas-range-marquee').is_visible()
                page.screenshot(path=str(output/'explicit-range-drag.png'))
                page.mouse.up()
                assert page.locator('#atlas-range-marquee').is_hidden()
                assert snapshot(page)['hidden']
                break
            page.mouse.up()
        assert positive is not None, "Explicit range drag lost FRAME RANGE before release"
    finally:
        page.close()


def test_rendered_context_geometry_after_old_right_seat_and_resize(context_browser):
    browser, url, output = context_browser
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(url, wait_until="networkidle")
        # Establish an actual authored context first, then exercise a right-edge
        # target and shrink the viewport while its old positioning is retained.
        hover_card_edge(page)
        assert not snapshot(page)['hidden']
        page.locator('#storage-search').fill('no-synthetic-target-matches-this-query')
        page.locator('#storage-stage').scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        bounds=page.locator('#storage-stage').bounding_box()
        old_seat=None
        for y in range(max(30,int(bounds['y'])+60),850,50):
            page.mouse.move(1340,y)
            page.mouse.down()
            page.mouse.move(1352,y+12)
            page.wait_for_timeout(150)
            candidate=snapshot(page)
            if not candidate['hidden'] and candidate['rect']['left']>900:
                old_seat=candidate
                break
            page.mouse.up()
        assert old_seat is not None, 'No real right-edge range context seat'
        page.set_viewport_size({'width':900,'height':1000})
        page.wait_for_timeout(150)
        page.mouse.up()
        page.locator('#storage-search').fill('')
        visible=0
        for node_id in ('reclaim-1','keep-1','unknown-1'):
            card,x,y=hover_card_edge(page,node_id)
            state=snapshot(page)
            if state['hidden']:
                continue
            visible+=1
            r=state['rect']
            assert r['left']>=8 and r['right']<=892
            assert r['top']>=8 and r['bottom']<=992
            assert math.hypot(max(r['left']-x,x-r['right'],0),max(r['top']-y,y-r['bottom'],0))<=48
            assert card.evaluate("""e=>{let a=e.getBoundingClientRect(),b=document.getElementById('atlas-cartouche').getBoundingClientRect();return !(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top)}""")
        assert visible>0, 'Resized actual targets never expose a legal context seat'
        page.screenshot(path=str(output/'context-after-resize.png'))
    finally:
        page.close()
