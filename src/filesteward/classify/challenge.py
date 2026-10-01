"""Independent adversarial challenge: sustain or downgrade, never promote.

This pass consumes only normalized evidence (`InventoryItem`,
`GateResults`, and the provisional rule output). It deliberately does
not import the nominating rules, so a defect in rule construction cannot
silently travel into the challenge. The challenge may sustain a
provisional `RECLAIM_PROVEN` or downgrade it to `HUMAN_REVIEW`; it may
never promote any disposition upward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from filesteward.classify.gates import GateResults, ProvisionalDisposition
from filesteward.models import CleanupDisposition, EntryType, InventoryItem
from filesteward.protect.index import ProtectionRelation

__all__ = ["AdversarialChallenge", "ChallengeResult"]

_ACTIONABLE_ENTRY_TYPES = (EntryType.FILE, EntryType.DIRECTORY)


@dataclass(frozen=True)
class ChallengeResult:
    """Outcome of the independent challenge.

    ``sustained`` is ``True`` when the final disposition equals the
    provisional one. For a reclaim nomination it means the strongest
    plausible loss case was deterministically defeated.
    """

    item_id: str
    sustained: bool
    final_disposition: CleanupDisposition
    challenge_notes: Tuple[str, ...] = ()


class AdversarialChallenge:
    """Second, independent pass over normalized evidence."""

    def review(
        self,
        item: InventoryItem,
        gates: GateResults,
        provisional: ProvisionalDisposition,
    ) -> ChallengeResult:
        if not (
            item.item_id == gates.item_id == provisional.item_id
        ):
            raise ValueError("item, gates, and provisional ids must match")
        if provisional.gates != gates:
            raise ValueError(
                "provisional disposition must carry the reviewed gate results"
            )

        if provisional.disposition is not CleanupDisposition.RECLAIM_PROVEN:
            return ChallengeResult(
                item_id=item.item_id,
                sustained=True,
                final_disposition=provisional.disposition,
                challenge_notes=(
                    "no reclaim nomination; challenge performs no upward promotion",
                ),
            )

        triggers: list[str] = []
        if gates.protection is not ProtectionRelation.UNRELATED:
            triggers.append(
                f"protection relation {gates.protection.value} present"
            )
        if not gates.observation_complete:
            triggers.append("observation incomplete")
        if not gates.passes_content_gates():
            triggers.append("gate evidence insufficient for reclaim")
        if item.link_count is not None and item.link_count > 1:
            triggers.append(
                f"shared hard-link content (link_count={item.link_count}); "
                "canonical survivor not proven"
            )
        if item.is_cloud_placeholder:
            triggers.append(
                "cloud placeholder content not locally verifiable "
                "without hydration"
            )
        if item.is_symlink:
            triggers.append(
                "symlink target state not observed under no-follow semantics"
            )
        if item.is_reparse_point:
            triggers.append(
                "reparse target state not observed under no-follow semantics"
            )
        if item.entry_type not in _ACTIONABLE_ENTRY_TYPES:
            triggers.append(
                f"entry type {item.entry_type.value} is not action-safe"
            )

        if triggers:
            return ChallengeResult(
                item_id=item.item_id,
                sustained=False,
                final_disposition=CleanupDisposition.HUMAN_REVIEW,
                challenge_notes=tuple(triggers),
            )
        return ChallengeResult(
            item_id=item.item_id,
            sustained=True,
            final_disposition=CleanupDisposition.RECLAIM_PROVEN,
            challenge_notes=(
                "strongest plausible loss cases deterministically defeated",
            ),
        )
