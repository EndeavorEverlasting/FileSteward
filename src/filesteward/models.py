"""Leaf domain contracts for FileSteward cleanup analysis.

Two type systems exist here and must never be conflated:

* Evidence states/dispositions describe what deterministic machinery
  observed (`EvidenceState`, `CleanupDisposition`).
* Authorization states describe whether an operator permitted mutation
  (`AuthorizationState`).

`RECLAIM_PROVEN` is evidence. It is not permission to mutate anything.
An agent-generated artifact always begins `UNAPPROVED`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

__all__ = [
    "AuthorizationState",
    "CleanupDisposition",
    "EntryType",
    "EvidenceState",
    "InventoryItem",
    "ScanCompleteness",
    "authorization_allows_mutation",
]


class EvidenceState(str, Enum):
    """Evidence collection progress for a single inventory item."""

    DISCOVERED = "DISCOVERED"
    EVALUATED = "EVALUATED"
    DISPOSITION_ASSIGNED = "DISPOSITION_ASSIGNED"


class CleanupDisposition(str, Enum):
    """Evidence disposition of an inventory item. Never an approval."""

    RECLAIM_PROVEN = "RECLAIM_PROVEN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    PROTECTED = "PROTECTED"
    KEEP_PROVEN = "KEEP_PROVEN"
    UNKNOWN = "UNKNOWN"


class AuthorizationState(str, Enum):
    """Operator authorization lifecycle, separate from evidence."""

    UNAPPROVED = "UNAPPROVED"
    APPROVED_FOR_ACTION = "APPROVED_FOR_ACTION"
    APPLIED = "APPLIED"
    VERIFIED = "VERIFIED"


class EntryType(str, Enum):
    """Filesystem entry type as observed without following links."""

    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    SYMLINK = "SYMLINK"
    REPARSE_POINT = "REPARSE_POINT"
    OTHER = "OTHER"


class ScanCompleteness(str, Enum):
    """Observation completeness. INCOMPLETE is an explicit scan gap and is
    never interpreted as absence of content."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


def authorization_allows_mutation(state: AuthorizationState) -> bool:
    """Fail-closed: only an explicit operator approval permits mutation.

    Evidence dispositions never reach this function's domain; passing a
    non-`AuthorizationState` value is a programming error and is rejected.
    """

    if not isinstance(state, AuthorizationState):
        raise TypeError(
            "mutation authority requires an AuthorizationState, not evidence"
        )
    return state is AuthorizationState.APPROVED_FOR_ACTION


@dataclass(frozen=True)
class InventoryItem:
    """Normalized, read-only evidence about one filesystem entry.

    Leaf contract: no classification, approval, or mutation semantics.
    Sizes may be ``None`` when they cannot be determined safely; an
    unknown value is reported, never guessed.
    """

    item_id: str
    path: str
    entry_type: EntryType
    logical_size_bytes: Optional[int] = None
    allocated_size_bytes: Optional[int] = None
    projected_reclaim_bytes: Optional[int] = None
    reclaim_basis: Optional[str] = None
    modified_at: Optional[float] = None
    link_count: Optional[int] = None
    scan_completeness: ScanCompleteness = ScanCompleteness.COMPLETE
    scan_error: Optional[str] = None
    is_symlink: bool = False
    is_reparse_point: bool = False
    is_cloud_placeholder: bool = False
    evidence_state: EvidenceState = EvidenceState.DISCOVERED

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if not self.path:
            raise ValueError("path must be non-empty")
        for name in ("logical_size_bytes", "allocated_size_bytes", "link_count"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0 or None, got {value!r}")
        if (
            self.projected_reclaim_bytes is not None
            and self.projected_reclaim_bytes < 0
        ):
            raise ValueError("projected_reclaim_bytes must be >= 0 or None")
        if self.scan_completeness is ScanCompleteness.INCOMPLETE and not self.scan_error:
            raise ValueError("an INCOMPLETE scan requires a scan_error")
        if self.scan_error and self.scan_completeness is ScanCompleteness.COMPLETE:
            raise ValueError("a scan_error cannot accompany COMPLETE observation")
