# FileSteward C:-Drive Cleanup Program — P04 Factoring Plan

**Status:** ACTIVE / IMPLEMENTATION-READY  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Foundation floor:** `agent/repository-foundation@7ca41c45e3d92aae7963d2fc6713cb88b98fa2c2`  
**Plan branch:** `plan/c-drive-cleanup-p04-20260930`  
**Execution host:** `LOCAL_AGENT_RUNTIME` (OpenCode on the operator workstation)  
**Proof ceiling of this plan:** durable design/factoring only; no real `C:\` data observed, classified, moved, quarantined, deleted, or reclaimed.

Read first:

1. `AGENTS.md`
2. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
3. `README.md`
4. this plan
5. `plans/active/C-DRIVE-CLEANUP-P04.plan.json`

## 1. Mission

Implement the first executable FileSteward cleanup program without giving a local agent semantic judgment authority over the operator's files.

The program must support:

```text
scan -> evaluate -> adversarial downgrade -> proposed-action artifacts
```

and stop there for Phase 1-4.

The live workstation audit is a separate read-only operator gate. Mutation/apply is a later gate. Permanent deletion is outside the current MVP.

## 2. Operator outcome

The eventual operational goal is to raise free space on `C:` from the observed low-space state to a healthy target without losing anything that matters.

The program optimizes for **false-positive avoidance**, not deletion volume.

Ambiguity is expected and successful when surfaced correctly.

## 3. Authority model

### 3.1 Local agent authority

The local agent may implement deterministic machinery and synthetic proofs.

The local agent is **not allowed to decide semantic ambiguity**.

When the answer depends on whether a file is personally meaningful, the only valid automated disposition is `HUMAN_REVIEW`.

### 3.2 Evidence state

```text
DISCOVERED -> EVALUATED -> DISPOSITION_ASSIGNED
```

### 3.3 CleanupDisposition

```text
RECLAIM_PROVEN
HUMAN_REVIEW
PROTECTED
KEEP_PROVEN
UNKNOWN
```

These are evidence dispositions, not approval states.

### 3.4 Authorization state

```text
UNAPPROVED -> APPROVED_FOR_ACTION -> APPLIED -> VERIFIED
```

Phase 1-4 must never produce a real operator approval, real apply, or real verified-reclaim record.

## 4. Naming corrections

Do not call `RECLAIM_PROVEN` a file classification. Subject/file classification and cleanup disposition are separate concepts.

Do not call a manifest an authorization surface. A manifest is an immutable proposed-action artifact.

A future operator approval must be a separate artifact bound to an exact manifest digest, run ID, and approved rows/actions.

## 5. Package/module map

Target layout:

```text
pyproject.toml
src/filesteward/
  __init__.py
  cli.py
  models.py
  run.py
  inventory/
    __init__.py
    scan.py
    windows.py
  protect/
    __init__.py
    index.py
    git.py
  classify/
    __init__.py
    rules.py
    gates.py
    challenge.py
  manifest/
    __init__.py
    artifacts.py
  policy/
    __init__.py
    paths.py
tests/
  fixtures/
  test_cli.py
  test_scan.py
  test_protection.py
  test_disposition.py
  test_challenge.py
  test_artifacts.py
  test_safety_stacks.py
docs/program/
  cleanup-program-design.md
  next-sprint-live-audit.md
plans/active/
  C-DRIVE-CLEANUP-P04.md
  C-DRIVE-CLEANUP-P04.plan.json
var/                         # ignored live/private runtime state
```

Names may move slightly if existing repository conventions demand it, but do not create a competing architecture without evidence.

## 6. Dependency direction

```text
cli
 -> run
    -> inventory adapters
    -> protection interfaces
    -> deterministic rules/gates
    -> independent adversarial challenge
    -> artifact writers

