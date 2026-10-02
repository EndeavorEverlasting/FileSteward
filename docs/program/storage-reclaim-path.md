# Storage reclaim path (post Phase 5)

Status of this document: **active program path / proposal for operator gates**.
This file does **not** authorize apply, quarantine, deletion, or verified reclaim.

```text
RECEIPT TRIAGE TOOL: IMPLEMENTED (filesteward plan)
LIVE AUDIT STATE (tracked program): NOT PROMOTED HERE
OPERATOR APPROVAL STATE: NOT GRANTED
APPLY STATE: NOT RUN
RECLAIM STATE: 0 BYTES VERIFIED
```

## Why reclaim was zero after the first C:\ scan

FileSteward nominates `RECLAIM_PROVEN` only when an explicit regenerable
`--contract` covers a path (`nominate()` fail-closed without contract).
A bare `filesteward scan C:\` therefore routes nearly everything to
`HUMAN_REVIEW`. That is intentional false-positive avoidance, not a
completed cleanup.

## Slice 1 — Receipt triage (read-only) — tool

Aggregate an existing run's `human-review.csv` into path-prefix buckets:

```powershell
$runDir = Join-Path (Join-Path $env:USERPROFILE 'dev\FileSteward') 'var\runs\phase5-cdrive-readonly-001'
filesteward plan $runDir --depth 2 --top 30
# Under large roots such as C:\Users, increase depth (3–5) to expose
# contractable prefixes (AppData caches, Temp, package managers).
filesteward plan $runDir --depth 4 --top 40
```

Artifacts written under the run directory (ignored `var/` tree only):

- `human-review-buckets.csv`
- `human-review-buckets.md`

Bucket rows are counts and logical-byte totals by prefix. Optional
`contract_hint_tags` are deterministic path-substring labels for operator
`--contract` selection. They are **not** reclaim authority.

## Slice 2 — Contract-backed rescan (read-only; operator inputs required)

After the operator names regenerable prefixes and a free-space target:

```powershell
$repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
Set-Location -LiteralPath $repo
$runDir = Join-Path $repo 'var\runs\phase5-contract-rescan-001'
filesteward scan C:\ --run-dir $runDir `
  --contract <regenerable-prefix> `
  --target-free-bytes <n>
filesteward validate $runDir
```

Success for this slice: `cleanup-plan.csv` rows may be non-zero, still
`UNAPPROVED`. Zero rows after contracts is a valid fail-closed outcome.

## Slice 3 — Apply (separate explicit gate)

Ordinary cleanup goes to quarantine first. Requires a distinct operator
approval artifact bound to exact manifest digest/run ID. Not authorized
by this document.

## Continuity

Do not replay completed P04 B0–L4. Do not promote ignored `var/runs/`
receipts into tracked LIVE-AUDITED claims without a separate
operator-directed reconciliation of program docs.
