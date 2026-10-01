"""Normalized deterministic evidence consumed by rules and challenger.

`GateResults` is a fact record: what was observed, nothing more.
`ProvisionalDisposition` is a rule output that may nominate
`RECLAIM_PROVEN`; it remains evidence, never approval, and carries no
score of any kind — no delete score, no confidence score, no
persuasion score.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional, Tuple

from filesteward.models import CleanupDisposition
from filesteward.protect.index import ProtectionRelation

__all__ = ["GateResults", "ProvisionalDisposition"]

_SCORE_FORBIDDEN_SUBSTRINGS = ("score", "confidence", "weight", "priority")


@dataclass(frozen=True)
class GateResults:
    """Deterministic gate facts for one candidate item.

    Produced by ``evaluate_gates``; consumed by ``nominate`` and by the
    independent adversarial challenger.
    """

    item_id: str
    protection: ProtectionRelation
    observation_complete: bool
    contract_id: Optional[str]
    provenance_documented: bool
    recoverability_documented: bool
    regenerable: bool
    notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if self.contract_id is None and (
            self.provenance_documented
            or self.recoverability_documented
            or self.regenerable
        ):
            raise ValueError(
                "documented evidence requires a contract_id; "
                "undocumented evidence must not carry provenance claims"
            )

    def passes_content_gates(self) -> bool:
        """Contract-backed, documented, regenerable evidence, complete."""

        return bool(
            self.observation_complete
            and self.contract_id is not None
            and self.provenance_documented
            and self.recoverability_documented
            and self.regenerable
        )


@dataclass(frozen=True)
class ProvisionalDisposition:
    """Rule output. ``RECLAIM_PROVEN`` here is provisional evidence that
    still faces the independent challenge. It is not approval."""

    item_id: str
    disposition: CleanupDisposition
    basis: str
    gates: GateResults

    def __post_init__(self) -> None:
        if not self.basis:
            raise ValueError("basis must be non-empty")
        if self.item_id != self.gates.item_id:
            raise ValueError("item_id must match its gate results")
        for field in fields(self):
            if any(
                token in field.name.lower() for token in _SCORE_FORBIDDEN_SUBSTRINGS
            ):  # pragma: no cover - structural tripwire
                raise ValueError(f"scored field forbidden: {field.name}")
        if self.disposition is CleanupDisposition.RECLAIM_PROVEN:
            gates = self.gates
            if gates.protection is not ProtectionRelation.UNRELATED:
                raise ValueError(
                    "RECLAIM_PROVEN requires unrelated protection relation"
                )
            if not gates.passes_content_gates():
                raise ValueError(
                    "RECLAIM_PROVEN requires complete contract-backed evidence"
                )
