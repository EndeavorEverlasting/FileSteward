# Cross-repository canonical artifact placement — FileSteward execution slice

Parent outcome: local agents on DTop and PTop must reliably discover upstream-source catalogs, Prompt Kit contracts, and project-specific canonical artifacts without inventing Windows paths or requiring Google Drive connectors in a coding harness. Source authority stays with original Drive/Git owner. FileSteward determines placement and validates local evidence only.

## Ownership and scope
- Owner: FileSteward path/ownership classification. No alternate content authority, no new Prompt Kit alias identity.
- Owned: `src/filesteward/placement.py`, `harness/contracts/canonical-artifact-placement.v1.json`, relevant tests, agent discovery instructions.
- Forbidden: data movement, deletion, root migration, installation, UI changes, private manifests/receipts in Git, OAuth/token inspections, TokenCorridor and ParallaxPort code, user-authenticated provider actions.
- Source dependencies: TokenCorridor PR #233 (design routing), ParallaxPort PR #21 (consumer references), TokenCorridor PR #220 (Google Drive live cert), Drive Upstream Intelligence Library. These are references; none is presumed merged or locally installed.

## Acceptance sequence
1. Contract has one owner per repo artifact; shared offline export is labeled replaceable, not canonical master.
2. Locator prints redacted proposal with NO automatic filesystem write; optional explicit read-only host probe checks only exact paths, Git root + origin, source sidecar SHA.
3. Test absent dev root, dirty/foreign repo preservation, symlinked dev root, wrong snapshot bytes/source, DTop vs PTop and cross-host identity isolation.
4. Execute tests on exact FileSteward PR branch, compare existing `docs/agent/CANONICAL-PATHS.md`/ownership graph and protect current runtime/visualization/cleanup gates.
5. If mergeable and all required checks/reviews are green, merge under established FileSteward P00 governance. Then verify default-branch containment. A green PR is not merge.
6. Local DTop and PTop agents run the probe on their own hosts, saving separate ignored receipts. Compare current Git refs, inspect local placement, and only then design a bounded, no-overwrite import from the 97-source Drive registry if the snapshot is absent.
7. Validate TokenCorridor's `TC_DESIGN_UPSTREAM_REGISTRY` explicitly against a provenance-verified local file; no auto exports or environment variable injection by FileSteward.

## Proof ceiling / handoff
Cloud GitHub writes, local synthetic code validation, host observation, snapshot provisioning, verified source freshness, and agent consumption are separate. Do not claim real local paths, authorization, or currently installed providers from provider-side repo inspection alone. Next unproven gate = execute host evidence probe on DTop and PTop independently.