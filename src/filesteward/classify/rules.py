"""Deterministic disposition rules: gates, nomination, directory composition.

Rules may nominate `RECLAIM_PROVEN` only from explicit, operator- or
adapter-authored contract evidence plus complete observation. No age,
size, name, or location heuristic may produce a reclaim nomination;
those inputs are deliberately never consulted by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

from filesteward.classify.gates import GateResults, ProvisionalDisposition
from filesteward.models import CleanupDisposition, InventoryItem, ScanCompleteness
from filesteward.protect.index import ProtectionRelation

__all__ = [
    "CacheContract",
    "evaluate_gates",
    "is_managed",
    "match_contract",
    "nominate",
    "resolve_directory_disposition",
]


@dataclass(frozen=True)
class CacheContract:
    """Explicit evidence that a path prefix is a deterministic,
    regenerable cache artifact.

    Contracts are authored by an operator or an adapter and supplied as
    input. Nothing in this module infers a contract from observed
    characteristics of a file.
    """

    contract_id: str
    path_prefix: str
    description: str
    regenerable: bool = True
    provenance_documented: bool = True
    recoverability_documented: bool = True

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise ValueError("contract_id must be non-empty")
        if not self.path_prefix.strip():
            raise ValueError("path_prefix must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")


def _norm(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").casefold()


def _prefix_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def match_contract(
    item: InventoryItem, contracts: Iterable[CacheContract]
) -> Optional[CacheContract]:
    """Return the first contract whose prefix matches, boundary-aware.

    Prefix comparison is case-insensitive and separator-insensitive, and
    only matches on a full path-component boundary
    (``C:/a/cache`` matches ``C:/a/cache/x`` and ``C:/a/cache`` itself,
    never ``C:/a/cache2/x``).
    """

    path = _norm(item.path)
    for contract in contracts:
        if _prefix_matches(path, _norm(contract.path_prefix)):
            return contract
    return None


def is_managed(
    item: InventoryItem, managed_paths: Iterable[str]
) -> bool:
    """True when the item sits beneath a declared system/application-
    managed prefix.

    The marking is declared by an adapter or the operator and supplied
    as input, exactly like a contract; nothing here infers "managed"
    from observed characteristics of a file. Lookup is boundary-aware
    with the same semantics as :func:`match_contract`.
    """

    path = _norm(item.path)
    for raw_prefix in managed_paths:
        prefix = _norm(raw_prefix)
        if prefix and _prefix_matches(path, prefix):
            return True
    return False


def evaluate_gates(
    item: InventoryItem,
    *,
    protection: ProtectionRelation = ProtectionRelation.UNRELATED,
    contracts: Sequence[CacheContract] = (),
    managed_paths: Sequence[str] = (),
    descendant_complete: bool = True,
) -> GateResults:
    """Derive normalized deterministic gate facts for one item.

    Facts only: no scoring, no persuasion, no recommendation. Missing
    evidence is recorded as missing, never inferred.
    """

    contract = match_contract(item, contracts)
    managed = is_managed(item, managed_paths)
    observation_complete = bool(
        item.scan_completeness is ScanCompleteness.COMPLETE and descendant_complete
    )
    notes = (
        f"protection={protection.value}",
        f"scan={item.scan_completeness.value}",
        f"descendants_complete={descendant_complete}",
        f"contract={contract.contract_id if contract else 'none'}",
        f"system_managed={managed}",
    )
    return GateResults(
        item_id=item.item_id,
        protection=protection,
        observation_complete=observation_complete,
        contract_id=contract.contract_id if contract else None,
        provenance_documented=bool(contract and contract.provenance_documented),
        recoverability_documented=bool(
            contract and contract.recoverability_documented
        ),
        regenerable=bool(contract and contract.regenerable),
        managed=managed,
        notes=notes,
    )


def nominate(gates: GateResults) -> ProvisionalDisposition:
    """Fail-closed deterministic nomination from gate facts.

    Precedence: protection beats everything; incomplete observation is
    `UNKNOWN`; a system/application-managed mark without an explicit
    adapter/contract is `HUMAN_REVIEW` (never an automatic mutation
    candidate); missing contract or undocumented provenance/
    recoverability is `HUMAN_REVIEW`; documented non-regenerable
    content is `KEEP_PROVEN`; only then may `RECLAIM_PROVEN` be
    nominated — and it remains provisional until the independent
    challenge sustains it.
    """

    if gates.protection in (
        ProtectionRelation.SELF,
        ProtectionRelation.DESCENDANT,
    ):
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.PROTECTED,
            basis=f"protection relation {gates.protection.value}",
            gates=gates,
        )
    if gates.protection is ProtectionRelation.ANCESTOR:
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis="protected subtree contained; decompose children",
            gates=gates,
        )
    if not gates.observation_complete:
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.UNKNOWN,
            basis="observation incomplete",
            gates=gates,
        )
    if gates.managed and gates.contract_id is None:
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis=(
                "system/application-managed; excluded from automatic "
                "mutation candidacy without an explicit adapter/contract"
            ),
            gates=gates,
        )
    if gates.contract_id is None:
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis="no explicit contract evidence",
            gates=gates,
        )
    if not (gates.provenance_documented and gates.recoverability_documented):
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis="provenance or recoverability not documented",
            gates=gates,
        )
    if not gates.regenerable:
        return ProvisionalDisposition(
            item_id=gates.item_id,
            disposition=CleanupDisposition.KEEP_PROVEN,
            basis=f"content retained: contract {gates.contract_id} not regenerable",
            gates=gates,
        )
    return ProvisionalDisposition(
        item_id=gates.item_id,
        disposition=CleanupDisposition.RECLAIM_PROVEN,
        basis=f"all gates satisfied under contract {gates.contract_id}",
        gates=gates,
    )


def resolve_directory_disposition(
    child_dispositions: Sequence[CleanupDisposition],
) -> Tuple[CleanupDisposition, str]:
    """Composition rule for a whole-directory action (S6).

    A directory may only be `RECLAIM_PROVEN` when every descendant is.
    Any protected, incomplete, or ambiguous descendant forces
    decomposition; retained descendants keep the directory.
    """

    for disposition in child_dispositions:
        if not isinstance(disposition, CleanupDisposition):
            raise TypeError(
                f"expected CleanupDisposition, got {type(disposition).__name__}"
            )
    if not child_dispositions:
        return (
            CleanupDisposition.HUMAN_REVIEW,
            "no descendant evidence; whole-directory action unproven",
        )
    if CleanupDisposition.PROTECTED in child_dispositions:
        return (
            CleanupDisposition.PROTECTED,
            "contains protected descendant; whole-directory action "
            "prohibited, decompose",
        )
    if CleanupDisposition.UNKNOWN in child_dispositions:
        return (
            CleanupDisposition.UNKNOWN,
            "descendant evidence incomplete",
        )
    if CleanupDisposition.HUMAN_REVIEW in child_dispositions:
        return (
            CleanupDisposition.HUMAN_REVIEW,
            "ambiguous descendant; decompose",
        )
    if CleanupDisposition.KEEP_PROVEN in child_dispositions:
        return (
            CleanupDisposition.KEEP_PROVEN,
            "retained descendant",
        )
    return (
        CleanupDisposition.RECLAIM_PROVEN,
        "all descendants reclaim-proven",
    )
