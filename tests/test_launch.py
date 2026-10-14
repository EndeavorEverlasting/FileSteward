"""Real loopback launch integration; all runtime evidence is synthetic."""
import base64
import http.client
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

import pytest

from filesteward import launch
from filesteward.policy import paths
from filesteward.review_bridge import (SESSION_HEADER, STATE_PATH, ReviewBridge,
    DecisionRequest, DecisionBridgeIntent, ApprovalRequest, serve_review)
from filesteward.approval import ApprovalAction
from filesteward.sample import write_sample_run


@pytest.fixture
def launch_service(tmp_path, monkeypatch):
    runtime = tmp_path / "private-runtime" / "var"
    (runtime / "runs").mkdir(parents=True)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    monkeypatch.setattr(launch, "runtime_root", lambda: runtime)
    monkeypatch.setattr(launch, "prepare_runtime", lambda: runtime)
    from filesteward.run import CleanupRun
    def no_scan(*args, **kwargs):
        pytest.fail("launch must not execute any scanner")
    monkeypatch.setattr(CleanupRun, "execute", no_scan)
    session, thread = launch.start_server(runtime)
    try:
        yield session, thread, runtime
    finally:
        session.server.shutdown()
        session.server.server_close()
        session.close()
        thread.join(timeout=3)


def request(origin, method, path, payload=None, headers=None, raw=None):
    parsed = urlparse(origin)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    supplied = {"Content-Type": "application/json"} if method == "POST" else {}
    supplied.update(headers or {})
    body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    try:
        connection.request(method, path, body=body, headers=supplied)
        response = connection.getresponse()
        status, response_headers, data = response.status, dict(response.getheaders()), response.read()
        if "application/json" in response_headers.get("Content-Type", ""):
            data = json.loads(data)
        else:
            data = data.decode()
        return status, response_headers, data
    finally:
        connection.close()


def authorized(session, **overrides):
    return {"Origin": session.origin, SESSION_HEADER: session.session_token, **overrides}


def uploaded_sample(tmp_path):
    source = write_sample_run(tmp_path / "captured-synthetic", "captured-example")
    return [{"name": name, "data": base64.b64encode((source / name).read_bytes()).decode()}
            for name in sorted(launch.IMPORT_FILES)]


def test_welcome_and_health_are_real_loopback_without_runtime_work(launch_service):
    session, _, runtime = launch_service
    assert urlparse(session.origin).hostname == "127.0.0.1"
    status, headers, html = request(session.origin, "GET", "/")
    assert status == 200 and "text/html" in headers["Content-Type"]
    assert session.session_token in html
    assert "__FILESTEWARD_RUNTIME__" not in html
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    status, _, data = request(session.origin, "GET", "/api/v1/launch/health")
    assert status == 200 and data["app_id"] == "filesteward"
    assert data["instance_id"] == session.instance_id
    assert not list((runtime / "runs").iterdir())


@pytest.mark.parametrize("headers", [{"Host": "attacker.invalid"}, {"Host": "localhost:1"}])
def test_host_binding_rejects_other_addresses(launch_service, headers):
    session, _, _ = launch_service
    assert request(session.origin, "GET", "/api/v1/launch/state", headers=headers)[0] == 403


@pytest.mark.parametrize("kind", ["missing", "origin", "token", "host"])
def test_mutation_guard_rejects_wrong_identity_without_effect(launch_service, kind):
    session, thread, runtime = launch_service
    headers = authorized(session)
    if kind == "missing":
        headers = {}
    elif kind == "origin":
        headers["Origin"] = "https://attacker.invalid"
    elif kind == "token":
        headers[SESSION_HEADER] = "invalid"
    else:
        headers["Host"] = "attacker.invalid"
    status, response_headers, _ = request(session.origin, "POST", "/api/v1/launch/demo", {}, headers)
    assert status == 403
    assert "Access-Control-Allow-Origin" not in response_headers
    assert thread.is_alive()
    assert not list((runtime / "runs").iterdir())


def test_preflight_and_unauthorized_stop_cannot_stop_service(launch_service):
    session, thread, _ = launch_service
    assert request(session.origin, "OPTIONS", "/api/v1/launch/stop")[0] == 403
    assert request(session.origin, "POST", "/api/v1/launch/stop", {})[0] == 403
    assert request(session.origin, "GET", "/api/v1/launch/health")[0] == 200
    assert thread.is_alive()


