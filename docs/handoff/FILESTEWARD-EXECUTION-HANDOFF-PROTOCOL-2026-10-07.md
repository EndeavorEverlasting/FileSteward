# FileSteward Execution Handoff Protocol — P04 + P82 — 2026-10-07

## Purpose

This protocol exists so a fresh local agent can **continue execution immediately** without reconstructing product judgment, re-planning completed work, or asking the operator to act as scheduler.

Canonical machine owners:

- `harness/contracts/execution-handoff-loop.v1.json`
- `harness/contracts/execution-handoff-packet.schema.v1.json`
- `harness/evals/execution-handoff-review-gates.v1.json`

The active dependency-aware sprint and scene contracts remain product/safety authority. This protocol owns **continuation mechanics**, not product judgment.

## Closed judgment authority

Before executing this protocol, read `harness/contracts/dependency-aware-judgment-closure.v1.json`. It closes the current integration order, lane ownership, module boundaries, provider PR policy, and PR #29 strategy. The receiver verifies and executes those decisions; it does not reopen them.

## Operating loop

Every handoff runs the same loop:

```text
RECOVER
  -> PARTITION
  -> DISPATCH
  -> EXECUTE
  -> PROVE
  -> REVIEW
  -> CONVERGE
  -> CONTINUE
  -> (next ready work or verified terminal outcome)
```

A gate failure routes back to the **earliest invalidated phase**. It does not disable the scheduler, cancel unrelated work, or force a new planning conversation.

A passing gate means continue under existing authority. Do not stop merely to report that a gate passed.

## Receiver algorithm

A receiving agent MUST:

1. Read `AGENTS.md`, the packet's canonical plan, and every packet contract reference.
2. Refresh provider truth and local Git/runtime truth. Treat `*_at_capture` SHAs as evidence floors until refreshed. A tracked packet cannot self-contain its own final commit SHA; RG0 therefore always refreshes current truth before mutation.
3. Validate that completed facts are still compatible with current truth.
4. Recompute only the **remaining** dependency graph. Completed facts are inputs, not tasks to repeat.
5. Start every dependency-ready lane that has a safe execution adapter and non-conflicting mutation ownership.
6. Execute the packet's `exact_next_action` immediately when dependencies and authority are satisfied.
7. Run the typed review gates before each transition that requires them.
8. Repair failed gates in their named owner surface and rerun only invalidated downstream proof.
9. Produce a successor packet before handing work to another agent/runtime.
10. Continue until the sprint outcome is verified or a genuine external/judgment blocker remains.

A response that only restates the plan, says “ready,” opens a PR, or asks the operator to paste the next lane is **not a valid handoff completion** when execution can continue.

## Packet semantics

### Captured head semantics

The packet fields `provider_base_sha_at_capture`, `provider_head_sha_at_capture`, and `local_head_sha_at_capture_or_unknown` describe what the sender observed **before the packet itself was persisted**. They are continuity evidence, not immutable current truth.

RG0 requires the receiver to refresh current provider/local heads before mutation. This removes the self-reference trap where committing a tracked handoff would instantly make a field named “current head” false.


Every handoff packet conforms to `filesteward.execution-handoff-packet/v1`.

### Completed facts

Completed facts MUST name evidence and an honest proof state.

Examples:

- `IMPLEMENTED` — source changed, not necessarily tested.
- `LOCALLY_VALIDATED` — repository-owned local proof passed on the named exact candidate.
- `PROVIDER_VALIDATED` — provider/readback/review proof exists; this does not imply local proof.
- `MERGED` — provider confirms integration.
- `LIVE_OBSERVED` / `APPLIED` / `VERIFIED` — require their own runtime evidence.

Never compress these states into “done.”

### Remaining work

Remaining work is executable work only. Each entry names:

- `work_id`
- exact action
- typed dependencies
- acceptance condition

Do not copy completed tasks into remaining work.

### Ownership

`owned_mutation_surfaces` and `forbidden_surfaces` are binding.

If two ready lanes need the same shared surface, P04 convergence resolves the collision **before** dispatch. Parallelism is for independent ownership, not racing writes.

### Private evidence

