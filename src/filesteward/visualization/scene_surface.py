"""U1 scenery surfaces — header scenes, classification legend, next actions.

Presentation/orchestration helpers only. Legal intents remain owned by
``decision_flow.allowed_intents()``. Permanent deletion is never offered.

Success stacks:
  USER activate metric card
    -> MetricSceneEntry
    -> scenery panel OPEN_* scene
    -> explanation only (no disposition mutation)

  USER consult classification legend
    -> ClassificationLegendEntry
    -> quality tone + meaning (no color-only semantics)

  USER wants to classify / "delete"
    -> operator_next_actions(flow)
    -> KEEP / REVIEW_LATER / … or OPEN APPROVAL for reclaim
    -> APPROVE_QUARANTINE path ends STAGED / NO BYTES REMOVED
    -> never emits PERMANENT_DELETE

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
    "OperatorNextAction",
    "classification_legend",
    "metric_scene_entries",
    "operator_next_actions",
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


@dataclass(frozen=True)
class ClassificationLegendEntry:
    state_id: str
    label: str
    meaning: str
    quality_tone: QualityTone
    operable_hint: str


@dataclass(frozen=True)
class OperatorNextAction:
    action_id: str
    label: str
    explanation: str
    intent: DecisionIntent | None
    opens_approval: bool
    consequence: str


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
            explanation="Where pressure lives in this run — magnitude is not authority.",
        ),
        MetricSceneEntry(
            surface_id="metric_baseline_free_space",
            label="Run baseline free space",
            value=free_space,
            required_action="OPEN_FREE_SPACE_SCENE",
            scene="FREE_SPACE",
            explanation="Baseline free space for this evidence run.",
        ),
        MetricSceneEntry(
            surface_id="metric_projected_reclaim",
            label="Projected reclaim",
            value=reclaim_label,
            required_action="OPEN_RECLAIM_SCENE",
            scene="RECLAIM",
            explanation="Projected reclaim candidates — still needs legal approval.",
        ),
        MetricSceneEntry(
            surface_id="metric_target_free_space",
            label="Target free space",
            value=target_free_space,
            required_action="OPEN_TARGET_SCENE",
            scene="TARGET",
            explanation="Operator target free-space goal for this cleanup journey.",
        ),
        MetricSceneEntry(
            surface_id="metric_authorization_state",
            label="Authorization state",
            value=authorization,
            required_action="OPEN_AUTHORIZATION_SCENE",
            scene="AUTHORIZATION",
            explanation="Authorization is separate from evidence classification.",
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
            operable_hint="Open protection explanation",
        ),
        ClassificationLegendEntry(
            state_id="RECLAIM_CANDIDATE",
            label="RECLAIM CANDIDATE",
            meaning="Evidence supports reclaim candidacy. Still needs approval.",
            quality_tone=QualityTone.RECLAIM_CANDIDATE,
            operable_hint="Open approval or keep",
        ),
        ClassificationLegendEntry(
            state_id="KEEP_ESSENTIAL",
            label="KEEP / ESSENTIAL",
            meaning="Affirmative keep. Not a reclaim target.",
            quality_tone=QualityTone.ESSENTIAL,
            operable_hint="Inspect keep rationale",
        ),
        ClassificationLegendEntry(
            state_id="AMBIGUOUS_HUMAN_REVIEW",
            label="HUMAN REVIEW / UNKNOWN",
            meaning="Ambiguous — operator judgment or rescan required.",
            quality_tone=QualityTone.AMBIGUOUS,
            operable_hint="Open first unresolved gate",
        ),
        ClassificationLegendEntry(
            state_id="AUTHORIZATION_LOCKED",
            label="AUTHORIZATION",
            meaning="Approval / lock state. Separate from CleanupDisposition.",
            quality_tone=QualityTone.NEUTRAL,
            operable_hint="Open authorization scene",
        ),
    )


def scenery_subtitle(flow: DecisionFlowState, disposition: CleanupDisposition) -> str:
    tone = quality_tone_for_disposition(disposition)
    scene = flow.scene.value
    if flow.scene is DecisionScene.APPROVAL:
        return (
            f"{tone.value.replace('_', ' ')} · scene {scene} · "
            "delete intent opens approval → quarantine staging — NO BYTES REMOVED"
        )
    if flow.scene is DecisionScene.STAGED:
        return (
            f"{tone.value.replace('_', ' ')} · scene {scene} · "
            "QUARANTINE STAGED — permanent deletion is not implemented"
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
                    "is not available."
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
                        "Operator delete/remove intent opens exact-plan approval. "
                        "Terminal truth: quarantine staging — NO BYTES REMOVED. "
                        "Permanent deletion is not implemented."
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
    return tuple(actions)


def assert_no_permanent_delete_actions(actions: Sequence[OperatorNextAction]) -> None:
    for action in actions:
        blob = f"{action.action_id} {action.label} {action.explanation}".upper()
        if "PERMANENT" in blob and "NOT IMPLEMENTED" not in blob:
            raise AssertionError("permanent deletion must remain unavailable")
        if action.action_id in {"delete", "permanent_delete", "permanently_delete"}:
            raise AssertionError("delete action ids are forbidden")
