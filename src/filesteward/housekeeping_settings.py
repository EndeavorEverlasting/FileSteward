"""Local/private housekeeping cadence settings — executable schedule seam.

Owns toggle/cadence validation and wake/run command classification only.
Does NOT register Windows tasks, approve cleanup, promote evidence, or
permanently delete. Permanent deletion remains forbidden.

Call stacks (success):
  OPERATOR toggle enable/cadence
    -> HousekeepingSettingsService.apply_settings
    -> validate against housekeeping-schedule/v1 policy
    -> SettingsStore.save (local/private)
    -> SchedulerPort.plan_registration (stub/planned descriptor only)
    -> SettingsApplyResult

  SCHEDULER wake (future)
    -> HousekeepingSettingsService.request_action(action)
    -> reject if disabled / forbidden / not allowed
    -> ScheduledActionResult (wake/run selection only)

Failure:
  PERMANENT_DELETE / SELF_APPROVE / PROMOTE_EVIDENCE
    -> HousekeepingAuthorityError
    -> store unchanged; scheduler not called
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

__all__ = [
    "ALLOWED_ACTIONS",
    "CADENCES",
    "FORBIDDEN_ACTIONS",
    "HousekeepingAuthorityError",
    "HousekeepingProfile",
    "HousekeepingSettings",
    "HousekeepingSettingsService",
    "InMemorySchedulerPort",
    "InMemorySettingsStore",
    "PlannedTask",
    "ScheduledActionResult",
    "SchedulerPort",
    "SettingsApplyResult",
    "SettingsStore",
    "default_settings_for_profile",
    "load_schedule_policy",
]

SETTINGS_SCHEMA_VERSION = "filesteward.housekeeping-settings/v1"
SCHEDULE_CONTRACT_SCHEMA = "filesteward.housekeeping-schedule/v1"

ALLOWED_ACTIONS = frozenset({"SCAN", "RECOMMEND", "QUARANTINE_APPROVED"})
FORBIDDEN_ACTIONS = frozenset(
    {"PERMANENT_DELETE", "PROMOTE_EVIDENCE", "SELF_APPROVE"}
)
CADENCES = frozenset({"disabled", "daily_idle", "weekly_idle"})


class HousekeepingProfile(str, Enum):
    DEVELOPMENT = "development"
    PRODUCT = "product"


class HousekeepingAuthorityError(ValueError):
    """Domain rejection for forbidden or illegal housekeeping authority."""


@dataclass(frozen=True)
class HousekeepingSettings:
    profile: HousekeepingProfile
    enabled: bool
    cadence: str
    schema_version: str = SETTINGS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.cadence not in CADENCES:
            raise ValueError(f"unsupported cadence: {self.cadence}")
        if self.enabled and self.cadence == "disabled":
            raise ValueError("enabled settings require a non-disabled cadence")
        if (not self.enabled) and self.cadence != "disabled":
            raise ValueError("disabled settings must use cadence=disabled")


@dataclass(frozen=True)
class PlannedTask:
    task_name: str
    enabled: bool
    cadence: str
    allowed_actions: tuple[str, ...]
    registered: bool = False


@dataclass(frozen=True)
class SettingsApplyResult:
    settings: HousekeepingSettings
    planned_task: PlannedTask
    store_revision: int


@dataclass(frozen=True)
class ScheduledActionResult:
    action: str
    accepted: bool
    reason: str


class SettingsStore(Protocol):
    def load(self) -> HousekeepingSettings | None: ...

    def save(self, settings: HousekeepingSettings) -> int: ...


class SchedulerPort(Protocol):
    def plan_registration(self, settings: HousekeepingSettings) -> PlannedTask: ...


@dataclass
class InMemorySettingsStore:
    """Test/fake local-private settings store."""

    _settings: HousekeepingSettings | None = None
    _revision: int = 0

    def load(self) -> HousekeepingSettings | None:
        return self._settings

    def save(self, settings: HousekeepingSettings) -> int:
        self._settings = settings
        self._revision += 1
        return self._revision


class InMemorySchedulerPort:
    """Fake scheduler: plans descriptors only; never registers OS tasks."""

    def __init__(self) -> None:
        self.calls: list[HousekeepingSettings] = []

    def plan_registration(self, settings: HousekeepingSettings) -> PlannedTask:
        self.calls.append(settings)
        return PlannedTask(
            task_name="FileSteward.Housekeeping",
            enabled=settings.enabled,
            cadence=settings.cadence,
            allowed_actions=tuple(sorted(ALLOWED_ACTIONS)),
            registered=False,
        )


def default_settings_for_profile(profile: HousekeepingProfile) -> HousekeepingSettings:
    if profile is HousekeepingProfile.DEVELOPMENT:
        return HousekeepingSettings(
            profile=profile,
            enabled=True,
            cadence="daily_idle",
        )
    return HousekeepingSettings(
        profile=HousekeepingProfile.PRODUCT,
        enabled=False,
        cadence="disabled",
    )


def load_schedule_policy(contract_path: Path) -> dict[str, object]:
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEDULE_CONTRACT_SCHEMA:
        raise ValueError("housekeeping schedule contract schema mismatch")
    allowed = set(payload.get("actions", {}).get("allowed", []))
    forbidden = set(payload.get("actions", {}).get("forbidden", []))
    if allowed != set(ALLOWED_ACTIONS):
        raise ValueError("module ALLOWED_ACTIONS drifted from schedule contract")
    if forbidden != set(FORBIDDEN_ACTIONS):
        raise ValueError("module FORBIDDEN_ACTIONS drifted from schedule contract")
    return payload


@dataclass
class HousekeepingSettingsService:
    store: SettingsStore
    scheduler: SchedulerPort
    profile: HousekeepingProfile = HousekeepingProfile.DEVELOPMENT

    def current(self) -> HousekeepingSettings:
        existing = self.store.load()
        if existing is not None:
            return existing
        return default_settings_for_profile(self.profile)

    def apply_settings(self, *, enabled: bool, cadence: str) -> SettingsApplyResult:
        """Persist local settings and plan (not register) a scheduler task."""

        normalized = "disabled" if not enabled else cadence
        settings = HousekeepingSettings(
            profile=self.profile,
            enabled=enabled,
            cadence=normalized,
        )
        revision = self.store.save(settings)
        planned = self.scheduler.plan_registration(settings)
        return SettingsApplyResult(
            settings=settings,
            planned_task=planned,
            store_revision=revision,
        )

    def request_action(self, action: str) -> ScheduledActionResult:
        """Classify a wake/run action without granting mutation authority."""

        key = action.strip().upper()
        if key in FORBIDDEN_ACTIONS:
            raise HousekeepingAuthorityError(
                f"{key} is forbidden; scheduler may not exercise this authority"
            )
        if key not in ALLOWED_ACTIONS:
            raise HousekeepingAuthorityError(f"{key} is not an allowed scheduled action")

        settings = self.current()
        if not settings.enabled:
            return ScheduledActionResult(
                action=key,
                accepted=False,
                reason="housekeeping disabled by local settings",
            )
        if key == "QUARANTINE_APPROVED":
            return ScheduledActionResult(
                action=key,
                accepted=False,
                reason=(
                    "QUARANTINE_APPROVED requires an exact operator approval "
                    "bound to cleanup-plan identity; settings alone are insufficient"
                ),
            )
        return ScheduledActionResult(
            action=key,
            accepted=True,
            reason="wake/run selection accepted; no disposition or approval granted",
        )

    def disable(self) -> SettingsApplyResult:
        return self.apply_settings(enabled=False, cadence="disabled")
