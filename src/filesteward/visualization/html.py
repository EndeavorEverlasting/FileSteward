"""F2 production HTML report assembly.

Expands the F0 shell with filter/search chrome and atomic publication helper.
Does not infer evidence or layout treemap geometry.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from filesteward.visualization.contracts import PresentationModel, TreemapRect
from filesteward.visualization.shell import render_report_shell

__all__ = ["render_report_html", "write_report_html_atomically"]


def render_report_html(
    model: PresentationModel,
    rects: Optional[Sequence[TreemapRect]] = None,
    *,
    title: Optional[str] = None,
    selected_id: Optional[str] = None,
) -> str:
    """Render a self-contained offline HTML report string."""

    html = render_report_shell(
        model,
        rects,
        title=title or "FileSteward Storage Decision Map",
        selected_id=selected_id,
    )
    # Inject display-only filter/search controls into the navigator pane head.
    controls = """
      <div class="filters" role="group" aria-label="Evidence filters">
        <button type="button" class="filter-chip active" data-filter="ALL">All</button>
        <button type="button" class="filter-chip" data-filter="HUMAN_REVIEW">Human review</button>
        <button type="button" class="filter-chip" data-filter="RECLAIM_PROVEN">Reclaim proven</button>
        <button type="button" class="filter-chip" data-filter="PROTECTED">Protected</button>
        <button type="button" class="filter-chip" data-filter="UNKNOWN">Unknown</button>
        <button type="button" class="filter-chip" data-filter="KEEP_PROVEN">Keep</button>
      </div>
      <label class="search-label">Search paths and groups
        <input type="search" class="search-field" height="36" style="height:36px;width:100%;"
               placeholder="Search paths and groups" aria-label="Search paths and groups">
      </label>
"""
    extra_css = """
.filter-chip{border:1px solid var(--fs-border-default);background:var(--fs-bg-surface-2);color:var(--fs-text-secondary);border-radius:var(--fs-radius-pill);padding:4px 10px;font-size:var(--fs-type-small-size);cursor:pointer;margin:2px;}
.filter-chip.active{background:var(--fs-accent-100);color:var(--fs-accent-800);border-color:var(--fs-accent-300);}
.search-label{display:block;padding:var(--fs-space-2) var(--fs-space-3);font-size:var(--fs-type-small-size);color:var(--fs-text-muted);}
.search-field{margin-top:4px;border:1px solid var(--fs-border-default);border-radius:var(--fs-radius-sm);background:var(--fs-bg-surface-1);color:var(--fs-text-primary);padding:0 10px;}
"""
    if "</style>" in html:
        html = html.replace("</style>", extra_css + "</style>", 1)
    needle = '<div class="pane-head"><h2>Storage navigator</h2></div>'
    if needle in html:
        html = html.replace(
            needle,
            '<div class="pane-head"><h2>Storage navigator</h2></div>' + controls,
            1,
        )

    filter_data = {
        node.node_id: {
            "disposition": node.disposition.value,
            "search": f"{node.display_name} {node.path}".casefold(),
        }
        for node in model.nodes
    }
    payload = (
        json.dumps(filter_data, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    behavior = f"""
<script>
(() => {{
  const nodeMeta = {payload};
  let activeFilter = "ALL";
  let query = "";

  const visibleFor = (id) => {{
    const meta = nodeMeta[id];
    if (!meta) return true;
    const stateMatch = activeFilter === "ALL" || meta.disposition === activeFilter;
    const searchMatch = !query || meta.search.includes(query);
    return stateMatch && searchMatch;
  }};

  const applyFilters = () => {{
    document.querySelectorAll('[data-node-id]').forEach((el) => {{
      const id = el.getAttribute('data-node-id');
      el.hidden = !visibleFor(id);
    }});

    document.querySelectorAll('.filter-chip').forEach((chip) => {{
      const active = chip.getAttribute('data-filter') === activeFilter;
      chip.classList.toggle('active', active);
      chip.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});

    const selected = document.querySelector('.nav-row.selected:not([hidden])');
    if (!selected) {{
      const first = document.querySelector('.nav-row:not([hidden])');
      if (first) first.click();
    }}
  }};

  document.querySelectorAll('.filter-chip').forEach((chip) => {{
    chip.setAttribute(
      'aria-pressed',
      chip.getAttribute('data-filter') === activeFilter ? 'true' : 'false'
    );
    chip.addEventListener('click', () => {{
      activeFilter = chip.getAttribute('data-filter') || 'ALL';
      applyFilters();
    }});
  }});

  const search = document.querySelector('.search-field');
  if (search) {{
    search.addEventListener('input', () => {{
      query = search.value.trim().toLocaleLowerCase();
      applyFilters();
    }});
  }}
  applyFilters();
}})();
</script>
"""
    if "</body>" in html:
        html = html.replace("</body>", behavior + "</body>", 1)
    return html


def write_report_html_atomically(path: Path, html: str) -> None:
    """Atomically publish HTML beside sibling artifacts (temp + replace)."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
