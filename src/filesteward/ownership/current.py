"""Bounded current evidence collection; incomplete probes never authorize action.

Construction is inert. Calling the resolver is an explicit observation boundary.
Native providers currently cover uninstall registration and bounded Git evidence;
the remaining domains are explicitly unavailable, rather than empty successes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from typing import Callable, Mapping

from filesteward.ownership.actions import OwnershipEvidence, OwnershipResolver
from filesteward.ownership.graph import OwnershipEdge, build_ownership_graph
from filesteward.ownership.repository import RepositoryAttribution, attribute_repositories_under
from filesteward.ownership.windows_app import (
    AppOwnershipRecord, UninstallRegistration, collect_app_ownership,
)
from filesteward.ownership._windows_paths import command_executable, path_intersects


DOMAINS = (
    "application_installation", "application_runtime", "application_serviceability",
    "service", "scheduled_task", "package_manager", "repository", "toolchain", "user_data",
    "shortcut", "file_metadata", "regeneration",
)


@dataclass(frozen=True)
class ProbeResult:
    """A provider's explicit coverage and normalized observations for one root."""
    complete: bool = False
    provenance: str = ""
    gaps: tuple[str, ...] = ()
    edges: tuple[OwnershipEdge, ...] = ()
    app_records: tuple[AppOwnershipRecord, ...] = ()
    repo_records: tuple[RepositoryAttribution, ...] = ()


@dataclass(frozen=True)
class ProbeCoverage:
    domain: str
    complete: bool
    provenance: str
    gaps: tuple[str, ...]


@dataclass(frozen=True)
class CurrentOwnershipEvidence(OwnershipEvidence):
    coverage: tuple[ProbeCoverage, ...] = ()

    @property
    def digest(self) -> str:
        # Coverage changes are semantic revisions, even if protective edges match.
        payload = {"evidence": super().digest, "coverage": [asdict(c) for c in self.coverage]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


ProbeProvider = Callable[[Path, Path], ProbeResult]


def _bounded_path(raw: Path, root: Path) -> Path:
    if not raw.is_absolute() or ".." in raw.parts:
        raise ValueError("PATH_NOT_ABSOLUTE_OR_NORMALIZED")
    path = Path(os.path.abspath(raw))
    if not path.is_relative_to(root):
        raise ValueError("PATH_OUTSIDE_ADMITTED_ROOT")
    # lstat every ancestor without resolving/following a link, including root's
    # ancestors. Missing/unreadable components fail before any domain provider.
    for part in reversed((path, *path.parents)):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("LINK_OR_REPARSE_COMPONENT")
    return path


def _unavailable(root: Path, target: Path) -> ProbeResult:
    return ProbeResult(provenance="native_provider_unavailable",
                       gaps=("NO_COMPLETE_READ_ONLY_PROVIDER",))


def _registry(root: Path, target: Path) -> ProbeResult:
    """Read registration metadata, then inspect serviceability only inside root.

    This is not runtime/process/package coverage. Registry errors are gaps and
    already observed protective edges survive a partial registry enumeration.
    """
    if os.name != "nt":
        return ProbeResult(provenance="windows_uninstall_registry", gaps=("WINDOWS_ONLY",))
    import winreg
    edges, records, gaps = [], [], []
    key_name = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    fields = {"display_name": "DisplayName", "publisher": "Publisher",
              "display_version": "DisplayVersion", "install_location": "InstallLocation",
              "uninstall_string": "UninstallString", "quiet_uninstall_string": "QuietUninstallString",
              "modify_path": "ModifyPath"}
    for hive_name, hive in (("HKLM", winreg.HKEY_LOCAL_MACHINE), ("HKCU", winreg.HKEY_CURRENT_USER)):
        for view_name, view in (("64", winreg.KEY_WOW64_64KEY), ("32", winreg.KEY_WOW64_32KEY)):
            try:
                with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for i in range(count):
                        try:
                            child_name = winreg.EnumKey(parent, i)
                            with winreg.OpenKey(parent, child_name) as child:
                                values = {}
                                for name, registry_name in fields.items():
                                    try:
                                        value, kind = winreg.QueryValueEx(child, registry_name)
                                    except FileNotFoundError:
                                        continue
                                    if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str):
                                        values[name] = os.path.expandvars(value)
                                entry = UninstallRegistration(
                                    app_id=f"{hive_name}:{view_name}:{child_name}",
                                    hive=hive_name, registry_path=key_name + "\\" + child_name,
                                    **{"display_name": child_name, **values})
                                anchors = [("INSTALLED_AT", entry.install_location)]
                                anchors.extend(("SERVICEABILITY_REQUIRES", command_executable(command)) for command in
                                               (entry.uninstall_string, entry.quiet_uninstall_string, entry.modify_path))
                                relevant = [(kind, anchor) for kind, anchor in anchors if anchor and path_intersects(str(target), anchor)]
                                if not relevant:
                                    continue
                                # Retain affirmative registration protection even
                                # if existence checks cannot be completed in scope.
                                for kind, anchor in relevant:
                                    edges.append(OwnershipEdge(kind, str(target), "APPLICATION", entry.app_id,
                                        entry.display_name, "windows_uninstall_registry", "strong", "APP_ACTIVE_REQUIRED",
                                        "Registered installation/serviceability intersects the selected target"))
                                def exists(path: str) -> bool:
                                    return _bounded_path(Path(path), root).exists()
                                try:
                                    records.extend(collect_app_ownership((entry,), path_exists=exists))
                                except (OSError, ValueError):
                                    gaps.append("SERVICEABILITY_EXISTENCE_UNRESOLVED_WITHIN_SCOPE")
                        except OSError:
                            gaps.append(f"REGISTRATION_UNREADABLE:{hive_name}:{view_name}")
            except FileNotFoundError:
                pass  # Absent uninstall key, not absent ownership.
            except OSError:
                gaps.append(f"REGISTRY_VIEW_UNREADABLE:{hive_name}:{view_name}")
    return ProbeResult(not gaps, "windows_uninstall_registry_four_views", tuple(sorted(set(gaps))),
                       tuple(edges), tuple(records))


