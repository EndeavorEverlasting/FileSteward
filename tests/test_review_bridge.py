import pytest

from filesteward.approval import ApprovalAction
from filesteward.review_bridge import (
    APPROVAL_PATH,
    DECISION_PATH,
    DELETE_PATH,
    STATE_PATH,
    ApprovalRequest,
    DecisionBridgeIntent,
    DecisionRequest,
    is_loopback_host,
)


def test_bridge_routes_are_versioned_and_loopback_only() -> None:
    assert STATE_PATH == "/api/v1/state"
    assert DECISION_PATH == "/api/v1/decision"
    assert APPROVAL_PATH == "/api/v1/approval"
    assert DELETE_PATH == "/api/v1/delete"
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("::1")
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("192.168.1.10")


def test_decision_request_is_explicit_and_serializable() -> None:
    request = DecisionRequest(
        run_id="run",
        item_id="item",
        intent=DecisionBridgeIntent.RESCAN,
    )
    assert request.as_mapping() == {
        "run_id": "run",
        "item_id": "item",
        "intent": "RESCAN",
    }


def test_approval_requires_exact_digest_quarantine_and_confirmation() -> None:
    request = ApprovalRequest(
        run_id="run",
        item_id="item",
        cleanup_plan_sha256="a" * 64,
        action=ApprovalAction.QUARANTINE,
        confirm=True,
    )
    assert request.as_mapping()["action"] == "QUARANTINE"

    with pytest.raises(ValueError, match="sha256"):
        ApprovalRequest(
            run_id="run",
            item_id="item",
            cleanup_plan_sha256="bad",
            action=ApprovalAction.QUARANTINE,
            confirm=True,
        )
    with pytest.raises(ValueError, match="confirm=true"):
        ApprovalRequest(
            run_id="run",
            item_id="item",
            cleanup_plan_sha256="b" * 64,
            action=ApprovalAction.QUARANTINE,
            confirm=False,
        )
