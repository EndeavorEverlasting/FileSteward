[CmdletBinding()]
param(
    [string]$OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ExePathFromCommand {
    param([AllowNull()][string]$Command)

    if ([string]::IsNullOrWhiteSpace($Command)) {
        return $null
    }

    $quoted = [regex]::Match($Command, '^\s*"([^"]+\.exe)"', 'IgnoreCase')
    if ($quoted.Success) {
        return [Environment]::ExpandEnvironmentVariables($quoted.Groups[1].Value)
    }

    $bare = [regex]::Match($Command, '^\s*([^\s]+\.exe)', 'IgnoreCase')
    if ($bare.Success) {
        return [Environment]::ExpandEnvironmentVariables($bare.Groups[1].Value)
    }

    return $null
}

function Get-OptionalProp {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        return ""
    }
    return [string]$prop.Value
}

function Get-WisprUninstallEntries {
    $locations = @(
        @{ Hive = "HKCU"; Path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" },
        @{ Hive = "HKLM64"; Path = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall" },
        @{ Hive = "HKLM32"; Path = "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" }
    )

    $result = @()

    foreach ($location in $locations) {
        if (-not (Test-Path -LiteralPath $location.Path)) {
            continue
        }

        foreach ($key in Get-ChildItem -LiteralPath $location.Path -ErrorAction SilentlyContinue) {
            $item = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            if ($null -eq $item) {
                continue
            }

            $displayName = Get-OptionalProp -Object $item -Name "DisplayName"
            if ($displayName -notmatch '(?i)wispr\s*flow') {
                continue
            }

            $commands = [ordered]@{
                UninstallString      = (Get-OptionalProp -Object $item -Name "UninstallString")
                QuietUninstallString = (Get-OptionalProp -Object $item -Name "QuietUninstallString")
                ModifyPath           = (Get-OptionalProp -Object $item -Name "ModifyPath")
            }

            $commandChecks = @()
            foreach ($pair in $commands.GetEnumerator()) {
                $exe = Get-ExePathFromCommand -Command $pair.Value
                $commandChecks += [ordered]@{
                    field        = $pair.Key
                    command      = $pair.Value
                    executable   = $exe
                    exists       = if ($exe) { Test-Path -LiteralPath $exe -PathType Leaf } else { $null }
                }
            }

            $installLocation = Get-OptionalProp -Object $item -Name "InstallLocation"
            $result += [ordered]@{
                hive             = $location.Hive
                registry_path    = $key.Name
                display_name     = $displayName
                display_version  = (Get-OptionalProp -Object $item -Name "DisplayVersion")
                publisher        = (Get-OptionalProp -Object $item -Name "Publisher")
                install_location = [Environment]::ExpandEnvironmentVariables($installLocation)
                display_icon     = (Get-OptionalProp -Object $item -Name "DisplayIcon")
                command_checks   = $commandChecks
            }
        }
    }

    return $result
}

function Get-WisprProcesses {
    $result = @()

    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.Name -match '(?i)^wispr' -or
                ($_.ExecutablePath -and $_.ExecutablePath -match '(?i)\\Wispr(?:\s*Flow|Flow)\\')
            }

        foreach ($process in $processes) {
            $result += [ordered]@{
                process_id      = [int]$process.ProcessId
                name            = [string]$process.Name
                executable_path = [string]$process.ExecutablePath
            }
        }
    }
    catch {
        $result += [ordered]@{
            error = $_.Exception.Message
        }
    }

    return $result
}

