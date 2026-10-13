"""Decision-signal projection for Memory Atlas v3.

Signals are display-only projections of persisted gate/authorization facts.
They never promote evidence, grant authority, or mutate a PresentationNode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence

__all__ = [
    "DecisionSignal",
    "SignalKind",
    "primary_decision_signal",
    "project_decision_signals",
]


class _Step(Protocol):
    gate_id: str
    name: str
    status: object
    explanation: str
    is_first_unresolved: bool


class _Node(Protocol):
    gate_steps: Sequence[_Step]
    authorization_state: object
    scan_completeness: object


class SignalKind(str, Enum):
    PASSED = "PASSED"
    UNRESOLVED = "UNRESOLVED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
    DORMANT = "DORMANT"
    UNAPPROVED = "UNAPPROVED"


@dataclass(frozen=True)
class DecisionSignal:
    signal_id: str
    kind: SignalKind
    label: str
    detail: str
    is_primary: bool = False
    pulse: bool = False
    hard_stop: bool = False

    @property
    def accessible_text(self) -> str:
        prefix = (
            "First unresolved decision"
            if self.is_primary
            else self.kind.value.replace("_", " ").title()
        )
        return f"{prefix}: {self.label}. {self.detail}".strip()


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _kind_for_step(step: _Step) -> SignalKind:
    status = _value(step.status)
    if status == "BLOCK":
        return SignalKind.BLOCKED
    if step.is_first_unresolved:
        if status == "UNKNOWN":
            return SignalKind.UNKNOWN
        return SignalKind.UNRESOLVED
    if status == "PASS":
        return SignalKind.PASSED
    if status == "UNKNOWN":
        return SignalKind.UNKNOWN
    return SignalKind.DORMANT


def project_decision_signals(node: _Node) -> tuple[DecisionSignal, ...]:
    """Project persisted decision facts into a stable visual-signal vocabulary."""

    signals: list[DecisionSignal] = []
    for step in node.gate_steps:
        kind = _kind_for_step(step)
        signals.append(
            DecisionSignal(
                signal_id=f"gate:{step.gate_id}",
                kind=kind,
                label=step.name,
                detail=step.explanation,
                is_primary=bool(step.is_first_unresolved),
                pulse=kind is SignalKind.UNRESOLVED and bool(step.is_first_unresolved),
                hard_stop=kind is SignalKind.BLOCKED,
            )
        )

    if _value(node.scan_completeness) == "INCOMPLETE" and not any(
        signal.kind is SignalKind.UNKNOWN and signal.is_primary for signal in signals
    ):
        signals.append(
            DecisionSignal(
                signal_id="scan:incomplete",
                kind=SignalKind.UNKNOWN,
                label="Observation incomplete",
                detail="Scan evidence is incomplete.",
                is_primary=not any(signal.is_primary for signal in signals),
            )
        )

    if _value(node.authorization_state) == "UNAPPROVED":
        signals.append(
            DecisionSignal(
                signal_id="authorization:unapproved",
                kind=SignalKind.UNAPPROVED,
                label="Authorization",
                detail="UNAPPROVED",
            )
        )

    return tuple(signals)


def primary_decision_signal(node: _Node) -> DecisionSignal | None:
    signals = project_decision_signals(node)
    return next((signal for signal in signals if signal.is_primary), None)
