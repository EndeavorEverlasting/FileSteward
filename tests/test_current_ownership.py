"""Current collection uses confined synthetic paths and injected native probes."""
from dataclasses import replace
import sys
import time
from types import SimpleNamespace

import pytest

from filesteward.models import CleanupDisposition
from filesteward.ownership import current
from filesteward.ownership.actions import plan_owner_actions
from filesteward.ownership.graph import OwnershipEdge


def complete_providers():
    return {domain: (lambda root, target: current.ProbeResult(True, "synthetic_complete"))
            for domain in current.DOMAINS}


def protected(path, owner="app", kind="APPLICATION", edge="INSTALLED_AT"):
    return OwnershipEdge(edge, str(path), kind, owner, owner, "synthetic", "strong", "APP_ACTIVE_REQUIRED")


def test_constructor_does_not_observe(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("constructor observed host")
    monkeypatch.setattr(current, "_registry", forbidden)
    monkeypatch.setattr(current, "_repositories", forbidden)
    monkeypatch.setattr(current.Path, "lstat", forbidden)
    monkeypatch.setattr(current, "time", forbidden)
    assert callable(current.make_current_resolver(tmp_path))


def test_missing_domains_are_explicit_and_never_delete_eligible(tmp_path):
    resolver = current.make_current_resolver(tmp_path, providers={})
    evidence = resolver(str(tmp_path))
    assert len(evidence.coverage) == len(current.DOMAINS)
    assert all(not c.complete and c.gaps for c in evidence.coverage)
    assert not evidence.adapters_complete
    assert not evidence.proofs
    assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.UNKNOWN


def test_complete_synthetic_coverage_without_owner_is_still_unknown(tmp_path):
    evidence = current.make_current_resolver(tmp_path, providers=complete_providers())(str(tmp_path))
    assert evidence.adapters_complete and evidence.fresh()
    assert not plan_owner_actions(str(tmp_path), evidence).raw_delete_eligible


@pytest.mark.parametrize("kind,edge", [("APPLICATION", "INSTALLED_AT"),
    ("SERVICE", "SERVICE_REFERENCES"), ("SCHEDULED_TASK", "TASK_REFERENCES"),
    ("REPOSITORY", "TRACKED_BY"), ("TOOLCHAIN", "TOOLCHAIN_REQUIRES")])
def test_known_protection_survives_missing_domains(tmp_path, kind, edge):
    provider = lambda root, target: current.ProbeResult(False, "partial", ("probe_gap",),
        edges=(protected(target, kind=kind, edge=edge),))
    evidence = current.make_current_resolver(tmp_path, providers={"application_installation": provider})(str(tmp_path))
    assert not evidence.adapters_complete
    assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.PROTECTED


def test_concurrent_owners_and_probe_exception_preserve_protection(tmp_path):
    def failure(*args):
        raise PermissionError("private host message must not escape")
    providers = complete_providers()
    providers["service"] = failure
    providers["application_installation"] = lambda root, target: current.ProbeResult(
        True, "synthetic", edges=(protected(target, "app"), protected(target, "repo", "REPOSITORY", "TRACKED_BY")))
    evidence = current.make_current_resolver(tmp_path, providers=providers)(str(tmp_path))
    assert len(evidence.graph.edges) == 2
    assert not evidence.adapters_complete
    assert next(c for c in evidence.coverage if c.domain == "service").gaps == ("PermissionError",)
    assert "private host" not in repr(evidence)
    assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.PROTECTED


@pytest.mark.parametrize("escape", ["outside", "relative", "dotdot"])
def test_scope_failures_precede_providers(tmp_path, escape):
    calls = []
    resolver = current.make_current_resolver(tmp_path, providers={"repository": lambda *args: calls.append(args)})
    raw = {"outside": str(tmp_path.parent), "relative": "relative", "dotdot": str(tmp_path / "..")}[escape]
    evidence = resolver(raw)
    assert not calls and not evidence.adapters_complete
    assert evidence.coverage[0].domain == "scope"


def test_reparse_failure_precedes_providers(tmp_path, monkeypatch):
    actual = current.Path.lstat
    def linked(path):
        info = actual(path)
        if path == tmp_path:
            class Link:
                st_mode = info.st_mode
                st_file_attributes = 0x400
            return Link()
        return info
    monkeypatch.setattr(current.Path, "lstat", linked)
    evidence = current.make_current_resolver(tmp_path, providers={})(str(tmp_path))
    assert evidence.coverage[0].gaps == ("LINK_OR_REPARSE_COMPONENT",)


def test_outside_provider_edge_rejected_without_erasing_good_edge(tmp_path):
    provider = lambda root, target: current.ProbeResult(True, "synthetic", edges=(
        protected(target), protected(tmp_path.parent, "outside")))
    evidence = current.make_current_resolver(tmp_path, providers={"service": provider})(str(tmp_path))
    assert [e.owner_id for e in evidence.graph.edges] == ["app"]
    assert "PROVIDER_EDGE_OUTSIDE_SAFE_SCOPE" in next(c for c in evidence.coverage if c.domain == "service").gaps


def test_freshness_digest_and_no_cached_evidence(tmp_path):
    tick = [time.time()]
    resolver = current.make_current_resolver(tmp_path, providers=complete_providers(), clock=lambda: tick[0])
    first = resolver(str(tmp_path))
    tick[0] += 1
    second = resolver(str(tmp_path))
    assert first.digest == second.digest
    assert first.observed_at_unix != second.observed_at_unix
    assert not replace(first, observed_at_unix=time.time() - 301).fresh()
    assert not replace(first, observed_at_unix=time.time() + 301).fresh()
    assert replace(first, coverage=first.coverage[:-1]).digest != first.digest


def test_native_defaults_are_actual_providers_but_observation_is_mocked(tmp_path, monkeypatch):
    calls = []
    def native(root, target):
        calls.append((root, target))
        return current.ProbeResult(True, "mock_native", edges=(protected(target),))
    monkeypatch.setattr(current, "_registry", native)
    monkeypatch.setattr(current, "_repositories", native)
    resolver = current.make_current_resolver(tmp_path)
    assert not calls
    evidence = resolver(str(tmp_path))
    assert len(calls) == 2 and not evidence.adapters_complete
    assert not evidence.proofs


def test_repository_provider_reuses_existing_discovery_and_reports_limits(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(current, "attribute_repositories_under", lambda root: calls.append(root) or ())
    result = current._repositories(tmp_path, tmp_path)
    assert calls == [tmp_path] and not result.complete
    assert "DISCOVERY_COMPLETENESS_UNPROVEN" in result.gaps


@pytest.mark.parametrize("nested", [False, True])
def test_windows_registry_reads_four_views_and_retains_partial_protection(tmp_path, monkeypatch, nested):
    if current.os.name != "nt":
        pytest.skip("Windows provider platform admission; no host registry access")
    calls = []
    install = tmp_path / "app" if nested else tmp_path
    if nested:
        install.mkdir()
    class Key:
        def __init__(self, child=False):
            self.child = child
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    def open_key(hive, name, reserved=0, access=0):
        if isinstance(hive, Key):
            return Key(True)
        calls.append((hive, access))
        return Key()
    def query(key, name):
        values = {"DisplayName": "Synthetic App", "InstallLocation": str(install),
                  "UninstallString": '"' + str(tmp_path.parent / "outside.exe") + '"'}
        if name not in values:
            raise FileNotFoundError()
        return values[name], 1
    fake = SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", HKEY_CURRENT_USER="HKCU",
        KEY_WOW64_64KEY=256, KEY_WOW64_32KEY=512, KEY_READ=1, REG_SZ=1, REG_EXPAND_SZ=2,
        OpenKey=open_key, QueryInfoKey=lambda key: (1, 0, 0), EnumKey=lambda key, i: "synthetic",
        QueryValueEx=query)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    result = current._registry(tmp_path, tmp_path)
    assert len(calls) == 4
    assert len(result.edges) == 4
    assert all(e.storage_path == str(install) for e in result.edges)
    assert not result.complete
    assert result.gaps == ("SERVICEABILITY_EXISTENCE_UNRESOLVED_WITHIN_SCOPE",)
    assert not result.app_records


def test_review_snapshot_batches_probes_but_live_calls_stay_fresh(tmp_path):
    calls = []
    now = [time.time()]
    providers = complete_providers()
    def provider(root, target):
        calls.append((root, target))
        return current.ProbeResult(True, "synthetic", edges=(protected(target),))
    providers["repository"] = provider
    resolver = current.make_current_resolver(tmp_path, providers=providers, clock=lambda: now[0])
    snapshot = resolver.review_snapshot()
    assert calls == [(tmp_path, tmp_path)]
    first = snapshot(str(tmp_path))
    now[0] += 2
    second = snapshot(str(tmp_path))
    assert len(calls) == 1
    assert first.observed_at_unix == second.observed_at_unix
    assert first.digest == second.digest
    assert not first.adapters_complete and not first.fresh()
    assert "SNAPSHOT_NOT_MUTATION_EVIDENCE" in first.coverage[-1].gaps
    assert not plan_owner_actions(str(tmp_path), first).raw_delete_eligible
    assert resolver(str(tmp_path)).adapters_complete
    assert resolver(str(tmp_path)).adapters_complete
    assert len(calls) == 3


def test_snapshot_expiration_never_retimestamps_or_reobserves(tmp_path):
    now = [time.time()]
    snapshot = current.make_current_resolver(tmp_path, providers=complete_providers(),
        clock=lambda: now[0]).review_snapshot()
    original = snapshot(str(tmp_path))
    now[0] += 301
    expired = snapshot(str(tmp_path))
    assert expired.observed_at_unix == original.observed_at_unix
    assert expired.coverage[-1].gaps == ("SNAPSHOT_EXPIRED_OR_FUTURE",)
    assert not expired.adapters_complete


def test_snapshot_revalidates_each_path_and_keeps_sibling_owners_separate(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    provider = lambda root, target: current.ProbeResult(True, "root_wide", edges=(protected(one),))
    resolver = current.make_current_resolver(tmp_path, providers={"application_installation": provider})
    snapshot = resolver.review_snapshot()
    assert plan_owner_actions(str(one), snapshot(str(one))).disposition is CleanupDisposition.PROTECTED
    assert plan_owner_actions(str(two), snapshot(str(two))).disposition is CleanupDisposition.UNKNOWN
    outside = snapshot(str(tmp_path.parent))
    assert not outside.graph.edges and outside.coverage[0].domain == "scope"
    one.rmdir()
    assert snapshot(str(one)).coverage[0].domain == "scope"


def test_snapshot_scope_reparse_rechecked_after_capture(tmp_path, monkeypatch):
    snapshot = current.make_current_resolver(tmp_path, providers={}).review_snapshot()
    original = current.Path.lstat
    def linked(path):
        info = original(path)
        if path == tmp_path:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(current.Path, "lstat", linked)
    assert snapshot(str(tmp_path)).coverage[0].domain == "scope"


def test_scoped_existence_missing_leaf_and_parent_are_false(tmp_path):
    assert current._scoped_exists(tmp_path, tmp_path)
    assert not current._scoped_exists(tmp_path / "missing.exe", tmp_path)
    assert not current._scoped_exists(tmp_path / "missing-parent" / "missing.exe", tmp_path)
    with pytest.raises(ValueError, match="OUTSIDE"):
        current._scoped_exists(tmp_path.parent / "outside.exe", tmp_path)


def test_scoped_existence_checks_junction_before_missing_leaf(tmp_path, monkeypatch):
    linked = tmp_path / "junction"
    linked.mkdir()
    original = current.Path.lstat
    def lstat(path):
        info = original(path)
        if path == linked:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(current.Path, "lstat", lstat)
    with pytest.raises(ValueError, match="LINK_OR_REPARSE"):
        current._scoped_exists(linked / "missing.exe", tmp_path)


def test_scoped_existence_access_denied_is_not_missing(tmp_path, monkeypatch):
    original = current.Path.lstat
    def denied(path):
        if path == tmp_path / "denied":
            raise PermissionError()
        return original(path)
    monkeypatch.setattr(current.Path, "lstat", denied)
    with pytest.raises(PermissionError):
        current._scoped_exists(tmp_path / "denied" / "missing.exe", tmp_path)


@pytest.mark.parametrize("junction", [False, True])
def test_missing_registered_serviceability_retains_broken_app_projection(tmp_path, monkeypatch, junction):
    if current.os.name != "nt":
        pytest.skip("Windows provider platform admission; no host registry access")
    from filesteward.visualization.judgment_script import resolve_scene_evidence
    from filesteward.ownership.windows_app import AppLifecycleClass
    class Key:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    def query(key, name):
        values = {"DisplayName": "Synthetic Broken App", "InstallLocation": str(tmp_path),
                  "UninstallString": '"' + str(tmp_path / "missing" / "uninstall.exe") + '"'}
        if name not in values:
            raise FileNotFoundError()
        return values[name], 1
    fake = SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", HKEY_CURRENT_USER="HKCU",
        KEY_WOW64_64KEY=256, KEY_WOW64_32KEY=512, KEY_READ=1, REG_SZ=1, REG_EXPAND_SZ=2,
        OpenKey=lambda *args: Key(), QueryInfoKey=lambda key: (1, 0, 0),
        EnumKey=lambda key, i: "broken-synthetic", QueryValueEx=query)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    if junction:
        linked = tmp_path / "missing"
        linked.mkdir()
        original = current.Path.lstat
        def lstat(path):
            info = original(path)
            if path == linked:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        monkeypatch.setattr(current.Path, "lstat", lstat)
    result = current._registry(tmp_path, tmp_path)
    if junction:
        assert not result.complete and not result.app_records
        assert "SERVICEABILITY_EXISTENCE_UNRESOLVED_WITHIN_SCOPE" in result.gaps
        evidence = current.make_current_resolver(tmp_path,
            providers={"application_installation": lambda *args: result})(str(tmp_path))
        assert plan_owner_actions(str(tmp_path), evidence).disposition is CleanupDisposition.PROTECTED
        return
    assert result.app_records
    assert all(r.lifecycle_class is AppLifecycleClass.BROKEN_REQUIRED for r in result.app_records)
    assert "SERVICEABILITY_EXISTENCE_UNRESOLVED_WITHIN_SCOPE" not in result.gaps
    evidence = current.make_current_resolver(tmp_path,
        providers={"application_installation": lambda *args: result})(str(tmp_path))
    assert evidence.graph.app_records
    projection = resolve_scene_evidence(str(tmp_path), CleanupDisposition.UNKNOWN, evidence)
    assert projection["effective_disposition"] == "PROTECTED"
    assert "APP_BROKEN_REQUIRED" in plan_owner_actions(str(tmp_path), evidence).consequence_classes
    assert projection["ownership_badge"] == "Broken app dependency"
    assert not projection["raw_delete_eligible"]
