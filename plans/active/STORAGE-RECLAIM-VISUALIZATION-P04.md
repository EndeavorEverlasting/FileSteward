# FileSteward Modern Storage Experience — P04 Factoring Plan

**Status:** ACTIVE / FACTORED / IMPLEMENTATION-READY AFTER P04 MERGE  
**Repository:** `EndeavorEverlasting/FileSteward`  
**Planning base:** `main@b2b312bca0076fc9459b6355eb659a24d037e2a2`  
**Plan branch:** `plan/storage-visualization-p04-20261002`  
**Upstream design floor:** P97 + P95 visualization design integrated via PR #6  
**Execution host for implementation:** operator workstation / LOCAL_AGENT_RUNTIME  
**Proof ceiling of this plan:** durable factoring, ownership, design-system contract, and execution manifest only. No real receipt rendering, contract declaration, apply, quarantine, deletion, or verified reclaim in this P04 lane.

## 1. Mission

Turn the integrated visualization concept into a modern, polished FileSteward product experience without inheriting WinDirStat's visual age.

We are deliberately carrying forward **structural ideas** proven by WinDirStat/SpaceSniffer-class tools:

- tree/list + treemap coordination;
- largest-first visual prioritization;
- zoom/drill-down;
- filtering;
- details on demand;
- stable synchronized selection.

We are deliberately **not** carrying forward their visual language.

FileSteward should feel like a current Windows productivity application: calm, precise, high-information, responsive, accessible, and visually polished while remaining deterministic and robust.

## 2. Product experience contract

### 2.1 Structural layout

Primary desktop composition:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ FileSteward  /  breadcrumb  / search-filter-controls  / run status       │
├───────────────────────┬────────────────────────────────┬───────────────────┤
│ Storage navigator     │ Storage map                    │ Decision inspector│
│                       │                                │                   │
│ largest groups        │ modern treemap                 │ evidence state    │
│ sortable exact data   │ linked selection              │ gate trace        │
│ filter chips          │ zoom/drilldown                 │ next valid action │
│                       │                                │ risk/explanation  │
├───────────────────────┴────────────────────────────────┴───────────────────┤
│ baseline free / projected reclaim / target / authorization state          │
└────────────────────────────────────────────────────────────────────────────┘
```

Medium widths collapse the decision inspector below the main workspace rather than clipping it. Narrow widths use sequential panes.

### 2.2 Visual language — FileSteward Modern

The visual system is **new**, not a reskin of WinDirStat.

- system-native typography: `Segoe UI Variable`, `Segoe UI`, system sans fallback;
- 8px spacing grid with compact high-information density;
- flat layered surfaces, subtle borders, restrained elevation;
- no bevels, faux-3D cushions, Win9x chrome, or dense multicolor extension-rainbow as the primary language;
- 10–14px corner radii for cards/panels where useful; treemap geometry itself remains crisp;
- dark/light mode from system preference, with high-contrast-safe semantic tokens;
- one accent family for interaction, semantic colors only for evidence state;
- state is always text/icon + color, never color alone;
- large numbers and progress metrics use tabular numerals;
- hover, focus, selected, disabled, and blocked states are deterministic and keyboard-visible;
- animations, if any, are short and nonessential; reduced-motion preference disables them;
- no blur/glass dependency for correctness.

### 2.3 Information hierarchy

1. **Where is the space?** — treemap + largest-first list.
2. **What exactly is selected?** — exact path/group, bytes, item count.
3. **What evidence exists?** — disposition, scan completeness, protection, projection quality.
4. **What decision is required?** — first unproven gate.
5. **What happens if approved?** — proposed action and projected outcome, never implicit execution.

### 2.4 Safety/authority invariants

- visualization never creates a contract;
- hint tags never create reclaim authority;
- size/age/path/type never promote `HUMAN_REVIEW`;
- protection precedence is preserved;
- missing persisted evidence renders `UNKNOWN / NOT PERSISTED`;
- `RECLAIM_PROVEN` is still `UNAPPROVED` until a separate exact approval artifact exists;
- initial product visualization contains no apply/delete control;
- receipt-derived strings are rendered literally, never as executable markup;
- real paths/receipts remain ignored local runtime data.

## 3. Runtime and provider partition

### LOCAL_AGENT_RUNTIME — implementation owner

Owns:

- repository source changes;
- local deterministic tests/validators;
- generated synthetic reports;
- browser/manual smoke;
- real receipt rendering only when that phase is reached and authorized by the existing privacy/runtime contract;
- Entire CLI continuity on the operator host.

Orientation begins with:

```powershell
entire status --json
```

when Entire is available.

Repository-owned local tests/validators are the semantic proof floor. **GitHub Actions are not required and must not be created merely to manufacture provider-green status.**

### Entire CLI — continuity/mirror layer

Use for Git-native agent/session continuity and configured mirror/clone transport. Entire evidence does not replace Git/content/test proof.

### GitHub — provider state only

Use GitHub for remote branch/PR/review/merge truth when hosted there. Provider bots may contribute review evidence. GitHub Actions, when present, are optional independent proof, not the canonical validator owner.

## 4. Dependency graph

```text
F0 Contract freeze
   ├── F1 Structured presentation/evidence model
   ├── F2 Modern visual system + report shell
   └── F3 Deterministic treemap/layout engine
            \        |        /
             \       |       /
               F4 Generator + CLI convergence
                         |
               F5 Accessibility/adversarial polish
                         |
               F6 Real receipt read-only proof
                         |
               F7 Contract-selection UX
                         |
               F8 Manifest-bound approval UX
                         |
               F9 Quarantine/apply + verification
                         |
              F10 Retention/permanent-delete policy
