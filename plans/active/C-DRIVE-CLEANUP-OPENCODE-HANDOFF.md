# OpenCode Handoff — Execute FileSteward Phase 1-4 Only

You are the local implementation agent for FileSteward.

You are **not** a cleanup judgment authority.

## Mission

Implement Phase 1-4 exactly as specified by the tracked FileSteward cleanup plan, using synthetic/temp fixtures only.

Do not perform a real `C:\` scan.

Do not apply, quarantine, delete, or approve any real file action.

## Read in this exact order

1. `AGENTS.md`
2. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
3. `README.md`
4. `plans/active/C-DRIVE-CLEANUP-P04.md`
5. `plans/active/C-DRIVE-CLEANUP-P04.plan.json`

If any of those files is missing, unreadable, contradictory, or materially stale relative to provider truth, STOP and report the exact conflict. Do not reconstruct missing rules from memory.

## Execution posture

- Reuse the checked-out plan branch when it is clean and still at the operator-provided floor.
- If the working tree contains unrelated/unknown changes, STOP. Do not stash, reset, clean, or overwrite them.
- Refresh provider/repository truth before mutation.
- Do not work on `main`.
- Execute lanes L0 -> L1 -> L2 -> L3 -> L4 in order.
- The accepted dependency graph width is 1. Do not invent parallel subagents or parallel writers.
- Commit bounded coherent work as you progress.
- Never merge without explicit operator instruction.

## Judgment prohibition

The following are NOT implementation shortcuts:

- "looks disposable"
- "probably generated"
- "old enough"
- "large enough"
- "safe installer"
- "duplicate-looking"
- "unlikely important"
- "AI confidence is high"

These phrases cannot justify `RECLAIM_PROVEN`.

When semantic meaning or operator preference is required, implement/emit `HUMAN_REVIEW`.

When evidence is technically incomplete, implement/emit `UNKNOWN`.

When protection applies, implement/emit `PROTECTED`.

Do not repeatedly reason about a human-review item until you convince yourself to reclaim it.

## Implementation requirement

Do the work. Do not return a new broad design as a substitute for implementation.

You may make a bounded correction when:
- repository evidence proves the plan's path/name assumption is wrong; or
- a test exposes a real contract defect.

When that happens:
1. preserve the safety intent;
2. make the smallest correction;
3. record it in the final report;
4. rerun the owning gates.

Do not simplify away safety requirements because they are inconvenient.

## Required lanes

### L0
Package + CLI + model/state floor.

### L1
Streaming inventory + Windows traversal boundaries + protection semantics.

### L2
Deterministic disposition gates + independent adversarial downgrade.

### L3
Read-only orchestration + artifacts + honest reclaim projection.

### L4
S1-S14 integration proof + mutation snapshot + CLI smoke + critique/refactor.

The detailed owned/forbidden surfaces and gates are canonical in the P04 plan and JSON manifest.

## Mandatory proof

Before declaring Phase 1-4 complete:

- run the focused tests required by the lanes;
- run the complete S1-S14 matrix;
- run `python -m pytest -q`;
- prove the intended CLI entry point executes;
- run `git diff --check`;
- prove synthetic analysis did not mutate the fixture tree;
- confirm no real `C:\` traversal occurred;
- confirm no private live artifacts are tracked;
- refresh git/provider state;
- commit and report the exact SHA.

A skipped platform-specific test must have a precise reason and may not be reported as proven.

## Hard stop

After L4, STOP.

Do not perform Phase 5.

Your final response may propose the exact bounded read-only Phase 5 command, but must not run it.

Required final states:

```text
LIVE AUDIT STATE: NOT RUN
OPERATOR APPROVAL STATE: NOT GRANTED
APPLY STATE: NOT RUN
RECLAIM STATE: 0 BYTES VERIFIED
```

## Final report

Report:

- completed work;
- created/modified files;
- validation/proof results;
- skipped checks and why;
- unresolved gaps/risks;
- important artifact/log/report paths;
- branch, commits, push/PR state, and git status;
- deployment/production state if applicable;
- exact proposed Phase 5 read-only command;
- then STOP.

Evidence before confidence. The operator owns judgment.
