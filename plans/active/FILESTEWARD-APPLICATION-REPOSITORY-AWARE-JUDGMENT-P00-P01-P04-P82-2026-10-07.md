# Application / Repository-Aware Storage Judgment — P00 + P01 + P04 + P82 — 2026-10-07

**Sprint ID:** `FILESTEWARD-DEPENDENCY-AWARE-JUDGMENT-20261007`  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Planning floor:** `main@610f4fe624bfdf7c9577bcbc28ac2bea394c81f5`  
**Planning branch:** `plan/application-repo-aware-judgment-20261007`  
**Operator outcome:** make storage cleanup fast and confidence-building without breaking installed applications, repositories, or recoverability.

## 1. Why this sprint exists

The 2026-10-06/07 reclaim program succeeded at its narrow byte-reclamation objective and brought C: above the 50 GB target. Immediately afterward, Wispr Flow no longer worked on the workstation.

That temporal correlation is **incident evidence, not yet root-cause proof**. FileSteward must not claim that a specific deleted path broke Wispr Flow until the ignored runtime receipts and local application evidence prove the relationship.

However, current repository truth exposes a systemic defect independent of the final Wispr root cause:

- `src/filesteward/deletion/regenerable.py` treats `%PROGRAMDATA%\Package Cache` as a generic regenerable-cache root;
- the corresponding tests explicitly require that root to be admitted for permanent deletion;
- installer/package caches can be serviceability dependencies for installed applications.

Therefore **cache-looking location is not sufficient evidence of regenerability**. The existing contract must be strengthened before FileSteward broadens cleanup again.

## 2. P00 — evidence-before-confidence / incident containment

### Immediate containment decision

Until an application-aware dependency adapter proves otherwise:

1. `%PROGRAMDATA%\Package Cache` is **not** an automatic permanent-delete seam.
2. It must be treated as `PROTECTED` for generic cleanup.
3. A future per-entry orphan detector may downgrade an individual entry to `HUMAN_REVIEW`; it may not infer `RECLAIM_PROVEN` merely because an entry is old, large, or under Package Cache.
4. Existing live receipts remain evidence and must not be rewritten to hide the incident.
5. Future cleanup is allowed to continue on independently proven safe seams; this incident does not require freezing all FileSteward work.

### Incident proof lane

Local execution must recover, without committing private workstation data:

- the exact deletion receipts from the reclaim run(s);
- which roots/items were successfully removed;
- Wispr Flow executable/install location and current launch failure;
- uninstall/repair metadata;
- whether deleted items were referenced by Wispr Flow, one of its dependencies, or its installer/serviceability chain;
- whether repair/reinstall restores operation.

The incident ends in one of:

- `CAUSAL_LINK_PROVEN`
- `CAUSAL_LINK_DISPROVEN`
- `CORRELATED_UNRESOLVED`

No stronger claim is permitted without evidence.

## 3. Product objective: storage health without deletion pressure

FileSteward should optimize toward **healthy free capacity**, not toward a volume of deleted bytes.

Default workstation policy for this program:

- `target_free_ratio = 0.20`
- `critical_free_ratio = 0.10`

Meaning:

- at or above 20% free: healthy;
- between 10% and 20%: prioritize low-friction cleanup decisions;
- below 10%: surface urgency and the highest-value proven actions first.

These thresholds affect **priority and scene emphasis only**. They never promote evidence, create deletion authority, or weaken safety gates.

The existing free-space stop condition remains authoritative: once the target is met, FileSteward should stop manufacturing additional deletion pressure.

## 4. Core judgment theorem

A path is not safely disposable until FileSteward can answer the relevant ownership and consequence questions.

For every meaningful candidate, derive a normalized evidence graph:

```text
FILE / DIRECTORY
  -> belongs_to / installed_by / used_by / repair_source_for / generated_by
  -> APPLICATION / PACKAGE / SERVICE / TASK / REPOSITORY / TOOLCHAIN / USER_DATA
  -> recoverability evidence
  -> consequence class
  -> CleanupDisposition
```

### Required consequence classes

- `APP_RUNTIME_DEPENDENCY`
- `APP_SERVICEABILITY_DEPENDENCY`
- `APP_CACHE_REGENERABLE`
- `APP_CACHE_UNKNOWN`
- `SERVICE_DEPENDENCY`
- `SCHEDULED_TASK_DEPENDENCY`
- `REPOSITORY_TRACKED`
- `REPOSITORY_DIRTY_OR_UNPUSHED`
- `REPOSITORY_REPRODUCIBLE_CLONE`
- `TOOLCHAIN_DEPENDENCY`
- `USER_DATA`
- `ORPHAN_CANDIDATE`
- `UNKNOWN_OWNERSHIP`

