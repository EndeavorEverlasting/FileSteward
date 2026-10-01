"""Protection semantics: what automation must never touch."""

from filesteward.protect.git import is_git_repository, iter_git_roots
from filesteward.protect.index import (
    ProtectedRoot,
    ProtectionIndex,
    ProtectionRelation,
)

__all__ = [
    "ProtectedRoot",
    "ProtectionIndex",
    "ProtectionRelation",
    "is_git_repository",
    "iter_git_roots",
]
