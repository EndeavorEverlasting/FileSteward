# FileSteward cleanup analysis — design (Phase 1-4)

Status: implemented and locally validated on branch
`plan/c-drive-cleanup-p04-20260930`. This document reflects the code as
built for sprint P04 (`plans/active/C-DRIVE-CLEANUP-P04.plan.json`).

## 1. Scope

FileSteward performs **read-only cleanup analysis**. It inventories a
root, classifies every observed item into evidence dispositions, and
writes unapproved evidence artifacts. It never mutates the scanned
tree, never opens file content, never follows links, and has no
implemented apply/delete path — `filesteward apply` is a refusal seam
(exit 3) for this sprint.

## 2. Dependency direction

```text
cli -> run -> inventory / protect / classify / manifest
                 \-> models, policy.paths (leaf contracts)
```

- `models.py` — leaf enums/dataclasses: `CleanupDisposition`,
  `AuthorizationState`, `ScanCompleteness`, `InventoryItem`.
  Disposition (evidence) and authorization (permission) are separate
  type systems and never interchanged (`authorization_allows_mutation`
  raises on non-authorization input).
- `policy/paths.py` — runtime output always beneath the ignored `var/`
  tree; forbidden scan roots (`Desktop`, `Documents`, `OneDrive`,
  `Backups`) refused component-wise, case-insensitively; repository
  root resolution fails closed without the `pyproject.toml` marker.
- `inventory/` — streaming post-order scanner (children before parents)
  with no-follow, no-content-open, fail-closed completeness semantics.
- `protect/` — containment index (SELF / DESCENDANT / ANCESTOR /
  UNRELATED, protection wins) plus fail-closed Git/worktree discovery.
- `classify/` — deterministic gates, nomination rules, directory
  composition, and the independent adversarial challenge.
- `manifest/` — artifact writers with disposition guards and
  `validate_run`, which re-derives every mechanical fact from disk.
- `run.py` — orchestration only: partition, projection, stop-point
  math, self-validation. It never decides a disposition.

## 3. Pipeline

```text
iter_inventory (post-order)
  -> ProtectionIndex.relation
  -> evaluate_gates (protection, observation, contract, managed)
  -> nominate (fail-closed precedence)
  -> AdversarialChallenge.review (sustain or downgrade, never promote)
  -> directory composition (downgrade-only promotion)
  -> partition (plan / human-review / protected-exclusions / keep)
  -> projection (allocated-evidence | estimate-logical | container-row)
  -> writers + summary
  -> validate_run (self-validation; failure aborts the run)
```

Nomination precedence (fail-closed): protection (SELF/DESCENDANT →
`PROTECTED`; ANCESTOR → decompose as `HUMAN_REVIEW`) → incomplete
observation → `UNKNOWN` → system/application-managed without a contract
→ `HUMAN_REVIEW` → no contract / undocumented evidence →
`HUMAN_REVIEW` → non-regenerable contract → `KEEP_PROVEN` →
`RECLAIM_PROVEN` (provisional only).

Directory composition may only downgrade, with two exceptions: adopt
`PROTECTED` when a descendant is protected, and allow a directory to be
`RECLAIM_PROVEN` only when every descendant is. An incomplete directory
can therefore never become whole-directory reclaimable.

## 4. Managed-path seam (S13)

`CleanupRun(managed_paths=...)` / `filesteward scan --managed PATH`
marks a path prefix as system/application-managed. The marking is
adapter/operator-declared input — never inferred from observed file
characteristics. Marked items are still inventoried in full, but
without an explicit `--contract` they are excluded from automatic
mutation candidacy (`HUMAN_REVIEW` with an explicit basis) and are
recorded in `run.json` under `managed_paths`. Boundary-aware prefix
matching is shared with contract matching.

## 5. Projection honesty

- Logical size and projected reclaim are distinct columns.
- `allocated-evidence`: platform-reported allocation
  (scanner `st_blocks`) for single-link regular files only.
- `estimate-logical`: explicitly labeled estimate when allocation
  evidence is unavailable (Windows) or link state is not single.
- `container-row`: directories project `None`; descendant rows carry
  the bytes, so nothing is double-counted.
