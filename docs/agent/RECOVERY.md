# Recovery

Durable map of agent-tooling state so a crashed session never requires forensic digging.

This file adds tooling-recovery knowledge only. It does not restate, weaken, or conflict with any safety, path, or scope contract.

## 1. Where tooling state lives

| Component | Location | Owner / scope |
|---|---|---|
| OpenCode CLI binary | `C:\Program Files\OpenCode\opencode.exe` (on PATH as `opencode`) | machine scope — Program Files tier |
| Other machine-level tools (Git, GitHub CLI, Python) | same Program Files tier | machine scope |
| OpenCode config (`opencode.json` / `opencode.jsonc`, `commands/`) | `<profile>\.config\opencode` | user scope — XDG-style user directories |
| OpenCode session/message history (SQLite; core tables `session`, `message`, `part`) | `<profile>\.local\share\opencode\opencode.db` | user scope |
| OpenCode logs | `<profile>\.local\share\opencode\log` | user scope |

The app install location and the user data location are deliberately different tiers: install = machine scope, data = user scope.

Path authority for these locations is `docs/agent/CANONICAL-PATHS.md` §4.1 (runtime-derived variables; the username is a runtime input, never a tracked constant). The table above orients by scope; do not let it drift from §4.1. To print the live session-database path without memorizing it:

```powershell
opencode db path
```

Rules:

- Layout rules and the no-fossilize rule: `docs/agent/CANONICAL-PATHS.md` §4.1. This file additionally forbids tracking transcripts or one-incident dates.
- If the session database file itself is unreadable: **STOP**. Copy it read-only as evidence, report the exact error, and do not repair, delete, or reinstall OpenCode data directories.

## 2. Recovering a lost session

Sessions are keyed to the project directory they ran in: resume from the same project directory the session was started in. Commands below are PowerShell; flags verified against `opencode --help` (the help output is authoritative if they evolve).

1. Locate the canonical checkout (path contract: `docs/agent/CANONICAL-PATHS.md` section 3):

   ```powershell
   $repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
   Set-Location -LiteralPath $repo
   ```

2. List sessions (columns: session ID, title, updated time):

   ```powershell
   opencode session list
   ```

3. Identify the interrupted session from the listing by title and updated time. Never record a specific session ID in tracked content.

4. Resume that session from its project directory:

   ```powershell
   opencode $repo -s <sessionID>    # flag: --session <sessionID>
   ```

   To reopen the most recent session instead:

   ```powershell
   opencode $repo -c                # flag: --continue
   ```

5. If the history cannot be opened interactively (crashed app, unreadable UI state), export the session as JSON for offline inspection:

   ```powershell
   opencode export <sessionID>      # --sanitize redacts transcript and file data
   ```

## 3. Proving repository state after an interruption

Run this read-only sequence before trusting any remembered state:

```powershell
git status --short
git fetch --all --prune --tags
git log --oneline --decorate -5
gh pr list --state all
gh pr checks <n>
git merge-base --is-ancestor <SHA> <branch>   # exit 0 = <SHA> is contained in <branch>
```

Rules:

- Report each command and its exact exit code. `git merge-base --is-ancestor` exit 0 proves containment; any other exit code means containment is not proven — report it, do not assume it.
- Any unrelated, untracked, or unknown local change => **STOP**: do not stash it, do not reset it, do not clean it, report it verbatim.
- Reconcile against the tracked handoff (`plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md`) for branch pins and continuation gates; never substitute a remembered pin for the supplied one.

## 4. Precedence and authority

This file adds tooling-recovery procedures and commands on top of the `CANONICAL-PATHS.md` §4.1 discoverability entry. Safety, ambiguity, privacy, and authorization semantics stay with `AGENTS.md` and `docs/agent/LOCAL-AGENT-PROTECTIONS.md`; repository, worktree, runtime, entry-point, and tooling-state path resolution stays with `docs/agent/CANONICAL-PATHS.md`.

Recovery or rehydration never authorizes mutation. Resumed context re-enters at the last unproven gate; safety authority stays with `AGENTS.md`, `docs/agent/LOCAL-AGENT-PROTECTIONS.md`, and `docs/agent/CANONICAL-PATHS.md`. A recovered transcript is context, not approval.
