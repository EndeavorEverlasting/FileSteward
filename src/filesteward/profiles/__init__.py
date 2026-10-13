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

SCHEMA = "filesteward.workstation-performance-profile/v1"
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")

class ProfileError(ValueError):
    pass

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
            psutil_module: Any = None) -> dict[str, Any]:
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
               "media_type: no trusted physical mapping",
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
    if directory.is_symlink():
        raise ProfileError("profile directory is symlink")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ProfileError("profile directory was replaced by symlink")
    binding_status = _ensure_identity(directory, alias, machine_binding or _binding())
    observed = observer(volumes, sample_seconds=sample_seconds)
    snapshots = directory / "snapshots"
    if snapshots.is_symlink():
        raise ProfileError("snapshots directory is symlink")
    snapshots.mkdir(exist_ok=True)
    if snapshots.is_symlink():
        raise ProfileError("snapshots directory changed to symlink")
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
    _latest(directory / "latest.json", result)
    return snapshot

def load_latest(alias: str, *, profiles_root: Path | None = None) -> dict[str, Any]:
    directory = (Path(profiles_root) if profiles_root is not None else _root()) / _key(alias)
    if directory.is_symlink():
        raise ProfileError("profile directory is symlink")
    result = _read(directory / "latest.json")
    if result.get("schema_version") != SCHEMA or result.get("alias") != alias:
        raise ProfileError("invalid host/schema binding")
    return result

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private read-only workstation profile")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("capture")
    collect.add_argument("--host-key", required=True)
    collect.add_argument("--volume", action="append", required=True)
    collect.add_argument("--sample-seconds", type=float, default=0.2)
    show = commands.add_parser("show")
    show.add_argument("--host-key", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            path = capture(args.host_key, args.volume, sample_seconds=args.sample_seconds)
            print("PROFILE_OBSERVED_ONLY: " + str(path))
        else:
            print(json.dumps(load_latest(args.host_key), indent=2))
    except (ProfileError, OSError, ValueError, TypeError) as exc:
        print("profile refused: " + str(exc), file=sys.stderr)
        return 2
    return 0
