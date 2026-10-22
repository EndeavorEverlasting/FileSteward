# Immersive folder navigation — 2026-10-22

Status: **implemented on stacked source branch; not integration-, Windows-, or operator-live-proven**.

## Parent objective and recovered truth
- Operator bootstrapped FileSteward on Admin Box 1, saw the current 0.18.0 absolute-path welcome input, and rejected typing a directory as normal onboarding.
- Source PR #68 (0.19.0) already implements OS KnownFolder Downloads recommendation, server-issued single-use scan scopes, a deliberate Review action, and an optional native Windows chooser. It is **draft and not on main**.
- This sprint builds **on PR #68's exact head**, without modifying its branch or bypassing its pending isolated Windows native-dialog proof.
- Operator prefers selection inside the application's own immersive interface rather than invoking Explorer or a Windows dialog.

## Desired journey
1. Welcome: **Review Downloads** remains a first-class one-click explicit metadata-review action.
2. **Browse folders here** expands an integrated navigator within the FileSteward page, with no focus switch to Explorer.
3. Locations are identified on the server: OS Downloads, current profile directory, and available Windows drive roots. No frontend-provided absolute path is admitted.
4. User opens one directory at a time and navigates backward or to Locations. Only directory names are shown, never file names or file contents. Protected and linked folders are excluded.
5. **Use this folder** shows the exact selected scope on the welcome page. This is a *selection*, not a scan.
6. **Review selected folder** is a separate deliberate action using PR #68's original single-use scan token and fresh identity checks. Current Atlas opens only after the review completes.
7. **Windows folder picker** remains an optional fallback for inaccessible/oversized directories or an operator preference. It is no longer the primary alternative.

## API and trust boundary
- New POST \`/api/v1/launch/folder-browser\` reuses local Host/Origin/session-header admission.
- Actions: \`roots\`, \`open(token,page)\`, \`select(token)\`. Input paths and action claims are rejected.
- Navigation handles are memory-only, session-bound, expiry-bound, and tied to verified directory/ancestor identities.
- Listing is shallow, paginated, bounded, links/reparse points denied, filenames excluded, no recursive scan. Protected roots reuse existing policy.
- Selecting calls the existing \`_offer_scope\`; scanning still requires independently authorized \`current-scan\`. None of the classifier, resolver, deletion, approval, or scheduler paths change.
- No implicit access to nonselected file contents or third-party model. Browse failures are visible; never silently fall back into scanning.

## Owned files
- \`src/filesteward/launch.py\` — host-side directory navigation and scoped selection.
- \`src/filesteward/web/launch.html\` — integrated browse panel, Location/Back/Next/Close controls, keyboard focus and navigation.
- \`tests/test_immersive_folder_browser.py\` — API/token/privacy/inertness regressions.
- \`tests/test_downloads_welcome_browser.py\` — six-mode browser journey.
- \`AGENTS.md\`, \`harness/contracts/immersive-folder-browser.v1.json\`, this plan, its handoff.

## Forbidden files / behavior
No edits to deletion/quarantine executors, task scheduler, runtime path contracts, private run contents, repository ownership inference, prior accepted cinematic scenes, or PR #68 head. Do not weaken the exact manifestation / ownership / live-proof gates.

## Acceptance and proof gates
- A0: fresh head contains the stacked parent PR #68 commit, parent still draft, no conflicting agent ownership.
- A1: Python compile/import and targeted pytest API suite pass (not run by connector-only authoring environment).
- A2: full tests and independent JSON contract load pass; existing Downloads/review/synthetic import behavior remains intact.
- A3: Playwright browser journey passes desktop 1440, narrow 390, keyboard, touch, reduced-motion, forced-colors; no console errors, overflow, lost focus, or accidental scan.
- A4: isolated Windows host live evidence: actual embedded navigator, location, scrolling, selection, focus/keyboard, and maintained sample/Downloads controls. Use **synthetic test tree only**. Explicitly verify zero scan before Review and one scan only after Review.
- A5: reconcile PR #68's existing Windows native picker/relocated KnownFolder acceptance; do not substitute this in-app journey for that unrelated evidence.
- A6: all material reviews/CI resolved; parent PR integrated, then rebase stacked feature from fresh main, rerun gates, merge and verify containment. Source CMD must then be rerun with app closed to update Admin Box 1; collect version and operator-live observation.

## Current evidence ceiling
Remote source edits and regression tests are committed on a stacked branch. **No local Python/pytest/Playwright process was invoked, no actual Admin Box filesystem browsed, and no app/PR was merged or deployed.** Actual P08 runtime proof remains the immediate blocker. The connector can inspect GitHub but cannot execute on Admin Box 1.

## Next agent entry
Read \`AGENTS.md\`, \`harness/contracts/immersive-folder-browser.v1.json\`, this plan, \`docs/program/downloads-first-review.md\`, \`plans/active/DOWNLOADS-FIRST-REVIEW-20261021.md\`, PR #68 and the stacked PR. Refresh provider refs, inspect patches and run acceptance gates A1-A6 in order. Repair failures on the stacked feature branch and preserve any other contributor work. Do **not** restart the design, silently merge an unproved candidate, or ask the user for a full folder path.
