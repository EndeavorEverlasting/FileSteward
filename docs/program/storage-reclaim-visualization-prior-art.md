# Storage Reclaim Visualization — P97 Prior-Art & Gap Analysis

**Status:** evidence-backed prior art for FileSteward visualization design  
**Problem:** make disk-space concentration obvious while preserving FileSteward's separate evidence, judgment, authorization, and execution states.  
**Rule:** emulate mechanisms, not third-party source code or visual assets.

## Evidence baseline

| System | Observed mechanism | Evidence class | Disposition |
|---|---|---|---|
| WinDirStat | Coordinated directory/list, extension/type view, and interactive treemap; central selection updates views; treemap supports zoom/reselection and size/color encoding. | OBSERVED_IMPLEMENTED in official repository; public product docs | **ADAPT** coordinated views + treemap selection model |
| QDirStat | Tree + treemap coordinated selection; current item gets a strong outline, non-relevant regions can be dimmed, dominant tree items are bold, and treemap zoom is directly operable. | OBSERVED_IMPLEMENTED / current official repository and release documentation | **ADAPT** selection salience, contextual dimming, dominant-item emphasis; reject cleanup actions |
| SpaceSniffer | Zoomable nested-rectangle treemap, details-on-demand, filters, temporary color tags, live visual feedback, exportable reports. | DOCUMENTED on official Uderzo product/release pages | **ADAPT** zoom/filter/review interactions |
| WizTree | Treemap plus sortable file tree, emphasis on fast discovery and allocated-space accuracy/hardlink handling. | DOCUMENTED on official product site | **ADAPT** largest-first and physical-space emphasis; no code reuse |
| TreeSize | Hierarchical list with relative-size bars, treemap, reports, largest-file workflows. | DOCUMENTED on official JAM Software site | **ADAPT** tabular companion and printable/reportable decision surface |
| Filelight | Concentric-ring hierarchy, drill-down, detailed item inspection. | DOCUMENTED on KDE site; GPL application | **DEFER** as alternate visualization after rectangular treemap |
| GNOME Disk Usage Analyzer (Baobab) | Tree plus graphical treemap/ring views for folder-size exploration. | DOCUMENTED on GNOME site; GPL application | **DEFER** alternate view; retain tree+graphic pairing |
| UMD/HCIL Treemap research | Space-filling hierarchy; size and color coding; overview -> zoom/filter -> details-on-demand; squarified layouts improve selection/labels. | PRIMARY RESEARCH / project documentation | **ADOPT** interaction principles; implement independently |

## Source/provenance notes

- WinDirStat's official history says Bernhard Seifert created it in 2003 after using KDirStat; the tree-list + treemap coupling was the central model he wanted on Windows. That history explicitly describes WinDirStat as heavily inspired by/cloning KDirStat's interaction concept.
- WinDirStat official repository was refreshed for the 2026-10-04 live-polish pass at commit 52b663eeb4887d71fbd4c2013b38f128fdaf0582: TreeMapView::HighlightSelectedItem is a dedicated selection-emphasis seam, while WinDirStatModel broadcasts selection refresh/style and zoom changes across coordinated views.
- QDirStat official repository was refreshed at commit ab3f28460a61264b7d7bc2fc356a0851e8736f26: its current item is explicitly outlined, dominant items may be bolded in the tree, and its branch-highlighting interaction dims unrelated treemap regions. FileSteward adapts those perception mechanics only; QDirStat cleanup actions remain outside the FileSteward authority model.
- WinDirStat's official background page currently states GPLv2 while the current official GitHub README states GPLv3-or-later. That public licensing inconsistency is itself a provenance risk. FileSteward is MIT. **Do not copy WinDirStat source.**
- SpaceSniffer is distributed as freeware; its official site documents behavior but is not a compatible source-code donor for FileSteward. **Mechanisms only.**
- WizTree and TreeSize are proprietary/commercially licensed products. **No code or asset reuse.**
- Filelight and Baobab are GPL-family applications. **No source copying into FileSteward's MIT codebase.**
- The historical UMD Treemap software has separate licensing terms. FileSteward should implement its own layout based on published visualization concepts, not copy the old package.

## What is already solved externally

### AVAILABLE_TO_EMULATE_EXTERNALLY

1. **Space-filling size map.** Rectangle area communicates relative storage immediately.
2. **Coordinated selection.** Selecting a row highlights the same object in the visualization and vice versa.
3. **Zoom/drill-down.** Users can start with an overview and progressively expose nested structure.
4. **Largest-first prioritization.** Sorting and area encoding put consequential storage in front of the user.
5. **Filters and temporary review marks.** Exploration can narrow without mutating underlying files.
6. **Details on demand.** Exact path/size/type information appears only after selection.
7. **Report/snapshot output.** The visual exploration can produce a durable review artifact.

## FileSteward-specific residual gap

### PROJECT_SPECIFIC_GAP

Existing analyzers answer **"where is the space?"** and often provide direct delete actions.

FileSteward must answer a different second question:

> **"What evidence state is this item in, what decision is still required, and what exact gate prevents action?"**

That requires a visualization with a companion decision trace:

```text
storage concentration
    -> selected node/bucket
    -> observation complete?
    -> protected overlap?
    -> explicit regenerable contract?
    -> provenance/recoverability documented?
    -> adversarial challenge sustained?
    -> RECLAIM_PROVEN evidence
    -> exact operator approval bound to manifest/run/rows
    -> quarantine/apply
    -> verified reclaim
```

The visualization must never convert size, color, age, type, or a hint tag into reclaim authority.

