"""Read-only Windows application attribution adapters.

Produces ownership edges and lifecycle classes for installed applications
from uninstall registration and injectable runtime/serviceability probes.
WMI product-inventory enumeration is forbidden. Live registry/process probes
are injectable so synthetic tests never require workstation mutation.

J4 consumes these normalized records; this module does not authorize deletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PureWindowsPath
from typing import Callable, Mapping, Optional, Sequence

from filesteward.ownership._windows_paths import (
    command_executable,
    expand_windows_path,
    path_intersects,
)

__all__ = [
    "AppLifecycleClass",
    "AppOwnershipEdge",
    "AppOwnershipRecord",
    "UninstallRegistration",
    "USER_FACING_BADGE",
    "attribute_path",
    "classify_uninstall_registration",
    "collect_app_ownership",
]


class AppLifecycleClass(str, Enum):
    ACTIVE_REQUIRED = "APP_ACTIVE_REQUIRED"
    BROKEN_REQUIRED = "APP_BROKEN_REQUIRED"
    CACHE_REGENERABLE = "APP_CACHE_REGENERABLE"
    ORPHAN_CANDIDATE = "APP_ORPHAN_CANDIDATE"


USER_FACING_BADGE: Mapping[AppLifecycleClass, str] = {
    AppLifecycleClass.ACTIVE_REQUIRED: "Required by app",
    AppLifecycleClass.BROKEN_REQUIRED: "Broken app dependency",
    AppLifecycleClass.CACHE_REGENERABLE: "Regenerable cache",
    AppLifecycleClass.ORPHAN_CANDIDATE: "Unknown ownership",
}


@dataclass(frozen=True)
class UninstallRegistration:
    """Normalized uninstall/registration evidence for one installed app."""

    app_id: str
    display_name: str
    publisher: str = ""
    display_version: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    quiet_uninstall_string: str = ""
    modify_path: str = ""
    hive: str = ""
    registry_path: str = ""
    regenerable_cache_roots: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppOwnershipEdge:
    edge_type: str
    storage_path: str
    owner_id: str
    owner_display_name: str
    evidence_source: str
    confidence: str
    detail: str = ""


@dataclass(frozen=True)
class AppOwnershipRecord:
    app_id: str
    display_name: str
    lifecycle_class: AppLifecycleClass
    user_facing_badge: str
    consequence_classes: tuple[str, ...]
    semantic_actions: tuple[str, ...]
    edges: tuple[AppOwnershipEdge, ...]
    reasons: tuple[str, ...]
    probes_attempted: tuple[str, ...]
    safety_floor: str


PathExists = Callable[[str], bool]
PathListProvider = Callable[[], Sequence[str]]


def _serviceability_commands(entry: UninstallRegistration) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for field_name, raw in (
        ("UninstallString", entry.uninstall_string),
        ("QuietUninstallString", entry.quiet_uninstall_string),
        ("ModifyPath", entry.modify_path),
    ):
        exe = command_executable(raw)
        if exe:
            pairs.append((field_name, exe))
    return pairs


def classify_uninstall_registration(
    entry: UninstallRegistration,
    *,
    path_exists: PathExists,
    runtime_paths: Sequence[str] = (),
    service_paths: Sequence[str] = (),
    task_paths: Sequence[str] = (),
    shortcut_targets: Sequence[str] = (),
) -> AppOwnershipRecord:
    """Classify one registered application from injectable evidence."""

    probes: list[str] = [
        "uninstall_registration",
        "install_location",
        "serviceability_executables",
        "runtime_modules",
        "services",
        "scheduled_tasks",
        "shortcuts",
    ]
    edges: list[AppOwnershipEdge] = []
    reasons: list[str] = []
    consequence: list[str] = []

    install = expand_windows_path(entry.install_location)
    if install:
        edges.append(
            AppOwnershipEdge(
                edge_type="INSTALLED_AT",
                storage_path=install,
                owner_id=entry.app_id,
                owner_display_name=entry.display_name,
                evidence_source="uninstall_registration",
                confidence="strong",
                detail=f"hive={entry.hive}",
            )
        )
        if path_exists(install):
            reasons.append(
                f"Windows still registers {entry.display_name} with install location {install}."
            )
        else:
            reasons.append(
                f"Windows registers {entry.display_name} at {install}, but that location is missing."
            )

    serviceability_missing = False
    serviceability_present = False
    for field_name, exe in _serviceability_commands(entry):
        exists = path_exists(exe)
        edges.append(
            AppOwnershipEdge(
                edge_type="SERVICEABILITY_REQUIRES",
                storage_path=exe,
                owner_id=entry.app_id,
                owner_display_name=entry.display_name,
                evidence_source=f"uninstall_registration.{field_name}",
                confidence="strong",
                detail="present" if exists else "missing",
            )
        )
        # Parent directory of the updater/uninstaller is also a serviceability root.
        parent = str(PureWindowsPath(exe).parent)
        if parent and parent not in {".", ""}:
            edges.append(
                AppOwnershipEdge(
                    edge_type="UPDATES_THROUGH",
                    storage_path=parent,
                    owner_id=entry.app_id,
                    owner_display_name=entry.display_name,
                    evidence_source=f"uninstall_registration.{field_name}",
                    confidence="strong",
                    detail="serviceability_parent",
                )
            )
        if exists:
            serviceability_present = True
        else:
            serviceability_missing = True
            reasons.append(
                f"Registered {field_name} executable is missing: {exe}."
            )

    for path in runtime_paths:
        if not path:
            continue
        if install and not path_intersects(path, install):
            # Still record if the process path clearly belongs to this app id/name.
            lowered = path.lower()
            token = entry.display_name.split()[0].lower() if entry.display_name else ""
            if token and token not in lowered and entry.app_id.lower() not in lowered:
                continue
        edges.append(
            AppOwnershipEdge(
                edge_type="RUNTIME_REQUIRES",
                storage_path=expand_windows_path(path),
                owner_id=entry.app_id,
                owner_display_name=entry.display_name,
                evidence_source="process_list",
                confidence="strong",
            )
        )
        consequence.append("APP_RUNTIME_DEPENDENCY")
        reasons.append(f"A running process/module uses {path}.")

    for path, edge_type, source, consequence_name in (
        *((p, "SERVICE_REFERENCES", "service", "SERVICE_DEPENDENCY") for p in service_paths),
        *((p, "TASK_REFERENCES", "scheduled_task", "SCHEDULED_TASK_DEPENDENCY") for p in task_paths),
        *((p, "SHORTCUT_TARGETS", "shortcut", "APP_RUNTIME_DEPENDENCY") for p in shortcut_targets),
    ):
        if not path:
            continue
        if install and not path_intersects(path, install):
            continue
        edges.append(
            AppOwnershipEdge(
                edge_type=edge_type,
                storage_path=expand_windows_path(path),
                owner_id=entry.app_id,
                owner_display_name=entry.display_name,
                evidence_source=source,
                confidence="strong" if edge_type != "SHORTCUT_TARGETS" else "corroboration",
            )
        )
        if consequence_name not in consequence:
            consequence.append(consequence_name)

    for cache_root in entry.regenerable_cache_roots:
        root = expand_windows_path(cache_root)
        if not root:
            continue
        edges.append(
            AppOwnershipEdge(
                edge_type="PACKAGE_OWNS",
                storage_path=root,
                owner_id=entry.app_id,
                owner_display_name=entry.display_name,
                evidence_source="adapter_regenerable_cache",
                confidence="strong",
                detail="regenerable_cache_boundary",
            )
        )

    has_registration = bool(entry.display_name or entry.uninstall_string or install)
    has_binding_edge = bool(edges)

    if serviceability_missing and has_registration:
        lifecycle = AppLifecycleClass.BROKEN_REQUIRED
        if "APP_INSTALLATION_BROKEN" not in consequence:
            consequence.append("APP_INSTALLATION_BROKEN")
        if "APP_SERVICEABILITY_DEPENDENCY" not in consequence:
            consequence.append("APP_SERVICEABILITY_DEPENDENCY")
        semantic = ("REPAIR_APPLICATION", "UNINSTALL_APPLICATION")
        safety = "PROTECTED"
        if not any("missing" in r.lower() for r in reasons):
            reasons.append(
                "Windows still expects this application, but a required "
                "uninstall/update/repair executable disappeared."
            )
    elif entry.regenerable_cache_roots and not (
        serviceability_missing or consequence
    ):
        # Cache-only adapter proof with no broken/runtime bindings.
        lifecycle = AppLifecycleClass.CACHE_REGENERABLE
        consequence.append("APP_CACHE_REGENERABLE")
        semantic = ("CLEAN_CACHE",)
        safety = "SEMANTIC_CLEAN_ACTION_ONLY"
        reasons.append(
            "Adapter proved a regenerable application cache boundary; "
            "use CLEAN_CACHE rather than raw deletion."
        )
    elif has_binding_edge or has_registration:
        lifecycle = AppLifecycleClass.ACTIVE_REQUIRED
        if "APP_SERVICEABILITY_DEPENDENCY" not in consequence and (
            serviceability_present or install
        ):
            consequence.append("APP_SERVICEABILITY_DEPENDENCY")
        if "APP_RUNTIME_DEPENDENCY" not in consequence and any(
            e.edge_type == "RUNTIME_REQUIRES" for e in edges
        ):
            consequence.append("APP_RUNTIME_DEPENDENCY")
        semantic = ("REPAIR_APPLICATION", "UNINSTALL_APPLICATION")
        safety = "PROTECTED"
        if not reasons:
            reasons.append(
                f"{entry.display_name or entry.app_id} currently depends on these bytes."
            )
    else:
        lifecycle = AppLifecycleClass.ORPHAN_CANDIDATE
        consequence.append("ORPHAN_CANDIDATE")
        semantic = ()
        safety = "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION"
        reasons.append(
            "No surviving owner/dependency found after safe app attribution "
            "adapters; absence of evidence is not deletion proof."
        )

    return AppOwnershipRecord(
        app_id=entry.app_id,
        display_name=entry.display_name or entry.app_id,
        lifecycle_class=lifecycle,
        user_facing_badge=USER_FACING_BADGE[lifecycle],
        consequence_classes=tuple(dict.fromkeys(consequence)),
        semantic_actions=semantic,
        edges=tuple(edges),
        reasons=tuple(reasons),
        probes_attempted=tuple(probes),
        safety_floor=safety,
    )


def collect_app_ownership(
    registrations: Sequence[UninstallRegistration],
    *,
    path_exists: PathExists,
    runtime_paths: Sequence[str] = (),
    service_paths: Sequence[str] = (),
    task_paths: Sequence[str] = (),
    shortcut_targets: Sequence[str] = (),
) -> tuple[AppOwnershipRecord, ...]:
    """Classify all provided registrations. Does not invent reclaim authority."""

    return tuple(
        classify_uninstall_registration(
            entry,
            path_exists=path_exists,
            runtime_paths=runtime_paths,
            service_paths=service_paths,
            task_paths=task_paths,
            shortcut_targets=shortcut_targets,
        )
        for entry in registrations
    )


@dataclass(frozen=True)
class PathAttribution:
    path: str
    matched_records: tuple[AppOwnershipRecord, ...]
    governing_lifecycle: Optional[AppLifecycleClass]
    user_facing_badge: str
    required_by: tuple[str, ...]
    reasons: tuple[str, ...]
    semantic_actions: tuple[str, ...]
    safety_floor: str
    probes_attempted: tuple[str, ...] = field(default_factory=tuple)


_LIFECYCLE_RANK = {
    AppLifecycleClass.BROKEN_REQUIRED: 400,
    AppLifecycleClass.ACTIVE_REQUIRED: 300,
    AppLifecycleClass.CACHE_REGENERABLE: 200,
    AppLifecycleClass.ORPHAN_CANDIDATE: 100,
}


def attribute_path(
    path: str,
    records: Sequence[AppOwnershipRecord],
    *,
    adapters_exhausted: bool = False,
) -> PathAttribution:
    """Explain what owns a path using most-protective matching edge wins."""

    matched: list[AppOwnershipRecord] = []
    for record in records:
        if any(path_intersects(path, edge.storage_path) for edge in record.edges):
            matched.append(record)

    if not matched:
        badge = "Unknown ownership"
        floor = (
            "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION"
            if adapters_exhausted
            else "UNKNOWN"
        )
        reasons = (
            (
                "Safe application adapters found no owner for this path; "
                "do not treat missing ownership as disposability."
            )
            if adapters_exhausted
            else (
                "Application ownership has not been fully resolved for this path."
            )
        )
        return PathAttribution(
            path=path,
            matched_records=(),
            governing_lifecycle=(
                AppLifecycleClass.ORPHAN_CANDIDATE if adapters_exhausted else None
            ),
            user_facing_badge=badge,
            required_by=(),
            reasons=(reasons,),
            semantic_actions=(),
            safety_floor=floor,
            probes_attempted=("path_owner_lookup",),
        )

    governing = max(matched, key=lambda r: _LIFECYCLE_RANK[r.lifecycle_class])
    required_by = tuple(dict.fromkeys(r.display_name for r in matched))
    reasons = tuple(dict.fromkeys(r for rec in matched for r in rec.reasons))
    actions = tuple(dict.fromkeys(a for rec in matched for a in rec.semantic_actions))
    return PathAttribution(
        path=path,
        matched_records=tuple(matched),
        governing_lifecycle=governing.lifecycle_class,
        user_facing_badge=governing.user_facing_badge,
        required_by=required_by,
        reasons=reasons,
        semantic_actions=actions,
        safety_floor=governing.safety_floor,
        probes_attempted=tuple(
            dict.fromkeys(p for rec in matched for p in rec.probes_attempted)
        ),
    )