models/policy are leaf contracts.
classification does not know CSV column order.
artifact writers do not decide disposition.
CLI does not contain cleanup judgment.
```

The scanner public seam must be streaming/iterable. Do not require a full-drive `InventoryItem[]` in memory.

## 7. Core models

### InventoryItem

Minimum relevant fields:

- stable item identifier for the run;
- path;
- entry type;
- logical size;
- allocated size when obtainable without unsafe side effects;
- projected reclaim bytes when supportable;
- reclaim basis;
- timestamps needed by inventory;
- filesystem identity/link-count evidence where supported;
- scan completeness/error state;
- reparse/symlink/cloud-placeholder metadata needed for safe traversal.

### ProtectionIndex

Must distinguish:

1. candidate equals protected root -> `PROTECTED`;
2. candidate is beneath protected root -> `PROTECTED`;
3. candidate directory is an ancestor containing a protected root -> whole-directory action prohibited; decompose children;
4. unrelated sibling -> independently evaluable.

Do not globally protect all siblings merely because one protected repository is nested beneath an ancestor.

### GateResults

Normalized deterministic evidence consumed by the adversarial challenger.

### ProvisionalDisposition

Rules/gates may nominate `RECLAIM_PROVEN`; the challenger gets an independent downgrade opportunity.

## 8. Reclaim math

Never treat logical file length as proven physical reclaim.

Model:

```text
logical_size_bytes
allocated_size_bytes: int | unknown
projected_reclaim_bytes: int | unknown
reclaim_basis
```

Hard links, sparse files, NTFS compression, cloud placeholders, and allocation behavior can make logical bytes misleading.

If exact reclaim is not proven, call it an estimate.

Target math:

```text
projected_free =
    baseline_free_bytes
    + cumulative_projected_reclaim_bytes

stop when projected_free >= target_free_bytes
```

With the previously observed approximate baseline of 17.5 GB free on 238 GB, 15% free is approximately 35.7 GB total free, so the approximate incremental gap is 18.2 GB. Production code must use live measurements rather than hardcoded screenshot values.

## 9. Privacy/runtime storage

All real workstation outputs must live beneath ignored runtime state:

```text
var/runs/<run_id>/
```

Never commit real:

- paths;
- filenames;
- hashes;
- inventory rows;
- scan errors containing private paths;
- review queues;
- proposed-action manifests;
- approval records;
- quarantine contents;
- live receipts.

Synthetic fixtures only in tracked tests/examples.

## 10. CLI contract

Preserve the repository's existing command vocabulary rather than creating a second system.

Required Phase 1-4 executable seams:

```text
filesteward scan <synthetic-root> --run-dir <runtime-dir>
filesteward validate <run-or-manifest>
filesteward plan <inventory-or-run>     # only if this extra command is needed
```

`filesteward apply` may exist only as a dry-run/refusal seam if needed by tests. It must not perform real permanent deletion.

The console entry point must be defined by `pyproject.toml` and proven executable, not merely importable.

## 11. Call-stack acceptance matrix

### S1 — CLI read-only happy path

```text
CLI
 -> CleanupRun
 -> synthetic scanner
 -> ProtectionIndex
 -> rules/gates
 -> challenge
 -> artifact writers
 -> summary
