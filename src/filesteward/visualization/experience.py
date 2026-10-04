"""High-salience cinematic experience layer for Memory Atlas v3.

This layer is presentation-only. It projects existing camera / selection /
decision state into stronger spatial affordances. It never infers evidence,
changes authorization, or creates a second state machine.
"""

from __future__ import annotations

__all__ = [
    "render_cinematic_experience_css",
    "render_cinematic_experience_markup",
    "render_cinematic_experience_script",
]


def render_cinematic_experience_markup() -> str:
    """Persistent Home, contextual cursor, and state-driven decision guide."""

    return r"""
<div class="atlas-experience-layer">
  <button type="button"
          class="atlas-home-beacon"
          data-atlas-action="home"
          aria-label="Return to Atlas home">
    <span aria-hidden="true">⌂</span>
    <span>ATLAS HOME</span>
    <kbd>Home</kbd>
  </button>

  <div class="atlas-back-hint" aria-hidden="true">
    <kbd>Esc</kbd><span>BACK</span>
  </div>

  <section class="decision-compass"
           id="decision-compass"
           aria-label="Decision path"
           aria-live="polite">
    <div class="decision-compass-status">
      <span class="decision-compass-kicker">DECISION PATH</span>
      <strong id="decision-compass-now">MAP THE PRESSURE</strong>
      <span id="decision-compass-next">Choose a dominant sector or search for exact evidence.</span>
    </div>
    <ol class="decision-compass-steps">
      <li class="decision-guide-step is-active" data-guide-step="MAP">
        <span class="guide-index">01</span><strong>MAP</strong>
        <span>Find where space lives</span>
      </li>
      <li class="decision-guide-step" data-guide-step="FOCUS">
        <span class="guide-index">02</span><strong>FOCUS</strong>
        <span>Magnify exact evidence</span>
      </li>
      <li class="decision-guide-step" data-guide-step="RESOLVE">
        <span class="guide-index">03</span><strong>RESOLVE</strong>
        <span>Clear the first unresolved gate</span>
      </li>
      <li class="decision-guide-step" data-guide-step="DECIDE">
        <span class="guide-index">04</span><strong>DECIDE</strong>
        <span>Human authorization stays separate</span>
      </li>
    </ol>
  </section>

  <div class="atlas-reticle"
       id="atlas-reticle"
       data-cursor-mode="explore"
       aria-hidden="true">
    <span class="reticle-bracket reticle-bracket-nw"></span>
    <span class="reticle-bracket reticle-bracket-ne"></span>
    <span class="reticle-bracket reticle-bracket-sw"></span>
    <span class="reticle-bracket reticle-bracket-se"></span>
    <span class="reticle-core"></span>
    <span class="reticle-label" id="atlas-reticle-label">EXPLORE</span>
  </div>
</div>
"""


