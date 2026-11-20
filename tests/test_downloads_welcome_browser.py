"""Real local APIs and browser actions; OS seams point only at synthetic folders."""
from contextlib import contextmanager
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from filesteward import launch
from filesteward.policy import paths
from filesteward.ownership.current import make_current_resolver, ProbeResult


@pytest.fixture
def downloads_app(tmp_path, monkeypatch):
    root = tmp_path / "synthetic-downloads"
    root.mkdir()
    (root / "synthetic-note.txt").write_text("Metadata-only synthetic fixture", encoding="utf-8")
    alternate = tmp_path / "chosen-synthetic-folder"
    alternate.mkdir()
    (alternate / "chosen-record.txt").write_text("Preserve this fixture", encoding="utf-8")
    runtime = tmp_path / "private-runtime" / "var"
    (runtime / "runs").mkdir(parents=True)
    monkeypatch.setattr(paths, "runtime_root", lambda: runtime)
    control = SimpleNamespace(root=root, alternate=alternate, runtime=runtime,
        known=root, picked=None, calls=[], entered=threading.Event(), release=threading.Event())
    control.release.set()

    def known_folder():
        if isinstance(control.known, Exception):
            raise control.known
        return control.known

    monkeypatch.setattr(launch, "windows_downloads_known_folder", known_folder, raising=False)
    monkeypatch.setattr(launch, "pick_windows_folder", lambda: control.picked, raising=False)

    def factory(root):
        control.calls.append(root)
        control.entered.set()
        assert control.release.wait(10), "synthetic scan pause exceeded its bounded test interval"
        return make_current_resolver(root, providers={"service": lambda admitted, target:
            ProbeResult(False, "synthetic_service_probe", ("SYNTHETIC_COVERAGE_GAP",))})

    session, thread = launch.start_server(runtime, resolver_factory=factory)
    control.session = session
    try:
        yield control
    finally:
        control.release.set()
        deadline = time.monotonic() + 5
        while session.scan_lock.locked() and time.monotonic() < deadline:
            time.sleep(.01)
        session.server.shutdown()
        session.server.server_close()
        session.close()
        thread.join(timeout=3)


@contextmanager
def browser_page(width=1440, *, mode="desktop"):
    api = pytest.importorskip("playwright.sync_api")
    with api.sync_playwright() as driver:
        browser = driver.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 1000},
                reduced_motion="reduce" if mode == "reduced" else "no-preference",
                forced_colors="active" if mode == "forced" else "none",
                has_touch=mode == "touch")
            errors, scans, actions = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def observe(request):
                if request.method == "POST":
                    actions.append(request.url)
                    if request.url.endswith("/api/v1/launch/current-scan"):
                        scans.append(request.post_data_json)

            page.on("request", observe)
            yield api, page, errors, scans, actions
        finally:
            browser.close()


def output_path(name):
    output = Path(__file__).resolve().parents[1] / "var/runs/downloads-welcome-browser"
    output.mkdir(parents=True, exist_ok=True)
    return str(output / name)


@pytest.mark.parametrize("mode,width", [("desktop", 1440), ("narrow", 390),
    ("keyboard", 1440), ("touch", 390), ("reduced", 1440), ("forced", 1440)])
def test_one_disclosed_downloads_activation_reads_once_and_enters_review(downloads_app, mode, width):
    app = downloads_app
    before = (app.root / "synthetic-note.txt").read_bytes()
    with browser_page(width, mode=mode) as (api, page, errors, scans, actions):
        page.goto(app.session.origin, wait_until="networkidle")
        api.expect(page.locator("#review-downloads")).to_be_enabled()
        api.expect(page.locator("#recommended-path")).to_contain_text(str(app.root))
        api.expect(page.locator("#current-title")).to_have_text("Start with Downloads")
        assert app.calls == [] and scans == []
        assert not list((app.runtime / "runs").iterdir())
        assert page.locator("#scan-root").count() == 0
        assert page.locator("#open-current").count() == 0
        assert page.locator("#review-downloads").bounding_box()["y"] < 1000
        assert page.locator("#demo").bounding_box()["y"] < 1000
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.screenshot(path=output_path(mode + "-welcome.png"), full_page=True)
        app.release.clear()
        if mode == "keyboard":
            page.locator("#review-downloads").focus()
            page.locator("#review-downloads").press("Enter")
        elif mode == "touch":
            page.locator("#review-downloads").tap()
        else:
            page.locator("#review-downloads").click()
        assert app.entered.wait(3)
        api.expect(page.locator("#main")).to_have_attribute("aria-busy", "true")
        api.expect(page.locator("#review-downloads")).to_be_disabled()
        api.expect(page.locator("#scan-result")).to_contain_text("Reading Downloads metadata")
        assert len(scans) == 1 and set(scans[0]) == {"scope_token"}
        assert "%" not in page.locator("#scan-result").inner_text()
        app.release.set()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert app.calls == [app.root] and len(scans) == 1
        assert not any(url.endswith(("/api/v1/delete", "/api/v1/approval")) for url in actions)
        assert (app.root / "synthetic-note.txt").read_bytes() == before
        assert not errors


