"""D1 delete-manifest proofs: schema, identity join, untouched, fail-closed."""

from __future__ import annotations

from safe_capacity_fixtures import action_record

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterator

import pytest

from filesteward.deletion import (
    DELETE_MANIFEST_FILENAME,
    DELETE_MANIFEST_SCHEMA,
    build_delete_manifest,
    emit_delete_manifest,
    sha256_file,
)
from filesteward.manifest import (
    SummaryModel,
    validate_run,
    write_cleanup_plan,
    write_human_review,
    write_inventory,
    write_protected_exclusions,
    write_run_metadata,
    write_summary,
)
from filesteward.policy.paths import run_dir as policy_run_dir


def _inventory_row(
    *,
    item_id: str,
    path: str,
    disposition: str,
    entry_type: str = "FILE",
    logical: int | str = 100,
    allocated: int | str = 100,
    protection_relation: str = "UNRELATED",
    scan_completeness: str = "COMPLETE",
    scan_error: str = "",
    modified_at: str = "2026-01-01T00:00:00+00:00",
    link_count: str = "1",
    is_symlink: str = "false",
    is_reparse_point: str = "false",
    is_cloud_placeholder: str = "false",
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "path": path,
        "entry_type": entry_type,
        "disposition": disposition,
        "evidence_state": "DISPOSITION_ASSIGNED",
        "protection_relation": protection_relation,
        "scan_completeness": scan_completeness,
        "scan_error": scan_error,
        "logical_size_bytes": logical,
        "allocated_size_bytes": allocated,
        "modified_at": modified_at,
        "link_count": link_count,
        "is_symlink": is_symlink,
        "is_reparse_point": is_reparse_point,
        "is_cloud_placeholder": is_cloud_placeholder,
    }


def _plan_row(
    *,
    item_id: str,
    path: str,
    logical: int = 100,
    allocated: int = 80,
    projected: int = 80,
    quality: str = "allocated-evidence",
    evidence: str = "explicit regenerable contract",
    confidence: str = "synthetic-contract-1",
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "path": path,
        "logical_size_bytes": logical,
        "allocated_size_bytes": allocated,
        "projected_reclaim_bytes": projected,
        "reclaim_basis": "allocated size under explicit contract",
        "disposition": "RECLAIM_PROVEN",
        "confidence_basis": confidence,
        "evidence": evidence,
        "protection_check": "UNRELATED",
        "recoverability": "regenerable cache",
        "canonical_survivor": "",
        "proposed_action": "quarantine",
        "projection_quality": quality,
    }


