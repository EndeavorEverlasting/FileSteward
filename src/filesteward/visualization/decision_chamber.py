"""Memory Atlas v4 Decision Chamber presentation wiring.

Owns operable evidence-status surfaces, Prompt-Kit-style orientation state,
legal intent controls, approval confirmation, and the staged quarantine
cinematic. Product judgment remains in decision_flow / approval / bridge.
"""

from __future__ import annotations

__all__ = [
    "render_decision_chamber_css",
    "render_decision_chamber_markup",
    "render_decision_chamber_script",
]


def render_decision_chamber_markup() -> str:
    return r"""
<aside class="decision-chamber"
       id="decision-chamber"
       data-open-scene="MAP"
       hidden
       aria-label="Decision Chamber">
  <div class="chamber-chrome">
    <div class="chamber-orientation" aria-live="polite">
      <span class="chamber-kicker">DECISION CHAMBER</span>
      <strong id="chamber-scene-label">MAP</strong>
      <span id="chamber-last-transition">No transition yet</span>
    </div>
    <div class="chamber-subject">
      <span class="chamber-kicker">SELECTED EVIDENCE</span>
      <strong id="chamber-node-name">—</strong>
      <span class="mono" id="chamber-node-path"></span>
      <div class="chamber-evidence-row">
        <span>Evidence: <strong id="chamber-evidence">—</strong></span>
        <span>Decision: <strong id="chamber-decision">NONE</strong></span>
        <span>Auth: <strong id="chamber-auth">UNAPPROVED</strong></span>
      </div>
    </div>
  </div>

  <ol class="chamber-gate-line" id="chamber-gate-line" aria-label="Active decision gates"></ol>

  <p class="chamber-brief fs-type-body" id="chamber-brief" aria-live="polite">
    Closed — choose a Decision Path step to open a distinct chamber scene.
  </p>

  <section class="chamber-next-actions" id="chamber-next-actions" aria-label="Scene next actions" hidden>
    <div class="next-actions-head">
      <strong>NEXT ACTIONS</strong>
      <span id="chamber-blocker-line">Legal intents for this evidence state</span>
    </div>
    <div class="next-actions-row" id="chamber-next-actions-row" role="group"></div>
  </section>

  <div class="chamber-actions" id="chamber-actions" role="group" aria-label="Legal operator intents"></div>

  <section class="chamber-approval" id="chamber-approval" hidden>
    <h3>APPROVAL SCOPE</h3>
    <dl>
      <dt>Node</dt><dd id="approval-node">—</dd>
      <dt>Path</dt><dd class="mono" id="approval-path">—</dd>
      <dt>Reclaim evidence</dt><dd id="approval-reclaim">—</dd>
      <dt>Cleanup-plan digest</dt><dd class="mono" id="approval-digest">—</dd>
      <dt>Proposed action</dt><dd>QUARANTINE</dd>
      <dt>Authorization</dt><dd id="approval-auth">UNAPPROVED</dd>
    </dl>
    <button type="button" class="chamber-confirm" id="chamber-confirm-staging">
      Confirm staging
    </button>
  </section>

  <section class="quarantine-rail" id="quarantine-rail" aria-label="Quarantine rail" hidden>
    <div class="rail-label">QUARANTINE RAIL</div>
    <div class="rail-slot" id="quarantine-slot"></div>
  </section>

  <p class="chamber-staged-banner" id="chamber-staged-banner" hidden>
    STAGED — QUARANTINE REQUIRED — NO BYTES REMOVED
  </p>
</aside>
"""


