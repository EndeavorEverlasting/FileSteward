# Wispr Flow broken-install recovery — evidence-first runbook

## Incident state

FileSteward previously removed Wispr Flow's per-user installation tree. Windows still showed Wispr Flow installed and attempted to invoke `%LOCALAPPDATA%\WisprFlow\Update.exe`, which no longer existed. Four subsequent executions of the current Wispr Flow installer completed the package download and then ended with the Squirrel-style **Installation has failed** dialog.

Do not repeatedly rerun the installer without inspecting the setup log. Do not delete more Wispr folders, registry values, or local user data while the root cause is unresolved.

## First transition — read-only diagnosis

From the FileSteward repository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\diagnose-wispr-install.ps1
```

The script is intentionally read-only. It writes private evidence only under ignored `var/runs/wispr-recovery-*/`.

It records:

- Wispr uninstall registrations from HKCU/HKLM, including both registry views;
- whether registered uninstall/modify executables still exist;
- whether the expected per-user `%LOCALAPPDATA%\WisprFlow\Update.exe` exists;
- currently running Wispr-prefixed processes and executable paths;
- presence only (not filenames/content) for documented Wispr data/install locations;
- the tail of any current Squirrel setup logs.

It does **not**:

- delete files;
- remove registry keys;
- terminate processes;
- enumerate transcript filenames/content;
- repair/reinstall Wispr.

## Classification

### APP_INSTALLATION_BROKEN

Use when Windows still has Wispr installation/serviceability registration but referenced executables or the expected install tree are missing.

This state is protected. It is not an orphan and cannot be raw-deleted.

### APP_REGISTERED_REQUIRES_LOG_DIAGNOSIS

Registration and install paths still exist. Read the Squirrel log before choosing a repair.

### NO_WISPR_UNINSTALL_REGISTRATION_FOUND

The installed-app registration is absent. Preserve user data and use the Squirrel log plus filesystem evidence to determine the next semantic recovery action.

## Second transition — classify installer failure

Read `diagnostic.json` and the copied Squirrel log tail.

Common classes:

1. **file/process lock** — installer cannot replace/remove an existing Wispr/Electron file:
   - preserve evidence;
   - end only verified Wispr processes or restart Windows;
   - rerun the official installer once;
   - verify launch + registration.

2. **access denied / endpoint protection**:
   - identify the exact denied path and security product event;
   - do not disable broad protections;
   - correct the bounded permission/quarantine issue, then rerun once.

3. **stale/broken Squirrel registration or missing Update.exe**:
   - preserve the uninstall registration and local-data evidence;
   - back up any surviving user-data directory before mutation;
   - repair/remove only the exact stale Wispr application registration as required by the proven failure;
   - rerun the official installer;
   - verify `Update.exe`, launch, version, and Installed Apps consistency.

4. **download/package/extraction error**:
   - preserve the log;
   - verify installer provenance/signature and available disk/temp access;
   - obtain a fresh official installer only if the log supports package corruption.

5. **unknown**:
   - stop mutation;
   - retain `CORRELATED_UNRESOLVED`;
   - escalate with the setup log.

## Repair acceptance

Recovery is complete only when all are observed:

- Wispr launches successfully;
- expected install/serviceability executable exists or registration points to its new valid location;
- Installed Apps registration is internally consistent;
- no additional Wispr user-data deletion occurred;
- the installer no longer emits the failing signature;
- incident evidence remains preserved under ignored runtime storage.

## FileSteward regression implication

The incident is a permanent safety fixture:

- AppData location never establishes disposability.
- Missing updater/uninstaller never means orphan.
- application, repository, toolchain, service/task, package, user-data, and generated-output ownership may coexist;
- the most protective current dependency edge wins;
- semantic repair/uninstall precedes raw deletion.
