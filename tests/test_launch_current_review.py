"""Explicit browser admission uses the canonical scanner on synthetic folders only."""
import json
import threading
import time
from pathlib import Path

import pytest

from filesteward import launch
from filesteward.policy import paths
from filesteward.ownership.actions import unresolved_ownership
from test_launch import request, authorized, uploaded_sample


@pytest.fixture
def current_service(tmp_path, monkeypatch):
    runtime = tmp_path / "private-runtime" / "var"
    (runtime / "runs").mkdir(parents=True)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    monkeypatch.setattr(launch, "runtime_root", lambda: runtime)
    calls = []

    def factory(root):
        calls.append(root)
        return unresolved_ownership

    session, thread = launch.start_server(runtime, resolver_factory=factory)
    try:
        yield session, runtime, calls
    finally:
        deadline = time.monotonic() + 5
        while session.scan_lock.locked() and time.monotonic() < deadline:
            time.sleep(.01)
        session.server.shutdown()
        session.server.server_close()
        session.close()
        thread.join(timeout=3)


def start(session, root, **extra):
    return request(session.origin, "POST", "/api/v1/launch/current-scan",
        {"scan_root": str(root), **extra}, authorized(session))


def finished(session):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status, _, result = request(session.origin, "GET", "/api/v1/launch/current-scan")
        assert status == 200
        if result["state"] != "READING":
            return result
        time.sleep(.01)
    pytest.fail("bounded synthetic metadata scan did not finish")


def test_no_startup_scan_or_collector_construction(current_service):
    session, runtime, calls = current_service
    assert request(session.origin, "GET", "/")[0] == 200
    assert request(session.origin, "GET", "/api/v1/launch/current-scan")[2] == {"state": "IDLE"}
    assert calls == []
    assert not list((runtime / "runs").iterdir())


def test_explicit_metadata_scan_reaches_validated_active_bridge(current_service, tmp_path, monkeypatch):
    session, runtime, calls = current_service
    source = tmp_path / "synthetic-folder"
    source.mkdir()
    important = source / "record.txt"
    important.write_text("Synthetic data must remain unchanged")
    bridge_calls = []
    real_serve = launch.serve_review

    def observe(*args, **kwargs):
        bridge_calls.append(kwargs)
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(launch, "serve_review", observe)
    assert start(session, source)[0] == 202
    result = finished(session)
    assert result["state"] == "READY", result
    assert result["item_count"] == 1
    assert result["metadata_complete"] is True
    assert result["ownership_complete"] is False
    assert result["coverage"][0]["domain"] == "ownership"
    assert calls == [source]
    target = runtime / "runs" / result["run_id"]
    assert launch.validate_run(target) == []
    assert json.loads((target / "run.json").read_text())["root"] == str(source)
    marker = json.loads((target / ".launch-run.json").read_text())
    assert marker["source_kind"] == "native-current"
    assert marker["scan_root"] == str(source)
    status, _, opened = request(session.origin, "POST", "/api/v1/launch/open",
        {"run_id": result["run_id"]}, authorized(session))
    assert status == 200, opened
    assert opened["url"].startswith(session.origin)
    assert bridge_calls[0]["observation_only"] is False
    assert bridge_calls[0]["scan_root"] == source
    assert bridge_calls[0]["ownership_resolver"] is unresolved_ownership
    assert important.read_text() == "Synthetic data must remain unchanged"
    assert not list(target.glob("*approval*"))
    report = session.reviews[result["run_id"]].report_path
    assert "Current folder metadata review" in report.read_text(encoding="utf-8")


def test_empty_folder_result_is_explicit(current_service, tmp_path):
    session, _, _ = current_service
    source = tmp_path / "empty-synthetic"
    source.mkdir()
    assert start(session, source)[0] == 202
    result = finished(session)
    assert result["state"] == "EMPTY"
    assert result["item_count"] == 0
    assert "no entries" in result["message"]


@pytest.mark.parametrize("raw", ["", "relative/folder", None, 17])
def test_invalid_root_never_invokes_collector(current_service, raw):
    session, _, calls = current_service
    status, _, _ = request(session.origin, "POST", "/api/v1/launch/current-scan",
        {"scan_root": raw}, authorized(session))
    assert status == 400
    assert calls == []


def test_missing_forbidden_and_linked_ancestors_refused(current_service, tmp_path, monkeypatch):
    session, _, calls = current_service
    forbidden = tmp_path / "OneDrive" / "synthetic"
    forbidden.mkdir(parents=True)
    assert start(session, forbidden)[0] == 400
    assert start(session, tmp_path / "missing")[0] == 400
    source = tmp_path / "linked-parent" / "synthetic"
    source.mkdir(parents=True)
    original = launch.is_symlink_or_reparse
    monkeypatch.setattr(launch, "is_symlink_or_reparse", lambda p: Path(p) == source.parent or original(p))
    assert start(session, source)[0] == 400
    assert calls == []


def test_client_cannot_assert_eligibility_or_forge_source(current_service, tmp_path):
    session, _, calls = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    assert start(session, source, adapters_complete=True, source_kind="native-current")[0] == 400
    assert calls == []
    assert request(session.origin, "POST", "/api/v1/launch/current-scan", {"scan_root": str(source)})[0] == 403
    assert calls == []


