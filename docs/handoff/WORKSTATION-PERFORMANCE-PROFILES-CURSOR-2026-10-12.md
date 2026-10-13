# Cursor successor — FileSteward workstation performance profiles

Updated 2026-10-12. Canonical remote: EndeavorEverlasting/FileSteward.
PR: https://github.com/EndeavorEverlasting/FileSteward/pull/41
Branch: feature/workstation-performance-profiles-20261012
Baseline main: 197c22ef976cb8caa668c4740f7911afc0fe3407

## Parent outcome

Maintain a durable, per-workstation performance baseline and history that
can inform FileSteward's safety-preserving storage policy without conferring
action/deletion authority. This is NOT an instruction to reclaim/delete or
invent new approvals.

## The mistaken local folder

Cursor found C:\Users\CheeksMcClappeth\Desktop\Dev\FileSteward empty on PTop.
That is a noncanonical folder, not an empty canonical project. Do not move,
overwrite, clean or delete it automatically. Checkout and runtime root are
specified in docs/agent/CANONICAL-PATHS.md:
  %USERPROFILE%\dev\FileSteward
Runtime is ignored var/profiles. Verify exact host identity, checkout status,
and Entire status on PTop; do not infer DTop or Admin Box state.

## What was changed (remote, not locally validated)

- Python profiles package with independent module CLI:
  python -m filesteward.profiles capture --host-key PTop --volume 'C:\'
  python -m filesteward.profiles show --host-key PTop
  python -m filesteward.profiles compare --host-key PTop
- Package opt-in profiles extra for psutil in pyproject.toml
- tests/test_workstation_profiles.py, including host mismatch and append-only
- program guide and typed sprint plan

No scan/delete/approval/visualization code was modified. No real inventory,
private snapshot, hostname, hardware serial, or application file was committed.
Host name digest is a local alias-collision guard, not hardware attestation.

## Required execution path: recovery -> validation -> repair -> integration

1. On the *verified PTop* environment, check existence and git state at the
   canonical checkout. Never bootstrap into Desktop or OneDrive. Preserve
   dirty/unpushed existing work. If canonical checkout is missing, recover
   safely from provider and canonical path contract before writing anything.
2. Inspect PR #41 exact head vs main; inspect review threads and changed files.
   Work from an isolated worktree/branch; do not reset dirty default checkout.
3. Run Entire: entire status --json (if present). If unavailable, report it
   rather than silently replacing Entire with GitHub Actions.
4. Refresh branch and prove:
     python -m pytest -q tests/test_workstation_profiles.py
     python -m pytest -q
   If failures occur, diagnose and repair; do not reinterpret test absence as
   pass. Audit symlink/junction handling, host identity tampering, atomic
   persistence, optional psutil, privacy and no mutation.
5. Reconcile review findings, update exact head, merge only when accepted
   repository-owned gates pass, then verify main containment. Update canonical
   checkout without discarding unrelated changes.
6. After local environment is verified, collect a bounded read-only PTop C:
   observation with the optional profiles dependency installed if appropriate;
   capture twice under comparable conditions; inspect explicit UNKNOWN
   metrics. Distinguish measured C: filesystem capacity from device throughput
   or user-experience slowdown. Never manufacture those values.
7. Feed missing Windows collectors (disk-media mapping, CPU/RAM/load, SMART,
   thermal, device latency) and dashboard/history ownership to the F2/F3 lanes
   from the tracked P04 .plan.json; dispatch independent lanes only through
   a confirmed adapter, not manual operator chat relay.

## Acceptance

- Host aliases cannot cross bind; no private data enters Git or external tools
- Snapshots append-only and latest projection coherent; unreadable/stale state
  fails closed
- 10% critical and 20% healthy free-space thresholds remain visibility only
- Missing metrics are explicitly null/unknown
- Zero app installation/repair paths touched; zero new delete authority
- Focused and full tests pass; no material unresolved review findings
- PR merged to main only after evidence; no claim of host deployment without
  PTop proof receipt

## Status ceiling

REMOTE_BRANCH_AND_PR_CREATED, tests NOT EXECUTED; Windows host capture NOT
EXECUTED; no new scheduler; no dashboard integration. First gate: exact
canonical checkout and executable tests on PTop. Use CHANGED | PROVED | NEXT,
and distinguish all local/integration/deployment/live levels.
