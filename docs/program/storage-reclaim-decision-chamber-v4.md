# Memory Atlas v4 — Decision Chamber

**Status:** P95 PROGRAM DESIGN + P13 recurrence repair; pure workflow prototypes provider-pushed; local integration/validation pending.

**Predecessor:** Memory Atlas v3 cinematic recovery on PR #15.

## 1. Product decision

The next experience is not another inspection dashboard. The operator must be able to click the visible evidence state and move through the actual decision gates.

Canonical journey:

```text
MAP -> FOCUS -> GATE -> RESOLVE -> APPROVAL -> STAGED
```

Permanent deletion is **not** implemented by this program. The first approved action remains **quarantine**. The UI may describe the operator's intent as a delete candidate, but the truthful terminal scene is:

> DELETE INTENT RECORDED -> APPROVED FOR ACTION -> QUARANTINE STAGED -> NO BYTES REMOVED YET

That distinction is visible in the scene, not buried in documentation.

## 2. UNKNOWN is interactive, not manually promotable

The UNKNOWN badge becomes an action surface.

Click/tap/keyboard activation opens the current decision scene for that exact node.

UNKNOWN never offers approval. Its allowed operator intents are:

- **RESCAN** — resolve incomplete observation;
- **KEEP** — record an operator keep intent separately from evidence;
- **REVIEW LATER**.

A decision may produce new inputs or a fresh scan. Only deterministic re-evaluation may change `CleanupDisposition`.

HUMAN_REVIEW similarly offers:

- **DECLARE REGENERABLE CONTRACT**;
- **KEEP**;
- **REVIEW LATER**.

The operator does not hand-edit `UNKNOWN -> RECLAIM_PROVEN`.

## 3. Approval gate

Only `RECLAIM_PROVEN + UNAPPROVED` enters APPROVAL.

Approval is a separate artifact bound to:

- exact run ID;
- SHA-256 of exact `cleanup-plan.csv`;
- exact approved item IDs;
- action `QUARANTINE`;
- authorization state `APPROVED_FOR_ACTION`.

The approval artifact lives only beneath ignored runtime state. It is never inferred from a click highlight.

After authoritative receipt readback, the scene may enter STAGED.

## 4. Staged delete cinematic

The operator's delete decision is made visible without pretending deletion occurred.

Required transition:

1. selected evidence block becomes the sole spatial subject;
2. surrounding dashboard chrome recedes;
3. the current gate line completes and collapses behind the subject;
4. approval identity/digest flashes as a signed checkpoint;
5. the selected block receives a warm copper cut/perimeter line;
6. the block separates from the evidence field and moves into a visible **QUARANTINE RAIL**;
7. the source location remains ghosted as `PENDING APPLY`;
8. terminal copy reads **STAGED — NO BYTES REMOVED**.

Do not animate the block vanishing. Vanishing would falsely imply deletion.

## 5. Prompt Kit selected-state adaptation

Prompt Kit's current selected-prompt implementation keeps selected, roving/focus, and open-detail identities separate and renders `data-selected`, `aria-selected`, a persistent selected highlight, and viewport centering.

Decision Chamber adapts that mechanism:

| Prompt Kit | FileSteward |
| --- | --- |
| `selectedPromptId` | `selectedNodeId` |
| `rovingPromptId` | `activeGateId` |
| `openPromptId` | `openDecisionScene` |
| selected highlight survives focus | selected evidence remains visually anchored while the active gate moves |
| center selected prompt | keep active gate/selected evidence inside the cinematic viewport |
| `aria-selected` | `aria-selected` on evidence + `aria-current="step"` on gate |

The UI must always answer **what object is selected, which gate is active, which scene is open, and what just changed**.

## 6. Environment-as-tutorial

No tour overlay.

The scene teaches itself:

- MAP — "find the pressure";
- FOCUS — "this is the object under review";
- GATE — "this exact question blocks progress";
- RESOLVE — only valid operator choices are physically available;
- APPROVAL — evidence is proven; mutation is still locked;
- STAGED — approved action is queued for quarantine; nothing removed yet.

Completed gates visibly cool/recede. The active gate is the only high-energy decision locus. The immediately previous gate retains a quieter "last completed" highlight so orientation survives the transition.

## 7. P13 palette root-cause disposition

The current token authority is the source of the repeated blue/cyan appearance. Downstream CSS polish cannot cure a blue canonical palette.

Decision Chamber requires a warm material palette derived from the operator-supplied reference:

- ivory / bone;
- espresso / carbon-brown;
- walnut / smoked wood;
- copper / amber;
- stone;
- moss / forest.

Dark navy, electric blue, and cyan are forbidden as dominant Atlas surfaces or primary interaction accents.

Semantic state remains distinguishable by text/icon/shape as well as color.

## 8. Local-agent no-judgment contract

The local agent does **not** choose:

- the state model;
- allowed intents;
- approval eligibility;
- action type;
- palette direction;
- cinematic narrative;
- tutorial strategy;
- version target.

Those are fixed here.

Local agent work is mechanical integration:

1. wire `decision_flow.py` into the existing selection/camera adapters;
2. make state badges operable;
3. render the current gate as the dominant scene;
4. wire only the intents returned by `allowed_intents`;
5. implement approval artifact persistence/readback under ignored `var/runs`;
6. stage only `QUARANTINE`;
7. implement the exact staged cinematic;
8. apply the canonical warm token palette;
9. bump candidate to **0.3.0** through P130;
10. run the required repository/browser proof.

