"""Display scan coverage and the bridge's recorded decision readback."""

from filesteward.models import CleanupDisposition
from filesteward.visualization.literal import escape_text
from filesteward.visualization.storage_coverage import Coverage, StorageCoverage

_LABELS = {
    CleanupDisposition.KEEP_PROVEN: "Keep evidence",
    CleanupDisposition.PROTECTED: "Protected",
    CleanupDisposition.RECLAIM_PROVEN: "Reclaim evidence",
    CleanupDisposition.HUMAN_REVIEW: "Needs review",
    CleanupDisposition.UNKNOWN: "Unknown",
}


def _size_label(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{size:,} B" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable byte unit")


def _size_html(size: int) -> str:
    return f'<span title="{size:,} bytes">{_size_label(size)}</span>'


def _ratio(classified: int, total: int) -> float:
    return classified * 100 / total if total else 0


def _disposition_breakdown(coverage: Coverage) -> str:
    return "".join(
        f'<li>{_LABELS[disposition]} <strong>{_size_html(size)}</strong></li>'
        for disposition, size in zip(CleanupDisposition, coverage.bytes_by_disposition)
    )


def render_storage_coverage(coverage: StorageCoverage | None) -> str:
    if coverage is None:
        return ""
    snapshot = coverage.total
    known = snapshot.total_bytes
    classified = snapshot.classified_bytes
    ratio = _ratio(classified, known)
    pie = (
        f'<div class="coverage-pie" role="img" aria-label="{ratio:.1f}% classified, '
        f'{100 - ratio:.1f}% unclassified" style="--coverage-share:{ratio:.6f}%">'
        f'<span>{ratio:.1f}%<small>classified</small></span></div>'
        if known else ""
    )
    rows = []
    for name, sector in coverage.sectors:
        size = sector.total_bytes
        found = sector.classified_bytes
        meter = (
            f'<span class="coverage-meter" aria-hidden="true" '
            f'style="--coverage-share:{_ratio(found, size):.6f}%"></span>'
            if size else ""
        )
        rows.append(
            f'<tr><th scope="row">{escape_text(name)}{meter}</th>'
            f'<td>{_size_html(found)}</td><td>{_size_html(size - found)}</td>'
            f'<td>{sector.files:,}</td><td>{sector.unmeasured:,}</td>'
            '<td><details class="coverage-sector-details"><summary>Breakdown</summary>'
            f'<ul>{_disposition_breakdown(sector)}</ul></details></td></tr>'
        )
    sectors = (
        '<div class="coverage-table" role="region" aria-label="Storage sectors" tabindex="0">'
        '<table><caption>Immediate folders under the scan root</caption>'
        '<thead><tr><th scope="col">Sector</th><th scope="col">Classified</th>'
        '<th scope="col">Unclassified</th><th scope="col">Files</th>'
        '<th scope="col">Size unknown</th><th scope="col">Evidence</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></div>'
        if rows else "<p>No regular file measurements are available for this inventory.</p>"
    )
    return f"""
<details class="storage-coverage" id="storage-coverage">
  <summary>Storage coverage by sector</summary>
  <p>Coverage uses logical file sizes recorded at scan time. Symlinks, reparse points, and cloud placeholders are excluded. Files with unknown sizes count as files and contribute no measured bytes. Disk allocation and reclaimed space are measured separately.</p>
  <div class="coverage-overview">
    {pie}
    <div>
      <dl class="coverage-key">
        <div><dt>Classified</dt><dd>{_size_html(classified)}</dd></div>
        <div><dt>Unclassified</dt><dd>{_size_html(known - classified)}</dd></div>
        <div><dt>Total measured</dt><dd>{_size_html(known)}</dd></div>
      </dl>
      <ul class="coverage-dispositions" aria-label="Scan disposition breakdown">{_disposition_breakdown(snapshot)}</ul>
    </div>
  </div>
  {sectors}
  <section id="coverage-decisions" aria-label="Recorded decisions" hidden>
    <h3>Recorded operator decisions</h3>
    <p id="coverage-decision-counts" role="status"></p>
  </section>
</details>
"""


