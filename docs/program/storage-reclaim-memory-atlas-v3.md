# FileSteward Memory Atlas v3 — Forensic Memory Substrate

**Status:** P95 PROGRAM DESIGN + P97 PRIOR ART + P129 CROSS-INPUT CONTRACT + P130 VERSIONING HOOK; IMPLEMENTATION PROTOTYPES NEXT

**Current live floor:** Memory Atlas v2 at PR #15 historical live-certified head `900caccda01931f8ce04f879856f57ac12ec008c`.

**Operator disposition:** v2 is technically proven but **not aesthetically/ergonomically accepted**; do not merge it as the final visual result.


**Safety inheritance:** every FileSteward evidence, authorization, privacy, literal-rendering, accessibility, and no-destructive-control invariant remains binding.

## 1. Why v3 exists

Memory Atlas v2 solved the first structural defect: the operator no longer lands on roughly 200 microscopic peer rectangles. It added a readable top-12 overview, Focus Chamber, reverse navigation, full-run context, keyboard support, and reduced-motion behavior.

The private live review then falsified a second assumption:

> a readable overview plus a cinematic transition is not yet an immersive decision instrument.

Observed shortcomings:

- the center scene still reads like a rectangular report rather than a navigable data world;
- tiny full-run sectors are effectively precision-pointer traps, so choosing a small item is partly ceremonial/random;
- the laptop-width focus view can crop/overflow large labels and compress the evidence scene;
- decision state is mostly text in the inspector instead of shaping the visual story;
- there is no universal camera-home semantic;
- mobile/touch has not yet become a separate interaction language.

v3 changes the product model from **overview -> one focus panel** into a **semantic camera over one truthful evidence field**.

## 2. North star — forensic memory substrate

The Atlas should evoke memory hardware, diagnostic consoles, secure forensic tooling, and terminal telemetry without pretending evidence groups are physical RAM addresses or disk sectors.

Visual grammar:

- graphite/deep-navy/mineral-black substrate;
- restrained phosphor/cyan signal light for active system paths;
- amber for the first unresolved decision gate;
- protected/blocked states use hard barrier edges and stop glyphs rather than inviting glow;
- coordinate rails, etched traces, scan/status telemetry, bounded terminal cursors;
- depth, occlusion, scale, and masking explain camera movement;
- no generic purple AI neon, rainbow extension mosaic, faux physical addresses, or decorative cyberpunk noise;
- glow is semantic: it indicates focus, state, signal travel, or a required decision.

This remains **Operate** UX with one earned **Experience** moment: the camera dive. Routine operations remain fast.

## 3. Reference translation — mechanisms, not imitation

### AYOCIN / ATMOS

The supplied reference screenshots demonstrate a useful interaction principle: **content becomes the transition medium**. Scale/masking/depth reframe the same subject so movement feels continuous rather than like a panel replacement.

Adopt:

- one authored focal transition;
- scene changes that temporarily reduce chrome;
- scale and masking as spatial continuity;
- a clear narrative relationship between previous and next view.

Reject:

- copying imagery, branding, typography, masks, source code, or the promotional/wellness visual world.

### pbakaus/impeccable

Adopt:

- one focal motion thesis rather than scattered animation;
- motion must explain state, hierarchy, feedback, or relationship;
- responsive behavior is structural;
- desktop and phone are reviewed as distinct shipped surfaces;
- reduced-motion preserves state meaning while reducing spatial travel;
- durable design context belongs in tracked artifacts.

### D3 zoomable data views

Adopt:

- fit/zoom to a known geometry;
- reproject existing rectangles into a new camera;
- fade/reposition between views;
- pointer and touch pan/zoom mechanics.

Reject hierarchy inference. Current F6 evidence remains flat (`parent_id=None`). Camera scale may change; evidence ancestry may not.

## 4. One truthful field, multiple semantic camera levels

The user’s 100,000-ft -> 5-ft metaphor becomes semantic level-of-detail (LOD), not fake physical distance.

| Camera level | Purpose | Target density |
| --- | --- | --- |
| `HOME` | orientation / dominant decisions | top 12 directly operable |
| `BANK` | broad exploration | roughly 24–48 readable targets |
| `FABRIC` | whole-run magnitude context | all evidence groups; micro nodes are context, not precision controls |
| `CELL` | selected-region magnification | selected node and neighbors become reliable targets |
| `CHAMBER` | one-node decision analysis | full evidence + gate signal + inspector |

