"""L3 proof: artifact writers, run orchestration, and mechanical validation.

Scenario coverage: cleanup-plan contains only RECLAIM_PROVEN, human-review
carries no score/persuasive language, protected exclusions reconcile by
stable item_id, honest stop-point math (baseline + cumulative >= target),
S6 mixed-directory decomposition at run level, and explicit UNKNOWN
routing for scan gaps.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest

from filesteward.classify import CacheContract
from filesteward.inventory.scan import ScanDeps
from filesteward.manifest import (
    PLAN_COLUMNS,
    REVIEW_COLUMNS,
    EXCLUSIONS_COLUMNS,
    validate_run,
    write_cleanup_plan,
    write_human_review,
    write_protected_exclusions,
)
from filesteward.policy.paths import run_dir as policy_run_dir
from filesteward.run import CleanupRun

_CACHE_CONTRACT_ID = "synthetic.cache"
_ZONE_CONTRACT_ID = "synthetic.zone"


@pytest.fixture
def artifact_run_dir() -> Iterator[Path]:
    path = policy_run_dir(f"test-artifacts-{uuid.uuid4().hex[:10]}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_mixed_fixture(root: Path) -> None:
    """Contracted cache, contract-covered zone with a shared hard link,
    an ambiguous file, and a protected repository."""

    (root / "cache").mkdir(parents=True)
    (root / "cache" / "a.bin").write_bytes(b"A" * 1000)
    (root / "cache" / "b.bin").write_bytes(b"B" * 800)
    (root / "zone").mkdir()
    (root / "zone" / "a.bin").write_bytes(b"Z" * 600)
    (root / "outside.dat").write_bytes(b"O" * 700)
    # Same content under two names: link_count=2 defeats reclaim.
    os.link(root / "outside.dat", root / "zone" / "b.bin")
    (root / "misc").mkdir()
    (root / "misc" / "note.txt").write_text("ambiguous note", encoding="utf-8")
    (root / "proj" / "repo").mkdir(parents=True)
    (root / "proj" / "repo" / "tracked.txt").write_text("repo", encoding="utf-8")


@pytest.fixture
def produced_run(tmp_path: Path, artifact_run_dir: Path):
    root = (tmp_path / "root").resolve()
    build_mixed_fixture(root)
    contracts = (
        CacheContract(
            contract_id=_CACHE_CONTRACT_ID,
            path_prefix=str(root / "cache"),
            description="synthetic cache contract",
        ),
        CacheContract(
            contract_id=_ZONE_CONTRACT_ID,
            path_prefix=str(root / "zone"),
            description="synthetic zone contract",
        ),
    )
    result = CleanupRun(
        root,
        artifact_run_dir,
        contracts=contracts,
        protected_roots=(root / "proj" / "repo",),
        baseline_free_bytes=0,
        target_free_bytes=1,
    ).execute()
    return root, artifact_run_dir, result


# --- writer units ------------------------------------------------------


def _plan_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "item_id": "abc123",
        "path": "C:/synthetic/cache/file.bin",
        "logical_size_bytes": 100,
        "allocated_size_bytes": None,
        "projected_reclaim_bytes": 100,
        "reclaim_basis": "estimate: logical size",
        "disposition": "RECLAIM_PROVEN",
        "confidence_basis": "rules: all gates satisfied",
        "evidence": "contract=synthetic.cache",
        "protection_check": "ProtectionIndex relation UNRELATED",
        "recoverability": "documented via contract synthetic.cache",
        "canonical_survivor": "not-applicable",
        "proposed_action": "quarantine",
        "projection_quality": "estimate-logical",
    }
    row.update(overrides)
    return row


class TestWriterGuards:
    def test_plan_writer_rejects_non_reclaim_rows(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="RECLAIM_PROVEN"):
            write_cleanup_plan(
                tmp_path / "plan.csv", [_plan_row(disposition="HUMAN_REVIEW")]
            )

    def test_plan_writer_rejects_unknown_projection_quality(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="projection_quality"):
            write_cleanup_plan(
                tmp_path / "plan.csv",
                [_plan_row(projection_quality=" vibes")],
            )

    def test_plan_writer_computes_priority_and_cumulative(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "plan.csv"
        write_cleanup_plan(
            path,
            [
                _plan_row(item_id="big", projected_reclaim_bytes=500),
                _plan_row(item_id="small", projected_reclaim_bytes=None),
                _plan_row(item_id="mid", projected_reclaim_bytes=300),
            ],
        )
        rows = _read_rows(path)
        assert [row["priority"] for row in rows] == ["1", "2", "3"]
        assert [
            row["cumulative_projected_reclaim_bytes"] for row in rows
        ] == ["500", "500", "800"]
        assert tuple(rows[0].keys()) == PLAN_COLUMNS

    def test_review_writer_rejects_wrong_disposition(
        self, tmp_path: Path
    ) -> None:
        row = {
            "item_id": "x",
            "path": "C:/synthetic/file",
            "disposition": "RECLAIM_PROVEN",
            "logical_size_bytes": 1,
            "allocated_size_bytes": None,
            "why_ambiguous": "no contract",
            "what_operator_should_check": "verify provenance",
            "known_context": "scan=COMPLETE",
            "risk_if_acted_on": "unproven",
        }
        with pytest.raises(ValueError, match="HUMAN_REVIEW/UNKNOWN"):
            write_human_review(tmp_path / "review.csv", [row])

    def test_exclusion_writer_requires_reason_and_source(
        self, tmp_path: Path
    ) -> None:
        row = {
            "item_id": "x",
            "path": "C:/synthetic/repo",
            "disposition": "PROTECTED",
            "protection_reason": "",
            "protection_source": "git-repository",
            "relationship": "SELF",
        }
        with pytest.raises(ValueError, match="protection_reason"):
            write_protected_exclusions(tmp_path / "excl.csv", [row])
        row["protection_reason"] = "protected root"
        row["protection_source"] = ""
        with pytest.raises(ValueError, match="protection_source"):
            write_protected_exclusions(tmp_path / "excl.csv", [row])


# --- produced run invariants ------------------------------------------


class TestProducedRun:
    def test_run_self_validates(self, produced_run) -> None:
        _, run_path, result = produced_run
        assert validate_run(run_path) == []
        assert result.plan_rows >= 1

    def test_cleanup_plan_contains_only_reclaim_proven(self, produced_run) -> None:
        _, run_path, _ = produced_run
        rows = _read_rows(run_path / "cleanup-plan.csv")
        assert rows
        assert all(
            row["disposition"] == "RECLAIM_PROVEN" for row in rows
        )
        assert all(
            row["projection_quality"]
            in ("allocated-evidence", "estimate-logical", "container-row")
            for row in rows
        )
        # Container rows never carry bytes: no double counting.
        for row in rows:
            if row["projection_quality"] == "container-row":
                assert row["projected_reclaim_bytes"] == ""

    def test_human_review_has_no_score_or_pressure_language(
        self, produced_run
    ) -> None:
        _, run_path, _ = produced_run
        path = run_path / "human-review.csv"
        rows = _read_rows(path)
        assert rows
        assert tuple(rows[0].keys()) == REVIEW_COLUMNS
        prose_columns = (
            "why_ambiguous",
            "what_operator_should_check",
            "known_context",
            "risk_if_acted_on",
        )
        for row in rows:
            for column in prose_columns:
                cell = row[column].casefold()
                assert "score" not in cell, (column, row[column])
                assert "probably safe" not in cell
                assert "likely safe" not in cell
                assert "safe to delete" not in cell
        # Headers themselves carry no score column.
        header = path.read_text(encoding="utf-8").splitlines()[0].casefold()
        assert "score" not in header

    def test_challenge_downgrade_narrates_loss_case(self, produced_run) -> None:
        root, run_path, _ = produced_run
        rows = _read_rows(run_path / "human-review.csv")
        by_path = {row["path"]: row for row in rows}
        shared = by_path[str(root / "zone" / "b.bin")]
        assert shared["disposition"] == "HUMAN_REVIEW"
        assert "hard-link" in shared["why_ambiguous"]

    def test_protected_exclusions_reconcile_with_relation_and_source(
        self, produced_run
    ) -> None:
        root, run_path, _ = produced_run
        rows = _read_rows(run_path / "protected-exclusions.csv")
        assert tuple(rows[0].keys()) == EXCLUSIONS_COLUMNS
        by_path = {row["path"]: row for row in rows}
        assert (
            by_path[str(root / "proj" / "repo")]["relationship"] == "SELF"
        )
        assert (
            by_path[str(root / "proj" / "repo" / "tracked.txt")][
                "relationship"
            ]
            == "DESCENDANT"
        )
        assert by_path[str(root)]["relationship"] == "ANCESTOR"
        for row in rows:
            assert row["protection_reason"]
            assert row["protection_source"]

    def test_inventory_and_queues_reconcile_by_item_id(self, produced_run) -> None:
        _, run_path, _ = produced_run
        inventory = _read_rows(run_path / "inventory.csv")
        ids = [row["item_id"] for row in inventory]
        assert len(ids) == len(set(ids))
        plan = _read_rows(run_path / "cleanup-plan.csv")
        review = _read_rows(run_path / "human-review.csv")
        exclusions = _read_rows(run_path / "protected-exclusions.csv")
        assert not (
            {row["item_id"] for row in plan}
            & {row["item_id"] for row in review}
        )
        assert len(inventory) == len(plan) + len(review) + len(exclusions)

    def test_run_json_is_unapproved_and_math_consistent(
        self, produced_run
    ) -> None:
        _, run_path, _ = produced_run
        metadata = json.loads(
            (run_path / "run.json").read_text(encoding="utf-8")
        )
        assert metadata["authorization_state"] == "UNAPPROVED"
        plan = _read_rows(run_path / "cleanup-plan.csv")
        total = sum(
            int(row["projected_reclaim_bytes"])
            for row in plan
            if row["projected_reclaim_bytes"]
        )
        assert metadata["cumulative_projected_reclaim_bytes"] == total
        assert metadata["plan_rows"] == len(plan)

    def test_summary_carries_required_sections_and_authorization(
        self, produced_run
    ) -> None:
        _, run_path, _ = produced_run
        text = (run_path / "cleanup-summary.md").read_text(encoding="utf-8")
        for section in (
            "## Inventory coverage",
            "## Reclaim projection",
            "## Free-space stop point",
            "## Human review queue",
            "## Protected exclusions",
            "## Unknown coverage",
            "## Authorization",
        ):
            assert section in text
        assert "UNAPPROVED" in text
        assert "estimate rows are not proven reclaimable bytes" in text


# --- S6 mixed directory at run level -----------------------------------


class TestMixedDirectoryComposition:
    def test_zone_directory_cannot_be_reclaim_proven(
        self, produced_run
    ) -> None:
        root, run_path, _ = produced_run
        plan_paths = {row["path"] for row in _read_rows(run_path / "cleanup-plan.csv")}
        review_paths = {row["path"] for row in _read_rows(run_path / "human-review.csv")}
        zone = str(root / "zone")
        assert zone not in plan_paths
        assert zone in review_paths
        # Its unambiguous child stays independently evaluable.
        assert str(root / "zone" / "a.bin") in plan_paths
        # And the ambiguous sibling is queued for the operator.
        assert str(root / "zone" / "b.bin") in review_paths


# --- UNKNOWN routing through a scan gap --------------------------------


class TestUnknownRouting:
    def test_denied_subtree_is_unknown_and_queued(
        self, tmp_path: Path, artifact_run_dir: Path
    ) -> None:
        root = (tmp_path / "root").resolve()
        (root / "good").mkdir(parents=True)
        (root / "good" / "ok.txt").write_text("ok", encoding="utf-8")
        (root / "bad").mkdir()
        (root / "bad" / "hidden.txt").write_text("secret", encoding="utf-8")

        real_scandir = os.scandir
        bad_path = os.path.normcase(str(root / "bad"))

        def fake_scandir(path: str):
            if os.path.normcase(path) == bad_path:
                raise PermissionError(5, "synthetic access denied")
            return real_scandir(path)

        result = CleanupRun(
            root,
            artifact_run_dir,
            scan_deps=ScanDeps(scandir=fake_scandir),
        ).execute()

        assert validate_run(artifact_run_dir) == []
        inventory = {
            row["path"]: row
            for row in _read_rows(artifact_run_dir / "inventory.csv")
        }
        bad_row = inventory[str(root / "bad")]
        assert bad_row["disposition"] == "UNKNOWN"
        assert bad_row["scan_completeness"] == "INCOMPLETE"
        assert bad_row["scan_error"]

        review = {
            row["path"]: row
            for row in _read_rows(artifact_run_dir / "human-review.csv")
        }
        assert review[str(root / "bad")]["disposition"] == "UNKNOWN"
        assert "not fully observed" in review[str(root / "bad")]["risk_if_acted_on"]
        assert result.disposition_counts.get("UNKNOWN", 0) >= 1

        # The unreadable subtree never becomes absence: its parent is
        # also incomplete, not silently complete.
        assert inventory[str(root)]["scan_completeness"] == "COMPLETE"
        assert inventory[str(root)]["disposition"] in (
            "UNKNOWN",
            "HUMAN_REVIEW",
        )


# --- stop-point math ---------------------------------------------------


def _tiny_run(
    root: Path,
    run_path: Path,
    *,
    baseline: Optional[int],
    target: Optional[int],
):
    (root).mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(exist_ok=True)
    (root / "cache" / "a.bin").write_bytes(b"A" * 1000)
    (root / "cache" / "b.bin").write_bytes(b"B" * 1000)
    contract = CacheContract(
        contract_id=_CACHE_CONTRACT_ID,
        path_prefix=str(root / "cache"),
        description="synthetic cache contract",
    )
    return CleanupRun(
        root,
        run_path,
        contracts=(contract,),
        baseline_free_bytes=baseline,
        target_free_bytes=target,
    ).execute()


class TestStopPointMath:
    def test_gap_covered_by_second_row(self, tmp_path: Path) -> None:
        run_path = policy_run_dir(f"test-stop-{uuid.uuid4().hex[:10]}")
        try:
            result = _tiny_run(
                tmp_path / "root",
                run_path,
                baseline=1_000_000,
                target=1_001_500,
            )
            assert result.stop_row == 2
            assert validate_run(run_path) == []
        finally:
            shutil.rmtree(run_path, ignore_errors=True)

    def test_unreachable_target_is_reported_not_faked(
        self, tmp_path: Path
    ) -> None:
        run_path = policy_run_dir(f"test-stop-{uuid.uuid4().hex[:10]}")
        try:
            result = _tiny_run(
                tmp_path / "root",
                run_path,
                baseline=0,
                target=10_000_000,
            )
            assert result.stop_row is None
            summary = (run_path / "cleanup-summary.md").read_text(
                encoding="utf-8"
            )
            assert "target not reachable" in summary
            assert validate_run(run_path) == []
        finally:
            shutil.rmtree(run_path, ignore_errors=True)

    def test_baseline_already_meeting_target_stops_at_zero(
        self, tmp_path: Path
    ) -> None:
        run_path = policy_run_dir(f"test-stop-{uuid.uuid4().hex[:10]}")
        try:
            result = _tiny_run(
                tmp_path / "root",
                run_path,
                baseline=1_000_000,
                target=1,
            )
            assert result.stop_row == 0
            assert validate_run(run_path) == []
        finally:
            shutil.rmtree(run_path, ignore_errors=True)

    def test_no_target_means_stop_point_not_evaluated(
        self, tmp_path: Path
    ) -> None:
        run_path = policy_run_dir(f"test-stop-{uuid.uuid4().hex[:10]}")
        try:
            result = _tiny_run(
                tmp_path / "root",
                run_path,
                baseline=1_000_000,
                target=None,
            )
            assert result.stop_row is None
            summary = (run_path / "cleanup-summary.md").read_text(
                encoding="utf-8"
            )
            assert "target free bytes: unknown" in summary
            assert "stop point not evaluated" in summary
            assert validate_run(run_path) == []
        finally:
            shutil.rmtree(run_path, ignore_errors=True)

    def test_negative_free_space_inputs_rejected(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="target_free_bytes"):
            CleanupRun(
                tmp_path, tmp_path / "out", target_free_bytes=-1
            )


# --- validation catches tampering -------------------------------------


class TestValidateTampering:
    @staticmethod
    def _copy(source: Path, destination: Path) -> Path:
        target = destination / "run-copy"
        shutil.copytree(source, target)
        return target

    @staticmethod
    def _rewrite_rows(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in header})

    def test_tampered_plan_disposition_rejected(
        self, produced_run, tmp_path: Path
    ) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        rows = _read_rows(copy / "cleanup-plan.csv")
        rows[0]["disposition"] = "HUMAN_REVIEW"
        self._rewrite_rows(copy / "cleanup-plan.csv", rows)
        errors = validate_run(copy)
        assert any("is not RECLAIM_PROVEN" in error for error in errors)

    def test_missing_review_row_breaks_reconciliation(
        self, produced_run, tmp_path: Path
    ) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        rows = _read_rows(copy / "human-review.csv")
        rows.pop()
        self._rewrite_rows(copy / "human-review.csv", rows)
        errors = validate_run(copy)
        assert any("missing from human-review.csv" in error for error in errors)

    def test_forbidden_phrase_detected(self, produced_run, tmp_path: Path) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        rows = _read_rows(copy / "human-review.csv")
        rows[0]["why_ambiguous"] = "this file is probably safe to remove"
        self._rewrite_rows(copy / "human-review.csv", rows)
        errors = validate_run(copy)
        assert any("forbidden phrase" in error for error in errors)

    def test_score_language_detected(self, produced_run, tmp_path: Path) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        rows = _read_rows(copy / "human-review.csv")
        rows[0]["risk_if_acted_on"] = "delete score says it is fine"
        self._rewrite_rows(copy / "human-review.csv", rows)
        errors = validate_run(copy)
        assert any("score language" in error for error in errors)

    def test_wrong_cumulative_detected(self, produced_run, tmp_path: Path) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        rows = _read_rows(copy / "cleanup-plan.csv")
        rows[0]["cumulative_projected_reclaim_bytes"] = "999999999"
        self._rewrite_rows(copy / "cleanup-plan.csv", rows)
        errors = validate_run(copy)
        assert any("does not equal running total" in error for error in errors)

    def test_missing_summary_section_detected(
        self, produced_run, tmp_path: Path
    ) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        summary = (copy / "cleanup-summary.md").read_text(encoding="utf-8")
        summary = summary.replace("## Authorization", "## Something else")
        (copy / "cleanup-summary.md").write_text(summary, encoding="utf-8")
        errors = validate_run(copy)
        assert any("missing section" in error for error in errors)

    def test_wrong_run_json_cumulative_detected(
        self, produced_run, tmp_path: Path
    ) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        metadata = json.loads((copy / "run.json").read_text(encoding="utf-8"))
        metadata["cumulative_projected_reclaim_bytes"] = -5
        (copy / "run.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        errors = validate_run(copy)
        assert any("run.json" in error for error in errors)

    def test_item_in_two_queues_detected(self, produced_run, tmp_path: Path) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        plan_rows = _read_rows(copy / "cleanup-plan.csv")
        review_rows = _read_rows(copy / "human-review.csv")
        duplicated = dict(plan_rows[0])
        for column in REVIEW_COLUMNS:
            duplicated.setdefault(column, duplicated.get(column, ""))
        duplicated["disposition"] = "RECLAIM_PROVEN"
        review_rows.append(duplicated)
        self._rewrite_rows(copy / "human-review.csv", review_rows)
        errors = validate_run(copy)
        assert any("appears in both" in error for error in errors)

    def test_missing_artifact_detected(self, produced_run, tmp_path: Path) -> None:
        _, run_path, _ = produced_run
        copy = self._copy(run_path, tmp_path)
        (copy / "cleanup-summary.md").unlink()
        errors = validate_run(copy)
        assert any("missing artifact" in error for error in errors)


# --- run-dir guards -----------------------------------------------------


class TestRunGuards:
    def test_run_dir_outside_runtime_tree_rejected(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError, match="runtime tree"):
            CleanupRun(root, tmp_path / "outside-var").execute()

    def test_run_dir_inside_scan_root_rejected(self) -> None:
        # Both paths must sit beneath var/ for the containment guard to
        # be the failing check, so the scan root itself lives in a
        # throwaway runtime directory.
        holder = policy_run_dir(f"test-guard-{uuid.uuid4().hex[:10]}")
        try:
            root = holder / "root"
            root.mkdir(parents=True)
            with pytest.raises(ValueError, match="inside the scan root"):
                CleanupRun(root, root / "out").execute()
        finally:
            shutil.rmtree(holder, ignore_errors=True)

    def test_missing_scan_root_rejected(self, tmp_path: Path) -> None:
        run_path = policy_run_dir(f"test-guard-{uuid.uuid4().hex[:10]}")
        try:
            with pytest.raises(ValueError, match="not a directory"):
                CleanupRun(tmp_path / "absent", run_path).execute()
        finally:
            shutil.rmtree(run_path, ignore_errors=True)

    def test_forbidden_root_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "Documents"
        root.mkdir()
        run_path = policy_run_dir(f"test-guard-{uuid.uuid4().hex[:10]}")
        try:
            with pytest.raises(ValueError, match="forbidden root"):
                CleanupRun(root, run_path).execute()
        finally:
            shutil.rmtree(run_path, ignore_errors=True)
