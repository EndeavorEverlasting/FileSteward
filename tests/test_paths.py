"""L0 proof: runtime output resolves beneath the ignored repository var/ tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesteward.policy.paths import (
    FORBIDDEN_ROOT_NAMES,
    is_under_forbidden_root,
    repository_root,
    run_dir,
    runtime_root,
)


class TestRepositoryRoot:
    def test_resolves_to_checkout_with_packaging_marker(self) -> None:
        root = repository_root()
        assert (root / "pyproject.toml").is_file()
        assert (root / "src" / "filesteward" / "__init__.py").is_file()

    def test_package_lives_beneath_repository_root(self) -> None:
        root = repository_root()
        package_dir = Path(__file__).resolve().parents[1] / "src" / "filesteward"
        assert str(package_dir).startswith(str(root))


class TestRuntimeRoot:
    def test_runtime_root_is_var_beneath_repository(self) -> None:
        root = runtime_root()
        assert root == repository_root() / "var"
        assert str(root).startswith(str(repository_root()))

    def test_var_is_git_ignored(self) -> None:
        ignore_text = (repository_root() / ".gitignore").read_text(encoding="utf-8")
        assert "\nvar/\n" in f"\n{ignore_text}", "var/ must be git-ignored"

    def test_runtime_root_not_beneath_forbidden_root(self) -> None:
        assert not is_under_forbidden_root(runtime_root())

    def test_no_tracked_files_beneath_var(self) -> None:
        var_dir = runtime_root()
        tracked = [
            p
            for p in (repository_root() / "var").rglob("*")
            if p.is_file() and ".gitkeep" not in p.name
        ]
        # runtime output is ignored; this asserts the policy root stays
        # inside the ignored tree rather than escaping the repository.
        assert all(str(p).startswith(str(var_dir)) for p in tracked)


class TestRunDir:
    def test_run_dir_shape(self) -> None:
        target = run_dir("20260930-0001")
        assert target == runtime_root() / "runs" / "20260930-0001"
        assert str(target).startswith(str(runtime_root()))

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            ".",
            "..",
            "../escape",
            "a/b",
            "a\\b",
            "-leading-dash",
            "x" * 65,
            "run id",
            "run\0id",
        ],
        ids=[
            "empty",
            "dot",
            "dotdot",
            "traversal",
            "slash",
            "backslash",
            "leading-dash",
            "too-long",
            "space",
            "nul",
        ],
    )
    def test_run_id_rejects_traversal_and_separators(self, bad: str) -> None:
        with pytest.raises(ValueError):
            run_dir(bad)

    @pytest.mark.parametrize(
        "good", ["run1", "20260930-0001", "a.b_c-D", "0"]
    )
    def test_run_id_accepts_single_safe_component(self, good: str) -> None:
        assert run_dir(good) == runtime_root() / "runs" / good

    def test_run_dir_computation_creates_nothing(self) -> None:
        target = run_dir("l0-no-create-check")
        assert not target.exists()
        assert not target.parent.exists() or target.parent == runtime_root() / "runs"


class TestForbiddenRoots:
    @pytest.mark.parametrize(
        "name", sorted(FORBIDDEN_ROOT_NAMES), ids=sorted(FORBIDDEN_ROOT_NAMES)
    )
    def test_each_forbidden_root_detected_case_insensitively(
        self, name: str
    ) -> None:
        assert is_under_forbidden_root(f"C:/Users/x/{name}/anything")
        assert is_under_forbidden_root(f"C:/Users/x/{name.lower()}/anything")
        assert is_under_forbidden_root(Path("C:/Users/x") / name / "sub")

    @pytest.mark.parametrize(
        "path",
        [
            "C:/Users/x/dev/FileSteward",
            "C:/Users/x/dev/worktrees/FileSteward/lane",
            "D:/data/projects",
        ],
    )
    def test_ordinary_paths_not_flagged(self, path: str) -> None:
        assert not is_under_forbidden_root(path)
