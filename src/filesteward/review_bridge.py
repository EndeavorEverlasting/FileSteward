"""Localhost-only FileSteward Decision Bridge protocol and HTTP adapter.

Binding is fixed to 127.0.0.1. Mutations require loopback Host, exact served
Origin, application/json, and an unpredictable per-process session token in
X-FileSteward-Session. No permissive CORS. The token is never written to
tracked files or durable runtime artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import webbrowser
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

from filesteward.approval import (
    ApprovalAction,
    ApprovalRecord,
    validate_approval_against_plan,
)
from filesteward.deletion import (
    DELETE_ACTION,
    DELETE_APPROVAL_FILENAME,
    DELETE_MANIFEST_FILENAME,
    build_delete_approval,
    emit_delete_manifest,
    execute_permanent_delete,
    load_delete_receipt,
    run_preflight,
    write_delete_approval,
    write_preflight_receipt,
)
from filesteward.deletion.preflight import load_run_protection_context
from filesteward.deletion.receipt import DELETE_RECEIPT_FILENAME
from filesteward.manifest import validate_run
from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.policy.paths import normalize_declared_path, prove_run_dir_under_runtime
from filesteward.visualization.decision_flow import (
    DecisionIntent,
    DecisionScene,
    ExecutionState,
    PendingAction,
    allowed_intents,
    choose_intent,
    open_decision_session,
)
from filesteward.visualization.html import render_report_html, write_report_html_atomically
from filesteward.visualization.model import build_presentation_model
from filesteward.visualization.report import REPORT_FILENAME
from filesteward.visualization.treemap import layout_treemap

__all__ = [
    "APPROVAL_PATH",
    "DECISION_PATH",
    "DELETE_PATH",
    "DECISION_STATE_FILENAME",
    "APPROVAL_RECORD_FILENAME",
    "SESSION_HEADER",
    "STATE_PATH",
    "DecisionBridgeIntent",
    "DecisionRequest",
    "ApprovalRequest",
    "ReviewBridge",
    "ReviewServeResult",
    "inject_bridge_runtime",
    "is_loopback_host",
    "sha256_file",
    "serve_review",
]

STATE_PATH = "/api/v1/state"
DECISION_PATH = "/api/v1/decision"
APPROVAL_PATH = "/api/v1/approval"
DELETE_PATH = "/api/v1/delete"
SESSION_HEADER = "X-FileSteward-Session"
DECISION_STATE_FILENAME = "decision-chamber-state.json"
APPROVAL_RECORD_FILENAME = "approval-record.json"
BRIDGE_RUNTIME_ID = "decision-bridge-runtime"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_LOOPBACK_NAMES = frozenset({"127.0.0.1", "::1", "localhost"})
_DECISION_SCHEMA = "filesteward.decision-chamber/v1"


class DecisionBridgeIntent(str, Enum):
    RESCAN = "RESCAN"
    DECLARE_REGENERABLE_CONTRACT = "DECLARE_REGENERABLE_CONTRACT"
    KEEP = "KEEP"
    REVIEW_LATER = "REVIEW_LATER"
    DELETE_PERMANENTLY = "DELETE_PERMANENTLY"


_COMPLETED_OPERATOR_INTENTS = frozenset(
    {DecisionBridgeIntent.KEEP.value, DecisionBridgeIntent.REVIEW_LATER.value}
)
_NON_ACTIONABLE_DISPOSITIONS = frozenset(
    {
        CleanupDisposition.PROTECTED,
        CleanupDisposition.KEEP_PROVEN,
    }
)


def is_loopback_host(host: str) -> bool:
    hostname = host.strip().lower()
    if hostname.startswith("["):
        hostname = hostname.split("]", 1)[0].lstrip("[")
    if ":" in hostname and not hostname.startswith("::"):
        # Strip port from host:port (IPv4 / localhost).
        hostname = hostname.rsplit(":", 1)[0]
    return hostname in _LOOPBACK_NAMES


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DecisionRequest:
    run_id: str
    item_id: str
    intent: DecisionBridgeIntent

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.item_id:
            raise ValueError("item_id must be non-empty")

    def as_mapping(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "item_id": self.item_id,
            "intent": self.intent.value,
        }


@dataclass(frozen=True)
class ApprovalRequest:
    run_id: str
    item_id: str
    cleanup_plan_sha256: str
    action: ApprovalAction
    confirm: bool

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if not _SHA256_RE.fullmatch(self.cleanup_plan_sha256):
            raise ValueError(
                "cleanup_plan_sha256 must be a lowercase 64-character sha256"
            )
        if self.action is not ApprovalAction.QUARANTINE:
            raise ValueError("Decision Bridge approval only admits QUARANTINE")
        if self.confirm is not True:
            raise ValueError("explicit confirm=true is required for approval")

    def as_mapping(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "item_id": self.item_id,
            "cleanup_plan_sha256": self.cleanup_plan_sha256,
            "action": self.action.value,
            "confirm": self.confirm,
        }


def inject_bridge_runtime(html: str, runtime: Mapping[str, object]) -> str:
    """Inject process-only bridge runtime into a served HTML document."""

    raw = (
        json.dumps(dict(runtime), ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    tag = (
        f'<script type="application/json" id="{BRIDGE_RUNTIME_ID}">'
        f"{raw}</script>"
    )
    if f'id="{BRIDGE_RUNTIME_ID}"' in html:
        pattern = re.compile(
            rf'<script type="application/json" id="{BRIDGE_RUNTIME_ID}">.*?</script>',
            re.DOTALL,
        )
        return pattern.sub(tag, html, count=1)
    if "</head>" in html:
        return html.replace("</head>", f"{tag}\n</head>", 1)
    return tag + html


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class _NodeView:
    node_id: str
    disposition: CleanupDisposition
    authorization_state: AuthorizationState
    gate_steps: tuple[Any, ...]
    path: str
    display_name: str
    reclaim_basis: str | None


@dataclass
class ReviewBridge:
    """In-process Decision Bridge for one validated run directory."""

    run_dir: Path
    run_id: str
    cleanup_plan_sha256: str
    session_token: str
    report_html: str
    origin: str = ""
    host_header: str = "127.0.0.1"
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _nodes: dict[str, _NodeView] = field(default_factory=dict, repr=False)
    _plan_rows: list[dict[str, object]] = field(default_factory=list, repr=False)
    _decisions: dict[str, dict[str, object]] = field(default_factory=dict, repr=False)
    _approvals: dict[str, dict[str, object]] = field(default_factory=dict, repr=False)
    _scene_revision: int = field(default=0, repr=False)
    _last_transition: str | None = field(default=None, repr=False)
    _pending_by_item: dict[str, PendingAction] = field(default_factory=dict, repr=False)
    _execution_by_item: dict[str, ExecutionState] = field(default_factory=dict, repr=False)

    @classmethod
    def open(cls, run_dir: Path, *, regenerate_report: bool = True) -> ReviewBridge:
        target = prove_run_dir_under_runtime(run_dir)
        errors = validate_run(target)
        if errors:
            joined = "; ".join(errors)
            raise ValueError(
                f"run failed FileSteward validation ({len(errors)} problem(s)): {joined}"
            )
        plan_path = target / "cleanup-plan.csv"
        plan_sha = sha256_file(plan_path)
        # One presentation-model build owns both report publication and bridge state.
        model = build_presentation_model(target)
        report_path = target / REPORT_FILENAME
        if regenerate_report or not report_path.is_file():
            rects = layout_treemap(model.nodes)
            html = render_report_html(model, rects)
            write_report_html_atomically(report_path, html)
        else:
            html = report_path.read_text(encoding="utf-8")
        nodes = {
            node.node_id: _NodeView(
                node_id=node.node_id,
                disposition=node.disposition,
                authorization_state=node.authorization_state,
                gate_steps=node.gate_steps,
                path=node.path,
                display_name=node.display_name,
                reclaim_basis=node.reclaim_basis,
            )
            for node in model.nodes
        }
        plan_rows: list[dict[str, object]] = []
        with plan_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                plan_rows.append(dict(row))
        bridge = cls(
            run_dir=target,
            run_id=model.run_id,
            cleanup_plan_sha256=plan_sha,
            session_token=secrets.token_urlsafe(32),
            report_html=html,
            _nodes=nodes,
            _plan_rows=plan_rows,
        )
        bridge._load_persisted()
        return bridge

    def bind_origin(self, host: str, port: int) -> None:
        self.host_header = f"{host}:{port}"
        self.origin = f"http://{host}:{port}"
        runtime = {
            "origin": self.origin,
            "runId": self.run_id,
            "cleanupPlanSha256": self.cleanup_plan_sha256,
            "sessionToken": self.session_token,
            "statePath": STATE_PATH,
            "decisionPath": DECISION_PATH,
            "approvalPath": APPROVAL_PATH,
            "deletePath": DELETE_PATH,
            "sessionHeader": SESSION_HEADER,
        }
        # Token stays in the process-served HTML only.
        self.report_html = inject_bridge_runtime(self.report_html, runtime)

    def decision_state_path(self) -> Path:
        return self.run_dir / DECISION_STATE_FILENAME

    def approval_record_path(self) -> Path:
        return self.run_dir / APPROVAL_RECORD_FILENAME

    def _load_persisted(self) -> None:
        state_path = self.decision_state_path()
        if state_path.is_file():
            data = json.loads(state_path.read_text(encoding="utf-8"))
            decisions = data.get("decisions") or {}
            if isinstance(decisions, dict):
                self._decisions = {
                    str(key): dict(value)
                    for key, value in decisions.items()
                    if isinstance(value, dict)
                }
        approval_path = self.approval_record_path()
        if approval_path.is_file():
            record = json.loads(approval_path.read_text(encoding="utf-8"))
            if record.get("cleanup_plan_sha256") == self.cleanup_plan_sha256:
                for item_id in record.get("approved_item_ids") or ():
                    self._approvals[str(item_id)] = {
                        "authorization_state": AuthorizationState.APPROVED_FOR_ACTION.value,
                        "action": record.get("action"),
                        "cleanup_plan_sha256": record.get("cleanup_plan_sha256"),
                    }
                    node = self._nodes.get(str(item_id))
                    if node is not None:
                        node.authorization_state = AuthorizationState.APPROVED_FOR_ACTION

    def _persist_decisions(self) -> None:
        payload = {
            "schema_version": _DECISION_SCHEMA,
            "run_id": self.run_id,
            "cleanup_plan_sha256": self.cleanup_plan_sha256,
            "updated_at": _utc_now(),
            "decisions": self._decisions,
        }
        _atomic_write_json(self.decision_state_path(), payload)

    def _operator_intent_for(self, item_id: str) -> str | None:
        recorded = self._decisions.get(item_id) or {}
        intent = recorded.get("intent")
        return str(intent) if intent else None

    def _is_completed_item(self, item_id: str) -> bool:
        return self._operator_intent_for(item_id) in _COMPLETED_OPERATOR_INTENTS

    def _is_actionable_node(self, node: _NodeView) -> bool:
        if node.disposition in _NON_ACTIONABLE_DISPOSITIONS:
            return False
        if self._is_completed_item(node.node_id):
            return False
        return True

    def _next_actionable_node(self, after_item_id: str | None) -> _NodeView | None:
        ids = list(self._nodes)
        if after_item_id and after_item_id in self._nodes:
            start = ids.index(after_item_id) + 1
            ordered = ids[start:] + ids[:start]
        else:
            ordered = ids
        for node_id in ordered:
            node = self._nodes[node_id]
            if after_item_id and node_id == after_item_id:
                continue
            if self._is_actionable_node(node):
                return node
        return None

    def _refresh_nodes(self) -> None:
        model = build_presentation_model(self.run_dir)
        nodes = {
            node.node_id: _NodeView(
                node_id=node.node_id,
                disposition=node.disposition,
                authorization_state=node.authorization_state,
                gate_steps=node.gate_steps,
                path=node.path,
                display_name=node.display_name,
                reclaim_basis=node.reclaim_basis,
            )
            for node in model.nodes
        }
        for item_id, approval in self._approvals.items():
            node = nodes.get(item_id)
            if node is not None:
                node.authorization_state = AuthorizationState(
                    str(approval.get("authorization_state") or AuthorizationState.APPROVED_FOR_ACTION.value)
                )
        self._nodes = nodes

    def _classification_views(self) -> dict[str, dict[str, int]]:
        dispositions: dict[str, int] = {}
        for node in self._nodes.values():
            key = node.disposition.value
            dispositions[key] = dispositions.get(key, 0) + 1
        operator_intents: dict[str, int] = {}
        for recorded in self._decisions.values():
            intent = str(recorded.get("intent") or "")
            if intent:
                operator_intents[intent] = operator_intents.get(intent, 0) + 1
        return {
            "dispositions": dispositions,
            "operator_intents": operator_intents,
        }

    def _session_for(self, node: _NodeView):
        if self._is_completed_item(node.node_id):
            closed = open_decision_session(node)
            return replace(
                closed,
                scene=DecisionScene.CLOSED,
                pending_action=PendingAction.NONE,
                last_transition=self._last_transition or "complete",
                execution_state=ExecutionState.COMPLETE,
            )
        return open_decision_session(node)

    def state_payload(self, item_id: str | None = None) -> dict[str, object]:
        with self._lock:
            requested = item_id if item_id and item_id in self._nodes else None
            current_item_id = requested
            selected_id = requested
            if requested and self._is_completed_item(requested):
                nxt = self._next_actionable_node(requested)
                selected_id = nxt.node_id if nxt is not None else requested
            node = self._nodes.get(selected_id) if selected_id else None
            flow = self._session_for(node) if node is not None else None
            pending = self._pending_by_item.get(selected_id or "")
            execution = self._execution_by_item.get(selected_id or "")
            if pending is not None and flow is not None:
                flow = replace(
                    flow,
                    pending_action=pending,
                    execution_state=execution or ExecutionState.PENDING,
                    last_transition=self._last_transition or flow.last_transition,
                    scene_revision=self._scene_revision,
                )
            intents: list[str] = []
            if flow is not None and not self._is_completed_item(selected_id or ""):
                intents = [intent.value for intent in allowed_intents(flow)]
            next_item = selected_id
            next_scene = flow.scene.value if flow else DecisionScene.MAP.value
            if requested and self._is_completed_item(requested):
                nxt = self._next_actionable_node(requested)
                next_item = nxt.node_id if nxt is not None else None
                if nxt is not None:
                    next_scene = self._session_for(nxt).scene.value
                else:
                    next_scene = DecisionScene.CLOSED.value
            decision = self._decisions.get(selected_id or "", {})
            approval = self._approvals.get(selected_id or "", {})
            open_scene = flow.scene.value if flow else DecisionScene.MAP.value
            last_transition = self._last_transition
            if last_transition is None and flow is not None:
                last_transition = flow.last_transition
            execution_state = (
                execution.value
                if execution is not None
                else (flow.execution_state.value if flow else ExecutionState.EXECUTABLE.value)
            )
            pending_action = (
                pending.value
                if pending is not None
                else (flow.pending_action.value if flow else PendingAction.NONE.value)
            )
            return {
                "run_id": self.run_id,
                "cleanup_plan_sha256": self.cleanup_plan_sha256,
                "selected_node_id": selected_id,
                "current_item_id": current_item_id,
                "next_item_id": next_item,
                "evidence_disposition": (
                    node.disposition.value if node else None
                ),
                "authorization_state": (
                    node.authorization_state.value if node else None
                ),
                "open_decision_scene": open_scene,
                "next_scene": next_scene,
                "active_gate_id": flow.active_gate_id if flow else None,
                "last_scene": flow.last_scene.value if flow and flow.last_scene else None,
                "last_transition": last_transition,
                "execution_state": execution_state,
                "pending_action": pending_action,
                "scene_revision": self._scene_revision,
                "classification_views": self._classification_views(),
                "allowed_intents": intents,
                "operator_decision": decision or None,
                "approval": approval or None,
                "node": (
                    {
                        "node_id": node.node_id,
                        "path": node.path,
                        "display_name": node.display_name,
                        "reclaim_basis": node.reclaim_basis,
                    }
                    if node
                    else None
                ),
                "staged_copy": (
                    "STAGED — quarantine staged, NO BYTES REMOVED. "
                    "Permanent delete uses a separate DELETE PERMANENTLY path when eligible."
                ),
            }

    def record_decision(self, request: DecisionRequest) -> dict[str, object]:
        with self._lock:
            if request.run_id != self.run_id:
                raise ValueError("run_id does not match the served run")
            if request.intent is DecisionBridgeIntent.DELETE_PERMANENTLY:
                raise ValueError("DELETE_PERMANENTLY must use POST /api/v1/delete")
            node = self._nodes.get(request.item_id)
            if node is None:
                raise ValueError(f"item {request.item_id} is not in the presentation model")
            if self._is_completed_item(request.item_id):
                return self.state_payload(request.item_id)
            session = open_decision_session(node)
            intent = DecisionIntent(request.intent.value)
            if intent is DecisionIntent.APPROVE_QUARANTINE:
                raise ValueError("approval must use POST /api/v1/approval")
            flow = choose_intent(session, intent)
            self._decisions[request.item_id] = {
                "intent": request.intent.value,
                "evidence_disposition": node.disposition.value,
                "recorded_at": _utc_now(),
                "label": f"Decision: {request.intent.value.replace('_', ' ')} REQUESTED",
            }
            self._persist_decisions()
            self._scene_revision += 1
            self._last_transition = flow.last_transition
            if request.intent in {
                DecisionBridgeIntent.KEEP,
                DecisionBridgeIntent.REVIEW_LATER,
            }:
                self._pending_by_item.pop(request.item_id, None)
                self._execution_by_item[request.item_id] = ExecutionState.COMPLETE
                return self.state_payload(request.item_id)
            if request.intent in {
                DecisionBridgeIntent.RESCAN,
                DecisionBridgeIntent.DECLARE_REGENERABLE_CONTRACT,
            }:
                self._pending_by_item[request.item_id] = flow.pending_action
                self._execution_by_item[request.item_id] = ExecutionState.PENDING
                before = node.disposition
                self._refresh_nodes()
                refreshed = self._nodes.get(request.item_id)
                if refreshed is None:
                    return self.state_payload(request.item_id)
                if refreshed.disposition is before:
                    self._pending_by_item[request.item_id] = flow.pending_action
                    self._execution_by_item[request.item_id] = ExecutionState.PENDING
                else:
                    self._pending_by_item.pop(request.item_id, None)
                    self._execution_by_item.pop(request.item_id, None)
                return self.state_payload(request.item_id)
            return self.state_payload(request.item_id)

    def execute_permanent_delete_ui(
        self,
        run_id: str,
        item_ids: list[str] | tuple[str, ...],
        scan_root: str | Path,
        irreversible_confirmation: str,
    ) -> dict[str, object]:
        with self._lock:
            if run_id != self.run_id:
                raise ValueError("run_id does not match the served run")
            token = str(irreversible_confirmation or "").strip()
            if not token:
                raise ValueError("irreversible_confirmation must be non-empty")
            if token.upper() == ApprovalAction.QUARANTINE.value:
                raise ValueError("quarantine approval cannot authorize permanent deletion")
            ids = [str(item_id) for item_id in item_ids]
            if not ids:
                raise ValueError("item_ids must be non-empty")
            for item_id in ids:
                node = self._nodes.get(item_id)
                if node is None:
                    raise ValueError(f"item {item_id} is not in the presentation model")
                if node.disposition is not CleanupDisposition.RECLAIM_PROVEN:
                    raise ValueError(
                        "permanent deletion requires RECLAIM_PROVEN disposition"
                    )
            approval_path = self.approval_record_path()
            if approval_path.is_file():
                quarantine = json.loads(approval_path.read_text(encoding="utf-8"))
                if str(quarantine.get("action") or "") == ApprovalAction.QUARANTINE.value:
                    # Quarantine receipts are not delete authority; continue
                    # only through the deletion-package approval below.
                    pass
            emit_delete_manifest(self.run_dir)
            manifest_path = self.run_dir / DELETE_MANIFEST_FILENAME
            protection_roots, managed_paths = load_run_protection_context(self.run_dir)
            scan = normalize_declared_path(scan_root)
            preflight = run_preflight(
                manifest_path,
                scan_root=scan,
                cleanup_plan_path=self.run_dir / "cleanup-plan.csv",
                protection_roots=protection_roots,
                managed_paths=managed_paths,
            )
            preflight_path = self.run_dir / "delete-preflight.json"
            write_preflight_receipt(preflight_path, preflight)
            if preflight.overall != "PASS":
                raise ValueError(
                    f"delete preflight did not PASS ({preflight.overall})"
                )
            approval = build_delete_approval(
                manifest=manifest_path,
                preflight=preflight_path,
                approved_item_ids=ids,
                irreversible_confirmation=DELETE_ACTION,
                run_id=self.run_id,
            )
            write_delete_approval(self.run_dir / DELETE_APPROVAL_FILENAME, approval)
            approved_snapshot = self.run_dir / "delete-preflight.approved.json"
            shutil.copy2(preflight_path, approved_snapshot)
            execute_permanent_delete(
                run_dir=self.run_dir,
                manifest=manifest_path,
                approval=self.run_dir / DELETE_APPROVAL_FILENAME,
                preflight=approved_snapshot,
                scan_root=scan,
            )
            receipt = load_delete_receipt(self.run_dir / DELETE_RECEIPT_FILENAME) or {}
            items = receipt.get("items") or []
            counts = {"attempted": 0, "succeeded": 0, "failed": 0, "skipped": 0}
            if isinstance(items, list):
                counts["attempted"] = len(items)
                for item in items:
                    status = str((item or {}).get("status") or "")
                    if status == "SUCCEEDED":
                        counts["succeeded"] += 1
                    elif status == "FAILED":
                        counts["failed"] += 1
                    elif status == "SKIPPED":
                        counts["skipped"] += 1
            self._scene_revision += 1
            self._last_transition = "delete_permanently"
            focus = ids[0]
            self._execution_by_item[focus] = ExecutionState.COMPLETE
            self._pending_by_item.pop(focus, None)
            payload = self.state_payload(focus)
            payload["open_decision_scene"] = DecisionScene.RESULT.value
            payload["next_scene"] = DecisionScene.RESULT.value
            payload["execution_state"] = ExecutionState.COMPLETE.value
            payload["pending_action"] = PendingAction.NONE.value
            payload["deletion_receipt"] = {
                **counts,
                "overall": receipt.get("overall"),
                "reclaim": receipt.get("reclaim"),
                "free_bytes_before": receipt.get("free_bytes_before"),
                "free_bytes_after": receipt.get("free_bytes_after"),
            }
            return payload

    def record_approval(self, request: ApprovalRequest) -> dict[str, object]:
        with self._lock:
            if request.run_id != self.run_id:
                raise ValueError("run_id does not match the served run")
            if request.cleanup_plan_sha256 != self.cleanup_plan_sha256:
                raise ValueError("cleanup_plan_sha256 does not match served plan digest")
            node = self._nodes.get(request.item_id)
            if node is None:
                raise ValueError(f"item {request.item_id} is not in the presentation model")
            if node.disposition is not CleanupDisposition.RECLAIM_PROVEN:
                raise ValueError("only RECLAIM_PROVEN evidence may be approved")
            record = ApprovalRecord(
                run_id=request.run_id,
                cleanup_plan_sha256=request.cleanup_plan_sha256,
                approved_item_ids=(request.item_id,),
                action=request.action,
            )
            errors = validate_approval_against_plan(record, self._plan_rows)
            if errors:
                raise ValueError("; ".join(errors))
            _atomic_write_json(self.approval_record_path(), record.as_mapping())
            self._approvals[request.item_id] = {
                "authorization_state": AuthorizationState.APPROVED_FOR_ACTION.value,
                "action": request.action.value,
                "cleanup_plan_sha256": request.cleanup_plan_sha256,
                "recorded_at": _utc_now(),
            }
            node.authorization_state = AuthorizationState.APPROVED_FOR_ACTION
            return self.state_payload(request.item_id)


@dataclass(frozen=True)
class ReviewServeResult:
    url: str
    host: str
    port: int
    run_id: str
    cleanup_plan_sha256: str
    report_path: Path
    server: ThreadingHTTPServer
    thread: threading.Thread


def _make_handler(bridge: ReviewBridge) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _json(self, code: int, payload: Mapping[str, object]) -> None:
            body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _html(self, code: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _reject(self, code: int, message: str) -> None:
            self._json(code, {"error": message})

        def _mutation_guard(self) -> bool:
            host = self.headers.get("Host", "")
            if not is_loopback_host(host):
                self._reject(403, "Host must be loopback")
                return False
            origin = self.headers.get("Origin")
            if origin is None or origin != bridge.origin:
                self._reject(403, "Origin must match the served Decision Bridge origin")
                return False
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip()
            if content_type != "application/json":
                self._reject(415, "Content-Type must be application/json")
                return False
            token = self.headers.get(SESSION_HEADER)
            if not token or not secrets.compare_digest(token, bridge.session_token):
                self._reject(403, "valid X-FileSteward-Session token required")
                return False
            # Fail closed: never emit Access-Control-Allow-Origin.
            if self.headers.get("Access-Control-Request-Method"):
                self._reject(403, "CORS preflight is not permitted")
                return False
            return True

        def _read_json(self) -> dict[str, Any] | None:
            length_raw = self.headers.get("Content-Length")
            if not length_raw:
                self._reject(411, "Content-Length required")
                return None
            try:
                length = int(length_raw)
            except ValueError:
                self._reject(400, "invalid Content-Length")
                return None
            if length < 0 or length > 1_000_000:
                self._reject(400, "request body too large")
                return None
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                self._reject(400, "JSON body required")
                return None
            if not isinstance(data, dict):
                self._reject(400, "JSON object required")
                return None
            return data

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._reject(403, "CORS preflight is not permitted")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", f"/{REPORT_FILENAME}"}:
                self._html(200, bridge.report_html)
                return
            if parsed.path == STATE_PATH:
                host = self.headers.get("Host", "")
                if not is_loopback_host(host):
                    self._reject(403, "Host must be loopback")
                    return
                item_id = None
                if parsed.query:
                    for part in parsed.query.split("&"):
                        if part.startswith("item_id="):
                            item_id = part.split("=", 1)[1]
                self._json(200, bridge.state_payload(item_id))
                return
            self._reject(404, "not found")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {DECISION_PATH, APPROVAL_PATH, DELETE_PATH}:
                self._reject(404, "not found")
                return
            if not self._mutation_guard():
                return
            data = self._read_json()
            if data is None:
                return
            try:
                if parsed.path == DELETE_PATH:
                    raw_ids = data.get("item_ids")
                    if raw_ids is None and data.get("item_id"):
                        raw_ids = [data.get("item_id")]
                    if not isinstance(raw_ids, list) or not raw_ids:
                        self._reject(400, "item_ids or item_id is required")
                        return
                    payload = bridge.execute_permanent_delete_ui(
                        run_id=str(data.get("run_id") or ""),
                        item_ids=[str(item) for item in raw_ids],
                        scan_root=str(data.get("scan_root") or ""),
                        irreversible_confirmation=str(
                            data.get("irreversible_confirmation") or ""
                        ),
                    )
                    self._json(200, payload)
                    return
                if parsed.path == DECISION_PATH:
                    intent_raw = str(data.get("intent") or "")
                    if intent_raw == DecisionIntent.DELETE_PERMANENTLY.value:
                        self._reject(
                            400, "DELETE_PERMANENTLY must use POST /api/v1/delete"
                        )
                        return
                    request = DecisionRequest(
                        run_id=str(data.get("run_id") or ""),
                        item_id=str(data.get("item_id") or ""),
                        intent=DecisionBridgeIntent(intent_raw),
                    )
                    payload = bridge.record_decision(request)
                    self._json(200, payload)
                    return
                action_raw = str(data.get("action") or "")
                if action_raw and action_raw != ApprovalAction.QUARANTINE.value:
                    self._reject(400, "only QUARANTINE approval is admitted")
                    return
                request = ApprovalRequest(
                    run_id=str(data.get("run_id") or ""),
                    item_id=str(data.get("item_id") or ""),
                    cleanup_plan_sha256=str(data.get("cleanup_plan_sha256") or ""),
                    action=ApprovalAction.QUARANTINE,
                    confirm=data.get("confirm") is True,
                )
                payload = bridge.record_approval(request)
                self._json(200, payload)
            except (ValueError, KeyError) as exc:
                self._reject(400, str(exc))

    return Handler


def serve_review(
    run_dir: Path,
    *,
    port: int = 0,
    open_browser: bool = True,
    bind_host: str = "127.0.0.1",
    regenerate_report: bool = True,
) -> ReviewServeResult:
    """Validate, regenerate report, and serve the Decision Bridge on loopback."""

    if bind_host != "127.0.0.1":
        raise ValueError("Decision Bridge bind host must be 127.0.0.1")
    if port < 0 or port > 65535:
        raise ValueError("port must be in 0..65535")

    bridge = ReviewBridge.open(run_dir, regenerate_report=regenerate_report)
    handler = _make_handler(bridge)
    try:
        server = ThreadingHTTPServer((bind_host, port), handler)
    except OSError as exc:
        raise RuntimeError(f"failed to bind Decision Bridge: {exc}") from exc

    bound_host, bound_port = server.server_address[:2]
    if bound_host not in {"127.0.0.1", "localhost"}:
        server.server_close()
        raise RuntimeError("Decision Bridge refused non-loopback bind")
    bridge.bind_origin("127.0.0.1", int(bound_port))
    thread = threading.Thread(target=server.serve_forever, name="filesteward-review", daemon=True)
    thread.start()
    url = f"{bridge.origin}/"
    if open_browser:
        webbrowser.open(url)
    return ReviewServeResult(
        url=url,
        host="127.0.0.1",
        port=int(bound_port),
        run_id=bridge.run_id,
        cleanup_plan_sha256=bridge.cleanup_plan_sha256,
        report_path=bridge.run_dir / REPORT_FILENAME,
        server=server,
        thread=thread,
    )


def run_review_until_interrupt(
    run_dir: Path,
    *,
    port: int = 0,
    open_browser: bool = True,
    on_ready: Optional[Callable[[ReviewServeResult], None]] = None,
) -> ReviewServeResult:
    result = serve_review(run_dir, port=port, open_browser=open_browser)
    if on_ready is not None:
        on_ready(result)
    try:
        result.thread.join()
    except KeyboardInterrupt:
        result.server.shutdown()
    return result
