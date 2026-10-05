# Housekeeping Settings — Call-Stack Prototype

**Status:** DESIGNED + executable seam prototyped (no OS registration, no scenery UI)
**Contracts:** `harness/contracts/housekeeping-schedule.v1.json`
**Module:** `src/filesteward/housekeeping_settings.py`
**Lane:** U1/S2 precursor on stewardship successor graph (PR #16+)

## User outcomes

1. Operator can enable/disable a local/private cleanup cadence without granting deletion authority.
2. Development profile defaults ON; product profile remains opt-in.
3. Scheduler wake/run selection can accept `SCAN` / `RECOMMEND` when enabled.
4. `QUARANTINE_APPROVED` remains gated on exact operator approval identity.
5. `PERMANENT_DELETE`, `SELF_APPROVE`, and `PROMOTE_EVIDENCE` fail closed.

## Domain vocabulary

| Term | Owner | Meaning |
|---|---|---|
| `HousekeepingSettings` | settings module | Local enabled/cadence/profile state |
| `SettingsStore` | port | Persistence for ignored local/private settings |
| `SchedulerPort` | port | Plans registration descriptors; OS adapter is later S1 |
| `HousekeepingSettingsService` | application | Validates toggles and wake/run actions |
| `PlannedTask` | result | Non-registered task plan for readback tests |

## Alternatives compared

| Candidate | Disposition | Why |
|---|---|---|
| Always-on daemon polling | REJECT | Battery/idle cost; contract prefers Task Scheduler |
| Encode cadence inside `decision_flow` | REJECT | Would conflate wake/run with legal decision authority |
| Full scenery settings UI now | DEFER to S2 | Depends on S1 registration + M2 warnings |
| Pure settings service + ports/fakes | SELECT | Proves authority boundary before OS/UI breadth |

## Dependency direction

```text
future scenery settings UI / CLI
        │
        ▼
HousekeepingSettingsService
        │ validates against schedule contract constants
        ├─► SettingsStore (local/private)
        └─► SchedulerPort.plan_registration (stub now; S1 later)
decision_flow / approval  ← independent; quarantine still requires them
```

## Success call stack

```text
OPERATOR enable daily_idle
  -> HousekeepingSettingsService.apply_settings(enabled=True, cadence="daily_idle")
  -> HousekeepingSettings validated
  -> SettingsStore.save
  -> SchedulerPort.plan_registration -> PlannedTask(registered=False)
  -> SettingsApplyResult
```

## Failure call stack

```text
request_action("PERMANENT_DELETE")
  -> HousekeepingAuthorityError
  -> store unchanged
  -> scheduler not called
```

## Proof ceiling

- Executable seam + focused tests: this pass
- Windows Task Scheduler registration/readback: S1 successor
- Immersive scenery settings scene: S2 successor
- Observed scheduled execution: later proof ladder
- Permanent deletion: forbidden / not implemented
