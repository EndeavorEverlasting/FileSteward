# Operator Delete Path — outcome-bound execution contract

## Purpose

This contract exists because FileSteward's storage program repeatedly reached intermediate states — inventory, visualization, manifest generation, preflight, implementation, tests, PRs, and merge-readiness — without delivering the operator's requested outcome: **freeing real space on C:**.

For a bounded deletion sprint, repository readiness is not the terminal outcome. The terminal outcome is an observed filesystem mutation with durable proof.

## Terminal success condition

A deletion iteration is successful only when all of the following are true:

1. At least one manifest-enumerated, operator-authorized item was actually removed by the permanent-delete executor.
2. A deletion execution receipt exists in ignored local runtime storage.
3. The receipt records attempted / succeeded / failed / skipped counts and does not collapse PARTIAL into success.
4. C: free bytes were measured before and after the execution.
5. The run reports the strongest supported reclaim state, with `VERIFIED_RECLAIM` only when the observed free-space evidence supports it.
6. The final report includes the exact run ID, receipt path, succeeded count, failed/skipped count, projected reclaim, observed free-space delta, and any residual items.

`implemented`, `tests green`, `PR open`, `PR merged`, `preflight PASS`, `approval artifact written`, and `ready to delete` are all **intermediate states**. An agent must not stop at one of them while the authorized deletion outcome remains executable.

## Authority model

Evidence, disposition, authorization, and execution remain separate:

```text
evidence -> disposition -> exact delete set -> operator authorization -> fresh revalidation -> deletion -> receipt -> reclaim verification
```

The separation is a safety control, not a conversational permission loop.

A clear natural-language operator instruction that identifies the bounded run or scope and authorizes permanent deletion is sufficient operator intent to create the repository's required local approval artifact. Do not invent or demand a magic phrase, chat incantation, extra confirmation sentence, UI toggle, or repeated approval at each seam.

The approval artifact remains mandatory because it binds the operator's authorization to an exact manifest/preflight identity. The artifact is evidence of authorization; it is not a reason to re-ask for the same authorization.

## Same-iteration continuation rule

Once the operator has authorized a bounded delete outcome, every repair necessary to make that exact bounded outcome executable belongs **inside the same iteration**.

Examples:

- If the old manifest drifted, regenerate the manifest from the same authorized scope and continue.
- If preflight finds a repairable implementation defect, repair it, add the regression, validate it, integrate the exact fix, refresh local main, and continue.
- If a subset is locked, stale, missing, or otherwise fails closed, preserve the failure evidence and continue with the independently valid authorized subset when the contract permits partial execution.
- If the executor returns PARTIAL, treat that as a non-success exit for automation while still preserving successful per-item deletions and then continue or report residual blockers.
- If the approved Temp run is stale beyond reuse, rebuild the Temp run from the same bounded regenerable-cache contract rather than stopping at "needs a new run."

A defect discovery is therefore not a terminal state. A successful repair is not a terminal state. A merged repair is not a terminal state. The iteration continues to deletion.

## Current production seams

Permanent-delete execute admits these contract-backed regenerable roots (realpath containment):

1. the operator's process temp root (`tempfile.gettempdir()`), including the Temp reclaim program;
2. the explicit regenerable-cache allowlist in `filesteward.deletion.regenerable`:
   - `%LOCALAPPDATA%\npm-cache`
   - `%LOCALAPPDATA%\ms-playwright`
   - `%LOCALAPPDATA%\CrashDumps`
   - `%LOCALAPPDATA%\pip\Cache`
   - Chrome `Default\Cache` and `Default\Code Cache` only (not the whole profile)

For those seams, preflight may seal identity with size+mtime only (skip full-file SHA-256) so large cache trees remain terminal; execute still uses open→fstat→unlink TOCTOU, and hashes when a content digest is present.

### Incident lock — application serviceability caches

`%PROGRAMDATA%\Package Cache` is **not** a generic regenerable seam. FileSteward must refuse automatic permanent deletion of that root until the dependency-aware storage judgment contract is implemented and a per-entry adapter proves an orphan/serviceability-safe disposition. Cache-like naming, age, or size does not establish regenerability.

The governing contract is `harness/contracts/storage-dependency-judgment.v1.json`, and the active implementation plan is `plans/active/FILESTEWARD-APPLICATION-REPOSITORY-AWARE-JUDGMENT-P00-P01-P04-P82-2026-10-07.md`.

Do not widen from these seams into semantically ambiguous personal files, whole browser profiles, OneDrive, or other home trees merely to increase deletion volume.

When a named historical run is no longer current, regenerate a fresh run from the same bounded authorized root and contract. The run identity may change; the authorized outcome and scope do not silently expand.

## Required live sequence

From the canonical local FileSteward checkout on refreshed `main`:

1. Record exact repo/branch/HEAD/status and baseline C: free bytes.
2. Resolve the current Temp run. Prefer the existing authorized run when still valid; otherwise regenerate from the same Temp contract and emit a fresh exact delete manifest.
3. Run fresh delete preflight.
4. If preflight exposes a repository defect, repair the smallest canonical owner, add a regression, run focused + full validation, integrate the exact repair, refresh the local checkout, then resume at step 2 or 3. **Do not end the iteration at the repair.**
5. Materialize the local irreversible approval artifact from the operator's already-given bounded authorization.
6. Run permanent delete through the repository-owned executor.
7. Read back the execution receipt.
8. Measure C: free bytes again.
9. Run/derive reclaim verification.
10. Continue on residual valid approved items when safe until the run reaches its bounded fixed point.
11. Report runtime proof.

## Defects that must be closed before or during the next live execution

Post-merge review of PR #20 identified defects that can invalidate live deletion safety. They are **inline prerequisites**, not successor sprints:

- live-home / pytest-name root-allowance bypass;
- target identity / TOCTOU gap between preflight and unlink/rmdir;
- current protection / managed-state freshness not propagated into execution;
- ancestor symlink/junction/reparse escape;
- insufficient content/file-identity strength;
- missing cleanup-plan digest failing open;
- PARTIAL execution returning a success exit status;
- allocated-size fixture mismatch that weakens proof portability;
- any still-current duplicate review threads representing the same defect families.

The next agent must reproduce or disprove each against current `main`, repair every material still-current finding, and then continue directly into live deletion in the same iteration.

## Hybrid execution semantics

The resolved execution program combines the relevant TokenCorridor prompt authorities without adding their authorities together:

- **P01 — Harness Infrastructure Builder:** encode this path durably in harness/docs/tests so later agents do not regress to permission theater.
- **P04 — Repo-Aware Sprint + Harness Factoring:** keep one bounded critical path whose final node is live deletion/reclaim proof; do not create cosmetic or UI lanes on the critical path.
- **P97 — Prior-Art & Gap Analyst:** use external/reference mechanisms only to sharpen a concrete defect repair when needed. Research is an input, never a reason to postpone an already-bounded deletion.
- **P83 — Agent Work Verifier & Iterative Advancer:** treat inherited Cursor claims as hypotheses, repair contradicted claims, and keep advancing past green intermediate states.
- **P82 — Prototype-Measure-Refine:** repair -> measure -> critique -> refine loops continue until the terminal runtime outcome is observed, not until a prototype looks plausible.
- **P08 — Live Runtime Proof Executor:** repository/static proof does not satisfy the sprint. The actual filesystem side effect, receipt, and free-space observation are required.

One coordinator retains final judgment. Local agents perform bounded repository and local-filesystem legwork.

## Local-agent role

Local agents are execution engines, not semantic authorities.

They may:

- inspect current repo/provider state;
- reproduce review defects;
- implement bounded repairs;
- add/run tests and validators;
- commit/push/open/merge authorized repair work under repository rules;
- regenerate contract-backed Temp artifacts;
- run preflight;
- create the local approval artifact from already-given operator authorization;
- execute the bounded permanent-delete CLI;
- read receipts and measure free space;
- retry repairable failures.

They may not:

- promote HUMAN_REVIEW / UNKNOWN / PROTECTED items into deletion;
- broaden the approved scope into personal or semantically ambiguous data;
- use generic recursive deletion outside the manifest;
- follow reparse/symlink targets;
- invent extra operator permission gates;
- stop merely because an intermediate repository milestone was reached.

## Stop rules

### PASS

Stop with PASS only after real deletion occurred and runtime evidence was collected.

Minimum PASS evidence:

```text
deleted_items > 0
execution_receipt = present
action = DELETE_PERMANENTLY
pre_free_bytes = observed
post_free_bytes = observed
free_space_delta = reported
repository/runtime artifacts = preserved
```

### BLOCKED

A BLOCKED stop is valid only for a genuine dependency the agent cannot repair, route around, or execute with available authority/capabilities. Examples include an OS/endpoint state that prevents every bounded eligible deletion and cannot be changed safely, missing credentials/privileges that the agent cannot obtain, or the authorized bounded scope containing zero eligible items after a fresh rescan.

Before declaring BLOCKED, the agent must have advanced every independent safe step, preserved evidence, and named the smallest exact operator/external action that would unblock deletion.

"Needs another sprint", "needs approval again", "repair merged", "tests green", "preflight ready", and "deletion can now be run" are **not** blockers.

## Privacy

All live manifests, approval records, paths, hashes, receipts, and free-space/runtime evidence remain under ignored local runtime storage such as `var/runs/<run_id>/`. Do not commit private workstation evidence.

## Final report contract

The agent's completion report must distinguish:

- repair implemented / validated / committed / pushed / merged;
- live run ID;
- approval artifact state;
- deletion execution state;
- execution receipt path;
- attempted / succeeded / failed / skipped counts;
- projected reclaim;
- pre/post C: free bytes;
- observed free-space delta;
- reclaim verification state;
- residual blockers, if any;
- git status and exact HEAD.

If `succeeded=0`, the requested outcome is not complete.
