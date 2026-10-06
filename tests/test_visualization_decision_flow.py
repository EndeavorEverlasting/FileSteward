from dataclasses import dataclass
from enum import Enum

import pytest

from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.visualization.decision_flow import (
    DecisionIntent,
    DecisionScene,
    PendingAction,
    allowed_intents,
    choose_intent,
    observe_authorization,
    open_decision_session,
)


class Status(str, Enum):
    PASS = "PASS"
    WAITING = "WAITING"


@dataclass(frozen=True)
class Step:
    gate_id: str
    status: Status
    is_first_unresolved: bool = False


@dataclass(frozen=True)
class Node:
    node_id: str
    disposition: CleanupDisposition
    authorization_state: AuthorizationState
    gate_steps: tuple[Step, ...] = ()


def test_unknown_opens_first_unresolved_gate_and_cannot_approve() -> None:
    state = open_decision_session(
        Node(
            "unknown",
            CleanupDisposition.UNKNOWN,
            AuthorizationState.UNAPPROVED,
            (Step("observation", Status.WAITING, True),),
        )
    )
    assert state.scene is DecisionScene.RESOLVE
    assert state.active_gate_id == "observation"
    assert DecisionIntent.APPROVE_QUARANTINE not in allowed_intents(state)
    assert DecisionIntent.DELETE_PERMANENTLY not in allowed_intents(state)
    with pytest.raises(ValueError, match="RECLAIM_PROVEN"):
        observe_authorization(state, AuthorizationState.APPROVED_FOR_ACTION)


def test_unknown_choices_are_legwork_not_evidence_promotion() -> None:
    state = open_decision_session(
        Node(
            "unknown",
            CleanupDisposition.UNKNOWN,
            AuthorizationState.UNAPPROVED,
            (Step("observation", Status.WAITING, True),),
        )
    )
    rescan = choose_intent(state, DecisionIntent.RESCAN)
    assert rescan.pending_action is PendingAction.RESCAN
    assert rescan.disposition is CleanupDisposition.UNKNOWN


def test_human_review_can_request_contract_but_not_self_promote() -> None:
    state = open_decision_session(
        Node(
            "review",
            CleanupDisposition.HUMAN_REVIEW,
            AuthorizationState.UNAPPROVED,
            (Step("contract", Status.WAITING, True),),
        )
    )
    next_state = choose_intent(
        state, DecisionIntent.DECLARE_REGENERABLE_CONTRACT
    )
    assert next_state.pending_action is PendingAction.DECLARE_CONTRACT
    assert next_state.disposition is CleanupDisposition.HUMAN_REVIEW


def test_reclaim_proven_requests_approval_before_staging() -> None:
    state = open_decision_session(
        Node(
            "reclaim",
            CleanupDisposition.RECLAIM_PROVEN,
            AuthorizationState.UNAPPROVED,
        )
    )
    assert state.scene is DecisionScene.APPROVAL
    requested = choose_intent(state, DecisionIntent.APPROVE_QUARANTINE)
    assert requested.pending_action is PendingAction.REQUEST_APPROVAL
    assert requested.authorization_state is AuthorizationState.UNAPPROVED
    delete = choose_intent(state, DecisionIntent.DELETE_PERMANENTLY)
    assert delete.pending_action is PendingAction.DELETE_PERMANENTLY
    kept = choose_intent(state, DecisionIntent.KEEP)
    assert kept.scene is DecisionScene.CLOSED

    staged = observe_authorization(
        requested, AuthorizationState.APPROVED_FOR_ACTION
    )
    assert staged.scene is DecisionScene.STAGED
    assert staged.pending_action is PendingAction.QUARANTINE
    assert staged.last_scene is DecisionScene.APPROVAL


def test_keep_closes_unknown_scene() -> None:
    state = open_decision_session(
        Node(
            "unknown",
            CleanupDisposition.UNKNOWN,
            AuthorizationState.UNAPPROVED,
            (Step("observation", Status.WAITING, True),),
        )
    )
    kept = choose_intent(state, DecisionIntent.KEEP)
    assert kept.scene is DecisionScene.CLOSED
    assert kept.last_scene is DecisionScene.RESOLVE


def test_protected_and_keep_nodes_never_open_delete_approval() -> None:
    for disposition in (
        CleanupDisposition.PROTECTED,
        CleanupDisposition.KEEP_PROVEN,
    ):
        state = open_decision_session(
            Node("closed", disposition, AuthorizationState.UNAPPROVED)
        )
        assert state.scene is DecisionScene.CLOSED
        assert allowed_intents(state) == ()
