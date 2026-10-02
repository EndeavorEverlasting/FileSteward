"""F4 visualization orchestration: validate -> model -> layout -> atomic HTML.

This module contains no disposition judgment. It wires F1/F2/F3 seams and
refuses to publish when validation fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from filesteward.manifest import validate_run
from filesteward.policy.paths import prove_run_dir_under_runtime
from filesteward.visualization.html import render_report_html, write_report_html_atomically
from filesteward.visualization.model import build_presentation_model
from filesteward.visualization.treemap import layout_treemap

__all__ = [
    "REPORT_FILENAME",
    "VisualizeResult",
    "visualize_run_dir",
]

REPORT_FILENAME = "storage-decision-map.html"


class VisualizeResult:
    """Outcome of a successful read-only visualization publication."""

    __slots__ = ("run_dir", "report_path", "node_count", "run_id")

    def __init__(
        self,
        *,
        run_dir: Path,
        report_path: Path,
        node_count: int,
        run_id: str,
    ) -> None:
        self.run_dir = run_dir
        self.report_path = report_path
        self.node_count = node_count
        self.run_id = run_id


def visualize_run_dir(
    run_dir: Path,
    *,
    output_name: str = REPORT_FILENAME,
    title: Optional[str] = None,
) -> VisualizeResult:
    """Build and atomically publish a self-contained offline HTML report.

    Call stack:
      prove_run_dir_under_runtime
        -> validate_run (fail closed)
        -> build_presentation_model
        -> layout_treemap
        -> render_report_html
        -> write_report_html_atomically
    """

    target = prove_run_dir_under_runtime(run_dir)
    errors = validate_run(target)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(
            f"run failed FileSteward validation ({len(errors)} problem(s)): {joined}"
        )

    model = build_presentation_model(target)
    rects = layout_treemap(model.nodes)
    html = render_report_html(model, rects, title=title)
    report_path = target / output_name
    write_report_html_atomically(report_path, html)
    return VisualizeResult(
        run_dir=target,
        report_path=report_path,
        node_count=len(model.nodes),
        run_id=model.run_id,
    )
