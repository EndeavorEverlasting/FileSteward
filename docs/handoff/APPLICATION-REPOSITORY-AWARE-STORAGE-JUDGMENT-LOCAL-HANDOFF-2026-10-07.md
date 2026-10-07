# Local Agent Handoff — Dependency-Aware Storage Judgment — 2026-10-07

## Role

You are the local execution coordinator for an already-judged FileSteward sprint.

Do not redesign the product policy in this handoff. Read canonical judgment, refresh provider/runtime truth, execute the graph, preserve evidence, and return proof.

## Repository frame

```text
repo: EndeavorEverlasting/FileSteward
canonical checkout: %USERPROFILE%\dev\FileSteward
remote planning branch: plan/application-repo-aware-judgment-20261007
PR target: main
current planning floor: main@610f4fe624bfdf7c9577bcbc28ac2bea394c81f5
open UX collision to reconcile later: PR #29
```

Historical SHAs are evidence floors only. Refresh before mutation.

## Canonical judgment — read in this order

1. `AGENTS.md`
2. `plans/active/FILESTEWARD-APPLICATION-REPOSITORY-AWARE-JUDGMENT-P00-P01-P04-P82-2026-10-07.md`
3. `plans/active/FILESTEWARD-APPLICATION-REPOSITORY-AWARE-JUDGMENT-P00-P01-P04-P82-2026-10-07.plan.json`
4. `harness/contracts/storage-dependency-judgment.v1.json`
5. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
6. `docs/agent/OPERATOR-DELETE-PATH.md`
7. `harness/contracts/action-scene-impact.v1.json`
8. `harness/contracts/judgment-scene-workflow.v1.json`
9. `harness/evals/judgment-scene-regression.v1.json`
10. `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.md`
11. `docs/agent/DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md`
12. `docs/handoff/FILESTEWARD-EXECUTION-HANDOFF-PROTOCOL-2026-10-07.md`
13. `harness/contracts/execution-handoff-loop.v1.json`
14. `harness/contracts/execution-handoff-packet.schema.v1.json`
15. `harness/evals/execution-handoff-review-gates.v1.json`

If handoff prose conflicts with those artifacts, the canonical artifact wins.

## Orientation / continuity

Before editing:

```powershell
cd $env:USERPROFILE\dev\FileSteward
git fetch --all --prune --tags
git status --short --branch
git log -1 --oneline --decorate origin/main

entire status --json
entire agent-help --json
```

If Entire Brain/Graph are installed, use them for context recovery and change-impact discovery. Verify current source/runtime/provider truth afterward. If the operator-mentioned Mini capability is not present in current Entire help/plugin output, do not invent it.

## Deterministic judgment-scene rule

Local agents are **implementation executors, not scene authors**.

- Implement the exact scene graph and scripts in `harness/contracts/judgment-scene-workflow.v1.json`.
- Treat `harness/evals/judgment-scene-regression.v1.json` as the retained P94 oracle.
- Resolve technical safety facts automatically/read-only before HUMAN_REVIEW whenever the contract names an adapter path.
- Ask the operator only for value/preference or exact action approval after technical safety is resolved.
- If required judgment is absent, return `BLOCKED_JUDGMENT_GAP` with the missing fact/transition. Do **not** improvise a scene, modal, dashboard, action label, or decision rule.
- Preserve the existing `MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED` tutorial. New attribution/consequence/recoverability work lives inside deterministic RESOLVE subscenes.
- Preserve the incumbent Memory Atlas visual/interaction world during refinement. A backend or bounded feature lane has no authority to flatten it into generic cards/tables or reset its interaction grammar.
- Never weaken/delete an accepted test, fixture, or protected behavior merely to fit a candidate.

The workflow intentionally allows read-only technical RESOLVE scenes to auto-advance when the result is deterministic and remains inspectable in the action/evidence trace. That is how judgment friction is removed without transferring safety judgment to an agent or to the operator.