```

Pass if artifacts reconcile and fixture filesystem is unchanged.

### S2 — protected descendant

An item under a synthetic protected repo/worktree is `PROTECTED` before reclaim nomination and appears in protected exclusions.

### S3 — large semantic ambiguity

Synthetic 4.8 GB archive with no proven provenance/recoverability -> `HUMAN_REVIEW`.

No delete score. No "probably safe" language.

### S4 — provisional reclaim survives challenge

A synthetic deterministic cache artifact with explicit contract evidence passes gates and independent challenge -> `RECLAIM_PROVEN`.

Projected reclaim math uses supported allocation evidence or is explicitly labeled estimate.

### S5 — challenge defeat

Rules nominate reclaim, but strongest plausible loss case cannot be deterministically defeated -> downgrade to `HUMAN_REVIEW`.

No upward promotion during challenge.

### S6 — mixed directory

Directory contains reclaimable + ambiguous descendants -> directory itself cannot be `RECLAIM_PROVEN`; decompose.

### S7 — protected-subtree ancestor

A parent contains a protected repo plus an unrelated sibling.

Whole-parent action is prohibited; protected subtree excluded; unrelated sibling remains independently evaluable.

### S8 — real Git semantics in temp repo

Create a temporary synthetic Git repository/worktree and prove protection discovery against it.

Do not scan the operator's real repositories for this test.

### S9 — junction/reparse no-follow

Scanner does not recursively traverse a reparse/junction target by default.

If portable fixture creation is unavailable, preserve a Windows-specific test with a precise skip reason and a deterministic adapter-unit test.

### S10 — symlink no-follow

Scanner records symlink metadata without silently traversing target as ordinary child content.

### S11 — access denied / unreadable

Unreadable item/subtree -> explicit scan gap / `UNKNOWN`, never inferred absent.

### S12 — cloud placeholder no-hydration seam

Inventory logic must not open/read an online-only placeholder merely to classify metadata.

If a real placeholder cannot be synthesized, prove the adapter decision seam without touching operator data.

### S13 — system/application-managed mutation exclusion

A synthetic path marked as system/application-managed may be inventoried but cannot become an automatic mutation candidate without an explicit adapter/contract.

### S14 — incomplete directory fail-closed

Directory containing unreadable/unknown descendant cannot be considered whole-directory reclaimable.

## 12. Mutation-proof fixture test

Before and after S1, snapshot at least:

- relative path;
- entry type;
- file size;
- content hash for regular files;
- relevant timestamps if scanner contract claims not to alter them.

Assert no creation, deletion, rename, type change, or byte mutation.

## 13. Adversarial challenge contract

The challenger is deliberately asymmetric.

For every provisional reclaim candidate:

> Construct the strongest plausible case that acting on this item could cause loss, broken state, lost evidence, rework, or difficult recovery.

Inputs:

- normalized `InventoryItem`;
- normalized gate results;
- provisional disposition.

Forbidden input:

- private internals of the nominating rule used solely to rationalize its decision.

Allowed result:

- sustain `RECLAIM_PROVEN`;
- downgrade to `HUMAN_REVIEW`.

Forbidden result:

- promote ambiguity into reclaim;
- invent missing provenance/recoverability;
- lower evidence gates.

## 14. Artifacts

### cleanup-plan.csv

Proposed reclaim evidence only. Never approval.

Required fields include:

- priority;
- item_id;
- path;
- logical_size_bytes;
- allocated_size_bytes;
- projected_reclaim_bytes;
- reclaim_basis;
- disposition;
- confidence_basis;
- evidence;
- protection_check;
- recoverability;
- canonical_survivor where relevant;
- proposed_action;
- cumulative_projected_reclaim_bytes;
- projection_quality.

Only `RECLAIM_PROVEN` rows may appear here.

### human-review.csv

Required fields include:

- item_id;
- path;
- size/reclaim evidence;
- why_ambiguous;
- what_operator_should_check;
- known_context;
- risk_if_acted_on.

No delete score and no persuasive recommendation.

### protected-exclusions.csv

Required fields include:

- item_id/path;
- protection reason;
- protection source;
- containment/decomposition relationship where relevant.

### cleanup-summary.md

Must distinguish:

- logical bytes observed;
- allocated bytes known;
- projected reclaim estimate;
- proven reclaim only where genuinely supported;
- baseline free bytes;
- target free bytes;
- incremental gap;
- projected stop point;
- number/size of human-review items;
- number/size of protected items;
- unreadable/unknown coverage.

## 15. Future apply contract — design only

Do not implement real apply in this sprint.

Document that any future mutation must revalidate immediately before action:

- exact approved manifest digest;
- exact approved row/action;
- path remains inside approved scope;
- source still exists;
- identity has not materially changed;
- protection index freshly rebuilt;
- no new protected overlap;
- canonical survivor still exists for duplicate-based actions;
- quarantine destination capacity;
- destination collision rules;
- required filesystem semantics.

Mismatch -> fail closed.

Ordinary cleanup action initially means quarantine + audit/restore receipt, not permanent deletion.

## 16. P04 factoring

### Runtime partition

| Field | Resolution |
|---|---|
| HOST | `LOCAL_AGENT_RUNTIME` |
| Provider access | GitHub through locally authenticated `gh` only when provider truth is required |
| Private data | local ignored runtime only |
| Current ChatGPT runtime | planning/governance owner, not local-filesystem executor |
| Live C: access | FORBIDDEN in Phase 1-4 |

### Dependency graph

The implementation is deliberately contract-first. Shared models and safety semantics are consumed by every later layer, so broad parallel mutation is not safe.

```text
L0 contract/package floor
 -> L1 inventory + Windows traversal + protection
 -> L2 dispositions + evidence gates + adversarial challenge
 -> L3 orchestration + CLI + artifacts
 -> L4 S1-S14 integration proof + critique/refactor + docs
