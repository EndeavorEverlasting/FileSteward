# Canonical artifact placement — workstation contract

**Owner:** FileSteward (location/ownership classification), not the master content for other projects. This guide is subordinate to `docs/agent/CANONICAL-PATHS.md`, `harness/contracts/storage-ownership-evidence-graph.v1.json`, and other owning repositories' governance. This is a *read-only placement* workflow, not an organization, sync, cleanup or deployment tool.

## Authority by type

- **Git-tracked canonical contract:** the owning repo's tracked path, and its normal mutable checkout under `<USERPROFILE>/dev/<repo>` **only after host Git identity and current revision are proved**. Worktrees (`dev/worktrees/<repo>/<lane>`), backups, OneDrive-mapped copies and old checkout copies are not authoritative replacements. No second editable global master.
- **External research master:** Google Drive Upstream Intelligence Library. Master resides in Drive; FileSteward merely locates an **optional** exact-source export at `<USERPROFILE>/dev/_shared/canonical-artifacts/upstream-intelligence/source-registry.json` — a new **proposed workstation shared-reference root**, not a checkout, installed app root, backup, or Git authority. Does not claim any workstation already has it. This shared root must not be used for credentials, private inventories, database state, profile captures, or generated app/runtime output.
- **Offline snapshot proof:** `source-registry.provenance.json` adjacent to the file, with `schema`, `source_url`, `sha256`, and `captured_at`. The FileSteward read-only probe hashes the exact file and checks sidecar binding, *not* Google Drive freshness or content trust. Import/sync is a separate provider-authorized workflow. Snapshot destination is replaceable; do not move/rename originals to satisfy it. Prefer atomic verified publication by the owning source adapter in a later sprint.
- **Private FileSteward placement observations:** FileSteward's own ignored `var/artifact-placement/<host_alias>.<UTC>.json` only in the admitted normal checkout. These contain local paths and never belong in a Git commit, a public cloud folder, or the shared-reference cache.
- **App runtimes:** kept in each application's declared AppData/private runtime, *not* this reference snapshot root. FileSteward installed app runtime is separately governed by `src/filesteward/contracts/runtime-profile.v1.json`.

## Steps (DTop and PTop independent)

From the **actual** canonical FileSteward checkout with the intended host's account:

```powershell
python -m filesteward.placement --host-key DTop --check
python -m filesteward.placement --host-key DTop --probe --save-private
# On the separate laptop:
python -m filesteward.placement --host-key PTop --probe --save-private
```

The default console response redacts the actual profile directory. The private JSON receipt contains exact resolved paths, actual hostname, per-artifact state and missing/conflated ownership evidence. `--probe` only checks explicit paths and local Git root/origin; no recursive broad scan, network, Google credential discovery, user-file hash scan, symlink traversal, file move, deletion, schedule or installation. `--save-private` is optional and writes once to an ignored runtime path, refusing an unsafe root or existing receipt. A host alias is not hardware authentication.

## Outcome interpretation

| State | Meaning | Allowed next step |
|---|---|---|
| `PROPOSED_NOT_OBSERVED` | Calculated candidate only | Probe on actual machine |
| `DEV_ROOT_MISSING` / `REPO_NOT_OBSERVED` | Required canonical dev/repo root not established | Recover approved checkout; do not substitute Desktop/OneDrive |
| `GIT_CONTRACT_MISSING` | Expected artifact absent in actual checkout | Check remote PR/branch vs `main`; do not invent a file |
| `LOCAL_GIT_CONTRACT_PRESENT` | Exact checkout root and origin matched, file exists | Compare local SHA/branch to remote before claiming current |
| `SNAPSHOT_MISSING` | Shared export absent | Safe adapter can offer an authorized staged copy separately |
| `SNAPSHOT_UNVERIFIED` | Bytes exist, but provenance incomplete | Recover/import authenticated source provenance before usage |
| `SNAPSHOT_HASH_CONFLICT` | Bytes differ from provenance | Preserve file, no overwrite, investigate |
| `SNAPSHOT_INTEGRITY_PROVED_FRESHNESS_UNKNOWN` | Verified local bytes and source binding | Use for offline read with captured timestamp; live cloud freshness still unproved |
| `UNSAFE_ROOT` / `GIT_OWNER_CONFLICT` | Risk of redirection or wrong ownership | Stop placement, preserve content and investigate |

## Agent discovery / downstream handoff

Aliases: **canonical artifacts**, **source registry location**, **where does this contract live**, **upstream design offline**, **shared reference snapshot**, **local artifact inventory**. These are location intents, **not Prompt Kit P-number aliases**. A fresh Cursor/OpenCode agent reads `AGENTS.md` and this guide, runs the FileSteward locator and then treats the returned Git/source links as an index. Each consuming repo continues using its own `AGENTS.md`, TokenCorridor source resolver and proof receipts. No direct access to Google connector is assumed.

When the FileSteward repo is not checked out or Python is absent, a local agent may inspect the tracked placement JSON and request bounded host evidence; it must report `NOT_OBSERVED`, not assert a known working path. The read-only Google connector work in TokenCorridor PR #220 remains a separate live-certification gate. TokenCorridor design router PR #233 and ParallaxPort consumer PR #21 are distinct from placement, and their Git checks must be independently established before promoting to default branches.

**Hard gate before actual provisioning:** On each host, prove profile/hostname, canonical checkout root, safe physical destination and source revision. Do not create a folder or copy a source until a specific non-destructive provisioning workflow has its own manifest, collision handling, source SHA, and post-copy readback. Every path with multiple owners is protected by the most restrictive owner.

## Tests

```bash
python -m pytest tests/test_canonical_artifact_placement.py -q
python -m filesteward.placement --host-key DTop --check
```

The synthetic tests prove deterministic proposals, foreign-remote refusal, missing host roots, symlink/prohibited-root gating, per-host isolation, snapshot hash binding and stale snapshot caveats. They do not prove host installation, real DTop/PTop readiness, authenticated Drive, physical movement or application runtime acceptance.