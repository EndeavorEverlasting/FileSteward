# Local Agent Protections

FileSteward is intentionally hostile to agent overconfidence.

The repository may be operated by local coding agents that are useful for deterministic execution but are not trusted to make semantic or destructive judgments about personal data. These protections turn that distrust into repository behavior.

## 0. Encode or it does not exist

Assume a local agent will forget context, soften constraints, overgeneralize a heuristic, or convert uncertainty into confidence.

Therefore:

- protections must live in tracked files;
- acceptance gates must be machine-checkable where practical;
- ambiguous states must be explicit outputs;
- authority must be separate from recommendation;
- no chat-only warning counts as a control plane.

## 1. Local agents are not judgment authorities

A local agent MAY:

- inventory metadata within an explicitly approved scope;
- apply deterministic protection rules;
- run deterministic evidence gates;
- produce a proposed-action manifest;
- execute synthetic tests and validators;
- surface ambiguity to the operator;
- perform an explicitly approved, bounded, revalidated quarantine action;
- perform an explicitly approved, bounded, revalidated permanent-delete action only through the repository-owned deletion lifecycle;
- repair repository defects, validate, integrate, regenerate bounded runtime artifacts, execute the approved action, and verify reclaim in one continuous iteration when the operator has already authorized that exact outcome.

A local agent MUST NOT:

- decide that a semantically ambiguous personal/project file is safe to remove;
- infer importance or lack of importance from age, size, filename, extension, location, or inactivity;
- convert "probably generated", "looks duplicate", "old installer", or similar language into action authority;
- inspect private content beyond the explicitly authorized privacy mode;
- self-approve its own manifest;
- weaken tests or policies to make a candidate pass;
- treat failure to find evidence of value as evidence of disposability;
- use AI confidence as a substitute for deterministic evidence;
- invent repeated operator approval gates after a bounded action has already been explicitly authorized;
- stop at repair-readiness, test-green, PR-green, merge, preflight, or approval-artifact creation when live deletion/reclaim proof is still the authorized terminal outcome.

When meaning, uniqueness, provenance, recoverability, personal relevance, or current usefulness requires interpretation, the correct terminal state is `HUMAN_REVIEW`.

## 2. Separate evidence, disposition, authorization, and execution

These are different concerns.

### Evidence state

```text
DISCOVERED -> EVALUATED -> DISPOSITION_ASSIGNED
```

### CleanupDisposition

- `RECLAIM_PROVEN`: affirmative evidence establishes an eligible reclaim candidate.
- `HUMAN_REVIEW`: evidence is present but operator judgment is required.
- `PROTECTED`: automation exclusion applies.
- `KEEP_PROVEN`: affirmative evidence establishes retention.
- `UNKNOWN`: evidence collection is incomplete or technically indeterminate.

`RECLAIM_PROVEN` is not permission to mutate.

### Authorization/execution state

```text
UNAPPROVED -> APPROVED_FOR_ACTION -> APPLIED -> VERIFIED
```

An agent-generated manifest begins `UNAPPROVED`.

Only a distinct operator-approval artifact bound to an exact manifest digest/run ID/row set may authorize action.

A clear natural-language operator instruction that identifies the bounded run/scope/action is sufficient intent to create that local approval artifact. The artifact provides exact binding and replay resistance; it is not a prompt for another conversational permission round.

No `HUMAN_REVIEW`, `UNKNOWN`, or `PROTECTED` item may be automatically promoted into an approved action.

## 3. Fail closed

Any unresolved conflict moves away from action:

- `RECLAIM_PROVEN` + new ambiguity -> `HUMAN_REVIEW`
- any disposition + protection evidence -> `PROTECTED`
- incomplete scan / unreadable child -> `UNKNOWN` or decomposition
- stale identity / changed file at apply time -> refuse that stale item/action until refreshed
- uncertain reclaim math -> estimate, never "proven bytes"