def test_sample_is_explicit_labeled_read_only_and_reuses_managed_review(launch_service):
    session, _, runtime = launch_service
    status, _, result = request(session.origin, "POST", "/api/v1/launch/demo", {}, authorized(session))
    assert status == 200
    path = urlparse(result["url"]).path
    status, headers, _ = request(session.origin, "GET", path)
    assert status == 302
    review_origin = headers["Location"].rstrip("/")
    status, _, html = request(review_origin, "GET", "/")
    assert status == 200 and "no files on this computer were scanned" in html
    assert "Storage figures are illustrative" in html
    status, _, state = request(review_origin, "GET", STATE_PATH + "?item_id=sample-archive")
    assert status == 200
    assert "DELETE_PERMANENTLY" not in state["allowed_intents"]
    assert "APPROVE_QUARANTINE" not in state["allowed_intents"]
    assert state["authorization_state"] == "UNAPPROVED"
    assert state["observation_only"] is True
    assert "RESCAN" not in state["allowed_intents"]
    assert session.sample() == result["url"] and len(session.reviews) == 1
    assert len(session.recent()) == 1 and session.recent()[0]["is_sample"]
    assert not list(runtime.rglob("delete-approval.json"))
    assert not list(runtime.rglob("delete-receipt.json"))
    assert not any(session.session_token in file.read_text(encoding="utf-8", errors="ignore")
                   for file in runtime.rglob("*") if file.is_file())


def test_partial_sample_target_is_preserved_and_fresh_sample_can_open(launch_service):
    session, _, runtime = launch_service
    identifier = "sample-" + launch.__version__.replace(".", "-")
    partial = runtime / "runs" / identifier
    partial.mkdir()
    sentinel = partial / "interrupted.txt"
    sentinel.write_text("preserve interrupted proof", encoding="utf-8")
    opened = session.sample()
    fresh_id = urlparse(opened).path.removeprefix("/review/")
    assert fresh_id.startswith(identifier + "-") and fresh_id != identifier
    assert sentinel.read_text() == "preserve interrupted proof"
    assert not (partial / ".launch-run.json").exists()
    assert len(session.recent()) == 1 and session.recent()[0]["id"] == fresh_id


def test_import_accepts_only_observational_files_and_preserves_readonly_boundary(launch_service, tmp_path):
    session, _, runtime = launch_service
    files = uploaded_sample(tmp_path)
    status, _, result = request(session.origin, "POST", "/api/v1/launch/import", {"files": files}, authorized(session))
    assert status == 200
    status, headers, _ = request(session.origin, "GET", urlparse(result["url"]).path)
    assert status == 302
    review_origin = headers["Location"].rstrip("/")
    status, _, html = request(review_origin, "GET", "/")
    assert status == 200 and "Imported captured evidence" in html
    assert "not a new scan or current deletion authority" in html
    status, _, state = request(review_origin, "GET", STATE_PATH + "?item_id=sample-archive")
    assert status == 200 and "DELETE_PERMANENTLY" not in state["allowed_intents"]
    assert "APPROVE_QUARANTINE" not in state["allowed_intents"]
    assert state["authorization_state"] == "UNAPPROVED"
    assert state["observation_only"] is True
    assert "RESCAN" not in state["allowed_intents"]
    assert len(session.recent()) == 1 and not session.recent()[0]["is_sample"]
    assert not list(runtime.rglob("approval-record.json"))
    assert not list(runtime.rglob("delete-approval.json"))


@pytest.mark.parametrize("bad_id", [None, "", "..", "../foreign", "x/y", "x\\y", "x" * 65])
def test_open_refuses_invalid_saved_review_identity(launch_service, bad_id):
    session, _, runtime = launch_service
    status, _, result = request(session.origin, "POST", "/api/v1/launch/open", {"run_id": bad_id}, authorized(session))
    assert status == 400 and result["error"]
    assert not list((runtime / "runs").iterdir())


