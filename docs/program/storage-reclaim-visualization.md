# Storage Reclaim Visualization — P95 Program Design & Call-Stack Prototype

**Status:** DESIGN PROVEN BY SYNTHETIC INTERACTION PROTOTYPE; production integration not started  
**Prior art:** `docs/program/storage-reclaim-visualization-prior-art.md`  
**Program owner:** `docs/program/storage-reclaim-path.md`

## 1. Outcome

Give an operator a visual, auditable path from **"where is the storage?"** to **"what decision can I safely make next?"**

The first production visualization should combine:

1. **treemap overview** — rectangle area = storage magnitude;
2. **sortable bucket/tree list** — exact counts/bytes and deterministic evidence;
3. **decision trace** — selected item's current FileSteward evidence/authorization state and the next valid gate.

No visualization element may itself grant mutation authority.

## 2. Invariants

- Size, age, filename, extension, color, location, or hint tags never imply disposability.
- `HUMAN_REVIEW`, `UNKNOWN`, and `PROTECTED` cannot be visually or logically promoted to reclaim.
- `RECLAIM_PROVEN` remains evidence only; authorization is separate.
- Real workstation paths remain ignored runtime data; tracked UI fixtures are synthetic/sanitized.
- The visualization is read-only in its first production slice.
- No direct delete button in the MVP.
- Ordinary future actions remain **approval -> quarantine -> verify** before any permanent-deletion feature is considered.

## 3. Candidate architectures

| Candidate | Shape | Strength | Weakness | Disposition |
|---|---|---|---|---|
| A. Self-contained HTML report | Python builds one local HTML file with inline CSS/JS from validated receipt artifacts | dependency-free, offline, privacy-preserving, portable, easy to iterate | browser shell rather than native Windows chrome | **SELECTED** |
| B. Native Python desktop | Tk/other desktop toolkit renders treemap and decision panel | native app feel | adds toolkit/platform behavior before interaction model is proven | DEFER |
| C. Local SPA + service | browser UI backed by local HTTP/API process | rich long-term interaction | server lifecycle, ports, security, packaging, more failure surfaces | REJECT for first slice |

### Selection

Start with **A**.

It fits FileSteward's current dependency-free Python package, can live entirely beneath the ignored run directory, and proves the interaction contract before committing to a native shell or local service.

## 4. Presentation model

The UI must consume a **presentation model**, not raw CSV rows directly.

Minimum node fields:

```text
node_id
parent_id
display_name
path
entry_type
logical_size_bytes
allocated_size_bytes
disposition
authorization_state
scan_completeness
protection_relation
reason
contract_summary
contract_hint_tags
risk_if_acted_on
next_gate
trace_evidence_source
```

The production builder derives these fields from already-validated FileSteward artifacts. It does not reclassify items.

**Critical evidence rule:** the viewer may only project a decision-trace fact from a structured persisted field or from an invariant logically guaranteed by the validated final disposition. It must not parse free-form `known_context`/prose to recover control facts, and it must not re-run classification to manufacture a prettier explanation of a historical receipt. If a desired trace fact is not structurally recoverable, render it as `UNKNOWN / NOT PERSISTED` and open a separate schema-evolution slice before claiming that fact.

## 5. Visual semantics

### Primary encoding

- **Area:** logical or allocated bytes, explicitly labeled.
- **Border/badge:** FileSteward disposition.
- **Text/icon:** authorization state / next gate.
- **Selection outline:** current operator focus.

Color is supportive, never the sole carrier of evidence state.

### Linked panes

```text
Bucket/tree list <-> Treemap <-> Decision trace
          \____________ selected node ____________/
```

Selecting in any pane updates the others. Selection changes presentation state only.

## 6. Decision trace

For a selected item/bucket, render the deterministic gate chain:

```text
1. Observation complete?
   NO  -> UNKNOWN -> stop
   YES -> continue

2. Protected relation?
   SELF/DESCENDANT -> PROTECTED -> stop
   ANCESTOR        -> HUMAN_REVIEW/decompose -> stop
   unrelated       -> continue

3. Explicit regenerable contract?
   NO  -> HUMAN_REVIEW -> operator may declare an exact contract
   YES -> continue

4. Provenance + recoverability documented?
   NO  -> HUMAN_REVIEW -> stop
   YES -> continue

5. Adversarial loss challenge defeated?
   NO  -> HUMAN_REVIEW -> stop
   YES -> RECLAIM_PROVEN

6. Exact operator approval bound to run/manifest/rows?
   NO  -> UNAPPROVED -> stop
   YES -> APPROVED_FOR_ACTION

7. Apply implementation/gates?
   Current MVP -> unavailable/refuse
   Future      -> quarantine, revalidate, verify reclaim
```