- Hard-linked content is defeated by the challenge
  (canonical survivor not proven) rather than estimated optimistically.
- Stop point: first plan row where
  `baseline_free + cumulative_projected >= target_free`; unreachable or
  unknown inputs are reported honestly (`stop_row: null` with a note),
  never faked.

## 6. Artifacts

All runs are `UNAPPROVED`. `manifest/` owns column contracts (P04
§14): `cleanup-plan.csv` (only `RECLAIM_PROVEN`), `human-review.csv`
(`HUMAN_REVIEW`/`UNKNOWN`, prose columns scanned for
score/persuasion language), `protected-exclusions.csv` (reason + source
required, relationship must be SELF/DESCENDANT/ANCESTOR),
`inventory.csv`, `cleanup-summary.md` (estimates separated from proof),
`run.json`. `validate_run` re-derives membership, arithmetic,
per-item `item_id` reconciliation, forbidden language, and stop-row
math; `CleanupRun.execute` runs it on every scan and aborts on error.

## 7. CLI

| Command | Behavior | Exit |
|---|---|---|
| `scan <root> --run-dir <dir>` | read-only analysis | 0 ok / 2 invalid |
| `validate <run-or-cleanup-plan.csv>` | re-derive artifacts | 0 ok / 2 invalid |
| `apply <manifest>` | refusal seam (never honors `--execute`) | 3 |

Scan options: `--contract` (repeatable cache-contract prefix),
`--protect` (repeatable protected root), `--managed` (repeatable
system/application-managed prefix), `--target-free-bytes`,
`--baseline-free-bytes` (tests/override).

## 8. Safety invariants (machine-checked)

- No destructive primitives anywhere in `src/` (grep-proven; the only
  "delete" strings are the forbidden-language list itself).
- Scanner opens no file content: placeholders cannot hydrate;
  proven structurally and by test.
- Symlinks/reparse points recorded, never followed.
- Unreadable entries become explicit `UNKNOWN`/incomplete evidence —
  absence is never inferred.
- Challenge can sustain or downgrade only; upward promotion is a
  structural impossibility (no import of nominating rules; tests).
- No age/size/name/location-only reclaim rule (tests).
- Runtime output only under `var/`; privacy greps and `git ls-files
  var` clean in CI-style checks.

## 9. S1–S14 → proof mapping

| Scenario | Primary proof |
|---|---|
| S1 CLI happy path | `tests/test_cli.py::TestS1CliEndToEnd` |
| S2 protected descendant | `tests/test_protection.py` |
| S3 semantic ambiguity | `tests/test_disposition.py -k s3` |
| S4 provisional survives | disposition + challenge `-k s4` |
| S5 challenge defeat | `tests/test_challenge.py` |
| S6 mixed directory | `test_disposition.py::test_s6_*` + `test_artifacts.py::TestMixedDirectoryComposition` |
| S7 protected-subtree ancestor | `tests/test_protection.py` |
| S8 real Git semantics | `tests/test_protection.py::TestRealGitSemantics` |
| S9 junction no-follow | `tests/test_scan.py::TestNoFollow` |
| S10 symlink no-follow | `tests/test_scan.py::TestNoFollow` |
| S11 access denied | `tests/test_scan.py::TestUnreadableIsExplicit` |
| S12 placeholder no-hydration | `tests/test_scan.py::TestCloudPlaceholder` |
| S13 managed mutation exclusion | disposition `-k s13`, `TestS13ManagedExclusion`, CLI `--managed` test |
| S14 incomplete directory fail-closed | `TestUnreadableIsExplicit` + `test_incomplete_descendants_are_unknown_even_with_contract` |

## 10. Known limitations (honest, by design)

- Windows does not report per-file allocation through `st_blocks`;
  projections there are labeled `estimate-logical` (the abandoned
  ctypes measurement attempt returned logical size and AV-crashed; it
  is not used).
- `DirEntry.stat(follow_symlinks=False)` reports `st_nlink=0` on
  Windows; the scanner re-observes via no-follow `os.stat` and records
  `None` rather than a false zero.
- The `PROTECTED`-disposition-with-`UNRELATED`-relation branch in
  `run._partition` is currently unreachable under rule precedence
  (defense in depth; noted by the L4 critique, left in place).
