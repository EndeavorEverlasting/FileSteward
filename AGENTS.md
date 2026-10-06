# FileSteward — agent entry

FileSteward handles potentially irreplaceable personal and project data. Local coding agents are execution engines, not judgment authorities.

## Read before mutation

1. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
2. `docs/agent/CANONICAL-PATHS.md` (including §4.1 recovery discoverability)
3. `docs/agent/OPERATOR-DELETE-PATH.md` when the requested outcome includes real deletion or reclaim
4. The active plan under `plans/active/` for the requested sprint
5. `README.md` safety, privacy, and MVP boundaries

If any required contract cannot be read, stop. Do not reconstruct it from memory.

## Non-negotiable local-agent boundary

- Do not resolve semantic ambiguity for the operator.
- Do not infer that a file is disposable from age, size, extension, filename, location, inactivity, or apparent duplication.
- Do not promote `HUMAN_REVIEW`, `UNKNOWN`, or `PROTECTED` into a reclaim/action state.
- Do not let an agent-generated manifest authorize its own mutation.
- Do not combine classification and destructive execution in one proof boundary.
- Permanent deletion is available only through the repository-owned exact-manifest path documented in `docs/agent/OPERATOR-DELETE-PATH.md`: exact eligible set, distinct operator authorization artifact, fresh revalidation, bounded executor, receipt, and reclaim verification. No generic recursive-delete substitute is allowed.
- A clear natural-language operator authorization for a bounded named run/scope/action is sufficient intent to create the required local approval artifact. Do not invent magic phrases, UI toggles, or repeated conversational approvals at each seam.
- Once a bounded deletion outcome is authorized, repository repair, tests, commit, PR, merge, preflight PASS, and approval-artifact creation are intermediate states. Continue through live deletion and runtime proof in the same iteration unless a genuine unrepairable external/user-only blocker remains.
- Real workstation scans, private paths, filenames, hashes, queues, manifests, approvals, and receipts belong in ignored runtime storage, never committed fixtures.

## Sprint discipline

Isolate → Build → Prove → Stop/Ship.

- Work on an isolated task branch/worktree; never build on `main`.
- Preserve the existing quality floor. Failed or skipped validation is not completion.
- Use synthetic fixtures for implementation proof.
- Crossing from synthetic proof into real `C:` observation or mutation requires an explicit operator gate. Once that exact bounded gate has already been granted, do not re-ask merely because the workflow crossed an internal seam.
- Do not stop at a green branch/PR merely to ask for ceremonial merge permission. When the exact validated head is current, required repository-owned gates/reviews/dependencies/protection rules are green, no explicit prohibition exists, and merge authority is available, integrate it into the refreshed default branch and verify containment/content.
- For an authorized deletion sprint, do not stop at a green merge either. Refresh the canonical local checkout and continue to the bounded live delete + receipt + free-space readback required by `docs/agent/OPERATOR-DELETE-PATH.md`.
- Before any PR merge, refresh the exact PR head and enumerate unresolved review threads. Every material finding must be either disproven against that exact head or repaired and resolved. A passing local test suite never overrides unresolved material review evidence.
- Release/deploy follows the repository's explicit promotion contract. When that contract already authorizes the promotion and its gates are green, no extra conversational confirmation is required; an explicit operator prohibition or named external gate still wins.

## Execution, Entire, and provider policy

Repository-owned local commands are the semantic proof floor. GitHub Actions are optional provider-side execution/independent evidence, not the canonical owner of tests, validators, build profiles, or merge readiness. Do not add or require Actions merely to create a green badge.

On an operator development host where Entire CLI is available, use Entire as the Git-native agent/session/context and mirror layer:

1. run `entire status --json` during repository orientation;
2. preserve Entire session/checkpoint integration across agent handoffs;
3. use Entire mirror/clone transport when configured by the operator;
4. never substitute GitHub Actions for missing local proof or Entire continuity;
5. never promote Entire session context into repository truth without Git/provider/content verification.

If Entire is expected by the repository/operator but unavailable on the current host, report the tooling gap and continue every safe repository-owned local proof that remains possible. Do not invent an Actions workflow as a fallback.

GitHub remains the remote provider for PR/review/merge state where this repository is hosted there. Provider status is reconciled with, not substituted for, repository-owned proof.

## Evidence language

Distinguish: designed, implemented, locally validated, committed, pushed, PR-open, merged, live-audited, operator-approved, applied, verified-reclaimed.

Never claim a higher state than the evidence proves.
