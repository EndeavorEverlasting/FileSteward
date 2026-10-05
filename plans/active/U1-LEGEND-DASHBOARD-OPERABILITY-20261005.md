# U1 Legend / Dashboard / Chamber Operability — Sprint Plan

**Status:** ACTIVE / LIVE-VALIDATED at `0.12.2` — dashboards survive home(); chamber viewport-fixed with settle redocks (rAF + timeouts); cartouche chrome-clear; PR #17 draft awaiting operator acceptance (merge blocked by stack drafts #15/#16/#17)

**Repository:** `EndeavorEverlasting/FileSteward`  
**Lane owner:** P07 on `design/u1-brand-home-schedule-seam-20261005` (PR #17 stack)  
**Base head at sprint start:** `d289545` / product `0.11.0`  
**Parent plans:** `STORAGE-RECLAIM-VISUALIZATION-P04.md`, `FILESTEWARD-SYSTEM-STEWARDSHIP-P01-P04-P97-2026-10-04.md`

## 1. Locked outcome

Operators can use the Storage Decision Map as a cinematic decision instrument:

1. Legend entries navigate to matching evidence subsets (not ceremonial chrome).
2. Cursor cartouche docks in Atlas negative space (does not occlude legend/metrics/HUD).
3. Five metric modules act as cinematic dashboards with real subset navigation and decision entry.
4. Authorization metric explains UNAPPROVED clearly and opens a functional approval/staging path when legal.
5. Decision Chamber is draggable into negative space like Decision Path.

## 2. Acceptance rubric (stable)

| ID | Criterion | Observable proof |
|---|---|---|
| A1 | Legend PROTECTED click filters to PROTECTED evidence and focuses first match | shell/html wiring + focused test asserts filter target + atlas call markers |
| A2 | Other legend states map to RECLAIM_PROVEN / KEEP_PROVEN / HUMAN_REVIEW∪UNKNOWN / AUTHORIZATION dashboard | scene_surface fields + shell handlers |
| A3 | Metric modules open dashboards that change Atlas/filter/chamber state | shell action branches beyond scene-panel text |
| A4 | Authorization copy is human-readable; panel is not a dead `OPEN_*` prompt | scene_surface explanation + shell opens chamber/approval path when reclaim available |
| A5 | Cartouche placement obstacles include chrome; prefers stage negative space | experience.js obstacles + stage-clamp |
| A6 | Decision Chamber drag handle + sessionStorage restore | decision_chamber markup/script/css |
| A7 | No permanent-delete control; PROTECTED/UNKNOWN/HUMAN_REVIEW not auto-promoted | existing safety tests remain green |
| A8 | Visual feature version bump above `0.11.0` | pyproject + `__version__` |

## 3. Forbidden scope

- Permanent deletion implementation
- Real `C:` mutation / apply / quarantine execution beyond existing staged cinematic truth
- Merging despite explicit operator-acceptance draft gate on PR #15/#17 without green owned proof
- Aesthetic redesign of warm material palette
- Inventing legal intents outside `decision_flow.allowed_intents()`

## 4. Prototype ladder

| Stage | Purpose |
|---|---|
| Functional prototype | Legend filter + metric dashboard wiring against synthetic fixtures |
| Integrated candidate | Cartouche negative-space + chamber drag + suite green |
| Release candidate | Version bump, docs call-stack update, PR head push |
| Final | Mainline convergence when merge gates permit |

## 5. Parallel lanes (graph width 3)

| Lane | Mutation owner | Hypothesis |
|---|---|---|
| A | `scene_surface.py`, `html.py`, `shell.py` | Legend/metrics become operable cinematic entrypoints via filter API |
| B | `experience.py` | Cartouche docks in stage negative space when chrome obstacles expand |
| C | `decision_chamber.py` | Chamber drag mirrors Decision Path without breaking intents |

Coordinator owns: tests, docs, version bump, validation, commit/push/integration.

## 6. Measurement / decision rules

- KEEP lane output when focused markers/tests pass and safety tests unchanged.
- REFINE when a metric still only paints scene-panel text without Atlas/filter/chamber effect.
- DISCARD any approach that adds permanent-delete affordances or promotes blocked dispositions.

## 7. Proof ceiling

- Local pytest + versioning ensure-visual-bump: this sprint
- Live operator visual acceptance of cinematic feel: operator gate
- Mainline merge: authorized when PR stack gates permit; draft operator-acceptance may remain BLOCKED

## 8. Successor phases (not absorbed here)

- Full immersive metric “dashboard rooms” beyond filter+focus+chamber entry
- F7/F8 contract/approval UX beyond existing Decision Chamber
- Permanent deletion lifecycle (F10)
