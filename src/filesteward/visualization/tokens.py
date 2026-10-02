"""F0 visual-system token loader.

Tokens are owned by docs/program/storage-reclaim-visual-system.tokens.json.
This module exposes them to CSS emission and disposition mapping without
inferring evidence or authorization.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from filesteward.models import CleanupDisposition

__all__ = [
    "TOKEN_CONTRACT_ID",
    "disposition_css_stem",
    "load_tokens",
    "token_document_path",
]

TOKEN_CONTRACT_ID = "storage-reclaim-visual-system"


def token_document_path() -> Path:
    """Resolve the tracked token JSON next to the repository docs contract."""

    # Prefer the repository docs path relative to this source file so editable
    # installs and worktrees resolve the same tracked contract.
    repo_docs = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "program"
        / "storage-reclaim-visual-system.tokens.json"
    )
    if repo_docs.is_file():
        return repo_docs
    raise FileNotFoundError(
        "visual-system token contract missing: "
        "docs/program/storage-reclaim-visual-system.tokens.json"
    )


@lru_cache(maxsize=1)
def load_tokens() -> Mapping[str, Any]:
    """Load and validate the frozen visual-system token document."""

    path = token_document_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract_id") != TOKEN_CONTRACT_ID:
        raise ValueError(
            f"unexpected visual-system contract_id: {data.get('contract_id')!r}"
        )
    if "themes" not in data or "light" not in data["themes"] or "dark" not in data["themes"]:
        raise ValueError("visual-system tokens must define light and dark themes")
    return data


def disposition_css_stem(disposition: CleanupDisposition | str) -> str:
    """Map a CleanupDisposition to the CSS token stem (without --fs- prefix).

    Authorization must never call this helper for reclaim-green styling.
    """

    value = (
        disposition.value
        if isinstance(disposition, CleanupDisposition)
        else str(disposition)
    )
    mapping = load_tokens()["disposition_token_map"]
    try:
        return str(mapping[value])
    except KeyError as exc:
        raise ValueError(f"no visual token for disposition {value!r}") from exc