def render_cinematic_experience_css() -> str:
    """High-salience scene grammar using existing FileSteward semantic tokens."""

    return r"""
.storage-stage{
  --atlas-signal:var(--fs-accent);
  --atlas-gate:var(--fs-state-review-edge);
  --atlas-danger:var(--fs-state-protected-edge);
}
.atlas-experience-layer{position:absolute;inset:0;z-index:8;pointer-events:none;}
.atlas-home-beacon{
  pointer-events:auto;position:absolute;left:1rem;top:1rem;z-index:12;
  display:flex;align-items:center;gap:.55rem;min-height:44px;padding:.55rem .75rem;
  border:1px solid color-mix(in srgb,var(--atlas-signal) 58%,var(--fs-border-default));
  border-radius:4px;background:color-mix(in srgb,var(--fs-bg-shell) 88%,transparent);
  color:var(--fs-text-primary);font:800 .72rem/1 var(--fs-font-mono);
  letter-spacing:.075em;
  box-shadow:0 0 0 1px color-mix(in srgb,var(--atlas-signal) 16%,transparent),
             0 0 28px color-mix(in srgb,var(--atlas-signal) 16%,transparent);
  backdrop-filter:blur(8px);cursor:pointer;
}
.atlas-home-beacon::before{
  content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;
  background:linear-gradient(90deg,transparent,var(--atlas-signal),transparent);
  opacity:.78;
}
.atlas-home-beacon kbd,.atlas-back-hint kbd{
  padding:.2rem .36rem;border:1px solid var(--fs-border-default);border-radius:3px;
  background:var(--fs-bg-surface-3);color:var(--fs-text-secondary);
  font:700 .67rem/1 var(--fs-font-mono);
}
.atlas-back-hint{
  position:absolute;right:1rem;top:1rem;z-index:12;
  display:flex;align-items:center;gap:.4rem;color:var(--fs-text-muted);
  font:800 .68rem/1 var(--fs-font-mono);letter-spacing:.07em;
}

.decision-compass{
  position:absolute;left:50%;top:1rem;transform:translateX(-50%);z-index:11;
  width:min(48rem,calc(100% - 20rem));min-width:28rem;
  display:grid;grid-template-columns:minmax(12rem,.75fr) minmax(22rem,1.4fr);gap:.8rem;
  padding:.55rem .7rem;
  border:1px solid color-mix(in srgb,var(--atlas-signal) 30%,var(--fs-border-subtle));
  border-radius:5px;
  background:linear-gradient(180deg,
    color-mix(in srgb,var(--fs-bg-shell) 90%,transparent),
    color-mix(in srgb,var(--fs-bg-surface-2) 78%,transparent));
  box-shadow:0 10px 40px rgba(0,0,0,.18),
             inset 0 1px 0 color-mix(in srgb,white 6%,transparent);
  backdrop-filter:blur(10px);
}
.decision-compass::after{
  content:"";position:absolute;left:1rem;right:1rem;bottom:-1px;height:1px;
  background:linear-gradient(90deg,transparent,var(--atlas-signal),var(--atlas-gate),transparent);
  opacity:.82;box-shadow:0 0 14px color-mix(in srgb,var(--atlas-signal) 38%,transparent);
}
.decision-compass-status{display:grid;align-content:center;gap:.2rem;min-width:0;}
.decision-compass-kicker{
  color:var(--atlas-signal);font:800 .66rem/1 var(--fs-font-mono);letter-spacing:.11em;
}
.decision-compass-status strong{
  color:var(--fs-text-primary);font:800 .83rem/1.1 var(--fs-font-mono);letter-spacing:.04em;
}
.decision-compass-status>span:last-child{
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:var(--fs-text-muted);font-size:.72rem;
}
.decision-compass-steps{
  list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));gap:2px;align-items:stretch;
}
.decision-guide-step{
  position:relative;display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;
  gap:.08rem .35rem;align-content:center;padding:.4rem .5rem;min-width:0;
  border:1px solid var(--fs-border-subtle);
  background:color-mix(in srgb,var(--fs-bg-surface-2) 82%,transparent);
  opacity:.46;
  transition:opacity 180ms ease-out,border-color 180ms ease-out,
             box-shadow 220ms ease-out,transform 220ms cubic-bezier(.16,1,.3,1);
}
.decision-guide-step .guide-index{
  grid-row:1/3;align-self:center;color:var(--fs-text-muted);
  font:700 .62rem/1 var(--fs-font-mono);
}
.decision-guide-step strong{font:800 .66rem/1 var(--fs-font-mono);letter-spacing:.07em;}
.decision-guide-step>span:last-child{
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:var(--fs-text-muted);font-size:.62rem;
}
.decision-guide-step.is-complete{opacity:.68;}
.decision-guide-step.is-complete::after{
  content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
  background:var(--atlas-signal);opacity:.55;
}
.decision-guide-step.is-active{
  opacity:1;border-color:var(--atlas-gate);transform:translateY(-1px);
  box-shadow:0 0 0 1px color-mix(in srgb,var(--atlas-gate) 35%,transparent),
             0 0 24px color-mix(in srgb,var(--atlas-gate) 26%,transparent);
}
.decision-guide-step.is-active::before{
  content:"NOW";position:absolute;right:.35rem;top:-.52rem;padding:.15rem .25rem;
  background:var(--fs-bg-shell);color:var(--atlas-gate);
  font:900 .52rem/1 var(--fs-font-mono);letter-spacing:.08em;
}

/* Selection must read as energized rather than merely outlined. */
.sector-card.selected,.map-node.selected{
  box-shadow:
    inset 0 0 0 2px var(--atlas-signal),
    0 0 0 1px color-mix(in srgb,var(--atlas-signal) 60%,transparent),
    0 0 22px color-mix(in srgb,var(--atlas-signal) 38%,transparent),
    0 0 54px color-mix(in srgb,var(--atlas-signal) 18%,transparent)!important;
}
.signal-primary{
  position:relative;overflow:visible;
  box-shadow:0 0 0 1px color-mix(in srgb,var(--atlas-gate) 54%,transparent),
             0 0 24px color-mix(in srgb,var(--atlas-gate) 24%,transparent);
  animation:fs-signal-breathe 1550ms ease-in-out infinite;
}
.signal-primary::before{
  content:"";position:absolute;inset:-3px;
  border:1px solid color-mix(in srgb,var(--atlas-gate) 70%,transparent);
  border-radius:inherit;pointer-events:none;
  animation:fs-signal-ring 1550ms ease-out infinite;
}
.signal-hard-stop{
  border-color:var(--atlas-danger)!important;
  box-shadow:inset 4px 0 0 var(--atlas-danger),
             0 0 0 1px color-mix(in srgb,var(--atlas-danger) 50%,transparent)!important;
  animation:none!important;
}
@keyframes fs-signal-breathe{
  0%,100%{filter:brightness(1);box-shadow:0 0 0 1px color-mix(in srgb,var(--atlas-gate) 48%,transparent),0 0 16px color-mix(in srgb,var(--atlas-gate) 18%,transparent)}
  50%{filter:brightness(1.16);box-shadow:0 0 0 1px var(--atlas-gate),0 0 34px color-mix(in srgb,var(--atlas-gate) 42%,transparent)}
}
@keyframes fs-signal-ring{
  0%{opacity:.72;transform:scale(.985)}
  75%,100%{opacity:0;transform:scale(1.035)}
}

/* Low-energy scan field: visual activity only, never fabricated evidence. */
.storage-stage::after{
  content:"";position:absolute;left:0;right:0;top:-18%;height:18%;z-index:1;pointer-events:none;
  background:linear-gradient(180deg,transparent,
    color-mix(in srgb,var(--atlas-signal) 5%,transparent) 48%,
    color-mix(in srgb,var(--atlas-signal) 24%,transparent) 50%,
    color-mix(in srgb,var(--atlas-signal) 5%,transparent) 52%,transparent);
  opacity:.62;animation:fs-scan-sweep 5200ms linear infinite;
}
@keyframes fs-scan-sweep{to{transform:translateY(660%)}}

/* Semantic camera levels visibly alter depth, not only the HUD label. */
.storage-substrate{
  transform-origin:50% 50%;
  transition:transform 700ms cubic-bezier(.16,1,.3,1),opacity 320ms ease-out,filter 420ms ease-out;
}
.storage-stage[data-camera-level="BANK"] .storage-substrate{transform:scale(1.025);opacity:.24;}
.storage-stage[data-camera-level="FABRIC"] .storage-substrate{transform:scale(1.055);opacity:.30;}
.storage-stage[data-camera-level="CELL"] .storage-substrate{
  transform:scale(1.10);opacity:.38;
  filter:drop-shadow(0 0 14px color-mix(in srgb,var(--atlas-signal) 22%,transparent));
}
.storage-stage[data-camera-level="CHAMBER"] .storage-substrate{
  transform:scale(1.16);opacity:.46;
  filter:drop-shadow(0 0 20px color-mix(in srgb,var(--atlas-signal) 28%,transparent));
}

/* CELL/CHAMBER are cinema states: the evidence field takes the viewport. */
@media (min-width:1180px){
  .workspace[data-camera-level="CELL"],
  .workspace[data-camera-level="CHAMBER"]{
    grid-template-columns:0 minmax(0,1fr) 0;
    transition:grid-template-columns 560ms cubic-bezier(.16,1,.3,1);
  }
  .workspace[data-camera-level="CELL"] .navigator-pane,
  .workspace[data-camera-level="CHAMBER"] .navigator-pane{
    opacity:0;visibility:hidden;pointer-events:none;overflow:hidden;
    transform:translateX(-2.5rem);
  }
  .workspace[data-camera-level="CELL"] .inspector-pane,
  .workspace[data-camera-level="CHAMBER"] .inspector-pane{
    opacity:0;visibility:hidden;pointer-events:none;overflow:hidden;
    transform:translateX(2.5rem);
  }
  .workspace[data-camera-level="CHAMBER"][data-decision-open="true"]{
    grid-template-columns:0 minmax(0,1fr) minmax(320px,390px);
  }
  .workspace[data-camera-level="CHAMBER"][data-decision-open="true"] .inspector-pane{
    opacity:1;visibility:visible;pointer-events:auto;overflow:auto;transform:none;
  }
}

/* Fine-pointer contextual reticle; coarse/reduced-motion users retain native cursor. */
.atlas-reticle{
  position:fixed;left:0;top:0;z-index:9999;width:52px;height:52px;display:none;
  pointer-events:none;transform:translate3d(-100px,-100px,0);will-change:transform;
  color:var(--atlas-signal);mix-blend-mode:screen;
}
.atlas-reticle .reticle-core{
  position:absolute;left:50%;top:50%;width:4px;height:4px;border-radius:50%;
  background:currentColor;transform:translate(-50%,-50%);
  box-shadow:0 0 12px currentColor;
}
.reticle-bracket{position:absolute;width:12px;height:12px;border-color:currentColor;opacity:.9;}
.reticle-bracket-nw{left:4px;top:4px;border-left:1px solid;border-top:1px solid}
.reticle-bracket-ne{right:4px;top:4px;border-right:1px solid;border-top:1px solid}
.reticle-bracket-sw{left:4px;bottom:4px;border-left:1px solid;border-bottom:1px solid}
.reticle-bracket-se{right:4px;bottom:4px;border-right:1px solid;border-bottom:1px solid}
.reticle-label{
  position:absolute;left:50%;top:calc(100% + 4px);transform:translateX(-50%);
  padding:.2rem .32rem;border:1px solid currentColor;
  background:color-mix(in srgb,var(--fs-bg-shell) 88%,transparent);white-space:nowrap;
  color:currentColor;font:900 .55rem/1 var(--fs-font-mono);letter-spacing:.09em;
}
.atlas-reticle[data-cursor-mode="dive"]{color:var(--atlas-signal);}
.atlas-reticle[data-cursor-mode="focus"]{color:var(--fs-focus);}
.atlas-reticle[data-cursor-mode="resolve"]{color:var(--atlas-gate);}
.atlas-reticle[data-cursor-mode="blocked"]{color:var(--atlas-danger);}
.atlas-reticle.is-active{filter:drop-shadow(0 0 7px currentColor);}
@media (pointer:fine) and (prefers-reduced-motion:no-preference){
  .storage-stage,.storage-stage button,.storage-stage .map-node,.storage-stage .sector-card{
    cursor:none!important;
  }
  .atlas-reticle.is-visible{display:block;}
}

@media (max-width:1179px){
  .decision-compass{
    width:min(40rem,calc(100% - 9rem));min-width:0;grid-template-columns:1fr;
  }
  .decision-compass-status>span:last-child{display:none;}
}
@media (max-width:799px){
  .atlas-home-beacon{top:.65rem;left:.65rem;}
  .atlas-back-hint{top:.75rem;right:.65rem;}
  .decision-compass{
    top:4.35rem;left:.65rem;right:.65rem;width:auto;transform:none;padding:.45rem;
  }
  .decision-compass-status{display:none;}
  .decision-guide-step{padding:.35rem .4rem;}
  .decision-guide-step>span:last-child{display:none;}
}
@media (prefers-reduced-motion:reduce){
  .storage-stage::after{animation:none;opacity:.18;transform:translateY(280%);}
  .signal-primary,.signal-primary::before,.atlas-reticle{animation:none!important;}
  .storage-substrate{transition:none;}
}
@media (forced-colors:active){
  .decision-compass,.atlas-home-beacon,.decision-guide-step{
    background:Canvas;color:CanvasText;border-color:CanvasText;backdrop-filter:none;
  }
  .decision-guide-step.is-active{outline:3px solid Highlight;box-shadow:none;}
  .signal-primary{outline:3px solid Highlight;box-shadow:none;animation:none;}
  .atlas-reticle{display:none!important;}
}
"""