```

**Graph width:** 1 for mutation ownership at the accepted integration boundary.

`PARALLEL EXECUTION: NOT_APPLICABLE — dependency graph width is 1 after shared-contract/collision analysis.`

Do not manufacture parallel lanes merely because multiple files exist.

## 17. Lane cards

### L0 — Contract + package floor

**Mission:** establish package/CLI skeleton and exact domain contracts before logic.  
**Owned:** `pyproject.toml`, package skeleton, `models.py`, policy constants, test skeleton.  
**Forbidden:** real disk traversal, apply/quarantine, live private artifacts.  
**Proof:** CLI entry point executes; model enums/states tested; runtime path resolves under ignored `var/`.

### L1 — Inventory + Windows safety + protection

**Depends on:** L0.  
**Mission:** implement streaming inventory and protection semantics.  
**Owned:** inventory/protect modules + focused tests.  
**Proof:** S2, S7-S12, relevant S14 components green.  
**Forbidden:** reclaim judgment beyond protection/scan completeness.

### L2 — Deterministic disposition + challenge

**Depends on:** L1.  
**Mission:** implement rules/gates and independent downgrade challenge.  
**Owned:** classify modules + focused tests.  
**Proof:** S3-S6 and fail-closed conflicts green.  
**Forbidden:** human semantic resolution, approval, apply.

### L3 — Orchestration + artifacts

**Depends on:** L2.  
**Mission:** wire read-only run, artifact schemas/writers, free-space projection.  
**Owned:** run/CLI/artifact modules + tests.  
**Proof:** cleanup plan contains only `RECLAIM_PROVEN`; review/protected queues reconcile; CLI path works end-to-end on synthetic fixture.

### L4 — Integration proof + critique

**Depends on:** L3.  
**Mission:** run complete S1-S14 matrix, mutation snapshot, CLI smoke, repository checks, adversarial architecture critique; perform at most bounded refactor(s) required by actual findings.  
**Owned:** tests/docs and necessary bounded repairs.  
**Proof:** acceptance checklist below green.  
**Stop:** no live `C:` scan.

## 18. Phase 1-4 acceptance checklist

The sprint is PASS only when every applicable item is proven.

### Repository / governance

- [ ] Correct repository and branch proven.
- [ ] `AGENTS.md`, local-agent protections, README, and this plan read.
- [ ] Work remains off `main`.
- [ ] No unrelated work overwritten.
- [ ] No real private data committed.

### Package / CLI

- [ ] `pyproject.toml` exists.
- [ ] supported Python floor declared.
- [ ] package discovery works.
- [ ] `filesteward` console entry point executes.
- [ ] existing scan/validate/apply vocabulary is not silently replaced.
- [ ] any new `plan` command is justified and documented.

### Safety semantics

- [ ] disposition and authorization state are separate.
- [ ] manifest is not approval.
- [ ] `HUMAN_REVIEW` is operator-owned ambiguity.
- [ ] `UNKNOWN` represents incomplete/technical evidence.
- [ ] `PROTECTED` cannot be overridden by heuristic rules.
- [ ] adversarial challenge can only sustain or downgrade a provisional reclaim.
- [ ] no age/size/name/location-only reclaim rule.
- [ ] no permanent deletion implementation.

### Filesystem / Windows

- [ ] streaming/iterable scanner seam.
- [ ] protected descendant semantics correct.
- [ ] protected-containing ancestor decomposes rather than globally protecting siblings.
- [ ] Git/worktree synthetic discovery works.
- [ ] reparse/junction no-follow behavior proven or precisely skipped with adapter-unit proof.
- [ ] symlink no-follow behavior proven.
- [ ] unreadable entries become explicit `UNKNOWN`/scan gaps.
- [ ] cloud-placeholder path does not hydrate content for inventory.
- [ ] system/application-managed mutation exclusion exists.
- [ ] incomplete directory cannot become whole-directory reclaimable.
- [ ] hard-link/reclaim limitations are modeled honestly.

### Reclaim projection

- [ ] logical and projected reclaim bytes are distinct.
- [ ] exact reclaim is not claimed from logical size alone.
- [ ] hard-link uncertainty cannot produce false exact reclaim.
- [ ] stop point uses `baseline_free + cumulative_reclaim >= target_free`.
- [ ] screenshot numbers are not hardcoded as production constants.

### Artifacts

- [ ] `cleanup-plan.csv` contains only `RECLAIM_PROVEN`.
- [ ] `human-review.csv` has no delete/recommendation score.
- [ ] `protected-exclusions.csv` records reason/source.
- [ ] `cleanup-summary.md` separates estimates from proof.
- [ ] artifacts reconcile by stable `item_id`.
- [ ] live/private artifact root is ignored.
- [ ] tests/fixtures are synthetic only.

### Proof

- [ ] S1-S14 pass, or any environment-specific skip is explicit and does not falsely prove the skipped behavior.
- [ ] fixture mutation snapshot proves no creation/deletion/rename/type/content mutation during analysis.
- [ ] `python -m pytest -q` passes.
- [ ] CLI smoke test passes.
- [ ] `git diff --check` passes.
- [ ] adversarial design critique performed.
- [ ] critique produces either a bounded repair + rerun or explicit evidence that no defect was found.
- [ ] no live `C:` traversal occurred.
- [ ] no file action/quarantine/delete occurred.

### Integration/reporting

- [ ] changed files listed.
- [ ] validation commands/results listed.
- [ ] skipped checks + reasons listed.
- [ ] commit SHA reported.
- [ ] push/PR state reported.
- [ ] proof ceiling says NOT LIVE-AUDITED.
- [ ] exact Phase 5 read-only command proposed, but not run.

## 19. Phase 5 gate — do not cross automatically

After Phase 1-4 passes, STOP.

Provide the exact bounded command that would perform the first real read-only workstation audit.

The operator must explicitly authorize crossing:

```text
synthetic implementation proof
    ->
