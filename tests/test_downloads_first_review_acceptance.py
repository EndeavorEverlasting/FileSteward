"""RED-first acceptance for FileSteward's one-click Downloads review.

Implement against the current local server, not a fake replacement scanner.
Expected production adapter: launch.windows_downloads_known_folder() -> Path.
All tests use synthetic directories; no real user Downloads are observed.
These tests must not be xfailed just to claim completion.
"""
from pathlib import Path
import time

import pytest

from filesteward import launch
from test_launch import authorized, request
from test_launch_current_review import current_service, finished


@pytest.fixture
def os_downloads(monkeypatch, tmp_path):
    # Deliberately NOT USERPROFILE/Downloads. No guessed-name fallback passes.
    root = tmp_path / "external-profile" / "Moved Download Collection"
    root.mkdir(parents=True)
    (root / "synthetic-note.txt").write_text("Only synthetic fixture data", encoding="utf-8")
    monkeypatch.setattr(launch, "windows_downloads_known_folder", lambda: root)
    return root


def recommendation(session):
    status, _, result = request(session.origin, "GET", "/api/v1/launch/recommended-scope")
    assert status == 200, result
    return result


def activate(session, token, *, headers=None):
    return request(session.origin, "POST", "/api/v1/launch/current-scan",
                   {"scope_token": token}, authorized(session) if headers is None else headers)


def test_discovery_is_inert_and_uses_os_downloads_not_runtime(current_service, os_downloads):
    session, runtime, collector_calls = current_service
    assert request(session.origin, "GET", "/")[0] == 200
    state = recommendation(session)
    assert state["kind"] == "downloads"
    assert state["display_name"] == "Downloads"
    assert state["display_path"] == str(os_downloads)
    assert state["available"] is True
    assert isinstance(state["scope_token"], str) and state["scope_token"]
    assert collector_calls == []
    assert not list((runtime / "runs").iterdir())
    assert not (os_downloads / "var").exists()


def test_one_authenticated_click_uses_original_scope_and_preserves_files(current_service, os_downloads):
    session, runtime, collector_calls = current_service
    original = (os_downloads / "synthetic-note.txt").read_bytes()
    token = recommendation(session)["scope_token"]
    status, _, started = activate(session, token)
    assert status == 202, started
    outcome = finished(session)
    assert outcome["state"] == "READY", outcome
    assert outcome["item_count"] == 1
    assert collector_calls == [os_downloads]
    assert (os_downloads / "synthetic-note.txt").read_bytes() == original
    assert not (os_downloads / "var").exists()
    assert not list((runtime / "runs" / outcome["run_id"]).glob("*approval*"))
    assert outcome["ownership_complete"] is False


def test_old_token_and_forged_requests_never_trigger_collector(current_service, os_downloads):
    session, runtime, collector_calls = current_service
    token = recommendation(session)["scope_token"]
    assert activate(session, token, headers={})[0] == 403
    assert collector_calls == []
    status, _, result = request(session.origin, "POST", "/api/v1/launch/current-scan",
        {"scope_token": "attacker-made", "eligible": True, "scan_root": str(os_downloads)},
        authorized(session))
    assert status == 400, result
    assert collector_calls == []
    # Unauthorized use does not consume the real scope token.
    assert activate(session, token)[0] == 202
    assert finished(session)["state"] == "READY"
    assert activate(session, token)[0] == 400
    assert collector_calls == [os_downloads]


def test_downloads_redirection_between_display_and_click_fails_closed(
        current_service, os_downloads, monkeypatch, tmp_path):
    session, runtime, collector_calls = current_service
    token = recommendation(session)["scope_token"]
    replacement = tmp_path / "different-downloads"
    replacement.mkdir()
    monkeypatch.setattr(launch, "windows_downloads_known_folder", lambda: replacement)
    status, _, _ = activate(session, token)
    assert status == 400
    assert collector_calls == []
    assert not list((runtime / "runs").iterdir())


@pytest.mark.parametrize("bad_case", ["missing", "forbidden", "linked", "volume_root", "resolver_error"])
def test_unsafe_or_unavailable_downloads_has_no_primary_scan(
        current_service, monkeypatch, tmp_path, bad_case):
    session, runtime, collector_calls = current_service
    if bad_case == "missing":
        location = tmp_path / "not-created"
    elif bad_case == "forbidden":
        location = tmp_path / "OneDrive" / "Downloads"
        location.mkdir(parents=True)
    elif bad_case == "linked":
        real = tmp_path / "source"
        real.mkdir()
        location = tmp_path / "link"
        try:
            location.symlink_to(real, target_is_directory=True)
        except (NotImplementedError, OSError):
            pytest.skip("Creating a synthetic linked directory is unavailable on this host")
    elif bad_case == "volume_root":
        location = Path(tmp_path.anchor)
    else:
        location = None

    if bad_case == "resolver_error":
        def unavailable():
            raise RuntimeError("KnownFolder API unavailable")
        monkeypatch.setattr(launch, "windows_downloads_known_folder", unavailable)
    else:
        monkeypatch.setattr(launch, "windows_downloads_known_folder", lambda: location)
    candidate = recommendation(session)
    assert candidate["available"] is False
    assert candidate.get("reason")
    assert not candidate.get("scope_token")
    assert collector_calls == []
    assert not list((runtime / "runs").iterdir())


def test_concurrent_review_requests_cannot_spawn_second_job(current_service, os_downloads):
    session, runtime, collector_calls = current_service
    token = recommendation(session)["scope_token"]
    status, _, _ = activate(session, token)
    assert status == 202
    # Single-use token is rejected whether first job is still running or complete.
    assert activate(session, token)[0] == 400
    assert finished(session)["state"] == "READY"
    assert collector_calls == [os_downloads]


@pytest.mark.parametrize("mode,width", [("desktop", 1440), ("narrow", 390),
                                        ("reduced", 1440), ("forced", 1440)])
def test_one_click_browser_journey_needs_no_path_entry_or_second_open(
        current_service, os_downloads, mode, width):
    api = pytest.importorskip("playwright.sync_api")
    session, _, collector_calls = current_service
    original = (os_downloads / "synthetic-note.txt").read_bytes()
    with api.sync_playwright() as driver:
        browser = driver.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 950},
                reduced_motion="reduce" if mode == "reduced" else "no-preference",
                forced_colors="active" if mode == "forced" else "none")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(session.origin, wait_until="networkidle")
            assert collector_calls == []
            assert page.locator("#review-downloads").is_visible()
            assert page.locator("#review-downloads").is_enabled()
            assert os_downloads.name in page.locator("body").inner_text()
            assert not page.locator("#scan-root").is_visible()
            if mode == "narrow":
                page.locator("#review-downloads").focus()
                page.keyboard.press("Enter")
            else:
                page.locator("#review-downloads").click()
            # No second click on Open current review; auto-transition to real Atlas.
            page.locator("#storage-stage").wait_for(timeout=20000)
            assert collector_calls == [os_downloads]
            assert not errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            assert (os_downloads / "synthetic-note.txt").read_bytes() == original
        finally:
            browser.close()
