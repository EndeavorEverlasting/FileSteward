# Delete-to-Done Live Reclaim Sprint — 2026-10-05

**Sprint ID:** `FILESTEWARD-DELETE-TO-DONE-20261005`  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Canonical local checkout:** `%USERPROFILE%\dev\FileSteward`  
**Canonical worktree root:** `%USERPROFILE%\dev\worktrees\FileSteward\<lane>`  
**Remote floor at sprint creation:** `main@210dbb627e2a300a55089eedf932b4e745093b7b`  
**Historical implementation:** PR #20 merged permanent-delete lifecycle D1-D6.  
**Operator disposition:** live permanent deletion of the bounded regenerable Temp tranche is authorized; do not ask again merely because an internal workflow seam is crossed.  
**Primary outcome:** free real bytes on C: now.

## 1. Resolved execution program

This sprint hybridizes the requested TokenCorridor prompts as orthogonal contributors to one execution graph. Their authorities do not add together.

```text
operator outcome + explicit delete authorization
  + P01 harness durability
  + P04 bounded factoring / critical path
  + P97 defect-specific prior-art evidence
  + P83 verify -> repair -> advance
  + P82 prototype -> measure -> refine
  + P08 observed live runtime proof
  -> one delete-to-done execution program
```

One coordinator retains judgment. Cursor/local agents perform bounded deterministic legwork and implementation. Cursor must not rewrite or "refine" this mission into a readiness-only sprint.

## 2. Acceptance gate — deletion, not readiness

The sprint is **not complete** at any of these states:

- implementation repaired;
- focused tests green;
- full tests green;
- PR opened;
- PR merged;
- local main refreshed;
- manifest regenerated;
- preflight PASS;
- approval artifact written;
- executor ready.

Those are intermediate checkpoints.

### PASS requires all of:

- repository defects blocking safe bounded deletion are repaired or disproved on current truth;
- the exact repair is integrated and the canonical local checkout observes it;
- a real bounded Temp delete set exists;
- operator authorization is materialized into the local exact approval artifact;
- `delete-execute` actually runs;
- `succeeded_count > 0`;
- `delete-execution-receipt.json` exists under ignored runtime storage;
- C: free bytes are observed before and after;
- reclaim state and observed delta are reported;
- residual failed/skipped items are classified without converting PARTIAL into full success.

If `succeeded_count == 0`, the requested outcome is not complete.

## 3. Runtime scope

Preferred inherited run:

```text
run_id: reclaim-regen-caches-001
root: %LOCALAPPDATA%\Temp
inherited candidate count: 8,762 RECLAIM_PROVEN items
inherited projected reclaim: ~2.45 GB
```

These are inherited claims, not current truth. Re-read the local ignored artifacts and current filesystem.

If the run is stale:

1. do not stop;
2. regenerate a fresh run from the same bounded Temp root and the same explicit regenerable-cache contract;
3. emit a fresh exact delete manifest;
4. continue the same iteration.

Do not widen into HUMAN_REVIEW, UNKNOWN, PROTECTED, cloud/provider-ambiguous, repository/worktree, or semantically personal data to increase volume.

## 4. Current provider evidence that must be reconciled

PR #20 is merged at `210dbb627e2a300a55089eedf932b4e745093b7b`, but post-merge review identified material deletion defects. Treat them as inline repair tasks, not as a new stop boundary:

1. live-home refusal bypass through a `pytest-` path component;
2. TOCTOU / target replacement gap between preflight and actual unlink/rmdir;
3. current protection/managed state not fully rebuilt/propagated into execution;
4. ancestor symlink/junction/reparse escape despite lexical containment;
5. weak content/file identity against equal-size rewrite + restored mtime;
6. missing `cleanup-plan.csv` digest verification failing open;
7. PARTIAL execution returning a success exit status;
8. allocated-size fixture mismatch weakening platform proof;
9. any duplicate unresolved review threads representing the same families;
10. any new material finding exposed by the repairs/tests.

Reproduce or disprove each against refreshed current truth. Fix every still-material defect in the smallest canonical owner. Do not create an architecture redesign.

### OBSERVED FACTS — PR #20 / #24 defect family classification (repair lane)

