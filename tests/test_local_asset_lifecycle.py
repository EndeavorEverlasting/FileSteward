"""Read-only local asset lifecycle: never infer disposable from lack of owner."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from filesteward.models import CleanupDisposition
from filesteward.ownership.local import (
    Attribution,
    Intent,
    LocalAssetEvidence,
    LocalIdentity,
    LocalLifecycle,
    LocalRoute,
    SCHEMA_VERSION,
    classify_local_asset,
    example_evidence,
    parse_local_evidence,
)


def proven_local(**overrides: object) -> LocalAssetEvidence:
    base = {
        "path": r"F:\synthetic\misc\folder",
        "identity": LocalIdentity.OTHER_LOCAL,
        "attribution": Attribution.VERIFIED_USER_LOCAL,
        "adapters_complete": True,
        "active_use": False,
        "unique_unbacked_work": False,
        "dependencies_resolved": True,
        "recoverable": True,
        "evidence_sources": ("synthetic:adapter-proof",),
    }
    base.update(overrides)
    return LocalAssetEvidence(**base)


def test_unclassified_unattributed_is_not_legacy_or_delete_target() -> None:
    evidence = LocalAssetEvidence(path=r"C:\synthetic\misc\thing")
    result = classify_local_asset(evidence)
    assert result.identity is LocalIdentity.UNCLASSIFIED
    assert result.lifecycle is LocalLifecycle.UNRESOLVED
    assert result.disposition is CleanupDisposition.UNKNOWN
    assert result.route is LocalRoute.RESOLVE_ATTRIBUTION
    assert result.mutation_authorized is False
    assert result.removal_candidate_review_only is False


@pytest.mark.parametrize(
    ("change", "expected_reason"),
    [
        ({"protected_by_policy": True}, "EXPLICIT_OR_STRUCTURAL_PROTECTION"),
        ({"active_use": True}, "POSITIVE_ACTIVE_USE"),
        ({"unique_unbacked_work": True}, "UNBACKED_UNIQUE_WORK"),
        ({"attribution": Attribution.OTHER_OWNER_PRESENT}, "NONLOCAL_OR_CONFLICTING_OWNER"),
        ({"attribution": Attribution.CONFLICTING}, "NONLOCAL_OR_CONFLICTING_OWNER"),
    ],
)
def test_protection_dominates_declared_deletion_review(
    change: dict, expected_reason: str,
) -> None:
    result = classify_local_asset(
        proven_local(intent=Intent.REMOVE_REVIEW, **change)
    )
    assert result.disposition is CleanupDisposition.PROTECTED
    assert expected_reason in result.reasons
    assert not result.removal_candidate_review_only


def test_operator_keep_is_preserved_even_when_owner_not_yet_found() -> None:
    result = classify_local_asset(
        LocalAssetEvidence(path="/synthetic/records", intent=Intent.KEEP)
    )
    assert result.disposition is CleanupDisposition.KEEP_PROVEN
    assert result.route is LocalRoute.KEEP


def test_explicit_dormant_does_not_require_deletion_or_recovery() -> None:
    result = classify_local_asset(
        proven_local(intent=Intent.DORMANT, recoverable=None)
    )
    assert result.lifecycle is LocalLifecycle.DORMANT
    assert result.disposition is CleanupDisposition.KEEP_PROVEN
    assert not result.removal_candidate_review_only


def test_inactivity_alone_stays_stable_without_legacy_intent() -> None:
    result = classify_local_asset(proven_local())
    assert result.lifecycle is LocalLifecycle.STABLE
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.route is LocalRoute.REVIEW_RETENTION


def test_explicit_legacy_requires_safe_recovery_and_no_dependents() -> None:
    result = classify_local_asset(proven_local(intent=Intent.LEGACY_REVIEW))
    assert result.lifecycle is LocalLifecycle.LEGACY_CANDIDATE
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.route is LocalRoute.REVIEW_ARCHIVE
    assert not result.removal_candidate_review_only


def test_explicit_remove_is_review_target_never_delete_set() -> None:
    result = classify_local_asset(proven_local(intent=Intent.REMOVE_REVIEW))
    assert result.lifecycle is LocalLifecycle.STABLE
    assert result.disposition is CleanupDisposition.HUMAN_REVIEW
    assert result.route is LocalRoute.REVIEW_REMOVAL
    assert result.removal_candidate_review_only is True
    assert result.mutation_authorized is False
    serialized = result.to_dict()
    assert serialized["mutation_authorized"] is False
    assert serialized["disposition"] != "RECLAIM_PROVEN"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"recoverable": None}, LocalRoute.RESOLVE_RECOVERABILITY),
        ({"recoverable": False}, LocalRoute.RESOLVE_RECOVERABILITY),
        ({"dependencies_resolved": None}, LocalRoute.RESOLVE_DEPENDENCIES),
        ({"dependencies_resolved": False}, LocalRoute.RESOLVE_DEPENDENCIES),
        ({"unique_unbacked_work": None}, LocalRoute.RESOLVE_UNIQUE_WORK),
        ({"active_use": None}, LocalRoute.REVIEW_RETENTION),
        ({"adapters_complete": False}, LocalRoute.RESOLVE_ATTRIBUTION),
        ({"attribution": Attribution.UNRESOLVED}, LocalRoute.RESOLVE_ATTRIBUTION),
    ],
)
def test_no_unproven_legacy_or_removal_promotion(change: dict, expected: LocalRoute) -> None:
    for intent in (Intent.LEGACY_REVIEW, Intent.REMOVE_REVIEW):
        result = classify_local_asset(proven_local(intent=intent, **change))
        assert result.route is expected
        assert result.lifecycle is not LocalLifecycle.LEGACY_CANDIDATE
        assert not result.removal_candidate_review_only
        assert result.disposition is not CleanupDisposition.RECLAIM_PROVEN


@pytest.mark.parametrize(
    "identity",
    [LocalIdentity.GENERATED, LocalIdentity.PERSONAL_RECORD, LocalIdentity.LEARNING,
     LocalIdentity.OTHER_LOCAL, LocalIdentity.UNCLASSIFIED],
)
def test_identity_is_not_deletion_or_regeneration_evidence(identity: LocalIdentity) -> None:
    unknown = classify_local_asset(LocalAssetEvidence(
        path=r"E:\synthetic\whatever", identity=identity,
        intent=Intent.REMOVE_REVIEW,
    ))
    assert unknown.disposition is CleanupDisposition.UNKNOWN
    assert not unknown.removal_candidate_review_only


def test_all_classifications_are_non_destructive() -> None:
    for intent in Intent:
        for identity in LocalIdentity:
            result = classify_local_asset(proven_local(intent=intent, identity=identity))
            assert result.disposition is not CleanupDisposition.RECLAIM_PROVEN
            assert result.mutation_authorized is False


def test_input_parser_rejects_unknown_fields_and_coercion() -> None:
    raw = example_evidence()
    assert parse_local_evidence(raw).intent is Intent.LEGACY_REVIEW
    with pytest.raises(ValueError, match="unknown evidence fields"):
        parse_local_evidence({**raw, "authorize_delete": True})
    with pytest.raises(ValueError, match="active_use"):
        parse_local_evidence({**raw, "active_use": "false"})
    with pytest.raises(ValueError, match="schema_version"):
        parse_local_evidence({**raw, "schema_version": "other"})
    with pytest.raises(ValueError, match="invalid intent"):
        parse_local_evidence({**raw, "intent": "DELETE_NOW"})


def test_verified_local_requires_provenance_and_absolute_path() -> None:
    with pytest.raises(ValueError, match="evidence_sources"):
        proven_local(evidence_sources=())
    with pytest.raises(ValueError, match="absolute"):
        proven_local(path="relative/local")
    with pytest.raises(ValueError, match="traversal"):
        proven_local(path=r"C:\synthetic\..\secret")


def test_revision_is_reproducible_and_tracks_evidence_changes() -> None:
    base = proven_local(intent=Intent.KEEP)
    first = classify_local_asset(base)
    assert first.evidence_revision == classify_local_asset(base).evidence_revision
    other = classify_local_asset(replace(base, intent=Intent.ARCHIVE_REVIEW))
    assert first.evidence_revision != other.evidence_revision


def test_cli_emits_machine_json_and_does_not_write_scanned_folder(tmp_path: Path) -> None:
    # The fixture is input-only and no scan of the candidate path occurs.
    raw = example_evidence()
    raw["path"] = str(tmp_path / "not-an-existing-directory")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(raw), encoding="utf-8")
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    result = subprocess.run(
        [sys.executable, "-m", "filesteward.ownership.local",
         "--evidence-file", str(evidence)],
        capture_output=True, text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assessment = json.loads(result.stdout)
    assert assessment["lifecycle"] == "LEGACY_CANDIDATE"
    assert assessment["disposition"] == "HUMAN_REVIEW"
    assert assessment["mutation_authorized"] is False
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


def test_invalid_evidence_cli_returns_failure(tmp_path: Path) -> None:
    payload = tmp_path / "invalid.json"
    payload.write_text('{"schema_version":"wrong","path":"C:\\\\x"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "filesteward.ownership.local",
         "--evidence-file", str(payload)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "schema_version" in result.stderr


def test_synthetic_example_is_not_local_runtime_claim() -> None:
    sample = example_evidence()
    assert sample["schema_version"] == SCHEMA_VERSION
    assert "synthetic" in sample["path"].lower()
    assert classify_local_asset(parse_local_evidence(sample)).mutation_authorized is False


def test_cursor_agent_routing_is_linked_to_canonical_skill() -> None:
    """The agent activation seam cannot silently lose its owning skill."""

    root = Path(__file__).resolve().parents[1]
    cursor_rule = (root / ".cursor" / "rules" /
                   "local-asset-lifecycle.mdc").read_text(encoding="utf-8")
    skill = (root / ".agents" / "skills" /
             "local-asset-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert ".agents/skills/local-asset-lifecycle/SKILL.md" in cursor_rule
    assert "src/filesteward/ownership/local.py" in cursor_rule
    assert "src/filesteward/ownership/local.py" in skill
    assert "docs/handoff/LOCAL-ASSET-LIFECYCLE-2026-10-24.md" in agents
