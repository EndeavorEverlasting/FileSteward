"""Public FileSteward detector commands and the status-only scheduler interface."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from . import profile

COMPLETED = 0
STATE_UNAVAILABLE = 1
INCOMPLETE = 10
POLICY_REJECTED = 12
DEPENDENCY_UNAVAILABLE = 13


def add_parser(subparsers) -> None:
    antivirus = subparsers.add_parser("antivirus", help="opt in to local SHA-256 content inspection")
    actions = antivirus.add_subparsers(dest="antivirus_action", required=True)
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
    quiet = action in {"run", "check"}
    try:
        if action == "configure":
            print(json.dumps({"profile": profile.configure(args.root, args.public_key, args.bundle.absolute())}))
        elif action == "signature-update":
            print(json.dumps({"sequence": profile.update(args.profile, args.bundle.absolute())}))
        elif action == "review":
            print(json.dumps(profile.review(args.profile), indent=2))
        else:
            return COMPLETED if profile.run(args.profile, validate_only=action == "check") else INCOMPLETE
    except (ValueError, RecursionError):
        status = POLICY_REJECTED
    except ImportError:
        status = DEPENDENCY_UNAVAILABLE
    except (OSError, RuntimeError, sqlite3.Error):
        status = STATE_UNAVAILABLE
    else:
        return COMPLETED
    if not quiet:
        print(json.dumps({"status": {
            POLICY_REJECTED: "POLICY_REJECTED",
            DEPENDENCY_UNAVAILABLE: "INSTALL_ANTIVIRUS_EXTRA",
            STATE_UNAVAILABLE: "LOCAL_STATE_UNAVAILABLE",
        }[status]}))
    return status