### Disposition floor

- runtime/serviceability/service/task/toolchain dependency -> `PROTECTED`;
- dirty/unpushed/unique repository evidence -> `PROTECTED`;
- unknown ownership or ambiguous orphan evidence -> `HUMAN_REVIEW` or `UNKNOWN`;
- reproducible app cache -> may reach `RECLAIM_PROVEN` only through an adapter with deterministic regeneration evidence;
- clean reproducible clone -> may be offered as a **decision**, never silently auto-deleted;
- absence of ownership evidence is never evidence of disposability.

## 5. Windows application evidence adapters

Implement read-only adapters that can attribute files/directories to installed software before cleanup disposition.

Priority evidence sources:

1. HKLM/HKCU uninstall registry records, including 32/64-bit views;
2. install location, display icon, uninstall/modify/repair command metadata;
3. Windows Installer / MSI product identity through side-effect-free APIs and registry-backed evidence;
4. WiX/Burn bundle/cache identity where present;
5. AppX/MSIX package manifests and install roots;
6. Windows services and their executable paths;
7. scheduled tasks and referenced executables/scripts;
8. Start Menu/Desktop shortcut targets as corroborating evidence;
9. currently running processes and executable/module paths as runtime evidence;
10. file version/product/company metadata and signing identity as corroboration;
11. package-manager inventory such as winget only as supporting evidence, never sole authority.

### Forbidden probe

Do **not** use `Win32_Product` / `Get-CimInstance Win32_Product` as an inventory mechanism because inventory must remain read-only and side-effect free.

### Application cleanup actions

When FileSteward discovers storage owned by an installed application, the preferred actions should be semantically correct:

- clean an application-defined cache;
- invoke uninstall/modify/repair through the owning installer when the operator wants the app removed;
- keep runtime/serviceability dependencies;
- investigate orphan status;
- only use raw permanent deletion when the dependency graph proves the bytes are independent of application function/serviceability.

FileSteward should prefer **uninstalling an unwanted application** over deleting its installation or installer support files piecemeal.

## 6. Repository / project evidence adapters

The existing Git/worktree ProtectionIndex remains the deletion safety owner for discovered repositories. This sprint adds richer classification and operator decision support; it does not weaken protection.

For every discovered Git repository/worktree collect, where available:

- repository root and worktree relation;
- current branch / detached state;
- dirty, staged, untracked state;
- remotes;
- ahead/behind or push-equivalence evidence when network/provider access is available;
- last commit time;
- nested repositories/submodules;
- linked worktrees;
- size by tracked/untracked/build/cache partitions;
- whether a clean clone from a known remote can reproduce the tree;
- whether generated/build artifacts are independently reclaimable.

Result examples:

- `ACTIVE_REPOSITORY`
- `DIRTY_UNIQUE_WORK`
- `CLEAN_REPRODUCIBLE_CLONE`
- `ARCHIVE_CANDIDATE`
- `BUILD_OUTPUT_RECLAIMABLE`
- `REPOSITORY_STATUS_UNKNOWN`

A repository may be stale yet valuable. Age alone never grants deletion authority.

## 7. Entire CLI / Brain / Graph integration

Entire is a context and evidence accelerator, not a filesystem mutation authority.

When installed on the local host, start orientation with:

```text
entire status --json
entire agent-help --json
```

Use current Entire capabilities to recover prior implementation/context efficiently:

- Entire checkpoints/sessions for why FileSteward rules changed;
- `entire search --compact` / code search for prior decisions and regressions;
- Entire Brain, when installed, for retained repository facts and prior agent decisions;
- Entire Graph, when installed, for code structure, definitions, callers, and change-impact discovery.

The agent must still verify current source, runtime, Git/provider state, and tests before acting.

The operator mentioned **Mini**. This plan does **not** fabricate a Mini API or dependency. The local agent must discover the installed Entire capability set using `entire agent-help --json` / plugin listing. If a supported Mini capability exists locally, record its exact command/schema and use it where it strengthens evidence. If not, continue without it.

## 8. P01 — durable harness / contract requirements

