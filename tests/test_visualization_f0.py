"""F0 visual-system seam prototypes: tokens, literal rendering, selection, shell."""

from __future__ import annotations

import re

import pytest

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
from filesteward.visualization.css import render_token_css
from filesteward.visualization.literal import escape_text
from filesteward.visualization.selection import SelectionController
from filesteward.visualization.shell import render_report_shell
from filesteward.visualization.tokens import disposition_css_stem, load_tokens


def _node(
    *,
    node_id: str,
    name: str,
    path: str,
    disposition: CleanupDisposition,
    logical: int,
    auth: AuthorizationState = AuthorizationState.UNAPPROVED,
    projected: int | None = None,
    quality: str | None = None,
    steps: tuple[GateStep, ...] = (),
    hints: tuple[str, ...] = (),
) -> PresentationNode:
    return PresentationNode(
        node_id=node_id,
        parent_id=None,
        display_name=name,
        path=path,
        entry_type="DIRECTORY",
        logical_size_bytes=logical,
        allocated_size_bytes=logical,
        projected_reclaim_bytes=projected,
        reclaim_basis="synthetic" if projected is not None else None,
        projection_quality=quality,
        disposition=disposition,
        authorization_state=auth,
        scan_completeness=ScanCompleteness.COMPLETE,
        protection_relation="UNRELATED",
        reason="synthetic fixture",
        contract_summary=None,
        contract_hint_tags=hints,
        risk_if_acted_on="synthetic risk text",
        next_gate="operator judgment",
        trace_evidence_source="fixture",
        item_count=12,
        gate_steps=steps,
    )


def _synthetic_model() -> PresentationModel:
    hostile = (
        r"C:\Users\<profile>\AppData\Local\Example & \"Cache\" <script>alert(1)</script>"
    )
    review_steps = (
        GateStep(
            gate_id="protection",
            name="Protected overlap",
            status=GateStepStatus.PASS,
            explanation="None observed",
        ),
        GateStep(
            gate_id="contract",
            name="Explicit regenerable contract",
            status=GateStepStatus.WAITING,
            explanation="No contract covers this prefix.",
            is_first_unresolved=True,
        ),
    )
    reclaim_steps = (
        GateStep(
            gate_id="evidence",
            name="Evidence disposition",
            status=GateStepStatus.PASS,
            explanation="RECLAIM_PROVEN",
        ),
        GateStep(
            gate_id="approval",
            name="Operator approval bound to run/manifest/rows",
            status=GateStepStatus.WAITING,
            explanation="Authorization remains UNAPPROVED.",
            is_first_unresolved=True,
        ),
    )
    nodes = (
        _node(
            node_id="review",
            name="Example Package Cache",
            path=hostile,
            disposition=CleanupDisposition.HUMAN_REVIEW,
            logical=49_000_000_000,
            steps=review_steps,
            hints=("cache",),
        ),
        _node(
            node_id="protected",
            name="Protected Repository",
            path=r"C:\Users\<profile>\dev\protected-project",
            disposition=CleanupDisposition.PROTECTED,
            logical=12_000_000_000,
        ),
        _node(
            node_id="unknown",
            name="Unreadable Subtree",
            path=r"C:\ExampleRestricted",
            disposition=CleanupDisposition.UNKNOWN,
            logical=7_500_000_000,
        ),
        _node(
            node_id="reclaim",
            name="Contract-backed Example Cache",
            path=r"C:\ProgramData\ExampleTool\RegenerableCache",
            disposition=CleanupDisposition.RECLAIM_PROVEN,
            logical=9_600_000_000,
            projected=8_900_000_000,
            quality="estimate-logical",
            steps=reclaim_steps,
        ),
        _node(
            node_id="keep",
            name="Retained Example",
            path=r"C:\ProgramData\ExampleTool\RequiredData",
            disposition=CleanupDisposition.KEEP_PROVEN,
            logical=4_200_000_000,
        ),
    )
    return PresentationModel(
        run_id="synthetic-visual-f0",
        nodes=nodes,
        metrics=ShellMetrics(
            observed_storage_label="81.2 GiB",
            free_space_label="32.8 GiB",
            projected_reclaim_label="8.9 GiB",
            projected_reclaim_quality="estimate-logical",
            target_free_space_label="80.0 GiB",
            authorization_label="UNAPPROVED",
        ),
        default_selected_id="review",
    )


