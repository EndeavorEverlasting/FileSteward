# Next sprint: Phase 5 real workstation read-only audit (proposal)

Status of this document: **proposed only**. Nothing in this file has
been executed.

```text
LIVE AUDIT STATE: NOT RUN
OPERATOR APPROVAL STATE: NOT GRANTED
APPLY STATE: NOT RUN
RECLAIM STATE: 0 BYTES VERIFIED
```

## Why authorization is required

Phase 1-4 proof is synthetic: every scan in sprint P04 ran against
fixture trees beneath `%TEMP%` or pytest temp directories. Passing
synthetic tests does not authorize real workstation observation. The
crossing from `synthetic implementation proof` to `real workstation
read-only observation` requires an explicit operator instruction; no
phrase such as "same run", "next logical step", or "read-only anyway"
substitutes for it (`plans/active/C-DRIVE-CLEANUP-P04.md` §19).

## Preconditions (must all be green before the operator authorizes)

- Phase 1-4 acceptance checklist green (P04 §18), including the S1-S14
  matrix, fixture no-mutation proof, CLI smoke, repository hygiene,
  and the adversarial critique outcome.
- Exact read-only command shown below, reviewed by the operator.
- No unresolved proof inflation (evidence states reported at the level
  they actually prove).
- The run directory below is beneath the ignored `var/` tree, so real
  paths, hashes, and queues remain uncommitted local runtime data.

## Exact proposed Phase 5 command (read-only)

Resolve the canonical checkout first. Prefer absolute `--run-dir` paths
derived from that checkout so CWD cannot relocate runtime output.
Relative `--run-dir` values are resolved against the repository root
(not the process CWD).

```powershell
# 1. enter the canonical checkout (runtime-derived; never hard-code a username)
Set-Location (Join-Path $env:USERPROFILE 'dev\FileSteward')

# 2. first real read-only workstation audit (requires explicit authorization)
$runDir = Join-Path (Get-Location) 'var\runs\phase5-cdrive-readonly-001'
filesteward scan C:\ --run-dir $runDir

# 3. mechanical validation of the produced artifacts
filesteward validate $runDir
```

When scanning an ancestor volume such as `C:\`, the canonical runtime
subtree under `<checkout>\var\` is admitted only through the runtime-output
rule (realpath proof under `var\runs\`, no symlink/reparse escape) and is
excluded from inventory before traversal begins. Arbitrary siblings inside
the scan namespace remain rejected.

Optional operator-supplied inputs (never guessed by the tool):

```powershell
filesteward scan C:\ --run-dir $runDir `
    --contract <path-prefix> --protect <path> --managed <path> `
    --target-free-bytes <n>
```

## What the command does and does not do

Does:

- stream a read-only inventory of `C:\` with no-follow semantics;
- never open file content (cloud placeholders cannot hydrate);
- refuse scan roots beneath `Desktop`/`Documents`/`OneDrive`/`Backups`
  (component-wise, case-insensitive);
- write UNAPPROVED evidence artifacts only into the proven run directory;
- self-validate the artifacts and exit non-zero on any inconsistency.

Does not:

- approve, quarantine, move, or delete anything (`apply` refuses with
  exit 3);
- commit or transmit anything (runtime tree stays git-ignored);
- treat `RECLAIM_PROVEN` as permission.

## Expected scale caveat

A full `C:\` walk on a real workstation is I/O-heavy and will produce
a large real inventory (paths, sizes, hashes of nothing — hashes are
not computed by the scanner; item ids are relative-path digests).
If the operator prefers a bounded first observation, substitute a
smaller real root in the same command shape, for example:

```powershell
Set-Location (Join-Path $env:USERPROFILE 'dev\FileSteward')
$runDir = Join-Path (Get-Location) 'var\runs\phase5-appdata-readonly-001'
filesteward scan (Join-Path $env:USERPROFILE 'AppData\Local') --run-dir $runDir
```

Any such root is still a real-path observation and still requires the
same explicit authorization. The tool's guards are unchanged; only the
operator's authorization decides whether the crossing happens.