Fail-closed behavior protects the candidate set; it does not automatically terminate the entire authorized iteration. Repairable implementation defects are repaired and revalidated. Stale artifacts are regenerated within the same bounded authorized scope. Independent still-valid approved items may continue when the contract permits partial execution.

No rule may resolve conflict toward deletion merely to make progress.

## 4. Protection semantics

A protected repository/worktree root protects itself and its descendants.

If a candidate directory is an ancestor that contains a protected subtree, the whole-directory action is prohibited and the directory must be decomposed. Unrelated siblings remain independently evaluable.

Protection must be rebuilt immediately before mutation. Audit-time protection evidence is not permanent authority.

## 5. Ambiguity belongs to the operator

The agent's responsibility is to make operator review efficient, not to eliminate it.

`human-review.csv` must:

- sort by consequence/size when useful;
- explain why the item is ambiguous;
- state what the operator should inspect;
- preserve known context;
- state risk if removed;
- contain no delete score, persuasion score, or "likely safe" pressure.

The agent must not repeatedly re-reason a `HUMAN_REVIEW` item until it becomes a reclaim candidate.

## 6. Adversarial downgrade

Every provisional `RECLAIM_PROVEN` candidate must face an independent second pass.

The challenge asks:

> What is the strongest plausible case that acting on this item causes data loss, broken state, lost evidence, rework, or difficult recovery?

The challenger consumes normalized evidence and gate results, not private internals of the nominating rule.

If deterministic evidence cannot defeat the strongest plausible loss case, downgrade to `HUMAN_REVIEW`.

The challenge may downgrade. It may not promote `HUMAN_REVIEW` to `RECLAIM_PROVEN`.

## 7. Reclaim math must be honest

Logical length is not guaranteed reclaimable disk space.

Model separately where available:

- `logical_size_bytes`
- `allocated_size_bytes`
- `projected_reclaim_bytes`
- `reclaim_basis`

NTFS compression, sparse files, hard links, cloud placeholders, and filesystem allocation semantics can make logical size misleading.

If exact allocation/reclaim semantics are unavailable, report estimates. Never label an estimate as proven reclaimable bytes.

The free-space stop condition is:

```text
baseline_free_bytes + cumulative_projected_reclaim_bytes >= target_free_bytes
```

The target is free space, not a fixed amount to delete.

For live delete proof, projected bytes do not satisfy the terminal gate. Measure free space before and after and record the strongest supported verification state.

## 8. Windows traversal safety

Default read-only scanning and mutation preflight must not:

- recursively follow junctions/reparse points;
- silently follow symlink targets as normal child content;
- hydrate online-only/cloud placeholder files merely to inventory them;
- treat access-denied descendants as absent;
- infer a complete directory when some descendants were unreadable;
- turn Windows/application-managed system paths into mutation candidates without an explicit adapter contract.

Scan gaps become explicit `UNKNOWN` evidence.

Deletion containment must account for ancestor reparse/junction/symlink redirection, not only the leaf target.

## 9. Permanent deletion is supported only through the gated delete lifecycle

Permanent deletion is no longer categorically outside the product.

It is allowed only when all required controls are present:

1. exact manifest-enumerated `RECLAIM_PROVEN` set;
2. current cleanup-plan/source evidence and digest;
3. fresh preflight against the real bounded scan root;
4. freshly rebuilt protection/managed state;
5. a distinct `DELETE_PERMANENTLY` approval artifact bound to the exact manifest/preflight/item set;
6. explicit irreversible execution flag;
7. executor-side revalidation immediately before each unlink/rmdir;
8. no reparse/symlink target traversal;
9. per-item execution receipt;
10. before/after free-space observation and reclaim verification.

A quarantine approval must never satisfy permanent deletion.

The supported live seams are contract-backed regenerable data under the process Temp root and the explicit regenerable-cache allowlist (npm-cache, pip\\Cache, ms-playwright, CrashDumps, Chrome cache/code-cache dirs) **only where the owning adapter still proves regenerability**. Semantic personal/project data remains outside automatic permanent deletion unless a separate explicit contract exists.

