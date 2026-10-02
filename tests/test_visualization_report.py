"""F4 visualize convergence: validate -> model -> layout -> atomic HTML."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from filesteward.cli import EXIT_INVALID, EXIT_OK, main
from filesteward.policy.paths import run_dir as policy_run_dir
from filesteward.visualization.report import REPORT_FILENAME, visualize_run_dir
from test_visualization_model import _write_valid_run


@pytest.fixture
def viz_run_dir() -> Iterator[Path]:
    path = policy_run_dir(f"test-viz-{uuid.uuid4().hex[:10]}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_visualize_run_dir_publishes_atomic_report(viz_run_dir: Path) -> None:
    _write_valid_run(viz_run_dir)
    before = {p.name for p in viz_run_dir.iterdir()}
    result = visualize_run_dir(viz_run_dir)
    assert result.report_path.name == REPORT_FILENAME
    assert result.report_path.is_file()
    assert result.node_count >= 5
    html = result.report_path.read_text(encoding="utf-8")
    assert "UNAPPROVED" in html
    assert "Logical size" in html
    assert "&lt;profile&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "apply</button>" not in html.lower()
    after = {p.name for p in viz_run_dir.iterdir()}
    assert REPORT_FILENAME in after
    assert before <= after
    assert not list(viz_run_dir.glob(".*.tmp"))


def test_visualize_cli_success(viz_run_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_valid_run(viz_run_dir)
    code = main(["visualize", str(viz_run_dir)])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert REPORT_FILENAME in out
    assert "no approval" in out.lower() or "UNAPPROVED" in out
    assert (viz_run_dir / REPORT_FILENAME).is_file()


def test_visualize_cli_refuses_invalid_run(
    viz_run_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_valid_run(viz_run_dir)
    (viz_run_dir / "inventory.csv").write_text("broken\n", encoding="utf-8")
    code = main(["visualize", str(viz_run_dir)])
    assert code == EXIT_INVALID
    err = capsys.readouterr().err
    assert "visualize" in err
    assert not (viz_run_dir / REPORT_FILENAME).exists()


def test_visualize_refuses_outside_runtime(tmp_path: Path) -> None:
    code = main(["visualize", str(tmp_path / "outside")])
    assert code == EXIT_INVALID


@pytest.mark.parametrize(
    "output_name",
    [
        "../escaped.html",
        r"..\escaped.html",
        r"C:\escaped.html",
    ],
)
def test_visualize_rejects_output_name_path_escape(
    viz_run_dir: Path, output_name: str
) -> None:
    _write_valid_run(viz_run_dir)
    with pytest.raises(ValueError, match="output_name"):
        visualize_run_dir(viz_run_dir, output_name=output_name)


def test_visualize_accepts_single_custom_filename(viz_run_dir: Path) -> None:
    _write_valid_run(viz_run_dir)
    result = visualize_run_dir(viz_run_dir, output_name="custom-map.html")
    assert result.report_path == viz_run_dir / "custom-map.html"
    assert result.report_path.is_file()
