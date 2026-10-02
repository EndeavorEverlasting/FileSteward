"""Visualization package: F0-frozen tokens/contracts and thin call-stack seams.

F1 owns model construction. F2 owns full HTML report assembly (expands shell).
F3 owns treemap geometry. F4 owns CLI orchestration and atomic publication.
This package must not reclassify evidence or grant authorization.
"""

from __future__ import annotations

from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
    ViewportMode,
)
from filesteward.visualization.css import render_token_css
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.model import build_presentation_model
from filesteward.visualization.selection import SelectionController
from filesteward.visualization.shell import render_report_shell
from filesteward.visualization.tokens import disposition_css_stem, load_tokens

__all__ = [
    "GateStep",
    "GateStepStatus",
    "PresentationModel",
    "PresentationNode",
    "SelectionController",
    "ShellMetrics",
    "ViewportMode",
    "build_presentation_model",
    "disposition_css_stem",
    "escape_attr",
    "escape_text",
    "load_tokens",
    "render_report_shell",
    "render_token_css",
]
