"""Atlas Interaction Grammar — presentation-only cue projection.

Projects camera / selection / decision_flow facts into one typed vocabulary
consumed by reticle, cartouche, status orbs, and action traces.

This module NEVER grants authority. Legal decision choices remain owned by
``decision_flow.allowed_intents()``. Evidence disposition and authorization
remain owned by classification and approval receipts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import Enum
from typing import Mapping, Protocol

from filesteward.models import AuthorizationState, CleanupDisposition, ScanCompleteness
from filesteward.visualization.decision_flow import (
    DecisionFlowState,
    DecisionIntent,
    allowed_intents,
)

__all__ = [
    "Availability",
    "Consequence",
    "ImpactKind",
    "InteractionCue",
    "InteractionVerb",
    "context_fingerprint",
    "QualityTone",
    "Recency",
    "StatusOrbKind",
    "TargetKind",
    "cue_for_camera_command",
    "cue_for_intent",
    "cue_for_map_node",
    "cue_for_navigation",
    "cue_for_status_orb",
    "html_data_attrs",
]


class TargetKind(str, Enum):
    EVIDENCE = "EVIDENCE"
    STATUS = "STATUS"
    GATE = "GATE"
    INTENT = "INTENT"
    NAVIGATION = "NAVIGATION"
    AUTHORIZATION = "AUTHORIZATION"


class InteractionVerb(str, Enum):
    EXPLORE = "EXPLORE"
    FOCUS = "FOCUS"
    FRAME = "FRAME"
    RESOLVE = "RESOLVE"
    APPROVE = "APPROVE"
    EXPLAIN = "EXPLAIN"
    RETURN = "RETURN"
    DIVE_IN = "DIVE_IN"
    PULL_BACK = "PULL_BACK"
    LOCATE = "LOCATE"
    INSPECT_BLOCK = "INSPECT_BLOCK"
    WHY_LOCKED = "WHY_LOCKED"
    RESCAN = "RESCAN"
    LOCKED = "LOCKED"


class Availability(str, Enum):
    OPERABLE = "OPERABLE"
    BLOCKED = "BLOCKED"
    INFORMATIONAL = "INFORMATIONAL"
    UNAVAILABLE = "UNAVAILABLE"


class Recency(str, Enum):
    CURRENT = "CURRENT"
    LAST = "LAST"
    RECENT = "RECENT"
    IDLE = "IDLE"


class Consequence(str, Enum):
    READ_ONLY = "READ_ONLY"
    RECORD_INTENT = "RECORD_INTENT"
    WRITE_APPROVAL = "WRITE_APPROVAL"
    STAGE_QUARANTINE = "STAGE_QUARANTINE"
    DELETE_PERMANENTLY = "DELETE_PERMANENTLY"


class ImpactKind(str, Enum):
    ORIENT = "ORIENT"
    FILTER = "FILTER"
    CLASSIFY = "CLASSIFY"
    DECIDE = "DECIDE"
    AUTHORIZE = "AUTHORIZE"
    RECLAIM = "RECLAIM"
    VERIFY = "VERIFY"
    EXPLORE = "EXPLORE"


class QualityTone(str, Enum):
    """Visual quality polarity for sacred/essential vs reclaim/junk candidates.

    Presentation only. Never promotes disposition or invents reclaim authority.
    """

    ESSENTIAL = "ESSENTIAL"
    RECLAIM_CANDIDATE = "RECLAIM_CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"
    BLOCKED = "BLOCKED"
    NEUTRAL = "NEUTRAL"


class StatusOrbKind(str, Enum):
    PROTECTED = "PROTECTED"
    UNAPPROVED = "UNAPPROVED"
    EVIDENCE_GAP = "EVIDENCE_GAP"


class _Node(Protocol):
    node_id: str
    disposition: object
    authorization_state: object
    scan_completeness: object
    item_count: int | None
    next_gate: str


@dataclass(frozen=True)
class InteractionCue:
    target_kind: TargetKind
    verb: InteractionVerb
    availability: Availability
    recency: Recency
    consequence: Consequence
    explanation: str
    label: str
    cursor_mode: str
    quality_tone: QualityTone = QualityTone.NEUTRAL
    action_id: str = ""
    source_scene: str = ""
    destination_scene: str = ""
    impact_kind: str = ImpactKind.ORIENT.value
    continuation: str = ""
    context_fingerprint: str = ""

    def bind(
        self,
        *,
        source_scene: str,
        destination_scene: str,
        impact_kind: ImpactKind | str,
        continuation: str,
        action_id: str | None = None,
        selected_node_id: str = "",
        evidence_disposition: str = "",
        active_gate_id: str = "",
        authorization_state: str = "",
        target_id: str = "",
        scene_revision: str = "0",
        execution_or_readback_state: str = "",
    ) -> "InteractionCue":
        impact = (
            impact_kind.value if isinstance(impact_kind, ImpactKind) else str(impact_kind)
        )
        registered = action_id or self.action_id or self.verb.value
        fingerprint = context_fingerprint(
            scene_id=source_scene,
            scene_revision=scene_revision,
            selected_node_id=selected_node_id,
            evidence_disposition=evidence_disposition,
            active_gate_id=active_gate_id,
            authorization_state=authorization_state,
            target_id=target_id,
            target_kind=self.target_kind.value,
            registered_action=registered,
            execution_or_readback_state=execution_or_readback_state,
        )
        return replace(
            self,
            action_id=registered,
            source_scene=source_scene,
            destination_scene=destination_scene,
            impact_kind=impact,
            continuation=continuation,
            context_fingerprint=fingerprint,
        )

    def as_data(self) -> Mapping[str, str]:
        return {
            "data-target-kind": self.target_kind.value,
            "data-action": self.action_id or self.verb.value,
            "data-actionability": self.availability.value,
            "data-recency": self.recency.value,
            "data-consequence": self.consequence.value,
            "data-quality-tone": self.quality_tone.value,
            "data-cursor-mode": self.cursor_mode,
            "data-cue-label": self.label,
            "data-cue-explain": self.explanation,
            "data-source-scene": self.source_scene,
            "data-destination-scene": self.destination_scene,
            "data-impact-kind": self.impact_kind,
            "data-continuation": self.continuation,
            "data-context-fingerprint": self.context_fingerprint,
        }


def context_fingerprint(**canonical: str) -> str:
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def html_data_attrs(cue: InteractionCue) -> str:
    """Serialize cue fields as HTML data-* attributes (values already escaped by caller)."""

    parts = [f'{key}="{_escape_attr(value)}"' for key, value in cue.as_data().items()]
    return " ".join(parts)


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _disposition(node: _Node) -> CleanupDisposition:
    return CleanupDisposition(_value(node.disposition))


def _authorization(node: _Node) -> AuthorizationState:
    return AuthorizationState(_value(node.authorization_state))


def _completeness(node: _Node) -> ScanCompleteness:
    return ScanCompleteness(_value(node.scan_completeness))


def quality_tone_for_disposition(disposition: CleanupDisposition) -> QualityTone:
    if disposition is CleanupDisposition.PROTECTED:
        return QualityTone.BLOCKED
    if disposition is CleanupDisposition.KEEP_PROVEN:
        return QualityTone.ESSENTIAL
    if disposition is CleanupDisposition.RECLAIM_PROVEN:
        return QualityTone.RECLAIM_CANDIDATE
    if disposition in {
        CleanupDisposition.HUMAN_REVIEW,
        CleanupDisposition.UNKNOWN,
    }:
        return QualityTone.AMBIGUOUS
    return QualityTone.NEUTRAL


def cue_for_map_node(node: _Node, *, selected: bool) -> InteractionCue:
    disposition = _disposition(node)
    tone = quality_tone_for_disposition(disposition)

    if disposition is CleanupDisposition.PROTECTED:
        return InteractionCue(
            target_kind=TargetKind.EVIDENCE,
            verb=InteractionVerb.INSPECT_BLOCK,
            availability=Availability.OPERABLE,
            recency=Recency.CURRENT if selected else Recency.IDLE,
            consequence=Consequence.READ_ONLY,
            explanation="Protection relation blocks reclaim. Inspect the blocking gate.",
            label="INSPECT BLOCK",
            cursor_mode="blocked",
            quality_tone=QualityTone.BLOCKED,
        ).bind(
            source_scene="MAP",
            destination_scene="FOCUS",
            impact_kind=ImpactKind.ORIENT,
            continuation="Inspect the protection gate; deletion stays unavailable.",
            action_id="INSPECT_BLOCK",
            selected_node_id=node.node_id if selected else "",
            evidence_disposition=disposition.value,
            target_id=node.node_id,
        )

    if selected:
        return InteractionCue(
            target_kind=TargetKind.EVIDENCE,
            verb=InteractionVerb.FOCUS,
            availability=Availability.OPERABLE,
            recency=Recency.CURRENT,
            consequence=Consequence.READ_ONLY,
            explanation="Selected evidence is focused; open the next unresolved gate.",
            label="FOCUS",
            cursor_mode="focus",
            quality_tone=tone,
        ).bind(
            source_scene="MAP",
            destination_scene="FOCUS",
            impact_kind=ImpactKind.CLASSIFY,
            continuation="Open the first unresolved gate or legal intent.",
            action_id="FOCUS",
            selected_node_id=node.node_id,
            evidence_disposition=disposition.value,
            target_id=node.node_id,
        )

    return InteractionCue(
        target_kind=TargetKind.EVIDENCE,
        verb=InteractionVerb.FOCUS,
        availability=Availability.OPERABLE,
        recency=Recency.IDLE,
        consequence=Consequence.READ_ONLY,
        explanation="Select this evidence to open decision context. This is not an exploration environment.",
        label="SELECT",
        cursor_mode="focus",
        quality_tone=tone,
    ).bind(
        source_scene="MAP",
        destination_scene="FOCUS",
        impact_kind=ImpactKind.CLASSIFY,
        continuation="Focus the selected node, then continue to GATE/RESOLVE.",
        action_id="SELECT",
        evidence_disposition=disposition.value,
        target_id=node.node_id,
    )


def cue_for_navigation(action: str, *, recency: Recency = Recency.IDLE) -> InteractionCue:
    key = action.strip().lower().replace("-", "_").replace(" ", "_")
    table: dict[str, tuple[InteractionVerb, str, str, str]] = {
        "home": (
            InteractionVerb.RETURN,
            "ATLAS HOME",
            "return",
            "Return the camera to Atlas home.",
        ),
        "atlas_home": (
            InteractionVerb.RETURN,
            "ATLAS HOME",
            "return",
            "Return the camera to Atlas home.",
        ),
        "brand_home": (
            InteractionVerb.RETURN,
            "ATLAS HOME",
            "return",
            "Return the camera to Atlas home via the FileSteward brand.",
        ),
        "zoom_in": (
            InteractionVerb.DIVE_IN,
            "DIVE IN · Zoom +",
            "dive",
            "Dive one camera level deeper into the selected pressure.",
        ),
        "zoom_out": (
            InteractionVerb.PULL_BACK,
            "PULL BACK · Zoom −",
            "explore",
            "Pull the camera back one level.",
        ),
        "fit": (
            InteractionVerb.FRAME,
            "FRAME TARGET",
            "focus",
            "Frame the current selection in the camera.",
        ),
        "fit_selected": (
            InteractionVerb.FRAME,
            "FRAME TARGET",
            "focus",
            "Frame the current selection in the camera.",
        ),
        "search": (
            InteractionVerb.LOCATE,
            "LOCATE",
            "explore",
            "Locate exact evidence by search.",
        ),
        "decision": (
            InteractionVerb.RESOLVE,
            "RESOLVE",
            "resolve",
            "Open the Decision Chamber for the selected evidence.",
        ),
        "toggle_decision": (
            InteractionVerb.RESOLVE,
            "RESOLVE",
            "resolve",
            "Open the Decision Chamber for the selected evidence.",
        ),
        "open": (
            InteractionVerb.FOCUS,
            "FOCUS",
            "focus",
            "Open the focused evidence chamber.",
        ),
    }
    spec = table.get(key)
    if spec is None:
        return InteractionCue(
            target_kind=TargetKind.NAVIGATION,
            verb=InteractionVerb.LOCKED,
            availability=Availability.UNAVAILABLE,
            recency=recency,
            consequence=Consequence.READ_ONLY,
            explanation="Unregistered navigation has no operable effect.",
            label="LOCKED",
            cursor_mode="locked",
            quality_tone=QualityTone.BLOCKED,
        ).bind(
            source_scene="MAP",
            destination_scene="MAP",
            impact_kind=ImpactKind.ORIENT,
            continuation="No continuation: unknown action fails closed.",
            action_id="UNREGISTERED",
            target_id=key,
        )
    verb, label, cursor, explanation = spec
    impact = (
        ImpactKind.EXPLORE
        if verb in {InteractionVerb.DIVE_IN, InteractionVerb.PULL_BACK}
        else ImpactKind.FILTER
        if verb is InteractionVerb.LOCATE
        else ImpactKind.DECIDE
        if verb is InteractionVerb.RESOLVE
        else ImpactKind.ORIENT
    )
    destination = "RESOLVE" if verb is InteractionVerb.RESOLVE else "MAP"
    return InteractionCue(
        target_kind=TargetKind.NAVIGATION,
        verb=verb,
        availability=Availability.OPERABLE,
        recency=recency,
        consequence=Consequence.READ_ONLY,
        explanation=explanation,
        label=label,
        cursor_mode=cursor,
        quality_tone=QualityTone.NEUTRAL,
    ).bind(
        source_scene="MAP",
        destination_scene=destination,
        impact_kind=impact,
        continuation="Visible path remains classify → decide → authorize → reclaim.",
        action_id=verb.value,
        target_id=key,
    )


def cue_for_camera_command(
    command: str,
    *,
    recency: Recency,
    is_current_state: bool = False,
) -> InteractionCue:
    """Camera command history cue. CURRENT state must not misuse historical aria-current."""

    cue = cue_for_navigation(command, recency=recency)
    if is_current_state:
        return InteractionCue(
            target_kind=cue.target_kind,
            verb=cue.verb,
            availability=cue.availability,
            recency=Recency.CURRENT,
            consequence=cue.consequence,
            explanation="Current camera orientation (not a historical command).",
            label=cue.label,
            cursor_mode=cue.cursor_mode,
            quality_tone=cue.quality_tone,
        )
    return cue


def cue_for_status_orb(
    kind: StatusOrbKind,
    node: _Node,
    flow: DecisionFlowState | None = None,
) -> InteractionCue:
    disposition = _disposition(node)
    authorization = _authorization(node)

    if kind is StatusOrbKind.PROTECTED:
        present = disposition is CleanupDisposition.PROTECTED
        return InteractionCue(
            target_kind=TargetKind.STATUS,
            verb=InteractionVerb.INSPECT_BLOCK if present else InteractionVerb.EXPLAIN,
            availability=Availability.OPERABLE if present else Availability.INFORMATIONAL,
            recency=Recency.IDLE,
            consequence=Consequence.READ_ONLY,
            explanation=(
                "Protection blocks reclaim. Opening this orb focuses the blocking gate."
                if present
                else "No PROTECTED overlap on the current selection."
            ),
            label="INSPECT BLOCK" if present else "PROTECTED",
            cursor_mode="blocked" if present else "explore",
            quality_tone=QualityTone.BLOCKED if present else QualityTone.NEUTRAL,
        )

    if kind is StatusOrbKind.UNAPPROVED:
        eligible = (
            disposition is CleanupDisposition.RECLAIM_PROVEN
            and authorization is AuthorizationState.UNAPPROVED
        )
        if flow is not None:
            eligible = DecisionIntent.APPROVE_QUARANTINE in allowed_intents(flow)

        if eligible:
            return InteractionCue(
                target_kind=TargetKind.AUTHORIZATION,
                verb=InteractionVerb.APPROVE,
                availability=Availability.OPERABLE,
                recency=Recency.IDLE,
                consequence=Consequence.WRITE_APPROVAL,
                explanation=(
                    "RECLAIM_PROVEN evidence is UNAPPROVED. Approval stages quarantine only; "
                    "no bytes are removed."
                ),
                label="APPROVE",
                cursor_mode="approve",
                quality_tone=QualityTone.RECLAIM_CANDIDATE,
            )

        blocked_by_protection = disposition is CleanupDisposition.PROTECTED
        return InteractionCue(
            target_kind=TargetKind.AUTHORIZATION,
            verb=InteractionVerb.WHY_LOCKED,
            availability=Availability.BLOCKED,
            recency=Recency.IDLE,
            consequence=Consequence.READ_ONLY,
            explanation=(
                "Approval stays locked while protection blocks reclaim."
                if blocked_by_protection
                else "Approval is unavailable until RECLAIM_PROVEN evidence is ready."
            ),
            label="WHY LOCKED",
            cursor_mode="locked",
            quality_tone=QualityTone.BLOCKED if blocked_by_protection else QualityTone.AMBIGUOUS,
        )

    # EVIDENCE_GAP — incomplete/unknown count or incomplete scan.
    # Distinct from CleanupDisposition.UNKNOWN as a disposition class.
    gap = (
        node.item_count is None
        or _completeness(node) is ScanCompleteness.INCOMPLETE
    )
    if not gap:
        return InteractionCue(
            target_kind=TargetKind.STATUS,
            verb=InteractionVerb.EXPLAIN,
            availability=Availability.INFORMATIONAL,
            recency=Recency.IDLE,
            consequence=Consequence.READ_ONLY,
            explanation="Evidence count and scan completeness are established for this selection.",
            label="EVIDENCE COMPLETE",
            cursor_mode="explore",
            quality_tone=QualityTone.NEUTRAL,
        )

    can_rescan = False
    if flow is not None:
        can_rescan = DecisionIntent.RESCAN in allowed_intents(flow)

    if can_rescan:
        return InteractionCue(
            target_kind=TargetKind.STATUS,
            verb=InteractionVerb.RESCAN,
            availability=Availability.OPERABLE,
            recency=Recency.IDLE,
            consequence=Consequence.RECORD_INTENT,
            explanation=(
                "Evidence gap: item count or scan completeness is incomplete. "
                "RESCAN is a legal operator intent from the current gate."
            ),
            label="RESCAN",
            cursor_mode="resolve",
            quality_tone=QualityTone.AMBIGUOUS,
        )

    return InteractionCue(
        target_kind=TargetKind.STATUS,
        verb=InteractionVerb.EXPLAIN,
        availability=Availability.OPERABLE,
        recency=Recency.IDLE,
        consequence=Consequence.READ_ONLY,
        explanation=(
            "Evidence gap (? items / incomplete observation). "
            "This is not CleanupDisposition.UNKNOWN unless disposition also says UNKNOWN."
        ),
        label="EXPLAIN EVIDENCE",
        cursor_mode="resolve",
        quality_tone=QualityTone.AMBIGUOUS,
    )


def cue_for_intent(
    intent: DecisionIntent,
    flow: DecisionFlowState,
) -> InteractionCue:
    allowed = intent in allowed_intents(flow)
    if not allowed:
        return InteractionCue(
            target_kind=TargetKind.INTENT,
            verb=InteractionVerb.LOCKED,
            availability=Availability.UNAVAILABLE,
            recency=Recency.IDLE,
            consequence=Consequence.READ_ONLY,
            explanation=f"{intent.value} is not legal from the current decision scene.",
            label="LOCKED",
            cursor_mode="locked",
            quality_tone=QualityTone.BLOCKED,
        )

    if intent is DecisionIntent.APPROVE_QUARANTINE:
        return InteractionCue(
            target_kind=TargetKind.INTENT,
            verb=InteractionVerb.APPROVE,
            availability=Availability.OPERABLE,
            recency=Recency.IDLE,
            consequence=Consequence.WRITE_APPROVAL,
            explanation="Request quarantine staging. Terminal mutation truth: NO BYTES REMOVED.",
            label="APPROVE",
            cursor_mode="approve",
            quality_tone=QualityTone.RECLAIM_CANDIDATE,
        )

    if intent is DecisionIntent.RESCAN:
        return InteractionCue(
            target_kind=TargetKind.INTENT,
            verb=InteractionVerb.RESCAN,
            availability=Availability.OPERABLE,
            recency=Recency.IDLE,
            consequence=Consequence.RECORD_INTENT,
            explanation="Record a rescan intent; does not mutate files.",
            label="RESCAN",
            cursor_mode="resolve",
            quality_tone=QualityTone.AMBIGUOUS,
        ).bind(
            source_scene=flow.scene.value,
            destination_scene=flow.scene.value,
            impact_kind=ImpactKind.CLASSIFY,
            continuation="Wait for authoritative rescan readback, then open the derived scene.",
            action_id="RESCAN",
            selected_node_id=flow.selected_node_id,
            evidence_disposition=flow.disposition.value,
            active_gate_id=flow.active_gate_id or "",
            authorization_state=flow.authorization_state.value,
        )

    if intent is DecisionIntent.DELETE_PERMANENTLY:
        return InteractionCue(
            target_kind=TargetKind.INTENT,
            verb=InteractionVerb.APPROVE,
            availability=Availability.OPERABLE,
            recency=Recency.IDLE,
            consequence=Consequence.DELETE_PERMANENTLY,
            explanation=(
                "One deliberate DELETE PERMANENTLY commit for the exact eligible "
                "RECLAIM_PROVEN set. Creates delete-specific approval, executes, "
                "and reads the receipt."
            ),
            label="DELETE PERMANENTLY",
            cursor_mode="approve",
            quality_tone=QualityTone.RECLAIM_CANDIDATE,
        ).bind(
            source_scene=flow.scene.value,
            destination_scene="RESULT",
            impact_kind=ImpactKind.RECLAIM,
            continuation="Surface execution receipt and remaining residual items.",
            action_id="DELETE_PERMANENTLY",
            selected_node_id=flow.selected_node_id,
            evidence_disposition=flow.disposition.value,
            authorization_state=flow.authorization_state.value,
        )

    return InteractionCue(
        target_kind=TargetKind.INTENT,
        verb=InteractionVerb.RESOLVE,
        availability=Availability.OPERABLE,
        recency=Recency.IDLE,
        consequence=Consequence.RECORD_INTENT,
        explanation=f"Record operator intent {intent.value} without promoting evidence.",
        label=intent.value.replace("_", " "),
        cursor_mode="resolve",
        quality_tone=QualityTone.NEUTRAL,
    ).bind(
        source_scene=flow.scene.value,
        destination_scene="CLOSED" if intent in {DecisionIntent.KEEP, DecisionIntent.REVIEW_LATER} else flow.scene.value,
        impact_kind=ImpactKind.DECIDE,
        continuation="Advance to the next actionable item or derived scene.",
        action_id=intent.value,
        selected_node_id=flow.selected_node_id,
        evidence_disposition=flow.disposition.value,
        active_gate_id=flow.active_gate_id or "",
        authorization_state=flow.authorization_state.value,
    )
