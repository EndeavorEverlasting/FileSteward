# FileSteward Visual System — F0 Contract Freeze

**Status:** F0 CONTRACT FROZEN BY DESIGN PROTOTYPE  
**Version:** visual-system/v1  
**Primary consumer:** F2 — modern visual system + report shell  
**Secondary consumers:** F3 treemap engine, F4 visualization convergence, F5 accessibility/polish  
**Upstream:** `docs/program/storage-reclaim-visualization.md` (P95), `plans/active/STORAGE-RECLAIM-VISUALIZATION-P04.md`  
**Machine tokens:** `docs/program/storage-reclaim-visual-system.tokens.json`  
**Interfaces + call stacks:** `docs/program/storage-reclaim-visual-system.interfaces.md`  
**Executable seam prototype:** `src/filesteward/visualization/` (tokens/contracts/css/literal/shell/selection)

## 1. Outcome

FileSteward's report UI must look and behave like modern Windows productivity software while preserving three non-conflated concepts:

1. **Magnitude** — how much storage an item occupies.
2. **Evidence state** — what FileSteward knows (`CleanupDisposition`).
3. **Authority state** — whether any action has been approved (`AuthorizationState`).

Visual magnitude must never imply actionability. A green evidence state is not authorization. A selected item is not an approved item.

Visual hierarchy:

```text
storage magnitude
        ↓
operator selection
        ↓
evidence state
        ↓
first unresolved gate
        ↓
possible next decision
        ↓
authorization state
```

## 2. Design language

Use: flat layered surfaces; subtle depth; generous but efficient spacing; strong numeric hierarchy; restrained semantic color; highly legible controls; crisp geometry; visible keyboard focus; predictable responsive behavior.

Do not use: beveled panels; faux-3D buttons; cushion-shaded treemaps; glossy gradients; Win95/WinXP chrome; tiny dense toolbars; rainbow color for variety; skeuomorphic disk/folder imagery; translucent blur as a structural requirement.

Borrow WinDirStat's **spatial grammar**, not its appearance.

## 3. Typography

Font stack:

```css
font-family:
  "Segoe UI Variable Text",
  "Segoe UI Variable",
  "Segoe UI",
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  sans-serif;
```

Monospace:

```css
font-family:
  "Cascadia Mono",
  "Cascadia Code",
  "Consolas",
  ui-monospace,
  monospace;
```

| Token | Size | Line height | Weight | Use |
|---|---:|---:|---:|---|
| `--fs-type-display` | 28px | 36px | 600 | major storage number / empty-state headline |
| `--fs-type-title-lg` | 20px | 28px | 600 | page title |
| `--fs-type-title` | 16px | 24px | 600 | pane headings |
| `--fs-type-body` | 14px | 20px | 400 | primary UI text |
| `--fs-type-body-strong` | 14px | 20px | 600 | important labels |
| `--fs-type-small` | 12px | 16px | 400 | metadata |
| `--fs-type-small-strong` | 12px | 16px | 600 | state labels |
| `--fs-type-micro` | 11px | 14px | 500 | compact tags only |

Never use body text below 12px. Treemap labels may use 11px only when rectangle area permits; otherwise omit the label.

Sizes, percentages, counts, reclaim projections, and free-space measurements use `font-variant-numeric: tabular-nums`.

## 4. Spacing, radius, targets

Base unit `--fs-space-unit: 4px`. Preferred rhythm: 8px.

| Token | Value |
|---|---:|
| `--fs-space-1` … `--fs-space-12` | 4, 8, 12, 16, 20, 24, 32, 40, 48 px |

Default pane padding: desktop 16px; compact/table 12px; major page edge 20–24px. Dense rows: min 40px, preferred 44px. Pointer targets: min 40×40, preferred 44×44.

Radius: xs 4 / sm 6 / md 10 / lg 14 / pill 999. Treemap rectangles: 2–4px max.

## 5. Color tokens

Light and dark tokens are intentional (not inverted). See `storage-reclaim-visual-system.tokens.json`.

- Neutrals own canvas/shell/surface/hover/selected/border/text.
- Accent family is cool blue for interaction and authorization emphasis.
- Semantic evidence colors: HUMAN_REVIEW, UNKNOWN, PROTECTED, KEEP_PROVEN, RECLAIM_PROVEN — each with text, bg, and edge tokens.
- Authorization uses neutral/interaction styling, **not** reclaim green.
- Focus: light `#176DB8`, dark `#8BCBFF`.
- No pure `#000000` canvas.

