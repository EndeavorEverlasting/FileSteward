"""Synthetic regression proof for non-Git learning-workspace protection.

All data live under pytest temporary fixtures, never a user's real teach tree.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from filesteward.classify import CacheContract, evaluate_gates, nominate
from filesteward.deletion.preflight import discover_scan_protection_roots
from filesteward.models import CleanupDisposition, EntryType, InventoryItem
from filesteward.protect import ProtectionIndex, ProtectionRelation
from filesteward.protect.learning import (
    iter_workspace_protection_roots,
    learning_workspace_stage,
)


def _classroom(base: Path, name: str, *, kind: str) -> Path:
    room = base / name
    room.mkdir(parents=True)
    if kind == "ghidra":
        docs = ("MISSION.md", "METHOD.md", "GUIDANCE.md", "NOTES.md")
        dirs = ("lessons", "learning-records", "upstreams")
    elif kind == "tax-budget":
        docs = ("START-HERE.md", "MISSION.md", "NOTES.md")
        dirs = ("lessons", "learning-records", "upstreams", "personal", "businesses", "reference")
    else:
        raise ValueError(kind)
    for filename in docs:
        (room / filename).write_text("Synthetic learning marker", encoding="utf-8")
    for dirname in dirs:
        (room / dirname).mkdir()
    return room


@pytest.mark.parametrize(
    ("files", "folders", "expected"),
    [
        ({"MISSION.md", "METHOD.md", "NOTES.md"}, set(), "confirmed"),
        ({"MISSION.md", "START-HERE.md", "NOTES.md"}, set(), "confirmed"),
        ({"mission.MD", "notes.MD"}, set(), "emerging"),
        ({"MISSION.md"}, {"learning-records"}, "emerging"),
        ({"MISSION.md", "GUIDANCE.md"}, {"upstreams"}, "confirmed"),
        ({"MISSION.md"}, set(), None),
        ({"METHOD.md", "NOTES.md"}, {"lessons"}, None),
        ({"MISSION.md"}, {"businesses", "personal"}, None),
        ({"MISSION.md.bak", "NOTES.md"}, {"lessons"}, None),
    ],
)
def test_learning_stage_is_structure_based_and_case_insensitive(
    files: set[str], folders: set[str], expected: str | None
) -> None:
    assert learning_workspace_stage(files, folders) == expected


def test_detects_both_classrooms_without_claiming_the_parent_or_sibling(
    tmp_path: Path,
) -> None:
    campus = tmp_path / "teach"
    ghidra = _classroom(campus, "ghidra", kind="ghidra")
    tax = _classroom(campus, "tax-budget", kind="tax-budget")
    sibling = tmp_path / "malware-lab"
    sibling.mkdir()
    (sibling / "samples.txt").write_text("not automatically disposable", encoding="utf-8")

    roots = list(iter_workspace_protection_roots(tmp_path))
    assert {path for path, _ in roots} == {ghidra, tax}
    assert all(source == "learning-workspace:confirmed" for _, source in roots)

    index = ProtectionIndex.from_workspace_discovery(tmp_path)
    assert index.relation(ghidra) is ProtectionRelation.SELF
    assert index.relation(ghidra / "upstreams" / "learning" / "pin.md") is ProtectionRelation.DESCENDANT
    assert index.relation(tax / "personal" / "private-budget.csv") is ProtectionRelation.DESCENDANT
    assert index.relation(campus) is ProtectionRelation.ANCESTOR
    assert index.requires_decomposition(campus)
    assert index.relation(sibling) is ProtectionRelation.UNRELATED
    assert not index.is_protected(sibling)


def test_partially_built_non_git_room_is_protected(tmp_path: Path) -> None:
    room = tmp_path / "new-track"
    room.mkdir()
    (room / "MISSION.md").write_text("synthetic", encoding="utf-8")
    (room / "NOTES.md").write_text("synthetic", encoding="utf-8")

    roots = list(iter_workspace_protection_roots(tmp_path))
    assert roots == [(room, "learning-workspace:emerging")]
    assert ProtectionIndex.from_workspace_discovery(tmp_path).is_protected(room / "draft")


def test_name_only_and_unrelated_directories_not_elevated(tmp_path: Path) -> None:
    empty = tmp_path / "teach"
    empty.mkdir()
    shallow = tmp_path / "project"
    shallow.mkdir()
    (shallow / "MISSION.md").write_text("synthetic", encoding="utf-8")
    index = ProtectionIndex.from_workspace_discovery(tmp_path)
    assert index.relation(empty) is ProtectionRelation.UNRELATED
    assert index.relation(shallow) is ProtectionRelation.UNRELATED


def test_git_and_learning_signals_share_a_protected_root(tmp_path: Path) -> None:
    classroom = _classroom(tmp_path, "class", kind="ghidra")
    (classroom / ".git").mkdir()
    roots = list(iter_workspace_protection_roots(tmp_path))
    assert roots == [(classroom, "git-repository+learning-workspace:confirmed")]
    assert ProtectionIndex.from_workspace_discovery(tmp_path).is_protected(classroom / "lessons")


def test_reparse_or_symlinked_classrooms_are_never_traversed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _classroom(outside, "class", kind="ghidra")
    scanned = tmp_path / "scanned"
    scanned.mkdir()
    shortcut = scanned / "shortcut"
    try:
        shortcut.symlink_to(outside / "class", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks unavailable on this host")
    assert list(iter_workspace_protection_roots(scanned)) == []


def test_discovery_never_opens_or_reads_learning_file_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _classroom(tmp_path, "room", kind="ghidra")

    def refuse_content_read(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("protection discovery attempted to read content")

    monkeypatch.setattr(Path, "open", refuse_content_read)
    roots = list(iter_workspace_protection_roots(tmp_path))
    assert len(roots) == 1
    assert roots[0][1].startswith("learning-workspace:")


def test_regenerable_contract_cannot_override_learning_workspace(
    tmp_path: Path,
) -> None:
    room = _classroom(tmp_path, "course", kind="tax-budget")
    descendant = room / "upstreams" / "learnharness" / "generated.bin"
    item = InventoryItem(
        item_id="synthetic-learning-item",
        path=str(descendant),
        entry_type=EntryType.FILE,
        logical_size_bytes=8_000_000_000,
        link_count=1,
    )
    contract = CacheContract(
        contract_id="synthetic.regenerable",
        path_prefix=str(tmp_path),
        description="Synthetic blanket contract that must not beat protected work",
    )
    index = ProtectionIndex.from_workspace_discovery(tmp_path)
    nomination = nominate(
        evaluate_gates(
            item,
            protection=index.relation(item.path),
            contracts=(contract,),
        )
    )
    assert nomination.disposition is CleanupDisposition.PROTECTED


def test_fresh_delete_discovery_detects_newly_created_workspace(
    tmp_path: Path,
) -> None:
    """The deletion path must not rely on only the old scan's protection roots."""

    prior = discover_scan_protection_roots(tmp_path)
    assert prior == ()
    classroom = tmp_path / "new-classroom"
    classroom.mkdir()
    (classroom / "MISSION.md").write_text("synthetic", encoding="utf-8")
    (classroom / "METHOD.md").write_text("synthetic", encoding="utf-8")
    refreshed = discover_scan_protection_roots(tmp_path)
    assert len(refreshed) == 1
    assert refreshed[0].path == str(classroom)
    assert refreshed[0].source == "learning-workspace:emerging"
    assert ProtectionIndex(refreshed).is_protected(classroom / "work-in-progress")