def test_one_scan_at_a_time_and_failed_job_can_retry(current_service, tmp_path):
    session, _, _ = current_service
    entered, release = threading.Event(), threading.Event()
    source = tmp_path / "synthetic"
    source.mkdir()

    def failing_factory(root):
        entered.set()
        assert release.wait(3)
        raise RuntimeError("Synthetic bounded probe unavailable")

    session.resolver_factory = failing_factory
    assert start(session, source)[0] == 202
    assert entered.wait(2)
    assert start(session, source)[0] == 400
    release.set()
    result = finished(session)
    assert result["state"] == "ERROR"
    assert "Synthetic bounded probe unavailable" in result["message"]
    session.resolver_factory = lambda root: unresolved_ownership
    assert start(session, source)[0] == 202
    assert finished(session)["state"] == "EMPTY"


def test_partial_inventory_preserves_missing_metadata(current_service, tmp_path, monkeypatch):
    from filesteward.inventory.scan import ScanDeps
    session, _, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    real_run = launch.CleanupRun

    def denied(_root):
        raise PermissionError("synthetic read gap")

    monkeypatch.setattr(launch, "CleanupRun", lambda *args, **kwargs:
        real_run(*args, **kwargs, scan_deps=ScanDeps(scandir=denied)))
    assert start(session, source)[0] == 202
    result = finished(session)
    assert result["state"] == "PARTIAL"
    assert "nothing was assumed absent" in result["message"]


def test_sample_import_and_restarted_capture_never_upgrade(current_service, tmp_path, monkeypatch):
    session, runtime, calls = current_service
    bridge_calls = []
    real_serve = launch.serve_review

    def observe(*args, **kwargs):
        bridge_calls.append(kwargs)
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(launch, "serve_review", observe)
    session.sample()
    files = uploaded_sample(tmp_path)
    session.import_run(files)
    assert all(call["observation_only"] is True for call in bridge_calls)
    assert calls == []
    assert not session.current_runs
    source = tmp_path / "synthetic"
    source.mkdir()
    assert start(session, source)[0] == 202
    result = finished(session)
    # New process has no trusted admission binding: preserved native capture is
    # historical rather than silently authorizing probes on its source again.
    restarted = launch.LaunchSession(runtime, resolver_factory=lambda root: pytest.fail("historical capture must not probe"))
    restarted.origin = session.origin
    try:
        restarted.open_review(result["run_id"])
        assert bridge_calls[-1]["observation_only"] is True
    finally:
        restarted.close()


def test_current_marker_tampering_fails_closed(current_service, tmp_path):
    session, runtime, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    assert start(session, source)[0] == 202
    result = finished(session)
    marker_path = runtime / "runs" / result["run_id"] / ".launch-run.json"
    marker = json.loads(marker_path.read_text())
    marker["scan_root"] = str(tmp_path / "other-root")
    marker_path.write_text(json.dumps(marker))
    with pytest.raises(ValueError, match="binding changed"):
        session.open_review(result["run_id"])


@pytest.mark.parametrize("changed_file", [".launch-run.json", "run.json"])
def test_cached_review_revalidates_source_binding(current_service, tmp_path, changed_file):
    session, runtime, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    assert start(session, source)[0] == 202
    identifier = finished(session)["run_id"]
    session.open_review(identifier)
    # An unchanged cached review remains usable despite the bridge's legitimate
    # first-open persistence of the same root into run.json.
    session.open_review(identifier)
    changed = runtime / "runs" / identifier / changed_file
    data = json.loads(changed.read_text())
    data["root" if changed_file == "run.json" else "scan_root"] = str(tmp_path / "different")
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="binding changed"):
        session.open_review(identifier)


def test_snapshot_coverage_is_visible_but_original_resolver_reaches_bridge(current_service, tmp_path, monkeypatch):
    from dataclasses import dataclass
    from filesteward.ownership.actions import OwnershipEvidence

    @dataclass(frozen=True)
    class Coverage:
        domain: str
        complete: bool
        provenance: str
        gaps: tuple[str, ...]

    @dataclass(frozen=True)
    class CoveredEvidence(OwnershipEvidence):
        coverage: tuple = ()

    session, _, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    (source / "record.txt").write_text("synthetic")
    snapshots = []

    class Current:
        def __call__(self, path):
            return unresolved_ownership(path)

        def review_snapshot(self):
            snapshots.append(True)
            return lambda path: CoveredEvidence(unresolved_ownership(path).graph,
                coverage=(Coverage("scheduled_tasks", False, "synthetic_provider",
                    ("Task enumeration unavailable in this bounded fixture",)),))

    current = Current()
    session.resolver_factory = lambda root: current
    observed = []
    real_serve = launch.serve_review

    def serve(*args, **kwargs):
        observed.append(kwargs)
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(launch, "serve_review", serve)
    assert start(session, source)[0] == 202
    result = finished(session)
    assert result["metadata_complete"] is True
    assert result["ownership_complete"] is False
    assert len(result["coverage"]) == 1
    assert result["coverage"][0]["domain"] == "scheduled_tasks"
    assert "Task enumeration unavailable" in result["coverage"][0]["gaps"][0]
    assert snapshots == [True]
    session.open_review(result["run_id"])
    assert observed[0]["ownership_resolver"] is current
