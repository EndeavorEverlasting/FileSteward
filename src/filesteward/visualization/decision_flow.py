"""Typed decision-session state for Memory Atlas Decision Chamber.

This module owns presentation/workflow state only. Evidence disposition remains
owned by classification, and authorization remains owned by an explicit
operator approval artifact. Nothing here mutates source files.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, Sequence

from filesteward.models import AuthorizationState, CleanupDisposition

__all__ = [
    "DecisionFlowState",
    "DecisionIntent",
    "DecisionScene",
    "ExecutionState",
    "PendingAction",
    "allowed_intents",
    "choose_intent",
    "execution_state_for",
    "observe_authorization",
    "open_decision_session",
]


class _Gate(Protocol):
    gate_id: str
    status: object
    is_first_unresolved: bool


class _Node(Protocol):
    node_id: str
    disposition: object
    authorization_state: object
    gate_steps: Sequence[_Gate]


class DecisionScene(str, Enum):
    MAP = "MAP"
    FOCUS = "FOCUS"
    GATE = "GATE"
    RESOLVE = "RESOLVE"
    APPROVAL = "APPROVAL"
    STAGED = "STAGED"
    RESULT = "RESULT"
    CLOSED = "CLOSED"


class DecisionIntent(str, Enum):
    RESCAN = "RESCAN"
    DECLARE_REGENERABLE_CONTRACT = "DECLARE_REGENERABLE_CONTRACT"
    KEEP = "KEEP"
    REVIEW_LATER = "REVIEW_LATER"
    APPROVE_QUARANTINE = "APPROVE_QUARANTINE"
    DELETE_PERMANENTLY = "DELETE_PERMANENTLY"


class PendingAction(str, Enum):
    NONE = "NONE"
    RESCAN = "RESCAN"
    DECLARE_CONTRACT = "DECLARE_CONTRACT"
    RECORD_KEEP = "RECORD_KEEP"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    QUARANTINE = "QUARANTINE"
    DELETE_PERMANENTLY = "DELETE_PERMANENTLY"


class ExecutionState(str, Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    EXECUTABLE = "executable"


@dataclass(frozen=True)
class DecisionFlowState:
    selected_node_id: str
    scene: DecisionScene
    disposition: CleanupDisposition
    authorization_state: AuthorizationState
    active_gate_id: str | None = None
    last_scene: DecisionScene | None = None
    pending_action: PendingAction = PendingAction.NONE
    last_transition: str = "open"
    scene_revision: int = 0
    execution_state: ExecutionState = ExecutionState.EXECUTABLE


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _first_unresolved(node: _Node) -> str | None:
    for step in node.gate_steps:
        if bool(step.is_first_unresolved):
            return step.gate_id
    for step in node.gate_steps:
        if _value(step.status) != "PASS":
            return step.gate_id
    return None


def open_decision_session(node: _Node) -> DecisionFlowState:
    """Open the truthful scene for the node's current persisted state."""

    disposition = CleanupDisposition(_value(node.disposition))
    authorization = AuthorizationState(_value(node.authorization_state))
    active_gate_id = _first_unresolved(node)

    if disposition in {CleanupDisposition.PROTECTED, CleanupDisposition.KEEP_PROVEN}:
        scene = DecisionScene.CLOSED
    elif disposition is CleanupDisposition.RECLAIM_PROVEN:
        if authorization is AuthorizationState.UNAPPROVED:
            scene = DecisionScene.APPROVAL
        elif authorization is AuthorizationState.APPROVED_FOR_ACTION:
            scene = DecisionScene.STAGED
        else:
            scene = DecisionScene.CLOSED
    else:
        scene = DecisionScene.RESOLVE if active_gate_id else DecisionScene.FOCUS

    flow = DecisionFlowState(
        selected_node_id=node.node_id,
        scene=scene,
        disposition=disposition,
        authorization_state=authorization,
        active_gate_id=active_gate_id,
        pending_action=(
            PendingAction.QUARANTINE
            if scene is DecisionScene.STAGED
            else PendingAction.NONE
        ),
    )
    return replace(flow, execution_state=execution_state_for(flow))