The implementation may interpolate continuously between these levels. The named levels define interaction/LOD semantics and testable state.

### Small-sector rule

A rectangle below the supported direct-target floor must **not pretend to be precisely clickable**.

For a micro node:

1. discover by search/navigator/keyboard or contextual traversal;
2. select exact node identity through the canonical selection owner;
3. fit the camera to its persisted geometry;
4. make it a deliberate target at `CELL`;
5. open `CHAMBER`.

This converts “dartboard selection” into deterministic spatial navigation.


### Accessibility geometry floor

The micro-sector rule is also an accessibility contract:

- WCAG 2.2 supplies a 24×24 CSS-pixel external floor, but FileSteward's existing visual-token contract is intentionally stronger: 40px minimum / 44px preferred for direct pointer targets;
- if the treemap geometry cannot honestly provide that size, an equivalent reliable control (navigator/search/keyboard result) must select the same node and expose `atlas.fit_selected`;
- camera zoom must not turn a visual context rectangle into a fake larger evidence object; only the view transform changes;
- responsive drawers/sheets/sticky chrome must not completely obscure the currently focused control;
- focus visibility, state text, and equivalent controls remain available under reduced motion and forced colors.

Reference: WCAG 2.2 SC 2.5.8 Target Size (Minimum) and SC 2.4.11 Focus Not Obscured (Minimum). FileSteward's 40/44px product floor remains authoritative where it is stronger.

## 5. Canonical semantic actions

Physical controls are adapters. These action names own product intent:

- `atlas.select(node_id)`
- `atlas.zoom_in`
- `atlas.zoom_out`
- `atlas.fit_selected`
- `atlas.open_selected`
- `atlas.back`
- `atlas.home`
- `atlas.search(query)`
- `atlas.toggle_decision`

### Back vs Home

- **Esc / Back** = one camera/scene step backward.
- **Home** = return camera to `HOME`.
- `atlas.home` must not clear orthogonal search, filter, or current-selection state.

This repairs the current “no way home” defect without introducing destructive reset semantics.

## 6. Decision Signal — make the interface tell the decision story

The visual signal layer is a **projection of existing gate state**, never a second decision engine.

| Existing evidence/gate state | Visual signal |
| --- | --- |
| passed | cool, steady, low-energy trace |
| first unresolved / waiting | bounded amber/phosphor pulse + visible cursor/next-gate target |
| unknown / incomplete | dim scan trace / dashed telemetry |
| protected / blocked | hard barrier/stop edge; no inviting motion |
| unapproved | explicit lock/label; never reclaim-green |
| selected | focused corridor connecting node identity to first unresolved gate |

Rules:

- state remains readable as text/icon; color/glow alone never carries meaning;
- no rapid strobe;
- reduced-motion removes spatial travel and nonessential pulsing while retaining meaningful state change;
- signal projection may classify presentation state only; it cannot mutate `PresentationNode`, disposition, gate truth, or authorization.

## 7. Scene composition and motion thesis

### Focal sequence

`HOME/BANK/FABRIC -> CELL -> CHAMBER`

1. exact node identity is selected;
2. surrounding chrome recedes;
3. camera fits the persisted rectangle/region;
4. substrate traces energize toward the selected evidence;
5. the first unresolved gate becomes the dominant signal target;
6. Chamber resolves with evidence and decision detail;
7. Back reverses one scene step; Home returns to `HOME`.

Routine focus changes inside a settled level do not replay the whole focal sequence.

### Motion budget

Guideline ranges, subject to real browser proof:

- focus/selection feedback: ~120–220 ms;
- camera step / fit-selected: ~220–420 ms depending on distance;
- authored `CELL -> CHAMBER` entrance: ~450–650 ms;
- exit should generally be faster than entrance;
- no page-load choreography.

Prefer transforms/opacity/geometry interpolation. Bound filter/blur/shadow to isolated elements. Use `will-change` only during active motion.

Web Animations is the baseline. Same-document View Transitions may be progressive enhancement where available; the state model must work without them.

## 8. Responsive architecture — laptop is not smaller desktop; phone is not tiny laptop

