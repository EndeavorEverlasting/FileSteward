"""L1 proof: protection discovery and containment relations.

Scenario coverage: S2 (protected descendant), S7 (protected-subtree
ancestor decomposition), S8 (real Git semantics in a temp repository).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from filesteward.inventory.scan import iter_inventory
from filesteward.protect import (
    ProtectedRoot,
    ProtectionIndex,
    ProtectionRelation,
    is_git_repository,
    iter_git_roots,
)

GIT = shutil.which("git")


def require_git() -> str:
    if GIT is None:
        pytest.skip("git executable not available")
    return GIT


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    exe = require_git()
    result = subprocess.run(
        [exe, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "synthetic",
            "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
            "GIT_COMMITTER_NAME": "synthetic",
            "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
        },
    )
    assert result.returncode == 0, f"git {args} failed: {result.stdout}{result.stderr}"
    return result


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "tracked.txt").write_text("synthetic repo content", encoding="utf-8")
    git("init", "-q", str(path), cwd=path)
    git("add", "tracked.txt", cwd=path)
    git("-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid",
        "commit", "-q", "-m", "init", cwd=path)
    return path


# ---------------------------------------------------------------------------
# is_git_repository
# ---------------------------------------------------------------------------


class TestGitDetection:
    def test_plain_directory_is_not_repository(self, tmp_path: Path) -> None:
        assert is_git_repository(tmp_path) is False

    def test_dotgit_directory_counts(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert is_git_repository(tmp_path) is True

    def test_dotgit_file_counts_as_worktree(self, tmp_path: Path) -> None:
        (tmp_path / ".git").write_text(
            "gitdir: /synthetic/gitdir", encoding="utf-8"
        )
        assert is_git_repository(tmp_path) is True


# ---------------------------------------------------------------------------
# S8 — real git repository + worktree in temp
# ---------------------------------------------------------------------------


class TestRealGitSemantics:
    def test_discovers_real_repository_without_descending(
        self, tmp_path: Path
    ) -> None:
        repo = make_repo(tmp_path / "repo")
        (repo / "deep").mkdir()
        (repo / "deep" / "inner.txt").write_text("inner", encoding="utf-8")

        calls: list[str] = []
        real_scandir = os.scandir

        def spying_scandir(path: str) -> object:
            calls.append(os.path.normcase(os.path.abspath(path)))
            return real_scandir(path)

        roots = list(iter_git_roots(str(tmp_path), scandir=spying_scandir))
        assert [r.name for r in roots] == ["repo"]
        assert os.path.normcase(str(repo)) not in calls, (
            "discovery must not descend into a found repository"
        )

    def test_discovers_linked_worktree_with_git_file(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path / "repo")
        worktree = tmp_path / "wt-lane"
        git("worktree", "add", "-q", "-b", "lane-b", str(worktree), cwd=repo)
        assert (worktree / ".git").is_file()

        roots = {os.path.normcase(str(r)) for r in iter_git_roots(str(tmp_path))}
        assert os.path.normcase(str(repo)) in roots
        assert os.path.normcase(str(worktree)) in roots

        index = ProtectionIndex.from_git_discovery(str(tmp_path))
        nested = worktree / "tracked.txt"
        assert index.is_protected(str(nested))
        assert index.relation(str(worktree)) is ProtectionRelation.SELF

    def test_nested_repository_covered_by_outer_root(self, tmp_path: Path) -> None:
        """Discovery stops at the first repository; containment still
        protects everything beneath it, including nested repositories."""

        outer = make_repo(tmp_path / "outer")
        inner = make_repo(outer / "vendor" / "inner")
        roots = [os.path.normcase(str(r)) for r in iter_git_roots(str(tmp_path))]
        assert roots == [os.path.normcase(str(outer))]

        index = ProtectionIndex.from_git_discovery(str(tmp_path))
        assert index.is_protected(str(inner))
        assert index.is_protected(str(inner / "tracked.txt"))
        assert index.relation(str(inner)) is ProtectionRelation.DESCENDANT


# ---------------------------------------------------------------------------
# S2 / S7 — containment and decomposition
# ---------------------------------------------------------------------------


class TestContainment:
    def test_self_and_descendant_and_unrelated(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        index = ProtectionIndex([ProtectedRoot(str(repo), "git-repository")])

        assert index.relation(str(repo)) is ProtectionRelation.SELF
        assert index.relation(str(repo / "src" / "main.py")) is (
            ProtectionRelation.DESCENDANT
        )
        assert index.relation(str(tmp_path / "sibling")) is (
            ProtectionRelation.UNRELATED
        )
        assert index.is_protected(str(repo / "src"))
        assert not index.is_protected(str(tmp_path / "sibling"))
        assert not index.requires_decomposition(str(tmp_path / "sibling"))

    def test_s2_protected_descendant_never_evaluable(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path / "repo")
        index = ProtectionIndex.from_git_discovery(str(tmp_path))
        scanned = list(iter_inventory(str(tmp_path)))
        protected_items = [
            item for item in scanned if index.is_protected(item.path)
        ]
        assert protected_items, "repository contents must be inventoried"
        assert all(
            os.path.normcase(item.path).startswith(os.path.normcase(str(repo)))
            for item in protected_items
        )

    def test_s7_ancestor_requires_decomposition_not_protection(
        self, tmp_path: Path
    ) -> None:
        parent = tmp_path / "parent"
        repo = make_repo(parent / "repo")
        sibling = parent / "unrelated-sibling"
        sibling.mkdir()
        (sibling / "keep.txt").write_text("keep", encoding="utf-8")

        index = ProtectionIndex.from_git_discovery(str(tmp_path))

        assert index.relation(str(parent)) is ProtectionRelation.ANCESTOR
        assert index.requires_decomposition(str(parent)) is True
        assert index.is_protected(str(parent)) is False, (
            "the parent itself is not protected"
        )

        assert index.is_protected(str(repo)) is True
        assert index.is_protected(str(repo / "tracked.txt")) is True

        assert index.relation(str(sibling)) is ProtectionRelation.UNRELATED
        assert index.is_protected(str(sibling)) is False
        assert index.requires_decomposition(str(sibling)) is False

    def test_sibling_name_prefix_is_not_containment(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        decoy = tmp_path / "repo2"
        decoy.mkdir()
        index = ProtectionIndex([ProtectedRoot(str(repo), "git-repository")])
        assert index.relation(str(decoy)) is ProtectionRelation.UNRELATED

    def test_windows_case_insensitive_containment(self, tmp_path: Path) -> None:
        repo = tmp_path / "Repo"
        repo.mkdir()
        index = ProtectionIndex([ProtectedRoot(str(repo), "git-repository")])
        upper = str(repo).upper()
        assert index.relation(upper) is ProtectionRelation.SELF
        assert index.relation(upper + "\\src\\file.py") is (
            ProtectionRelation.DESCENDANT
        )

    def test_protection_wins_over_ancestorship(self, tmp_path: Path) -> None:
        """A path under root B that contains root A stays protected."""

        outer = tmp_path / "outer"
        inner_repo = make_repo(outer / "inner-repo")
        outer_repo = make_repo(outer)
        index = ProtectionIndex(
            [
                ProtectedRoot(str(inner_repo), "git-repository"),
                ProtectedRoot(str(outer_repo), "git-repository"),
            ]
        )
        mixed = inner_repo / "sub"
        mixed.mkdir()
        assert index.relation(str(mixed)) is ProtectionRelation.DESCENDANT
        assert index.is_protected(str(mixed)) is True

    def test_duplicate_roots_deduplicated_and_empty_index_safe(
        self, tmp_path: Path
    ) -> None:
        index = ProtectionIndex([str(tmp_path), str(tmp_path)])
        assert len(index) == 1
        empty = ProtectionIndex([])
        assert len(empty) == 0
        assert empty.relation(str(tmp_path)) is ProtectionRelation.UNRELATED
        assert empty.is_protected(str(tmp_path)) is False

    def test_root_under_itself_style_path_shapes(self, tmp_path: Path) -> None:
        index = ProtectionIndex([ProtectedRoot(str(tmp_path), "git-repository")])
        assert index.relation(str(tmp_path)) is ProtectionRelation.SELF
        assert index.relation(str(tmp_path) + os.sep) is ProtectionRelation.SELF
        assert index.relation(str(tmp_path) + os.sep + "a" + os.sep + "b") is (
            ProtectionRelation.DESCENDANT
        )
