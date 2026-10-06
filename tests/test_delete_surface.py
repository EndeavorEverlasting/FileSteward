"""D1 delete-set decision surface proofs."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from filesteward.deletion import emit_delete_manifest
from filesteward.deletion.surface import (
    DELETE_SET_HTML_FILENAME,
    DELETE_SET_TXT_FILENAME,
    render_delete_set_html,
    render_delete_set_text,
)
from filesteward.policy.paths import run_dir as policy_run_dir
from tests.test_delete_manifest import write_synthetic_run


@pytest.fixture
def d1_surface_run_dir() -> Iterator[Path]:
    path = policy_run_dir(f"test-d1-surface-{uuid.uuid4().hex[:10]}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_surface_answers_operator_decision_questions(
    d1_surface_run_dir: Path,
) -> None:
    write_synthetic_run(d1_surface_run_dir)
    result = emit_delete_manifest(d1_surface_run_dir)
    text = result.text_path.read_text(encoding="utf-8")
    html = result.html_path.read_text(encoding="utf-8")

    assert result.text_path.name == DELETE_SET_TXT_FILENAME
    assert result.html_path.name == DELETE_SET_HTML_FILENAME

    for body in (text, html):
        assert "item_count" in body or "item_count" in body.lower() or "Exact items" in body
        assert "UNAPPROVED" in body
        assert "QUARANTINE" in body
        assert "REVERSIBLE_QUARANTINE" in body or "reversible quarantine" in body.casefold()
        assert "HUMAN_REVIEW" in body
        assert "PROTECTED" in body
        assert "KEEP_PROVEN" in body
        assert "UNKNOWN" in body
        assert "Nothing was mutated" in body or "nothing was mutated" in body.casefold()
        assert "D2" in body or "preflight" in body.casefold()
        assert "free-space" in body.casefold() or "free space" in body.casefold()
        assert r"C:\SyntheticCache\body.bin" in body
        assert "80" in body  # projected / allocated evidence

    # Text surface carries exact byte totals explicitly.
    assert "logical_size_bytes: 100 bytes" in text
    assert "allocated_size_bytes: 80 bytes" in text
    assert "projected_reclaim_bytes: 80 bytes" in text
    assert "Permanent deletion" in text or "DELETE_PERMANENTLY" in text


def test_render_helpers_cover_empty_set() -> None:
    empty = {
        "schema_version": "filesteward.delete-manifest/v1",
        "run_id": "empty",
        "source_cleanup_plan_sha256": "0" * 64,
        "authorization_state": "UNAPPROVED",
        "intended_action": "QUARANTINE",
        "item_count": 0,
        "totals": {
            "logical_size_bytes": 0,
            "allocated_size_bytes": 0,
            "projected_reclaim_bytes": 0,
            "projection_quality": "unknown",
        },
        "untouched": {
            "human_review_count": 2,
            "protected_count": 1,
            "unknown_count": 1,
            "keep_proven_count": 3,
            "note": "excluded",
        },
        "items": [],
    }
    text = render_delete_set_text(empty)
    html = render_delete_set_html(empty)
    assert "(empty delete set)" in text
    assert "(empty delete set)" in html
    assert "HUMAN_REVIEW: 2" in text
    assert "KEEP_PROVEN: 3" in text
