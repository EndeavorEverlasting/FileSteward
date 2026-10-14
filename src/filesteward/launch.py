"""One local entry point: welcome, explicit sample/import, and managed reviews.

Startup never scans, classifies live paths, deletes, or registers a schedule.
Imported files are observational artifacts only; approvals are not imported.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen
import uuid
import webbrowser

from filesteward import __version__
from filesteward.manifest import validate_run
from filesteward.policy.paths import (prove_run_dir_under_runtime, run_dir, runtime_root,
    is_symlink_or_reparse, repository_root)
from filesteward.review_bridge import SESSION_HEADER, serve_review
from filesteward.sample import write_sample_run
from filesteward.visualization.report import visualize_run_dir
from filesteward.visualization.html import write_report_html_atomically

IMPORT_FILES = frozenset({"inventory.csv", "human-review.csv", "cleanup-plan.csv",
    "protected-exclusions.csv", "cleanup-summary.md", "run.json"})
MAX_IMPORT_BYTES = 32 * 1024 * 1024
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def prepare_runtime() -> Path:
    if getattr(sys, "frozen", False):
        from filesteward.runtime_profile import initialize_installed_runtime
        return initialize_installed_runtime().runtime_root
    try:
        repository_root()
    except RuntimeError:
        from filesteward.runtime_profile import initialize_installed_runtime
        return initialize_installed_runtime().runtime_root
    target = runtime_root()
    target.mkdir(parents=True, exist_ok=True)
    (target / "runs").mkdir(exist_ok=True)
    return target


def _write_json(path: Path, payload: dict) -> None:
    if is_symlink_or_reparse(path) or is_symlink_or_reparse(path.parent):
        raise ValueError("Refusing a linked application metadata path")
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    os.replace(temp, path)


class InstanceLock:
    def __init__(self, path: Path):
        self.path, self.stream = path, None

    def acquire(self) -> bool:
        if is_symlink_or_reparse(self.path) or is_symlink_or_reparse(self.path.parent):
            raise ValueError("Refusing a linked application lock")
        self.stream = self.path.open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0"); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close(); self.stream = None
            return False
        return True

    def close(self) -> None:
        if self.stream:
            self.stream.close(); self.stream = None


class LaunchSession:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.session_token = secrets.token_urlsafe(32)
        self.instance_id = uuid.uuid4().hex
        self.origin = ""
        self.reviews = {}
        self.lock = threading.RLock()
        self.server = None

    def candidate(self, identifier: str) -> Path:
        if not isinstance(identifier, str) or not RUN_ID.fullmatch(identifier):
            raise ValueError("Choose a saved FileSteward review")
        return prove_run_dir_under_runtime(run_dir(identifier))

    def recent(self) -> list[dict]:
        runs = self.state_root / "runs"
        result = []
        for target in runs.iterdir():
            try:
                self.candidate(target.name)
                marker = target / ".launch-run.json"
                if is_symlink_or_reparse(marker):
                    continue
                data = json.loads(marker.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("schema_version") != "filesteward.launch-run/v1":
                    continue
                result.append(dict(id=target.name, run_id=data["run_id"], title=data["title"],
                    is_sample=data.get("is_sample") is True, saved_at=marker.stat().st_mtime_ns))
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return sorted(result, key=lambda entry: entry["saved_at"], reverse=True)[:100]

    def sample(self) -> str:
        identifier = "sample-" + __version__.replace(".", "-")
        with self.lock:
            target = self.candidate(identifier)
            if target.exists() and not (target / ".launch-run.json").exists():
                # Preserve an interrupted/unrecognized directory. An explicit
                # sample request may create a fresh synthetic run instead.
                identifier += "-" + uuid.uuid4().hex[:12]
                target = self.candidate(identifier)
            if not target.exists():
                write_sample_run(target, identifier)
                _write_json(target / ".launch-run.json", dict(
                    schema_version="filesteward.launch-run/v1", run_id=identifier,
                    title="Illustrative sample", is_sample=True))
            return self.open_review(identifier)

    def import_run(self, files: object) -> str:
        if not isinstance(files, list) or len(files) != len(IMPORT_FILES):
            raise ValueError("Select the six root-level FileSteward evidence files")
        decoded, total = {}, 0
        for file in files:
            if not isinstance(file, dict) or set(file) != {"name", "data"}:
                raise ValueError("Invalid evidence upload")
            name = file["name"]
            if not isinstance(name, str) or name not in IMPORT_FILES or name in decoded:
                raise ValueError("Only distinct observational artifacts may be imported")
            if not isinstance(file["data"], str):
                raise ValueError("Evidence must be base64 encoded")
            raw = base64.b64decode(file["data"], validate=True)
            total += len(raw)
            if total > MAX_IMPORT_BYTES:
                raise ValueError("This preview accepts evidence folders up to 32 MiB")
            decoded[name] = raw
        identifier = "import-" + uuid.uuid4().hex
        target = self.candidate(identifier)
        target.mkdir()
        created = []
        try:
            for name, raw in decoded.items():
                path = target / name
                with path.open("xb") as stream:
                    identity = os.fstat(stream.fileno())
                    created.append((path, identity.st_dev, identity.st_ino))
                    stream.write(raw)
            errors = validate_run(target)
            if errors:
                raise ValueError("Imported evidence did not pass validation: " + "; ".join(errors[:3]))
            metadata = json.loads((target / "run.json").read_text(encoding="utf-8"))
            _write_json(target / ".launch-run.json", dict(schema_version="filesteward.launch-run/v1",
                run_id=metadata["run_id"], title="Imported review", is_sample=False))
        except Exception:
            # These are this request's transient copies, never source files.
            # Remove only exact created objects; preserve substituted/linked
            # paths and unknown additions rather than recursively deleting.
            if not is_symlink_or_reparse(target):
                for path, device, inode in created:
                    try:
                        current = path.lstat()
                        if not is_symlink_or_reparse(path) and (current.st_dev, current.st_ino) == (device, inode):
                            path.unlink()
                    except OSError:
                        pass
                try:
                    target.rmdir()
                except OSError:
                    pass
            raise
        return self.open_review(identifier)

    def open_review(self, identifier: str) -> str:
        with self.lock:
            target = self.candidate(identifier)
            if identifier not in self.reviews:
                marker = json.loads((target / ".launch-run.json").read_text(encoding="utf-8"))
                if not isinstance(marker, dict) or marker.get("schema_version") != "filesteward.launch-run/v1":
                    raise ValueError("Saved review identity is invalid")
                errors = validate_run(target)
                if errors:
                    raise ValueError("Saved review no longer passes validation")
                result = visualize_run_dir(target)
                html = result.report_path.read_text(encoding="utf-8")
                sample = marker.get("is_sample") is True
                label = ("Sample data - no files on this computer were scanned. Storage figures are illustrative."
                    if sample else "Imported captured evidence - not a new scan or current deletion authority.")
                banner = '<nav style="padding:14px 24px;background:#fffaf1;border-bottom:1px solid #c8b8a4">' \
                    + '<a href="' + escape(self.origin, quote=True) + '/">Back to launch</a> &middot; ' + escape(label) + '</nav>'
                html = html.replace("<body>", "<body>" + banner, 1)
                if sample:
                    html = html.replace("Observed storage", "Example storage").replace("Run baseline free space", "Example free space")
                write_report_html_atomically(result.report_path, html)
                self.reviews[identifier] = serve_review(target, open_browser=False,
                    regenerate_report=False, observation_only=True)
            return self.origin + "/review/" + identifier

    def close(self) -> None:
        for review in list(self.reviews.values()):
            review.server.shutdown(); review.server.server_close(); review.thread.join(timeout=2)


def start_server(state_root: Path, port: int = 0) -> tuple[LaunchSession, threading.Thread]:
    session = LaunchSession(state_root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def handle(self):
            try:
                super().handle()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                self.close_connection = True

        def send(self, status, payload, content_type="application/json; charset=utf-8"):
            if self.command == "POST" and not getattr(self, "body_consumed", False):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if 0 < length <= 65536:
                        previous_timeout = self.connection.gettimeout()
                        try:
                            self.connection.settimeout(.25)
                            self.rfile.read(length)
                        finally:
                            self.connection.settimeout(previous_timeout)
                except (ValueError, OSError):
                    pass
                self.body_consumed = True
            data = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers(); self.wfile.write(data)

        def admitted(self):
            return self.headers.get("Host") == urlparse(session.origin).netloc

        def do_GET(self):
            if not self.admitted():
                return self.send(403, {"error":"Host must match the local app"})
            path = urlparse(self.path).path
            if path == "/favicon.ico":
                return self.send(204, "", "image/x-icon")
            if path == "/":
                runtime = dict(version=__version__, origin=session.origin,
                    sessionToken=session.session_token, sessionHeader=SESSION_HEADER,
                    allowedImportFiles=sorted(IMPORT_FILES))
                html = resources.files("filesteward").joinpath("web", "launch.html").read_text(encoding="utf-8")
                html = html.replace("__FILESTEWARD_VERSION__", __version__).replace(
                    "__FILESTEWARD_RUNTIME__", json.dumps(runtime).replace("<", "\\u003c"))
                return self.send(200, html, "text/html; charset=utf-8")
            if path == "/api/v1/launch/health":
                return self.send(200, dict(app_id="filesteward", version=__version__, instance_id=session.instance_id))
            if path == "/api/v1/launch/state":
                return self.send(200, dict(version=__version__, runs=session.recent(), allowedImportFiles=sorted(IMPORT_FILES)))
            if path.startswith("/review/"):
                identifier = path[len("/review/"):]
                try:
                    session.open_review(identifier)
                    location = session.reviews[identifier].url
                except (ValueError, OSError, TypeError, KeyError):
                    return self.send(400, {"error":"This review could not be opened"})
                self.send_response(302); self.send_header("Location", location)
                self.send_header("Content-Length", "0"); self.end_headers(); return
            return self.send(404, {"error":"Not found"})

        def do_POST(self):
            if (not self.admitted() or self.headers.get("Origin") != session.origin
                    or not hmac.compare_digest(self.headers.get(SESSION_HEADER, ""), session.session_token)):
                self.close_connection = True
                return self.send(403, {"error":"The local session identity did not match"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_IMPORT_BYTES * 2:
                    raise ValueError("Request size exceeds this preview's evidence limit")
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("JSON evidence request required")
                self.connection.settimeout(15)
                raw = self.rfile.read(length)
                self.body_consumed = True
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("A request object is required")
                path = urlparse(self.path).path
                if path == "/api/v1/launch/demo":
                    return self.send(200, {"url":session.sample()})
                if path == "/api/v1/launch/import":
                    return self.send(200, {"url":session.import_run(payload.get("files"))})
                if path == "/api/v1/launch/open":
                    return self.send(200, {"url":session.open_review(payload.get("run_id"))})
                if path == "/api/v1/launch/stop":
                    self.send(200, {"stopped":True})
                    threading.Thread(target=session.server.shutdown, daemon=True).start()
                    return
                return self.send(404, {"error":"Not found"})
            except (ValueError, OSError, TypeError, KeyError) as error:
                return self.send(400, {"error":str(error)})

        def do_OPTIONS(self):
            self.send(403, {"error":"Cross-origin requests are not permitted"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    session.server = server
    session.origin = "http://127.0.0.1:" + str(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return session, thread


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="FileSteward", description="Open the local FileSteward welcome app")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        if sys.stdout:
            print("FileSteward " + __version__)
        return 0
    if not 0 <= args.port <= 65535:
        return 2
    state_root = prepare_runtime()
    launch_root = state_root / "launch"
    if is_symlink_or_reparse(launch_root):
        raise ValueError("Refusing a linked launch directory")
    launch_root.mkdir(exist_ok=True)
    logging.basicConfig(filename=launch_root / "launch.log", level=logging.INFO, encoding="utf-8")
    if args.diagnose:
        _write_json(launch_root / "diagnostics.json", dict(app_id="filesteward", version=__version__,
            runtime_root=str(state_root), frozen=bool(getattr(sys,"frozen",False)),
            scan_started=False, deletion_started=False, schedule_registered=False))
        return 0
    lock = InstanceLock(launch_root / "instance.lock")
    if not lock.acquire():
        for _ in range(30):
            try:
                prior = json.loads((launch_root / "instance.json").read_text(encoding="utf-8"))
                url = prior["origin"]
                parsed = urlparse(url)
                if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path:
                    raise ValueError("Invalid existing app address")
                with urlopen(url + "/api/v1/launch/health", timeout=1) as response:
                    health = json.load(response)
                if health.get("app_id") == "filesteward" and health.get("instance_id") == prior["instance_id"]:
                    if not args.no_browser:
                        webbrowser.open(url)
                    return 0
            except (OSError, ValueError, KeyError):
                time.sleep(.1)
        raise RuntimeError("FileSteward is already running but its local session could not be reached")
    session = None
    try:
        session, thread = start_server(state_root, args.port)
        _write_json(launch_root / "instance.json", dict(app_id="filesteward", version=__version__,
            instance_id=session.instance_id, origin=session.origin, pid=os.getpid(),
            scan_started=False, deletion_started=False, schedule_registered=False))
        if sys.stdout:
            print(session.origin, flush=True)
        if not args.no_browser:
            webbrowser.open(session.origin)
        while thread.is_alive():
            thread.join(.5)
    except KeyboardInterrupt:
        pass
    finally:
        if session:
            session.server.shutdown(); session.server.server_close(); session.close()
        lock.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logging.exception("FileSteward startup failed")
        if os.name == "nt" and not sys.stderr:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "FileSteward could not start", 0x10)
        else:
            print(str(error), file=sys.stderr)
        raise SystemExit(2)
