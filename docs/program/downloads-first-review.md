# Downloads-first review — exact welcome UX (2026-10-21)

Status: **contract and test-first design; not an implementation/live-proof claim**. Canonical machine-readable owner: [downloads-first-review.v1.json](../../harness/contracts/downloads-first-review.v1.json). Scope: FileSteward's *local welcome* and explicit first metadata review. Preserve [CANONICAL-PATHS](../agent/CANONICAL-PATHS.md), [LOCAL-AGENT-PROTECTIONS](../agent/LOCAL-AGENT-PROTECTIONS.md), [OPERATOR-DECISION-UX-PATH](../agent/OPERATOR-DECISION-UX-PATH.md), the existing scene workflow, and current folder-admission/scanner machinery.

## What "one click" means

After normal app launch, **one activation of Review Downloads** starts one explicit, bounded, recursive, metadata-only review of the current Windows user's OS-registered Downloads folder, and **automatically enters the existing current-review experience** when the job returns READY, PARTIAL, or EMPTY. The user does *not* need to type a path, approve a redundant modal, or click "Open current review" afterward. Background discovery during page load is allowed; scanning is not. The click is authorization for only this disclosed review scope—not file contents, moves, deletion, upload, recurrence, or future rescans.

### Exact screen copy and hierarchy

Place this main card in the welcome page's first visible content region, visually coequal with the existing sample experience. The known-folder candidate is derived on the **server**. Keep the existing warm material/typographic identity; do not replace the Atlas or Decision Chamber.

