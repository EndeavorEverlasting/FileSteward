# FileSteward Visual System — Program Interfaces & Call Stacks

**Status:** F0 DESIGN PROVEN BY EXECUTABLE SEAMS  
**Companion:** `docs/program/storage-reclaim-visual-system.md`  
**Tokens:** `docs/program/storage-reclaim-visual-system.tokens.json`

## 1. User outcomes / invariants

| Outcome | Meaning |
|---|---|
| Locate storage concentration | Treemap + largest-first navigator |
| Inspect exact selected evidence | Path, logical/allocated/projected reclaim, disposition |
| See next valid gate | Decision inspector emphasizes first unresolved gate |
| Never confuse size/evidence with authority | Authorization remains separate and visually distinct |

Invariants from `LOCAL-AGENT-PROTECTIONS.md` and P95 remain binding. Visualization is read-only in F0–F6.

## 2. Domain vocabulary

| Term | Owner | Decides |
|---|---|---|
| `PresentationNode` | F1 produces; F2/F3 consume | Immutable display facts only |
| `TreemapRect` | F3 | Geometry for one node at a zoom root |
| `ReportShell` | F2 | HTML/CSS/JS chrome around model+rects |
| `SelectionState` | F2 runtime (generated JS) | Which `node_id` is focused across panes |
| `ViewportMode` | F2 CSS | wide / standard / medium / narrow |
| `EvidenceTone` | F2 tokens | Border/badge/text for disposition |
| `AuthorizationTone` | F2 tokens | Neutral/accent styling — never reclaim green |
| `GateStepView` | F1 fields → F2 render | PASS / FAIL / WAITING / UNKNOWN / N/A |
| `VisualTokens` | F0 freeze → F2 emit | CSS custom properties |

## 3. Alternatives compared

### A. Token delivery

| Candidate | Verdict |
|---|---|
| A1. Python-owned token dict → emitted CSS custom properties | **SELECTED** — single source, testable, no build step, offline-safe |
| A2. Hand-authored static CSS only | Reject — drifts from Python tests and token JSON |
| A3. CSS-in-JS theme engine at runtime | Reject — extra JS failure surface for first offline report |
| A4. Jinja/template dependency | Reject — violates dependency-free package floor |

### B. Shell composition

| Candidate | Verdict |
|---|---|
| B1. Python emits one self-contained HTML file | **SELECTED** — matches P95 Candidate A |
| B2. Multi-file report directory | Defer — breaks single portable artifact |
| B3. Native desktop + WebView | Defer — after interaction model proven |

### C. Selection ownership

| Candidate | Verdict |
|---|---|
| C1. Single `node_id` SelectionController in generated JS | **SELECTED** — list/map/inspector sync without server |
| C2. Local HTTP selection API | Reject — ports/lifecycle |
| C3. Hash-URL as sole selection owner | Defer — optional later deep-link; not required for F2 |

## 4. Module / interface map

```text
filesteward.visualization.tokens
  owned state: frozen VisualTokens (light/dark)
  public: load_tokens(), disposition_css_stem()
  side effects: none
  failure: KeyError / ValueError on unknown disposition

filesteward.visualization.contracts
  owned state: PresentationNode / GateStep / ShellMetrics / ShellEvent Typed shapes
  public: dataclasses + validation helpers
  side effects: none
  failure: ValueError on illegal empty ids / negative sizes when present

filesteward.visualization.css
  owned: CSS custom-property emission from tokens
  public: render_token_css()
  side effects: none
  failure: none beyond token load

filesteward.visualization.literal
  owned: receipt-derived string → HTML-safe text/attr
  public: escape_text(), escape_attr()
  side effects: none
  failure: TypeError if non-str coerced incorrectly — callers pass str

filesteward.visualization.shell
  owned: thin report shell skeleton (F0 prototype; F2 expands to full html.py)
  public: render_report_shell(model, rects=None, *, title=...)
  side effects: none (string return only; F4 owns atomic write)
  failure: ValueError if model empty / selection missing

filesteward.visualization.selection
  owned: selection sync rules (display-only)
  public: SelectionController.select / filter / visible_ids
  side effects: none
  failure: KeyError if selecting unknown id

F1 model.py (successor)     — validated artifacts → PresentationModel
F3 treemap.py (successor)   — PresentationModel → TreemapRect[]
F2 html.py (successor)      — expands shell + paints F3 rects
F4 cli.py (successor)       — validate → model → layout → atomic HTML
```

