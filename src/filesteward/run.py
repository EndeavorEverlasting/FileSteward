"""Read-only cleanup run: scan -> protection -> gates -> challenge -> artifacts.

Dependency direction (P04 section 6): ``cli -> run -> inventory /
protection / classify / manifest``. This module orchestrates and
computes evidence enrichment; it never decides a disposition (that is
``classify``'s job) and never decides column semantics (that is
``manifest``'s job).

All mutation performed here is limited to creating the run directory
beneath the ignored ``var/`` tree and writing evidence artifacts into
it. The scanned root is never written to.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping, Optional, Sequence

from filesteward.classify import (
    AdversarialChallenge,
    CacheContract,
    evaluate_gates,
    nominate,
    resolve_directory_disposition,
)
from filesteward.inventory.scan import ScanDeps, iter_inventory
from filesteward.manifest import artifacts
from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    EntryType,
)
from filesteward.policy.paths import is_under_forbidden_root, runtime_root
from filesteward.protect import ProtectedRoot, ProtectionIndex, ProtectionRelation

__all__ = ["CleanupRun", "RunResult"]

_EXCLUSION_REASONS = {
    ProtectionRelation.SELF.value: "candidate is a protected root (SELF)",
    ProtectionRelation.DESCENDANT.value: (
        "candidate is beneath a protected root (DESCENDANT)"
    ),
    ProtectionRelation.ANCESTOR.value: (
        "ancestor directory contains a protected subtree; whole-directory "
        "action prohibited, children evaluated separately"
    ),
}

_ARTIFACT_FILENAMES = (
    "inventory.csv",
    "cleanup-plan.csv",
    "human-review.csv",
    "protected-exclusions.csv",
    "cleanup-summary.md",
    "run.json",
)


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


@dataclass(frozen=True)
class RunResult:
    """Outcome of one read-only run; evidence, never approval."""

    run_dir: Path
    inventory_items: int
    disposition_counts: Mapping[str, int]
    plan_rows: int
    cumulative_projected_reclaim_bytes: int
    baseline_free_bytes: Optional[int]
    target_free_bytes: Optional[int]
    stop_row: Optional[int]
    artifact_paths: tuple[Path, ...]


class CleanupRun:
    """One deterministic, read-only analysis pass over a synthetic root."""

    def __init__(
        self,
        root: os.PathLike[str] | str,
        run_dir: os.PathLike[str] | str,
        *,
        contracts: Sequence[CacheContract] = (),
        protected_roots: Sequence[os.PathLike[str] | str] = (),
        managed_paths: Sequence[os.PathLike[str] | str] = (),
        target_free_bytes: Optional[int] = None,
        baseline_free_bytes: Optional[int] = None,
        scan_deps: Optional[ScanDeps] = None,
    ) -> None:
        for name, value in (
            ("target_free_bytes", target_free_bytes),
            ("baseline_free_bytes", baseline_free_bytes),
        ):
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative int or None")
        self._root = Path(root)
        self._run_dir = Path(run_dir)
        self._contracts = tuple(contracts)
        self._protected_roots = tuple(
            ProtectedRoot(path=os.fspath(path), source="operator-declared")
            for path in protected_roots
        )
        self._managed_paths = tuple(
            os.fspath(path) for path in managed_paths
        )
        self._target_free_bytes = target_free_bytes
        self._baseline_free_bytes = baseline_free_bytes
        self._scan_deps = scan_deps

    def execute(self) -> RunResult:
        root = self._root.absolute()
        run_dir = self._run_dir.absolute()

        if not root.is_dir():
            raise ValueError(f"scan root is not a directory: {root}")
        if is_under_forbidden_root(root):
            raise ValueError(
                f"scan root {root} sits beneath a forbidden root "
                "(Desktop/Documents/OneDrive/Backups); refusing"
            )
        runtime = runtime_root()
        if run_dir == runtime or not _is_within(run_dir, runtime):
            raise ValueError(
                f"run-dir must live beneath the ignored runtime tree "
                f"{runtime}; got {run_dir}"
            )
        if _is_within(run_dir, root):
            raise ValueError(
                "run-dir must not live inside the scan root; "
                f"{run_dir} is within {root}"
            )

        run_dir.mkdir(parents=True, exist_ok=True)

        baseline = self._baseline_free_bytes
        if baseline is None:
            try:
                baseline = int(shutil.disk_usage(root).free)
            except OSError:
                baseline = None

        index = ProtectionIndex(
            list(self._protected_roots)
            + list(ProtectionIndex.from_git_discovery(root))
        )

        challenge = AdversarialChallenge()
        children: dict[str, list[str]] = {}
        subtree_complete: dict[str, bool] = {}
        final_disposition: dict[str, CleanupDisposition] = {}
        records: list[dict[str, Any]] = []

        for item in iter_inventory(str(root), deps=self._scan_deps):
            relation = index.relation(item.path)
            kids = children.get(item.path, ())
            gates = evaluate_gates(
                item,
                protection=relation,
                contracts=self._contracts,
                managed_paths=self._managed_paths,
                descendant_complete=all(
                    subtree_complete[child] for child in kids
                ),
            )
            provisional = nominate(gates)
            reviewed = challenge.review(item, gates, provisional)
            disposition = reviewed.final_disposition
            basis_parts = [provisional.basis, *reviewed.challenge_notes]

            if item.entry_type is EntryType.DIRECTORY and kids:
                composed, composed_basis = resolve_directory_disposition(
                    [final_disposition[child] for child in kids]
                )
                if composed is not disposition:
                    if composed is CleanupDisposition.PROTECTED or (
                        disposition is CleanupDisposition.RECLAIM_PROVEN
                    ):
                        disposition = composed
                        basis_parts.append(
                            f"directory composition: {composed_basis}"
                        )
                elif disposition is CleanupDisposition.RECLAIM_PROVEN:
                    basis_parts.append(
                        "directory composition: all descendants reclaim-proven"
                    )

            subtree_complete[item.item_id] = gates.observation_complete
            final_disposition[item.item_id] = disposition
            children.setdefault(os.path.dirname(item.path), []).append(
                item.item_id
            )
            records.append(
                {
                    "item": item,
                    "relation": relation,
                    "gates": gates,
                    "provisional": provisional,
                    "reviewed": reviewed,
                    "disposition": disposition,
                    "basis": " | ".join(basis_parts),
                    "allocated_size_bytes": item.allocated_size_bytes,
                }
            )

        plan_rows, review_rows, exclusion_rows, keep_count = self._partition(
            records, index
        )
        self._project(plan_rows)

        plan_rows.sort(key=self._plan_sort_key)
        review_rows.sort(key=self._review_sort_key)
        exclusion_rows.sort(key=lambda row: str(row["path"]).casefold())

        counts: dict[str, int] = {}
        logical_total = 0
        logical_unknown = 0
        allocated_total = 0
        allocated_items = 0
        for record in records:
            disposition_value = record["disposition"].value
            counts[disposition_value] = counts.get(disposition_value, 0) + 1
            logical = record["item"].logical_size_bytes
            if logical is None:
                logical_unknown += 1
            else:
                logical_total += logical
            allocated = record["allocated_size_bytes"]
            if allocated is not None:
                allocated_total += allocated
                allocated_items += 1

        cumulative = sum(
            int(row["projected_reclaim_bytes"])
            for row in plan_rows
            if row["projected_reclaim_bytes"] is not None
        )
        stop_row, stop_note = self._stop_point(
            plan_rows, baseline, self._target_free_bytes
        )

        artifacts.write_inventory(
            run_dir / "inventory.csv",
            [self._inventory_row(record) for record in records],
        )
        artifacts.write_cleanup_plan(run_dir / "cleanup-plan.csv", plan_rows)
        artifacts.write_human_review(run_dir / "human-review.csv", review_rows)
        artifacts.write_protected_exclusions(
            run_dir / "protected-exclusions.csv", exclusion_rows
        )

        counts_for_metadata = dict(counts)
        metadata: dict[str, Any] = {
            "run_id": run_dir.name,
            "root": str(root),
            "authorization_state": AuthorizationState.UNAPPROVED.value,
            "baseline_free_bytes": baseline,
            "target_free_bytes": self._target_free_bytes,
            "cumulative_projected_reclaim_bytes": cumulative,
            "plan_rows": len(plan_rows),
            "stop_row": stop_row,
            "disposition_counts": counts_for_metadata,
            "contracts": [
                {
                    "contract_id": contract.contract_id,
                    "path_prefix": contract.path_prefix,
                }
                for contract in self._contracts
            ],
            "protected_roots": [
                {"path": protected.path, "source": protected.source}
                for protected in index
            ],
            "managed_paths": list(self._managed_paths),
        }
        artifacts.write_run_metadata(run_dir / "run.json", metadata)

        allocated_quality_total = sum(
            int(row["projected_reclaim_bytes"])
            for row in plan_rows
            if row["projection_quality"] == "allocated-evidence"
            and row["projected_reclaim_bytes"] is not None
        )
        estimate_total = sum(
            int(row["projected_reclaim_bytes"])
            for row in plan_rows
            if row["projection_quality"] == "estimate-logical"
            and row["projected_reclaim_bytes"] is not None
        )
        container_rows = sum(
            1
            for row in plan_rows
            if row["projection_quality"] == "container-row"
        )
        review_bytes = sum(
            int(row["logical_size_bytes"])
            for row in review_rows
            if row["logical_size_bytes"] is not None
        )
        review_unknown_size = sum(
            1 for row in review_rows if row["logical_size_bytes"] is None
        )
        unknown_records = [
            record
            for record in records
            if record["disposition"] is CleanupDisposition.UNKNOWN
        ]
        unknown_bytes = sum(
            int(record["item"].logical_size_bytes or 0)
            for record in unknown_records
        )
        breakdown = {
            relation.value: sum(
                1
                for row in exclusion_rows
                if row["relationship"] == relation.value
            )
            for relation in ProtectionRelation
        }

        summary = artifacts.SummaryModel(
            run_id=run_dir.name,
            root=str(root),
            run_dir=str(run_dir),
            inventory_items=len(records),
            logical_bytes_observed=logical_total,
            logical_unknown_items=logical_unknown,
            allocated_known_bytes=allocated_total,
            allocated_known_items=allocated_items,
            allocation_note=(
                "allocation evidence is taken only from the scanner "
                "(st_blocks where the platform reports it); items "
                "without it are explicitly labeled estimates"
            ),
            disposition_counts=counts,
            plan_rows=len(plan_rows),
            projected_reclaim_total=cumulative,
            projected_allocated_bytes=allocated_quality_total,
            projected_estimate_bytes=estimate_total,
            container_rows=container_rows,
            baseline_free_bytes=baseline,
            target_free_bytes=self._target_free_bytes,
            cumulative_projected_reclaim_bytes=cumulative,
            stop_row=stop_row,
            stop_note=stop_note,
            human_review_count=len(review_rows),
            human_review_bytes=review_bytes,
            human_review_unknown_size=review_unknown_size,
            protected_count=len(exclusion_rows),
            protected_breakdown=breakdown,
            unknown_count=len(unknown_records),
            unknown_bytes=unknown_bytes,
            keep_count=keep_count,
        )
        artifacts.write_summary(run_dir / "cleanup-summary.md", summary)

        errors = artifacts.validate_run(run_dir)
        if errors:
            raise RuntimeError(
                "self-validation failed after writing artifacts:\n"
                + "\n".join(errors)
            )

        return RunResult(
            run_dir=run_dir,
            inventory_items=len(records),
            disposition_counts=counts,
            plan_rows=len(plan_rows),
            cumulative_projected_reclaim_bytes=cumulative,
            baseline_free_bytes=baseline,
            target_free_bytes=self._target_free_bytes,
            stop_row=stop_row,
            artifact_paths=tuple(
                run_dir / name for name in _ARTIFACT_FILENAMES
            ),
        )

    # ------------------------------------------------------------------
    # Partition, projection, and presentation helpers.

    @staticmethod
    def _relation_source(index: ProtectionIndex, path: str) -> str:
        candidate = tuple(
            part.lower() for part in PureWindowsPath(path).parts
        )
        sources: list[str] = []
        for protected in index:
            base = protected.key
            matches = candidate == base or (
                len(candidate) > len(base)
                and candidate[: len(base)] == base
            ) or (
                len(base) > len(candidate)
                and base[: len(candidate)] == candidate
            )
            if matches and protected.source not in sources:
                sources.append(protected.source)
        return ", ".join(sources) if sources else "unspecified"

    def _partition(
        self,
        records: Sequence[Mapping[str, Any]],
        index: ProtectionIndex,
    ) -> tuple[list[dict], list[dict], list[dict], int]:
        plan_rows: list[dict] = []
        review_rows: list[dict] = []
        exclusion_rows: list[dict] = []
        keep_count = 0

        for record in records:
            item = record["item"]
            relation: ProtectionRelation = record["relation"]
            disposition: CleanupDisposition = record["disposition"]
            gates = record["gates"]
            provisional = record["provisional"]

            if relation is not ProtectionRelation.UNRELATED:
                exclusion_rows.append(
                    {
                        "item_id": item.item_id,
                        "path": item.path,
                        "disposition": disposition.value,
                        "protection_reason": _EXCLUSION_REASONS[
                            relation.value
                        ],
                        "protection_source": self._relation_source(
                            index, item.path
                        ),
                        "relationship": relation.value,
                    }
                )
                continue

            if disposition is CleanupDisposition.RECLAIM_PROVEN:
                plan_rows.append(
                    {
                        "_record": record,
                        "item_id": item.item_id,
                        "path": item.path,
                        "logical_size_bytes": item.logical_size_bytes,
                        "allocated_size_bytes": record[
                            "allocated_size_bytes"
                        ],
                        "projected_reclaim_bytes": None,
                        "reclaim_basis": "",
                        "disposition": disposition.value,
                        "confidence_basis": (
                            f"rules: {record['basis']}; "
                            "challenge: sustained"
                        ),
                        "evidence": "; ".join(gates.notes),
                        "protection_check": (
                            f"ProtectionIndex relation {relation.value}"
                        ),
                        "recoverability": (
                            f"documented via contract {gates.contract_id}"
                        ),
                        "canonical_survivor": "not-applicable",
                        "proposed_action": "quarantine",
                        "projection_quality": "estimate-logical",
                    }
                )
            elif disposition in (
                CleanupDisposition.HUMAN_REVIEW,
                CleanupDisposition.UNKNOWN,
            ):
                if disposition is CleanupDisposition.UNKNOWN:
                    why = (
                        f"observation incomplete: {item.scan_error}"
                        if item.scan_error
                        else "observation incomplete"
                    )
                    check = (
                        "resolve access errors and rescan; unreadable "
                        "descendants are not absent"
                    )
                    risk = (
                        "item was not fully observed; acting risks "
                        "removing unread content"
                    )
                elif (
                    provisional.disposition
                    is CleanupDisposition.RECLAIM_PROVEN
                ):
                    # Fell out of a reclaim nomination via the
                    # independent challenge or directory composition:
                    # the full narrative is the ambiguity.
                    why = record["basis"]
                    check = (
                        "resolve the reported loss case or composition "
                        "conflict before any action"
                    )
                    risk = (
                        "the deterministic loss case was not defeated; "
                        "acting may destroy shared or ambiguous content"
                    )
                else:
                    why = provisional.basis
                    check = (
                        "verify provenance, recoverability, and whether "
                        "removal would cause loss"
                    )
                    risk = (
                        "unproven provenance/recoverability; removal may "
                        "destroy data with no recovery path"
                    )
                review_rows.append(
                    {
                        "item_id": item.item_id,
                        "path": item.path,
                        "disposition": disposition.value,
                        "logical_size_bytes": item.logical_size_bytes,
                        "allocated_size_bytes": record[
                            "allocated_size_bytes"
                        ],
                        "why_ambiguous": why,
                        "what_operator_should_check": check,
                        "known_context": (
                            f"entry={item.entry_type.value}; "
                            f"scan={item.scan_completeness.value}; "
                            f"protection={relation.value}; "
                            f"contract={gates.contract_id or 'none'}; "
                            f"link_count={item.link_count}; "
                            f"placeholder={item.is_cloud_placeholder}; "
                            f"system_managed={gates.managed}"
                        ),
                        "risk_if_acted_on": risk,
                    }
                )
            elif disposition is CleanupDisposition.PROTECTED:
                exclusion_rows.append(
                    {
                        "item_id": item.item_id,
                        "path": item.path,
                        "disposition": disposition.value,
                        "protection_reason": (
                            "disposition PROTECTED (fail-closed conflict)"
                        ),
                        "protection_source": "disposition-gates",
                        "relationship": relation.value,
                    }
                )
            elif disposition is CleanupDisposition.KEEP_PROVEN:
                keep_count += 1

        return plan_rows, review_rows, exclusion_rows, keep_count

    @staticmethod
    def _project(plan_rows: Sequence[dict]) -> None:
        """Attach projection evidence to each plan row in place.

        Directories are container rows: their descendants carry the
        bytes, so the directory itself projects ``None`` and never
        double-counts. Enriched allocation is written back into the
        backing record so inventory and summary agree.
        """

        for row in plan_rows:
            record = row.pop("_record")
            item = record["item"]
            if item.entry_type is EntryType.DIRECTORY:
                row["projected_reclaim_bytes"] = None
                row["reclaim_basis"] = (
                    "container of reclaim-proven descendants; reclaim "
                    "bytes counted on descendant rows"
                )
                row["projection_quality"] = "container-row"
                continue
            allocated = row.get("allocated_size_bytes")
            if allocated is not None and item.link_count == 1:
                row["allocated_size_bytes"] = allocated
                record["allocated_size_bytes"] = allocated
                row["projected_reclaim_bytes"] = int(allocated)
                row["reclaim_basis"] = (
                    "allocated bytes: single-link regular file, "
                    "scanner-reported allocation evidence"
                )
                row["projection_quality"] = "allocated-evidence"
            else:
                row["allocated_size_bytes"] = (
                    row.get("allocated_size_bytes") or None
                )
                row["projected_reclaim_bytes"] = item.logical_size_bytes
                row["reclaim_basis"] = (
                    "estimate: logical size; allocation evidence "
                    "unavailable on this platform"
                )
                row["projection_quality"] = "estimate-logical"

    @staticmethod
    def _plan_sort_key(row: Mapping[str, Any]) -> tuple:
        projected = row.get("projected_reclaim_bytes")
        return (
            projected is None,
            -(projected or 0),
            str(row["path"]).casefold(),
        )

    @staticmethod
    def _review_sort_key(row: Mapping[str, Any]) -> tuple:
        logical = row.get("logical_size_bytes")
        return (
            logical is None,
            -(logical or 0),
            str(row["path"]).casefold(),
        )

    @staticmethod
    def _stop_point(
        plan_rows: Sequence[Mapping[str, Any]],
        baseline: Optional[int],
        target: Optional[int],
    ) -> tuple[Optional[int], str]:
        if target is None:
            return None, "target free bytes not set; stop point not evaluated"
        if baseline is None:
            return (
                None,
                "baseline free bytes unknown; stop point not evaluated",
            )
        gap = max(0, target - baseline)
        if gap == 0:
            return 0, "baseline already meets or exceeds the target"
        running = 0
        for index, row in enumerate(plan_rows, start=1):
            projected = row.get("projected_reclaim_bytes")
            if projected is not None:
                running += int(projected)
            if running >= gap:
                return index, (
                    "cumulative projected reclaim covers the gap after "
                    f"plan row {index} of {len(plan_rows)}"
                )
        return None, (
            "target not reachable from this plan: cumulative projected "
            f"reclaim {running} bytes leaves a shortfall of "
            f"{gap - running} bytes"
        )

    @staticmethod
    def _inventory_row(record: Mapping[str, Any]) -> dict[str, Any]:
        item = record["item"]
        return {
            "item_id": item.item_id,
            "path": item.path,
            "entry_type": item.entry_type.value,
            "disposition": record["disposition"].value,
            "evidence_state": "DISPOSITION_ASSIGNED",
            "protection_relation": record["relation"].value,
            "scan_completeness": item.scan_completeness.value,
            "scan_error": item.scan_error,
            "logical_size_bytes": item.logical_size_bytes,
            "allocated_size_bytes": record["allocated_size_bytes"],
            "modified_at": item.modified_at,
            "link_count": item.link_count,
            "is_symlink": item.is_symlink,
            "is_reparse_point": item.is_reparse_point,
            "is_cloud_placeholder": item.is_cloud_placeholder,
        }
