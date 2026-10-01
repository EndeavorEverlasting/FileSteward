"""L2 proof: independent adversarial challenge.

Scenario coverage: S4 (sustained reclaim), S5 (challenge defeat with no
upward promotion), and structural independence of the challenger from
the nominating rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from filesteward.classify import (
    AdversarialChallenge,
    CacheContract,
    ChallengeResult,
    ProvisionalDisposition,
    evaluate_gates,
    nominate,
)
from filesteward.classify import challenge as challenge_module
from filesteward.models import (
    CleanupDisposition,
    EntryType,
    InventoryItem,
    ScanCompleteness,
)
from filesteward.protect.index import ProtectionRelation

CACHE_CONTRACT = CacheContract(
    contract_id="synthetic.pip-cache",
    path_prefix="C:/synthetic/AppData/Local/pip/cache",
    description="synthetic deterministic pip cache artifact",
)


def make_item(**overrides: object) -> InventoryItem:
    base: dict = {
        "item_id": "item-1",
        "path": "C:/synthetic/AppData/Local/pip/cache/http/hash/body.whl",
        "entry_type": EntryType.FILE,
        "logical_size_bytes": 1_048_576,
        "allocated_size_bytes": 1_048_576,
        "link_count": 1,
    }
    base.update(overrides)
    return InventoryItem(**base)  # type: ignore[arg-type]


def nominal(item: InventoryItem | None = None):
    """Rules nominate reclaim for a clean synthetic cache artifact."""

    item = item or make_item()
    gates = evaluate_gates(item, contracts=(CACHE_CONTRACT,))
    provisional = nominate(gates)
    assert provisional.disposition is CleanupDisposition.RECLAIM_PROVEN
    return item, gates, provisional


def review(item: InventoryItem) -> ChallengeResult:
    gates = evaluate_gates(item, contracts=(CACHE_CONTRACT,))
    provisional = nominate(gates)
    return AdversarialChallenge().review(item, gates, provisional)


# --- S4: sustain -------------------------------------------------------

def test_s4_challenge_sustains_nominal_cache_artifact() -> None:
    item, gates, provisional = nominal()
    result = AdversarialChallenge().review(item, gates, provisional)
    assert result.sustained is True
    assert result.final_disposition is CleanupDisposition.RECLAIM_PROVEN
    assert result.challenge_notes


# --- S5: defeat --------------------------------------------------------

def test_s5_hard_link_sharing_defeats_reclaim() -> None:
    result = review(make_item(link_count=2))
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.sustained is False
    assert any("hard-link" in note for note in result.challenge_notes)


def test_s5_cloud_placeholder_content_not_verifiable() -> None:
    result = review(make_item(is_cloud_placeholder=True))
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.sustained is False
    assert any("placeholder" in note for note in result.challenge_notes)


def test_s5_symlink_target_unobserved() -> None:
    result = review(
        make_item(entry_type=EntryType.SYMLINK, is_symlink=True, link_count=1)
    )
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.sustained is False


def test_s5_reparse_point_target_unobserved() -> None:
    result = review(
        make_item(entry_type=EntryType.REPARSE_POINT, is_reparse_point=True)
    )
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.sustained is False


def test_s5_unknown_entry_type_is_not_action_safe() -> None:
    result = review(make_item(entry_type=EntryType.OTHER))
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.sustained is False


def test_s5_downgrade_is_to_human_review_not_stronger() -> None:
    for item in (
        make_item(link_count=4),
        make_item(is_cloud_placeholder=True),
    ):
        assert review(item).final_disposition is CleanupDisposition.HUMAN_REVIEW


# --- no upward promotion ----------------------------------------------


@pytest.mark.parametrize(
    "setup",
    [
        pytest.param(
            lambda: evaluate_gates(
                make_item(path="C:/synthetic/Downloads/old-backup.tar")
            ),
            id="no-contract",
        ),
        pytest.param(
            lambda: evaluate_gates(
                make_item(
                    scan_completeness=ScanCompleteness.INCOMPLETE,
                    scan_error="synthetic access denied",
                ),
                contracts=(CACHE_CONTRACT,),
            ),
            id="incomplete",
        ),
        pytest.param(
            lambda: evaluate_gates(
                make_item(),
                protection=ProtectionRelation.DESCENDANT,
                contracts=(CACHE_CONTRACT,),
            ),
            id="protected",
        ),
    ],
)
def test_s5_challenge_never_promotes_upward(setup) -> None:
    gates = setup()
    item = make_item(
        item_id=gates.item_id,
        scan_completeness=(
            ScanCompleteness.INCOMPLETE
            if not gates.observation_complete
            else ScanCompleteness.COMPLETE
        ),
        scan_error=(
            "synthetic access denied" if not gates.observation_complete else None
        ),
        path="C:/synthetic/Downloads/old-backup.tar"
        if gates.contract_id is None
        else "C:/synthetic/AppData/Local/pip/cache/http/hash/body.whl",
    )
    provisional = nominate(gates)
    result = AdversarialChallenge().review(item, gates, provisional)
    assert result.final_disposition is provisional.disposition
    assert result.final_disposition is not CleanupDisposition.RECLAIM_PROVEN
    assert result.sustained is True
    assert "no upward promotion" in result.challenge_notes[0]


def test_challenge_cannot_promote_even_when_gates_pass() -> None:
    item = make_item()
    gates = evaluate_gates(item, contracts=(CACHE_CONTRACT,))
    assert gates.passes_content_gates()
    downgraded_by_rule = nominate(
        evaluate_gates(
            item,
            protection=ProtectionRelation.ANCESTOR,
            contracts=(CACHE_CONTRACT,),
        )
    )
    assert downgraded_by_rule.disposition is CleanupDisposition.HUMAN_REVIEW
    forged = ProvisionalDisposition(
        item_id=item.item_id,
        disposition=CleanupDisposition.HUMAN_REVIEW,
        basis="rule output before challenge",
        gates=gates,
    )
    result = AdversarialChallenge().review(item, gates, forged)
    assert result.final_disposition is CleanupDisposition.HUMAN_REVIEW


# --- integrity and independence ---------------------------------------

def test_challenge_requires_matching_ids_and_gates() -> None:
    item, gates, provisional = nominal()
    other = make_item(item_id="item-2")
    with pytest.raises(ValueError, match="ids must match"):
        AdversarialChallenge().review(other, gates, provisional)
    other_gates = evaluate_gates(item)  # same id, different facts
    with pytest.raises(ValueError, match="carry the reviewed gate"):
        AdversarialChallenge().review(item, other_gates, provisional)


def test_challenge_module_source_does_not_import_nominating_rules() -> None:
    source = Path(challenge_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "filesteward.classify.rules" not in imported
    assert not any(
        name.endswith(".rules") for name in imported
    ), f"challenge must stay independent of rules, found: {imported}"
