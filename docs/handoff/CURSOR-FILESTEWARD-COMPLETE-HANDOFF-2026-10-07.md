# Cursor complete handoff — FileSteward dependency-aware judgment sprint — 2026-10-07

## ROLE

You are the local execution coordinator for FileSteward.

The product/system judgment for the current known graph is already closed. **Do not plan a replacement architecture. Do not redesign the Memory Atlas. Do not choose a different PR #29 strategy.**

Your job is to recover current truth, execute the closed graph, run the gates, repair failures inside their named ownership, integrate when gates permit, and continue until the next genuine external/operator-only blocker or the verified sprint outcome.

## REPOSITORY

```text
repository: EndeavorEverlasting/FileSteward
canonical checkout: %USERPROFILE%\dev\FileSteward
foundation branch / PR #33:
  branch: plan/application-repo-aware-judgment-20261007
  PR: #33
PR #29 UX lineage donor:
  branch: feature/decision-to-deletion-ux-20261006
  decision-time head: c093f2cb69d69be153fcf983b6ad785636825b7e
```

Historical/captured SHAs orient only. Refresh provider/local truth before mutation.

## MANDATORY READ ORDER

Read these before mutation:

1. `AGENTS.md`
2. `plans/active/FILESTEWARD-APPLICATION-REPOSITORY-AWARE-JUDGMENT-P00-P01-P04-P82-2026-10-07.md`
3. `plans/active/FILESTEWARD-APPLICATION-REPOSITORY-AWARE-JUDGMENT-P00-P01-P04-P82-2026-10-07.plan.json`
4. `harness/contracts/dependency-aware-judgment-closure.v1.json`
5. `docs/handoff/FILESTEWARD-DEPENDENCY-AWARE-CURRENT-HANDOFF-2026-10-07.json`
6. `docs/handoff/FILESTEWARD-EXECUTION-HANDOFF-PROTOCOL-2026-10-07.md`
7. `docs/handoff/FILESTEWARD-EXECUTION-REVIEW-CHECKLIST-2026-10-07.md`
8. `harness/contracts/execution-handoff-loop.v1.json`
9. `harness/evals/execution-handoff-review-gates.v1.json`
10. `harness/contracts/storage-ownership-evidence-graph.v1.json`
11. `harness/contracts/storage-dependency-judgment.v1.json`
12. `harness/contracts/judgment-scene-workflow.v1.json`
13. `harness/evals/judgment-scene-regression.v1.json`
14. `harness/contracts/action-scene-impact.v1.json`
15. `docs/handoff/WISPR-FLOW-BROKEN-INSTALL-RECOVERY-2026-10-07.md`
16. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
17. `docs/agent/OPERATOR-DELETE-PATH.md`

If prose conflicts with a machine contract, the machine contract wins. If current provider/runtime truth conflicts with a captured handoff SHA, current truth wins.

## CANONICAL LOOP

Execute:

```text
RECOVER
 -> PARTITION
 -> DISPATCH
 -> EXECUTE
 -> PROVE
 -> REVIEW
 -> CONVERGE
 -> CONTINUE
```

A passing gate means continue under existing authority. A failed gate routes to the named repair owner, then rerun only invalidated proof.

These are NOT terminal:
- plan written;
- handoff written;
- branch green;
- PR open;
- PR mergeable;
- one blocked lane while independent lanes remain runnable.

## RG0 — RECOVER CURRENT TRUTH FIRST

From the canonical checkout:

```powershell
cd $env:USERPROFILE\dev\FileSteward
git fetch --all --prune --tags
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git rev-parse origin/plan/application-repo-aware-judgment-20261007
git rev-parse origin/feature/decision-to-deletion-ux-20261006

entire status --json
entire agent-help --json
```

If Entire Brain/Graph/Mini capabilities are present, record the exact supported commands before use. Do not fabricate unavailable Entire capability. Entire is context/change-impact evidence, not deletion authority.

Refresh:
- PR #33 exact head/state/reviews/threads;
- PR #29 exact head/state;
- local worktrees/branches;
- any existing J2/J3 work;
- ignored `var/runs/**` evidence posture.

Do not overwrite unknown local work. Recover it first.

## JUDGMENT IS CLOSED

Canonical owner:

`harness/contracts/dependency-aware-judgment-closure.v1.json`

No known architectural/product question is delegated to you.

Specifically already decided:

- technical safety is machine-resolved before human value choice;
- multi-owner storage uses most-protective-edge-wins;
- Entire never independently declares legacy/disposable;
- J2/J3/J4/J5/J6 ownership is fixed;
- PR #29 is a **selective lineage donor**, not a whole-branch merge;
- current safety/ownership/deletion contracts outrank PR #29 stale runtime hunks;
- review-gate failure does not freeze independent lanes;
- operator remains owner only of value preference and exact mutation authority when prior intent does not cover the action.

