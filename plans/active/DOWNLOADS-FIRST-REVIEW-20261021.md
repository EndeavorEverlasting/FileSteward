# Active sprint: Downloads-first onboarding and one-click review

**Parent outcome:** Ordinary FileSteward users must never need to type an absolute path to begin a normal Downloads review. OS knows the default; FileSteward performs deterministic technical discovery; the person makes one deliberate read-only review choice. No user-specific path decision, no automatic personal scan. See [exact design](../../docs/program/downloads-first-review.md) and [machine contract](../../harness/contracts/downloads-first-review.v1.json).

## Proven baseline (main at sprint inception)

- Provider: `EndeavorEverlasting/FileSteward`, `main@9bc065a853c280e34477496c9d8f972c11348aff`.
- Installed application storage is already locked to Windows KnownFolder LocalAppData; the source checkout/worktree contract is separate.
- Current `launch.py` admits explicit absolute `{"scan_root": "..."}` through `admit_scan_root`, `CurrentScanScope`, the local Host/Origin/session token checks, and single-scan lock.
- Current `web/launch.html` exposes a path-entry field and requires a *second* manual "Open current review" click.
- Existing synthetic tests validate the scanner, captured-run downgrade, admission, ownership gaps, Windows runtime profile and browser Atlas journey.
- PRs #59 and #64 own separate Downloads scheduling/agent classification; #67 owns cross-repository artifact-location work. Avoid those mutation surfaces.

## Scope

**Owned:** server-scope recommendation capability; scoped admission token and drift guard; an interactive Windows native *directory picker adapter* for secondary choice; welcome page copy/buttons/one-click continuation; contract/test/doc synchronization.

**Forbidden:** personal-filesystem observation without user action, broad C: traversal, installs/moves/deletes/quarantine, cloud upload, scheduling, PR29 whole-branch import, classification or judgment-policy rewrite, weakening current admission/root protections, release publication without independent gates.

**Boundary:** The user has approved **designing and testing** a safe workflow, not scanning their actual workstation. Only isolated synthetic profile/folders may be used for live tests. Windows-specific proof on a host needs an explicit synthetic test profile; do not substitute real user Downloads.

## Work split and strict completion

1. RED acceptance: `tests/test_downloads_first_review_acceptance.py` is new and deliberately fails on the missing route/adapter. Retain the original launch and scene tests; never hide missing behavior behind skips/xfails.
2. Server: expose `launch.windows_downloads_known_folder()` as the OS-owned resolver; GET recommendation is inert; a single-use token binds known-folder source and stable identity; POST rechecks, invokes existing scanner only on deliberate activation. Keep legacy `{"scan_root": ...}` use tests and explicit CLI compatible.
3. Picker: OS-native folder choosing on Windows, no HTML `webkitdirectory` misuse. Cancelling has no scan; selection shows exact target and a separately labeled review action.
4. Browser: primary `#review-downloads`; keyboard/touch parity, narrow/forced/reduced mode; automatic transition to current Atlas after verified READY/PARTIAL/EMPTY. Show errors in place and never invent percent-complete.
5. Contract: keep read-only profile and scope authority separate, mark default unavailability when redirected into forbidden/linked roots, reject drift, preserve current ownership gaps and capture downgrade.
6. Proof: focused tests -> full relevant suite -> actual browser click proof on four viewport/motion modes -> Windows synthetic KnownFolder+picker proof -> reconcile provider review and integrate only after gates pass.
7. Closeout states separately: contract designed, tests committed, implementation, local validated, pushed, PR open, merged, Windows live proven, released. None may be inferred from another.

## First executable agent action

Read AGENTS.md, canonical paths and new contract. Refresh the exact branch/head and open PR; implement the smallest compatible server-owned KnownFolder recommendation and token flow until the first acceptance tests pass. Reuse `CurrentScanScope`, never create another scanner or copy its safety checks. Then implement welcome, picker, browser journey and maintainability regression tests. Re-run all retained tests before integration.

### Current progress

- **DESIGNED**: deterministic user flow, token protocol, screen copy, explicit states, 16 invariant families.
- **TESTS AUTHORED**: contract guards and intentionally RED behavioral acceptance tests (synthetic). No repo test runner or Windows host is accessible from this remote connector session, so no green verification is claimed.
- **NOT IMPLEMENTED:** Windows resolver/API, native picker, browser one-click navigation. The PR remains draft pending implementation/validation; no real user storage was read.

## Local implementation ownership and proof admission

Provider refreshed at main9bc065a and design PR68 head dd9388ea; required PR66
slice is an ancestor and its scene/current-review/runtime contracts remain present.
Use this existing design branch as convergence owner, not a parallel replacement PR.

- OS adapter writer: isolated downloads-os-20261021 worktree/branch; new
  src/filesteward/windows_folders.py and tests/test_windows_folders.py only.
  Expose windows_downloads_known_folder()->Path and pick_windows_folder()->Path|None.
  OS KnownFolder/modern native picker; no guessed paths or scanning; no runtime
  profile mutation. Use scoped synthetic providers/native dialog proof, never scan
  real Downloads. Root reexports both seams from launch.py for acceptance injection.
- Welcome writer: isolated downloads-welcome-20261021; web/launch.html and new
  tests/test_downloads_welcome_browser.py, plus adapt tests/test_current_review_browser.py
  to the explicitly redesigned first-click flow while retaining Atlas/Chamber and
  evidence/geometry controls. No launch.py/OS adapter/acceptance contract mutation.
- Coordinator: launch.py backend and server-bound single-use tokens, additional
  protocol/safety tests, acceptance convergence, docs/AGENTS/version/regression ledger,
  canonical plan/handoff. No direct sibling source edits until completed commits rejoin.

All lanes fork the same pinned committed design floor and use their own virtual
environments, ignored runtime trees and ephemeral ports. Primary owns convergence,
provider reviews, exact proof and integration. Existing explicit scan_root API stays
compatible; normal UI removes path entry and second-open friction. Preserve original
CurrentScanScope instances from display through click, rather than re-capturing a
substituted path. Scope tokens are memory-only, session-bound, one-use, expire600s;
drift fails before factory construction. Choosing is not review authorization.

Acceptance: RED baseline -> green deterministic API + native adapter tests -> real
synthetic one-click browser navigation in supported modes -> retained full floor,
wheel/version guard, exact review and merge. Startup/OS discovery never traverses
Downloads or constructs ownership collectors. Actual Windows discovery/native dialog
proof is separate from mocked API proof; report unavailable interactive proof rather
than pretending mocked selection is live. No real Downloads scan is authorized.
