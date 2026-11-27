# Installs a per-user FileSteward shortcut from a canonical checkout or worktree.
# It invokes the existing "filesteward launch" single-instance behavior.
# No network binding, personal scan, cleanup, schedule, or shell-wide setup.
[CmdletBinding()]
param(
    [switch]$StartMenuOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This shortcut installer requires Windows.' }
if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) { throw 'Windows USERPROFILE is unavailable.' }

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\')
$profile = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
$canonical = [IO.Path]::Combine($profile, 'dev', 'FileSteward')
$worktreeBase = [IO.Path]::Combine($profile, 'dev', 'worktrees', 'FileSteward')
$equals = [StringComparison]::OrdinalIgnoreCase
$worktreePrefix = $worktreeBase.TrimEnd('\') + '\'
$relativeLane = if ($source.StartsWith($worktreePrefix, $equals)) {
    $source.Substring($worktreePrefix.Length)
} else { '' }
if (!($source.Equals($canonical, $equals) -or (
    $relativeLane.Length -gt 0 -and $relativeLane.IndexOf('\') -lt 0))) {
    throw 'Run the installer from the canonical dev\FileSteward checkout or its dev\worktrees\FileSteward\<lane> worktree.'
}

function Assert-OrdinaryPath([string]$path) {
    $part = [IO.Path]::GetFullPath($path)
    while ($part) {
        if (Test-Path -LiteralPath $part) {
            $item = Get-Item -LiteralPath $part -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing a linked/reparse path: $part"
            }
        }
        $parent = [IO.Directory]::GetParent($part)
        if ($null -eq $parent) { break }
        $part = $parent.FullName
    }
}

Assert-OrdinaryPath $source
foreach ($required in @('pyproject.toml', 'src\filesteward\cli.py', 'src\filesteward\launch.py')) {
    if (!(Test-Path -LiteralPath (Join-Path $source $required) -PathType Leaf)) {
        throw "FileSteward checkout is incomplete: $required"
    }
}
$git = Join-Path $source '.git'
if (!(Test-Path -LiteralPath $git)) { throw 'Not an existing FileSteward Git checkout/worktree.' }

# Only an isolated environment inside the approved checkout/worktree is prepared.
$venv = Join-Path $source '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$pythonw = Join-Path $venv 'Scripts\pythonw.exe'
Assert-OrdinaryPath $venv
if (!(Test-Path -LiteralPath $venv)) {
    if (!(Get-Command py.exe -ErrorAction SilentlyContinue)) {
        throw 'Install Python 3.12+ with the Windows py launcher, then retry.'
    }
    & py.exe -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }
    & py.exe -3 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated FileSteward virtual environment.' }
}
Assert-OrdinaryPath $python
Assert-OrdinaryPath $pythonw
if (!(Test-Path -LiteralPath $python -PathType Leaf) -or
    !(Test-Path -LiteralPath $pythonw -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $venv 'pyvenv.cfg') -PathType Leaf)) {
    throw 'The FileSteward .venv is incomplete. Preserve and repair it before installing a shortcut.'
}

& $python -I -m pip install --editable $source
if ($LASTEXITCODE -ne 0) { throw 'The isolated FileSteward package installation failed. No shortcut was created.' }
& $python -I -c 'import filesteward; from filesteward.cli import main; assert callable(main)'
if ($LASTEXITCODE -ne 0) { throw 'Installed FileSteward entrypoint is unavailable. No shortcut was created.' }

$isPreview = !$source.Equals($canonical, $equals)
$name = if ($isPreview) { 'FileSteward (Preview)' } else { 'FileSteward' }
$programs = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)
if ([string]::IsNullOrWhiteSpace($programs)) { throw 'Windows Start Menu Programs folder is unavailable.' }
$startMenuFolder = Join-Path $programs 'FileSteward'
Assert-OrdinaryPath $startMenuFolder
[IO.Directory]::CreateDirectory($startMenuFolder) | Out-Null

# A .lnk launches pythonw, not a temporary http://127.0.0.1:<port> URL.
# The existing app's InstanceLock / health reconciliation opens the right port
# if the app already runs and otherwise starts its own loopback server.
$targets = @(Join-Path $startMenuFolder ($name + '.lnk'))
if (!$StartMenuOnly) {
    $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if ([string]::IsNullOrWhiteSpace($desktop)) { throw 'Windows Desktop known folder is unavailable.' }
    $targets += Join-Path $desktop ($name + '.lnk')
}
$shell = New-Object -ComObject WScript.Shell
foreach ($target in $targets) {
    Assert-OrdinaryPath $target
    if (Test-Path -LiteralPath $target) {
        $existing = $shell.CreateShortcut($target)
        # Do not overwrite a shortcut previously owned by another launcher.
        if (!$existing.TargetPath.Equals($pythonw, $equals) -or
            !$existing.WorkingDirectory.Equals($source, $equals)) {
            throw "Existing shortcut belongs to a different installation; preserved: $target"
        }
    }
}
foreach ($target in $targets) {
    $link = $shell.CreateShortcut($target)
    $link.TargetPath = $pythonw
    $link.Arguments = '-m filesteward.cli launch'
    $link.WorkingDirectory = $source
    $link.Description = if ($isPreview) {
        'Open the locally tested FileSteward preview; no automatic storage scan.'
    } else { 'Open FileSteward; no automatic storage scan.' }
    $link.WindowStyle = 1
    $link.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',3'
    $link.Save()
    Write-Output "Shortcut installed: $target"
}
if (!$NoLaunch) {
    Start-Process -FilePath $pythonw -ArgumentList '-m filesteward.cli launch' -WorkingDirectory $source
    Write-Output 'FileSteward launch requested. The app will open its current local URL in your default browser.'
}
