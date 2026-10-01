# OpenCode Handoff — Execute FileSteward Phase 1-4 Only

CONTINUE THE FILESTEWARD C:-DRIVE CLEANUP PROGRAM. EXECUTE B0, THEN PHASE 1-4 ONLY. THIS IS AN EXECUTION REQUEST, NOT A REQUEST TO RETURN ANOTHER PLAN.

**THIS FILE IS A POINTER TO THE TRACKED CONTRACTS, NOT A LICENSE TO REINTERPRET THEM.**

## Authority and precedence

The tracked repository files are authoritative. Chat text is convenience only.

### Safety authority — may be strengthened, never relaxed

1. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
2. `AGENTS.md`
3. `README.md`

These own safety, ambiguity handling, privacy, and authorization semantics.

### Path authority — exclusive

`docs/agent/CANONICAL-PATHS.md` exclusively owns repository, worktree, runtime, and entry-point path resolution. Within a path dispute, `CANONICAL-PATHS.md` wins. Path authority may never weaken the safety authority above.

### Execution detail — owned scope, forbidden scope, lanes, and gates

1. `plans/active/C-DRIVE-CLEANUP-P04.plan.json`
2. `plans/active/C-DRIVE-CLEANUP-P04.md`
3. this handoff

Rules:

- A conflict about safety, ambiguity handling, authorization, privacy, or mutation => **STOP** and report the exact conflict.
- A conflict about ordinary task detail => follow the plan JSON, then note the deviation in the final report.
- Never reconstruct a missing rule from memory.
- A lower-precedence file may not weaken a higher-precedence safety rule.

## Repository / immutable floor

Repository:

```text
EndeavorEverlasting/FileSteward
```

Execution branch:

```text
plan/c-drive-cleanup-p04-20260930
```

Immutable predecessor / planning floor:

```text
de08acde37aa6f865c233aa9459a3a378f0dc34e
```

Foundation base:

```text
agent/repository-foundation
7ca41c45e3d92aae7963d2fc6713cb88b98fa2c2
```

This tracked handoff is intentionally committed *after* the immutable predecessor. Therefore do not require the branch head to equal the predecessor.

Instead, bootstrap must prove all of the following:

1. fetched remote branch head exists;
2. `de08acde...` is an ancestor of that remote head;
3. the only tracked delta from `de08acde...` to the fetched remote head before implementation begins is exactly these approved governance files:
   `AGENTS.md`,
   `docs/agent/CANONICAL-PATHS.md`,
   `plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md`
   (this is the single-use launch gate — see **B0.C**);
4. after checkout/pull, local HEAD exactly equals the fetched remote head.

Any other pre-existing delta => STOP.

## Canonical session bootstrap

PowerShell-oriented commands follow because the execution host is Windows.

Path resolution is owned exclusively by `docs/agent/CANONICAL-PATHS.md` (section 3). All bootstrap inspection is non-destructive. Any mismatch => STOP. Do not stash, reset, clean, force, amend, rebase, reclone, rewrite the remote, or "repair" the discrepancy.

### Canonical directory

Open every session from the canonical checkout:

```powershell
$repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
Set-Location -LiteralPath $repo
git rev-parse --show-toplevel   # B0.B identity gate — before any fetch
git remote get-url origin       # B0.B identity gate — before any fetch
git fetch --all --prune --tags
git status --short --branch
git rev-parse HEAD
git remote get-url origin
```

Expected checkout shape:

| Shape | State |
|---|---|
| `$env:USERPROFILE\dev\FileSteward` | canonical — the execution owner |
| `...\dev\_worktrees\...` | not this continuation |
| `...\dev\_upstreams\...` | not this continuation |
| `...\Desktop\Dev\...` | forbidden root |
| `...\OneDrive\...` | forbidden root |

`$env:USERPROFILE\dev\worktrees\FileSteward` is the reserved worktree root. It exists in the contract only. Do not `Set-Location` there for this continuation; the normal canonical checkout already exists and is the execution owner.

### B0.B — existing-checkout identity, before fetch/checkout/pull

Prove identity before any `fetch`, `checkout`, or `pull` against an existing checkout. The two identity lines in the canonical block above are the raw commands; this is their machine-checkable form, executed before the `fetch` line:

