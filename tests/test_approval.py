import pytest

from filesteward.approval import (
    ApprovalAction,
    ApprovalRecord,
    validate_approval_against_plan,
)
from filesteward.models import AuthorizationState


def _record(*item_ids: str) -> ApprovalRecord:
    return ApprovalRecord(
        run_id="synthetic-run",
        cleanup_plan_sha256="a" * 64,
        approved_item_ids=tuple(item_ids),
    )


def test_approval_record_is_bound_to_plan_digest_and_quarantine() -> None:
    record = _record("a", "b")
    assert record.action is ApprovalAction.QUARANTINE
    assert record.authorization_state is AuthorizationState.APPROVED_FOR_ACTION
    assert record.as_mapping()["cleanup_plan_sha256"] == "a" * 64


def test_approval_record_rejects_bad_digest_or_duplicate_rows() -> None:
    with pytest.raises(ValueError, match="sha256"):
        ApprovalRecord(
            run_id="run",
            cleanup_plan_sha256="not-a-digest",
            approved_item_ids=("a",),
        )
    with pytest.raises(ValueError, match="unique"):
        ApprovalRecord(
            run_id="run",
            cleanup_plan_sha256="b" * 64,
            approved_item_ids=("a", "a"),
        )


def test_approval_validation_accepts_only_exact_reclaim_quarantine_rows() -> None:
    plan = (
        {
            "item_id": "a",
            "disposition": "RECLAIM_PROVEN",
            "proposed_action": "quarantine",
        },
        {
            "item_id": "b",
            "disposition": "RECLAIM_PROVEN",
            "proposed_action": "quarantine",
        },
    )
    assert validate_approval_against_plan(_record("a", "b"), plan) == ()


def test_approval_validation_fails_closed_on_drift() -> None:
    plan = (
        {
            "item_id": "a",
            "disposition": "HUMAN_REVIEW",
            "proposed_action": "quarantine",
        },
        {
            "item_id": "b",
            "disposition": "RECLAIM_PROVEN",
            "proposed_action": "delete",
        },
    )
    errors = validate_approval_against_plan(_record("a", "b", "c"), plan)
    assert any("not RECLAIM_PROVEN" in error for error in errors)
    assert any("must be quarantine" in error for error in errors)
    assert any("not present" in error for error in errors)
