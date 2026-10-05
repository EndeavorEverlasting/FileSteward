# U1 Operator Comprehension — Call-Stack Design

**Status:** DESIGNED + executable seams wired into report shell
**Module:** `src/filesteward/visualization/scene_surface.py`
**Authority floor:** `decision_flow.allowed_intents()`; permanent deletion forbidden
**Product version:** `0.11.0` (visual-feature after chamber next-actions / delete-blocker / cartouche dodge)

## Operator correction 2026-10-05 (blocker / scenery pass)

- Disposition UNKNOWN must open Decision Chamber with operable intents + locked STAGE REMOVAL explaining the delete blocker.
- Header Next Actions must not encumber Atlas Home; invoke in chamber at GATE/RESOLVE/APPROVAL.
- Cartouche must float into negative space away from inspector/chamber/compass.
- Legend entries glow for the active disposition during traversal.
- Permanent deletion remains forbidden; real C: apply remains an operator gate.

## Operator rejection recovered from live screenshot

The brand/Home-only candidate left these gaps visible:

1. Header/metrics were inert chrome — not scenery entrypoints.
2. Classification legend (contracted) was absent; only status orbs showed.
3. No obvious answer to “how do I change classification?” or “how do I delete?”
4. Decision Path hover always showed EXPLORE (compass had `pointer-events:none`; steps lacked cue attrs).
5. System cursor returned outside the map stage; OS scrollbar mismatched scenery.
6. Pane titles were static labels; `? items` mode taught nothing; footer text did not scroll.

## Alternatives compared

| Candidate | Disposition | Why |
|---|---|---|
| Add a real Delete button that removes bytes | REJECT | Permanent deletion not implemented; safety model forbids |
| Encode classify/delete only inside Decision Chamber JS | REJECT | Offline report still needs comprehension; chamber can stay closed on MAP |
| Pure scene_surface projection + shell wiring | SELECT | One owner for metric scenes, legend, next actions, path previews, pane scenes, mode brief, footer ticker |
| Scatter legend/path copy into experience.py only | REJECT | Would duplicate acceptance-contract surfaces |
| Keep system scrollbar / default cursor outside stage | REJECT | Breaks scenery continuity the operator already rejected |

## Domain vocabulary (owned concepts)

| Concept | Owner | Decides |
|---|---|---|
| `PathStepPreview` | `scene_surface.path_step_previews` | Cue label/mode/consequence per Decision Path step |
| `PaneSceneEntry` | `scene_surface.pane_scene_entries` | Navigator/Atlas/Inspector scene activation |
| `ModeBrief` | `scene_surface.evidence_gap_mode_brief` | Rules/assumptions/choices for `? items` |
| `footer_ticker_items` | `scene_surface` | Scrolling status truths (auth, no permanent delete) |
| InteractionCue paint | `experience.cueFrom` / `paintCue` | Reticle + cartouche from DOM cue attrs |
| Legal next actions | `operator_next_actions` ← `decision_flow` | STAGE REMOVAL PATH / KEEP / REVIEW LATER |

## Dependency direction

```text
interaction-scene-acceptance.v1 / decision_flow
        │
        ▼
scene_surface.py  (metrics, legend, next actions, path previews,
                   pane scenes, mode brief, footer ticker, scenery subtitle)
        │
        ├─► experience.py  (Decision Path markup cues + app-wide reticle)
        └─► shell.py render + selection/scene script
                │
                ▼
operator perception (headers = scene buttons; path steps glow + cue change;
                     scrollbar/cursor match scenery; ? items brief; footer ticks)
```

## Success stacks

### Decision Path hover → distinct cue

```text
USER pointerenter path step GATE
  -> .decision-guide-step[data-cue-label="PREVIEW GATE"] (pointer-events:auto)
  -> experience.cueFrom(host)
  -> paintCue({mode:resolve, label:PREVIEW GATE, explain:...})
  -> step.is-hover glow
  -> terminal: cartouche/reticle show GATE preview, not default EXPLORE
```

### Pane header → scenery

```text
USER click "Storage atlas" pane-scene-btn
  -> data-scene-action=OPEN_ATLAS_SCENE
  -> atlas-scene-panel explanation
  -> FileStewardAtlas.home() + stage focus
  -> terminal: Atlas Home camera scenery
```

### ? items mode brief

```text
USER selects evidence with item_count=None / INCOMPLETE scan
  -> shell._render_mode_brief
  -> evidence_gap_mode_brief() rules/assumptions/choices
  -> terminal: legend area teaches gap ≠ UNKNOWN, legal choices, no auto stage-removal
```

### Classify / stage removal

```text
USER selects RECLAIM_PROVEN + UNAPPROVED
  -> operator_next_actions(flow)
  -> STAGE REMOVAL PATH / KEEP / REVIEW LATER
  -> STAGE REMOVAL PATH opens Decision chamber approval path
  -> terminal truth: quarantine staging — NO BYTES REMOVED
```

## Failure stack

```text
USER wants to delete PROTECTED evidence
  -> allowed_intents() empty
  -> WHY LOCKED next action
  -> no inviting delete control
```

```text
USER hovers Decision Path when compass pointer-events:none (regression)
  -> cueFrom misses .decision-guide-step
  -> default EXPLORE cartouche
  -> FAIL acceptance; prevented by compass/step pointer-events:auto + cue attrs
```

## Proof ceiling

- Shell markup + focused/full pytest: this pass
- Live operator acceptance of path glow/cues, scrollbar, app-wide cursor, pane scenes, mode brief, footer ticker: waiting
- Permanent deletion: still not implemented
- Full U1 remainder (favicon, health scenes beyond gap brief): successor
