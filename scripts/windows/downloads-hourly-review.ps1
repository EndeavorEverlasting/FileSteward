<#
.SYNOPSIS
  FileSteward opt-in hourly Downloads review (Windows Task Scheduler).
.DESCRIPTION
  Schedules the existing read-only FileSteward scanner and validator.
  Does not quarantine, move, approve or delete downloaded files. Review
  artifacts are private, under the canonical checkout's ignored var/runs.
  Registration, disabling and removal require an explicit -Authorize switch.
.EXAMPLE
  .\scripts\windows\downloads-hourly-review.ps1 -Mode Preview
.EXAMPLE
  .\scripts\windows\downloads-hourly-review.ps1 -Mode Register -Authorize
#>
[CmdletBinding()]
param(
    [ValidateSet('Preview', 'Register', 'RunOnce', 'Status', 'Disable', 'Unregister')]
    [string]$Mode = 'Preview',

    [string]$Checkout = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'dev\FileSteward'),

    [string]$Downloads = '',

    [string]$Python = '',

    [switch]$Authorize
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OwnerMarker = 'FileSteward.downloads-hourly-review/v1'
$TaskPrefix = 'FileSteward-DownloadsReview-'

function Assert-Windows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Windows Task Scheduler is required. No task was changed.'
    }
}

function Get-Identity {
    Assert-Windows
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($null -eq $id.User -or [string]::IsNullOrWhiteSpace($id.Name)) {
        throw 'Could not establish the current Windows identity.'
    }
    return $id
}

function Get-KnownDownloads {
    if (-not ('FileStewardDownloadsKnownFolder' -as [type])) {
        Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FileStewardDownloadsKnownFolder {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SHGetKnownFolderPath(ref Guid id, uint flags, IntPtr token, out IntPtr result);
    public static string GetPath() {
        var id = new Guid("374DE290-123F-4565-9164-39C4925E467B");
        IntPtr ptr = IntPtr.Zero;
        int hr = SHGetKnownFolderPath(ref id, 0, IntPtr.Zero, out ptr);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        try { return Marshal.PtrToStringUni(ptr); }
        finally { if (ptr != IntPtr.Zero) Marshal.FreeCoTaskMem(ptr); }
    }
}
'@
    }
    $value = [FileStewardDownloadsKnownFolder]::GetPath()
    if ([string]::IsNullOrWhiteSpace($value)) { throw 'FOLDERID_Downloads unavailable.' }
    return $value
}