This incident class must become mechanically difficult to repeat.

Canonical machine contract:

`harness/contracts/storage-dependency-judgment.v1.json`

The implementation must eventually enforce:

1. cache-looking path != regenerability proof;
2. application-managed paths require ownership/consequence evaluation;
3. generic `%PROGRAMDATA%\Package Cache` deletion is prohibited;
4. app/runtime/serviceability dependencies cannot become `RECLAIM_PROVEN`;
5. repository discovery protects the repo while classification enriches the UX;
6. dependency evidence is re-evaluated before destructive execution when proof-relevant state can change;
7. deletion receipts preserve dependency-evidence revision/digest sufficient for post-incident audit;
8. one broken-app incident becomes a regression fixture, not a chat memory.

## 9. P04 — implementation graph and ownership

```text
J0 contract + emergency containment
 |
 +--> J1 incident evidence / Wispr correlation (read-only runtime lane)
 |
 +--> J2 Windows application attribution adapters
 |
 +--> J3 repository/project attribution adapters
          |
          +------------------+
                             v
                    J4 dependency graph + disposition reducer
                             |
                    J5 cleanup-plan / deletion integration
                             |
                    J6 scenes + filtered decision views
                             |
                    J7 P82 live falsification + incident regression
```

### J0 — emergency containment
**Owns:** `deletion/regenerable.py`, focused tests, delete-path contracts.  
**Must do first:** remove generic ProgramData Package Cache admission; add regression proof.  
**Forbidden:** broad new cleanup roots.

### J1 — incident evidence
**Owns:** ignored `var/runs/**` and workstation inspection only; tracked output limited to sanitized incident conclusions/tests if proven.  
**Parallel-safe with J2/J3.**  
**Forbidden:** committing private paths/receipts.

### J2 — app attribution
**Owns:** new application-evidence adapters + tests.  
**No visualization edits.**

### J3 — repo attribution
**Owns:** Git/project evidence adapters + tests.  
**Must reuse existing `ProtectionIndex.from_git_discovery`; do not replace it.**

### J4 — dependency graph/reducer
**Depends:** J2 + J3.  
**Owns:** normalized evidence graph, consequence classes, disposition integration, explainability payload.

### J5 — deletion integration
**Depends:** J0 + J4.  
**Owns:** manifest/preflight integration so dependency evidence can block stale/unsafe deletes.  
**Must preserve:** exact-manifest approval/executor/receipt architecture.

### J6 — scenes / filtered views
**Depends:** J4 and current Decision-to-Deletion UX lineage.  
**Collision rule:** PR #29 currently owns Decision Chamber integration. Do not independently rewrite `src/filesteward/visualization/**` from a backend lane. Reconcile against refreshed PR #29/main truth before UI mutation.

### J7 — validation / live falsification
**Depends:** J0-J6 as applicable.  
**Owns:** P82 evidence loop and live read-only/application-safe probes.

## 10. Scene / impact architecture

Every operator action remains bound by `harness/contracts/action-scene-impact.v1.json`.

Required journey expansion:

```text
CAPACITY
 -> ATTRIBUTION
 -> EVIDENCE
 -> DECIDE
 -> AUTHORIZE
 -> RECLAIM
 -> VERIFY
```

Examples:

- Click a large directory -> **ATTRIBUTION scene**: show app/repo/unknown ownership and consequence evidence.
- Click an installed app footprint -> **APP scene**: show runtime, cache, serviceability, uninstall/repair facts and legal cleanup actions.
- Click a repository -> **REPO scene**: show dirty/remote/reproducibility/build-output status and legal actions.
- Classify/decide -> persist result into filterable views and queues.
- Delete/uninstall/clean -> transition to execution result and measured capacity impact.

No click should merely decorate the same state. Each operable action must orient, classify, decide, authorize, execute, or verify.

## 11. P82 — prototype -> measure -> critique -> refine

Do not accept a plausible classifier without adversarial measurement.

Required falsification corpus:

### Application cases
- active installed app runtime file;
- WiX/Burn or MSI serviceability cache;
- ordinary application cache that is actually regenerable;
- app cache with open handle;
- uninstalled-app orphan candidate;
- shared dependency used by multiple applications;
- service executable;
- scheduled-task target;
- portable app with no installer metadata;
- unknown third-party directory.

### Repository cases
- clean pushed clone;
- dirty repo;
- untracked unique files;
- local-only branch;
- detached worktree;
- nested repo/submodule;
- build output inside repo;
- repo with unavailable remote/network.

