"""F2 HTML report assembly proofs."""

from __future__ import annotations

from pathlib import Path

from filesteward.models import (
    AuthorizationState,
    CleanupDisposition,
    ScanCompleteness,
)
from filesteward.visualization.contracts import (
    GateStep,
    GateStepStatus,
    PresentationModel,
    PresentationNode,
    ShellMetrics,
    TreemapRect,
)
from filesteward.visualization.html import render_report_html, write_report_html_atomically


def _model() -> PresentationModel:
    hostile = r'C:\Users\<profile>\x & "y" <script>alert(1)</script>'
    nodes = (
        PresentationNode(
            node_id="review",
            parent_id=None,
            display_name="Example Package Cache",
            path=hostile,
            entry_type="DIRECTORY",
            logical_size_bytes=49_000_000_000,
            allocated_size_bytes=49_000_000_000,
            projected_reclaim_bytes=None,
            reclaim_basis=None,
            projection_quality=None,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            authorization_state=AuthorizationState.UNAPPROVED,
            scan_completeness=ScanCompleteness.COMPLETE,
            protection_relation="UNRELATED",
            reason="no contract",
            contract_summary=None,
            contract_hint_tags=("cache",),
            risk_if_acted_on="risk",
            next_gate="contract decision",
            trace_evidence_source="fixture",
            item_count=10,
            gate_steps=(
                GateStep(
                    gate_id="contract",
                    name="Explicit regenerable contract",
                    status=GateStepStatus.WAITING,
                    explanation="No contract",
                    is_first_unresolved=True,
                ),
            ),
        ),
        PresentationNode(
            node_id="reclaim",
            parent_id=None,
            display_name="Contract Cache",
            path=r"C:\ProgramData\Example\Cache",
            entry_type="DIRECTORY",
            logical_size_bytes=9_600_000_000,
            allocated_size_bytes=9_600_000_000,
            projected_reclaim_bytes=8_900_000_000,
            reclaim_basis="contract",
            projection_quality="estimate-logical",
            disposition=CleanupDisposition.RECLAIM_PROVEN,
            authorization_state=AuthorizationState.UNAPPROVED,
            scan_completeness=ScanCompleteness.COMPLETE,
            protection_relation="UNRELATED",
            reason="structured evidence",
            contract_summary="example-contract-1",
            contract_hint_tags=(),
            risk_if_acted_on="still unapproved",
            next_gate="approval",
            trace_evidence_source="fixture",
            item_count=3,
            gate_steps=(
                GateStep(
                    gate_id="approval",
                    name="Operator approval",
                    status=GateStepStatus.WAITING,
                    explanation="UNAPPROVED",
                    is_first_unresolved=True,
                ),
            ),
        ),
    )
    return PresentationModel(
        run_id="f2-synthetic",
        nodes=nodes,
        metrics=ShellMetrics(
            observed_storage_label="58.6 GiB",
            free_space_label="32.8 GiB",
            projected_reclaim_label="8.9 GiB",
            projected_reclaim_quality="estimate-logical",
            target_free_space_label="80.0 GiB",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="review",
    )


def test_render_report_html_core_contract() -> None:
    html = render_report_html(_model())
    assert "--fs-bg-canvas:" in html
    assert "@media (prefers-color-scheme: dark)" in html
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "@media (forced-colors: active)" in html
    assert ":focus-visible" in html
    assert "max-width:1179px" in html
    assert "max-width:799px" in html
    assert "filter-chip" in html
    assert 'placeholder="Search paths and groups"' in html
    assert "Logical size" in html
    assert "Projected reclaim" in html
    assert "UNAPPROVED" in html
    assert "&lt;profile&gt;" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "http://" not in html and "https://" not in html
    assert "apply</button>" not in html.lower()
    assert "delete</button>" not in html.lower()


def test_rects_and_atomic_write(tmp_path: Path) -> None:
    model = _model()
    html = render_report_html(
        model,
        (
            TreemapRect(node_id="review", x=0, y=0, width=60, height=100),
            TreemapRect(node_id="reclaim", x=60, y=0, width=40, height=100),
        ),
        selected_id="reclaim",
    )
    assert "state-edge-state-reclaim" in html
    assert "Contract Cache" in html
    out = tmp_path / "report.html"
    write_report_html_atomically(out, html)
    assert out.is_file()
    assert "UNAPPROVED" in out.read_text(encoding="utf-8")
    leftovers = list(tmp_path.glob(".report.html.*.tmp"))
    assert leftovers == []


def test_filter_and_search_controls_are_wired() -> None:
    html = render_report_html(_model())
    assert "const applyFilters" in html
    assert "data-filter" in html
    assert 'aria-pressed="true"' in html
    assert 'aria-pressed="false"' in html
    assert "search.addEventListener('input'" in html
    assert "meta.disposition === activeFilter" in html
    assert "meta.search.includes(query)" in html
    assert "No items match these filters." in html


def test_empty_filter_clears_stale_selection_class() -> None:
    html = render_report_html(_model())
    assert "classList.remove('selected')" in html
    assert ".nav-row.selected, .map-node.selected" in html
    assert "selection-summary" in html
    assert "No items match these filters." in html
    assert "mapWrap.classList.remove('selection-active')" in html


def test_search_uses_locale_independent_lowercase() -> None:
    html = render_report_html(_model())
    assert "toLowerCase()" in html
    assert "toLocaleLowerCase()" not in html


def test_filter_payload_escapes_markup_like_receipt_text() -> None:
    html = render_report_html(_model())
    # Dynamic filter/search metadata must not create executable markup.
    assert r"\u003cscript\u003ealert(1)\u003c/script\u003e" in html
    assert html.count("<script>alert(1)</script>") == 0