real workstation read-only observation
```

No phrase such as "same run", "next logical step", or "read-only anyway" substitutes for that authorization.

## 20. Final Phase 1-4 report contract

The executing agent must report:

```text
COMPLETED
CREATED/MODIFIED FILES
VALIDATION / PROOF
SKIPPED CHECKS + WHY
UNRESOLVED GAPS/RISKS
ARTIFACT / LOG PATHS
BRANCH / COMMIT / PUSH / PR STATE
LIVE AUDIT STATE: NOT RUN
OPERATOR APPROVAL STATE: NOT GRANTED
APPLY STATE: NOT RUN
RECLAIM STATE: 0 BYTES VERIFIED
NEXT: exact Phase 5 read-only command, then STOP
```

Do not use "done" if any mandatory gate is red.

## 21. OpenCode-specific execution rule

OpenCode must behave as a bounded implementer.

It is explicitly forbidden to "use judgment" to make the safety contract more convenient.

When uncertain:

1. preserve the ambiguity;
2. encode the uncertainty in a typed state/test;
3. keep the item out of reclaim/action surfaces;
4. continue with independent deterministic work;
5. ask the operator only if implementation cannot proceed without a genuinely semantic decision.

The operator is not a context courier or routine test runner.

The agent is not the operator's substitute for judgment.