### Wide desktop

Tri-pane is permitted only while the Atlas still owns a generous center stage. The operator’s evidence world is primary; chrome is secondary.

### Constrained laptop

- scene-first composition;
- navigator collapses to rail/drawer;
- inspector becomes overlay/drawer or lower region after explicit selection;
- no fixed three-column squeeze;
- all flex/grid children that contain long labels/paths explicitly allow shrink (`min-width: 0`);
- long names/paths wrap or clamp intentionally rather than escape the scene.

### Tablet

- full-width Atlas;
- navigator/search in a sheet/drawer;
- decision detail in a side/bottom sheet;
- touch and keyboard both remain valid.

### Phone

- full-screen Atlas camera;
- thumb-reachable command bar: Home, Search, Zoom out, Zoom in, Decision;
- selection detail opens a touch-native bottom sheet;
- pinch is an accelerator, not the only zoom path;
- no hover dependency;
- no precision tapping of micro sectors;
- keyboard appears only for explicit text entry;
- safe area, orientation, visual viewport, and browser/OS back are deliberate.

## 9. Cross-input convergence — P129 (requested alias P1009)

The current Prompt Kit has no canonical `P1009` identity. The requested cross-input semantics resolve to **P129 — Cross-Input UX Modality & Phone-Native Interaction Architect**. Preserve that alias mismatch as continuity evidence; do not invent a second prompt.

| Capability | Pointer | Keyboard | Phone/touch | Semantic owner |
| --- | --- | --- | --- | --- |
| return home | Home control | `Home` | Home command | `atlas.home` |
| step back | Back control | `Esc` | Back/sheet back | `atlas.back` |
| zoom | wheel/trackpad + +/- | +/- | pinch + +/- | `atlas.zoom_in/out` |
| select | click readable sector | arrows/search | tap readable sector | `atlas.select` |
| magnify micro node | search/nav -> Fit | search -> Fit | search result -> Fit | `atlas.fit_selected` |
| open Chamber | explicit Open / deliberate second action | `Enter` | Open in sheet | `atlas.open_selected` |
| search | field | `/` | Search command | `atlas.search` |
| decision detail | inspector/control | collision-checked shortcut | Decision sheet | `atlas.toggle_decision` |

Exact shortcut letters remain subject to collision review; semantic actions are stable.

## 10. Program seams — P95

### Camera

`input adapter -> semantic action -> AtlasCamera -> transform/LOD -> renderer`

`AtlasCamera` owns presentation-only state:

- scale/translation;
- current semantic camera level;
- back-stack;
- selected node reference;
- reduced-motion preference.

It does **not** own evidence, authorization, search, filter, or disposition truth.

### Decision Signal

`PresentationNode + gate_steps -> DecisionSignal projector -> accessible SVG/CSS signal`

The projector derives presentation classes only.

### Input convergence

`pointer | keyboard | touch adapter -> semantic action -> shared selection/camera state -> mode-native feedback`

Do not create a second mobile state machine or duplicate business rules.

### Proposed modules

- `src/filesteward/visualization/camera.py` — camera/LOD math and scene transitions;
- `src/filesteward/visualization/signals.py` — gate-to-signal projection;
- existing `selection.py` remains canonical selection owner;
- `cinematic.py` becomes composition/motion convergence;
- `shell.py` owns responsive chrome/composition;
- `tests/test_visualization_camera.py`;
- `tests/test_visualization_signals.py`.

## 11. P04 execution map

| Lane | State | Mission | Dependency | Owned surface |
| --- | --- | --- | --- | --- |
| `V3-A` | provider-pushed; local repo validation pending | v3 design + P97 research + P130 version authority | none | design/prior-art/versioning/plan |
| `V3-B` | ready after V3-A local validation | semantic camera + LOD | V3-A | new camera seam + tests |
| `V3-C` | ready after V3-A local validation | Decision Signal projector | V3-A | new signal seam + tests |
| `V3-D` | waiting | scene composition + responsive + pointer/keyboard/phone convergence | V3-B + V3-C | cinematic/shell + acceptance tests |
| `V3-E` | waiting | exact-head private report + operator visual acceptance | V3-D | ignored local runtime proof only |
| `F7` | downstream | contract-selection UX | V3-E | separate operator decision lane |

