"""L0 proof: domain models are deterministic, separated, and fail closed."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum

import pytest

from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    EntryType,
    EvidenceState,
    InventoryItem,
    ScanCompleteness,
    authorization_allows_mutation,
)


class TestEnumDeterminism:
    """Exact value sets: an accidental enum edit must fail loudly."""

    def test_evidence_state_values(self) -> None:
        assert [e.value for e in EvidenceState] == [
            "DISCOVERED",
            "EVALUATED",
            "DISPOSITION_ASSIGNED",
        ]

    def test_cleanup_disposition_values(self) -> None:
        assert [e.value for e in CleanupDisposition] == [
            "RECLAIM_PROVEN",
            "HUMAN_REVIEW",
            "PROTECTED",
            "KEEP_PROVEN",
            "UNKNOWN",
        ]

    def test_authorization_state_values(self) -> None:
        assert [e.value for e in AuthorizationState] == [
            "UNAPPROVED",
            "APPROVED_FOR_ACTION",
            "APPLIED",
            "VERIFIED",
        ]

    def test_entry_type_values(self) -> None:
        assert [e.value for e in EntryType] == [
            "FILE",
            "DIRECTORY",
            "SYMLINK",
            "REPARSE_POINT",
            "OTHER",
        ]

    @pytest.mark.parametrize(
        "enum_cls",
        [EvidenceState, CleanupDisposition, AuthorizationState, EntryType, ScanCompleteness],
    )
    def test_enums_are_str_enums_roundtripping_by_value(
        self, enum_cls: type[Enum]
    ) -> None:
        for member in enum_cls:  # type: ignore[arg-type]
            assert enum_cls(member.value) is member
            assert isinstance(member.value, str)


class TestAuthorizationSeparation:
    """Evidence must never become mutation authority."""

    @pytest.mark.parametrize(
        "state,expected",
        [
            (AuthorizationState.UNAPPROVED, False),
            (AuthorizationState.APPROVED_FOR_ACTION, True),
            (AuthorizationState.APPLIED, False),
            (AuthorizationState.VERIFIED, False),
        ],
    )
    def test_only_explicit_approval_allows_mutation(
        self, state: AuthorizationState, expected: bool
    ) -> None:
        assert authorization_allows_mutation(state) is expected

    @pytest.mark.parametrize(
        "disposition",
        list(CleanupDisposition),
        ids=[d.value for d in CleanupDisposition],
    )
    def test_no_disposition_is_mutation_authority(
        self, disposition: CleanupDisposition
    ) -> None:
        with pytest.raises(TypeError):
            authorization_allows_mutation(disposition)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "evidence_state", list(EvidenceState), ids=[e.value for e in EvidenceState]
    )
    def test_no_evidence_state_is_mutation_authority(
        self, evidence_state: EvidenceState
    ) -> None:
        with pytest.raises(TypeError):
            authorization_allows_mutation(evidence_state)  # type: ignore[arg-type]

    def test_reclaim_proven_carries_no_approval(self) -> None:
        assert CleanupDisposition.RECLAIM_PROVEN is not AuthorizationState.APPROVED_FOR_ACTION
        assert (
            CleanupDisposition.RECLAIM_PROVEN.value
            not in {s.value for s in AuthorizationState}
        )


class TestInventoryItem:
    def _item(self, **overrides: object) -> InventoryItem:
        payload: dict = {
            "item_id": "abc123",
            "path": "C:/synthetic/root/file.txt",
            "entry_type": EntryType.FILE,
            "logical_size_bytes": 10,
        }
        payload.update(overrides)
        return InventoryItem(**payload)

    def test_defaults_are_fail_closed_evidence(self) -> None:
        item = self._item()
        assert item.evidence_state is EvidenceState.DISCOVERED
        assert item.scan_completeness is ScanCompleteness.COMPLETE
        assert item.allocated_size_bytes is None
        assert item.projected_reclaim_bytes is None

    def test_is_frozen(self) -> None:
        item = self._item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.path = "other"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "overrides",
        [
            {"item_id": ""},
            {"path": ""},
            {"logical_size_bytes": -1},
            {"allocated_size_bytes": -1},
            {"link_count": -1},
            {"projected_reclaim_bytes": -1},
            {"scan_completeness": ScanCompleteness.INCOMPLETE},
            {
                "scan_completeness": ScanCompleteness.COMPLETE,
                "scan_error": "access denied",
            },
        ],
        ids=[
            "empty-id",
            "empty-path",
            "negative-logical",
            "negative-allocated",
            "negative-link-count",
            "negative-projected",
            "incomplete-without-error",
            "complete-with-error",
        ],
    )
    def test_invalid_values_rejected(self, overrides: dict) -> None:
        with pytest.raises(ValueError):
            self._item(**overrides)

    def test_incomplete_with_error_accepted(self) -> None:
        item = self._item(
            scan_completeness=ScanCompleteness.INCOMPLETE,
            scan_error="access denied",
        )
        assert item.scan_completeness is ScanCompleteness.INCOMPLETE
        assert item.scan_error == "access denied"

    def test_unknown_sizes_stay_none_not_zero(self) -> None:
        item = self._item(logical_size_bytes=None)
        assert item.logical_size_bytes is None
        assert item.logical_size_bytes != 0

    @pytest.mark.parametrize("enum_cls", [EvidenceState, CleanupDisposition, AuthorizationState])
    def test_enums_are_shared_leaf_contract(self, enum_cls: type[Enum]) -> None:
        @dataclass(frozen=True)
        class Holder:
            kind: Enum

        for member in enum_cls:  # type: ignore[arg-type]
            assert Holder(member).kind is member
