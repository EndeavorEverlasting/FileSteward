# Decision-to-Deletion UX Continuity Sprint — 2026-10-06

**Sprint ID:** `FILESTEWARD-DECISION-TO-DELETION-UX-20261006`  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Remote floor at creation:** `3d3c2e3309430b9492fc7feb01c82ca35bb26e4e`  
**UI lineage to reconcile:** PR #15 → PR #16 → PR #17 (Decision Chamber / interaction grammar / Home + operability)  
**Deletion lineage to consume:** merged PR #20 + merged PR #21 and any newer deletion repair that lands before implementation begins  
**Execution mode:** parallel UX/integration lane; do not interrupt or redefine the currently authorized live Temp deletion sprint  
**Prompt composition:** P83 + P82 + P01 + P04; one coordinator retains judgment; local agents perform bounded implementation/proof legwork.

## 1. Operator outcome

Make FileSteward's public Decision Chamber behave like one continuous, immersive decision instrument rather than a ceremonial status viewer.

A completed user decision must immediately cause an authored transition to the next valid decision surface. The UI must never persist a decision and then visually reopen the same unresolved scene as though nothing happened.

For deletion, "frictionless" means **one deliberate commit gesture after the exact scope and safety gates are already established**, not an unguarded unlink and not a chain of redundant confirmation screens.

## 2. Verified defects on remote code

These are current remote-code findings, not screenshot inference.

### DUX-01 — split scene authority

The UI lineage documents `MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED`, and browser code uses `RESOLVE`, but `DecisionScene` in `decision_flow.py` does not define `RESOLVE`.

**Consequence:** Python state, browser state, Decision Path highlighting, and persisted bridge responses can disagree about the current scene.

### DUX-02 — bridge records intent without advancing workflow

`ReviewBridge.record_decision()` validates and persists the operator decision, then returns `state_payload()`. `state_payload()` reconstructs flow from `open_decision_session(node)` using the unchanged presentation node; the persisted decision is not an input to the returned transition.

**Consequence:** a legal decision can be recorded while the UI returns to the same scene/gate. This is the ceremonial loop reported by the operator.

### DUX-03 — the canonical reducer is bypassed

`choose_intent()` exists in `decision_flow.py`, but the bridge does not use it when recording decisions.

**Consequence:** legal-intent validation and transition semantics have separate owners.

### DUX-04 — deletion copy and mutation route are stale

The UI lineage still states "Permanent deletion is not implemented" and approval means QUARANTINE. Main now contains the merged permanent-delete lifecycle from PR #20 and the observed-reclaim terminal contract from PR #21.

**Consequence:** the public-facing UI lies about current product capability and cannot marry the decision experience to the implemented delete path.

### DUX-05 — pointer reticle can teleport independently of the physical pointer

The cinematic layer positions the fixed reticle from real `pointermove` coordinates, but `focusin` also calls `paintCue()` using the focused element's center.

**Consequence:** a click/scene transition that changes focus can move the visual cursor even though the user's physical pointer did not move.

### DUX-06 — range-marquee capture is too broad

A document-level `pointerdown` begins range selection for nearly every left-click outside a small "chrome" selector. It does not require an eligible map surface or a movement threshold before entering the range gesture.

**Consequence:** ordinary clicks can transiently activate a competing gesture/cue model and make the interaction language feel displaced.

## 3. Non-negotiable interaction contract

### 3.1 One scene authority

There must be one canonical transition model.

- No browser-only phantom scene.
- No renderer may invent next-state semantics.
- The server/decision-flow reducer owns legal transition state.
- The browser may animate/present that state but may not fork it.
- If `RESOLVE` remains a product scene, it must exist in the canonical typed scene model and tests.
- If it is removed, every renderer/doc/path preview must be changed together. Do not paper over the mismatch.

### 3.2 Decision -> readback -> next action

Every operable decision follows:

```text
user commit
  -> validate against allowed_intents()
  -> persist decision / perform bounded required effect
  -> authoritative readback
  -> derive next valid scene/gate/item
  -> animate directly to that next target
```

The post-commit response must make the next target explicit. At minimum expose:

- current/next scene;
- current/next gate ID when applicable;
- current/next item ID when the selected item is complete/deferred;
- last transition;
- whether work is pending, complete, blocked, or executable.

