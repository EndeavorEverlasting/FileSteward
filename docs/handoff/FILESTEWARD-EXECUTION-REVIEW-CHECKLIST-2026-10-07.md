# FileSteward execution review checklist — P04 + P82 — 2026-10-07

Use this checklist as the transition gate sheet for the current dependency-aware sprint.

**Authority:** `harness/evals/execution-handoff-review-gates.v1.json`  
**Closed judgment:** `harness/contracts/dependency-aware-judgment-closure.v1.json`  
**Rule:** a failed box routes to the named repair owner. It does not stop independent lanes or invite a new architecture decision.

## RG0 — current truth — before partition

- [ ] Fetch/prune provider refs and tags.
- [ ] Record exact `origin/main`, PR #33 head, PR #29 head, and local HEAD/status.
- [ ] Read current AGENTS + active plan + judgment closure + handoff packet.
- [ ] Run `entire status --json` and `entire agent-help --json` when Entire is available.
- [ ] Treat every `*_at_capture` SHA as continuity evidence only.
- [ ] Confirm current unresolved review threads for PR #33.
- [ ] If any required authority artifact is unreadable: stop that transition and report exact missing artifact.

**PASS -> RG1 / Wave 1 dispatch.**

## RG1 — ownership collision — before Wave 1 dispatch

- [ ] J0 owns the PR #33 foundation branch only.
- [ ] J1 owns ignored runtime evidence; no tracked mutation unless a diagnostic defect is proven.
- [ ] J2 worktree/branch: `feature/windows-app-attribution-20261007`.
- [ ] J2 writes only `src/filesteward/ownership/windows_app.py`, `tests/test_ownership_windows_app.py`, and private `_windows_*` helpers.
- [ ] J3 worktree/branch: `feature/repository-attribution-20261007`.
- [ ] J3 writes only `src/filesteward/ownership/repository.py`, `tests/test_ownership_repository.py`, and private `_git_*` helpers.
- [ ] No J2/J3 visualization or deletion files.
- [ ] No two ready lanes own the same tracked file.

**PASS -> dispatch J0/J1/J2/J3 concurrently where local adapters allow.**

## RG2 — lane scope — before each lane mutates

- [ ] Lane reads its owned/forbidden surfaces from the judgment closure.
- [ ] Lane acceptance condition is explicit.
- [ ] Lane proof ceiling is explicit.
- [ ] No product/architecture choice remains for the lane.
- [ ] If a genuinely new product judgment appears, emit `BLOCKED_JUDGMENT_GAP`; do not improvise.
- [ ] Existing operator value/authorization boundary is not broadened.

## RG3 — focused proof — before lane review

### J0
- [ ] Run focused Package Cache/regenerable deletion tests.
- [ ] Prove Package Cache is absent from generic allowlist.
- [ ] Prove Package Cache cannot use size+mtime identity shortcut.
- [ ] Prove execute admission refuses Package Cache.
- [ ] Do not weaken the negative regression.

### J1
- [ ] Run read-only Wispr diagnostic first.
- [ ] Preserve `diagnostic.json` + Squirrel log evidence under ignored `var/runs/**`.
- [ ] Classify the failure before repair.
- [ ] If repair mutation is required, verify that the exact action is covered by operator authority before mutation.
- [ ] Verify launch + registration consistency after repair.

### J2
- [ ] Registry/service/task/process/package probes are read-only.
- [ ] `Win32_Product` is not used.
- [ ] Synthetic tests distinguish runtime/serviceability/cache/orphan evidence.
- [ ] Evidence normalizes into ownership edges rather than direct deletion recommendations.

### J3
- [ ] Reuse `ProtectionIndex.from_git_discovery`.
- [ ] Test dirty/staged/untracked/unique work.
- [ ] Test clean reproducible clone.
- [ ] Test local-only/ahead/unpushed work.
- [ ] Entire evidence only enriches activity/relationship evidence.
- [ ] Age or Entire absence alone never creates legacy/reclaim.

