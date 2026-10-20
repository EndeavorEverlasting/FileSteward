# Update and open the local FileSteward website

Download the readable [FileSteward-source.cmd](https://github.com/EndeavorEverlasting/FileSteward/raw/refs/heads/main/FileSteward-source.cmd), save it, and double-click it. This is the source update launcher: each run downloads the current `main`, installs the application into its own Python environment, and opens the local welcome page in your browser. Keep its console open while using the app. Use **Close app** on the welcome page to stop it.

You need Git for Windows and Python 3.12 or newer, including the Windows `py` launcher. Administrator access is not needed. If a prerequisite is missing, the CMD names it and stops. The [released Windows preview](windows-start.md) is the separate option that requires neither Git nor Python; its release CMD remains pinned to a published executable and does not update source.

The source launcher always uses `%USERPROFILE%\dev\FileSteward` and its ignored `.venv`. It clones an absent checkout, or verifies the existing checkout's origin and clean `main` before a fast-forward update. It refuses modified files, untracked source files, unpublished commits, other branches, linked paths, and unrelated repositories. It never resets, cleans, stashes, or overwrites your work. If it refuses an update, preserve and reconcile the displayed checkout state before retrying. A failed or offline fetch stops launch rather than silently claiming the newest version.

If you already have the repository, the same command is available from a Command Prompt:

```bat
"%USERPROFILE%\dev\FileSteward\FileSteward-source.cmd"
```

On first startup, choose **Explore sample** to enter the Memory Atlas and Decision Chamber with illustrative data. To view captured storage evidence, choose an existing FileSteward evidence folder in the welcome page. The import accepts the six observational artifacts, validates them, and opens a read-only review. Your source checkout's private runtime records remain under ignored `var`; the installed preview uses its separate LocalAppData runtime.

Startup does not scan personal folders, grant action approval, delete files, or register recurring tasks. Imported evidence describes a past observation. Current live ownership collection and semantic application/repository execution adapters are not yet connected to the welcome app; this source launcher does not fill those product gaps. Exact approval, fresh preflight, execution receipts, and measured reclaim remain separate gates in the repository-owned deletion path.

If the page is already open, use **Close app** before updating, then rerun the CMD. The application can reuse a local session, but the source updater requires it to be closed so your browser observes the newly updated code. Server addresses use `http://127.0.0.1` with a locally assigned port and are printed in the console. If the browser does not open automatically, copy that printed address into it.
