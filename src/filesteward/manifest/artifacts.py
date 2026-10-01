"""Artifact writers and validation: serialization only, no disposition logic.

Dependency direction (P04 section 6): artifact writers do not decide
disposition. Every writer asserts the disposition invariants it was
handed, and ``validate_run`` re-derives every mechanical fact (columns,
arithmetic, reconciliation, forbidden language) from the bytes on disk.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from filesteward.models import CleanupDisposition

__all__ = [
    "EXCLUSIONS_COLUMNS",
    "INVENTORY_COLUMNS",
    "PLAN_COLUMNS",
    "PROJECTION_QUALITIES",
    "REQUIRED_SUMMARY_SECTIONS",
    "REVIEW_COLUMNS",
    "SummaryModel",
    "validate_run",
    "write_cleanup_plan",
    "write_human_review",
    "write_inventory",
    "write_protected_exclusions",
    "write_run_metadata",
    "write_summary",
]

#: P04 section 14 column order, verbatim.
PLAN_COLUMNS = (
    "priority",
    "item_id",
    "path",
    "logical_size_bytes",
    "allocated_size_bytes",
    "projected_reclaim_bytes",
    "reclaim_basis",
    "disposition",
    "confidence_basis",
    "evidence",
    "protection_check",
    "recoverability",
    "canonical_survivor",
    "proposed_action",
    "cumulative_projected_reclaim_bytes",
    "projection_quality",
)

REVIEW_COLUMNS = (
    "item_id",
    "path",
    "disposition",
    "logical_size_bytes",
    "allocated_size_bytes",
    "why_ambiguous",
    "what_operator_should_check",
    "known_context",
    "risk_if_acted_on",
)

EXCLUSIONS_COLUMNS = (
    "item_id",
    "path",
    "disposition",
    "protection_reason",
    "protection_source",
    "relationship",
)

INVENTORY_COLUMNS = (
    "item_id",
    "path",
    "entry_type",
    "disposition",
    "evidence_state",
    "protection_relation",
    "scan_completeness",
    "scan_error",
    "logical_size_bytes",
    "allocated_size_bytes",
    "modified_at",
    "link_count",
    "is_symlink",
    "is_reparse_point",
    "is_cloud_placeholder",
)

PROJECTION_QUALITIES = frozenset(
    {"allocated-evidence", "estimate-logical", "container-row"}
)

REQUIRED_SUMMARY_SECTIONS = (
    "## Scope",
    "## Inventory coverage",
    "## Dispositions",
    "## Reclaim projection",
    "## Free-space stop point",
    "## Human review queue",
    "## Protected exclusions",
    "## Unknown coverage",
    "## Authorization",
)

#: Language that pressures or scores a cleanup decision. Forbidden in
#: any prose cell of plan/review/exclusion artifacts.
FORBIDDEN_CELL_PHRASES = (
    "probably safe",
    "likely safe",
    "safe to delete",
    "delete score",
    "confidence score",
    "persuasion",
    "recommended for removal",
    "recommended for deletion",
    "recommended for delete",
)

_SCORE_WORD = re.compile(r"\bscore\b", re.IGNORECASE)

_REVIEW_TEXT_COLUMNS = (
    "why_ambiguous",
    "what_operator_should_check",
    "known_context",
    "risk_if_acted_on",
)
_PLAN_TEXT_COLUMNS = (
    "reclaim_basis",
    "confidence_basis",
    "evidence",
    "recoverability",
    "canonical_survivor",
    "proposed_action",
)

_ARTIFACT_NAMES = (
    "cleanup-plan.csv",
    "human-review.csv",
    "protected-exclusions.csv",
    "inventory.csv",
    "cleanup-summary.md",
    "run.json",
)


def _opt_str(value: Any) -> str:
    return "" if value is None else str(value)


def _write_csv(
    path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            missing = [column for column in columns if column not in row]
            if missing:
                raise ValueError(
                    f"{path.name}: row missing column(s) {missing}"
                )
            writer.writerow([_opt_str(row[column]) for column in columns])


def write_cleanup_plan(
    path: Path, rows: Sequence[Mapping[str, Any]]
) -> None:
    """Write ``cleanup-plan.csv``. Only ``RECLAIM_PROVEN`` rows, ever."""

    prepared: list[dict[str, Any]] = []
    running = 0
    for index, row in enumerate(rows, start=1):
        if row.get("disposition") != CleanupDisposition.RECLAIM_PROVEN.value:
            raise ValueError(
                "cleanup-plan.csv accepts only RECLAIM_PROVEN rows; got "
                f"{row.get('disposition')!r} for item {row.get('item_id')!r}"
            )
        quality = row.get("projection_quality")
        if quality not in PROJECTION_QUALITIES:
            raise ValueError(
                f"cleanup-plan.csv: unknown projection_quality {quality!r}"
            )
        projected = row.get("projected_reclaim_bytes")
        if projected is not None:
            running += int(projected)
        prepared.append(
            {
                **row,
                "priority": index,
                "cumulative_projected_reclaim_bytes": running,
            }
        )
    _write_csv(path, PLAN_COLUMNS, prepared)


def write_human_review(
    path: Path, rows: Sequence[Mapping[str, Any]]
) -> None:
    allowed = {
        CleanupDisposition.HUMAN_REVIEW.value,
        CleanupDisposition.UNKNOWN.value,
    }
    for row in rows:
        if row.get("disposition") not in allowed:
            raise ValueError(
                "human-review.csv accepts only HUMAN_REVIEW/UNKNOWN rows; "
                f"got {row.get('disposition')!r} for item {row.get('item_id')!r}"
            )
    _write_csv(path, REVIEW_COLUMNS, rows)


def write_protected_exclusions(
    path: Path, rows: Sequence[Mapping[str, Any]]
) -> None:
    relationships = {"SELF", "DESCENDANT", "ANCESTOR"}
    for row in rows:
        if row.get("relationship") not in relationships:
            raise ValueError(
                "protected-exclusions.csv: unknown relationship "
                f"{row.get('relationship')!r} for item {row.get('item_id')!r}"
            )
        for column in ("protection_reason", "protection_source"):
            if not row.get(column):
                raise ValueError(
                    f"protected-exclusions.csv: empty {column} for item "
                    f"{row.get('item_id')!r}"
                )
    _write_csv(path, EXCLUSIONS_COLUMNS, rows)


def write_inventory(
    path: Path, rows: Sequence[Mapping[str, Any]]
) -> None:
    _write_csv(path, INVENTORY_COLUMNS, rows)


def write_run_metadata(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(data), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class SummaryModel:
    """Facts computed by the run; rendering stays in this module."""

    run_id: str
    root: str
    run_dir: str
    inventory_items: int
    logical_bytes_observed: int
    logical_unknown_items: int
    allocated_known_bytes: int
    allocated_known_items: int
    allocation_note: str
    disposition_counts: Mapping[str, int]
    plan_rows: int
    projected_reclaim_total: int
    projected_allocated_bytes: int
    projected_estimate_bytes: int
    container_rows: int
    baseline_free_bytes: Optional[int]
    target_free_bytes: Optional[int]
    cumulative_projected_reclaim_bytes: int
    stop_row: Optional[int]
    stop_note: str
    human_review_count: int
    human_review_bytes: int
    human_review_unknown_size: int
    protected_count: int
    protected_breakdown: Mapping[str, int]
    unknown_count: int
    unknown_bytes: int
    keep_count: int


def _fmt(value: Optional[int]) -> str:
    return "unknown" if value is None else str(value)


def render_summary(model: SummaryModel) -> str:
    counts = model.disposition_counts
    lines = [
        f"# FileSteward cleanup summary — run {model.run_id}",
        "",
        "Read-only analysis. This run produced no approval, no apply, and no deletion.",
        "",
        "## Scope",
        f"- scan root: {model.root}",
        f"- run directory: {model.run_dir}",
        "",
        "## Inventory coverage",
        f"- items observed: {model.inventory_items}",
        f"- logical bytes observed: {model.logical_bytes_observed} "
        f"(unknown-size items: {model.logical_unknown_items})",
        f"- allocated bytes known: {model.allocated_known_bytes} "
        f"(items with allocation evidence: {model.allocated_known_items})",
        f"- allocation note: {model.allocation_note}",
        "",
        "## Dispositions",
        f"- RECLAIM_PROVEN: {counts.get('RECLAIM_PROVEN', 0)}",
        f"- HUMAN_REVIEW: {counts.get('HUMAN_REVIEW', 0)}",
        f"- PROTECTED: {counts.get('PROTECTED', 0)}",
        f"- KEEP_PROVEN: {counts.get('KEEP_PROVEN', 0)}",
        f"- UNKNOWN: {counts.get('UNKNOWN', 0)}",
        "",
        "## Reclaim projection",
        f"- proposed plan rows: {model.plan_rows}",
        f"- projected reclaim (total): {model.projected_reclaim_total} bytes",
        f"- projected with allocation evidence: {model.projected_allocated_bytes} bytes",
        f"- projected as estimate: {model.projected_estimate_bytes} bytes",
        f"- container rows (bytes counted on descendant rows): {model.container_rows}",
        "- estimate rows are not proven reclaimable bytes",
        "",
        "## Free-space stop point",
        f"- baseline free bytes: {_fmt(model.baseline_free_bytes)}",
        f"- target free bytes: {_fmt(model.target_free_bytes)}",
        f"- cumulative projected reclaim: {model.cumulative_projected_reclaim_bytes}",
        f"- stop point: {model.stop_note}",
        "",
        "## Human review queue",
        f"- items: {model.human_review_count}",
        f"- logical bytes: {model.human_review_bytes} "
        f"(unknown-size items: {model.human_review_unknown_size})",
        "",
        "## Protected exclusions",
        f"- items: {model.protected_count}",
        "- relationship breakdown: "
        + ", ".join(
            f"{name}={model.protected_breakdown.get(name, 0)}"
            for name in ("SELF", "DESCENDANT", "ANCESTOR")
        ),
        "",
        "## Unknown coverage",
        f"- items with incomplete observation: {model.unknown_count}",
        f"- logical bytes: {model.unknown_bytes}",
        "",
        "## Authorization",
        "All rows are UNAPPROVED proposed-action evidence.",
        "This run produced no operator approval, no apply, and no deletion.",
        "Future ordinary cleanup actions go to quarantine first with an "
        "audit/restore receipt.",
        "",
    ]
    return "\n".join(lines)


def write_summary(path: Path, model: SummaryModel) -> None:
    path.write_text(render_summary(model), encoding="utf-8")


def _read_csv(
    path: Path, columns: Sequence[str], errors: list[str]
) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = tuple(next(reader))
        except StopIteration:
            errors.append(f"{path.name}: file is empty")
            return []
        if header != tuple(columns):
            errors.append(
                f"{path.name}: header mismatch; expected {list(columns)}, "
                f"found {list(header)}"
            )
            return []
        rows: list[dict[str, str]] = []
        for number, raw in enumerate(reader, start=2):
            if len(raw) != len(columns):
                errors.append(
                    f"{path.name}: row {number} has {len(raw)} fields, "
                    f"expected {len(columns)}"
                )
                continue
            rows.append(dict(zip(columns, raw)))
        return rows


def _opt_int(text: str) -> Optional[int]:
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _scan_cells(
    name: str, rows: Sequence[Mapping[str, str]], columns: Sequence[str]
) -> list[str]:
    errors: list[str] = []
    for number, row in enumerate(rows, start=2):
        for column in columns:
            cell = row.get(column, "").casefold()
            for phrase in FORBIDDEN_CELL_PHRASES:
                if phrase in cell:
                    errors.append(
                        f"{name}: row {number} column {column} contains "
                        f"forbidden phrase {phrase!r}"
                    )
            if _SCORE_WORD.search(cell):
                errors.append(
                    f"{name}: row {number} column {column} contains "
                    "score language"
                )
    return errors


def _bucket(row: Mapping[str, str]) -> Optional[str]:
    """Expected artifact for one inventory row, mirroring run routing."""

    relation = row.get("protection_relation")
    disposition = row.get("disposition")
    if relation in ("SELF", "DESCENDANT", "ANCESTOR"):
        return "protected-exclusions.csv"
    if disposition == CleanupDisposition.RECLAIM_PROVEN.value:
        return "cleanup-plan.csv"
    if disposition in (
        CleanupDisposition.HUMAN_REVIEW.value,
        CleanupDisposition.UNKNOWN.value,
    ):
        return "human-review.csv"
    if disposition == CleanupDisposition.KEEP_PROVEN.value:
        return None
    return "<invalid>"


def validate_run(run_dir: Path) -> list[str]:
    """Re-derive every mechanical artifact fact. Returns error strings."""

    run_dir = Path(run_dir)
    errors: list[str] = []
    paths = {name: run_dir / name for name in _ARTIFACT_NAMES}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"missing artifact: {name}")
    if errors:
        return errors

    plan = _read_csv(paths["cleanup-plan.csv"], PLAN_COLUMNS, errors)
    review = _read_csv(paths["human-review.csv"], REVIEW_COLUMNS, errors)
    exclusions = _read_csv(
        paths["protected-exclusions.csv"], EXCLUSIONS_COLUMNS, errors
    )
    inventory = _read_csv(paths["inventory.csv"], INVENTORY_COLUMNS, errors)
    if errors:
        return errors

    for name, columns in (
        ("cleanup-plan.csv", PLAN_COLUMNS),
        ("human-review.csv", REVIEW_COLUMNS),
        ("protected-exclusions.csv", EXCLUSIONS_COLUMNS),
        ("inventory.csv", INVENTORY_COLUMNS),
    ):
        for column in columns:
            if "score" in column.casefold():
                errors.append(f"{name}: forbidden column {column!r}")

    # Disposition membership per row.
    for number, row in enumerate(plan, start=2):
        if row["disposition"] != CleanupDisposition.RECLAIM_PROVEN.value:
            errors.append(
                f"cleanup-plan.csv: row {number} disposition "
                f"{row['disposition']!r} is not RECLAIM_PROVEN"
            )
        if row["projection_quality"] not in PROJECTION_QUALITIES:
            errors.append(
                f"cleanup-plan.csv: row {number} projection_quality "
                f"{row['projection_quality']!r} is not a known label"
            )
    allowed_review = {
        CleanupDisposition.HUMAN_REVIEW.value,
        CleanupDisposition.UNKNOWN.value,
    }
    for number, row in enumerate(review, start=2):
        if row["disposition"] not in allowed_review:
            errors.append(
                f"human-review.csv: row {number} disposition "
                f"{row['disposition']!r} is not HUMAN_REVIEW/UNKNOWN"
            )
    for number, row in enumerate(exclusions, start=2):
        if row["relationship"] not in ("SELF", "DESCENDANT", "ANCESTOR"):
            errors.append(
                f"protected-exclusions.csv: row {number} relationship "
                f"{row['relationship']!r} unknown"
            )
        for column in ("protection_reason", "protection_source"):
            if not row[column]:
                errors.append(
                    f"protected-exclusions.csv: row {number} empty {column}"
                )

    # Forbidden language in prose columns.
    errors.extend(
        _scan_cells("cleanup-plan.csv", plan, _PLAN_TEXT_COLUMNS)
    )
    errors.extend(
        _scan_cells("human-review.csv", review, _REVIEW_TEXT_COLUMNS)
    )

    # Plan arithmetic: priorities and cumulative column.
    running = 0
    for index, row in enumerate(plan, start=1):
        if row["priority"] != str(index):
            errors.append(
                f"cleanup-plan.csv: row {index + 1} priority "
                f"{row['priority']!r} out of sequence"
            )
        projected = _opt_int(row["projected_reclaim_bytes"])
        if projected is not None:
            running += projected
        recorded = _opt_int(row["cumulative_projected_reclaim_bytes"])
        if recorded != running:
            errors.append(
                f"cleanup-plan.csv: row {index + 1} cumulative "
                f"{recorded!r} does not equal running total {running}"
            )
    cumulative = running

    # Inventory identity and reconciliation by stable item_id.
    inventory_by_id: dict[str, dict[str, str]] = {}
    inventory_by_path: dict[str, str] = {}
    for number, row in enumerate(inventory, start=2):
        item_id = row["item_id"]
        if item_id in inventory_by_id:
            errors.append(f"inventory.csv: duplicate item_id {item_id}")
        if row["path"] in inventory_by_path:
            errors.append(
                f"inventory.csv: duplicate path {row['path']!r}"
            )
        inventory_by_id[item_id] = row
        inventory_by_path[row["path"]] = item_id

    queue_maps: dict[str, dict[str, dict[str, str]]] = {
        "cleanup-plan.csv": {},
        "human-review.csv": {},
        "protected-exclusions.csv": {},
    }
    for name, rows in (
        ("cleanup-plan.csv", plan),
        ("human-review.csv", review),
        ("protected-exclusions.csv", exclusions),
    ):
        for number, row in enumerate(rows, start=2):
            item_id = row["item_id"]
            if item_id in queue_maps[name]:
                errors.append(f"{name}: duplicate item_id {item_id}")
            queue_maps[name][item_id] = row
    for left, right in (
        ("cleanup-plan.csv", "human-review.csv"),
        ("cleanup-plan.csv", "protected-exclusions.csv"),
        ("human-review.csv", "protected-exclusions.csv"),
    ):
        overlap = set(queue_maps[left]) & set(queue_maps[right])
        for item_id in sorted(overlap):
            errors.append(
                f"item {item_id} appears in both {left} and {right}"
            )

    keep_count = 0
    for item_id, inv in inventory_by_id.items():
        bucket = _bucket(inv)
        if bucket is None:
            keep_count += 1
            if any(
                item_id in queue_maps[name] for name in queue_maps
            ):
                errors.append(
                    f"item {item_id} is KEEP_PROVEN but appears in a queue"
                )
            continue
        if bucket == "<invalid>":
            errors.append(
                f"item {item_id}: disposition {inv['disposition']!r} "
                "without a protection relation"
            )
            continue
        if item_id not in queue_maps[bucket]:
            errors.append(
                f"item {item_id} with disposition {inv['disposition']!r} "
                f"and relation {inv['protection_relation']!r} is missing "
                f"from {bucket}"
            )
            continue
        queued = queue_maps[bucket][item_id]
        if queued["disposition"] != inv["disposition"]:
            errors.append(
                f"item {item_id}: queued disposition "
                f"{queued['disposition']!r} does not match inventory "
                f"{inv['disposition']!r}"
            )
        if bucket == "protected-exclusions.csv":
            if queued["relationship"] != inv["protection_relation"]:
                errors.append(
                    f"item {item_id}: exclusion relationship "
                    f"{queued['relationship']!r} does not match inventory "
                    f"relation {inv['protection_relation']!r}"
                )
    accounted = len(plan) + len(review) + len(exclusions) + keep_count
    if accounted != len(inventory):
        errors.append(
            f"reconciliation: {accounted} accounted rows "
            f"(plan {len(plan)}, review {len(review)}, exclusions "
            f"{len(exclusions)}, keep {keep_count}) != inventory "
            f"{len(inventory)}"
        )

    # run.json facts.
    try:
        metadata = json.loads(paths["run.json"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"run.json: unreadable ({exc})")
        metadata = {}
    if metadata:
        if metadata.get("authorization_state") != "UNAPPROVED":
            errors.append("run.json: authorization_state must be UNAPPROVED")
        recorded_cumulative = metadata.get(
            "cumulative_projected_reclaim_bytes"
        )
        if recorded_cumulative != cumulative:
            errors.append(
                "run.json: cumulative_projected_reclaim_bytes "
                f"{recorded_cumulative!r} does not match plan total "
                f"{cumulative}"
            )
        if metadata.get("plan_rows") != len(plan):
            errors.append(
                f"run.json: plan_rows {metadata.get('plan_rows')!r} does "
                f"not match {len(plan)} plan rows"
            )
        counts: dict[str, int] = {}
        for row in inventory:
            counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1
        if metadata.get("disposition_counts") != counts:
            errors.append(
                "run.json: disposition_counts do not match inventory tally"
            )
        baseline = metadata.get("baseline_free_bytes")
        target = metadata.get("target_free_bytes")
        stop_row = metadata.get("stop_row")
        if baseline is not None and target is not None:
            gap = max(0, int(target) - int(baseline))
            expected: Optional[int] = 0
            if gap > 0:
                expected = None
                running = 0
                for index, row in enumerate(plan, start=1):
                    projected = _opt_int(row["projected_reclaim_bytes"])
                    if projected is not None:
                        running += projected
                    if running >= gap:
                        expected = index
                        break
            if stop_row != expected:
                errors.append(
                    f"run.json: stop_row {stop_row!r} does not match "
                    f"recomputed {expected!r}"
                )
        elif stop_row is not None:
            errors.append(
                "run.json: stop_row must be null when baseline or target "
                "is unknown"
            )

    # Summary structure.
    summary_text = paths["cleanup-summary.md"].read_text(encoding="utf-8")
    for section in REQUIRED_SUMMARY_SECTIONS:
        if section not in summary_text:
            errors.append(f"cleanup-summary.md: missing section {section!r}")
    if "UNAPPROVED" not in summary_text:
        errors.append("cleanup-summary.md: missing UNAPPROVED statement")

    return errors
