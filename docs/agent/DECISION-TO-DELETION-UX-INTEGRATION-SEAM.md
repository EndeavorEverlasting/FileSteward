# Decision-to-Deletion UX Integration Seam — 2026-10-06

**Judgment owner:** remote P04/P83/P82 coordination  
**Purpose:** remove integration judgment from local agents while preserving both the complete UI lineage and current deletion/safety truth.

## Canonical graph decision

The implementation PR **MUST target `main`**, not PR #17 and not any older stacked UI base.

The implementation branch name is:

```text
feature/decision-to-deletion-ux-20261006
```

The branch is created from **refreshed current `origin/main` after the governance contract in PR #22 is merged**.

The complete UI source lineage is:

```text
design/u1-brand-home-schedule-seam-20261005
exact observed head at seam definition:
25caadd2245905569ce3b83e9249c30dcccd7884
```

Current graph observation at seam definition:

```text
main@3d3c2e3309430b9492fc7feb01c82ca35bb26e4e
UI head: 58 ahead / 17 behind main
merge base: be0406b3047ce07a769fb3f9a14cd6618dbf086e
```

This means the UI lane is a real diverged product lineage. It must not be reconstructed by cherry-picking a guessed subset of commits.

## Required integration operation

After refreshing provider truth:

1. create `feature/decision-to-deletion-ux-20261006` from current `origin/main`;
2. merge the **entire** current PR #17 head with `--no-ff --no-commit`;
3. resolve conflicts according to the authority map below;
4. commit that reconciliation as one explicit integration seam commit;
5. only then implement DUX-01..DUX-06 / UX-T01..UX-T22 on top;
6. before delete-UI binding and before final validation, merge refreshed `origin/main` again if the live deletion lane has advanced it.

Do not rebase or rewrite PR #15/#16/#17. They remain historical/source lineage.
Do not target the implementation PR at PR #17; that would place current deletion capability on the wrong side of the graph.

## Conflict / authority map

### MAIN + PR #22 ALWAYS WIN semantics

These paths/contracts are current safety/governance authority. Never take stale UI-branch wording over them:

