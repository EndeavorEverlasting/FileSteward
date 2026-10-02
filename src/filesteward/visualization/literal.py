"""Literal rendering helpers for receipt-derived strings.

Dynamic strings must never execute or alter markup. Prefer DOM textContent
in browser JS; Python emitters use these escapes when embedding into HTML.
"""

from __future__ import annotations

__all__ = ["escape_attr", "escape_text"]

_TEXT_REPLACEMENTS = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&#39;"),
)


def escape_text(value: str) -> str:
    """Escape a string for HTML text-node / element-body context."""

    if not isinstance(value, str):
        raise TypeError("escape_text requires str")
    out = value
    for src, dst in _TEXT_REPLACEMENTS:
        out = out.replace(src, dst)
    return out


def escape_attr(value: str) -> str:
    """Escape a string for a double-quoted HTML attribute context."""

    return escape_text(value)