def test_native_picker_cancel_is_noop_selection_waits_for_separate_review(downloads_app):
    app = downloads_app
    with browser_page() as (api, page, errors, scans, _):
        page.goto(app.session.origin, wait_until="networkidle")
        page.locator("#choose-folder").click()
        api.expect(page.locator("#status")).to_contain_text("No folder selected")
        assert not scans and not app.calls
        assert page.locator("#chosen-scope").is_hidden()
        app.picked = app.alternate
        page.locator("#choose-folder").click()
        api.expect(page.locator("#chosen-path")).to_contain_text(str(app.alternate))
        api.expect(page.locator("#review-selected")).to_be_enabled()
        assert not scans and not app.calls
        assert page.evaluate("document.activeElement.id") == "chosen-title"
        page.locator("#review-selected").click()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert app.calls == [app.alternate]
        assert len(scans) == 1 and set(scans[0]) == {"scope_token"}
        assert not errors


def test_unavailable_downloads_keeps_alternate_and_sample_without_fallback_scan(downloads_app):
    app = downloads_app
    app.known = OSError("SYNTHETIC_KNOWN_FOLDER_UNAVAILABLE")
    with browser_page() as (api, page, errors, scans, _):
        page.goto(app.session.origin, wait_until="networkidle")
        api.expect(page.locator("#review-downloads")).to_be_disabled()
        api.expect(page.locator("#recommended-state")).to_contain_text("Downloads is not available")
        api.expect(page.locator("#choose-folder")).to_be_enabled()
        api.expect(page.locator("#demo")).to_be_enabled()
        page.locator("#demo").click()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert not app.calls and not scans
        assert "Sample data" in page.locator("body").inner_text()
        assert not errors


def test_replaced_downloads_refuses_then_refreshes_without_automatic_retry(downloads_app, tmp_path):
    app = downloads_app
    with browser_page() as (api, page, errors, scans, _):
        page.goto(app.session.origin, wait_until="networkidle")
        api.expect(page.locator("#review-downloads")).to_be_enabled()
        app.root.rename(tmp_path / "preserved-downloads")
        app.root.mkdir()
        (app.root / "replacement.txt").write_text("new synthetic directory")
        page.locator("#review-downloads").click()
        api.expect(page.locator("#error")).to_be_visible()
        api.expect(page.locator("#review-downloads")).to_be_enabled()
        assert "changed" in page.locator("#error").inner_text().lower()
        assert page.evaluate("document.activeElement.id") == "error"
        assert len(scans) == 1 and not app.calls
        assert not list((app.runtime / "runs").iterdir())
        # Discovery supplied a new capability but did not retry the review.
        page.locator("#review-downloads").click()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert len(scans) == 2 and app.calls == [app.root]
        assert not errors


def test_empty_downloads_opens_without_second_activation(downloads_app):
    app = downloads_app
    (app.root / "synthetic-note.txt").unlink()
    with browser_page() as (api, page, errors, scans, _):
        page.goto(app.session.origin, wait_until="networkidle")
        api.expect(page.locator("#review-downloads")).to_be_enabled()
        page.locator("#review-downloads").click()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert app.session.scan_job["state"] == "EMPTY"
        assert len(scans) == 1 and app.calls == [app.root]
        assert not errors


def test_partial_metadata_opens_automatically_with_destination_warning(downloads_app, monkeypatch):
    from filesteward.inventory.scan import ScanDeps
    app = downloads_app
    denied = app.root / "unreadable-synthetic-folder"
    denied.mkdir()
    original_run = launch.CleanupRun

    def partial_run(*args, **kwargs):
        admitted_scandir = kwargs["scan_deps"].scandir

        def scandir(path):
            # Preserve scope revalidation even when injecting a read failure.
            iterator = admitted_scandir(path)
            if Path(path) == denied:
                iterator.close()
                raise PermissionError("SYNTHETIC_METADATA_GAP")
            return iterator

        kwargs["scan_deps"] = ScanDeps(scandir=scandir)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(launch, "CleanupRun", partial_run)
    with browser_page() as (api, page, errors, scans, _):
        page.goto(app.session.origin, wait_until="networkidle")
        api.expect(page.locator("#review-downloads")).to_be_enabled()
        page.locator("#review-downloads").click()
        page.locator("#storage-stage").wait_for(timeout=15000)
        assert app.session.scan_job["state"] == "PARTIAL"
        assert len(scans) == 1 and app.calls == [app.root]
        assert "partial" in page.locator("body").inner_text().lower()
        assert not errors


def test_welcome_markup_uses_disclosed_scope_capabilities_and_no_manual_path():
    source = (Path(__file__).resolve().parents[1] / "src/filesteward/web/launch.html").read_text(encoding="utf-8")
    assert 'id="review-downloads"' in source
    assert 'id="choose-folder"' in source
    assert 'id="review-selected"' in source
    assert 'id="scan-root"' not in source
    assert 'id="open-current"' not in source
    assert "{scope_token:token}" in source
    assert "request('/api/v1/launch/choose-folder', {intent:'choose'})" in source
    assert "request('/api/v1/launch/open', {run_id:result.run_id})" in source
    assert "byId('recommended-path').textContent" in source
    assert 'role="alert"' in source and 'tabindex="-1"' in source
