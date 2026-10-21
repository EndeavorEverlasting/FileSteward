"""Current evidence is explicit and reaches the existing owning bridge."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import time

import pytest

from filesteward import cli
from filesteward.ownership.current import CurrentOwnershipEvidence, ProbeCoverage
from filesteward.ownership.graph import build_ownership_graph
from filesteward.models import CleanupDisposition
from filesteward.visualization.judgment_script import resolve_scene_evidence


def test_current_cli_requires_explicit_root(monkeypatch, capsys):
    import filesteward.review_bridge as bridge
    called = Mock()
    monkeypatch.setattr(bridge, "run_review_until_interrupt", called)
    assert cli.main(["review", "unused", "--current-evidence"]) == cli.EXIT_INVALID
    assert "requires --scan-root" in capsys.readouterr().err
    called.assert_not_called()


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_resolver_is_opt_in(monkeypatch, tmp_path, explicit):
    import filesteward.review_bridge as bridge
    import filesteward.ownership.current as current
    served = Mock()
    resolver = Mock()
    factory = Mock(return_value=resolver)
    monkeypatch.setattr(current, "make_current_resolver", factory)
    monkeypatch.setattr(bridge, "run_review_until_interrupt", served)
    monkeypatch.setattr(cli, "resolve_run_dir_argument", lambda value: tmp_path)
    monkeypatch.setattr(cli, "prove_run_dir_under_runtime", lambda value: value)
    args = ["review", "unused", "--no-browser", "--scan-root", str(tmp_path)]
    if explicit:
        args.append("--current-evidence")
    assert cli.main(args) == cli.EXIT_OK
    kwargs = served.call_args.kwargs
    if explicit:
        factory.assert_called_once_with(tmp_path)
        assert kwargs["ownership_resolver"] is resolver
    else:
        factory.assert_not_called()
        assert "ownership_resolver" not in kwargs


def test_interrupt_wrapper_forwards_exact_resolver(monkeypatch, tmp_path):
    import filesteward.review_bridge as bridge
    thread = Mock()
    thread.is_alive.return_value = False
    result = SimpleNamespace(thread=thread, server=Mock())
    serve = Mock(return_value=result)
    resolver = Mock()
    monkeypatch.setattr(bridge, "serve_review", serve)
    bridge.run_review_until_interrupt(tmp_path, scan_root=tmp_path, ownership_resolver=resolver)
    assert serve.call_args.kwargs["ownership_resolver"] is resolver
    resolver.assert_not_called()


def test_probe_failures_reach_existing_attribution_scene_without_authority():
    evidence = CurrentOwnershipEvidence(build_ownership_graph(), False, time.time(), coverage=(
        ProbeCoverage("service", False, "native_service_probe", ("ACCESS_DENIED",)),
        ProbeCoverage("repository", False, "repository_adapter", ("ANCESTOR_CONTEXT_UNRESOLVED",)),
    ))
    result = resolve_scene_evidence("C:/synthetic/item", CleanupDisposition.HUMAN_REVIEW, evidence)
    assert result["scene_id"] == "ATTRIBUTION_RESOLVE"
    assert result["raw_delete_eligible"] is False
    assert "service" in result["missing_fact"] and "repository" in result["missing_fact"]
    assert "ACCESS_DENIED" in result["trace"][0]["finding"]
    assert result["probe_coverage"][0]["gaps"] == ["ACCESS_DENIED"]
    assert "native_service_probe" in result["safe_probes_attempted"]
    assert "RECLAIM_GENERATED_OUTPUT" not in result["value_actions"]


def test_default_launch_factory_is_lazy_and_uses_native_collector_seam(tmp_path, monkeypatch):
    from filesteward import launch
    from filesteward.policy import paths
    from filesteward.ownership import current
    from test_launch_current_review import start, finished
    runtime = tmp_path / "private-runtime/var"
    (runtime / "runs").mkdir(parents=True)
    root = tmp_path / "synthetic-folder"
    root.mkdir()
    (root / "fixture.txt").write_text("synthetic", encoding="utf-8")
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    calls = []
    def native(root, target):
        calls.append((root, target))
        return current.ProbeResult(False, "mocked_native", ("SYNTHETIC_DOMAIN_GAP",))
    monkeypatch.setattr(current, "_registry", native)
    monkeypatch.setattr(current, "_repositories", native)
    session, thread = launch.start_server(runtime)
    try:
        assert calls == []
        assert start(session, root)[0] == 202
        result = finished(session)
        assert result["state"] in {"READY", "PARTIAL"}
        assert result["ownership_complete"] is False
        assert calls == [(root, root), (root, root)]
        session.open_review(result["run_id"])
        # Opening the service may resolve initial current scene state. The
        # important distinction is that the stored resolver is the live owner.
        original = session.current_runs[result["run_id"]][2]
        assert isinstance(original, current.CurrentResolver)
        prior = len(calls)
        evidence = original(str(root / "fixture.txt"))
        assert len(calls) == prior + 2
        assert not evidence.adapters_complete
        assert "review_snapshot" not in {c.domain for c in evidence.coverage}
    finally:
        session.server.shutdown(); session.server.server_close(); session.close()
        thread.join(timeout=3)


def test_current_cli_does_not_infer_relative_scope(monkeypatch, capsys):
    import filesteward.review_bridge as bridge
    called = Mock()
    monkeypatch.setattr(bridge, "run_review_until_interrupt", called)
    assert cli.main(["review", "unused", "--current-evidence", "--scan-root", "relative"]) == cli.EXIT_INVALID
    assert "absolute --scan-root" in capsys.readouterr().err
    called.assert_not_called()


@pytest.mark.parametrize("source_kind,is_sample", [(None,True),(None,False),("native-current",False)])
def test_cli_cannot_upgrade_launcher_capture(tmp_path, monkeypatch, capsys, source_kind, is_sample):
    import json
    import filesteward.review_bridge as bridge
    import filesteward.ownership.current as current
    marker = {"schema_version":"filesteward.launch-run/v1", "is_sample":is_sample}
    if source_kind:
        marker["source_kind"] = source_kind
    (tmp_path / ".launch-run.json").write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.setattr(cli, "resolve_run_dir_argument", lambda value: tmp_path)
    monkeypatch.setattr(cli, "prove_run_dir_under_runtime", lambda value: value)
    served, factory = Mock(), Mock()
    monkeypatch.setattr(bridge, "run_review_until_interrupt", served)
    monkeypatch.setattr(current, "make_current_resolver", factory)
    assert cli.main(["review", "unused", "--scan-root", str(tmp_path), "--current-evidence"]) == cli.EXIT_INVALID
    assert "stays observational" in capsys.readouterr().err
    served.assert_not_called(); factory.assert_not_called()
    assert cli.main(["review", "unused", "--scan-root", str(tmp_path)]) == cli.EXIT_OK
    assert served.call_args.kwargs["observation_only"] is True


def test_interrupt_wrapper_preserves_observation_boundary(tmp_path, monkeypatch):
    import filesteward.review_bridge as bridge
    thread = Mock(); thread.is_alive.return_value = False
    result = SimpleNamespace(thread=thread, server=Mock())
    serve = Mock(return_value=result)
    monkeypatch.setattr(bridge, "serve_review", serve)
    bridge.run_review_until_interrupt(tmp_path, observation_only=True)
    assert serve.call_args.kwargs["observation_only"] is True
