# Safe Capacity Reclamation — P04 + P82 — 2026-10-07

**Sprint ID:** `FILESTEWARD-SAFE-CAPACITY-20261007`  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Execution floor:** `main@81cc58c51b55c249710b1438b11a956fea8efe12`  
**Planning branch:** `plan/safe-capacity-p04-p82-20261007`  
**Operator outcome:** FileSteward must recover meaningful disk capacity without breaking installed applications, repositories, or serviceability.

## 1. Current truth

This is a successor to `FILESTEWARD-DEPENDENCY-AWARE-JUDGMENT-20261007`; it does not replace its safety doctrine.

Already merged to `main`:

- J0 containment: generic `%PROGRAMDATA%\Package Cache` raw-delete admission removed.
- J2: Windows application attribution adapters.
- J3: repository/project attribution adapters with Entire as context evidence only.
- J4: revisioned cross-domain ownership graph + most-protective-edge-wins reducer.
- Wispr archetype encoded: a surviving installed-app registration with a missing updater/uninstaller is a broken/serviceability dependency, not an orphan signal.

Still open:

- J1 forensic causality remains workstation-local. The operator reports that deletion of Wispr Flow application files broke the installation; repository proof must continue to distinguish operator report from independently reproduced causality.
- J5 deletion/cleanup-plan integration is not complete.
- J6 scene integration must reconcile the current Decision Chamber lineage (PR #29) before visualization mutation.
- J7 P82 falsification/live proof is not complete.

## 2. Product theorem

FileSteward is not a file deleter that happens to know about applications.

FileSteward is a **capacity recovery orchestrator** that chooses the lowest-risk, owner-correct action capable of restoring healthy free space.

Canonical loop:

```
MEASURE CAPACITY
  -> DISCOVER LARGE/RECLAIMABLE SURFACES
  -> ATTRIBUTE OWNERSHIP
  -> CLASSIFY CONSEQUENCE
  -> PROVE RECOVERABILITY
  -> SELECT OWNER-CORRECT ACTION
  -> REFRESH EVIDENCE
  -> AUTHORIZE EXACT MUTATION
  -> EXECUTE
  -> VERIFY CAPACITY + SERVICEABILITY
  -> STOP WHEN HEALTHY
```

Default capacity policy remains:

- healthy: free ratio >= 20%
- degraded: 10% <= free ratio < 20%
- critical: free ratio < 10%

Capacity state affects ranking and urgency only. It never changes evidence or authorization.

## 3. Hard safety boundary

Raw recursive deletion is **not** the default reclaim primitive.

A path may enter the permanent-delete lane only when all of these are true:

1. ownership is resolved;
2. no app runtime/serviceability/service/task/package/repository protection edge intersects the candidate;
3. the candidate is an exact regenerable/generated artifact, not an installation footprint;
4. deterministic regeneration/reproduction evidence exists;
5. the ownership graph revision is bound into the delete artifact;
6. fresh preflight recomputes ownership/consequence and rejects drift;
7. operator authorization is bound to the exact item set/action;
8. repository-owned executor performs the mutation and emits a receipt.

Unknown ownership, stale ownership evidence, or conflicting owners fail away from raw deletion.

### Never raw-delete in the first safe-capacity implementation

- `%WINDIR%\Installer`
- `%PROGRAMDATA%\Package Cache`
- a registered application's install root
- a path containing the registered uninstall/update/modify/repair executable
- a service executable/script target
- a scheduled-task executable/script target
- a running executable/module path
- an MSIX/AppX install root
- a repository with dirty, staged, untracked, local-only, unpushed, or otherwise unique work
- any path whose ownership adapters have not completed

These surfaces may have semantic actions such as uninstall, repair, vendor cleanup, archive, or review. They do not become raw-delete candidates merely because they are large.

## 4. Owner-correct action ladder

FileSteward should recover capacity in this order, stopping once the capacity target is satisfied.

### Tier 0 — zero-judgment proven reclaim

Use only repository-owned, deterministic contracts for exact regenerable outputs whose owner semantics are already known. Examples may include explicitly modeled tool caches or build outputs.

Required: owner + regeneration recipe + fresh proof.

### Tier 1 — semantic cache cleanup

Invoke or model the owning application's supported cache-clean operation when available.

A directory named "cache" is not sufficient. The adapter must identify the owning application and the cache contract.

### Tier 2 — generated repository outputs

Offer removal of build/generated outputs only when:

- the repository itself remains protected;
- the output is independently reproducible;
- no untracked/unique work is co-located in the exact target;
- deletion does not widen to the repository root.

### Tier 3 — application uninstall

When the operator does not want an installed application, prefer its registered installer/vendor uninstall path. FileSteward should not simulate uninstall by deleting files.

### Tier 4 — repository/archive decision

A clean reproducible clone may be offered as a value decision. Whole-repository removal is never automatic and must expose remote/reproducibility/unique-work evidence.

### Tier 5 — orphan investigation

Only after safe adapters are exhausted may an unowned surface become `HUMAN_REVIEW`. Absence of evidence never promotes it to `RECLAIM_PROVEN`.

## 5. P04 execution graph

```
K0 CURRENT-TRUTH / J0-J4 READBACK
 |
 +--> K1 SAFE-CANDIDATE GATE (J5A)
 |      owns cleanup-plan admission + ownership judgment projection
 |
 +--> K2 SEMANTIC ACTION PLANNER (J5A)
 |      owns KEEP / CLEAN_CACHE / REPAIR / UNINSTALL / REPO_OUTPUT_CLEAN / REVIEW
 |
 +--> K3 DEPENDENCY-BOUND PREFLIGHT (J5B)
 |      binds ownership graph revision/digest and re-resolves before execute
 |
 +--> K4 RECEIPT + POSTCONDITION (J5C)
 |      records action kind, owner, proof revision, bytes, and verification state
 |
 +--> K5 CAPACITY STRATEGY / STOP RULE
 |      ranks legal actions by reclaim value and friction; stops >=20% free
 |
 +--> K6 DECISION SCENES (J6)
 |      depends on refreshed PR #29 reconciliation; no parallel visualization rewrite
 |
 +--> K7 P82 ADVERSARIAL + BOUNDED LIVE PROOF (J7)
        depends on K1-K6 as applicable
```

### K1 — safe-candidate gate

**Owned scope**
- cleanup-plan candidate admission
- bridge from `PathOwnershipJudgment` into cleanup disposition/actionability
- exact reason codes for blocked candidates
- tests

**Forbidden**
- visualization rewrite
- widening regenerable roots
- app uninstall execution
- workstation deletion

Acceptance:
- no candidate with app/serviceability/repo protection can become raw-delete eligible;
- unknown ownership stays non-actionable;
- most-protective-edge-wins survives plan generation.

### K2 — semantic action planner

Introduce an action plan separate from `CleanupDisposition`.

Minimum action vocabulary:

- `KEEP`
- `CLEAN_CACHE`
- `CLEAN_GENERATED_OUTPUT`
- `REPAIR_APPLICATION`
- `UNINSTALL_APPLICATION`
- `ARCHIVE_OR_REMOVE_REPOSITORY`
- `INVESTIGATE_ORPHAN`
- `RAW_DELETE_REGENERABLE_ARTIFACT`

Rules:

- application installation/serviceability edges may emit repair/uninstall/keep, never raw delete;
- repository roots may emit keep/archive/remove decision, never automatic delete;
- exact generated outputs may emit clean actions when reproduction is proven;
- unknown emits investigate only.

### K3 — dependency-bound preflight

Extend permanent-delete manifest/preflight so every item carries:

- ownership graph revision id;
- normalized owners;
- consequence classes;
- action kind;
- regeneration/reproduction proof reference or digest;
- evidence timestamp/freshness contract.

Preflight must recompute the relevant ownership/consequence slice immediately before execution.

New fail classes should include:

- `OWNERSHIP_REVISION_DRIFT`
- `APP_DEPENDENCY_PRESENT`
- `SERVICEABILITY_DEPENDENCY_PRESENT`
- `REPOSITORY_UNIQUE_WORK_PRESENT`
- `REGENERATION_PROOF_MISSING`
- `SEMANTIC_ACTION_REQUIRED`

Any one blocks raw deletion.

### K4 — receipt + postcondition

A successful reclaim receipt must say what kind of action occurred, not just what bytes disappeared.

Record:

- action kind;
- owner identity;
- before/after ownership graph revision;
- exact items;
- reclaim bytes;
- capacity before/after;
- semantic executor used;
- postcondition state: `VERIFIED`, `PARTIAL`, `UNVERIFIED`.

"Bytes reclaimed" alone is not proof that the action was safe.

### K5 — capacity strategy

Rank only legal actions.

Suggested ranking inputs:

1. safety class / semantic correctness (hard gate, not score);
2. projected reclaim bytes;
3. execution friction;
4. recoverability/reversibility;
5. user value decision required;
6. capacity urgency.

Do not use an LLM confidence score to override any hard gate.

Stop generating additional deletion pressure once target free capacity is reached.

### K6 — scenes

Reconcile PR #29 against current `main` and J4 ownership contracts before touching visualization.

The operator should see:

- **what owns these bytes**;
- **what breaks if they disappear**;
- **what the safe action is**;
- **why raw delete is unavailable**;
- **how much capacity the safe action is expected to recover**.

The journey remains:

`MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED -> VERIFY`

Dependency-aware scenes extend RESOLVE; they do not create a second router/state machine.

### K7 — P82 falsification

Use `harness/evals/storage-reclamation-p82-corpus.v1.json` as the adversarial oracle.

Required proof ladder:

```
focused synthetic fixtures
 -> integration tests across scan/plan/preflight
 -> full repository suite
 -> provider readback/review
 -> bounded live read-only attribution on workstation
 -> one owner-safe reclaim canary
 -> post-action capacity + serviceability verification
```

A failed gate routes to repair and retry. It does not become a completion claim.

## 6. P82 adversarial requirements

At minimum falsify against:

### Applications
- Squirrel/Electron-style user-scoped install with `Update.exe`;
- surviving uninstall registration with missing updater/uninstaller (Wispr archetype);
- Windows Installer serviceability cache;
- WiX/Burn `%ProgramData%\Package Cache`;
- ordinary app cache with deterministic regeneration;
- cache nested beneath an installation root;
- running app/module;
- Windows service target;
- Scheduled Task target;
- MSIX/AppX package root;
- portable application with no installer registration;
- shared dependency used by more than one owner;
- unknown third-party directory.

### Repositories
- clean pushed clone;
- dirty repo;
- staged changes;
- untracked unique files;
- local-only/unpushed branch;
- detached/linked worktree;
- nested repo/submodule;
- generated output in repo;
- provider/network unavailable;
- Entire has no session/activity evidence for a still-valid repository.

### Filesystem / race
- symlink/junction/reparse;
- hardlink ambiguity;
- target changed after plan;
- owner registration changed after approval;
- app updated between approval and preflight.

## 7. Quantitative acceptance gates

- false-positive raw-delete eligibility on protected/serviceability/unique fixtures: **0**
- raw-delete candidate without owner-specific regeneration proof: **0**
- raw-delete candidate under `%WINDIR%\Installer`: **0**
- raw-delete candidate under `%PROGRAMDATA%\Package Cache`: **0**
- whole installed-app root offered as raw delete while registered: **0**
- stale ownership revision accepted by preflight: **0**
- unknown ownership promoted to reclaim: **0**
- repo unique work promoted to reclaim: **0**
- post-action receipt missing action/owner/proof revision: **0**
- capacity strategy continuing to pressure deletion after healthy target is met: **0**

## 8. External design provenance

P82 reference facts used to harden the plan:

- Microsoft Learn: Windows Installer cache files are required for repair/update/uninstall and should not be deleted.
  - https://learn.microsoft.com/en-us/troubleshoot/windows-client/application-management/missing-windows-installer-cache
- Microsoft Learn: uninstall registry metadata exposes install/serviceability identity such as InstallLocation, ModifyPath, and UninstallString.
  - https://learn.microsoft.com/en-us/windows/win32/msi/uninstall-registry-key
- FireGiant/WiX: Burn uses `%ProgramData%\Package Cache` as its default package cache and retains package data for bundle/package lifecycle operations.
  - https://docs.firegiant.com/wix/development/wips/4278-allow-administrators-and-users-to-redefine-the-payload-cache-locations/
  - https://docs.firegiant.com/wix/whatsnew/faqs/

These references inform safety invariants; FileSteward's repository contracts remain the executable authority.

## 9. Proof semantics

Report separately:

`designed -> contract-encoded -> implemented -> locally-validated -> integration-validated -> committed -> pushed -> PR-open -> merged -> live-readonly-attributed -> cleanup-canary-applied -> postcondition-verified -> capacity-verified`

## 10. Immediate successor

The next local implementation pass is **K1 + K2 first**, with K3 design/tests prepared in parallel only where interfaces are stable.

Do not ask the local agent to decide whether application files are safe to delete. The answer is now deterministic:

- if FileSteward can prove an owner-correct semantic cleanup action, use that;
- if FileSteward can prove an exact regenerable artifact, raw delete may proceed through the existing delete architecture;
- otherwise, fail closed and continue to the next legal capacity-recovery candidate.