@pytest.mark.parametrize("variant", ["missing", "duplicate", "approval", "traversal", "base64"])
def test_import_refuses_bad_file_set_before_creating_run(launch_service, tmp_path, variant):
    session, _, runtime = launch_service
    files = uploaded_sample(tmp_path)
    if variant == "missing":
        files.pop()
    elif variant == "duplicate":
        files[-1] = files[0]
    elif variant == "approval":
        files[-1] = {"name": "delete-approval.json", "data": "e30="}
    elif variant == "traversal":
        files[-1]["name"] = "../run.json"
    else:
        files[-1]["data"] = "not-base64!"
    status, _, result = request(session.origin, "POST", "/api/v1/launch/import", {"files": files}, authorized(session))
    assert status == 400 and result["error"]
    assert not list((runtime / "runs").iterdir())


def test_malformed_evidence_is_not_added_to_recent_reviews(launch_service, tmp_path):
    session, _, runtime = launch_service
    files = uploaded_sample(tmp_path)
    next(file for file in files if file["name"] == "inventory.csv")["data"] = base64.b64encode(b"invalid,csv\n").decode()
    status, _, result = request(session.origin, "POST", "/api/v1/launch/import", {"files": files}, authorized(session))
    assert status == 400 and "validation" in result["error"]
    assert session.recent() == [] and session.reviews == {}
    assert list((runtime / "runs").iterdir()) == []


@pytest.mark.parametrize("marker_payload", [["not a marker object"], {"schema_version": "wrong-schema"}])
def test_malformed_saved_marker_is_skipped_and_refused(launch_service, marker_payload):
    session, _, runtime = launch_service
    target = write_sample_run(runtime / "runs/malformed-marker", "malformed-marker")
    (target / ".launch-run.json").write_text(json.dumps(marker_payload), encoding="utf-8")
    assert session.recent() == []
    status, _, refusal = request(session.origin, "GET", "/review/malformed-marker")
    assert status == 400 and refusal["error"]
    assert session.reviews == {}


@pytest.mark.parametrize("raw,headers", [(b"[1]", {}), (b"not JSON", {}), (b"{}", {"Content-Type": "text/plain"})])
def test_json_shape_and_content_type_are_required(launch_service, raw, headers):
    session, _, _ = launch_service
    assert request(session.origin, "POST", "/api/v1/launch/demo", headers=authorized(session, **headers), raw=raw)[0] == 400


def test_session_close_stops_all_managed_review_servers(launch_service):
    session, _, _ = launch_service
    session.sample()
    reviews = list(session.reviews.values())
    session.close()
    assert reviews and all(not review.thread.is_alive() for review in reviews)


def test_authorized_stop_stops_launch_listener(launch_service):
    session, thread, _ = launch_service
    status, _, result = request(session.origin, "POST", "/api/v1/launch/stop", {}, authorized(session))
    assert status == 200 and result["stopped"]
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_observation_only_never_admits_captured_scope_or_resolver(launch_service, monkeypatch):
    session, _, runtime = launch_service
    target = write_sample_run(runtime / "runs" / "captured", "captured")
    metadata_path = target / "run.json"
    captured = json.loads(metadata_path.read_text())
    captured["scan_root"] = r"C:\not-authorized-captured-scope"
    metadata_path.write_text(json.dumps(captured))
    def no_resolver(*args):
        pytest.fail("observation-only mode must not invoke live ownership adapters")
    bridge = ReviewBridge.open(target, observation_only=True, ownership_resolver=no_resolver)
    assert bridge.scan_root is None
    state = bridge.state_payload("sample-archive")
    assert state["observation_only"] is True
    assert state["authorization_state"] == "UNAPPROVED"
    assert "observation-only" in state["delete_unavailable_reason"]
    assert set(state["allowed_intents"]) <= {"KEEP", "REVIEW_LATER"}
    # Captured provenance remains historical; it never becomes a current root.
    assert json.loads(metadata_path.read_text())["scan_root"] == captured["scan_root"]
    with pytest.raises(ValueError, match="Observation-only"):
        bridge.set_scan_root(captured["scan_root"])
    for intent in (DecisionBridgeIntent.RESCAN, DecisionBridgeIntent.DECLARE_REGENERABLE_CONTRACT,
                   DecisionBridgeIntent.RECLAIM_GENERATED_OUTPUT):
        with pytest.raises(ValueError, match="Observation-only"):
            bridge.record_decision(DecisionRequest("captured", "sample-archive", intent))
    with pytest.raises(ValueError, match="Observation-only"):
        bridge.record_approval(ApprovalRequest("captured", "sample-archive", bridge.cleanup_plan_sha256,
                                              ApprovalAction.QUARANTINE, True))
    with pytest.raises(ValueError, match="Observation-only"):
        bridge.execute_permanent_delete_ui("captured", ["sample-archive"], captured["scan_root"], "DELETE_PERMANENTLY")
    assert not list(target.glob("*approval*.json"))
    assert not (target / "delete-manifest.json").exists()
    positive = bridge.record_decision(DecisionRequest("captured", "sample-archive", DecisionBridgeIntent.KEEP))
    assert positive["observation_only"]
    assert bridge._is_completed_item("sample-archive")


