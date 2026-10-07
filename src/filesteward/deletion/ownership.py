"""Exact ownership binding and fresh, fail-closed dependency revalidation."""
from __future__ import annotations

import math
import time
from typing import Any, Mapping

from filesteward.ownership.actions import (
    ActionKind, ActionPlan, OwnershipResolver, plan_owner_actions,
)
from filesteward.ownership._windows_paths import normalize_path_key


def bind_ownership(plan: ActionPlan, observed_at_unix: float) -> dict[str, Any]:
    if not plan.raw_delete_eligible:
        raise ValueError("SEMANTIC_ACTION_REQUIRED: owner action is not raw-delete eligible")
    return {
        "path": plan.path,
        "graph_revision_id": plan.graph_revision_id,
        "evidence_digest": plan.evidence_digest,
        "owner_ids": list(plan.owner_ids),
        "consequence_classes": list(plan.consequence_classes),
        "action_kind": ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT.value,
        "regeneration_digest": plan.regeneration_digest,
        "observed_at_unix": observed_at_unix,
        "max_age_seconds": 300,
    }


def action_plan_from_record(record: Mapping[str, Any]) -> ActionPlan:
    plan = ActionPlan(
        str(record["path"]), record["disposition"], tuple(record["actions"]),
        tuple(record["reason_codes"]), tuple(record["owner_ids"]),
        tuple(record["consequence_classes"]), str(record["graph_revision_id"]),
        str(record["evidence_digest"]), str(record["regeneration_digest"]),
    )
    from filesteward.models import CleanupDisposition
    from dataclasses import replace
    plan = replace(plan, disposition=CleanupDisposition(plan.disposition),
                   actions=tuple(ActionKind(a) for a in plan.actions))
    return plan


def binding_from_action_record(record: Mapping[str, Any]) -> dict[str, Any]:
    plan = action_plan_from_record(record)
    if not record.get("adapters_complete"):
        raise ValueError("OWNERSHIP_UNKNOWN: adapters incomplete")
    return bind_ownership(plan, float(record["observed_at_unix"]))


def revalidate_ownership(item: Mapping[str, Any], resolver: OwnershipResolver) -> tuple[str, str, dict[str, Any] | None]:
    """Return reason/detail/current binding; empty reason means PASS."""
    expected = item.get("ownership")
    if not isinstance(expected, Mapping):
        return "OWNERSHIP_UNKNOWN", "ownership binding missing", None
    path = str(item.get("path") or "")
    if normalize_path_key(str(expected.get("path") or "")) != normalize_path_key(path):
        return "OWNERSHIP_REVISION_DRIFT", "ownership binding path changed", None
    if expected.get("action_kind") != ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT.value:
        return "SEMANTIC_ACTION_REQUIRED", "manifest action is not exact raw regenerable deletion", None
    try:
        stamp = float(expected["observed_at_unix"])
        age = time.time() - stamp
        if not math.isfinite(stamp) or not 0 <= age <= 300 or expected.get("max_age_seconds") != 300:
            return "OWNERSHIP_EVIDENCE_STALE", "manifest evidence freshness expired or invalid", None
        evidence = resolver(path)
        plan = plan_owner_actions(path, evidence)
    except Exception as exc:
        return "OWNERSHIP_UNKNOWN", f"ownership resolver failed ({type(exc).__name__})", None
    if not plan.raw_delete_eligible:
        preferred = ("SERVICEABILITY_DEPENDENCY_PRESENT", "APP_DEPENDENCY_PRESENT", "REPOSITORY_UNIQUE_WORK_PRESENT",
                     "PROTECTIVE_DEPENDENCY_PRESENT", "REGENERATION_PROOF_MISSING", "SEMANTIC_ACTION_REQUIRED")
        reason = next((r for r in preferred if r in plan.reason_codes), "OWNERSHIP_UNKNOWN")
        return reason, "fresh dependency evidence blocks raw deletion: " + ",".join(plan.reason_codes), None
    current = bind_ownership(plan, evidence.observed_at_unix)
    for field in ("graph_revision_id", "evidence_digest", "owner_ids", "consequence_classes", "regeneration_digest"):
        if not expected.get(field) or expected.get(field) != current[field]:
            return "OWNERSHIP_REVISION_DRIFT", f"ownership {field} changed or missing", current
    return "", "ownership and regeneration evidence re-resolved", current
