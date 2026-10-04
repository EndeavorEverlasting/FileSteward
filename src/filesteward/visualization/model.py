"""F1: validated run artifacts -> immutable PresentationModel.

Never reclassifies. Never parses free-form prose into authority/gate facts.
Gate steps are projected only from structured fields and disposition invariants.

Large receipts prefer persisted triage buckets (or prefix aggregation) so the
presentation model does not expand hundreds of thousands of inventory rows.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from filesteward.manifest import validate_run
from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    ScanCompleteness,
)
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
)

__all__ = ["build_presentation_model"]

_NOT_PERSISTED = "UNKNOWN / NOT PERSISTED"
_PROTECTION_RELATIONS = {"UNRELATED", "SELF", "DESCENDANT", "ANCESTOR"}
#: Expand inventory rows into presentation nodes only at or below this count.
_ROW_EXPAND_LIMIT = 5_000
#: Cap aggregated HUMAN_REVIEW bucket nodes for offline HTML usability.
_MAX_AGGREGATE_NODES = 200


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _count_csv_data_rows(path: Path) -> int:
    """Count CSV records without materializing DictReader rows.

    Uses ``csv.reader`` so quoted fields that contain newlines still count as
    one logical record.
    """

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        # Skip header when present.
        next(reader, None)
        return sum(1 for _ in reader)


def _opt_int(raw: str | None) -> Optional[int]:
    if raw is None or raw == "":
        return None
    return int(raw)


def _display_name(path: str) -> str:
    cleaned = path.rstrip("\\/")
    if not cleaned:
        return path
    parts = cleaned.replace("/", "\\").split("\\")
    return parts[-1] or path


def _fmt_bytes_label(value: Optional[int]) -> str:
    if value is None:
        return "not established"
    gib = value / (1024**3)
    if gib >= 10:
        return f"{gib:.1f} GiB"
    if gib >= 1:
        return f"{gib:.2f} GiB"
    return f"{value} bytes"


def _gate_steps_for(
    *,
    disposition: CleanupDisposition,
    protection_relation: str,
    scan_completeness: ScanCompleteness,
    contract_summary: Optional[str],
    plan_evidence: Optional[str],
) -> tuple[GateStep, ...]:
    """Project gate rows from structured invariants only."""

    steps: list[GateStep] = []

    # 1. Protection
    if protection_relation in {"SELF", "DESCENDANT"}:
        steps.append(
            GateStep(
                gate_id="protection",
                name="Protected overlap",
                status=GateStepStatus.BLOCK,
                explanation=f"Protection relation {protection_relation}.",
                is_first_unresolved=True,
            )
        )
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Disposition",
                status=GateStepStatus.BLOCK,
                explanation="PROTECTED. Protection wins.",
            )
        )
        return tuple(steps)
    if protection_relation == "ANCESTOR":
        steps.append(
            GateStep(
                gate_id="protection",
                name="Protected subtree contained",
                status=GateStepStatus.WAITING,
                explanation="Ancestor contains a protected subtree; decompose.",
                is_first_unresolved=True,
            )
        )
        return tuple(steps)

    steps.append(
        GateStep(
            gate_id="protection",
            name="Protected overlap",
            status=GateStepStatus.PASS,
            explanation="None observed",
        )
    )

    # 2. Observation completeness
    if scan_completeness is ScanCompleteness.INCOMPLETE:
        steps.append(
            GateStep(
                gate_id="observation",
                name="Observation complete",
                status=GateStepStatus.WAITING,
                explanation="Scan evidence is incomplete.",
                is_first_unresolved=True,
            )
        )
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Disposition",
                status=GateStepStatus.UNKNOWN,
                explanation="UNKNOWN. Stop before contract or action.",
            )
        )
        return tuple(steps)

    steps.append(
        GateStep(
            gate_id="observation",
            name="Observation complete",
            status=GateStepStatus.PASS,
            explanation="COMPLETE",
        )
    )

    if disposition is CleanupDisposition.KEEP_PROVEN:
        steps.append(
            GateStep(
                gate_id="retention",
                name="Retention evidence",
                status=GateStepStatus.PASS,
                explanation="KEEP_PROVEN.",
            )
        )
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Disposition",
                status=GateStepStatus.PASS,
                explanation="KEEP_PROVEN. No reclaim action.",
                is_first_unresolved=False,
            )
        )
        return tuple(steps)

    if disposition is CleanupDisposition.UNKNOWN:
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Disposition",
                status=GateStepStatus.UNKNOWN,
                explanation=_NOT_PERSISTED
                if not plan_evidence
                else "UNKNOWN from inventory.",
                is_first_unresolved=True,
            )
        )
        return tuple(steps)

    # Contract gate — only structured contract_summary / plan evidence counts.
    if disposition is CleanupDisposition.HUMAN_REVIEW:
        steps.append(
            GateStep(
                gate_id="contract",
                name="Explicit regenerable contract",
                status=GateStepStatus.WAITING,
                explanation=(
                    "No structured regenerable contract covers this prefix."
                    if not contract_summary
                    else f"Structured contract note: {contract_summary}"
                ),
                is_first_unresolved=True,
            )
        )
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Disposition",
                status=GateStepStatus.WAITING,
                explanation="HUMAN_REVIEW. Operator judgment remains required.",
            )
        )
        return tuple(steps)

    if disposition is CleanupDisposition.RECLAIM_PROVEN:
        steps.append(
            GateStep(
                gate_id="contract",
                name="Explicit regenerable contract",
                status=GateStepStatus.PASS,
                explanation=contract_summary or plan_evidence or _NOT_PERSISTED,
            )
        )
        steps.append(
            GateStep(
                gate_id="disposition",
                name="Evidence disposition",
                status=GateStepStatus.PASS,
                explanation="RECLAIM_PROVEN.",
            )
        )
        steps.append(
            GateStep(
                gate_id="approval",
                name="Operator approval bound to run/manifest/rows",
                status=GateStepStatus.WAITING,
                explanation="Authorization remains UNAPPROVED.",
                is_first_unresolved=True,
            )
        )
        steps.append(
            GateStep(
                gate_id="apply",
                name="Apply",
                status=GateStepStatus.NOT_APPLICABLE,
                explanation="Unavailable in the current MVP.",
            )
        )
        return tuple(steps)

    steps.append(
        GateStep(
            gate_id="disposition",
            name="Disposition",
            status=GateStepStatus.UNKNOWN,
            explanation=_NOT_PERSISTED,
            is_first_unresolved=True,
        )
    )
    return tuple(steps)


def _next_gate(steps: tuple[GateStep, ...], disposition: CleanupDisposition) -> str:
    for step in steps:
        if step.is_first_unresolved:
            return f"{step.name}: {step.explanation}"
    if disposition is CleanupDisposition.KEEP_PROVEN:
        return "No reclaim action."
    return _NOT_PERSISTED


def _node_from_inventory(
    inv: Mapping[str, str],
    *,
    plan: Optional[Mapping[str, str]] = None,
    review: Optional[Mapping[str, str]] = None,
    exclusion: Optional[Mapping[str, str]] = None,
) -> PresentationNode:
    disposition = CleanupDisposition(inv["disposition"])
    protection = inv.get("protection_relation") or ""
    if exclusion is not None:
        protection = exclusion.get("relationship") or protection
    if protection not in _PROTECTION_RELATIONS:
        raise ValueError(
            f"unknown protection_relation for {inv.get('item_id', '<unknown>')}: "
            f"{protection or '<missing>'}"
        )

    completeness_raw = inv.get("scan_completeness") or ""
    if not completeness_raw:
        completeness = ScanCompleteness.INCOMPLETE
    else:
        try:
            completeness = ScanCompleteness(completeness_raw)
        except ValueError as exc:
            raise ValueError(
                f"unknown scan_completeness for {inv.get('item_id', '<unknown>')}: "
                f"{completeness_raw}"
            ) from exc

    contract_summary = None
    plan_evidence = None
    projected = None
    reclaim_basis = None
    projection_quality = None
    reason = ""
    risk = ""
    hints: tuple[str, ...] = ()

    if plan is not None:
        projected = _opt_int(plan.get("projected_reclaim_bytes"))
        reclaim_basis = plan.get("reclaim_basis") or None
        projection_quality = plan.get("projection_quality") or None
        plan_evidence = plan.get("evidence") or None
        contract_summary = plan.get("confidence_basis") or None
        reason = plan.get("evidence") or ""
        risk = plan.get("recoverability") or ""
    if review is not None:
        # Structured fields only — never promote known_context prose.
        reason = review.get("why_ambiguous") or reason
        risk = review.get("risk_if_acted_on") or risk
        # known_context is intentionally ignored for authority/gate facts.
    if exclusion is not None:
        reason = exclusion.get("protection_reason") or reason
        risk = "Protected overlap prohibits automated reclaim."

    if disposition is CleanupDisposition.PROTECTED and not reason:
        reason = "PROTECTED"
    if not reason:
        reason = _NOT_PERSISTED
    if not risk:
        risk = _NOT_PERSISTED

    steps = _gate_steps_for(
        disposition=disposition,
        protection_relation=protection,
        scan_completeness=completeness,
        contract_summary=contract_summary,
        plan_evidence=plan_evidence,
    )
    source_bits = ["inventory.csv"]
    if plan is not None:
        source_bits.append("cleanup-plan.csv")
    if review is not None:
        source_bits.append("human-review.csv")
    if exclusion is not None:
        source_bits.append("protected-exclusions.csv")

    return PresentationNode(
        node_id=inv["item_id"],
        parent_id=None,
        display_name=_display_name(inv["path"]),
        path=inv["path"],
        entry_type=inv.get("entry_type") or "OTHER",
        logical_size_bytes=_opt_int(inv.get("logical_size_bytes")),
        allocated_size_bytes=_opt_int(inv.get("allocated_size_bytes")),
        projected_reclaim_bytes=projected,
        reclaim_basis=reclaim_basis,
        projection_quality=projection_quality,
        disposition=disposition,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=completeness,
        protection_relation=protection,
        reason=reason,
        contract_summary=contract_summary,
        contract_hint_tags=hints,
        risk_if_acted_on=risk,
        next_gate=_next_gate(steps, disposition),
        trace_evidence_source="+".join(source_bits),
        item_count=None,
        gate_steps=steps,
    )


def _bucket_node_id(prefix: str, depth: str) -> str:
    digest = hashlib.sha256(f"{depth}\0{prefix}".encode("utf-8")).hexdigest()[:20]
    return f"bucket-{digest}"


def _parse_hint_tags(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    parts = [part.strip() for part in raw.replace("|", ",").split(",")]
    return tuple(part for part in parts if part and part != "-")


def _node_from_review_bucket(row: Mapping[str, str]) -> PresentationNode:
    """Project a persisted triage bucket into a presentation node.

    Persisted ``human-review-buckets.csv`` aggregates HUMAN_REVIEW and UNKNOWN
    rows without per-bucket disposition splits. Fail closed to UNKNOWN so the
    stop-before-contract gate remains visible.
    """

    prefix = row.get("prefix") or ""
    if not prefix:
        raise ValueError("human-review bucket is missing prefix")
    depth = row.get("depth") or ""
    logical = _opt_int(row.get("logical_bytes_known"))
    unknown = _opt_int(row.get("unknown_size_count")) or 0
    item_count = _opt_int(row.get("item_count"))
    completeness = (
        ScanCompleteness.COMPLETE if unknown == 0 else ScanCompleteness.INCOMPLETE
    )
    hints = _parse_hint_tags(row.get("contract_hint_tags"))
    # Fail closed: mixed HUMAN_REVIEW/UNKNOWN triage buckets are not labeled
    # HUMAN_REVIEW when disposition splits are unavailable.
    disposition = CleanupDisposition.UNKNOWN
    steps = _gate_steps_for(
        disposition=disposition,
        protection_relation="UNRELATED",
        scan_completeness=completeness,
        contract_summary=None,
        plan_evidence=None,
    )
    reason = (
        "Aggregated HUMAN_REVIEW/UNKNOWN triage bucket from persisted evidence. "
        "Disposition splits are not recorded per bucket, so presentation fails "
        "closed to UNKNOWN. Not a reclaim nomination and not an approved contract."
    )
    return PresentationNode(
        node_id=_bucket_node_id(prefix, depth),
        parent_id=None,
        display_name=_display_name(prefix),
        path=prefix,
        entry_type="DIRECTORY",
        logical_size_bytes=logical,
        allocated_size_bytes=None,
        projected_reclaim_bytes=None,
        reclaim_basis=None,
        projection_quality=None,
        disposition=disposition,
        authorization_state=AuthorizationState.UNAPPROVED,
        scan_completeness=completeness,
        protection_relation="UNRELATED",
        reason=reason,
        contract_summary=None,
        contract_hint_tags=hints,
        risk_if_acted_on=(
            "Bucket remains UNAPPROVED/UNKNOWN. Operator judgment is required "
            "before any contract or reclaim nomination."
        ),
        next_gate=_next_gate(steps, disposition),
        trace_evidence_source="human-review-buckets.csv",
        item_count=item_count,
        gate_steps=steps,
    )


def _top_bucket_nodes(path: Path, *, limit: int) -> list[PresentationNode]:
    rows = _read_csv(path)
    ranked: list[tuple[int, int, Mapping[str, str]]] = []
    for index, row in enumerate(rows):
        logical = _opt_int(row.get("logical_bytes_known")) or 0
        ranked.append((logical, index, row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [_node_from_review_bucket(row) for _, _, row in ranked[:limit]]


def _nodes_from_inventory_rows(
    inventory: Iterable[Mapping[str, str]],
    *,
    plan_rows: Mapping[str, Mapping[str, str]],
    review_rows: Mapping[str, Mapping[str, str]],
    exclusion_rows: Mapping[str, Mapping[str, str]],
) -> list[PresentationNode]:
    nodes: list[PresentationNode] = []
    for inv in inventory:
        item_id = inv["item_id"]
        nodes.append(
            _node_from_inventory(
                inv,
                plan=plan_rows.get(item_id),
                review=review_rows.get(item_id),
                exclusion=exclusion_rows.get(item_id),
            )
        )
    return nodes


def _metrics_from_metadata(metadata: Mapping[str, Any]) -> ShellMetrics:
    observed = metadata.get("logical_bytes_observed")
    if observed is None:
        observed_label = "not established"
    else:
        observed_label = _fmt_bytes_label(int(observed))
    free = metadata.get("baseline_free_bytes")
    free_label = _fmt_bytes_label(int(free) if free is not None else None)
    projected = metadata.get("cumulative_projected_reclaim_bytes")
    projected_label = _fmt_bytes_label(
        int(projected) if projected is not None else None
    )
    target = metadata.get("target_free_bytes")
    target_label = _fmt_bytes_label(int(target) if target is not None else None)
    quality = metadata.get("projection_quality_summary")
    if not isinstance(quality, str) or not quality:
        quality = "estimate-logical" if projected else None
    return ShellMetrics(
        observed_storage_label=observed_label,
        free_space_label=free_label,
        projected_reclaim_label=projected_label,
        projected_reclaim_quality=quality,
        target_free_space_label=target_label,
        authorization_label=str(
            metadata.get("authorization_state") or "UNAPPROVED"
        ),
    )


def build_presentation_model(run_dir: Path) -> PresentationModel:
    """Load a validated run directory into an immutable presentation model.

    Call stack / scale policy:
      validate_run (fail closed)
        -> if inventory rows exceed expand limit and triage buckets exist:
             project top aggregated triage buckets as UNKNOWN
             (does not expand human-review.csv / inventory into presentation nodes;
              validate_run may still read full artifacts as its own gate)
        -> else expand inventory rows with joined structured evidence
        -> largest-first default selection
    """

    target = Path(run_dir)
    errors = validate_run(target)
    if errors:
        raise ValueError(
            "run failed FileSteward validation; refusing presentation model: "
            + "; ".join(errors)
        )

    inventory_path = target / "inventory.csv"
    buckets_path = target / "human-review-buckets.csv"
    metadata = json.loads((target / "run.json").read_text(encoding="utf-8"))
    run_id = str(metadata.get("run_id") or target.name)
    inventory_rows = _count_csv_data_rows(inventory_path)

    if inventory_rows > _ROW_EXPAND_LIMIT:
        if not buckets_path.is_file():
            raise ValueError(
                "inventory exceeds presentation expand limit "
                f"({inventory_rows} > {_ROW_EXPAND_LIMIT}); run "
                "`filesteward plan` to persist human-review-buckets.csv "
                "before visualize"
            )
        nodes = _top_bucket_nodes(buckets_path, limit=_MAX_AGGREGATE_NODES)
    else:
        inventory = _read_csv(inventory_path)
        plan_rows = {
            row["item_id"]: row for row in _read_csv(target / "cleanup-plan.csv")
        }
        review_rows = {
            row["item_id"]: row for row in _read_csv(target / "human-review.csv")
        }
        exclusion_rows = {
            row["item_id"]: row
            for row in _read_csv(target / "protected-exclusions.csv")
        }
        nodes = _nodes_from_inventory_rows(
            inventory,
            plan_rows=plan_rows,
            review_rows=review_rows,
            exclusion_rows=exclusion_rows,
        )

    if not nodes:
        raise ValueError("presentation model has no nodes")

    # Largest-first default selection among positive logical sizes.
    ordered = sorted(
        nodes,
        key=lambda n: (
            n.logical_size_bytes is None,
            -(n.logical_size_bytes or 0),
            n.node_id,
        ),
    )
    default_id = ordered[0].node_id if ordered else None
    return PresentationModel(
        run_id=run_id,
        nodes=tuple(nodes),
        metrics=_metrics_from_metadata(metadata),
        default_selected_id=default_id,
    )
