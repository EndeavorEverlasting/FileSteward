"""D3 delete-specific irreversible approval proofs."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from filesteward.deletion.approval import (
    DELETE_ACTION,
    DELETE_APPROVAL_SCHEMA,
    build_delete_approval,
    canonical_item_set_hash,
    load_delete_approval,
    preflight_identity_digest,
    request_permanent_delete_set,
    validate_delete_approval,
    write_delete_approval,
)
from filesteward.deletion.manifest import DELETE_MANIFEST_SCHEMA
from filesteward.deletion.preflight import PREFLIGHT_SCHEMA_VERSION


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_item(path: Path, *, item_id: str, projected: int | None = None) -> dict[str, Any]:
    st = os.lstat(path)
    size = int(st.st_size)
    reclaim = size if projected is None else projected
    return {
        "item_id": item_id,
        "path": str(path.resolve()),
        "item_type": "FILE",
        "disposition": "RECLAIM_PROVEN",
        "evidence": "synthetic",
        "contract_source": "test",
        "logical_size_bytes": size,
        "allocated_size_bytes": size,
        "projected_reclaim_bytes": reclaim,
        "reclaim_basis": "synthetic",
        "projection_quality": "allocated-evidence",
        "protection_check": "UNRELATED",
        "is_managed": False,
        "is_cloud_placeholder": False,
        "is_symlink": False,
        "is_reparse_point": False,
        "link_count": 1,
        "modified_at": float(st.st_mtime),
        "source_run_id": "run-d3",
        "source_cleanup_plan_sha256": "a" * 64,
        "identity": {
            "path": str(path.resolve()),
            "item_type": "FILE",
            "logical_size_bytes": size,
            "allocated_size_bytes": size,
            "modified_at": float(st.st_mtime),
            "link_count": 1,
        },
        "intended_action": "QUARANTINE",
        "reversibility": "REVERSIBLE_QUARANTINE",
    }


def _manifest(items: list[dict[str, Any]], *, run_id: str = "run-d3") -> dict[str, Any]:
    projected = sum(int(i["projected_reclaim_bytes"]) for i in items)
    return {
        "schema_version": DELETE_MANIFEST_SCHEMA,
        "run_id": run_id,
        "source_cleanup_plan_sha256": "a" * 64,
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


def _pass_preflight(item_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "manifest_schema_version": DELETE_MANIFEST_SCHEMA,
        "overall": "PASS",
        "mutated_filesystem": False,
        "baseline_free_bytes": 1_000_000,
        "recalculated_projected_reclaim_bytes": 100,
        "items": [
            {
                "item_id": item_id,
                "verdict": "PASS",
                "reason_class": "OK",
                "detail": "ok",
            }
            for item_id in item_ids
        ],
    }


def _write_pair(
    tmp_path: Path, manifest: dict[str, Any], preflight: dict[str, Any]
) -> tuple[Path, Path]:
    m_path = tmp_path / "delete-manifest.json"
    p_path = tmp_path / "delete-preflight.json"
    m_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    p_path.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return m_path, p_path


class TestBuildAndRoundTrip:
    def test_build_validate_write_load(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        f1 = scan / "a.bin"
        f2 = scan / "b.bin"
        f1.write_bytes(b"1234")
        f2.write_bytes(b"567890")
        items = [_file_item(f1, item_id="z-item"), _file_item(f2, item_id="a-item")]
        manifest = _manifest(items)
        preflight = _pass_preflight(["a-item", "z-item"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)

        # Unsorted input ids become canonical sorted order.
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["z-item", "a-item"],
            irreversible_confirmation="I-UNDERSTAND-IRREVERSIBLE",
            created_at_unix=1_700_000_000.0,
        )
        assert record["schema_version"] == DELETE_APPROVAL_SCHEMA
        assert record["action"] == DELETE_ACTION
        assert record["approved_item_ids"] == ["a-item", "z-item"]
        assert record["item_count"] == 2
        assert record["item_set_hash"] == canonical_item_set_hash(["a-item", "z-item"])
        assert record["delete_manifest_sha256"] == _sha256_file(m_path)
        assert record["preflight_sha256"] == _sha256_file(p_path)
        assert record["projected_reclaim_bytes"] == 4 + 6
        assert record["authorization_state"] == "APPROVED_FOR_ACTION"

        errors = validate_delete_approval(record, m_path, p_path)
        assert errors == ()

        out = tmp_path / "delete-approval.json"
        write_delete_approval(out, record)
        loaded = load_delete_approval(out)
        assert loaded["item_set_hash"] == record["item_set_hash"]
        assert validate_delete_approval(loaded, m_path, p_path) == ()

    def test_request_permanent_delete_set_does_not_authorize(
        self, tmp_path: Path
    ) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "x.bin"
        target.write_bytes(b"xx")
        manifest = _manifest([_file_item(target, item_id="item-1")])
        request = request_permanent_delete_set(manifest)
        assert request["requested_action"] == DELETE_ACTION
        assert request["authorization_state"] == "UNAPPROVED"
        assert manifest["intended_action"] == "QUARANTINE"
        assert "delete-approval" in request["note"]


class TestNegativeFixtures:
    def test_quarantine_schema_and_action_rejected(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "q.bin"
        target.write_bytes(b"q")
        manifest = _manifest([_file_item(target, item_id="item-q")])
        preflight = _pass_preflight(["item-q"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        quarantine = {
            "schema_version": "filesteward.approval/v1",
            "run_id": "run-d3",
            "action": "QUARANTINE",
            "authorization_state": "APPROVED_FOR_ACTION",
            "approved_item_ids": ["item-q"],
            "item_count": 1,
            "item_set_hash": canonical_item_set_hash(["item-q"]),
            "delete_manifest_sha256": _sha256_file(m_path),
            "preflight_sha256": _sha256_file(p_path),
            "preflight_overall": "PASS",
            "projected_reclaim_bytes": 1,
            "irreversible_confirmation": "token",
            "created_at_unix": 1.0,
        }
        errors = validate_delete_approval(quarantine, m_path, p_path)
        assert any("quarantine" in e.casefold() for e in errors)

    def test_digest_drift_manifest_and_preflight(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "d.bin"
        target.write_bytes(b"drift")
        manifest = _manifest([_file_item(target, item_id="item-d")])
        preflight = _pass_preflight(["item-d"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-d"],
            irreversible_confirmation="token-ok",
        )
        m_path.write_text(m_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        errors = validate_delete_approval(record, m_path, p_path)
        assert any("delete_manifest_sha256 drift" in e for e in errors)

        # Restore manifest bytes; drift preflight.
        _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-d"],
            irreversible_confirmation="token-ok",
        )
        p_path.write_text(p_path.read_text(encoding="utf-8").replace("PASS", "PASS "), encoding="utf-8")
        # Invalid JSON would fail load; rewrite with overall still PASS but different bytes.
        drifted = copy.deepcopy(preflight)
        drifted["detail_note"] = "stale"
        p_path.write_text(json.dumps(drifted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        errors = validate_delete_approval(record, m_path, p_path)
        assert any("preflight_sha256 drift" in e for e in errors)

    def test_preflight_fail_rejected(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "f.bin"
        target.write_bytes(b"fail")
        manifest = _manifest([_file_item(target, item_id="item-f")])
        preflight = _pass_preflight(["item-f"])
        preflight["overall"] = "FAIL"
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        with pytest.raises(ValueError, match="PASS"):
            build_delete_approval(
                manifest=m_path,
                preflight=p_path,
                approved_item_ids=["item-f"],
                irreversible_confirmation="token",
            )

    def test_item_mismatch_count_and_duplicates(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "c.bin"
        target.write_bytes(b"cc")
        manifest = _manifest([_file_item(target, item_id="item-c")])
        preflight = _pass_preflight(["item-c"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-c"],
            irreversible_confirmation="token",
        )
        bad = dict(record)
        bad["item_count"] = 99
        errors = validate_delete_approval(bad, m_path, p_path)
        assert any("item_count" in e for e in errors)

        bad2 = dict(record)
        bad2["approved_item_ids"] = ["item-c", "item-c"]
        bad2["item_count"] = 2
        bad2["item_set_hash"] = canonical_item_set_hash(["item-c", "item-c"])
        errors = validate_delete_approval(bad2, m_path, p_path)
        assert any("duplicate" in e for e in errors)

        bad3 = dict(record)
        bad3["approved_item_ids"] = ["ghost-id"]
        bad3["item_count"] = 1
        bad3["item_set_hash"] = canonical_item_set_hash(["ghost-id"])
        bad3["projected_reclaim_bytes"] = 0
        errors = validate_delete_approval(bad3, m_path, p_path)
        assert any("unknown" in e for e in errors)

    def test_projected_mismatch(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "p.bin"
        target.write_bytes(b"proj")
        manifest = _manifest([_file_item(target, item_id="item-p")])
        preflight = _pass_preflight(["item-p"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-p"],
            irreversible_confirmation="token",
        )
        bad = dict(record)
        bad["projected_reclaim_bytes"] = int(record["projected_reclaim_bytes"]) + 50
        errors = validate_delete_approval(bad, m_path, p_path)
        assert any("projected_reclaim_bytes mismatch" in e for e in errors)

    def test_blocked_dispositions(self, tmp_path: Path) -> None:
        for disposition in ("HUMAN_REVIEW", "UNKNOWN", "PROTECTED"):
            case_dir = tmp_path / disposition
            scan = case_dir / "scan"
            scan.mkdir(parents=True)
            target = scan / f"{disposition}.bin"
            target.write_bytes(b"xx")
            item = _file_item(target, item_id=f"item-{disposition}")
            item["disposition"] = disposition
            manifest = _manifest([item])
            preflight = _pass_preflight([item["item_id"]])
            m_path, p_path = _write_pair(case_dir, manifest, preflight)
            with pytest.raises(ValueError, match=disposition):
                build_delete_approval(
                    manifest=m_path,
                    preflight=p_path,
                    approved_item_ids=[item["item_id"]],
                    irreversible_confirmation="token",
                )

    def test_wrong_action_and_run_id(self, tmp_path: Path) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "w.bin"
        target.write_bytes(b"w")
        manifest = _manifest([_file_item(target, item_id="item-w")])
        preflight = _pass_preflight(["item-w"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-w"],
            irreversible_confirmation="token",
        )
        bad_action = dict(record)
        bad_action["action"] = "QUARANTINE"
        errors = validate_delete_approval(bad_action, m_path, p_path)
        assert any("quarantine" in e.casefold() or "action" in e for e in errors)

        bad_run = dict(record)
        bad_run["run_id"] = "other-run"
        errors = validate_delete_approval(bad_run, m_path, p_path)
        assert any("run_id mismatch" in e for e in errors)

    def test_manifest_quarantine_intended_action_is_not_authority(
        self, tmp_path: Path
    ) -> None:
        """Manifest intended_action=QUARANTINE must not block/authorize delete approval."""

        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "lane.bin"
        target.write_bytes(b"lane")
        manifest = _manifest([_file_item(target, item_id="item-lane")])
        assert manifest["intended_action"] == "QUARANTINE"
        preflight = _pass_preflight(["item-lane"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-lane"],
            irreversible_confirmation="token",
        )
        assert record["action"] == DELETE_ACTION
        assert validate_delete_approval(record, m_path, p_path) == ()

    def test_directory_null_projected_binds_as_zero(self, tmp_path: Path) -> None:
        """Directory container rows with null projected reclaim must not block approve."""

        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "f.bin"
        target.write_bytes(b"bytes")
        empty_dir = scan / "empty-dir"
        empty_dir.mkdir()
        file_item = _file_item(target, item_id="item-file", projected=5)
        dir_item = {
            "item_id": "item-dir",
            "path": str(empty_dir.resolve()),
            "item_type": "DIRECTORY",
            "disposition": "RECLAIM_PROVEN",
            "evidence": "synthetic",
            "contract_source": "test",
            "logical_size_bytes": 0,
            "allocated_size_bytes": 0,
            "projected_reclaim_bytes": None,
            "reclaim_basis": "container",
            "projection_quality": "container-row",
            "protection_check": "UNRELATED",
            "is_managed": False,
            "is_cloud_placeholder": False,
            "is_symlink": False,
            "is_reparse_point": False,
            "link_count": 1,
            "modified_at": 0.0,
            "source_run_id": "run-d3",
            "source_cleanup_plan_sha256": "a" * 64,
            "identity": {
                "path": str(empty_dir.resolve()),
                "item_type": "DIRECTORY",
                "logical_size_bytes": 0,
                "allocated_size_bytes": 0,
                "modified_at": 0.0,
                "link_count": 1,
            },
            "intended_action": "QUARANTINE",
            "reversibility": "REVERSIBLE_QUARANTINE",
        }
        # Build from file-only first so helper totals stay numeric, then attach
        # the null-projected directory row for the approve path under test.
        manifest = _manifest([file_item])
        manifest["items"].append(dir_item)
        manifest["item_count"] = 2
        preflight = _pass_preflight(["item-file", "item-dir"])
        m_path, p_path = _write_pair(tmp_path, manifest, preflight)
        record = build_delete_approval(
            manifest=m_path,
            preflight=p_path,
            approved_item_ids=["item-file", "item-dir"],
            irreversible_confirmation="token",
        )
        assert record["projected_reclaim_bytes"] == 5
        assert validate_delete_approval(record, m_path, p_path) == ()


class TestPreflightIdentityDigest:
    def test_path_vs_mapping_digest(self, tmp_path: Path) -> None:
        payload = _pass_preflight(["x"])
        path = tmp_path / "delete-preflight.json"
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        assert preflight_identity_digest(path) == _sha256_file(path)
        # Mapping digest uses canonical compact JSON — may differ from pretty file.
        assert len(preflight_identity_digest(payload)) == 64
