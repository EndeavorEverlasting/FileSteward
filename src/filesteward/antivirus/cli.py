"""Public FileSteward detector commands and the status-only scheduler interface."""
from __future__ import annotations

import argparse
import json
import sqlite3
from functools import cache
from importlib.resources import files
from pathlib import Path

from . import profile


@cache
def _detector_contract() -> dict:
    resource = files("filesteward").joinpath("contracts", "antivirus-detection.v1.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def add_parser(subparsers) -> None:
    antivirus = subparsers.add_parser("antivirus", help="opt in to local SHA-256 content inspection")
    actions = antivirus.add_subparsers(dest="antivirus_action", required=True)
    actions.add_parser("contract", help="print the versioned public detector semantics")
    configure = actions.add_parser("configure", help="approve one local directory and signing key")
    configure.add_argument("--root", type=Path, required=True)
    configure.add_argument("--public-key", required=True, help="32-byte Ed25519 public key in lowercase hex")
    configure.add_argument("--bundle", type=Path, required=True)
    for command, help_text in (
        ("check", "validate the local detector profile without reading scan files"),
        ("run", "execute the detector and return completion status only"),
        ("review", "display historical exact-match evidence locally"),
        ("signature-update", "import a newer locally signed signature bundle"),
    ):
        action = actions.add_parser(command, help=help_text)
        action.add_argument("--profile", required=True)
        if command == "signature-update":
            action.add_argument("--bundle", type=Path, required=True)


def dispatch(args: argparse.Namespace) -> int:
    action = args.antivirus_action
    contract = _detector_contract()
    if action == "contract":
        print(json.dumps(contract, indent=2))
        return 0
    exit_codes = contract["scheduler"]["exit_codes"]
    quiet = action in {"run", "check"}
    try:
        if action == "configure":
            print(json.dumps({"profile": profile.configure(args.root, args.public_key, args.bundle.absolute())}))
        elif action == "signature-update":
            print(json.dumps({"sequence": profile.update(args.profile, args.bundle.absolute())}))
        elif action == "review":
            print(json.dumps(profile.review(args.profile), indent=2))
        else:
            complete = profile.run(args.profile, validate_only=action == "check")
            return exit_codes["COMPLETED" if complete else "INCOMPLETE"]
    except (ValueError, RecursionError):
        status = "POLICY_REJECTED"
    except ImportError:
        status = "DEPENDENCY_UNAVAILABLE"
    except (OSError, RuntimeError, sqlite3.Error):
        status = "LOCAL_STATE_UNAVAILABLE"
    else:
        return exit_codes["COMPLETED"]
    if not quiet:
        print(json.dumps({"status": {
            "DEPENDENCY_UNAVAILABLE": "INSTALL_ANTIVIRUS_EXTRA",
        }.get(status, status)}))
    return exit_codes[status]
