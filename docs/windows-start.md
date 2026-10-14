# Start FileSteward on Windows

The Windows x64 `0.16.0` pre-alpha preview opens a local welcome screen. Startup does not scan your computer or delete files. The executable is unsigned; release publication, signing, and live deletion proof are separate states.

## Open the preview

1. Download `FileSteward.exe` from the repository's `v0.16.0` release to a folder you control. The download page pins that version; a missing artifact means publication has not completed.
2. Download `SHA256SUMS.txt` from the same release. Use `Get-FileHash .\FileSteward.exe -Algorithm SHA256` in PowerShell and compare its result with the exact filename's digest in the checksum file.
3. Open `FileSteward.exe`. Follow your device's security policy if Windows reports an unsigned application.
4. Select **Explore sample** for synthetic data, or open a recent review. A sample never establishes workstation scan, deletion, or reclaim proof.

The portable ZIP contains the folder distribution; keep its executable and bundled resources together. The separate readable `FileSteward.cmd` bootstrap downloads and verifies the pinned release executable, installs it in your private LocalAppData application folder, and opens it. Neither route requires Python, Git, or administrator installation.

## Import an existing run

Choose the existing FileSteward run folder on the welcome screen. Only permitted files directly inside that folder are imported. Nested files and other private material are excluded; the app shows the accepted filenames before import. The server enforces the whitelist and validates the run. Importing evidence is not authorization to scan or mutate its source paths.

## Understand the boundaries

The downloadable welcome app exposes sample and imported reviews in observation-only mode. It does not grant rescan, approval, or deletion capabilities. Classification, exact action approval, execution, and verification remain separate in the repository execution path. Protected, unknown, and unresolved evidence cannot be promoted into deletion. Quarantine staging removes no bytes. Permanent deletion uses the repository-owned exact-manifest path, current evidence, fresh preflight, distinct operator approval, bounded execution, and receipt readback. Reclaimed space requires measured verification. Recurring cleanup preferences are unavailable in this preview.

## Close or recover

Use **Close app** on the welcome screen to stop the local session, then close its browser tab. If an action reports a connection or validation failure, read the displayed error, restore the local session, and refresh recent reviews. An error is not a success receipt. Reopen the executable if the local session has stopped.

For a missing download, check the exact release's publication state. For a launch failure, preserve the displayed error and consult the repository release notes; do not substitute a different executable or weaken storage protection gates.