Dependency direction:

```text
tokens.json ──► tokens.py ──► css.py ──┐
contracts.py ─────────────────────────┼──► shell.py ──► (F4 write)
selection.py ─────────────────────────┘
F1 PresentationModel ──► shell/html (consume only)
F3 TreemapRect[] ───────► shell/html (consume only; optional in F0 prototype)
```

No cycles. Shell must not infer disposition or invent gate facts.

## 5. Success call stacks

### Journey V1 — emit modern token CSS (terminal: CSS string for embedding)

```text
OPERATOR / F2 builder
  -> visualization.css.render_token_css()
  -> tokens.load_tokens()
  -> emit :root + prefers-color-scheme:dark custom properties
  -> return CSS text
```

Terminal user value: one coherent token surface every later component inherits.

### Journey V2 — render literal hostile receipt text (terminal: escaped fragment)

```text
receipt-derived path containing <profile>, &, quotes, markup-like text
  -> literal.escape_text(path)
  -> HTML fragment with entities only
  -> no script/markup execution
```

### Journey V3 — synchronized selection across panes (terminal: stable selected node)

```text
user selects navigator row OR treemap node OR keyboard activation
  -> SelectionController.select(node_id)
  -> visible filter preserved
  -> selected_id updated if still visible else first visible / None
  -> shell re-render uses same selected_id for list/map/inspector
  -> disposition/authorization unchanged
```

### Journey V4 — shell composition from presentation stubs (terminal: offline HTML string)

```text
synthetic PresentationModel
  -> shell.render_report_shell(model, rects=None)
  -> css.render_token_css()
  -> literal-escape all receipt strings
  -> emit shell/header/metrics/navigator/map-container/inspector/footer
  -> return HTML string (F4 later writes atomically)
```

Terminal user value for V4 at F0: **auditable offline report skeleton** with synchronized selection hooks — not apply/delete. Opening a detail panel *is* the terminal value for visualization review (ENTRYPOINT=`visualize`, TERMINAL=inspect decision gate). Mutation journeys are later F7–F9.

## 6. Failure call stacks

### F-V1 — unknown disposition token mapping

```text
disposition_css_stem("NOT_A_STATE")
  -> ValueError
  -> caller refuses shell publication
```

### F-V2 — select id not in model

```text
SelectionController.select("missing")
  -> KeyError
  -> UI keeps prior selection / surfaces error in prototype tests
```

### F-V3 — empty model shell

```text
render_report_shell(empty)
  -> ValueError("presentation model has no nodes")
  -> no HTML claimed successful
```

## 7. State model

```text
SelectionState: { selected_id: str | None, filter: ALL|disposition, query: str }
ViewportMode: wide | standard | medium | narrow   (CSS only; no domain mutation)
ThemeMode: light | dark                          (prefers-color-scheme; future override)
MotionMode: full | reduced                       (prefers-reduced-motion)
```

Illegal: selection that mutates disposition; filter that mutates authorization; theme that remaps reclaim green onto approval.

## 8. Test / observability seams

| Proof | Kind |
|---|---|
| token JSON loads and emits both themes | unit |
| disposition→token map covers CleanupDisposition | unit |
| hostile path escapes literally | unit |
| selection sync + filter rebind | unit |
| shell contains no apply/delete controls | unit |
| shell embeds focus + reduced-motion CSS hooks | unit |
| RECLAIM_PROVEN row still shows UNAPPROVED | unit |

Logs/traces: prototype tests print traversed module names; no durable telemetry owner in F0.

## 9. Second-pass critique (after prototypes)

| Finding | Disposition |
|---|---|
| Full visual-regression screenshots belong to F5 | REQUIRED SUCCESSOR WORK |
| Squarified geometry stays F3 | do not absorb into shell |
| Gate-step reconstruction stays F1 | shell only renders structured GateStep fields |
| Production `html.py` name reserved for F2 expansion of shell.py | F2 may rename/move; contracts remain |

## 10. Exact next build seam

F2 production implementation starts by:

1. Expanding `shell.py` into owned `html.py` without changing token/contract public shapes.
2. Consuming F1 `PresentationModel` and F3 `TreemapRect` without inferring evidence.
3. Embedding the proven `render_token_css()` + `escape_*` call stack.