## RG4 — cross-lane contract — before J4/J5/J6 convergence

- [ ] J2/J3 interfaces are integrated, not duplicated.
- [ ] J4 uses `graph.py` + `reducer.py` as the shared convergence owner.
- [ ] Multi-owner state uses **most-protective-edge-wins**.
- [ ] Unknown/conflicting/shared ownership fails away from automatic reclaim.
- [ ] Any producer contract change invalidates affected downstream proof.

## RG5 — provider review — before PR merge-candidate status

- [ ] Refresh exact PR head after final material commit.
- [ ] Enumerate all review threads.
- [ ] Every material finding is repaired or disproven against the exact head.
- [ ] Zero unresolved material threads.
- [ ] Do not use green tests to override an unresolved material review.

## RG6 — local full proof — before merge

- [ ] Run repository-required local full suite/validators on exact candidate head.
- [ ] Run Git/diff hygiene.
- [ ] Record exact head in proof receipt.
- [ ] Provider green alone is not sufficient.
- [ ] For PR #33: merge only after RG3 + RG5 + RG6 pass.
- [ ] After PR #33 merge, refresh main before J2/J3 provider integration.

## RG7 — PR #29 lineage — before J6 visual mutation

- [ ] J4 is integrated into refreshed main.
- [ ] Create `integration/j6-pr29-lineage-20261007` from that refreshed main.
- [ ] Use PR #29 head `c093f2cb69d69be153fcf983b6ad785636825b7e` only as the lineage donor unless provider truth changed.
- [ ] **Do not merge PR #29 wholesale.**
- [ ] Port only the allowlist in `dependency-aware-judgment-closure.v1.json`.
- [ ] Do not port PR #29 `AGENTS.md`, deletion modules, storage/execution contracts, current dependency plan, or housekeeping/system-stewardship work.
- [ ] For `src/filesteward/cli.py`, port only the review/Decision-Chamber command/routing needed by the accepted UX; preserve current scan/delete/ownership safety.
- [ ] For `pyproject.toml`, keep refreshed-main baseline and add only required UX dependencies/entrypoints.
- [ ] Recompute product version through repository versioning gate; do not copy PR #29's historical version blindly.
- [ ] Current P94/P110 + judgment-scene/storage contracts outrank PR #29 implementation details.

## RG8 — live UX acceptance — before J6 PROVEN

- [ ] Desktop live journey.
- [ ] Narrow viewport live journey.
- [ ] Reduced-motion behavior.
- [ ] Forced-colors behavior.
- [ ] Pointer path.
- [ ] Keyboard path.
- [ ] Touch/phone path when product-declared supported.
- [ ] Search/filter/selection survive unrelated scene transitions.
- [ ] No dead click.
- [ ] No generic EXPLORE fallback.
- [ ] No second router/mobile state machine.
- [ ] Memory Atlas visual world remains recognizable and task-effective.
- [ ] Static HTML/string checks are supplemental only.

## RG9 — live mutation authority — before repair/delete

- [ ] Exact semantic action identified.
- [ ] Exact target/manifest identified.
- [ ] Dependency graph evidence current.
- [ ] Existing operator authority covers the exact action; otherwise obtain only that missing gate.
- [ ] No broad cleanup, registry purge, user-data deletion, or security-disable side effect.

## RG10 — post-action verification — before terminal success

- [ ] Receipt exists.
- [ ] Receipt scope matches authorization.
- [ ] Capacity impact measured where applicable.
- [ ] Application/system health verified after mutation.
- [ ] Any regression routes to INCIDENT_RECOVERY.
- [ ] Classifications/queues refresh after action.
- [ ] Next continuation is explicit.

## Sprint close

The sprint may report terminal success only when J5 + J6 are integrated, J7's negative/positive corpus and required live proofs pass, and the relevant runtime effects are verified.

The following are **not terminal**:

- plan written;
- handoff written;
- local branch green;
- PR open;
- PR mergeable;
- one lane blocked while others are runnable.
