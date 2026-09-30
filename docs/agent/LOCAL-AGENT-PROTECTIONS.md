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
- perform an explicitly approved, bounded, revalidated quarantine action in a future execution phase.

A local agent MUST NOT:

- decide that a semantically ambiguous personal/project file is safe to remove;
- infer importance or lack of importance from age, size, filename, extension, location, or inactivity;
- convert "probably generated", "looks duplicate", "old installer", or similar language into action authority;
- inspect private content beyond the explicitly authorized privacy mode;
- self-approve its own manifest;
- weaken tests or policies to make a candidate pass;
- treat failure to find evidence of value as evidence of disposability;
- use AI confidence as a substitute for deterministic evidence.

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

Only a distinct operator-approval artifact bound to an exact manifest digest/run ID/row set may authorize future action.

No `HUMAN_REVIEW`, `UNKNOWN`, or `PROTECTED` item may be automatically promoted into an approved action.

## 3. Fail closed

Any unresolved conflict moves away from action:

- `RECLAIM_PROVEN` + new ambiguity -> `HUMAN_REVIEW`
- any disposition + protection evidence -> `PROTECTED`
- incomplete scan / unreadable child -> `UNKNOWN` or decomposition
- stale identity / changed file at apply time -> refuse action
- uncertain reclaim math -> estimate, never "proven bytes"

No rule may resolve conflict toward deletion merely to make progress.

## 4. Protection semantics

A protected repository/worktree root protects itself and its descendants.

If a candidate directory is an ancestor that contains a protected subtree, the whole-directory action is prohibited and the directory must be decomposed. Unrelated siblings remain independently evaluable.

Protection must be rebuilt immediately before any future mutation. Audit-time protection evidence is not permanent authority.

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

## 8. Windows traversal safety

Default read-only scanning must not:

- recursively follow junctions/reparse points;
- silently follow symlink targets as normal child content;
- hydrate online-only/cloud placeholder files merely to inventory them;
- treat access-denied descendants as absent;
- infer a complete directory when some descendants were unreadable;
- turn Windows/application-managed system paths into mutation candidates without an explicit adapter contract.

Scan gaps become explicit `UNKNOWN` evidence.

## 9. No permanent deletion in the current MVP

FileSteward's current repository contract excludes permanent deletion.

For ordinary files, a future operator-approved cleanup action goes to quarantine first and produces an audit/restore record.

Application-managed/native caches may eventually require a separate direct-purge adapter where quarantine is technically inappropriate. That must be an explicit adapter contract with its own proof, not an exception invented by a local agent.

## 10. Audit and apply are separate proof boundaries

A live audit may propose reclaim candidates. It may not mutate them.

Future apply must revalidate:

- exact approved manifest digest;
- explicit approved rows/actions;
- source still inside approved scope;
- source still exists;
- item identity has not materially changed;
- protection index freshly rebuilt;
- no new protected overlap;
- canonical survivor still exists for duplicate-based actions;
- quarantine destination capacity;
- collision rules;
- filesystem semantics needed for the action.

Any mismatch fails closed.

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

Before mutation:

1. refresh origin/provider truth;
2. work on an isolated task branch/worktree;
3. declare owned and forbidden scope;
4. preserve unrelated work;
5. build the smallest correct change;
6. run the owning validators/tests;
7. report skipped/failed checks honestly;
8. stop at the requested proof boundary.

Do not merge, release, live-scan, or cross into a more sensitive phase merely because the preceding phase passed.

## 13. Real-data gate

Synthetic implementation proof and real workstation observation are different authorization domains.

Phase 1-4 implementation may use only synthetic/temp fixtures.

A real `C:` scan begins only after:

- synthetic gates are green;
- exact read-only command is shown;
- operator explicitly authorizes crossing into real workstation observation.

Read-only does not mean privacy-free.

## 14. Reporting semantics

Final reports distinguish exactly:

- designed
- implemented
- locally validated
- committed
- pushed
- PR-open
- live-audited
- operator-approved
- applied
- verified-reclaimed

Never turn a skipped check, estimate, design assertion, or reviewer/status badge into higher proof.
