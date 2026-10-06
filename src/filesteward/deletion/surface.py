"""Operator-readable delete-set decision surface (HTML + text).

Projection only: never a visualize report rewrite, never an approval, and
never a mutation of scanned targets. Preflight freshness is explicitly
deferred to D2.
"""

from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "DELETE_SET_HTML_FILENAME",
    "DELETE_SET_TXT_FILENAME",
    "render_delete_set_html",
    "render_delete_set_text",
    "write_delete_set_surface",
]

DELETE_SET_HTML_FILENAME = "delete-set.html"
DELETE_SET_TXT_FILENAME = "delete-set.txt"


def _fmt_bytes(value: Any) -> str:
    if value is None:
        return "unknown"
    return f"{int(value)} bytes"


def render_delete_set_text(manifest: Mapping[str, Any]) -> str:
    """Plain-text operator decision surface for one delete-manifest."""

    totals = manifest.get("totals") or {}
    untouched = manifest.get("untouched") or {}
    items = list(manifest.get("items") or [])
    lines = [
        "FileSteward delete set — exact UNAPPROVED quarantine candidates",
        "",
        f"schema_version: {manifest.get('schema_version')}",
        f"run_id: {manifest.get('run_id')}",
        f"source_cleanup_plan_sha256: {manifest.get('source_cleanup_plan_sha256')}",
        f"authorization_state: {manifest.get('authorization_state')}",
        f"intended_action: {manifest.get('intended_action')}",
        f"reversibility (lane default): REVERSIBLE_QUARANTINE",
        f"item_count: {manifest.get('item_count')}",
        "",
        "## Totals",
        f"- logical_size_bytes: {_fmt_bytes(totals.get('logical_size_bytes'))}",
        f"- allocated_size_bytes: {_fmt_bytes(totals.get('allocated_size_bytes'))}",
        f"- projected_reclaim_bytes: {_fmt_bytes(totals.get('projected_reclaim_bytes'))}",
        f"- projection_quality: {totals.get('projection_quality')}",
        "",
        "## Reversibility",
        "- This delete set defaults to QUARANTINE / REVERSIBLE_QUARANTINE.",
        "- Permanent deletion (DELETE_PERMANENTLY) is NOT claimed and is NOT executed.",
        "- Same-volume quarantine is not verified free-space reclaim.",
        "",
        "## Approval",
        "- authorization_state=UNAPPROVED",
        "- This artifact does not authorize mutation.",
        "",
        "## Freshness / preflight",
        "- Mutation preflight is owned by D2 and is NOT included here.",
        "- Predicted vs verified free-space delta is NOT yet measured.",
        "",
        "## Will NOT be touched",
        f"- HUMAN_REVIEW: {untouched.get('human_review_count', 0)}",
        f"- PROTECTED: {untouched.get('protected_count', 0)}",
        f"- UNKNOWN: {untouched.get('unknown_count', 0)}",
        f"- KEEP_PROVEN: {untouched.get('keep_proven_count', 0)}",
        f"- note: {untouched.get('note', '')}",
        "",
        "## Exact items (what would disappear under a later approved quarantine)",
    ]
    if not items:
        lines.append("- (empty delete set)")
    else:
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"{index}. {item.get('path')}",
                    f"   item_id={item.get('item_id')}",
                    f"   item_type={item.get('item_type')}",
                    f"   disposition={item.get('disposition')}",
                    f"   evidence={item.get('evidence')}",
                    f"   contract_source={item.get('contract_source')}",
                    f"   logical={_fmt_bytes(item.get('logical_size_bytes'))}",
                    f"   allocated={_fmt_bytes(item.get('allocated_size_bytes'))}",
                    f"   projected_reclaim={_fmt_bytes(item.get('projected_reclaim_bytes'))}",
                    f"   reclaim_basis={item.get('reclaim_basis')}",
                    f"   projection_quality={item.get('projection_quality')}",
                    f"   intended_action={item.get('intended_action')}",
                    f"   reversibility={item.get('reversibility')}",
                    f"   is_symlink={item.get('is_symlink')} "
                    f"is_reparse_point={item.get('is_reparse_point')} "
                    f"is_cloud_placeholder={item.get('is_cloud_placeholder')} "
                    f"is_managed={item.get('is_managed')}",
                ]
            )
    lines.extend(
        [
            "",
            "## Safety statement",
            "Nothing was mutated. No deletion occurred. No Recycle Bin purge occurred.",
            "",
        ]
    )
    return "\n".join(lines)


