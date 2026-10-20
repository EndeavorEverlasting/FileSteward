# FileSteward Hourly Steward — canonical P141/P82/P04 design and local test packet

Status: **repository-committed design + read-only coordinator source, NOT registered on a real Windows host; no agent launched; no files moved or deleted.**

Parent intent (2026-10-20): a persistent local FileSteward steward that periodically reviews files and FileSteward's own unresolved work, classifies app experience, memorabilia, activity and dormancy using codified evidence, dispatches narrowly scoped specialists through registered adapters, and continuously improves the rules without asking a fresh agent to reinvent policy. The high-frequency mechanical job must cost **zero model tokens**; actual local/remote agents run only on distinct, authorized outstanding work, with explicit privacy and budget gates.

## 1. Canonical authority and no ambiguity

- Repository owner: `EndeavorEverlasting/FileSteward`. TokenCorridor owns external agent harness/dispatch adaptation and canonical P-number resolution, **not** FileSteward's content value or deletion policy.
- Read before any mutation: `AGENTS.md`, `docs/agent/LOCAL-AGENT-PROTECTIONS.md`, `docs/agent/CANONICAL-PATHS.md`, `docs/agent/OPERATOR-DELETE-PATH.md`, `harness/contracts/storage-dependency-judgment.v1.json`, `harness/contracts/storage-ownership-evidence-graph.v1.json`, `harness/contracts/judgment-scene-workflow.v1.json`.
- New authoritative product contracts: `harness/contracts/steward-program.v1.json` (facet semantics, rules, limits, default refusal), `harness/contracts/steward-routing.v1.json` (typed lane registry, permissions, status states, prerequisites), `harness/contracts/steward-adapter-map.v1.json` (ticket-to-executable-lane mapping), and `harness/contracts/steward-worker-protocol.v1.json` (exact claim/lease/receipt API; worker implementation gate).
- Canonical executable current source: `src/filesteward/steward/__init__.py` + `__main__.py`. Windows Task Scheduler wrapper: `scripts/windows/steward-hourly.ps1`. Synthetic regression oracle: `tests/test_steward_cycle.py`.
- Current legacy sibling: PR #59 schedules read-only Downloads review but is not accepted as a live installed task. Never install two hourly scanners against the same root; new scheduler refuses when its legacy task name exists. PR #59 may still have unresolved review findings; refresh GitHub and do not co-merge colliding code blindly.
- Private metadata, paths, hashes, model tickets and approvals belong in ignored canonical `var/` runtime. No local filesystem scanned from GitHub/this chat. Operator consent remains required for content inspection or new mutation authority.

## 2. P141 — strategic decision locked

Three materially different architectural theses were considered against the observed repository floor:

| Thesis | Evidence/falsifier | Disposition |
| --- | --- | --- |
| **A. Hourly age/extension-based cleanup** | Easy and cheap but FileSteward's incident protections show old installers can remain application serviceability assets and mtime is not user-value evidence | REJECT |
| **B. Periodic deterministic evidence reduction + typed specialist work tickets + independently gated actions** | Existing scan/ownership/disposition/approval code provides the substrate; reduces repeated manual triage. Reject if synthetic traces cannot preserve safety, recoverability and zero default agent spend | **SELECTED** |
| **C. Invoke an LLM to re-analyze all Downloads every hour** | Duplicates expensive interpretation, incurs recurring tokens/privacy exposure, does not create operator deletion authority | REJECT |

The operator has already selected the strategic target. This record documents the decision, **not** a claim that P141 itself authorizes execution or that a generic agent may pick a new thesis.

## 3. Exact facet interpretation (no local judgment left to agent)

| Facet | Machine can conclude from evidence | Machine must NOT conclude |
| --- | --- | --- |
| App experience / serviceability | Windows app registration, uninstall/repair/update paths, running executable/module, tasks, services, package identity, repo/toolchain/shared references; most-protective edge wins | AppData is junk; missing uninstaller means orphan; no process now means unused |
| Memorabilia / personal value | Explicit operator-authored keeps; media/creative format is only **POTENTIAL_MEMORABILIA** for review | AI can reliably determine emotional meaning, or age means disposable |
| Activity / recent use | Last modified (change only), current proven open references, Git working trees/Entire context, bounded multi-snapshot history | mtime is actual last access; absence of observed use establishes dormancy |
| Archived/dormant intent | Explicit operator archive choice; evidence-proven active dependency; otherwise dormant candidate *for review only* | Dormant means delete; clean remote clone means disposable |
| Duplicate/installer/record kind | Deterministic extension/file-kind navigation hints; exact hashes can nominate **review** under contract | Same name/version/extension or hash automatically authorizes removal |
| Recovery / uniqueness | Proven current backup source, synced copy, active repo remote and exact restore means can be recovered *conditionally* | Backup is current from cloud icon; file exists elsewhere without identity proof |

