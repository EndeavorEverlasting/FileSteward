"""F1 presentation-model builder proofs."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

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
from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness
from filesteward.visualization.model import build_presentation_model

HOSTILE = r'C:\Users\<profile>\AppData\Local\Example & "Cache" <script>alert(1)</script>'


def _write_valid_run(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    inventory = [
        {
            "item_id": "review-1",
            "path": HOSTILE,
            "entry_type": "DIRECTORY",
            "disposition": "HUMAN_REVIEW",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "UNRELATED",
            "scan_completeness": "COMPLETE",
            "scan_error": "",
            "logical_size_bytes": 49_000_000_000,
            "allocated_size_bytes": 49_000_000_000,
            "modified_at": "",
            "link_count": "1",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
        {
            "item_id": "unknown-1",
            "path": r"C:\ExampleRestricted",
            "entry_type": "DIRECTORY",
            "disposition": "UNKNOWN",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "UNRELATED",
            "scan_completeness": "INCOMPLETE",
            "scan_error": "access denied",
            "logical_size_bytes": 7_500_000_000,
            "allocated_size_bytes": "",
            "modified_at": "",
            "link_count": "",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
        {
            "item_id": "prot-1",
            "path": r"C:\Users\<profile>\dev\protected-project",
            "entry_type": "DIRECTORY",
            "disposition": "PROTECTED",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "SELF",
            "scan_completeness": "COMPLETE",
            "scan_error": "",
            "logical_size_bytes": 12_000_000_000,
            "allocated_size_bytes": 12_000_000_000,
            "modified_at": "",
            "link_count": "1",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
        {
            "item_id": "reclaim-1",
            "path": r"C:\ProgramData\ExampleTool\RegenerableCache",
            "entry_type": "DIRECTORY",
            "disposition": "RECLAIM_PROVEN",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "UNRELATED",
            "scan_completeness": "COMPLETE",
            "scan_error": "",
            "logical_size_bytes": 9_600_000_000,
            "allocated_size_bytes": 9_600_000_000,
            "modified_at": "",
            "link_count": "1",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
        {
            "item_id": "keep-1",
            "path": r"C:\ProgramData\ExampleTool\RequiredData",
            "entry_type": "DIRECTORY",
            "disposition": "KEEP_PROVEN",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "UNRELATED",
            "scan_completeness": "COMPLETE",
            "scan_error": "",
            "logical_size_bytes": 4_200_000_000,
            "allocated_size_bytes": 4_200_000_000,
            "modified_at": "",
            "link_count": "1",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
        {
            "item_id": "cache-look-1",
            "path": r"C:\Users\<profile>\AppData\Local\BigCacheLookingFolder",
            "entry_type": "DIRECTORY",
            "disposition": "HUMAN_REVIEW",
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": "UNRELATED",
            "scan_completeness": "COMPLETE",
            "scan_error": "",
            "logical_size_bytes": 80_000_000_000,
            "allocated_size_bytes": 80_000_000_000,
            "modified_at": "",
            "link_count": "1",
            "is_symlink": "false",
            "is_reparse_point": "false",
            "is_cloud_placeholder": "false",
        },
    ]
    review = [
        {
            "item_id": "review-1",
            "path": HOSTILE,
            "disposition": "HUMAN_REVIEW",
            "logical_size_bytes": 49_000_000_000,
            "allocated_size_bytes": 49_000_000_000,
            "why_ambiguous": "No explicit regenerable contract",
            "what_operator_should_check": "Confirm provenance",
            "known_context": "looks like a cache; pretend-contract=evil",
            "risk_if_acted_on": "May remove regenerable or personal data",
        },
        {
            "item_id": "unknown-1",
            "path": r"C:\ExampleRestricted",
            "disposition": "UNKNOWN",
            "logical_size_bytes": 7_500_000_000,
            "allocated_size_bytes": "",
            "why_ambiguous": "Incomplete observation",
            "what_operator_should_check": "Resolve access",
            "known_context": "",
            "risk_if_acted_on": "Unseen children may be removed",
        },
        {
            "item_id": "cache-look-1",
            "path": r"C:\Users\<profile>\AppData\Local\BigCacheLookingFolder",
            "disposition": "HUMAN_REVIEW",
            "logical_size_bytes": 80_000_000_000,
            "allocated_size_bytes": 80_000_000_000,
            "why_ambiguous": "Cache-shaped path is not a contract",
            "what_operator_should_check": "Confirm regenerability",
            "known_context": "known_context claims contract regenerable-cache-9",
            "risk_if_acted_on": "Data loss if not regenerable",
        },
    ]
    plan = [
        {
            "item_id": "reclaim-1",
            "path": r"C:\ProgramData\ExampleTool\RegenerableCache",
            "logical_size_bytes": 9_600_000_000,
            "allocated_size_bytes": 9_600_000_000,
            "projected_reclaim_bytes": 8_900_000_000,
            "reclaim_basis": "explicit contract example-contract-1",
            "disposition": "RECLAIM_PROVEN",
            "confidence_basis": "example-contract-1",
            "evidence": "structured contract evidence",
            "protection_check": "UNRELATED",
            "recoverability": "regenerable cache",
            "canonical_survivor": "",
            "proposed_action": "quarantine",
            "projection_quality": "estimate-logical",
        }
    ]
    exclusions = [
        {
            "item_id": "prot-1",
            "path": r"C:\Users\<profile>\dev\protected-project",
            "disposition": "PROTECTED",
            "protection_reason": "git repository root",
            "protection_source": "protection-index",
            "relationship": "SELF",
        }
    ]
    write_inventory(run_dir / "inventory.csv", inventory)
    write_human_review(run_dir / "human-review.csv", review)
    write_cleanup_plan(run_dir / "cleanup-plan.csv", plan)
    write_protected_exclusions(run_dir / "protected-exclusions.csv", exclusions)
    counts = {
        "HUMAN_REVIEW": 2,
        "UNKNOWN": 1,
        "PROTECTED": 1,
        "RECLAIM_PROVEN": 1,
        "KEEP_PROVEN": 1,
    }
    metadata = {
        "run_id": "synthetic-viz-f1",
        "authorization_state": "UNAPPROVED",
        "plan_rows": 1,
        "cumulative_projected_reclaim_bytes": 8_900_000_000,
        "disposition_counts": counts,
        "baseline_free_bytes": 32_000_000_000,
        "target_free_bytes": 80_000_000_000,
        "stop_row": None,
        "logical_bytes_observed": 162_300_000_000,
    }
    # stop_row: gap = 80G - 32G = 48G; plan only 8.9G so stop_row stays None
    write_run_metadata(run_dir / "run.json", metadata)
    summary = SummaryModel(
        run_id="synthetic-viz-f1",
        root=r"C:\synthetic",
        run_dir=str(run_dir),
        inventory_items=6,
        logical_bytes_observed=162_300_000_000,
        logical_unknown_items=0,
        allocated_known_bytes=154_800_000_000,
        allocated_known_items=5,
        allocation_note="synthetic",
        disposition_counts=counts,
        plan_rows=1,
        projected_reclaim_total=8_900_000_000,
        projected_allocated_bytes=0,
        projected_estimate_bytes=8_900_000_000,
        container_rows=0,
        baseline_free_bytes=32_000_000_000,
        target_free_bytes=80_000_000_000,
        cumulative_projected_reclaim_bytes=8_900_000_000,
        stop_row=None,
        stop_note="target not reached by proposed reclaim",
        human_review_count=2,
        human_review_bytes=129_000_000_000,
        human_review_unknown_size=0,
        protected_count=1,
        protected_breakdown={"SELF": 1},
        unknown_count=1,
        unknown_bytes=7_500_000_000,
        keep_count=1,
    )
    write_summary(run_dir / "cleanup-summary.md", summary)
    errors = validate_run(run_dir)
    assert errors == [], errors
    return run_dir


def test_build_presentation_model_happy_path(tmp_path: Path) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    model = build_presentation_model(run_dir)
    by_id = model.by_id()
    assert set(by_id) >= {
        "review-1",
        "unknown-1",
        "prot-1",
        "reclaim-1",
        "keep-1",
        "cache-look-1",
    }
    assert by_id["review-1"].disposition is CleanupDisposition.HUMAN_REVIEW
    assert by_id["review-1"].path == HOSTILE
    assert by_id["reclaim-1"].disposition is CleanupDisposition.RECLAIM_PROVEN
    assert by_id["reclaim-1"].authorization_state is AuthorizationState.UNAPPROVED
    assert by_id["reclaim-1"].projected_reclaim_bytes == 8_900_000_000
    assert by_id["reclaim-1"].projection_quality == "estimate-logical"
    assert any(s.is_first_unresolved for s in by_id["reclaim-1"].gate_steps)
    assert by_id["cache-look-1"].disposition is CleanupDisposition.HUMAN_REVIEW
    assert by_id["cache-look-1"].contract_summary is None
    assert "evil" not in (by_id["cache-look-1"].contract_summary or "")
    assert by_id["prot-1"].disposition is CleanupDisposition.PROTECTED
    assert by_id["unknown-1"].scan_completeness is ScanCompleteness.INCOMPLETE
    assert model.metrics.authorization_label == "UNAPPROVED"


def test_protection_precedes_incomplete_on_protected_row(tmp_path: Path) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    model = build_presentation_model(run_dir)
    prot = model.by_id()["prot-1"]
    assert prot.gate_steps[0].gate_id == "protection"
    assert prot.gate_steps[0].is_first_unresolved is True


def test_refuse_invalid_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "bad"
    run_dir.mkdir()
    (run_dir / "inventory.csv").write_text("nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="validation"):
        build_presentation_model(run_dir)


def test_prose_contract_claim_does_not_promote(tmp_path: Path) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    model = build_presentation_model(run_dir)
    node = model.by_id()["cache-look-1"]
    assert node.disposition is CleanupDisposition.HUMAN_REVIEW
    assert node.contract_summary is None
    assert "regenerable-cache-9" not in node.next_gate


def _rewrite_inventory_field(
    run_dir: Path, *, item_id: str, field: str, value: str
) -> None:
    path = run_dir / "inventory.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or ())
    for row in rows:
        if row["item_id"] == item_id:
            row[field] = value
            break
    else:
        raise AssertionError(f"fixture item not found: {item_id}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_unknown_protection_relation_fails_closed(tmp_path: Path) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    _rewrite_inventory_field(
        run_dir,
        item_id="reclaim-1",
        field="protection_relation",
        value="FUTURE_RELATION",
    )
    with pytest.raises(ValueError, match="protection_relation|validation"):
        build_presentation_model(run_dir)


def test_unknown_scan_completeness_fails_closed(tmp_path: Path) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    _rewrite_inventory_field(
        run_dir,
        item_id="reclaim-1",
        field="scan_completeness",
        value="PARTIALLY_COMPLETE",
    )
    with pytest.raises(ValueError, match="scan_completeness|validation"):
        build_presentation_model(run_dir)


def _write_buckets(run_dir: Path, rows: list[dict[str, object]]) -> None:
    path = run_dir / "human-review-buckets.csv"
    fieldnames = [
        "prefix",
        "depth",
        "item_count",
        "logical_bytes_known",
        "unknown_size_count",
        "contract_hint_tags",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_large_inventory_uses_persisted_review_buckets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    _write_buckets(
        run_dir,
        [
            {
                "prefix": r"C:\Users\<profile>\.cache\opencode",
                "depth": 5,
                "item_count": 100,
                "logical_bytes_known": 8_000_000_000,
                "unknown_size_count": 0,
                "contract_hint_tags": "cache",
            },
            {
                "prefix": r"C:\Users\<profile>\AppData\Local\Temp",
                "depth": 5,
                "item_count": 50,
                "logical_bytes_known": 2_000_000_000,
                "unknown_size_count": 3,
                "contract_hint_tags": "temp",
            },
            {
                "prefix": r"C:\Users\<profile>\Documents",
                "depth": 4,
                "item_count": 10,
                "logical_bytes_known": 500_000_000,
                "unknown_size_count": 0,
                "contract_hint_tags": "",
            },
        ],
    )
    monkeypatch.setattr(
        "filesteward.visualization.model._count_csv_data_rows",
        lambda _path: 6000,
    )
    model = build_presentation_model(run_dir)
    assert len(model.nodes) == 3
    assert all(node.disposition is CleanupDisposition.UNKNOWN for node in model.nodes)
    assert all(
        node.authorization_state is AuthorizationState.UNAPPROVED for node in model.nodes
    )
    assert all(
        node.trace_evidence_source == "human-review-buckets.csv" for node in model.nodes
    )
    largest = max(model.nodes, key=lambda n: n.logical_size_bytes or -1)
    assert model.default_selected_id == largest.node_id
    assert largest.path.endswith(r".cache\opencode")
    assert largest.contract_hint_tags == ("cache",)
    assert largest.projected_reclaim_bytes is None
    assert "fails closed to UNKNOWN" in largest.reason
    assert any(step.gate_id == "disposition" for step in largest.gate_steps)


def test_large_inventory_without_buckets_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    monkeypatch.setattr(
        "filesteward.visualization.model._count_csv_data_rows",
        lambda _path: 6000,
    )
    with pytest.raises(ValueError, match="human-review-buckets"):
        build_presentation_model(run_dir)


def test_count_csv_data_rows_handles_quoted_newlines(tmp_path: Path) -> None:
    from filesteward.visualization.model import _count_csv_data_rows

    path = tmp_path / "quoted.csv"
    path.write_text(
        'item_id,path\n'
        'a,"line1\nline2"\n'
        "b,plain\n",
        encoding="utf-8",
        newline="",
    )
    assert _count_csv_data_rows(path) == 2


def test_bucket_aggregation_caps_node_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write_valid_run(tmp_path / "run")
    rows = [
        {
            "prefix": rf"C:\Users\<profile>\Bucket{i:03d}",
            "depth": 5,
            "item_count": 1,
            "logical_bytes_known": 1_000_000_000 - i,
            "unknown_size_count": 0,
            "contract_hint_tags": "cache" if i % 2 == 0 else "",
        }
        for i in range(250)
    ]
    _write_buckets(run_dir, rows)
    monkeypatch.setattr(
        "filesteward.visualization.model._count_csv_data_rows",
        lambda _path: 6000,
    )
    model = build_presentation_model(run_dir)
    assert len(model.nodes) == 200
    sizes = [node.logical_size_bytes or 0 for node in model.nodes]
    assert sizes == sorted(sizes, reverse=True)