def allowed_intents(state: DecisionFlowState) -> tuple[DecisionIntent, ...]:
    """Return operator choices without pretending they are evidence transitions."""

    if state.scene in {DecisionScene.GATE, DecisionScene.RESOLVE}:
        if state.disposition is CleanupDisposition.UNKNOWN:
            return (
                DecisionIntent.RESCAN,
                DecisionIntent.KEEP,
                DecisionIntent.REVIEW_LATER,
            )
        if state.disposition is CleanupDisposition.HUMAN_REVIEW:
            return (
                DecisionIntent.DECLARE_REGENERABLE_CONTRACT,
                DecisionIntent.KEEP,
                DecisionIntent.REVIEW_LATER,
            )

    if (
        state.scene is DecisionScene.APPROVAL
        and state.disposition is CleanupDisposition.RECLAIM_PROVEN
        and state.authorization_state is AuthorizationState.UNAPPROVED
    ):
        return (
            DecisionIntent.APPROVE_QUARANTINE,
            DecisionIntent.DELETE_PERMANENTLY,
            DecisionIntent.KEEP,
            DecisionIntent.REVIEW_LATER,
        )

    return ()


def choose_intent(
    state: DecisionFlowState,
    intent: DecisionIntent,
) -> DecisionFlowState:
    """Record an operator intent; never rewrite CleanupDisposition."""

    if intent not in allowed_intents(state):
        raise ValueError(
            f"intent {intent.value} is not allowed from "
            f"{state.disposition.value}/{state.scene.value}"
        )

    common = {
        "last_scene": state.scene,
        "last_transition": intent.value.lower(),
    }

    if intent is DecisionIntent.RESCAN:
        next_state = replace(state, pending_action=PendingAction.RESCAN, **common)
        return replace(next_state, execution_state=execution_state_for(next_state))
    if intent is DecisionIntent.DECLARE_REGENERABLE_CONTRACT:
        next_state = replace(
            state,
            pending_action=PendingAction.DECLARE_CONTRACT,
            **common,
        )
        return replace(next_state, execution_state=execution_state_for(next_state))
    if intent is DecisionIntent.KEEP:
        next_state = replace(
            state,
            scene=DecisionScene.CLOSED,
            pending_action=PendingAction.RECORD_KEEP,
            **common,
        )
        return replace(next_state, execution_state=execution_state_for(next_state))
    if intent is DecisionIntent.REVIEW_LATER:
        return replace(
            state,
            scene=DecisionScene.CLOSED,
            pending_action=PendingAction.NONE,
            **common,
        )
    if intent is DecisionIntent.DELETE_PERMANENTLY:
        next_state = replace(
            state,
            pending_action=PendingAction.DELETE_PERMANENTLY,
            **common,
        )
        return replace(next_state, execution_state=execution_state_for(next_state))

    # APPROVE_QUARANTINE is an approval request, not approval itself.
    next_state = replace(
        state,
        scene=DecisionScene.APPROVAL,
        pending_action=PendingAction.REQUEST_APPROVAL,
        **common,
    )
    return replace(next_state, execution_state=execution_state_for(next_state))


def observe_authorization(
    state: DecisionFlowState,
    authorization: AuthorizationState,
) -> DecisionFlowState:
    """Advance only after authoritative authorization has been read back."""

    if (
        authorization is AuthorizationState.APPROVED_FOR_ACTION
        and state.disposition is not CleanupDisposition.RECLAIM_PROVEN
    ):
        raise ValueError(
            "only RECLAIM_PROVEN evidence may become action-approved"
        )

    if authorization is AuthorizationState.APPROVED_FOR_ACTION:
        return replace(
            state,
            authorization_state=authorization,
            scene=DecisionScene.STAGED,
            pending_action=PendingAction.QUARANTINE,
            last_scene=state.scene,
            last_transition="approval-receipt-validated",
        )

    if authorization in {
        AuthorizationState.APPLIED,
        AuthorizationState.VERIFIED,
    }:
        return replace(
            state,
            authorization_state=authorization,
            scene=DecisionScene.CLOSED,
            pending_action=PendingAction.NONE,
            last_scene=state.scene,
            last_transition=authorization.value.lower(),
        )

    return replace(
        state,
        authorization_state=authorization,
        execution_state=execution_state_for(
            replace(state, authorization_state=authorization)
        ),
    )


def execution_state_for(state: DecisionFlowState) -> ExecutionState:
    if state.pending_action in {
        PendingAction.RESCAN,
        PendingAction.DECLARE_CONTRACT,
        PendingAction.DELETE_PERMANENTLY,
        PendingAction.REQUEST_APPROVAL,
    }:
        return ExecutionState.PENDING
    if state.scene is DecisionScene.CLOSED:
        return ExecutionState.COMPLETE
    if state.scene is DecisionScene.RESULT:
        return ExecutionState.COMPLETE
    if not allowed_intents(state) and state.scene is not DecisionScene.STAGED:
        return ExecutionState.BLOCKED
    return ExecutionState.EXECUTABLE
