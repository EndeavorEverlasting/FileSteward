"""HTTP adapter proofs for the localhost Decision Bridge."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from filesteward.review_bridge import (
    APPROVAL_PATH,
    DECISION_PATH,
    SESSION_HEADER,
    STATE_PATH,
    is_loopback_host,
    serve_review,
)
from filesteward.policy.paths import run_dir as policy_run_dir
from test_visualization_model import _write_valid_run


@pytest.fixture
def review_run() -> Iterator[Path]:
    path = policy_run_dir(f"test-review-{uuid.uuid4().hex[:10]}")
    _write_valid_run(path)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"error": raw}
        return exc.code, data


def test_non_loopback_bind_is_rejected(review_run: Path) -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        serve_review(review_run, bind_host="0.0.0.0", open_browser=False)


def test_bridge_security_and_decision_flow(review_run: Path) -> None:
    assert not is_loopback_host("0.0.0.0")
    result = serve_review(review_run, port=0, open_browser=False)
    try:
        origin = result.url.rstrip("/")
        # HTML is served with runtime injection and no durable token file.
        with urlopen(origin + "/", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert "decision-bridge-runtime" in html
        assert "NO BYTES REMOVED" in html
        assert "/api/v1/delete" not in html
        token = json.loads(
            html.split('id="decision-bridge-runtime">', 1)[1].split("</script>", 1)[0]
        )["sessionToken"]
        assert token
        assert token not in (review_run / "decision-chamber-state.json").read_text(
            encoding="utf-8"
        ) if (review_run / "decision-chamber-state.json").exists() else True

        # Find an UNKNOWN / HUMAN_REVIEW node from state by probing presentation ids via HTML.
        gate_id = None
        gate_payload = None
        import re

        for match in re.finditer(r'data-node-id="([^"]+)"', html):
            candidate = match.group(1)
            code, payload = _json(f"{origin}{STATE_PATH}?item_id={candidate}")
            assert code == 200
            if payload.get("evidence_disposition") in {"UNKNOWN", "HUMAN_REVIEW"}:
                gate_id = candidate
                gate_payload = payload
                break
        assert gate_id is not None
        assert gate_payload is not None
        assert "APPROVE_QUARANTINE" not in gate_payload["allowed_intents"]
        assert gate_payload["open_decision_scene"] == "GATE"
        legal_intent = (
            "RESCAN"
            if gate_payload["evidence_disposition"] == "UNKNOWN"
            else "DECLARE_REGENERABLE_CONTRACT"
        )

        # Wrong origin rejected.
        code, body = _json(
            f"{origin}{DECISION_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": gate_id,
                "intent": legal_intent,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": "http://evil.example",
                SESSION_HEADER: token,
            },
        )
        assert code == 403
        assert "Origin" in body["error"]

        # Missing token rejected.
        code, body = _json(
            f"{origin}{DECISION_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": gate_id,
                "intent": legal_intent,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
            },
        )
        assert code == 403

        # Legal gate decision persists without promoting evidence.
        code, body = _json(
            f"{origin}{DECISION_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": gate_id,
                "intent": legal_intent,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 200, body
        assert body["evidence_disposition"] in {"UNKNOWN", "HUMAN_REVIEW"}
        assert body["operator_decision"]["intent"] == legal_intent
        assert (review_run / "decision-chamber-state.json").is_file()
        durable = (review_run / "decision-chamber-state.json").read_text(encoding="utf-8")
        assert token not in durable

        # UNKNOWN cannot approve even if a client asks.
        unknown_id = None
        for match in re.finditer(r'data-node-id="([^"]+)"', html):
            candidate = match.group(1)
            code, payload = _json(f"{origin}{STATE_PATH}?item_id={candidate}")
            if payload.get("evidence_disposition") == "UNKNOWN":
                unknown_id = candidate
                break
        assert unknown_id is not None
        code, body = _json(
            f"{origin}{APPROVAL_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": unknown_id,
                "cleanup_plan_sha256": result.cleanup_plan_sha256,
                "action": "QUARANTINE",
                "confirm": True,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 400

        # CORS preflight rejected / not permissive.
        code, body = _json(
            f"{origin}{DECISION_PATH}",
            method="OPTIONS",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert code == 403

        # Find RECLAIM_PROVEN item present in cleanup-plan.
        reclaim_id = None
        for match in re.finditer(r'data-node-id="([^"]+)"', html):
            candidate = match.group(1)
            code, payload = _json(f"{origin}{STATE_PATH}?item_id={candidate}")
            if payload.get("evidence_disposition") == "RECLAIM_PROVEN":
                reclaim_id = candidate
                break
        assert reclaim_id is not None

        # Digest mismatch fails closed.
        code, body = _json(
            f"{origin}{APPROVAL_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": reclaim_id,
                "cleanup_plan_sha256": "0" * 64,
                "action": "QUARANTINE",
                "confirm": True,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 400

        # confirm=false fails closed.
        code, body = _json(
            f"{origin}{APPROVAL_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": reclaim_id,
                "cleanup_plan_sha256": result.cleanup_plan_sha256,
                "action": "QUARANTINE",
                "confirm": False,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 400

        # Absent item fails closed.
        code, body = _json(
            f"{origin}{APPROVAL_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": "missing-item",
                "cleanup_plan_sha256": result.cleanup_plan_sha256,
                "action": "QUARANTINE",
                "confirm": True,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 400

        # Exact approval stages quarantine without deleting bytes.
        code, body = _json(
            f"{origin}{APPROVAL_PATH}",
            method="POST",
            payload={
                "run_id": result.run_id,
                "item_id": reclaim_id,
                "cleanup_plan_sha256": result.cleanup_plan_sha256,
                "action": "QUARANTINE",
                "confirm": True,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                SESSION_HEADER: token,
            },
        )
        assert code == 200, body
        assert body["open_decision_scene"] == "STAGED"
        assert body["authorization_state"] == "APPROVED_FOR_ACTION"
        assert "NO BYTES REMOVED" in body["staged_copy"]
        assert (review_run / "approval-record.json").is_file()
        assert (review_run / "inventory.csv").exists()
    finally:
        result.server.shutdown()
        result.server.server_close()
