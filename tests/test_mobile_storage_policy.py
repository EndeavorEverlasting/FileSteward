"""M0 adversarial cross-platform mobile routing tests (synthetic only)."""
import itertools

import pytest

from filesteward.models import CleanupDisposition
from filesteward.mobile import (
    CloudResidency, MobileEvidence, MobilePlatform, MobileReviewRoute,
    MobileStorageSurface, PermissionScope, decide_mobile_review,
)


@pytest.mark.parametrize("platform,surface,permission,cloud", itertools.product(
    tuple(MobilePlatform), tuple(MobileStorageSurface),
    tuple(PermissionScope), tuple(CloudResidency),
))
def test_every_mobile_combination_never_grants_mutation(platform, surface, permission, cloud):
    result = decide_mobile_review(MobileEvidence(
        platform=platform, surface=surface, permission=permission,
        cloud_residency=cloud, owner_verified=True, regeneration_proven=True,
        observed_local_bytes=2**40,
    ))
    assert result.mutation_authorized is False
    assert result.is_executable is False
    assert result.estimated_reclaim_bytes is None
    assert result.disposition is not CleanupDisposition.RECLAIM_PROVEN


@pytest.mark.parametrize("platform", list(MobilePlatform))
@pytest.mark.parametrize("surface", [
    MobileStorageSurface.OTHER_APP_PRIVATE, MobileStorageSurface.SYSTEM_MANAGED,
])
def test_app_private_and_system_are_always_protected(platform, surface):
    result = decide_mobile_review(MobileEvidence(
        platform, surface, PermissionScope.AUTHORIZED,
        CloudResidency.LOCAL_ONLY, owner_verified=True, regeneration_proven=True,
    ))
    assert result.disposition is CleanupDisposition.PROTECTED
    assert result.route is MobileReviewRoute.MANAGE_WITH_OWNER_APP


@pytest.mark.parametrize("platform", list(MobilePlatform))
def test_own_app_cache_needs_both_proofs(platform):
    base = dict(platform=platform, surface=MobileStorageSurface.OWN_APP_CACHE)
    assert decide_mobile_review(MobileEvidence(**base)).disposition is CleanupDisposition.PROTECTED
    assert decide_mobile_review(MobileEvidence(**base, owner_verified=True)).disposition is CleanupDisposition.PROTECTED
    result = decide_mobile_review(MobileEvidence(**base, owner_verified=True, regeneration_proven=True))
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.route is MobileReviewRoute.REVIEW_OWN_CACHE


@pytest.mark.parametrize("platform,surface", itertools.product(
    tuple(MobilePlatform),
    (MobileStorageSurface.MEDIA_LIBRARY, MobileStorageSurface.USER_SELECTED_DOCUMENTS),
))
def test_scoped_review_requires_permission_and_local_residency(platform, surface):
    base = dict(platform=platform, surface=surface)
    assert decide_mobile_review(MobileEvidence(**base)).route is MobileReviewRoute.REQUEST_SCOPED_ACCESS
    limited = MobileEvidence(**base, permission=PermissionScope.LIMITED, cloud_residency=CloudResidency.LOCAL_ONLY)
    result = decide_mobile_review(limited)
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert "LIMITED_SELECTION_ONLY" in result.reason_codes
    assert result.route is (MobileReviewRoute.REVIEW_IN_SYSTEM_MEDIA_UI if surface is MobileStorageSurface.MEDIA_LIBRARY
                           else MobileReviewRoute.REVIEW_IN_DOCUMENT_PROVIDER)
    remote = MobileEvidence(**base, permission=PermissionScope.AUTHORIZED, cloud_residency=CloudResidency.REMOTE_ONLY)
    assert decide_mobile_review(remote).route is MobileReviewRoute.VERIFY_LOCAL_RESIDENCY


@pytest.mark.parametrize("platform", list(MobilePlatform))
def test_synced_photos_cannot_imply_backup_or_reclaim(platform):
    result = decide_mobile_review(MobileEvidence(
        platform, MobileStorageSurface.MEDIA_LIBRARY,
        PermissionScope.AUTHORIZED, CloudResidency.SYNCED, observed_local_bytes=10_000,
    ))
    assert "SYNC_IS_NOT_BACKUP_PROOF" in result.reason_codes
    assert result.estimated_reclaim_bytes is None
    assert result.mutation_authorized is False


@pytest.mark.parametrize("invalid", ["ANDROID", None, 0])
def test_untyped_platform_fails_closed(invalid):
    with pytest.raises(TypeError):
        MobileEvidence(invalid, MobileStorageSurface.MEDIA_LIBRARY)


@pytest.mark.parametrize("size", [-1, True, 1.2, "500"])
def test_invalid_size_fails_closed(size):
    with pytest.raises(ValueError):
        MobileEvidence(MobilePlatform.IOS, MobileStorageSurface.MEDIA_LIBRARY, observed_local_bytes=size)


def test_policy_rejects_unstructured_object():
    with pytest.raises(TypeError):
        decide_mobile_review({"platform": "ANDROID", "surface": "MEDIA_LIBRARY"})