`private_evidence_refs` may point to ignored local receipts/captures. The packet must not embed private workstation paths, filenames, identities, or raw captures that repository policy keeps local.

### Missing judgment

If the work cannot proceed because product/safety judgment is absent:

```text
blocked_judgment_gap:
  missing_judgment
  canonical_owner
  why_required
```

The receiver does not invent the missing policy.

### Autonomy gap

If graph width permits parallel work but no safe adapter can launch it, record:

- missing adapter
- evidence of unavailability
- smallest repair/bootstrap route

Do not turn the operator into the scheduler merely because one preferred adapter is absent.

## Review gates

Review gates are defined by `harness/evals/execution-handoff-review-gates.v1.json`.

### RG0 — current truth

Before partitioning, refresh:

- main/base/head
- local status/head when available
- canonical contract revisions
- PR/review state
- runtime/tool availability

A historical SHA can orient; it cannot prove current truth.

### RG1 — ownership collision

Before dispatch:

- one mutation owner per shared surface
- lane IDs only in lane dependency arrays
- external prerequisites typed separately
- parallel mutation ownership disjoint

### RG2 — lane scope

Before execution:

- owned and forbidden surfaces
- acceptance condition
- proof ceiling
- no missing product judgment

### RG3 — focused proof

Before review:

- parse changed machine contracts
- run focused tests or mark exact local proof unavailable
- retain negative regression for repaired defect
- retain positive control
- do not weaken the oracle

### RG4 — cross-lane contract

Before convergence:

- downstream references resolve
- changed evidence revisions propagate
- stale proof is invalidated, not reused

### RG5 — provider review

Before merge-candidate status:

- refresh exact PR head
- zero unresolved material review findings
- every finding repaired or disproven against the exact head

### RG6 — repository-local full proof

Before merge:

- required local suite/validators on exact candidate
- Git/diff hygiene
- receipt binds exact head

Provider green cannot substitute for this gate.

### RG7 — PR #29 visual lineage

Before J6 visual mutation:

- refresh PR #29 + main
- recover current Memory Atlas/Decision Chamber lineage
- load P94 protected behavior ledger
- execute the sole authorized selective-lineage procedure in `harness/contracts/dependency-aware-judgment-closure.v1.json`; strategy selection is already closed

No backend lane gets to casually rewrite the scenery.

### RG8 — live UX acceptance

Before J6 is called proven:

- desktop
- narrow viewport
- reduced motion
- forced colors
- pointer + keyboard
- touch/phone when product-declared

Static HTML/string checks do not satisfy this gate.

### RG9 — live mutation authority

Before workstation mutation:

- exact semantic action is covered by operator authority
- target/manifest exact
- dependency evidence current
- authorization current

### RG10 — post-action verification

Before terminal success:

- action receipt
- measured capacity impact where applicable
- action-specific health verification
- incident recovery on regression

## Handoff loop for the current sprint

Current work partitions as:

```text
J0 containment
  -> focused local proof
  -> full local proof / integration gate

J1 incident evidence -----------+
J2 app attribution ------------+--> J4 dependency reducer
J3 repo attribution -----------+           |
                                           v
                                  J5 deletion integration
                                           |
                       J4 integrated -> fixed PR #29 selective lineage port
                                           |
                                           v
                                  J6 scripted scenes
                                           |
                                           v
                                  J7 P82/P94/P110 proof
```

J1/J2/J3 are dependency-independent and should run concurrently when the local runtime has safe adapters. J0's source repair already exists on the remote branch but still needs repository-local proof.

## Exact packet return rule

Every execution agent returns:

1. one valid packet;
2. changed files / exact head;
3. tests and validators actually run;
4. failed-and-repaired evidence;
5. review-thread state;
6. proof ceiling;
7. one exact executable next action.

If another agent/runtime will continue, that packet is the handoff. If the same agent can continue, it should **consume its own next transition rather than stop at the packet**.

## Terminal standard

The loop is terminal only at:

- `SPRINT_OUTCOME_VERIFIED`;
- a genuine external blocker with an executable resume route; or
- `BLOCKED_JUDGMENT_GAP` with its canonical judgment owner.

“Plan complete,” “handoff ready,” “PR open,” “mergeable,” and “tests green while required review remains” are explicitly non-terminal.