The UI should show the first failing/unproven gate prominently.

## 7. Call stacks

### Success stack — visual review

```text
filesteward visualize <run-dir>
 -> prove run dir beneath canonical runtime tree
 -> validate_run(run-dir)
 -> load validated inventory / review / plan / exclusions
 -> build presentation model without reclassification
 -> compute deterministic treemap layout
 -> atomically write self-contained HTML under run-dir
 -> operator opens local report
 -> select rectangle
 -> synchronized list selection
 -> decision trace renders current evidence + next gate
 -> no filesystem mutation
```

### Failure stack — invalid evidence

```text
filesteward visualize <run-dir>
 -> path proof fails OR validate_run reports inconsistency
 -> no presentation model
 -> no final HTML publication
 -> non-zero exit
 -> existing source artifacts untouched
```

### Failure stack — ambiguous selection

```text
select large HUMAN_REVIEW rectangle
 -> show size/hints
 -> decision trace reaches "no explicit contract"
 -> next gate = operator contract decision
 -> no reclaim nomination
 -> no approval
```

### Success stack — later contract-backed evidence

```text
select RECLAIM_PROVEN rectangle
 -> show evidence basis + projected reclaim
 -> authorization badge remains UNAPPROVED
 -> next gate = exact manifest/row approval
 -> no apply from visualization
```

## 8. Executable prototype

`docs/program/storage-reclaim-visualization-prototype.html` is a self-contained synthetic prototype.

It proves:

- three-pane composition;
- treemap/list linked selection;
- evidence-state filtering;
- decision-trace rendering;
- a HUMAN_REVIEW candidate that stops at the contract gate;
- PROTECTED and UNKNOWN stop states;
- RECLAIM_PROVEN remaining UNAPPROVED;
- zero destructive controls.

It uses **synthetic paths and sizes only** and does not read `var/`.

## 9. Production module boundary

A future P07 implementation should prefer the smallest repository-native seams:

```text
src/filesteward/visualization/model.py
    validated artifacts -> immutable presentation model

src/filesteward/visualization/treemap.py
    presentation model -> deterministic rectangles

src/filesteward/visualization/html.py
    model + rectangles -> atomic self-contained HTML

src/filesteward/cli.py
    visualize subcommand only; no judgment logic
```

Exact names may change if repository evidence reveals a better existing owner; the boundaries are the contract.

## 10. P07 acceptance gates

Production implementation is ready only when it proves:

1. `visualize` refuses targets outside the canonical runtime tree.
2. It calls the existing run validator before rendering.
3. It streams/handles large receipts without loading 961k rows unnecessarily where aggregation suffices.
4. Decision traces consume structured persisted evidence only; a negative fixture proves free-form prose is never parsed into authority/gate facts.
5. Missing historical gate detail renders `UNKNOWN / NOT PERSISTED` rather than being recomputed or guessed.
6. It publishes atomically; partial HTML is not left as success.
7. Treemap layout is deterministic for the same normalized model.
8. Linked selection maps to stable item/bucket identity.
9. No UI event changes disposition or authorization.
10. Synthetic fixtures cover HUMAN_REVIEW, UNKNOWN, PROTECTED, KEEP_PROVEN, and RECLAIM_PROVEN.
11. Negative fixture proves a large/cache-looking item without contract remains HUMAN_REVIEW.
12. Generated output contains no network dependency and makes no outbound requests.
13. Browser/manual smoke proves selection + decision trace on a generated synthetic report.
14. Existing `scan`, `validate`, `plan`, and refusal `apply` behavior remains green.

## 11. Fixed-point design decision

The architecture question is sufficiently resolved for a bounded implementation slice:

> **Build a dependency-free, self-contained local HTML treemap report first; make FileSteward's decision trace the primary differentiator; keep the UI read-only and authority-free.**

A native Windows shell can wrap the same presentation model later if operator use proves the interaction model.

## 12. Proof ceiling and next owner

**DESIGNED:** yes  
**EXECUTABLE SYNTHETIC INTERACTION PROTOTYPE:** yes  
**PRODUCTION VISUALIZATION IMPLEMENTED:** no  
**RUNTIME/REAL-RECEIPT PROOF:** no  
**MUTATION AUTHORITY:** none

**Next owner:** P07 bounded implementation of the presentation-model + HTML generator + `filesteward visualize` seam, followed by synthetic and browser smoke proof.
