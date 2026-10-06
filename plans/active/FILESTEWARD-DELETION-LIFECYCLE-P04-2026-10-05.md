# FileSteward Deletion Lifecycle — P04

**Plan ID:** `FILESTEWARD-DELETION-LIFECYCLE-P04-20261005`
**Repository:** `EndeavorEverlasting/FileSteward`
**Provider floor at plan creation:** PR #17 `design/u1-brand-home-schedule-seam-20261005@4c23b8fe88c73a384ebaebd1da121fe6e6575266`
**Stack:** PR #17 -> PR #16 -> PR #15 -> `main@be0406b3047ce07a769fb3f9a14cd6618dbf086e`
**Disposition:** deletion is now an active required product outcome, not an indefinite post-MVP aspiration.

## 1. Operator outcome

Two outcomes have equal priority:

1. **SEE EXACTLY WHAT WILL BE REMOVED** — paths/items, evidence, allocated bytes, projected reclaim, reversibility, approval state, and the consequence of the chosen action must be visible before mutation.
2. **ACTUALLY RECLAIM THE BYTES** — the program must progress beyond read-only analysis and same-volume staging to an explicitly authorized deletion lifecycle with measurable post-action free-space proof.

Interface polish is no longer allowed to indefinitely postpone the deletion path.

## 2. Current truth and supersession

Current implementation at the provider floor proves useful read-only analysis, visualization, manifest-bound QUARANTINE approval, and a localhost review bridge. It does **not** implement filesystem apply or permanent deletion.

The older program rule “permanent deletion is outside the MVP / forbidden” remains a **current implementation safety boundary**, but it is superseded as a roadmap endpoint. P04 now requires a gated permanent-delete phase. No existing code is authorized to delete merely because this plan exists.

The existing approval contract remains QUARANTINE-only until the deletion-specific approval gate below is implemented and proven.

## 3. Critical product distinction: staging is not reclaim

A same-volume rename/move, Recycle Bin placement, or quarantine directory on `C:` can preserve recoverability while reclaiming **zero** usable bytes on that volume until the retained bytes are purged.

Therefore the UI and receipts MUST distinguish:

- **staged/reversible bytes**;
- **source-volume bytes actually reclaimed**;
- **projected reclaim**;
- **verified reclaim after mutation**.

No “cleanup complete” claim may be derived from a quarantine move alone.

## 4. Execution frame

### Owned by this P04 program

- deletion lifecycle phase map;
- exact deletion-manifest contract;
- preflight/revalidation requirements;
- reversible quarantine/restore path;
- explicit permanent-delete authority path;
- execution receipts and reclaim verification;
- collision boundaries and provider-refresh discipline;
- integration with the existing decision surface and scheduler only after the manual path is proven.

### Forbidden until the named gates are proven

- deleting from HUMAN_REVIEW/UNKNOWN merely because an item is large;
- scheduler self-approval;
- scheduler promotion of evidence;
- blanket recursive delete commands over broad roots;
- following symlinks/junctions/reparse points into unenumerated targets;
- permanent deletion of cloud/shared/linked/managed/system-protected content without a dedicated provider-aware contract;
- claiming projected bytes as reclaimed bytes;
- merging/undrafting the existing UI stack merely because this planning branch exists;
- mutating the operator filesystem from this planning lane.

## 5. Source-of-truth inputs

Reuse rather than replace:

- `cleanup-plan.csv` and existing manifest validation;
- `RECLAIM_PROVEN` as the initial recommended-deletion eligibility floor;
- `src/filesteward/approval.py` for current QUARANTINE approval semantics;
- `decision_flow.allowed_intents()` as the UI legality authority;
- the localhost review bridge for operator decisions;
- logical vs allocated-byte evidence already carried by the presentation model;
- the system-stewardship schedule contract for later recurrence, not initial delete authority.

## 6. P04 dependency graph

```text
D0 deletion contract freeze  [THIS PLAN]
       |
       +---------------------------+
       |                           |
D1 exact delete-set visibility    D2 mutation preflight / dry-run engine
       |                           |
       +------------+--------------+
                    |
              D3 delete approval v1
                    |
          +---------+----------+
          |                    |
D4A reversible quarantine   D4B permanent delete
          |                    |
          +---------+----------+
                    |
            D5 execution receipt
                    |
            D6 reclaim verification
                    |
            D7 recurrence / retention
```

D1 and D2 are intentionally parallel after D0 because “see it” and “be able to remove it safely” are equally urgent.

## 7. Lane contracts

### D0 — Deletion contract freeze

**Status:** IMPLEMENTED by this plan branch.

Defines:
- exact item-set identity;
- approval separation;
- mutation/reclaim terminology;
- protected surfaces;
- provider refresh/collision policy;
- proof ladder.

**Gate:** this Markdown + machine-readable plan are provider-read-back from the exact isolated branch.

### D1 — Exact Delete Set + Decision Surface

**Dependency:** D0.
**Parallel-safe with D2** if D1 owns manifest/presentation files and D2 owns executor/preflight files.

