"""Read-only performance projection: history quality and observation-only bounds."""
from __future__ import annotations

import json

import pytest

from filesteward.profiles import capture
from filesteward.visualization.performance import (
    PROJECTION_SCHEMA,
    ProjectionError,
    main,
    project_history,
    render_plain_text,
)


def _capture_pair(tmp_path, *, roots_first, roots_second, alias="LabHost"):
    """Append two synthetic snapshots under injectable profiles_root."""
    root = tmp_path / "profiles"
    volume = tmp_path / "vol"
    volume.mkdir()
    observations = iter(
        [
            {
                "volumes": [
                    {
                        "declared_root": r,
                        "free_pct": 22.0,
                        "capacity_status": "AT_OR_ABOVE_TARGET",
                        "action_authorization": "NONE",
                    }
                    for r in roots_first
                ],
                "metrics": {},
                "missing_metrics": [],
            },
            {
                "volumes": [
                    {
                        "declared_root": r,
                        "free_pct": 9.0,
                        "capacity_status": "CRITICAL",
                        "action_authorization": "NONE",
                    }
                    for r in roots_second
                ],
                "metrics": {},
                "missing_metrics": [],
            },
        ]
    )

    def synthetic(volumes, *, sample_seconds):
        return next(observations)

    capture(
        alias,
        [str(volume)],
        profiles_root=root,
        observer=synthetic,
        machine_binding="test\0lab",
    )
    capture(
        alias,
        [str(volume)],
        profiles_root=root,
        observer=synthetic,
        machine_binding="test\0lab",
    )
    return root, volume


def test_same_alias_same_volume_history_quality(tmp_path):
    volume = tmp_path / "C"
    volume.mkdir()
    root, _ = _capture_pair(
        tmp_path,
        roots_first=[str(volume)],
        roots_second=[str(volume)],
    )
    projection = project_history("LabHost", profiles_root=root)
    assert projection["schema_version"] == PROJECTION_SCHEMA
    assert projection["history_quality"] == "SAME_ALIAS_SAME_VOLUME_ROOT_LABEL"
    assert projection["volumes"][0]["comparison_quality"] == (
        "ROOT_LABEL_MATCH_DEVICE_ID_UNVERIFIED"
    )
    assert projection["causal_attribution"] == "NOT_ESTABLISHED"


def test_same_alias_unmatched_volume_quality(tmp_path):
    first = tmp_path / "A"
    second = tmp_path / "B"
    first.mkdir()
    second.mkdir()
    root = tmp_path / "profiles"
    observations = iter(
        [
            {
                "volumes": [
                    {
                        "declared_root": str(first),
                        "free_pct": 30.0,
                        "capacity_status": "AT_OR_ABOVE_TARGET",
                        "action_authorization": "NONE",
                    }
                ],
                "metrics": {},
                "missing_metrics": [],
            },
            {
                "volumes": [
                    {
                        "declared_root": str(second),
                        "free_pct": 12.0,
                        "capacity_status": "BELOW_TARGET",
                        "action_authorization": "NONE",
                    }
                ],
                "metrics": {},
                "missing_metrics": [],
            },
        ]
    )

    def synthetic(volumes, *, sample_seconds):
        return next(observations)

    capture(
        "LabHost",
        [str(first)],
        profiles_root=root,
        observer=synthetic,
        machine_binding="test\0lab",
    )
    capture(
        "LabHost",
        [str(second)],
        profiles_root=root,
        observer=synthetic,
        machine_binding="test\0lab",
    )
    projection = project_history("LabHost", profiles_root=root)
    assert projection["volumes"][0]["comparison_quality"] == "NO_COMPARATOR"
    assert projection["history_quality"] == "NO_COMPARABLE_VOLUMES"
    assert projection["volumes"][0]["change_free_percentage_points"] is None


def test_projection_is_observation_only_and_never_delete_authority(tmp_path):
    volume = tmp_path / "C"
    volume.mkdir()
    root, _ = _capture_pair(
        tmp_path,
        roots_first=[str(volume)],
        roots_second=[str(volume)],
    )
    projection = project_history("LabHost", profiles_root=root)
    assert projection["authorization_state"] == "OBSERVATION_ONLY"
    assert projection["profile_provides_delete_authority"] is False
    assert projection["decision_support"]["delete_authority"] is False
    assert projection["decision_support"]["capacity_statuses_are_actionable"] is False
    critical = projection["volumes"][0]
    assert critical["capacity_status"] == "CRITICAL"
    assert critical["capacity_status_role"] == "VISIBILITY_ONLY"
    assert critical["reclaim_or_action_state"] is None
    assert critical["action_authorization"] == "NONE"
    text = render_plain_text(projection)
    assert "OBSERVATION_ONLY" in text
    assert "profile_provides_delete_authority=False" in text
    assert "does not approve" in text
    assert "VISIBILITY_ONLY" in text
    # Must not invent reclaim language from CRITICAL.
    assert "RECLAIM" not in text
    assert "APPROVED" not in text


def test_single_snapshot_insufficient_history(tmp_path):
    root = tmp_path / "profiles"
    volume = tmp_path / "C"
    volume.mkdir()

    def synthetic(volumes, *, sample_seconds):
        return {
            "volumes": [
                {
                    "declared_root": str(volume),
                    "free_pct": 25.0,
                    "capacity_status": "AT_OR_ABOVE_TARGET",
                    "action_authorization": "NONE",
                }
            ],
            "metrics": {},
            "missing_metrics": [],
        }

    capture(
        "Solo",
        [str(volume)],
        profiles_root=root,
        observer=synthetic,
        machine_binding="test\0solo",
    )
    projection = project_history("Solo", profiles_root=root)
    assert projection["history_quality"] == "INSUFFICIENT_HISTORY"
    assert projection["comparison"] is None
    assert projection["authorization_state"] == "OBSERVATION_ONLY"
    assert projection["profile_provides_delete_authority"] is False
    assert projection["causal_attribution"] == "NOT_ESTABLISHED"
    assert projection["volumes"][0]["comparison_quality"] == "NO_COMPARATOR"


def test_cli_json_and_text(tmp_path, capsys):
    volume = tmp_path / "C"
    volume.mkdir()
    root, _ = _capture_pair(
        tmp_path,
        roots_first=[str(volume)],
        roots_second=[str(volume)],
    )
    assert main(["--host-key", "LabHost", "--profiles-root", str(root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authorization_state"] == "OBSERVATION_ONLY"
    assert payload["profile_provides_delete_authority"] is False
    assert main(
        [
            "--host-key",
            "LabHost",
            "--profiles-root",
            str(root),
            "--format",
            "text",
        ]
    ) == 0
    text = capsys.readouterr().out
    assert "NOT_ESTABLISHED" in text
    assert "SAME_ALIAS_SAME_VOLUME_ROOT_LABEL" in text


def test_missing_alias_refused(tmp_path):
    with pytest.raises(ProjectionError):
        project_history("MissingHost", profiles_root=tmp_path / "empty")
