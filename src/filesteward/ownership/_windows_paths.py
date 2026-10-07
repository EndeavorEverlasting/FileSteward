"""Private path helpers for Windows application attribution."""

from __future__ import annotations

import os
import re
from pathlib import PureWindowsPath
from typing import Optional

__all__ = [
    "command_executable",
    "expand_windows_path",
    "normalize_path_key",
    "path_intersects",
]


_QUOTED_EXE = re.compile(r'^\s*"([^"]+\.(?:exe|cmd|bat|msi))"', re.IGNORECASE)
_BARE_EXE = re.compile(r"^\s*([^\s]+\.(?:exe|cmd|bat|msi))", re.IGNORECASE)


def expand_windows_path(value: Optional[str]) -> str:
    """Expand environment variables; empty/None becomes ''."""

    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return os.path.expandvars(text)


def normalize_path_key(path: str) -> tuple[str, ...]:
    """Case-folded Windows path parts for containment checks."""

    expanded = expand_windows_path(path)
    if not expanded:
        return ()
    return tuple(part.lower() for part in PureWindowsPath(expanded).parts)


def path_intersects(candidate: str, anchor: str) -> bool:
    """True when candidate equals or is under/above anchor (shared tree)."""

    left = normalize_path_key(candidate)
    right = normalize_path_key(anchor)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) > len(right) and left[: len(right)] == right:
        return True
    if len(right) > len(left) and right[: len(left)] == left:
        return True
    return False


def command_executable(command: Optional[str]) -> str:
    """Extract the primary executable path from an uninstall/modify command."""

    if command is None:
        return ""
    text = str(command).strip()
    if not text:
        return ""
    quoted = _QUOTED_EXE.match(text)
    if quoted:
        return expand_windows_path(quoted.group(1))
    bare = _BARE_EXE.match(text)
    if bare:
        return expand_windows_path(bare.group(1))
    return ""
