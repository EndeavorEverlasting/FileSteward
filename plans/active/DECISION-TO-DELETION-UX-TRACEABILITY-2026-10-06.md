# Decision-to-Deletion UX Traceability Matrix — 2026-10-06

**Sprint:** `FILESTEWARD-DECISION-TO-DELETION-UX-20261006`  
**Authority:** P04 acceptance factoring + P83 claim verification + P82 measure/critique/refine  
**Status at creation:** remote contract implemented; product implementation not yet performed  
**Canonical plan:** `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.md`

This matrix is the acceptance ledger. A local agent may not replace a row's proof gate with a weaker proxy such as "button exists", "unit tests green", "looks right", or "PR ready".

| ID | Requirement / defect | Primary owner(s) | Required proof | PASS condition | Initial state |
|---|---|---|---|---|---|
| UX-T01 | One typed scene authority; eliminate DUX-01 split around `RESOLVE` | `visualization/decision_flow.py`, `scene_surface.py`, Decision Chamber renderer | pure transition tests + rendered-path parity test | every rendered journey scene is representable by the canonical typed scene model; no browser-only semantic scene | DESIGNED / UNPROVEN |
| UX-T02 | Canonical reducer owns intent transition; close DUX-03 | `decision_flow.py`, `review_bridge.py` | unit test spies/fixtures proving bridge delegates transition semantics to reducer or equivalent single owner | bridge does not duplicate/reinvent allowed-intent transition rules | DESIGNED / UNPROVEN |
| UX-T03 | KEEP advances instead of reopening same gate | `review_bridge.py`, queue/next-target resolver, chamber | bridge HTTP test + browser journey | persisted KEEP returns an explicit different next target or terminal/queue-empty state; same item/gate cannot remain active as unresolved | DESIGNED / UNPROVEN |
| UX-T04 | REVIEW_LATER advances | same as UX-T03 | bridge HTTP test + browser journey | deferral is persisted and immediate queue advances without manual rediscovery | DESIGNED / UNPROVEN |
| UX-T05 | RESCAN completes effect/readback then advances from new evidence | canonical observation path + bridge | synthetic effect/readback integration test | UI reports pending while observation is incomplete; after authoritative readback, next scene derives from refreshed evidence, not stale presentation state | DESIGNED / UNPROVEN |
| UX-T06 | DECLARE_REGENERABLE_CONTRACT uses canonical evidence owner then advances | contract/evidence owner + bridge | synthetic contract/evidence integration test | presentation code never promotes disposition; authoritative refreshed evidence determines next scene | DESIGNED / UNPROVEN |
| UX-T07 | Post-decision response explicitly identifies continuation | `review_bridge.py` response contract | unit/schema test | response contains explicit current/next scene, gate, item (nullable as appropriate), last transition, and execution state; browser need not infer next subsection | DESIGNED / UNPROVEN |
| UX-T08 | No same-gate ceremonial loop after an authoritative completed decision (DUX-02) | bridge + chamber | regression test covering all completed non-pending intents | a completed decision cannot yield the identical active item+gate+scene tuple unless response says it is still pending and why | DESIGNED / UNPROVEN |
| UX-T09 | Permanent-delete capability copy is current (DUX-04) | interaction copy, scene surface, chamber | string/semantic regression + browser proof | no reachable delete-capable scene states "Permanent deletion is not implemented"; blocked states explain the actual unmet gate | DESIGNED / UNPROVEN |
| UX-T10 | One deliberate exact-scope DELETE PERMANENTLY gesture | chamber/bridge deletion adapter + `deletion/*` | synthetic end-to-end UI-to-executor integration | one activation on unchanged exact eligible scope materializes `filesteward.delete-approval/v1`, executes repository executor, reads receipt and reclaim result; no redundant same-scope confirmation | DESIGNED / UNPROVEN |
| UX-T11 | Destructive binding remains deletion-specific | `deletion/approval.py`, bridge adapter | negative tests | quarantine `ApprovalRecord` / `APPROVE_QUARANTINE` can never satisfy permanent-delete authorization | DESIGNED / UNPROVEN |
| UX-T12 | Noneligible evidence cannot expose executable delete | decision flow + interaction projection | parameterized UNKNOWN/HUMAN_REVIEW/PROTECTED/KEEP tests + browser check | DELETE PERMANENTLY absent/locked for every non-`RECLAIM_PROVEN` disposition; presentation cannot promote evidence | DESIGNED / UNPROVEN |
| UX-T13 | Pointer modality owns physical reticle; close DUX-05 | `visualization/experience.py` | browser pointer/focus probe | with pointer stationary through click/focus transition, reticle moves <= 2 CSS px or hides until next pointer event; `focusin` cannot teleport it | DESIGNED / UNPROVEN |
| UX-T14 | Keyboard focus has its own authored indication | experience/interaction layer | keyboard-only browser journey | keyboard user receives focus/cartouche feedback without impersonating physical pointer coordinates | DESIGNED / UNPROVEN |
| UX-T15 | Range marquee cannot hijack ordinary clicks; close DUX-06 | `visualization/experience.py` | browser click/drag probes | simple click does not enter `FRAME RANGE`; gesture arms only on explicit eligible Atlas surface after movement threshold | DESIGNED / UNPROVEN |
| UX-T16 | Deliberate eligible range drag still works | experience layer | browser drag probe | drag beyond threshold on eligible surface renders range marquee and cleans it up on pointerup/cancel | DESIGNED / UNPROVEN |
| UX-T17 | UI/deletion integration preserves current delete CLI and safety owners | integration seam conflict resolution | CLI tests + source assertions + full suite | `delete-manifest`, `delete-preflight`, `delete-approve`, `delete-execute` remain available with current safety semantics while `review` is added/preserved | DESIGNED / UNPROVEN |
| UX-T18 | Stale UI AGENTS safety language cannot overwrite current main | integration seam + governance | exact file readback | merged/integration head retains current permanent-delete contract and `OPERATOR-DELETE-PATH.md` / `OPERATOR-DECISION-UX-PATH.md` requirements; stale "permanent deletion outside MVP" text absent | DESIGNED / UNPROVEN |
| UX-T19 | Product-version lineage is reconciled, not silently regressed | `pyproject.toml`, `__init__.py`, versioning gate | repository P130/version guard | implementation head contains UI lineage version floor and repository-owned visual-feature bump; no downgrade to main's stale `0.1.0` identity | DESIGNED / UNPROVEN |
| UX-T20 | Cross-mode scenery continuity | chamber + experience + cinematic + shell | live browser self-falsification | desktop, laptop, narrow/phone, reduced-motion, and forced-colors all preserve the same logical next-target progression | DESIGNED / UNPROVEN |
| UX-T21 | Integration ancestry contains both current main safety/deletion line and complete UI lineage | git graph | `git merge-base --is-ancestor` / provider compare evidence | exact implementation head descends from refreshed main and includes PR #17 head via the defined merge seam; no cherry-picked partial reconstruction | DESIGNED / UNPROVEN |
| UX-T22 | P82 iteration evidence is durable | proof report under ignored/local or tracked non-private docs as appropriate | before/after probe results + failure/retry ledger | failures found during behavioral probes are diagnosed, repaired, rerun, and preserved; first-pass green is not assumed | DESIGNED / UNPROVEN |

