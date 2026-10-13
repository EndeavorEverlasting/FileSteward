"""Read-only workstation performance history projection (decision support only).

Consumes filesteward.profiles load_latest / compare_latest (or the same
ignored var/profiles tree via injectable profiles_root). Never invents a
second authority: capacity CRITICAL/BELOW_TARGET remain visibility labels,
causal attribution stays NOT_ESTABLISHED unless profiles.compare_latest
already established otherwise, and projections always carry
authorization_state=OBSERVATION_ONLY with profile_provides_delete_authority
false.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from filesteward.profiles import ProfileError, compare_latest, load_latest

__all__ = [
    "PROJECTION_SCHEMA",
    "ProjectionError",
    "project_history",
    "render_plain_text",
    "main",
]

PROJECTION_SCHEMA = "filesteward.workstation-performance-projection/v1"

# Reused / aligned with profiles.compare_latest volume comparison_quality.
QUALITY_ROOT_MATCH = "ROOT_LABEL_MATCH_DEVICE_ID_UNVERIFIED"
QUALITY_NO_COMPARATOR = "NO_COMPARATOR"


class ProjectionError(ValueError):
    """Fail-closed projection refusal (invalid alias/history binding)."""


def _history_quality_from_comparison(comparison: dict[str, Any]) -> str:
    """Label same-alias history using per-volume comparison_quality language."""
    volumes = comparison.get("volumes") or []
    if not volumes:
        return "NO_COMPARABLE_VOLUMES"
    qualities = [row.get("comparison_quality") for row in volumes]
    if all(q == QUALITY_ROOT_MATCH for q in qualities):
        return "SAME_ALIAS_SAME_VOLUME_ROOT_LABEL"
    if any(q == QUALITY_ROOT_MATCH for q in qualities):
        return "PARTIAL_VOLUME_OVERLAP"
    return "NO_COMPARABLE_VOLUMES"


def _volume_rows(
    latest: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Project latest volumes with optional compare_latest fields; no promotion."""
    by_root: dict[str, dict[str, Any]] = {}
    if comparison is not None:
        for row in comparison.get("volumes") or []:
            root = row.get("declared_root")
            if isinstance(root, str):
                by_root[root] = row

    projected: list[dict[str, Any]] = []
    for row in (latest.get("observation") or {}).get("volumes") or []:
        root = row.get("declared_root")
        if not isinstance(root, str):
            continue
        status = row.get("capacity_status")
        compared = by_root.get(root)
        projected.append(
            {
                "declared_root": root,
                "free_pct": row.get("free_pct"),
                "capacity_status": status,
                "capacity_status_role": "VISIBILITY_ONLY",
                "action_authorization": row.get("action_authorization", "NONE"),
                "previous_free_pct": (
                    compared.get("previous_free_pct") if compared else None
                ),
                "change_free_percentage_points": (
                    compared.get("change_free_percentage_points") if compared else None
                ),
                "comparison_quality": (
                    compared.get("comparison_quality")
                    if compared
                    else QUALITY_NO_COMPARATOR
                ),
                # Explicit: never promote capacity pressure into reclaim/action.
                "reclaim_or_action_state": None,
            }
        )
    return projected


