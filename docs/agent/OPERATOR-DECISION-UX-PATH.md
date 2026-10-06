# Operator Decision UX Path — progression and destructive-action contract

This contract governs public Decision Chamber / Atlas interaction changes.

## Core rule

A completed operator decision is a state transition, not a static receipt. After authoritative persistence/effect readback, FileSteward must advance to the next valid scene, gate, or item without forcing the operator to manually rediscover the continuation.

The UI must use the repository's canonical decision/evidence/authorization owners. Presentation code may animate state; it may not invent state.

## Deletion rule

When permanent deletion is available, the public UI must use the repository-owned deletion manifest, deletion-specific approval, fresh preflight, bounded executor, execution receipt, and reclaim verification.

One deliberate **DELETE PERMANENTLY** commit on an exact visible eligible scope may serve as the irreversible confirmation and materialize the required approval artifact. Do not add redundant conversational/UI confirmation theater for the same unchanged scope.

Quarantine approval does not authorize permanent deletion.

## Pointer rule

The physical-pointer reticle belongs to pointer coordinates. Keyboard/focus presentation must not teleport that reticle. Range selection is an explicit map-drag gesture, not a default consequence of ordinary non-chrome clicks.

## Durable owner

The active implementation/proof plan is `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.md` and its machine-readable sibling.

## Action → scene → impact rule

Every operable visible action is a promise:

```text
current canonical context
 -> truthful action
 -> scene/context transition
 -> named impact
 -> feedback/readback
 -> continuation
```

The public UI must not render an inviting action verb whose activation does not produce the promised effect.

### EXPLORE

`EXPLORE` is reserved for explicitly exploratory environments and effects. It is not a generic fallback for unknown targets, unselected evidence, empty canvas, or actions whose real effect is focus/filter/decision/authorization/deletion.

Unknown or stale action projection fails closed. Do not fabricate an operable fallback.

### Context continuity

The cursor/cartouche/action projection is derived from canonical scene, selection, evidence disposition, gate, authorization, target, destination, and impact. When any owning context changes, the prior cue is invalid and must be recomputed or hidden.

Presentation remains a projection; it does not become another authority owner.

### Scene impact

Every scene must declare what impact it delivers and how the operator continues. FileSteward's primary through-line is:

```text
classify -> decide -> authorize -> reclaim -> verify
```

Exploration/orientation supports that journey rather than replacing it.

Classification and decision results must remain available to later filterable views and decision queues after authoritative readback.
