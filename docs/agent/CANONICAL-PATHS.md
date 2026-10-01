# Canonical Paths

FileSteward runs on real workstations where Desktop redirection, cloud sync, nested checkouts, and improvised directories are routine. This file is the single path authority for the repository.

If any other tracked file, chat message, script default, or habit disagrees with this file, this file wins. A conflict about paths is a safety conflict: **STOP** and report the exact conflict. Never reconstruct a path rule from memory.

## 1. Repository identity

```text
EndeavorEverlasting/FileSteward
https://github.com/EndeavorEverlasting/FileSteward.git
```

## 2. Profile key

Profile key: `windows-userprofile`.

One rule per profile. The username is a runtime input, never a constant in tracked content. POSIX/macOS hosts resolve the same shape under `$HOME`.

## 3. Resolution rule

```powershell
$devRoot      = Join-Path $env:USERPROFILE 'dev'
$repo         = Join-Path $devRoot 'FileSteward'
$worktreeRoot = Join-Path $devRoot 'worktrees\FileSteward'
```

- The development checkout is `dev\FileSteward` directly under the machine dev root.
- Worktree lanes live under `dev\worktrees\FileSteward\<lane>`.
- The checkout never nests inside another checkout, and worktrees never live inside the checkout or at unrelated siblings.

## 4. Roles

Each role has exactly one owner. Do not collapse roles.

| Role | Owner |
|---|---|
| Canonical development checkout | `$repo` — exactly one normal mutable checkout per machine |
| Canonical worktree root | `$worktreeRoot\<lane>` — created only via `git -C $repo worktree add` |
| Canonical production/use path | the `filesteward` console entry point declared in `pyproject.toml` |
| Canonical entry point | `filesteward` (CLI vocabulary is owned by the active plan, section 10) |

The production/use path is an entry point, not a directory. It resolves through the active Python environment to an installed copy or an editable link to the checkout. The relation must be observed and recorded (section 5), never assumed.

## 5. Path relation and production state — record, never collapse

Observed receipt (state as of this contract):

```text
PROD_USE_STATE: OFFLINE
evidence: pip package not installed; no filesteward command; import fails
```

Rules:

- After `python -m pip install -e .`, the relation is **SAME + EDITABLE**: the use path is the checkout itself.
- Because `PROD_USE_STATE` is `OFFLINE`, no consumer observes the checkout, so ordinary checkout writes are safe. If a consumer appears, record it before any mutation.
- A future non-editable install or release is a tracked promotion boundary. It does not exist yet. Never silently substitute one relation for another, and never report `PROD_PATH_CURRENT` or `ENTRYPOINT_PROVED` without fresh command evidence.

## 6. Forbidden roots

Never resolve the checkout, worktrees, runtime output, quarantine, or install targets under:

```text
Desktop
Documents
OneDrive
Backups
```

Machine evidence for this rule: the Desktop Known Folder on the reference workstation is redirected into OneDrive while the physical `%USERPROFILE%\Desktop` also exists, so any `Desktop\Dev` rule resolves ambiguously; OneDrive-synced checkouts are also unsafe for git objects and file locks. The rule does not depend on that machine state and must not be relaxed where redirection is absent.

## 7. Precedence

1. This tracked contract.
2. An authorized machine/profile override recorded in this file or a tracked successor.
3. Runtime environment resolution (`$env:USERPROFILE`, `$HOME`).
4. Verified evidence of an existing checkout.

If the canonical root is unavailable, the result is a **BLOCKER**. Never fall back to a forbidden root, the current working directory, or a plausible-looking substitute.

## 8. Drift states

| State | Meaning |
|---|---|
| `CANONICAL+PROVED` | path derived from this contract and proved by command output |
| `NONCANONICAL+PRESERVE` | copy exists outside the contract and may contain uncommitted work |
| `NONCANONICAL+DISPOSABLE` | copy is provably empty of unique work; disposal still needs operator approval |
| `MISSING` | role exists in the contract but no path/entry point was observed |
| `CONFLICT` | two rules or two observed paths disagree — STOP |
| `UNKNOWN` | not yet inspected on this machine |

## 9. Noncanonical copies

Classify every observed copy as one of: `CLONE`, `WORKTREE`, `INSTALL`, `MIRROR`, `CACHE`, `OUTPUT`, `BACKUP`.

- Refuse a second normal mutable checkout while the canonical one is usable.
- Preserve dirty or unpushed work. Never reset, clean, or force-move a copy for tidiness.
- Disposition of a noncanonical copy is operator judgment: default is preserve, classify, and report.

## 10. Integration ladder — four distinct states

```text
REMOTE_INTEGRATED  — commit exists on the tracked remote branch
DEV_CHECKOUT_CURRENT — local checkout matches the expected remote head
PROD_PATH_CURRENT  — observed production/use relation matches this contract
ENTRYPOINT_PROVED  — installed entry point invoked with recorded exit code
```

Remote integration is not workstation deployment. Report each state separately with its own evidence; never infer one from another.

## 11. Receipt

Whenever paths matter to a claim, report:

- profile key and host;
- contract file as read (path and commit);
- resolved path per section 3;
- observed path per role, or `MISSING`;
- relation per section 5;
- drift state per section 8;
- exact command and exit code behind each observation.

Evidence before confidence. The operator owns judgment.