def project_history(
    alias: str,
    *,
    profiles_root: Path | None = None,
) -> dict[str, Any]:
    """Build a structured read-only projection for one host alias.

    profiles_root is injectable for synthetic tests; production callers omit
    it so profiles resolve under the ignored runtime var/profiles tree.
    """
    try:
        latest = load_latest(alias, profiles_root=profiles_root)
    except ProfileError as exc:
        raise ProjectionError(str(exc)) from exc

    if latest.get("profile_provides_delete_authority") is not False:
        raise ProjectionError("unsafe snapshot authority marker")
    if latest.get("authorization_state") != "OBSERVATION_ONLY":
        raise ProjectionError("snapshot is not observation-only")

    comparison: dict[str, Any] | None = None
    history_quality = "INSUFFICIENT_HISTORY"
    # Default: do not invent causality. Pass through only when compare_latest
    # already established a value (today always NOT_ESTABLISHED).
    causal_attribution = "NOT_ESTABLISHED"
    try:
        comparison = compare_latest(alias, profiles_root=profiles_root)
    except ProfileError as exc:
        message = str(exc)
        if "two snapshots" in message or "no captured snapshots" in message:
            history_quality = "INSUFFICIENT_HISTORY"
        else:
            raise ProjectionError(message) from exc
    else:
        if comparison.get("authorization_state") != "OBSERVATION_ONLY":
            raise ProjectionError("comparison is not observation-only")
        established = comparison.get("causal_attribution", "NOT_ESTABLISHED")
        causal_attribution = (
            established if isinstance(established, str) and established else "NOT_ESTABLISHED"
        )
        history_quality = _history_quality_from_comparison(comparison)

    return {
        "schema_version": PROJECTION_SCHEMA,
        "alias": alias,
        "authorization_state": "OBSERVATION_ONLY",
        "profile_provides_delete_authority": False,
        "causal_attribution": causal_attribution,
        "history_quality": history_quality,
        "latest_snapshot_id": latest.get("snapshot_id"),
        "previous_snapshot_id": (
            comparison.get("previous_snapshot_id") if comparison else None
        ),
        "current_snapshot_id": (
            comparison.get("current_snapshot_id") if comparison else None
        ),
        "captured_utc": latest.get("captured_utc"),
        "volumes": _volume_rows(latest, comparison),
        "comparison": comparison,
        "decision_support": {
            "role": "HISTORY_AND_CAPACITY_VISIBILITY",
            "delete_authority": False,
            "capacity_statuses_are_actionable": False,
            "notes": (
                "Projection summarizes same-alias profile history for operator "
                "decision support. Capacity CRITICAL and BELOW_TARGET are "
                "visibility labels only; they do not authorize reclaim, scan, "
                "or deletion. Use the repository-owned exact-manifest path for "
                "any destructive action."
            ),
        },
    }


def render_plain_text(projection: dict[str, Any]) -> str:
    """Accessibility-minded plain text suitable for later UI / screen readers."""
    lines = [
        "FileSteward workstation performance projection",
        f"Schema: {projection.get('schema_version')}",
        f"Host alias: {projection.get('alias')}",
        f"Authorization: {projection.get('authorization_state')} "
        f"(profile_provides_delete_authority="
        f"{projection.get('profile_provides_delete_authority')})",
        f"Causal attribution: {projection.get('causal_attribution')}",
        f"History quality: {projection.get('history_quality')}",
        f"Latest snapshot: {projection.get('latest_snapshot_id')}",
        f"Captured (UTC): {projection.get('captured_utc')}",
        "",
        "Volumes (visibility only; not reclaim/action states):",
    ]
    volumes = projection.get("volumes") or []
    if not volumes:
        lines.append("  (none)")
    for row in volumes:
        change = row.get("change_free_percentage_points")
        change_text = "n/a" if change is None else f"{change:+.2f} pp"
        lines.append(
            f"  Root: {row.get('declared_root')}"
            f" | free_pct={row.get('free_pct')}"
            f" | status={row.get('capacity_status')} "
            f"({row.get('capacity_status_role')})"
            f" | comparison_quality={row.get('comparison_quality')}"
            f" | free_pct_change={change_text}"
            f" | reclaim_or_action_state={row.get('reclaim_or_action_state')}"
        )
    support = projection.get("decision_support") or {}
    notes = support.get("notes")
    if notes:
        lines.extend(["", "Decision support note:", notes])
    lines.append("")
    lines.append(
        "This projection does not approve, promote, or execute deletion."
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Repository-native projection entrypoint (read-only)."""
    parser = argparse.ArgumentParser(
        description=(
            "Read-only workstation performance history projection; "
            "never grants cleanup or delete authority"
        )
    )
    parser.add_argument("--host-key", required=True)
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=None,
        help="Optional profiles root (tests / explicit local tree)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Structured JSON (default) or accessibility plain text",
    )
    args = parser.parse_args(argv)
    try:
        projection = project_history(
            args.host_key,
            profiles_root=args.profiles_root,
        )
    except (ProjectionError, ProfileError, OSError, ValueError, TypeError) as exc:
        print("performance projection refused: " + str(exc), file=sys.stderr)
        return 2
    if args.format == "text":
        print(render_plain_text(projection), end="")
    else:
        print(json.dumps(projection, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
