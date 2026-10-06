# Local Agent Handoff — Decision-to-Deletion UX — 2026-10-06

## MODE

EXECUTE. This is not a planning assignment.

P04 has already resolved scope, factoring, and the integration seam.
P83 requires inherited claims to be reproduced/disproved.
P82 requires measure -> critique -> repair -> rerun until the acceptance ledger closes.

## Repository

```text
repo: EndeavorEverlasting/FileSteward
canonical checkout: %USERPROFILE%\dev\FileSteward
implementation branch: feature/decision-to-deletion-ux-20261006
target: main
```

## Read first

1. `AGENTS.md`
2. `docs/agent/OPERATOR-DECISION-UX-PATH.md`
3. `docs/agent/OPERATOR-DELETE-PATH.md`
4. `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.md`
5. `plans/active/DECISION-TO-DELETION-UX-TRACEABILITY-2026-10-06.md`
6. `docs/agent/DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md`

If current remote truth moved, refresh it; do not replace these judgment decisions with a new plan.

## Execution frame

Owned:
- PR #17 UI lineage integration onto current main;
- canonical scene/decision progression;
- bridge continuation state;
- pointer modality + range gesture;
- synthetic public-UI permanent-delete binding;
- regression tests and browser proof.

Forbidden:
- widening deletion eligibility;
- generic recursive delete;
- second state machine;
- second HTTP bridge;
- second deletion executor;
- quarantine approval used as delete authority;
- interruption/redefinition of the independent live Temp delete-to-done sprint.

## Integration first

Refresh main and PR #17 provider truth.

Create an isolated worktree/branch from current main:

```powershell
git fetch origin --prune
git switch main
git pull --ff-only
git worktree add "$env:USERPROFILE\dev\worktrees\FileSteward\decision-to-deletion-ux-20261006" -b feature/decision-to-deletion-ux-20261006 origin/main
```

In the worktree, merge the entire current PR #17 head:

```powershell
git merge --no-ff --no-commit origin/design/u1-brand-home-schedule-seam-20261005
```

Resolve conflicts exactly per `docs/agent/DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md`.
Do not improvise conflict authority.

Before committing the seam, verify:
- current main delete contract language survives in `AGENTS.md`;
- `cli.py` contains `review` plus all four delete commands;
- root quarantine approval and `deletion/approval.py` remain separate;
- UI visualization/review bridge lineage is present.

Commit the seam as a distinct integration commit.

Then prove both ancestors:
```powershell
git merge-base --is-ancestor origin/main HEAD
if ($LASTEXITCODE -ne 0) { throw "current main is not an ancestor" }

git merge-base --is-ancestor origin/design/u1-brand-home-schedule-seam-20261005 HEAD
if ($LASTEXITCODE -ne 0) { throw "PR17 UI lineage is not an ancestor" }
```

Run full tests once **before feature repair**. Preserve seam failures separately.

## Implement against the traceability ledger

Close UX-T01 through UX-T22. Do not substitute a prose status for proof.

Minimum functional outcomes:

```text
KEEP -> persist -> authoritative readback -> next target
REVIEW_LATER -> persist -> next target
RESCAN -> effect/pending -> authoritative readback -> derived next target
DECLARE_REGENERABLE_CONTRACT -> canonical evidence refresh -> derived next target
eligible DELETE_PERMANENTLY -> delete approval -> fresh preflight -> executor -> receipt/reclaim -> result scene
```

The post-decision bridge response must tell the browser the continuation target explicitly.
The browser must not infer the next subsection.

## Pointer requirements

- track pointer vs keyboard/focus modality;
- pointer reticle moves only from real pointer coordinates;
- `focusin` may not teleport it;
- stationary click/transition: <=2 CSS px reticle movement OR hide until next pointer event;
- range marquee requires eligible Atlas surface + movement threshold;
- a simple click must not activate `FRAME RANGE`.

## Delete requirements

Use the existing `src/filesteward/deletion/**` package.

One exact-scope **DELETE PERMANENTLY** activation is the irreversible confirmation for an unchanged eligible/preflight-PASS scope.

It must bind:
```text
delete-manifest
 -> fresh delete-preflight PASS
 -> filesteward.delete-approval/v1 / DELETE_PERMANENTLY
 -> repository executor
 -> execution receipt
 -> reclaim readback
 -> result/residual scene
```

No second same-scope confirmation modal.
Changed/stale identity fails closed and returns to the actual blocking gate.

## Validation loop

Run focused tests as each row closes.
On failure: diagnose -> repair -> rerun failed gate -> rerun dependent gates.

Before final proof, refresh main again and merge any newly landed deletion repair.

Then run:
- focused decision/bridge/interaction/deletion adapter tests;
- CLI regression for review + delete commands;
- full pytest;
- versioning/P130 visual-feature gate;
- git diff --check;
- browser self-falsification: desktop, laptop, narrow/phone, reduced motion, forced colors.

Preserve a trace for each browser decision journey.

## Integration

Open/update the implementation PR against `main`.

If exact head is green, review threads are resolved, and repository rules allow merge, integrate it rather than stopping at "ready".

Do not claim live Temp reclaim unless the independent deletion lane has actual receipt/free-space evidence available.

## Return contract

```text
CHANGED:
PROVED:
FAILED_AND_REPAIRED:
SKIPPED:
TRACEABILITY:
  UX-T01 ...
  ...
  UX-T22 ...
ARTIFACTS:
BRANCH:
PR:
HEAD:
GIT_STATUS:
MERGED:
LIVE_DELETION_STATE:
NEXT:
```

A row is not closed by intent or implementation alone. Evidence before confidence.
