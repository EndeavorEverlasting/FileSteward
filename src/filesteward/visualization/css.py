"""Emit CSS custom properties from the frozen visual-system token document."""

from __future__ import annotations

from typing import Mapping

from filesteward.visualization.tokens import load_tokens

__all__ = ["render_token_css"]


def _theme_block(theme: Mapping[str, str], indent: str = "  ") -> str:
    lines = []
    for key, value in theme.items():
        lines.append(f"{indent}--fs-{key}: {value};")
    return "\n".join(lines)


def render_token_css() -> str:
    """Return the shared CSS token skeleton for embedding in the offline report.

    Call stack:
      render_token_css -> load_tokens -> :root + dark media query + motion/focus hooks
    """

    tokens = load_tokens()
    light = tokens["themes"]["light"]
    dark = tokens["themes"]["dark"]
    space = tokens["space"]["scale_px"]
    radius = tokens["radius_px"]
    motion = tokens["motion"]
    type_scale = tokens["typography"]["scale"]
    sans = ", ".join(f'"{f}"' if " " in f else f for f in tokens["typography"]["sans"])
    mono = ", ".join(f'"{f}"' if " " in f else f for f in tokens["typography"]["mono"])

    space_lines = "\n".join(
        f"  --fs-space-{key}: {value}px;" for key, value in space.items()
    )
    radius_lines = "\n".join(
        f"  --fs-radius-{key}: {value}px;"
        for key, value in radius.items()
        if key != "treemap_max"
    )
    type_lines = []
    for name, spec in type_scale.items():
        css_name = name.replace("_", "-")
        type_lines.append(f"  --fs-type-{css_name}-size: {spec['size_px']}px;")
        type_lines.append(
            f"  --fs-type-{css_name}-line: {spec['line_height_px']}px;"
        )
        type_lines.append(f"  --fs-type-{css_name}-weight: {spec['weight']};")

    return f"""/* FileSteward visual-system tokens v1 — generated from frozen contract */
:root {{
  color-scheme: light dark;
  --fs-font-sans: {sans};
  --fs-font-mono: {mono};
{space_lines}
{radius_lines}
{chr(10).join(type_lines)}
  --fs-radius-treemap: {radius['treemap_max']}px;
  --fs-shadow-sm: {tokens['shadow']['light']['sm']};
  --fs-shadow-md: {tokens['shadow']['light']['md']};
  --fs-motion-easing: {motion['easing']};
  --fs-motion-hover: {motion['hover_ms'][1]}ms;
  --fs-motion-selection: {motion['selection_ms'][1]}ms;
{_theme_block(light)}
}}

@media (prefers-color-scheme: dark) {{
  :root {{
    --fs-shadow-sm: {tokens['shadow']['dark']['sm']};
    --fs-shadow-md: {tokens['shadow']['dark']['md']};
{_theme_block(dark, indent='    ')}
  }}
}}

@media (prefers-reduced-motion: reduce) {{
  :root {{
    --fs-motion-hover: {motion['reduced_motion_ms']}ms;
    --fs-motion-selection: {motion['reduced_motion_ms']}ms;
  }}
  *, *::before, *::after {{
    animation-duration: {motion['reduced_motion_ms']}ms !important;
    transition-duration: {motion['reduced_motion_ms']}ms !important;
    scroll-behavior: auto !important;
  }}
}}

@media (forced-colors: active) {{
  :root {{
    --fs-bg-canvas: Canvas;
    --fs-bg-shell: Canvas;
    --fs-bg-surface-1: Canvas;
    --fs-bg-surface-2: Canvas;
    --fs-text-primary: CanvasText;
    --fs-border-subtle: CanvasText;
    --fs-accent: Highlight;
    --fs-focus: Highlight;
  }}
}}
"""
