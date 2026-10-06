"""D6 reclaim verification from free-space before/after + success set.

Reports discrepancy honestly. No fake equality tolerance that hides
concurrent disk activity: a positive free-byte delta with targets gone and
a consistent receipt yields VERIFIED_RECLAIM; mixed success yields
PARTIAL_RECLAIM; zero free increase with successes yields NO_RECLAIM or
UNKNOWN with an explicit reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "ReclaimState",
    "ReclaimVerification",
    "verify_reclaim",
]


class ReclaimState:
    VERIFIED_RECLAIM = "VERIFIED_RECLAIM"
    PARTIAL_RECLAIM = "PARTIAL_RECLAIM"
    NO_RECLAIM = "NO_RECLAIM"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReclaimVerification:
    state: str
    free_bytes_before: Optional[int]
    free_bytes_after: Optional[int]
    free_bytes_delta: Optional[int]
    succeeded_item_count: int
    failed_item_count: int
    skipped_item_count: int
    residual_paths: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "free_bytes_before": self.free_bytes_before,
            "free_bytes_after": self.free_bytes_after,
            "free_bytes_delta": self.free_bytes_delta,
            "succeeded_item_count": self.succeeded_item_count,
            "failed_item_count": self.failed_item_count,
            "skipped_item_count": self.skipped_item_count,
            "residual_paths": list(self.residual_paths),
            "reason": self.reason,
        }


def verify_reclaim(
    *,
    free_bytes_before: Optional[int],
    free_bytes_after: Optional[int],
    item_results: Sequence[Mapping[str, Any]],
    residual_paths: Sequence[str] = (),
) -> ReclaimVerification:
    """Compute reclaim state from measured free space and per-item outcomes."""

    succeeded = [r for r in item_results if str(r.get("status")) == "SUCCEEDED"]
    failed = [r for r in item_results if str(r.get("status")) == "FAILED"]
    skipped = [r for r in item_results if str(r.get("status")) == "SKIPPED"]
    residuals = tuple(str(p) for p in residual_paths)

    if free_bytes_before is None or free_bytes_after is None:
        return ReclaimVerification(
            state=ReclaimState.UNKNOWN,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=None,
            succeeded_item_count=len(succeeded),
            failed_item_count=len(failed),
            skipped_item_count=len(skipped),
            residual_paths=residuals,
            reason="free-space observation unavailable before and/or after delete",
        )

    delta = int(free_bytes_after) - int(free_bytes_before)

    if not succeeded and not failed:
        return ReclaimVerification(
            state=ReclaimState.NO_RECLAIM,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=delta,
            succeeded_item_count=0,
            failed_item_count=0,
            skipped_item_count=len(skipped),
            residual_paths=residuals,
            reason="no items succeeded; nothing deleted",
        )

    if failed and succeeded:
        return ReclaimVerification(
            state=ReclaimState.PARTIAL_RECLAIM,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=delta,
            succeeded_item_count=len(succeeded),
            failed_item_count=len(failed),
            skipped_item_count=len(skipped),
            residual_paths=residuals,
            reason=(
                f"partial success ({len(succeeded)} succeeded, {len(failed)} failed); "
                f"free_bytes_delta={delta}"
            ),
        )

    if failed and not succeeded:
        return ReclaimVerification(
            state=ReclaimState.NO_RECLAIM,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=delta,
            succeeded_item_count=0,
            failed_item_count=len(failed),
            skipped_item_count=len(skipped),
            residual_paths=residuals,
            reason="all attempted items failed; no reclaim",
        )

    # All approved attempts succeeded (skipped from prior receipt OK).
    if residuals:
        return ReclaimVerification(
            state=ReclaimState.UNKNOWN,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=delta,
            succeeded_item_count=len(succeeded),
            failed_item_count=0,
            skipped_item_count=len(skipped),
            residual_paths=residuals,
            reason="receipt reports success but residual approved paths remain on disk",
        )

    if delta > 0:
        return ReclaimVerification(
            state=ReclaimState.VERIFIED_RECLAIM,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=delta,
            succeeded_item_count=len(succeeded),
            failed_item_count=0,
            skipped_item_count=len(skipped),
            residual_paths=(),
            reason=(
                "targets gone, receipt consistent, free_bytes_delta>0 "
                f"(delta={delta}); concurrent disk activity may inflate delta"
            ),
        )

    if delta == 0:
        return ReclaimVerification(
            state=ReclaimState.NO_RECLAIM,
            free_bytes_before=free_bytes_before,
            free_bytes_after=free_bytes_after,
            free_bytes_delta=0,
            succeeded_item_count=len(succeeded),
            failed_item_count=0,
            skipped_item_count=len(skipped),
            residual_paths=(),
            reason=(
                "targets gone and receipt consistent but free_bytes_delta==0; "
                "same-volume retain or concurrent allocation may hide reclaim"
            ),
        )

    # delta < 0
    return ReclaimVerification(
        state=ReclaimState.UNKNOWN,
        free_bytes_before=free_bytes_before,
        free_bytes_after=free_bytes_after,
        free_bytes_delta=delta,
        succeeded_item_count=len(succeeded),
        failed_item_count=0,
        skipped_item_count=len(skipped),
        residual_paths=(),
        reason=(
            f"targets gone but free_bytes_delta={delta} (negative); "
            "concurrent disk activity likely; reclaim not proven"
        ),
    )
