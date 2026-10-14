"""Mobile storage review routing (M0): evidence -> disposition, never mutation.

The desktop filesystem action planner cannot operate on an Android content URI
or an iOS PhotoKit/Files identifier. This adapter only identifies a permitted
next REVIEW route and uses the existing CleanupDisposition vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from filesteward.models import CleanupDisposition


class MobilePlatform(str, Enum):
    ANDROID = "ANDROID"
    IOS = "IOS"


class MobileStorageSurface(str, Enum):
    MEDIA_LIBRARY = "MEDIA_LIBRARY"
    USER_SELECTED_DOCUMENTS = "USER_SELECTED_DOCUMENTS"
    OTHER_APP_PRIVATE = "OTHER_APP_PRIVATE"
    SYSTEM_MANAGED = "SYSTEM_MANAGED"
    OWN_APP_CACHE = "OWN_APP_CACHE"


class PermissionScope(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    DENIED = "DENIED"
    LIMITED = "LIMITED"
    AUTHORIZED = "AUTHORIZED"


class CloudResidency(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOCAL_ONLY = "LOCAL_ONLY"
    SYNCED = "SYNCED"
    REMOTE_ONLY = "REMOTE_ONLY"


class MobileReviewRoute(str, Enum):
    REQUEST_SCOPED_ACCESS = "REQUEST_SCOPED_ACCESS"
    REVIEW_IN_SYSTEM_MEDIA_UI = "REVIEW_IN_SYSTEM_MEDIA_UI"
    REVIEW_IN_DOCUMENT_PROVIDER = "REVIEW_IN_DOCUMENT_PROVIDER"
    VERIFY_LOCAL_RESIDENCY = "VERIFY_LOCAL_RESIDENCY"
    MANAGE_WITH_OWNER_APP = "MANAGE_WITH_OWNER_APP"
    REVIEW_OWN_CACHE = "REVIEW_OWN_CACHE"


@dataclass(frozen=True)
class MobileEvidence:
    platform: MobilePlatform
    surface: MobileStorageSurface
    permission: PermissionScope = PermissionScope.NOT_REQUESTED
    cloud_residency: CloudResidency = CloudResidency.UNKNOWN
    owner_verified: bool = False
    regeneration_proven: bool = False
    observed_local_bytes: int | None = None

    def __post_init__(self) -> None:
        for name, cls in (
            ("platform", MobilePlatform),
            ("surface", MobileStorageSurface),
            ("permission", PermissionScope),
            ("cloud_residency", CloudResidency),
        ):
            if not isinstance(getattr(self, name), cls):
                raise TypeError(f"{name} requires a {cls.__name__} value")
        if type(self.owner_verified) is not bool or type(self.regeneration_proven) is not bool:
            raise TypeError("ownership and regeneration flags must be explicit booleans")
        if self.observed_local_bytes is not None and (
            type(self.observed_local_bytes) is not int or self.observed_local_bytes < 0
        ):
            raise ValueError("observed_local_bytes must be a nonnegative integer or None")


@dataclass(frozen=True)
class MobileReviewDecision:
    disposition: CleanupDisposition
    route: MobileReviewRoute
    reason_codes: tuple[str, ...]
    estimated_reclaim_bytes: None = None
    mutation_authorized: bool = False

    @property
    def is_executable(self) -> bool:
        """All M0 classifications are advisory, regardless of observed capacity."""
        return False


def decide_mobile_review(evidence: MobileEvidence) -> MobileReviewDecision:
    """Return a safe UI route; never treat access or sync as deletion permission."""
    if not isinstance(evidence, MobileEvidence):
        raise TypeError("mobile review requires validated MobileEvidence")

    def decision(disposition: CleanupDisposition, route: MobileReviewRoute, *reasons: str) -> MobileReviewDecision:
        return MobileReviewDecision(disposition, route, tuple(reasons))

    if evidence.surface in (MobileStorageSurface.OTHER_APP_PRIVATE, MobileStorageSurface.SYSTEM_MANAGED):
        return decision(
            CleanupDisposition.PROTECTED, MobileReviewRoute.MANAGE_WITH_OWNER_APP,
            "SANDBOX_OR_OS_OWNED", "NO_GENERIC_RAW_FILE_DELETE",
        )

    if evidence.surface is MobileStorageSurface.OWN_APP_CACHE:
        if not evidence.owner_verified or not evidence.regeneration_proven:
            return decision(
                CleanupDisposition.PROTECTED, MobileReviewRoute.MANAGE_WITH_OWNER_APP,
                "CACHE_OWNERSHIP_OR_REGENERATION_UNPROVEN",
            )
        return decision(
            CleanupDisposition.HUMAN_REVIEW, MobileReviewRoute.REVIEW_OWN_CACHE,
            "REGENERABLE_OWN_CACHE_REVIEW_ONLY", "NO_MUTATION_AUTHORITY",
        )

    if evidence.permission in (PermissionScope.NOT_REQUESTED, PermissionScope.DENIED):
        return decision(
            CleanupDisposition.UNKNOWN, MobileReviewRoute.REQUEST_SCOPED_ACCESS,
            "NO_CURRENT_CONTENT_ACCESS", "NO_PERSISTENT_BROAD_ACCESS",
        )

    if evidence.cloud_residency in (CloudResidency.UNKNOWN, CloudResidency.REMOTE_ONLY):
        return decision(
            CleanupDisposition.UNKNOWN, MobileReviewRoute.VERIFY_LOCAL_RESIDENCY,
            "ON_DEVICE_BYTES_NOT_VERIFIED", "SYNC_IS_NOT_BACKUP_PROOF",
        )

    if evidence.surface is MobileStorageSurface.MEDIA_LIBRARY:
        return decision(
            CleanupDisposition.HUMAN_REVIEW, MobileReviewRoute.REVIEW_IN_SYSTEM_MEDIA_UI,
            "SYSTEM_MEDIATED_MEDIA_ACTION", "PERMISSION_IS_NOT_DELETE_AUTHORITY",
            "LIMITED_SELECTION_ONLY" if evidence.permission is PermissionScope.LIMITED else "SCOPED_ACCESS",
            "SYNC_IS_NOT_BACKUP_PROOF" if evidence.cloud_residency is CloudResidency.SYNCED else "LOCAL_ONLY_OBSERVED",
        )

    if evidence.surface is MobileStorageSurface.USER_SELECTED_DOCUMENTS:
        return decision(
            CleanupDisposition.HUMAN_REVIEW, MobileReviewRoute.REVIEW_IN_DOCUMENT_PROVIDER,
            "PROVIDER_DOCUMENT_ACTION", "PERMISSION_IS_NOT_DELETE_AUTHORITY",
            "LIMITED_SELECTION_ONLY" if evidence.permission is PermissionScope.LIMITED else "SCOPED_ACCESS",
            "SYNC_IS_NOT_BACKUP_PROOF" if evidence.cloud_residency is CloudResidency.SYNCED else "LOCAL_ONLY_OBSERVED",
        )

    raise ValueError("Unsupported mobile storage surface")
