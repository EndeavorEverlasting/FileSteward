# Windows distribution

The Windows distribution starts FileSteward's local browser application without requiring Python, Git, administrator access, or a repository checkout. First launch opens the welcome experience; it does not authorize a scan, deletion, or recurring task.

## Artifacts and identity

The release has four download assets: `FileSteward.exe`, `FileSteward.cmd`, `FileSteward-windows-x64.zip`, and `SHA256SUMS.txt`. The EXE embeds Python, package resources, license notices, and `filesteward/contracts/build-info.json` with package version, runtime profile, exact source commit, and prototype status. The ZIP contains the easier-to-inspect folder distribution.

The readable CMD/PowerShell bootstrap downloads the exact version's EXE over HTTPS, verifies the executable SHA256 embedded during the build, then launches it. It uses Windows Known Folder LocalAppData, creating `FileSteward/app/vVERSION/FileSteward.exe`. A versionless `.filesteward-application.json` marker binds `schema_version: filesteward.application-root/v1`, `app_id: filesteward`, and `runtime_profile: windows-localappdata/v1`. An existing unmarked application root, reparse point, or mismatching executable stops launch without replacement. The downloaded EXE's location does not define the private runtime root.

The bootstrap is pinned to `/releases/download/vVERSION/FileSteward.exe`; a prerelease does not depend on GitHub's `latest` alias. The pinned link becomes available only after the matching release asset is published. An embedded hash verifies transport content against this bootstrap's identity; it is not Authenticode publisher verification.

## Build and proof

Use a dedicated ignored virtual environment on native Windows x64:

```powershell
python -m venv var/windows-build-venv
var/windows-build-venv/Scripts/python.exe -m pip install -r packaging/windows/build-requirements.txt
var/windows-build-venv/Scripts/python.exe scripts/build_windows_distribution.py --label release-VERSION
```

The helper rejects a dirty source HEAD for public release builds. `--prototype` permits local implementation proof and marks both embedded identity and the build manifest accordingly; prototype artifacts must not be presented as an exact committed release. Every build uses a new label under ignored `var/windows-distribution/`; existing evidence is never overwritten or recursively removed.

The helper builds the folder distribution first and runs its bounded `--version` startup proof, then builds and checks the single EXE. It writes build logs, bundled notices, `distribution-manifest.json` containing exact source identity, dependency versions and asset hashes, plus the four release assets. Browser startup, runtime location, HTTP confinement, and explicit user-driven scanning remain separate acceptance gates. An EXE startup success does not prove those gates or production use.

Before publication, refresh the exact source head, run repository validation and packaged runtime proof, then publish the named version's assets under repository promotion authority. Rebuild from a clean committed head after implementation; do not publish a prototype manifest as a release.