### Required metrics
- false-positive deletion eligibility: **0 on protected/serviceability/unique fixtures**;
- every automatic `RECLAIM_PROVEN` app candidate has deterministic regeneration evidence;
- every repo delete recommendation exposes reproducibility + dirty/push state;
- unknown ownership fails away from deletion;
- application/repository evidence appears in scene/filter projections;
- permanent-delete preflight rejects stale dependency evidence.

P82 loop:

```text
implement candidate
 -> run focused fixtures
 -> inspect false positives / unknowns
 -> critique evidence gaps
 -> refine adapters/reducer
 -> rerun
 -> full suite
 -> bounded live read-only proof
```

## 12. Acceptance gates

This sprint is not complete merely because the plan or classifier exists.

- **A0:** ProgramData Package Cache generic deletion path removed and regression-tested.
- **A1:** Wispr incident disposition recorded as proven/disproven/unresolved with preserved local evidence.
- **A2:** application adapter can explain ownership/consequence for representative installed-app footprints.
- **A3:** repository adapter distinguishes protected unique work from reproducible/generated storage.
- **A4:** normalized dependency graph drives disposition without AI-confidence promotion.
- **A5:** delete preflight consumes current dependency evidence and fails closed on drift.
- **A6:** scenes expose attribution, consequence, legal action, and continuation.
- **A7:** 20% target / 10% critical capacity policy appears as prioritization only, not deletion authority.
- **A8:** full repository suite green on exact head.
- **A9:** one bounded live read-only attribution pass proves the model on the workstation.
- **A10:** no new broken-app regression is observed after any subsequent authorized cleanup specimen.

## 13. Proof semantics

Report separately:

`designed -> contract-encoded -> implemented -> locally-validated -> committed -> pushed -> PR-open -> merged -> live-attributed -> incident-causal-state -> cleanup-applied -> verified-capacity`

Do not collapse these states.

## 14. First executable successor

Start **J0 + J1 + J2 + J3**, with J0 on the critical path.

J0 must make the current unsafe generic Package Cache admission impossible before any broader live cleanup.

J1 must preserve the Wispr incident evidence and determine what actually broke without inventing causality.

J2/J3 build the attribution substrate in parallel so FileSteward can make future deletion judgment frictionless because it knows what a file *belongs to*, not because it has become more aggressive about deletion.


## 15. Judgment boundary — make technical judgment deterministic

The product should remove judgment friction by eliminating questions the machine can safely answer.

**Machine-owned technical judgment:** attribution, runtime/serviceability consequence, repo uniqueness/reproducibility, regenerability, evidence freshness, and capacity measurement.

**Operator-owned judgment:** whether an otherwise-safe application/repository is wanted locally, archive/keep preference, and exact authorization for a mutating semantic action.

**Local-agent boundary:** implement the canonical decision system. Do not invent product judgment.

Unknown ownership no longer jumps directly to a vague HUMAN_REVIEW stop. It routes first to the deterministic attribution/consequence/recoverability workflow. HUMAN_REVIEW is legal only after safe adapters are exhausted and must carry the exact unresolved fact, probes attempted, why the fact matters, and only safe choices.

Canonical machine script:

- `harness/contracts/judgment-scene-workflow.v1.json`
- retained regression ledger: `harness/evals/judgment-scene-regression.v1.json`

Missing scene judgment is `BLOCKED_JUDGMENT_GAP`, not an invitation for Cursor/OpenCode to create a new modal, dashboard, action, or policy.

## 16. Deterministic scene script

Preserve the existing immersive tutorial:

```text
MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED
```

Dependency-aware judgment extends **RESOLVE** rather than replacing this journey:

```text
ATLAS_HOME (MAP)
  -> TARGET_FOCUS (FOCUS)
  -> EVIDENCE_GATE (GATE)
  -> ATTRIBUTION_RESOLVE
  -> CONSEQUENCE_RESOLVE
  -> RECOVERABILITY_RESOLVE
  -> VALUE_DECISION
  -> AUTHORIZATION_GATE (APPROVAL)
  -> RECLAIM_EXECUTION (STAGED/execute)
  -> VERIFY_RETURN
  -> next target or ATLAS_HOME

post-action regression
  -> INCIDENT_RECOVERY
  -> VERIFY_RETURN
```

### Scene behavior by construction

