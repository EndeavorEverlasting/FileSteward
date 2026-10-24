# Learning Workspace Recognition and Protection

## Objective

FileSteward recognizes user-authored teaching and learning environments even
when they are not Git repositories and no teaching desktop app is installed.
A folder holding lesson progression, learning records, research references,
tools, or upstream methodology is intentional user work. Such content is not
reclaimable merely because files are old, large, generated-looking, on a
secondary drive, or outside a project checkout.

## Synthetic examples

~~~text
X:\
  teach\
    reverse-engineering\
      MISSION.md
      METHOD.md
      GUIDANCE.md
      NOTES.md
      lessons\
      learning-records\
      upstreams\
    finance-literacy\
      START-HERE.md
      MISSION.md
      NOTES.md
      personal\
      businesses\
      reference\
      learning-records\
      lessons\
      upstreams\
  unrelated-lab\      (independent sibling)
~~~

These examples represent a dual methodology: file-oriented teaching materials
and an optional external teaching harness. Neither dependency is required.
A user can use Cursor and ordinary files; no desktop-app registry presence,
app install, external service or Git history is a prerequisite.

## Metadata-only detection

The current detector checks immediate entry names and types, never contents:

- MISSION.md plus at least two of METHOD.md, GUIDANCE.md, START-HERE.md,
  NOTES.md => **confirmed curriculum structure**.
- MISSION.md plus a supporting curriculum document and a directory among
  lessons/, learning-records/, upstreams/ => **confirmed curriculum structure**.
- MISSION.md plus one supporting document or one of those structural
  directories => **emerging curriculum structure**, already protected.
- A folder called teach, a solitary marker file, or a similarly named
  MISSION.md.bak does not prove a learning workspace. Generic businesses/
  or personal/ alone are not evidence of a curriculum.

These are structure-confidence labels, **not claims that a course is active,
completed, obsolete, or disposable**. Recognition is path-independent and
volume-independent. An explicit operator-protected root is also honored when
these signals are absent.

The detector walks directories once, does not follow symlinks, junctions or
reparse points, and does not read the contents of notes, tax records, budgets,
samples, lesson histories, or other private material. Unreadable nodes remain
unknown through the inventory completeness policy.

## Consequences for every workflow

1. **Scan:** use ProtectionIndex.from_workspace_discovery; identified
   classrooms and all descendants receive PROTECTED irrespective of broad
   regenerable-cache contracts or apparent duplicates.
2. **Composition:** the parent containing classrooms is an ANCESTOR; never
   nominate the whole parent for reclaim or relocation. Decompose siblings.
3. **Report:** emit source provenance learning-workspace:confirmed or
   learning-workspace:emerging in run.json protected roots and
   protected-exclusions.csv. Do not commit private content or real user paths.
4. **Action planning:** preserve lesson logs, scratch work, tools, references,
   upstream pins, guidance, generated exercise work, and learner notes;
   classification is not authorization to move, quarantine, or delete.
5. **Fresh delete gate:** execute-time preflight and deletion must rediscover
   learning roots from the scan root and union them with recorded protection
   roots. Newly created lessons cannot be removed using a stale older scan.
6. **Drive placement:** media type (SSD/HDD) is observation, not evidence that
   curriculum work can move. Per-app preferences and authorized relocation
   remain separate, not shipped by this detector. Even a seemingly
   regenerable cache inside a protected learning root is excluded until an
   explicit narrower policy is designed, reviewed and validated.
7. **App data:** a separate teaching app's local data home is application-
   managed, not automatically a classroom root. Its ownership, lifecycle,
   privacy and portability need an independent adapter; the presence or
   emptiness of that directory does not downgrade a folder-based curriculum.

## Review and validation

The synthetic tests exercise independent classrooms, emerging classrooms,
Git-plus-learning roots, path independence, sibling decomposition, broad
cache-contract conflict, symlink non-traversal, metadata-only discovery and
fresh delete-time rediscovery.

Run:

~~~powershell
python -m pytest -q tests/test_learning_workspace_protection.py tests/test_protection.py tests/test_disposition.py tests/test_delete_preflight.py
~~~

Then run the repository-owned full suite. Windows-specific junction tests and
real workstation observation remain separate proof boundaries. No user
filesystem scan, move or deletion is authorized by this feature.