Do not make the browser guess the next subsection.

### 3.3 Meaning of the existing intents

- **KEEP:** record the operator keep decision, remove that item from the active reclaim journey, then advance to the next actionable gate/item. Do not visually reopen the same gate.
- **REVIEW_LATER:** persist deferral, remove it from the immediate queue, then advance.
- **RESCAN:** start/queue the repository-owned observation path, show progress truthfully, and on successful readback advance to the newly-derived gate/scene.
- **DECLARE_REGENERABLE_CONTRACT:** persist the operator contract decision through its existing owner, rerun the evidence/classification seam that consumes it, then advance from authoritative readback. Do not promote evidence in presentation code.
- **DELETE_PERMANENTLY:** available only for exact eligible `RECLAIM_PROVEN` scope that satisfies the deletion contract below.

### 3.4 Frictionless destructive commit

Do not recreate permission theater.

When the exact delete set is visible and the fresh preflight is PASS, the UI may present one primary destructive action:

**DELETE PERMANENTLY**

That single deliberate action is the user's irreversible confirmation for the exact visible scope and must:

1. create/materialize the deletion-specific approval artifact required by `filesteward.delete-approval/v1`;
2. bind it to the exact manifest/preflight identity and action `DELETE_PERMANENTLY`;
3. invoke the repository-owned permanent-delete executor;
4. read back the execution receipt;
5. surface attempted/succeeded/failed/skipped counts;
6. surface pre/post free bytes and strongest supported reclaim verification;
7. transition the scenery to the result/next residual action.

Do not add a second confirmation dialog merely to repeat the same consent. A changed manifest, failed/stale preflight, or other fail-closed identity change may invalidate the action and require returning to the relevant gate.

Quarantine approval is not permanent-delete authority. Do not reuse the old `APPROVE_QUARANTINE` receipt as deletion permission.

### 3.5 No fake deletion from ambiguous evidence

`UNKNOWN`, `HUMAN_REVIEW`, `PROTECTED`, and `KEEP_PROVEN` remain excluded from permanent deletion unless the canonical evidence/disposition pipeline legitimately changes their state. The UI must make progress frictionless without bypassing evidence.

## 4. Cursor / scenery coherence contract

The visual cursor must never claim a position different from the user's pointer modality.

1. Track input modality explicitly: pointer vs keyboard/focus.
2. During pointer modality, reticle position changes only from pointer coordinates. `focusin` must not snap the pointer reticle to a control center.
3. Keyboard focus may use an authored focus indicator/cartouche, but it is not the physical-pointer reticle.
4. On scene/camera transitions, either keep the reticle at the last physical pointer coordinates or hide it until the next pointer event. Never teleport it to newly-focused DOM geometry.
5. Range marquee begins only from an explicitly eligible atlas/map surface and only after a drag threshold. A simple click must not enter `FRAME RANGE`.
6. Interactive decision/chrome elements must be excluded from map-range gesture capture.
7. No scene transition may leave stale cartouche/cursor semantics from the prior target.

## 5. Scene-continuity contract

A decision is a transition, not a receipt screen.

- Preserve the selected evidence anchor while moving between gates for the same item.
- When an item is completed/deferred, transition to the next actionable item without requiring the operator to rediscover the queue manually.
- Compass, chamber, inspector, camera, and cursor/cartouche must agree on the same current scene.
- The active scene must be visually dominant; the previous scene may remain as context, not as a competing active surface.
- Avoid arbitrary modal jumps. The transition should be spatially authored from the user's current target into the next target.
- Reduced-motion mode must preserve the same logical transition with motion removed, not skip navigation state.

## 6. P83 verification gates

Inherited green claims are hypotheses.

Before implementation:
- refresh main, UI PR heads, open review threads, and the current deletion-repair head;
- reproduce or disprove DUX-01 through DUX-06 against the exact implementation floor;
- record any drift from this plan before changing code.

After implementation:
- verify the bridge response actually changes after each completed intent;
- verify no stale `Permanent deletion is not implemented` copy survives on a path where the merged delete engine is available;
- verify the UI never exposes deletion from non-eligible evidence.

