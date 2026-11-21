"""Read-only coverage of regular files in a validated inventory snapshot."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping

from filesteward.models import CleanupDisposition, EntryType

_CLASSIFIED = frozenset({
    CleanupDisposition.KEEP_PROVEN,
    CleanupDisposition.PROTECTED,
    CleanupDisposition.RECLAIM_PROVEN,
})


@dataclass(frozen=True)
class Coverage:
    files: int
    unmeasured: int
    bytes_by_disposition: tuple[int, ...]

    @property
    def total_bytes(self) -> int:
        return sum(self.bytes_by_disposition)

    @property
    def classified_bytes(self) -> int:
        return sum(
            size for disposition, size in zip(CleanupDisposition, self.bytes_by_disposition)
            if disposition in _CLASSIFIED
        )


@dataclass(frozen=True)
class StorageCoverage:
    total: Coverage
    sectors: tuple[tuple[str, Coverage], ...]


def summarize_inventory(
    rows: Iterable[Mapping[str, str]], root: str | None
) -> StorageCoverage:
    path_type = PureWindowsPath if root and PureWindowsPath(root).is_absolute() else PurePosixPath
    scan_root = path_type(root) if root else None
    labels: dict[tuple[str, str], str] = {}
    groups: dict[tuple[str, str], dict[CleanupDisposition, int]] = defaultdict(lambda: defaultdict(int))
    files: dict[tuple[str, str], int] = defaultdict(int)
    unmeasured: dict[tuple[str, str], int] = defaultdict(int)
    total: dict[CleanupDisposition, int] = defaultdict(int)

    for row in rows:
        if row["entry_type"] != EntryType.FILE.value or any(
            row.get(flag, "").lower() == "true"
            for flag in ("is_cloud_placeholder", "is_symlink", "is_reparse_point")
        ):
            continue
        path = path_type(row["path"])
        relative = (
            path.relative_to(scan_root).parts
            if scan_root and scan_root.is_absolute() and path.is_relative_to(scan_root)
            else ()
        )
        if not relative or ".." in relative:
            key, label = ("unmapped", ""), "Sector unavailable"
        elif len(relative) == 1:
            key, label = ("root", ""), "Files in scan root"
        else:
            folder = relative[0]
            key = ("folder", folder.casefold() if path_type is PureWindowsPath else folder)
            label = folder + ("\\" if path_type is PureWindowsPath else "/")
        labels.setdefault(key, label)
        files[key] += 1
        disposition = CleanupDisposition(row["disposition"])
        raw_size = row.get("logical_size_bytes")
        size = int(raw_size) if raw_size else None
        if size is None or size < 0:
            unmeasured[key] += 1
            continue
        groups[key][disposition] += size
        total[disposition] += size

    sectors = [
        (label, Coverage(files[key], unmeasured[key], tuple(groups[key][d] for d in CleanupDisposition)))
        for key, label in labels.items()
    ]
    sectors.sort(key=lambda sector: (-sector[1].total_bytes, sector[0].casefold(), sector[0]))
    return StorageCoverage(
        Coverage(sum(files.values()), sum(unmeasured.values()), tuple(total[d] for d in CleanupDisposition)),
        tuple(sectors),
    )