```powershell
Set-Location -LiteralPath $repo

$top = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $top) { throw 'git rev-parse --show-toplevel failed. STOP.' }

$canonical = (Resolve-Path -LiteralPath $repo).Path
if (($top -replace '/', '\') -ne ($canonical -replace '/', '\')) {
    throw "Resolved worktree root $top does not equal canonical checkout $canonical. STOP."
}

$origin = (git remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or -not $origin) { throw 'git remote get-url origin failed. STOP.' }

$normalizedOrigin = $origin -replace '\.git$', '' -replace '^https://github\.com/', '' -replace '^git@github\.com:', ''
if ($normalizedOrigin -ne 'EndeavorEverlasting/FileSteward') {
    throw "Origin $origin does not identify EndeavorEverlasting/FileSteward. STOP."
}
```

Required proofs, all four:

1. `git rev-parse --show-toplevel` succeeds;
2. the resolved root equals the canonical checkout exactly (normalized);
3. `git remote get-url origin` succeeds;
4. the normalized origin identifies `EndeavorEverlasting/FileSteward`.

A directory named `FileSteward` is not sufficient identity proof.

Mismatch => STOP. Do not rewrite the remote, reclone over the directory, reset, move, or repair the checkout.

### Pin, execution-start SHA, and single-use launch gate

Only after the identity gate passes, using the `fetch` and `status` already performed in the canonical block above:

```powershell
$branch = 'plan/c-drive-cleanup-p04-20260930'
$floor = 'de08acde37aa6f865c233aa9459a3a378f0dc34e'
$approvedDelta = @(
    'AGENTS.md',
    'docs/agent/CANONICAL-PATHS.md',
    'plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md'
)

$remoteHead = (git rev-parse "refs/remotes/origin/$branch").Trim()
if ($LASTEXITCODE -ne 0 -or -not $remoteHead) { throw 'Remote plan branch head could not be resolved.' }

$expectedPin = '<exact remote HEAD stated in the operator continuation instruction>'
if ($remoteHead -ne $expectedPin) {
    throw "Provider truth moved: remote head $remoteHead does not equal supplied pin $expectedPin. STOP before mutation and report the new truth."
}

$executionStartSha = $remoteHead
```

The operator's continuation instruction carries the exact expected remote plan-branch pin. At the time this handoff was last written that pin was:

```text
19f54d0791e113ab2101df80021bde5899c1d715
```

It is superseded the moment B0 pushes a commit; the post-B0 continuation instruction carries the refreshed pin. Never substitute a remembered pin for the supplied one.

`execution-start SHA` must be recorded and named in every stop or continuation report.

Then the launch gate — this exact-three-file check is SINGLE USE and applies only while no implementation commit exists on the branch (see B0.C):

```powershell
git merge-base --is-ancestor $floor $remoteHead
if ($LASTEXITCODE -ne 0) { throw "Remote head $remoteHead is not descended from immutable floor $floor." }

$preImplementationDelta = @(git diff --name-only "$floor..$remoteHead")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$unexpected = @($preImplementationDelta | Where-Object { $_ -notin $approvedDelta })
$missing = @($approvedDelta | Where-Object { $_ -notin $preImplementationDelta })
if ($preImplementationDelta.Count -ne $approvedDelta.Count -or $unexpected.Count -ne 0 -or $missing.Count -ne 0) {
    $preImplementationDelta | ForEach-Object { Write-Error "Unexpected pre-implementation delta: $_" }
    throw 'Plan branch changed beyond the approved handoff update. STOP.'
}

git checkout $branch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Plan branch did not fast-forward cleanly. STOP.' }

$localHead = (git rev-parse HEAD).Trim()
if ($localHead -ne $remoteHead) {
    throw "Local HEAD $localHead does not equal fetched remote head $remoteHead."
}

git status --short --branch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

After `status --short --branch`:

- any unrelated, untracked, or unknown local change => STOP;
- do not stash it;
- do not reset it;
- do not clean it;
- report it verbatim.

## Environment preflight

Before implementation:

```powershell
Set-Location -LiteralPath $repo
python --version
python -m pytest --version
git --version
```

Expected workstation evidence currently indicates Python 3.12.x and pytest are present, but the commands above are authoritative for this run.

Missing runtime/tool => report **BLOCKED** with the exact command and error. Do not claim test proof that did not run.

## Read before mutation — exact order

Read the full files, not summaries:

1. `AGENTS.md`
2. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
3. `docs/agent/CANONICAL-PATHS.md`
4. `README.md`
5. `plans/active/C-DRIVE-CLEANUP-P04.md`
6. `plans/active/C-DRIVE-CLEANUP-P04.plan.json`
7. `plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md`

Missing, unreadable, contradictory, or materially stale safety contract => STOP.

These are execution contracts, not suggestions.

## Writer rules

- Work only on `plan/c-drive-cleanup-p04-20260930`.
- Never mutate `main`.
- Never modify, close, merge, retarget, or otherwise touch PR #1.
- Never merge anything in this sprint.
- Never open a new PR in this sprint.
- Dependency graph width is 1.
- Execute `B0 -> L0 -> L1 -> L2 -> L3 -> L4` strictly serially, in this session, without pausing to re-plan between lanes.
- No subagents.
- No parallel mutation workers.
- No "many files means many agents."

Hard-forbidden throughout B0 and L0-L4:

- No real `C:\` traversal, including "read-only."
- No real quarantine.
- No real apply.
- No deletion of any kind.
- No PR #1 mutation.
- No `main` mutation.
- No merge.

Commit bounded coherent work per lane:

```powershell
git add <exact-owned-files>
git diff --cached --check
# MUST exit 0 before commit
git commit -m "<lane>: <bounded change>"
```

Never use broad `git add .` when exact owned files can be named.

Never amend, rebase, reset, or force-push the plan branch.

Push only after the lane's owning gates are green:

```powershell
git push origin plan/c-drive-cleanup-p04-20260930
```

### Read-only contract files during implementation

B0 is the one sanctioned edit window for `plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md`, and it may only encode the three corrections in **B0** above. From L0 onward this file joins the read-only list below.

The following are read-only during L0-L4 unless the **Bounded Correction** rule below explicitly applies:

- `AGENTS.md`
- `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
- `docs/agent/CANONICAL-PATHS.md`
- `README.md`
- `plans/active/C-DRIVE-CLEANUP-P04.md`
- `plans/active/C-DRIVE-CLEANUP-P04.plan.json`
- `plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md`