def write_synthetic_run(
    run_dir: Path,
    *,
    include_reclaim: bool = True,
    reclaim_path: str = r"C:\SyntheticCache\body.bin",
) -> Path:
    """Write a validate_run-clean synthetic run under an ignored runtime path."""

    run_dir.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, Any]] = [
        _inventory_row(
            item_id="review-1",
            path=r"C:\Synthetic\ambiguous.txt",
            disposition="HUMAN_REVIEW",
            logical=50,
            allocated=50,
        ),
        _inventory_row(
            item_id="unknown-1",
            path=r"C:\Synthetic\restricted",
            disposition="UNKNOWN",
            entry_type="DIRECTORY",
            logical=25,
            allocated="",
            scan_completeness="INCOMPLETE",
            scan_error="access denied",
            link_count="",
            modified_at="",
        ),
        _inventory_row(
            item_id="prot-1",
            path=r"C:\Synthetic\protected-repo",
            disposition="PROTECTED",
            entry_type="DIRECTORY",
            logical=200,
            allocated=200,
            protection_relation="SELF",
        ),
        _inventory_row(
            item_id="keep-1",
            path=r"C:\Synthetic\required.dat",
            disposition="KEEP_PROVEN",
            logical=40,
            allocated=40,
        ),
    ]
    review = [
        {
            "item_id": "review-1",
            "path": r"C:\Synthetic\ambiguous.txt",
            "disposition": "HUMAN_REVIEW",
            "logical_size_bytes": 50,
            "allocated_size_bytes": 50,
            "why_ambiguous": "No explicit regenerable contract",
            "what_operator_should_check": "Confirm provenance",
            "known_context": "entry=FILE",
            "risk_if_acted_on": "May remove personal data",
        },
        {
            "item_id": "unknown-1",
            "path": r"C:\Synthetic\restricted",
            "disposition": "UNKNOWN",
            "logical_size_bytes": 25,
            "allocated_size_bytes": "",
            "why_ambiguous": "Incomplete observation",
            "what_operator_should_check": "Resolve access",
            "known_context": "",
            "risk_if_acted_on": "Unseen children may be removed",
        },
    ]
    exclusions = [
        {
            "item_id": "prot-1",
            "path": r"C:\Synthetic\protected-repo",
            "disposition": "PROTECTED",
            "protection_reason": "git repository root",
            "protection_source": "protection-index",
            "relationship": "SELF",
        }
    ]
    plan: list[dict[str, Any]] = []
    if include_reclaim:
        inventory.append(
            _inventory_row(
                item_id="reclaim-1",
                path=reclaim_path,
                disposition="RECLAIM_PROVEN",
                logical=100,
                allocated=80,
            )
        )
        plan.append(
            _plan_row(
                item_id="reclaim-1",
                path=reclaim_path,
                logical=100,
                allocated=80,
                projected=80,
            )
        )

    (run_dir / "owner-action-plan.json").write_text(json.dumps({
        "schema_version": "filesteward.owner-action-plan/v1",
        "items": [action_record(row["path"], row["item_id"]) for row in plan],
    }), encoding="utf-8")
    write_inventory(run_dir / "inventory.csv", inventory)
    write_human_review(run_dir / "human-review.csv", review)
    write_cleanup_plan(run_dir / "cleanup-plan.csv", plan)
    write_protected_exclusions(run_dir / "protected-exclusions.csv", exclusions)

    counts = {
        "HUMAN_REVIEW": 1,
        "UNKNOWN": 1,
        "PROTECTED": 1,
        "KEEP_PROVEN": 1,
    }
    if include_reclaim:
        counts["RECLAIM_PROVEN"] = 1
    projected_total = 80 if include_reclaim else 0
    write_run_metadata(
        run_dir / "run.json",
        {
            "run_id": "synthetic-d1-delete",
            "authorization_state": "UNAPPROVED",
            "plan_rows": len(plan),
            "cumulative_projected_reclaim_bytes": projected_total,
            "disposition_counts": counts,
            "baseline_free_bytes": 1_000,
            "target_free_bytes": 2_000,
            "stop_row": None,
            "logical_bytes_observed": 415 if include_reclaim else 315,
            "managed_paths": [],
        },
    )
    write_summary(
        run_dir / "cleanup-summary.md",
        SummaryModel(
            run_id="synthetic-d1-delete",
            root=r"C:\Synthetic",
            run_dir=str(run_dir),
            inventory_items=len(inventory),
            logical_bytes_observed=415 if include_reclaim else 315,
            logical_unknown_items=0,
            allocated_known_bytes=370 if include_reclaim else 290,
            allocated_known_items=len(inventory) - 1,
            allocation_note="synthetic",
            disposition_counts=counts,
            plan_rows=len(plan),
            projected_reclaim_total=projected_total,
            projected_allocated_bytes=projected_total,
            projected_estimate_bytes=0,
            container_rows=0,
            baseline_free_bytes=1_000,
            target_free_bytes=2_000,
            cumulative_projected_reclaim_bytes=projected_total,
            stop_row=None,
            stop_note="target not reached",
            human_review_count=1,
            human_review_bytes=50,
            human_review_unknown_size=0,
            protected_count=1,
            protected_breakdown={"SELF": 1, "DESCENDANT": 0, "ANCESTOR": 0},
            unknown_count=1,
            unknown_bytes=25,
            keep_count=1,
        ),
    )
    errors = validate_run(run_dir)
    assert not errors, errors
    return run_dir