| Element | Required accessible text / behavior |
| --- | --- |
| Eyebrow | **Your starting point** |
| Heading | **Start with Downloads** |
| Body | "Review names, sizes, dates, folders, and ownership evidence in Downloads and its subfolders. File contents stay closed. Nothing is moved or deleted." |
| Scope label | "Folder: <OS-resolved path>" — render as text, never interpolated HTML |
| Primary button | **Review Downloads** (\`id="review-downloads"\`); enabled only after safe scope discovery |
| Secondary | **Choose another folder** (\`id="choose-folder"\`) |
| Sample | Keep **Explore sample**, clearly labeled synthetic |
| Boundary | "Opening FileSteward never scans your files. This review reads metadata only." |

The literal displayed path is **not a client-authored authority**. Do not label an unsafe/inaccessible location "ready" or guess a replacement Downloads path.

### Interaction transcript

\`\`\`text
LAUNCH app
  -> welcome page; no personal scan, no collector construction, no recurring task
  -> server resolves SHGetKnownFolderPath(FOLDERID_Downloads) and checks eligibility
  -> WELCOME_READY: visible path + Review Downloads
     or WELCOME_UNAVAILABLE: localized, actionable reason + Choose another folder / Explore sample

USER activates Review Downloads by click, Enter, or Space
  -> one authenticated POST with opaque session-bound scope token
  -> server re-resolves OS KnownFolder and compares original path/identity
  -> existing admit_scan_root + CurrentScanScope enforce scope/linked-path/ancestor checks
  -> one worker via existing current-scan lock; no second confirmation
  -> READING: busy action, progress text without invented percent, no misleading success
  -> READY/PARTIAL/EMPTY: persist canonical run receipt and automatically open current review
       PARTIAL preserves explicit gaps; EMPTY shows a truthful empty experience
  -> ERROR: remain on welcome, show cause, offer fresh retry, never auto-retry/auto-broaden

USER activates Choose another folder
  -> Windows native directory picker (interactive desktop session), NOT browser webkitdirectory
  -> cancel: unchanged welcome, zero scans
  -> select: show exact chosen path, purpose and "Review selected folder" button
  -> pressing that button uses same guarded admission/review path (the picker alone never scans)
\`\`\`

Browser file inputs and \`webkitdirectory\` provide selected files/relative names; **they do not grant a trusted absolute directory path**. Do not repurpose the existing evidence *import* picker for choosing a scan root. The Windows picker must be hosted by the trusted local app through a native directory-picker adapter (e.g. \`IFileOpenDialog\` with \`FOS_PICKFOLDERS\` on an appropriate STA thread); it must not create a generic, remotely callable filesystem browsing API. On a noninteractive host return PICKER_UNAVAILABLE and offer the sample; do not guess paths.

## API and authority, not just a button

The contract specifies:

- \`GET /api/v1/launch/recommended-scope\` — **discovery only**. It returns an opaque, memory-only, single-use scope token bound to the OS-resolved path and stable directory/ancestor identity, a display path, an eligible flag, and a reason if unavailable. No run, scan, ownership collection, or source-content read.
- \`POST /api/v1/launch/current-scan\` body \`{"scope_token":"..."}\` — admitted by the **existing Host + Origin + session-header** checks. The token is not a browser statement of eligibility. On use, verify session, expiry (<= 600 s), whether consumed, KnownFolder resolution, eligibility and identity again; then run the existing \`begin_current_scan\` / \`CurrentScanScope\` path. Do not weaken the current legacy explicit \`{"scan_root":"..."}\` test/CLI path while migrating UI.
- \`POST /api/v1/launch/choose-folder\` — explicit request to launch **native** Windows picker; returns cancellation or a *server-derived* selected path/token for separate review activation. It must not start scanning when the picker merely closes.

Tokens are capability-style references, not privileges to delete. The server owns path facts and observed identity. The browser owns deliberate activation and feedback. An OS known-folder change, disconnected/reparse target, changed ancestor, stale token, or failure to resolve is an actionable refusal and fresh-scope recovery—not a fallback to environment variables, \`cwd\`, \`USERPROFILE\Downloads\`, Desktop, OneDrive, or a whole drive.

The installed app data location stays exactly as defined by \`windows-localappdata/v1\`: \`SHGetKnownFolderPath(FOLDERID_LocalAppData)\FileSteward\runtime\var\`. Source/editable checkout and worktree layout remain governed by CANONICAL-PATHS; scan targets never become app data destinations. No personal absolute paths, filenames, or run artifacts go into Git.

## State/feedback contract

| State | Button behavior | Feedback | Continuation |
| --- | --- | --- | --- |
| Discovering | Disabled "Finding Downloads…" | Explain OS folder discovery | READY or UNAVAILABLE |
| READY | Enabled "Review Downloads" | Path and exact read-only scope visible | one authorized scan |
| UNAVAILABLE | Disabled or absent primary | "Downloads is not available for a safe review. No files were scanned." + concrete reason | Alternate folder/sample |
| READING | Disabled, \`aria-busy=true\` | "Reading Downloads metadata and ownership evidence…" | READY/PARTIAL/EMPTY or ERROR |
| READY result | No extra "Open" click | Show result count and truthful complete/incomplete status | automatic existing review open |
| PARTIAL result | No extra "Open" click | Missing metadata/ownership stays unresolved | automatic review with gaps visible |
| EMPTY result | No extra "Open" click | "No entries to review" | existing empty review |
| ERROR | Re-enabled fresh retry when safe | Error cause; "No action was applied" | re-discover only on explicit retry |
| Picker canceled | unchanged | optional "No folder selected" | no scan |

Use \`role=status\`/\`aria-live=polite\` for progress, \`role=alert\` for errors, focus management on error, native keyboard actions, adequate hit sizes, reduced-motion and forced-colors fallbacks. An automatic navigation must not lose the partial/incomplete evidence warning in the destination. No fake progress percentages, indefinite spinners without error handling, cross-origin navigation, or "success" before authoritative run readback.

## Acceptance gates

The executable initial suite is \`tests/test_downloads_first_review_acceptance.py\`. The machine-readable contract lint is \`tests/test_downloads_first_review_contract.py\`. The former is **expected RED until the endpoints/UX exist**; never mask missing behavior with xfail/skip to claim a green release.

| ID | Test / proof | Pass criterion |
| --- | --- | --- |
| D01 | GET /, state, recommended-scope | no scanner/collector, source file read, run artifact or schedule |
| D02 | real headless browser click | exactly one activation starts one job then automatically navigates; no "Open current review" second click |
| D03 | synthetic file tree | scope precisely Downloads and descendants; metadata-only, files byte-identical, no action artifacts |
| D04 | KnownFolder monkeypatch | relocated and nonstandard usernames resolve via OS API; \`USERPROFILE\`, \`cwd\` and EXE are irrelevant |
| D05 | bad scope fixtures | forbidden, linked/reparse, missing, inaccessible, volume root refuse with no scan |
| D06 | rename / OS path drift | mismatch between discovery and click refuses *before* scanner construction |
| D07 | forged token/body | no client-provided eligible flag, forged path, expired/consumed token may authorize default scan |
| D08 | Origin, Host, CSRF/session header | unauthorized POST rejected without side effects |
| D09 | duplicate click / concurrent worker | at most one current-scan job; retries are explicit |
| D10 | historical run, sample, import | all remain observational; no recency-based fresh-ownership upgrade |
| D11 | runtime hooks/probes | zero content reads, moves, quarantine, deletion, upload, recurrence |
| D12 | runtime profile tests | FileSteward runtime stays in OS LocalAppData; target folder untouched |
| D13 | Playwright desktop, 390px, keyboard, touch, reduced motion, forced colors | accessible usable state; complete journey; no JS errors |
| D14 | native picker cancel | zero scan; selection returns to a clearly disclosed selected-root review action |
| D15 | missing owner/protection evidence | no deletion/reclaim/action elevation; real uncertainty visible |
| D16 | app restart | prior read becomes captured, not newly authorized; new real review requires one new activation |

Local quality gates: retained \`tests/test_launch.py\`, \`tests/test_launch_current_review.py\`, \`tests/test_current_review_browser.py\`, \`tests/test_installed_runtime_profile.py\`, \`tests/test_scene_composition_contract.py\`, and \`tests/test_decision_ux_continuity.py\`. Browser proof must capture the real start->busy->review transition and keyboard/narrow behavior; static HTML presence is insufficient. Runtime proof on Windows must use an isolated synthetic/profile test environment and **must not scan an operator's personal Downloads without explicit authorization**.

## Engineering handoff / convergence

Own these surfaces: \`launch.py\` welcome route/backend, a scoped Windows KnownFolder/picker adapter, \`web/launch.html\`, associated tests, and this contract/doc. Do **not** touch classification, deletion executors, scheduling, ownership judgment policy, release assets, or Pixel/Atlas scene authority unless an evidenced acceptance failure demands the narrowest compatible repair. Preserve the current \`{"scan_root": ...}\` compatibility until migrations/tests are proven.

Sequence: RED acceptance -> OS resolution and session-bound scope service -> green API tests -> accessible single-click welcome -> green browser proof -> full retained safety suite -> exact-head review -> authorized integration -> Windows synthetic runtime proof. Integration and published release are distinct; no declaration of live proof from a contract or PR alone.
