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

```powershell
# 1. first real read-only workstation audit (requires explicit authorization)
filesteward scan C:\ --run-dir var\runs\phase5-cdrive-readonly-001

# 2. mechanical validation of the produced artifacts
filesteward validate var\runs\phase5-cdrive-readonly-001
```

Optional operator-supplied inputs (never guessed by the tool):

```powershell
# explicit cache contracts, protected roots, managed-path marks:
filesteward scan C:\ --run-dir var\runs\phase5-cdrive-readonly-001 `
    --contract <path-prefix> --protect <path> --managed <path> `
    --target-free-bytes <n>
```

## What the command does and does not do

Does:

- stream a read-only inventory of `C:\` with no-follow semantics;
- never open file content (cloud placeholders cannot hydrate);
- refuse scan roots beneath `Desktop`/`Documents`/`OneDrive`/`Backups`
  (component-wise, case-insensitive);
- write UNAPPROVED evidence artifacts only into
  `var\runs\phase5-cdrive-readonly-001`;
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
filesteward scan C:\Users\<profile>\AppData\Local `
    --run-dir var\runs\phase5-appdata-readonly-001
```

Any such root is still a real-path observation and still requires the
same explicit authorization. The tool's guards are unchanged; only the
operator's authorization decides whether the crossing happens.