If a genuinely new fact contradicts this closure, return `BLOCKED_JUDGMENT_GAP` with the contradiction. Do not invent replacement policy.

# WAVE 1 — EXECUTE IN PARALLEL WHERE SAFE

Wave 1 consists of J0 + J1 + J2 + J3.

Use native subagents / AgentSwitchboard / local process adapters when available. If no safe parallel adapter exists, report the exact `AUTONOMY_GAP` and continue serially rather than making the operator shuttle prompts.

## J0 — FOUNDATION LOCAL PROOF — CRITICAL GATE

**Branch:** `plan/application-repo-aware-judgment-20261007`  
**Purpose:** prove the already-implemented Package Cache containment and foundation PR.

Run focused proof first:

```powershell
python -m pytest tests/test_regenerable_cache_roots.py -q
```

Then run directly owning deletion/preflight tests discovered by the repo, followed by the full suite:

```powershell
python -m pytest -q
```

Also run repository-owned validators named by AGENTS/current scripts.

Required J0 facts:

- `%PROGRAMDATA%\Package Cache` is absent from the generic regenerable allowlist;
- Package Cache cannot use the size+mtime identity shortcut;
- execute admission refuses the generic Package Cache root;
- no unrelated cleanup root was widened;
- JSON/contracts parse;
- exact candidate head recorded.

Do not “fix” a failing negative test by weakening it.

### PR #33 integration rule

PR #33 is the **foundation/containment PR only**.

Do not add J2/J3/J4/J5/J6 implementation to PR #33.

After J0 local proof:

1. refresh PR #33 exact head;
2. enumerate review threads;
3. repair/disprove every material finding;
4. rerun invalidated focused/full proof;
5. satisfy RG5 + RG6;
6. merge PR #33 when repository/provider authority permits;
7. refresh `main` and verify merged content.

If provider merge tooling is unavailable, record an `AUTONOMY_GAP`; do not stop J1/J2/J3 local work.