class TestTokenSeam:
    def test_load_tokens_has_light_and_dark(self) -> None:
        tokens = load_tokens()
        assert tokens["contract_id"] == "storage-reclaim-visual-system"
        assert "bg-canvas" in tokens["themes"]["light"]
        assert "bg-canvas" in tokens["themes"]["dark"]
        assert tokens["themes"]["dark"]["bg-canvas"] != "#000000"

    def test_disposition_map_covers_cleanup_disposition(self) -> None:
        for disposition in CleanupDisposition:
            stem = disposition_css_stem(disposition)
            assert stem.startswith("state-")

    def test_unknown_disposition_fails_closed(self) -> None:
        with pytest.raises(ValueError, match="no visual token"):
            disposition_css_stem("NOT_A_STATE")

    def test_render_token_css_includes_dark_and_reduced_motion(self) -> None:
        css = render_token_css()
        assert "--fs-bg-canvas:" in css
        assert "@media (prefers-color-scheme: dark)" in css
        assert "@media (prefers-reduced-motion: reduce)" in css
        assert "@media (forced-colors: active)" in css
        assert "--fs-focus:" in css


class TestLiteralSeam:
    def test_hostile_path_escapes_literally(self) -> None:
        raw = r'C:\Users\<profile>\x & "y" <script>alert(1)</script>'
        escaped = escape_text(raw)
        assert "<script>" not in escaped
        assert "&lt;profile&gt;" in escaped
        assert "&amp;" in escaped
        assert "&quot;" in escaped
        assert "&lt;script&gt;" in escaped


class TestSelectionSeam:
    def test_select_and_filter_rebind(self) -> None:
        model = _synthetic_model()
        ctl = SelectionController(model)
        assert ctl.state.selected_id == "review"
        ctl.select("reclaim")
        assert ctl.selected_node() is not None
        assert ctl.selected_node().disposition is CleanupDisposition.RECLAIM_PROVEN
        assert (
            ctl.selected_node().authorization_state is AuthorizationState.UNAPPROVED
        )
        ctl.set_disposition_filter(CleanupDisposition.PROTECTED)
        assert ctl.state.selected_id == "protected"
        ctl.set_disposition_filter(CleanupDisposition.HUMAN_REVIEW)
        assert ctl.state.selected_id == "review"

    def test_unknown_selection_fails(self) -> None:
        ctl = SelectionController(_synthetic_model())
        with pytest.raises(KeyError):
            ctl.select("missing")


class TestShellSeam:
    def test_shell_call_stack_emits_modern_report(self) -> None:
        model = _synthetic_model()
        html = render_report_shell(model)
        assert "Segoe UI Variable" in html or "--fs-font-sans" in html
        assert "Logical size" in html
        assert "Allocated size" in html
        assert "Projected reclaim" in html
        assert "UNAPPROVED" in html
        assert "RECLAIM PROVEN" in html or "RECLAIM_PROVEN" in html.replace(" ", "_")
        assert "Authorization remains UNAPPROVED" in html or "UNAPPROVED" in html
        assert "estimate-logical" in html
        assert "&lt;profile&gt;" in html
        assert "&lt;script&gt;" in html
        assert "<script>alert(1)</script>" not in html
        assert 'type="button"' in html
        assert re.search(r"apply</button>", html, re.I) is None
        assert re.search(r"delete</button>", html, re.I) is None
        assert "unresolved" in html
        assert 'data-run-id="synthetic-visual-f0"' in html

    def test_reclaim_proven_remains_unapproved_in_shell(self) -> None:
        model = _synthetic_model()
        html = render_report_shell(model, selected_id="reclaim")
        assert "Contract-backed Example Cache" in html
        assert "UNAPPROVED" in html
        assert "No apply control exists" in html

    def test_optional_rects_paint_without_inferring_state(self) -> None:
        model = _synthetic_model()
        rects = (
            TreemapRect(node_id="review", x=0, y=0, width=50, height=100),
            TreemapRect(node_id="reclaim", x=50, y=0, width=50, height=100),
        )
        html = render_report_shell(model, rects=rects, selected_id="reclaim")
        assert 'data-node-id="reclaim"' in html
        assert "state-edge-state-reclaim" in html
        assert "Map container ready" not in html
        assert 'class="map-placeholder"' not in html

    def test_empty_model_rejected(self) -> None:
        with pytest.raises(ValueError, match="no nodes"):
            PresentationModel(
                run_id="x",
                nodes=(),
                metrics=ShellMetrics(
                    observed_storage_label="0",
                    free_space_label="0",
                    projected_reclaim_label="0",
                    projected_reclaim_quality=None,
                    target_free_space_label="0",
                    authorization_label="UNAPPROVED",
                ),
            )
