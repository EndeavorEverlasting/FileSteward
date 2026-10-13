"""Windows physical-disk to volume media mapping (observation only).

Maps a declared volume root to MSFT_PhysicalDisk.MediaType through CIM
associations. Fail closed: unavailable, ambiguous, or unspecified evidence
leaves media_type unset. Never invents SSD/HDD labels. Never records SMART
serials, model strings, or other private hardware identifiers in profile
metrics.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "WindowsMediaProbe",
    "default_windows_media_probe",
    "drive_letter_for_root",
    "normalize_media_type",
    "resolve_declared_volumes_media_type",
]

WindowsMediaProbe = Callable[[str], Mapping[str, Any]]

# MSFT_PhysicalDisk.MediaType (Storage CIM). Unspecified/unknown stay null.
_MEDIA_TYPE_CODE: dict[int, str | None] = {
    0: None,  # Unspecified
    3: "HDD",
    4: "SSD",
    5: "SCM",
}

_MEDIA_TYPE_NAME: dict[str, str | None] = {
    "hdd": "HDD",
    "ssd": "SSD",
    "scm": "SCM",
    "storage class memory": "SCM",
    "unspecified": None,
    "unknown": None,
}

# Compact PowerShell: logical disk -> partition -> disk drive index ->
# MSFT_PhysicalDisk.MediaType. Stdout is JSON with ok/media_type_code/reason only.
_PS_MEDIA_PROBE = r"""
$ErrorActionPreference = 'Stop'
$letter = $env:FILESTEWARD_DRIVE_LETTER
if (-not $letter -or $letter.Length -ne 1) {
  @{ ok = $false; reason = 'invalid_drive_letter' } | ConvertTo-Json -Compress
  exit 0
}
$deviceId = ($letter + ':')
$parts = @(Get-CimInstance -Query ("ASSOCIATORS OF {Win32_LogicalDisk.DeviceID='" + $deviceId + "'} WHERE AssocClass=Win32_LogicalDiskToPartition"))
if ($parts.Count -ne 1) {
  @{ ok = $false; reason = 'ambiguous_or_missing_partition' } | ConvertTo-Json -Compress
  exit 0
}
$partId = [string]$parts[0].DeviceID
$drives = @(Get-CimInstance -Query ("ASSOCIATORS OF {Win32_DiskPartition.DeviceID='" + $partId + "'} WHERE AssocClass=Win32_DiskDriveToDiskPartition"))
if ($drives.Count -ne 1) {
  @{ ok = $false; reason = 'ambiguous_or_missing_disk' } | ConvertTo-Json -Compress
  exit 0
}
$index = [int]$drives[0].Index
$phys = @(Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_PhysicalDisk |
  Where-Object { $_.DeviceId -eq ([string]$index) })
if ($phys.Count -ne 1) {
  @{ ok = $false; reason = 'ambiguous_or_missing_physical' } | ConvertTo-Json -Compress
  exit 0
}
@{ ok = $true; media_type_code = [int]$phys[0].MediaType } | ConvertTo-Json -Compress
"""


def drive_letter_for_root(root: str) -> str | None:
    """Return a single A–Z drive letter for a Windows path, else None."""
    drive, _tail = os.path.splitdrive(os.path.abspath(os.path.expanduser(root)))
    if len(drive) == 2 and drive[1] == ":" and drive[0].isalpha():
        return drive[0].upper()
    return None


def normalize_media_type(raw: Any) -> str | None:
    """Map CIM MediaType code or label to SSD/HDD/SCM; None when untrusted."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return _MEDIA_TYPE_CODE.get(raw)
    if isinstance(raw, float) and raw.is_integer():
        return _MEDIA_TYPE_CODE.get(int(raw))
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.isdigit():
            return _MEDIA_TYPE_CODE.get(int(text))
        return _MEDIA_TYPE_NAME.get(text.casefold())
    return None


def default_windows_media_probe(drive_letter: str) -> Mapping[str, Any]:
    """Live CIM probe for one drive letter. Prefer injecting a stub in tests."""
    letter = (drive_letter or "").strip().upper()
    if len(letter) != 1 or not letter.isalpha():
        return {"ok": False, "reason": "invalid_drive_letter"}
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return {"ok": False, "reason": "powershell_unavailable"}
    env = {**os.environ, "FILESTEWARD_DRIVE_LETTER": letter}
    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                _PS_MEDIA_PROBE,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"cim_probe_failed:{type(exc).__name__}"}
    if completed.returncode != 0:
        return {"ok": False, "reason": "cim_probe_nonzero_exit"}
    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {"ok": False, "reason": "cim_probe_empty_stdout"}
    try:
        payload = json.loads(stdout.splitlines()[-1])
    except (ValueError, TypeError):
        return {"ok": False, "reason": "cim_probe_invalid_json"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "cim_probe_invalid_payload"}
    return payload


def _media_from_probe_result(payload: Mapping[str, Any]) -> tuple[str | None, str]:
    if not payload.get("ok"):
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            reason = "cim_mapping_unavailable"
        return None, reason.strip()
    media = normalize_media_type(payload.get("media_type_code", payload.get("media_type")))
    if media is None:
        return None, "media_type_unspecified_or_unknown"
    return media, ""


def resolve_declared_volumes_media_type(
    volume_roots: Sequence[str],
    *,
    probe: WindowsMediaProbe | None = None,
    platform_name: str | None = None,
) -> tuple[str | None, str]:
    """Resolve a single media_type for declared roots, or a missing-metric reason.

    Returns ``(media_type, missing_reason)``. ``media_type`` is set only when
    every declared volume maps to the same trusted SSD/HDD/SCM label.
    """
    platform = (platform_name if platform_name is not None else sys.platform).casefold()
    active_probe = probe
    if active_probe is None:
        if not platform.startswith("win"):
            return None, "media_type: no trusted physical mapping"
        active_probe = default_windows_media_probe

    if not volume_roots:
        return None, "media_type: no declared volumes"

    seen_letters: set[str] = set()
    media_labels: list[str] = []
    for root in volume_roots:
        letter = drive_letter_for_root(root)
        if letter is None:
            return None, "media_type: volume lacks Windows drive letter"
        if letter in seen_letters:
            # Duplicate roots are refused earlier in observe(); still fail closed.
            continue
        seen_letters.add(letter)
        try:
            payload = active_probe(letter)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            return None, f"media_type: cim probe error ({type(exc).__name__})"
        if not isinstance(payload, Mapping):
            return None, "media_type: cim probe returned non-object"
        media, detail = _media_from_probe_result(payload)
        if media is None:
            return None, f"media_type: {detail}"
        media_labels.append(media)

    if not media_labels:
        return None, "media_type: no trusted physical mapping"
    unique = set(media_labels)
    if len(unique) != 1:
        return None, "media_type: ambiguous across declared volumes"
    return next(iter(unique)), ""
