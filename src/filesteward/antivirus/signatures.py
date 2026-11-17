"""Admit bounded, locally imported Ed25519 signature bundles."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .matcher import linux_mount_id, open_directory, open_readonly, regular_file, same_opened_file

MAX_BUNDLE_BYTES = 3 * 1024 * 1024
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
DIGEST = re.compile(r"[a-f0-9]{64}")
ENVELOPE = "filesteward.signature-envelope/v1"
PAYLOAD = "filesteward.sha256-signatures/v1"


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return result


@dataclass(frozen=True)
class SignatureBundle:
    sequence: int
    digest: str
    signatures: frozenset[str]


def read_bundle(path: Path) -> bytes:
    with open_directory(path.parent) as (directory, _):
        name = path.name if directory is not None else path
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if not regular_file(info) or info.st_size > MAX_BUNDLE_BYTES:
            raise ValueError("Bundle must be a bounded local regular file")
        with open_readonly(name, directory) as stream:
            opened = os.fstat(stream.fileno())
            if directory is not None and linux_mount_id(stream.fileno()) != linux_mount_id(directory):
                raise ValueError("Bundle crosses a filesystem mount")
            if not regular_file(opened) or not same_opened_file(info, opened):
                raise ValueError("Bundle changed before opening")
            return stream.read(MAX_BUNDLE_BYTES + 1)


def verify_bundle(raw: bytes, key: bytes) -> SignatureBundle:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("Signature bundle exceeds size limit")
    envelope = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(envelope, dict) or set(envelope) != {"schema_version", "payload", "signature"}
            or envelope["schema_version"] != ENVELOPE
            or not all(isinstance(envelope[field], str) for field in ("payload", "signature"))):
        raise ValueError("Invalid signature envelope")
    payload = base64.b64decode(envelope["payload"], validate=True)
    signature = base64.b64decode(envelope["signature"], validate=True)
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("Signature payload exceeds size limit")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, payload)
    except InvalidSignature as exc:
        raise ValueError("Signature did not verify") from exc
    document = json.loads(payload, object_pairs_hook=unique_object)
    if (not isinstance(document, dict) or set(document) != {"schema_version", "sequence", "sha256"}
            or document["schema_version"] != PAYLOAD
            or type(document["sequence"]) is not int
            or not 1 <= document["sequence"] <= 2**63 - 1):
        raise ValueError("Invalid signed signature policy")
    digests = document["sha256"]
    if (not isinstance(digests, list) or not digests
            or any(not isinstance(item, str) or not DIGEST.fullmatch(item) for item in digests)
            or len(set(digests)) != len(digests)):
        raise ValueError("Expected unique SHA-256 digests")
    return SignatureBundle(document["sequence"], hashlib.sha256(payload).hexdigest(), frozenset(digests))