A local agent may not edit a contract merely because implementation is difficult.

## Authority boundary

You are an implementation/execution agent.

You are **not** the operator's judgment substitute.

You MAY:

- build deterministic machinery;
- scan synthetic/temp fixtures;
- run deterministic evidence gates;
- implement protection semantics;
- implement the adversarial downgrade;
- generate synthetic proposed-action artifacts;
- run tests and validators;
- diagnose failed gates;
- repair in-scope implementation code.

You MAY NOT:

- decide an ambiguous personal/project file is disposable;
- reason `HUMAN_REVIEW` into `RECLAIM_PROVEN`;
- infer disposability from age, size, filename, extension, location, or inactivity;
- use "probably generated", "looks duplicate", "old installer", "unlikely important", "AI confidence is high", or similar intuition as authority;
- self-approve a manifest;
- scan real `C:\` during Phase 1-4;
- quarantine, apply, move, or delete a real file;
- weaken a test, invariant, or safety requirement to make implementation pass.

Routing:

```text
Semantic decision required     => HUMAN_REVIEW
Technical evidence incomplete  => UNKNOWN
Protection applies             => PROTECTED
```

Do not re-reason an ambiguous item until you convince yourself it is safe.

There is no "think harder until it becomes RECLAIM_PROVEN."

## B0 — execution door hardening

B0 is a bounded governance gate that runs after bootstrap and before L0. It is not a plan JSON lane; `C-DRIVE-CLEANUP-P04.plan.json` remains canonical for L0-L4 and is not edited for B0. B0 touches exactly one file: this handoff.

### A. Path authority

Encoded in **Authority and precedence** above:

- `LOCAL-AGENT-PROTECTIONS.md` / `AGENTS.md` / `README.md` own safety, ambiguity, privacy, and authorization semantics;
- `docs/agent/CANONICAL-PATHS.md` exclusively owns repository, worktree, runtime, and entry-point path resolution;
- within a path dispute, `CANONICAL-PATHS.md` wins;
- path authority may never weaken the safety authority.

### B. Existing-checkout identity

Encoded in the bootstrap above: before any fetch/checkout/pull, prove toplevel success, canonical equality, origin command success, and normalized origin identity. A directory named `FileSteward` is not sufficient identity proof. Mismatch => STOP with no rewrite, reclone, reset, move, or repair.

### C. Bootstrap lifecycle — single-use launch gate

The immutable floor + approved three-file governance delta is an **INITIAL L0-L4 LAUNCH GATE ONLY**.

- Before the first implementation commit exists, the pre-implementation delta from the floor must be exactly the approved files. Any other delta => STOP.
- After the first implementation commit exists, implementation files are expected to extend the floor-to-HEAD delta. That is normal. The exact-three-file gate no longer applies to them.
- If this agent loses context, restarts, or hands the run to another agent after implementation begins:
  - DO NOT widen the initial `approvedDelta`;
  - DO NOT guess which implementation commits are legitimate;
  - STOP;
  - report local HEAD, remote HEAD, `git status`, last completed lane, and commits since this run's execution-start SHA;
  - require a freshly pinned continuation handoff.

This is intentional fail-closed continuity behavior. A widened allowlist is never an acceptable continuity repair.

If a continuation already finds corrections A-C present in this file, verify them read-only, record B0 as already landed, and proceed to L0. Do not create a second governance commit.

### B0 validation

- `git diff --cached --check` exits 0;
- final newline present on every touched tracked file;
- no literal operator `USERPROFILE` path or username in tracked content (`git grep` exit 1 is the expected no-match pass state);
- `main` untouched;
- PR #1 untouched;
- commit and push only `plan/c-drive-cleanup-p04-20260930`;
- refresh and report the exact remote HEAD after push.

### B0 -> L0

After B0 succeeds, CONTINUE IN THIS SAME EXECUTION SESSION. Do not fall back into planning merely because the branch HEAD changed. Refresh the exact branch HEAD, record it as the new pin for any future continuation, and proceed to L0.

## Canonical lane execution

Owned/forbidden surfaces and validation gates are canonical in `C-DRIVE-CLEANUP-P04.plan.json`. Do not re-derive them.

### L0 — package floor

Implement:

- `pyproject.toml`;
- console entry point;
- domain models/state;
- runtime-path policy;
- package/test skeleton;
- focused tests.

CLI vocabulary is canonical in P04 section 10. Implement that contract. Do not invent a competing command system.

After `pyproject.toml` exists:

```powershell
python -m pip install -e .
```

Record the actual command and exit code.

### L1 — streaming inventory + Windows safety + protection

Implement:

- streaming/iterable inventory;
- Windows traversal boundaries;
- Git/worktree protection;
- protected ancestor decomposition;
- unreadable => explicit `UNKNOWN`;
- reparse/junction no-follow behavior;
- symlink no-follow behavior;
- cloud-placeholder no-hydration seam;
- system/application-managed mutation exclusion.

Synthetic/temp repositories and fixtures only.

### L2 — disposition + evidence gates + adversarial downgrade

Implement:

- `CleanupDisposition`;
- `GateResults`;
- `ProvisionalDisposition`;
- deterministic nomination;
- fail-closed conflict behavior;
- independent `AdversarialChallenge`.

The challenger may:

- sustain a provisional `RECLAIM_PROVEN`;
- downgrade to `HUMAN_REVIEW`.

It may never promote ambiguity.

No age/size/name/location-only reclaim rule.

### L3 — orchestration + CLI + artifacts

Implement:

- `CleanupRun`;
- CLI;
- `cleanup-plan.csv` — **only `RECLAIM_PROVEN` rows**;
- `human-review.csv` — no delete score, no persuasive recommendation;
- `protected-exclusions.csv`;
- `cleanup-summary.md`;
- stable item reconciliation;
- honest reclaim/free-space projection.

Required separation:

```text
logical_size_bytes
allocated_size_bytes | unknown
projected_reclaim_bytes | unknown
reclaim_basis
```

Stop condition:

```text
baseline_free_bytes + cumulative_projected_reclaim_bytes >= target_free_bytes
```

Do not hardcode screenshot values.

Logical length is not automatically reclaimable physical space.

### L4 — full proof + critique

Run:

- complete S1-S14 matrix;
- deterministic fixture-tree before/after snapshot proving no creation, deletion, rename, type change, size/content change, or contractually protected metadata mutation during analysis;
- full pytest;
- CLI smoke through the installed console entry point;
- repository hygiene checks;
- adversarial architecture critique.

If critique finds a real defect:

1. make the smallest bounded repair;
2. rerun the owning focused gate;
3. rerun the affected integration proof;
4. record the defect and repair in the final report.

## Bounded Correction — only license to deviate

A bounded correction is allowed only when:

1. repository evidence proves a plan path/name assumption wrong; or
2. a test exposes a real contract defect.

Then:

1. preserve safety intent;
2. make the smallest possible change;
3. record it in the final report;
4. rerun the owning gates.

Additional hard boundary:

- Contract-file corrections must be additive/non-weakening.
- A correction may clarify a path, interface, typo, or machine-checkable gate.
- A local agent may **not** weaken or reinterpret ambiguity ownership, authorization separation, privacy boundaries, protection semantics, no-live-scan scope, or no-permanent-delete scope.
- If satisfying a test appears to require weakening any safety contract, STOP and ask the operator. Do not edit the contract.

## Mandatory proof — report each command and exit code

### 1. Editable installation

After L0:

```powershell
python -m pip install -e .
```

### 2. Full test suite

```powershell
python -m pytest -q
```

### 3. Focused S1-S14 proof

Run the exact focused test invocations created/owned by the plan.

Report every command and exit code.

### 4. CLI smoke

Invoke the installed `filesteward` console entry point only against a synthetic root beneath `$env:TEMP`.

No real `C:\` scan.

### 5. Fixture no-mutation proof

Use a deterministic directory snapshot manifest before and after analysis.

The manifest must cover at least:

- relative path;
- entry type;
- file size;
- regular-file content hash;
- relevant timestamps where the scanner contract promises non-mutation.

Before/after manifests must be identical.

Do not substitute a vague "hash checked" statement.

### 6. Git hygiene

Before every commit:

```powershell
git diff --cached --check
```

Final candidate range:

```powershell
git diff --check 7ca41c45e3d92aae7963d2fc6713cb88b98fa2c2...HEAD
```

Both must exit 0.

### 7. Private-artifact checks

First, prove no tracked runtime files under `var/`:

```powershell
$trackedVar = @(git ls-files var)
if ($trackedVar.Count -ne 0) {
    $trackedVar
    throw 'Tracked files exist beneath var/.'
}
```

Second, prove the operator's actual profile path was not accidentally committed into tracked text content:

```powershell
git grep -n -I -F -e "$env:USERPROFILE" -- .
$profileGrep = $LASTEXITCODE
if ($profileGrep -eq 0) {
    throw 'Tracked content contains the operator USERPROFILE path.'
}
if ($profileGrep -ne 1) {
    throw "git grep failed with exit code $profileGrep"
}
```

The successful no-match state for `git grep` is exit code **1** and must be reported as the expected no-match result, not as a failed validation.

### 8. Final status

```powershell
git status --short --branch
git log --oneline 7ca41c45e3d92aae7963d2fc6713cb88b98fa2c2...HEAD
```

Report outputs and exit codes.

### Skipped tests

Any skipped platform-specific test must report:

- exact reason;
- exact substitute deterministic adapter/unit proof that ran;
- reduced proof ceiling.

A skip is not a pass for behavior that was not observed.

## Private data boundary

Tracked tests/examples: synthetic or sanitized only.

Real runtime material belongs only beneath ignored:

```text
var/runs/<run_id>/
```

Never commit real:

- absolute user paths;
- filenames from the operator's workstation;
- hashes from the operator's files;
- inventories;
- review queues;
- live proposed manifests;
- approvals;
- quarantine data;
- scan errors containing private paths.

No real `C:\` traversal in this sprint, including "read-only."

## Hard stop

After L4 is green:

**STOP.**

Do not execute Phase 5.

Do not scan `C:\` "because it is read-only."

Passing synthetic tests does not authorize real workstation observation.

You may propose the exact bounded Phase 5 read-only command.

You must not run it.

## Final report

P04 section 20 remains canonical. Include all of:

```text
COMPLETED WORK
CREATED/MODIFIED FILES
VALIDATION / PROOF
  - actual commands
  - actual exit codes
SKIPPED CHECKS AND WHY
UNRESOLVED GAPS / RISKS
ARTIFACT / LOG / REPORT PATHS
BRANCH
EXECUTION-START SHA
LAST COMPLETED LANE
COMMITS
  git log --oneline 7ca41c45e3d92aae7963d2fc6713cb88b98fa2c2...HEAD
PUSH STATE
PR STATE
GIT STATUS

B0 STATE: <NOT RUN | LANDED @ <sha>>
LIVE AUDIT STATE: NOT RUN
OPERATOR APPROVAL STATE: NOT GRANTED
APPLY STATE: NOT RUN
RECLAIM STATE: 0 BYTES VERIFIED

NEXT: exact proposed Phase 5 read-only command
```

Then STOP.

Do not ask the operator to run tests you can run yourself.

Do not return a broad redesign instead of implementing the tracked plan.

Do not "use judgment" to weaken an ambiguity boundary.

**Evidence before confidence. The operator owns judgment.**