## 6. Surface hierarchy

1. Canvas — `--fs-bg-canvas`, no border.
2. Shell — `--fs-bg-shell`, bottom border.
3. Pane — `--fs-bg-surface-1`, subtle border; desktop panes share edges.
4. Card/inset — `--fs-bg-surface-2`, subtle border, `--fs-radius-md`.

Shadows are weak; borders provide most separation. Dark mode weakens shadows further.

## 7. Application shell

Desktop minimum: 1280×720. Primary grid:

```css
grid-template-columns:
  minmax(260px, 320px)
  minmax(480px, 1fr)
  minmax(320px, 400px);
```

Breakpoints: wide ≥1440 three panes; standard 1180–1439 compressed three; medium 800–1179 navigator+map then inspector below; narrow <800 sequential. No horizontal app-shell scroll. No pane clipped horizontally.

## 8. Component contracts (F2 owns rendering)

### Storage navigator

Row: name/path fragment + size; second line state · item count · secondary metadata. Selected: `--fs-bg-selected` + 2px accent leading edge. Hover must not resemble selected.

### Treemap (F3 geometry; F2 paint)

Outer padding 8px; gap 2px (3px at high-density parent boundaries). Base fill from restrained hierarchy tints; evidence via 2px state edge + glyph/badge + optional low-opacity tint — not a state-color mosaic. Selection outline 3px accent. Labels only when space permits (name → size → state). Zoom never changes classification.

### Decision inspector

Sections: Selected item, Evidence, Decision trace, Reclaim projection, Risk, Next valid action, Authorization. Size labels must say Logical / Allocated / Projected reclaim explicitly. First unresolved gate dominates. Passed gates recede. No apply/quarantine/delete in initial visualization.

### Filters / search / metrics

Filters are display-only chips. Search height 36px; placeholder `Search paths and groups`. Metrics strip: Observed, Free, Projected reclaim (+ quality), Target, Authorization.

## 9. Interaction, a11y, motion

Every interactive element: rest, hover, focus-visible, pressed, selected, disabled, blocked, loading. Never remove focus outlines without equal replacement. Disabled remains readable and explains unavailability.

Target WCAG 2.2 AA. State never by color alone. Keyboard reaches all decision-relevant information. Screen-reader treemap name includes display name, logical size, disposition, authorization. Respect `forced-colors` and `prefers-color-scheme` / future user override. Respect `prefers-reduced-motion: reduce` (transitions ≤0.01ms; zoom immediate). No pulsing status.

Tooltips are supplemental only (300–500ms mouse; immediate on keyboard focus).

## 10. Loading / empty / error

Static progress language for receipt load → validate → model → layout → render. Never claim “Analyzing safety…” when reading persisted evidence. Empty and error states use factual language; never publish a partial successful-looking report.

## 11. Iconography

Repository-owned SVG or CSS geometry only — no CDN. Icons supplement labels. Suggested: HUMAN_REVIEW `?`, UNKNOWN `…`, PROTECTED shield/lock, KEEP_PROVEN bookmark/check, RECLAIM_PROVEN archive mark, UNAPPROVED lock, APPROVED signed check.

## 12. F5 visual-regression fixtures (required later)

Deterministic fixtures for: light desktop; dark desktop; 1024px; narrow; HUMAN_REVIEW / PROTECTED / UNKNOWN / RECLAIM_PROVEN+UNAPPROVED selected; hostile long path; keyboard focus navigator; keyboard focus treemap; reduced-motion; forced-colors when tooling allows.

## 13. Acceptance floor

Passes only when: modern (not WinDirStat-inherited); list/map/inspector synchronized; semantic state comprehensible without color; magnitude ≠ reclaim authority; logical/allocated/projected distinct; RECLAIM_PROVEN ≠ approved; keyboard-complete; intentional dark mode; reduced-motion honored; intermediate layouts do not clip inspector; receipt text cannot execute markup; first unresolved gate dominates; no apply/quarantine/delete; fixtures detect UI drift.

## 14. Proof ceiling

**F0 CONTRACT:** frozen in this document + token JSON + interface map + executable seam prototypes.  
**F2 PRODUCTION SHELL:** not implemented by this freeze.  
**F1 MODEL / F3 TREEMAP / F4 CLI:** not owned here.