- live-home `pytest-` path bypass — **VERIFIED_DEFECT** (loose component match admitted `Path.home()/pytest-victim`)
- TOCTOU identity gap before unlink — **VERIFIED_DEFECT** (open→fstat/hash→unlink; POSIX hold-fd; Windows close-then-unlink)
- protection/managed not rebuilt into execute/CLI preflight — **VERIFIED_DEFECT** (run artifacts + fresh git rediscovery union)
- ancestor symlink/junction/reparse escape — **VERIFIED_DEFECT** (component walk + `realpath(path)` within `realpath(scan_root)`)
- weak size+mtime identity (equal-size rewrite) — **VERIFIED_DEFECT** (preflight seals `content_sha256`; invalid tokens FAIL; approval/fresh/unlink enforce)
- missing `cleanup-plan.csv` digest fail-open — **VERIFIED_DEFECT** (empty digest + existing plan → `DIGEST_DRIFT`; item digests require top-level)
- PARTIAL execute exit status EXIT_OK — **VERIFIED_DEFECT**
- allocated-size fixture POSIX `st_blocks*512` mismatch — **VERIFIED_DEFECT**
- temp lexical OR admitting junction into home — **VERIFIED_DEFECT** (temp membership realpath-only; home checks `root_real`)
- `load_run_protection_context` silent empty on malformed artifacts — **VERIFIED_DEFECT** (raise `ValueError`; no partial CSV)
- duplicate unresolved review threads for same families — **DUPLICATE** (collapsed into the owners above; Codex/CodeAnt TOCTOU = one fix)
- new material finding from repairs/tests — **STALE** / none new beyond the verified set above at repair time

## 5. Execution frame

### Repo / path

```powershell
$repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
Set-Location -LiteralPath $repo
```

### Repair branch

Use an isolated branch/worktree from refreshed current `origin/main`, suggested:

```text
fix/delete-to-done-live-reclaim-20261005
```

### Owned scope

- `src/filesteward/deletion/**`
- deletion CLI semantics in `src/filesteward/cli.py`
- focused deletion tests
- exact harness/docs needed to preserve the repaired delete path
- tracked review resolutions / PR integration
- ignored local runtime under `var/runs/**`
- live C: free-space measurement for proof

### Forbidden scope

- Storage Atlas / Decision Map polish;
- unrelated UI work;
- scheduler/recurrence work;
- broad cleanup refactors;
- semantic promotion of ambiguous data;
- generic wildcard or recursive OS deletion outside the manifest;
- committing live paths/manifests/approval/receipt/private evidence;
- replacing repository-owned delete-execute with an ad hoc shell delete merely for speed.

## 6. Cursor role

Cursor is the local execution worker, not the planning/judgment owner.

Cursor SHALL:

- recover current repo/local/runtime evidence;
- implement the smallest evidence-required repairs;
- add or update deterministic regressions;
- run validators/tests;
- commit/push/open or update the repair PR;
- reconcile review/provider truth;
- merge the exact validated authorized repair when repository rules permit;
- refresh canonical local main;
- regenerate stale Temp runtime artifacts inside the same scope;
- execute preflight/approval/delete;
- collect receipt/free-space proof;
- update the plan/handoff with observed facts.

Cursor SHALL NOT:

- replace this sprint with a new plan;
- defer live deletion to "the next sprint";
- ask for a second deletion authorization for the same bounded Temp outcome;
- stop at "ready to execute";
- decide ambiguous personal-file semantics.

## 7. Required execution loop

### A. Orient once

Capture:

