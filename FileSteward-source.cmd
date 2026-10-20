@echo off
setlocal
set "FS_SOURCE_BOOTSTRAP=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$text=[IO.File]::ReadAllText($env:FS_SOURCE_BOOTSTRAP); $marker='# POWERSHELL_PAYLOAD'; & ([ScriptBlock]::Create($text.Substring($text.LastIndexOf($marker)+$marker.Length)))"
if errorlevel 1 (
  echo FileSteward did not start. Read the error above; your existing work was preserved.
  pause
  exit /b 1
)
exit /b 0
# POWERSHELL_PAYLOAD
$ErrorActionPreference = 'Stop'
$sourceRemote = 'https://github.com/EndeavorEverlasting/FileSteward.git'

function Invoke-SourceGit([string]$repo, [string[]]$arguments) {
  $output = & git -C $repo @arguments
  if ($LASTEXITCODE -ne 0) { throw "Git failed ($LASTEXITCODE): $($arguments -join ' ')" }
  return $output
}

function Assert-SourcePath([string]$path) {
  $current = [IO.Path]::GetFullPath($path)
  while ($current) {
    if ([IO.Path]::GetFileName($current) -match '^(Desktop|Documents|OneDrive|Backups)$') {
      throw "Canonical source path contains a forbidden root: $current"
    }
    if (Test-Path -LiteralPath $current) {
      $item = Get-Item -LiteralPath $current -Force
      if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Source launch requires ordinary directories: $current"
      }
    }
    $parent = [IO.Directory]::GetParent($current)
    if ($null -eq $parent) { break }
    $current = $parent.FullName
  }
}

function Update-SourceCheckout([string]$repo) {
  Assert-SourcePath $repo
  $launchRoot = Join-Path $repo 'var\launch'
  Assert-SourcePath $launchRoot
  $instanceLock = Join-Path $launchRoot 'instance.lock'
  if (Test-Path -LiteralPath $instanceLock) {
    $lockItem = Get-Item -LiteralPath $instanceLock -Force
    if ($lockItem.PSIsContainer -or ($lockItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
      throw 'Launch lock is not an ordinary file; update refused.'
    }
    try {
      $probe = [IO.File]::Open($instanceLock, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
      $probe.Dispose()
    } catch { throw 'Close the running FileSteward source app before updating, then retry.' }
  }
  $top = Invoke-SourceGit $repo @('rev-parse', '--show-toplevel')
  if ([IO.Path]::GetFullPath($top) -ne [IO.Path]::GetFullPath($repo)) {
    throw 'Canonical directory must itself be the FileSteward checkout.'
  }
  # Reject linked worktrees: there is exactly one canonical normal checkout.
  if (!(Test-Path -LiteralPath (Join-Path $repo '.git') -PathType Container)) {
    throw 'Canonical source must be a normal checkout, not a linked worktree.'
  }
  Assert-SourcePath (Join-Path $repo '.git')
  $remote = Invoke-SourceGit $repo @('remote', 'get-url', 'origin')
  if ($remote -notin @($sourceRemote, 'git@github.com:EndeavorEverlasting/FileSteward.git')) {
    throw 'Origin does not match EndeavorEverlasting/FileSteward; nothing was updated.'
  }
  $branch = Invoke-SourceGit $repo @('branch', '--show-current')
  if ($branch -ne 'main') { throw 'Switch the canonical checkout to main after preserving your work, then retry.' }
  $dirty = Invoke-SourceGit $repo @('status', '--porcelain', '--untracked-files=normal')
  if ($dirty) { throw 'Canonical checkout has local changes. Commit or preserve them before updating; nothing was overwritten.' }
  Invoke-SourceGit $repo @('fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main') | Out-Host
  $ahead = Invoke-SourceGit $repo @('rev-list', '--count', 'origin/main..HEAD')
  if ($ahead -ne '0') { throw 'Local main has unpublished commits. Preserve and reconcile them before updating.' }
  Invoke-SourceGit $repo @('merge', '--ff-only', 'origin/main') | Out-Host
  $head = Invoke-SourceGit $repo @('rev-parse', 'HEAD')
  $expected = Invoke-SourceGit $repo @('rev-parse', 'origin/main')
  if ($head -ne $expected) { throw 'Updated checkout does not match origin/main; launch refused.' }
  Write-Host "Source current: $head"
}

function Start-SourceFileSteward {
  if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) { throw 'USERPROFILE is unavailable; canonical source cannot be resolved.' }
  if (!(Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows, then run this CMD again.' }
  $repo = Join-Path $env:USERPROFILE 'dev\FileSteward'
  Assert-SourcePath $repo
  if (!(Test-Path -LiteralPath $repo)) {
    $dev = Split-Path -Parent $repo
    [IO.Directory]::CreateDirectory($dev) | Out-Null
    Write-Host "Cloning FileSteward into $repo ..."
    & git clone --branch main --single-branch $sourceRemote $repo
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed. Any partial checkout was preserved; inspect it before retrying.' }
  }
  Update-SourceCheckout $repo
  $venv = Join-Path $repo '.venv'
  Assert-SourcePath $venv
  $python = Join-Path $venv 'Scripts\python.exe'
  if (!(Test-Path -LiteralPath $venv)) {
    if (!(Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 or newer with its Windows py launcher, then retry.' }
    & py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }
    & py -3 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated .venv.' }
  }
  if (!(Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Existing .venv is incomplete. Preserve or repair it before retrying.' }
  $pythonItem = Get-Item -LiteralPath $python -Force
  if ($pythonItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Virtual environment Python must not be a link.' }
  Assert-SourcePath (Split-Path -Parent $python)
  & $python -I -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) and sys.prefix != sys.base_prefix else 1)'
  if ($LASTEXITCODE -ne 0) { throw 'The isolated .venv must use Python 3.12 or newer.' }
  Push-Location -LiteralPath $repo
  try {
    & $python -I -m pip install --editable $repo
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; launch refused.' }
    $entry = Join-Path $venv 'Scripts\filesteward.exe'
    if (!(Test-Path -LiteralPath $entry -PathType Leaf)) { throw 'The filesteward entry point was not installed.' }
    Write-Host 'Opening FileSteward on loopback. Keep this window open; use Close app in the welcome page to stop.'
    & $entry launch
    if ($LASTEXITCODE -ne 0) { throw 'FileSteward local launch failed.' }
  } finally { Pop-Location }
}

Start-SourceFileSteward
