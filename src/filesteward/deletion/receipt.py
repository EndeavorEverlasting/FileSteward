"""D5 permanent-delete execution receipt.

Writes ``delete-execution-receipt.json`` under the run directory. Receipts
survive interruption well enough to prevent blind re-unlink of items already
recorded as SUCCEEDED.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional, Union

__all__ = [
    "DELETE_RECEIPT_FILENAME",
    "DELETE_RECEIPT_SCHEMA",
    "load_delete_receipt",
    "write_delete_receipt",
]

DELETE_RECEIPT_SCHEMA = "filesteward.delete-execution-receipt/v1"
DELETE_RECEIPT_FILENAME = "delete-execution-receipt.json"

PathLike = Union[str, Path]


def write_delete_receipt(path: PathLike, receipt: Mapping[str, Any]) -> Path:
    """Atomically write the execution receipt."""

    out = Path(os.fspath(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(receipt)
    payload.setdefault("schema_version", DELETE_RECEIPT_SCHEMA)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{out.name}.",
        suffix=".tmp",
        dir=str(out.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, out)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return out


def load_delete_receipt(path: PathLike) -> Optional[dict[str, Any]]:
    """Load an existing receipt, or return None if missing."""

    target = Path(os.fspath(path))
    if not target.is_file():
        return None
    with target.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("delete-execution-receipt root must be a JSON object")
    return data
