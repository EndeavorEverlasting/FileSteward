"""F4 visualization orchestration: validate -> model -> layout -> atomic HTML.

This module contains no disposition judgment. It wires F1/F2/F3 seams and
refuses to publish when validation fails.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
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

#: Validated run evidence that visualization must never overwrite.
_PROTECTED_RUN_ARTIFACTS = frozenset(
    {
        "cleanup-plan.csv",
        "human-review.csv",
        "protected-exclusions.csv",
        "inventory.csv",
        "cleanup-summary.md",
        "run.json",
        "human-review-buckets.csv",
        "human-review-buckets.md",
    }
)


def _validate_output_name(output_name: str) -> str:
    """Require one safe filename that cannot escape or overwrite run evidence."""

    if not output_name or output_name in {".", ".."}:
        raise ValueError("visualization output_name must be a non-empty filename")
    win = PureWindowsPath(output_name)
    if (
        Path(output_name).is_absolute()
        or win.is_absolute()
        or bool(win.drive)
        or "/" in output_name
        or "\\" in output_name
        or ":" in output_name
    ):
        raise ValueError("visualization output_name must not contain a path")
    # Windows artifact comparison is case-insensitive; reject protected names.
    if output_name.casefold() in {name.casefold() for name in _PROTECTED_RUN_ARTIFACTS}:
        raise ValueError(
            "visualization output_name must not overwrite a required run artifact"
        )
    return output_name


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
    safe_output_name = _validate_output_name(output_name)
    errors = validate_run(target)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(
            f"run failed FileSteward validation ({len(errors)} problem(s)): {joined}"
        )

    model = build_presentation_model(target)
    rects = layout_treemap(model.nodes)
    html = render_report_html(model, rects, title=title)
    report_path = target / safe_output_name
    write_report_html_atomically(report_path, html)
    return VisualizeResult(
        run_dir=target,
        report_path=report_path,
        node_count=len(model.nodes),
        run_id=model.run_id,
    )