@pytest.fixture
def d1_run_dir() -> Iterator[Path]:
    path = policy_run_dir(f"test-d1-{uuid.uuid4().hex[:10]}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_sha256_cleanup_plan_and_reclaim_list(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    plan_path = d1_run_dir / "cleanup-plan.csv"
    expected = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert sha256_file(plan_path) == expected

    manifest = build_delete_manifest(d1_run_dir)
    assert manifest["schema_version"] == DELETE_MANIFEST_SCHEMA
    assert manifest["source_cleanup_plan_sha256"] == expected
    assert manifest["item_count"] == 1
    assert [item["item_id"] for item in manifest["items"]] == ["reclaim-1"]
    assert all(item["disposition"] == "RECLAIM_PROVEN" for item in manifest["items"])


def test_full_schema_identity_join_and_untouched(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    result = emit_delete_manifest(d1_run_dir)
    manifest = result.manifest

    assert result.manifest_path == d1_run_dir / DELETE_MANIFEST_FILENAME
    assert result.html_path.is_file()
    assert result.text_path.is_file()
    assert manifest["authorization_state"] == "UNAPPROVED"
    assert manifest["intended_action"] == "QUARANTINE"
    assert manifest["item_count"] == 1
    assert manifest["totals"]["logical_size_bytes"] == 100
    assert manifest["totals"]["allocated_size_bytes"] == 80
    assert manifest["totals"]["projected_reclaim_bytes"] == 80
    assert manifest["totals"]["projection_quality"] == "allocated-evidence"
    assert manifest["untouched"] == {
        "human_review_count": 1,
        "protected_count": 1,
        "unknown_count": 1,
        "keep_proven_count": 1,
        "note": (
            "HUMAN_REVIEW, UNKNOWN, PROTECTED, and KEEP_PROVEN rows are "
            "excluded from this delete set."
        ),
    }

    item = manifest["items"][0]
    assert item["item_type"] == "FILE"
    assert item["contract_source"] == "synthetic-contract-1"
    assert item["intended_action"] == "QUARANTINE"
    assert item["reversibility"] == "REVERSIBLE_QUARANTINE"
    assert item["is_symlink"] is False
    assert item["is_reparse_point"] is False
    assert item["is_cloud_placeholder"] is False
    assert item["is_managed"] is False
    assert item["link_count"] == 1
    assert item["identity"]["path"] == item["path"]
    assert item["identity"]["item_type"] == "FILE"
    assert item["source_run_id"] == "synthetic-d1-delete"
    assert item["source_cleanup_plan_sha256"] == manifest["source_cleanup_plan_sha256"]

    disk = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert disk["schema_version"] == DELETE_MANIFEST_SCHEMA
    assert disk["item_count"] == 1


def test_empty_plan_produces_empty_set_with_untouched(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir, include_reclaim=False)
    manifest = build_delete_manifest(d1_run_dir)
    assert manifest["item_count"] == 0
    assert manifest["items"] == []
    assert manifest["totals"]["logical_size_bytes"] == 0
    assert manifest["totals"]["projected_reclaim_bytes"] == 0
    assert manifest["totals"]["projection_quality"] == "unknown"
    assert manifest["untouched"]["human_review_count"] == 1
    assert manifest["untouched"]["protected_count"] == 1
    assert manifest["untouched"]["unknown_count"] == 1
    assert manifest["untouched"]["keep_proven_count"] == 1


def test_non_reclaim_proven_rejected(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    # Bypass writers: inject a non-RECLAIM disposition into the plan CSV.
    plan_path = d1_run_dir / "cleanup-plan.csv"
    text = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(
        text.replace("RECLAIM_PROVEN", "HUMAN_REVIEW", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not RECLAIM_PROVEN"):
        build_delete_manifest(d1_run_dir)


def test_missing_inventory_row_fail_closed(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    inventory_path = d1_run_dir / "inventory.csv"
    rows = inventory_path.read_text(encoding="utf-8").splitlines()
    # Drop the reclaim inventory row while leaving the plan row intact.
    kept = [rows[0]] + [line for line in rows[1:] if "reclaim-1" not in line]
    inventory_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing from inventory"):
        build_delete_manifest(d1_run_dir)


def test_identity_drift_fail_closed(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    plan_path = d1_run_dir / "cleanup-plan.csv"
    text = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(
        text.replace(r"C:\SyntheticCache\body.bin", r"C:\SyntheticCache\drift.bin", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot be bound"):
        build_delete_manifest(d1_run_dir)


def test_emit_does_not_mutate_source_artifacts(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    protected = (
        "cleanup-plan.csv",
        "human-review.csv",
        "protected-exclusions.csv",
        "inventory.csv",
        "cleanup-summary.md",
        "run.json",
    )
    before = {name: (d1_run_dir / name).read_bytes() for name in protected}
    emit_delete_manifest(d1_run_dir)
    after = {name: (d1_run_dir / name).read_bytes() for name in protected}
    assert before == after


def test_emit_refuses_invalid_run(d1_run_dir: Path) -> None:
    write_synthetic_run(d1_run_dir)
    (d1_run_dir / "cleanup-summary.md").unlink()
    with pytest.raises(ValueError, match="validation"):
        emit_delete_manifest(d1_run_dir)