def test_no_drive_letter_or_teach_path_assumption(tmp_path: Path) -> None:
    nested = _classroom(tmp_path / "different" / "home", "algebra", kind="tax-budget")
    assert ProtectionIndex.from_workspace_discovery(tmp_path).is_protected(
        nested / "learning-records" / "session.json"
    )


def test_read_only_cleanup_run_persists_learning_protection_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual scan pipeline must report protected roots and descendants."""

    import csv
    import json

    from filesteward.run import CleanupRun
    from filesteward.policy import paths as path_policy
    from filesteward import run as run_module

    campus = tmp_path / "campus"
    classroom = _classroom(campus, "physics", kind="tax-budget")
    sibling = campus / "unrelated"
    sibling.mkdir()
    (sibling / "scratch.bin").write_bytes(b"synthetic")

    private_runtime = tmp_path / "private-runtime"
    monkeypatch.setattr(path_policy, "runtime_root", lambda: private_runtime)
    monkeypatch.setattr(run_module, "runtime_root", lambda: private_runtime)

    output = private_runtime / "runs" / "synthetic-learning"
    CleanupRun(campus, output).execute()

    metadata = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert {
        (row["path"], row["source"])
        for row in metadata["protected_roots"]
    } == {(str(classroom), "learning-workspace:confirmed")}

    with (output / "protected-exclusions.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        exclusions = list(csv.DictReader(handle))
    classroom_rows = [
        row for row in exclusions
        if Path(row["path"]) == classroom / "MISSION.md"
    ]
    assert len(classroom_rows) == 1
    assert classroom_rows[0]["disposition"] == "PROTECTED"
    assert "learning-workspace:confirmed" in classroom_rows[0]["protection_source"]
    assert any(
        row["path"] == str(campus) and row["relationship"] == "ANCESTOR"
        for row in exclusions
    )
    assert not any(row["path"] == str(sibling / "scratch.bin") for row in exclusions)
