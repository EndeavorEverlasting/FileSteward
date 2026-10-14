"""Illustrative welcome evidence. No scanner or filesystem classifier is called."""
from pathlib import Path

from filesteward.manifest import (SummaryModel, validate_run, write_cleanup_plan,
    write_human_review, write_inventory, write_protected_exclusions,
    write_run_metadata, write_summary)


def write_sample_run(target: Path, run_id: str) -> Path:
    target.mkdir()
    subjects = [
        ("sample-archive", "Family archive", "HUMAN_REVIEW", 24_000_000_000),
        ("sample-project", "Work project", "PROTECTED", 12_000_000_000),
        ("sample-downloads", "Downloads to review", "HUMAN_REVIEW", 8_000_000_000),
        ("sample-unread", "Incomplete example", "UNKNOWN", 3_000_000_000),
        ("sample-required", "Required application data", "KEEP_PROVEN", 4_000_000_000),
    ]
    inventory, review, exclusions = [], [], []
    counts = {key: 0 for key in ("HUMAN_REVIEW", "PROTECTED", "UNKNOWN", "KEEP_PROVEN")}
    for item_id, name, disposition, size in subjects:
        path = "C:\\FileSteward illustrative sample\\" + name
        complete = disposition != "UNKNOWN"
        inventory.append(dict(item_id=item_id, path=path, entry_type="DIRECTORY",
            disposition=disposition, evidence_state="DISPOSITION_ASSIGNED",
            protection_relation="SELF" if disposition == "PROTECTED" else "UNRELATED",
            scan_completeness="COMPLETE" if complete else "INCOMPLETE",
            scan_error="Illustrative missing observation" if not complete else "",
            logical_size_bytes=size, allocated_size_bytes=size if complete else "",
            modified_at="", link_count="1", is_symlink="false",
            is_reparse_point="false", is_cloud_placeholder="false"))
        counts[disposition] += 1
        if disposition in {"UNKNOWN", "HUMAN_REVIEW"}:
            review.append(dict(item_id=item_id, path=path, disposition=disposition,
                logical_size_bytes=size, allocated_size_bytes=size if complete else "",
                why_ambiguous="Illustrative example, not current workstation evidence",
                what_operator_should_check="Learn the evidence and value gates",
                known_context="Synthetic welcome sample; no files were scanned",
                risk_if_acted_on="Real data always requires current ownership evidence"))
        if disposition == "PROTECTED":
            exclusions.append(dict(item_id=item_id, path=path, disposition=disposition,
                protection_reason="Illustrative protected project",
                protection_source="synthetic-sample", relationship="SELF"))
    total = sum(row[3] for row in subjects)
    write_inventory(target / "inventory.csv", inventory)
    write_human_review(target / "human-review.csv", review)
    write_cleanup_plan(target / "cleanup-plan.csv", [])
    write_protected_exclusions(target / "protected-exclusions.csv", exclusions)
    write_run_metadata(target / "run.json", dict(run_id=run_id,
        authorization_state="UNAPPROVED", plan_rows=0,
        cumulative_projected_reclaim_bytes=0, disposition_counts=counts,
        baseline_free_bytes=32_000_000_000, target_free_bytes=80_000_000_000,
        stop_row=None, logical_bytes_observed=total, synthetic_sample=True))
    write_summary(target / "cleanup-summary.md", SummaryModel(
        run_id=run_id, root=r"C:\FileSteward illustrative sample", run_dir=str(target),
        inventory_items=5, logical_bytes_observed=total, logical_unknown_items=0,
        allocated_known_bytes=total-3_000_000_000, allocated_known_items=4,
        allocation_note="Illustrative only: no workstation scan", disposition_counts=counts,
        plan_rows=0, projected_reclaim_total=0, projected_allocated_bytes=0,
        projected_estimate_bytes=0, container_rows=0, baseline_free_bytes=32_000_000_000,
        target_free_bytes=80_000_000_000, cumulative_projected_reclaim_bytes=0,
        stop_row=None, stop_note="No mutation is proposed by this sample",
        human_review_count=2, human_review_bytes=32_000_000_000,
        human_review_unknown_size=0, protected_count=1, protected_breakdown={"SELF":1},
        unknown_count=1, unknown_bytes=3_000_000_000, keep_count=1))
    errors = validate_run(target)
    if errors:
        raise ValueError("Sample failed its owning validator: " + "; ".join(errors))
    return target