**Mission:** convert eligible cleanup rows into a local/private, exact deletion-set artifact that the operator can inspect before any mutation.

**Initial eligibility:** `RECLAIM_PROVEN` only. USER_SELECTED/HUMAN_REVIEW deletion is a later expansion and must not delay the first reclaim path.

**Required local/private artifact:**
- `delete-manifest.json` as the authority;
- optional CSV/HTML projections for operator readability.

Each manifest item must carry, at minimum:
- stable FileSteward item ID;
- exact normalized path;
- item type;
- disposition and evidence/contract source;
- logical bytes;
- allocated bytes when known;
- projected source-volume reclaim;
- protection/managed/cloud/link flags;
- source run ID;
- source cleanup-plan SHA-256;
- source item identity facts sufficient for D2 drift checks;
- intended action: `QUARANTINE` or `DELETE_PERMANENTLY`;
- reversibility label.

**Decision scene must show:**
- exact item count;
- exact selected paths/details on demand;
- total logical bytes;
- total allocated/projected reclaim bytes;
- what is reversible vs irreversible;
- what will **not** be touched;
- approval state;
- freshness/preflight state;
- predicted vs later verified free-space delta.

**Acceptance:** operator can answer “what exactly will disappear, why, and how much C: space should this free?” without consulting raw CSV.

### D2 — Mutation Preflight / Dry-Run Engine

**Dependency:** D0.
**Mission:** prove the exact selected objects still match the approved evidence immediately before mutation.

Future owned surface:
- dedicated deletion/preflight module + focused tests;
- no visualization edits.

Preflight must fail closed on:
- missing or newly appeared target identity ambiguity;
- path escaping approved roots;
- symlink/junction/reparse traversal;
- protection/managed classification change;
- cleanup-plan digest drift;
- changed file identity where the platform can prove it;
- material size/mtime drift under the accepted identity policy;
- cloud placeholder/provider uncertainty;
- directory contents not exactly represented by the manifest;
- unsupported filesystem semantics.

Preflight output:
- `delete-preflight.json`;
- PASS/FAIL per item;
- recalculated projected reclaim;
- baseline source-volume free bytes;
- no filesystem mutation.

Windows edge cases to characterize explicitly:
- hardlinks;
- sparse/compressed files;
- files opened without delete sharing;
- ACL denial;
- long paths;
- readonly attributes;
- junctions/reparse points;
- directories that become non-empty between scan and action.

### D3 — Explicit Delete Approval v1

**Dependencies:** D1 + D2.

Do **not** overload the existing QUARANTINE-only `filesteward.approval/v1` record in a way that makes old approvals stronger.

Create a deletion-specific exact-manifest approval contract whose authority is bound to:
- delete-manifest SHA-256;
- preflight identity/revision;
- exact item IDs;
- exact action;
- exact item count;
- exact projected allocated-byte reclaim;
- operator-issued approval timestamp/nonce or equivalent replay-resistant local identity.

Actions:
- `QUARANTINE`;
- `DELETE_PERMANENTLY`.

A QUARANTINE approval must never satisfy DELETE_PERMANENTLY.

DELETE_PERMANENTLY requires an explicit irreversible confirmation scene after the exact set and projected reclaim are visible.

### D4A — Reversible Quarantine + Restore

**Dependencies:** D3 QUARANTINE approval.

Purpose:
- prove bounded filesystem mutation and restore semantics before irreversible mutation;
- provide a recoverable path for items where retention is desired.

Required truth:
- same-volume quarantine reports **0 immediate source-volume reclaim** unless evidence proves otherwise;
- cross-volume quarantine may report source-volume reclaim only after measured verification;
- restore must be tested against synthetic fixtures and one bounded private/live specimen before general use.

Receipt must retain original path, quarantine path, identity, action result, and restoration state.

### D4B — Permanent Delete Executor

**Dependencies:** D3 DELETE_PERMANENTLY approval + D2 current preflight.

This is the first phase that may intentionally and irreversibly remove bytes.

Rules:
- operate only on manifest-enumerated items;
- no generic recursive deletion of an unenumerated tree;
- files are removed only after exact revalidation;
- directories are removed bottom-up only when all approved descendants are accounted for and the directory is empty at deletion time;
- never follow reparse/symlink targets;
- partial failure is a partial result, never a global success;
- one failed item must not cause unrelated unapproved expansion;
- protected/cloud/managed/provider-ambiguous items remain blocked.

Initial production target should be the safest useful class: already-`RECLAIM_PROVEN` regenerable data, not arbitrary personal files.

### D5 — Execution Receipt

**Dependencies:** D4A or D4B.

Local/private immutable receipt:
- manifest + approval digests;
- action mode;
- per-item attempted/succeeded/failed/skipped;
- exact failure reason class;
- bytes associated with successful items;
- start/end timestamps;
- pre/post free-space observations;
- pending-delete/open-handle cases explicitly separated;
- no secrets/content capture.

A receipt must survive process interruption well enough to prevent blind replay.

### D6 — Reclaim Verification

**Dependency:** D5.

Program success is measured here, not at click time.