| Scene | System does | Operator does | Exit condition |
|---|---|---|---|
| ATLAS_HOME | measures capacity, ranks evidence-bearing candidates, preserves filters | focuses a target | canonical selection changes |
| TARGET_FOCUS | loads known facts and identifies first unresolved gate | opens/continues gate | exact gate known |
| EVIDENCE_GATE | routes missing fact and starts safe probe when possible | acts only if a probe genuinely needs an explicit trigger | typed resolver chosen |
| ATTRIBUTION_RESOLVE | checks app/service/task/repo/toolchain/user-data ownership | nothing unless all safe adapters exhaust | owner or exact unknown recorded |
| CONSEQUENCE_RESOLVE | deterministically classifies what depends on bytes | nothing | consequence/disposition floor known |
| RECOVERABILITY_RESOLVE | proves regeneration/reproduction/reacquisition | nothing | recovery proof or exact uncertainty known |
| VALUE_DECISION | derives only legal semantic actions | chooses keep/remove-app/clean-cache/remove-clone/review-later as applicable | value intent recorded |
| AUTHORIZATION_GATE | refreshes evidence and binds exact target/action | authorizes or backs out | exact current approval exists |
| RECLAIM_EXECUTION | invokes semantic owner action and receipts scope | observes | execution receipt |
| VERIFY_RETURN | measures bytes + health and refreshes queues | continues or returns Home | impact read back |
| INCIDENT_RECOVERY | freezes same-family eligibility, preserves evidence, diagnoses/repairs | only supplies unavoidable external input | causal state + recovery state recorded |

Read-only technical RESOLVE scenes may auto-advance when deterministic, provided their evidence remains inspectable. The system must never auto-select value preference or grant mutation authority.

## 17. P94 regression hardening — immersive scenery is protected behavior

The failure mode is now treated as a retained regression family: local agents repeatedly compress intentional immersive UX into generic implementation surfaces while preserving enough strings/tests to appear complete.

P94 therefore protects at least these behaviors:

1. the decision tree is the tutorial; no second tour;
2. EXPLORE is reserved for genuine exploration;
3. Home uses the canonical Atlas Home authority; no second router;
4. search/filter/selection are orthogonal state and survive unrelated scene transitions;
5. blocked/protected states never look reclaimable;
6. the accepted Memory Atlas material/interaction world is preserved during refinement;
7. contextual pointer treatment remains scoped and accessibility-aware;
8. pointer/keyboard/touch use one semantic action model; no second mobile state machine;
9. every operable action produces transition + impact + feedback + continuation;
10. technical safety is resolved before asking the operator;
11. decisions persist into filterable views/queues;
12. static proof cannot close a live UX claim;
13. tests/fixtures/oracles may not be weakened to fit a broken candidate.

The machine-readable negative fixtures and positive controls live in `harness/evals/judgment-scene-regression.v1.json`. Any scene/interaction change must update that ledger and retain a negative fixture plus positive control.

## 18. Product-design upstream used, without outsourcing authority

This design pass checked current upstream product-design guidance and adopted only mechanics compatible with FileSteward's existing world:

- **Paul Bakaus / Impeccable** — `skill/SKILL.src.md` blob `c413ae26e832b36d54603353f1c7a0ae04784eea`; `skill/reference/operate.md` blob `5e4666de08f63f55c832c7bb2511cc9ad8068744`. FileSteward is an **Operate** surface: task completion, scanability, consistency, real usage scenes, stateful motion, and preservation during refinement outrank decorative novelty.
- **Anthropic / Claude frontend-design** — `plugins/frontend-design/skills/frontend-design/SKILL.md` blob `a5333457c414d20d625f307df945842c0952ecc3`. Adopted: structure must encode information, action copy must name the actual effect, and visual identity should be specific to the product rather than a generic template.
- **Local Prompt Kit remains authority:** P106 owns interaction architecture, P108 bounded polish, P110 cross-viewport/live acceptance, and P94 retained regression behavior.

Upstream resources are prior art, not a license for a local agent to redesign the product.

## 19. P82 validation for this hardening pass

Remote coordination validation must prove before handoff:

- both new JSON artifacts parse from provider readback;
- every transition target names a declared scene;
- no scene with a mutating action bypasses VALUE_DECISION + AUTHORIZATION_GATE;
- technical resolution precedes operator value judgment;
- the protected tutorial remains MAP/FOCUS/GATE/RESOLVE/APPROVAL/STAGED;
- the action-scene and storage-dependency contracts point to the same canonical scene script + regression ledger;
- P94 ledger contains both negative fixtures and positive controls;
- PR #29 is treated as a collision/preservation owner, not silently overwritten.