def render_decision_chamber_css() -> str:
    return r"""
.decision-chamber{
  pointer-events:auto;position:absolute;left:50%;right:auto;bottom:1rem;transform:translateX(-50%);
  z-index:16;width:min(40rem,calc(100% - 2rem));
  display:grid;gap:.7rem;padding:.85rem 1rem;
  border:1px solid color-mix(in srgb,var(--fs-accent) 45%,var(--fs-border-default));
  border-radius:6px;background:color-mix(in srgb,var(--fs-bg-shell) 94%,transparent);
  color:var(--fs-text-primary);backdrop-filter:blur(10px);
  box-shadow:0 0 0 1px color-mix(in srgb,var(--fs-accent) 18%,transparent),
             0 18px 40px color-mix(in srgb,var(--fs-bg-canvas) 55%,transparent);
}
.chamber-next-actions{padding:.55rem;border:1px solid var(--fs-border-subtle);border-radius:4px;background:color-mix(in srgb,var(--fs-accent) 8%,var(--fs-bg-surface-1));}
.chamber-next-actions[hidden]{display:none!important;}
.chamber-next-actions .next-action[data-consequence="READ_ONLY"]{cursor:help;}
.decision-chamber[data-open-scene="GATE"]{border-color:var(--fs-state-review-edge);}
.decision-chamber[data-open-scene="RESOLVE"]{border-color:var(--fs-accent);}
.decision-chamber[data-open-scene="APPROVAL"],.decision-chamber[data-open-scene="STAGED"]{
  border-color:color-mix(in srgb,var(--fs-accent) 80%,white);
}
.chamber-brief{margin:0;padding:.45rem .55rem;border:1px solid var(--fs-border-subtle);border-radius:4px;}
.chamber-gate-line[hidden],.chamber-actions[hidden]{display:none!important;}
.decision-chamber[hidden]{display:none!important;}
.chamber-chrome{display:grid;grid-template-columns:minmax(10rem,.8fr) minmax(16rem,1.4fr);gap:.8rem;}
.chamber-kicker{display:block;font:800 .66rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-text-muted);}
.chamber-orientation strong,.chamber-subject strong{display:block;margin:.25rem 0;font-size:1.05rem;font-family:var(--fs-font-mono);letter-spacing:.04em;}
.chamber-evidence-row{display:flex;flex-wrap:wrap;gap:.7rem;font:700 .72rem/1.3 var(--fs-font-mono);}
.chamber-approval dd,.chamber-subject .mono{font-family:var(--fs-font-mono)!important;}
.chamber-gate-line{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.45rem;}
.chamber-gate{
  min-width:7rem;padding:.45rem .55rem;border:1px solid var(--fs-border-default);
  border-radius:4px;background:var(--fs-bg-surface-2);opacity:.62;
  font:700 .7rem/1.25 var(--fs-font-mono);
}
.chamber-gate[data-active="true"]{
  opacity:1;border-color:var(--fs-accent);background:color-mix(in srgb,var(--fs-bg-selected) 80%,transparent);
  box-shadow:0 0 0 1px color-mix(in srgb,var(--fs-accent) 40%,transparent),
             0 0 22px color-mix(in srgb,var(--fs-accent) 28%,transparent);
  transform:translateY(-1px);
}
.chamber-gate[data-last-completed="true"]{
  opacity:.9;border-color:color-mix(in srgb,var(--fs-state-keep-edge) 70%,var(--fs-border-default));
  background:color-mix(in srgb,var(--fs-state-keep) 18%,var(--fs-bg-surface-2));
}
.chamber-actions{display:flex;flex-wrap:wrap;gap:.45rem;}
.chamber-actions button,.chamber-confirm{
  min-height:44px;padding:.55rem .8rem;border-radius:4px;cursor:pointer;
  border:1px solid color-mix(in srgb,var(--fs-accent) 55%,var(--fs-border-default));
  background:var(--fs-bg-surface-3);color:var(--fs-text-primary);
  font:800 .72rem/1 var(--fs-font-mono);letter-spacing:.04em;
}
.chamber-actions button:focus-visible,.chamber-confirm:focus-visible,
button.evidence-state-action:focus-visible{outline:3px solid var(--fs-focus);outline-offset:2px;}
.chamber-approval{
  border-top:1px solid var(--fs-border-subtle);padding-top:.65rem;
}
.chamber-approval dl{display:grid;grid-template-columns:10rem minmax(0,1fr);gap:.25rem .7rem;margin:0 0 .7rem;}
.chamber-approval dt{color:var(--fs-text-muted);font:700 .7rem/1.4 var(--fs-font-mono);}
.chamber-approval dd{margin:0;font:600 .82rem/1.35 var(--fs-font-sans);}
.quarantine-rail{
  min-height:4.5rem;border:1px dashed color-mix(in srgb,var(--fs-accent) 60%,transparent);
  border-radius:4px;padding:.55rem;background:color-mix(in srgb,var(--fs-bg-canvas) 70%,transparent);
}
.rail-label{font:800 .68rem/1 var(--fs-font-mono);letter-spacing:.08em;color:var(--fs-accent);}
.rail-slot{
  margin-top:.45rem;min-height:2.6rem;padding:.55rem .7rem;border-radius:4px;
  border:2px solid var(--fs-accent);background:color-mix(in srgb,var(--fs-bg-selected) 85%,transparent);
}
.chamber-staged-banner{
  margin:0;padding:.7rem .8rem;border-radius:4px;text-align:center;
  border:1px solid color-mix(in srgb,var(--fs-accent) 55%,transparent);
  background:color-mix(in srgb,var(--fs-accent) 16%,var(--fs-bg-shell));
  font:800 .8rem/1.3 var(--fs-font-mono);letter-spacing:.05em;
}
.workspace[data-open-decision-scene="GATE"] .navigator-pane,
.workspace[data-open-decision-scene="RESOLVE"] .navigator-pane,
.workspace[data-open-decision-scene="APPROVAL"] .navigator-pane,
.workspace[data-open-decision-scene="STAGED"] .navigator-pane,
.workspace[data-open-decision-scene="GATE"] .metrics,
.workspace[data-open-decision-scene="RESOLVE"] .metrics,
.workspace[data-open-decision-scene="APPROVAL"] .metrics,
.workspace[data-open-decision-scene="STAGED"] .metrics,
.workspace[data-open-decision-scene="GATE"] .inspector,
.workspace[data-open-decision-scene="RESOLVE"] .inspector,
.workspace[data-open-decision-scene="APPROVAL"] .inspector,
.workspace[data-open-decision-scene="STAGED"] .inspector{
  opacity:.28;filter:saturate(.7);
}
.workspace[data-open-decision-scene="GATE"] .inspector,
.workspace[data-open-decision-scene="RESOLVE"] .inspector,
.workspace[data-open-decision-scene="APPROVAL"] .inspector,
.workspace[data-open-decision-scene="STAGED"] .inspector{
  pointer-events:none;
}
.workspace[data-open-decision-scene="STAGED"] .map-node[data-selected="true"],
.workspace[data-open-decision-scene="STAGED"] .nav-row[data-selected="true"]{
  box-shadow:0 0 0 2px var(--fs-accent),0 0 28px color-mix(in srgb,var(--fs-accent) 35%,transparent);
}
.workspace[data-open-decision-scene="STAGED"] .map-node[data-ghost="true"]{
  opacity:.28;filter:grayscale(.35);
}
.workspace[data-staged-cinematic="true"] .decision-chamber{
  animation:fs-staged-settle 720ms ease-out both;
}
@keyframes fs-staged-settle{
  0%{transform:translateX(-50%) translateY(8px);opacity:.2}
  100%{transform:translateX(-50%) translateY(0);opacity:1}
}
button.evidence-state-action,.evidence-state-action[role="button"],.signal-chip[data-open-decision="true"]{
  display:inline-flex;align-items:center;gap:.35rem;min-height:32px;padding:.2rem .45rem;
  border:1px solid color-mix(in srgb,var(--fs-accent) 40%,var(--fs-border-default));
  border-radius:3px;background:color-mix(in srgb,var(--fs-bg-surface-2) 80%,transparent);
  color:inherit;font:inherit;cursor:pointer;
}
button.evidence-state-action .state-marker,.evidence-state-action .state-marker{pointer-events:none;}
.signal-chip[data-open-decision="true"]{display:grid;}
@media (max-width:799px){
  .decision-chamber{bottom:4.4rem;width:calc(100% - 1.2rem);padding:.7rem;}
  .chamber-chrome{grid-template-columns:1fr;}
}
@media (prefers-reduced-motion:reduce){
  .workspace[data-staged-cinematic="true"] .decision-chamber,
  .chamber-gate[data-active="true"]{animation:none;transform:none;}
}
@media (forced-colors:active){
  .decision-chamber,.chamber-gate,.chamber-actions button,.chamber-confirm,button.evidence-state-action{
    background:Canvas;color:CanvasText;border-color:CanvasText;box-shadow:none;backdrop-filter:none;
  }
  .chamber-gate[data-active="true"]{outline:3px solid Highlight;}
}
"""