function Get-PathState {
    param([string]$Path)

    return [ordered]@{
        path   = $Path
        exists = Test-Path -LiteralPath $Path
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot "var\runs\wispr-recovery-$timestamp"
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$localAppData = [Environment]::GetFolderPath("LocalApplicationData")
$roamingAppData = [Environment]::GetFolderPath("ApplicationData")
$tempPath = [IO.Path]::GetTempPath()

$paths = @(
    (Join-Path $localAppData "WisprFlow"),
    (Join-Path $localAppData "Wispr Flow"),
    (Join-Path $localAppData "wispr-flow-updater"),
    (Join-Path $localAppData "Programs\WisprFlow"),
    (Join-Path $localAppData "Programs\Wispr Flow"),
    (Join-Path $roamingAppData "Wispr Flow"),
    (Join-Path $roamingAppData "WisprFlow"),
    (Join-Path $roamingAppData "wispr-flow"),
    (Join-Path $roamingAppData "Flow")
)

$pathStates = @()
foreach ($path in $paths) {
    $pathStates += Get-PathState -Path $path
}

$squirrelCandidates = @(
    (Join-Path $localAppData "SquirrelTemp\Squirrel-Install.log"),
    (Join-Path $localAppData "SquirrelTemp\SquirrelSetup.log"),
    (Join-Path $tempPath "SquirrelTemp\Squirrel-Install.log"),
    (Join-Path $tempPath "SquirrelTemp\SquirrelSetup.log")
)

$logEvidence = @()
foreach ($log in ($squirrelCandidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $log -PathType Leaf)) {
        continue
    }

    $tail = @(Get-Content -LiteralPath $log -Tail 250 -ErrorAction SilentlyContinue)
    $copyName = ([IO.Path]::GetFileName($log) + "." + ([Math]::Abs($log.GetHashCode())) + ".tail.txt")
    $copyPath = Join-Path $OutputRoot $copyName
    $tail | Set-Content -LiteralPath $copyPath -Encoding UTF8

    $logEvidence += [ordered]@{
        source_path = $log
        tail_copy   = $copyPath
        line_count  = $tail.Count
    }
}

$entries = @(Get-WisprUninstallEntries)
$processes = @(Get-WisprProcesses)

$brokenRefs = @()
foreach ($entry in $entries) {
    foreach ($check in $entry.command_checks) {
        if ($null -ne $check.exists -and -not $check.exists) {
            $brokenRefs += [ordered]@{
                registry_path = $entry.registry_path
                field         = $check.field
                executable    = $check.executable
            }
        }
    }
}

$expectedUpdateExe = Join-Path $localAppData "WisprFlow\Update.exe"
$expectedInstallRoot = Join-Path $localAppData "WisprFlow"

$classification = if ($entries.Count -gt 0 -and $brokenRefs.Count -gt 0) {
    "APP_INSTALLATION_BROKEN"
}
elseif ($entries.Count -gt 0 -and -not (Test-Path -LiteralPath $expectedInstallRoot)) {
    "APP_INSTALLATION_BROKEN"
}
elseif ($entries.Count -gt 0) {
    "APP_REGISTERED_REQUIRES_LOG_DIAGNOSIS"
}
else {
    "NO_WISPR_UNINSTALL_REGISTRATION_FOUND"
}

$report = [ordered]@{
    schema_version = "filesteward.wispr-recovery-diagnostic/v1"
    generated_at   = (Get-Date).ToString("o")
    mode           = "READ_ONLY_DIAGNOSIS"
    mutation       = $false
    classification = $classification
    expected_per_user_install = [ordered]@{
        root       = $expectedInstallRoot
        update_exe = $expectedUpdateExe
        root_exists = Test-Path -LiteralPath $expectedInstallRoot
        update_exe_exists = Test-Path -LiteralPath $expectedUpdateExe -PathType Leaf
    }
    uninstall_entries = $entries
    broken_registered_executables = $brokenRefs
    wispr_processes = $processes
    path_presence = $pathStates
    squirrel_logs = $logEvidence
    next_gate = "Inspect Squirrel log failure signature before any registry/app-data mutation."
    safety = [ordered]@{
        no_registry_mutation = $true
        no_process_termination = $true
        no_file_deletion = $true
        no_user_data_enumeration = $true
        private_output_is_under_ignored_var = $true
    }
}

$reportPath = Join-Path $OutputRoot "diagnostic.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText(
    $reportPath,
    ($report | ConvertTo-Json -Depth 12),
    $utf8NoBom
)

Write-Host ""
Write-Host "Wispr Flow recovery probe complete."
Write-Host "Classification: $classification"
Write-Host "Evidence: $reportPath"
Write-Host "Squirrel logs found: $($logEvidence.Count)"
Write-Host "Broken registered executable references: $($brokenRefs.Count)"
Write-Host ""
Write-Host "No registry keys, files, processes, or application state were modified."
