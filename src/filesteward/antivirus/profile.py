"""Own local detector scope, signature trust, and review persistence."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from filesteward.models import AuthorizationState, CleanupDisposition
from filesteward.policy.paths import is_lexically_within, runtime_root
from filesteward.runtime_profile import initialize_installed_runtime, resolve_installed_runtime

from .matcher import open_directory, regular_file, scan_directory, scope_identity
from .signatures import DIGEST, read_bundle, verify_bundle

SCHEMA = """
CREATE TABLE policy (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    configuration TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    bundle BLOB NOT NULL
);
CREATE TABLE review (
    path BLOB NOT NULL,
    sha256 TEXT NOT NULL,
    bundle_sequence INTEGER NOT NULL,
    bundle_sha256 TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (path, sha256)
);
"""


def state_root(*, create: bool = False) -> Path:
    runtime = runtime_root()
    state = runtime / "antivirus"
    if create:
        if not runtime.parent.exists():
            # A marked installation can be admitted before its first launch.
            installed = resolve_installed_runtime()
            if runtime != installed.runtime_root:
                raise ValueError("Detector runtime differs from the admitted installation")
            initialize_installed_runtime(installed.application_root)
        with open_directory(runtime.parent):
            runtime.mkdir(exist_ok=True, mode=0o700)
        with open_directory(runtime):
            state.mkdir(exist_ok=True, mode=0o700)
    with open_directory(state) as (_, info):
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError("Antivirus state must be private to the current account")
    return state


def configure(scope: Path, public_key: str, bundle_path: Path) -> str:
    if not DIGEST.fullmatch(public_key):
        raise ValueError("Expected a raw Ed25519 public key in lowercase hex")
    state = state_root(create=True)
    if is_lexically_within(scope, state) or is_lexically_within(state, scope):
        raise ValueError("The approved scope must exclude detector state")
    fingerprint = scope_identity(scope)
    raw_bundle = read_bundle(bundle_path)
    bundle = verify_bundle(raw_bundle, bytes.fromhex(public_key))
    config = json.dumps({
        "scope": str(scope), "identity": fingerprint, "public_key": public_key,
        "nonce": secrets.token_hex(32),
    }, sort_keys=True)
    profile = hashlib.sha256(config.encode()).hexdigest()
    location = state / profile
    location.mkdir(mode=0o700)
    db_path = location / "detector.sqlite"
    db_path.touch(mode=0o600, exist_ok=False)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO policy VALUES (1, ?, ?, ?)", (config, bundle.sequence, raw_bundle))
    return profile


@contextmanager
def profile_state(profile: str):
    if not DIGEST.fullmatch(profile):
        raise ValueError("Invalid detector profile")
    location = state_root() / profile
    path = location / "detector.sqlite"
    with open_directory(location) as (_, info):
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError("Detector profile must be private")
        entry = path.lstat()
        if not regular_file(entry) or (
            os.name != "nt" and (entry.st_uid != os.getuid() or entry.st_mode & 0o077)
        ):
            raise ValueError("Invalid detector database")
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True, timeout=0.5)) as db, db:
        # Serialize a scan, receipt and signature update for this profile.
        db.execute("BEGIN IMMEDIATE")
        config, sequence, raw_bundle = db.execute(
            "SELECT configuration, sequence, bundle FROM policy WHERE id = 1"
        ).fetchone() or ("", 0, b"")
        if hashlib.sha256(config.encode()).hexdigest() != profile:
            raise ValueError("Detector profile configuration changed")
        configuration = json.loads(config)
        key = bytes.fromhex(configuration["public_key"])
        bundle = verify_bundle(raw_bundle, key)
        if bundle.sequence != sequence:
            raise ValueError("Detector signature sequence changed")
        yield db, configuration, key, bundle


def update(profile: str, bundle_path: Path) -> int:
    raw = read_bundle(bundle_path)
    with profile_state(profile) as (db, _, key, current):
        candidate = verify_bundle(raw, key)
        if candidate.sequence <= current.sequence:
            raise ValueError("Signature update must advance the trusted sequence")
        db.execute("UPDATE policy SET sequence = ?, bundle = ? WHERE id = 1",
                   (candidate.sequence, raw))
    return candidate.sequence


def run(profile: str, *, validate_only: bool = False) -> bool:
    with profile_state(profile) as (db, config, _, bundle):
        scope = Path(config["scope"])
        expected = tuple(config["identity"])
        if scope_identity(scope) != expected:
            raise ValueError("Approved directory identity changed")
        if validate_only:
            return True
        matches, complete = scan_directory(scope, expected, bundle.signatures)
        observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        db.executemany("""
            INSERT INTO review VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path, sha256) DO UPDATE SET
              bundle_sequence=excluded.bundle_sequence, bundle_sha256=excluded.bundle_sha256,
              observed_at=excluded.observed_at
            """, ((os.fsencode(scope / name), digest, bundle.sequence, bundle.digest, observed)
                  for name, digest in matches))
    return complete


def review(profile: str) -> list[dict]:
    with profile_state(profile) as (db, _, _, _):
        rows = db.execute(
            "SELECT path, sha256, bundle_sequence, bundle_sha256, observed_at FROM review "
            "ORDER BY observed_at DESC, path, sha256"
        )
        return [{
            "disposition": CleanupDisposition.HUMAN_REVIEW.value,
            "authorization_state": AuthorizationState.UNAPPROVED.value,
            "evidence": "EXACT_SHA256_MATCH",
            "path": os.fsdecode(path),
            "sha256": digest,
            "bundle_sequence": sequence,
            "bundle_sha256": bundle_digest,
            "observed_at_utc": observed,
        } for path, digest, sequence, bundle_digest, observed in rows]
