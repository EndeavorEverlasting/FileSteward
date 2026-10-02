# Storage Reclaim Visualization — P97 Prior-Art & Gap Analysis

**Status:** evidence-backed prior art for FileSteward visualization design  
**Problem:** make disk-space concentration obvious while preserving FileSteward's separate evidence, judgment, authorization, and execution states.  
**Rule:** emulate mechanisms, not third-party source code or visual assets.

## Evidence baseline

| System | Observed mechanism | Evidence class | Disposition |
|---|---|---|---|
| WinDirStat | Coordinated directory/list, extension/type view, and interactive treemap; central selection updates views; treemap supports zoom/reselection and size/color encoding. | OBSERVED_IMPLEMENTED in official repository; public product docs | **ADAPT** coordinated views + treemap selection model |
| SpaceSniffer | Zoomable nested-rectangle treemap, details-on-demand, filters, temporary color tags, live visual feedback, exportable reports. | DOCUMENTED on official Uderzo product/release pages | **ADAPT** zoom/filter/review interactions |
| WizTree | Treemap plus sortable file tree, emphasis on fast discovery and allocated-space accuracy/hardlink handling. | DOCUMENTED on official product site | **ADAPT** largest-first and physical-space emphasis; no code reuse |
| TreeSize | Hierarchical list with relative-size bars, treemap, reports, largest-file workflows. | DOCUMENTED on official JAM Software site | **ADAPT** tabular companion and printable/reportable decision surface |
| Filelight | Concentric-ring hierarchy, drill-down, detailed item inspection. | DOCUMENTED on KDE site; GPL application | **DEFER** as alternate visualization after rectangular treemap |
| GNOME Disk Usage Analyzer (Baobab) | Tree plus graphical treemap/ring views for folder-size exploration. | DOCUMENTED on GNOME site; GPL application | **DEFER** alternate view; retain tree+graphic pairing |
| UMD/HCIL Treemap research | Space-filling hierarchy; size and color coding; overview -> zoom/filter -> details-on-demand; squarified layouts improve selection/labels. | PRIMARY RESEARCH / project documentation | **ADOPT** interaction principles; implement independently |

## Source/provenance notes

- WinDirStat official repository inspected at commit `3abce9a69b80a527f52c0a87482d9b09d343ff0c`: `TreeMapView`, `WinDirStatModel`, extension view, zoom/selection events, and treemap rendering are separate coordinated components.
- WinDirStat's current public materials present strong-copyleft licensing, while GitHub metadata/history has varied between GPL version labels. FileSteward is MIT. **Do not copy WinDirStat source.**
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

## P97 conclusion

The strongest starting point is **WinDirStat's coordinated tree + treemap structure combined with SpaceSniffer's zoom/filter immediacy**, implemented independently and coupled to a **FileSteward-native decision trace**.

The external ecosystem already supplies mature storage-visualization patterns. The novel work is not inventing another disk map; it is making the map an auditable front end to FileSteward's evidence and approval contracts.

**Next owner:** P95 architecture/prototype.  
**Proof ceiling:** prior-art/gap evidence only; no production visualization implementation or mutation authority.
