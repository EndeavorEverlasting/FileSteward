# Memory Atlas scene composition

A scene is the current storage question, its evidence, the legal immediate actions,
and the continuation after authoritative readback. It is not a separate page or
another router. The [judgment workflow](../../harness/contracts/judgment-scene-workflow.v1.json)
owns every entry condition and event-to-destination mapping. The
[composition contract](../../harness/contracts/scene-composition.v1.json) binds all
eleven scenes to those fields by JSON pointer, so a renderer cannot silently copy
an old transition table and become a second policy owner.

## Components and ownership

| Component | Question it answers | Owner |
| --- | --- | --- |
| World/canvas | Where are the storage regions and what is selected? | Existing Atlas camera and renderer |
| Subject | Which exact target does this question concern? | Canonical selection identity |
| Related subjects | Which other visible representations or evidenced dependencies must remain legible? | Target identity and canonical evidence relationships |
| Gate/evidence | What fact is known, missing, stale, protected or being checked? | Judgment script and deterministic adapters |
| Chamber | What is the current question, legal choice, authorization or result? | Decision flow and authoritative bridge readback |
| Path guide | Where am I in MAP → FOCUS → GATE → RESOLVE → APPROVAL → STAGED? | Existing tutorial projection |
| Context/reticle | What is this target and what will activation immediately do? | Action projection and input adapter |
| Chrome | How do I return Home, search, or filter? | Existing navigation/search/filter owners |
| Input mode | Which physical interaction is active? | Shared pointer/keyboard/touch capability adapters |

The subject persists between gates for the same item. Search, filters and evidence
history remain orthogonal. If authoritative readback removes the selected target,
the existing continuation owner chooses the next valid subject. Tooltip placement,
chamber dragging and camera position never grant authority or change disposition.

## Complete scene inventory

These are composition summaries. Entry conditions, allowed choices, automatic
work, exact transition events and success evidence remain in the linked script.

| Canonical scene | Dominant content | Related evidence kept visible | Scripted continuation families |
| --- | --- | --- | --- |
| ATLAS_HOME | Storage health and decision-relevant world | Selection summary and next actions | Focus a candidate; preserve Home on filters or satisfied goal |
| TARGET_FOCUS | One subject and first unresolved gate | Subject identity and selected map representation | Evidence gate or value decision |
| EVIDENCE_GATE | One missing technical fact | Subject and active gate line | Attribution, consequence, recoverability or exact unresolved value review |
| ATTRIBUTION_RESOLVE | Ownership probes, provenance and conflicts | Subject and evidence trace | Consequence or exhausted-adapter value review |
| CONSEQUENCE_RESOLVE | Dependencies and protective consequence | Subject and evidence trace | Recoverability or value decision |
| RECOVERABILITY_RESOLVE | Reproduction/reacquisition proof and limits | Subject and evidence trace | Value decision with the proven disposition floor |
| VALUE_DECISION | Legal human preference after technical resolution | Subject, evidence and legal action controls | Verification for keep/defer; exact authorization for mutating intent |
| AUTHORIZATION_GATE | Exact scope/action/evidence and consequence | Subject and authorization summary | Execute if authorized and fresh; evidence gate on drift; value decision on cancel |
| RECLAIM_EXECUTION | Bounded action progress and receipt | Subject and result | Verification or incident recovery |
| VERIFY_RETURN | Measured result, health and continuation | Receipt and next actions | Next candidate, Home or incident recovery |
| INCIDENT_RECOVERY | Affected capability, causal state and frozen family | Error, receipt and diagnostic evidence | Verification after repair or safe Home return |

Technical RESOLVE subscenes may advance only under the canonical automatic
transition policy, with their evidence retained in the trace. Value preferences and
exact destructive authorization are never inferred by presentation. Unknown
script mappings produce `BLOCKED_JUDGMENT_GAP`.

## Context panel placement

The cursor is a physical position, the hovered subject is an evidence identity,
and the context panel is a disposable explanation. Treat those as distinct objects.
Measure all rectangles in viewport CSS pixels after layout/camera transforms.

1. Resolve the hovered target and its nearest subject/card. Collect the hovered
   rectangle, visible same-identity representations, visible selected subjects,
   scene-specific evidence regions and active controls/chrome as exclusions.
   DOM proximity alone does not prove a dependency; use identity or evidenced
   relationships. Ignore hidden or offscreen geometry.
2. Try local placements around the pointer and beside the target. Reject overlap
   with every exclusion and reject out-of-viewport rectangles. The rectangle-to-
   anchor gap must be at most 48 CSS pixels. Choose the nearest legal candidate.
   Clamping after collision checking is invalid because it can reintroduce overlap.
3. If the full explanation cannot fit, retry with a compact action label. If that
   cannot fit either, hide the transient panel. Keep the native pointer and the
   persistent subject/evidence/action text available. Never park context on the
   opposite edge of the page or cover the evidence to force a panel to remain open.

The transient panel receives no pointer events and contains no unique action or
necessary evidence. This prevents a hover panel becoming a mouse-chasing menu.
Legal actions stay in the persistent controls. An unavailable target has an empty
action cue or “No action available”; it never acquires a generic EXPLORE promise.
Only a full visible explanation receives the transient accessible-description
association. Keyboard and touch retain persistent names, evidence and controls.

Pointer events own the physical reticle coordinates. Keyboard focus can anchor a
separate explanation to the focused control but cannot move the physical reticle.
Escape dismisses context until the target or pointer changes. Leaving the Atlas,
switching input modes, scrolling, resizing, dragging the Chamber, changing camera
geometry, or changing scene/selection/gate/authorization/result invalidates old
geometry and semantics. Recompute or hide before the next action. Reduced motion
and forced colors preserve the same scene, action and fallback semantics.

## Proof boundary

`tests/test_scene_composition_contract.py` checks complete ordered coverage,
canonical entry/transition/evidence bindings, valid destinations, retained
component ownership and resolvable source selectors. Negative mutations demonstrate
that omitted scenes, redirected transitions and weakened local fallback rules fail.
These checks establish contract integrity. Browser collision, distance, input,
viewport and action-effect probes establish rendered behavior; static contract
checks alone do not establish live UX acceptance.
