# FileSteward Product Versioning

**Authority:** `[project].version` in `pyproject.toml`  
**Current cutover version:** `0.1.0`  
**Status:** P130 repository versioning system established for future changes; no release tag is created by this sprint.

## Purpose

FileSteward needs one human-friendly product version that advances when shipped product behavior changes, including visual/aesthetic work. Exact Git commit and artifact identity remain the forensic proof of what actually ran.

Schema, protocol, plan, and contract versions remain independently owned by their own compatibility contracts. A visible `v2`/`v3` design label is not a product release version.

## Scheme

FileSteward uses SemVer while the Python package and operator-facing product share one release identity.

During pre-1.0 development:

- **PATCH** — compatible fix or accepted aesthetic polish that does not add a new interaction capability;
- **MINOR** — new user-visible capability, scene, navigation/input language, or pre-1.0 incompatible behavior that requires explicit migration notes;
- **MAJOR** — reserved for the 1.0 compatibility boundary and later SemVer-breaking releases.

## No-bump changes

These do not advance the product version by themselves:

- docs/research/plans only;
- tests only;
- internal refactor with unchanged product behavior;
- generated evidence/receipts;
- schema/protocol version changes whose product behavior did not change.

## Visual-change automation

`scripts/versioning.py` recognizes the shipped visualization surfaces:

- `src/filesteward/visualization/**`
- `docs/program/storage-reclaim-visual-system.tokens.json`

Before validating/committing a visual product change, run one of:

```powershell
python scripts/versioning.py ensure-visual-bump --base origin/main --kind visual-polish
python scripts/versioning.py ensure-visual-bump --base origin/main --kind visual-feature
```

The command is idempotent for the same accepted change set:

- if no visual product surface changed, it does nothing;
- if the branch already advanced beyond the base version, it does not bump again;
- if visual product surfaces changed and the version did not, it advances the canonical version;
- when run before commit, staged and unstaged visual edits are included in the decision.

The merge/readiness guard is:

```powershell
python scripts/versioning.py guard --base origin/main
```

It fails when shipped visualization changed without a higher product version.

## Current Memory Atlas transition

The Memory Atlas v3 design phase does not bump the product merely because a design document exists.

The first runtime v3 implementation should run:

```powershell
python scripts/versioning.py ensure-visual-bump --base origin/main --kind visual-feature
```

With the current `0.1.0` base, that yields `0.2.0`.

Later accepted visual-only polish on a `0.2.x` floor uses `visual-polish` and increments PATCH.

## Tags and releases

At the time this system was established, GitHub exposed no releases and no existing tag namespace was found. Do not rewrite history or manufacture retroactive releases.

A future release executor may create `vX.Y.Z` only after:

1. the exact candidate passed repository-owned validation;
2. the product version guard passes;
3. the tag resolves to the exact validated release commit/artifact;
4. repository release/promotion authority allows publication.

## Rollback

Rollback means restoring/redeploying a previously identified commit/artifact. Never decrement or reuse a published version number.

## Proof boundary

The versioning script and its tests prove deterministic version calculation and the visual-change gate. They do not prove a release was published, installed, or observed at runtime.
