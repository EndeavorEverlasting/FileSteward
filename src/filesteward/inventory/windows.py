"""Windows traversal predicates: no-follow, no-hydration, attribute truth.

All classification here uses metadata only. Nothing in this module (or
the scanner that consumes it) opens file content, which is what makes
cloud-placeholder no-hydration structural rather than aspirational.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CLOUD_PLACEHOLDER_ATTRIBUTES",
    "FILE_ATTRIBUTE_OFFLINE",
    "FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS",
    "FILE_ATTRIBUTE_RECALL_ON_OPEN",
    "FILE_ATTRIBUTE_REPARSE_POINT",
    "file_attributes",
    "is_cloud_placeholder",
    "is_reparse_point",
]

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000

#: Attribute flags that identify an online-only/cloud placeholder without
#: opening the file. Opening a placeholder risks hydration, which the
#: scanner contract forbids.
CLOUD_PLACEHOLDER_ATTRIBUTES = (
    FILE_ATTRIBUTE_OFFLINE
    | FILE_ATTRIBUTE_RECALL_ON_OPEN
    | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)


def file_attributes(st: Any) -> int:
    """``st_file_attributes`` when present (Windows), else 0."""

    value = getattr(st, "st_file_attributes", 0)
    return int(value) if value else 0


def is_reparse_point(st: Any) -> bool:
    return bool(file_attributes(st) & FILE_ATTRIBUTE_REPARSE_POINT)


def is_cloud_placeholder(st: Any) -> bool:
    return bool(file_attributes(st) & CLOUD_PLACEHOLDER_ATTRIBUTES)
