#!/usr/bin/env python3
"""Build a traceable Windows distribution into a fresh ignored output directory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8").strip()


def admit_output(root: Path, label: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", label):
        raise ValueError("output label must be one simple directory name")
    parent = root / "var" / "windows-distribution"
    for path in (root / "var", parent):
        if path.is_symlink() or path.is_junction() or (path.exists() and not path.is_dir()):
            raise ValueError("output ancestors must be ordinary directories")
    output = parent / label
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; choose a new label to preserve prior proof")
    if not output.resolve().is_relative_to(root.resolve()):
        raise ValueError("output escaped the checkout")
    return output


def render_bootstrap(template: str, version: str, exe_hash: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not re.fullmatch(r"[0-9a-f]{64}", exe_hash):
        raise ValueError("bootstrap requires a product version and exact executable SHA256")
    return template.replace("@VERSION@", version).replace("@EXE_SHA256@", exe_hash)


def source_identity(root: Path) -> dict[str, str]:
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", root=root).split("\0")
    return {
        name: sha256(root / name) for name in sorted(set(paths))
        if (name.startswith(("src/", "packaging/windows/"))
            or name in {"pyproject.toml", "LICENSE", "scripts/build_windows_distribution.py"})
        and (root / name).is_file()
    }


def collect_notices(root: Path, target: Path) -> None:
    target.mkdir()
    (target / "FileSteward-MIT.txt").write_bytes((root / "LICENSE").read_bytes())
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise ValueError("Python runtime LICENSE.txt is required")
    (target / "Python.txt").write_bytes(python_license.read_bytes())
    for package in ("pyinstaller", "pyinstaller-hooks-contrib", "psutil", "altgraph", "packaging", "pefile", "pywin32-ctypes", "setuptools"):
        distribution = importlib.metadata.distribution(package)
        included = 0
        for entry in distribution.files or ():
            if entry.name.lower().startswith(("license", "copying")):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    (target / f"{package}-{str(entry).replace('/', '_')}").write_bytes(source.read_bytes())
                    included += 1
        if not included:
            raise ValueError(f"dependency license text is missing: {package}")
    (target / "README.txt").write_text(
        "FileSteward bundles Python and psutil. Build/runtime dependency license texts are included.\n"
        "PyInstaller's bootloader distribution exception permits packaged applications; see its license.\n",
        encoding="utf-8",
    )


def build(label: str, *, prototype: bool = False, root: Path = ROOT) -> Path:
    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise ValueError("build requires native Windows x64")
    dirty = git("status", "--porcelain", "--untracked-files=all", root=root)
    if dirty and not prototype:
        raise ValueError("public release builds require a clean source HEAD; --prototype is local proof only")
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not (root / "src/filesteward/launch.py").is_file():
        raise ValueError("package launcher is required before building")
    output = admit_output(root, label)
    identity = source_identity(root)
    source_head = git("rev-parse", "HEAD", root=root)
    output.mkdir(parents=True)
    notices = output / "licenses"
    collect_notices(root, notices)
    build_info = output / "build-info.json"
    build_info.write_text(json.dumps({"schema_version": "filesteward.build-info/v1",
                                      "app_id": "filesteward", "package_version": version,
                                      "runtime_profile": "windows-localappdata/v1",
                                      "source_commit": source_head,
                                      "prototype": prototype}, indent=2) + "\n", encoding="utf-8")
    tool_versions = {name: importlib.metadata.version(name) for name in ("pyinstaller", "setuptools", "psutil")}
    common = [sys.executable, "-m", "PyInstaller", "--windowed", "--name", "FileSteward",
              "--paths", str(root / "src"), "--collect-all", "filesteward", "--collect-all", "psutil",
              "--add-data", f"{notices};licenses", "--add-data", f"{build_info};filesteward/contracts",
              "--specpath", str(output / "spec")]
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    for mode in ("onedir", "onefile"):
        command = common + [f"--{mode}", "--distpath", str(output / mode), "--workpath", str(output / f"work-{mode}"),
                            str(root / "packaging/windows/entrypoint.py")]
        with (output / f"build-{mode}.log").open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        executable = output / mode / ("FileSteward/FileSteward.exe" if mode == "onedir" else "FileSteward.exe")
        # A bounded startup mode must succeed before progressing to the next bundle.
        subprocess.run([str(executable), "--version"], cwd=output, check=True, timeout=30)
        if source_identity(root) != identity or git("rev-parse", "HEAD", root=root) != source_head:
            raise ValueError("source changed during the build; retained outputs are not release proof")
    executable = output / "FileSteward.exe"
    executable.write_bytes((output / "onefile/FileSteward.exe").read_bytes())
    bootstrap = render_bootstrap((root / "packaging/windows/FileSteward.cmd.in").read_text(encoding="utf-8"), version, sha256(executable))
    (output / "FileSteward.cmd").write_text(bootstrap, encoding="utf-8", newline="\r\n")
    archive = output / "FileSteward-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted((output / "onedir").rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output / "onedir").as_posix())
    assets = (executable, output / "FileSteward.cmd", archive)
    hashes = {path.name: sha256(path) for path in assets}
    (output / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="ascii")
    manifest = {"schema_version": "filesteward.windows-distribution/v1", "version": version,
                "source_head": source_head, "prototype": prototype,
                "source_dirty": bool(dirty), "dirty_status": dirty, "python": sys.version,
                "source_files_sha256": identity,
                "platform": platform.platform(), "tools": tool_versions, "assets": hashes,
                "release_tag": f"v{version}", "proof": "onedir and onefile --version exits succeeded",
                "publication": "NOT_PUBLISHED"}
    (output / "distribution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--prototype", action="store_true")
    args = parser.parse_args()
    try:
        print(build(args.label, prototype=args.prototype))
    except (ValueError, subprocess.SubprocessError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"Windows distribution build refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
