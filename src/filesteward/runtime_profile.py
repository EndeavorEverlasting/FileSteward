"""Explicit installed Windows runtime authority, separate from a checkout.

The OS KnownFolder result owns runtime placement. Neither environment variables,
the working directory, nor a frozen extraction directory supply path authority.
Initialization creates runtime directories/receipt only; it never scans data.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
from importlib import metadata, resources
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from filesteward import __version__
from filesteward.inventory import windows

PROFILE_ID = "windows-localappdata/v1"
APPLICATION_MARKER = ".filesteward-application.json"
KNOWN_FOLDER_ID = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"
_FORBIDDEN = {"desktop", "documents", "onedrive", "backups"}

__all__ = ["InstalledRuntimeProfile", "PROFILE_ID", "APPLICATION_MARKER",
           "windows_local_app_data", "resolve_installed_runtime", "initialize_installed_runtime"]


@dataclass(frozen=True)
class InstalledRuntimeProfile:
    application_root: Path
    runtime_root: Path
    local_app_data: Path
    mode: str
    package_version: str
    profile_digest: str
    artifact_origin: Path

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": "filesteward.runtime-readiness/v1",
            "runtime_profile": PROFILE_ID,
            "application_root": str(self.application_root),
            "runtime_root": str(self.runtime_root),
            "local_app_data": str(self.local_app_data),
            "mode": self.mode,
            "package_version": self.package_version,
            "profile_digest": self.profile_digest,
            "artifact_origin": str(self.artifact_origin),
            "startup_authority": "PRIVATE_RUNTIME_ONLY",
            "scan_started": False,
            "deletion_started": False,
            "schedule_registered": False,
        }


def windows_local_app_data() -> Path:
    """Resolve FOLDERID_LocalAppData through SHGetKnownFolderPath, no fallback."""
    if os.name != "nt":
        raise RuntimeError("Windows installed runtime requires the OS KnownFolder API")

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    guid = GUID.from_buffer_copy(uuid.UUID(KNOWN_FOLDER_ID).bytes_le)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), ctypes.c_uint32,
                                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    buffer = ctypes.c_void_p()
    result = shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buffer))
    try:
        if result != 0 or not buffer.value:
            raise RuntimeError(f"LocalAppData KnownFolder resolution failed (HRESULT {result:#x})")
        path = Path(ctypes.wstring_at(buffer.value))
    finally:
        if buffer.value:
            ole.CoTaskMemFree(buffer)
    if not path.is_absolute():
        raise RuntimeError("LocalAppData KnownFolder did not resolve an absolute path")
    return path


def _safe_path(path: Path) -> Path:
    """Reject links/reparse points in every existing component, not just leaf."""
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("installed runtime path must be absolute without traversal")
    if any(part.lower() in _FORBIDDEN for part in path.parts):
        raise RuntimeError("installed runtime path lies beneath a forbidden root")
    for probe in (*reversed(path.parents), path):
        try:
            st = os.lstat(probe)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeError("installed runtime path identity cannot be established") from exc
        if probe.is_symlink() or windows.is_reparse_point(st):
            raise RuntimeError("installed runtime path contains a symlink/reparse component")
    if Path(os.path.realpath(path)) != path:
        raise RuntimeError("installed runtime path resolves outside its declared identity")
    return path


def _bundled_profile() -> tuple[dict, str]:
    raw = resources.files("filesteward").joinpath("contracts", "runtime-profile.v1.json").read_bytes()
    document = json.loads(raw)
    marker = document.get("application_marker") or {}
    if (document.get("schema_version") != "filesteward.runtime-profile/v1"
            or document.get("profile_id") != PROFILE_ID
            or type(document.get("profile_version")) is not int or document["profile_version"] != 1
            or document.get("known_folder_id") != KNOWN_FOLDER_ID
            or document.get("application_namespace") != "FileSteward"
            or document.get("runtime_components") != ["runtime", "var"]
            or document.get("supported_modes") != ["frozen", "wheel"]
            or marker != {"filename": APPLICATION_MARKER,
                          "schema_version": "filesteward.application-root/v1",
                          "app_id": "filesteward", "runtime_profile": PROFILE_ID}):
        raise RuntimeError("bundled installed runtime profile identity/version mismatch")
    return document, hashlib.sha256(raw).hexdigest()


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _package_file() -> Path:
    import filesteward
    return Path(filesteward.__file__).absolute()


def _wheel_identity(package_file: Path) -> None:
    try:
        distribution = metadata.distribution("filesteward")
        located = Path(distribution.locate_file("filesteward/__init__.py")).absolute()
    except (metadata.PackageNotFoundError, OSError, TypeError) as exc:
        raise RuntimeError("installed wheel distribution identity is unavailable") from exc
    if distribution.version != __version__ or located != package_file:
        raise RuntimeError("installed wheel metadata/version/import-origin mismatch")


def _frozen_identity() -> None:
    try:
        document = json.loads(resources.files("filesteward").joinpath(
            "contracts", "build-info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("immutable frozen build identity is unavailable") from exc
    if (not isinstance(document, dict)
            or document.get("schema_version") != "filesteward.build-info/v1"
            or document.get("app_id") != "filesteward"
            or document.get("runtime_profile") != PROFILE_ID
            or document.get("package_version") != __version__):
        raise RuntimeError("immutable frozen build identity/version mismatch")


def _admit_profile(application_root: str | Path | None) -> InstalledRuntimeProfile:
    _document, digest = _bundled_profile()
    local = _safe_path(windows_local_app_data())
    if not local.is_dir():
        raise RuntimeError("LocalAppData KnownFolder directory is unavailable")
    namespace = _safe_path(local / "FileSteward")
    runtime = _safe_path(namespace / "runtime" / "var")
    mode = "frozen" if _is_frozen() else "wheel"
    if mode == "frozen":
        _frozen_identity()
        origin = Path(sys.executable)
        if not origin.is_absolute() or not origin.is_file():
            raise RuntimeError("frozen executable transport identity is unavailable")
    else:
        origin = _package_file()
        _wheel_identity(origin)
    root = namespace if application_root is None else _safe_path(Path(application_root))
    if root != namespace:
        raise RuntimeError("installed application root differs from the admitted KnownFolder family root")
    return InstalledRuntimeProfile(root, runtime, local, mode, __version__, digest, origin)


def _validate_application_marker(root: Path) -> None:
    if not root.is_dir():
        raise RuntimeError("installed application family root is unavailable")
    marker_path = _safe_path(root / APPLICATION_MARKER)
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("installed application root marker is missing or invalid") from exc
    if (not isinstance(marker, dict)
            or marker.get("schema_version") != "filesteward.application-root/v1"
            or marker.get("app_id") != "filesteward"
            or marker.get("runtime_profile") != PROFILE_ID):
        raise RuntimeError("installed application root marker identity mismatch")


def resolve_installed_runtime(application_root: str | Path | None = None) -> InstalledRuntimeProfile:
    """Read-only admission; absent/unknown family markers refuse runtime use."""
    profile = _admit_profile(application_root)
    _validate_application_marker(profile.application_root)
    return profile


def initialize_installed_runtime(application_root: str | Path | None = None) -> InstalledRuntimeProfile:
    """Create only the admitted private runtime and a startup-readiness receipt."""
    profile = _admit_profile(application_root)
    root = profile.application_root
    if root.exists():
        # Never adopt an existing unmarked directory or replace another app's
        # marker. The bootstrap or a prior admitted launch must establish it.
        _validate_application_marker(root)
    else:
        try:
            root.mkdir()
        except FileExistsError:
            _validate_application_marker(root)
        else:
            _safe_path(root)
            marker = _safe_path(root / APPLICATION_MARKER)
            with marker.open("x", encoding="utf-8") as stream:
                json.dump({"schema_version": "filesteward.application-root/v1",
                           "app_id": "filesteward", "runtime_profile": PROFILE_ID,
                           "created_version": __version__}, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            _validate_application_marker(root)
    namespace = profile.local_app_data / "FileSteward"
    for target in (namespace / "runtime", profile.runtime_root, profile.runtime_root / "runs"):
        _safe_path(target)
        target.mkdir(exist_ok=True)
        _safe_path(target)
    receipt = _safe_path(profile.runtime_root / "runtime-readiness.json")
    fd, temporary = tempfile.mkstemp(prefix=".readiness-", suffix=".json", dir=profile.runtime_root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(profile.as_mapping(), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(profile.runtime_root)
        _safe_path(receipt)
        os.replace(temporary, receipt)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return profile
