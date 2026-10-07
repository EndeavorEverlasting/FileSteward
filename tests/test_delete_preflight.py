"""D2 delete-preflight: fail-closed, no-mutation proofs."""

from __future__ import annotations

from safe_capacity_fixtures import ownership_binding, resolver_for

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from filesteward.deletion.preflight import (
    MANIFEST_SCHEMA_VERSION,
    PREFLIGHT_SCHEMA_VERSION,
    ReasonClass,
    run_preflight as _run_preflight,
    write_preflight_receipt,
)
from filesteward.protect import ProtectedRoot

# ---------------------------------------------------------------------------
# Helpers — construct frozen delete-manifest dicts without D1 producer
# ---------------------------------------------------------------------------


def run_preflight(manifest, **kwargs):
    kwargs.setdefault("ownership_resolver", resolver_for(manifest["items"]))
    return _run_preflight(manifest, **kwargs)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _file_identity(path: Path) -> dict[str, Any]:
    st = os.lstat(path)
    nlink = getattr(st, "st_nlink", 1)
    if not isinstance(nlink, int) or nlink <= 0:
        nlink = os.stat(os.fspath(path), follow_symlinks=False).st_nlink
    # Use platform allocation when known; otherwise leave null so preflight
    # compares logical size only (POSIX st_blocks*512 often exceeds st_size).
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


def _dir_identity(path: Path) -> dict[str, Any]:
    st = os.lstat(path)
    return {
        "path": str(path.resolve()),
        "item_type": "DIRECTORY",
        "logical_size_bytes": 0,
        "allocated_size_bytes": 0,
        "modified_at": float(st.st_mtime),
        "link_count": 1,
    }


