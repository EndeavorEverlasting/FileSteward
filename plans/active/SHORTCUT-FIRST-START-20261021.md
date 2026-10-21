# Shortcut-first FileSteward launch: runtime recovery / one-click entry

Date: 2026-10-21. This continuation belongs to the existing PR #68 and current Downloads-first product objective. No new app router, port registry, background service, GitHub Actions scheduler, or second checkout is authorized.

## Trigger and concrete observed failure
Cursor's browser shows \`http://127.0.0.1:50315/\` with \`ERR_CONNECTION_REFUSED\` after the previous preview server stopped. The address was a runtime receipt, not a durable application locator. The worktree candidate is 0.19.0; canonical main still lacks PR68, and \`FileSteward-source.cmd\` downloads and runs **main**, not a draft PR. A browser bookmark is not equivalent to an installed application shortcut.

## Implemented in this continuation
- \`scripts/windows/Install-FileSteward-Shortcut.ps1\`: opt-in one-time Windows installer for a Start Menu + Desktop \`.lnk\`, anchored to the already-authorized canonical checkout or current canonical worktree. It validates/creates an isolated venv, installs the local source into it, checks entrypoint availability, preserves unknown preexisting shortcut targets and uses \`pythonw.exe -m filesteward.cli launch\`. \`-StartMenuOnly\` and \`-NoLaunch\` are available. It is not a Windows release installer; no user storage scan runs.
- \`tests/test_windows_shortcut_launcher.py\`: static regression guards against ephemeral URL shortcuts, guessed worktrees, and cleanup/scheduled-task side effects. They **do not** establish native .lnk proof.
- \`docs/local-start.md\`: source/preview distinction, exact install command, failure/recovery, and direct start shortcut semantics.

## Operator-facing behavior
1. The first install invokes the script from the current PR68 worktree; it creates \`FileSteward (Preview)\` shortcuts rather than launching an obsolete published executable or copying an expired URL.
2. Clicking the desktop/Start Menu shortcut starts an independent Pythonw process without foreground terminal windows. The app's existing lock/health logic either reopens a valid running instance or binds a new loopback port and opens the browser.
3. The browser tab may remain open after the app closes, but that tab is not a launch authority. Clicking the shortcut relaunches. Merely launching shows the welcome and discovers the folder; personal Downloads are **not** scanned.
4. Once PR68 is proven/merged and the canonical main contains the feature, run this installer from \`dev\FileSteward\` to create the official \`FileSteward\` shortcut. Preserve the preview link until the canonical experience is verified; then retire it by explicit owner disposition.

## Immediate safe local agent gate
- Refresh provider PR #68 and the exact worktree. If the worktree has operator edits, preserve/commit/reconcile them; never reset/clean.
- Fast-forward the local PR68 worktree only after those edits are preserved. Read \`AGENTS.md\`, \`docs/agent/CANONICAL-PATHS.md\`, this file, and \`docs/local-start.md\`.
- From interactive Windows PowerShell on the host, invoke \`scripts/windows/Install-FileSteward-Shortcut.ps1 -NoLaunch\`. An actual \`.lnk\` must be read back through WScript.Shell; assert its target is the verified worktree \`.venv\Scripts\pythonw.exe\`, arguments \`-m filesteward.cli launch\`, and working directory is the correct worktree.
- Close only the FileSteward app via the app's own Close control, then launch by double-clicking the actual shortcut in Explorer/Start. Verify: no console flashes in front, a new reachable URL opens, native process remains after the shortcut/installer exits, launch is no-scan, reload works while running; a second click reopens same instance rather than creating a second server. Explicit Close then shortcut must relaunch with any new port. Record process identity and loopback health in ignored receipt.
- Prove error cases against a synthetic isolated checkout: missing Python, absent/incomplete venv, noncanonical path, linked ancestor, existing conflicting shortcut, and blocked PowerShell policy. No user shell link should be overwritten by test cases.
- If native interaction is unavailable, report \`NATIVE_SHORTCUT_ACCEPTANCE_UNPROVEN\`; do not promote static checks or remote commits to live launch proof. Continue the separate isolated Windows KnownFolder/native picker acceptance gate for PR68.
- Later integrate through PR68's existing review/merge sequence only after all original native gates are met. Preserve other branch/lane work.

## Proof status
- Design and source implementation committed to PR68; GitHub branch verified.
- No native Windows \`.lnk\` has been installed or clicked by this remote connector session.
- No user-local server can be started by GitHub, and the old \`127.0.0.1:50315\` page will remain unreachable until an actual local launch.
