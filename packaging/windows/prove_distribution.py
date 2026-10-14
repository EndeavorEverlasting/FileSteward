"""Bounded native launch proof; use only synthetic sample/import evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import PurePosixPath
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import psutil


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from filesteward.runtime_profile import windows_local_app_data


def request(url: str, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    try:
        with urlopen(Request(url, data=data, headers=headers or {}), timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw
    except HTTPError as error:
        raise ValueError(f"HTTP {error.code}: {error.read().decode('utf-8')}") from error


def wait_for(callback, seconds=30):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            result = callback()
            if result:
                return result
        except (OSError, ValueError, KeyError) as error:
            last = error
        time.sleep(.1)
    raise RuntimeError(f"Native launch readiness timed out: {last}")


def stop_owned(process, executable):
    if process.poll() is not None:
        return
    # A windowed startup refusal can leave the onefile child on a dialog.
    # Cleanup is restricted to descendants with this exact transport executable.
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in children:
        try:
            if Path(child.exe()) == executable:
                child.terminate()
        except psutil.NoSuchProcess:
            pass
    process.terminate()
    process.wait(timeout=10)


def prove(distribution: Path, output: Path) -> dict:
    if distribution.is_symlink() or distribution.is_junction():
        raise ValueError("distribution directory cannot be redirected")
    manifest = json.loads((distribution / "distribution-manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["assets"].items():
        if Path(name).name != name:
            raise ValueError("manifest asset name escaped the distribution")
        with (distribution / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("distribution asset digest no longer matches its manifest")
    output.mkdir(parents=True)
    external = Path(tempfile.mkdtemp(prefix="FileSteward native proof " + output.name + " "))
    # Windows executable lookup includes CWD. Evaluate the restricted PATH
    # from the same unrelated, empty directory used for this proof, rather
    # than the runner's virtual-environment Scripts directory.
    os.chdir(external)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    assert shutil.which("python", path=environment["PATH"]) is None
    assert shutil.which("git", path=environment["PATH"]) is None
    runtime = windows_local_app_data() / "FileSteward/runtime/var"
    instance_file = runtime / "launch/instance.json"
    receipt = {"schema_version": "filesteward.native-launch-proof/v1", "status": "RUNNING",
               "distribution": str(distribution), "python_on_child_path": False,
               "external_proof_directory": str(external),
               "version": manifest["version"], "source_head": manifest["source_head"],
               "prototype": manifest["prototype"], "assets": manifest["assets"],
               "git_on_child_path": False, "child_pythonpath": None,
               "proof_ceiling": "native Windows host with child PATH restricted; not a clean Windows VM",
               "modes": []}
    try:
        for mode in ("onedir", "onefile"):
            if instance_file.exists():
                prior = json.loads(instance_file.read_text(encoding="utf-8"))
                try:
                    alive = request(prior["origin"] + "/api/v1/launch/health")
                except (OSError, ValueError):
                    alive = None
                if alive and alive.get("instance_id") == prior.get("instance_id"):
                    raise RuntimeError("An existing native session is active; proof will not interfere")
            transport = external / (mode + " transport with spaces")
            if mode == "onedir":
                # Prove the actual hashed portable download, rather than an
                # unhashed intermediate build directory.
                transport.mkdir()
                with zipfile.ZipFile(distribution / "FileSteward-windows-x64.zip") as archive:
                    for member in archive.infolist():
                        path = PurePosixPath(member.filename)
                        if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
                                or ":" in member.filename or not path.parts or path.parts[0] != "FileSteward"
                                or (member.external_attr >> 16) & 0o170000 == 0o120000):
                            raise ValueError("Portable archive contains an unsafe entry")
                        relative = path.relative_to("FileSteward")
                        target = transport.joinpath(*relative.parts)
                        if not target.resolve().is_relative_to(transport.resolve()):
                            raise ValueError("Portable archive escaped its proof directory")
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with target.open("xb") as stream:
                                stream.write(archive.read(member))
            else:
                transport.mkdir()
                shutil.copyfile(distribution / "FileSteward.exe", transport / "FileSteward.exe")
            executable = transport / "FileSteward.exe"
            unrelated = external / (mode + " unrelated cwd")
            unrelated.mkdir()
            result = {"mode": mode, "transport": str(executable), "cwd": str(unrelated)}
            receipt["modes"].append(result)
            diagnose = subprocess.Popen([str(executable), "--diagnose"], cwd=unrelated, env=environment)
            try:
                result["diagnose_exit"] = diagnose.wait(timeout=30)
                assert result["diagnose_exit"] == 0
            finally:
                stop_owned(diagnose, executable)
            diagnostics = json.loads((runtime / "launch/diagnostics.json").read_text(encoding="utf-8"))
            assert diagnostics["frozen"] is True
            assert Path(diagnostics["runtime_root"]) == runtime
            assert all(diagnostics[key] is False for key in ("scan_started", "deletion_started", "schedule_registered"))
            result["diagnostics"] = diagnostics
            process = subprocess.Popen([str(executable), "--no-browser"], cwd=unrelated, env=environment)
            origin, headers = None, None
            try:
                def ready():
                    instance = json.loads(instance_file.read_text(encoding="utf-8"))
                    owned_pids = {process.pid}
                    try:
                        owned_pids.update(child.pid for child in psutil.Process(process.pid).children(recursive=True))
                    except psutil.NoSuchProcess:
                        pass
                    if instance.get("pid") not in owned_pids:
                        return None
                    health = request(instance["origin"] + "/api/v1/launch/health")
                    return instance if health.get("instance_id") == instance["instance_id"] else None

                instance = wait_for(ready)
                origin = instance["origin"]
                welcome = request(origin + "/")
                matched = re.search(r'<script[^>]+id="launch-runtime"[^>]*>(.*?)</script>', welcome, re.S)
                if not matched:
                    raise ValueError("Welcome runtime payload is absent")
                payload = json.loads(matched.group(1))
                headers = {"Content-Type": "application/json", "Origin": origin,
                           payload["sessionHeader"]: payload["sessionToken"]}
                result["welcome_utf8"] = isinstance(welcome, str) and "__FILESTEWARD_RUNTIME__" not in welcome
                assert result["welcome_utf8"]
                duplicate = subprocess.Popen([str(executable), "--no-browser"], cwd=unrelated, env=environment)
                try:
                    result["duplicate_exit"] = duplicate.wait(timeout=30)
                    assert result["duplicate_exit"] == 0
                finally:
                    stop_owned(duplicate, executable)
                after = json.loads(instance_file.read_text(encoding="utf-8"))
                assert after["instance_id"] == instance["instance_id"] and after["pid"] == instance["pid"]
                result["duplicate_retained_instance_and_pid"] = True
                demo = request(origin + "/api/v1/launch/demo", {}, headers)
                demo_html = request(demo["url"])
                assert "no files on this computer were scanned" in demo_html
                result["demo_opened"] = True
                state = request(origin + "/api/v1/launch/state")
                sample = next(item for item in state["runs"] if item["is_sample"])
                files = [{"name": name, "data": base64.b64encode(
                    (runtime / "runs" / sample["id"] / name).read_bytes()).decode("ascii")}
                    for name in state["allowedImportFiles"]]
                assert len(files) == 6
                imported = request(origin + "/api/v1/launch/import", {"files": files}, headers)
                imported_html = request(imported["url"])
                assert "not a new scan or current deletion authority" in imported_html
                result["synthetic_six_file_import_opened"] = True
                stopped = request(origin + "/api/v1/launch/stop", {}, headers)
                assert stopped["stopped"] is True
                result["stop_exit"] = process.wait(timeout=15)
                assert result["stop_exit"] == 0
            finally:
                if process.poll() is None and origin and headers:
                    try:
                        request(origin + "/api/v1/launch/stop", {}, headers)
                        process.wait(timeout=10)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                stop_owned(process, executable)
        receipt["status"] = "PASS"
    except Exception as error:
        receipt["status"] = "FAIL"
        receipt["error"] = repr(error)
        raise
    finally:
        (output / "native-proof.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution-label", required=True)
    parser.add_argument("--proof-label", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("distribution_build", ROOT / "scripts/build_windows_distribution.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    output = builder.admit_output(ROOT, args.proof_label)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.distribution_label):
        raise ValueError("distribution label must identify one retained build")
    distribution = ROOT / "var/windows-distribution" / args.distribution_label
    prove(distribution, output)
    print(output / "native-proof.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
