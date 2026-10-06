# P97 Prior Art — Action → Scene → Impact Context Engine — 2026-10-06

**Status:** judgment evidence for the Decision-to-Deletion UX sprint  
**Purpose:** determine how FileSteward should name pointer/actions, preserve context across scene changes, and ensure every interaction produces a truthful, useful consequence.  
**Rule:** adapt mechanisms and semantics; do not vendor third-party source, visual assets, or a second state-machine framework.

## Operator-observed defect

The current UI can render the custom reticle as **EXPLORE** over a target where clicking does not actually enter an exploration environment or produce a recognizable exploratory transition.

That is not merely copy debt. It exposes a missing contract between:
- current scene/context;
- target;
- action label;
- executable transition;
- effect/impact;
- continuation.

A custom cursor/reticle is an action promise. If the visible verb and the click result diverge, the product loses its through-line.

## Upstream evidence

| Reference | Observed principle | FileSteward disposition |
|---|---|---|
| MDN CSS `cursor` — https://developer.mozilla.org/docs/Web/CSS/cursor | Cursor state should communicate the mouse operation actually available at the current location. Specialized cursor vocabulary corresponds to concrete operations such as zoom, grab, copy, context menu, etc. | **ADOPT semantic rule.** A FileSteward reticle verb must name the operation activation will actually perform. |
| W3C WAI G131 / control labeling — https://www.w3.org/WAI/WCAG21/Techniques/general/G131.html | Interactive labels must make component purpose clear. | **ADOPT proof rule.** Visible/accessible action label and actual purpose must agree. |
| W3C Cognitive Accessibility clear controls — https://www.w3.org/WAI/WCAG2/supplemental/patterns/o1p05-clear-controls/ | Controls should make available tasks/actions recognizable and behave according to familiar patterns. | **ADOPT continuity rule.** Do not render an inviting action if activation has no matching consequence. |
| Apple HIG Buttons — https://developer.apple.com/design/human-interface-guidelines/buttons | A button initiates an action; its content and role communicate purpose. Verb labels should tell people what the action does. | **ADOPT action-language discipline.** Use immediate-effect verbs, not atmospheric verbs. |
| Apple HIG Feedback — https://developer.apple.com/design/human-interface-guidelines/feedback | Feedback tells people what is happening, the result of an action, and what they can do next. | **ADOPT result/continuation contract.** Completed actions produce impact feedback and a next path. |
| Apple HIG Writing — https://developer.apple.com/design/human-interface-guidelines/writing | Action-oriented labels help people move from one step/screen to the next; clarity beats clever wording. | **ADOPT.** Reticle/cartouche vocabulary is functional navigation language, not cinematic decoration. |
| Apple HIG Motion — https://developer.apple.com/design/human-interface-guidelines/motion | Feedback motion should follow gestures/expectations and help users track transitions rather than disorient them. | **ADOPT spatial-continuity rule.** Scene motion supports the transition contract; it does not substitute for it. |
| Stately state-machine/statechart model — https://stately.ai/docs/glossary | Context stores state data; events/transitions determine state changes; actions are effects executed through transitions. | **ADAPT architectural discipline only.** Keep FileSteward's existing canonical state owners; do not add XState/another state machine. |
| FileSteward existing WinDirStat/QDirStat/SpaceSniffer prior art | Exploration succeeds when selection, zoom, focus, filtering, and details-on-demand visibly change the user's working context. | **RETAIN** exploration as a real environment/capability, not a generic default verb. |

## P97 conclusion

### 1. `EXPLORE` is a reserved semantic verb

`EXPLORE` is legal only when activation enters or operates an explicitly exploratory scene/context and produces a recognizable exploration effect such as:
- drill/zoom into a storage region;
- pan/navigate an exploration surface;
- enter an evidence-browsing scene;
- reveal details-on-demand while remaining in an exploration environment.

It is **not** a generic fallback for:
- unknown targets;
- unselected evidence;
- empty canvas;
- controls whose real effect is SELECT, FOCUS, FILTER, OPEN GATE, RESOLVE, APPROVE, DELETE, RETURN, or no action.

