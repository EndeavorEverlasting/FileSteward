# P82 Experiment Admission — U1 interaction declutter

**Thesis (single):** Cursor/context occlusion and ceremonial Decision Path steps are stacking-context + enactment gaps, not missing copy.

## Falsifiable hypothesis

If reticle/cartouche are portaled to `document.body` (escaping `storage-stage{isolation:isolate}` and `.atlas-hud{z-index:4}`), HUD/chamber hovers show distinct cues; if Decision Path steps dispatch `filesteward:path-step` and call Atlas camera APIs, each step changes scenery; if the compass docks in negative space and is draggable, it no longer permanently occludes the atlas.

## Baseline / comparator

- Baseline: `84522fd` proof where HUD hover stays EXPLORE under panels; path clicks mostly preview-only; floating ATLAS HOME beacon overlaps; compass centered over sectors.
- Comparator: this candidate with body portal, `enactPathStep`, docked/draggable compass, removed beacon, scenery type classes, brand-home zoom.

## Prototype boundary

Owned: `experience.py`, `shell.py`, `cinematic.py`, `decision_chamber.py`, `scene_surface` tests/docs. Forbidden: permanent delete, merge without operator acceptance, real C: scans.

## Measurement

1. Markup/script contains `document.body.appendChild`, `data-portal="body"`, `enactPathStep`, `data-drag-handle`.
2. Focused + full pytest green.
3. Regenerated proof HTML includes those markers and omits `atlas-home-beacon`.
4. Operator hard-refresh confirms: HUD cues visible; path steps change scenery; compass draggable; brand title zooms home.

## Decision rule

- KEEP if (1)+(2)+(3) pass and operator does not reject the interaction set.
- REFINE if operator finds residual occlusion/ceremony.
- REJECT only if Atlas API enactment cannot change scenery without a new camera owner (route P95).
