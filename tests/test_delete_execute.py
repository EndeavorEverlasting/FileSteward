"""D4B permanent delete + D5 receipt + D6 reclaim proofs (synthetic temp only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from filesteward.deletion.approval import (
    build_delete_approval,
    write_delete_approval,
)
from filesteward.deletion.execute import execute_permanent_delete
from filesteward.deletion.manifest import DELETE_MANIFEST_SCHEMA
from filesteward.deletion.preflight import (
    PREFLIGHT_SCHEMA_VERSION,
    run_preflight,
    write_preflight_receipt,
)
from filesteward.deletion.receipt import DELETE_RECEIPT_FILENAME, load_delete_receipt
from filesteward.deletion.reclaim import ReclaimState, verify_reclaim


def _file_item(path: Path, *, item_id: str) -> dict[str, Any]:
    st = os.lstat(path)
    size = int(st.st_size)
    blocks = getattr(st, "st_blocks", None)
    allocated = blocks * 512 if isinstance(blocks, int) and blocks > 0 else None
    return {
        "item_id": item_id,
        "path": str(path.resolve()),
        "item_type": "FILE",
        "disposition": "RECLAIM_PROVEN",
        "evidence": "synthetic",
        "contract_source": "test",
        "logical_size_bytes": size,
        "allocated_size_bytes": allocated,
        "projected_reclaim_bytes": allocated if allocated is not None else size,
        "reclaim_basis": "synthetic",
        "projection_quality": "allocated-evidence",
        "protection_check": "UNRELATED",
        "is_managed": False,
        "is_cloud_placeholder": False,
        "is_symlink": False,
        "is_reparse_point": False,
        "link_count": getattr(st, "st_nlink", 1) or 1,
        "modified_at": float(st.st_mtime),
        "source_run_id": "run-d4b",
        # Empty digest: synthetic fixtures omit cleanup-plan.csv on purpose.
        "source_cleanup_plan_sha256": "",
        "identity": {
            "path": str(path.resolve()),
            "item_type": "FILE",
            "logical_size_bytes": size,
            "allocated_size_bytes": allocated,
            "modified_at": float(st.st_mtime),
            "link_count": getattr(st, "st_nlink", 1) or 1,
        },
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _dir_item(path: Path, *, item_id: str) -> dict[str, Any]:
    st = os.lstat(path)
    return {
        "item_id": item_id,
        "path": str(path.resolve()),
        "item_type": "DIRECTORY",
        "disposition": "RECLAIM_PROVEN",
        "evidence": "synthetic",
        "contract_source": "test",
        "logical_size_bytes": 0,
        "allocated_size_bytes": 0,
        "projected_reclaim_bytes": 0,
        "reclaim_basis": "container",
        "projection_quality": "container-row",
        "protection_check": "UNRELATED",
        "is_managed": False,
        "is_cloud_placeholder": False,
        "is_symlink": False,
        "is_reparse_point": False,
        "link_count": 1,
        "modified_at": float(st.st_mtime),
        "source_run_id": "run-d4b",
        "source_cleanup_plan_sha256": "",
        "identity": {
            "path": str(path.resolve()),
            "item_type": "DIRECTORY",
            "logical_size_bytes": 0,
            "allocated_size_bytes": 0,
            "modified_at": float(st.st_mtime),
            "link_count": 1,
        },
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
    projected = sum(int(i.get("projected_reclaim_bytes") or 0) for i in items)
    return {
        "schema_version": DELETE_MANIFEST_SCHEMA,
        "run_id": "run-d4b",
        "source_cleanup_plan_sha256": "",
        "authorization_state": "UNAPPROVED",
        "intended_action": "QUARANTINE",
        "item_count": len(items),
        "totals": {
            "logical_size_bytes": projected,
            "allocated_size_bytes": projected,
            "projected_reclaim_bytes": projected,
            "projection_quality": "allocated-evidence",
        },
        "untouched": {
            "human_review_count": 0,
            "protected_count": 0,
            "unknown_count": 0,
            "keep_proven_count": 0,
            "note": "synthetic",
        },
        "items": items,
    }


def _prepare_run(
    tmp_path: Path, items: list[dict[str, Any]], scan_root: Path
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _manifest(items)
    m_path = run_dir / "delete-manifest.json"
    m_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pf = run_preflight(manifest, scan_root=scan_root)
    assert pf.overall == "PASS", [i.to_dict() for i in pf.items]
    pf_path = run_dir / "delete-preflight.json"
    write_preflight_receipt(pf_path, pf)
    # Freeze approval-time preflight identity.
    (run_dir / "delete-preflight.approved.json").write_bytes(pf_path.read_bytes())

    approval = build_delete_approval(
        manifest=m_path,
        preflight=run_dir / "delete-preflight.approved.json",
        approved_item_ids=[str(i["item_id"]) for i in items],
        irreversible_confirmation="SYNTHETIC-IRREVERSIBLE",
    )
    write_delete_approval(run_dir / "delete-approval.json", approval)
    return run_dir, manifest, approval


class TestPermanentDeleteExecutor:
    def test_deletes_files_and_empty_dir_bytes_gone(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        nested = scan / "cache"
        nested.mkdir(parents=True)
        f1 = nested / "a.bin"
        f2 = nested / "b.bin"
        f1.write_bytes(b"A" * 4096)
        f2.write_bytes(b"B" * 8192)
        items = [
            _file_item(f1, item_id="file-a"),
            _file_item(f2, item_id="file-b"),
            _dir_item(nested, item_id="dir-cache"),
        ]
        run_dir, _manifest_data, approval = _prepare_run(tmp_path, items, scan)

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )

        assert result.overall == "SUCCEEDED"
        assert not f1.exists()
        assert not f2.exists()
        assert not nested.exists()
        assert all(i.status == "SUCCEEDED" for i in result.items)
        assert result.receipt_path.is_file()
        receipt = load_delete_receipt(result.receipt_path)
        assert receipt is not None
        assert receipt["mode"] == "DELETE_PERMANENTLY"
        assert receipt["schema_version"].startswith("filesteward.delete-execution-receipt")
        assert result.reclaim is not None
        assert result.reclaim.state in {
            ReclaimState.VERIFIED_RECLAIM,
            ReclaimState.NO_RECLAIM,
            ReclaimState.UNKNOWN,
        }

    def test_refuses_without_valid_approval(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "keep.bin"
        target.write_bytes(b"keep-me")
        items = [_file_item(target, item_id="keep-1")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)
        bad = dict(approval)
        bad["action"] = "QUARANTINE"

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=bad,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert result.overall == "FAILED"
        assert target.exists()
        assert target.read_bytes() == b"keep-me"
        assert result.approval_errors

    def test_path_escape_not_deleted(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"escape")
        # Manifest points outside scan_root; preflight will FAIL PATH_ESCAPE.
        items = [_file_item(outside, item_id="escape-1")]
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = _manifest(items)
        m_path = run_dir / "delete-manifest.json"
        m_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # Build a synthetic PASS preflight for approval binding only (execute will
        # re-run fresh preflight and fail closed).
        synthetic_pf = {
            "schema_version": PREFLIGHT_SCHEMA_VERSION,
            "manifest_schema_version": DELETE_MANIFEST_SCHEMA,
            "overall": "PASS",
            "mutated_filesystem": False,
            "baseline_free_bytes": 1,
            "recalculated_projected_reclaim_bytes": 6,
            "items": [
                {
                    "item_id": "escape-1",
                    "verdict": "PASS",
                    "reason_class": "OK",
                    "detail": "synthetic",
                }
            ],
        }
        pf_path = run_dir / "delete-preflight.approved.json"
        pf_path.write_text(json.dumps(synthetic_pf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        approval = build_delete_approval(
            manifest=m_path,
            preflight=pf_path,
            approved_item_ids=["escape-1"],
            irreversible_confirmation="token",
        )
        write_delete_approval(run_dir / "delete-approval.json", approval)

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=m_path,
            approval=approval,
            preflight=pf_path,
            scan_root=scan,
        )
        assert result.overall == "FAILED"
        assert outside.exists()
        assert any("PASS" in e for e in result.approval_errors)

    def test_interruption_skips_prior_succeeded(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        f1 = scan / "one.bin"
        f2 = scan / "two.bin"
        f1.write_bytes(b"1111")
        f2.write_bytes(b"2222")
        items = [_file_item(f1, item_id="one"), _file_item(f2, item_id="two")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)

        first = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert first.overall == "SUCCEEDED"
        assert not f1.exists() and not f2.exists()

        # Replay: both should SKIP (prior SUCCEEDED, paths absent).
        second = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert all(i.status == "SKIPPED" for i in second.items)
        assert (run_dir / DELETE_RECEIPT_FILENAME).is_file()

    def test_does_not_enlarge_approved_set(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        approved = scan / "approved.bin"
        extra = scan / "extra.bin"
        approved.write_bytes(b"appr")
        extra.write_bytes(b"extra-stay")
        items = [
            _file_item(approved, item_id="only-approved"),
            _file_item(extra, item_id="not-approved"),
        ]
        # Approve only one id.
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = _manifest(items)
        m_path = run_dir / "delete-manifest.json"
        m_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pf = run_preflight(manifest, scan_root=scan)
        assert pf.overall == "PASS"
        write_preflight_receipt(run_dir / "delete-preflight.json", pf)
        (run_dir / "delete-preflight.approved.json").write_bytes(
            (run_dir / "delete-preflight.json").read_bytes()
        )
        approval = build_delete_approval(
            manifest=m_path,
            preflight=run_dir / "delete-preflight.approved.json",
            approved_item_ids=["only-approved"],
            irreversible_confirmation="token",
        )
        write_delete_approval(run_dir / "delete-approval.json", approval)

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=m_path,
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert result.overall == "SUCCEEDED"
        assert not approved.exists()
        assert extra.exists()
        assert extra.read_bytes() == b"extra-stay"
        assert len(result.items) == 1


class TestExecuteSafetyRepairs:
    def test_identity_drift_skips_unlink(self, tmp_path: Path, monkeypatch: Any) -> None:
        from filesteward.deletion import execute as execute_mod
        from filesteward.deletion.preflight import PreflightResult

        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "race.bin"
        target.write_bytes(b"ORIGINAL")
        items = [_file_item(target, item_id="race-1")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)

        # Fresh preflight forced PASS so execute reaches unlink-time revalidation.
        monkeypatch.setattr(
            execute_mod,
            "run_preflight",
            lambda *a, **k: PreflightResult(overall="PASS", mutated_filesystem=False),
        )
        target.write_bytes(b"REPLACED!")

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert target.exists()
        assert target.read_bytes() == b"REPLACED!"
        assert any(i.reason_class == "IDENTITY_DRIFT" for i in result.items)

    def test_protection_from_run_json_blocks_execute(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        protected = scan / "repo"
        protected.mkdir(parents=True)
        target = protected / "secret.bin"
        target.write_bytes(b"secret")
        items = [_file_item(target, item_id="prot-1")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": "run-d4b",
                    "protected_roots": [{"path": str(protected), "source": "test"}],
                    "managed_paths": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert target.exists()
        assert result.overall == "FAILED"
        assert any("PASS" in e for e in result.approval_errors) or any(
            i.reason_class == "PROTECTION_HIT" for i in result.items
        )

    def test_symlink_parent_escape(self, tmp_path: Path) -> None:
        import pytest

        scan = tmp_path / "scan"
        real = scan / "real"
        real.mkdir(parents=True)
        target = real / "victim.bin"
        target.write_bytes(b"via-link")
        link_parent = scan / "via"
        try:
            link_parent.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        linked = link_parent / "victim.bin"
        items = [_file_item(linked, item_id="link-esc")]
        # Seal identity against the lexical linked path.
        items[0]["path"] = str(linked)
        items[0]["identity"]["path"] = str(linked)
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = _manifest(items)
        m_path = run_dir / "delete-manifest.json"
        m_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        synthetic_pf = {
            "schema_version": PREFLIGHT_SCHEMA_VERSION,
            "manifest_schema_version": DELETE_MANIFEST_SCHEMA,
            "overall": "PASS",
            "mutated_filesystem": False,
            "baseline_free_bytes": 1,
            "recalculated_projected_reclaim_bytes": 8,
            "items": [
                {
                    "item_id": "link-esc",
                    "verdict": "PASS",
                    "reason_class": "OK",
                    "detail": "synthetic",
                }
            ],
        }
        pf_path = run_dir / "delete-preflight.approved.json"
        pf_path.write_text(
            json.dumps(synthetic_pf, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        approval = build_delete_approval(
            manifest=m_path,
            preflight=pf_path,
            approved_item_ids=["link-esc"],
            irreversible_confirmation="token",
        )
        write_delete_approval(run_dir / "delete-approval.json", approval)

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=m_path,
            approval=approval,
            preflight=pf_path,
            scan_root=scan,
        )
        assert target.exists()
        assert result.overall == "FAILED"

    def test_equal_size_mtime_rewrite_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        # Isolate process temp so this non-regenerable scan still seals SHA-256.
        isolated = tmp_path / "isolated-temp"
        isolated.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(isolated))

        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "rewrite.bin"
        original = b"SAME-SIZE-PAYLOAD!!"  # 19 bytes
        target.write_bytes(original)
        items = [_file_item(target, item_id="rewrite-1")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)

        # Equal-size rewrite with restored mtime after approval.
        st = os.lstat(target)
        target.write_bytes(b"REWRITTEN-PAYLOAD!!")  # also 19 bytes
        os.utime(target, (st.st_atime, st.st_mtime))

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert target.exists()
        assert target.read_bytes() == b"REWRITTEN-PAYLOAD!!"
        assert result.overall == "FAILED"
        assert (
            any(i.reason_class == "IDENTITY_DRIFT" for i in result.items)
            or any("digest" in e.casefold() for e in result.approval_errors)
            or result.preflight_overall == "FAIL"
        )

    def test_git_root_rediscovered_at_execute(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        repo = scan / "late-repo"
        repo.mkdir(parents=True)
        target = repo / "tracked.bin"
        target.write_bytes(b"git-protected")
        items = [_file_item(target, item_id="git-1")]
        run_dir, _, approval = _prepare_run(tmp_path, items, scan)
        # Create a git marker after approval-time preflight.
        (repo / ".git").mkdir()

        result = execute_permanent_delete(
            run_dir=run_dir,
            manifest=run_dir / "delete-manifest.json",
            approval=approval,
            preflight=run_dir / "delete-preflight.approved.json",
            scan_root=scan,
        )
        assert target.exists()
        assert result.overall == "FAILED"
        assert any("PASS" in e for e in result.approval_errors) or any(
            i.reason_class == "PROTECTION_HIT" for i in result.items
        )


class TestReclaimVerificationUnit:
    def test_verified_partial_none_unknown(self) -> None:
        ok = [{"status": "SUCCEEDED", "item_id": "a"}]
        fail = [{"status": "FAILED", "item_id": "b"}]
        v = verify_reclaim(
            free_bytes_before=1000,
            free_bytes_after=1500,
            item_results=ok,
            residual_paths=(),
        )
        assert v.state == ReclaimState.VERIFIED_RECLAIM

        p = verify_reclaim(
            free_bytes_before=1000,
            free_bytes_after=1200,
            item_results=ok + fail,
            residual_paths=["C:\\x"],
        )
        assert p.state == ReclaimState.PARTIAL_RECLAIM

        n = verify_reclaim(
            free_bytes_before=1000,
            free_bytes_after=1000,
            item_results=ok,
            residual_paths=(),
        )
        assert n.state == ReclaimState.NO_RECLAIM

        u = verify_reclaim(
            free_bytes_before=None,
            free_bytes_after=1000,
            item_results=ok,
        )
        assert u.state == ReclaimState.UNKNOWN
