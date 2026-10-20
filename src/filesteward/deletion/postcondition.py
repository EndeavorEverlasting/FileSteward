"""K4 reclaim receipt postconditions — action/owner/revision health, not bytes alone."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from filesteward.deletion.reclaim import ReclaimState

__all__ = [
    "PostconditionState",
    "SEMANTIC_EXECUTOR_ID",
    "build_reclaim_postcondition",
    "item_action_record",
]

SEMANTIC_EXECUTOR_ID = "filesteward.deletion.execute:execute_permanent_delete"


class PostconditionState:
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"


def item_action_record(
    *,
    item_id: str,
    path: str,
    status: str,
    reason_class: str,
    manifest_ownership: Mapping[str, Any] | None,
    immediate_ownership: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Per-item action/owner/revision envelope for the execution receipt."""

    before = dict(manifest_ownership) if isinstance(manifest_ownership, Mapping) else None
    after = dict(immediate_ownership) if isinstance(immediate_ownership, Mapping) else None
    action_kind = None
    owner_ids: list[str] = []
    if before is not None:
        action_kind = before.get("action_kind")
        owner_ids = [str(x) for x in (before.get("owner_ids") or [])]
    elif after is not None:
        action_kind = after.get("action_kind")
        owner_ids = [str(x) for x in (after.get("owner_ids") or [])]
    return {
        "item_id": item_id,
        "path": path,
        "status": status,
        "reason_class": reason_class,
        "action_kind": action_kind,
        "owner_ids": owner_ids,
        "graph_revision_before": None if before is None else before.get("graph_revision_id"),
        "graph_revision_after": None if after is None else after.get("graph_revision_id"),
        "evidence_digest_before": None if before is None else before.get("evidence_digest"),
        "evidence_digest_after": None if after is None else after.get("evidence_digest"),
        "ownership_before": before,
        "ownership_after": after,
    }


def build_reclaim_postcondition(
    *,
    item_actions: Sequence[Mapping[str, Any]],
    reclaim: Mapping[str, Any] | None,
    free_bytes_before: Optional[int],
    free_bytes_after: Optional[int],
    residual_paths: Sequence[str],
) -> dict[str, Any]:
    """Derive VERIFIED / PARTIAL / UNVERIFIED from ownership + reclaim evidence."""

    succeeded = [row for row in item_actions if str(row.get("status")) == "SUCCEEDED"]
    failed = [row for row in item_actions if str(row.get("status")) == "FAILED"]
    skipped = [row for row in item_actions if str(row.get("status")) == "SKIPPED"]
    residuals = [str(p) for p in residual_paths]

    action_kinds = sorted({str(row.get("action_kind")) for row in succeeded if row.get("action_kind")})
    owner_ids = sorted({
        str(owner)
        for row in succeeded
        for owner in (row.get("owner_ids") or [])
    })
    revisions_before = sorted({
        str(row.get("graph_revision_before"))
        for row in succeeded
        if row.get("graph_revision_before")
    })
    revisions_after = sorted({
        str(row.get("graph_revision_after"))
        for row in succeeded
        if row.get("graph_revision_after")
    })

    ownership_complete = bool(succeeded) and all(
        row.get("graph_revision_before")
        and row.get("graph_revision_after")
        and row.get("action_kind")
        and row.get("owner_ids") is not None
        for row in succeeded
    )
    reclaim_state = None if reclaim is None else str(reclaim.get("state") or "")
    free_observed = free_bytes_before is not None and free_bytes_after is not None

    if failed and succeeded:
        state = PostconditionState.PARTIAL
        reason = "mixed per-item outcomes; ownership/action recorded for succeeded subset only"
    elif not succeeded and failed:
        state = PostconditionState.UNVERIFIED
        reason = "no succeeded mutations; postcondition cannot verify reclaim safety"
    elif not succeeded:
        state = PostconditionState.UNVERIFIED
        reason = "no succeeded mutations"
    elif residuals:
        state = PostconditionState.PARTIAL
        reason = "succeeded receipt rows still have residual paths on disk"
    elif not ownership_complete:
        state = PostconditionState.UNVERIFIED
        reason = "succeeded items missing action/owner/graph-revision before/after binding"
    elif not free_observed:
        state = PostconditionState.UNVERIFIED
        reason = "capacity before/after observation unavailable"
    elif reclaim_state == ReclaimState.VERIFIED_RECLAIM:
        state = PostconditionState.VERIFIED
        reason = "targets absent, ownership revisions bound, free-space delta supports reclaim"
    elif reclaim_state == ReclaimState.NO_RECLAIM:
        # Targets gone with bound ownership, but capacity gain was not observed.
        state = PostconditionState.PARTIAL
        reason = "targets absent with bound ownership; free-space delta did not increase (NO_RECLAIM)"
    elif reclaim_state == ReclaimState.PARTIAL_RECLAIM:
        state = PostconditionState.PARTIAL
        reason = "reclaim verification reported PARTIAL_RECLAIM"
    else:
        state = PostconditionState.UNVERIFIED
        reason = f"reclaim state {reclaim_state or 'missing'} does not support verified postcondition"

    delta = None
    if free_observed:
        delta = int(free_bytes_after) - int(free_bytes_before)

    return {
        "state": state,
        "reason": reason,
        "semantic_executor": SEMANTIC_EXECUTOR_ID,
        "action_kinds": action_kinds,
        "owner_ids": owner_ids,
        "graph_revision_before": revisions_before,
        "graph_revision_after": revisions_after,
        "succeeded_item_count": len(succeeded),
        "failed_item_count": len(failed),
        "skipped_item_count": len(skipped),
        "residual_paths": residuals,
        "capacity": {
            "free_bytes_before": free_bytes_before,
            "free_bytes_after": free_bytes_after,
            "free_bytes_delta": delta,
        },
        "reclaim_state": reclaim_state,
        "ownership_bindings_complete": ownership_complete,
    }
