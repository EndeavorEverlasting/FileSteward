"""Protocol contract for the localhost-only FileSteward Decision Bridge.

This module defines request/state shapes only. The HTTP adapter is a later
mechanical integration. The bridge must never bind to a non-loopback address,
must never enable permissive CORS, and must require a per-process session token
for mutations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from filesteward.approval import ApprovalAction

__all__ = [
    "APPROVAL_PATH",
    "DECISION_PATH",
    "STATE_PATH",
    "DecisionBridgeIntent",
    "DecisionRequest",
    "ApprovalRequest",
    "is_loopback_host",
]

STATE_PATH = "/api/v1/state"
DECISION_PATH = "/api/v1/decision"
APPROVAL_PATH = "/api/v1/approval"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_LOOPBACK_NAMES = frozenset({"127.0.0.1", "::1", "localhost"})


class DecisionBridgeIntent(str, Enum):
    RESCAN = "RESCAN"
    DECLARE_REGENERABLE_CONTRACT = "DECLARE_REGENERABLE_CONTRACT"
    KEEP = "KEEP"
    REVIEW_LATER = "REVIEW_LATER"


def is_loopback_host(host: str) -> bool:
    return host.strip().lower() in _LOOPBACK_NAMES


@dataclass(frozen=True)
class DecisionRequest:
    run_id: str
    item_id: str
    intent: DecisionBridgeIntent

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.item_id:
            raise ValueError("item_id must be non-empty")

    def as_mapping(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "item_id": self.item_id,
            "intent": self.intent.value,
        }


@dataclass(frozen=True)
class ApprovalRequest:
    run_id: str
    item_id: str
    cleanup_plan_sha256: str
    action: ApprovalAction
    confirm: bool

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if not _SHA256_RE.fullmatch(self.cleanup_plan_sha256):
            raise ValueError(
                "cleanup_plan_sha256 must be a lowercase 64-character sha256"
            )
        if self.action is not ApprovalAction.QUARANTINE:
            raise ValueError("Decision Bridge approval only admits QUARANTINE")
        if self.confirm is not True:
            raise ValueError("explicit confirm=true is required for approval")

    def as_mapping(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "item_id": self.item_id,
            "cleanup_plan_sha256": self.cleanup_plan_sha256,
            "action": self.action.value,
            "confirm": self.confirm,
        }