def test_observation_only_http_refuses_authorized_execution_requests(launch_service):
    _, _, runtime = launch_service
    target = write_sample_run(runtime / "runs/http-observation", "http-observation")
    service = serve_review(target, observation_only=True, open_browser=False)
    try:
        _, _, html = request(service.url.rstrip("/"), "GET", "/")
        import re
        runtime_json = json.loads(re.search(r'<script[^>]*id="decision-bridge-runtime"[^>]*>(.*?)</script>', html, re.S).group(1))
        headers = {"Origin": service.url.rstrip("/"), SESSION_HEADER: runtime_json["sessionToken"]}
        paths_and_payloads = [
            ("/api/v1/decision", {"run_id": "http-observation", "item_id": "sample-archive", "intent": "RESCAN"}),
            ("/api/v1/approval", {"run_id": "http-observation", "item_id": "sample-archive",
                "cleanup_plan_sha256": service.cleanup_plan_sha256, "action": "QUARANTINE", "confirm": True}),
            ("/api/v1/delete", {"run_id": "http-observation", "item_id": "sample-archive",
                "scan_root": r"C:\not-authorized-captured-scope", "irreversible_confirmation": "DELETE_PERMANENTLY"}),
        ]
        for path, payload in paths_and_payloads:
            status, _, refusal = request(service.url.rstrip("/"), "POST", path, payload, headers)
            assert status == 400 and "Observation-only" in refusal["error"]
        assert not list(target.glob("*approval*.json"))
        assert not (target / "delete-manifest.json").exists()
    finally:
        service.server.shutdown()
        service.server.server_close()
        service.thread.join(timeout=3)


def test_main_manages_launch_and_review_shutdown(tmp_path, monkeypatch):
    runtime = tmp_path / "managed-runtime" / "var"
    (runtime / "runs").mkdir(parents=True)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    monkeypatch.setattr(launch, "prepare_runtime", lambda: runtime)
    failures = []
    result = []
    def run_main():
        try:
            result.append(launch.main(["--no-browser"]))
        except Exception as error:
            failures.append(error)
    thread = threading.Thread(target=run_main)
    thread.start()
    deadline = time.monotonic() + 5
    metadata = runtime / "launch/instance.json"
    while not metadata.exists() and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.02)
    try:
        assert metadata.exists() and not failures
        origin = json.loads(metadata.read_text())["origin"]
        status, _, html = request(origin, "GET", "/")
        assert status == 200
        # The process-only token is intentionally obtained through its served
        # bootstrap JSON, not a persisted runtime token file.
        import re
        runtime_json = json.loads(re.search(r'<script[^>]*id="launch-runtime"[^>]*>(.*?)</script>', html, re.S).group(1))
        headers = {"Origin": origin, SESSION_HEADER: runtime_json["sessionToken"]}
        status, _, opened = request(origin, "POST", "/api/v1/launch/demo", {}, headers)
        assert status == 200
        status, redirect, _ = request(origin, "GET", urlparse(opened["url"]).path)
        assert status == 302
        assert request(origin, "POST", "/api/v1/launch/stop", {}, headers)[0] == 200
        thread.join(timeout=5)
        assert not thread.is_alive() and result == [0] and not failures
        review = urlparse(redirect["Location"])
        connection = http.client.HTTPConnection(review.hostname, review.port, timeout=1)
        try:
            with pytest.raises(OSError):
                connection.connect()
        finally:
            connection.close()
    finally:
        if thread.is_alive() and metadata.exists():
            # Recover the process-only token from the same served bootstrap;
            # never interrupt unrelated services or leave this fixture running.
            try:
                request(origin, "POST", "/api/v1/launch/stop", {}, headers)
            except (OSError, UnboundLocalError):
                pass
            thread.join(timeout=5)
