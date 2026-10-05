# FileSteward Memory Atlas — cinematic visualization v2

**Status:** P95 program-design replacement + P97/Impeccable implementation slice
**Branch:** `design/p95-p97-live-selection-salience-20261004`
**Safety inheritance:** all FileSteward evidence / authorization / no-mutation invariants remain binding.

## Why v1 was falsified

The private F6 browser proof established that the v1 treemap could be technically
correct and still fail the operator. With ~200 peer buckets, the overview
rendered many targets below useful visual size. Selection highlighting improved
state visibility but did not solve the first-frame information architecture.

The failure is therefore structural:

```text
flat 200-node overview
    -> operator hunts microscopic rectangles
    -> select one
    -> inspector explains it
```

The replacement journey is:

```text
bounded dominant-sector overview
    -> operator recognizes a consequential sector
    -> click / Enter performs one spatial dive
    -> selected sector becomes a full-size evidence chamber
    -> full-run treemap remains secondary context
    -> decision inspector appears only after focus
    -> Escape / Back returns spatially to overview
```

## Product register

Impeccable mode: **Operate**, with one earned **Experience** moment.

The tool must remain fast to scan and safe to operate. Cinematic motion is
allowed only where it explains spatial continuity between overview and focus.
The motion is not decoration and does not delay access to evidence.

## Replacement visual world

**Memory Atlas** is hardware/substrate-inspired, not literal RAM and not a claim
about physical disk layout.

- graphite / deep navy substrate
- etched SVG circuit traces as atmosphere only
- crisp module geometry with restrained anodized-metal depth
- cool-blue energy accent reserved for interaction and focus
- large numeric storage values
- no rainbow file-type mosaic
- no generic SaaS card grid
- no tiny text packed into rectangles
- no animation that carries evidence or authorization meaning

The prior v1 prohibition on faux-3D / hardware-like imagery is superseded for
this surface by the operator's explicit redesign brief. The safety distinction
remains: visual material may evoke hardware, but labels must say **storage
sector / evidence group**, never imply actual RAM addresses or physical disk
sectors.

## Presentation state ownership

```text
PresentationModel (evidence truth; unchanged)
        |
        +--> StorageNavigator (all evidence groups)
        |
        +--> MemoryAtlasOverview (top 12 existing nodes only)
        |       no synthetic evidence / no authority
        |
        +--> FocusChamber (one existing selected node)
        |
        +--> ContextTreemap (all nodes, secondary)
        |
        +--> DecisionInspector (focus scene only)
```

No scene may mutate `CleanupDisposition`, `AuthorizationState`, receipt
artifacts, contracts, or reclaim projections.

## First-frame contract

The overview deliberately caps itself at **12 dominant existing evidence
groups**. Remaining groups are represented only by a non-interactive count and
known logical-size summary. They remain individually accessible through the
navigator/search.

This is progressive disclosure, not data deletion.

The overview cards are laid out for readability rather than pretending to be a
physical map. Exact magnitude remains visible as text. The complete treemap
remains available after focus as the full-run magnitude context.

## Motion thesis

One authored focal sequence:

1. user clicks/keyboard-activates a sector;
2. a temporary geometry-matched ghost expands from the source sector toward the
   focus chamber using an exponential ease-out;
3. overview recedes while the focus chamber resolves;
4. SVG substrate traces perform one short charge sweep;
5. inspector becomes available;
6. Escape/back reverses the spatial relationship.

Routine selection inside focus does not replay the full cinematic transition.
It updates the chamber and context map directly.

`prefers-reduced-motion: reduce` removes the animation while preserving the
same overview/focus states and keyboard path.

## P97 / Impeccable disposition

| Mechanism | Source | Disposition |
| --- | --- | --- |
| bounded first frame / progressive disclosure | live F6 falsification + product UX principle | ADOPT |
| spatial continuity / FLIP-style transition | Impeccable motion guidance | ADOPT |
| one authored focal motion, not scattered effects | Impeccable craft floor / animate | ADOPT |
| strong current-item selection | QDirStat / WinDirStat | ADAPT |
| SVG substrate / technically extraordinary transition | operator brief + Impeccable overdrive | ADAPT |
| literal RAM / physical-sector semantics | none | REJECT — visually evocative only |
| direct delete/apply from visualization | storage-analyzer precedent | REJECT |
| 200 peer rectangles as the first frame | FileSteward v1 live proof | REJECT |

## Acceptance

The slice is accepted only when the private real F6 run proves all of:

- overview begins with readable dominant sectors rather than 200 tiny targets;
- overview uses the full decision stage; inspector is deferred until focus;
- top sectors expose name, logical size, state, and path without hover;
- clicking a sector visibly dives into a full-size focus chamber;
- a navigator row outside the top 12 can still be opened directly;
- Escape/back reverses to overview;
- context treemap still exposes the full run after focus;
- decision inspector still preserves first-unresolved-gate dominance;
- keyboard and reduced-motion paths reach the same states;
- no disposition, authorization, contract, receipt, or filesystem mutation occurs.

## Proof ceiling

This v2 slice proves a new presentation/interaction architecture only after
focused tests and the private browser run pass. It does **not** prove true
filesystem hierarchy drill-down. The current F6 large-run model remains a flat
set of persisted buckets (`parent_id=None`). A later multi-resolution evidence
model is required before the focus chamber can truthfully reveal child sectors.
