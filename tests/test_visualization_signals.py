from dataclasses import dataclass
from enum import Enum

from filesteward.visualization.signals import (
    SignalKind,
    primary_decision_signal,
    project_decision_signals,
)


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"
    WAITING = "WAITING"
    UNKNOWN = "UNKNOWN"


class Auth(str, Enum):
    UNAPPROVED = "UNAPPROVED"
    APPROVED = "APPROVED_FOR_ACTION"


class Completeness(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class Step:
    gate_id: str
    name: str
    status: Status
    explanation: str
    is_first_unresolved: bool = False


@dataclass(frozen=True)
class Node:
    gate_steps: tuple[Step, ...]
    authorization_state: Auth = Auth.UNAPPROVED
    scan_completeness: Completeness = Completeness.COMPLETE


def test_first_unresolved_gate_is_the_only_pulsing_primary_signal() -> None:
    node = Node(
        gate_steps=(
            Step("protection", "Protected overlap", Status.PASS, "None observed"),
            Step(
                "observation",
                "Observation complete",
                Status.FAIL,
                "Scan evidence is incomplete",
                True,
            ),
            Step("approval", "Operator approval", Status.WAITING, "Not reached"),
        )
    )
    signals = project_decision_signals(node)
    primary = primary_decision_signal(node)
    assert primary is not None
    assert primary.signal_id == "gate:observation"
    assert primary.kind is SignalKind.UNRESOLVED
    assert primary.pulse is True
    assert sum(signal.pulse for signal in signals) == 1
    assert any(signal.kind is SignalKind.UNAPPROVED for signal in signals)


def test_blocked_primary_is_hard_stop_not_inviting_pulse() -> None:
    node = Node(
        gate_steps=(
            Step(
                "protection",
                "Protected overlap",
                Status.BLOCK,
                "Protected",
                True,
            ),
        )
    )
    primary = primary_decision_signal(node)
    assert primary is not None
    assert primary.kind is SignalKind.BLOCKED
    assert primary.hard_stop is True
    assert primary.pulse is False


def test_incomplete_scan_gets_unknown_signal_without_promoting_authority() -> None:
    node = Node(gate_steps=(), scan_completeness=Completeness.INCOMPLETE)
    signals = project_decision_signals(node)
    assert signals[0].kind is SignalKind.UNKNOWN
    assert signals[0].is_primary is True
    assert signals[-1].kind is SignalKind.UNAPPROVED


def test_passed_gate_stays_cool_and_non_primary() -> None:
    node = Node(
        gate_steps=(
            Step("protection", "Protected overlap", Status.PASS, "None observed"),
        ),
        authorization_state=Auth.APPROVED,
    )
    signals = project_decision_signals(node)
    assert len(signals) == 1
    assert signals[0].kind is SignalKind.PASSED
    assert signals[0].pulse is False
    assert signals[0].hard_stop is False
    assert signals[0].is_primary is False
