"""Synthetic browser proof for spatial scene arrival and authored input chrome."""
import pytest
from filesteward.policy.paths import run_dir
from filesteward.review_bridge import serve_review
from filesteward.sample import write_sample_run


@pytest.mark.parametrize('mode,width,height', [('desktop',1910,910),('dark',1910,910),('keyboard',1440,900),('narrow',390,844),('reduced',1440,900),('forced',1440,900)])
def test_resolve_frames_selected_world_and_active_destination(mode,width,height):
    api=pytest.importorskip('playwright.sync_api')
    output=run_dir('resolve-framing-browser')/mode
    output.mkdir(parents=True,exist_ok=True)
    sample=output/'synthetic-sample'
    if not sample.exists():
        write_sample_run(sample,'resolve-framing-'+mode)
    service=serve_review(sample,open_browser=False,observation_only=True)
    try:
        with api.sync_playwright() as driver:
            try:
                browser=driver.chromium.launch(channel='msedge',headless=True)
            except api.Error as error:
                pytest.skip(f'Installed Edge unavailable: {error}')
            try:
                page=browser.new_page(viewport={'width':width,'height':height},color_scheme='dark' if mode=='dark' else 'light',reduced_motion='reduce' if mode=='reduced' else 'no-preference',forced_colors='active' if mode=='forced' else 'none')
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(service.url,wait_until='networkidle')
                page.locator('.nav-row[data-node-id="sample-downloads"]').click()
                page.evaluate('window.scrollTo(0,0)')
                initial=page.locator('.storage-substrate').evaluate('e=>getComputedStyle(e).transform')
                waypoint_transforms=[]
                for waypoint in ('MAP','FOCUS','GATE'):
                    step=page.locator(f'.decision-guide-step[data-guide-step="{waypoint}"]')
                    if mode=='keyboard':
                        step.focus();page.keyboard.press('Enter')
                    else:
                        step.click()
                    page.wait_for_timeout(850)
                    waypoint_transforms.append(page.locator('.storage-substrate').evaluate('e=>getComputedStyle(e).transform'))
                    if waypoint!='MAP':
                        assert abs(page.locator('#storage-stage').bounding_box()['y']-12)<2
                target=page.locator('.decision-guide-step[data-guide-step="RESOLVE"]')
                if mode=='keyboard':
                    target.focus()
                    page.keyboard.press('Enter')
                else:
                    target.click()
                page.wait_for_timeout(950)
                actual=page.evaluate("""() => {
                  const rect=s=>{let r=document.querySelector(s).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
                  return {identity:rect('.focus-identity'),world:rect('.focus-chamber'),chamber:rect('#decision-chamber'),path:rect('#decision-compass'),hostTransform:getComputedStyle(document.getElementById('focus-host')).transform,
                    subject:document.querySelector('.focus-identity h3').textContent,stageTop:document.getElementById('storage-stage').getBoundingClientRect().top,
                    active:document.querySelector('.decision-guide-step.is-active').dataset.guideStep,
                    scrollbar:getComputedStyle(document.getElementById('decision-chamber')).scrollbarColor,
                    viewportScrollbar:getComputedStyle(document.documentElement).scrollbarColor};
                }""")
                assert actual['subject']=='Downloads to review'
                assert actual['stageTop']>=-1 and actual['stageTop']<30
                assert actual['identity']['top']>=0 and actual['identity']['bottom']<=height
                assert actual['identity']['left']>=0 and actual['identity']['right']<=width
                assert actual['hostTransform']=='none'
                assert page.locator('.focus-layer').evaluate('e=>getComputedStyle(e).filter')=='none'
                assert page.locator('.focus-chamber').evaluate('e=>getComputedStyle(e).transform')=='none'
                assert actual['active']=='RESOLVE'
                a,b=actual['chamber'],actual['path']
                assert a['top']>=0 and a['bottom']<=height
                assert a['left']>=0 and a['right']<=width
                assert page.locator('#decision-chamber').evaluate("e=>['auto','scroll'].includes(getComputedStyle(e).overflowY)")
                assert page.locator('#chamber-brief').inner_text().strip()
                assert not (a['left']<b['right'] and a['right']>b['left'] and a['top']<b['bottom'] and a['bottom']>b['top'])
                if width>=1180:
                    assert a['left']>=actual['world']['right']
                if mode!='forced':
                    waypoint_transforms.append(page.locator('.storage-substrate').evaluate('e=>getComputedStyle(e).transform'))
                    assert len(set(waypoint_transforms))==4
                if mode!='forced':
                    assert actual['scrollbar']!='auto' and actual['viewportScrollbar']!='auto'
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/'resolve-arrived.png'))
                if mode not in ('forced','keyboard'):
                    identity=page.locator('.focus-identity').bounding_box()
                    page.mouse.move(identity['x']+identity['width']*.5,identity['y']+identity['height']*.5)
                    page.wait_for_timeout(80)
                    assert page.locator('#atlas-reticle').evaluate("e=>e.classList.contains('is-visible')")
                    assert page.locator('.focus-identity').evaluate("e=>getComputedStyle(e).cursor")=='none'
                    assert page.locator('#atlas-reticle-label').inner_text()==''
                    assert page.locator('#atlas-reticle-label').evaluate('e=>getComputedStyle(e).display')=='none'
                    position=page.locator('#atlas-reticle').evaluate('e=>e.style.transform')
                    page.evaluate("document.dispatchEvent(new Event('scroll'))")
                    assert page.locator('#atlas-reticle').evaluate("e=>e.classList.contains('is-visible')")
                    assert page.locator('#atlas-reticle').evaluate('e=>e.style.transform')==position
                    assert page.locator('#atlas-cartouche').is_hidden()
                # An interrupted traversal must settle at the most recent target.
                page.locator('.decision-guide-step[data-guide-step="GATE"]').click()
                page.wait_for_timeout(80)
                page.locator('.decision-guide-step[data-guide-step="RESOLVE"]').click()
                page.wait_for_timeout(900)
                assert page.locator('#workspace').get_attribute('data-path-preview')=='RESOLVE'
                assert page.locator('#focus-host').evaluate("e=>getComputedStyle(e).transform")=='none'
                assert not errors
            finally:
                browser.close()
    finally:
        service.server.shutdown();service.server.server_close();service.thread.join(timeout=5)