- `AGENTS.md`
- `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
- `docs/agent/OPERATOR-DELETE-PATH.md`
- `docs/agent/OPERATOR-DECISION-UX-PATH.md`
- `plans/active/DELETE-TO-DONE-2026-10-05.*`
- `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.*`
- `src/filesteward/deletion/**`
- deletion tests guarding manifest/preflight/approval/executor/receipt/reclaim

In particular, the stale UI-lineage statement **"Permanent deletion is outside the current MVP"** is forbidden from surviving the seam.

### UI LINEAGE WINS product implementation baseline

The following come from the current PR #17 head unless a same-file conflict requires additive reconciliation with newer main:

- `src/filesteward/review_bridge.py`
- `src/filesteward/housekeeping_settings.py`
- `src/filesteward/visualization/**`
- UI/visual interaction docs under `docs/program/**`
- UI-specific tests and harness artifacts introduced by PR #15/#16/#17
- UI product version lineage as input to the repository-owned versioning gate

These are the product surface to repair, not files to reconstruct from old screenshots.

### ADDITIVE / MANUAL RECONCILIATION

#### `src/filesteward/cli.py`
Neither side wins wholesale.

The reconciled CLI must preserve all current main permanent-delete commands:

- `delete-manifest`
- `delete-preflight`
- `delete-approve`
- `delete-execute`

and add/preserve the UI lineage's:

- `review`

Existing scan/validate/plan/visualize/apply behavior must remain unless an owned acceptance test requires a bounded change.

A resolution that drops either the delete command family or `review` is an immediate integration failure (UX-T17).

#### `pyproject.toml` + `src/filesteward/__init__.py`
Current `main` still reports product `0.1.0`; PR #17 reports `0.12.2`.

Do not resolve this by taking main's stale version.
Do not hand-invent the final version.

Use the UI lineage as the product-version floor, then run the repository-owned P130/versioning gate for a **visual-feature** change after the integrated implementation exists. The two version declarations must agree.

#### approval domains
The UI lineage's root `src/filesteward/approval.py` is the quarantine/Decision-Chamber approval domain.
Permanent deletion is owned separately by `src/filesteward/deletion/approval.py`.

Preserve both domains. Do not alias, rename, or reuse quarantine approval as delete authority. The public UI may adapt between them only through an explicit action-specific bridge that preserves the deletion contract.

#### `AGENTS.md`
Start from refreshed main/PR #22 text and selectively carry forward only non-conflicting UI-specific requirements such as the product-versioning gate. Never restore stale permanent-delete prohibitions or remove delete-to-done continuation rules.

## Implementation adapter boundary

The existing localhost `ReviewBridge` remains the public decision UI bridge.

Do **not** create a second HTTP bridge.

Extend/adapt it so that:
- ordinary decision intents use the single canonical decision-flow transition owner;
- permanent-delete UI action calls the existing deletion package;
- exact delete approval remains `filesteward.delete-approval/v1`;
- bridge response returns explicit continuation state;
- private runtime artifacts stay under ignored runtime storage.

The deletion package remains the mutation owner.
The visualization package remains presentation owner.
The bridge coordinates; it does not absorb either domain.

## P83 pre-implementation ancestry gate

Before modifying product code, prove and record:

```text
git merge-base --is-ancestor <refreshed-main-sha> HEAD
git merge-base --is-ancestor <current-pr17-head-sha> HEAD
```

Both must succeed after the seam commit.

Also read back:
- `AGENTS.md` and confirm current delete contract language;
- `src/filesteward/cli.py` and confirm both `review` and delete command family;
- `src/filesteward/deletion/approval.py` and root `src/filesteward/approval.py` remain distinct.

## P82 seam falsification

Immediately after the seam commit, before feature repairs:

1. run full tests to expose merge regressions;
2. run CLI help / parser tests for `review` + deletion commands;
3. render/serve the inherited UI once;
4. record all seam-caused failures separately from pre-existing DUX defects;
5. repair seam regressions before attributing them to feature work.

This establishes an integration floor instead of letting feature changes hide a broken merge.

## Dependency on the live deletion lane

Parallelism remains intentional.

The UX branch does **not** wait idle for the live Temp deletion sprint.

However, before implementing the final permanent-delete UI binding and again before final full-suite/browser proof:

```text
git fetch origin
merge refreshed origin/main into the UX branch
reconcile only new conflicts under this same authority map
```

This consumes any deletion repair that has landed without turning the live lane into a prerequisite for independent scene/pointer work.

If the live deletion lane has only uncommitted/local evidence, the UX lane does not guess it. It consumes remote/merged repository truth only.

## Integration completion

The implementation PR targets `main`.

It is eligible to merge only when:
- UX-T01..UX-T22 meet their required proof ceiling;
- exact PR head/review threads are refreshed;
- no material review finding remains unresolved;
- full suite/browser proof is current on the exact head;
- ancestry and authority-map checks pass.

The old stacked UI PRs remain source/history and may be closed or dispositioned separately after successful integration; their closure is not part of this sprint's product acceptance gate.

## Local-agent conflict boundary

This document is the integration judgment owner.

The local agent may mechanically apply the authority map above. It may not choose an alternate merge topology, selectively reconstruct the UI lineage, or resolve a material conflict by product preference.

If a conflict is not covered by this document or by a more specific canonical repository contract:
- preserve the conflict/evidence;
- continue independent non-conflicting work;
- return `BLOCKED_JUDGMENT_GAP` naming the exact paths/symbols and competing authorities;
- do not make a new policy decision in the local lane.

Routine code-level reconciliation that preserves the already-declared authority is implementation, not new judgment.
