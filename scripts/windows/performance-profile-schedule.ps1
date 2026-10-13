<#
.SYNOPSIS
  Opt-in FileSteward workstation performance profile Task Scheduler helper.

.DESCRIPTION
  Thin operator wrapper around:
    python -m filesteward.profiles.schedule ...

  Never invents a default cadence. Never registers unless -Authorize is supplied
  for register/disable/unregister. Live schtasks requires -LiveSchtasks on Windows.

  Does not store passwords. Does not elevate to SYSTEM.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("preview", "inspect", "register", "run-once", "status", "disable", "unregister")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$HostKey,

    [string[]]$Volume,

    [string]$Python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),

    [string]$Checkout,

    [string]$Cadence,

    [string]$Authorize,

    [switch]$LiveSchtasks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Python)) {
    throw "Known Python executable path required (-Python)."
}

$argsList = @("-m", "filesteward.profiles.schedule", $Action, "--host-key", $HostKey)

switch ($Action) {
    { $_ -in @("preview", "register") } {
        if (-not $Volume -or $Volume.Count -lt 1) {
            throw "At least one -Volume is required for $Action."
        }
        if ([string]::IsNullOrWhiteSpace($Cadence)) {
            throw "Cadence is required (DAILY/HH:MM or WEEKLY/DAY/HH:MM); no default is invented."
        }
        foreach ($root in $Volume) {
            $argsList += @("--volume", $root)
        }
        $argsList += @("--python", $Python, "--cadence", $Cadence)
        if (-not [string]::IsNullOrWhiteSpace($Checkout)) {
            $argsList += @("--checkout", $Checkout)
        }
    }
    "run-once" {
        if (-not $Volume -or $Volume.Count -lt 1) {
            throw "At least one -Volume is required for run-once."
        }
        foreach ($root in $Volume) {
            $argsList += @("--volume", $root)
        }
        $argsList += @("--python", $Python)
        if (-not [string]::IsNullOrWhiteSpace($Checkout)) {
            $argsList += @("--checkout", $Checkout)
        }
    }
    { $_ -in @("inspect", "status", "disable", "unregister") } {
        # host-key only (+ authorize / live flags below)
    }
}

if ($Action -eq "register") {
    if ([string]::IsNullOrWhiteSpace($Authorize)) {
        throw "Explicit -Authorize OPERATOR_OPT_IN_REGISTER_PROFILE_SCHEDULE is required."
    }
    $argsList += @("--authorize", $Authorize)
}
if ($Action -eq "disable") {
    if ([string]::IsNullOrWhiteSpace($Authorize)) {
        throw "Explicit -Authorize OPERATOR_OPT_IN_DISABLE_PROFILE_SCHEDULE is required."
    }
    $argsList += @("--authorize", $Authorize)
}
if ($Action -eq "unregister") {
    if ([string]::IsNullOrWhiteSpace($Authorize)) {
        throw "Explicit -Authorize OPERATOR_OPT_IN_UNREGISTER_PROFILE_SCHEDULE is required."
    }
    $argsList += @("--authorize", $Authorize)
}

if ($LiveSchtasks) {
    if ($Action -in @("inspect", "register", "status", "disable", "unregister")) {
        $argsList += "--live-schtasks"
    }
}

& $Python @argsList
exit $LASTEXITCODE