That proves **remote static design/harness consistency only**. Local tests, browser acceptance, and the visual state of the current application remain separate proof gates.

**P82 remote result (2026-10-07): PASS — 19/19 provider-read-back checks after review-driven J0 repair.** Receipt: `harness/evals/judgment-scene-p82-validation-2026-10-07.json`. This proves the static scene/contract graph plus the source/test shape that removes generic Package Cache admission. It does **not** prove local pytest, browser, or workstation runtime behavior.

### Additional acceptance gates

- **A11:** scripted scene graph has no missing transition targets.
- **A12:** technical safety cannot be delegated to the operator before safe adapter exhaustion.
- **A13:** existing MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED tutorial remains intact.
- **A14:** P94 negative fixtures fail broken candidates and positive controls pass legitimate flows.
- **A15:** desktop + narrow + reduced-motion + forced-colors live acceptance passes, plus supported input modes.
- **A16:** local agents emit BLOCKED_JUDGMENT_GAP instead of inventing scene semantics.


### Review-driven J0 containment repair

Provider review found that the first pass documented the Package Cache incident lock while runtime source still admitted that root. The branch now removes that generic runtime admission and inverts the focused regression so Package Cache must be refused. The handoff also requires a covering operator gate before installer repair, requires dependency evidence to be refreshed immediately before each removal, and records PR #29 reconciliation as an external J6 prerequisite rather than a lane ID.

This raises J0 to **implemented on the remote branch + provider-read-back statically validated**. Local focused and full test execution remain unproven.


## 20. P04 operating loop — execution survives handoff

The execution spine is now repository-owned:

`harness/contracts/execution-handoff-loop.v1.json`

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

The loop intentionally prevents a new agent/runtime from turning accepted work back into planning.

Key rules:

- completed facts become inputs to remaining work;
- remaining work is repartitioned from current truth rather than copied blindly;
- dependency-ready independent lanes launch without operator prompt-shuttling when a safe adapter exists;
- one blocked lane does not stop independent lanes;
- review failure routes to a named repair owner and retry;
- a passing gate advances automatically under existing authority;
- `PLAN_READY`, `HANDOFF_WRITTEN`, `PR_OPEN`, and `MERGEABLE` are explicitly non-terminal.

## 21. Typed handoff protocol

Canonical protocol:

- `docs/handoff/FILESTEWARD-EXECUTION-HANDOFF-PROTOCOL-2026-10-07.md`
- `harness/contracts/execution-handoff-packet.schema.v1.json`
- current successor packet: `docs/handoff/FILESTEWARD-DEPENDENCY-AWARE-CURRENT-HANDOFF-2026-10-07.json`

The packet carries completed facts, remaining work, ownership, dependencies, external prerequisites, proof receipts, proof ceiling, review state, private-evidence pointers, judgment/autonomy gaps, and one executable next action.

Captured SHA fields use `*_at_capture`. This is deliberate: persisting the packet itself moves the tracked branch head. The receiver therefore treats captured heads as continuity evidence and RG0 refreshes current provider/local truth before mutation.

If the same agent can execute the packet's next transition, it should consume that transition itself rather than stopping because a handoff artifact now exists.

## 22. Next review gates

Canonical gate map:

`harness/evals/execution-handoff-review-gates.v1.json`

The next critical gates are:

| Gate | Transition protected | Current significance |
| --- | --- | --- |
| RG0_CURRENT_TRUTH | every pickup -> partition | refresh remote/local state before using captured packet heads |
| RG1_OWNERSHIP_COLLISION | partition -> dispatch | J1/J2/J3 may parallelize only with disjoint mutation owners |
| RG3_FOCUSED_PROOF | execute -> review | J0 Package Cache repair still needs local focused proof |
| RG5_PROVIDER_REVIEW | review -> merge candidate | refresh exact PR #33 head and material review after changes |
| RG6_LOCAL_FULL_PROOF | merge candidate -> merge | local repository suite is still required; provider green is insufficient |
| RG7_PR29_VISUAL_LINEAGE | J4 -> J6 visual mutation | refresh/reconcile PR #29 and incumbent Memory Atlas before touching scenery |
| RG8_LIVE_UX_ACCEPTANCE | J6 implementation -> J6 PROVEN | desktop/narrow/reduced-motion/forced-colors/input proof |
| RG9_LIVE_MUTATION_AUTHORITY | preflight -> workstation mutation | exact action, current evidence, exact scope, current authorization |
| RG10_POST_ACTION_VERIFY | mutation -> terminal | receipt + measured impact + health verification |