## 7. P82 measure -> critique -> refine loop

Do not stop at a plausible patch.

Run at least these behavioral probes and iterate on failures:

### Decision progression
- UNKNOWN -> KEEP -> next actionable item/scene, no same-gate loop.
- UNKNOWN -> REVIEW_LATER -> next actionable item/scene.
- UNKNOWN -> RESCAN -> progress -> authoritative readback -> next derived scene.
- HUMAN_REVIEW -> DECLARE_REGENERABLE_CONTRACT -> authoritative evidence refresh -> next derived scene.
- RECLAIM_PROVEN -> delete-ready -> DELETE_PERMANENTLY -> execution receipt/result scene.

### Pointer coherence
- Pointer stationary while clicking a control that receives focus: reticle must not jump to element center.
- Scene/camera transition with stationary pointer: reticle displacement <= 2 CSS px or reticle hidden until next pointermove.
- Simple click on non-range control: no `FRAME RANGE` cue/marquee.
- Deliberate drag on eligible map surface beyond threshold: range marquee works.

### Visual continuity
Exercise desktop, laptop, phone/narrow layout, reduced motion, and forced colors using the repository's existing browser-proof mechanism. Capture before/after state transitions, not only static home screenshots.

## 8. P01 durability requirements

This failure family is systemic and must not return as a chat-only correction.

Implementation must leave durable guards for:

- scene-model parity between typed state and rendered path steps;
- bridge post-decision advancement;
- pointer reticle modality ownership;
- range-drag eligibility/threshold;
- stale deletion-capability copy;
- destructive-action binding to deletion-specific approval + fresh preflight + receipt/readback.

Prefer repository tests/validators that fail when these contracts drift.

## 9. P04 execution graph

This lane is intentionally serial where authority overlaps:

```text
refresh provider truth
  -> establish integration floor
  -> reproduce DUX defects
  -> unify transition authority
  -> fix bridge advancement
  -> fix pointer/range gesture ownership
  -> integrate deletion-specific UI path
  -> focused tests
  -> full suite
  -> live browser self-falsification
  -> integrate exact validated head
  -> operator acceptance of the public UX
```

Parallel work is allowed only for independent proof lanes (for example, browser pointer regression probes vs pure Python transition tests) once the shared transition contract is fixed.

## 10. Integration boundary with the live deletion sprint

The currently running local delete-to-done sprint owns real Temp deletion and filesystem proof. This UX lane must not distract it into UI work or redefine its terminal gate.

This UX lane consumes the deletion engine after refreshing whatever repair/integration head the deletion sprint produces. If that head has not landed yet, continue all independent UX repairs and leave the final delete-UI binding as the only dependency.

## 11. Expected implementation owners

Reuse existing owners before adding mechanisms:

- `src/filesteward/visualization/decision_flow.py`
- `src/filesteward/review_bridge.py`
- `src/filesteward/visualization/decision_chamber.py`
- `src/filesteward/visualization/experience.py`
- `src/filesteward/visualization/interaction.py`
- existing deletion package under `src/filesteward/deletion/`
- existing tests for decision flow, bridge HTTP, interaction, chamber, and deletion

Do not add a second state machine, second deletion executor, generic recursive delete path, or separate router.

## 12. Acceptance / proof gates

The lane is not complete because buttons exist or a screenshot looks better.

PASS requires:

- one authoritative scene model;
- no same-gate loop after a completed decision;
- automatic next-subsection/item progression;
- physical pointer and visual reticle remain coherent;
- range marquee cannot hijack ordinary clicks;
- deletion UI uses the deletion-specific manifest/approval/preflight/executor/receipt path;
- one deliberate destructive commit gesture, no redundant confirmation theater;
- synthetic deletion UI integration proof;
- focused tests + full suite green;
- browser self-falsification across required view/motion modes;
- exact commit/provider state reported;
- no claim of live deletion from this lane unless the separate live runtime evidence actually exists.

## 13. Forbidden shortcuts

- Do not solve this by adding explanatory copy while keeping the same state loop.
- Do not let JavaScript invent evidence/disposition/authorization.
- Do not let a persisted decision be visually treated as completion unless its effect/readback supports that state.
- Do not bind permanent deletion to the quarantine approval artifact.
- Do not move the reticle from focus geometry while pointer modality is active.
- Do not widen deletion eligibility.
- Do not block the live deletion sprint on this UX work.

