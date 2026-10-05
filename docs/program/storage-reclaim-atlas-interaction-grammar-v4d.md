# Memory Atlas V4-D — Atlas Interaction Grammar

**Status:** DESIGNED + IMPLEMENTED (local suite); live operator acceptance open  
**Authority floor:** V4-C preserved at PR #15 `4e8a529` (0.4.0)  
**Product version after V4-D visual-feature:** `0.5.0`
**Product version after U1 brand/Home visual-feature:** decided by P130 (`0.6.0`)

## User outcomes

1. Pointing at Atlas evidence/controls always shows a truthful verb (EXPLORE / FOCUS / INSPECT BLOCK / APPROVE / WHY LOCKED / …).
2. Sacred/essential vs reclaim-candidate vs blocked vs ambiguous states are color+glow distinct without granting authority.
3. Camera CURRENT state is never confused with LAST/RECENT commands.
4. `PROTECTED`, `UNAPPROVED`, and evidence-gap (`? items`) are operable status nodes.
5. Native browser tooltips never pierce the authored world.
6. Illegal intents never look operable; explanation is visible.
7. The FileSteward brand/title is a conventional Home affordance that returns the camera to Atlas Home through the existing `FileStewardAtlas.home()` authority (no second navigation/state owner).

## Invariants

- `decision_flow.allowed_intents()` is the only legal-choice authority.
- Presentation cues never promote disposition, invent reclaim, or authorize mutation.
- Permanent deletion is NOT IMPLEMENTED.
- Terminal mutation truth remains: QUARANTINE STAGED — NO BYTES REMOVED.
- Warm espresso/copper contract remains canonical; no navy/cyan except OS forced-colors.

## Domain vocabulary

| Term | Owner | Meaning |
|---|---|---|
| `InteractionCue` | `interaction.py` | Typed presentation projection |
| `target_kind` | cue | EVIDENCE / STATUS / GATE / INTENT / NAVIGATION / AUTHORIZATION |
| `verb` | cue | What acting does (never invents legality) |
| `availability` | cue | OPERABLE / BLOCKED / INFORMATIONAL / UNAVAILABLE |
| `recency` | cue | CURRENT / LAST / RECENT / IDLE |
| `consequence` | cue | READ_ONLY / RECORD_INTENT / WRITE_APPROVAL / STAGE_QUARANTINE |
| `quality_tone` | cue | ESSENTIAL / RECLAIM_CANDIDATE / AMBIGUOUS / BLOCKED / NEUTRAL |
| Status orb | shell/chamber | Operable PROTECTED / UNAPPROVED / EVIDENCE_GAP node |
| Cartouche | experience | Informational explanation surface (not a choice dialog) |

## Module map

```text
decision_flow.py / camera.py / selection
        │ authoritative facts
        ▼
interaction.py          ← presentation-only projection
        │ InteractionCue + data-* attrs
        ▼
shell.py / experience.py / decision_chamber.py / cinematic.py
        │ reticle · cartouche · glow · action trace · status orbs
        ▼
operator perception (same semantic action)
```

Dependency direction: renderers → interaction → decision_flow/models. Never reverse.

## Representative success call stacks

### Brand / title Home

```text
USER activate brand title (click / Enter / Space / keyboard focus)
  -> shell #brand-home data-atlas-action="home"
  -> cue_for_navigation("brand_home") -> RETURN / READ_ONLY / ATLAS HOME
  -> cinematic [data-atlas-action] listener -> FileStewardAtlas.home()
  -> camera HOME + overview scene
  -> terminal value: Atlas Home restored (same path as #atlas-home / Home key)
  -> no decision_flow mutation; no second router
```

### Explore map evidence

```text
USER pointer/focus on map-node
  -> experience.cueFrom reads data-* from InteractionCue
  -> reticle/cartouche show EXPLORE or FOCUS
  -> click -> SelectionController selects node_id
  -> decision_chamber opens truthful scene via open_decision_session
  -> no disposition mutation
```

### PROTECTED status orb

```text
USER activate PROTECTED orb
  -> cue_for_status_orb(PROTECTED) -> INSPECT BLOCK / READ_ONLY
  -> chamber focuses blocking gate
  -> APPROVE_QUARANTINE remains absent from allowed_intents()
```

### Eligible UNAPPROVED

```text
USER activate UNAPPROVED orb on RECLAIM_PROVEN + UNAPPROVED
  -> allowed_intents includes APPROVE_QUARANTINE
  -> cue -> APPROVE / WRITE_APPROVAL
  -> bridge records approval request
  -> staged scene: NO BYTES REMOVED
```

## Failure call stacks

### Illegal approve

```text
USER attempts APPROVE on PROTECTED
  -> allowed_intents() empty for APPROVE_QUARANTINE
  -> cue_for_status_orb -> WHY LOCKED / BLOCKED
  -> no tempting operable delete/reclaim control
```

### Native tooltip leak

```text
map-node must not emit title=
  -> cartouche + aria-label carry explanation
  -> characterization test asserts no title= in <body>
```

## Alternatives compared (P95)

| Candidate | Disposition |
|---|---|
| Scatter cursor/tooltip/glow fixes in each renderer | REJECT |
| Typed presentation-only Interaction Projection | SELECT |
| XState / second state machine | REJECT |
| Radix/React migration | REJECT |

## Proof ceiling

- Designed / implemented / locally validated / committed / pushed: this sprint.
- Provider read-back: required after push.
- Browser/live observed + operator accepted: successor V4-D4 / PR acceptance.
- Merge/undraft: forbidden until operator acceptance.
