"""Runtime path policy. Resolution authority: docs/agent/CANONICAL-PATHS.md."""

from filesteward.policy.paths import (
    FORBIDDEN_ROOT_NAMES,
    is_under_forbidden_root,
    repository_root,
    run_dir,
    runtime_root,
)

__all__ = [
    "FORBIDDEN_ROOT_NAMES",
    "is_under_forbidden_root",
    "repository_root",
    "run_dir",
    "runtime_root",
]
