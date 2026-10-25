---
name: local-asset-lifecycle
description: Invoke when an agent classifies local paths not clearly belonging to an app, Git repository, or recognized curriculum, or assesses active/stable/dormant/legacy/removal-review status.
---

# Local asset assessment

## Trigger and boundary

Trigger on: local path, unclassified, miscellaneous data, active,
dormant, legacy, archive candidate, deletion target, removal review
in the context of FileSteward storage decisions.

This skill routes to deterministic product code. It is not a replacement
for the native adapters, ownership graph, or deletion authorization.

Read first:

1. AGENTS.md and docs/agent/LOCAL-AGENT-PROTECTIONS.md.
2. harness/contracts/storage-ownership-evidence-graph.v1.json.
3. harness/contracts/storage-dependency-judgment.v1.json.
4. harness/contracts/local-asset-lifecycle.v1.json.
5. docs/program/local-asset-lifecycle.md.
6. src/filesteward/ownership/local.py and tests/test_local_asset_lifecycle.py.
7. docs/handoff/LOCAL-ASSET-LIFECYCLE-2026-10-24.md (live successor).

## Deterministic workflow

1. Reconfirm admitted root, privacy mode, host and fresh scan/adapter boundary.
   Without real-host permission, work with synthetic data only.
2. Gather scoped owner/dependency/curriculum/Git/registry evidence via
   existing read-only providers. Preserve incomplete domains and unknowns.
3. Never manufacture adapters_complete, active-use negatives, recovery
   proof or operator preference. Inactivity dates alone are not technical
   proof that active_use=false.
4. Put JSON evidence in the ignored local runtime. View sample input:

       python -m filesteward.ownership.local --example

   Run deterministic evaluator:

       python -m filesteward.ownership.local --evidence-file <private-json-path>

5. Consume route and missing_evidence from JSON output: safe technical
   remediation can continue automatically, user intent requires user
   declaration, and no unknown becomes deletion permission.
6. Persist sanitized synthetic tests and contract updates in the repo, and
   private asset evidence only in ignored runtime. Integrate into the
   canonical Decision Chamber only through its existing scene contract.
7. Before actual mutation use repository-owned exact-manifest approval,
   preflight, execute and receipt path; this skill does not bypass any step.

## Evidence return contract

Report identity, attribution, lifecycle, disposition, route,
missing_evidence, revision, provider/host, authorization state, and proof
ceiling. Report LIVE_UNPROVEN unless the actual bounded interaction and
readback are observed. A tracked handoff is not deployment proof.
