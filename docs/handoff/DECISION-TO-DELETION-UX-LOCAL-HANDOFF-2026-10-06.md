# Local Agent Handoff — Decision-to-Deletion UX — 2026-10-06

## Role

You are the **local execution engine** for an already-judged sprint.

Do not redesign, re-plan, reinterpret, narrow, widen, or replace the canonical requirements.

## Canonical judgment — read, then execute

Read in this order:

1. `AGENTS.md`
2. `plans/active/DECISION-TO-DELETION-UX-P04-2026-10-06.md`
3. `docs/agent/DECISION-TO-DELETION-UX-INTEGRATION-SEAM.md`
4. `plans/active/DECISION-TO-DELETION-UX-TRACEABILITY-2026-10-06.json`
5. `harness/contracts/action-scene-impact.v1.json`
6. `docs/program/action-scene-impact-prior-art-p97-2026-10-06.md`
7. `docs/agent/OPERATOR-DECISION-UX-PATH.md`
8. `docs/agent/OPERATOR-DELETE-PATH.md`

Those artifacts own judgment. This handoff does not.

If this handoff conflicts with a canonical artifact, **the canonical artifact wins**.

## Mechanical mission

1. Refresh local + provider truth.
2. Create the prescribed isolated implementation branch/worktree.
3. Execute the exact integration seam from the canonical seam document.
4. Record seam ancestry and pre-feature validation evidence.
5. Implement the canonical requirements.
6. Drive every row in the canonical traceability ledger from `UNPROVEN` toward its required proof ceiling.
7. On validation failure: inspect -> diagnose against the owning row -> repair within scope -> rerun failed/dependent gates.
8. Refresh `origin/main` at the canonical checkpoints and consume newly landed deletion repairs exactly as prescribed.
9. Run the full repository/browser/versioning proof stack.
10. Push/open/update/integrate the implementation PR when the canonical gates permit.
11. Return an evidence report keyed to every canonical traceability row.

## No local judgment substitution

Do not:
- invent a new plan;
- choose a different merge topology;
- selectively cherry-pick a substitute UI lineage;
- change deletion authority;
- reinterpret an acceptance row;
- add a redundant permission/confirmation gate;
- waive a failed proof;
- call a canonical requirement "future work";
- stop at "ready" when the canonical integration gates authorize continuation.

If a **material** judgment is genuinely missing from all canonical artifacts and current repository/provider truth:

```text
BLOCKED_JUDGMENT_GAP
```

Complete all independent mechanical work first, preserve the evidence, and return the smallest unresolved decision. Do not invent the answer.

## Required local execution frame

```text
repo: EndeavorEverlasting/FileSteward
canonical checkout: %USERPROFILE%\dev\FileSteward
implementation branch: feature/decision-to-deletion-ux-20261006
PR target: main
UI source lineage: current origin/design/u1-brand-home-schedule-seam-20261005
```

Refresh exact SHAs before mutation. Historical SHAs in canonical docs are evidence floors, not permission to ignore newer provider truth.

## Proof/report format

Return:

```text
CHANGED:
PROVED:
FAILED_AND_REPAIRED:
SKIPPED:
BLOCKED_JUDGMENT_GAP: <none or exact unresolved decision>

TRACEABILITY:
UX-T01: <state + evidence>
...
UX-T30: <state + evidence>

ARTIFACTS:
BRANCH:
PR:
HEAD:
GIT_STATUS:
MERGED:
LIVE_DELETION_STATE:
NEXT:
```

Evidence before confidence.