| UX-T23 | action scene impact projection complete | `interaction.py + scene_surface.py + decision_flow.py` | projection unit tests + schema/validator | every operable cue binds source scene, destination scene/context, impact kind, continuation, and freshness fingerprint | DESIGNED / UNPROVEN |
| UX-T24 | explore reserved semantics | `interaction.py + experience.py` | parameterized projection tests + browser target probes | EXPLORE appears only for explicit exploration scenes/effects; unselected evidence/default canvas cannot receive generic EXPLORE | DESIGNED / UNPROVEN |
| UX-T25 | unknown action fails closed | `interaction.py` | negative unit/property tests | unregistered target/action cannot become an operable custom action cue and cannot silently fall back to EXPLORE | DESIGNED / UNPROVEN |
| UX-T26 | context projection freshness | `interaction projection + experience.py + chamber` | scene/selection/gate/auth mutation tests + browser probe | scene/selection/disposition/gate/authorization/target/result changes invalidate stale cue; reticle recomputes or hides before next action | DESIGNED / UNPROVEN |
| UX-T27 | scene primary impact contract | `scene_surface.py + harness contracts` | contract validator + scene table tests | every canonical scene declares purpose, primary impact, success evidence and continuation policy; receipt-only scenes are terminal or expose continuation | DESIGNED / UNPROVEN |
| UX-T28 | label effect truth | `interaction projection + renderers` | browser click trace + accessible-label assertion | visible/accessibility label names the immediate executable effect and observed activation matches it | DESIGNED / UNPROVEN |
| UX-T29 | classification compounds filterable views | `classification/decision owner + filters/scene counts/queues` | synthetic decision/classification readback + filter/queue integration test | authoritative classification/decision result immediately appears in relevant filters/counts/queues without presentation-only mutation | DESIGNED / UNPROVEN |
| UX-T30 | supporting scenes preserve product throughline | `scene navigation + chamber/atlas` | browser journey across exploration/orientation -> decision -> reclaim | exploration/orientation never becomes a dead-end scenic loop; a visible truthful continuation leads toward classify/decide/authorize/reclaim/verify | DESIGNED / UNPROVEN |

