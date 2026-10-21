"""Explicit browser admission uses the canonical scanner on synthetic folders only."""
import json
import os
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


def test_current_result_keeps_primary_action_before_collapsed_diagnostics(current_service):
    import re
    session, _, _ = current_service
    status, _, html = request(session.origin, "GET", "/")
    assert status == 200
    assert re.search(r'<div[^>]*id="scan-result"[^>]*role="status"[^>]*tabindex="-1"[^>]*></div>', html)
    assert re.search(r'<details id="ownership-checks" hidden><summary id="ownership-summary">Ownership checks</summary><ul id="ownership-gaps"></ul></details>', html)
    assert html.index('id="open-current"') < html.index('id="ownership-checks"')
    assert "byId('scan-result').append(gaps)" not in html
    assert "byId('ownership-checks').open = false" in html
    assert "String(record.domain || 'ownership').replace(/_/g, ' ')" in html
    assert "byId('scan-result').focus()" in html
    assert "Ownership checks \\u2014 " in html


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
    assert bridge_calls[0]["ownership_resolver"].delegate is unresolved_ownership
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

    def partial_run(*args, **kwargs):
        kwargs["scan_deps"] = ScanDeps(scandir=denied)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(launch, "CleanupRun", partial_run)
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
    assert observed[0]["ownership_resolver"].delegate is current


def test_root_parent_replaced_after_admission_aborts_before_scanner(current_service, tmp_path, monkeypatch):
    session, runtime, _ = current_service
    parent = tmp_path / "admitted-parent"
    source = parent / "synthetic"
    source.mkdir(parents=True)
    (source / "original.txt").write_text("synthetic original")

    def replaced_factory(root):
        parent.rename(tmp_path / "preserved-original-parent")
        source.mkdir(parents=True)
        (source / "outside-scope.txt").write_text("synthetic replacement must not be observed")
        return unresolved_ownership

    session.resolver_factory = replaced_factory
    monkeypatch.setattr(launch, "CleanupRun", lambda *args, **kwargs:
        pytest.fail("Canonical scanner must not run against a substituted admitted root"))
    assert start(session, source)[0] == 202
    result = finished(session)
    assert result["state"] == "ERROR"
    assert "ancestor changed" in result["message"]
    assert not list((runtime / "runs").iterdir())
    assert not session.current_runs


@pytest.mark.skipif(os.name != "nt", reason="Windows native directory pin proof")
def test_windows_scan_pin_blocks_ancestor_replacement_until_read_finishes(tmp_path):
    parent = tmp_path / "synthetic-parent"
    source = parent / "synthetic"
    source.mkdir(parents=True)
    scope = launch.CurrentScanScope(source)
    with scope.pinned():
        with pytest.raises(OSError):
            parent.rename(tmp_path / "replacement-destination")
        scope.validate()
    # No leaked handles: the operator's directory becomes renameable again.
    parent.rename(tmp_path / "replacement-destination")


def test_stop_reservation_rejects_new_job_without_invoking_factory(current_service, tmp_path, monkeypatch):
    session, runtime, calls = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    session.reserve_stop()
    assert session.stopping is True
    assert not session.scan_lock.locked()
    monkeypatch.setattr(launch, "CleanupRun", lambda *args, **kwargs: pytest.fail("Stopping app must not scan"))
    status, _, result = start(session, source)
    assert status == 400
    assert "closing" in result["error"]
    assert calls == []
    assert session.scan_job is None
    assert not session.scan_lock.locked()
    assert not list((runtime / "runs").iterdir())


def test_active_scan_rejects_stop_then_shutdown_prevents_followup_scan(current_service, tmp_path):
    session, _, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    entered, release = threading.Event(), threading.Event()

    def paused_factory(root):
        entered.set()
        assert release.wait(4)
        return unresolved_ownership

    session.resolver_factory = paused_factory
    assert start(session, source)[0] == 202
    assert entered.wait(2)
    try:
        status, _, result = request(session.origin, "POST", "/api/v1/launch/stop", {}, authorized(session))
        assert status == 400
        assert "still being read" in result["error"]
        assert session.stopping is False
    finally:
        release.set()
    assert finished(session)["state"] == "EMPTY"
    session.reserve_stop()
    assert start(session, source)[0] == 400


def test_stop_wins_between_root_admission_and_scan_reservation(current_service, tmp_path, monkeypatch):
    session, runtime, calls = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    admitted, release = threading.Event(), threading.Event()
    original = session.admit_scan_root

    def paused_admission(raw):
        root = original(raw)
        admitted.set()
        assert release.wait(4)
        return root

    monkeypatch.setattr(session, "admit_scan_root", paused_admission)
    responses = []
    requester = threading.Thread(target=lambda: responses.append(start(session, source)))
    requester.start()
    assert admitted.wait(2)
    try:
        session.reserve_stop()
    finally:
        release.set()
    requester.join(timeout=3)
    assert not requester.is_alive()
    assert responses[0][0] == 400
    assert "closing" in responses[0][2]["error"]
    assert calls == []
    assert session.scan_job is None
    assert not list((runtime / "runs").iterdir())


