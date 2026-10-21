# Update and open the local FileSteward website

Download the readable [FileSteward-source.cmd](https://github.com/EndeavorEverlasting/FileSteward/raw/refs/heads/main/FileSteward-source.cmd), save it, and double-click it. This is the source update launcher: each run downloads the current `main`, installs the application into its own Python environment, and opens the local welcome page in your browser. Keep its console open while using the app. Use **Close app** on the welcome page to stop it.

You need Git for Windows and Python 3.12 or newer, including the Windows `py` launcher. Administrator access is not needed. If a prerequisite is missing, the CMD names it and stops. The [released Windows preview](windows-start.md) is the separate option that requires neither Git nor Python; its release CMD remains pinned to a published executable and does not update source.

The source launcher always uses `%USERPROFILE%\dev\FileSteward` and its ignored `.venv`. It clones an absent checkout, or verifies the existing checkout's origin and clean `main` before a fast-forward update. It refuses modified files, untracked source files, unpublished commits, other branches, linked paths, and unrelated repositories. It never resets, cleans, stashes, or overwrites your work. If it refuses an update, preserve and reconcile the displayed checkout state before retrying. A failed or offline fetch stops launch rather than silently claiming the newest version.

If you already have the repository, the same command is available from a Command Prompt:

```bat
"%USERPROFILE%\dev\FileSteward\FileSteward-source.cmd"
```

On first startup, **Start with Downloads** shows your Windows Downloads location, discovered through the operating system even when relocated. **Review Downloads** starts one read-only review of names, sizes, dates, folders and ownership evidence, then opens its Memory Atlas automatically. File contents stay closed; nothing is moved or deleted. Opening the app and discovering the location do not scan. **Choose another folder** opens the native Windows folder picker; selecting a folder only displays its scope. **Review selected folder** starts that review. Canceling the picker does nothing. If Downloads is missing, inaccessible, linked or excluded by the folder safety contract, the app explains why and offers the picker or sample without silently choosing a different location. **Explore sample** enters the Memory Atlas and Decision Chamber with illustrative data. Metadata completion and ownership coverage are separate: missing ownership checks are listed and cannot authorize reclaim. Known protective application and repository evidence survives partial collection.

To view captured storage evidence, choose an existing FileSteward evidence folder. The import accepts the six observational artifacts, validates them, and opens a read-only review. Samples and imported evidence remain observational even if a path happens to match a current folder. A current review belongs to the process that created it; after restart it becomes historical and needs a new explicit metadata review. Private runtime records remain under ignored `var`; the installed preview uses its separate LocalAppData runtime.

Current ownership collection uses native Windows uninstall registration and the existing repository adapter. Runtime, service/task, package, toolchain, user-data and regeneration coverage is not yet complete; those gaps remain visible in the Chamber. No location, filename, size, age, absent owner or user checkbox makes a file reclaimable. The production collector currently supplies no regeneration proof, so a successful folder review does not imply that raw deletion is available. Semantic application/repository actions still require their owning execution adapters.

For an original validated scanner run, the CLI can explicitly request current evidence with `filesteward review <run-directory> --scan-root <absolute-folder> --current-evidence`. Supplying `--scan-root` alone retains the existing unresolved resolver. Launcher-marked sample/import/captured runs remain observational through CLI review and reject `--current-evidence`; start a new folder review in the local app to admit current data. Current facts feed the existing scene script and safety reducers; exact action approval, fresh preflight, execution receipts and measured reclaim remain separate gates in the repository-owned deletion path.

Startup does not grant action approval, delete files, inspect file contents, call a model or register recurring tasks.

If the page is already open, use **Close app** before updating, then rerun the CMD. The application can reuse a local session, but the source updater requires it to be closed so your browser observes the newly updated code. Server addresses use `http://127.0.0.1` with a locally assigned port and are printed in the console. If the browser does not open automatically, copy that printed address into it.
