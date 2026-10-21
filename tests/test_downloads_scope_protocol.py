"""Synthetic HTTP regressions for server-owned scope capabilities and admission."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from filesteward import launch
from filesteward.review_bridge import SESSION_HEADER
from test_launch import authorized, request
from test_launch_current_review import current_service, finished


@pytest.fixture
def synthetic_downloads(tmp_path, monkeypatch):
    root = tmp_path / 'synthetic-profile' / 'OS registered collection'
    root.mkdir(parents=True)
    (root / 'synthetic-record.txt').write_text('Retain these synthetic bytes')
    monkeypatch.setattr(launch, 'windows_downloads_known_folder', lambda: root)
    return root


def offer(session):
    status, _, payload = request(session.origin, 'GET', '/api/v1/launch/recommended-scope')
    assert status == 200 and payload['available'], payload
    return payload['scope_token']


def activate(session, token, headers=None):
    return request(session.origin, 'POST', '/api/v1/launch/current-scan',
                   {'scope_token': token}, authorized(session) if headers is None else headers)


@pytest.mark.parametrize('age,accepted', [(599.999, True), (600, False), (601, False), (-1, False)])
def test_scope_clock_expiry_and_rollback_fail_closed(current_service, synthetic_downloads, age, accepted):
    session, runtime, calls = current_service
    tick = [1000.0]
    session.scope_clock = lambda: tick[0]
    token = offer(session)
    tick[0] += age
    response = activate(session, token)
    assert response[0] == (202 if accepted else 400), response
    if accepted:
        assert finished(session)['state'] == 'READY'
        assert calls == [synthetic_downloads]
    else:
        assert calls == [] and not list((runtime / 'runs').iterdir())
    assert activate(session, token)[0] == 400


@pytest.mark.parametrize('token', [None, [], {}, 12, True, '', 'x' * 257])
def test_malformed_token_is_controlled_refusal(current_service, synthetic_downloads, token):
    session, runtime, calls = current_service
    real = offer(session)
    status, _, body = activate(session, token)
    assert status == 400 and body.get('error')
    assert calls == [] and real in session.scope_tokens
    assert not list((runtime / 'runs').iterdir())


def test_discovery_storage_bounded_and_expired_offers_evicted(current_service, synthetic_downloads):
    session, runtime, calls = current_service
    tick = [10.0]
    session.scope_clock = lambda: tick[0]
    tokens = [offer(session) for _ in range(70)]
    assert len(set(tokens)) == 70
    assert len(session.scope_tokens) <= 64
    assert tokens[0] not in session.scope_tokens and tokens[-1] in session.scope_tokens
    assert calls == [] and not list((runtime / 'runs').iterdir())
    tick[0] += 600
    fresh = offer(session)
    assert set(session.scope_tokens) == {fresh}
    assert activate(session, tokens[-1])[0] == 400
    assert calls == []


def test_session_and_restart_cannot_replay_prior_capability(current_service, synthetic_downloads):
    original, runtime, calls = current_service
    token = offer(original)
    other, thread = launch.start_server(runtime, resolver_factory=lambda root: pytest.fail('foreign token started collector'))
    try:
        assert activate(other, token)[0] == 400
        assert not other.current_runs and not list((runtime / 'runs').iterdir())
        assert token in original.scope_tokens
    finally:
        other.server.shutdown(); other.server.server_close(); other.close(); thread.join(timeout=3)
    # New process/session dictionaries are not populated from captured artifacts.
    assert calls == []
    assert activate(original, token)[0] == 202
    assert finished(original)['state'] == 'READY'


@pytest.mark.parametrize('replace_parent', [False, True])
def test_same_path_directory_or_ancestor_substitution_refused(
        current_service, synthetic_downloads, replace_parent):
    session, runtime, calls = current_service
    token = offer(session)
    subject = synthetic_downloads.parent if replace_parent else synthetic_downloads
    preserved = subject.with_name(subject.name + '-preserved-synthetic')
    assert subject.parent == preserved.parent
    subject.rename(preserved)
    synthetic_downloads.mkdir(parents=True)
    assert activate(session, token)[0] == 400
    assert calls == [] and not list((runtime / 'runs').iterdir())


def test_original_scope_not_recaptured_between_consume_and_worker(
        current_service, synthetic_downloads, monkeypatch):
    session, runtime, calls = current_service
    token = offer(session)
    original_scope = session.scope_tokens[token][1]
    consume = session._consume_scope

    def substitute_after_validation(value):
        scope = consume(value)
        assert scope is original_scope
        preserved = synthetic_downloads.with_name('preserved-before-worker')
        assert preserved.parent == synthetic_downloads.parent
        synthetic_downloads.rename(preserved)
        synthetic_downloads.mkdir()
        return scope

    monkeypatch.setattr(session, '_consume_scope', substitute_after_validation)
    status, _, started = activate(session, token)
    assert status == 202, started
    assert finished(session)['state'] == 'ERROR'
    assert calls == [] and not session.current_runs


@pytest.mark.parametrize('fault', ['missing', 'origin', 'host', 'session'])
def test_auth_rejection_neither_opens_picker_nor_consumes_token(
        current_service, synthetic_downloads, monkeypatch, fault):
    session, runtime, calls = current_service
    picker_calls = []
    monkeypatch.setattr(launch, 'pick_windows_folder', lambda: picker_calls.append(True))
    token = offer(session)
    headers = authorized(session)
    if fault == 'missing':
        headers = {}
    elif fault == 'origin':
        headers['Origin'] = 'https://untrusted.invalid'
    elif fault == 'host':
        headers['Host'] = 'untrusted.invalid'
    else:
        headers[SESSION_HEADER] = 'wrong-session'
    assert activate(session, token, headers)[0] == 403
    assert request(session.origin, 'POST', '/api/v1/launch/choose-folder',
                   {'intent': 'choose'}, headers)[0] == 403
    assert picker_calls == [] and calls == [] and token in session.scope_tokens
    assert not list((runtime / 'runs').iterdir())


@pytest.mark.parametrize('same_token', [True, False])
def test_concurrent_activation_has_one_worker(current_service, synthetic_downloads, same_token):
    session, runtime, calls = current_service
    first = offer(session)
    second = first if same_token else offer(session)
    entered, release, barrier = threading.Event(), threading.Event(), threading.Barrier(2)
    factory = session.resolver_factory

    def blocked(root):
        entered.set()
        assert release.wait(3), 'test failed to release synthetic collector'
        return factory(root)

    session.resolver_factory = blocked
    def submit(token):
        barrier.wait(timeout=3)
        return activate(session, token)[0]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit, token) for token in (first, second)]
            statuses = sorted(f.result(timeout=4) for f in futures)
            assert statuses == [202, 400]
            assert entered.wait(2)
    finally:
        release.set()
    assert finished(session)['state'] == 'READY'
    assert calls == [synthetic_downloads]
    assert len(list((runtime / 'runs').iterdir())) == 1


def test_picker_serializes_scan_and_other_picker_without_auto_scan(
        current_service, synthetic_downloads, monkeypatch):
    session, runtime, calls = current_service
    token = offer(session)
    entered, release = threading.Event(), threading.Event()
    picker_calls = []
    def picker():
        picker_calls.append(True); entered.set()
        assert release.wait(3)
        return None
    monkeypatch.setattr(launch, 'pick_windows_folder', picker)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(request, session.origin, 'POST', '/api/v1/launch/choose-folder',
                                  {'intent': 'choose'}, authorized(session))
            assert entered.wait(2)
            assert request(session.origin, 'POST', '/api/v1/launch/choose-folder',
                           {'intent': 'choose'}, authorized(session))[0] == 400
            assert activate(session, token)[0] == 400
            assert request(session.origin, 'POST', '/api/v1/launch/stop', {}, authorized(session))[0] == 400
            release.set()
            result = pending.result(timeout=4)
            assert result[0] == 200 and result[2]['state'] == 'CANCELED'
    finally:
        release.set()
    assert picker_calls == [True] and calls == [] and not session.stopping
    assert not list((runtime / 'runs').iterdir())


def test_selected_scope_does_not_follow_downloads_redirection(
        current_service, synthetic_downloads, monkeypatch, tmp_path):
    session, runtime, calls = current_service
    selected = tmp_path / 'synthetic-selected-folder'
    selected.mkdir()
    monkeypatch.setattr(launch, 'pick_windows_folder', lambda: selected)
    status, _, result = request(session.origin, 'POST', '/api/v1/launch/choose-folder',
                               {'intent': 'choose'}, authorized(session))
    assert status == 200 and result['scan_started'] is False
    monkeypatch.setattr(launch, 'windows_downloads_known_folder', lambda: tmp_path / 'moved-downloads')
    assert activate(session, result['scope_token'])[0] == 202
    assert finished(session)['state'] == 'EMPTY'
    assert calls == [selected]


@pytest.mark.parametrize('failure', ['NO_INTERACTIVE_DESKTOP', 'PICKER_UNAVAILABLE'])
def test_native_picker_failure_returns_actionable_json_and_releases_reservation(
        current_service, synthetic_downloads, monkeypatch, failure):
    session, runtime, calls = current_service
    token = offer(session)
    def unavailable():
        raise RuntimeError(failure + ': synthetic adapter cannot open a dialog')
    monkeypatch.setattr(launch, 'pick_windows_folder', unavailable)
    status, _, result = request(session.origin, 'POST', '/api/v1/launch/choose-folder',
                               {'intent': 'choose'}, authorized(session))
    assert status == 400 and failure in result.get('error', '')
    assert not session.scan_lock.locked() and calls == []
    assert token in session.scope_tokens and not list((runtime / 'runs').iterdir())


@pytest.mark.parametrize('kind', ['missing', 'forbidden'])
def test_picker_selection_still_requires_canonical_admission(
        current_service, synthetic_downloads, monkeypatch, tmp_path, kind):
    session, runtime, calls = current_service
    selected = tmp_path / ('OneDrive' if kind == 'forbidden' else 'missing') / 'selected'
    if kind == 'forbidden':
        selected.mkdir(parents=True)
    original_tokens = set(session.scope_tokens)
    monkeypatch.setattr(launch, 'pick_windows_folder', lambda: selected)
    status, _, result = request(session.origin, 'POST', '/api/v1/launch/choose-folder',
                               {'intent': 'choose'}, authorized(session))
    assert status == 400 and result.get('error')
    assert set(session.scope_tokens) == original_tokens and not session.scan_lock.locked()
    assert calls == [] and not list((runtime / 'runs').iterdir())


def test_mixed_client_scope_claims_cannot_consume_real_token(current_service, synthetic_downloads):
    session, runtime, calls = current_service
    token = offer(session)
    for additions in ({'scan_root': str(synthetic_downloads)}, {'eligible': True}, {'kind': 'selected'}):
        status, _, result = request(session.origin, 'POST', '/api/v1/launch/current-scan',
                                   {'scope_token': token, **additions}, authorized(session))
        assert status == 400 and result.get('error')
        assert token in session.scope_tokens
    assert calls == [] and not list((runtime / 'runs').iterdir())
