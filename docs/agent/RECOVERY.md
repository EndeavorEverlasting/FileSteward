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
- If the session database file itself is unreadable: **STOP**. Copy it read-only as evidence and report the exact error; do not repair, delete, or reinstall OpenCode data directories. The evidence copy may live only in the ignored runtime tree (`var/`, per `docs/agent/CANONICAL-PATHS.md`) or an explicitly operator-approved external location — never a tracked path.

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

Step A — read-only inspection (no repository mutation). Run before trusting any remembered state:

```powershell
git rev-parse --show-toplevel        # identity gate 1: must be the canonical checkout root
git remote get-url origin            # identity gate 2: must equal the repository URL in CANONICAL-PATHS section 1
git status --short
git log --oneline --decorate -5
gh pr list --state all
gh pr checks <n>
git merge-base --is-ancestor <SHA> <branch>   # exit 0 = <SHA> is contained in <branch>
```

Step B — refresh (explicitly authorized sync step; mutates local refs). Run only after both identity gates pass:

```powershell
git fetch --all --prune --tags       # updates remote-tracking refs, prunes stale refs, contacts origin
```

Rules:

- Report each command and its exact exit code. `git merge-base --is-ancestor` exit 0 proves containment; any other exit code means containment is not proven — report it, do not assume it.
- Any identity-gate mismatch (root is not the canonical checkout, or origin differs from `CANONICAL-PATHS.md` section 1) => **STOP**: do not fetch, do not redirect the remote, report the exact observed values.
- `git fetch` is never read-only: it updates remote-tracking refs, prunes stale refs, and contacts the configured remote. Keep it out of any sequence labeled read-only, and never run it before both identity gates pass.
- Any unrelated, untracked, or unknown local change => **STOP**: do not stash it, do not reset it, do not clean it, report it verbatim.
- Reconcile continuation against **current** tracked status, not a remembered sprint:
  - `plans/active/C-DRIVE-CLEANUP-P04.md` status header (integrated vs implementation-ready),
  - `plans/active/C-DRIVE-CLEANUP-OPENCODE-HANDOFF.md` **Current disposition** block first (archival B0→L4 text below it is not a re-execution order),
  - `docs/program/next-sprint-live-audit.md` for the Phase 5 authorization surface.
  Never substitute a remembered branch pin or chat “next step” for those tracked gates. If the handoff still looked like a live `B0→L4` execution order, treat that as a continuity defect and **STOP** rather than replaying the completed lane.

## 4. Precedence and authority

This file adds tooling-recovery procedures and commands on top of the `CANONICAL-PATHS.md` §4.1 discoverability entry. Safety, ambiguity, privacy, and authorization semantics stay with `AGENTS.md` and `docs/agent/LOCAL-AGENT-PROTECTIONS.md`; repository, worktree, runtime, entry-point, and tooling-state path resolution stays with `docs/agent/CANONICAL-PATHS.md`.

Recovery or rehydration never authorizes mutation. Resumed context re-enters at the last unproven gate; safety authority stays with `AGENTS.md`, `docs/agent/LOCAL-AGENT-PROTECTIONS.md`, and `docs/agent/CANONICAL-PATHS.md`. A recovered transcript is context, not approval.
