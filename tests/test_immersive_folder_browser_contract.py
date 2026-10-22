"""Retained static governance tests for the browser-first welcome contract.

Behavioral and Windows runtime proof is owned by the separate API/Playwright
tests. These static checks prevent later agents from silently restoring a
native-chooser-first onboarding flow or accepting user-submitted scan paths.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "harness/contracts/immersive-folder-browser.v1.json"
WELCOME = ROOT / "src/filesteward/web/launch.html"
LAUNCH = ROOT / "src/filesteward/launch.py"


def test_embedded_navigator_is_primary_without_changing_scan_authority():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["contract_id"] == "filesteward.immersive-folder-browser/v1"
    assert contract["experience"]["primary"] == "embedded_accessible_directory_navigator"
    assert contract["experience"]["fallback"] == "existing_native_Windows_folder_picker"
    assert contract["endpoints"]["no_client_absolute_paths"] is True
    assert contract["enforcement"]["exclude_file_names"] is True
    assert contract["enforcement"]["no_recursive_listing"] is True
    assert contract["enforcement"]["selection_inert"] is True
    assert contract["endpoints"]["token_policy"]["ttl_seconds"] <= 600


def test_browser_controls_and_backend_are_separate_from_scan_activation():
    html = WELCOME.read_text(encoding="utf-8")
    source = LAUNCH.read_text(encoding="utf-8")
    ids = ("browse-folders", "browser-panel", "browser-items", "browser-path",
           "browser-home", "browser-back", "browser-next", "browser-close",
           "browser-select", "review-selected", "choose-folder")
    for element_id in ids:
        assert f'id="{element_id}"' in html
    assert "Browse folders here" in html
    assert "Windows folder picker" in html
    assert "const browserRequest = body => request('/api/v1/launch/folder-browser', body)" in html
    assert "byId('browser-select').addEventListener" in html
    assert "byId('review-selected').addEventListener" in html
    assert "def folder_browser(self, payload):" in source
    assert "session.folder_browser(payload)" in source
    assert 'self._offer_scope(scope.root, "selected")' in source
    assert "self.begin_current_scan(payload)" not in source[source.index("    def folder_browser("):source.index("    def _consume_scope(")]
