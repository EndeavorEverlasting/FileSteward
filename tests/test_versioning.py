from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "versioning.py"
SPEC = importlib.util.spec_from_file_location("filesteward_versioning", SCRIPT)
assert SPEC and SPEC.loader
versioning = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = versioning
SPEC.loader.exec_module(versioning)


def test_version_parse_and_bump_matrix() -> None:
    version = versioning.Version.parse("0.1.0")
    assert str(version.bump("visual-polish")) == "0.1.1"
    assert str(version.bump("visual-feature")) == "0.2.0"
    assert str(version.bump("major")) == "1.0.0"


def test_replace_pyproject_version_has_single_authority() -> None:
    original = '[project]\nname = "filesteward"\nversion = "0.1.0"\n'
    updated = versioning.replace_pyproject_version(
        original, versioning.Version.parse("0.2.0")
    )
    assert 'version = "0.2.0"' in updated
    assert updated.count('version = "') == 1


def test_visual_path_detection_is_bounded() -> None:
    changed = versioning.visual_change_paths(
        [
            "src/filesteward/visualization/cinematic.py",
            "docs/program/storage-reclaim-visual-system.tokens.json",
            "docs/program/storage-reclaim-memory-atlas-v3.md",
            "tests/test_visualization_f5.py",
            "README.md",
        ]
    )
    assert changed == [
        "docs/program/storage-reclaim-visual-system.tokens.json",
        "src/filesteward/visualization/cinematic.py",
    ]


def test_non_visual_changes_do_not_trigger_product_bump() -> None:
    assert versioning.visual_change_paths(
        ["tests/test_versioning.py", "docs/agent/RECOVERY.md"]
    ) == []


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout


def test_changed_paths_include_staged_and_unstaged_worktree_edits(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src/filesteward/visualization").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "filesteward"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    visual = root / "src/filesteward/visualization/cinematic.py"
    visual.write_text("BASE = True\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "FileSteward Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    base = _git(root, "rev-parse", "HEAD").strip()

    visual.write_text("BASE = False\n", encoding="utf-8")
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    _git(root, "add", "README.md")

    paths = versioning.changed_paths(base, root=root)
    assert paths == ["README.md", "src/filesteward/visualization/cinematic.py"]

    before, after, visual_paths, changed = versioning.ensure_visual_bump(
        base=base, kind="visual-feature", fix=True, root=root
    )
    assert str(before) == "0.1.0"
    assert str(after) == "0.2.0"
    assert visual_paths == ["src/filesteward/visualization/cinematic.py"]
    assert changed is True
    assert 'version = "0.2.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")


def test_write_version_keeps_package_dunder_in_lockstep(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src/filesteward").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "filesteward"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (root / "src/filesteward/__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    versioning.write_version(versioning.Version.parse("0.2.0"), root=root)
    assert 'version = "0.2.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.2.0"' in (
        root / "src/filesteward/__init__.py"
    ).read_text(encoding="utf-8")

def test_subsequent_visual_pass_bumps_from_committed_candidate(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src/filesteward/visualization").mkdir(parents=True)
    (root / "src/filesteward").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "filesteward"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (root / "src/filesteward/__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    visual = root / "src/filesteward/visualization/cinematic.py"
    visual.write_text("PASS = 1\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "FileSteward Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    base = _git(root, "rev-parse", "HEAD").strip()

    visual.write_text("PASS = 2\n", encoding="utf-8")
    before, after, _, changed = versioning.ensure_visual_bump(
        base=base, kind="visual-feature", fix=True, root=root
    )
    assert str(before) == "0.1.0"
    assert str(after) == "0.2.0"
    assert changed is True
    _git(root, "add", ".")
    _git(root, "commit", "-m", "visual v2")

    visual.write_text("PASS = 3\n", encoding="utf-8")
    before2, after2, paths2, changed2 = versioning.ensure_visual_bump(
        base=base, kind="visual-feature", fix=True, root=root
    )
    assert str(before2) == "0.2.0"
    assert str(after2) == "0.3.0"
    assert paths2 == ["src/filesteward/visualization/cinematic.py"]
    assert changed2 is True
    assert 'version = "0.3.0"' in (
        root / "pyproject.toml"
    ).read_text(encoding="utf-8")
    assert '__version__ = "0.3.0"' in (
        root / "src/filesteward/__init__.py"
    ).read_text(encoding="utf-8")
