# FileSteward — agent entry

FileSteward handles potentially irreplaceable personal and project data. Local coding agents are execution engines, not judgment authorities.

## Read before mutation

1. `docs/agent/LOCAL-AGENT-PROTECTIONS.md`
2. `docs/agent/CANONICAL-PATHS.md` (including §4.1 recovery discoverability)
3. The active plan under `plans/active/` for the requested sprint
4. `README.md` safety, privacy, and MVP boundaries

If any required contract cannot be read, stop. Do not reconstruct it from memory.

## Non-negotiable local-agent boundary

- Do not resolve semantic ambiguity for the operator.
- Do not infer that a file is disposable from age, size, extension, filename, location, inactivity, or apparent duplication.
- Do not promote `HUMAN_REVIEW`, `UNKNOWN`, or `PROTECTED` into a reclaim/action state.
- Do not let an agent-generated manifest authorize its own mutation.
- Do not combine classification and destructive execution in one proof boundary.
- Permanent deletion is outside the current MVP. Ordinary approved cleanup actions go through quarantine first.
- Real workstation scans, private paths, filenames, hashes, queues, manifests, and receipts belong in ignored runtime storage, never committed fixtures.

## Sprint discipline

Isolate → Build → Prove → Stop/Ship.

- Work on an isolated task branch/worktree; never build on `main`.
- Preserve the existing quality floor. Failed or skipped validation is not completion.
- Use synthetic fixtures for implementation proof.
- Crossing from synthetic proof into real `C:` observation requires an explicit operator gate.
- Merge or release only on explicit operator instruction.

## Evidence language

Distinguish: designed, implemented, locally validated, committed, pushed, PR-open, live-audited, operator-approved, applied, verified-reclaimed.

Never claim a higher state than the evidence proves.