def render_delete_set_html(manifest: Mapping[str, Any]) -> str:
    """Minimal self-contained HTML decision surface (not the visualize stack)."""

    totals = manifest.get("totals") or {}
    untouched = manifest.get("untouched") or {}
    items = list(manifest.get("items") or [])

    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{esc(item.get('item_id'))}</td>"
            f"<td><code>{esc(item.get('path'))}</code></td>"
            f"<td>{esc(item.get('item_type'))}</td>"
            f"<td>{esc(item.get('disposition'))}</td>"
            f"<td>{esc(item.get('evidence'))}</td>"
            f"<td>{esc(item.get('logical_size_bytes'))}</td>"
            f"<td>{esc(item.get('allocated_size_bytes'))}</td>"
            f"<td>{esc(item.get('projected_reclaim_bytes'))}</td>"
            f"<td>{esc(item.get('intended_action'))}</td>"
            f"<td>{esc(item.get('reversibility'))}</td>"
            "</tr>"
        )
    body_rows = "\n".join(rows) if rows else (
        '<tr><td colspan="10">(empty delete set)</td></tr>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>FileSteward delete set — {esc(manifest.get('run_id'))}</title>
  <style>
    body {{ font-family: Consolas, "Courier New", monospace; margin: 1.5rem; color: #1b1b1b; background: #f7f4ef; }}
    h1, h2 {{ font-family: Georgia, "Times New Roman", serif; }}
    .banner {{ border: 2px solid #7a3e12; padding: 0.75rem 1rem; background: #fff6e8; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; background: #fff; }}
    th, td {{ border: 1px solid #c9bdae; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #efe7da; }}
    code {{ word-break: break-all; }}
    .meta dt {{ font-weight: bold; }}
    .meta dd {{ margin: 0 0 0.4rem 0; }}
  </style>
</head>
<body>
  <h1>FileSteward delete set</h1>
  <p class="banner">
    Authorization: <strong>{esc(manifest.get('authorization_state'))}</strong>.
    Intended action: <strong>{esc(manifest.get('intended_action'))}</strong>
    (reversible quarantine). Nothing was mutated. No deletion occurred.
    Permanent deletion is not claimed. Preflight freshness is D2 (not measured here).
    Predicted vs verified free-space is not yet measured.
  </p>
  <dl class="meta">
    <dt>schema_version</dt><dd>{esc(manifest.get('schema_version'))}</dd>
    <dt>run_id</dt><dd>{esc(manifest.get('run_id'))}</dd>
    <dt>source_cleanup_plan_sha256</dt><dd><code>{esc(manifest.get('source_cleanup_plan_sha256'))}</code></dd>
    <dt>item_count</dt><dd>{esc(manifest.get('item_count'))}</dd>
    <dt>logical_size_bytes</dt><dd>{esc(totals.get('logical_size_bytes'))}</dd>
    <dt>allocated_size_bytes</dt><dd>{esc(totals.get('allocated_size_bytes'))}</dd>
    <dt>projected_reclaim_bytes</dt><dd>{esc(totals.get('projected_reclaim_bytes'))}</dd>
    <dt>projection_quality</dt><dd>{esc(totals.get('projection_quality'))}</dd>
  </dl>
  <h2>Will NOT be touched</h2>
  <ul>
    <li>HUMAN_REVIEW: {esc(untouched.get('human_review_count', 0))}</li>
    <li>PROTECTED: {esc(untouched.get('protected_count', 0))}</li>
    <li>UNKNOWN: {esc(untouched.get('unknown_count', 0))}</li>
    <li>KEEP_PROVEN: {esc(untouched.get('keep_proven_count', 0))}</li>
  </ul>
  <p>{esc(untouched.get('note', ''))}</p>
  <h2>Exact items</h2>
  <table>
    <thead>
      <tr>
        <th>item_id</th>
        <th>path</th>
        <th>type</th>
        <th>disposition</th>
        <th>evidence</th>
        <th>logical</th>
        <th>allocated</th>
        <th>projected reclaim</th>
        <th>action</th>
        <th>reversibility</th>
      </tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</body>
</html>
"""


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_delete_set_surface(
    run_dir: Path, manifest: Mapping[str, Any]
) -> tuple[Path, Path]:
    """Write ``delete-set.html`` and ``delete-set.txt`` beside the manifest."""

    target = Path(run_dir)
    html_path = target / DELETE_SET_HTML_FILENAME
    text_path = target / DELETE_SET_TXT_FILENAME
    _atomic_write_text(html_path, render_delete_set_html(manifest))
    _atomic_write_text(text_path, render_delete_set_text(manifest))
    return html_path, text_path
