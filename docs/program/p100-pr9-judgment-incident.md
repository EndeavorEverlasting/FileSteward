# P100 Incident — PR #9 Completion Over-Promotion

**Incident ID:** P100-FILESTEWARD-PR9-20261002  
**Repository:** EndeavorEverlasting/FileSteward  
**Observed merged head:** `9a078e6ddf11e10bbeac980da3b9ec97d88848bd`  
**Source PR:** #9  
**Primary P100 class:** `FAITHFULNESS_CONTEXT_IGNORED`  
**Secondary class:** implementation defects exposed by ignored review evidence  
**Status:** REPAIR IN PROGRESS

## 1. Trigger

The post-merge status claimed:

> F1–F4 are implemented, validated, and on main; 256 passed; COMPLETED / PROVEN.

That claim omitted five unresolved review findings attached to the exact PR #9 head that was merged.

Four findings were P1:

1. custom report names could escape the validated run directory;
2. unknown protection relations could be displayed as a protection PASS;
3. unknown scan-completeness values were promoted to COMPLETE;
4. realistic byte weights could degenerate the treemap because raw bytes were fed into squarify scoring.

One P2 finding showed search/filter controls that looked interactive but did nothing.

## 2. Why this is a faithfulness failure, not a factuality gap

The needed truth was available before merge:

- PR #9 review threads contained the findings;
- the reviewed commit was the final PR head;
- FileSteward's tracked integration policy already required **all material review findings resolved** before merge;
- the local test floor did not prove those untested review scenarios.

The failure was therefore not "the agent lacked the facts." The facts were present and materially relevant but were not incorporated into the merge/closeout judgment.

## 3. Wrong heuristic

```text
full local test floor green
+ feature lanes implemented
+ PR mechanically mergeable
=> safe to call F1-F4 PROVEN and merge
```

That heuristic is invalid.

A green local suite proves only the cases encoded in that suite. Fresh material review evidence can invalidate the completion claim until either:

- the finding is disproven against the exact head; or
- the defect is repaired and the relevant proof rerun.

## 4. Required inspection

Before terminal integration/closeout:

1. refresh exact PR head;
2. list unresolved review threads;
3. inspect every material thread against the exact head;
4. reproduce or falsify each finding;
5. repair confirmed defects;
6. add a negative fixture plus positive control;
7. rerun focused and full local gates;
8. only then promote to PROVEN / merge-complete.

## 5. Required decision

Material unresolved provider review evidence is a blocking acceptance input even when:

- pytest is green;
- the PR is mechanically mergeable;
- GitHub Actions is absent;
- the implementation looks coherent.

Provider review is not the semantic test owner, but a concrete review finding is evidence that must be adjudicated.

## 6. Forbidden shortcut

Do not use any of these as substitutes for adjudication:

- "256 passed";
- "PR CLEAN/mergeable";
- "review bot only commented";
- "Actions are optional";
- "F5 will polish it later";
- "the issue is probably cosmetic."

P1/P2 findings affecting safety, authority, path confinement, or core interaction behavior are not deferred polish.

## 7. Executable repair map

| Finding | Repair owner | Negative fixture | Positive control |
| --- | --- | --- | --- |
| output path escape | F4 report orchestration | path-like `output_name` rejects | simple custom filename publishes inside run dir |
| unknown protection relation | F1 model | future/unknown relation rejects | known UNRELATED/SELF paths retain expected traces |
| unknown scan completeness | F1 model | future enum rejects | COMPLETE/INCOMPLETE retain expected traces |
| byte-scale treemap collapse | F3 geometry | realistic byte-scale equivalence | ordinary deterministic geometry still passes |
| inert filter/search controls | F2 HTML | generated report contains working filter/search listeners | hostile markup remains literal/non-executable |

## 8. Counterfactual replay

If P100 had been applied before PR #9 merge:

```text
trigger:
  local tests green; PR appears ready

authoritative contradictory context:
  unresolved P1/P2 review findings on exact head

required judgment:
  completion claim is PARTIAL / REPAIR_REQUIRED, not PROVEN

required action:
  adjudicate findings -> add fixtures -> rerun tests -> merge only after zero material unresolved findings

counterfactual outcome:
  PR #9 would not have been terminally merged in its reviewed state.
```

## 9. Proof ceiling

Until the repair branch is locally validated and integrated:

- F1–F4 implementation remains present on main;
- prior 256-test evidence remains historical proof of its encoded cases;
- F1–F4 **clean completion is invalidated** by confirmed untested defects;
- F5 is not the correct immediate owner for these defects;
- F6 remains untouched.

## 10. Return condition

After repair integration:

- all five PR #9 findings are repaired or disproven;
- each confirmed defect has regression coverage;
- focused + full local suite are green;
- patch hygiene is clean;
- PR #9 review threads are replied to with repair evidence and resolved;
- refreshed main contains the repair.

Then F5 may resume from the repaired F1–F4 floor.
