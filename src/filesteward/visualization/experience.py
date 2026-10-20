"""High-salience cinematic experience layer for Memory Atlas v3.

This layer is presentation-only. It projects existing camera / selection /
decision state into stronger spatial affordances. It never infers evidence,
changes authorization, or creates a second state machine.
"""

from __future__ import annotations

from filesteward.visualization.context_geometry import context_placement_javascript
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.scene_surface import path_step_previews

__all__ = [
    "render_cinematic_experience_css",
    "render_cinematic_experience_markup",
    "render_cinematic_experience_script",
]


def render_cinematic_experience_markup() -> str:
    """Persistent Home, contextual cursor, and state-driven decision guide."""

    steps: list[str] = []
    for index, preview in enumerate(path_step_previews(), start=1):
        active = " is-active" if preview.step_id == "MAP" else ""
        current = ' aria-current="step"' if preview.step_id == "MAP" else ""
        steps.append(
            f'<li class="decision-guide-step{active}" tabindex="0" '
            f'data-guide-step="{escape_attr(preview.step_id)}" '
            f'data-target-kind="NAVIGATION" '
            f'data-action="{escape_attr(preview.cue_label.replace(" ", "_"))}" '
            f'data-actionability="OPERABLE" '
            f'data-consequence="{escape_attr(preview.consequence)}" '
            f'data-cursor-mode="{escape_attr(preview.cursor_mode)}" '
            f'data-cue-label="{escape_attr(preview.cue_label)}" '
            f'data-cue-explain="{escape_attr(preview.explanation + " Prerequisite: " + preview.prerequisites)}" '
            f'aria-label="{escape_attr(preview.title + ": " + preview.explanation)}"{current}>'
            f'<span class="guide-index">{index:02d}</span>'
            f"<strong>{escape_text(preview.title)}</strong>"
            f"<span>{escape_text(preview.summary)}</span>"
            f"</li>"
        )

    return f"""
<div class="atlas-experience-layer">
  <div class="atlas-back-hint" aria-hidden="true">
    <kbd>Esc</kbd><span>BACK</span>
  </div>

  <section class="decision-compass"
           id="decision-compass"
           data-docked="negspace"
           aria-label="Decision path"
           aria-live="polite">
    <div class="decision-compass-status" id="decision-compass-drag" data-drag-handle="true"
         aria-grabbed="false" data-drag-hint="Drag Decision Path into negative space">
      <span class="decision-compass-kicker">DECISION PATH · drag</span>
      <strong id="decision-compass-now" class="fs-type-scene">MAP THE PRESSURE</strong>
      <span id="decision-compass-next" class="fs-type-meta">Choose a dominant sector or search for exact evidence.</span>
    </div>
    <ol class="decision-compass-steps">
      {"".join(steps)}
    </ol>
  </section>
</div>

<div class="atlas-reticle atlas-cursor-portal"
     id="atlas-reticle"
     data-cursor-mode="idle"
     data-actionability="UNAVAILABLE"
     data-portal="body"
     aria-hidden="true">
  <span class="reticle-bracket reticle-bracket-nw"></span>
  <span class="reticle-bracket reticle-bracket-ne"></span>
  <span class="reticle-bracket reticle-bracket-sw"></span>
  <span class="reticle-bracket reticle-bracket-se"></span>
  <span class="reticle-core"></span>
  <span class="reticle-label fs-type-scene" id="atlas-reticle-label"></span>
</div>

<div class="atlas-cartouche atlas-cursor-portal"
     id="atlas-cartouche"
     role="tooltip"
     data-portal="body"
     hidden
     aria-hidden="true">
  <strong id="atlas-cartouche-verb" class="fs-type-scene"></strong>
  <span id="atlas-cartouche-explain" class="fs-type-body">Point at Atlas evidence or controls.</span>
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
.atlas-back-hint kbd{
  padding:.2rem .36rem;border:1px solid var(--fs-border-default);border-radius:3px;
  background:var(--fs-bg-surface-3);color:var(--fs-text-secondary);
  font:700 .67rem/1 var(--fs-font-mono);
}
.atlas-back-hint{
  position:absolute;right:.65rem;bottom:.65rem;z-index:9;
  display:flex;align-items:center;gap:.4rem;color:var(--fs-text-muted);
  font:800 .68rem/1 var(--fs-font-mono);letter-spacing:.07em;
  opacity:.72;pointer-events:none;
}

/* Default dock: lower-left negative space — not over sector cards. */
.decision-compass{
  pointer-events:auto;
  position:absolute;left:.75rem;right:auto;top:auto;bottom:.75rem;transform:none;z-index:11;
  width:min(34rem,calc(100% - 1.5rem));min-width:16rem;
  display:grid;grid-template-columns:minmax(9rem,.7fr) minmax(14rem,1.3fr);gap:.55rem;
  padding:.45rem .55rem;
  border:1px solid color-mix(in srgb,var(--atlas-signal) 30%,var(--fs-border-subtle));
  border-radius:5px;
  background:linear-gradient(180deg,
    color-mix(in srgb,var(--fs-bg-shell) 90%,transparent),
    color-mix(in srgb,var(--fs-bg-surface-2) 78%,transparent));
  box-shadow:0 10px 40px rgba(0,0,0,.18),
             inset 0 1px 0 color-mix(in srgb,white 6%,transparent);
  backdrop-filter:blur(10px);
  touch-action:none;
}
.decision-compass[data-docked="free"]{z-index:16;}
.decision-compass.is-dragging{
  opacity:.94;box-shadow:0 0 0 1px var(--atlas-signal),0 18px 48px rgba(0,0,0,.35);
}
.decision-compass-status[data-drag-handle="true"]{cursor:grab;user-select:none;}
.decision-compass.is-dragging .decision-compass-status{cursor:grabbing;}
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
  grid-template-columns:repeat(3,minmax(0,1fr));gap:3px;align-items:stretch;
}
.decision-guide-step{
  pointer-events:auto;cursor:pointer;
  position:relative;display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;
  gap:.08rem .35rem;align-content:center;padding:.4rem .5rem;min-width:0;
  border:1px solid var(--fs-border-subtle);
  background:color-mix(in srgb,var(--fs-bg-surface-2) 82%,transparent);
  opacity:.46;
  transition:opacity 180ms ease-out,border-color 180ms ease-out,
             box-shadow 220ms ease-out,transform 220ms cubic-bezier(.16,1,.3,1);
}
.decision-guide-step:hover,.decision-guide-step:focus-visible,.decision-guide-step.is-hover{
  opacity:1;outline:none;transform:translateY(-2px);
  border-color:color-mix(in srgb,var(--atlas-signal) 70%,var(--fs-border-default));
  box-shadow:0 0 0 1px color-mix(in srgb,var(--atlas-signal) 45%,transparent),
             0 0 28px color-mix(in srgb,var(--atlas-signal) 34%,transparent),
             0 8px 18px rgba(0,0,0,.22);
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
/* Portal to document.body — escapes storage-stage isolation + HUD stacking. */
.atlas-cursor-portal,.atlas-reticle,.atlas-cartouche{
  position:fixed!important;z-index:2147483000!important;pointer-events:none!important;
}
.atlas-reticle{
  left:0;top:0;width:56px;height:56px;display:none;
  transform:translate3d(-100px,-100px,0);will-change:transform;
  color:var(--atlas-signal);
}
.atlas-reticle .reticle-core{
  position:absolute;left:50%;top:50%;width:10px;height:10px;border-radius:50%;
  border:2px solid currentColor;background:color-mix(in srgb,var(--fs-bg-canvas) 70%,transparent);
  transform:translate(-50%,-50%);
  box-shadow:0 0 0 1px color-mix(in srgb,var(--fs-bg-canvas) 85%,transparent),0 0 14px currentColor;
}
.reticle-bracket{position:absolute;width:14px;height:14px;border-color:currentColor;opacity:.95;}
.reticle-bracket-nw{left:3px;top:3px;border-left:2px solid;border-top:2px solid}
.reticle-bracket-ne{right:3px;top:3px;border-right:2px solid;border-top:2px solid}
.reticle-bracket-sw{left:3px;bottom:3px;border-left:2px solid;border-bottom:2px solid}
.reticle-bracket-se{right:3px;bottom:3px;border-right:2px solid;border-bottom:2px solid}
.reticle-label{
  position:absolute;left:50%;top:calc(100% + 4px);transform:translateX(-50%);
  padding:.22rem .4rem;border:1px solid currentColor;border-radius:3px;
  background:color-mix(in srgb,var(--fs-bg-shell) 92%,transparent);white-space:nowrap;
  color:currentColor;font:900 .58rem/1 var(--fs-font-mono);letter-spacing:.09em;
  box-shadow:0 0 10px color-mix(in srgb,currentColor 35%,transparent);
}
.atlas-reticle[data-cursor-mode="dive"],.atlas-reticle[data-cursor-mode="approve"]{color:var(--atlas-signal);}
.atlas-reticle[data-cursor-mode="focus"],.atlas-reticle[data-cursor-mode="return"]{color:var(--fs-focus);}
.atlas-reticle[data-cursor-mode="resolve"]{color:var(--atlas-gate);}
.atlas-reticle[data-cursor-mode="blocked"],.atlas-reticle[data-cursor-mode="locked"],
.atlas-reticle[data-actionability="BLOCKED"]{color:var(--atlas-danger);}
.atlas-reticle.is-active{filter:drop-shadow(0 0 8px currentColor);}
.atlas-reticle.has-panel .reticle-label{display:none;}
.atlas-cartouche{
  max-width:18rem;padding:.55rem .7rem;
  border:1px solid color-mix(in srgb,var(--atlas-signal) 50%,var(--fs-border-default));
  border-radius:4px;background:color-mix(in srgb,var(--fs-bg-shell) 94%,transparent);
  color:var(--fs-text-primary);box-shadow:0 10px 28px color-mix(in srgb,var(--fs-bg-canvas) 55%,transparent);
}
.atlas-cartouche[hidden]{display:none!important;}
.atlas-cartouche[data-presentation="compact"] span{display:none;}
.atlas-cartouche strong{display:block;font:800 .72rem/1.2 var(--fs-font-mono);letter-spacing:.06em;margin-bottom:.25rem;}
.atlas-cartouche span{display:block;font:600 .74rem/1.35 var(--fs-font-mono);color:var(--fs-text-secondary);}
.storage-stage.returning-home .camera-plane,
.storage-stage.returning-home .sector-overview{
  animation:fs-home-zoom 720ms cubic-bezier(.16,1,.3,1) both;
}
.storage-stage.path-enacting{
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--atlas-signal) 45%,transparent);
}
html,body,.app,.app *{user-select:none;-webkit-user-select:none;}
.app input,.app textarea,.app [contenteditable="true"]{user-select:text;-webkit-user-select:text;}
html::selection,body::selection,.app::selection,.app *::selection{
  background:color-mix(in srgb,var(--fs-accent) 42%,transparent);
  color:var(--fs-text-primary);
}
.atlas-range-marquee{
  position:fixed;z-index:2147482990;pointer-events:none;
  border:1px solid var(--fs-accent);
  background:color-mix(in srgb,var(--fs-accent) 16%,transparent);
  box-shadow:0 0 18px color-mix(in srgb,var(--fs-accent) 28%,transparent);
}
@keyframes fs-home-zoom{
  0%{transform:scale(1.1);filter:blur(2px);opacity:.86}
  100%{transform:none;filter:none;opacity:1}
}
@media (pointer:fine) and (prefers-reduced-motion:no-preference){
  .storage-stage.has-context-reticle,.storage-stage.has-context-reticle *{cursor:none!important;}
  .atlas-reticle.is-visible{display:block;}
}

@media (max-width:1179px){
  .decision-compass{
    width:min(32rem,calc(100% - 1.2rem));min-width:0;grid-template-columns:1fr;
  }
  .decision-compass-status>span:last-child{display:none;}
}
@media (max-width:799px){
  .atlas-back-hint{right:.55rem;bottom:.55rem;}
  .decision-compass{
    left:.55rem;right:.55rem;bottom:.55rem;width:auto;padding:.45rem;
  }
  .decision-guide-step{padding:.35rem .4rem;}
  .decision-guide-step>span:last-child{display:none;}
}
@media (prefers-reduced-motion:reduce){
  .storage-stage::after{animation:none;opacity:.18;transform:translateY(280%);}
  .signal-primary,.signal-primary::before,.atlas-reticle{animation:none!important;}
  .storage-substrate,.storage-stage.returning-home .camera-plane{transition:none;animation:none!important;}
}
@media (forced-colors:active){
  .decision-compass,.decision-guide-step{
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
  const cartouche = document.getElementById('atlas-cartouche');
  const cartoucheVerb = document.getElementById('atlas-cartouche-verb');
  const cartoucheExplain = document.getElementById('atlas-cartouche-explain');
  const cameraCurrent = document.getElementById('atlas-camera-current');
  const commandHistory = document.getElementById('atlas-command-history');
  if (!stage || !workspace || !compass) return;

  /* Escape storage-stage isolation:isolate and atlas-hud z-index stacking. */
  [reticle, cartouche].forEach((el) => {
    if (el && el.parentElement !== document.body) document.body.appendChild(el);
  });


  /* CONTEXT_GEOMETRY */

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(pointer: fine)');
  const forcedColors = window.matchMedia('(forced-colors: active)');
  const guideSteps = () => Array.from(compass.querySelectorAll('[data-guide-step]'));
  const recentCommands = [];
  let pathLockUntil = 0;

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
    if (Date.now() < pathLockUntil && workspace.dataset.pathPreview) {
      return workspace.dataset.pathPreview;
    }
    const scene = workspace.dataset.openDecisionScene;
    if (scene && scene !== 'MAP' && scene !== 'CLOSED') return scene;
    const level = workspace.dataset.cameraLevel || 'HOME';
    if (workspace.dataset.decisionOpen === 'true') return 'APPROVAL';
    if (level === 'CHAMBER') return 'GATE';
    if (level === 'CELL') return 'FOCUS';
    return 'MAP';
  };

  const guideCopy = (state) => {
    if (state === 'FOCUS') return ['FOCUS THE EVIDENCE', 'Fit the exact selection, then open its gate.'];
    if (state === 'GATE') {
      const gate = currentGate();
      return ['OPEN THE GATE', gate ? 'Active: ' + gate : 'Activate UNKNOWN / HUMAN_REVIEW evidence status.'];
    }
    if (state === 'RESOLVE') {
      const gate = currentGate();
      return ['RESOLVE THE GATE', gate ? 'Next: ' + gate : 'Only legal operator intents are available.'];
    }
    if (state === 'APPROVAL') return ['APPROVAL SCOPE', 'Exact run, digest, and item IDs required before staging.'];
    if (state === 'STAGED') return ['STAGED', 'QUARANTINE REQUIRED — NO BYTES REMOVED'];
    return ['MAP THE PRESSURE', 'Choose a dominant sector or search for exact evidence.'];
  };

  const setGuideState = () => {
    const active = guideState();
    const order = ['MAP', 'FOCUS', 'GATE', 'RESOLVE', 'APPROVAL', 'STAGED'];
    const activeIndex = order.indexOf(active);
    guideSteps().forEach((step) => {
      const key = step.getAttribute('data-guide-step');
      const index = order.indexOf(key);
      step.classList.toggle('is-active', key === active);
      step.classList.toggle('is-complete', index >= 0 && index < activeIndex);
      if (key === active) {
        step.setAttribute('aria-current', 'step');
        step.setAttribute('data-active', 'true');
      } else {
        step.removeAttribute('aria-current');
        step.removeAttribute('data-active');
      }
      if (activeIndex > 0 && index === activeIndex - 1) {
        step.setAttribute('data-last-completed', 'true');
      } else {
        step.removeAttribute('data-last-completed');
      }
    });
    const copy = guideCopy(active);
    if (compassNow) compassNow.textContent = copy[0];
    if (compassNext) compassNext.textContent = copy[1];
  };

  const cueFrom = (target) => {
    if (!(target instanceof Element)) {
      return { mode: 'idle', label: '', actionability: 'UNAVAILABLE', explain: 'No operable action.', impact: '', destination: '', fingerprint: '' };
    }
    const host = target.closest(
      '.decision-guide-step,[data-action],[data-cursor-mode],[data-cue-label],[data-scene-entry],'
      + '.map-node,.status-orb,.sector-card,.signal-primary,.signal-hard-stop,.gate-lead,'
      + '.atlas-hud button,.atlas-hud [data-action],.chamber-gate,.chamber-actions button,'
      + '[data-atlas-action],.metric-scene,.next-action,.pane-scene-btn,'
      + '.brand-home,.class-legend-item,#atlas-classification-legend,.decision-chamber,'
      + '.decision-chamber button,.inspector,[data-decision-intent],.chamber-gate,.chamber-confirm'
    );
    if (host) {
      if (host.matches(':disabled,[aria-disabled="true"]')) return { mode: 'idle', label: '', actionability: 'UNAVAILABLE', explain: 'No action available.' };
      const mode = host.getAttribute('data-cursor-mode')
        || (host.classList.contains('decision-guide-step') ? 'resolve' : null)
        || (host.classList.contains('signal-hard-stop') ? 'blocked' : null)
        || (host.classList.contains('signal-primary') || host.classList.contains('gate-lead') || host.classList.contains('chamber-gate') ? 'resolve' : null)
        || (host.classList.contains('sector-card') ? 'dive' : null)
        || (host.classList.contains('map-node') ? 'focus' : null);
      if (!mode) {
        return { mode: 'idle', label: '', actionability: 'UNAVAILABLE', explain: 'No registered action.', impact: '', destination: '', fingerprint: '' };
      }
      const label = host.getAttribute('data-cue-label')
        || host.getAttribute('data-action')
        || (host.classList.contains('decision-guide-step')
          ? ('PREVIEW ' + (host.getAttribute('data-guide-step') || 'PATH'))
          : null)
        || (mode === 'blocked' ? 'INSPECT BLOCK' : mode === 'dive' ? 'DIVE IN' : mode === 'resolve' ? 'RESOLVE' : mode === 'focus' ? 'SELECT' : '');
      if (String(label).toUpperCase() === 'EXPLORE' && host.getAttribute('data-impact-kind') !== 'EXPLORE') {
        return { mode: 'idle', label: '', actionability: 'UNAVAILABLE', explain: 'EXPLORE is reserved.', impact: '', destination: '', fingerprint: '' };
      }
      if (!label) return { mode: 'idle', label: '', actionability: 'UNAVAILABLE' };
      return {
        host,
        mode,
        label: String(label).split('_').join(' '),
        actionability: host.getAttribute('data-actionability') || 'OPERABLE',
        explain: host.getAttribute('data-cue-explain') || host.getAttribute('aria-label') || label,
        impact: host.getAttribute('data-impact-kind') || '',
        destination: host.getAttribute('data-destination-scene') || '',
        fingerprint: host.getAttribute('data-context-fingerprint') || ''
      };
    }
    return { mode: 'idle', label: '', actionability: 'UNAVAILABLE', explain: 'No operable action on empty canvas.', impact: '', destination: '', fingerprint: '' };
  };

  let pointerModality = 'pointer';
  let lastPointer = { x: 0, y: 0 };
  let hideReticleUntilPointer = false;
  let cueFingerprint = '';
  let lastPointerType = 'mouse';

  let contextTarget = null;
  let dismissedTarget = null;
  let describedHost = null;
  let geometryFrame = 0;
  const clearContext = () => {
    cancelAnimationFrame(geometryFrame);
    stage.classList.remove('has-context-reticle');
    if (reticle) reticle.classList.remove('is-visible', 'is-active', 'has-panel');
    if (cartouche) { cartouche.hidden = true; cartouche.setAttribute('aria-hidden', 'true'); }
    if (describedHost) {
      const ids = (describedHost.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== 'atlas-cartouche');
      if (ids.length) describedHost.setAttribute('aria-describedby', ids.join(' '));
      else describedHost.removeAttribute('aria-describedby');
      describedHost = null;
    }
  };
  /* Protect hovered and selected subjects, related representations and scene evidence. */
  const cartoucheObstacles = (host) => {
    const elements = new Set(document.querySelectorAll([
      'header.shell', '.metrics', '.atlas-hud', '.scene-toolbar', '.phone-command-bar',
      '.atlas-classification-legend', '#atlas-next-actions', '.atlas-scene-panel:not([hidden])', '.decision-compass',
      '.chamber-subject', '#selection-summary', '#chamber-gate-line', '.script-impact', '#chamber-evidence-trace',
      '#chamber-approval', '#chamber-result', '#chamber-error', '#chamber-next-actions',
      '.chamber-actions', '.inspector-pane', '.filter-chip', '#storage-search', '.sector-card', '.map-node.selected',
      '.app button', '.app a', '.app input', '.app select', '.app textarea',
      '.app summary', '.app [role="button"]', '.app [tabindex="0"]', 'footer'
    ].join(',')));
    if (host) {
      elements.add(host.closest('.sector-card,.map-node,.nav-row,.chamber-gate') || host);
      const node = host.closest('[data-node-id]');
      const ids = new Set((host.getAttribute('data-context-related') || '').split(/\s+/).filter(Boolean));
      if (node) ids.add(node.dataset.nodeId);
      document.querySelectorAll('[data-node-id]').forEach(el => {
        if (ids.has(el.dataset.nodeId) || el.dataset.selected === 'true') elements.add(el);
      });
    }
    return [...elements].filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
      .map(el => el.getBoundingClientRect()).filter(r => r.width > 1 && r.height > 1 && r.bottom > 0 && r.top < innerHeight);
  };
  const placeCartoucheAway = (x, y, host) => {
    const anchor = pointerModality === 'keyboard' && host ? host.getBoundingClientRect() : {left:x, right:x, top:y, bottom:y};
    return placeContextPanel({anchor, width:cartouche.offsetWidth, height:cartouche.offsetHeight,
      viewport:{width:innerWidth, height:innerHeight}, obstacles:cartoucheObstacles(host)});
  };
  const watchContextGeometry = (host) => {
    const signature = () => {
      const cue = cueFrom(host);
      const semantics = [cue.label, cue.explain, cue.actionability, cue.fingerprint].join('|');
      return semantics + cartoucheObstacles(host).map(r =>
        [r.left, r.top, r.right, r.bottom].map(n => Math.round(n * 2)).join(',')).join('|');
    };
    const previous = signature();
    const check = () => {
      if (cartouche.hidden) return;
      if (!host || !host.isConnected || signature() !== previous) { clearContext(); return; }
      geometryFrame = requestAnimationFrame(check);
    };
    geometryFrame = requestAnimationFrame(check);
  };

  const paintCue = (cue, x, y, showCartouche, moveReticlePos) => {
    clearContext();
    contextTarget = cue.host || null;
    if (dismissedTarget && dismissedTarget === contextTarget) return;
    dismissedTarget = null;
    const fp = cue.fingerprint || (cue.mode + '|' + cue.label + '|' + (cue.impact || ''));
    if (cueFingerprint && fp && cueFingerprint !== fp) {
      if (reticle) reticle.classList.remove('is-visible', 'is-active');
    }
    cueFingerprint = fp;
    if (!cue.mode || cue.actionability === 'UNAVAILABLE') {
      if (reticle) reticle.classList.remove('is-visible', 'is-active');
      if (cartouche) {
        cartouche.hidden = true;
        cartouche.setAttribute('aria-hidden', 'true');
      }
      return;
    }
    if (reticle && fine.matches && !reduced.matches && !forcedColors.matches && moveReticlePos !== false) {
      if (hideReticleUntilPointer) {
        reticle.classList.remove('is-visible', 'is-active');
      } else {
        reticle.dataset.cursorMode = cue.mode;
        reticle.dataset.actionability = cue.actionability;
        if (reticleLabel) reticleLabel.textContent = cue.label;
        reticle.classList.add('is-visible', 'is-active');
        stage.classList.add('has-context-reticle');
        reticle.style.transform = 'translate3d(' + (x - 28) + 'px,' + (y - 28) + 'px,0)';
      }
    }
    if (cartouche && showCartouche) {
      if (cartoucheVerb) cartoucheVerb.textContent = cue.label;
      if (cartoucheExplain) cartoucheExplain.textContent = cue.explain;
      cartouche.hidden = false;
      cartouche.setAttribute('aria-hidden', 'false');
      cartouche.dataset.presentation = 'full';
      let pos = placeCartoucheAway(x, y, cue.host);
      if (!pos) { cartouche.dataset.presentation = 'compact'; pos = placeCartoucheAway(x, y, cue.host); }
      if (!pos) {
        clearContext();
        cartouche.dataset.presentation = 'suppressed'; return;
      }
      if (cue.host && cartouche.dataset.presentation === 'full') {
        describedHost = cue.host;
        const ids = new Set((cue.host.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
        ids.add('atlas-cartouche'); cue.host.setAttribute('aria-describedby', [...ids].join(' '));
      }
      if (reticle) reticle.classList.add('has-panel');
      cartouche.style.left = pos.left + 'px';
      cartouche.style.top = pos.top + 'px';
      watchContextGeometry(cue.host);
    } else if (cartouche) {
      cartouche.hidden = true;
      cartouche.setAttribute('aria-hidden', 'true');
    }
  };

  const moveReticle = (event) => {
    lastPointerType = event.pointerType || 'mouse';
    pointerModality = 'pointer';
    hideReticleUntilPointer = false;
    if (lastPointer.x !== event.clientX || lastPointer.y !== event.clientY) dismissedTarget = null;
    lastPointer = { x: event.clientX, y: event.clientY };
    if (event.pointerType === 'touch') { clearContext(); return; }
    if (!stage.contains(event.target)) {
      clearContext();
      if (reticle) reticle.classList.remove('is-visible', 'is-active');
      if (cartouche) { cartouche.hidden = true; cartouche.setAttribute('aria-hidden','true'); }
      return;
    }
    const cue = cueFrom(event.target);
    paintCue(cue, event.clientX, event.clientY, true, true);
  };

  const syncCameraTrace = () => {
    const level = workspace.dataset.cameraLevel || 'HOME';
    if (cameraCurrent) {
      cameraCurrent.textContent = level;
      cameraCurrent.setAttribute('aria-current', 'true');
    }
    if (!commandHistory) return;
    const items = recentCommands.slice(0, 3);
    commandHistory.innerHTML = items.map((item, index) => {
      const recency = index === 0 ? 'LAST' : 'RECENT';
      return '<li data-recency="' + recency + '"><span>' + item + '</span></li>';
    }).join('') || '<li data-recency="IDLE"><span>ATLAS HOME</span></li>';
    document.querySelectorAll('.atlas-hud button[data-action]').forEach((btn) => {
      const label = btn.getAttribute('data-cue-label') || btn.textContent.trim();
      const idx = items.indexOf(label);
      btn.setAttribute('data-recency', idx === 0 ? 'LAST' : idx > 0 ? 'RECENT' : 'IDLE');
    });
  };

  const rememberCommand = (label) => {
    if (!label) return;
    if (recentCommands[0] === label) return;
    recentCommands.unshift(label);
    while (recentCommands.length > 3) recentCommands.pop();
    syncCameraTrace();
  };

  const openScenePanel = (label, explain) => {
    const panel = document.getElementById('atlas-scene-panel');
    const title = document.getElementById('atlas-scene-panel-title');
    const body = document.getElementById('atlas-scene-panel-body');
    if (panel) panel.hidden = false;
    if (title) title.textContent = label;
    if (body) body.textContent = explain;
  };

  const hideScenePanel = () => {
    const panel = document.getElementById('atlas-scene-panel');
    if (panel) {
      panel.hidden = true;
      panel.removeAttribute('data-dashboard-open');
    }
    workspace.dataset.dashboardOpen = 'false';
  };

  const resetHighlights = () => {
    pathLockUntil = 0;
    workspace.dataset.pathPreview = 'MAP';
    workspace.dataset.openDecisionScene = 'MAP';
    stage.classList.remove('path-enacting');
    /* Explicit Atlas Home clears dashboards; metric/legend handlers reopen after home(). */
    hideScenePanel();
    if (window.getSelection) window.getSelection().removeAllRanges();
    const marquee = document.getElementById('atlas-range-marquee');
    if (marquee) marquee.hidden = true;
    document.querySelectorAll('.decision-guide-step').forEach((step) => {
      const on = step.getAttribute('data-guide-step') === 'MAP';
      step.classList.toggle('is-active', on);
      step.classList.remove('is-complete', 'is-hover');
      if (on) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
      step.removeAttribute('data-last-completed');
    });
    setGuideState();
  };

  const ensureDecisionOpen = (atlas) => {
    if (!atlas || typeof atlas.toggle_decision !== 'function') return;
    if (workspace.dataset.decisionOpen !== 'true') atlas.toggle_decision();
  };

  const enactPathStep = (step) => {
    const key = step.getAttribute('data-guide-step') || 'MAP';
    const explain = step.getAttribute('data-cue-explain') || '';
    const label = step.getAttribute('data-cue-label') || key;
    const atlas = window.FileStewardAtlas;
    hideReticleUntilPointer = true;
    if (reticle) reticle.classList.remove('is-visible', 'is-active');
    openScenePanel(label, explain);
    workspace.dataset.pathPreview = key;
    workspace.dataset.openDecisionScene = key;
    pathLockUntil = Date.now() + 4200;
    stage.classList.add('path-enacting');
    window.setTimeout(() => stage.classList.remove('path-enacting'), 700);

    if (key === 'MAP') {
      workspace.dataset.decisionOpen = 'false';
      if (atlas && typeof atlas.home === 'function') atlas.home();
    } else if (key === 'FOCUS') {
      if (atlas && typeof atlas.fit_selected === 'function') atlas.fit_selected();
    } else if (key === 'GATE') {
      if (atlas && typeof atlas.open_selected === 'function') atlas.open_selected();
      ensureDecisionOpen(atlas);
    } else if (key === 'RESOLVE') {
      if (atlas && typeof atlas.open_selected === 'function') atlas.open_selected();
      ensureDecisionOpen(atlas);
    } else if (key === 'APPROVAL') {
      if (atlas && typeof atlas.open_selected === 'function') atlas.open_selected();
      ensureDecisionOpen(atlas);
    } else if (key === 'STAGED') {
      ensureDecisionOpen(atlas);
      workspace.dataset.stagedCinematic = 'preview';
    }

    document.dispatchEvent(new CustomEvent('filesteward:path-step', {
      detail: { step: key, label: label, explain: explain }
    }));
    rememberCommand(label);
    setGuideState();
  };

  /* Drag Decision Path into negative space. */
  const dragHandle = document.getElementById('decision-compass-drag') || compass;
  let drag = null;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const placeCompass = (left, top) => {
    const bounds = stage.getBoundingClientRect();
    const width = compass.offsetWidth || 320;
    const height = compass.offsetHeight || 120;
    const x = clamp(left - bounds.left, 8, Math.max(8, bounds.width - width - 8));
    const y = clamp(top - bounds.top, 8, Math.max(8, bounds.height - height - 8));
    compass.style.left = x + 'px';
    compass.style.top = y + 'px';
    compass.style.right = 'auto';
    compass.style.bottom = 'auto';
    compass.style.transform = 'none';
    compass.dataset.docked = 'free';
    try {
      sessionStorage.setItem('fs.decisionPath.pos', JSON.stringify({ x: x, y: y }));
    } catch (_err) { /* ignore */ }
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem('fs.decisionPath.pos') || 'null');
    if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
      const bounds = stage.getBoundingClientRect();
      placeCompass(bounds.left + saved.x, bounds.top + saved.y);
    }
  } catch (_err) { /* ignore */ }
  dragHandle.addEventListener('pointerdown', (event) => {
    if (event.target instanceof Element && event.target.closest('.decision-guide-step')) return;
    drag = {
      id: event.pointerId,
      ox: event.clientX - compass.getBoundingClientRect().left,
      oy: event.clientY - compass.getBoundingClientRect().top
    };
    compass.classList.add('is-dragging');
    dragHandle.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  dragHandle.addEventListener('pointermove', (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    placeCompass(event.clientX - drag.ox, event.clientY - drag.oy);
  });
  const endDrag = (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    compass.classList.remove('is-dragging');
  };
  dragHandle.addEventListener('pointerup', endDrag);
  dragHandle.addEventListener('pointercancel', endDrag);

  const app = document.querySelector('.app') || document.body;
  let marquee = document.getElementById('atlas-range-marquee');
  if (!marquee) {
    marquee = document.createElement('div');
    marquee.id = 'atlas-range-marquee';
    marquee.className = 'atlas-range-marquee';
    marquee.hidden = true;
    marquee.setAttribute('aria-hidden', 'true');
    document.body.appendChild(marquee);
  }
  let rangeDrag = null;
  const RANGE_THRESHOLD = 8;
  const inChrome = (target) => target instanceof Element && !!target.closest(
    'input,textarea,button,a,select,[contenteditable="true"],.decision-compass,.decision-chamber,'
    + '.atlas-hud,.filters,.navigator-pane,header.shell,.chamber-actions,.next-action'
  );
  const eligibleRangeSurface = (target) => target instanceof Element && !!target.closest(
    '.map-wrap,.map-stage,#storage-stage,.map-node,[data-atlas-surface]'
  );
  document.addEventListener('selectstart', (event) => {
    if (inChrome(event.target)) return;
    event.preventDefault();
  });
  document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || inChrome(event.target)) return;
    if (!eligibleRangeSurface(event.target)) return;
    rangeDrag = { x: event.clientX, y: event.clientY, armed: false };
  });
  document.addEventListener('pointermove', (event) => {
    if (!rangeDrag) return;
    const dx = Math.abs(event.clientX - rangeDrag.x);
    const dy = Math.abs(event.clientY - rangeDrag.y);
    if (!rangeDrag.armed) {
      if (dx < RANGE_THRESHOLD && dy < RANGE_THRESHOLD) return;
      rangeDrag.armed = true;
      marquee.hidden = false;
      marquee.style.left = rangeDrag.x + 'px';
      marquee.style.top = rangeDrag.y + 'px';
      marquee.style.width = '0px';
      marquee.style.height = '0px';
    }
    const x = Math.min(event.clientX, rangeDrag.x);
    const y = Math.min(event.clientY, rangeDrag.y);
    marquee.style.left = x + 'px';
    marquee.style.top = y + 'px';
    marquee.style.width = Math.abs(event.clientX - rangeDrag.x) + 'px';
    marquee.style.height = Math.abs(event.clientY - rangeDrag.y) + 'px';
    paintCue({
      mode: 'focus',
      label: 'FRAME RANGE',
      actionability: 'OPERABLE',
      explain: 'Immersive range mark. Native browser selection is contained.',
      impact: 'FILTER',
      fingerprint: 'range'
    }, event.clientX, event.clientY, true, true);
  });
  const endRange = () => {
    rangeDrag = null;
    if (marquee) marquee.hidden = true;
  };
  document.addEventListener('pointerup', endRange);
  document.addEventListener('pointercancel', endRange);

  app.addEventListener('pointerenter', moveReticle);
  app.addEventListener('pointermove', moveReticle);
  app.addEventListener('pointerleave', () => {
    clearContext();
    if (reticle) reticle.classList.remove('is-visible', 'is-active');
    if (cartouche) {
      cartouche.hidden = true;
      cartouche.setAttribute('aria-hidden', 'true');
    }
  });

  app.addEventListener('focusin', (event) => {
    if (lastPointerType === 'touch' && pointerModality !== 'keyboard') { clearContext(); return; }
    const cue = cueFrom(event.target);
    const rect = event.target instanceof Element ? event.target.getBoundingClientRect() : null;
    if (!rect) return;
    /* Pointer modality owns the reticle — never teleport to element center. */
    if (pointerModality === 'pointer') {
      hideReticleUntilPointer = true;
      if (reticle) reticle.classList.remove('is-visible', 'is-active');
      paintCue(cue, lastPointer.x, lastPointer.y, true, false);
      return;
    }
    pointerModality = 'keyboard';
    hideReticleUntilPointer = true;
    if (reticle) reticle.classList.remove('is-visible', 'is-active');
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    paintCue(cue, x, y, true, false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { dismissedTarget = contextTarget; clearContext(); }
    if (event.key === 'Tab' || event.key.startsWith('Arrow')) pointerModality = 'keyboard';
  }, true);
  app.addEventListener('focusout', clearContext);
  // A settled camera/card transform may make a local seat usable again.
  // Re-project from the current hit target, never from an old cached cue.
  app.addEventListener('transitionend', (event) => {
    if (!['transform', 'grid-template-columns'].includes(event.propertyName)
        || lastPointerType === 'touch' || !contextTarget) return;
    const target = pointerModality === 'keyboard' ? document.activeElement
      : document.elementFromPoint(lastPointer.x, lastPointer.y);
    const cue = cueFrom(target);
    if (cue.host !== contextTarget) return;
    paintCue(cue, lastPointer.x, lastPointer.y, true, pointerModality !== 'keyboard');
  });
  window.addEventListener('resize', clearContext);
  document.addEventListener('scroll', clearContext, true);
  reduced.addEventListener('change', clearContext);
  fine.addEventListener('change', clearContext);
  forcedColors.addEventListener('change', clearContext);
  document.addEventListener('visibilitychange', clearContext);
  if (window.ResizeObserver) {
    const geometryObserver = new ResizeObserver(clearContext);
    [stage, compass, document.getElementById('decision-chamber')].filter(Boolean)
      .forEach(el => geometryObserver.observe(el));
  }

  guideSteps().forEach((step) => {
    step.addEventListener('pointerenter', (event) => {
      step.classList.add('is-hover');
      moveReticle(event);
    });
    step.addEventListener('pointerleave', () => step.classList.remove('is-hover'));
    step.addEventListener('click', (event) => {
      event.stopPropagation();
      enactPathStep(step);
    });
    step.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        enactPathStep(step);
      }
    });
  });

  document.addEventListener('click', (event) => {
    const host = event.target instanceof Element
      ? event.target.closest('.atlas-hud button,[data-atlas-action],.status-orb,.brand-home')
      : null;
    if (host) {
      rememberCommand(host.getAttribute('data-cue-label') || host.textContent.trim());
      if (host.classList.contains('brand-home') || host.getAttribute('data-atlas-action') === 'home') {
        resetHighlights();
        openScenePanel('ATLAS HOME', 'Zooming camera to Atlas Home overview. Path highlight, chamber, and native selection reset.');
        window.setTimeout(hideScenePanel, 1600);
      }
    }
    window.requestAnimationFrame(setGuideState);
  });

  let lastObservedScene = workspace.dataset.openDecisionScene || '';
  const observer = new MutationObserver(() => {
    clearContext();
    const sceneNow = workspace.dataset.openDecisionScene || '';
    if (sceneNow !== lastObservedScene) {
      lastObservedScene = sceneNow;
      clearContext();
      hideReticleUntilPointer = true;
      if (reticle) reticle.classList.remove('is-visible', 'is-active');
    }
    setGuideState();
    syncCameraTrace();
  });
  observer.observe(workspace, {
    attributes: true,
    attributeFilter: ['data-camera-level', 'data-decision-open', 'data-scene', 'data-open-decision-scene', 'data-path-preview']
  });

  document.addEventListener('filesteward:selection', () => {
    clearContext();
    window.requestAnimationFrame(() => {
      setGuideState();
      syncCameraTrace();
    });
  });
  const chamber = document.getElementById('decision-chamber');
  if (chamber) new MutationObserver(clearContext).observe(chamber, {childList:true, subtree:true,
    attributes:true, characterData:true,
    attributeFilter:['data-script-scene', 'data-open-scene', 'style', 'data-docked', 'data-context-fingerprint',
      'data-actionability', 'data-cue-label', 'data-cue-explain', 'disabled', 'hidden']});
  document.addEventListener('filesteward:atlas-home', () => { clearContext(); resetHighlights(); });

  setGuideState();
  syncCameraTrace();
})();
</script>
""".replace("/* CONTEXT_GEOMETRY */", context_placement_javascript())