Each facet returns a finite enum in `steward-program.v1.json`. Disposition (PROTECTED, HUMAN_REVIEW, UNKNOWN, KEEP_PROVEN, RECLAIM_PROVEN) remains a **separate safety floor** from authorization (UNAPPROVED/APPROVED/APPLIED/VERIFIED). Agent suggestions are advisory, never an approval artifact.

## 4. Job architecture and transaction boundaries

```text
Task Scheduler, hourly (disabled until operator registers)
  -> current-user KnownFolder Downloads + canonical FileSteward checkout
  -> existing filesteward.cli scan [READ ONLY]
  -> existing filesteward.cli validate [READ ONLY]
  -> python -m filesteward.steward --scan-run <validated run>
       -> current safety floors + typed facet reducer
       -> classified.jsonl + unresolved.jsonl + coverage.json
       -> work-items.jsonl (BLOCKED_ADAPTER unless separately configured)
       -> cycle.json (source_mutations=0, agent_executions=0)
  -> FUTURE: registered TokenCorridor/local agent adapter consumes typed work
       -> current evidence check, scoped claim, bounded execution receipt
       -> independent revalidation and evidence convergence
  -> FUTURE: Decision Chamber prompts for actual operator value/mutation authority
  -> SEPARATE existing exact-manifest deletion/restore path, never a cron shortcut
```

This cycle *issues* work into a private outbox; the baseline does not launch workers. That is an intentional, observable adapter boundary, not an assertion that multi-agent execution is completed. The live executable proves the deterministic mechanical half now. Broader agent harness integration is a separate bounded capability lane with exact contract below.

**Persisted outputs:** `var/runs/steward-hourly-*/` for validated inventory; `var/steward/cycles/<run-id>-<nonce>/` for classified, unresolved, work orders, coverage, cycle. Treat all as private, excluded from Git, never copy into PR text.

**Dedup/state:** work ticket key SHA256(policy_version|scan_run|item_id|lane), limited 250 classification rows and 40 tickets per cycle; 3 proposals per file; excess is `INCOMPLETE_BUDGET`, never `DONE`. Agent adapter must maintain durable dedupe *across* scan IDs, claim leases, aging, retries (at most 3), and terminal closure receipt; that cross-cycle component is **NOT IMPLEMENTED** and must be completed before a live agent worker can claim anything.

## 5. P04 — fixed execution graph and owners

| Gate | Owner and mutation scope | Must prove / failure route | Dependency |
| --- | --- | --- | --- |
| G0: focused tests | FileSteward integration, current branch only. Source and `tests/test_steward_cycle.py` | Python compile, 12 tests, CLI/scan/ownership regression. Defect -> repair, no test weakening | None |
| G1: Windows native scheduler proof | Local Windows host only, `scripts/windows/steward-hourly.ps1` | Preview, RunOnce, status, register/disable/unregister ownership semantics, two hourly cycle receipts. Block on canonical path/missing Python/reparse/legacy task | G0 |
| G2: adapter evidence normalization | `filesteward.ownership` and `steward` typed evidence consumer | Implement complete/partial adapter coverage, expiry, authoritative provenance, multiowner graph revision, activity truth vs mtime. Missing -> UNKNOWN | G0, independent of G1 |
| G3: agent dispatch bridge | TokenCorridor owns host harness adapter; FileSteward owns outbox/receipt contract | Resolve actual available native/OpenCode/Cursor/approved provider adapters; prove launch+return claim with no private payload leakage and exact ticket receipts. No adapter -> BLOCKED_ADAPTER, don't fake dispatch | G2 |
| G4: coverage/unknown taxonomy | FileSteward classification rules + Decision Chamber owner | Produce counts of unresolved facets and stable error families across 2 cycles; route policy gaps to proposal + synthetic fixture, never self-modify contract | G2 |
| G5: separate approved action | FileSteward operator exact-manifest lifecycle, not scheduler | Only after actual approval and fresh dependency/preflight/handle-bound mutation receipt/restore; no standing approval invented | G3+G4+actual operator gate |

**Parallel graph width:** after G0, G1 and G2 can run independently (Windows physical host vs FileSteward Python/adapter code). Do not claim they actually ran parallel unless two workers started and independent receipts exist. Current remote runtime cannot drive the operator's Windows Task Scheduler; that lane remains an explicit host proof blocker.