def render_storage_coverage_css() -> str:
    return """
.storage-coverage{--coverage-found:var(--fs-accent);--coverage-open:color-mix(in srgb,var(--fs-state-review) 20%,var(--fs-bg-surface-1));margin:.55rem 0 0;padding:.55rem .75rem;border:1px solid var(--fs-border-subtle);border-radius:var(--fs-radius-md);background:var(--fs-bg-surface-1);min-width:0;}
.storage-coverage summary{cursor:pointer;font-weight:700;}
.storage-coverage p,.coverage-table caption{color:var(--fs-text-muted);}
.coverage-overview{display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center;}
.coverage-pie{background:conic-gradient(var(--coverage-found) 0 var(--coverage-share),var(--coverage-open) var(--coverage-share) 100%);}
.coverage-pie{box-shadow:inset 0 0 0 1px var(--fs-border-default);width:8rem;aspect-ratio:1;border-radius:50%;display:grid;place-items:center;}
.coverage-pie>span{width:76%;aspect-ratio:1;border-radius:50%;display:grid;align-content:center;text-align:center;background:var(--fs-bg-surface-1);font:700 1.2rem var(--fs-font-mono);}
.coverage-pie small{font:normal .72rem var(--fs-font-mono);}
.coverage-key{display:flex;gap:.65rem 1.25rem;flex-wrap:wrap;margin:.5rem 0;}
.coverage-key dd{margin:0;font:700 1rem var(--fs-font-mono);}
.coverage-key>div:nth-child(-n+2){border-inline-start:3px solid var(--coverage-found);padding-inline-start:.45rem;}
.coverage-key>div:nth-child(2){border-color:var(--coverage-open);}
.coverage-dispositions{list-style:none;padding:0;margin:.55rem 0;display:flex;gap:.35rem .8rem;flex-wrap:wrap;}
.coverage-dispositions strong{white-space:nowrap;}
.coverage-table{contain:inline-size;overflow:auto;max-height:20rem;margin-top:.6rem;}
.coverage-table table{width:100%;border-collapse:collapse;}
.coverage-table caption{text-align:left;margin-bottom:.3rem;}
.coverage-table th,.coverage-table td{text-align:right;border-bottom:1px solid var(--fs-border-subtle);padding:.35rem .5rem;white-space:nowrap;}
.coverage-table th:first-child{text-align:left;white-space:normal;overflow-wrap:anywhere;min-width:7rem;}
.coverage-sector-details{text-align:left;}
.coverage-sector-details ul{padding-left:1.1rem;}
.coverage-meter{background:linear-gradient(to right,var(--coverage-found) 0 var(--coverage-share),var(--coverage-open) var(--coverage-share) 100%);display:block;width:min(100%,10rem);height:.2rem;margin-top:.2rem;border-radius:1rem;}
@media (forced-colors:active){.coverage-pie,.coverage-meter{display:none;}}
"""


def render_storage_coverage_script() -> str:
    return """
<script>
(() => {
  const mount = document.getElementById('coverage-decisions');
  const output = document.getElementById('coverage-decision-counts');
  const runtime = document.getElementById('decision-bridge-runtime');
  if (!mount || !output || !runtime) return;
  const bridge = JSON.parse(runtime.textContent);
  const labels = {
    KEEP: 'Keep',
    REVIEW_LATER: 'Review later',
    RECLAIM_GENERATED_OUTPUT: 'Reclaim requested',
    DELETE_PERMANENTLY: 'Permanent delete recorded'
  };
  let revision = -1;
  const render = (views, next) => {
    if (!views || !Number.isInteger(next) || next < revision) return;
    revision = next;
    const counts = views.operator_intents || {};
    const recorded = Object.entries(labels).filter(([intent]) => counts[intent] > 0)
      .map(([intent, label]) => label + ' ' + counts[intent].toLocaleString());
    output.textContent = recorded.length ? recorded.join(' · ') : 'No Keep, Review later, or removal decisions recorded yet.';
    mount.hidden = false;
  };
  const acceptReadback = (payload) => {
    if (payload && payload.run_id === bridge.runId) render(payload.classification_views, payload.scene_revision);
  };
  document.addEventListener('filesteward:decision-readback', (event) => acceptReadback(event.detail));
  const status = document.getElementById('storage-coverage');
  const readOnOpen = async () => {
    if (!status.open || revision >= 0 || !bridge.origin || !bridge.statePath) return;
    mount.hidden = false;
    output.textContent = 'Reading recorded decisions…';
    try {
      const response = await fetch(bridge.origin + bridge.statePath, {headers: {'Accept': 'application/json'}});
      if (!response.ok) throw new Error('Decision readback refused');
      acceptReadback(await response.json());
      if (revision < 0) throw new Error('Invalid decision readback');
    } catch (_error) {
      if (revision < 0) output.textContent = 'Recorded decisions are unavailable. Reopen coverage to retry.';
    }
  };
  status.addEventListener('toggle', readOnOpen);
  readOnOpen();
})();
</script>
"""
