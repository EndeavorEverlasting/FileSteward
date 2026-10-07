"""Owner-correct action planning. Evidence is never mutation authority."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Callable

from filesteward.models import CleanupDisposition
from filesteward.ownership._windows_paths import normalize_path_key, path_intersects
from filesteward.ownership.graph import OwnershipGraph, build_ownership_graph
from filesteward.ownership.reducer import reduce_path_ownership


class ActionKind(str, Enum):
    KEEP = "KEEP"
    CLEAN_CACHE = "CLEAN_CACHE"
    CLEAN_GENERATED_OUTPUT = "CLEAN_GENERATED_OUTPUT"
    REPAIR_APPLICATION = "REPAIR_APPLICATION"
    UNINSTALL_APPLICATION = "UNINSTALL_APPLICATION"
    ARCHIVE_OR_REMOVE_REPOSITORY = "ARCHIVE_OR_REMOVE_REPOSITORY"
    INVESTIGATE_ORPHAN = "INVESTIGATE_ORPHAN"
    RAW_DELETE_REGENERABLE_ARTIFACT = "RAW_DELETE_REGENERABLE_ARTIFACT"


@dataclass(frozen=True)
class RegenerationProof:
    """Adapter-authored exact boundary, owner identity and recreation recipe."""
    path: str
    owner_id: str
    recipe: str
    source_digest: str
    raw_delete_allowed: bool = False

    def valid_for(self, path: str, owners: tuple[str, ...]) -> bool:
        return bool(
            normalize_path_key(self.path) == normalize_path_key(path)
            and self.owner_id in owners and self.recipe.strip()
            and len(self.source_digest) == 64
            and all(c in "0123456789abcdef" for c in self.source_digest)
        )


@dataclass(frozen=True)
class OwnershipEvidence:
    graph: OwnershipGraph
    adapters_complete: bool = False
    observed_at_unix: float = 0.0
    proofs: tuple[RegenerationProof, ...] = ()

    @property
    def digest(self) -> str:
        # Timestamp is freshness, not semantic revision. All evidence content
        # participates, including details omitted by the J4 revision identifier.
        payload = {"graph": asdict(self.graph), "proofs": [asdict(p) for p in self.proofs],
                   "adapters_complete": self.adapters_complete}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def fresh(self, now: float | None = None) -> bool:
        age = (time.time() if now is None else now) - self.observed_at_unix
        return self.adapters_complete and 0 <= age <= 300


OwnershipResolver = Callable[[str], OwnershipEvidence]


def unresolved_ownership(path: str) -> OwnershipEvidence:
    """No live adapter completeness claim exists by default."""
    return OwnershipEvidence(build_ownership_graph())


@dataclass(frozen=True)
class ActionPlan:
    path: str
    disposition: CleanupDisposition
    actions: tuple[ActionKind, ...]
    reason_codes: tuple[str, ...]
    owner_ids: tuple[str, ...]
    consequence_classes: tuple[str, ...]
    graph_revision_id: str
    evidence_digest: str
    regeneration_digest: str

    @property
    def raw_delete_eligible(self) -> bool:
        return (self.disposition is CleanupDisposition.RECLAIM_PROVEN
                and ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT in self.actions)


_PROTECTIVE_EDGES = frozenset({
    "INSTALLED_AT", "RUNTIME_REQUIRES", "SERVICEABILITY_REQUIRES", "UPDATES_THROUGH",
    "UNINSTALLS_THROUGH", "SERVICE_REFERENCES", "TASK_REFERENCES", "PACKAGE_OWNS",
    "PROCESS_USES", "TRACKED_BY", "TOOLCHAIN_REQUIRES", "IMPORTS_OR_REFERENCES",
    "USER_DATA_FOR", "SHARED_BY", "WORKTREE_OF",
})


def plan_owner_actions(path: str, evidence: OwnershipEvidence) -> ActionPlan:
    graph = evidence.graph
    edges = graph.edges_for_path(path)
    owners = tuple(sorted({e.owner_id for e in edges if e.owner_id}))
    labels = tuple(sorted({e.lifecycle_hint for e in edges if e.lifecycle_hint}))
    judgment = (reduce_path_ownership(path, graph)
                if edges and all(e.owner_kind in {"APPLICATION", "REPOSITORY"}
                                 and e.lifecycle_hint for e in edges) else None)
    proof = next((p for p in evidence.proofs if p.valid_for(path, owners)), None)
    regen_digest = hashlib.sha256(json.dumps(asdict(proof), sort_keys=True).encode()).hexdigest() if proof else ""

    def result(disposition, actions, reasons):
        return ActionPlan(path, disposition, tuple(actions), tuple(reasons), owners, labels,
                          graph.revision.revision_id, evidence.digest, regen_digest)

    roots = (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Installer"),
             os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Package Cache"))
    if any(path_intersects(path, root) for root in roots):
        return result(CleanupDisposition.PROTECTED, (ActionKind.KEEP,), ("SERVICEABILITY_DEPENDENCY_PRESENT",))
    protective = [e for e in edges if e.edge_type in _PROTECTIVE_EDGES
                  or e.lifecycle_hint in {"APP_ACTIVE_REQUIRED", "APP_BROKEN_REQUIRED", "REPO_ACTIVE"}]
    if protective or (judgment and judgment.disposition is CleanupDisposition.PROTECTED):
        reasons = []
        actions = [ActionKind.KEEP]
        if any(e.owner_kind == "APPLICATION" for e in protective):
            reasons.append("APP_DEPENDENCY_PRESENT")
            actions += [ActionKind.REPAIR_APPLICATION, ActionKind.UNINSTALL_APPLICATION]
        if any(e.edge_type in {"SERVICEABILITY_REQUIRES", "UPDATES_THROUGH", "UNINSTALLS_THROUGH"}
               or e.lifecycle_hint == "APP_BROKEN_REQUIRED" for e in protective):
            reasons.append("SERVICEABILITY_DEPENDENCY_PRESENT")
        if any(e.owner_kind == "REPOSITORY" for e in protective):
            reasons.append("REPOSITORY_UNIQUE_WORK_PRESENT")
        return result(CleanupDisposition.PROTECTED, actions, reasons or ["PROTECTIVE_DEPENDENCY_PRESENT"])
    if not evidence.fresh():
        return result(CleanupDisposition.UNKNOWN, (ActionKind.INVESTIGATE_ORPHAN,), ("OWNERSHIP_INCOMPLETE_OR_STALE",))
    # Unrecognized edges cannot silently become an owner-specific contract.
    if not owners or any(not e.owner_id or not e.lifecycle_hint or not e.evidence_source
                         or e.confidence != "strong" for e in edges):
        return result(CleanupDisposition.UNKNOWN, (ActionKind.INVESTIGATE_ORPHAN,), ("UNKNOWN_OWNERSHIP",))
    if len(owners) > 1:
        return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.KEEP,), ("SHARED_DEPENDENCY_UNRESOLVED",))
    if any(e.owner_kind == "REPOSITORY" for e in edges):
        if proof and all(e.lifecycle_hint == "REPO_GENERATED_OUTPUT" for e in edges):
            return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.CLEAN_GENERATED_OUTPUT,), ("SEMANTIC_ACTION_REQUIRED",))
        return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.KEEP, ActionKind.ARCHIVE_OR_REMOVE_REPOSITORY), ("SEMANTIC_ACTION_REQUIRED",))
    if any(e.owner_kind == "APPLICATION" for e in edges):
        if proof and all(e.lifecycle_hint == "APP_CACHE_REGENERABLE" for e in edges):
            return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.CLEAN_CACHE,), ("SEMANTIC_ACTION_REQUIRED",))
        return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.INVESTIGATE_ORPHAN,), ("REGENERATION_PROOF_MISSING",))
    generated = all(e.owner_kind == "GENERATED_OUTPUT" and e.edge_type == "GENERATED_FROM"
                    and e.lifecycle_hint == "REGENERABLE_ARTIFACT" for e in edges)
    if not generated or not proof:
        return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.INVESTIGATE_ORPHAN,), ("REGENERATION_PROOF_MISSING",))
    if not proof.raw_delete_allowed:
        return result(CleanupDisposition.HUMAN_REVIEW, (ActionKind.CLEAN_GENERATED_OUTPUT,), ("SEMANTIC_ACTION_REQUIRED",))
    return result(CleanupDisposition.RECLAIM_PROVEN, (ActionKind.RAW_DELETE_REGENERABLE_ARTIFACT,), ())


def admit_cleanup_disposition(disposition: CleanupDisposition, plan: ActionPlan) -> CleanupDisposition:
    """Ownership may downgrade existing classification, never promote it."""
    if disposition is CleanupDisposition.PROTECTED or plan.disposition is CleanupDisposition.PROTECTED:
        return CleanupDisposition.PROTECTED
    if disposition is CleanupDisposition.RECLAIM_PROVEN and not plan.raw_delete_eligible:
        return plan.disposition
    return disposition