**First local commands** (must resolve actual checkout/branch before running; do not overwrite dirty/unpushed work):

```powershell
$repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
git -C $repo status --short --branch
git -C $repo fetch origin
git -C $repo worktree list --porcelain
python -m pytest -q tests/test_steward_cycle.py tests/test_scan.py tests/test_disposition.py tests/test_ownership_reducer.py
.\scripts\windows\steward-hourly.ps1 -Action Preview
.\scripts\windows\steward-hourly.ps1 -Action RunOnce
.\scripts\windows\steward-hourly.ps1 -Action Status
```

Only after parser/tests/preview proof and verifying no conflicting scheduled task: `-Action Register -Authorize`. `-Action Disable -Authorize` and `-Action Unregister -Authorize` are required controls. The user has asked to **design and commit**, not to claim host registration happened.

## 6. P82 experiment admission and run criteria

Selected thesis: deterministic hourly evidence coordination is superior to periodic free-form reclassification.

Hypothesis: Given identical synthetic inventories and typed evidence, the steward emits reproducible facet states and bounded unresolved tickets **with no safety-downgrade, no source mutation, no model invocation**, whereas raw inventory alone does not classify those facets or surface next work.

Comparator: current `filesteward.cli scan/validate` produces inventory/plan; prototype additionally produces facet/unknown/ticket artifacts. Falsifiers: any old document/memorabilia/application changes to a new reclaim/approved state, wrong last-access claim, inconsistent rerun tickets, missing unknown item, privacy escape, queue without receipts treated completed, scheduler overlap/foreign task overwritten.

Synthetic cases `tests/test_steward_cycle.py`: S01 old photo (potential memorabilia), S02 operator keep, S03 active app, S04 broken app, S05 old mtime not access, S06 live Git reference, S07 observed no-reference still dormant review, S08 operator-only archive, S09 reparse -> unknown, S10 upstream protected stays protected, S11 budget incomplete, S12 invalid and duplicate inputs refused.

Measurement: 12 scenario pass count; protected-downgrade violations 0; default agent calls 0; source mutations 0; max 250 observed records/40 work tickets; unresolved counts match entries; two real Windows hourly cycles; proof that incomplete budget stays incomplete.

Decision: PROMOTE only if semantic and safety fixtures, scheduler native proof, host privacy and adapter acknowledgment pass. WEAKEN if zero-token/UX improvement disproven. REJECT if unsafe classification or agent self-approval. INCONCLUSIVE if host tests unavailable; do not silently promote.

## 7. Remnant taxonomy — next rules must follow evidence

`coverage.json` counts unresolved facets. `unresolved.jsonl` retains exact item IDs and missing facet states for a local review scene. The next specialist must aggregate by **why evidence is absent** (adapter offline, scan gap, unknown owner, sentimental choice, missing access-history capability, conflicting owners, archival preference, unmatched file kind, incomplete source) rather than asking an LLM to assign a deletion confidence.

For each recurring unknown pattern: assign canonical evidence source, minimal read-only probe, confidence/coverage *of observation*, deterministic state/reason, synthetic regression test, and only then an optional policy extension PR. If a pattern needs personal value, route `NEEDS_OPERATOR_VALUE`. If it needs live process/host evidence, route the host adapter. If it needs filesystem mutation, route the existing approval path. **No generic “JUNK” output and no automatic promotion from UNKNOWN/HUMAN_REVIEW.**

## 8. Explicit gaps: do not conceal these as agent success

- Full application/usage evidence adapters are **not invoked** by first read-only cycle; supplemental evidence is accepted as context, not new authorization.
- No TokenCorridor agent launch or claim/complete adapter has been installed. Work orders remain `BLOCKED_ADAPTER`; agent launch costs are not included in default hourly job.
- Memorabilia is a user value judgment. The system can reliably identify questions to ask, not decide emotional worth.
- No opt-in to inspect file contents, external upload, or unattended deletion was granted by this job-design request.
- Actual Windows Task Scheduler preview/registration, two-hour observation, exact runtime lifecycle and recoverability are **not** proved by a remote GitHub commit.
- Installed executable v0.16.0 does not inherit these source-only features until rebuilt, versioned, tested and shipped.

**Terminal parent proof:** not “PR open,” not “scheduler registered,” and not “100% classified by guess.” Parent closeout requires a native repeated scheduled run, source-safe evidence coverage, working typed agent claim/receipt loop, visible unresolved taxonomy, and any separately authorized cleanup behavior actually observed with receipts.
