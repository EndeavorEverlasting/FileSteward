"""U1 scenery surfaces — header scenes, classification legend, next actions.

Presentation/orchestration helpers only. Legal intents remain owned by
``decision_flow.allowed_intents()``. Permanent deletion is available through
the repository-owned deletion package, not through quarantine approval.

Success stacks:
  USER activate metric card
    -> MetricSceneEntry
    -> cinematic dashboard (readable title + consequence)
    -> navigator filter / Atlas home / Decision chamber as declared
    -> no disposition mutation from the metric itself

  USER activate classification legend
    -> ClassificationLegendEntry
    -> filter_target / legend_action
    -> navigator subset + Atlas focus of first match
    -> AUTHORIZATION opens auth dashboard (not a disposition filter)

  USER wants to classify / "delete"
    -> operator_next_actions(flow)
    -> KEEP / REVIEW_LATER / … or OPEN APPROVAL for reclaim
    -> APPROVE_QUARANTINE path ends STAGED / NO BYTES REMOVED
    -> DELETE_PERMANENTLY uses the deletion-package path when eligible

Failure:
  PROTECTED / no allowed intents
    -> locked explanation action only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from filesteward.models import CleanupDisposition
from filesteward.visualization.decision_flow import (
    DecisionFlowState,
    DecisionIntent,
    DecisionScene,
    allowed_intents,
)
from filesteward.visualization.interaction import QualityTone, quality_tone_for_disposition

__all__ = [
    "ClassificationLegendEntry",
    "MetricSceneEntry",
    "ModeBrief",
    "OperatorNextAction",
    "PaneSceneEntry",
    "PathStepPreview",
    "assert_noneligible_cannot_delete",
    "canonical_scene_impacts",
    "classification_legend",
    "evidence_gap_mode_brief",
    "footer_ticker_items",
    "metric_scene_entries",
    "operator_next_actions",
    "pane_scene_entries",
    "path_step_previews",
    "scenery_subtitle",
]


@dataclass(frozen=True)
class MetricSceneEntry:
    surface_id: str
    label: str
    value: str
    required_action: str
    scene: str
    explanation: str
    dashboard_title: str
    filter_target: str | None = None
    opens_decision: bool = False


@dataclass(frozen=True)
class ClassificationLegendEntry:
    state_id: str
    label: str
    meaning: str
    quality_tone: QualityTone
    operable_hint: str
    filter_target: str | tuple[str, ...] | None = None
    legend_action: str = "FILTER_AND_FOCUS"


@dataclass(frozen=True)
class OperatorNextAction:
    action_id: str
    label: str
    explanation: str
    intent: DecisionIntent | None
    opens_approval: bool
    consequence: str


@dataclass(frozen=True)
class PathStepPreview:
    step_id: str
    title: str
    summary: str
    cue_label: str
    explanation: str
    cursor_mode: str
    consequence: str
    prerequisites: str


@dataclass(frozen=True)
class PaneSceneEntry:
    surface_id: str
    label: str
    scene: str
    required_action: str
    explanation: str


@dataclass(frozen=True)
class ModeBrief:
    mode_id: str
    title: str
    rules: tuple[str, ...]
    assumptions: tuple[str, ...]
    choices: tuple[str, ...]


def path_step_previews() -> tuple[PathStepPreview, ...]:
    """Decision Path step hover/focus previews — PATH_PREVIEW contract."""

    return (
        PathStepPreview(
            step_id="MAP",
            title="MAP",
            summary="Find where space lives",
            cue_label="PREVIEW MAP",
            explanation="Locate pressure sectors. Magnitude is visible; no reclaim authority yet.",
            cursor_mode="explore",
            consequence="READ_ONLY",
            prerequisites="Open the atlas overview or search.",
        ),
        PathStepPreview(
            step_id="FOCUS",
            title="FOCUS",
            summary="Magnify exact evidence",
            cue_label="PREVIEW FOCUS",
            explanation="Dive to one evidence group. Selection stays anchored while the camera moves.",
            cursor_mode="focus",
            consequence="READ_ONLY",
            prerequisites="Choose a sector/card or Fit selected.",
        ),
        PathStepPreview(
            step_id="GATE",
            title="GATE",
            summary="Open the first unresolved gate",
            cue_label="PREVIEW GATE",
            explanation="Open the first unresolved evidence gate. UNKNOWN/HUMAN_REVIEW become action surfaces.",
            cursor_mode="resolve",
            consequence="READ_ONLY",
            prerequisites="Focused evidence with an unresolved gate.",
        ),
        PathStepPreview(
            step_id="RESOLVE",
            title="RESOLVE",
            summary="Choose only legal operator intents",
            cue_label="PREVIEW RESOLVE",
            explanation="Only intents from decision_flow.allowed_intents() are legal. Illegal choices stay locked.",
            cursor_mode="resolve",
            consequence="RECORD_INTENT",
            prerequisites="An open gate with legal intents.",
        ),
        PathStepPreview(
            step_id="APPROVAL",
            title="APPROVAL",
            summary="Authorize exact quarantine scope",
            cue_label="PREVIEW APPROVAL",
            explanation="Exact run, plan digest, and item IDs required. This is authorization, not deletion.",
            cursor_mode="approve",
            consequence="WRITE_APPROVAL",
            prerequisites="RECLAIM_PROVEN + UNAPPROVED evidence.",
        ),
        PathStepPreview(
            step_id="STAGED",
            title="STAGED",
            summary="NO BYTES REMOVED",
            cue_label="PREVIEW STAGED",
            explanation=(
                "Quarantine staged, NO BYTES REMOVED. Permanent delete uses a "
                "separate DELETE PERMANENTLY path when eligible."
            ),
            cursor_mode="approve",
            consequence="STAGE_QUARANTINE",
            prerequisites="Validated APPROVED_FOR_ACTION receipt.",
        ),
    )


def pane_scene_entries() -> tuple[PaneSceneEntry, ...]:
    return (
        PaneSceneEntry(
            surface_id="pane_navigator",
            label="Storage navigator",
            scene="NAVIGATOR",
            required_action="OPEN_NAVIGATOR_SCENE",
            explanation="Browse evidence rows. Enter/Space selects; classification tags open decision gates.",
        ),
        PaneSceneEntry(
            surface_id="pane_atlas",
            label="Storage atlas",
            scene="ATLAS",
            required_action="OPEN_ATLAS_SCENE",
            explanation="Spatial pressure map. Dive sectors, use camera HUD, or open Decision Path steps.",
        ),
        PaneSceneEntry(
            surface_id="pane_inspector",
            label="Decision inspector",
            scene="INSPECTOR",
            required_action="OPEN_INSPECTOR_SCENE",
            explanation="Gate trace and rationale for the selected evidence. Not a delete console.",
        ),
    )


def evidence_gap_mode_brief() -> ModeBrief:
    return ModeBrief(
        mode_id="EVIDENCE_GAP",
        title="? items mode — evidence completeness gap",
        rules=(
            "This status means item count or scan completeness is incomplete.",
            "It is not the same as CleanupDisposition.UNKNOWN unless disposition also says UNKNOWN.",
            "Color alone is never authority; the orb label and Next actions carry the rule.",
        ),
        assumptions=(
            "Observation may be partial; reclaim math stays estimate-grade until complete.",
            "Protected evidence still blocks reclaim even if counts are incomplete.",
        ),
        choices=(
            "If the gate allows RESCAN — use Next actions / Decision to rescan.",
            "KEEP or REVIEW LATER remain legal when decision_flow allows them.",
            "STAGE REMOVAL PATH appears only for RECLAIM_PROVEN + UNAPPROVED — not from ? items alone.",
        ),
    )


def footer_ticker_items(
    *,
    authorization: str,
    disposition_label: str | None,
    scene_hint: str,
) -> tuple[str, ...]:
    items = [
        f"AUTH {authorization}",
        f"SCENE {scene_hint}",
        "QUARANTINE STAGING ≠ PERMANENT DELETE",
        "Brand title / Home key → Atlas Home",
        "Decision Path steps preview consequence before commit",
        "Legend states ≠ mutation authority",
    ]
    if disposition_label:
        items.insert(0, f"SELECTED {disposition_label}")
    return tuple(items)


def metric_scene_entries(
    *,
    observed_storage: str,
    free_space: str,
    projected_reclaim: str,
    projected_reclaim_quality: str | None,
    target_free_space: str,
    authorization: str,
) -> tuple[MetricSceneEntry, ...]:
    reclaim_label = projected_reclaim
    if projected_reclaim_quality:
        reclaim_label = f"{projected_reclaim} · {projected_reclaim_quality}"
    return (
        MetricSceneEntry(
            surface_id="metric_observed_storage",
            label="Observed storage",
            value=observed_storage,
            required_action="OPEN_STORAGE_SCENE",
            scene="STORAGE_PRESSURE",
            dashboard_title="Storage pressure",
            explanation=(
                "Atlas overview of where observed storage pressure lives in this run. "
                "Magnitude is visible; it is not reclaim authority."
            ),
            filter_target="ALL",
        ),
        MetricSceneEntry(
            surface_id="metric_baseline_free_space",
            label="Run baseline free space",
            value=free_space,
            required_action="OPEN_FREE_SPACE_SCENE",
            scene="FREE_SPACE",
            dashboard_title="Free space baseline",
            explanation=(
                "Run baseline free space for this evidence set. "
                "Use Atlas Home to re-orient before chasing reclaim candidates."
            ),
            filter_target=None,
        ),
        MetricSceneEntry(
            surface_id="metric_projected_reclaim",
            label="Projected reclaim",
            value=reclaim_label,
            required_action="OPEN_RECLAIM_SCENE",
            scene="RECLAIM",
            dashboard_title="Reclaim candidates",
            explanation=(
                "Projected reclaim candidates with affirmative evidence. "
                "Still needs legal operator approval before quarantine staging — "
                "NO BYTES REMOVED."
            ),
            filter_target="RECLAIM_PROVEN",
            opens_decision=True,
        ),
        MetricSceneEntry(
            surface_id="metric_target_free_space",
            label="Target free space",
            value=target_free_space,
            required_action="OPEN_TARGET_SCENE",
            scene="TARGET",
            dashboard_title="Target free space",
            explanation=(
                "Operator target free-space goal for this cleanup journey. "
                "Keeps the current evidence context; does not invent reclaim authority."
            ),
            filter_target=None,
        ),
        MetricSceneEntry(
            surface_id="metric_authorization_state",
            label="Authorization state",
            value=authorization,
            required_action="OPEN_AUTHORIZATION_SCENE",
            scene="AUTHORIZATION",
            dashboard_title="Authorization",
            explanation=(
                "Authorization is separate from CleanupDisposition classification. "
                "UNAPPROVED means no operator approval artifact yet — not a reclaim "
                "permission and not a disposition. When a reclaim candidate is available, "
                "open Decision toward the approval / quarantine staging path."
            ),
            filter_target=None,
            opens_decision=True,
        ),
    )


def classification_legend() -> tuple[ClassificationLegendEntry, ...]:
    """Persistent legend — contracted classification states, not status orbs alone."""

    return (
        ClassificationLegendEntry(
            state_id="PROTECTED_BLOCKED",
            label="PROTECTED",
            meaning="Blocked from reclaim. Inspect why; cannot promote to reclaim here.",
            quality_tone=QualityTone.BLOCKED,
            operable_hint="Filter to PROTECTED evidence and focus the first match",
            filter_target="PROTECTED",
            legend_action="FILTER_AND_FOCUS",
        ),
        ClassificationLegendEntry(
            state_id="RECLAIM_CANDIDATE",
            label="RECLAIM CANDIDATE",
            meaning="Evidence supports reclaim candidacy. Still needs approval.",
            quality_tone=QualityTone.RECLAIM_CANDIDATE,
            operable_hint="Filter to RECLAIM_PROVEN evidence and focus the first match",
            filter_target="RECLAIM_PROVEN",
            legend_action="FILTER_AND_FOCUS",
        ),
        ClassificationLegendEntry(
            state_id="KEEP_ESSENTIAL",
            label="KEEP / ESSENTIAL",
            meaning="Affirmative keep. Not a reclaim target.",
            quality_tone=QualityTone.ESSENTIAL,
            operable_hint="Filter to KEEP_PROVEN evidence and focus the first match",
            filter_target="KEEP_PROVEN",
            legend_action="FILTER_AND_FOCUS",
        ),
        ClassificationLegendEntry(
            state_id="AMBIGUOUS_HUMAN_REVIEW",
            label="HUMAN REVIEW / UNKNOWN",
            meaning="Ambiguous — operator judgment or rescan required.",
            quality_tone=QualityTone.AMBIGUOUS,
            operable_hint="Filter to HUMAN_REVIEW and UNKNOWN evidence; focus the first match",
            filter_target="AMBIGUOUS",
            legend_action="FILTER_AND_FOCUS",
        ),
        ClassificationLegendEntry(
            state_id="AUTHORIZATION_LOCKED",
            label="AUTHORIZATION",
            meaning="Approval / lock state. Separate from CleanupDisposition.",
            quality_tone=QualityTone.NEUTRAL,
            operable_hint="Open authorization dashboard (not a disposition filter)",
            filter_target=None,
            legend_action="OPEN_AUTHORIZATION",
        ),
    )


def scenery_subtitle(flow: DecisionFlowState, disposition: CleanupDisposition) -> str:
    tone = quality_tone_for_disposition(disposition)
    scene = flow.scene.value
    if flow.scene is DecisionScene.APPROVAL:
        return (
            f"{tone.value.replace('_', ' ')} · scene {scene} · "
            "quarantine approval or DELETE PERMANENTLY for eligible reclaim — "
            "quarantine stages with NO BYTES REMOVED"
        )
    if flow.scene is DecisionScene.STAGED:
        return (
            f"{tone.value.replace('_', ' ')} · scene {scene} · "
            "quarantine staged, NO BYTES REMOVED; permanent delete is a separate path"
        )
    if not allowed_intents(flow):
        return (
            f"{tone.value.replace('_', ' ')} · scene {scene} · "
            "no legal classification change from this evidence state"
        )
    return (
        f"{tone.value.replace('_', ' ')} · scene {scene} · "
        "use Next actions for legal classify / stage-removal choices"
    )


def operator_next_actions(flow: DecisionFlowState) -> tuple[OperatorNextAction, ...]:
    """Terminal-user-value actions for classify / stage-removal comprehension."""

    intents = allowed_intents(flow)
    if not intents:
        return (
            OperatorNextAction(
                action_id="why_locked",
                label="WHY LOCKED",
                explanation=(
                    "No legal operator intents from this evidence/authorization state. "
                    "Classification cannot be force-changed here; permanent deletion "
                    "stays unavailable for this evidence."
                ),
                intent=None,
                opens_approval=False,
                consequence="READ_ONLY",
            ),
        )

    actions: list[OperatorNextAction] = []
    for intent in intents:
        if intent is DecisionIntent.APPROVE_QUARANTINE:
            actions.append(
                OperatorNextAction(
                    action_id="open_approval",
                    label="STAGE REMOVAL PATH",
                    explanation=(
                        "Operator quarantine intent opens exact-plan approval. "
                        "Terminal truth: quarantine staged — NO BYTES REMOVED. "
                        "Permanent delete uses a separate DELETE PERMANENTLY path."
                    ),
                    intent=intent,
                    opens_approval=True,
                    consequence="WRITE_APPROVAL",
                )
            )
            continue
        if intent is DecisionIntent.KEEP:
            actions.append(
                OperatorNextAction(
                    action_id="keep",
                    label="KEEP",
                    explanation="Record keep intent. Does not reclaim or remove bytes.",
                    intent=intent,
                    opens_approval=False,
                    consequence="RECORD_INTENT",
                )
            )
            continue
        if intent is DecisionIntent.REVIEW_LATER:
            actions.append(
                OperatorNextAction(
                    action_id="review_later",
                    label="REVIEW LATER",
                    explanation="Leave ambiguous; return without promoting reclaim.",
                    intent=intent,
                    opens_approval=False,
                    consequence="RECORD_INTENT",
                )
            )
            continue
        if intent is DecisionIntent.RESCAN:
            actions.append(
                OperatorNextAction(
                    action_id="rescan",
                    label="RESCAN",
                    explanation="Evidence incomplete — rescan before classification change.",
                    intent=intent,
                    opens_approval=False,
                    consequence="RECORD_INTENT",
                )
            )
            continue
        if intent is DecisionIntent.DECLARE_REGENERABLE_CONTRACT:
            actions.append(
                OperatorNextAction(
                    action_id="declare_contract",
                    label="DECLARE REGENERABLE",
                    explanation="Human-review path: declare regenerable contract evidence.",
                    intent=intent,
                    opens_approval=False,
                    consequence="RECORD_INTENT",
                )
            )
            continue
        if intent is DecisionIntent.DELETE_PERMANENTLY:
            actions.append(
                OperatorNextAction(
                    action_id="delete_permanently",
                    label="DELETE PERMANENTLY",
                    explanation=(
                        "One deliberate DELETE PERMANENTLY commit for the exact "
                        "eligible RECLAIM_PROVEN set. Uses deletion-package approval, "
                        "fresh preflight, executor, and receipt — not quarantine."
                    ),
                    intent=intent,
                    opens_approval=False,
                    consequence="DELETE_PERMANENTLY",
                )
            )

    # Always surface delete/remove intent fate — never silent absence (ncdu/BleachBit confirm pattern).
    if (
        DecisionIntent.APPROVE_QUARANTINE not in intents
        and DecisionIntent.DELETE_PERMANENTLY not in intents
    ):
        disp = flow.disposition.value.replace("_", " ")
        actions.append(
            OperatorNextAction(
                action_id="stage_removal_locked",
                label="STAGE REMOVAL PATH — LOCKED",
                explanation=(
                    f"Delete/remove intent is blocked for {disp}. "
                    "Quarantine staging requires RECLAIM_PROVEN + UNAPPROVED → APPROVAL. "
                    "UNKNOWN/HUMAN_REVIEW stay on RESCAN / KEEP / REVIEW LATER. "
                    "Permanent deletion requires RECLAIM_PROVEN and the DELETE PERMANENTLY path."
                ),
                intent=None,
                opens_approval=False,
                consequence="READ_ONLY",
            )
        )
    return tuple(actions)


def _is_executable_delete_action(action: OperatorNextAction) -> bool:
    if action.intent is DecisionIntent.DELETE_PERMANENTLY:
        return True
    if action.action_id in {
        "delete_permanently",
        "delete",
        "permanent_delete",
        "permanently_delete",
    }:
        return action.consequence != "READ_ONLY"
    return False


def assert_noneligible_cannot_delete(
    actions: Sequence[OperatorNextAction],
    flow: DecisionFlowState,
) -> None:
    if flow.disposition not in {
        CleanupDisposition.UNKNOWN,
        CleanupDisposition.HUMAN_REVIEW,
        CleanupDisposition.PROTECTED,
        CleanupDisposition.KEEP_PROVEN,
    }:
        return
    for action in actions:
        if _is_executable_delete_action(action):
            raise AssertionError(
                "UNKNOWN/HUMAN_REVIEW/PROTECTED/KEEP flows cannot execute delete"
            )


def canonical_scene_impacts() -> tuple[dict[str, object], ...]:
    """Declare each canonical scene's impact and continuation policy."""

    return (
        {
            "scene_id": "MAP",
            "purpose": "Locate storage pressure without granting reclaim authority.",
            "primary_impact": "ORIENT",
            "entry_context": "Atlas overview or search landing.",
            "operable_actions": ("SELECT", "FOCUS", "DIVE_IN", "PULL_BACK", "LOCATE"),
            "success_evidence": "A selected evidence node is focused.",
            "continuation_policy": "Advance focused evidence into FOCUS then GATE/RESOLVE.",
        },
        {
            "scene_id": "FOCUS",
            "purpose": "Magnify exact evidence while preserving the selected anchor.",
            "primary_impact": "CLASSIFY",
            "entry_context": "A selected presentation node.",
            "operable_actions": ("FOCUS", "OPEN_GATE"),
            "success_evidence": "Inspector and chamber agree on the selected node.",
            "continuation_policy": "Open the first unresolved gate or legal intent surface.",
        },
        {
            "scene_id": "GATE",
            "purpose": "Surface the first unresolved evidence gate.",
            "primary_impact": "CLASSIFY",
            "entry_context": "Focused evidence with an unresolved gate.",
            "operable_actions": ("RESCAN", "KEEP", "REVIEW_LATER", "DECLARE_REGENERABLE_CONTRACT"),
            "success_evidence": "Active gate id is explicit and legal intents are listed.",
            "continuation_policy": "Commit a legal intent, then advance from authoritative readback.",
        },
        {
            "scene_id": "RESOLVE",
            "purpose": "Choose only legal operator intents for the open gate.",
            "primary_impact": "DECIDE",
            "entry_context": "An open gate with allowed_intents().",
            "operable_actions": ("RESCAN", "KEEP", "REVIEW_LATER", "DECLARE_REGENERABLE_CONTRACT"),
            "success_evidence": "Persisted operator decision and a derived next scene/item.",
            "continuation_policy": "Do not reopen the same unresolved scene after KEEP/REVIEW_LATER.",
        },
        {
            "scene_id": "APPROVAL",
            "purpose": "Authorize exact quarantine or eligible permanent-delete scope.",
            "primary_impact": "AUTHORIZE",
            "entry_context": "RECLAIM_PROVEN + UNAPPROVED evidence.",
            "operable_actions": ("APPROVE_QUARANTINE", "DELETE_PERMANENTLY", "KEEP", "REVIEW_LATER"),
            "success_evidence": "Exact-plan approval or deletion-package approval artifact.",
            "continuation_policy": "Quarantine continues to STAGED; delete continues to RESULT.",
        },
        {
            "scene_id": "STAGED",
            "purpose": "Show quarantine staging with no bytes removed.",
            "primary_impact": "AUTHORIZE",
            "entry_context": "Validated QUARANTINE APPROVED_FOR_ACTION receipt.",
            "operable_actions": ("INSPECT_STAGED",),
            "success_evidence": "STAGED copy states NO BYTES REMOVED.",
            "continuation_policy": "Permanent delete remains a separate DELETE PERMANENTLY path when eligible.",
        },
        {
            "scene_id": "RESULT",
            "purpose": "Surface deletion receipt counts and reclaim verification.",
            "primary_impact": "VERIFY",
            "entry_context": "Completed DELETE PERMANENTLY executor readback.",
            "operable_actions": ("REVIEW_RECEIPT",),
            "success_evidence": "attempted/succeeded/failed/skipped plus reclaim fields.",
            "continuation_policy": "Continue to residual eligible items or CLOSED.",
        },
        {
            "scene_id": "CLOSED",
            "purpose": "Terminal keep/protected/completed item is off the reclaim journey.",
            "primary_impact": "DECIDE",
            "entry_context": "KEEP, REVIEW_LATER, PROTECTED, KEEP_PROVEN, or finished authorization.",
            "operable_actions": (),
            "success_evidence": "Item is not reopened as GATE/RESOLVE.",
            "continuation_policy": "Advance to the next actionable item when one remains.",
        },
    )
