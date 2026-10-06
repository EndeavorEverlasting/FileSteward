"""Executable call-stack prototypes for local housekeeping settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesteward.housekeeping_settings import (
    ALLOWED_ACTIONS,
    FORBIDDEN_ACTIONS,
    HousekeepingAuthorityError,
    HousekeepingProfile,
    HousekeepingSettingsService,
    InMemorySchedulerPort,
    InMemorySettingsStore,
    default_settings_for_profile,
    load_schedule_policy,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_CONTRACT = ROOT / "harness" / "contracts" / "housekeeping-schedule.v1.json"


def test_schedule_policy_matches_module_constants() -> None:
    policy = load_schedule_policy(SCHEDULE_CONTRACT)
    assert set(policy["actions"]["allowed"]) == set(ALLOWED_ACTIONS)
    assert set(policy["actions"]["forbidden"]) == set(FORBIDDEN_ACTIONS)


def test_apply_settings_success_stack_persists_and_plans_without_registering() -> None:
    store = InMemorySettingsStore()
    scheduler = InMemorySchedulerPort()
    service = HousekeepingSettingsService(
        store=store,
        scheduler=scheduler,
        profile=HousekeepingProfile.PRODUCT,
    )

    result = service.apply_settings(enabled=True, cadence="daily_idle")

    assert result.settings.enabled is True
    assert result.settings.cadence == "daily_idle"
    assert result.store_revision == 1
    assert store.load() == result.settings
    assert result.planned_task.registered is False
    assert result.planned_task.enabled is True
    assert scheduler.calls == [result.settings]


def test_forbidden_action_failure_stack_leaves_store_and_scheduler_untouched() -> None:
    store = InMemorySettingsStore()
    scheduler = InMemorySchedulerPort()
    service = HousekeepingSettingsService(store=store, scheduler=scheduler)
    baseline = service.apply_settings(enabled=True, cadence="weekly_idle")
    scheduler.calls.clear()

    with pytest.raises(HousekeepingAuthorityError, match="PERMANENT_DELETE"):
        service.request_action("PERMANENT_DELETE")
    with pytest.raises(HousekeepingAuthorityError, match="SELF_APPROVE"):
        service.request_action("SELF_APPROVE")
    with pytest.raises(HousekeepingAuthorityError, match="PROMOTE_EVIDENCE"):
        service.request_action("PROMOTE_EVIDENCE")

    assert store.load() == baseline.settings
    assert scheduler.calls == []


def test_disabled_settings_reject_wake_without_raising_authority_error() -> None:
    service = HousekeepingSettingsService(
        store=InMemorySettingsStore(),
        scheduler=InMemorySchedulerPort(),
        profile=HousekeepingProfile.PRODUCT,
    )
    assert default_settings_for_profile(HousekeepingProfile.PRODUCT).enabled is False
    denied = service.request_action("SCAN")
    assert denied.accepted is False
    assert "disabled" in denied.reason


def test_scan_wake_accepted_when_enabled_but_quarantine_still_gated() -> None:
    service = HousekeepingSettingsService(
        store=InMemorySettingsStore(),
        scheduler=InMemorySchedulerPort(),
        profile=HousekeepingProfile.DEVELOPMENT,
    )
    service.apply_settings(enabled=True, cadence="daily_idle")

    scan = service.request_action("SCAN")
    quarantine = service.request_action("QUARANTINE_APPROVED")

    assert scan.accepted is True
    assert quarantine.accepted is False
    assert "approval" in quarantine.reason.lower()
