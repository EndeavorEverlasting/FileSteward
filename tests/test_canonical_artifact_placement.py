"""Synthetic placement tests: no real workstation access or filesystem changes."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from filesteward.placement import load_contract, resolve, validate_contract, _redact

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT)


def _rows(root, probe=False, hostname="actual-machine", git_command=None):
    return resolve("DTop", profile=root, hostname=hostname, contract=CONTRACT,
                   probe=probe, git_command=git_command)


def _by_id(plan, id):
    return next(x for x in plan["records"] if x["id"] == id)


def test_contract_exact_owner_and_legacy_path_authority():
    assert CONTRACT["canonical_path_authority"] == "docs/agent/CANONICAL-PATHS.md"
    assert len(CONTRACT["artifact_catalog"]) >= 6
    existing = (ROOT / "docs/agent/CANONICAL-PATHS.md").read_text(encoding="utf-8")
    for name in ("Desktop", "Documents", "OneDrive", "Backups"):
        assert name in existing
    assert "dev\\FileSteward" in existing or "dev\\\\FileSteward" in existing


def test_proposal_does_not_create_files_or_assume_mount(tmp_path):
    home = tmp_path / "home"
    plan = _rows(home)
    item = _by_id(plan, "upstream-intelligence-source-registry")
    assert item["target"] == str(home / "dev/_shared/canonical-artifacts/upstream-intelligence/source-registry.json")
    assert item["state"] == "PROPOSED_NOT_OBSERVED"
    assert plan["observed"] is False and plan["changes_applied"] == 0
    assert not home.exists()
    assert plan["observed_hostname"] == "actual-machine"
    assert plan["host_binding_state"] == "HOST_ALIAS_NOT_HARDWARE_ATTESTED"
    assert _redact(plan, home)["records"][0]["target"].startswith("<USERPROFILE>/dev/")


def test_each_git_master_stays_in_own_checkout(tmp_path):
    plan = _rows(tmp_path / "DTop")
    assert _by_id(plan,"tokencorridor-design-source-router")["target"].endswith("/dev/TokenCorridor/harness/contracts/design-source-routing.v1.json")
    assert _by_id(plan,"filesteward-canonical-paths")["target"].endswith("/dev/FileSteward/docs/agent/CANONICAL-PATHS.md")
    assert _by_id(plan,"parallaxport-design-reference-index")["target"].endswith("/dev/ParallaxPort/harness/plans/portfolio-cinema/DESIGN_UPSTREAM_REFERENCES_20261019.md")


def test_probe_never_assumes_checkouts_when_dev_absent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    plan = _rows(home, probe=True)
    assert {x["state"] for x in plan["records"]} == {"DEV_ROOT_MISSING"}


def test_existing_git_cannot_claim_other_remote(tmp_path):
    home = tmp_path / "home"
    path = home / "dev" / "TokenCorridor"
    (path / "harness/contracts").mkdir(parents=True)
    (path / "harness/contracts/design-source-routing.v1.json").write_text("{}")
    def git(args, repo):
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, str(path) + "\n", "")
        return subprocess.CompletedProcess(args, 0, "https://github.com/someone-else/TokenCorridor\n", "")
    r = _rows(home, probe=True, git_command=git)
    assert _by_id(r,"tokencorridor-design-source-router")["state"] == "GIT_OWNER_CONFLICT"
    assert "LOCAL_GIT_CONTRACT_PRESENT" not in {x["state"] for x in r["records"]}


def test_git_contract_present_only_with_exact_owner(tmp_path):
    home = tmp_path / "home"
    path = home / "dev" / "TokenCorridor"
    (path / "harness/contracts").mkdir(parents=True)
    (path / "harness/contracts/design-source-routing.v1.json").write_text("{}")
    def git(args, repo):
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, str(path) + "\n", "")
        return subprocess.CompletedProcess(args, 0, "git@github.com:EndeavorEverlasting/TokenCorridor.git\n", "")
    r = _rows(home, probe=True, git_command=git)
    assert _by_id(r,"tokencorridor-design-source-router")["state"] == "LOCAL_GIT_CONTRACT_PRESENT"
    assert _by_id(r,"tokencorridor-prompt-invocation-catalog")["state"] == "GIT_CONTRACT_MISSING"


def test_snapshot_requires_exact_sidecar_but_never_claims_drive_freshness(tmp_path):
    home = tmp_path / "home"
    f = home / "dev/_shared/canonical-artifacts/upstream-intelligence/source-registry.json"
    f.parent.mkdir(parents=True)
    body = b'{"records":[]}'
    f.write_bytes(body)
    r = _rows(home, probe=True)
    assert _by_id(r,"upstream-intelligence-source-registry")["state"] == "SNAPSHOT_UNVERIFIED"
    sidecar = f.with_name("source-registry.provenance.json")
    sidecar.write_text(json.dumps({
        "schema":"filesteward.reference-snapshot-provenance/v1",
        "source_url":"https://drive.google.com/file/d/10rjbCG0Ck_PLkvbSXElNH0oiJ3H8uXVh/view",
        "sha256":hashlib.sha256(body).hexdigest(),
        "captured_at":"2026-10-20T22:00:00Z"
    }),encoding="utf-8")
    r = _rows(home, probe=True)
    assert _by_id(r,"upstream-intelligence-source-registry")["state"] == "SNAPSHOT_INTEGRITY_PROVED_FRESHNESS_UNKNOWN"
    f.write_text("changed")
    assert _by_id(_rows(home,probe=True),"upstream-intelligence-source-registry")["state"] == "SNAPSHOT_HASH_CONFLICT"
    assert sidecar.exists()


def test_symlinks_and_forbidden_roots_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "home"
    parent.mkdir()
    (parent / "dev").symlink_to(outside, target_is_directory=True)
    result = _rows(parent, probe=True)
    assert result["status"] == "BLOCKED_UNSAFE_ROOT"
    assert {x["state"] for x in result["records"]} == {"UNSAFE_ROOT"}
    no = _rows(tmp_path / "OneDrive" / "person", probe=True)
    assert no["status"] == "BLOCKED_UNSAFE_ROOT"


def test_invalid_host_and_contract_traversal_fail(tmp_path):
    with pytest.raises(ValueError, match="INVALID_HOST_ALIAS"):
        resolve("../PTop", profile=tmp_path, hostname=None, contract=CONTRACT)
    changed = json.loads(json.dumps(CONTRACT))
    changed["artifact_catalog"][1]["relative_path"] = "../bad.txt"
    with pytest.raises(ValueError, match="REPO_ARTIFACT_INVALID"):
        validate_contract(changed)


def test_host_aliases_have_independent_observation(tmp_path):
    first = resolve("DTop", profile=tmp_path / "one", hostname="REAL-A", contract=CONTRACT)
    second = resolve("PTop", profile=tmp_path / "two", hostname="REAL-B", contract=CONTRACT)
    assert first["host_alias"] != second["host_alias"]
    assert first["profile_root"] != second["profile_root"]
    assert first["observed_hostname"] != second["observed_hostname"]