"""Read-only HUMAN_REVIEW receipt triage: path-prefix buckets only.

This module never nominates reclaim, never mutates source files, and never
promotes bucket hints into ``RECLAIM_PROVEN``. Hints are operator-facing
contract candidates derived from deterministic path parts only.
"""

from __future__ import annotations

import csv
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping, Optional, Sequence, Type

from filesteward.models import CleanupDisposition

__all__ = [
    "BUCKET_COLUMNS",
    "BucketRow",
    "TriageResult",
    "aggregate_human_review_buckets",
    "contract_hint_tags",
    "path_prefix",
    "receipt_path_class",
    "triage_run_dir",
    "write_bucket_artifacts",
]

BUCKET_COLUMNS = (
    "prefix",
    "depth",
    "item_count",
    "logical_bytes_known",
    "unknown_size_count",
    "contract_hint_tags",
)

_REQUIRED_REVIEW_COLUMNS = frozenset({"path", "disposition", "logical_size_bytes"})

# Deterministic path-part hints only. Never disposition authority.
_HINT_PARTS: dict[str, frozenset[str]] = {
    "temp": frozenset({"temp", "tmp", "temporary internet files"}),
    "cache": frozenset({"cache", "caches", ".cache"}),
    "npm": frozenset({"npm-cache", "node_modules"}),
    "pip": frozenset({"pip"}),
    "nuget": frozenset({"nuget", ".nuget"}),
    "cargo": frozenset({"cargo"}),
    "build": frozenset({"obj", ".tox"}),
}


@dataclass(frozen=True)
class BucketRow:
    prefix: str
    depth: int
    item_count: int
    logical_bytes_known: int
    unknown_size_count: int
    contract_hint_tags: tuple[str, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "prefix": self.prefix,
            "depth": self.depth,
            "item_count": self.item_count,
            "logical_bytes_known": self.logical_bytes_known,
            "unknown_size_count": self.unknown_size_count,
            "contract_hint_tags": ",".join(self.contract_hint_tags),
        }


@dataclass(frozen=True)
class TriageResult:
    run_dir: Path
    depth: int
    human_review_rows: int
    buckets: tuple[BucketRow, ...]
    csv_path: Path
    markdown_path: Path


def receipt_path_class(raw: str) -> Type[PurePath]:
    """Select PureWindowsPath vs PurePosixPath from the recorded path text."""

    text = (raw or "").strip()
    if not text:
        raise ValueError("human-review path must be non-empty")
    if len(text) >= 2 and text[1] == ":":
        return PureWindowsPath
    if "\\" in text and "/" not in text:
        return PureWindowsPath
    if text.startswith("\\\\") or text.startswith("//"):
        return PureWindowsPath
    return PurePosixPath


def _normalize_path(raw: str) -> PurePath:
    flavor = receipt_path_class(raw)
    return flavor(raw.strip())


def path_prefix(path: PurePath, depth: int) -> str:
    """Return the first ``depth`` path parts joined as a prefix string."""

    if depth < 1:
        raise ValueError("depth must be >= 1")
    parts = path.parts
    if not parts:
        raise ValueError("path has no parts")
    take = min(depth, len(parts))
    return str(type(path)(*parts[:take]))


def contract_hint_tags(prefix: str) -> tuple[str, ...]:
    flavor = receipt_path_class(prefix)
    parts = {part.lower() for part in flavor(prefix).parts}
    return tuple(tag for tag, needles in _HINT_PARTS.items() if parts & needles)


def _parse_size(raw: object) -> tuple[Optional[int], bool]:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None, True
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"invalid logical_size_bytes: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"logical_size_bytes must be >= 0; got {value}")
    return value, False


def aggregate_human_review_buckets(
    review_rows: Iterable[Mapping[str, object]],
    *,
    depth: int,
) -> tuple[BucketRow, ...]:
    """Aggregate HUMAN_REVIEW/UNKNOWN review rows into path-prefix buckets."""

    if depth < 1:
        raise ValueError("depth must be >= 1")

    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    # totals[prefix] = [item_count, logical_bytes_known, unknown_size_count]

    for row in review_rows:
        disposition = str(row.get("disposition") or "").strip()
        if disposition not in (
            CleanupDisposition.HUMAN_REVIEW.value,
            CleanupDisposition.UNKNOWN.value,
        ):
            continue
        prefix = path_prefix(_normalize_path(str(row.get("path") or "")), depth)
        size, unknown = _parse_size(row.get("logical_size_bytes"))
        bucket = totals[prefix]
        bucket[0] += 1
        if unknown or size is None:
            bucket[2] += 1
        else:
            bucket[1] += size

    rows = [
        BucketRow(
            prefix=prefix,
            depth=depth,
            item_count=counts[0],
            logical_bytes_known=counts[1],
            unknown_size_count=counts[2],
            contract_hint_tags=contract_hint_tags(prefix),
        )
        for prefix, counts in totals.items()
    ]
    rows.sort(key=lambda item: (-item.logical_bytes_known, -item.item_count, item.prefix))
    return tuple(rows)