@pytest.mark.parametrize("traversal", ["protection", "inventory"])
@pytest.mark.parametrize("swap_at", ["open", "next"])
def test_scope_breach_aborts_both_canonical_traversals(current_service, tmp_path, monkeypatch, traversal, swap_at):
    session, runtime, _ = current_service
    source = tmp_path / "synthetic"
    source.mkdir()
    (source / "synthetic.txt").write_text("unchanged")
    original_scandir = launch.os.scandir
    original_link_check = launch.is_symlink_or_reparse
    state = {"root_calls": 0, "replaced": False}
    target_call = 1 if traversal == "protection" else 2

    def link_check(path):
        return (Path(path) == source.parent and state["replaced"]) or original_link_check(path)

    class SwappingIterator:
        def __init__(self, iterator):
            self.iterator = iterator

        def __next__(self):
            entry = next(self.iterator)
            state["replaced"] = True
            return entry

        def close(self):
            self.iterator.close()

    def swapping_scandir(path):
        iterator = original_scandir(path)
        if Path(path) == source:
            state["root_calls"] += 1
            if state["root_calls"] == target_call:
                if swap_at == "open":
                    state["replaced"] = True
                else:
                    return SwappingIterator(iterator)
        return iterator

    monkeypatch.setattr(launch, "is_symlink_or_reparse", link_check)
    monkeypatch.setattr(launch.os, "scandir", swapping_scandir)
    assert start(session, source)[0] == 202
    result = finished(session)
    assert state["root_calls"] == target_call
    assert result["state"] == "ERROR", result
    assert "ancestor changed" in result["message"]
    assert not list((runtime / "runs").glob("*/inventory.csv"))
    assert not list((runtime / "runs").glob("*/.launch-run.json"))
    assert not session.current_runs


@pytest.mark.parametrize("opened", [False, True])
def test_completed_review_retains_admitted_root_identity_for_live_evidence(current_service, tmp_path, opened):
    from filesteward.review_bridge import STATE_PATH
    from filesteward.inventory.scan import stable_item_id
    session, _, _ = current_service
    parent = tmp_path / "original-parent"
    source = parent / "synthetic"
    source.mkdir(parents=True)
    (source / "record.txt").write_text("original synthetic fixture")
    observed = []

    def provider(path):
        observed.append(path)
        return unresolved_ownership(path)

    session.resolver_factory = lambda root: provider
    assert start(session, source)[0] == 202
    identifier = finished(session)["run_id"]
    if opened:
        session.open_review(identifier)
        service = session.reviews[identifier]
        assert request(service.url.rstrip("/"), "GET", STATE_PATH + "?item_id=" + stable_item_id("record.txt"))[0] == 200
    observed.clear()
    parent.rename(tmp_path / "preserved-original-parent")
    source.mkdir(parents=True)
    (source / "record.txt").write_text("outside original admission")
    resolver = session.current_runs[identifier][2]
    with pytest.raises(ValueError, match="ancestor changed"):
        resolver(str(source / "record.txt"))
    with pytest.raises(ValueError, match="ancestor changed"):
        with resolver.read_batch():
            resolver(str(source / "record.txt"))
    with pytest.raises(ValueError, match="ancestor changed"):
        session.open_review(identifier)
    if opened:
        status, _, state = request(service.url.rstrip("/"), "GET", STATE_PATH + "?item_id=" + stable_item_id("record.txt"))
        assert status in {200, 400}
        assert ("unavailable" in json.dumps(state).lower() if status == 200
            else "ancestor changed" in state["error"])
    assert observed == [], "Original-root replacement must not reach any live provider"


def test_scoped_live_resolver_preserves_fresh_calls_and_delegated_batch(tmp_path):
    from contextlib import contextmanager
    source = tmp_path / "synthetic"
    source.mkdir()
    path = str(source)
    events = []

    class FreshResolver:
        def __call__(self, raw):
            events.append(("fresh", raw))
            return unresolved_ownership(raw)

        @contextmanager
        def read_batch(self):
            events.append("batch-enter")
            try:
                yield self
            finally:
                events.append("batch-exit")

    original = FreshResolver()
    wrapped = launch.ScopedCurrentResolver(original, launch.CurrentScanScope(source))
    assert wrapped.delegate is original
    assert events == []
    with wrapped.read_batch() as current:
        assert current is wrapped
        current(path)
        current(path)
    assert events == ["batch-enter", ("fresh", path), ("fresh", path), "batch-exit"]
    wrapped(path)
    assert events[-1] == ("fresh", path), "The scope guard must not cache current evidence"
    plain = launch.ScopedCurrentResolver(unresolved_ownership, wrapped.scope)
    with plain.read_batch() as current:
        assert current is plain
        assert current(path).adapters_complete is False
