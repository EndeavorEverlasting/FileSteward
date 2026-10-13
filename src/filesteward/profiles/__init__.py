"""Private, append-only workstation performance profiles; never cleanup approval."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from filesteward.policy.paths import is_symlink_or_reparse
from filesteward.profiles.windows import (
    WindowsMediaProbe,
    resolve_declared_volumes_media_type,
)

SCHEMA = "filesteward.workstation-performance-profile/v1"
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")

class ProfileError(ValueError):
    pass

def _refuse_linked(path: Path, label: str) -> None:
    """Fail closed on symlink or Windows junction/reparse (Path.is_symlink misses junctions)."""
    if is_symlink_or_reparse(path):
        raise ProfileError(f"{label} is a symlink/reparse")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _key(key: str) -> str:
    if not KEY.fullmatch(key):
        raise ProfileError("invalid alias; use 1-48 letters/digits/_/-")
    return key

def _binding() -> str:
    node = platform.node().strip().casefold()
    if not node:
        raise ProfileError("machine name unavailable")
    return platform.system().casefold() + "\0" + node

def _digest(salt: str, binding: str) -> str:
    return hashlib.sha256((salt + "\0" + binding).encode("utf-8")).hexdigest()

def _read(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("expected object")
        return obj
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProfileError("invalid or missing profile artifact: " + path.name) from exc

def _create(path: Path, obj: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, allow_nan=False)
        fh.write("\n")

def _latest(path: Path, obj: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".profile-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True, allow_nan=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def _ensure_identity(directory: Path, alias: str, binding: str) -> str:
    path = directory / "identity.json"
    _refuse_linked(path, "identity artifact")
    if not path.exists():
        salt = secrets.token_hex(16)
        try:
            _create(path, {
                "schema_version": "filesteward.workstation-identity/v1",
                "alias": alias,
                "salt": salt,
                "digest": _digest(salt, binding),
                "binding_kind": "salted-os-and-host-name",
                "warning": "not hardware attestation"
            })
            return "NEW"
        except FileExistsError:
            pass
    identity = _read(path)
    if (identity.get("schema_version") != "filesteward.workstation-identity/v1"
            or identity.get("alias") != alias or
            not isinstance(identity.get("salt"), str) or
            identity.get("digest") != _digest(identity["salt"], binding)):
        raise ProfileError("HOST_BINDING_MISMATCH: refusing alias reuse")
    return "MATCHED"

def observe(volumes: Sequence[str], *, sample_seconds: float = 0.2,
            disk_usage: Callable[[str], Any] = shutil.disk_usage,
            psutil_module: Any = None,
            windows_media_probe: WindowsMediaProbe | None = None) -> dict[str, Any]:
    if not 1 <= len(volumes) <= 32:
        raise ProfileError("declare 1-32 volumes explicitly")
    if not 0 <= sample_seconds <= 5:
        raise ProfileError("sample time outside 0-5 seconds")
    if psutil_module is None:
        try:
            import psutil as psutil_module
        except ImportError:
            psutil_module = None
    metrics = {"cpu_logical_count": os.cpu_count(), "cpu_utilization_pct": None,
               "memory_total_bytes": None, "memory_available_bytes": None,
               "volume_latency_ms": None, "device_wear_pct": None,
               "media_type": None, "temperature_c": None}
    missing = ["volume_latency_ms: no mapped volume counter",
               "device_wear_pct: no trusted collector",
               "temperature_c: no trusted sensor"]
    if psutil_module is None:
        missing.extend(["cpu_utilization_pct: psutil unavailable",
                        "memory: psutil unavailable"])
    else:
        try:
            value = float(psutil_module.cpu_percent(interval=sample_seconds))
            if not 0 <= value <= 100:
                raise ValueError("out of range")
            metrics["cpu_utilization_pct"] = round(value, 2)
        except (OSError, ValueError, TypeError, AttributeError):
            missing.append("cpu_utilization_pct: unavailable")
        try:
            memory = psutil_module.virtual_memory()
            available, total = int(memory.available), int(memory.total)
            if not 0 <= available <= total:
                raise ValueError("out of range")
            metrics["memory_total_bytes"] = total
            metrics["memory_available_bytes"] = available
        except (OSError, ValueError, TypeError, AttributeError):
            missing.append("memory: unavailable")
    results = []
    seen = set()
    resolved_roots: list[str] = []
    for volume in volumes:
        root = os.path.abspath(os.path.expanduser(volume))
        casefolded = os.path.normcase(root).casefold()
        if casefolded in seen:
            raise ProfileError("duplicate declared volume")
        seen.add(casefolded)
        if not os.path.isdir(root):
            raise ProfileError("inaccessible declared volume: " + volume)
        try:
            usage = disk_usage(root)
            total, used, free = int(usage.total), int(usage.used), int(usage.free)
        except (OSError, TypeError, ValueError) as exc:
            raise ProfileError("capacity unavailable for: " + volume) from exc
        if total <= 0 or not 0 <= free <= total:
            raise ProfileError("invalid capacity counters")
        percent = round(free * 100 / total, 2)
        status = ("CRITICAL" if percent < 10 else
                  "BELOW_TARGET" if percent < 20 else "AT_OR_ABOVE_TARGET")
        results.append({"declared_root": root, "total_bytes": total,
                        "used_bytes": used, "free_bytes": free,
                        "free_pct": percent, "capacity_status": status,
                        "target_pct": 20, "critical_pct": 10,
                        "action_authorization": "NONE"})
        resolved_roots.append(root)
    media_type, media_missing = resolve_declared_volumes_media_type(
        resolved_roots, probe=windows_media_probe)
    if media_type is not None:
        metrics["media_type"] = media_type
    elif media_missing:
        missing.append(media_missing)
    else:
        missing.append("media_type: no trusted physical mapping")
    return {"metrics": metrics, "volumes": results, "missing_metrics": missing}

def _root() -> Path:
    from filesteward.policy.paths import runtime_root
    return Path(runtime_root()) / "profiles"

def capture(alias: str, volumes: Sequence[str], *,
            profiles_root: Path | None = None,
            sample_seconds: float = 0.2,
            observer: Callable[..., dict[str, Any]] = observe,
            machine_binding: str | None = None) -> Path:
    alias = _key(alias)
    base = Path(profiles_root) if profiles_root is not None else _root()
    directory = base / alias
    if base.exists():
        _refuse_linked(base, "profile root")
    if directory.exists():
        _refuse_linked(directory, "profile directory")
    directory.mkdir(parents=True, exist_ok=True)
    _refuse_linked(directory, "profile directory")
    lock_path = directory / ".capture.lock"
    try:
        with lock_path.open("x", encoding="utf-8") as lock:
            lock.write("FileSteward capture in progress; investigate before removing\n")
    except FileExistsError as exc:
        raise ProfileError("CAPTURE_BUSY: existing host capture lock; verify owner before recovery") from exc
    try:
        binding_status = _ensure_identity(directory, alias, machine_binding or _binding())
        observed = observer(volumes, sample_seconds=sample_seconds)
        snapshots = directory / "snapshots"
        if snapshots.exists():
            _refuse_linked(snapshots, "snapshots directory")
        snapshots.mkdir(exist_ok=True)
        _refuse_linked(snapshots, "snapshots directory")
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
        result = {"schema_version": SCHEMA, "alias": alias, "snapshot_id": name,
                  "captured_utc": _now(), "os_family": platform.system(),
                  "os_release": platform.release(), "architecture": platform.machine(),
                  "binding_status": binding_status, "observation": observed,
                  "authorization_state": "OBSERVATION_ONLY",
                  "profile_provides_delete_authority": False,
                  "privacy": "LOCAL_ONLY_METADATA"}
        snapshot = snapshots / (name + ".json")
        _create(snapshot, result)
        latest = directory / "latest.json"
        if latest.exists():
            _refuse_linked(latest, "latest pointer")
        _latest(latest, result)
        return snapshot
    finally:
        lock_path.unlink(missing_ok=True)

def load_latest(alias: str, *, profiles_root: Path | None = None) -> dict[str, Any]:
    directory = (Path(profiles_root) if profiles_root is not None else _root()) / _key(alias)
    latest = directory / "latest.json"
    _refuse_linked(directory, "profile directory")
    _refuse_linked(latest, "latest pointer")
    result = _read(latest)
    if result.get("schema_version") != SCHEMA or result.get("alias") != alias:
        raise ProfileError("invalid host/schema binding")
    return result


def compare_latest(alias: str, *, profiles_root: Path | None = None) -> dict[str, Any]:
    """Compare the two newest snapshots of one host; never infer causality."""
    base = Path(profiles_root) if profiles_root is not None else _root()
    directory = base / _key(alias)
    snapshots = directory / "snapshots"
    _refuse_linked(directory, "profile directory")
    if snapshots.exists():
        _refuse_linked(snapshots, "snapshots directory")
    if not snapshots.is_dir():
        raise ProfileError("no captured snapshots")
    files = sorted(snapshots.glob("*.json"))
    if len(files) < 2:
        raise ProfileError("at least two snapshots required")
    _refuse_linked(files[-1], "snapshot")
    _refuse_linked(files[-2], "snapshot")
    previous, current = _read(files[-2]), _read(files[-1])
    for snap in (previous, current):
        if snap.get("schema_version") != SCHEMA or snap.get("alias") != alias:
            raise ProfileError("cross-host or schema-mismatched history")
        if snap.get("profile_provides_delete_authority") is not False:
            raise ProfileError("unsafe snapshot authority marker")
    prior_volumes = {
        row["declared_root"]: row for row in
        previous.get("observation", {}).get("volumes", [])
    }
    diffs = []
    for row in current.get("observation", {}).get("volumes", []):
        root = row["declared_root"]
        older = prior_volumes.get(root)
        diffs.append({
            "declared_root": root,
            "previous_free_pct": older["free_pct"] if older else None,
            "current_free_pct": row["free_pct"],
            "change_free_percentage_points":
                round(row["free_pct"] - older["free_pct"], 2) if older else None,
            "current_capacity_status": row["capacity_status"],
            "comparison_quality": "ROOT_LABEL_MATCH_DEVICE_ID_UNVERIFIED" if older else "NO_COMPARATOR",
        })
    return {
        "schema_version": "filesteward.workstation-profile-comparison/v1",
        "alias": alias,
        "previous_snapshot_id": previous["snapshot_id"],
        "current_snapshot_id": current["snapshot_id"],
        "volumes": diffs,
        "causal_attribution": "NOT_ESTABLISHED",
        "authorization_state": "OBSERVATION_ONLY",
    }

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private read-only workstation profile")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("capture")
    collect.add_argument("--host-key", required=True)
    collect.add_argument("--volume", action="append", required=True)
    collect.add_argument("--sample-seconds", type=float, default=0.2)
    show = commands.add_parser("show")
    show.add_argument("--host-key", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--host-key", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            path = capture(args.host_key, args.volume, sample_seconds=args.sample_seconds)
            print("PROFILE_OBSERVED_ONLY: " + str(path))
        elif args.command == "show":
            print(json.dumps(load_latest(args.host_key), indent=2))
        else:
            print(json.dumps(compare_latest(args.host_key), indent=2))
    except (ProfileError, OSError, ValueError, TypeError) as exc:
        print("profile refused: " + str(exc), file=sys.stderr)
        return 2
    return 0
