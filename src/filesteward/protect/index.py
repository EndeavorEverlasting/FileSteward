"""Protection index: containment relations, not global sibling blocking.

Per P04 section 7 / LOCAL-AGENT-PROTECTIONS section 4:

1. candidate == protected root            -> SELF (protected)
2. candidate beneath protected root       -> DESCENDANT (protected)
3. candidate directory contains a root    -> ANCESTOR (whole-directory
   action prohibited; decompose children; siblings stay evaluable)
4. unrelated sibling                      -> UNRELATED (evaluable)

When a path is both a descendant of one root and an ancestor of another,
protection wins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import PureWindowsPath
from typing import Any, Iterable, Iterator, Union

from filesteward.protect.git import iter_git_roots

__all__ = ["ProtectedRoot", "ProtectionIndex", "ProtectionRelation"]


class ProtectionRelation(str, Enum):
    SELF = "SELF"
    DESCENDANT = "DESCENDANT"
    ANCESTOR = "ANCESTOR"
    UNRELATED = "UNRELATED"


def _key(path: Any) -> tuple[str, ...]:
    """Case-folded, separator-normalized path parts (Windows semantics)."""

    return tuple(part.lower() for part in PureWindowsPath(os.fspath(path)).parts)


@dataclass(frozen=True)
class ProtectedRoot:
    path: str
    source: str

    @property
    def key(self) -> tuple[str, ...]:
        return _key(self.path)


class ProtectionIndex:
    """Immutable snapshot of protected roots for one analysis pass."""

    def __init__(self, roots: Iterable[Union[ProtectedRoot, Any]]) -> None:
        normalized: list[ProtectedRoot] = []
        seen: set[tuple[str, ...]] = set()
        for root in roots:
            item = (
                root
                if isinstance(root, ProtectedRoot)
                else ProtectedRoot(path=os.fspath(root), source="unspecified")
            )
            if item.key in seen:
                continue
            seen.add(item.key)
            normalized.append(item)
        self._roots = tuple(normalized)

    @property
    def roots(self) -> tuple[ProtectedRoot, ...]:
        return self._roots

    @classmethod
    def from_git_discovery(
        cls, root: Any, *, scandir: Any = None
    ) -> "ProtectionIndex":
        """Build an index by streaming git/worktree discovery under ``root``."""

        kwargs = {} if scandir is None else {"scandir": scandir}
        return cls(
            ProtectedRoot(path=str(path), source="git-repository")
            for path in iter_git_roots(root, **kwargs)
        )

    def relation(self, path: Any) -> ProtectionRelation:
        candidate = _key(path)
        has_self = has_descendant = has_ancestor = False
        for root in self._roots:
            base = root.key
            if candidate == base:
                has_self = True
            elif len(candidate) > len(base) and candidate[: len(base)] == base:
                has_descendant = True
            elif len(base) > len(candidate) and base[: len(candidate)] == candidate:
                has_ancestor = True
        if has_self:
            return ProtectionRelation.SELF
        if has_descendant:
            return ProtectionRelation.DESCENDANT
        if has_ancestor:
            return ProtectionRelation.ANCESTOR
        return ProtectionRelation.UNRELATED

    def is_protected(self, path: Any) -> bool:
        return self.relation(path) in (
            ProtectionRelation.SELF,
            ProtectionRelation.DESCENDANT,
        )

    def requires_decomposition(self, path: Any) -> bool:
        return self.relation(path) is ProtectionRelation.ANCESTOR

    def __iter__(self) -> Iterator[ProtectedRoot]:
        return iter(self._roots)

    def __len__(self) -> int:
        return len(self._roots)
