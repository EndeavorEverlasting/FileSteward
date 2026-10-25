# LIVE HANDOFF — Local Asset Lifecycle Classification (2026-10-24)

This tracked handoff and its .handoff.json companion are canonical execution
state, not a chat-only plan. Parent objective: classify ordinary local assets,
including active, stable, dormant, legacy and removal-review cases. Never
turn absence of an application, Git checkout or curriculum into disposal proof.

## LAUNCH ORDER

1. RECOVER: FileSteward main was c3abf4984474b16a957f4148cf835880bfd7f93a
   at capture; isolated branch feat/local-asset-lifecycle-20261024. PR #71 is
   the separately owned learning discovery branch; PR #64 has overlapping
   agent/orchestration scope. Refresh both before combining work.
2. P97: inspected source and tests in tfeldmann/organize main tree
   a736516555d0daeb83a604448fbdf5379f42f2ef and qarmin/czkawka master
   tree eb8b91dbb4d25dff416202674ee0de84ee4b5e5c. ADAPT distinct
   selection/simulation/action stages and exclusion/reference targets. REJECT
   duplicate- or timestamp-only deletion, and unsafe arbitrary actions.
3. P07: code/fixtures/contract committed to feature branch:
   src/filesteward/ownership/local.py,
   tests/test_local_asset_lifecycle.py,
   harness/contracts/local-asset-lifecycle.v1.json,
   .agents/skills/local-asset-lifecycle/SKILL.md, AGENTS.md.
   Output is read-only identity, lifecycle, disposition, review route and
   missing evidence. No file content read, delete, move or approval.
4. P08: validate focused synthetic tests (Linux + Windows), inspect each
   failure/skip, then test bounded actual-host UX via canonical source CMD
   and current queue only after the local adapter/projection integration.
5. P04: partition dependent successors into (A) safe user-local attribution
   and recoverability evidence adapters, (B) canonical scan/ownership graph
   and Decision Chamber projection, (C) bounded Windows P08 runtime proof.
   No duplicate implementation in prompts or standalone UI.
6. CONVERGE: refresh exact provider/main/PR heads, checks and unresolved
   reviews. Verify affected tests and integrate only when gates satisfy repo
   policy, then independently observe local runtime.

## First next executable gate

    python -m pip install -e . pytest
    python -m pytest -q tests/test_local_asset_lifecycle.py tests/test_ownership_reducer.py tests/test_disposition.py
    python -m json.tool harness/contracts/local-asset-lifecycle.v1.json
    python -m json.tool docs/handoff/LOCAL-ASSET-LIFECYCLE-2026-10-24.handoff.json

Agent or operator can inspect the synthetic input with:

    python -m filesteward.ownership.local --example

Run a private adapter-authored evidence record using:

    python -m filesteward.ownership.local --evidence-file <private-runtime-json>

Never assert adapters_complete, active_use=False, unique_unbacked_work=False,
dependencies_resolved=True, recoverable=True from lack of observed evidence.
Actual provenance and operator intent must be recorded separately. Identity
GENERATED is not regeneration proof. An operator removal preference is
REVIEW_REMOVAL, not RECLAIM_PROVEN or a manifest authority.

## Runtime placement and proof

- CURRENT_CHAT_RUNTIME + GitHub provider: code, contracts, public/synthetic
  test artifacts, handoff commits and PR review; never local Windows files.
- CI_OR_REMOTE_RUNNER + GitHub: independent synthetic Windows/Linux proof.
  Green CI does not prove that an operator workstation was observed.
- LOCAL_AGENT_RUNTIME on an admitted Windows host: safe adapter collection
  only within operator-authorized exact roots; keep all paths/receipts private
  in ignored var/runs. Native host launcher, correct browser/queue projection,
  user input, active/dependency protection, and evidence readback are required
  for P08 LIVE_OBSERVED. No new visual design and no deletion here.

## Parent outcome still open

The module supplies a real deterministic classification/evaluation seam, but
normal FileSteward inventory, runtime adapters and Decision Chamber do not
automatically consume its output yet. Those are follow-on owned implementation
gates, not permission to mark the product complete or a reason to ask the user
to paste this handoff. This tracked handoff and its machine companion are what
the next agent should recover automatically.

Read: AGENTS.md; docs/agent/LOCAL-AGENT-PROTECTIONS.md;
harness/contracts/storage-ownership-evidence-graph.v1.json;
harness/contracts/storage-dependency-judgment.v1.json;
harness/contracts/local-asset-lifecycle.v1.json;
harness/contracts/execution-handoff-loop.v1.json;
docs/program/local-asset-lifecycle.md; companion .handoff.json.
