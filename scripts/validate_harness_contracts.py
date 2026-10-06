#!/usr/bin/env python3
"""Validate FileSteward P01 harness contracts without third-party dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "harness" / "contracts"
REGISTRY = ROOT / "harness" / "artifact-registry.v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_thresholds(metric_name: str, spec: dict, errors: list[str]) -> None:
    values = spec.get("development_defaults", {})
    try:
        careful = float(values["careful"])
        warning = float(values["warning"])
        critical = float(values["critical"])
    except (KeyError, TypeError, ValueError):
        errors.append(f"{metric_name}: missing numeric careful/warning/critical defaults")
        return
    direction = spec.get("direction")
    if direction == "high_is_bad" and not (careful < warning < critical):
        errors.append(f"{metric_name}: expected careful < warning < critical")
    elif direction == "low_is_bad" and not (critical < warning < careful):
        errors.append(f"{metric_name}: expected critical < warning < careful")
    elif direction not in {"high_is_bad", "low_is_bad"}:
        errors.append(f"{metric_name}: unsupported direction {direction!r}")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contracts = root / "harness" / "contracts"
    health = _load(contracts / "system-health-snapshot.v1.json")
    schedule = _load(contracts / "housekeeping-schedule.v1.json")
    interaction = _load(contracts / "interaction-scene-acceptance.v1.json")
    registry = _load(root / "harness" / "artifact-registry.v1.json")

    if health.get("schema_version") != "filesteward.system-health-snapshot/v1":
        errors.append("system-health-snapshot schema_version mismatch")
    for name, spec in health.get("metrics", {}).items():
        _check_thresholds(name, spec, errors)
    if health.get("authority", {}).get("may_delete") is not False:
        errors.append("health observer must not delete")
    if health.get("authority", {}).get("may_change_cleanup_disposition") is not False:
        errors.append("health observer must not promote cleanup disposition")

    profiles = schedule.get("profiles", {})
    if profiles.get("development", {}).get("enabled_by_default") is not True:
        errors.append("development recurring housekeeping must default enabled for current product-development profile")
    if profiles.get("product", {}).get("enabled_by_default") is not False:
        errors.append("public product recurring housekeeping must remain opt-in")
    allowed = set(schedule.get("actions", {}).get("allowed", []))
    forbidden = set(schedule.get("actions", {}).get("forbidden", []))
    if "PERMANENT_DELETE" in allowed or "PERMANENT_DELETE" not in forbidden:
        errors.append("PERMANENT_DELETE must be forbidden by the schedule contract")
    if not {"SCAN", "RECOMMEND", "QUARANTINE_APPROVED"} <= allowed:
        errors.append("schedule allowed actions are incomplete")

    required_surfaces = {
        "brand_title", "decision_map_title", "metric_observed_storage",
        "metric_baseline_free_space", "metric_projected_reclaim",
        "metric_target_free_space", "metric_authorization_state",
        "status_unknown", "status_human_review", "status_unapproved",
        "status_protected", "camera_controls", "decision_path_steps",
        "footer_ticker", "favicon", "health_warning",
    }
    actual = set(interaction.get("surfaces", {}))
    missing = sorted(required_surfaces - actual)
    if missing:
        errors.append("interaction acceptance missing surfaces: " + ", ".join(missing))
    invariants = set(interaction.get("global_invariants", []))
    for required in {
        "environment_is_tutorial", "cursor_and_legend_are_topmost",
        "hover_focus_touch_semantics_converge", "no_color_only_meaning",
        "no_native_browser_title_tooltips",
    }:
        if required not in invariants:
            errors.append(f"interaction acceptance missing invariant: {required}")

    for artifact in registry.get("artifacts", []):
        path = root / artifact["path"]
        if not path.is_file():
            errors.append(f"registry path missing: {artifact['path']}")
    if not any(
        x.get("name") == "Prompt Scratch Agent Reliability Event Ledger"
        and "do not create a second" in x.get("duplication_rule", "")
        for x in registry.get("external_authorities", [])
    ):
        errors.append("registry must preserve the external reliability-ledger authority boundary")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: FileSteward P01 harness contracts are coherent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
