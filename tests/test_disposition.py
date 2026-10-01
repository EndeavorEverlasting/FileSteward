"""L2 proof: deterministic disposition rules and fail-closed gates.

Scenario coverage: S3 (large semantic ambiguity -> HUMAN_REVIEW, no
delete score), S4 (contract-backed cache nomination), S6 (mixed
directory decomposition), protection conflict fail-closed, and the
no age/size/name/location-only reclaim rule.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from filesteward.classify import (
    CacheContract,
    GateResults,
    ProvisionalDisposition,
    evaluate_gates,
    match_contract,
    nominate,
    resolve_directory_disposition,
)
from filesteward.models import (
    CleanupDisposition,
    EntryType,
    InventoryItem,
    ScanCompleteness,
)
from filesteward.protect.index import ProtectionRelation

CACHE_PREFIX = "C:/synthetic/AppData/Local/pip/cache"

CACHE_CONTRACT = CacheContract(
    contract_id="synthetic.pip-cache",
    path_prefix=CACHE_PREFIX,
    description="synthetic deterministic pip cache artifact",
)

BROAD_CONTRACT = CacheContract(
    contract_id="synthetic.loose-keep",
    path_prefix="C:/synthetic",
    description="synthetic retained content",
    regenerable=False,
)


def make_item(**overrides: object) -> InventoryItem:
    base: dict = {
        "item_id": "item-1",
        "path": f"{CACHE_PREFIX}/http/hash/body.whl",
        "entry_type": EntryType.FILE,
        "logical_size_bytes": 1_048_576,
        "allocated_size_bytes": 1_048_576,
        "link_count": 1,
    }
    base.update(overrides)
    return InventoryItem(**base)  # type: ignore[arg-type]


def gates_for(item: InventoryItem, **kwargs: object) -> GateResults:
    return evaluate_gates(item, **kwargs)  # type: ignore[arg-type]


# --- S3: large semantic ambiguity -------------------------------------

def test_s3_large_archive_without_contract_is_human_review() -> None:
    archive = make_item(
        path="C:/synthetic/Downloads/old-backup.tar",
        logical_size_bytes=4_800_000_000,
        allocated_size_bytes=4_800_000_000,
        modified_at=1_000_000.0,
    )
    disposition = nominate(gates_for(archive))
    assert disposition.disposition is CleanupDisposition.HUMAN_REVIEW
    assert disposition.basis == "no explicit contract evidence"


def test_s3_basis_carries_no_score_or_probably_safe_language() -> None:
    archive = make_item(
        path="C:/synthetic/Downloads/old-backup.tar",
        logical_size_bytes=4_800_000_000,
    )
    basis = nominate(gates_for(archive)).basis.lower()
    for forbidden in ("score", "probably", "likely", "safe", "confidence"):
        assert forbidden not in basis
    for field in fields(ProvisionalDisposition):
        for token in ("score", "confidence", "weight", "persuasion"):
            assert token not in field.name.lower()


def test_s3_unknown_size_is_equally_unproven() -> None:
    unknown = make_item(path="C:/synthetic/Downloads/thing.bin", logical_size_bytes=None)
    assert nominate(gates_for(unknown)).disposition is CleanupDisposition.HUMAN_REVIEW


# --- no age/size/name/location-only reclaim rule -----------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"logical_size_bytes": 0, "allocated_size_bytes": 0},
        {"logical_size_bytes": 4_800_000_000},
        {"path": "C:/synthetic/Windows/Temp/important.docx"},
        {"path": "D:/other-root/tiny.tmp", "logical_size_bytes": 1},
        {"modified_at": 0.0},
        {"modified_at": 4_102_444_800.0},
    ],
    ids=["zero-size", "huge-size", "other-name", "other-location", "ancient", "fresh"],
)
def test_no_age_size_name_location_only_reclaim_rule(overrides: dict) -> None:
    item = make_item(**overrides)
    result = nominate(gates_for(item))
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.basis == "no explicit contract evidence"


def test_observed_attributes_do_not_change_a_contract_decision() -> None:
    small = make_item(logical_size_bytes=1)
    large = make_item(path=f"{CACHE_PREFIX}/other-body.whl", logical_size_bytes=4_800_000_000)
    small_result = nominate(gates_for(small, contracts=(CACHE_CONTRACT,)))
    large_result = nominate(gates_for(large, contracts=(CACHE_CONTRACT,)))
    assert small_result.disposition is large_result.disposition
    assert small_result.disposition is CleanupDisposition.RECLAIM_PROVEN


# --- S4: contract-backed nomination -----------------------------------

def test_s4_contract_evidence_nominates_reclaim_proven() -> None:
    artifact = make_item()
    result = nominate(gates_for(artifact, contracts=(CACHE_CONTRACT,)))
    assert result.disposition is CleanupDisposition.RECLAIM_PROVEN
    assert CACHE_CONTRACT.contract_id in result.basis


def test_s4_provisional_rejects_unprotected_invariant_violations() -> None:
    artifact = make_item()
    good = gates_for(artifact, contracts=(CACHE_CONTRACT,))
    with pytest.raises(ValueError, match="unrelated"):
        ProvisionalDisposition(
            item_id=artifact.item_id,
            disposition=CleanupDisposition.RECLAIM_PROVEN,
            basis="attempted bypass",
            gates=gates_for(
                artifact,
                protection=ProtectionRelation.DESCENDANT,
                contracts=(CACHE_CONTRACT,),
            ),
        )
    with pytest.raises(ValueError, match="complete contract-backed"):
        ProvisionalDisposition(
            item_id=artifact.item_id,
            disposition=CleanupDisposition.RECLAIM_PROVEN,
            basis="attempted bypass",
            gates=gates_for(artifact),
        )
    assert good.passes_content_gates()


def test_provisional_rejects_empty_basis_and_mismatched_ids() -> None:
    artifact = make_item()
    gates = gates_for(artifact, contracts=(CACHE_CONTRACT,))
    with pytest.raises(ValueError, match="basis"):
        ProvisionalDisposition(
            item_id=artifact.item_id,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis="",
            gates=gates,
        )
    with pytest.raises(ValueError, match="item_id"):
        ProvisionalDisposition(
            item_id="other-item",
            disposition=CleanupDisposition.HUMAN_REVIEW,
            basis="mismatch",
            gates=gates,
        )


def test_undocumented_evidence_without_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="contract_id"):
        GateResults(
            item_id="item-1",
            protection=ProtectionRelation.UNRELATED,
            observation_complete=True,
            contract_id=None,
            provenance_documented=True,
            recoverability_documented=True,
            regenerable=True,
        )


def test_gate_results_are_frozen_and_deterministic() -> None:
    artifact = make_item()
    first = gates_for(artifact, contracts=(CACHE_CONTRACT,))
    second = gates_for(artifact, contracts=(CACHE_CONTRACT,))
    assert first == second
    with pytest.raises(Exception):
        first.observation_complete = False  # type: ignore[misc]


def test_s4_not_regenerable_contract_keeps_content() -> None:
    result = nominate(gates_for(make_item(), contracts=(BROAD_CONTRACT,)))
    assert result.disposition is CleanupDisposition.KEEP_PROVEN


def test_incomplete_scan_is_unknown_even_with_contract() -> None:
    broken = make_item(
        scan_completeness=ScanCompleteness.INCOMPLETE,
        scan_error="synthetic access denied",
    )
    result = nominate(gates_for(broken, contracts=(CACHE_CONTRACT,)))
    assert result.disposition is CleanupDisposition.UNKNOWN


def test_incomplete_descendants_are_unknown_even_with_contract() -> None:
    result = nominate(
        gates_for(
            make_item(entry_type=EntryType.DIRECTORY),
            contracts=(CACHE_CONTRACT,),
            descendant_complete=False,
        )
    )
    assert result.disposition is CleanupDisposition.UNKNOWN


# --- protection conflict fail-closed ----------------------------------

@pytest.mark.parametrize(
    "relation",
    [ProtectionRelation.SELF, ProtectionRelation.DESCENDANT],
    ids=["self", "descendant"],
)
def test_protection_beats_full_contract_evidence(relation: ProtectionRelation) -> None:
    result = nominate(
        gates_for(
            make_item(),
            protection=relation,
            contracts=(CACHE_CONTRACT,),
        )
    )
    assert result.disposition is CleanupDisposition.PROTECTED
    assert relation.value in result.basis


def test_protected_ancestor_decomposes_instead_of_reclaiming() -> None:
    directory = make_item(
        entry_type=EntryType.DIRECTORY,
        path="C:/synthetic/repos",
    )
    result = nominate(
        gates_for(
            directory,
            protection=ProtectionRelation.ANCESTOR,
            contracts=(BROAD_CONTRACT,),
        )
    )
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert "decompose" in result.basis


# --- contract matching -------------------------------------------------

def test_contract_prefix_requires_component_boundary() -> None:
    near_miss = make_item(path="C:/synthetic/AppData/Local/pip/cache2/file.bin")
    assert match_contract(near_miss, (CACHE_CONTRACT,)) is None
    exact = make_item(path=CACHE_PREFIX)
    assert match_contract(exact, (CACHE_CONTRACT,)) is CACHE_CONTRACT


def test_contract_matching_is_separator_and_case_insensitive() -> None:
    windows_style = make_item(
        path="C:\\synthetic\\AppData\\Local\\pip\\cache\\file.bin"
    )
    assert match_contract(windows_style, (CACHE_CONTRACT,)) is CACHE_CONTRACT
    upper_prefix = CacheContract(
        contract_id="upper",
        path_prefix=CACHE_PREFIX.upper(),
        description="uppercase synthetic prefix",
    )
    assert match_contract(make_item(), (upper_prefix,)) is upper_prefix


def test_contract_requires_id_prefix_and_description() -> None:
    with pytest.raises(ValueError, match="contract_id"):
        CacheContract(contract_id="", path_prefix="C:/x", description="d")
    with pytest.raises(ValueError, match="path_prefix"):
        CacheContract(contract_id="c", path_prefix="  ", description="d")
    with pytest.raises(ValueError, match="description"):
        CacheContract(contract_id="c", path_prefix="C:/x", description="")


# --- S6: mixed directory ----------------------------------------------

@pytest.mark.parametrize(
    ("children", "expected", "basis_fragment"),
    [
        ([], CleanupDisposition.HUMAN_REVIEW, "unproven"),
        (
            [CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.RECLAIM_PROVEN],
            CleanupDisposition.RECLAIM_PROVEN,
            "all descendants",
        ),
        (
            [CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.HUMAN_REVIEW],
            CleanupDisposition.HUMAN_REVIEW,
            "decompose",
        ),
        (
            [CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.UNKNOWN],
            CleanupDisposition.UNKNOWN,
            "incomplete",
        ),
        (
            [CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.PROTECTED],
            CleanupDisposition.PROTECTED,
            "protected",
        ),
        (
            [CleanupDisposition.RECLAIM_PROVEN, CleanupDisposition.KEEP_PROVEN],
            CleanupDisposition.KEEP_PROVEN,
            "retained",
        ),
        (
            [CleanupDisposition.HUMAN_REVIEW, CleanupDisposition.PROTECTED],
            CleanupDisposition.PROTECTED,
            "protected",
        ),
    ],
    ids=[
        "empty",
        "all-reclaim",
        "mixed-reclaim-ambiguous",
        "mixed-reclaim-unknown",
        "mixed-reclaim-protected",
        "mixed-reclaim-keep",
        "protected-beats-ambiguous",
    ],
)
def test_s6_directory_composition(
    children: list[CleanupDisposition],
    expected: CleanupDisposition,
    basis_fragment: str,
) -> None:
    disposition, basis = resolve_directory_disposition(children)
    assert disposition is expected
    assert basis_fragment in basis


def test_directory_composition_rejects_non_dispositions() -> None:
    with pytest.raises(TypeError):
        resolve_directory_disposition(["RECLAIM_PROVEN"])  # type: ignore[list-item]