**Incident lock — ProgramData Package Cache:** generic `%PROGRAMDATA%\\Package Cache` admission is prohibited. Installer/package caches can be application serviceability dependencies; location under a cache-named root is not proof of regenerability. Until a per-entry application/serviceability adapter proves an orphan contract, these paths are `PROTECTED` for automatic deletion and may not become `RECLAIM_PROVEN` from age/size/path heuristics. See `harness/contracts/storage-dependency-judgment.v1.json`.

Do not substitute a generic `rm -rf`, `Remove-Item -Recurse`, wildcard deletion, or broad OS cleanup command for the repository-owned executor when FileSteward is the active path.

See `docs/agent/OPERATOR-DELETE-PATH.md`.

## 10. Audit and apply are separate proof boundaries

A live audit may propose reclaim candidates. It may not mutate them merely because the audit exists.

Apply/delete must revalidate:

- exact approved manifest digest;
- exact approved rows/actions;
- source still inside approved scope;
- source still exists;
- item identity has not materially changed;
- protection index freshly rebuilt;
- no new protected overlap;
- canonical survivor still exists for duplicate-based actions;
- cleanup-plan/source digest still exists and matches;
- ancestor reparse/junction/symlink path remains safe;
- filesystem semantics needed for the action.

Any mismatch fails that stale action closed.

However, once the operator has already authorized the bounded delete outcome, mismatch handling remains inside the same iteration: refresh/regenerate/reapprove the newly exact bounded set when the original authorization still covers the same scope/action, then continue to execution. Do not turn revalidation into repeated permission theater.

## 11. Private data boundary

Real workstation artifacts belong under ignored runtime storage such as:

```text
var/runs/<run_id>/
```

Do not commit:

- real absolute paths;
- real filenames;
- real hashes;
- real inventories;
- real review queues;
- live manifests/approval artifacts;
- scan errors containing private paths;
- quarantine contents;
- live receipts.

Tracked examples and tests must use synthetic/sanitized fixtures.

## 12. Isolate -> Build -> Prove -> Stop/Ship

Before repository mutation:

1. refresh origin/provider truth;
2. work on an isolated task branch/worktree;
3. declare owned and forbidden scope;
4. preserve unrelated work;
5. build the smallest correct change;
6. run the owning validators/tests;
7. report skipped/failed checks honestly;
8. integrate an exact validated repair when repository rules authorize it;
9. if the requested authorized outcome is live deletion, refresh the canonical local checkout and continue through delete execution + runtime proof.

A phase boundary is not automatically a user boundary. Do not stop merely because a predecessor implementation phase completed if the same operator request explicitly requires the next executable outcome and the user-only authorization for that outcome is already present.

Repository integration and live filesystem mutation remain different proof states, but an authorized delete sprint may cross both sequentially in one iteration.

## 13. Real-data and real-mutation gate

Synthetic implementation proof and real workstation observation/mutation are different authorization domains.

A real `C:` scan or deletion begins only after:

- required synthetic/repository gates for the owned path are green;
- the bounded real root/run/action is known;
- operator authorization for crossing into that bounded real domain exists.

Once the operator has explicitly authorized that exact bounded real outcome, do not re-ask at each internal command boundary. Materialize the repository-required local artifact and proceed.

If the exact run artifact has become stale but the operator authorized the same bounded scope/action, regenerate the run within that scope and continue. Do not broaden scope silently.

## 14. Reporting semantics

Final reports distinguish exactly:

- designed
- implemented
- locally validated
- committed
- pushed
- PR-open
- merged
- live-audited
- operator-approved
- applied
- verified-reclaimed

For an authorized deletion sprint, `applied` requires a real execution receipt with at least one successful deletion. `verified-reclaimed` requires measured runtime evidence.

If `succeeded=0`, the deletion outcome is not complete.
