<#
.SYNOPSIS
  FileSteward hourly evidence/steward cycle. No model calls or filesystem cleanup.
.DESCRIPTION
  Windows Scheduled Task, current limited user, opt-in. Runs FileSteward's
  existing scan+validate, then the read-only stewardship classifier/work outbox.
  Does NOT install an agent, execute outbox tickets, move or delete files.
  Mutating FileSteward actions require a different operator-gated executor.
.EXAMPLE
  .\scripts\windows\steward-hourly.ps1 -Action Preview
.EXAMPLE
  .\scripts\windows\steward-hourly.ps1 -Action Register -Authorize
#>
[CmdletBinding()]
param(
    [ValidateSet('Preview','RunOnce','Register','Status','Disable','Unregister')]
    [string]$Action = 'Preview',
    [string]$Python = '',
    [switch]$Authorize
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owner = 'FileSteward.steward-hourly/v1'
$checkout = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'dev\FileSteward'
$taskName = ''
function Need-Windows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'WINDOWS_ONLY: cannot register Windows Scheduled Task.'
    }
}
function Current-Identity {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($null -eq $identity.User) { throw 'WINDOWS_IDENTITY_UNAVAILABLE' }
    return $identity
}
function Task-Name {
    $sid = (Current-Identity).User.Value
    return "FileSteward-StewardHourly-$sid"
}
function Get-DownloadsKnownFolder {
    if (-not ('FileStewardStewardKnownDownloads' -as [type])) {
        Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FileStewardStewardKnownDownloads {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetKnownFolderPath(ref Guid id, uint flags, IntPtr token, out IntPtr result);
    public static string Resolve() {
        Guid id = new Guid("374DE290-123F-4565-9164-39C4925E467B");
        IntPtr ptr = IntPtr.Zero;
        int hr = SHGetKnownFolderPath(ref id, 0, IntPtr.Zero, out ptr);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        try { return Marshal.PtrToStringUni(ptr); }
        finally { if (ptr != IntPtr.Zero) Marshal.FreeCoTaskMem(ptr); }
    }
}
'@
    }
    $root = [FileStewardStewardKnownDownloads]::Resolve()
    if ([string]::IsNullOrWhiteSpace($root)) { throw 'DOWNLOADS_KNOWN_FOLDER_MISSING' }
    return [IO.Path]::GetFullPath($root)
}
function Assert-No-Reparse-Ancestors([string]$fullPath) {
    $walk = [IO.Path]::GetPathRoot($fullPath)
    foreach ($piece in $fullPath.Substring($walk.Length).Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)) {
        $walk = Join-Path $walk $piece
        if (((Get-Item -LiteralPath $walk -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'REPARSE_ROOT_REFUSED'
        }
    }
}
function Confirm-Checkout {
    $required = [IO.Path]::GetFullPath($checkout)
    $current = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (-not [string]::Equals($current, $required, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'NONCANONICAL_CHECKOUT: use %USERPROFILE%\dev\FileSteward.'
    }
    Assert-No-Reparse-Ancestors $required
    $git = Get-Command git -CommandType Application -ErrorAction Stop
    $root = & $git.Source -C $required rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or -not [string]::Equals(
        ([IO.Path]::GetFullPath([string]$root)), $required, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'CANONICAL_GIT_ROOT_MISMATCH'
    }
    $origin = & $git.Source -C $required remote get-url origin
    if ($LASTEXITCODE -ne 0 -or [string]$origin -notmatch '^(https://github\.com/EndeavorEverlasting/FileSteward(?:\.git)?|git@github\.com:EndeavorEverlasting/FileSteward(?:\.git)?)$') {
        throw 'CANONICAL_REPOSITORY_MISMATCH'
    }
    return $required
}
function Resolve-Python {
    $interpreter = $Python
    if ([string]::IsNullOrWhiteSpace($interpreter)) {
        $cmd = Get-Command python -CommandType Application -ErrorAction Stop
        $interpreter = $cmd.Source
    }
    if (-not [IO.Path]::IsPathRooted($interpreter) -or -not (Test-Path -LiteralPath $interpreter -PathType Leaf)) {
        throw 'PYTHON_INTERPRETER_UNAVAILABLE'
    }
    if ($interpreter -match '\\Microsoft\\WindowsApps\\python(?:3)?\.exe$') {
        throw 'PYTHON_WINDOWS_STORE_ALIAS_REFUSED'
    }
    & $interpreter -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 2)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_REQUIRED' }
    return [IO.Path]::GetFullPath($interpreter)
}
function Exact-Task {
    return (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)
}
function Require-Owned($task) {
    if ($null -eq $task -or [string]$task.Description -ne $owner) {
        throw 'FOREIGN_TASK_COLLISION_OR_MISSING'
    }
    $who = Current-Identity
    if (-not ([string]::Equals([string]$task.Principal.UserId, $who.Name, [StringComparison]::OrdinalIgnoreCase) -or
              [string]::Equals([string]$task.Principal.UserId, $who.User.Value, [StringComparison]::OrdinalIgnoreCase))) {
        throw 'TASK_PRINCIPAL_MISMATCH'
    }
    if (@($task.Actions).Count -ne 1) { throw 'TASK_ACTION_COUNT_MISMATCH' }
    if (-not ([string]$task.Actions[0].Arguments).Contains(('-File "' + [IO.Path]::GetFullPath($PSCommandPath) + '"'))) {
        throw 'TASK_ACTION_MISMATCH'
    }
}
function Quote-Arg([string]$x) {
    if ($x -match '[\r\n"]') { throw 'UNSAFE_EXECUTION_ARGUMENT' }
    return '"' + $x + '"'
}
Need-Windows
$taskName = Task-Name

if ($Action -in @('Register','Disable','Unregister') -and -not $Authorize) {
    throw 'EXPLICIT_AUTHORIZE_REQUIRED'
}
if ($Action -in @('Status','Disable','Unregister')) {
    $existing = Exact-Task
    if ($null -eq $existing -and $Action -eq 'Status') {
        Write-Output "NOT_REGISTERED: $taskName"
        exit 0
    }
    Require-Owned $existing
    if ($Action -eq 'Status') {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        [pscustomobject]@{task_name=$taskName;state="$($existing.State)";
            last_run=$info.LastRunTime;next_run=$info.NextRunTime;
            last_result=$info.LastTaskResult;mode='READ_ONLY_OUTBOX'} | ConvertTo-Json
        exit 0
    }
    if ($Action -eq 'Disable') {
        Disable-ScheduledTask -TaskName $taskName | Out-Null
        Write-Output "DISABLED: $taskName"
        exit 0
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Output "UNREGISTERED: $taskName"
    exit 0
}

$checkout = Confirm-Checkout
$downloads = Get-DownloadsKnownFolder
Assert-No-Reparse-Ancestors $downloads
$pythonExe = Resolve-Python

if ($Action -eq 'RunOnce') {
    $mutex = [Threading.Mutex]::new($false, "Local\$taskName")
    $held = $false
    try {
        try { $held = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $held = $true }
        if (-not $held) {
            Write-Output 'OVERLAPPING_CYCLE_SKIPPED'
            exit 4
        }
        $runDir = Join-Path $checkout ('var\runs\steward-hourly-' + [guid]::NewGuid().ToString('N'))
        $previous = $env:PYTHONPATH
        $env:PYTHONPATH = Join-Path $checkout 'src'
        try {
            & $pythonExe -m filesteward.cli scan $downloads --run-dir $runDir
            if ($LASTEXITCODE -ne 0) { throw "SCAN_FAILED: $LASTEXITCODE" }
            & $pythonExe -m filesteward.cli validate $runDir
            if ($LASTEXITCODE -ne 0) { throw "VALIDATE_FAILED: $LASTEXITCODE" }
            & $pythonExe -m filesteward.steward --scan-run $runDir
            if ($LASTEXITCODE -ne 0) { throw "STEWARD_FAILED: $LASTEXITCODE" }
            Write-Output 'CYCLE_READONLY_COMPLETED'
        }
        finally { $env:PYTHONPATH = $previous }
    }
    finally {
        if ($held) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
    exit 0
}

$script = [IO.Path]::GetFullPath($PSCommandPath)
$exe = (Get-Process -Id $PID).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'POWERSHELL_BINARY_UNAVAILABLE' }
$arguments = @('-NoLogo','-NoProfile','-NonInteractive','-File',
               (Quote-Arg $script),'-Action','RunOnce','-Python',
               (Quote-Arg $pythonExe)) -join ' '
if ($Action -eq 'Preview') {
    [pscustomobject]@{task_name=$taskName; cadence_minutes=60;
        engine='Windows Task Scheduler'; user=(Current-Identity).Name;
        python=$pythonExe; command=$exe; arguments=$arguments;
        root=$downloads; mode='READ_ONLY_OUTBOX'; requires_opt_in=$true;
        agent_spawns=0; source_mutations=0; registers=$false} | ConvertTo-Json
    exit 0
}
$legacyTask = "FileSteward-DownloadsReview-$((Current-Identity).User.Value)"
if ($null -ne (Get-ScheduledTask -TaskName $legacyTask -ErrorAction SilentlyContinue)) {
    throw 'LEGACY_HOURLY_TASK_PRESENT: refuse duplicate scanning; migrate deliberately.'
}
if ($null -ne (Exact-Task)) {
    throw 'TASK_ALREADY_EXISTS: never overwrite even if marked FileSteward-owned.'
}
$principal = New-ScheduledTaskPrincipal -UserId (Current-Identity).Name -LogonType Interactive -RunLevel Limited
$act = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $checkout
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Description $owner -Principal $principal -Action $act -Trigger $trigger -Settings $settings -ErrorAction Stop | Out-Null
Require-Owned (Exact-Task)
Write-Output "REGISTERED_READ_ONLY: $taskName"
