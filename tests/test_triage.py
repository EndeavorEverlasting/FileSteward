"""Receipt triage: path-prefix buckets from HUMAN_REVIEW rows."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from filesteward.cli import EXIT_INVALID, EXIT_OK, main
from filesteward.manifest.triage import (
    aggregate_human_review_buckets,
    contract_hint_tags,
    path_prefix,
    triage_run_dir,
)
from pathlib import PureWindowsPath, PurePosixPath


def test_path_prefix_windows_depth() -> None:
    path = PureWindowsPath(r"C:\Users\example\AppData\Local\Temp\a.txt")
    assert path_prefix(path, 2) == r"C:\Users"
    assert path_prefix(path, 4) == r"C:\Users\example\AppData"


def test_path_prefix_posix_depth() -> None:
    path = PurePosixPath("/home/example/.cache/pip/http/x")
    assert path_prefix(path, 3) == "/home/example"
    assert path_prefix(path, 4) == "/home/example/.cache"


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


def test_triage_run_dir_writes_bucket_artifacts(tmp_path: Path) -> None:
    review = tmp_path / "human-review.csv"
    with review.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "path",
                "disposition",
                "logical_size_bytes",
                "allocated_size_bytes",
                "why_ambiguous",
                "what_operator_should_check",
                "known_context",
                "risk_if_acted_on",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_id": "1",
                "path": r"C:\cache\pip\http\a",
                "disposition": "HUMAN_REVIEW",
                "logical_size_bytes": "42",
                "allocated_size_bytes": "",
                "why_ambiguous": "no explicit contract evidence",
                "what_operator_should_check": "whether regenerable",
                "known_context": "",
                "risk_if_acted_on": "unknown",
            }
        )

    result = triage_run_dir(tmp_path, depth=2)
    assert result.human_review_rows == 1
    assert result.csv_path.is_file()
    assert result.markdown_path.is_file()
    text = result.markdown_path.read_text(encoding="utf-8").lower()
    assert "not reclaim authority" in text or "not** reclaim authority" in text
    assert "reclaim_proven" not in text
    assert "no approval" in text


def test_cli_plan_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    review = tmp_path / "human-review.csv"
    review.write_text(
        "item_id,path,disposition,logical_size_bytes,allocated_size_bytes,"
        "why_ambiguous,what_operator_should_check,known_context,risk_if_acted_on\n"
        "1,C:\\cache\\pip\\x,HUMAN_REVIEW,10,,, ,,\n",
        encoding="utf-8",
    )
    code = main(["plan", str(tmp_path), "--depth", "2", "--top", "5"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "buckets" in out
    assert "no reclaim nomination" in out
    assert (tmp_path / "human-review-buckets.csv").is_file()


def test_cli_plan_missing_dir(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["plan", "C:/definitely-missing-filesteward-run-dir"])
    assert code == EXIT_INVALID
    assert "not found" in capsys.readouterr().err
