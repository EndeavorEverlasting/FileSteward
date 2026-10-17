# Downloads hourly review: Windows Task Scheduler

Status: **opt-in read-only scheduler**, not unattended deletion. This feature
must not be conflated with the released v0.16.0 unsigned welcome preview:
that binary does not contain or install this scheduler.

## Operator objective

Run FileSteward locally once every hour without AI tokens. Keep Downloads
as the only source root. Make repeated intake/review inexpensive and show
ambiguous work artifacts without deciding that they are disposable.
Cleanup automation (quarantine, approved moves or deletion) is a separate
future proof gate, not a hidden side effect of the hourly schedule.

Observed initial evidence on 2026-10-16: roughly 1.65 TB free on C:;
Downloads contains repeated CreativeAgentBootstrap ZIP generations, software
installers, CV/cover letters, spreadsheets, project archives and correspondence.
These observations are examples, not deletion authorization. Exact hostname,
Windows identity, installed FileSteward checkout, and local disk/Downloads
inventory have not been independently verified from this repository runtime.

## Local commands: canonical checkout

Open PowerShell in the *actual* canonical FileSteward checkout. The prior
PTop path was %USERPROFILE%\dev\FileSteward; verify the running host and
checkout before assuming that layout applies here.

    cd "$env:USERPROFILE\dev\FileSteward"
    git status --short --branch
    git rev-parse HEAD
    .\scripts\windows\downloads-hourly-review.ps1 -Mode Preview
    .\scripts\windows\downloads-hourly-review.ps1 -Mode RunOnce
    .\scripts\windows\downloads-hourly-review.ps1 -Mode Register -Authorize
    .\scripts\windows\downloads-hourly-review.ps1 -Mode Status

An explicit -Python "C:\absolute\python.exe" is supported when python is
not discoverable as an installed application. Python must run FileSteward
from the checkout; the script pins PYTHONPATH to its src directory.

Operator controls:

    .\scripts\windows\downloads-hourly-review.ps1 -Mode Disable -Authorize
    .\scripts\windows\downloads-hourly-review.ps1 -Mode Unregister -Authorize

Register never replaces any existing task name, including an existing
FileSteward task. Unregister affects only an exactly owned task; neither
operation touches any other task. A new install requires the owner to
unregister the existing one intentionally first.

### Hourly behavior

- Current-user, limited-privilege interactive task, with no saved password;
  can run when that user is signed in. Sleeping/offline hours are not
  independent proof of execution; Task Scheduler may run it later if able.
- First run scheduled roughly five minutes after registration, then
  every 60 minutes. 10-year trigger repetition duration bounds the
  Windows Task Scheduler XML. No external service or model call.
- Overlap is refused (Task Scheduler IgnoreNew and per-user named mutex).
- Execute only the existing read-only FileSteward commands:
  filesteward.cli scan and filesteward.cli validate.
- Never call FileSteward approval, apply, quarantine, delete-execute,
  or a generic delete/move primitive.
- Reject a redirected, junctioned or symlinked Downloads root instead of
  traversing it. Refuse paths outside the current user's canonical Downloads.
- Each run produces a unique ID and locally ignored evidence under
  var/runs/downloads-hourly-*/. Preserve provenance and failures; do not
  upload private filename/metadata/receipt artifacts to GitHub.
- An unreadable root, missing interpreter, scanner failure or artifact
  validation failure is a failed run, not a successful cleanup claim.

This schedule does **not** delete obsolete bootstrap archives, installers,
project correspondence, PDFs, or anything else. The fact that an installer
is superseded or a filename looks duplicated is insufficient evidence.

### Acceptance / proof matrix

| Gate | Evidence required | Current ceiling |
| --- | --- | --- |
| Registration design | Owner-tagged scheduled task, opt-in, hourly trigger, current-user principal | Implemented in script |
| Source policy | Canonical checkout + pinned Downloads root + reparse refusal | Implemented in script |
| Synthetic regression | Static assertions; PowerShell parser when pwsh available | Not proof of Windows task behavior |
| Windows registration | Preview, exact task XML, owner, next run and identity | Operator-host runtime required |
| Live hourly observation | First and subsequent run receipts, last task result = 0, valid review artifacts | Operator-host runtime required |
| Actual cleanup | Approved exact item set, bounded preflight, authorization, safe apply, independent receipt and recovery proof | **NOT IMPLEMENTED by this schedule** |

## P97 prior art and disposition

- Existing FileSteward workstation performance scheduler:
  REUSE its opt-in, owner-scoped scheduler semantics; do not make a
  second product-owned deletion system.
- tfeldmann/organize: ADAPT explicit review/dry-run separation and
  composable file rules; REJECT automatic age/extension-based disposal of
  meaningful personal/project data.
- purePutthipong/organize-downloads: ADAPT native Windows scheduling
  with preview before installation; REJECT automatic "recycle junk"
  decisions from a heuristic without current FileSteward ownership evidence.
- sahib/rmlint: ADAPT findings vs action separation and stale-candidate
  revalidation. REJECT treating an exact hash or filename duplication
  as automatic personal-file deletion authority.

Reference repos:
https://github.com/tfeldmann/organize
https://github.com/purePutthipong/organize-downloads
https://github.com/sahib/rmlint

## P04 ownership and next execution slice

Canonical owner: FileSteward. TokenCorridor owns prompt/sprint orchestration,
not the workstation job or its approval logic. AgentSwitchboard is retired.

1. **Shipped review scheduler**: script in scripts/windows, synthetic
   contract tests in tests, this runbook. No additional LLM scheduler.
2. **Local execution gate** (physical Windows host): fetch the integrated
   branch, run preview + one-shot review, inspect current-user task
   ownership, opt in to registration, and observe at least two hourly runs.
   Do not claim these tasks were performed by GitHub/provider operations.
3. **Actual cleanup gate**: FileSteward must first support a bounded
   recurring cleanup contract with explicit allowed actions, protected
   personal/project/installed-app dependencies, freshness/revalidation,
   collision/recovery handling, per-run approval identity and audit.
   Never let the scheduler self-approve new manifests, broad delete sets
   or age-only candidates. Preserve an operator-facing Decision Chamber
   for ambiguous data.

P82 experimental measure: compare one manual read-only Downloads scan with
the scheduled one-shot for identical root, inspect scan/validate exit status,
manifest identity, missing/unreadable evidence, overlap refusal, and task
registration inspect output; retain known-good scheduler behavior if a
new mechanism fails any safety gate. Do not advertise real cleanup or a
healthy hourly cadence until live runs prove it.

## Safety invariants

Keep LOCAL-AGENT-PROTECTIONS, OPERATOR-DELETE-PATH, storage dependency
judgment and ownership graph as governing contracts. Installed app serviceability
and incomplete/unique repository/work artifacts take precedence over reclaim.
No age, size, path, filename, content guess or model score grants deletion
authority. Refuse all mutation on unknown ownership. A FileSteward scheduler
registration is not permission to delete arbitrary future downloads.
