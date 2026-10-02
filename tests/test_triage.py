"""Receipt triage: path-prefix buckets from HUMAN_REVIEW rows."""

from __future__ import annotations

import csv
import shutil
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator

import pytest

from filesteward.cli import EXIT_INVALID, EXIT_OK, main
from filesteward.manifest.triage import (
    aggregate_human_review_buckets,
    contract_hint_tags,
    path_prefix,
    receipt_path_class,
    triage_run_dir,
)
from filesteward.policy.paths import run_dir as policy_run_dir


@pytest.fixture
def triage_run() -> Iterator[Path]:
    path = policy_run_dir(f"test-triage-{uuid.uuid4().hex[:10]}")
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_path_prefix_windows_depth() -> None:
    path = PureWindowsPath(r"C:\Users\example\AppData\Local\Temp\a.txt")
    assert path_prefix(path, 2) == r"C:\Users"
    assert path_prefix(path, 4) == r"C:\Users\example\AppData"


def test_path_prefix_posix_depth() -> None:
    path = PurePosixPath("/home/example/.cache/pip/http/x")
    assert path_prefix(path, 3) == "/home/example"
    assert path_prefix(path, 4) == "/home/example/.cache"


def test_receipt_path_class_preserves_windows_flavor_on_any_host() -> None:
    assert receipt_path_class(r"C:\Users\x\cache\a") is PureWindowsPath
    assert receipt_path_class("/home/x/.cache/a") is PurePosixPath
    parsed = receipt_path_class(r"C:\Users\x\cache\a")(r"C:\Users\x\cache\a")
    assert path_prefix(parsed, 3) == r"C:\Users\x"
    assert "cache" in contract_hint_tags(r"C:\Users\x\cache")


def test_contract_hint_tags_are_non_authoritative_substrings() -> None:
    assert "cache" in contract_hint_tags(r"C:\Users\x\AppData\Local\pip\cache")
    assert "pip" in contract_hint_tags(r"C:\Users\x\AppData\Local\pip\cache")
    assert "temp" in contract_hint_tags(r"C:\Windows\Temp")
    assert contract_hint_tags(r"C:\Users\x\Documents\records") == ()


def test_aggregate_sorts_by_logical_bytes() -> None:
    rows = [
        {
            "disposition": "HUMAN_REVIEW",
            "path": r"C:\Users\a\big\file.bin",
            "logical_size_bytes": "1000",
        },
        {
            "disposition": "HUMAN_REVIEW",
            "path": r"C:\Users\a\big\other.bin",
            "logical_size_bytes": "500",
        },
        {
            "disposition": "HUMAN_REVIEW",
            "path": r"C:\Temp\small\x.bin",
            "logical_size_bytes": "50",
        },
        {
            "disposition": "PROTECTED",
            "path": r"C:\repo\secret",
            "logical_size_bytes": "999999",
        },
        {
            "disposition": "UNKNOWN",
            "path": r"C:\Temp\denied",
            "logical_size_bytes": "",
        },
    ]
    buckets = aggregate_human_review_buckets(rows, depth=2)
    assert [b.prefix for b in buckets] == [r"C:\Users", r"C:\Temp"]
    assert buckets[0].item_count == 2
    assert buckets[0].logical_bytes_known == 1500
    assert buckets[1].item_count == 2
    assert buckets[1].logical_bytes_known == 50
    assert buckets[1].unknown_size_count == 1
    assert "temp" in buckets[1].contract_hint_tags


def _write_review(path: Path, *, include_disposition: bool = True) -> None:
    fields = [
        "item_id",
        "path",
        "logical_size_bytes",
        "allocated_size_bytes",
        "why_ambiguous",
        "what_operator_should_check",
        "known_context",
        "risk_if_acted_on",
    ]
    if include_disposition:
        fields.insert(2, "disposition")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        row = {
            "item_id": "1",
            "path": r"C:\cache\pip\http\a",
            "logical_size_bytes": "42",
            "allocated_size_bytes": "",
            "why_ambiguous": "no explicit contract evidence",
            "what_operator_should_check": "whether regenerable",
            "known_context": "",
            "risk_if_acted_on": "unknown",
        }
        if include_disposition:
            row["disposition"] = "HUMAN_REVIEW"
        writer.writerow(row)


def test_triage_run_dir_writes_bucket_artifacts(triage_run: Path) -> None:
    _write_review(triage_run / "human-review.csv")
    result = triage_run_dir(triage_run, depth=2)
    assert result.human_review_rows == 1
    assert result.csv_path.is_file()
    assert result.markdown_path.is_file()
    text = result.markdown_path.read_text(encoding="utf-8").lower()
    assert "not reclaim authority" in text or "not** reclaim authority" in text
    assert "reclaim_proven" not in text
    assert "no approval" in text


def test_triage_rejects_missing_disposition_column(triage_run: Path) -> None:
    _write_review(triage_run / "human-review.csv", include_disposition=False)
    with pytest.raises(ValueError, match="missing required columns"):
        triage_run_dir(triage_run, depth=2)


def test_cli_plan_happy_path(
    triage_run: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_review(triage_run / "human-review.csv")
    code = main(["plan", str(triage_run), "--depth", "2", "--top", "5"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "buckets" in out
    assert "no reclaim nomination" in out
    assert (triage_run / "human-review-buckets.csv").is_file()


def test_cli_plan_rejects_outside_runtime(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = tmp_path / "human-review.csv"
    _write_review(review)
    code = main(["plan", str(tmp_path)])
    assert code == EXIT_INVALID
    assert "runtime tree" in capsys.readouterr().err
