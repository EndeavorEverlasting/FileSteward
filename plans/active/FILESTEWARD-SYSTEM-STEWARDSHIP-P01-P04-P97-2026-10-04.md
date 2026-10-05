# FileSteward System Stewardship — P01 / P04 / P97 Successor Plan

**Plan ID:** `FILESTEWARD-SYSTEM-STEWARDSHIP-P01-P04-P97-20261004`  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Baseline:** draft PR #15 head `925aa8e6351af1ccc69e68c98afcd5b253ed2c91` (`0.5.0`)  
**Current operator disposition:** V4-D is a meaningful improvement, **not live-accepted**.  
**Canonical reliability evidence:** Prompt Scratch Agent Reliability Event Ledger `INC-2026-10-04-013` and `INC-2026-10-04-014`.

## Execution frame

### Owned in this harness lane

- P97 system-stewardship prior-art disposition;
- P01 machine-readable harness contracts;
- P01 artifact registry;
- deterministic harness validator and focused tests;
- P04 dependency graph / collision boundaries / successor proof gates.

### Forbidden in this harness lane

- changing the active PR #15 UI implementation;
- merging or undrafting PR #15;
- F7;
- permanent deletion;
- evidence/disposition promotion;
- approval invention;
- installing a background scheduler on the operator workstation;
- creating a second mutable reliability ledger.

## Operator truths preserved

1. **The scene is the tutorial.**
2. UNKNOWN and HUMAN_REVIEW must become obvious action surfaces that open truthful decision scenes.
3. The reticle + contextual assistant/legend must remain visually above review/chamber layers.
4. Hover/focus/touch on Decision Path steps 1–6 must preview consequence, prerequisites and blocked reason.
5. Header/title/metric cards/camera/status/footer are not inert chrome; meaningful surfaces must open scenes or explain state.
6. FileSteward needs a favicon/product identity and a less generic typography/chrome treatment.
7. The footer should become a cinematic status ticker, not a Matrix/hacker-terminal trope.
8. Classification must be standardized and not rely on color alone.
9. Low storage must become a measured/fresh warning surface, not hidden baseline text.
10. Future system stewardship includes RAM/CPU/disk/sensor observations and recommendations.
11. Recurring housekeeping is user-controlled local/private state.
12. **Development profile recurring housekeeping defaults ON. Public/product profile remains opt-in until proven.**
13. Scheduler authority is wake/run selection only. It may not promote evidence, approve, or permanently delete.
14. A failed run never silently retires recurrence.

## P04 dependency graph

### H0 — P01 Harness Stabilization
**Status:** IMPLEMENTED in this successor branch; integration/local full-suite proof remains pending.

Owns:
- `harness/contracts/system-health-snapshot.v1.json`
- `harness/contracts/housekeeping-schedule.v1.json`
- `harness/contracts/interaction-scene-acceptance.v1.json`
- `harness/artifact-registry.v1.json`
- `scripts/validate_harness_contracts.py`
- `tests/test_harness_contracts.py`

Gate:
- JSON parses;
- standalone validator PASS;
- focused tests PASS;
- later full FileSteward suite on local runtime.

### U1 — V4-E Decision Scene Actionability
**Dependency:** H0 acceptance contract.

Owns:
- current interaction grammar extension;
- status/metric/title/path/camera scene entrypoints;
- reticle/cartouche top-layer behavior;
- browser edge-case sampler;
- favicon/identity hook;
- low-storage warning scene rendering from typed health data.

Must prove:
- UNKNOWN/HUMAN_REVIEW open legal decision scenes;
- UNAPPROVED either opens APPROVAL when eligible or explains lock;
- PROTECTED explains the block;
- top metric cards open their respective scenes;
- product/decision-map title navigation is intentional;
- Decision Path hover/focus previews impact;
- cursor assistant stays topmost;
- keyboard/touch parity;
- no color-only semantics;
- private/live operator comprehension pass.

**Collision note:** shell/experience/decision-chamber work is one UI mutation owner. Do not split cosmetic sublanes across workers that touch the same renderers.

### M1 — Read-only System Health Observer
**Dependency:** H0 health contract.  
**Parallel-safe with U1** if it owns new health modules/tests only.

First scope:
- storage total/free/used + freshness;
- RAM total/available/used + freshness;
- optional CPU/disk-busy measurements when a stable local provider is available;
- no cleanup judgment and no mutation.

Output:
- local/private `system-health-snapshot/v1` artifact under ignored runtime state.

### M2 — Advisory / Warning Engine
**Dependency:** M1.

Owns:
- configurable threshold evaluation;
- `NORMAL/CAREFUL/WARNING/CRITICAL/UNKNOWN`;
- warning event/history artifact;
- recommendations only.

Must never:
- promote `CleanupDisposition`;
- approve;
- quarantine/delete.

### S1 — Windows Scheduler Adapter
**Dependency:** H0 schedule contract.  
**Parallel-safe with U1/M1** after contract freeze if it owns separate scheduler modules/tests.

Selected mechanism:
- Windows Task Scheduler;
- idle/power-aware conditions;
- no short-interval battery polling;
- explicit registered-task readback;
- no overlapping run storm.

Development profile:
- recurring housekeeping enabled by default.

Product profile:
- disabled until user opts in.

First allowed scheduled actions:
- `SCAN`
- `RECOMMEND`

`QUARANTINE_APPROVED` remains gated on the existing apply/quarantine program.

### S2 — Local Settings / Schedule Scene
**Dependencies:** S1 + M2.

Owns:
- local/private settings store;
- immersive toggle scene;
- cadence/idle/power options;
- next-run/last-run state;
- explicit readback after registration changes.

### Q1 — Approved Quarantine Cadence
**Dependencies:** manifest-bound approval + quarantine/apply + retention policy.

May stage only already-approved quarantine work.

Permanent deletion remains a later separate policy/program and is forbidden here.

### R1 — P124 Structural Readability
**Dependency:** U1 behavior characterized and green.

Rank actual 0.5.x/0.6.x hotspots. Refactor only behavior-preserving ownership seams; do not use P124 to redesign product behavior.

## Parallel capability disposition

Graph width after H0 is at least 2: U1, M1 and S1 can be dependency-ready with non-overlapping mutation owners.

This ChatGPT runtime does not possess the operator's Windows/Cursor execution host, so it must **not** claim parallel local dispatch. Local dispatch should use the repository/operator's proven agent runner when available. If unavailable, record `PARALLEL EXECUTION: DEGRADED` rather than pretending serial work is parallel proof.

## Acceptance / proof ladder

`designed -> contract-encoded -> isolated-validated -> local-full-suite -> browser/live-observed -> operator-accepted -> committed -> pushed -> integrated -> deployed/registered -> production-observed`

No rung may be inferred from a lower rung.

## Current next action

Local owner should first pull this successor harness branch in an isolated worktree, run:

```powershell
python scripts/validate_harness_contracts.py
python -m pytest -q tests/test_harness_contracts.py
python -m pytest -q
```

If green, preserve this harness contract independently from PR #15 and then execute U1/M1/S1 according to collision ownership.
