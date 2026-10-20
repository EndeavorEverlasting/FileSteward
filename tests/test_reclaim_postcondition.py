"""K4 receipt postcondition: action/owner/revision health beyond free-space delta."""

from __future__ import annotations

import json
from pathlib import Path

from filesteward.deletion.postcondition import (
    PostconditionState,
    SEMANTIC_EXECUTOR_ID,
    build_reclaim_postcondition,
    item_action_record,
)
from filesteward.deletion.reclaim import ReclaimState
from filesteward.deletion.receipt import load_delete_receipt
from test_delete_execute import _file_item, _prepare_run, execute_permanent_delete


def test_item_action_record_binds_before_and_after_revisions() -> None:
    before = {
        "path": "C:/tmp/a",
        "action_kind": "RAW_DELETE_REGENERABLE_ARTIFACT",
        "owner_ids": ["synthetic-generator"],
        "graph_revision_id": "rev-before",
        "evidence_digest": "d1",
    }
    after = dict(before)
    after["graph_revision_id"] = "rev-after"
    after["evidence_digest"] = "d2"
    row = item_action_record(
        item_id="i1",
        path="C:/tmp/a",
        status="SUCCEEDED",
        reason_class="OK",
        manifest_ownership=before,
        immediate_ownership=after,
    )
    assert row["action_kind"] == "RAW_DELETE_REGENERABLE_ARTIFACT"
    assert row["owner_ids"] == ["synthetic-generator"]
    assert row["graph_revision_before"] == "rev-before"
    assert row["graph_revision_after"] == "rev-after"


def test_postcondition_verified_when_ownership_and_reclaim_hold() -> None:
    actions = [
        item_action_record(
            item_id="i1",
            path="C:/tmp/a",
            status="SUCCEEDED",
            reason_class="OK",
            manifest_ownership={
                "action_kind": "RAW_DELETE_REGENERABLE_ARTIFACT",
                "owner_ids": ["owner-a"],
                "graph_revision_id": "g1",
                "evidence_digest": "e1",
            },
            immediate_ownership={
                "action_kind": "RAW_DELETE_REGENERABLE_ARTIFACT",
                "owner_ids": ["owner-a"],
                "graph_revision_id": "g1",
                "evidence_digest": "e1",
            },
        )
    ]
    post = build_reclaim_postcondition(
        item_actions=actions,
        reclaim={"state": ReclaimState.VERIFIED_RECLAIM},
        free_bytes_before=1000,
        free_bytes_after=2000,
        residual_paths=(),
    )
    assert post["state"] == PostconditionState.VERIFIED
    assert post["semantic_executor"] == SEMANTIC_EXECUTOR_ID
    assert post["action_kinds"] == ["RAW_DELETE_REGENERABLE_ARTIFACT"]
    assert post["owner_ids"] == ["owner-a"]
    assert post["capacity"]["free_bytes_delta"] == 1000


def test_postcondition_unverified_without_ownership_binding() -> None:
    actions = [
        {
            "item_id": "i1",
            "path": "C:/tmp/a",
            "status": "SUCCEEDED",
            "reason_class": "OK",
            "action_kind": None,
            "owner_ids": [],
            "graph_revision_before": None,
            "graph_revision_after": None,
        }
    ]
    post = build_reclaim_postcondition(
        item_actions=actions,
        reclaim={"state": ReclaimState.VERIFIED_RECLAIM},
        free_bytes_before=1000,
        free_bytes_after=2000,
        residual_paths=(),
    )
    assert post["state"] == PostconditionState.UNVERIFIED


def test_postcondition_partial_on_mixed_outcomes() -> None:
    ok = item_action_record(
        item_id="ok",
        path="C:/tmp/a",
        status="SUCCEEDED",
        reason_class="OK",
        manifest_ownership={
            "action_kind": "RAW_DELETE_REGENERABLE_ARTIFACT",
            "owner_ids": ["o"],
            "graph_revision_id": "g",
            "evidence_digest": "e",
        },
        immediate_ownership={
            "action_kind": "RAW_DELETE_REGENERABLE_ARTIFACT",
            "owner_ids": ["o"],
            "graph_revision_id": "g",
            "evidence_digest": "e",
        },
    )
    bad = item_action_record(
        item_id="bad",
        path="C:/tmp/b",
        status="FAILED",
        reason_class="IDENTITY_DRIFT",
        manifest_ownership=None,
        immediate_ownership=None,
    )
    post = build_reclaim_postcondition(
        item_actions=[ok, bad],
        reclaim={"state": ReclaimState.PARTIAL_RECLAIM},
        free_bytes_before=1000,
        free_bytes_after=1500,
        residual_paths=("C:/tmp/b",),
    )
    assert post["state"] == PostconditionState.PARTIAL


def test_execute_receipt_includes_k4_postcondition(tmp_path: Path) -> None:
    scan = tmp_path / "scan"
    nested = scan / "cache"
    nested.mkdir(parents=True)
    target = nested / "a.bin"
    target.write_bytes(b"K4" * 2048)
    run_dir, _, approval = _prepare_run(
        tmp_path, [_file_item(target, item_id="file-a")], scan
    )
    result = execute_permanent_delete(
        run_dir=run_dir,
        manifest=run_dir / "delete-manifest.json",
        approval=approval,
        preflight=run_dir / "delete-preflight.approved.json",
        scan_root=scan,
    )
    assert result.overall == "SUCCEEDED"
    receipt = load_delete_receipt(result.receipt_path)
    assert receipt is not None
    assert receipt["semantic_executor"] == SEMANTIC_EXECUTOR_ID
    assert "postcondition" in receipt
    post = receipt["postcondition"]
    assert post["state"] in {
        PostconditionState.VERIFIED,
        PostconditionState.PARTIAL,
        PostconditionState.UNVERIFIED,
    }
    assert post["semantic_executor"] == SEMANTIC_EXECUTOR_ID
    assert receipt["items"]
    action = receipt["items"][0]["action"]
    assert action["action_kind"] == "RAW_DELETE_REGENERABLE_ARTIFACT"
    assert action["graph_revision_before"]
    assert action["graph_revision_after"]
    assert action["owner_ids"]
    # Bytes alone must not be the only proof field.
    assert "capacity" in post
    assert "owner_ids" in post
    assert "graph_revision_before" in post
    assert "graph_revision_after" in post
    # Ensure receipt JSON remains loadable/stable.
    raw = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert raw["postcondition"]["state"] == post["state"]
