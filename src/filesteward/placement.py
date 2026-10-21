"""Read-only canonical artifact path locator for explicit workstation identities.

Authority is the tracked FileSteward CANONICAL-PATHS and ownership graph policy.
A placement proposal never copies, deletes or authorizes a filesystem mutation.
A sidecar hash attests only snapshot integrity, never live cloud freshness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

_CONTRACT_REL = "harness/contracts/canonical-artifact-placement.v1.json"
_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_ROLES = {"GIT_TRACKED_CONTRACT", "READ_ONLY_SHARED_SNAPSHOT"}
_MAX_SIDECAR_BYTES = 32768
_MAX_HASH_BYTES = 50000000


def _repo_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file() or not (root / "docs/agent/CANONICAL-PATHS.md").is_file():
        raise ValueError("FILESTEWARD_CHECKOUT_AUTHORITY_MISSING")
    return root


def load_contract(root: Path | None = None) -> dict[str, Any]:
    path = (root or _repo_root()) / _CONTRACT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_contract(payload)
    return payload


def _component(value: Any) -> bool:
    return isinstance(value, str) and bool(_COMPONENT.fullmatch(value)) and value not in (".", "..")


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or ":" in value:
        return False
    p = PurePosixPath(value)
    return not p.is_absolute() and all(_component(x) for x in p.parts) and "//" not in value


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "filesteward.canonical-artifact-placement/v1":
        raise ValueError("SCHEMA_UNRECOGNIZED")
    if contract.get("canonical_path_authority") != "docs/agent/CANONICAL-PATHS.md":
        raise ValueError("CANONICAL_PATH_OWNER_CHANGED")
    policy = contract.get("path_policy") or {}
    if policy.get("repo_template") != "<USERPROFILE>/dev/<repo>" or policy.get("shared_snapshot_template") != "<USERPROFILE>/dev/_shared/canonical-artifacts/<namespace>/<filename>":
        raise ValueError("PATH_POLICY_DRIFT")
    if set(x.lower() for x in policy.get("forbidden_components", [])) != {"desktop", "documents", "onedrive", "backups"}:
        raise ValueError("FORBIDDEN_ROOT_DRIFT")
    seen = set()
    records = contract.get("artifact_catalog")
    if not isinstance(records, list) or not records:
        raise ValueError("CATALOG_EMPTY")
    for item in records:
        name, role = item.get("id"), item.get("role")
        if not _component(name) or name in seen or role not in _ROLES:
            raise ValueError("CATALOG_ID_OR_ROLE_INVALID")
        seen.add(name)
        if role == "GIT_TRACKED_CONTRACT":
            if item.get("authority") != "GIT" or not _component(item.get("repo")) or not _safe_relative(item.get("relative_path")):
                raise ValueError("REPO_ARTIFACT_INVALID:" + name)
            if item.get("owner") != "EndeavorEverlasting/" + item["repo"]:
                raise ValueError("REPO_OWNER_MISMATCH:" + name)
        else:
            if item.get("authority") != "GOOGLE_DRIVE" or not _component(item.get("namespace")) or not _component(item.get("filename")):
                raise ValueError("SNAPSHOT_ARTIFACT_INVALID:" + name)
            if item.get("provenance_sidecar") != item["filename"].rsplit(".", 1)[0] + ".provenance.json":
                raise ValueError("PROVENANCE_PATH_MISMATCH:" + name)
            if not str(item.get("authority_url", "")).startswith("https://drive.google.com/"):
                raise ValueError("SOURCE_AUTHORITY_INVALID:" + name)


def _forbidden(path: Path, blocked: set[str]) -> bool:
    return any(part.lower() in blocked for part in path.parts)


def _existing_link_ancestor(path: Path, stop: Path) -> bool:
    """No symlink or Windows reparse point in inspected profile->destination chain.

    On non-Windows os.stat's file attributes may not exist. Unreadable
    components are never treated as safe.
    """
    paths = [stop]
    try:
        relative = path.relative_to(stop)
    except ValueError:
        return True
    cursor = stop
    for part in relative.parts:
        cursor = cursor / part
        paths.append(cursor)
    for candidate in paths:
        try:
            details = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if stat.S_ISLNK(details.st_mode) or getattr(details, "st_file_attributes", 0) & 0x400:
            return True
    return False


def _git_identity(repo_path: Path, expected_owner: str, *, command: Callable | None = None) -> str:
    """An exact-root and origin check, no network, no checkout mutations."""
    def run(args):
        if command is not None:
            return command(args, repo_path)
        return subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True, text=True, timeout=8, check=False)
    try:
        root = run(["rev-parse", "--show-toplevel"])
        origin = run(["remote", "get-url", "origin"])
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return "GIT_UNAVAILABLE"
    if root.returncode != 0 or origin.returncode != 0:
        return "GIT_NOT_VERIFIED"
    try:
        if Path(root.stdout.strip()).resolve(strict=True) != repo_path.resolve(strict=True):
            return "GIT_ROOT_MISMATCH"
    except OSError:
        return "GIT_ROOT_UNVERIFIED"
    remote = origin.stdout.strip().rstrip("/")
    suffix = expected_owner + ".git"
    valid = {"https://github.com/" + expected_owner, "https://github.com/" + suffix,
             "git@github.com:" + expected_owner, "git@github.com:" + suffix,
             "ssh://git@github.com/" + expected_owner, "ssh://git@github.com/" + suffix}
    return "GIT_OWNER_CONFIRMED" if remote in valid else "GIT_OWNER_CONFLICT"


def _snapshot_state(path: Path, sidecar: Path, authority_url: str) -> tuple[str, str]:
    if path.exists() and not path.is_file():
        return "SNAPSHOT_PATH_CONFLICT", "the configured file path is occupied by a non-file"
    if not path.is_file():
        return "SNAPSHOT_MISSING", "no file was installed by this read-only command"
    try:
        if path.is_symlink() or sidecar.is_symlink():
            return "SNAPSHOT_UNSAFE_LINK", "snapshot or provenance sidecar is a symlink"
        size = path.stat().st_size
        if size > _MAX_HASH_BYTES:
            return "SNAPSHOT_UNVERIFIED", "snapshot exceeds bounded hashing limit"
        if not sidecar.is_file() or sidecar.stat().st_size > _MAX_SIDECAR_BYTES:
            return "SNAPSHOT_UNVERIFIED", "provenance sidecar missing/oversized"
        side = json.loads(sidecar.read_text(encoding="utf-8"))
        if (side.get("schema") != "filesteward.reference-snapshot-provenance/v1" or
            side.get("source_url") != authority_url or
            not re.fullmatch(r"[0-9a-f]{64}", str(side.get("sha256", ""))) or
            not isinstance(side.get("captured_at"), str) or len(side["captured_at"]) < 10):
            return "SNAPSHOT_UNVERIFIED", "sidecar missing exact source/identity fields"
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
        if hasher.hexdigest() != side["sha256"]:
            return "SNAPSHOT_HASH_CONFLICT", "local snapshot and sidecar hash disagree"
        return "SNAPSHOT_INTEGRITY_PROVED_FRESHNESS_UNKNOWN", "integrity is local-only; Google Drive revision/freshness not checked"
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return "SNAPSHOT_UNVERIFIED", "snapshot could not be safely verified"


def resolve(host_key: str, *, profile: Path, hostname: str | None, contract: dict[str, Any],
            probe: bool = False, git_command: Callable | None = None) -> dict[str, Any]:
    validate_contract(contract)
    if not _component(host_key):
        raise ValueError("INVALID_HOST_ALIAS")
    if not profile.is_absolute() or str(profile) in ("/", "\\") or ".." in profile.parts:
        raise ValueError("INVALID_PROFILE_ROOT")
    blocked = {x.lower() for x in contract["path_policy"]["forbidden_components"]}
    dev = profile / "dev"
    invalid_root = _forbidden(profile, blocked) or _existing_link_ancestor(dev, profile)
    reports = []
    for item in contract["artifact_catalog"]:
        if item["role"] == "GIT_TRACKED_CONTRACT":
            repo = dev / item["repo"]
            target = repo / item["relative_path"]
        else:
            repo = None
            target = dev / "_shared" / "canonical-artifacts" / item["namespace"] / item["filename"]
        unsafe = invalid_root or _forbidden(target, blocked) or _existing_link_ancestor(target, profile)
        state = "UNSAFE_ROOT" if unsafe else "PROPOSED_NOT_OBSERVED"
        reason = "forbidden component, unreadable path or linked ancestor" if unsafe else "path derived from tracked policy; existence not inspected"
        if probe and not unsafe:
            if not dev.is_dir():
                state, reason = "DEV_ROOT_MISSING", "canonical dev root absent; no fallback used"
            elif item["role"] == "GIT_TRACKED_CONTRACT":
                if not repo.is_dir():
                    state, reason = "REPO_NOT_OBSERVED", "canonical repo checkout absent; do not substitute another clone"
                else:
                    owner = _git_identity(repo, item["owner"], command=git_command)
                    if owner != "GIT_OWNER_CONFIRMED":
                        state, reason = owner, "repository root/origin not certified; preserve existing content"
                    elif target.is_file():
                        state, reason = "LOCAL_GIT_CONTRACT_PRESENT", "git origin and exact checkout root matched; revision and upstream integration not checked"
                    else:
                        state, reason = "GIT_CONTRACT_MISSING", "repo verified but artifact not present on checked-out revision"
            else:
                sidecar = target.with_name(item["provenance_sidecar"])
                state, reason = _snapshot_state(target, sidecar, item["authority_url"])
        reports.append({"id": item["id"], "role": item["role"], "authority": item["authority"],
                        "target": str(target), "state": state, "reason": reason,
                        "owner": item.get("owner") or item.get("authority_url"),
                        "consumer_env": item.get("consumer_env"),
                        "provisioning": "NO_MUTATION_ALLOWED"})
    return {"schema": "filesteward.canonical-artifact-placement-receipt/v1",
            "host_alias": host_key, "observed_hostname": hostname or None,
            "host_binding_state": "HOST_ALIAS_NOT_HARDWARE_ATTESTED",
            "profile_key": "windows-userprofile", "profile_root": str(profile),
            "observed": probe,
            "canonical_dev_root": str(dev),
            "records": reports,
            "changes_applied": 0,
            "master_authority_unchanged": True,
            "status": "BLOCKED_UNSAFE_ROOT" if invalid_root else "READ_ONLY_PROBE" if probe else "PATH_PROPOSAL_ONLY"}


def _redact(result: dict[str, Any], profile: Path) -> dict[str, Any]:
    """The default console projection protects per-user absolute path details."""
    clone = json.loads(json.dumps(result))
    base = str(profile)
    clone["profile_root"] = "<USERPROFILE>"
    clone["canonical_dev_root"] = "<USERPROFILE>/dev"
    for record in clone["records"]:
        full = record["target"]
        if not (full == base or full.startswith(base + os.sep)):
            raise ValueError("REDACTION_FAILED")
        record["target"] = "<USERPROFILE>" + full[len(base):]
    return clone


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-key", required=True, help="Explicit alias, e.g. DTop or PTop; NOT hostname attestation")
    parser.add_argument("--probe", action="store_true", help="Read only exact proposed local paths and Git identity")
    parser.add_argument("--save-private", action="store_true", help="Write local private receipt only under FileSteward ignored var/artifact-placement")
    parser.add_argument("--check", action="store_true", help="Validate tracked placement contract only")
    args = parser.parse_args(argv)
    try:
        contract = load_contract()
        if args.check:
            print(json.dumps({"state": "CONTRACT_VALID", "records": len(contract["artifact_catalog"])}))
            return 0
        profile_var = "USERPROFILE" if os.name == "nt" else "HOME"
        root = os.environ.get(profile_var)
        if not root:
            raise ValueError("USER_PROFILE_NOT_AVAILABLE")
        profile = Path(root)
        report = resolve(args.host_key, profile=profile, hostname=os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME"), contract=contract, probe=args.probe)
        if args.save_private:
            checkout = _repo_root()
            expected = profile / "dev" / "FileSteward"
            if checkout != expected or report["status"] == "BLOCKED_UNSAFE_ROOT":
                raise ValueError("PRIVATE_RECEIPT_REQUIRES_ADMITTED_CANONICAL_CHECKOUT")
            output = checkout / "var" / "artifact-placement"
            if _existing_link_ancestor(output, profile) or _forbidden(output, {"desktop", "documents", "onedrive", "backups"}):
                raise ValueError("PRIVATE_RECEIPT_ROOT_UNSAFE")
            output.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            target = output / (args.host_key + "." + stamp + ".json")
            if target.exists() or target.is_symlink():
                raise ValueError("EXISTING_RECEIPT_PRESERVE_NO_OVERWRITE")
            with target.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
                handle.write("\n")
        print(json.dumps(_redact(report, profile), indent=2))
        return 3 if report["status"] == "BLOCKED_UNSAFE_ROOT" else 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "PLACEMENT_BLOCKED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())