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

    [string]$Checkout = (Join-Path $PSScriptRoot '..\..'),

    [string]$Downloads = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'),

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

function Resolve-Inputs {
    $canonical = [IO.Path]::GetFullPath($Checkout)
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
    $root = [IO.Path]::GetFullPath($Downloads)
    $expectedRoot = [IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'))
    if (-not [string]::Equals($root.TrimEnd('\'), $expectedRoot.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Only the current Windows user Downloads folder is supported by this task.'
    }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw 'Downloads directory is inaccessible.'
    }
    $rootInfo = Get-Item -LiteralPath $root -Force
    if (($rootInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Downloads is a junction/symlink/reparse path; refusing scheduled traversal.'
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
    if ($interpreter -match '\\Microsoft\\WindowsApps\\python(?:3)?\.exe
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

function Invoke-ReadOnlyReview($inputPaths) {
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
            return 4
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
        return 0
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
    exit (Invoke-ReadOnlyReview $inputPaths)
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
) {
        throw 'WindowsApps Store launcher is not a verified Python interpreter.'
    }
    & $interpreter -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 2)' | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'FileSteward requires an operational Python 3.12+ interpreter.'
    }
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

function Invoke-ReadOnlyReview($inputPaths) {
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
            return 4
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
        return 0
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
    exit (Invoke-ReadOnlyReview $inputPaths)
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