## 9. Acceptance

Deterministic:

- UNKNOWN cannot request approval;
- HUMAN_REVIEW cannot self-promote;
- PROTECTED/KEEP cannot open delete approval;
- only RECLAIM_PROVEN can accept APPROVED_FOR_ACTION;
- approval is bound to exact run + cleanup-plan digest + item IDs;
- STAGED always means QUARANTINE pending, never bytes removed;
- selected / active gate / open scene remain separate state.

Browser:

- clicking UNKNOWN opens the actual first unresolved gate;
- active gate is unmistakable and marked `aria-current="step"`;
- previous gate remains visibly identifiable as last completed;
- advancing a gate causes a spatial scene transition;
- approval scene exposes exact scope before confirmation;
- staged scene ends with `NO BYTES REMOVED`;
- no blue/cyan dominant visual language remains;
- mouse, keyboard, and touch use the same semantic intents.

Proof ceiling:

This design/prototype does not prove local persistence, approval receipt creation against a real private run, quarantine/apply behavior, deletion, reclaimed bytes, or operator live acceptance.

## 10. Canonical warm material token values

The palette is not left to implementation taste.

### Dark / cinematic

| Role | Value |
| --- | --- |
| canvas | `#15120F` espresso-black |
| shell | `#1C1814` carbon-brown |
| selected | `#4A3528` walnut |
| primary accent | `#D7AA82` warm copper |
| focus | `#E7C49F` bone-copper |
| review | `#D6A24A` amber |
| unknown | `#C1B6A8` warm stone |
| protected | `#D47B67` oxidized rust |
| keep | `#A9AD7B` sage/moss |
| reclaim | `#86A76A` forest-moss |

### Light / reference-adjacent

| Role | Value |
| --- | --- |
| canvas | `#F3EDE3` ivory |
| shell | `#FBF7F0` warm bone |
| selected | `#E7D2BE` pale walnut |
| primary accent | `#8D5F3F` walnut/copper |
| keep | `#626B43` olive |
| reclaim | `#4F713E` forest |

Blue/cyan may appear only when an operating-system forced-color mode chooses it. It is not an authored dominant Atlas color.

## 11. P130 recurrence repair

Decision Chamber is product candidate **0.3.0**.

The version helper now treats staged/unstaged visual changes relative to the previous committed HEAD as a new visual pass. Therefore a long-lived branch already at 0.3.0 will still auto-bump a later polish pass instead of silently reusing 0.3.0 merely because it is already greater than main.

## 12. Localhost Decision Bridge — exact interaction transport

The generated report is static evidence. It cannot become the authority for operator decisions by mutating JavaScript objects in memory.

Decision Chamber therefore uses one local-only bridge:

```text
browser scene
  -> semantic decision intent
  -> same-origin 127.0.0.1 Decision Bridge
  -> ignored var/runs/<run>/ operator artifact
  -> authoritative readback
  -> next cinematic scene
```

### CLI entrypoint to implement

```text
filesteward review <run-dir> [--port 0]
```

Binding is fixed to `127.0.0.1` by the application. There is no `--host 0.0.0.0` escape hatch.

The command:

1. validates the existing run before serving;
2. generates/resolves the current report;
3. computes the exact `cleanup-plan.csv` SHA-256;
4. starts a loopback-only HTTP server on an ephemeral port by default;
5. generates an unpredictable per-process session token;
6. injects that token into the served report as runtime-only data;
7. opens or prints the local report URL.

### API

`GET /api/v1/state`

Returns only current local session facts needed by the UI: run ID, plan digest, selected decision events/approval state, and permitted semantic actions. Private path/evidence content remains sourced from the already-local report.

`POST /api/v1/decision`

Accepts only the typed intents from `DecisionBridgeIntent`. It writes/updates an ignored operator-decision artifact. It never rewrites inventory evidence.

`POST /api/v1/approval`

Requires:

- exact run ID;
- exact item ID;
- exact cleanup-plan SHA-256;
- action `QUARANTINE`;
- `confirm: true`;
- item present in the exact cleanup plan;
- item disposition `RECLAIM_PROVEN`;
- proposed action `quarantine`.

On success it atomically writes/updates the approval artifact and returns authoritative `APPROVED_FOR_ACTION`. The browser then reads that state and enters STAGED.

### Browser-to-localhost security

Mutation requests must fail closed unless all are true:

- server bound to loopback only;
- request Host resolves to the serving loopback authority;
- request Origin matches the exact served origin;
- JSON content type;
- unpredictable per-process token supplied in `X-FileSteward-Session`;
- no permissive CORS headers;
- token is never written to tracked files or durable runtime artifacts.

A random web page must not be able to authorize a local FileSteward action by sending a blind request to localhost.

### UNKNOWN status behavior

Clicking UNKNOWN opens the GATE scene and may record `RESCAN`, `KEEP`, or `REVIEW_LATER`.

The UI may visually change the **operator-decision status** immediately, for example:

```text
Evidence: UNKNOWN
Decision: RESCAN REQUESTED
```

It must not relabel evidence as RECLAIM_PROVEN.

A future/read-only rescan consumes the decision input and creates a fresh evidence run. If deterministic evidence then becomes RECLAIM_PROVEN, the new report advances naturally to APPROVAL.

The first Decision Bridge implementation does not need to automate the full rescan job in the same POST. It must persist the request and expose the exact next executable action. A later bounded lane may make RESCAN asynchronous without changing these semantics.
