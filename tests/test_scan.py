"""L1 proof: streaming, no-follow, explicit UNKNOWN, no hydration, no mutation.

Scenario coverage: S9 (junction/reparse), S10 (symlink), S11 (unreadable),
S12 (cloud placeholder), S14 (incomplete directory fail-closed).
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from filesteward.inventory import windows
from filesteward.inventory.scan import ScanDeps, iter_inventory, stable_item_id
from filesteward.models import EntryType, ScanCompleteness

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_plain_tree(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "docs" / "a.txt").write_text("A" * 100, encoding="utf-8")
    (root / "docs" / "nested").mkdir()
    (root / "docs" / "nested" / "b.txt").write_text("B" * 50, encoding="utf-8")
    (root / "empty").mkdir()
    (root / "top.txt").write_text("T" * 10, encoding="utf-8")


def snapshot(root: Path) -> list[tuple]:
    rows: list[tuple] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append((rel, "symlink", None, None, None))
        elif path.is_dir():
            rows.append((rel, "dir", None, None, None))
        else:
            data = path.read_bytes()
            stat = path.stat()
            rows.append(
                (
                    rel,
                    "file",
                    stat.st_size,
                    hashlib.sha256(data).hexdigest(),
                    stat.st_mtime_ns,
                )
            )
    return rows


def scan_all(root: Path, deps: ScanDeps | None = None) -> list[Any]:
    return list(iter_inventory(str(root), deps=deps))


def by_rel(items: list[Any], root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        rel = os.path.relpath(item.path, str(root)).replace(os.sep, "/")
        result[rel if rel != "." else "."] = item
    return result


# ---------------------------------------------------------------------------
# streaming / identity
# ---------------------------------------------------------------------------


class TestStreamingInventory:
    def test_returns_lazy_generator_and_enumerates_incrementally(
        self, tmp_path: Path
    ) -> None:
        for i in range(50):
            (tmp_path / f"dir{i:02d}").mkdir()
            (tmp_path / f"dir{i:02d}" / "f.txt").write_text("x", encoding="utf-8")

        calls: list[str] = []
        real_scandir = os.scandir

        def spying_scandir(path: str) -> Any:
            calls.append(path)
            return real_scandir(path)

        stream = iter_inventory(str(tmp_path), deps=ScanDeps(scandir=spying_scandir))
        assert not calls, "generator must not enumerate before first next()"
        first = next(stream)
        assert first is not None
        assert len(calls) < 51, "first item must not require full enumeration"
        rest = list(stream)
        assert len(rest) >= 51

    def test_inventory_includes_root_and_children_with_stable_ids(
        self, tmp_path: Path
    ) -> None:
        make_plain_tree(tmp_path)
        first = by_rel(scan_all(tmp_path), tmp_path)
        second = by_rel(scan_all(tmp_path), tmp_path)

        assert set(first) == {
            ".",
            "docs",
            "docs/a.txt",
            "docs/nested",
            "docs/nested/b.txt",
            "empty",
            "top.txt",
        }
        assert first["."].entry_type is EntryType.DIRECTORY
        assert first["docs/a.txt"].logical_size_bytes == 100
        assert first["top.txt"].logical_size_bytes == 10
        for key, item in first.items():
            assert item.item_id == second[key].item_id, f"id not stable: {key}"
            assert item.item_id == stable_item_id(key)
            assert item.scan_completeness is ScanCompleteness.COMPLETE
            assert item.scan_error is None

    def test_item_ids_are_relative_not_absolute(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "same.txt").write_text("1", encoding="utf-8")
        (b / "same.txt").write_text("1", encoding="utf-8")
        ids_a = {i.item_id for i in scan_all(a) if i.path.endswith("same.txt")}
        ids_b = {i.item_id for i in scan_all(b) if i.path.endswith("same.txt")}
        assert ids_a == ids_b


# ---------------------------------------------------------------------------
# S9 / S10 — no-follow
# ---------------------------------------------------------------------------


class TestNoFollow:
    def test_junction_recorded_not_followed(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "secret-junction-target.txt").write_text("do not traverse", "utf-8")
        link = tmp_path / "jlink"
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        except Exception as exc:  # pragma: no cover - environment specific
            pytest.skip(f"junction fixture unavailable: {type(exc).__name__}: {exc}")

        calls: list[str] = []
        real_scandir = os.scandir

        def spying_scandir(path: str) -> Any:
            calls.append(os.path.normcase(path))
            return real_scandir(path)

        items = by_rel(
            scan_all(tmp_path, deps=ScanDeps(scandir=spying_scandir)), tmp_path
        )
        assert "jlink" in items
        jitem = items["jlink"]
        assert jitem.entry_type is EntryType.REPARSE_POINT
        assert jitem.is_reparse_point is True
        assert jitem.is_symlink is False
        assert "jlink/secret-junction-target.txt" not in items
        assert os.path.normcase(str(link)) not in calls, "junction target was entered"
        assert "target/secret-junction-target.txt" in items, (
            "the real target dir is independently visible and that is fine"
        )

    @pytest.mark.parametrize(
        "symlink_maker",
        [
            pytest.param(
                lambda target, link: os.symlink(
                    str(target), str(link),
                    target_is_directory=target.is_dir(),
                ),
                id="symlink",
            )
        ],
    )
    def test_symlink_recorded_not_followed(
        self, tmp_path: Path, symlink_maker: Callable[[Path, Path], None]
    ) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "inside-link.txt").write_text("x" * 5, encoding="utf-8")
        link = tmp_path / "dlink"
        try:
            symlink_maker(target, link)
        except OSError as exc:
            pytest.skip(
                "symlink fixture unavailable (privilege/developer mode): "
                f"{exc}"
            )

        items = by_rel(scan_all(tmp_path), tmp_path)
        assert items["dlink"].entry_type is EntryType.SYMLINK
        assert items["dlink"].is_symlink is True
        assert "dlink/inside-link.txt" not in items

    def test_adapter_unit_synthetic_reparse_never_descended(self) -> None:
        """Deterministic substitute proof when fixture creation fails.

        A synthetic scandir stream containing a reparse-flavoured entry
        must be yielded as a leaf: no child frame is ever pushed for it.
        """

        seen_dirs: list[str] = []

        class FakeStat:
            st_mode = 0o040755
            st_file_attributes = windows.FILE_ATTRIBUTE_REPARSE_POINT
            st_size = 0
            st_blocks = 0
            st_mtime = 0.0
            st_nlink = 2

        class FakeEntry:
            def __init__(self, path: str) -> None:
                self.path = path

            def is_symlink(self) -> bool:
                return False

            def stat(self, *, follow_symlinks: bool = True) -> FakeStat:
                return FakeStat()

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                raise AssertionError("reparse entry must not be classified as dir")

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                raise AssertionError("reparse entry must not be classified as file")

        root = os.path.abspath("C:/synthetic/reparse-root")

        def fake_scandir(path: str) -> Iterator[FakeEntry]:
            seen_dirs.append(path)
            if path == root:
                return iter([FakeEntry(os.path.join(root, "junction"))])
            raise AssertionError(f"must not descend into reparse: {path}")

        items = list(iter_inventory(root, deps=ScanDeps(scandir=fake_scandir)))
        assert len(seen_dirs) == 1
        kinds = [i.entry_type for i in items]
        assert EntryType.REPARSE_POINT in kinds
        assert EntryType.DIRECTORY in kinds  # root itself


# ---------------------------------------------------------------------------
# S11 / S14 — unreadable becomes explicit UNKNOWN evidence
# ---------------------------------------------------------------------------


class TestUnreadableIsExplicit:
    def test_seam_denied_directory_is_incomplete_not_absent(
        self, tmp_path: Path
    ) -> None:
        make_plain_tree(tmp_path)
        denied = tmp_path / "docs"
        real_scandir = os.scandir

        def failing_scandir(path: str) -> Any:
            if os.path.normcase(path) == os.path.normcase(str(denied)):
                raise PermissionError(5, "access is denied", path)
            return real_scandir(path)

        items = by_rel(
            scan_all(tmp_path, deps=ScanDeps(scandir=failing_scandir)), tmp_path
        )
        # the denied directory still exists in the inventory as evidence
        assert "docs" in items
        docs = items["docs"]
        assert docs.scan_completeness is ScanCompleteness.INCOMPLETE
        assert docs.scan_error is not None
        assert "PermissionError" in docs.scan_error
        # its children were not enumerated, and their absence is NOT inferred:
        assert "docs/a.txt" not in items
        # siblings remain complete
        assert items["top.txt"].scan_completeness is ScanCompleteness.COMPLETE

    def test_missing_root_yields_explicit_incomplete_evidence(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist"
        items = scan_all(missing)
        assert len(items) == 1
        assert items[0].scan_completeness is ScanCompleteness.INCOMPLETE
        assert items[0].scan_error is not None

    def test_type_probe_race_becomes_incomplete_evidence(self) -> None:
        """F2: is_dir/is_file OSError must not abort the whole scan."""

        class FakeStat:
            st_size = 10
            st_mtime = 1.0
            st_nlink = 1
            st_file_attributes = 0

        class RacingEntry:
            def __init__(self, path: str) -> None:
                self.path = path

            def is_symlink(self) -> bool:
                return False

            def stat(self, *, follow_symlinks: bool = True) -> FakeStat:
                return FakeStat()

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                raise FileNotFoundError(2, "vanished", self.path)

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                raise FileNotFoundError(2, "vanished", self.path)

        class StableFile:
            def __init__(self, path: str) -> None:
                self.path = path

            def is_symlink(self) -> bool:
                return False

            def stat(self, *, follow_symlinks: bool = True) -> FakeStat:
                return FakeStat()

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                return False

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                return True

        root = os.path.abspath("C:/synthetic/race-root")

        def fake_scandir(path: str) -> Iterator[Any]:
            assert path == root
            return iter(
                [
                    RacingEntry(os.path.join(root, "vanishing.bin")),
                    StableFile(os.path.join(root, "stable.bin")),
                ]
            )

        items = list(iter_inventory(root, deps=ScanDeps(scandir=fake_scandir)))
        by_name = {os.path.basename(i.path): i for i in items if i.path != root}
        assert "vanishing.bin" in by_name
        assert by_name["vanishing.bin"].scan_completeness is ScanCompleteness.INCOMPLETE
        assert "FileNotFoundError" in (by_name["vanishing.bin"].scan_error or "")
        assert "stable.bin" in by_name
        assert by_name["stable.bin"].entry_type is EntryType.FILE
        assert by_name["stable.bin"].scan_completeness is ScanCompleteness.COMPLETE

    def test_mid_iteration_failure_marks_directory_incomplete(self) -> None:
        """S14: a partially enumerated directory is not COMPLETE."""

        root = os.path.abspath("C:/synthetic/partial-root")

        class FakeStat:
            st_mode = 0o100644
            st_file_attributes = 0
            st_size = 1
            st_blocks = 1
            st_mtime = 0.0
            st_nlink = 1

        class FakeFile:
            def __init__(self, path: str) -> None:
                self.path = path

            def is_symlink(self) -> bool:
                return False

            def stat(self, *, follow_symlinks: bool = True) -> FakeStat:
                return FakeStat()

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                return False

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                return True

        def broken_scandir(path: str) -> Any:
            def gen() -> Iterator[FakeFile]:
                yield FakeFile(os.path.join(path, "one.txt"))
                raise OSError(5, "access is denied during enumeration")

            return gen()

        items = list(iter_inventory(root, deps=ScanDeps(scandir=broken_scandir)))
        root_item = next(i for i in items if i.path == root)
        assert root_item.scan_completeness is ScanCompleteness.INCOMPLETE
        assert any(i.path.endswith("one.txt") for i in items), (
            "entries seen before failure are preserved"
        )

    @pytest.mark.skipif(
        shutil.which("icacls") is None, reason="icacls not available"
    )
    def test_real_acl_denied_directory_incomplete(self, tmp_path: Path) -> None:
        denied = tmp_path / "locked"
        denied.mkdir()
        (denied / "hidden.txt").write_text("secret", encoding="utf-8")
        (tmp_path / "open.txt").write_text("visible", encoding="utf-8")
        user = os.environ.get("USERNAME") or os.environ.get("USER")
        if not user:
            pytest.skip("no USERNAME/USER environment variable")

        # Deny only FILE_READ_DATA/LIST_DIRECTORY (RD) on the directory
        # itself — no inheritance, no READ_CONTROL, no WRITE_DAC — so
        # enumeration fails while the owner can always read and restore
        # the DACL afterwards.
        deny = subprocess.run(
            ["icacls", str(denied), "/deny", f"{user}:(RD)"],
            capture_output=True,
            text=True,
        )
        if deny.returncode != 0:
            pytest.skip(f"icacls deny failed: {deny.stdout}{deny.stderr}")
        try:
            items = by_rel(scan_all(tmp_path), tmp_path)
        finally:
            restore = subprocess.run(
                ["icacls", str(denied), "/remove:d", user],
                capture_output=True,
                text=True,
            )
            if restore.returncode != 0:  # pragma: no cover
                pytest.fail(
                    f"ACL restore failed: {restore.stdout}{restore.stderr}"
                )

        assert items["locked"].scan_completeness is ScanCompleteness.INCOMPLETE
        assert items["locked"].scan_error is not None
        assert "locked/hidden.txt" not in items
        assert items["open.txt"].scan_completeness is ScanCompleteness.COMPLETE


# ---------------------------------------------------------------------------
# S12 — cloud placeholder: metadata only, never hydrated
# ---------------------------------------------------------------------------


class TestCloudPlaceholder:
    def test_inventory_package_source_never_reads_content(self) -> None:
        """Structural proof: no content-read calls exist in inventory code."""

        package_dir = Path(windows.__file__).resolve().parent
        forbidden_attrs = {
            "open",
            "read",
            "read_bytes",
            "read_text",
            "readlines",
            "readinto",
            "readall",
            "readinto1",
        }
        forbidden_names = {"open"}
        for source in sorted(package_dir.glob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in forbidden_names, (
                        f"{source.name} calls {node.func.id}"
                    )
                elif isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in forbidden_attrs, (
                        f"{source.name} calls .{node.func.attr}"
                    )

    def test_placeholder_attributes_flagged_from_metadata_alone(self) -> None:
        class FakeStat:
            st_mode = 0o100644
            st_size = 4096
            st_blocks = 0
            st_mtime = 0.0
            st_nlink = 1
            st_file_attributes = 0

        recall = FakeStat()
        recall.st_file_attributes = windows.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
        assert windows.is_cloud_placeholder(recall) is True

        offline = FakeStat()
        offline.st_file_attributes = windows.FILE_ATTRIBUTE_OFFLINE
        assert windows.is_cloud_placeholder(offline) is True

        regular = FakeStat()
        regular.st_file_attributes = 0x20  # ARCHIVE only
        assert windows.is_cloud_placeholder(regular) is False

        class BareStat:
            st_mode = 0o100644

        bare = BareStat()
        assert not hasattr(bare, "st_file_attributes")
        assert windows.is_cloud_placeholder(bare) is False

    def test_unit_synthetic_placeholder_entry(self) -> None:
        root = os.path.abspath("C:/synthetic/placeholder-root")

        class FakeStat:
            st_mode = 0o100644
            st_file_attributes = (
                windows.FILE_ATTRIBUTE_OFFLINE | windows.FILE_ATTRIBUTE_RECALL_ON_OPEN
            )
            st_size = 1_048_576
            st_blocks = 8
            st_mtime = 1.0
            st_nlink = 1

        class FakeFile:
            def __init__(self, path: str) -> None:
                self.path = path

            def is_symlink(self) -> bool:
                return False

            def stat(self, *, follow_symlinks: bool = True) -> FakeStat:
                return FakeStat()

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                return False

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                return True

        def fake_scandir(path: str) -> Iterator[FakeFile]:
            assert path == root
            return iter([FakeFile(os.path.join(root, "online.bin"))])

        items = list(iter_inventory(root, deps=ScanDeps(scandir=fake_scandir)))
        placeholder = next(i for i in items if i.path.endswith("online.bin"))
        assert placeholder.is_cloud_placeholder is True
        assert placeholder.scan_completeness is ScanCompleteness.COMPLETE
        assert placeholder.logical_size_bytes == 1_048_576

    def test_real_offline_flag_file_detected_without_mutation(
        self, tmp_path: Path
    ) -> None:
        if sys.platform != "win32":
            pytest.skip("Win32 attributes API")
        target = tmp_path / "placeholder.bin"
        payload = b"payload" * 1000
        target.write_bytes(payload)
        digest_before = hashlib.sha256(target.read_bytes()).hexdigest()

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_attr = kernel32.GetFileAttributesW
        set_attr = kernel32.SetFileAttributesW
        get_attr.argtypes = [ctypes.c_wchar_p]
        get_attr.restype = ctypes.c_uint32
        set_attr.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
        set_attr.restype = ctypes.c_int

        current = get_attr(str(target))
        if current == 0:
            pytest.skip("GetFileAttributesW failed for synthetic file")
        desired = current | windows.FILE_ATTRIBUTE_OFFLINE
        if set_attr(str(target), desired) == 0:
            pytest.skip("SetFileAttributesW(OFFLINE) rejected on this filesystem")
        try:
            after_set = get_attr(str(target))
            if not after_set & windows.FILE_ATTRIBUTE_OFFLINE:
                pytest.skip("filesystem did not retain FILE_ATTRIBUTE_OFFLINE")

            items = by_rel(scan_all(tmp_path), tmp_path)
            item = items["placeholder.bin"]
            assert item.is_cloud_placeholder is True
            assert item.scan_completeness is ScanCompleteness.COMPLETE
            assert item.logical_size_bytes == len(payload)
            digest_after = hashlib.sha256(target.read_bytes()).hexdigest()
            assert digest_after == digest_before, "scan mutated file content"
        finally:
            set_attr(str(target), current)


# ---------------------------------------------------------------------------
# no-mutation proof
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_scan_does_not_modify_fixture_tree(self, tmp_path: Path) -> None:
        make_plain_tree(tmp_path)
        before = snapshot(tmp_path)
        scan_all(tmp_path)
        scan_all(tmp_path)
        after = snapshot(tmp_path)
        assert after == before

    def test_scan_does_not_create_runtime_output(self, tmp_path: Path) -> None:
        make_plain_tree(tmp_path)
        before = snapshot(tmp_path)
        scan_all(tmp_path)
        after = snapshot(tmp_path)
        assert len(after) == len(before)
