# U1 Operator Comprehension — Call-Stack Design

**Status:** DESIGNED + executable seams wired into report shell
**Module:** `src/filesteward/visualization/scene_surface.py`
**Authority floor:** `decision_flow.allowed_intents()`; permanent deletion forbidden

## Operator rejection recovered from live screenshot

The brand/Home-only candidate left these gaps visible:

1. Header/metrics were inert chrome — not scenery entrypoints.
2. Classification legend (contracted) was absent; only status orbs showed.
3. No obvious answer to “how do I change classification?” or “how do I delete?”

## Alternatives compared

| Candidate | Disposition | Why |
|---|---|---|
| Add a real Delete button that removes bytes | REJECT | Permanent deletion not implemented; safety model forbids |
| Encode classify/delete only inside Decision Chamber JS | REJECT | Offline report still needs comprehension; chamber can stay closed on MAP |
| Pure scene_surface projection + shell wiring | SELECT | One owner for metric scenes, legend, next actions; consumes decision_flow |
| Scatter legend copy into experience.py only | REJECT | Would duplicate acceptance-contract surfaces |

## Dependency direction

```text
interaction-scene-acceptance.v1 / decision_flow
        │
        ▼
scene_surface.py  (metric entries, legend, next actions, scenery subtitle)
        │
        ▼
shell.py render + selection script
        │
        ▼
operator perception (header matches selected scenery; legend always present;
                     Next actions name legal classify / stage-removal paths)
```

## Success stacks

### Metric → scenery

```text
USER activate Observed storage metric
  -> MetricSceneEntry.OPEN_STORAGE_SCENE
  -> atlas-scene-panel shows STORAGE_PRESSURE explanation
  -> no disposition mutation
```

### Classify / stage removal

```text
USER selects RECLAIM_PROVEN + UNAPPROVED
  -> operator_next_actions(flow)
  -> STAGE REMOVAL PATH / KEEP / REVIEW LATER
  -> STAGE REMOVAL PATH opens Decision chamber approval path
  -> terminal truth: quarantine staging — NO BYTES REMOVED
```

## Failure stack

```text
USER wants to delete PROTECTED evidence
  -> allowed_intents() empty
  -> WHY LOCKED next action
  -> no inviting delete control
```

## Proof ceiling

- Shell markup + focused tests: this pass
- Live operator acceptance of legend/header/next-actions: waiting
- Permanent deletion: still not implemented
- Full U1 remainder (favicon, footer ticker, health scenes): successor