- `git rev-parse --show-toplevel`
- `git remote get-url origin`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short --branch`
- `entire status --json` when available
- current open/recent FileSteward PRs and PR #20 unresolved review evidence
- current local state of `var/runs/reclaim-regen-caches-001`
- baseline C: free bytes

Do not turn orientation into a report-only stop.

### B. P83 verification pass

For every PR #20 defect family, classify against current main:

```text
VERIFIED_DEFECT | ALREADY_FIXED | STALE_REVIEW | DUPLICATE_FAMILY
```

Any VERIFIED_DEFECT becomes immediate owned repair work.

### C. P82 repair-measure-refine loop

For each material defect family:

```text
hypothesis
-> smallest repair
-> focused negative regression + positive control
-> focused tests
-> critique new evidence
-> refine if needed
```

Continue until the delete path reaches a practical fixed point. Do not iterate cosmetics.

### D. Validation

At minimum:

- focused deletion / CLI suites;
- newly added regression tests for every reproduced defect;
- full pytest;
- `git diff --check`;
- `git status --short`;
- exact PR review-thread reconciliation;
- provider readback of the exact candidate.

A failed gate is diagnosed and repaired; it is not renamed as a blocker.

### E. Integrate

When exact repair head is current and green:

- commit coherent repair;
- push;
- open/update PR;
- resolve/disposition material review threads from evidence;
- merge when repository rules permit;
- verify `origin/main` contains the exact repair;
- refresh canonical local checkout to that main.

**Do not stop here.**

### F. P08 live deletion proof

Re-read the current Temp run.

If reusable:

```powershell
python -m filesteward delete-preflight reclaim-regen-caches-001 --scan-root "$env:LOCALAPPDATA\Temp"
python -m filesteward delete-approve reclaim-regen-caches-001 --irreversible-confirmation "DELETE_PERMANENTLY reclaim-regen-caches-001"
python -m filesteward delete-execute reclaim-regen-caches-001 --scan-root "$env:LOCALAPPDATA\Temp" --i-understand-irreversible
```

If not reusable, regenerate the same-scope Temp run and substitute its fresh run ID. Natural-language operator authority for this bounded Temp permanent-delete outcome is already present; the local approval artifact must bind that authority to the new exact set.

Collect:

- pre/post `Get-PSDrive C` free bytes;
- preflight overall and item counts;
- approval artifact identity;
- delete receipt overall;
- attempted/succeeded/failed/skipped;
- successful expected allocated bytes;
- observed C: free delta;
- reclaim verification state;
- residual paths/items by reason class.

If PARTIAL, preserve successful deletion proof, return nonzero for automation, repair/retry independent residuals where safe, and continue toward the bounded fixed point.

## 8. P97 rule

Prior art is subordinate to execution.

Use P97 only when a concrete defect repair has more than one materially different implementation and repository evidence is insufficient. Inspect credible implementations for the specific mechanism (TOCTOU-safe identity binding, ancestor reparse defense, interruption-safe per-item receipts, filesystem allocation measurement, etc.), choose ADOPT/ADAPT/REJECT, then implement immediately.

Do not pause this sprint for a broad research essay.

## 9. Failure semantics

A local failure is a work item unless it proves a real external boundary.

Valid terminal BLOCKED examples:

- no eligible Temp items remain after a fresh same-scope rescan, so there is literally nothing in the authorized scope to delete;
- required OS privilege/endpoint capability is absent and cannot be acquired or routed around by the local agent;
- every exact eligible target is locked/denied in a way that cannot be safely retried or independently progressed;
- repository/provider access required to integrate a safety repair is unavailable.

Invalid blockers:

- "review found issues";
- "needs code changes";
- "tests need updating";
- "PR needs opening";
- "merge required";
- "preflight must be rerun";
- "approval artifact must be regenerated";
- "run is stale";
- "needs operator confirmation again";
- "ready to delete."

## 10. Final response contract

Cursor's final response must use:

```text
CHANGED:
- repairs and commits
- integrated PR / main SHA
- local canonical checkout state

PROVED:
- focused tests
- full tests
- review reconciliation
- live run id
- preflight state
- approval artifact state
- delete execution receipt path
- attempted / succeeded / failed / skipped
- C: free bytes before
- C: free bytes after
- observed delta
- reclaim verification state

SKIPPED:
- exact skipped checks and why

RISKS / RESIDUAL:
- only remaining failed/locked/stale items and exact reason

GIT:
- branch / commit / PR / merge / main / status

TERMINAL RESULT:
- PASS only if succeeded > 0 and runtime proof exists
- otherwise BLOCKED with exact unrepairable boundary

NEXT:
- next useful reclaim tranche only after this deletion proof is complete
```

No final handoff whose terminal line is "run delete-execute next."