## 14. Canonical traceability + integration seam

The following artifacts are not successor planning. They are part of this sprint's execution contract:

- `plans/active/DECISION-TO-DELETION-UX-TRACEABILITY-2026-10-06.md`
- `plans/active/DECISION-TO-DELETION-UX-TRACEABILITY-2026-10-06.json`
- `docs/agent/DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md`
- `docs/handoff/DECISION-TO-DELETION-UX-LOCAL-HANDOFF-2026-10-06.md`

### Integration decision

The implementation branch is `feature/decision-to-deletion-ux-20261006`, created from refreshed current `main` after this governance contract lands.

The complete PR #17 UI lineage is merged into that branch with `--no-ff --no-commit`; it is **not** rebuilt by selective cherry-pick and the implementation PR does **not** target PR #17.

Conflict authority is already decided in the integration-seam document. The local agent is not authorized to replace it with a different graph strategy.

The seam must preserve current main deletion/safety authority while carrying the complete UI lineage:

- current main / this contract win safety/governance;
- PR #17 wins the visualization/review product baseline;
- `cli.py` is an additive manual reconciliation preserving `review` plus `delete-manifest`, `delete-preflight`, `delete-approve`, and `delete-execute`;
- quarantine approval and deletion approval remain distinct domains;
- product version uses the UI lineage floor and the repository-owned visual-feature versioning gate, never main's stale `0.1.0`.

### Acceptance ownership

UX-T01 through UX-T22 in the traceability matrix are the terminal acceptance ledger. A green implementation PR that leaves a required row unproved is incomplete.

## 15. Delegation topology — judgment stays remote, execution stays local

This section is normative.

The local agent is a **bounded execution engine**, not a sprint designer, product judge, or integration strategist.

Authority is partitioned as follows:

| Artifact | Authority | May local agent reinterpret it? |
|---|---|---|
| `DECISION-TO-DELETION-UX-P04-2026-10-06.md` | product/sprint judgment, scope, invariants, intended outcomes | **NO** |
| `DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md` | resolved graph/integration/conflict judgment | **NO** |
| `DECISION-TO-DELETION-UX-TRACEABILITY-2026-10-06.md/.json` | acceptance semantics and proof ceiling | **NO** |
| `DECISION-TO-DELETION-UX-LOCAL-HANDOFF-2026-10-06.md` | mechanical execution projection | not an authority source |

### Local-agent responsibilities

The local agent **does**:
- refresh repository/provider/local truth;
- create the prescribed branch/worktree;
- perform the prescribed merge;
- resolve only conflicts whose authority is already specified by the integration seam;
- implement the canonical requirements;
- run tests/validators/browser probes;
- diagnose failures mechanically against the named acceptance row;
- repair within the already-owned scope;
- preserve artifacts and evidence;
- push/open/update/integrate when the canonical gates permit it;
- return evidence keyed to UX-T01..UX-T22.

The local agent **does not**:
- redesign the product journey;
- redefine what "frictionless" means;
- choose a different integration graph;
- invent a different conflict policy;
- weaken or strengthen deletion authority;
- reinterpret acceptance rows;
- add new terminal gates;
- convert a proof failure into a requirement change;
- decide that a canonical requirement is "unnecessary", "too risky", "future work", or "out of scope".

### Unspecified judgment rule

If execution reaches a genuinely material judgment that is **not resolved** by the canonical plan, integration seam, traceability ledger, current repository contracts, or refreshed provider truth, the local agent must:

1. complete every independent mechanical step;
2. preserve the exact evidence;
3. return `BLOCKED_JUDGMENT_GAP` with the smallest unresolved decision;
4. **not invent the missing judgment locally**.

A normal implementation choice within an already-resolved contract is not a judgment gap.

### Handoff role

The handoff is intentionally thin. It points the agent at canonical judgment and tells it what mechanical sequence to execute. If handoff prose and a canonical artifact differ, the canonical artifact wins.

This separation is itself a P04 acceptance gate. A future handoff that restates or mutates product/integration judgment is a regression.