def _repositories(root: Path, target: Path) -> ProbeResult:
    # Canonical discovery, not a second directory scanner. Its current interface
    # does not return a complete traversal-error ledger or cross-repo references.
    records = attribute_repositories_under(root)
    return ProbeResult(False, "ProtectionIndex.from_git_discovery+repository_adapter",
        ("DISCOVERY_COMPLETENESS_UNPROVEN", "EXTERNAL_REPOSITORY_DEPENDENCIES_UNRESOLVED",
         "ANCESTOR_REPOSITORY_CONTEXT_UNRESOLVED", "ENTIRE_RELATIONSHIPS_UNRESOLVED"), repo_records=records)


def make_current_resolver(scan_root: Path, *, providers: Mapping[str, ProbeProvider] | None = None,
                          clock: Callable[[], float] = time.time) -> OwnershipResolver:
    """Return a fresh per-call resolver; construction performs no host I/O.

    ``providers`` is a trusted in-process adapter injection, never client input.
    Omitted domains remain unavailable even when other providers succeed. The
    native implementation intentionally supplies no regeneration proof.
    """
    root = Path(scan_root)
    supplied = dict(providers) if providers is not None else {
        "application_installation": _registry, "repository": _repositories,
    }
    if set(supplied) - set(DOMAINS):
        raise ValueError("UNREGISTERED_EVIDENCE_DOMAIN")

    def resolve(raw: str) -> CurrentOwnershipEvidence:
        coverage, edges, apps, repos = [], [], [], []
        observed = clock()  # Start, not completion: slow probes cannot mint freshness.
        try:
            if not root.is_absolute() or ".." in root.parts:
                raise ValueError("ROOT_NOT_ABSOLUTE_OR_NORMALIZED")
            target = _bounded_path(Path(raw), root)
            if not _bounded_path(root, root).is_dir():
                raise ValueError("ROOT_NOT_DIRECTORY")
        except (OSError, ValueError) as exc:
            return CurrentOwnershipEvidence(build_ownership_graph(), False, observed,
                coverage=(ProbeCoverage("scope", False, "bounded_lstat", (str(exc) if isinstance(exc, ValueError) else type(exc).__name__,)),))
        for domain in DOMAINS:
            provider = supplied.get(domain, _unavailable)
            try:
                result = provider(root, target)
                if not isinstance(result, ProbeResult):
                    raise TypeError("INVALID_PROBE_RESULT")
                # Reject provider edges outside scope; registration relations
                # crossing root are represented at the selected target instead.
                accepted = []
                invalid = False
                for edge in result.edges:
                    try:
                        _bounded_path(Path(edge.storage_path), root)
                        accepted.append(edge)
                    except (OSError, ValueError):
                        invalid = True
                edges.extend(accepted)
                for record in result.app_records:
                    try:
                        for edge in record.edges:
                            _bounded_path(Path(edge.storage_path), root)
                        apps.append(record)
                    except (OSError, ValueError):
                        invalid = True
                        # Preserve scoped edges from a partially usable record.
                        for edge in build_ownership_graph(app_records=(record,)).edges:
                            if path_intersects(str(target), edge.storage_path):
                                edges.append(OwnershipEdge(edge.edge_type, str(target), edge.owner_kind,
                                    edge.owner_id, edge.owner_display_name, edge.evidence_source,
                                    edge.confidence, edge.lifecycle_hint, edge.detail))
                for record in result.repo_records:
                    try:
                        _bounded_path(Path(record.root), root)
                        repos.append(record)
                    except (OSError, ValueError):
                        invalid = True
                gaps = result.gaps + (("PROVIDER_EDGE_OUTSIDE_SAFE_SCOPE",) if invalid else ())
                complete = result.complete is True and bool(result.provenance) and not gaps
                coverage.append(ProbeCoverage(domain, complete, result.provenance, gaps))
            except Exception as exc:
                coverage.append(ProbeCoverage(domain, False, "provider_failed", (type(exc).__name__,)))
        return CurrentOwnershipEvidence(build_ownership_graph(app_records=apps, repo_records=repos,
            extra_edges=edges), all(c.complete for c in coverage), observed, coverage=tuple(coverage))

    return resolve