## Required evidence bundles

### Pure / repository proof
- focused tests for decision flow, bridge, deletion adapter, interaction, chamber;
- CLI regression covering both `review` and the four permanent-delete commands;
- full `pytest` suite;
- repository versioning guard;
- `git diff --check`;
- exact branch/HEAD/status;
- ancestry proof for UX-T21.

### Browser proof
For each supported mode, preserve a compact trace with:
- starting item / disposition / authorization;
- committed intent;
- bridge response current+next tuple;
- scene after render;
- pointer modality + pre/post coordinates when applicable;
- resulting actionability.

Modes:
- desktop;
- laptop;
- narrow/phone;
- `prefers-reduced-motion`;
- forced colors.

### Synthetic delete proof
Use only synthetic/private-safe fixture data in the UX lane. Prove:
```text
visible exact eligible scope
 -> fresh preflight PASS
 -> DELETE PERMANENTLY
 -> deletion-specific approval artifact
 -> bounded executor
 -> receipt
 -> reclaim readback
 -> result/residual scene
```

The UX lane must not claim the independent live Temp deletion result unless it reads actual live runtime evidence from that other lane.

## P83 claim rule

Every row is one of:
`UNPROVEN -> IMPLEMENTED -> LOCALLY_VALIDATED -> INTEGRATION_VALIDATED -> MERGED`.

Rows involving live browser behavior require browser proof before `INTEGRATION_VALIDATED`.
Rows involving deletion side effects in this UX lane are synthetic-only unless explicitly supplied with live runtime evidence.

## P82 retry rule

A failed row does not get waived by another green row. Diagnose the owning defect, repair within scope, rerun the smallest failed gate, then rerun all dependent gates before promotion.


## Action → scene → impact evidence bundle

For UX-T23..UX-T30 preserve, per tested interaction:

```text
source_scene/context_revision
target_id/kind
projected_action + visible/accessibility label
destination_scene/context_revision
impact_kind
observed effect/readback
continuation
context_fingerprint before/after
```

At least one negative trace must prove that an unregistered action does **not** become `EXPLORE`, and at least one browser trace must prove that an old cue disappears/recomputes after a scene-context change.
