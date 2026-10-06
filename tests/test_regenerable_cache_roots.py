"""Regenerable-cache execute allowlist and size+mtime identity seal."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from filesteward import cli as cli_mod
from filesteward.deletion.preflight import run_preflight
from filesteward.deletion.regenerable import (
    allows_size_mtime_identity_seal,
    is_under_regenerable_cache_allowlist,
    regenerable_cache_allowlist_roots,
)
from filesteward.policy.paths import normalize_declared_path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    st = os.lstat(path)
    nlink = getattr(st, "st_nlink", 1)
    if not isinstance(nlink, int) or nlink <= 0:
        nlink = os.stat(os.fspath(path), follow_symlinks=False).st_nlink
    blocks = getattr(st, "st_blocks", None)
    if isinstance(blocks, int) and blocks > 0:
        allocated: int | None = blocks * 512
    else:
        allocated = None
    return {
        "path": str(path.resolve()),
        "item_type": "FILE",
        "logical_size_bytes": int(st.st_size),
        "allocated_size_bytes": allocated,
        "modified_at": float(st.st_mtime),
        "link_count": int(nlink),
    }


def _item_from_file(
    path: Path,
    *,
    item_id: str,
    plan_sha: str,
    run_id: str = "run-regen-synth",
) -> dict[str, Any]:
    identity = _file_identity(path)
    return {
        "item_id": item_id,
        "path": identity["path"],
        "item_type": "FILE",
        "disposition": "RECLAIM_PROVEN",
        "evidence": "synthetic",
        "contract_source": "test",
        "logical_size_bytes": identity["logical_size_bytes"],
        "allocated_size_bytes": identity["allocated_size_bytes"],
        "projected_reclaim_bytes": (
            identity["allocated_size_bytes"]
            if identity["allocated_size_bytes"] is not None
            else identity["logical_size_bytes"]
        ),
        "reclaim_basis": "allocated-evidence",
        "projection_quality": "allocated-evidence",
        "protection_check": "UNRELATED",
        "is_managed": False,
        "is_cloud_placeholder": False,
        "is_symlink": False,
        "is_reparse_point": False,
        "link_count": identity["link_count"],
        "modified_at": identity["modified_at"],
        "source_run_id": run_id,
        "source_cleanup_plan_sha256": plan_sha,
        "identity": identity,
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _manifest(items: list[dict[str, Any]], *, plan_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "filesteward.delete-manifest/v1",
        "run_id": "run-regen-synth",
        "authorization_state": "UNAPPROVED",
        "source_cleanup_plan_sha256": plan_sha,
        "items": items,
    }


def _make_plan(tmp: Path, content: bytes = b"cleanup-plan-v1\n") -> tuple[Path, str]:
    plan = tmp / "cleanup-plan.csv"
    plan.write_bytes(content)
    return plan, _sha256_bytes(content)


def _fake_home_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Return (home, localappdata) with Path.home + LOCALAPPDATA patched.

    Also isolates ``tempfile.gettempdir`` so pytest's real Temp-backed
    ``tmp_path`` is not admitted as the process temp root.
    """

    import tempfile

    isolated_temp = tmp_path / "isolated-temp"
    isolated_temp.mkdir(exist_ok=True)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(isolated_temp))

    home = tmp_path / "home"
    local = home / "AppData" / "Local"
    local.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "ProgramData"))
    return home, local


class TestRegenerableAllowlist:
    def test_npm_cache_under_home_admitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _home, local = _fake_home_local(tmp_path, monkeypatch)
        npm = local / "npm-cache"
        npm.mkdir(parents=True)
        assert is_under_regenerable_cache_allowlist(npm) is True
        assert cli_mod._scan_root_allowed_for_execute(npm) is None

    def test_chrome_cache_admitted_not_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _home, local = _fake_home_local(tmp_path, monkeypatch)
        profile = local / "Google" / "Chrome" / "User Data" / "Default"
        cache = profile / "Cache"
        cache.mkdir(parents=True)
        assert cli_mod._scan_root_allowed_for_execute(cache) is None
        refusal = cli_mod._scan_root_allowed_for_execute(profile)
        assert refusal is not None
        assert "home" in refusal.casefold() or "personal" in refusal.casefold()

    def test_personal_documents_still_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home, _local = _fake_home_local(tmp_path, monkeypatch)
        docs = home / "Documents" / "photos"
        docs.mkdir(parents=True)
        refusal = cli_mod._scan_root_allowed_for_execute(docs)
        assert refusal is not None
        assert "home" in refusal.casefold() or "personal" in refusal.casefold()

    def test_localappdata_ancestor_not_allowlisted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _home, local = _fake_home_local(tmp_path, monkeypatch)
        (local / "npm-cache").mkdir()
        assert is_under_regenerable_cache_allowlist(local) is False
        refusal = cli_mod._scan_root_allowed_for_execute(local)
        assert refusal is not None

    def test_package_cache_listed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pd = tmp_path / "ProgramData"
        pkg = pd / "Package Cache"
        pkg.mkdir(parents=True)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        monkeypatch.setenv("PROGRAMDATA", str(pd))
        roots = regenerable_cache_allowlist_roots()
        assert normalize_declared_path(pkg) in roots
        assert is_under_regenerable_cache_allowlist(pkg) is True
        assert cli_mod._scan_root_allowed_for_execute(pkg) is None


class TestSizeMtimeIdentitySeal:
    def test_allowlisted_root_skips_content_hash_seal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _home, local = _fake_home_local(tmp_path, monkeypatch)
        npm = local / "npm-cache"
        npm.mkdir(parents=True)
        target = npm / "pkg.tgz"
        payload = b"regenerable-cache-bytes"
        target.write_bytes(payload)
        assert allows_size_mtime_identity_seal(npm) is True

        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="npm-1", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        result = run_preflight(manifest, scan_root=npm, cleanup_plan_path=plan)
        assert result.overall == "PASS"
        assert result.items[-1].content_sha256 is None
        assert result.items[-1].verdict == "PASS"

    def test_non_allowlisted_root_still_seals_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        # Isolate process temp so pytest's Temp-backed tmp_path is not treated
        # as an allowlisted regenerable root.
        isolated_temp = tmp_path / "isolated-temp"
        isolated_temp.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(isolated_temp))

        scan = tmp_path / "arbitrary-scan"
        scan.mkdir()
        target = scan / "seal.bin"
        payload = b"must-hash-me"
        target.write_bytes(payload)
        assert allows_size_mtime_identity_seal(scan) is False

        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="hash-1", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        result = run_preflight(manifest, scan_root=scan, cleanup_plan_path=plan)
        assert result.overall == "PASS"
        assert result.items[-1].content_sha256 == _sha256_bytes(payload)

    def test_temp_root_allows_size_mtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        fake_temp = tmp_path / "fake-temp"
        fake_temp.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))
        assert allows_size_mtime_identity_seal(fake_temp / "nested") is True
