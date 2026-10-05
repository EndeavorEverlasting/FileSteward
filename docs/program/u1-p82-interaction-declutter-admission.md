# P82 Experiment Admission — U1 interaction declutter

**Thesis (single):** Cursor/context occlusion and ceremonial Decision Path steps are stacking-context + enactment gaps, not missing copy.

## Falsifiable hypothesis

If reticle/cartouche are portaled to `document.body` (escaping `storage-stage{isolation:isolate}` and `.atlas-hud{z-index:4}`), HUD/chamber hovers show distinct cues; if Decision Path steps dispatch `filesteward:path-step` and call Atlas camera APIs, each step changes scenery; if the compass docks in negative space and is draggable, it no longer permanently occludes the atlas.

## Baseline / comparator

- Baseline: `84522fd` proof where HUD hover stays EXPLORE under panels; path clicks mostly preview-only; floating ATLAS HOME beacon overlaps; compass centered over sectors.
- Comparator: this candidate with body portal, `enactPathStep`, docked/draggable compass, removed beacon, scenery type classes, brand-home zoom.

## Prototype boundary

Owned: `experience.py`, `shell.py`, `cinematic.py`, `decision_chamber.py`, `scene_surface` tests/docs. Forbidden: permanent delete, merge without operator acceptance, real C: scans.

## Measurement (this pass)

1. Markup/script contains `requestedScene`, distinct `sceneBrief` GATE/RESOLVE/APPROVAL, `resetHighlights`, `el.classList.remove('selected')` on home, `atlas-range-marquee`, document `selectstart` preventDefault, `html,body` user-select none, visible `data-product-version`.
2. Focused + full pytest green.
3. Regenerated `Outputs/u1-brand-home-proof.html` includes those markers and `0.10.0`.
4. Operator hard-refresh confirms: Home clears highlights; GATE/RESOLVE/APPROVAL are distinct; drag-range is scenery not native blue; version visible.

## Decision rule

- KEEP if (1)+(2)+(3) pass and operator does not reject the interaction set.
- REFINE if operator finds residual occlusion/ceremony.
- REJECT only if Atlas API enactment cannot change scenery without a new camera owner (route P95).

**This pass thesis:** requestedScene + home deselect + document-level range capture + visible version close the 2026-10-05 screenshot gaps without C: mutation.