def _atomic_write_text(path: Path, text: str) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(directory),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_csv(path: Path, buckets: Sequence[BucketRow]) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(directory),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(BUCKET_COLUMNS))
            writer.writeheader()
            for row in buckets:
                writer.writerow(row.as_mapping())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_bucket_artifacts(
    run_dir: Path,
    buckets: Sequence[BucketRow],
    *,
    depth: int,
    human_review_rows: int,
) -> tuple[Path, Path]:
    """Write bucket CSV + markdown under an existing run directory."""

    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ValueError(f"run directory not found: {run_dir}")

    csv_path = run_dir / "human-review-buckets.csv"
    md_path = run_dir / "human-review-buckets.md"

    lines = [
        f"# HUMAN_REVIEW path-prefix triage — depth {depth}",
        "",
        "Read-only bucket totals only. No reclaim nomination, no approval,",
        "no apply, and no deletion. `contract_hint_tags` are deterministic",
        "path-part candidates for operator `--contract` decisions;",
        "they are **not** reclaim authority.",
        "",
        f"- human-review/unknown rows considered: {human_review_rows}",
        f"- buckets: {len(buckets)}",
        f"- depth: {depth}",
        "",
        "| prefix | items | logical_bytes_known | unknown_size_count | contract_hint_tags |",
        "|---|---:|---:|---:|---|",
    ]
    for row in buckets[:50]:
        tags = ",".join(row.contract_hint_tags) if row.contract_hint_tags else ""
        lines.append(
            f"| `{row.prefix}` | {row.item_count} | {row.logical_bytes_known} | "
            f"{row.unknown_size_count} | {tags} |"
        )
    if len(buckets) > 50:
        lines.append("")
        lines.append(f"_Showing top 50 of {len(buckets)} buckets by logical_bytes_known._")
    lines.append("")
    lines.append(
        "Next gate: operator declares regenerable `--contract` prefixes and "
        "optional `--target-free-bytes`, then a fresh read-only rescan."
    )
    lines.append("")

    # Write both temps then publish CSV then markdown for a tighter pair.
    _atomic_write_csv(csv_path, buckets)
    _atomic_write_text(md_path, "\n".join(lines))
    return csv_path, md_path


def triage_run_dir(run_dir: Path, *, depth: int = 2) -> TriageResult:
    """Stream ``human-review.csv`` from a run directory and write bucket artifacts."""

    run_dir = Path(run_dir)
    review_path = run_dir / "human-review.csv"
    if not review_path.is_file():
        raise ValueError(f"human-review.csv not found under {run_dir}")

    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    considered = 0

    with review_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("human-review.csv has no header row")
        present = {name.strip() for name in reader.fieldnames if name}
        missing = sorted(_REQUIRED_REVIEW_COLUMNS - present)
        if missing:
            raise ValueError(
                "human-review.csv missing required columns: "
                + ", ".join(missing)
            )
        for row in reader:
            disposition = str(row.get("disposition") or "").strip()
            if disposition not in (
                CleanupDisposition.HUMAN_REVIEW.value,
                CleanupDisposition.UNKNOWN.value,
            ):
                continue
            considered += 1
            prefix = path_prefix(
                _normalize_path(str(row.get("path") or "")), depth
            )
            size, unknown = _parse_size(row.get("logical_size_bytes"))
            bucket = totals[prefix]
            bucket[0] += 1
            if unknown or size is None:
                bucket[2] += 1
            else:
                bucket[1] += size

    buckets = [
        BucketRow(
            prefix=prefix,
            depth=depth,
            item_count=counts[0],
            logical_bytes_known=counts[1],
            unknown_size_count=counts[2],
            contract_hint_tags=contract_hint_tags(prefix),
        )
        for prefix, counts in totals.items()
    ]
    buckets.sort(
        key=lambda item: (-item.logical_bytes_known, -item.item_count, item.prefix)
    )
    bucket_tuple = tuple(buckets)
    csv_path, md_path = write_bucket_artifacts(
        run_dir,
        bucket_tuple,
        depth=depth,
        human_review_rows=considered,
    )
    return TriageResult(
        run_dir=run_dir,
        depth=depth,
        human_review_rows=considered,
        buckets=bucket_tuple,
        csv_path=csv_path,
        markdown_path=md_path,
    )
