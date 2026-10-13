# FileSteward workstation-performance profile — P97 / P04 / P82

2026-10-12. Baseline main 197c22ef976cb8caa668c4740f7911afc0fe3407.

Parent objective: a durable, machine-specific performance record for every
selected workstation that informs safe capacity decisions but never grants
destructive authority.

Recovery: Cursor found an empty noncanonical folder at
C:\Users\CheeksMcClappeth\Desktop\Dev\FileSteward. Canonical remote is
EndeavorEverlasting/FileSteward; the checkout contract is
%USERPROFILE%\dev\FileSteward. Preserve the unrelated Desktop directory; do
not silently replace, clone to, reset or remove it. Canonical local state on
PTop is UNOBSERVED in this provider-only session.

P97 = Open-Source Prior-Art & Gap Analyst (Glances, osquery, windows_exporter).
P04 = dependency-aware parallel sprint/harness distributor.
P82 = Prototype-Measure-Refine Delivery Loop.

## Dependency graph and collision owner

F0 Contract/research -> F1 append-only local observation prototype.
From F1:
- F2 Windows-specific storage and sensor binding: collector owner; dependencies F1.
- F3 profile trends & UX: visualization owner; dependencies F1.
F2 and F3 have disjoint mutations and can run concurrently once dispatched
through a proven execution adapter.
F2+F3 -> F4 opt-in scheduled local collection; F3 -> F5 safety gate integration.
No new automation is authorized until host capture/trend correctness is proven.

F0/F1 INTEGRATED on main. Successor lanes F2/F3 own: profiles package, synthetic tests, tracked
P97/P04/P82 plan, program guide. It does not own deletion, scanner,
visualization UI, agents/TokenCorridor, installed applications or local PTop.

## Proof ledger

- Source code and private journal: committed when branch receives these files.
- Synthetic unit suite: must be measured; not green by declaration.
- Capture from real Windows machines: not yet authorized/executed through the
  GitHub connector runtime; no host shell access.
- Exact manifest path: untouched; profile never supplies approval.
- P82: hypothesis -> prototype -> same-workload observation -> critique ->
  refine/reject; preserve last known good.
- P04: parallelism graph width 2 after F1; no host agent adapter observed here.
  Do not claim dispatch merely from this plan.

Next: run focused tests and whole-suite regressions in canonical host
checkout, refresh provider PR/reviews, repair, merge validated exact head,
then capture PTop read-only with explicit alias/volume; repeat on other
workstations only when host identity is verified.