function Resolve-Inputs {
    $canonical = [IO.Path]::GetFullPath($Checkout).TrimEnd('\')
    $profileRoot = [Environment]::GetFolderPath('UserProfile')
    $expectedCanonical = [IO.Path]::GetFullPath((Join-Path $profileRoot 'dev\FileSteward')).TrimEnd('\')
    if (-not [string]::Equals($canonical, $expectedCanonical, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'NONCANONICAL_CHECKOUT: required %USERPROFILE%\dev\FileSteward per docs/agent/CANONICAL-PATHS.md.'
    }
    foreach ($directory in @((Join-Path $profileRoot 'dev'), $canonical)) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            throw 'CANONICAL_CHECKOUT_MISSING: required directory does not exist.'
        }
        if (((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'CANONICAL_CHECKOUT_REPARSE: redirect/junction checkout refused.'
        }
    }
    $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $git) { throw 'CANONICAL_GIT_UNAVAILABLE.' }
    $gitRoot = & $git.Source -C $canonical rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or -not [string]::Equals(([IO.Path]::GetFullPath([string]$gitRoot)).TrimEnd('\'), $canonical, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'CANONICAL_GIT_MISMATCH.'
    }
    $origin = & $git.Source -C $canonical remote get-url origin
    if ($LASTEXITCODE -ne 0 -or [string]$origin -notmatch '^(https://github\.com/EndeavorEverlasting/FileSteward(?:\.git)?|git@github\.com:EndeavorEverlasting/FileSteward(?:\.git)?)$') {
        throw 'CANONICAL_REPOSITORY_MISMATCH.'
    }
    $self = [IO.Path]::GetFullPath($PSCommandPath)
    $expected = [IO.Path]::GetFullPath((Join-Path $canonical 'scripts\windows\downloads-hourly-review.ps1'))
    if (-not [string]::Equals($self, $expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Launch the script from its own canonical FileSteward checkout.'
    }
    foreach ($relative in @('pyproject.toml', 'src\filesteward\cli.py', 'AGENTS.md')) {
        if (-not (Test-Path -LiteralPath (Join-Path $canonical $relative) -PathType Leaf)) {
            throw "Not a verified FileSteward checkout: $relative missing"
        }
    }
    $expectedRoot = [IO.Path]::GetFullPath((Get-KnownDownloads))
    $selected = if ([string]::IsNullOrWhiteSpace($Downloads)) { $expectedRoot } else { $Downloads }
    $root = [IO.Path]::GetFullPath($selected)
    if (-not [string]::Equals($root.TrimEnd('\'), $expectedRoot.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'DOWNLOADS_KNOWN_FOLDER_MISMATCH: use current-user FOLDERID_Downloads.'
    }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw 'Downloads directory is inaccessible.'
    }
    # Reject redirection through ANY ancestor, not just the Downloads leaf.
    $walk = [IO.Path]::GetPathRoot($root)
    foreach ($component in $root.Substring($walk.Length).Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)) {
        $walk = Join-Path $walk $component
        if (((Get-Item -LiteralPath $walk -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'DOWNLOADS_REPARSE_ANCESTOR: symbolic link/junction/mount point refused.'
        }
    }

    $interpreter = $Python
    if ([string]::IsNullOrWhiteSpace($interpreter)) {
        $command = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $command) { throw 'Python executable required. Pass -Python with an absolute path.' }
        $interpreter = $command.Source
    }
    if (-not [IO.Path]::IsPathRooted($interpreter) -or -not (Test-Path -LiteralPath $interpreter -PathType Leaf)) {
        throw 'The Python executable must be an existing absolute file.'
    }
    if ($interpreter -match '[\r\n"]' -or $canonical -match '[\r\n"]' -or $root -match '[\r\n"]') {
        throw 'Cannot encode path into a safe scheduled-task argument.'
    }
    if ($interpreter -match '\\Microsoft\\WindowsApps\\python(?:3)?\.exe$') {
        throw 'WindowsApps Store launcher is not a verified Python interpreter.'
    }
    & $interpreter -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 2)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'FileSteward requires an operational Python 3.12+ interpreter.' }
    return @{
        Checkout = $canonical
        Downloads = $root
        Python = [IO.Path]::GetFullPath($interpreter)
    }
}

function Get-OwnedTaskName {
    $identity = Get-Identity
    $sid = $identity.User.Value -replace '[^0-9A-Za-z-]', '-'
    return "$TaskPrefix$sid"
}

function Get-ExistingTask([string]$name) {
    return (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue)
}

function Assert-OwnedTask($task) {
    if ($null -eq $task) { throw 'FileSteward task was not found.' }
    if ($task.Description -ne $OwnerMarker) {
        throw 'A foreign or changed task occupies this name; refusing mutation.'
    }
}

function Quote-Argument([string]$value) {
    if ($value -match '[\r\n"]') { throw 'Unsafe scheduled-task argument.' }
    return '"' + $value + '"'
}

function Invoke-ReadOnlyReview($inputPaths, [ref]$ExitCode) {
    $ExitCode.Value = 2
    $name = Get-OwnedTaskName
    $mutex = [Threading.Mutex]::new($false, "Local\$name")
    $acquired = $false
    try {
        try {
            $acquired = $mutex.WaitOne(0)
        }
        catch [Threading.AbandonedMutexException] {
            $acquired = $true
        }
        if (-not $acquired) {
            Write-Output 'A prior FileSteward Downloads review is still active; skipped overlapping run.'
            $ExitCode.Value = 4
            return
        }
        $runtime = Join-Path $inputPaths.Checkout 'var\runs'
        $id = 'downloads-hourly-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
        $runDir = Join-Path $runtime $id
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null

        $oldPythonPath = $env:PYTHONPATH
        $env:PYTHONPATH = (Join-Path $inputPaths.Checkout 'src')
        try {
            & $inputPaths.Python -m filesteward.cli scan $inputPaths.Downloads --run-dir $runDir
            if ($LASTEXITCODE -ne 0) { throw "Read-only scan failed (exit $LASTEXITCODE)." }
            & $inputPaths.Python -m filesteward.cli validate $runDir
            if ($LASTEXITCODE -ne 0) { throw "Read-only artifact validation failed (exit $LASTEXITCODE)." }
            Write-Output "VERIFIED_READ_ONLY_REVIEW: $runDir"
        }
        finally {
            $env:PYTHONPATH = $oldPythonPath
        }
        $ExitCode.Value = 0
    }
    finally {
        if ($acquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

Assert-Windows
$name = Get-OwnedTaskName

if ($Mode -in @('Disable', 'Unregister', 'Register') -and -not $Authorize) {
    throw "Explicit -Authorize required for $Mode. No task was changed."
}

if ($Mode -in @('Status', 'Disable', 'Unregister')) {
    $task = Get-ExistingTask $name
    if ($null -eq $task) {
        if ($Mode -eq 'Status') {
            [pscustomobject]@{ TaskName=$name; State='NOT_REGISTERED'; Owner=$OwnerMarker } | ConvertTo-Json
            exit 0
        }
        throw "Task not registered: $name"
    }
    Assert-OwnedTask $task
    if ($Mode -eq 'Status') {
        $info = Get-ScheduledTaskInfo -TaskName $name
        [pscustomobject]@{
            TaskName=$name; State="$($task.State)"; LastRunTime=$info.LastRunTime
            NextRunTime=$info.NextRunTime; LastTaskResult=$info.LastTaskResult
            Owner=$OwnerMarker
        } | ConvertTo-Json
        exit 0
    }
    if ($Mode -eq 'Disable') {
        Disable-ScheduledTask -TaskName $name | Out-Null
        Write-Output "DISABLED: $name"
        exit 0
    }
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Output "UNREGISTERED: $name"
    exit 0
}

$inputPaths = Resolve-Inputs
if ($Mode -eq 'RunOnce') {
    $exitCode = 2
    Invoke-ReadOnlyReview $inputPaths ([ref]$exitCode)
    exit $exitCode
}

$scriptPath = [IO.Path]::GetFullPath($PSCommandPath)
$exe = (Get-Process -Id $PID).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw 'Cannot pin the running PowerShell interpreter.'
}
$arguments = @(
    '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
    (Quote-Argument $scriptPath), '-Mode', 'RunOnce',
    '-Checkout', (Quote-Argument $inputPaths.Checkout),
    '-Downloads', (Quote-Argument $inputPaths.Downloads),
    '-Python', (Quote-Argument $inputPaths.Python)
) -join ' '

if ($Mode -eq 'Preview') {
    [pscustomobject]@{
        TaskName=$name; Owner=$OwnerMarker; EveryMinutes=60
        LoginMode='INTERACTIVE_CURRENT_USER'; Command=$exe; Arguments=$arguments
        Downloads=$inputPaths.Downloads; Checkout=$inputPaths.Checkout
        Registers=$false; WritesFiles=$false; DeletesFiles=$false
        Note='Hourly run creates ignored review evidence; it never acts on Downloads.'
    } | ConvertTo-Json
    exit 0
}

if (Get-ExistingTask $name) {
    throw 'Task name already exists; refusing to overwrite or replace an existing registration.'
}

$identity = Get-Identity
$action = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $inputPaths.Checkout
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Description $OwnerMarker -Action $action -Trigger $trigger -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
$registered = Get-ExistingTask $name
Assert-OwnedTask $registered
Write-Output "REGISTERED: $name (hourly; read-only; current user; no stored password)"
