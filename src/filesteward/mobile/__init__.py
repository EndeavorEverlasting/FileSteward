"""Read-only, platform-aware mobile storage capability and review routing.

This package never requests permissions, scans a device or deletes content.
"""
from .policy import (
    CloudResidency, MobileEvidence, MobilePlatform, MobileReviewRoute,
    MobileStorageSurface, PermissionScope, MobileReviewDecision,
    decide_mobile_review,
)

__all__ = [
    "CloudResidency", "MobileEvidence", "MobilePlatform", "MobileReviewRoute",
    "MobileStorageSurface", "PermissionScope", "MobileReviewDecision",
    "decide_mobile_review",
]