def render_decision_chamber_script() -> str:
    return r"""
<script>
(() => {
  const workspace = document.getElementById('workspace');
  const chamber = document.getElementById('decision-chamber');
  const bridgeEl = document.getElementById('decision-bridge-runtime');
  if (!workspace || !chamber) return;

  const bridge = bridgeEl ? JSON.parse(bridgeEl.textContent || '{}') : null;
  const state = {
    selectedNodeId: null,
    activeGateId: null,
    openDecisionScene: 'MAP',
    lastScene: null,
    lastTransition: null,
    evidence: null,
    decisionLabel: 'NONE',
    auth: 'UNAPPROVED',
    allowedIntents: [],
    node: null,
    digest: bridge && bridge.cleanupPlanSha256 ? bridge.cleanupPlanSha256 : null
  };

  const sceneLabel = document.getElementById('chamber-scene-label');
  const lastTransitionEl = document.getElementById('chamber-last-transition');
  const chamberBrief = document.getElementById('chamber-brief');
  const nodeName = document.getElementById('chamber-node-name');
  const nodePath = document.getElementById('chamber-node-path');
  const evidenceEl = document.getElementById('chamber-evidence');
  const decisionEl = document.getElementById('chamber-decision');
  const authEl = document.getElementById('chamber-auth');
  const gateLine = document.getElementById('chamber-gate-line');
  const actions = document.getElementById('chamber-actions');
  const approval = document.getElementById('chamber-approval');
  const stagedBanner = document.getElementById('chamber-staged-banner');
  const rail = document.getElementById('quarantine-rail');
  const railSlot = document.getElementById('quarantine-slot');
  const confirmBtn = document.getElementById('chamber-confirm-staging');

  const selectedId = () => {
    const row = document.querySelector('[data-node-id][data-selected="true"], .nav-row.selected, .map-node.selected');
    return row ? row.getAttribute('data-node-id') : state.selectedNodeId;
  };

  const paintSelectionMarkers = (id) => {
    document.querySelectorAll('[data-node-id]').forEach((el) => {
      const on = el.getAttribute('data-node-id') === id;
      el.classList.toggle('selected', on);
      if (on) {
        el.setAttribute('data-selected', 'true');
        el.setAttribute('aria-selected', 'true');
      } else {
        el.removeAttribute('data-selected');
        el.removeAttribute('aria-selected');
      }
    });
  };

  const gateStepsFromDom = () => {
    const steps = [];
    document.querySelectorAll('#inspector-body .trace > li, .focus-host .trace > li').forEach((li) => {
      const name = (li.querySelector('.gate-name') || {}).textContent || '';
      const status = (li.querySelector('.gate-status') || {}).textContent || '';
      const id = (name || status || 'gate').toLowerCase().replace(/\s+/g, '-');
      steps.push({
        gate_id: id,
        name: name.trim(),
        status: status.trim(),
        unresolved: li.classList.contains('unresolved') || li.getAttribute('aria-current') === 'step'
      });
    });
    return steps;
  };

  const renderGates = (activeGateId, lastGateId) => {
    if (!gateLine) return;
    const steps = gateStepsFromDom();
    if (!steps.length && activeGateId) {
      steps.push({ gate_id: activeGateId, name: activeGateId, status: 'ACTIVE', unresolved: true });
    }
    gateLine.innerHTML = steps.map((step) => {
      const active = step.gate_id === activeGateId || (step.unresolved && !activeGateId);
      const last = !active && lastGateId && step.gate_id === lastGateId;
      return '<li class="chamber-gate"'
        + (active ? ' data-active="true" aria-current="step"' : '')
        + (last ? ' data-last-completed="true"' : '')
        + ' data-gate-id="' + step.gate_id.replace(/"/g, '') + '">'
        + '<div>' + (step.name || step.gate_id) + '</div>'
        + '<div>' + (step.status || '') + '</div></li>';
    }).join('');
    document.querySelectorAll('#inspector-body .trace > li, .focus-host .trace > li').forEach((li) => {
      const name = ((li.querySelector('.gate-name') || {}).textContent || '').toLowerCase().replace(/\s+/g, '-');
      const active = name && state.activeGateId && name === state.activeGateId;
      const last = name && state.lastTransition && name === String(state.lastTransition).toLowerCase();
      if (active) {
        li.setAttribute('data-active', 'true');
        li.setAttribute('aria-current', 'step');
        li.removeAttribute('data-last-completed');
      } else {
        li.removeAttribute('data-active');
        if (li.getAttribute('aria-current') === 'step' && !li.classList.contains('unresolved')) {
          li.removeAttribute('aria-current');
        }
        if (last) li.setAttribute('data-last-completed', 'true');
        else li.removeAttribute('data-last-completed');
      }
    });
  };

  const intentLabel = (intent) => intent.replace(/_/g, ' ');

  const sceneBrief = (scene) => {
    if (scene === 'GATE') return 'GATE — inspect the first unresolved evidence gate. No mutation. UNKNOWN/HUMAN_REVIEW stay locked from reclaim.';
    if (scene === 'RESOLVE') return 'RESOLVE — only decision_flow.allowed_intents() are operable. Delete/remove intent shows LOCKED unless RECLAIM_PROVEN.';
    if (scene === 'APPROVAL') return 'APPROVAL — authorize exact quarantine scope. Permanent deletion is not implemented. Bytes stay until a later verified quarantine apply.';
    if (scene === 'STAGED') return 'STAGED — quarantine receipt recorded. NO BYTES REMOVED. Real C: apply remains an operator gate outside this report.';
    if (scene === 'FOCUS') return 'FOCUS — evidence is framed. Open GATE to inspect, RESOLVE to choose a legal intent.';
    if (scene === 'MAP') return 'MAP — chamber closed. Camera at Atlas Home.';
    return 'Chamber closed.';
  };

  const stageRemovalLockedExplain = () => {
    const upper = ((state.evidence || '') + ' ' + ((state.node && state.node.reclaim_basis) || '')).toUpperCase();
    if (upper.indexOf('UNKNOWN') >= 0) {
      return 'STAGE REMOVAL LOCKED — disposition UNKNOWN. Rescan or complete evidence before quarantine. Permanent deletion is not implemented. NO BYTES REMOVED.';
    }
    if (upper.indexOf('HUMAN') >= 0) {
      return 'STAGE REMOVAL LOCKED — HUMAN_REVIEW requires operator contract judgment first. Permanent deletion is not implemented.';
    }
    if (upper.indexOf('PROTECTED') >= 0 || upper.indexOf('KEEP') >= 0) {
      return 'STAGE REMOVAL LOCKED — evidence is keep/protected. No reclaim path from this state.';
    }
    return 'STAGE REMOVAL LOCKED — quarantine requires RECLAIM_PROVEN + UNAPPROVED. Permanent deletion is not implemented.';
  };

  const renderSceneNextActions = () => {
    const mount = document.getElementById('chamber-next-actions');
    const row = document.getElementById('chamber-next-actions-row');
    const blocker = document.getElementById('chamber-blocker-line');
    if (!mount || !row) return;
    const scene = state.openDecisionScene;
    const show = scene === 'GATE' || scene === 'RESOLVE' || scene === 'APPROVAL';
    mount.hidden = !show;
    if (!show) {
      row.innerHTML = '';
      return;
    }
    row.innerHTML = '';
    const canStage = state.allowedIntents.indexOf('APPROVE_QUARANTINE') >= 0;
    if (blocker) {
      blocker.textContent = canStage
        ? 'Delete/remove intent opens quarantine APPROVAL — NO BYTES REMOVED'
        : stageRemovalLockedExplain();
    }
    const addAction = (opts) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'next-action';
      btn.setAttribute('data-next-action', opts.id);
      btn.setAttribute('data-consequence', opts.consequence || 'RECORD_INTENT');
      btn.setAttribute('data-cue-label', opts.label);
      btn.setAttribute('data-cue-explain', opts.explain);
      btn.setAttribute('data-cursor-mode', opts.mode || 'resolve');
      btn.setAttribute('data-actionability', opts.locked ? 'BLOCKED' : 'OPERABLE');
      btn.innerHTML = '<strong>' + opts.label + '</strong><span>' + opts.explain + '</span>';
      if (opts.locked) {
        btn.addEventListener('click', () => {
          state.lastTransition = 'stage_removal_locked_' + String(scene).toLowerCase();
          if (chamberBrief) chamberBrief.textContent = opts.explain;
          applyScene();
        });
      } else if (opts.intent) {
        btn.setAttribute('data-decision-intent', opts.intent);
        btn.addEventListener('click', () => postDecision(opts.intent));
      } else if (opts.openApproval) {
        btn.setAttribute('data-open-approval', 'true');
        btn.addEventListener('click', () => {
          state.openDecisionScene = 'APPROVAL';
          applyScene();
        });
      }
      row.appendChild(btn);
    };
    if (scene === 'GATE') {
      addAction({
        id: 'advance_resolve',
        label: 'ADVANCE TO RESOLVE',
        explain: 'Open legal intents for this evidence. Delete/remove stays locked unless RECLAIM_PROVEN.',
        mode: 'resolve',
        openApproval: false
      });
      const advance = row.querySelector('[data-next-action="advance_resolve"]');
      if (advance) {
        advance.onclick = () => {
          state.openDecisionScene = 'RESOLVE';
          state.lastTransition = 'gate_to_resolve';
          applyScene();
        };
      }
    }
    if (scene === 'RESOLVE' || scene === 'APPROVAL') {
      state.allowedIntents.forEach((intent) => {
        if (intent === 'APPROVE_QUARANTINE') {
          addAction({
            id: 'open_approval',
            label: 'STAGE REMOVAL PATH',
            explain: 'Operator delete/remove intent opens exact-plan approval. Terminal truth: quarantine staging — NO BYTES REMOVED.',
            mode: 'approve',
            openApproval: true
          });
          return;
        }
        addAction({
          id: intent.toLowerCase(),
          label: intentLabel(intent),
          explain: 'Legal operator intent. Records intent only; does not delete files.',
          mode: intent === 'KEEP' ? 'explore' : 'resolve',
          intent: intent
        });
      });
    }
    if (!canStage) {
      addAction({
        id: 'stage_removal_locked',
        label: 'STAGE REMOVAL PATH — LOCKED',
        explain: stageRemovalLockedExplain(),
        mode: 'blocked',
        locked: true,
        consequence: 'READ_ONLY'
      });
    }
  };

  const renderActions = () => {
    if (!actions) return;
    const scene = state.openDecisionScene;
    actions.innerHTML = '';
    const showIntents = scene === 'RESOLVE' || scene === 'APPROVAL';
    if (showIntents) {
      state.allowedIntents.forEach((intent) => {
        if (intent === 'APPROVE_QUARANTINE') return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = intentLabel(intent);
        btn.setAttribute('data-decision-intent', intent);
        btn.setAttribute('data-cursor-mode', intent === 'KEEP' ? 'explore' : 'resolve');
        btn.setAttribute('data-cue-label', intentLabel(intent));
        btn.setAttribute('data-cue-explain', 'Legal operator intent from decision_flow.allowed_intents(). Toggle records intent; it does not delete files.');
        btn.setAttribute('data-actionability', 'OPERABLE');
        btn.addEventListener('click', () => postDecision(intent));
        actions.appendChild(btn);
      });
    }
    actions.hidden = true; /* Scene next-actions owns the operable surface */
    const showApproval = scene === 'APPROVAL'
      && state.allowedIntents.indexOf('APPROVE_QUARANTINE') >= 0;
    if (approval) approval.hidden = !showApproval;
    if (showApproval) {
      const set = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value || '—'; };
      set('approval-node', state.node && state.node.display_name);
      set('approval-path', state.node && state.node.path);
      set('approval-reclaim', (state.node && state.node.reclaim_basis) || 'RECLAIM_PROVEN');
      set('approval-digest', state.digest || 'synthetic-offline');
      set('approval-auth', state.auth);
    }
    if (gateLine) gateLine.hidden = !(scene === 'GATE' || scene === 'RESOLVE');
    renderSceneNextActions();
  };

  const applyScene = () => {
    workspace.dataset.openDecisionScene = state.openDecisionScene;
    chamber.setAttribute('data-open-scene', state.openDecisionScene);
    const scene = state.openDecisionScene;
    const open = scene === 'GATE' || scene === 'RESOLVE' || scene === 'APPROVAL' || scene === 'STAGED' || scene === 'FOCUS';
    chamber.hidden = !open;
    if (sceneLabel) sceneLabel.textContent = scene;
    if (chamberBrief) chamberBrief.textContent = sceneBrief(scene);
    if (lastTransitionEl) {
      lastTransitionEl.textContent = state.lastTransition
        ? ('Last completed: ' + String(state.lastTransition).replace(/_/g, ' '))
        : 'No transition yet';
    }
    if (nodeName) nodeName.textContent = (state.node && state.node.display_name) || state.selectedNodeId || '—';
    if (nodePath) nodePath.textContent = (state.node && state.node.path) || '';
    if (evidenceEl) evidenceEl.textContent = state.evidence || '—';
    if (decisionEl) decisionEl.textContent = state.decisionLabel || 'NONE';
    if (authEl) authEl.textContent = state.auth || 'UNAPPROVED';
    const staged = state.openDecisionScene === 'STAGED';
    if (stagedBanner) stagedBanner.hidden = !staged;
    if (rail) rail.hidden = !staged;
    if (staged && railSlot) {
      railSlot.textContent = (state.node && state.node.display_name) || state.selectedNodeId || 'staged candidate';
      workspace.dataset.stagedCinematic = 'true';
      const selected = document.querySelector('[data-node-id][data-selected="true"]');
      if (selected) {
        const ghost = selected.cloneNode(true);
        ghost.setAttribute('data-ghost', 'true');
        ghost.removeAttribute('data-selected');
        ghost.removeAttribute('aria-selected');
        ghost.tabIndex = -1;
        if (selected.parentElement && !selected.parentElement.querySelector('[data-ghost="true"]')) {
          selected.parentElement.appendChild(ghost);
        }
      }
    }
    renderGates(state.activeGateId, state.lastScene);
    renderActions();
    const compass = document.getElementById('decision-compass');
    if (compass) {
      const order = ['MAP','FOCUS','GATE','RESOLVE','APPROVAL','STAGED'];
      const active = state.openDecisionScene;
      const idx = order.indexOf(active);
      compass.querySelectorAll('[data-guide-step]').forEach((step) => {
        const key = step.getAttribute('data-guide-step');
        const i = order.indexOf(key);
        step.classList.toggle('is-active', key === active);
        step.classList.toggle('is-complete', i >= 0 && idx >= 0 && i < idx);
        if (key === active) step.setAttribute('aria-current', 'step');
        else step.removeAttribute('aria-current');
        if (state.lastScene && key === state.lastScene) step.setAttribute('data-last-completed', 'true');
        else step.removeAttribute('data-last-completed');
      });
      const now = document.getElementById('decision-compass-now');
      const next = document.getElementById('decision-compass-next');
      if (now) now.textContent = active;
      if (next) {
        next.textContent = active === 'STAGED'
          ? 'STAGED — QUARANTINE REQUIRED — NO BYTES REMOVED'
          : 'Selected evidence stays anchored while the active gate moves.';
      }
    }
  };

  const absorbState = (payload) => {
    if (!payload) return;
    state.selectedNodeId = payload.selected_node_id || state.selectedNodeId;
    state.activeGateId = payload.active_gate_id || null;
    state.openDecisionScene = payload.open_decision_scene || state.openDecisionScene;
    state.lastScene = payload.last_scene || state.lastScene;
    state.lastTransition = payload.last_transition || state.lastTransition;
    state.evidence = payload.evidence_disposition || state.evidence;
    state.auth = payload.authorization_state || state.auth;
    state.allowedIntents = payload.allowed_intents || [];
    state.node = payload.node || state.node;
    state.digest = payload.cleanup_plan_sha256 || state.digest;
    if (payload.operator_decision && payload.operator_decision.label) {
      state.decisionLabel = payload.operator_decision.label.replace(/^Decision:\s*/i, '');
    } else if (payload.operator_decision && payload.operator_decision.intent) {
      state.decisionLabel = payload.operator_decision.intent.replace(/_/g, ' ') + ' REQUESTED';
    }
    if (payload.approval && payload.approval.authorization_state === 'APPROVED_FOR_ACTION') {
      state.openDecisionScene = 'STAGED';
      state.auth = 'APPROVED_FOR_ACTION';
    }
    if (state.selectedNodeId) paintSelectionMarkers(state.selectedNodeId);
    applyScene();
  };

  const localOpenGate = (id, requestedScene) => {
    state.selectedNodeId = id;
    paintSelectionMarkers(id);
    const evidenceNode = document.querySelector('[data-inspector-for="' + CSS.escape(id) + '"]');
    const stateText = evidenceNode
      ? ((evidenceNode.querySelector('.state') || {}).textContent || '').trim()
      : '';
    state.evidence = stateText.replace(/\[.*?\]\s*/, '') || state.evidence;
    const steps = gateStepsFromDom();
    const first = steps.find((s) => s.unresolved) || steps[0];
    state.activeGateId = first ? first.gate_id : 'observation';
    const upper = (state.evidence || '').toUpperCase();
    if (upper.indexOf('UNKNOWN') >= 0) {
      state.allowedIntents = ['RESCAN', 'KEEP', 'REVIEW_LATER'];
    } else if (upper.indexOf('HUMAN') >= 0) {
      state.allowedIntents = ['DECLARE_REGENERABLE_CONTRACT', 'KEEP', 'REVIEW_LATER'];
    } else if (upper.indexOf('RECLAIM') >= 0) {
      state.allowedIntents = ['APPROVE_QUARANTINE', 'KEEP', 'REVIEW_LATER'];
    } else if (upper.indexOf('KEEP') >= 0 || upper.indexOf('PROTECTED') >= 0) {
      state.allowedIntents = [];
    } else {
      state.allowedIntents = ['KEEP', 'REVIEW_LATER'];
    }
    const scene = requestedScene || 'GATE';
    if (scene === 'APPROVAL' && state.allowedIntents.indexOf('APPROVE_QUARANTINE') < 0) {
      state.openDecisionScene = 'RESOLVE';
      state.lastTransition = 'approval_locked_no_reclaim_authority';
    } else if (scene === 'STAGED' && state.auth !== 'APPROVED_FOR_ACTION') {
      state.openDecisionScene = state.allowedIntents.indexOf('APPROVE_QUARANTINE') >= 0 ? 'APPROVAL' : 'RESOLVE';
      state.lastTransition = 'staging_requires_approval';
    } else {
      state.openDecisionScene = scene;
    }
    state.lastScene = state.lastScene || 'FOCUS';
    state.node = {
      display_name: (document.querySelector('.nav-row.selected .nav-name') || {}).textContent || id,
      path: (document.querySelector('.selection-path') || {}).textContent || '',
      reclaim_basis: upper.indexOf('RECLAIM') >= 0 ? 'RECLAIM_PROVEN' : null
    };
    applyScene();
  };

  const fetchState = async (id, requestedScene) => {
    if (!bridge || !bridge.origin || !bridge.statePath) {
      localOpenGate(id, requestedScene);
      return;
    }
    const url = bridge.origin + bridge.statePath + '?item_id=' + encodeURIComponent(id);
    const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!response.ok) {
      localOpenGate(id, requestedScene);
      return;
    }
    absorbState(await response.json());
    if (requestedScene) {
      state.openDecisionScene = requestedScene;
      applyScene();
    }
  };

  const postDecision = async (intent) => {
    if (!bridge || !bridge.origin) {
      state.decisionLabel = intent.replace(/_/g, ' ') + ' REQUESTED';
      state.lastScene = state.openDecisionScene;
      state.lastTransition = intent.toLowerCase();
      if (intent === 'KEEP' || intent === 'REVIEW_LATER') {
        state.openDecisionScene = 'RESOLVE';
        state.lastTransition = intent.toLowerCase() + '_recorded';
      }
      applyScene();
      return;
    }
    const response = await fetch(bridge.origin + bridge.decisionPath, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [bridge.sessionHeader || 'X-FileSteward-Session']: bridge.sessionToken
      },
      body: JSON.stringify({
        run_id: bridge.runId,
        item_id: state.selectedNodeId,
        intent: intent
      })
    });
    if (!response.ok) return;
    absorbState(await response.json());
  };

  const postApproval = async () => {
    if (!state.selectedNodeId) return;
    if (!bridge || !bridge.origin) {
      if (state.allowedIntents.indexOf('APPROVE_QUARANTINE') < 0) {
        state.lastTransition = 'approval_rejected_no_reclaim_authority';
        state.openDecisionScene = 'RESOLVE';
        applyScene();
        return;
      }
      state.auth = 'APPROVED_FOR_ACTION';
      state.decisionLabel = 'QUARANTINE STAGED';
      state.lastScene = 'APPROVAL';
      state.lastTransition = 'confirm_staging_offline';
      state.openDecisionScene = 'STAGED';
      applyScene();
      return;
    }
    const response = await fetch(bridge.origin + bridge.approvalPath, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [bridge.sessionHeader || 'X-FileSteward-Session']: bridge.sessionToken
      },
      body: JSON.stringify({
        run_id: bridge.runId,
        item_id: state.selectedNodeId,
        cleanup_plan_sha256: bridge.cleanupPlanSha256,
        action: 'QUARANTINE',
        confirm: true
      })
    });
    if (!response.ok) return;
    absorbState(await response.json());
  };

  if (confirmBtn) confirmBtn.addEventListener('click', postApproval);

  const sceneForDispositionLabel = (label) => {
    const upper = String(label || '').toUpperCase();
    if (upper.indexOf('RECLAIM') >= 0) return 'APPROVAL';
    if (upper.indexOf('UNKNOWN') >= 0 || upper.indexOf('HUMAN') >= 0) return 'RESOLVE';
    return 'GATE';
  };

  const openFromEvidenceControl = (event) => {
    const control = event.target instanceof Element
      ? event.target.closest('[data-open-decision],button.evidence-state-action,.map-state,.signal-chip.signal-primary')
      : null;
    if (!control) return;
    const host = control.closest('[data-node-id]') || document.querySelector('[data-node-id].selected');
    const id = control.getAttribute('data-node-id')
      || (host ? host.getAttribute('data-node-id') : null)
      || selectedId();
    if (!id) return;
    event.preventDefault();
    event.stopPropagation();
    state.selectedNodeId = id;
    paintSelectionMarkers(id);
    document.dispatchEvent(new CustomEvent('filesteward:selection', { detail: { id } }));
    const scene = sceneForDispositionLabel(control.getAttribute('data-state-label'));
    fetchState(id, scene);
  };

  document.addEventListener('click', openFromEvidenceControl);
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const control = event.target instanceof Element
      ? event.target.closest('[data-open-decision],button.evidence-state-action,.map-state,.signal-chip.signal-primary')
      : null;
    if (!control) return;
    openFromEvidenceControl(event);
  });

  document.addEventListener('filesteward:selection', (event) => {
    const id = event.detail && event.detail.id;
    if (!id) return;
    state.selectedNodeId = id;
    paintSelectionMarkers(id);
    if (state.openDecisionScene === 'GATE' || state.openDecisionScene === 'RESOLVE' || state.openDecisionScene === 'APPROVAL' || state.openDecisionScene === 'STAGED') {
      fetchState(id, state.openDecisionScene);
    } else {
      state.openDecisionScene = 'FOCUS';
      applyScene();
    }
  });

  document.addEventListener('filesteward:path-step', (event) => {
    const key = event.detail && event.detail.step;
    if (!key) return;
    state.lastScene = state.openDecisionScene;
    state.lastTransition = 'path_step_' + String(key).toLowerCase();
    if (!state.selectedNodeId) state.selectedNodeId = selectedId();
    if (key === 'MAP' || key === 'FOCUS') {
      state.openDecisionScene = key;
      applyScene();
      return;
    }
    if (state.selectedNodeId) {
      fetchState(state.selectedNodeId, key);
      return;
    }
    state.openDecisionScene = key;
    applyScene();
  });

  document.addEventListener('filesteward:atlas-home', () => {
    state.openDecisionScene = 'MAP';
    state.lastTransition = 'atlas_home_reset';
    state.lastScene = null;
    state.selectedNodeId = null;
    paintSelectionMarkers('');
    chamber.hidden = true;
    chamber.setAttribute('data-open-scene', 'MAP');
    document.querySelectorAll('[data-ghost="true"]').forEach((el) => el.remove());
    applyScene();
  });

  // Expose orientation for tests / self-falsification probes.
  window.__filestewardDecisionChamber = state;
})();
</script>
"""