## J1 — WISPR INCIDENT — READ-ONLY DIAGNOSIS FIRST

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\diagnose-wispr-install.ps1
```

Evidence belongs under ignored:

`var/runs/wispr-recovery-*/`

Read `diagnostic.json` and copied Squirrel setup-log tail.

Classify only from evidence:

- file/process lock;
- access denied / endpoint protection;
- stale/broken Squirrel registration or missing `Update.exe`;
- package/download/extraction failure;
- unknown.

Follow:

`docs/handoff/WISPR-FLOW-BROKEN-INSTALL-RECOVERY-2026-10-07.md`

Rules:

- preserve pre-repair evidence;
- do not raw-delete Wispr AppData/user data;
- do not broad-purge registry;
- do not disable endpoint protection;
- no blind installer loop;
- before mutation, bind the exact repair action to existing operator authority or stop only at the exact missing RG9 authorization;
- after repair, verify Wispr launch, serviceability executable/registration consistency, and absence of the prior failure signature.

Return one causal state only:

- `CAUSAL_LINK_PROVEN`
- `CAUSAL_LINK_DISPROVEN`
- `CORRELATED_UNRESOLVED`

J1 may continue independently of J2/J3.

## J2 — WINDOWS APPLICATION ATTRIBUTION

**Branch:** `feature/windows-app-attribution-20261007`  
**Preferred worktree:** `%USERPROFILE%\dev\worktrees\FileSteward\j2-app-attribution`

Create/attach this branch from the **refreshed PR #33 foundation head**, not stale main. If the branch/worktree already exists, inspect and continue it rather than recreating or deleting it.

Owned tracked surface:

- `src/filesteward/ownership/windows_app.py`
- `tests/test_ownership_windows_app.py`
- private `src/filesteward/ownership/_windows_*` helpers only if necessary

Forbidden:

- `src/filesteward/visualization/**`
- `src/filesteward/deletion/**`
- J3/J4 modules
- product-policy changes

Implement read-only normalized evidence for:

- HKCU/HKLM uninstall registry, both views;
- InstallLocation / DisplayIcon / uninstall / modify / repair/update metadata;
- safe MSI/WiX/Burn identity evidence;
- AppX/MSIX where applicable;
- services;
- scheduled tasks;
- running executables/modules;
- shortcuts as corroboration;
- file product/company/signature metadata;
- package-manager metadata as corroboration only.

**Never use `Win32_Product`.**

Output cross-domain ownership edges/classes required by:

`harness/contracts/storage-ownership-evidence-graph.v1.json`

Focused fixtures must include:
- active runtime dependency;
- installer/serviceability dependency;
- actual regenerable app cache;
- cache with open handle;
- orphan candidate after adapter exhaustion;
- shared dependency;
- service target;
- scheduled-task target;
- portable app;
- unknown third-party directory;
- broken registered app dependency.

Do not output “safe to delete.” Output evidence/ownership/consequence.

## J3 — REPOSITORY ATTRIBUTION

**Branch:** `feature/repository-attribution-20261007`  
**Preferred worktree:** `%USERPROFILE%\dev\worktrees\FileSteward\j3-repo-attribution`

Fork from the same refreshed PR #33 foundation head.

Owned tracked surface:

- `src/filesteward/ownership/repository.py`
- `tests/test_ownership_repository.py`
- private `src/filesteward/ownership/_git_*` helpers only if necessary

Forbidden:
- visualization;
- deletion;
- J2/J4 modules;
- product-policy changes.

Reuse `ProtectionIndex.from_git_discovery`.

Collect:
- repo/worktree root relationships;
- dirty/staged/untracked;
- branch/detached;
- remotes;
- ahead/behind or push-equivalence when available;
- nested repos/submodules;
- linked worktrees;
- tracked/untracked/generated/build partitions;
- reproducibility/recovery evidence.

Use Entire when available for:
- current worktree/session activity;
- graph relationships/change impact;
- HEAD vs working-tree comparison.

But:
- Entire absence is never dispensability evidence;
- age/inactivity is never deletion authority.

Implement lifecycle evidence:
- `REPO_ACTIVE`
- `REPO_STABLE`
- `REPO_LEGACY_CANDIDATE`
- `REPO_GENERATED_OUTPUT`

Fixtures:
- clean pushed clone;
- dirty repo;
- untracked unique files;
- local-only/ahead branch;
- detached worktree;
- nested repo/submodule;
- generated output;
- unavailable remote/network;
- active Entire/current worktree evidence where capability exists.

# FOUNDATION CONVERGENCE AFTER PR #33 MERGES

Once PR #33 is merged:

1. refresh `main`;
2. rebase J2 and J3 onto refreshed main;
3. rerun any invalidated focused/full proof;
4. open/refresh **separate focused PRs** for J2 and J3;
5. apply RG5/RG6 to each;
6. integrate them independently when green.

Do not combine J2/J3 into an omnibus PR simply for convenience.

# J4 — CROSS-DOMAIN OWNERSHIP GRAPH / REDUCER

Start only after J2 + J3 are integrated.

**Branch:** `feature/storage-ownership-reducer-20261007`

Owned:
- `src/filesteward/ownership/graph.py`
- `src/filesteward/ownership/reducer.py`
- `src/filesteward/ownership/__init__.py`
- `tests/test_ownership_graph.py`
- `tests/test_ownership_reducer.py`

Consume J2/J3 normalized evidence. Do not duplicate their probes.

Implement:

```text
storage path
 -> simultaneous app/repo/service/task/package/toolchain/user-data/generated edges
 -> consequence/lifecycle evidence
 -> most-protective-edge-wins
 -> explainable disposition floor
```

Required failures away from automatic reclaim:
- unknown owner;
- conflicting owner evidence;
- app runtime/serviceability dependency;
- active/unique repo;
- shared dependency unresolved;
- stale evidence.

Required user-facing evidence projection:
- Required by app
- Broken app dependency
- Part of active repo
- Stable repo
- Legacy repo candidate
- Regenerable cache
- Shared dependency
- User data
- Unknown ownership

These are classifications, not raw deletion recommendations.

# J5 — DELETION INTEGRATION

Start after J4.

**Branch:** `feature/dependency-aware-delete-preflight-20261007`

Preserve:

```text
exact manifest
 -> approval
 -> fresh ownership/dependency check
 -> bounded executor
 -> per-item receipt
 -> capacity/health verification
```

Bind the current ownership-graph revision/digest into manifest/preflight.

Immediately before **each** destructive mutation:
- recompute/recheck proof-relevant ownership/dependency state;
- fail closed if it drifted or newly protects the item;
- bind the immediately checked revision/digest into that item's receipt.

Target-identity revalidation alone is not dependency freshness.

Current main deletion/safety code is authoritative. Do not import old PR #29 deletion hunks.

# J6 — MEMORY ATLAS / DECISION CHAMBER INTEGRATION

Start after J4 is integrated.

**Branch:** `integration/j6-pr29-lineage-20261007`

## Fixed PR #29 strategy

**DO NOT merge PR #29 wholesale.**  
**DO NOT re-decide this strategy.**

Refresh PR #29 only to establish the current lineage source. At judgment close its head was:

`c093f2cb69d69be153fcf983b6ad785636825b7e`

Create J6 from refreshed main after J4.

Selectively port the allowlist defined in:

`harness/contracts/dependency-aware-judgment-closure.v1.json`

Core allowed lineage:
- `src/filesteward/visualization/**`
- `src/filesteward/review_bridge.py`
- `src/filesteward/approval.py`
- interaction-scene acceptance contract
- Memory Atlas / Decision Chamber visual docs/tokens
- Decision-to-Deletion traceability
- corresponding Decision Chamber/visualization/review tests
- versioning support required for accepted visual feature

Explicitly do **not** port PR #29 versions of:
- `AGENTS.md`
- `src/filesteward/deletion/**`
- storage/execution contracts
- current dependency-aware plan/handoff
- housekeeping/system-stewardship work unrelated to J6

Shared files:

### `src/filesteward/cli.py`

Keep refreshed-main file as baseline. Port only the Decision-Chamber/review command registration/routing required to expose the accepted UX. Preserve all current scan/delete/ownership safety.

### `pyproject.toml`

Keep refreshed-main baseline. Add only dependencies/entrypoints actually required by the ported UX. Recompute version through repository versioning gate. Do not copy PR #29's old product version blindly.

### `src/filesteward/__init__.py`

Keep refreshed-main version/export authority. Add only required UX exports.

## Scene implementation

The preserved tutorial remains:

`MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED`

Implement canonical RESOLVE subscenes from:

`harness/contracts/judgment-scene-workflow.v1.json`

Do not flatten the product into a generic dashboard.

P94/P110 + current scene/storage contracts outrank PR #29 implementation details. Adapt the ported lineage to current contracts; never weaken current contracts to make old lineage pass.

## RG8 live proof

Before J6 is PROVEN, run:
- desktop browser journey;
- narrow viewport;
- reduced motion;
- forced colors;
- pointer;
- keyboard;
- touch/phone when product-declared.

Verify:
- search/filter/selection survive unrelated scene transitions;
- no dead clicks;
- EXPLORE only means real exploration;
- no second router/mobile state machine;
- blocked states remain visibly blocked;
- classifications persist to filterable views;
- Memory Atlas visual identity remains intact and useful.

Static HTML/string assertions do not close live proof.

# J7 — FINAL P82 / P94 / P110 FALSIFICATION

Start only after J5 + J6 are integrated.

Run:
- all retained negative defect families;
- all positive controls;
- dependency false-positive corpus;
- full repository suite;
- exact-head review refresh;
- bounded live UX proof;
- one safe live **read-only** ownership-attribution specimen.

Acceptance:
- zero automatic reclaim eligibility for protected/serviceability/unique fixtures;
- every app cache reaching reclaim has deterministic regeneration proof;
- repo decisions expose dirty/reproducibility evidence;
- stale dependency evidence blocks mutation;
- no retained scene regression;
- no post-action application/system regression on any authorized live specimen.

First PASS is a checkpoint. Critique false positives/unknowns, repair systemic defect, rerun.

# REVIEW CHECKLIST

Use and update:

`docs/handoff/FILESTEWARD-EXECUTION-REVIEW-CHECKLIST-2026-10-07.md`

Do not substitute a prose “looks good” review.

# PROVIDER / MERGE POLICY

- PR #33 = foundation only.
- J2 = separate PR.
- J3 = separate PR.
- J4 = separate convergence PR.
- J5 = separate deletion-integration PR.
- J6 = separate selective-lineage integration PR.
- J7 repairs the owning branch/PR where possible.

Before every merge:
- exact PR head refreshed;
- zero unresolved material review threads;
- repository-required local full proof on exact head;
- current branch not behind target or conflicts consciously repaired;
- proof ceiling honest.

When gates are green and merge authority exists, integrate and continue. Do not stop for ceremonial permission unless an explicit repository/operator gate requires it.

# RETURN CONTRACT

Return a successor packet conforming to:

`filesteward.execution-handoff-packet/v1`

Also return:

```text
CHANGED:
PROVED:
FAILED_AND_REPAIRED:
SKIPPED:
BLOCKED_JUDGMENT_GAP:
AUTONOMY_GAP:

RG0:
RG1:
RG2:
RG3:
RG4:
RG5:
RG6:
RG7:
RG8:
RG9:
RG10:

J0:
J1:
J2:
J3:
J4:
J5:
J6:
J7:

WISPR_CAUSAL_STATE:
PACKAGE_CACHE_GENERIC_DELETE_STATE:
APP_ATTRIBUTION_STATE:
REPO_ATTRIBUTION_STATE:
OWNERSHIP_GRAPH_STATE:
DEPENDENCY_PREFLIGHT_STATE:
SCENE_INTEGRATION_STATE:

ARTIFACTS:
TESTS:
BRANCHES:
PRS:
HEADS:
GIT_STATUS:
MERGED:
LIVE_MUTATION_STATE:
PROOF_CEILING:
NEXT:
```

If the next transition is executable by you, **execute it instead of stopping at the return packet**.

Do not ask the operator to re-supply judgment already encoded in the repository.
