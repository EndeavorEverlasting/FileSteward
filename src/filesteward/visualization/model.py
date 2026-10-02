"""F1: validated run artifacts -> immutable PresentationModel.

Never reclassifies. Never parses free-form prose into authority/gate facts.
Gate steps are projected only from structured fields and disposition invariants.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Optional

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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
    protection = inv.get("protection_relation") or "UNRELATED"
    if exclusion is not None:
        protection = exclusion.get("relationship") or protection
    completeness_raw = inv.get("scan_completeness") or "COMPLETE"
    try:
        completeness = ScanCompleteness(completeness_raw)
    except ValueError:
        completeness = ScanCompleteness.COMPLETE

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
    """Load a validated run directory into an immutable presentation model."""

    target = Path(run_dir)
    errors = validate_run(target)
    if errors:
        raise ValueError(
            "run failed FileSteward validation; refusing presentation model: "
            + "; ".join(errors)
        )

    inventory = _read_csv(target / "inventory.csv")
    plan_rows = {row["item_id"]: row for row in _read_csv(target / "cleanup-plan.csv")}
    review_rows = {
        row["item_id"]: row for row in _read_csv(target / "human-review.csv")
    }
    exclusion_rows = {
        row["item_id"]: row
        for row in _read_csv(target / "protected-exclusions.csv")
    }
    metadata = json.loads((target / "run.json").read_text(encoding="utf-8"))
    run_id = str(metadata.get("run_id") or target.name)

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