V3-B and V3-C are intended as independent writers because their primary files do not collide. V3-D is the convergence owner.

## 12. Product version contract — P130

The human-facing product authority is `[project].version` in `pyproject.toml`.

- docs/research/tests-only: no bump;
- accepted visual polish affecting shipped visualization/tokens: PATCH;
- new scene/camera/input capability: MINOR.

The first shipped v3 visual mutation should run:

```powershell
python scripts/versioning.py ensure-visual-bump --base origin/main --kind visual-feature
python scripts/versioning.py guard --base origin/main
```

On the current `0.1.0` floor that yields `0.2.0`. Design-only V3-A deliberately does not bump.

## 13. Acceptance

### Deterministic

- one canonical evidence/selection model survives every camera state;
- Home preserves search/filter/selection;
- micro nodes cannot masquerade as reliable direct targets;
- Decision Signal never promotes evidence/authorization;
- pointer/keyboard/touch call the same semantic actions;
- reduced motion preserves meaning;
- hostile/private strings remain literal;
- shipped visual changes cannot merge with a stale product version.

### Browser/device

Capture at least:

- 1440 desktop;
- the constrained laptop width that reproduced overflow;
- 390px phone emulation;
- reduced motion;
- keyboard-only path.

Prove:

- no clipped focus target or overflowing title/path;
- Home is always reachable after a dive;
- search-to-micro-node creates deterministic camera fit;
- camera scale remains understandable;
- first unresolved gate is visually obvious without reading the whole inspector;
- phone requires neither hover nor precision micro-target tapping;
- no private receipt data is committed.

### Operator

The operator must experience the real local report and accept the spatial feel. Automation cannot certify aesthetics or physical-phone ergonomics.

## 14. Proof ceiling

This contract proves the next architecture, ownership seams, acceptance model, and versioning dependency. It does **not** prove v3 runtime behavior, filesystem hierarchy, physical RAM/disk topology, phone hardware comfort, operator aesthetic acceptance, F7 contract choice, approval, quarantine, deletion, or reclaimed space.

## 15. P13 visual-overhaul failure and repair contract — 2026-10-04

The first wired v3 candidate at `4f0eeec88ae0ddba69b580546116f32aa5ef0fa0`
passed the local suite but **failed operator visual review from screenshots before a trusted-click
verdict was needed**.

### Repeated failure class

The recurring defect is **UX intent compression**:

`cinematic overhaul requested -> semantic/state infrastructure implemented -> familiar dashboard composition retained -> operator asked to judge the last mile`.

That is not acceptable for a deliberately experiential sprint. A green state machine is necessary
but cannot stand in for the requested visual transformation.

### Screenshot-proven failures

- CELL/CHAMBER still preserve the familiar navigator + rectangular center + inspector composition;
- standard cursor language remains instead of context-dependent DIVE / FOCUS / RESOLVE affordance;
- glow reads mainly as a selected outline rather than live decision-signal energy;
- the decision trace is still something to read after arrival instead of teaching the path during navigation;
- Home exists technically but is visually equivalent to ordinary toolbar controls;
- the authored cinematic motion is too small relative to the requested reference bar.

### P13 prevention

Before an experiential candidate may be sent to the operator for acceptance, the implementing agent
must perform a screenshot/browser self-falsification against the operator's requested experience.

The candidate is automatically **REJECTED BEFORE OPERATOR** when any of these are true:

1. semantic camera levels do not materially recompose the viewport;
2. the pointer remains generic over the immersive Atlas on fine-pointer devices;
3. the first unresolved gate lacks a visible animated signal path/beacon;
4. Atlas Home / Back recovery is not persistent and self-explanatory;
5. a new user cannot infer MAP -> FOCUS -> RESOLVE -> DECIDE from the interface itself;
6. the new screenshot remains recognizably the same three-pane dashboard with additional controls.

### Natural tutorial contract

P25 classifies the tutorial opportunity as **READY_AFTER_PRODUCT_FIX**. P18 documentation is
deferred because documenting a rejected journey would create tutorial theater.

The product itself teaches the stable workflow through a compact **Decision Compass**:

`MAP -> FOCUS -> RESOLVE -> DECIDE`

It is a projection of existing camera/gate/authorization state, not a tour overlay and not a second
decision engine.