```

Graph width after F0 is **3**. F1/F2/F3 must use isolated worktrees/branches and must not write each other's owned files.

## 5. Lane contracts

### F0 — UI contract freeze

**Owner:** architecture/convergence agent  
**Dependencies:** P95/P97 integrated on main  
**Owned:** this plan, presentation-model contract, design tokens/interfaces only  
**Forbidden:** production F1/F2/F3/F4 implementation beyond seam prototypes, real receipt data
**Artifacts:**
- `docs/program/storage-reclaim-visual-system.md`
- `docs/program/storage-reclaim-visual-system.tokens.json`
- `docs/program/storage-reclaim-visual-system.interfaces.md`
- executable seams in `src/filesteward/visualization/` (`tokens`, `contracts`, `css`, `literal`, `selection`, `shell`)
- `tests/test_visualization_f0.py`
**Gate:** no unresolved contradiction between FileSteward disposition rules and UI state model; token→CSS, literal escape, selection sync, and shell call stacks pass locally.
**Status:** PROVEN (design + executable seams); production F2 `html.py` expansion remains F2.

### F1 — Structured presentation/evidence model

**Owner:** P07 implementation lane  
**Dependencies:** F0  
**Owned:** `src/filesteward/visualization/model.py`, schema/helper tests, only the minimal upstream artifact/schema changes required for structured persisted evidence  
**Forbidden:** HTML/CSS/treemap layout/CLI  
**Mission:** validated artifacts -> immutable presentation model; no prose parsing, no reclassification.  
**Must carry:** logical/allocated bytes, projected reclaim bytes, reclaim basis, projection quality, disposition, authorization, scan/protection, structured reason/evidence source, next gate.  
**Negative fixtures:** markup-like path text; missing gate detail; protected+incomplete; large/cache-looking no-contract item.

### F2 — FileSteward Modern visual system + report shell

**Owner:** P07 implementation lane  
**Dependencies:** F0  
**Owned:** `src/filesteward/visualization/html.py` shell/templates/styles and focused renderer tests  
**Forbidden:** evidence inference, treemap algorithm, CLI  
**Mission:** implement design tokens, desktop/medium/narrow composition, navigator + map container + decision inspector + metrics/footer.  
**Gates:** dark/light, keyboard focus, reduced motion, no external assets/network calls, literal text rendering, intermediate-width no clipping.

### F3 — deterministic treemap/layout engine

**Owner:** P07 implementation lane  
**Dependencies:** F0  
**Owned:** `src/filesteward/visualization/treemap.py` and focused geometry tests  
**Forbidden:** HTML shell, evidence judgment, CLI  
**Mission:** stable deterministic rectangles from normalized hierarchy/size input.  
**Gates:** deterministic same-input layout; no negative/overlapping geometry; stable identity; zero/unknown-size handling explicit; selection/zoom coordinates reproducible.

### F4 — generator + CLI convergence

**Owner:** convergence P07 lane  
**Dependencies:** F1 + F2 + F3  
**Owned:** `src/filesteward/cli.py`, visualization package integration, generated-report orchestration, integration tests  
**Mission:** `filesteward visualize <run-dir>` validates, builds model, lays out map, atomically publishes one offline HTML report.  
**Gates:** canonical runtime-tree proof; existing `scan/validate/plan/apply` behavior green; no source-file mutation; atomic output.

### F5 — accessibility, responsiveness, adversarial polish

**Owner:** review-hardening lane  
**Dependencies:** F4  
**Owned:** focused repairs/tests only  
**Mission:** treat the first functional UI as a prototype, not the finish line.  
**Gates:** keyboard-only complete selection workflow; focus visible; screen-reader labels; 100%-200% zoom; 1024px/intermediate width; literal hostile text; high-contrast semantics; first failing gate visually dominant; no state conveyed only by color.

### F6 — real Phase 5 receipt visualization

**Owner:** LOCAL_AGENT_RUNTIME  
**Dependencies:** F5  
**Private input:** existing ignored Phase 5 receipt under canonical `var/runs/`  
**Owned output:** ignored local HTML/report only  
**Forbidden:** committing real paths/data, contracts, apply/quarantine/delete  
**Mission:** prove the real 961k-row-scale receipt can be rendered/usefully aggregated without leaking private data.  
**Gate:** operator can identify largest actionable decision buckets from the visual; performance and memory remain acceptable; no mutation.

### F7 — contract-selection UX

**Owner:** successor product lane  
**Dependencies:** F6  
**Mission:** let the operator mark exact prefixes as **draft contract decisions**, with clear scope, provenance, recoverability, and estimated impact.  
**Hard boundary:** a UI click is not a final contract until an explicit durable operator-authored contract artifact is produced and validated.

### F8 — manifest-bound approval UX

**Owner:** successor product lane  
**Dependencies:** contract-backed rescan + nonzero cleanup plan  
**Mission:** present exact `RECLAIM_PROVEN` rows, projection quality, cumulative outcome, run ID and manifest digest for explicit action approval.  
**Hard boundary:** approval is bound to exact rows/digest; stale evidence fails closed.

### F9 — quarantine/apply + verified reclaim

**Owner:** separately authorized mutation implementation  
**Dependencies:** F8 + apply contract implementation  
**Mission:** ordinary approved cleanup goes through quarantine, revalidation, receipt, and free-space verification.  
**Not part of F0-F6 implementation.**

### F10 — permanent deletion / retention lifecycle

**Owner:** future explicit product-policy lane  
**Dependencies:** proven quarantine/restore lifecycle and retention policy  
**Mission:** if permanent deletion is added, it is a second explicit lifecycle after reversible quarantine, with independent policy/approval/evidence.  
**Current repo contract:** permanent deletion remains outside the MVP.

## 6. Integration policy

A feature branch/PR is temporary.

When an exact head has:

- repository-owned required checks green;
- all material review findings resolved;
- dependencies satisfied;
- no conflicts/protection blockers;
- no explicit operator prohibition;
- merge authority available;

**merge it into refreshed `main` in the same execution and verify containment/content.**

Do not stop merely to ask, "Should I merge?"

GitHub Actions are not an implied gate when the repository has no workflow. Do not add Actions to substitute for local proof.

## 7. Design acceptance floor

The FileSteward visualization is not "done" merely because a treemap renders.

Minimum product acceptance:

- visual hierarchy feels current rather than legacy Windows;
- exact bytes and evidence remain auditable beside the visual;
- operator can move list -> map -> decision trace without losing selection context;
- filtering/zoom does not change evidence state;
- every actionable-looking state names its next gate;
- no ambiguous item is visually pressured toward deletion;
- accessibility and keyboard behavior are first-class;
- real-receipt scale is demonstrated before approval UX is built;
- visual output is deterministic enough for regression fixtures/screenshots.

## 8. Proof and contract horizon

| Contract | Owner | P04 state | Required next transition |
|---|---|---|---|
| Prior art / interaction model | P97 doc | PROVEN | consume, do not reopen |
| Program architecture | P95 doc | PROVEN | consume |
| Modern visual-system contract | `docs/program/storage-reclaim-visual-system.md` + tokens/interfaces | PROVEN (F0 seams) | F2 expands shell → html.py |
| Evidence presentation model | F1 | REQUIRED SUCCESSOR WORK | implement + fixtures |
| Treemap engine | F3 | REQUIRED SUCCESSOR WORK | deterministic implementation |
| Offline report generator | F4 | REQUIRED SUCCESSOR WORK | integrate F1/F2/F3 |
| Accessibility/polish | F5 | REQUIRED SUCCESSOR WORK | adversarial/browser proof |
| Real receipt visualization | F6 | REQUIRED SUCCESSOR WORK | local private proof |
| Contract selection | F7 | REQUIRED SUCCESSOR WORK | operator UX + durable contract |
| Approval UX | F8 | REQUIRED SUCCESSOR WORK | exact manifest-bound approval |
| Apply/quarantine | F9 | REQUIRED SUCCESSOR WORK | separately authorized mutation |
| Permanent deletion | F10 | REQUIRED SUCCESSOR WORK / outside current MVP | retention + second policy gate |

## 9. Next implementation command

F0 remains proven. PR #10 repairs the P100 incident against PR #9 (including follow-on artifact-overwrite, stale-selection, and locale-independent search findings) with focused + full local pytest observed green on the repair head. After PR #10 integrates, F5 accessibility/adversarial polish is the next implementation slice. F6 remains later and still requires its privacy/runtime gate.

Do not reopen P95/P97/F0–F4 visual-language or architecture decisions unless new evidence falsifies them.
