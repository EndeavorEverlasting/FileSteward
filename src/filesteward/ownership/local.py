"""Deterministic, read-only lifecycle evaluation for ordinary local assets.

This module does not discover or inspect user files. It consumes typed,
provenance-bearing adapter/operator evidence; classification is never a
cleanup plan, deletion approval, or permission to mutate source data.

Run: python -m filesteward.ownership.local --evidence-file <ignored-runtime-json>
     python -m filesteward.ownership.local --example
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import sys
from typing import Any, Mapping, Optional, Sequence

from filesteward.models import CleanupDisposition

SCHEMA_VERSION = "filesteward.local-asset-evidence/v1"


class LocalIdentity(str, Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    PERSONAL_RECORD = "PERSONAL_RECORD"
    USER_PROJECT = "USER_PROJECT"
    LEARNING = "LEARNING"
    REFERENCE = "REFERENCE"
    GENERATED = "GENERATED"
    OTHER_LOCAL = "OTHER_LOCAL"


class Attribution(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    VERIFIED_USER_LOCAL = "VERIFIED_USER_LOCAL"
    OTHER_OWNER_PRESENT = "OTHER_OWNER_PRESENT"
    CONFLICTING = "CONFLICTING"


class Intent(str, Enum):
    UNDECLARED = "UNDECLARED"
    KEEP = "KEEP"
    DORMANT = "DORMANT"
    ARCHIVE_REVIEW = "ARCHIVE_REVIEW"
    LEGACY_REVIEW = "LEGACY_REVIEW"
    REMOVE_REVIEW = "REMOVE_REVIEW"


class LocalLifecycle(str, Enum):
    ACTIVE = "ACTIVE"
    STABLE = "STABLE"
    DORMANT = "DORMANT"
    LEGACY_CANDIDATE = "LEGACY_CANDIDATE"
    UNRESOLVED = "UNRESOLVED"


class LocalRoute(str, Enum):
    KEEP = "KEEP"
    RESOLVE_ATTRIBUTION = "RESOLVE_ATTRIBUTION"
    RESOLVE_DEPENDENCIES = "RESOLVE_DEPENDENCIES"
    RESOLVE_RECOVERABILITY = "RESOLVE_RECOVERABILITY"
    RESOLVE_UNIQUE_WORK = "RESOLVE_UNIQUE_WORK"
    REVIEW_RETENTION = "REVIEW_RETENTION"
    REVIEW_ARCHIVE = "REVIEW_ARCHIVE"
    REVIEW_REMOVAL = "REVIEW_REMOVAL"


@dataclass(frozen=True)
class LocalAssetEvidence:
    path: str
    identity: LocalIdentity = LocalIdentity.UNCLASSIFIED
    attribution: Attribution = Attribution.UNRESOLVED
    intent: Intent = Intent.UNDECLARED
    adapters_complete: bool = False
    active_use: Optional[bool] = None
    unique_unbacked_work: Optional[bool] = None
    dependencies_resolved: Optional[bool] = None
    recoverable: Optional[bool] = None
    protected_by_policy: bool = False
    evidence_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        windows = PureWindowsPath(self.path)
        posix = PurePosixPath(self.path)
        if not self.path.strip() or not (windows.is_absolute() or posix.is_absolute()):
            raise ValueError("path must be a non-empty absolute path")
        if ".." in self.path.replace("\\", "/").split("/"):
            raise ValueError("path must be normalized without traversal")
        for field_name in (
            "adapters_complete", "active_use", "unique_unbacked_work",
            "dependencies_resolved", "recoverable", "protected_by_policy",
        ):
            value = getattr(self, field_name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"{field_name} must be boolean or null")
        if self.adapters_complete and (
            self.attribution is Attribution.VERIFIED_USER_LOCAL
            and not self.evidence_sources
        ):
            raise ValueError("verified local attribution needs explicit evidence_sources")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.evidence_sources):
            raise ValueError("evidence_sources must contain nonempty provenance strings")


@dataclass(frozen=True)
class LocalAssetAssessment:
    path: str
    identity: LocalIdentity
    attribution: Attribution
    lifecycle: LocalLifecycle
    disposition: CleanupDisposition
    route: LocalRoute
    reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    evidence_revision: str
    removal_candidate_review_only: bool = False
    mutation_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "filesteward.local-asset-assessment/v1",
            "path": self.path,
            "identity": self.identity.value,
            "attribution": self.attribution.value,
            "lifecycle": self.lifecycle.value,
            "disposition": self.disposition.value,
            "route": self.route.value,
            "reasons": list(self.reasons),
            "missing_evidence": list(self.missing_evidence),
            "evidence_revision": self.evidence_revision,
            "removal_candidate_review_only": self.removal_candidate_review_only,
            "mutation_authorized": False,
        }


def _revision(evidence: LocalAssetEvidence) -> str:
    blob = json.dumps(asdict(evidence), sort_keys=True, separators=(",", ":"))
    return "local-evidence-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def classify_local_asset(evidence: LocalAssetEvidence) -> LocalAssetAssessment:
    """Separate identity, lifecycle, disposition and review route.

    Fail-closed:
    * structural/policy protection, active use and unique unbacked work win;
    * an unknown owner cannot be promoted to a legacy or removal candidate;
    * 'dormant' requires explicit user intent, never age or inactivity alone;
    * legacy/removal review requires verified local scope, complete adapters,
      explicit negative active/unique signals, resolved dependencies,
      and proven recovery.
    * no result ever sets RECLAIM_PROVEN or grants mutation authority.
    """

    revision = _revision(evidence)
    def result(
        lifecycle: LocalLifecycle, disposition: CleanupDisposition,
        route: LocalRoute, *reasons: str,
        missing: tuple[str, ...] = (), removal: bool = False,
    ) -> LocalAssetAssessment:
        return LocalAssetAssessment(
            path=evidence.path, identity=evidence.identity,
            attribution=evidence.attribution, lifecycle=lifecycle,
            disposition=disposition, route=route,
            reasons=tuple(reasons), missing_evidence=missing,
            evidence_revision=revision, removal_candidate_review_only=removal,
        )

    if evidence.protected_by_policy:
        return result(LocalLifecycle.ACTIVE if evidence.active_use is True
                      else LocalLifecycle.UNRESOLVED,
                      CleanupDisposition.PROTECTED, LocalRoute.KEEP,
                      "EXPLICIT_OR_STRUCTURAL_PROTECTION")
    if evidence.attribution in (Attribution.CONFLICTING, Attribution.OTHER_OWNER_PRESENT):
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.PROTECTED,
                      LocalRoute.RESOLVE_ATTRIBUTION, "NONLOCAL_OR_CONFLICTING_OWNER")
    if evidence.active_use is True:
        return result(LocalLifecycle.ACTIVE, CleanupDisposition.PROTECTED,
                      LocalRoute.KEEP, "POSITIVE_ACTIVE_USE")
    if evidence.unique_unbacked_work is True:
        return result(LocalLifecycle.ACTIVE, CleanupDisposition.PROTECTED,
                      LocalRoute.KEEP, "UNBACKED_UNIQUE_WORK")
    if evidence.intent is Intent.KEEP:
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.KEEP_PROVEN,
                      LocalRoute.KEEP, "OPERATOR_DECLARED_KEEP")
    if evidence.attribution is not Attribution.VERIFIED_USER_LOCAL or not evidence.adapters_complete:
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.UNKNOWN,
                      LocalRoute.RESOLVE_ATTRIBUTION, "INCOMPLETE_LOCAL_ATTRIBUTION",
                      missing=("complete_owner_adapters", "verified_user_local"))
    if evidence.active_use is None:
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.UNKNOWN,
                      LocalRoute.REVIEW_RETENTION, "ACTIVE_USE_UNOBSERVED",
                      missing=("active_use",))
    if evidence.unique_unbacked_work is None:
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.UNKNOWN,
                      LocalRoute.RESOLVE_UNIQUE_WORK, "UNIQUE_CONTENT_UNRESOLVED",
                      missing=("unique_unbacked_work",))
    if evidence.dependencies_resolved is not True:
        return result(LocalLifecycle.UNRESOLVED, CleanupDisposition.HUMAN_REVIEW,
                      LocalRoute.RESOLVE_DEPENDENCIES, "DEPENDENCIES_UNRESOLVED",
                      missing=("dependencies_resolved",))
    # The path is locally attributed, not active, and has no currently
    # demonstrated unique unbacked work/dependency. Retention still matters.
    if evidence.intent is Intent.DORMANT:
        return result(LocalLifecycle.DORMANT, CleanupDisposition.KEEP_PROVEN,
                      LocalRoute.KEEP, "EXPLICIT_DORMANT_RETENTION")
    if evidence.intent in (
        Intent.ARCHIVE_REVIEW, Intent.LEGACY_REVIEW, Intent.REMOVE_REVIEW
    ):
        if evidence.recoverable is not True:
            return result(LocalLifecycle.STABLE, CleanupDisposition.HUMAN_REVIEW,
                          LocalRoute.RESOLVE_RECOVERABILITY,
                          "RECOVERY_NOT_PROVEN", missing=("recoverable",))
        if evidence.intent is Intent.LEGACY_REVIEW:
            return result(LocalLifecycle.LEGACY_CANDIDATE,
                          CleanupDisposition.HUMAN_REVIEW, LocalRoute.REVIEW_ARCHIVE,
                          "OPERATOR_LEGACY_INTENT_AND_RECOVERY_EVIDENCE")
        if evidence.intent is Intent.REMOVE_REVIEW:
            return result(LocalLifecycle.STABLE, CleanupDisposition.HUMAN_REVIEW,
                          LocalRoute.REVIEW_REMOVAL, "REVIEW_ONLY_NOT_DELETE_AUTHORITY",
                          removal=True)
        return result(LocalLifecycle.STABLE, CleanupDisposition.HUMAN_REVIEW,
                      LocalRoute.REVIEW_ARCHIVE, "OPERATOR_ARCHIVE_REVIEW")
    return result(LocalLifecycle.STABLE, CleanupDisposition.HUMAN_REVIEW,
                  LocalRoute.REVIEW_RETENTION, "LOCAL_STABLE_VALUE_UNDECIDED")


_KEYS = frozenset(f.name for f in LocalAssetEvidence.__dataclass_fields__.values())
_BOOL_KEYS = frozenset({
    "adapters_complete", "active_use", "unique_unbacked_work",
    "dependencies_resolved", "recoverable", "protected_by_policy",
})
_ENUMS = {"identity": LocalIdentity, "attribution": Attribution, "intent": Intent}


def parse_local_evidence(raw: Mapping[str, Any]) -> LocalAssetEvidence:
    """Strict v1 parser. Unknown properties cannot become policy controls."""

    if not isinstance(raw, Mapping):
        raise ValueError("evidence root must be an object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("expected schema_version " + SCHEMA_VERSION)
    unknown = set(raw) - _KEYS - {"schema_version"}
    if unknown:
        raise ValueError("unknown evidence fields: " + ", ".join(sorted(unknown)))
    if not isinstance(raw.get("path"), str):
        raise ValueError("path must be a string")
    kwargs: dict[str, Any] = {"path": raw["path"]}
    for key in _BOOL_KEYS:
        if key in raw:
            value = raw[key]
            if value is not None and type(value) is not bool:
                raise ValueError(f"{key} must be boolean or null")
            kwargs[key] = value
    for key, enum_type in _ENUMS.items():
        if key in raw:
            try:
                kwargs[key] = enum_type(raw[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid {key}: {raw[key]!r}") from exc
    if "evidence_sources" in raw:
        sources = raw["evidence_sources"]
        if not isinstance(sources, list) or not all(
            isinstance(ref, str) and ref.strip() for ref in sources
        ):
            raise ValueError("evidence_sources must be an array of provenance strings")
        kwargs["evidence_sources"] = tuple(sources)
    return LocalAssetEvidence(**kwargs)


def example_evidence() -> dict[str, Any]:
    """Synthetic example only; not a claim about any user's filesystem."""

    return {
        "schema_version": SCHEMA_VERSION,
        "path": "C:\\synthetic\\local\\archive-candidate",
        "identity": "USER_PROJECT",
        "attribution": "VERIFIED_USER_LOCAL",
        "intent": "LEGACY_REVIEW",
        "adapters_complete": True,
        "active_use": False,
        "unique_unbacked_work": False,
        "dependencies_resolved": True,
        "recoverable": True,
        "protected_by_policy": False,
        "evidence_sources": ["synthetic:operator_intent", "synthetic:adapter_proof"],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m filesteward.ownership.local",
        description="Read-only assessment of typed local-asset evidence",
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--evidence-file", help="JSON evidence in ignored local runtime")
    modes.add_argument("--example", action="store_true", help="print synthetic input only")
    args = parser.parse_args(argv)
    if args.example:
        print(json.dumps(example_evidence(), indent=2))
        return 0
    try:
        with open(args.evidence_file, "r", encoding="utf-8") as handle:
            evidence = parse_local_evidence(json.load(handle))
        print(json.dumps(classify_local_asset(evidence).to_dict(), indent=2))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print("local-asset-evidence: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