If clicking an evidence node focuses it and opens its decision context, the cue should name that actual result (for example `FOCUS` / `OPEN DECISION` according to the canonical vocabulary), not `EXPLORE`.

### 2. No permissive generic action fallback

An unregistered action/target combination must not silently become an operable `EXPLORE` cue.

Fail closed:
- registered action projection -> truthful operable cue;
- informational target -> truthful informational cue or no custom action cursor;
- unknown/unresolvable action -> unavailable/diagnostic state in development proof, never a fabricated operable verb.

This directly targets the current `cue_for_navigation(... table.get(... EXPLORE ...))` pattern and any equivalent fallback.

### 3. Action → Scene → Impact → Continuation

Every operable interaction must resolve a projection:

```text
source scene/context
  + target
  + current evidence/selection/gate/authorization
  -> action
  -> destination scene/context revision
  -> impact
  -> feedback/readback
  -> continuation
```

A **scene** is an authored user context, not necessarily a separate page/modal. A transition may retain the same scene type while changing its canonical context revision (selection/filter/gate), but the impact must be visible and truthful.

### 4. Every scene must deliver product impact

A FileSteward scene must name at least one primary impact class:

- `ORIENT` — establish truthful system/evidence context;
- `FILTER` — narrow to a meaningful evidence subset;
- `CLASSIFY` — advance/persist evidence disposition through its canonical owner;
- `DECIDE` — record/advance an operator decision;
- `AUTHORIZE` — establish exact action authority;
- `RECLAIM` — execute bounded deletion/quarantine as contracted;
- `VERIFY` — prove result/reclaim;
- `EXPLORE` — inspect/navigate evidence in an explicitly exploratory environment.

For FileSteward's main journey, `EXPLORE` and `ORIENT` are supporting impacts. They must preserve a visible route toward decision/classification/reclaim impact rather than becoming a terminal scenic loop.

### 5. Context projection must be centralized and freshness-bound

Do not scatter label guesses through renderers.

The existing interaction projection should be factored so an operable cue is derived from the authoritative context tuple, at minimum:

```text
scene_id / scene_revision
selected_node_id
evidence disposition
active_gate_id
authorization state
target_id / target_kind
registered action
availability
destination scene/context
impact kind
continuation
```

Any change to scene, selection, gate, authorization, target, or execution result invalidates the prior cue projection. The cursor/cartouche must recompute or disappear. It must not carry stale semantics into new scenery.

This remains a **projection**, not a new state machine.

### 6. Classification must compound future usefulness

Classification/decision impact is not complete merely because a receipt was written.

When canonical classification/decision state changes, the resulting state must be available to:
- classification filters;
- relevant scene counts/status;
- subsequent decision queues;
- filtered views that let the operator revisit KEEP / HUMAN_REVIEW / UNKNOWN / RECLAIM_PROVEN / PROTECTED evidence.

The scene system therefore carries the classification through-line forward instead of treating each decision as an isolated cinematic event.

## Rejected alternatives

| Alternative | Disposition |
|---|---|
| Rename `EXPLORE` to another generic atmospheric word everywhere | **REJECT** — does not fix semantic projection. |
| Make every renderer choose its own verb based on DOM context | **REJECT** — repeats the current drift mechanism. |
| Add another client-side state machine/context engine | **REJECT** — duplicates canonical authority. |
| Remove the custom reticle entirely to avoid semantic responsibility | **REJECT** as a default fix — the reticle can be valuable if it is truthful. |
| Keep generic `EXPLORE` but improve tooltip explanation | **REJECT** — explanation cannot cure a false action promise. |

## Implementation target

Extend the existing FileSteward interaction projection / scene contracts rather than replacing them.

Likely owner surfaces after the prescribed UI-lineage merge:
- `src/filesteward/visualization/interaction.py`
- `src/filesteward/visualization/scene_surface.py`
- `src/filesteward/visualization/decision_flow.py`
- `src/filesteward/visualization/experience.py`
- `src/filesteward/visualization/decision_chamber.py`
- `src/filesteward/review_bridge.py`
- `harness/contracts/interaction-scene-acceptance.v1.json`

The canonical P04 plan and the dedicated action/scene/impact harness contract define acceptance. Local agents implement and prove; they do not reinterpret this prior-art conclusion.
