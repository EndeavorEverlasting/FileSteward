#!/usr/bin/env python3
"""FileSteward product-version authority and visual-change bump guard.

`pyproject.toml` is the only human-facing product release version authority.
Schema/protocol versions remain independently owned by their contracts.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VERSION_RE = re.compile(r'(?m)^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")\s*$')
VISUAL_PATH_PREFIXES = (
    "src/filesteward/visualization/",
)
VISUAL_EXACT_PATHS = {
    "docs/program/storage-reclaim-visual-system.tokens.json",
}


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value.strip())
        if not match:
            raise ValueError(f"invalid FileSteward product version: {value!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, kind: str) -> "Version":
        if kind in {"patch", "visual-polish"}:
            return Version(self.major, self.minor, self.patch + 1)
        if kind in {"minor", "visual-feature"}:
            return Version(self.major, self.minor + 1, 0)
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        raise ValueError(f"unsupported bump kind: {kind}")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def pyproject_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "pyproject.toml"


def parse_pyproject_version(text: str) -> Version:
    match = VERSION_RE.search(text)
    if not match:
        raise ValueError("pyproject.toml must contain exactly one simple project version assignment")
    return Version(int(match.group(2)), int(match.group(3)), int(match.group(4)))


def replace_pyproject_version(text: str, version: Version) -> str:
    if len(VERSION_RE.findall(text)) != 1:
        raise ValueError("pyproject.toml must contain exactly one simple project version assignment")
    return VERSION_RE.sub(lambda m: f'{m.group(1)}{version}{m.group(5)}', text, count=1)


def visual_change_paths(paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in paths:
        path = raw.replace("\\", "/").lstrip("./")
        if path in VISUAL_EXACT_PATHS or any(path.startswith(prefix) for prefix in VISUAL_PATH_PREFIXES):
            out.append(path)
    return sorted(set(out))


def run_git(args: list[str], root: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root or repo_root()),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")
    return proc.stdout


def version_at_ref(ref: str, root: Path | None = None) -> Version:
    text = run_git(["show", f"{ref}:pyproject.toml"], root=root)
    return parse_pyproject_version(text)


def changed_paths(base: str, head: str = "HEAD", root: Path | None = None) -> list[str]:
    """Return proof-relevant changed paths for the requested candidate.

    When `head` is the live worktree (`HEAD`), include committed branch changes plus
    staged and unstaged edits. This makes `ensure-visual-bump` useful before the
    commit that introduces the visual change rather than only after it.
    """

    paths: set[str] = set()

    def add(output: str) -> None:
        paths.update(line.strip() for line in output.splitlines() if line.strip())

    add(run_git(["diff", "--name-only", f"{base}...{head}"], root=root))
    if head == "HEAD":
        add(run_git(["diff", "--name-only", "HEAD"], root=root))
        add(run_git(["diff", "--name-only", "--cached"], root=root))
    return sorted(paths)


def current_version(root: Path | None = None) -> Version:
    return parse_pyproject_version(pyproject_path(root).read_text(encoding="utf-8"))


def write_version(version: Version, root: Path | None = None) -> None:
    path = pyproject_path(root)
    original = path.read_text(encoding="utf-8")
    updated = replace_pyproject_version(original, version)
    path.write_text(updated, encoding="utf-8")


def ensure_visual_bump(
    *,
    base: str,
    head: str = "HEAD",
    kind: str = "visual-polish",
    fix: bool = False,
    root: Path | None = None,
) -> tuple[Version, Version, list[str], bool]:
    root = root or repo_root()
    paths = visual_change_paths(changed_paths(base, head, root))
    base_version = version_at_ref(base, root)
    head_version = current_version(root) if head == "HEAD" else version_at_ref(head, root)

    if not paths:
        return base_version, head_version, paths, False

    if head_version > base_version:
        return base_version, head_version, paths, False

    if not fix:
        raise ValueError(
            "visual product surface changed without a product-version bump: "
            + ", ".join(paths)
        )

    if head != "HEAD":
        raise ValueError("--fix is only valid when --head=HEAD")

    next_version = base_version.bump(kind)
    write_version(next_version, root)
    return base_version, next_version, paths, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("current", help="print the canonical product version")

    bump = sub.add_parser("bump", help="advance the canonical product version")
    bump.add_argument(
        "--kind",
        choices=["visual-polish", "visual-feature", "patch", "minor", "major"],
        required=True,
    )

    guard = sub.add_parser("guard", help="fail if visual changes did not advance product version")
    guard.add_argument("--base", default="origin/main")
    guard.add_argument("--head", default="HEAD")

    ensure = sub.add_parser(
        "ensure-visual-bump",
        help="automatically bump when visual surfaces changed and the version did not",
    )
    ensure.add_argument("--base", default="origin/main")
    ensure.add_argument("--head", default="HEAD")
    ensure.add_argument(
        "--kind",
        choices=["visual-polish", "visual-feature", "patch", "minor", "major"],
        default="visual-polish",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "current":
            print(current_version())
            return 0

        if args.command == "bump":
            before = current_version()
            after = before.bump(args.kind)
            write_version(after)
            print(f"{before} -> {after} ({args.kind})")
            return 0

        if args.command == "guard":
            base, head, paths, _ = ensure_visual_bump(
                base=args.base,
                head=args.head,
                fix=False,
            )
            if paths:
                print(f"visual version gate PASS: {base} -> {head}; {len(paths)} visual paths changed")
            else:
                print(f"visual version gate NOT_APPLICABLE: no visual product paths changed; version {head}")
            return 0

        if args.command == "ensure-visual-bump":
            base, head, paths, changed = ensure_visual_bump(
                base=args.base,
                head=args.head,
                kind=args.kind,
                fix=True,
            )
            if not paths:
                print(f"visual version bump NOT_APPLICABLE: no visual product paths changed; version {head}")
            elif changed:
                print(f"visual version bump APPLIED: {base} -> {head} ({args.kind}); {len(paths)} visual paths changed")
            else:
                print(f"visual version bump ALREADY_SATISFIED: {base} -> {head}; {len(paths)} visual paths changed")
            return 0
    except (RuntimeError, ValueError) as exc:
        print(f"versioning error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