## Operating / handoff loop

Do not treat this handoff as permission to plan again. Consume it through the canonical loop:

`RECOVER -> PARTITION -> DISPATCH -> EXECUTE -> PROVE -> REVIEW -> CONVERGE -> CONTINUE`.

Before handing to another agent/runtime, emit a packet conforming to `filesteward.execution-handoff-packet/v1`. If the same agent can execute the packet's next transition, **execute it rather than stopping at the packet**.

Review gates are transition gates, not meeting points. Failures route to the named repair owner and then rerun the invalidated gate. Independent lanes continue.

## Execution graph

### Lane J0 — emergency containment — CRITICAL PATH

**Owned scope**
- `src/filesteward/deletion/regenerable.py`
- `tests/test_regenerable_cache_roots.py`
- directly owning delete-path contract/tests if needed

**Assignment**
- remove generic `%PROGRAMDATA%\Package Cache` from automatic permanent-delete admission;
- make the test prove it is refused/protected, not admitted;
- preserve other existing seams unless a current failing proof shows a separate defect;
- run focused deletion tests, then full suite;
- integrate this repair as soon as exact-head gates permit.

**Acceptance**
- generic Package Cache scan root cannot reach permanent-delete execute;
- focused regression proves the refusal;
- no unrelated cleanup seam widened.

### Lane J1 — Wispr Flow incident evidence — READ-ONLY FIRST

**Owned scope**
- ignored `var/runs/**`;
- live workstation read-only evidence;
- sanitized tracked regression only after facts are established.

**Assignment**
- locate the exact reclaim receipts that ran before Wispr stopped working;
- identify successful deleted roots/items without committing private paths;
- establish Wispr install/runtime/repair metadata;
- attempt safe diagnostic launch/readback;
- correlate deleted evidence with Wispr runtime/serviceability/dependency metadata;
- if repair is needed, first check whether the existing operator gate explicitly covers that repair; because repair mutates C: and can change incident evidence, obtain an explicit bounded gate before invoking vendor/installer repair when it is not already covered;
- after authorization, use normal vendor/installer repair semantics and preserve pre-repair evidence/readback;
- record one state only: `CAUSAL_LINK_PROVEN`, `CAUSAL_LINK_DISPROVEN`, or `CORRELATED_UNRESOLVED`.

Do not claim causality from timing alone.

### Lane J2 — Windows application attribution

Create a new backend adapter surface; do not edit visualization.

Minimum adapters/evidence:
- HKLM/HKCU uninstall entries in both registry views;
- install/modify/repair/uninstall metadata;
- MSI/WiX/Burn identity where safely observable;
- AppX/MSIX roots;
- services;
- scheduled tasks;
- shortcuts as corroboration;
- running executable/module evidence;
- file product/company/signature metadata;
- optional package-manager corroboration.

Do not use `Win32_Product`.

Produce normalized ownership/consequence evidence and focused synthetic tests.

### Lane J3 — repository/project attribution

Reuse `ProtectionIndex.from_git_discovery`.

Add read-only evidence for:
- repo/worktree root;
- dirty/staged/untracked state;
- branch/detached state;
- remotes;
- ahead/behind/push equivalence when available;
- nested repos/submodules/worktrees;
- tracked vs generated/build storage;
- reproducibility evidence.

Classification may enrich scenes and decisions. It must not weaken repository protection.

### Lane J4 — dependency graph + reducer

After J2/J3, normalize evidence into the canonical consequence classes from the plan/contract.

Required rule: missing ownership evidence, app/serviceability dependency, or dirty/unique repo state can never be auto-promoted to `RECLAIM_PROVEN`.

### Lane J5 — deletion integration

Bind current dependency-evidence revision into delete manifest/preflight/receipt as required by the canonical contract.

Preflight must fail closed when proof-relevant ownership/dependency state drifted.