Gate failure invalidates the attempted transition, **not the scheduler**.

## 23. P82 handoff-protocol falsification

Receipt:

`harness/evals/execution-handoff-p82-validation-2026-10-07.json`

**Remote result: PASS — 27/27 checks.**

The falsification matrix verifies that the protocol rejects:

- stale captured heads treated as present truth;
- unresolved material review hidden by green tests;
- provider green substituted for local full proof;
- J6 launched from stale PR #29 lineage;
- static HTML/string checks promoted to live UX proof;
- mutation outside the exact operator gate;
- terminal success without post-action health verification;
- a blocked lane disabling independent work;
- operator prompt-shuttling when a safe automated adapter exists;
- stopping at plan/handoff/PR-open/mergeable.

This is still a **remote protocol proof**, not actual local execution evidence. The next local receiver must run RG0, execute J0 local proof, and dispatch J1/J2/J3 when safe independent adapters are available.


## 24. Judgment closure — Cursor receives execution, not architecture

Canonical closure:

`harness/contracts/dependency-aware-judgment-closure.v1.json`

For the current known graph, architectural/product judgment is closed.

### Integration order

1. Wave 1 may run concurrently from refreshed PR #33 foundation truth: J0 local proof, J1 Wispr evidence, J2 app attribution, J3 repo attribution.
2. PR #33 remains the foundation/containment contract PR. It must pass RG3/RG5/RG6 and merge before J2/J3 provider integration.
3. J2/J3 may implement locally in isolated worktrees while J0 proves PR #33. After PR #33 merges, rebase both onto refreshed main, rerun invalidated proof, and use separate focused PRs.
4. J4 begins after J2/J3 integration.
5. J5 begins after J4.
6. J6 begins after J4 and uses the fixed PR #29 selective-lineage procedure.
7. J7 begins after J5/J6 integration.

### PR #29 decision

PR #29 is **not** a branch to merge wholesale.

At judgment close it is 62 commits ahead / 6 behind main and mixes desired Memory Atlas / Decision Chamber lineage with unrelated or stale safety/governance/runtime work.

The J6 owner therefore:

- creates `integration/j6-pr29-lineage-20261007` from refreshed main after J4;
- treats PR #29 head `c093f2cb69d69be153fcf983b6ad785636825b7e` as a lineage donor unless refreshed provider truth changes the head;
- selectively ports only the allowlist in the closure contract;
- excludes PR #29 deletion/safety/governance/housekeeping surfaces;
- ports only the Decision-Chamber/review CLI routing from PR #29 rather than replacing current `cli.py`;
- keeps current `pyproject.toml` as baseline and recomputes the product version through the repository version gate;
- adapts the ported UX to current P94/P110 + ownership/judgment contracts rather than weakening those contracts.

No local agent is authorized to choose a different merge/rebase architecture.

### Exact lane ownership

- **J2:** `src/filesteward/ownership/windows_app.py`, `tests/test_ownership_windows_app.py`, private `_windows_*` helpers.
- **J3:** `src/filesteward/ownership/repository.py`, `tests/test_ownership_repository.py`, private `_git_*` helpers.
- **J4:** `ownership/graph.py`, `ownership/reducer.py`, `ownership/__init__.py`, focused graph/reducer tests.
- **J5:** deletion preflight/executor + exact manifest/receipt dependency-revision integration.
- **J6:** visualization lineage, review bridge, approval, Decision Chamber tests, visual contracts/tokens/versioning support.

### Remaining human boundary

The operator still owns only:

- value/preference for an otherwise technically safe application/repository;
- exact repair/destructive authorization when prior intent does not already cover that action.

Cursor does not escalate already-closed technical/product judgment.

## 25. Exact review checklist

Cursor must use:

`docs/handoff/FILESTEWARD-EXECUTION-REVIEW-CHECKLIST-2026-10-07.md`

The checklist operationalizes RG0-RG10 and is the expected return/readback surface. A failed gate routes to repair; it does not reopen architecture or stop independent lanes.