def render_cinematic_experience_script() -> str:
    """Bind visual guidance to existing DOM and canonical semantic actions."""

    return r"""
<script>
(() => {
  const stage = document.getElementById('storage-stage');
  const workspace = document.getElementById('workspace');
  const compass = document.getElementById('decision-compass');
  const compassNow = document.getElementById('decision-compass-now');
  const compassNext = document.getElementById('decision-compass-next');
  const reticle = document.getElementById('atlas-reticle');
  const reticleLabel = document.getElementById('atlas-reticle-label');
  if (!stage || !workspace || !compass) return;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(pointer: fine)');
  const guideSteps = () => Array.from(compass.querySelectorAll('[data-guide-step]'));

  const currentGate = () => {
    const signal = document.querySelector('.focus-host .signal-primary strong');
    if (signal && signal.textContent) return signal.textContent.trim();
    const lead = document.querySelector('#inspector-body .gate-lead');
    if (lead && lead.textContent) {
      return lead.textContent.replace(/^First unresolved gate:\s*/i, '').trim();
    }
    return '';
  };

  const guideState = () => {
    const level = workspace.dataset.cameraLevel || 'HOME';
    if (workspace.dataset.decisionOpen === 'true') return 'DECIDE';
    if (level === 'CHAMBER') return 'RESOLVE';
    if (level === 'CELL') return 'FOCUS';
    return 'MAP';
  };

  const guideCopy = (state) => {
    if (state === 'FOCUS') return ['FOCUS THE EVIDENCE', 'Fit the exact selection, then open its Chamber.'];
    if (state === 'RESOLVE') {
      const gate = currentGate();
      return ['RESOLVE THE GATE', gate ? 'Next: ' + gate : 'Follow the first unresolved evidence gate.'];
    }
    if (state === 'DECIDE') return ['DECISION CONTEXT', 'Review evidence; authorization remains a separate human gate.'];
    return ['MAP THE PRESSURE', 'Choose a dominant sector or search for exact evidence.'];
  };

  const setGuideState = () => {
    const active = guideState();
    const order = ['MAP', 'FOCUS', 'RESOLVE', 'DECIDE'];
    const activeIndex = order.indexOf(active);
    guideSteps().forEach((step) => {
      const key = step.getAttribute('data-guide-step');
      const index = order.indexOf(key);
      step.classList.toggle('is-active', key === active);
      step.classList.toggle('is-complete', index >= 0 && index < activeIndex);
    });
    const copy = guideCopy(active);
    if (compassNow) compassNow.textContent = copy[0];
    if (compassNext) compassNext.textContent = copy[1];
  };

  const cursorModeFor = (target) => {
    if (!(target instanceof Element)) return ['explore', 'EXPLORE'];
    if (target.closest('.signal-hard-stop,.state-edge-state-protected')) return ['blocked', 'BLOCKED'];
    if (target.closest('.signal-primary,.gate-lead')) return ['resolve', 'RESOLVE'];
    if (target.closest('.sector-card')) return ['dive', 'DIVE'];
    if (target.closest('.map-node')) return ['focus', 'FOCUS'];
    if (target.closest('.focus-chamber')) return ['resolve', 'INSPECT'];
    return ['explore', 'EXPLORE'];
  };

  const moveReticle = (event) => {
    if (!reticle || !fine.matches || reduced.matches) return;
    const mode = cursorModeFor(event.target);
    reticle.dataset.cursorMode = mode[0];
    if (reticleLabel) reticleLabel.textContent = mode[1];
    reticle.classList.add('is-visible', 'is-active');
    reticle.style.transform =
      'translate3d(' + (event.clientX - 26) + 'px,' + (event.clientY - 26) + 'px,0)';
  };

  stage.addEventListener('pointerenter', moveReticle);
  stage.addEventListener('pointermove', moveReticle);
  stage.addEventListener('pointerleave', () => {
    if (reticle) reticle.classList.remove('is-visible', 'is-active');
  });

  const observer = new MutationObserver(setGuideState);
  observer.observe(workspace, {
    attributes: true,
    attributeFilter: ['data-camera-level', 'data-decision-open', 'data-scene']
  });

  document.addEventListener('filesteward:selection', () => {
    window.requestAnimationFrame(setGuideState);
  });
  document.addEventListener('click', () => window.requestAnimationFrame(setGuideState));
  document.addEventListener('keydown', () => window.requestAnimationFrame(setGuideState));

  setGuideState();
})();
</script>
"""