## Mechanisms selected for FileSteward

### ADOPT / ADAPT

- **Rectangular treemap as the primary overview** — closest fit to WinDirStat/SpaceSniffer and best for comparing storage magnitude.
- **Sortable hierarchical/table companion** — preserves exact numbers and makes the treemap auditable.
- **Linked selection across panes** — one selected evidence object, multiple coordinated views.
- **Zoom/filter/details-on-demand** — follow the proven overview-first exploration model.
- **Decision-trace pane** — FileSteward addition; shows why the selected item is HUMAN_REVIEW, UNKNOWN, PROTECTED, KEEP_PROVEN, or RECLAIM_PROVEN and names the next gate.
- **Evidence-state encoding instead of file-extension color as the primary semantic layer.** Extension/type may become an optional secondary layer later.
- **Non-destructive review marks only.** A future UI may record draft operator decisions, but it must not self-authorize mutation.

### REJECT / DEFER

- Direct delete actions from the visualization: **REJECT** for the current MVP.
- Copying GPL/proprietary/freeware source or artwork: **REJECT**.
- File-type rainbow as the dominant color system: **DEFER**; it competes with FileSteward disposition/authority semantics.
- Radial/sunburst view: **DEFER** until the rectangular treemap decision flow is proven.
- Live filesystem mutation/update coupling: **DEFER**; FileSteward's audit and apply boundaries stay separate.

## 2026-10-04 live F6 falsification -> P95/P97 polish target

The first private real-scale browser view falsified an important assumption from the synthetic acceptance floor: **linked selection can be technically correct while still being perceptually ineffective**.

Observed on the real aggregated F6 surface, without committing private receipt contents:

1. A selected small treemap bucket could be technically outlined yet remain extremely difficult to locate among roughly 200 rectangles.
2. Tiny rectangles attempted to render labels/state text that could not be read at normal desktop viewing distance; unreadable text created noise without adding decision value.
3. The decision inspector put explanatory evidence before the decision trace, pushing the first unresolved gate below the first viewport for a normal desktop window.
4. The map showed magnitude by area but not explicit size text on the dominant rectangles, forcing unnecessary cross-pane eye travel.
5. Selecting a treemap item did not guarantee its navigator row remained visible.
6. The metric labeled **Free space** is persisted run-baseline evidence, not a continuously refreshed workstation reading. The interface must say **Run baseline free space** rather than imply live currency.
7. Duplicate or terse bucket basenames remain a later disambiguation/hierarchy problem; the immediate slice must not invent path semantics or distort area.

### P97 pattern disposition for this falsification

| Pattern | Reference | Disposition | FileSteward adaptation |
| --- | --- | --- | --- |
| Strong current-item outline | QDirStat + WinDirStat | **ADOPT / ADAPT** | Thicker selected outline, elevated z-order, and a beacon for micro/compact rectangles |
| Contextual dimming outside focus | QDirStat | **ADAPT** | Slightly dim non-selected rectangles while preserving hover/focus readability; no evidence/state mutation |
| Dominant-item emphasis | QDirStat | **ADAPT** | Stronger navigator selected row and explicit size inside readable treemap rectangles |
| Central synchronized selection | WinDirStat | **ADOPT** | One selected node updates map, navigator visibility, selection summary, and decision inspector |
| Direct cleanup actions from the map | QDirStat / WinDirStat | **REJECT** | FileSteward remains read-only/UNAPPROVED; no apply/delete/quarantine control |

### P95 terminal-value call stack selected for implementation

operator click / keyboard-select
  -> one node_id becomes current selection
  -> navigator row is emphasized and scrolled into view
  -> treemap selection receives high-salience outline / micro-node beacon
  -> always-readable selection summary shows name + size + disposition + next gate
  -> decision inspector renders decision trace + next valid action before explanatory evidence
  -> underlying disposition / authorization / receipt artifacts remain unchanged

This slice deliberately leaves true hierarchical drill-down, current-live free-space telemetry, bucket-path disambiguation, and density/top-N exploration as successor work. Those require different data or interaction contracts; they are not excuses to leave selection illegible now.

**Proof boundary for this slice:** improve perception and interaction only. No contract selection, disposition promotion, approval, apply, quarantine, deletion, or real receipt mutation.

## P97 conclusion

The strongest starting point is **WinDirStat's coordinated tree + treemap structure combined with SpaceSniffer's zoom/filter immediacy**, implemented independently and coupled to a **FileSteward-native decision trace**.

The external ecosystem already supplies mature storage-visualization patterns. The novel work is not inventing another disk map; it is making the map an auditable front end to FileSteward's evidence and approval contracts.

**Next owner:** P95 architecture/prototype.  
**Proof ceiling:** prior-art/gap evidence only; no production visualization implementation or mutation authority.


## Public reference anchors

- WinDirStat background/history: https://windirstat.net/background.html
- WinDirStat official repository: https://github.com/windirstat/windirstat
- QDirStat official repository: https://github.com/shundhammer/qdirstat
- SpaceSniffer official product/features: https://www.uderzo.it/main_products/space_sniffer/
- WizTree official product: https://diskanalyzer.com/
- TreeSize official product: https://www.jam-software.com/treesize_free
- KDE Filelight: https://apps.kde.org/filelight/
- GNOME Disk Usage Analyzer: https://apps.gnome.org/Baobab/
- UMD HCIL Treemap project/history: https://www.cs.umd.edu/projects/hcil/treemap/

These anchors are research provenance only. No third-party assets or source are vendored by this sprint.
