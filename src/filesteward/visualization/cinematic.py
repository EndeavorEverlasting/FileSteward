"""Cinematic storage-atlas presentation helpers.

Presentation-only overview/focus state for the offline report.
Never classifies evidence, grants authorization, or mutates receipt data.
"""

from __future__ import annotations

from typing import Optional, Sequence

from filesteward.visualization.contracts import PresentationNode
from filesteward.visualization.literal import escape_attr, escape_text
from filesteward.visualization.tokens import disposition_css_stem

__all__ = [
    "OVERVIEW_LIMIT",
    "render_cinematic_css",
    "render_cinematic_script",
    "render_focus_chamber",
    "render_focus_templates",
    "render_sector_overview",
    "render_substrate_svg",
]

OVERVIEW_LIMIT = 12
