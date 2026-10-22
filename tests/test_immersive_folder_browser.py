"""Directory-only in-app chooser: synthetic HTTP, token and safety regression tests."""
import pytest
from filesteward import launch
from test_launch import authorized, request
from test_launch_current_review import current_service, finished


def browse(session, payload, headers=None):
    return request(session.origin, 'POST', '/api/v1/launch/folder-browser',
                   payload, authorized(session) if headers is None else headers)


@pytest.fixture
def browser_sandbox(tmp_path, monkeypatch):
    root = tmp_path / 'Synthetic Profile'
    root.mkdir()
    downloads = root / 'Downloads'
    downloads.mkdir()
    nested = downloads / 'Music Archive'
    nested.mkdir()
    (downloads / 'private-file-do-not-display.txt').write_text('Synthetic private bytes')
    (nested / 'keep.mp3').write_bytes(b'not real audio')
    (downloads / 'Desktop').mkdir()
    (downloads / 'OneDrive').mkdir()
    monkeypatch.setattr(launch, 'windows_downloads_known_folder', lambda: downloads)
    monkeypatch.setattr(launch.Path, 'home', lambda: root)
    return root, downloads, nested


def find_downloads(session):
    status, _, roots = browse(session, {'action':'roots'})
    assert status == 200 and roots['state'] == 'ROOTS'
    assert roots['scan_started'] is False
    token = next(item['token'] for item in roots['locations'] if item['label'] == 'Downloads')
    return token


def test_folder_browser_explicit_selection_then_explicit_scan(current_service, browser_sandbox):
    session, runtime, calls = current_service
    _, downloads, nested = browser_sandbox
    token = find_downloads(session)
    assert calls == [] and not list((runtime / 'runs').iterdir())
    status, _, view = browse(session, {'action':'open','token':token,'page':0})
    assert status == 200 and view['state'] == 'FOLDERS'
    assert view['can_select'] and view['scan_started'] is False
    assert [item['name'] for item in view['folders']] == ['Music Archive']
    assert 'private-file-do-not-display.txt' not in str(view)
    assert 'Desktop' not in str(view) and 'OneDrive' not in str(view)
    child = view['folders'][0]['token']
    status, _, child_view = browse(session, {'action':'open','token':child,'page':0})
    assert status == 200 and child_view['path'] == str(nested)
    assert child_view['folders'] == []
    status, _, selected = browse(session, {'action':'select','token':child})
    assert status == 200 and selected['state'] == 'SELECTED'
    assert selected['display_path'] == str(nested) and selected['scan_started'] is False
    assert calls == [] and not list((runtime / 'runs').iterdir())
    assert browse(session, {'action':'open','token':selected['scope_token'],'page':0})[0] == 400
    status, _, started = request(session.origin, 'POST', '/api/v1/launch/current-scan',
                                {'scope_token':selected['scope_token']}, authorized(session))
    assert status == 202 and started['state'] == 'READING'
    assert finished(session)['state'] == 'READY'
    assert calls == [nested]


def test_browser_rejects_client_paths_and_unauthorized_sessions(current_service, browser_sandbox):
    session, runtime, calls = current_service
    token = find_downloads(session)
    for injection in [
        {'action':'open','path':'C:\\','page':0},
        {'action':'select','path':'C:\\'},
        {'action':'open','token':token,'page':True},
        {'action':'open','token':token,'page':-1},
        {'action':'roots','scan_root':'C:\\'},
        {'action':'select','token':token,'eligible':True},
    ]:
        status, _, body = browse(session, injection)
        assert status == 400 and body.get('error')
    status, _, _ = browse(session, {'action':'select','token':token}, headers={})
    assert status == 403
    assert calls == [] and not list((runtime / 'runs').iterdir())


def test_browser_stale_directory_identity_fails_closed(current_service, browser_sandbox):
    session, runtime, calls = current_service
    _, downloads, _ = browser_sandbox
    token = find_downloads(session)
    downloads.rename(downloads.with_name('DownloadsMoved'))
    for payload in ({'action':'open','token':token,'page':0},
                    {'action':'select','token':token}):
        status, _, body = browse(session, payload)
        assert status == 400 and body.get('error')
    assert calls == [] and not list((runtime / 'runs').iterdir())


def test_browser_token_timeout_and_restart_behavior(current_service, browser_sandbox):
    session, runtime, calls = current_service
    clock = [1000.0]
    session.scope_clock = lambda: clock[0]
    token = find_downloads(session)
    clock[0] += 600
    assert browse(session, {'action':'open','token':token,'page':0})[0] == 400
    assert browse(session, {'action':'select','token':token})[0] == 400
    assert calls == []


def test_browser_downloads_unavailable_still_offers_profile(current_service, browser_sandbox, monkeypatch):
    session, runtime, calls = current_service
    def missing():
        raise RuntimeError('Simulated Downloads KnownFolder is unavailable')
    monkeypatch.setattr(launch, 'windows_downloads_known_folder', missing)
    status, _, roots = browse(session, {'action':'roots'})
    assert status == 200 and roots['state'] == 'ROOTS'
    assert any(item['label'] == 'Your profile' for item in roots['locations'])
    assert all(item['label'] != 'Downloads' for item in roots['locations'])
    assert calls == []


def test_browser_does_not_start_scan_during_selection_or_navigation(current_service, browser_sandbox):
    session, runtime, calls = current_service
    token = find_downloads(session)
    for _ in range(2):
        assert browse(session, {'action':'open','token':token,'page':0})[0] == 200
    assert browse(session, {'action':'select','token':token})[0] == 200
    assert session.scan_job is None and calls == []
    assert not list((runtime / 'runs').iterdir())