The destructive executor must also re-evaluate proof-relevant dependency/ownership state immediately before **each** deletion/unlink, not merely once at preflight. If the current evidence revision/digest differs from the approved/preflight revision or newly protects the target, fail closed before mutation. Bind the immediately checked dependency-evidence revision/digest to that item's deletion receipt; target identity revalidation alone is not dependency freshness.

Do not replace the existing exact-manifest -> approval -> executor -> receipt architecture.

### Lane J6 — scripted scenes / filtered views

Do not start by independently rewriting the visualization lineage.

After J4 is integrated, refresh PR #29 and main for evidence, create `integration/j6-pr29-lineage-20261007` from refreshed main, and execute the selective-lineage allowlist/exclusion/shared-file procedure in `harness/contracts/dependency-aware-judgment-closure.v1.json`. **Do not merge PR #29 wholesale and do not design another integration strategy.** Then implement the existing script.

Required implementation owners:
- `harness/contracts/judgment-scene-workflow.v1.json` — scene order, entry/exit rules, automatic technical resolution, legal operator choices, copy semantics, continuation;
- `harness/evals/judgment-scene-regression.v1.json` — protected immersive behavior, negative fixtures, positive controls, live acceptance matrix;
- `harness/contracts/action-scene-impact.v1.json` — action projection and fail-closed binding.

The key flow remains `MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED`. Attribution, consequence, recoverability, and value judgment are scripted RESOLVE subscenes. Technical subscenes should auto-run/auto-advance when safe and deterministic; human interruption is reserved for real value choice and exact action approval.

Persist resulting classifications/decisions into filterable views/queues and preserve unrelated search/filter/selection state across scene changes.

### Lane J7 — P82 falsification

Run the canonical fixture corpus. Treat false-positive deletion eligibility as a defect.

Iterate until:
- protected/serviceability/unique fixtures produce zero automatic deletion eligibility;
- regenerable app candidates have deterministic regeneration evidence;
- repo decisions expose dirty/reproducibility state;
- stale dependency evidence blocks delete preflight;
- full suite passes on exact head.

Then perform one bounded live **read-only** attribution proof before proposing any new broad live cleanup.

### P94 + P110 retained-scene acceptance

A green unit suite is not enough for a live UX claim.

Before J6/J7 can report scene integration PROVEN:
1. run the negative defect families and positive controls from the regression ledger;
2. prove composed state (search/filter/selection) across unrelated scene transitions;
3. prove truthful pointer + keyboard paths and touch/phone when product-declared supported;
4. perform bounded browser acceptance on desktop, narrow viewport, reduced-motion, and forced-colors states;
5. inspect the result against the incumbent Memory Atlas visual world and interaction grammar;
6. repair defects without editing the oracle to match the broken candidate;
7. rerun one bounded confirmation pass.

If live/browser tooling is unavailable, keep live acceptance UNPROVEN; do not substitute static HTML/string checks.

## Parallel execution

After refreshing provider truth, J1/J2/J3 are independent of one another and may run in separate worktrees/agents while J0 stays the critical path.

Each lane owns only its declared surface. No lane may edit J6 visualization files unless it is the reconciled J6 owner.

If using a secondary Entire worktree/session, preserve Entire session/checkpoint linkage according to the installed CLI guidance rather than silently losing continuity.

## Forbidden scope

- no new broad cleanup allowlists;
- no raw deletion of installed-app files as a substitute for uninstall/repair;
- no weakening exact-manifest deletion gates;
- no auto-deleting repositories because they are old;
- no private runtime receipts/paths in Git;
- no PR #29 visualization rewrite from a backend lane;
- no fabricated Entire Mini API;
- no stopping at a green plan or “ready to implement” state.

## Completion / return format

Return:

```text
CHANGED:
PROVED:
FAILED_AND_REPAIRED:
SKIPPED:
BLOCKED_JUDGMENT_GAP: <none or exact unresolved judgment>

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
NEXT:
```

Evidence before confidence. A blocked lane does not prevent independent lanes from advancing.
