# FileSteward System Stewardship — P97 Prior-Art & Gap Analysis

**Date:** 2026-10-04  
**Baseline:** FileSteward draft PR #15 at `925aa8e6351af1ccc69e68c98afcd5b253ed2c91` (`0.5.0`)  
**Scope:** resource monitoring, warning/advisory semantics, recurring local housekeeping, immersive status/ticker mechanics, and runtime reliability evidence.  
**Boundary:** mechanisms are adapted; no third-party assets, branding, or source are vendored by this plan.

## Product question

FileSteward is evolving from a read-only storage-decision instrument toward a local/private **system stewardship** product:

- explain storage pressure and reclaim opportunity;
- surface low-storage / high-memory / other resource warnings;
- help the operator understand what is consuming resources;
- make ambiguous cleanup choices explicit scenes;
- optionally run recurring observation/recommendation work from local settings;
- later stage only already-approved quarantine actions;
- never let a scheduler manufacture evidence, approval, or permanent-delete authority.

The operator's development profile intentionally keeps recurring housekeeping **enabled by default** so failures are exercised early. Public/user installs remain opt-in until field behavior is proven.

## Reference matrix

| Reference | Source evidence | Mechanism | FileSteward disposition |
| --- | --- | --- | --- |
| System Informer (`winsiderss/systeminformer`, README at `d4058279...`) | Current source README describes highlighted system activity, graphs/statistics, resource-hog discovery, active network connections, and real-time disk access. | Resource pressure should be visible, classifiable, and drillable instead of hidden in a generic dashboard. | **ADOPT product principle / IMPLEMENT INDEPENDENTLY.** FileSteward should make storage/RAM/disk pressure a scene with provenance and recommendations rather than copy System Informer's UI. |
| LibreHardwareMonitor (`LibreHardwareMonitor/LibreHardwareMonitor`, README at `e4310745...`) | Current README exposes a library/API that enumerates hardware and sensor values, including memory/network-related providers, while keeping UI and library separable. | Sensor-provider abstraction: collection is a replaceable adapter; presentation is not the sensor owner. | **ADAPT architecture.** Do not add the C# library as a dependency now. Create a FileSteward observation-provider interface so Windows counters/WMI/other sensor providers can be added without changing warning/scene semantics. |
| Glances (`nicolargo/glances`, `conf/glances.conf` at `f15a795b...`) | Current config separates refresh cadence from threshold tiers and defines careful/warning/critical thresholds for CPU, memory, GPU, sensors and network; alert events are separately tracked. | Explicit severity bands, operator-configurable thresholds, alert history, plugin-specific measurement cadence. | **ADOPT semantics / ADAPT values.** FileSteward should own `NORMAL/CAREFUL/WARNING/CRITICAL/UNKNOWN`, preserve freshness, and separate measurement from advisory action. Development defaults are provisional configuration, not universal truth. |
| Windows Task Scheduler | Microsoft Task Scheduler documentation exposes enabled state, idle conditions, battery conditions, start-when-available, multiple-instance policy, restart behavior and maintenance scheduling. | Durable OS-owned scheduling and power-aware conditions instead of an always-running app polling loop. | **ADOPT as first scheduler adapter on Windows.** Register/query/delete tasks through one FileSteward adapter; read back enabled/cadence/next-run state; failed work does not retire recurrence. Avoid short-interval battery polling. |
| React Fast Marquee (`justin-chu/react-fast-marquee`, source at `f67747ba...`) | Current component implements continuous CSS animation with auto-fill, speed, direction, pause-on-hover and pause-on-click controls. | Seamless status ticker mechanics. | **ADAPT MECHANICS ONLY / NO REACT DEPENDENCY.** Implement the footer/status rail with repository-native HTML/CSS/JS, pause on hover/focus, and static reduced-motion fallback. |
| Existing FileSteward v4 Interaction Grammar | `interaction.py` at PR #15 head `925aa8e...` | Typed presentation cues for reticle/cartouche/status orbs/camera trace. | **KEEP AND EXTEND.** Do not create a second presentation state machine. V4-E must project more surfaces into the same grammar. |

## Cursor timeout precedent

The 2026-10-04 local-agent interruption emitted:

`ERROR_EXTENSION_HOST_TIMEOUT / deadline_exceeded`

with Request ID `7face822-8b9f-4f33-b5c8-0762913de8b2`.

Public Cursor support threads document the same error family when the extension host / agent-execution provider fails to register in time, including Windows/worktree cases. That precedent narrows the failing layer but **does not prove this instance's root cause**.

Disposition:

- preserve exact Request ID/error/time/worktree;
- treat context size, network, RAM, CPU, storage pressure, extensions, and Cursor defects as competing hypotheses;
- on recurrence capture diagnostics before reload when practical;
- keep the canonical reliability incident in the Prompt Scratch Agent Reliability Event Ledger rather than creating a second FileSteward reliability ledger.

## Solved baseline versus FileSteward gap

The ecosystem already demonstrates:

- resource measurement;
- severity thresholds;
- system activity highlighting;
- durable OS scheduling;
- configurable alert history;
- continuous status ticker mechanics.

The FileSteward-specific gap is the **safe combination**:

1. local/private health measurements with freshness;
2. evidence/authority separation;
3. cinematic scene-based explanation;
4. agent-assist for deterministic recommendations;
5. explicit human judgment for ambiguous states;
6. user-controlled recurrence that cannot self-authorize;
7. quarantine-only first mutation path;
8. development-on / product-opt-in schedule defaults;
9. one typed visual grammar across storage, health, camera, status and warning surfaces.

## Selected development target

Do **not** begin with an always-running daemon or permanent-delete cron.

First establish:

- P01 harness contracts for health snapshots, schedule semantics, and interaction-scene acceptance;
- a repository validator for those contracts;
- V4-E interaction scenes that make the existing statuses/metrics/path/header/footer actionable and self-explanatory;
- a read-only system-health observer prototype;
- a Windows Task Scheduler adapter only after the schedule contract is green.

That sequence lets the product become more capable without weakening the safety model.
