"""Read-only, evidence-first FileSteward stewardship cycle.

A scheduled cycle *issues typed work orders*, not shell commands or mutation
authority. Existing inventory dispositions remain authoritative safety floors.
No file contents, source data, or external models are accessed here.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Mapping, Sequence

POLICY_VERSION = "filesteward.steward-program/v1"
TICKET_VERSION = "filesteward.steward-work-item/v1"
FACETS = ("app_experience", "personal_value", "activity", "lifecycle")
DISPOSITIONS = frozenset(
    ("RECLAIM_PROVEN", "HUMAN_REVIEW", "PROTECTED", "KEEP_PROVEN", "UNKNOWN")
)
KINDS = {
    ".exe": "INSTALLER", ".msi": "INSTALLER", ".msix": "INSTALLER",
    ".zip": "OTHER", ".7z": "OTHER",
    ".pdf": "RECORD", ".doc": "RECORD", ".docx": "RECORD",
    ".msg": "RECORD", ".eml": "RECORD", ".xlsx": "RECORD",
    ".csv": "RECORD", ".json": "RECORD",
    ".png": "MEDIA", ".jpg": "MEDIA", ".jpeg": "MEDIA",
    ".gif": "MEDIA", ".mp4": "MEDIA", ".mov": "MEDIA",
    ".wav": "MEDIA", ".mp3": "MEDIA", ".psd": "MEDIA",
    ".crdownload": "PARTIAL", ".part": "PARTIAL",
}


def _observed_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _proven(observation: Mapping[str, Any], states: tuple[str, ...]) -> bool:
    return (
        observation.get("state") in states
        and observation.get("source") in ("WINDOWS_ADAPTER", "GIT_ADAPTER", "OPERATOR_DECLARATION")
        and isinstance(observation.get("evidence_ref"), str)
        and bool(observation["evidence_ref"].strip())
    )


def _ticket(scan_id: str, item_id: str, lane: str, reason: str) -> dict[str, Any]:
    raw = f"{POLICY_VERSION}|{scan_id}|{item_id}|{lane}"
    token = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return {
        "schema_version": TICKET_VERSION,
        "work_id": f"steward-{token}",
        "source_scan": scan_id,
        "item_id": item_id,
        "lane": lane,
        "reason": reason,
        "state": "BLOCKED_ADAPTER",
        "owner": "FileSteward",
        "capability_required": lane,
        "authority": "READ_ONLY_OR_ADVISORY",
        "result_required": "TYPED_EVIDENCE_RECEIPT_AND_REOBSERVATION",
        "source_mutation_authorized": False,
        "agent_dispatched": False,
        "retry_count": 0,
    }


def classify_item(
    row: Mapping[str, str],
    evidence: Mapping[str, Any],
    *,
    scan_id: str,
    now: datetime,
    stale_days: int = 90,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Classify knowledge gaps; never grant a new cleanup disposition.

    External assertions cannot declassify an upstream PROTECTED/UNKNOWN item.
    The supplemental evidence is for context and protection, NOT deletion approval.
    """
    item_id = row.get("item_id", "")
    if not item_id or not isinstance(item_id, str):
        raise ValueError("inventory item_id required")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if stale_days <= 0:
        raise ValueError("stale_days must be positive")
    raw_disposition = row.get("disposition", "")
    if raw_disposition not in DISPOSITIONS:
        raise ValueError(f"invalid input disposition on {item_id}")
    observed = _observed_value(evidence)
    ownership = _observed_value(observed.get("ownership"))
    activity = _observed_value(observed.get("activity"))
    memory = _observed_value(observed.get("memorabilia"))
    archival = _observed_value(observed.get("archival"))
    path = str(row.get("path") or "")
    if not path:
        raise ValueError("inventory path required")
    filename = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    kind = KINDS.get("." + filename.rsplit(".", 1)[-1], "OTHER") if "." in filename else "OTHER"
    if filename == ".git" or filename.endswith(".git"):
        kind = "REPOSITORY"
    flags = tuple(k for k in ("is_symlink", "is_reparse_point", "is_cloud_placeholder")
                  if str(row.get(k, "")).lower() in ("true", "1"))
    incomplete = row.get("scan_completeness") != "COMPLETE"
    unsafe_shape = bool(flags) or incomplete or kind == "PARTIAL"
    app = "OWNER_UNRESOLVED"
    if _proven(ownership, ("APP_REQUIRED", "APP_BROKEN_SERVICEABILITY",
                          "APP_REGENERABLE_CACHE", "NOT_ATTRIBUTED_AFTER_COMPLETE_ADAPTERS")):
        app = str(ownership["state"])
    personal = "VALUE_UNRESOLVED"
    if _proven(memory, ("OPERATOR_MARKED_MEMORABILIA", "OPERATOR_MARKED_NOT_MEMORABILIA")):
        if memory.get("source") == "OPERATOR_DECLARATION":
            personal = str(memory["state"])
    elif kind == "MEDIA":
        personal = "POTENTIAL_MEMORABILIA"
    modified = row.get("modified_at", "")
    age_days: int | None = None
    try:
        age = (now.timestamp() - float(modified)) / 86400
        if age >= 0 and age < 100000:
            age_days = int(age)
    except (TypeError, ValueError, OverflowError):
        pass
    recency = "ACTIVITY_UNRESOLVED"
    if _proven(activity, ("ACTIVE_REFERENCE", "NO_REFERENCE_FOUND_COMPLETE")):
        recency = ("ACTIVE_PROVEN" if activity["state"] == "ACTIVE_REFERENCE"
                   else "NO_CURRENT_REFERENCE_OBSERVED")
    elif age_days is not None and age_days >= stale_days:
        recency = "LAST_MODIFIED_OLD"
    lifecycle = "LIFECYCLE_UNRESOLVED"
    if app in ("APP_REQUIRED", "APP_BROKEN_SERVICEABILITY") or recency == "ACTIVE_PROVEN":
        lifecycle = "ACTIVE_REQUIRED"
    elif _proven(archival, ("USER_DECLARED_ARCHIVE",)) and archival.get("source") == "OPERATOR_DECLARATION":
        lifecycle = "USER_DECLARED_ARCHIVE"
    elif age_days is not None and age_days >= stale_days:
        lifecycle = "DORMANCY_CANDIDATE_REVIEW"
    # The most protective existing disposition remains the safety floor.
    floor = "UNKNOWN" if unsafe_shape else raw_disposition
    if app in ("APP_REQUIRED", "APP_BROKEN_SERVICEABILITY") or recency == "ACTIVE_PROVEN":
        floor = "PROTECTED"
    if personal == "OPERATOR_MARKED_MEMORABILIA":
        floor = "PROTECTED"
    if raw_disposition == "PROTECTED":
        floor = "PROTECTED"
    if raw_disposition == "UNKNOWN" and floor != "PROTECTED":
        floor = "UNKNOWN"
    reasons: list[str] = []
    lanes: list[str] = []
    if unsafe_shape:
        lanes.append("ADAPTER_SCAN_COMPLETENESS")
        reasons.append("incomplete, partial, or redirected item; no traversal/actuation")
    if app == "OWNER_UNRESOLVED":
        lanes.append("ADAPTER_APP_REPO_ATTRIBUTION")
        reasons.append("missing current complete application/repository ownership attribution")
    if recency in ("ACTIVITY_UNRESOLVED", "LAST_MODIFIED_OLD"):
        lanes.append("ADAPTER_ACTIVITY_EVIDENCE")
        reasons.append("file modification time does not prove last access or active dependency")
    if personal == "POTENTIAL_MEMORABILIA":
        lanes.append("AGENT_PERSONAL_VALUE_CONTEXT")
        reasons.append("media/creative cue is not a determination of sentimental value")
    if lifecycle == "DORMANCY_CANDIDATE_REVIEW" and personal != "OPERATOR_MARKED_MEMORABILIA":
        lanes.append("AGENT_DORMANCY_ARCHIVE_INTENT")
        reasons.append("dormancy and archive intent require evidence/operator declaration")
    if raw_disposition == "HUMAN_REVIEW" and not lanes:
        lanes.append("AGENT_RULE_GAP_REVIEW")
        reasons.append("upstream human review not resolved by evidence")
    tickets = [_ticket(scan_id, item_id, lane, reason) for lane, reason in zip(lanes, reasons)]
    result = {
        "schema_version": "filesteward.steward-classification/v1",
        "item_id": item_id,
        "source_disposition": raw_disposition,
        "safety_floor": floor,
        "facets": {
            "app_experience": app,
            "personal_value": personal,
            "activity": recency,
            "lifecycle": lifecycle,
            "artifact_kind": kind,
        },
        "last_modified_age_days": age_days,
        "last_access_verified": recency == "ACTIVE_PROVEN",
        "authorizes_move_or_delete": False,
        "unresolved_facets": [
            f for f, state in (("app_experience", app), ("personal_value", personal),
                               ("activity", recency), ("lifecycle", lifecycle))
            if state in ("OWNER_UNRESOLVED", "VALUE_UNRESOLVED", "POTENTIAL_MEMORABILIA",
                         "ACTIVITY_UNRESOLVED", "LAST_MODIFIED_OLD",
                         "LIFECYCLE_UNRESOLVED", "DORMANCY_CANDIDATE_REVIEW")
        ],
    }
    return result, tickets


