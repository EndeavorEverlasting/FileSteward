"""Approval-record contract for a future FileSteward action gate.

The record grants no deletion implementation by itself. It binds explicit
operator authorization to one exact cleanup-plan digest and exact plan rows.
The only action admitted by this first contract is QUARANTINE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from filesteward.models import AuthorizationState, CleanupDisposition

__all__ = [
    "APPROVAL_SCHEMA_VERSION",
    "ApprovalAction",
    "ApprovalRecord",
    "validate_approval_against_plan",
]

APPROVAL_SCHEMA_VERSION = "filesteward.approval/v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ApprovalAction(str, Enum):
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class ApprovalRecord:
    run_id: str
    cleanup_plan_sha256: str
    approved_item_ids: tuple[str, ...]
    action: ApprovalAction = ApprovalAction.QUARANTINE
    authorization_state: AuthorizationState = AuthorizationState.APPROVED_FOR_ACTION
    schema_version: str = APPROVAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not _SHA256_RE.fullmatch(self.cleanup_plan_sha256):
            raise ValueError(
                "cleanup_plan_sha256 must be a lowercase 64-character sha256"
            )
        if not self.approved_item_ids:
            raise ValueError("approved_item_ids must be non-empty")
        if any(not item_id for item_id in self.approved_item_ids):
            raise ValueError("approved item ids must be non-empty")
        if len(set(self.approved_item_ids)) != len(self.approved_item_ids):
            raise ValueError("approved_item_ids must be unique")
        if self.authorization_state is not AuthorizationState.APPROVED_FOR_ACTION:
            raise ValueError(
                "approval records must carry APPROVED_FOR_ACTION"
            )

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "cleanup_plan_sha256": self.cleanup_plan_sha256,
            "approved_item_ids": list(self.approved_item_ids),
            "action": self.action.value,
            "authorization_state": self.authorization_state.value,
        }


def validate_approval_against_plan(
    record: ApprovalRecord,
    plan_rows: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    """Fail closed if approval rows drift from the exact cleanup plan."""

    by_id = {
        str(row.get("item_id") or ""): row
        for row in plan_rows
        if row.get("item_id")
    }
    errors: list[str] = []

    for item_id in record.approved_item_ids:
        row = by_id.get(item_id)
        if row is None:
            errors.append(f"item {item_id} is not present in cleanup-plan.csv")
            continue
        if row.get("disposition") != CleanupDisposition.RECLAIM_PROVEN.value:
            errors.append(f"item {item_id} is not RECLAIM_PROVEN")
        if row.get("proposed_action") != "quarantine":
            errors.append(
                f"item {item_id} proposed_action must be quarantine"
            )

    return tuple(errors)