def _item_from_file(
    path: Path,
    *,
    item_id: str,
    plan_sha: str,
    run_id: str = "run-preflight-synth",
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
        "ownership": ownership_binding(identity["path"]),
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _item_from_dir(
    path: Path,
    *,
    item_id: str,
    plan_sha: str,
    run_id: str = "run-preflight-synth",
) -> dict[str, Any]:
    identity = _dir_identity(path)
    return {
        "item_id": item_id,
        "path": identity["path"],
        "item_type": "DIRECTORY",
        "disposition": "RECLAIM_PROVEN",
        "evidence": "synthetic",
        "contract_source": "test",
        "logical_size_bytes": 0,
        "allocated_size_bytes": 0,
        "projected_reclaim_bytes": 0,
        "reclaim_basis": "container-row",
        "projection_quality": "container-row",
        "protection_check": "UNRELATED",
        "is_managed": False,
        "is_cloud_placeholder": False,
        "is_symlink": False,
        "is_reparse_point": False,
        "link_count": 1,
        "modified_at": identity["modified_at"],
        "source_run_id": run_id,
        "source_cleanup_plan_sha256": plan_sha,
        "identity": identity,
        "ownership": ownership_binding(identity["path"]),
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _manifest(
    items: list[dict[str, Any]],
    *,
    plan_sha: str,
    run_id: str = "run-preflight-synth",
    schema_version: str = MANIFEST_SCHEMA_VERSION,
) -> dict[str, Any]:
    logical = sum(int(i.get("logical_size_bytes") or 0) for i in items)
    allocated = sum(int(i.get("allocated_size_bytes") or 0) for i in items)
    projected = sum(int(i.get("projected_reclaim_bytes") or 0) for i in items)
    return {
        "schema_version": schema_version,
        "run_id": run_id,
        "source_cleanup_plan_sha256": plan_sha,
        "authorization_state": "UNAPPROVED",
        "intended_action": "QUARANTINE",
        "item_count": len(items),
        "totals": {
            "logical_size_bytes": logical,
            "allocated_size_bytes": allocated,
            "projected_reclaim_bytes": projected,
            "projection_quality": "allocated-evidence",
        },
        "untouched": {
            "human_review_count": 0,
            "protected_count": 0,
            "unknown_count": 0,
            "keep_proven_count": 0,
            "note": "synthetic fixture",
        },
        "items": items,
    }


def _snapshot(path: Path) -> tuple[int, float, bytes]:
    st = os.lstat(path)
    data = path.read_bytes() if path.is_file() else b""
    return int(st.st_size), float(st.st_mtime), data


def _make_plan(tmp: Path, content: bytes = b"cleanup-plan-v1\n") -> tuple[Path, str]:
    plan = tmp / "cleanup-plan.csv"
    plan.write_bytes(content)
    return plan, _sha256_file(plan)


# ---------------------------------------------------------------------------
# Spike: lstat identity match vs mismatch without mutation
# ---------------------------------------------------------------------------


class TestIdentitySpike:
    def test_lstat_match_and_mismatch_without_mutation(self, tmp_path: Path) -> None:
        target = tmp_path / "spike.txt"
        target.write_bytes(b"hello-preflight")
        before = _snapshot(target)
        identity = _file_identity(target)
        st = os.lstat(target)
        assert int(st.st_size) == identity["logical_size_bytes"]
        assert abs(float(st.st_mtime) - float(identity["modified_at"])) <= 1.0

        # Mismatch simulation: compare against drifted expected values.
        drifted_size = identity["logical_size_bytes"] + 99
        assert int(st.st_size) != drifted_size

        after = _snapshot(target)
        assert after == before


# ---------------------------------------------------------------------------
# PASS path + receipt writer
# ---------------------------------------------------------------------------


class TestPassPath:
    def test_regular_file_pass_and_receipt(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "ok.bin"
        target.write_bytes(b"ABCDEFGH")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-ok", plan_sha=plan_sha)
        before = _snapshot(target)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(
            manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
        )
        assert result.overall == "PASS"
        assert result.mutated_filesystem is False
        assert result.baseline_free_bytes is not None
        assert result.baseline_free_bytes >= 0
        assert result.items[0].verdict == "PASS"
        assert result.items[0].reason_class == ReasonClass.OK
        assert result.recalculated_projected_reclaim_bytes is not None

        receipt = tmp_path / "delete-preflight.json"
        write_preflight_receipt(receipt, result)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        assert payload["schema_version"] == PREFLIGHT_SCHEMA_VERSION
        assert payload["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
        assert payload["overall"] == "PASS"
        assert payload["mutated_filesystem"] is False
        assert isinstance(payload["baseline_free_bytes"], int)
        assert _snapshot(target) == before

    def test_delete_permanently_still_dry_run(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "still-here.txt"
        target.write_bytes(b"do-not-delete")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-perm", plan_sha=plan_sha)
        item["intended_action"] = "DELETE_PERMANENTLY"
        manifest = _manifest([item], plan_sha=plan_sha)
        manifest["intended_action"] = "DELETE_PERMANENTLY"
        manifest["authorization_state"] = "APPROVED_FOR_ACTION"
        before = _snapshot(target)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "PASS"
        assert result.mutated_filesystem is False
        assert target.exists()
        assert _snapshot(target) == before


# ---------------------------------------------------------------------------
# Fail-closed classes
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_schema_mismatch(self, tmp_path: Path) -> None:
        plan, plan_sha = _make_plan(tmp_path)
        manifest = _manifest([], plan_sha=plan_sha, schema_version="filesteward.delete-manifest/v0")
        result = run_preflight(manifest, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[0].reason_class == ReasonClass.SCHEMA_MISMATCH
        assert result.mutated_filesystem is False

    def test_digest_drift(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "a.txt"
        target.write_bytes(b"a")
        plan, plan_sha = _make_plan(tmp_path, b"original-plan\n")
        item = _item_from_file(target, item_id="item-digest", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        # Mutate the plan after manifest was sealed.
        plan.write_bytes(b"tampered-plan\n")
        before = _snapshot(target)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert any(v.reason_class == ReasonClass.DIGEST_DRIFT for v in result.items)
        assert _snapshot(target) == before

    def test_identity_missing(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        ghost = scan_root / "gone.txt"
        ghost.write_bytes(b"temp")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(ghost, item_id="item-missing", plan_sha=plan_sha)
        ghost.unlink()
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.IDENTITY_MISSING

    def test_identity_size_mtime_drift(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "drift.txt"
        target.write_bytes(b"v1")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-drift", plan_sha=plan_sha)
        # Material size change after identity sealed.
        time.sleep(0.05)
        target.write_bytes(b"v2-changed-content")
        after_change = _snapshot(target)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.IDENTITY_DRIFT
        assert _snapshot(target) == after_change

    def test_item_type_mismatch(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "was-file"
        target.write_bytes(b"x")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-type", plan_sha=plan_sha)
        target.unlink()
        target.mkdir()
        # Identity still claims FILE.
        item["item_type"] = "FILE"
        item["identity"]["item_type"] = "FILE"
        item["path"] = str(target.resolve())
        item["identity"]["path"] = item["path"]
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.ITEM_TYPE_MISMATCH

    def test_symlink_fail_closed(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        real = scan_root / "real.txt"
        real.write_bytes(b"payload")
        link = scan_root / "link.txt"
        try:
            link.symlink_to(real)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        plan, plan_sha = _make_plan(tmp_path)
        # Seal identity as if it were a normal file, then the path is a symlink.
        item = _item_from_file(real, item_id="item-symlink", plan_sha=plan_sha)
        item["path"] = str(link.resolve()) if not link.is_symlink() else str(link)
        # Prefer lexical path without following.
        item["path"] = str((scan_root / "link.txt").absolute())
        item["identity"]["path"] = item["path"]
        before_real = _snapshot(real)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.REPARSE_OR_SYMLINK
        assert _snapshot(real) == before_real

    def test_reparse_detection_unit_with_stub(self, tmp_path: Path) -> None:
        """Unit-test reparse fail-closed via stubbed lstat attributes."""
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "maybe-reparse.txt"
        target.write_bytes(b"x")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-reparse", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        before = _snapshot(target)

        real_lstat = os.lstat

        class _St:
            def __init__(self, base: os.stat_result) -> None:
                self.st_mode = base.st_mode
                self.st_size = base.st_size
                self.st_mtime = base.st_mtime
                self.st_nlink = getattr(base, "st_nlink", 1) or 1
                self.st_file_attributes = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
                self.st_blocks = getattr(base, "st_blocks", None)

        def fake_lstat(path: str | bytes | os.PathLike[str]) -> Any:
            base = real_lstat(path)
            if Path(os.fspath(path)).name == "maybe-reparse.txt":
                return _St(base)
            return base

        with mock.patch("os.lstat", side_effect=fake_lstat):
            result = run_preflight(
                manifest, scan_root=scan_root, cleanup_plan_path=plan
            )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.REPARSE_OR_SYMLINK
        assert _snapshot(target) == before

    def test_junction_if_available(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("junctions are Windows-specific")
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        real_dir = scan_root / "realdir"
        real_dir.mkdir()
        (real_dir / "child.txt").write_bytes(b"c")
        junction = scan_root / "junction"
        # mklink /J requires shell; use ctypes CreateSymbolicLinkW with directory flag
        # or subprocess. Prefer cmd mklink /J.
        import subprocess

        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(real_dir)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            pytest.skip(f"junction creation unavailable: {completed.stderr}")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_dir(real_dir, item_id="item-junc", plan_sha=plan_sha)
        item["path"] = str(junction)
        item["identity"]["path"] = str(junction)
        item["item_type"] = "DIRECTORY"
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.REPARSE_OR_SYMLINK

    def test_protection_hit(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        protected = scan_root / "repo"
        protected.mkdir()
        target = protected / "secret.txt"
        target.write_bytes(b"secret")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-prot", plan_sha=plan_sha)
        # Stale flag says unrelated; preflight must rebuild and hit.
        item["protection_check"] = "UNRELATED"
        manifest = _manifest([item], plan_sha=plan_sha)
        before = _snapshot(target)

        result = run_preflight(
            manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
            protection_roots=[ProtectedRoot(path=str(protected), source="test")],
        )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.PROTECTION_HIT
        assert _snapshot(target) == before

    def test_managed_path(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        managed = scan_root / "managed"
        managed.mkdir()
        target = managed / "m.txt"
        target.write_bytes(b"m")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-managed", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(
            manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
            managed_paths=[managed],
        )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.MANAGED_PATH

    def test_cloud_placeholder_flag(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "cloudish.txt"
        target.write_bytes(b"c")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-cloud", plan_sha=plan_sha)
        item["is_cloud_placeholder"] = True
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.CLOUD_PLACEHOLDER

    def test_cloud_placeholder_attrs_stub(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "placeholder.txt"
        target.write_bytes(b"p")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-ph", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        before = _snapshot(target)

        real_lstat = os.lstat

        class _St:
            def __init__(self, base: os.stat_result) -> None:
                self.st_mode = base.st_mode
                self.st_size = base.st_size
                self.st_mtime = base.st_mtime
                self.st_nlink = getattr(base, "st_nlink", 1) or 1
                self.st_file_attributes = 0x1000  # OFFLINE
                self.st_blocks = getattr(base, "st_blocks", None)

        def fake_lstat(path: str | bytes | os.PathLike[str]) -> Any:
            base = real_lstat(path)
            if Path(os.fspath(path)).name == "placeholder.txt":
                return _St(base)
            return base

        with mock.patch("os.lstat", side_effect=fake_lstat):
            result = run_preflight(
                manifest, scan_root=scan_root, cleanup_plan_path=plan
            )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.CLOUD_PLACEHOLDER
        assert _snapshot(target) == before

    def test_directory_child_set_extra(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        d = scan_root / "dir"
        d.mkdir()
        child = d / "known.txt"
        child.write_bytes(b"k")
        extra = d / "extra.txt"
        extra.write_bytes(b"e")
        plan, plan_sha = _make_plan(tmp_path)
        items = [
            _item_from_dir(d, item_id="item-dir", plan_sha=plan_sha),
            _item_from_file(child, item_id="item-child", plan_sha=plan_sha),
            # extra.txt deliberately omitted from approved set
        ]
        before_extra = _snapshot(extra)
        manifest = _manifest(items, plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        dir_verdict = next(v for v in result.items if v.item_id == "item-dir")
        assert dir_verdict.reason_class == ReasonClass.DIRECTORY_CHILD_DRIFT
        assert _snapshot(extra) == before_extra

    def test_directory_child_set_missing(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        d = scan_root / "dir"
        d.mkdir()
        child = d / "known.txt"
        child.write_bytes(b"k")
        plan, plan_sha = _make_plan(tmp_path)
        items = [
            _item_from_dir(d, item_id="item-dir", plan_sha=plan_sha),
            _item_from_file(child, item_id="item-child", plan_sha=plan_sha),
        ]
        # Seal, then remove approved child.
        child.unlink()
        manifest = _manifest(items, plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        # Directory drift or missing child — either is fail-closed.
        classes = {v.reason_class for v in result.items}
        assert ReasonClass.DIRECTORY_CHILD_DRIFT in classes or (
            ReasonClass.IDENTITY_MISSING in classes
        )

    def test_directory_child_set_exact_pass(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        d = scan_root / "dir"
        d.mkdir()
        child = d / "known.txt"
        child.write_bytes(b"k")
        plan, plan_sha = _make_plan(tmp_path)
        items = [
            _item_from_dir(d, item_id="item-dir", plan_sha=plan_sha),
            _item_from_file(child, item_id="item-child", plan_sha=plan_sha),
        ]
        before = _snapshot(child)
        manifest = _manifest(items, plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "PASS"
        assert all(v.verdict == "PASS" for v in result.items)
        assert _snapshot(child) == before

    def test_hardlink_ambiguity(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        a = scan_root / "a.txt"
        b = scan_root / "b.txt"
        a.write_bytes(b"shared")
        try:
            os.link(a, b)
        except OSError as exc:
            pytest.skip(f"hardlink creation unavailable: {exc}")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(a, item_id="item-hl", plan_sha=plan_sha)
        # Force identity to claim exclusive link even if OS reports 2.
        item["link_count"] = 1
        item["identity"]["link_count"] = 1
        before = _snapshot(a)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.HARDLINK_AMBIGUITY
        assert _snapshot(a) == before

    def test_locked_or_denied_lstat(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "locked.txt"
        target.write_bytes(b"x")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-lock", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        before = _snapshot(target)

        def boom(path: str | bytes | os.PathLike[str]) -> Any:
            if Path(os.fspath(path)).name == "locked.txt":
                raise PermissionError(13, "Permission denied", os.fspath(path))
            return os.stat(path, follow_symlinks=False)

        with mock.patch("os.lstat", side_effect=boom):
            result = run_preflight(
                manifest, scan_root=scan_root, cleanup_plan_path=plan
            )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.LOCKED_OR_DENIED
        assert _snapshot(target) == before

    def test_readonly_unsupported(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "ro.txt"
        target.write_bytes(b"ro")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-ro", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)
        before = _snapshot(target)

        real_lstat = os.lstat

        class _St:
            def __init__(self, base: os.stat_result) -> None:
                self.st_mode = base.st_mode
                self.st_size = base.st_size
                self.st_mtime = base.st_mtime
                self.st_nlink = getattr(base, "st_nlink", 1) or 1
                self.st_file_attributes = 0x1  # READONLY
                self.st_blocks = getattr(base, "st_blocks", None)

        def fake_lstat(path: str | bytes | os.PathLike[str]) -> Any:
            base = real_lstat(path)
            if Path(os.fspath(path)).name == "ro.txt":
                return _St(base)
            return base

        with mock.patch("os.lstat", side_effect=fake_lstat):
            result = run_preflight(
                manifest, scan_root=scan_root, cleanup_plan_path=plan
            )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.UNSUPPORTED_SEMANTICS
        assert _snapshot(target) == before

    def test_sparse_compressed_uncertainty(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "sparse.txt"
        target.write_bytes(b"s")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-sparse", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)

        real_lstat = os.lstat

        class _St:
            def __init__(self, base: os.stat_result) -> None:
                self.st_mode = base.st_mode
                self.st_size = base.st_size
                self.st_mtime = base.st_mtime
                self.st_nlink = getattr(base, "st_nlink", 1) or 1
                self.st_file_attributes = 0x200  # SPARSE
                self.st_blocks = None  # cannot prove allocated

        def fake_lstat(path: str | bytes | os.PathLike[str]) -> Any:
            base = real_lstat(path)
            if Path(os.fspath(path)).name == "sparse.txt":
                return _St(base)
            return base

        with mock.patch("os.lstat", side_effect=fake_lstat):
            result = run_preflight(
                manifest, scan_root=scan_root, cleanup_plan_path=plan
            )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.UNSUPPORTED_SEMANTICS

    def test_path_escape(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_bytes(b"out")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(outside, item_id="item-escape", plan_sha=plan_sha)
        before = _snapshot(outside)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.PATH_ESCAPE
        assert _snapshot(outside) == before

    def test_long_path_fail_closed(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        # Construct a path string that exceeds MAX_PATH without creating it.
        long_name = "x" * 230
        long_path = scan_root / long_name / ("y" * 40) / "z.txt"
        plan, plan_sha = _make_plan(tmp_path)
        identity = {
            "path": str(long_path),
            "item_type": "FILE",
            "logical_size_bytes": 1,
            "allocated_size_bytes": 1,
            "modified_at": 1.0,
            "link_count": 1,
        }
        item = {
            "item_id": "item-long",
            "path": str(long_path),
            "item_type": "FILE",
            "disposition": "RECLAIM_PROVEN",
            "evidence": "synthetic",
            "contract_source": "test",
            "logical_size_bytes": 1,
            "allocated_size_bytes": 1,
            "projected_reclaim_bytes": 1,
            "reclaim_basis": "test",
            "projection_quality": "test",
            "protection_check": "UNRELATED",
            "is_managed": False,
            "is_cloud_placeholder": False,
            "is_symlink": False,
            "is_reparse_point": False,
            "link_count": 1,
            "modified_at": 1.0,
            "source_run_id": "run",
            "source_cleanup_plan_sha256": plan_sha,
            "identity": identity,
        "ownership": ownership_binding(identity["path"]),
            "intended_action": "QUARANTINE",
            "reversibility": "REVERSIBLE_QUARANTINE",
        }
        manifest = _manifest([item], plan_sha=plan_sha)
        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.UNSUPPORTED_SEMANTICS


class TestMutatedFilesystemInvariant:
    def test_receipt_always_false(self, tmp_path: Path) -> None:
        result = run_preflight(
            {
                "schema_version": "wrong",
                "items": [],
                "source_cleanup_plan_sha256": "0" * 64,
            }
        )
        assert result.mutated_filesystem is False
        out = tmp_path / "delete-preflight.json"
        write_preflight_receipt(out, result)
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["mutated_filesystem"] is False


class TestSafetyRepairs:
    def test_cleanup_plan_missing_fail_closed(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "ok.bin"
        target.write_bytes(b"ABCDEFGH")
        plan_sha = "a" * 64
        item = _item_from_file(target, item_id="item-plan", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=None)
        assert result.overall == "FAIL"
        assert any(v.reason_class == ReasonClass.CLEANUP_PLAN_MISSING for v in result.items)

        missing = tmp_path / "cleanup-plan.csv"
        result2 = run_preflight(
            manifest, scan_root=scan_root, cleanup_plan_path=missing
        )
        assert result2.overall == "FAIL"
        assert any(
            v.reason_class == ReasonClass.CLEANUP_PLAN_MISSING for v in result2.items
        )

    def test_content_sha256_mismatch(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "hashed.bin"
        target.write_bytes(b"v1-content")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-hash", plan_sha=plan_sha)
        wrong = "0" * 64
        item["content_sha256"] = wrong
        item["identity"]["content_sha256"] = wrong
        # Equal-size rewrite with restored mtime still fails on hash.
        st = os.lstat(target)
        target.write_bytes(b"v2-content")
        os.utime(target, (st.st_atime, st.st_mtime))
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.IDENTITY_DRIFT
        assert "digest" in result.items[-1].detail.casefold()

    def test_symlink_ancestor_fail_closed(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        real = scan_root / "real"
        real.mkdir(parents=True)
        target = real / "nested.bin"
        target.write_bytes(b"nested")
        link_dir = scan_root / "linkdir"
        try:
            link_dir.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        linked = link_dir / "nested.bin"
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-anc", plan_sha=plan_sha)
        item["path"] = str(linked)
        item["identity"]["path"] = str(linked)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class in {
            ReasonClass.REPARSE_OR_SYMLINK,
            ReasonClass.PATH_ESCAPE,
        }

    def test_protection_loaded_from_run_context(self, tmp_path: Path) -> None:
        from filesteward.deletion.preflight import load_run_protection_context

        scan_root = tmp_path / "scan"
        protected = scan_root / "repo"
        protected.mkdir(parents=True)
        target = protected / "secret.txt"
        target.write_bytes(b"secret")
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": "run-prot",
                    "protected_roots": [
                        {"path": str(protected), "source": "operator-declared"}
                    ],
                    "managed_paths": [],
                }
            ),
            encoding="utf-8",
        )
        roots, managed = load_run_protection_context(run_dir)
        assert managed == ()
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-prot2", plan_sha=plan_sha)
        item["protection_check"] = "UNRELATED"
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(
            manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
            protection_roots=roots,
            managed_paths=managed,
        )
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.PROTECTION_HIT

    def test_malformed_run_json_fails_closed(self, tmp_path: Path) -> None:
        from filesteward.deletion.preflight import load_run_protection_context

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "run.json").write_text("{not-json", encoding="utf-8")
        with pytest.raises(ValueError, match="run.json"):
            load_run_protection_context(run_dir)

    def test_malformed_exclusions_csv_fails_closed(self, tmp_path: Path) -> None:
        from filesteward.deletion.preflight import load_run_protection_context

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "protected-exclusions.csv").write_bytes(b"\xff\xfe\x00bad")
        with pytest.raises(ValueError, match="protected-exclusions"):
            load_run_protection_context(run_dir)

    def test_exclusion_ancestor_scan_root_not_protection_root(
        self, tmp_path: Path
    ) -> None:
        """ANCESTOR exclusion paths must not become ProtectedRoot entries.

        Live Temp blocker: protected-exclusions.csv records the scan root as
        an ANCESTOR row; promoting that path to a protection root makes every
        reclaim candidate under the scan root PROTECTION_HIT/DESCENDANT.
        """
        from filesteward.deletion.preflight import load_run_protection_context

        scan_root = tmp_path / "scan"
        nested_git = scan_root / "nested-repo"
        nested_git.mkdir(parents=True)
        (nested_git / ".git").mkdir()
        sibling = scan_root / "reclaim.bin"
        sibling.write_bytes(b"reclaim-ok")
        under_git = nested_git / "secret.bin"
        under_git.write_bytes(b"secret")

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": "run-csv-overmatch",
                    "protected_roots": [
                        {
                            "path": str(nested_git.resolve()),
                            "source": "git-repository",
                        }
                    ],
                    "managed_paths": [],
                }
            ),
            encoding="utf-8",
        )
        # Canonical exclusions header has no explicit root column; path of the
        # ANCESTOR row is the scan root and must be ignored for root load.
        (run_dir / "protected-exclusions.csv").write_text(
            "\n".join(
                [
                    "item_id,path,disposition,protection_reason,"
                    "protection_source,relationship",
                    (
                        f"ex-ancestor,{scan_root.resolve()},PROTECTED,"
                        "ancestor of protected root,git-repository,ANCESTOR"
                    ),
                    (
                        f"ex-self,{nested_git.resolve()},PROTECTED,"
                        "git repository root,git-repository,SELF"
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

        roots, managed = load_run_protection_context(run_dir)
        assert managed == ()
        root_paths = {str(Path(r.path).resolve()).casefold() for r in roots}
        assert str(nested_git.resolve()).casefold() in root_paths
        assert str(scan_root.resolve()).casefold() not in root_paths
        assert len(roots) == 1

        plan, plan_sha = _make_plan(tmp_path)
        ok_item = _item_from_file(sibling, item_id="item-sibling", plan_sha=plan_sha)
        hit_item = _item_from_file(
            under_git, item_id="item-under-git", plan_sha=plan_sha
        )
        ok_manifest = _manifest([ok_item], plan_sha=plan_sha)
        hit_manifest = _manifest([hit_item], plan_sha=plan_sha)

        ok_result = run_preflight(
            ok_manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
            protection_roots=roots,
            managed_paths=managed,
        )
        assert ok_result.overall == "PASS"
        assert ok_result.items[-1].reason_class == ReasonClass.OK

        hit_result = run_preflight(
            hit_manifest,
            scan_root=scan_root,
            cleanup_plan_path=plan,
            protection_roots=roots,
            managed_paths=managed,
        )
        assert hit_result.overall == "FAIL"
        assert hit_result.items[-1].reason_class == ReasonClass.PROTECTION_HIT

    def test_empty_digest_with_existing_plan_fails(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "ok.bin"
        target.write_bytes(b"ABCDEFGH")
        plan, _plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-empty-digest", plan_sha="")
        manifest = _manifest([item], plan_sha="")

        result = run_preflight(
            manifest, scan_root=scan_root, cleanup_plan_path=plan
        )
        assert result.overall == "FAIL"
        assert any(v.reason_class == ReasonClass.DIGEST_DRIFT for v in result.items)

    def test_item_digest_without_top_level_fails(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "ok.bin"
        target.write_bytes(b"ABCDEFGH")
        item = _item_from_file(target, item_id="item-only", plan_sha="b" * 64)
        manifest = _manifest([item], plan_sha="")
        # No cleanup-plan.csv on disk; item still declares a plan digest.
        result = run_preflight(
            manifest, scan_root=scan_root, cleanup_plan_path=None
        )
        assert result.overall == "FAIL"
        assert any(v.reason_class == ReasonClass.DIGEST_DRIFT for v in result.items)

    def test_invalid_content_sha256_token_fails(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "hashed.bin"
        target.write_bytes(b"v1-content")
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-bad-hash", plan_sha=plan_sha)
        item["content_sha256"] = "not-a-valid-sha256"
        item["identity"]["content_sha256"] = "not-a-valid-sha256"
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "FAIL"
        assert result.items[-1].reason_class == ReasonClass.IDENTITY_DRIFT
        assert "invalid" in result.items[-1].detail.casefold()

    def test_pass_seals_content_sha256(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        # Isolate process temp: pytest tmp lives under real Temp, which now
        # uses size+mtime seal; this test proves full SHA-256 seal elsewhere.
        isolated = tmp_path / "isolated-temp"
        isolated.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(isolated))

        scan_root = tmp_path / "scan"
        scan_root.mkdir()
        target = scan_root / "seal.bin"
        payload = b"seal-me-please"
        target.write_bytes(payload)
        plan, plan_sha = _make_plan(tmp_path)
        item = _item_from_file(target, item_id="item-seal", plan_sha=plan_sha)
        manifest = _manifest([item], plan_sha=plan_sha)

        result = run_preflight(manifest, scan_root=scan_root, cleanup_plan_path=plan)
        assert result.overall == "PASS"
        assert result.items[-1].content_sha256 == _sha256_bytes(payload)
        receipt = result.to_dict()
        assert receipt["items"][-1]["content_sha256"] == _sha256_bytes(payload)

    def test_realpath_escape_from_scan_root(self, tmp_path: Path) -> None:
        from filesteward.deletion.preflight import reparse_or_path_escape

        scan_root = tmp_path / "scan"
        outside = tmp_path / "outside"
        scan_root.mkdir()
        outside.mkdir()
        target = outside / "escaped.bin"
        target.write_bytes(b"escaped")
        link = scan_root / "escape-link"
        try:
            link.symlink_to(target, target_is_directory=False)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        # Lexical path is under scan_root, but realpath escapes.
        result = reparse_or_path_escape(link, scan_root)
        assert result is not None
        assert result[0] in {ReasonClass.REPARSE_OR_SYMLINK, ReasonClass.PATH_ESCAPE}