def build_cycle(
    rows: Sequence[Mapping[str, str]],
    evidence_by_id: Mapping[str, Any],
    *,
    scan_id: str,
    now: datetime,
    max_items: int = 250,
    max_tickets: int = 40,
    unobserved_input_count: int = 0,
) -> dict[str, Any]:
    if not scan_id or "/" in scan_id or "\\" in scan_id or not max_items > 0 or not max_tickets > 0 or unobserved_input_count < 0:
        raise ValueError("invalid bounded cycle configuration")
    if len(rows) > max_items:
        # Deliberately never claim a partial scan as complete.
        limit_exceeded = len(rows) - max_items + unobserved_input_count
    else:
        limit_exceeded = unobserved_input_count
    classifications: list[dict[str, Any]] = []
    tickets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows[:max_items]:
        if row.get("item_id") in seen_ids:
            raise ValueError("duplicate inventory item_id; refusing ambiguous receipts")
        seen_ids.add(row["item_id"])
        cls, proposals = classify_item(row, _observed_value(evidence_by_id.get(row["item_id"])),
                                       scan_id=scan_id, now=now)
        classifications.append(cls)
        # De-duplicate tickets and enforce a strict bounded outbox.
        for proposal in proposals[:3]:
            if len(tickets) < max_tickets:
                tickets.append(proposal)
    unresolved = [row for row in classifications if row["unresolved_facets"]]
    facet_counts = dict(Counter(f for item in unresolved for f in item["unresolved_facets"]))
    return {
        "schema_version": "filesteward.steward-cycle/v1",
        "policy_version": POLICY_VERSION,
        "source_scan": scan_id,
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "coverage": {
            "observed_items": len(classifications),
            "unobserved_budget_items": limit_exceeded,
            "coverage_state": "INCOMPLETE_BUDGET" if limit_exceeded else "OBSERVED_INPUT",
            "unresolved_items": len(unresolved),
            "unresolved_facets": facet_counts,
            "queue_items": len(tickets),
            "agent_executions": 0,
            "source_mutations": 0,
        },
        "classified": classifications,
        "unresolved": unresolved,
        "work_items": tickets,
    }