Required calculations:
- source-volume free bytes before;
- source-volume free bytes after;
- verified delta;
- successful allocated bytes expected;
- discrepancy;
- residual approved paths;
- pending/locked items.

States:
- `VERIFIED_RECLAIM`;
- `PARTIAL_RECLAIM`;
- `NO_RECLAIM`;
- `UNKNOWN`.

The UI must surface prediction vs measured result.

### D7 — Retention / Recurrence Integration

**Dependencies:** one manually executed D4/D5/D6 lifecycle proven + scheduler program.

Only after the manual path is proven:
- scheduler may run SCAN/RECOMMEND as today;
- approved-quarantine recurrence can use exact fresh approval identities;
- recurring permanent deletion remains opt-in and requires its own retention policy/freshness contract;
- recurrence never self-approves a newly discovered item;
- failed runs do not disable recurrence;
- old approval/manifests expire or fail closed when proof-relevant inputs drift.

## 8. Provider-refresh and collision contract

There is active local work that is not necessarily visible to GitHub. Therefore **every writer** must refresh provider truth immediately before commit/push and reconcile its owned branch.

Required pre-commit floor:

```text
git fetch --all --prune --tags
resolve current remote default branch
resolve current PR/dependency heads
compare the writer's base/head with refreshed provider truth
inspect overlapping changed files
preserve dirty/separately owned work
reconcile proof-relevant base movement before validation/commit
```

No writer may assume this plan's creation SHA remains the latest branch head.

Branch ownership:
- this P04 plan branch owns only `plans/active/FILESTEWARD-DELETION-LIFECYCLE-P04-2026-10-05.*`;
- D1/D2 should use separate isolated worktrees/branches from the then-refreshed accepted dependency head;
- do not modify PR #17 UI files from a deletion backend lane;
- convergence happens only after both sibling lanes are individually green and refreshed.

## 9. Validation strategy

Cheap/focused first, then broader:

1. plan JSON parse + provider readback;
2. pure manifest/preflight unit tests;
3. negative mutation fixtures;
4. temporary-directory mutation tests only;
5. full repository suite;
6. exact-candidate patch hygiene;
7. private/live preview of the exact deletion set;
8. one bounded reversible mutation + restore;
9. one bounded permanent deletion of an explicitly approved regenerable specimen;
10. free-space readback;
11. operator acceptance;
12. only then broaden execution.

Required negative fixtures include:
- modified target after approval;
- path replaced by symlink/junction;
- protected descendant injected into a directory;
- locked file;
- ACL denial;
- partial directory contents;
- same-volume quarantine falsely claiming reclaim;
- hardlink overprojection;
- cloud placeholder/provider-ambiguous item;
- stale approval digest;
- scheduler attempting deletion without exact current approval.

## 10. Parallel work plan

After D0:
- **Lane D1 / Visibility** can implement delete-manifest + operator view.
- **Lane D2 / Executor Preflight** can implement no-op revalidation/dry-run.
- Existing U1 visual polish may continue independently where files do not overlap.

The coordinator must refresh provider truth before creating each lane and again before convergence.

## 11. Proof ladder

`PLANNED -> CONTRACT_ENCODED -> DRY_RUN_VALIDATED -> EXACT_SET_VISIBLE -> OPERATOR_APPROVED -> REVERSIBLE_MUTATION_PROVEN -> PERMANENT_DELETE_PROVEN -> RECEIPT_PROVEN -> RECLAIM_VERIFIED -> INTEGRATED -> SCHEDULED/OBSERVED`

No rung may be inferred from a lower rung.

## 12. End-state contract horizon

| Contract | Owner | Current state | Required next transition |
|---|---|---|---|
| exact cleanup evidence | existing scan/manifest | PROVEN for prior read-only program | feed D1 |
| deletion plan | this P04 plan | IMPLEMENTED / provider validation pending | read back branch |
| exact delete set | D1 | REQUIRED SUCCESSOR WORK | generate manifest + scene |
| mutation preflight | D2 | REQUIRED SUCCESSOR WORK | dry-run + adversarial fixtures |
| delete approval | D3 | REQUIRED SUCCESSOR WORK | exact irreversible authority |
| quarantine/restore | D4A | REQUIRED SUCCESSOR WORK | bounded mutation proof |
| permanent deletion | D4B | REQUIRED SUCCESSOR WORK | one explicit regenerable specimen |
| execution receipt | D5 | REQUIRED SUCCESSOR WORK | interruption-safe record |
| reclaim verification | D6 | REQUIRED SUCCESSOR WORK | measured C: free-space delta |
| recurrence | D7 | REQUIRED SUCCESSOR WORK | only after manual lifecycle proof |

## 13. First executable successor slice

**D1 and D2 should start in parallel from freshly refreshed provider truth.**

D1 produces the first exact local/private delete-manifest and a decision scene from already-`RECLAIM_PROVEN` items.

D2 produces a no-mutation preflight engine that can prove whether those exact items are still safe and unchanged enough to act on.

They converge only when the operator can see the exact set **and** the engine can prove the set is still current.

That convergence, not further cosmetic polish, unlocks D3 approval and the first real removal experiment.
